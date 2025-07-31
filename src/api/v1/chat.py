"""
对话API接口
"""
from typing import Dict, Any
from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from fastapi.responses import JSONResponse
import time
import uuid
import json

from src.schemas.chat import (
    ChatRequest, ChatResponse, SessionMetadata, IntentCandidate,
    DisambiguationRequest, DisambiguationResponse
)
from src.schemas.common import StandardResponse
from src.services.intent_service import IntentService
from src.services.slot_service import SlotService
from src.services.conversation_service import ConversationService
from src.services.function_service import FunctionService
from src.services.ragflow_service import RagflowService
from src.services.cache_service import CacheService
from src.api.dependencies import get_intent_service, get_conversation_service
from src.utils.logger import get_logger
from src.utils.response_transformer import get_response_transformer, ResponseType
#from src.utils.security import verify_token
from src.models.conversation import Conversation, IntentAmbiguity

logger = get_logger(__name__)
router = APIRouter(prefix="/chat", tags=["对话接口"])


@router.post("/test")
async def test_endpoint(request: ChatRequest):
    """测试端点，用于调试JSON序列化问题"""
    return {
        "message": "测试成功",
        "received_user_id": request.user_id,
        "received_input": request.input,
        "received_session_id": request.session_id
    }


@router.get("/simple")
async def simple_test():
    """最简单的测试端点，无依赖"""
    return {"status": "ok", "message": "simple test working"}


@router.post("/interact", response_model=StandardResponse[ChatResponse])
async def chat_interact(
    request: ChatRequest,
    background_tasks: BackgroundTasks,
    intent_service: IntentService = Depends(get_intent_service),
    conversation_service: ConversationService = Depends(get_conversation_service)
):
    """
    智能对话处理接口
    
    实现混合架构设计的核心对话处理逻辑：
    1. 查询会话历史对话和槽位状态
    2. 基于历史上下文的意图识别和置信度评估
    3. 多轮对话的槽位累积和验证
    4. 意图转移和打岔处理
    5. 条件式API调用
    6. RAGFLOW集成
    7. 对话状态持久化
    """
    start_time = time.time()
    request_id = f"req_{int(time.time())}_{uuid.uuid4().hex[:8]}"
    
    try:
        logger.info(f"收到对话请求: {request_id}, 用户: {request.user_id}")
        
        # 1. 输入安全校验和预处理
        sanitized_input = await _sanitize_user_input(request.input)
        
        # 2. 获取或创建会话，并加载历史对话上下文
        session_context = await conversation_service.get_or_create_session(
            request.user_id, session_id=request.session_id, context=request.context
        )
        
        # 3. 加载历史对话和当前槽位状态（关键改进）
        conversation_history = await conversation_service.get_conversation_history(
            session_context['session_id'], limit=10  # 获取最近10轮对话
        )
        
        current_slot_values = await conversation_service.get_current_slot_values(
            session_context['session_id']
        )
        
        # V2.2 bug修复：将对话历史设置到session_context中供槽位补充检查使用
        session_context['conversation_history'] = conversation_history
        session_context['current_slots'] = current_slot_values
        
        # 4. 计算当前对话轮次
        current_turn = len(conversation_history) + 1
        session_context['current_turn'] = current_turn
        session_context['conversation_history'] = conversation_history
        session_context['current_slots'] = current_slot_values
        session_id = session_context['session_id']
        
        # 5. 优先处理上下文相关的输入
        
        # 5.1 检查是否存在待处理的歧义，如果有则尝试解决
        disambiguation_result = await conversation_service.try_resolve_disambiguation_with_input(
            session_id, sanitized_input
        )
        
        if disambiguation_result:
            # 歧义已解决，使用解决的意图继续处理
            logger.info(f"歧义已通过用户输入解决: {disambiguation_result['intent_name']}")
            
            # 获取解决的意图对象
            resolved_intent = await intent_service._get_intent_by_name(disambiguation_result['intent_name'])
            if resolved_intent:
                from src.schemas.intent_recognition import IntentRecognitionResult
                intent_result = IntentRecognitionResult(
                    intent=resolved_intent,
                    confidence=disambiguation_result['confidence'],
                    is_ambiguous=False,
                    alternatives=[]
                )
            else:
                # 如果找不到意图对象，回退到正常识别
                intent_result = await intent_service.recognize_intent_with_history(
                    sanitized_input, request.user_id, session_context, conversation_history
                )
        else:
            # 5.2 检查是否是对缺失槽位的补充（优先级高于新意图识别）
            slot_supplement_result = await _try_handle_slot_supplement(
                sanitized_input, session_context, conversation_service, intent_service, session_id
            )
            
            if slot_supplement_result:
                # 槽位补充成功，直接返回结果，跳过后续的意图识别
                response = slot_supplement_result
                
                # 记录对话历史
                processing_time = int((time.time() - start_time) * 1000)
                
                # 构建槽位补充的intent_result
                from src.schemas.intent_recognition import IntentRecognitionResult
                supplement_intent = await intent_service._get_intent_by_name(slot_supplement_result.intent)
                if supplement_intent:
                    final_intent_result = IntentRecognitionResult(
                        intent=supplement_intent,
                        confidence=slot_supplement_result.confidence,
                        is_ambiguous=False,
                        alternatives=[]
                    )
                else:
                    final_intent_result = None
                
                background_tasks.add_task(
                    _save_conversation_record,
                    request.user_id, session_id, sanitized_input,
                    final_intent_result, response, processing_time, request_id, current_turn
                )
                
                # 构建标准响应
                transformer = get_response_transformer()
                return transformer.chat_to_standard(response, request_id)
            
            # 5.3 没有待处理的歧义也没有槽位补充，进行正常的意图识别
            intent_result = await intent_service.recognize_intent_with_history(
                sanitized_input, request.user_id, session_context, conversation_history
            )
        
        # 6. 处理意图识别结果（槽位补充已在前面处理）
        if intent_result.is_ambiguous:
            # 处理意图歧义
            response = await _handle_intent_ambiguity(
                intent_result, sanitized_input, session_context, conversation_service
            )
        elif intent_result.intent is None:
            # 检查是否是确认响应
            confirmation_result = await _try_handle_confirmation_response(
                sanitized_input, session_context, conversation_service, intent_service
            )
            
            if confirmation_result:
                response = confirmation_result
            else:
                # 非意图输入，调用RAGFLOW
                response = await _handle_non_intent_input(
                    sanitized_input, session_context, conversation_service
                )
        else:
            # 明确的意图识别，检查是否是确认响应
            confirmation_result = await _try_handle_confirmation_response(
                sanitized_input, session_context, conversation_service, intent_service
            )
            
            if confirmation_result:
                response = confirmation_result
            else:
                # 进行槽位处理
                response = await _handle_clear_intent(
                    intent_result, sanitized_input, session_context, 
                    intent_service, conversation_service
                )
        
        # 7. 记录对话历史（包含轮次信息）
        processing_time = int((time.time() - start_time) * 1000)
        
        background_tasks.add_task(
            _save_conversation_record,
            request.user_id, session_id, sanitized_input,
            intent_result, response, processing_time, request_id, current_turn
        )
        
        # 8. 构建标准响应 - 使用统一转换器
        transformer = get_response_transformer()
        return transformer.chat_to_standard(response, request_id)
        
    except Exception as e:
        logger.error(f"对话处理失败: {request_id}, 错误: {str(e)}")
        
        # 记录错误对话
        background_tasks.add_task(
            _save_error_conversation,
            request.user_id, request.input, str(e), request_id
        )
        
        # 使用统一转换器处理错误响应
        transformer = get_response_transformer()
        return transformer.error_to_standard(
            "服务暂时不可用，请稍后重试",
            "SERVICE_UNAVAILABLE",
            request_id=request_id
        )


async def _sanitize_user_input(user_input: str) -> str:
    """
    用户输入安全校验和清理
    
    Args:
        user_input: 原始用户输入
        
    Returns:
        str: 清理后的用户输入
    """
    # 基本安全校验：移除潜在的恶意字符
    import re
    
    # 移除SQL注入相关字符
    sanitized = re.sub(r'[;<>\'\"\\]', '', user_input)
    
    # 限制长度
    if len(sanitized) > 1000:
        sanitized = sanitized[:1000]
    
    # 移除多余空白
    sanitized = sanitized.strip()
    
    if not sanitized:
        raise HTTPException(status_code=400, detail="输入不能为空")
    
    return sanitized


async def _handle_intent_ambiguity(intent_result, user_input: str, 
                                 session_context: Dict, 
                                 conversation_service: ConversationService) -> ChatResponse:
    """
    处理意图歧义
    
    Args:
        intent_result: 意图识别结果
        user_input: 用户输入
        session_context: 会话上下文
        conversation_service: 对话服务
        
    Returns:
        ChatResponse: 歧义处理响应
    """
    # 生成歧义澄清问题
    candidates_list = [f"{i+1}. {alt.display_name}" for i, alt in enumerate(intent_result.alternatives)]
    disambiguation_question = f"您是想要：\n" + "\n".join(candidates_list) + "\n\n请输入对应的数字或者重新描述您的需求。"
    
    # 记录意图歧义
    await conversation_service.record_intent_ambiguity(
        session_context['session_id'], user_input, [
            {'intent_name': alt.intent_name, 'display_name': alt.display_name, 'confidence': alt.confidence}
            for alt in intent_result.alternatives
        ]
    )
    
    return ChatResponse(
        response=disambiguation_question,
        session_id=session_context['session_id'],
        conversation_turn=session_context.get('current_turn', 1),
        intent=None,
        confidence=0.0,
        slots={},
        status="ambiguous",
        response_type="disambiguation",
        next_action="user_choice",
        ambiguous_intents=[
            IntentCandidate(
                intent_name=alt.intent_name,
                display_name=alt.display_name or alt.intent_name,
                confidence=alt.confidence,
                description=alt.reasoning
            ) for alt in intent_result.alternatives
        ],
        session_metadata=SessionMetadata(
            total_turns=session_context.get('current_turn', 1),
            session_duration_seconds=0
        )
    )


async def _handle_non_intent_input(user_input: str, session_context: Dict,
                                 conversation_service: ConversationService) -> ChatResponse:
    """
    处理非意图输入（RAGFLOW处理）
    
    Args:
        user_input: 用户输入
        session_context: 会话上下文
        conversation_service: 对话服务
        
    Returns:
        ChatResponse: RAGFLOW响应
    """
    # 暂时跳过RAGFLOW调用，直接返回降级处理
    logger.info("跳过RAGFLOW调用，使用降级处理")
    
    fallback_response = "抱歉，我暂时无法理解您的问题。请明确描述您的需求，或者尝试以下操作："
    fallback_response += "\n• 订机票"
    fallback_response += "\n• 查银行卡余额" 
    fallback_response += "\n• 其他服务咨询"
    
    return ChatResponse(
        response=fallback_response,
        session_id=session_context['session_id'],
        conversation_turn=session_context.get('current_turn', 1),
        intent=None,
        confidence=0.0,
        slots={},
        status="non_intent_input", 
        response_type="qa_response",
        next_action="clarification"
    )


async def _handle_clear_intent(intent_result, user_input: str, session_context: Dict,
                             intent_service: IntentService,
                             conversation_service: ConversationService) -> ChatResponse:
    """
    处理明确的意图
    
    Args:
        intent_result: 意图识别结果
        user_input: 用户输入
        session_context: 会话上下文
        intent_service: 意图服务
        conversation_service: 对话服务
        
    Returns:
        ChatResponse: 意图处理响应
    """
    intent = intent_result.intent
    
    # 检查是否存在意图转移
    current_intent = session_context.get('current_intent')
    if current_intent and current_intent != intent.intent_name:
        # 记录意图转移
        await conversation_service.record_intent_transfer(
            session_context['session_id'], current_intent, intent.intent_name, 
            "用户主动切换意图"
        )
    
    # V2.2重构: 使用当前会话的槽位状态（已在主流程中查询）
    inherited_slots = session_context.get('current_slots', {})
    
    # V2.2增强：使用统一的槽位数据服务
    from src.services.enhanced_slot_service import get_enhanced_slot_service
    enhanced_slot_service = await get_enhanced_slot_service()
    
    # 提取当前输入的槽位（使用增强服务，返回统一格式）
    slot_result = await enhanced_slot_service.extract_slots(
        intent, user_input, inherited_slots, session_context
    )
    
    # 检查槽位完整性
    if slot_result.is_complete and not slot_result.has_errors:
        # 槽位完整，先生成确认信息
        return await _generate_confirmation_prompt(
            intent, slot_result.slots, session_context, conversation_service
        )
    else:
        # 槽位不完整，生成询问提示
        return await _generate_slot_prompt(
            intent, slot_result, session_context, conversation_service
        )


async def _execute_function_call(intent, slots: Dict, session_context: Dict,
                               conversation_service: ConversationService) -> ChatResponse:
    """
    执行功能调用 - 使用配置驱动的意图处理器
    
    Args:
        intent: 意图对象
        slots: 完整的槽位值字典
        session_context: 会话上下文
        conversation_service: 对话服务
        
    Returns:
        ChatResponse: 功能调用响应
    """
    try:
        # 使用配置驱动的意图处理器
        from src.services.config_driven_intent_processor import get_config_driven_processor
        processor = await get_config_driven_processor()
        
        # 执行意图处理
        return await processor.execute_intent(intent, slots, session_context)
            
    except Exception as e:
        logger.error(f"配置驱动意图处理失败: {str(e)}")
        
        # 回退到Mock服务处理已知意图
        if intent.intent_name == 'book_flight':
            return await _mock_book_flight_service(intent, slots, session_context)
        elif intent.intent_name == 'check_balance':
            return await _mock_check_balance_service(intent, slots, session_context)
        
        return ChatResponse(
            response="系统繁忙，请稍后重试。",
            session_id=session_context['session_id'],
            intent=intent.intent_name,
            confidence=0.95,
            slots=slots,
            status="system_error",
            response_type="error_with_alternatives",
            next_action="retry",
        )


async def _mock_book_flight_service(intent, slots: Dict, session_context: Dict) -> ChatResponse:
    """
    Mock机票预订服务
    
    Args:
        intent: 意图对象
        slots: 槽位字典
        session_context: 会话上下文
        
    Returns:
        ChatResponse: Mock响应
    """
    try:
        # 提取槽位值 - 兼容SlotInfo对象和字典格式
        def get_slot_value(slot_data, default='未知'):
            if slot_data is None:
                return default
            if hasattr(slot_data, 'value'):  # SlotInfo对象
                return slot_data.value or default
            elif isinstance(slot_data, dict):  # 字典格式
                return slot_data.get('value', default)
            else:  # 直接值
                return str(slot_data)
        
        departure_city = get_slot_value(slots.get('departure_city'))
        arrival_city = get_slot_value(slots.get('arrival_city'))
        departure_date = get_slot_value(slots.get('departure_date'))
        passenger_count = get_slot_value(slots.get('passenger_count'), '1')
        
        # 生成mock订单号
        import random
        order_id = f"FL{random.randint(100000, 999999)}"
        
        # 构建成功响应
        response_message = f"✅ 机票预订成功！\n\n" \
                          f"订单号：{order_id}\n" \
                          f"航程：{departure_city} → {arrival_city}\n" \
                          f"日期：{departure_date}\n" \
                          f"乘客数：{passenger_count}人\n\n" \
                          f"请保存好订单号，稍后将发送确认短信。"
        
        # Mock API结果数据
        api_result = {
            "order_id": order_id,
            "departure_city": departure_city,
            "arrival_city": arrival_city,
            "departure_date": departure_date,
            "passenger_count": int(passenger_count) if str(passenger_count).isdigit() else 1,
            "status": "confirmed",
            "booking_time": session_context.get('current_time', '2025-07-28 15:40:00')
        }
        
        return ChatResponse(
            response=response_message,
            session_id=session_context['session_id'],
            intent=intent.intent_name,
            confidence=0.95,
            slots=slots,
            status="completed",
            response_type="api_result",
            next_action="none",
            api_result=api_result,
        )
        
    except Exception as e:
        logger.error(f"Mock机票预订服务失败: {str(e)}")
        return ChatResponse(
            response="很抱歉，机票预订服务暂时不可用，请稍后重试。",
            session_id=session_context['session_id'],
            intent=intent.intent_name,
            confidence=0.0,
            slots=slots,
            status="error",
            response_type="error",
            next_action="retry",
        )


async def _mock_check_balance_service(intent, slots: Dict, session_context: Dict) -> ChatResponse:
    """
    Mock银行卡余额查询服务
    
    Args:
        intent: 意图对象
        slots: 槽位字典
        session_context: 会话上下文
        
    Returns:
        ChatResponse: Mock响应
    """
    try:
        # 提取槽位值
        def get_slot_value(slot_data, default='储蓄卡'):
            if slot_data is None:
                return default
            if hasattr(slot_data, 'value'):  # SlotInfo对象
                return slot_data.value or default
            elif isinstance(slot_data, dict):  # 字典格式
                return slot_data.get('value', default)
            else:  # 直接值
                return str(slot_data)
        
        account_type = get_slot_value(slots.get('account_type'), '银行卡')
        
        # 生成mock余额和卡号
        import random
        balance = random.randint(1000, 50000) + random.randint(0, 99) / 100
        card_number = f"****{random.randint(1000, 9999)}"
        
        # 构建成功响应
        response_message = f"💳 {account_type}余额查询成功！\n\n" \
                          f"卡号：{card_number}\n" \
                          f"余额：¥{balance:,.2f}\n" \
                          f"查询时间：{session_context.get('current_time', '2025-07-28 16:10:00')}\n\n" \
                          f"如需其他服务，请继续咨询。"
        
        # Mock API结果数据
        api_result = {
            "account_type": account_type,
            "card_number": card_number,
            "balance": balance,
            "currency": "CNY",
            "status": "success",
            "query_time": session_context.get('current_time', '2025-07-28 16:10:00')
        }
        
        return ChatResponse(
            response=response_message,
            session_id=session_context['session_id'],
            intent=intent.intent_name,
            confidence=0.95,
            slots=slots,
            status="completed",
            response_type="api_result",
            next_action="none",
            api_result=api_result,
        )
        
    except Exception as e:
        logger.error(f"Mock余额查询服务失败: {str(e)}")
        return ChatResponse(
            response="很抱歉，余额查询服务暂时不可用，请稍后重试。",
            session_id=session_context['session_id'],
            intent=intent.intent_name,
            confidence=0.0,
            slots=slots,
            status="error",
            response_type="error",
            next_action="retry",
        )


async def _generate_slot_prompt(intent, slot_result, session_context: Dict,
                              conversation_service: ConversationService) -> ChatResponse:
    """
    生成槽位询问提示
    
    Args:
        intent: 意图对象
        slot_result: 槽位提取结果
        session_context: 会话上下文
        conversation_service: 对话服务
        
    Returns:
        ChatResponse: 槽位询问响应
    """
    # V2.2重构: 保存当前槽位提取结果到slot_values表
    from src.services.slot_value_service import get_slot_value_service
    slot_value_service = get_slot_value_service()
    
    if slot_result.slots:
        try:
            await slot_value_service.update_session_slots(
                session_context['session_id'], intent.intent_name, slot_result.slots
            )
        except Exception as e:
            logger.warning(f"更新会话槽位失败: {str(e)}")
    
    # V2.2增强：使用统一的槽位数据服务
    from src.services.enhanced_slot_service import get_enhanced_slot_service
    enhanced_slot_service = await get_enhanced_slot_service()
    
    # 生成槽位询问提示
    prompt_message = await enhanced_slot_service.generate_slot_prompt(
        intent, slot_result.missing_slots, session_context
    )
    
    # 处理验证错误
    if slot_result.has_errors:
        error_messages = []
        for slot_name, error in slot_result.validation_errors.items():
            error_messages.append(f"{slot_name}: {error}")
        
        if error_messages:
            prompt_message = "输入信息有误：\n" + "\n".join(error_messages) + "\n\n" + prompt_message
    
    # V2.2 bug修复：合并slot_result.slots和会话历史槽位，确保响应包含完整槽位
    session_slots = await slot_value_service.get_session_slot_values(session_context['session_id'])
    
    # 合并新提取的槽位和历史槽位
    response_slots = {}
    response_slots.update(session_slots)  # 先添加历史槽位
    response_slots.update(slot_result.slots)  # 新提取的槽位会覆盖同名的历史槽位
    
    # 重新计算missing_slots，基于合并后的完整槽位
    # 获取必需槽位定义
    from src.models.slot import Slot
    slot_definitions = list(Slot.select().where(Slot.intent == intent.id, Slot.is_required == True))
    required_slots = [slot.slot_name for slot in slot_definitions]
    actual_missing_slots = [slot_name for slot_name in required_slots if slot_name not in response_slots or not response_slots.get(slot_name)]
    
    # 重新判断完整性
    is_complete = len(actual_missing_slots) == 0 and len(slot_result.validation_errors) == 0
    status = "complete" if is_complete else "incomplete"
    
    return ChatResponse(
        response=prompt_message,
        session_id=session_context['session_id'],
        intent=intent.intent_name,
        confidence=0.95,
        slots=response_slots,
        status=status,
        response_type="slot_prompt",
        next_action="collect_missing_slots" if not is_complete else "execute_function",
        missing_slots=actual_missing_slots,
        validation_errors=slot_result.validation_errors,
    )


@router.post("/disambiguate", response_model=StandardResponse[DisambiguationResponse])
async def resolve_disambiguation(
    request: DisambiguationRequest,
    intent_service: IntentService = Depends(get_intent_service)
):
    """
    解决意图歧义
    
    处理用户对歧义澄清问题的回复：
    1. 解析用户选择（数字或文本）
    2. 确定用户真实意图
    3. 继续后续的槽位处理
    """
    try:
        # 查找歧义记录
        try:
            ambiguity = IntentAmbiguity.get(
                IntentAmbiguity.conversation == request.conversation_id,
                IntentAmbiguity.resolved_at.is_null(True)
            )
        except IntentAmbiguity.DoesNotExist:
            raise HTTPException(status_code=404, detail="未找到待解决的歧义")
        
        # 获取候选意图
        candidates = ambiguity.get_candidate_intents()
        
        # 解析用户选择
        selected_intent = await intent_service.resolve_ambiguity(
            request.conversation_id, candidates, request.user_choice
        )
        
        if selected_intent:
            return StandardResponse(
                success=True,
                data=DisambiguationResponse(
                    resolved_intent=selected_intent.intent_name,
                    display_name=selected_intent.display_name,
                    next_step="slot_filling"
                ),
                message="歧义解决成功"
            )
        else:
            return StandardResponse(
                success=False,
                message="无法理解您的选择，请重新选择",
                data=DisambiguationResponse(
                    resolved_intent=None,
                    next_step="clarification"
                )
            )
            
    except Exception as e:
        logger.error(f"歧义解决失败: {str(e)}")
        raise HTTPException(status_code=500, detail="歧义解决失败")


async def _save_conversation_record(user_id: str, session_id: str, user_input: str,
                                  intent_result, response: ChatResponse, 
                                  processing_time: int, request_id: str, conversation_turn: int):
    """
    保存对话记录（后台任务）
    
    Args:
        user_id: 用户ID
        session_id: 会话ID
        user_input: 用户输入
        intent_result: 意图识别结果
        response: 系统响应
        processing_time: 处理时间
        request_id: 请求ID
    """
    try:
        logger.info(f"保存对话记录: user_input='{user_input}', intent='{response.intent}', status='{response.status}', response_type='{response.response_type}'")
        # V2.2重构: 更新对话记录创建以适配新的字段结构
        from src.models.conversation import Session
        session = Session.get(Session.session_id == session_id)
        
        # 确定正确的意图名称 - 优先使用response中的意图信息
        recognized_intent = response.intent or (intent_result.intent.intent_name if intent_result and intent_result.intent else None)
        confidence_score = response.confidence if hasattr(response, 'confidence') else (intent_result.confidence if intent_result else 0.0)
        
        # 检查是否已存在相同的记录，避免重复键错误
        try:
            conversation = Conversation.get(
                Conversation.session_id == session.session_id,
                Conversation.id == conversation_turn  # 假设conversation_turn对应id
            )
            # 更新现有记录
            conversation.user_input = user_input
            conversation.intent_recognized = recognized_intent
            conversation.confidence_score = confidence_score
            conversation.system_response = response.response
            conversation.response_type = response.response_type
            conversation.status = response.status
            conversation.processing_time_ms = processing_time
            conversation.save()
        except Conversation.DoesNotExist:
            # 创建新记录
            conversation = Conversation.create(
                session_id=session.session_id,  # 修复：传递session_id而不是session对象
                user_id=session.user_id,
                user_input=user_input,
                intent_recognized=recognized_intent,
                confidence_score=confidence_score,
                system_response=response.response,
                response_type=response.response_type,
                status=response.status,
                processing_time_ms=processing_time,
                conversation_turn=conversation_turn
            )
        
        # V2.2重构: 如果有槽位信息，保存到slot_values表
        if response.slots:
            from src.services.slot_value_service import get_slot_value_service
            slot_value_service = get_slot_value_service()
            try:
                await slot_value_service.save_conversation_slots(
                    session_id, conversation.id,
                    recognized_intent,  # 使用已确定的正确意图名称
                    response.slots
                )
            except Exception as e:
                logger.warning(f"保存对话槽位失败: {str(e)}")
        
        logger.info(f"对话记录保存成功: {conversation.id}")
        
    except Exception as e:
        logger.error(f"保存对话记录失败: {str(e)}")


async def _try_handle_confirmation_response(
    user_input: str,
    session_context: Dict,
    conversation_service: ConversationService,
    intent_service: IntentService
) -> ChatResponse:
    """
    尝试处理用户的确认响应
    
    Args:
        user_input: 用户输入
        session_context: 会话上下文
        conversation_service: 对话服务
        intent_service: 意图服务
        
    Returns:
        ChatResponse: 如果成功处理确认响应则返回响应，否则返回None
    """
    try:
        logger.info(f"检查确认响应: 用户输入='{user_input}'")
        
        # 检查对话历史，查找最近的确认提示
        conversation_history = session_context.get('conversation_history', [])
        
        if not conversation_history:
            logger.info("确认检查: 无对话历史，跳过")
            return None
        
        # 查找最近的确认提示
        latest_conversation = conversation_history[0] if conversation_history else None
        logger.info(f"确认检查: 最近对话状态={latest_conversation.get('status') if latest_conversation else None}, 响应类型={latest_conversation.get('response_type') if latest_conversation else None}")
        
        if (not latest_conversation or 
            latest_conversation.get('status') != 'awaiting_confirmation' or
            latest_conversation.get('response_type') != 'confirmation_prompt'):
            logger.info("确认检查: 最近对话不是确认状态，跳过")
            return None
        
        # 获取待确认的意图和槽位信息
        intent_name = latest_conversation.get('intent')
        if not intent_name:
            return None
        
        intent = await intent_service._get_intent_by_name(intent_name)
        if not intent:
            return None
        
        # 获取当前会话的槽位值
        from src.services.slot_value_service import get_slot_value_service
        slot_value_service = get_slot_value_service()
        current_slots = await slot_value_service.get_session_slot_values(session_context['session_id'])
        
        # 解析用户的确认响应
        user_input_lower = user_input.strip().lower()
        
        # 确认关键词
        confirm_keywords = ['确认', '是', '对', '正确', '好的', '可以', 'yes', 'ok', '是的', '确认订票', '确认预订']
        # 修改关键词
        modify_keywords = ['修改', '改', '重新', '不对', '错了', '不是', 'no', '修正']
        # 取消关键词
        cancel_keywords = ['取消', '不要', '算了', '退出', 'cancel']
        
        logger.info(f"确认检查: 关键词匹配测试 - 用户输入='{user_input_lower}', 确认关键词匹配={any(keyword in user_input_lower for keyword in confirm_keywords)}")
        
        if any(keyword in user_input_lower for keyword in confirm_keywords):
            # 用户确认，执行功能调用
            logger.info(f"用户确认操作: {intent_name}")
            return await _execute_function_call(intent, current_slots, session_context, conversation_service)
            
        elif any(keyword in user_input_lower for keyword in modify_keywords):
            # 用户要求修改，重新生成槽位询问
            logger.info(f"用户要求修改槽位: {intent_name}")
            
            # 构造一个slot_result来生成槽位询问
            from src.services.enhanced_slot_service import get_enhanced_slot_service
            enhanced_slot_service = await get_enhanced_slot_service()
            
            # 获取必需槽位
            from src.models.slot import Slot
            slot_definitions = list(Slot.select().where(Slot.intent == intent.id, Slot.is_required == True))
            missing_slots = [slot.slot_name for slot in slot_definitions]
            
            # 创建一个模拟的slot_result
            class MockSlotResult:
                def __init__(self):
                    self.slots = {}
                    self.missing_slots = missing_slots
                    self.is_complete = False
                    self.has_errors = False
                    self.validation_errors = {}
            
            mock_slot_result = MockSlotResult()
            
            return await _generate_slot_prompt(
                intent, mock_slot_result, session_context, conversation_service
            )
            
        elif any(keyword in user_input_lower for keyword in cancel_keywords):
            # 用户取消操作
            logger.info(f"用户取消操作: {intent_name}")
            
            return ChatResponse(
                response=f"好的，已取消{intent.display_name}操作。如需其他帮助，请随时告诉我。",
                session_id=session_context['session_id'],
                intent=intent_name,
                confidence=0.95,
                slots=current_slots,
                status="cancelled",
                response_type="cancellation",
                next_action="none",
                session_metadata=SessionMetadata(
                    total_turns=session_context.get('current_turn', 1),
                    session_duration_seconds=0
                )
            )
        
        # 如果不是明确的确认响应，返回None让其他处理逻辑处理
        return None
        
    except Exception as e:
        logger.error(f"处理确认响应失败: {str(e)}")
        return None


async def _try_handle_slot_supplement(
    user_input: str, 
    session_context: Dict, 
    conversation_service: ConversationService,
    intent_service: IntentService,
    session_id: str = None
) -> ChatResponse:
    """
    尝试处理槽位补充（会话连续性关键功能）
    
    Args:
        user_input: 用户输入
        session_context: 会话上下文
        conversation_service: 对话服务
        intent_service: 意图服务
        
    Returns:
        ChatResponse: 如果成功处理槽位补充则返回响应，否则返回None
    """
    try:
        # 1. 检查当前会话是否有未完成的意图
        conversation_history = session_context.get('conversation_history', [])
        logger.info(f"槽位补充检查: 获取到对话历史{len(conversation_history)}轮")
        
        if not conversation_history:
            logger.info("槽位补充检查: 无对话历史，跳过")
            return None
        
        # 2. 智能查找最近的未完成意图（支持多轮间隔）
        incomplete_conversation = None
        incomplete_intent_name = None
        
        # 从最近的对话开始向前查找，最多查找5轮
        for i in range(min(5, len(conversation_history))):
            conv = conversation_history[i]  # 修复：conversation_history已经是按时间倒序的，直接使用索引i
            logger.info(f"检查轮次{i+1}: status={conv.get('status')}, response_type={conv.get('response_type')}, intent={conv.get('intent')}, user_input='{conv.get('user_input', '')[:20]}'")
            
            # 查找最近的槽位收集状态对话
            if (conv.get('status') == 'incomplete' and 
                conv.get('response_type') == 'slot_prompt' and
                conv.get('intent')):
                
                incomplete_conversation = conv
                incomplete_intent_name = conv.get('intent')
                logger.info(f"找到候选未完成意图: {incomplete_intent_name}")
                
                # 检查该意图是否还有缺失的槽位
                # 从数据库加载该会话的所有历史槽位
                from src.services.slot_value_service import get_slot_value_service
                slot_value_service = get_slot_value_service()
                session_slots = await slot_value_service.get_session_slot_values(session_id)
                
                # 合并会话上下文中的槽位和数据库中的历史槽位
                current_slots = session_context.get('current_slots', {})
                current_slots.update(session_slots)
                
                logger.info(f"当前会话槽位: {current_slots}")
                
                intent_obj = await intent_service._get_intent_by_name(incomplete_intent_name)
                
                if intent_obj:
                    # 获取该意图的所有必需槽位
                    from src.services.slot_service import get_slot_service
                    slot_service = get_slot_service()
                    required_slots = await slot_service.get_required_slots(intent_obj.id)
                    
                    # 检查是否还有缺失的槽位
                    missing_slots = []
                    for slot_name in required_slots:
                        if (slot_name not in current_slots or 
                            not current_slots.get(slot_name)):
                            missing_slots.append(slot_name)
                    
                    logger.info(f"必需槽位检查: 需要={required_slots}, 缺失={missing_slots}")
                    
                    # 如果还有缺失的槽位，则可以进行补充
                    if missing_slots:
                        logger.info(f"✅ 找到未完成意图: {incomplete_intent_name}, 缺失槽位: {missing_slots}, 间隔轮次: {i}")
                        break
                    else:
                        logger.info(f"意图{incomplete_intent_name}槽位已完整，继续查找")
                
                # 清空，继续查找
                incomplete_conversation = None
                incomplete_intent_name = None
        
        # 如果没有找到未完成的意图，返回None
        if not incomplete_conversation or not incomplete_intent_name:
            logger.info("槽位补充检查: 未找到可补充的未完成意图")
            return None
            
        # 3. 获取意图对象（已在上面验证过，直接使用）
        intent = await intent_service._get_intent_by_name(incomplete_intent_name)
        if not intent:
            return None
            
        # 4. 获取当前会话的槽位状态
        current_slots = session_context.get('current_slots', {})
        
        # 5. 尝试识别用户输入作为槽位值
        from src.services.enhanced_slot_service import get_enhanced_slot_service
        enhanced_slot_service = await get_enhanced_slot_service()
        
        # 重新获取完整的历史槽位（确保包含最新数据）
        from src.services.slot_value_service import get_slot_value_service
        slot_value_service = get_slot_value_service()
        session_slots = await slot_value_service.get_session_slot_values(session_id)
        
        # 构建槽位补充上下文
        supplement_context = {
            **session_context,
            'is_slot_supplement': True,
            'target_intent': incomplete_intent_name,
            'existing_slots': session_slots
        }
        
        # 提取槽位（重点关注缺失的槽位）
        slot_result = await enhanced_slot_service.extract_slots(
            intent, user_input, session_slots, supplement_context
        )
        
        # 5. 检查是否有新的槽位被识别
        new_slots_found = False
        for slot_name in slot_result.slots.keys():
            if slot_name not in session_slots or not session_slots.get(slot_name):
                new_slots_found = True
                break
                
        if not new_slots_found:
            # 没有识别到新的槽位，返回None让后续处理
            return None
            
        logger.info(f"识别到槽位补充: {user_input} -> {list(slot_result.slots.keys())}")
        
        # 6. 检查槽位完整性并生成响应 - 考虑历史槽位
        # 合并新提取的槽位和历史槽位
        complete_slots = {}
        complete_slots.update(session_slots)
        complete_slots.update(slot_result.slots)
        
        # 重新计算完整性，基于合并后的槽位
        from src.models.slot import Slot
        slot_definitions = list(Slot.select().where(Slot.intent == intent.id, Slot.is_required == True))
        required_slots = [slot.slot_name for slot in slot_definitions]
        missing_slots = [slot_name for slot_name in required_slots if slot_name not in complete_slots or not complete_slots.get(slot_name)]
        
        is_actually_complete = len(missing_slots) == 0 and not slot_result.has_errors
        
        if is_actually_complete:
            # 槽位完整，先生成确认信息
            return await _generate_confirmation_prompt(
                intent, complete_slots, session_context, conversation_service
            )
        else:
            # 槽位不完整，继续询问
            return await _generate_slot_prompt(
                intent, slot_result, session_context, conversation_service
            )
            
    except Exception as e:
        logger.error(f"槽位补充处理失败: {str(e)}", exc_info=True)
        return None


async def _generate_confirmation_prompt(
    intent, 
    slots: Dict[str, Any], 
    session_context: Dict, 
    conversation_service: ConversationService
) -> ChatResponse:
    """
    生成槽位确认提示 - 使用配置驱动的响应模板
    
    Args:
        intent: 意图对象
        slots: 完整的槽位值字典
        session_context: 会话上下文
        conversation_service: 对话服务
        
    Returns:
        ChatResponse: 确认提示响应
    """
    try:
        # 应用默认值到槽位字典中
        complete_slots = await _apply_default_values_to_slots(intent, slots)
        
        # 使用配置驱动的意图处理器生成确认提示
        from src.services.config_driven_intent_processor import get_config_driven_processor
        processor = await get_config_driven_processor()
        
        # 获取确认响应模板
        template = await processor._get_response_template(intent.id, 'confirmation')
        
        # 如果有专用模板，使用配置驱动的方式渲染
        if template and template != '请确认您的信息是否正确？':
            confirmation_message = processor._render_response_template(template, {**complete_slots})
        else:
            # 回退到硬编码逻辑
            confirmation_message = await _generate_hardcoded_confirmation(intent, complete_slots)
        
        return ChatResponse(
            response=confirmation_message,
            session_id=session_context['session_id'],
            intent=intent.intent_name,
            confidence=0.95,
            slots=complete_slots,  # 使用包含默认值的完整槽位
            status="awaiting_confirmation",
            response_type="confirmation_prompt",
            next_action="user_confirmation",
            session_metadata=SessionMetadata(
                total_turns=session_context.get('current_turn', 1),
                session_duration_seconds=0
            )
        )
        
    except Exception as e:
        logger.error(f"生成确认提示失败: {str(e)}")
        # 回退到直接执行功能调用
        return await _execute_function_call(intent, slots, session_context, conversation_service)


async def _generate_hardcoded_confirmation(intent, slots: Dict[str, Any]) -> str:
    """
    生成硬编码的确认信息（向后兼容）
    
    Args:
        intent: 意图对象
        slots: 完整的槽位值字典
        
    Returns:
        str: 确认信息
    """
    # 提取槽位值 - 兼容SlotInfo对象和字典格式
    def get_slot_value(slot_data, default='未知'):
        if slot_data is None:
            return default
        if hasattr(slot_data, 'value'):  # SlotInfo对象
            return slot_data.value or default
        elif isinstance(slot_data, dict):  # 字典格式
            return slot_data.get('value', default)
        else:  # 直接值
            return str(slot_data)
    
    # 根据意图类型生成确认信息
    if intent.intent_name == 'book_flight':
        departure_city = get_slot_value(slots.get('departure_city'))
        arrival_city = get_slot_value(slots.get('arrival_city'))
        departure_date = get_slot_value(slots.get('departure_date'))
        passenger_count = get_slot_value(slots.get('passenger_count'), '1')
        return_date = get_slot_value(slots.get('return_date'))
        trip_type = get_slot_value(slots.get('trip_type'))
        
        # 构建基础信息
        confirmation_message = (
            f"✈️ 请确认您的航班预订信息：\n\n"
            f"🏙️ 出发城市：{departure_city}\n"
            f"🏙️ 到达城市：{arrival_city}\n"
            f"📅 出发日期：{departure_date}\n"
        )
        
        # 如果是往返机票，添加返程信息
        if trip_type and (trip_type == 'round_trip' or '往返' in str(trip_type)):
            if return_date and return_date != '未知':
                confirmation_message += f"🔄 返程日期：{return_date}\n"
            confirmation_message += f"✈️ 行程类型：往返\n"
        else:
            confirmation_message += f"✈️ 行程类型：单程\n"
        
        # 添加乘客信息和操作提示
        confirmation_message += (
            f"👥 乘客人数：{passenger_count}人\n\n"
            f"以上信息是否正确？\n"
            f"• 输入'确认'或'是'来预订机票\n"
            f"• 输入'修改'来重新填写信息\n"
            f"• 输入'取消'来取消预订"
        )
        
    elif intent.intent_name == 'check_balance':
        account_type = get_slot_value(slots.get('account_type'), '银行卡')
        
        confirmation_message = (
            f"💳 请确认您的查询信息：\n\n"
            f"🏦 账户类型：{account_type}\n\n"
            f"以上信息是否正确？\n"
            f"• 输入'确认'或'是'来查询余额\n"
            f"• 输入'修改'来重新选择账户类型\n"
            f"• 输入'取消'来取消查询"
        )
        
    else:
        # 通用确认格式
        slot_lines = []
        for slot_name, slot_data in slots.items():
            if slot_data:
                slot_value = get_slot_value(slot_data)
                slot_lines.append(f"• {slot_name}：{slot_value}")
        
        confirmation_message = (
            f"📋 请确认您的信息：\n\n" +
            "\n".join(slot_lines) +
            "\n\n以上信息是否正确？\n"
            f"• 输入'确认'或'是'来执行操作\n"
            f"• 输入'修改'来重新填写信息\n"
            f"• 输入'取消'来取消操作"
        )
    
    return confirmation_message


async def _save_error_conversation(user_id: str, user_input: str, 
                                 error_message: str, request_id: str):
    """
    保存错误对话记录（后台任务）
    """
    try:
        # V2.2重构: 为错误对话创建临时会话或使用默认会话
        from src.models.conversation import Session, User
        
        # 尝试获取或创建用户
        try:
            user = User.get(User.user_id == user_id)
        except User.DoesNotExist:
            user = User.create(user_id=user_id, user_type='individual')
        
        # 创建错误会话
        error_session = Session.create(
            session_id=f"error_{request_id}",
            user_id=user.user_id,  # v2.2修复: 使用user_id字符串而非User对象
            session_state='error',
            context=json.dumps({'error': True, 'request_id': request_id})
        )
        
        conversation = Conversation.create(
            session_id=error_session.session_id,  # 修复：传递session_id而不是session对象
            user_id=user.user_id,  # v2.2修复: 使用user_id字符串而非User对象
            user_input=user_input,
            system_response=f"系统错误: {error_message}",
            response_type="system_error",
            status="system_error",
            conversation_turn=1
        )
        
        logger.info(f"错误对话记录保存成功: {conversation.id}")
        
    except Exception as e:
        logger.error(f"保存错误对话记录失败: {str(e)}")


async def _apply_default_values_to_slots(intent, slots: Dict[str, Any]) -> Dict[str, Any]:
    """
    为槽位字典应用默认值
    
    Args:
        intent: 意图对象
        slots: 当前槽位字典
        
    Returns:
        Dict[str, Any]: 包含默认值的完整槽位字典
    """
    try:
        # 直接从数据库获取意图的所有槽位定义
        from src.models.slot import Slot
        slot_definitions = list(Slot.select().where(Slot.intent == intent.id))
        
        # 创建完整的槽位字典副本
        complete_slots = dict(slots)
        
        # 为每个有默认值的槽位应用默认值（如果当前不存在）
        for slot_def in slot_definitions:
            slot_name = slot_def.slot_name
            default_value = slot_def.default_value
            
            # 如果槽位不存在且有默认值，应用默认值
            if slot_name not in complete_slots and default_value is not None and default_value.strip():
                logger.info(f"为槽位 {slot_name} 应用默认值: {default_value}")
                
                # 创建槽位信息对象，与现有格式保持一致
                complete_slots[slot_name] = {
                    'name': slot_name,
                    'original_text': default_value,
                    'extracted_value': default_value,
                    'normalized_value': default_value,
                    'confidence': 1.0,
                    'extraction_method': 'default',
                    'validation': None,
                    'is_confirmed': True,
                    'value': default_value,
                    'source': 'default',
                    'is_validated': True,
                    'validation_error': None
                }
        
        return complete_slots
        
    except Exception as e:
        logger.error(f"应用默认值失败: {str(e)}")
        return slots  # 出错时返回原始槽位字典