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
    ChatRequest, ChatResponse, SessionMetadata,
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
        
        # 5. 多轮对话的意图识别（基于历史上下文）
        intent_result = await intent_service.recognize_intent_with_history(
            sanitized_input, request.user_id, session_context, conversation_history
        )
        
        # 6. 处理不同的意图识别结果
        if intent_result.is_ambiguous:
            # 处理意图歧义
            response = await _handle_intent_ambiguity(
                intent_result, sanitized_input, session_context, conversation_service
            )
        elif intent_result.intent is None:
            # 检查是否是对缺失槽位的补充（会话连续性关键修复）
            slot_supplement_result = await _try_handle_slot_supplement(
                sanitized_input, session_context, conversation_service, intent_service, session_id
            )
            
            if slot_supplement_result:
                response = slot_supplement_result
            else:
                # 非意图输入，调用RAGFLOW
                response = await _handle_non_intent_input(
                    sanitized_input, session_context, conversation_service
                )
        else:
            # 明确的意图，进行槽位处理
            response = await _handle_clear_intent(
                intent_result, sanitized_input, session_context, 
                intent_service, conversation_service
            )
        
        # 7. 记录对话历史（包含轮次信息）
        processing_time = int((time.time() - start_time) * 1000)
        
        # 如果是槽位补充且有响应意图，更新intent_result
        final_intent_result = intent_result
        if (intent_result.intent is None and response.intent and 
            hasattr(response, 'intent') and response.intent):
            # 构建槽位补充的intent_result
            from src.schemas.intent_recognition import IntentRecognitionResult
            intent_obj = await intent_service._get_intent_by_name(response.intent)
            if intent_obj:
                final_intent_result = IntentRecognitionResult(
                    intent=intent_obj,
                    confidence=response.confidence,
                    is_ambiguous=False,
                    alternatives=[]
                )
        
        background_tasks.add_task(
            _save_conversation_record,
            request.user_id, session_id, sanitized_input,
            final_intent_result, response, processing_time, request_id, current_turn
        )
        
        # 6. 构建标准响应 - 使用统一转换器
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
        ambiguous_intents=intent_result.alternatives,
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
        # 槽位完整，调用功能API
        return await _execute_function_call(
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
    执行功能调用
    
    Args:
        intent: 意图对象
        slots: 完整的槽位值字典
        session_context: 会话上下文
        conversation_service: 对话服务
        
    Returns:
        ChatResponse: 功能调用响应
    """
    try:
        # 如果是book_flight意图，使用mock服务
        if intent.intent_name == 'book_flight':
            return await _mock_book_flight_service(intent, slots, session_context)
        
        # 获取功能调用服务
        from src.api.dependencies import get_function_service
        function_service = await get_function_service()
        
        # 执行功能调用
        function_result = await function_service.execute_function_call(
            intent, slots, session_context
        )
        
        if function_result.success:
            return ChatResponse(
                response=function_result.response_message,
                session_id=session_context['session_id'],
                intent=intent.intent_name,
                confidence=0.95,  # 功能执行成功时设置高置信度
                slots=slots,
                status="completed",
                response_type="api_result",
                next_action="none",
                api_result=function_result.data,
            )
        else:
            # API调用失败
            error_response = f"很抱歉，{intent.display_name}服务暂时不可用"
            if hasattr(function_result, 'error_message') and function_result.error_message:
                error_response += f"：{function_result.error_message}"
            error_response += "。请稍后重试或联系客服。"
            
            return ChatResponse(
                response=error_response,
                session_id=session_context['session_id'],
                intent=intent.intent_name,
                confidence=0.95,
                slots=slots,
                status="api_error",
                response_type="error_with_alternatives",
                next_action="retry",
            )
            
    except Exception as e:
        logger.error(f"功能调用执行失败: {str(e)}")
        
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
        # V2.2重构: 更新对话记录创建以适配新的字段结构
        from src.models.conversation import Session
        session = Session.get(Session.session_id == session_id)
        
        # 检查是否已存在相同的记录，避免重复键错误
        try:
            conversation = Conversation.get(
                Conversation.session_id == session.session_id,
                Conversation.id == conversation_turn  # 假设conversation_turn对应id
            )
            # 更新现有记录
            conversation.user_input = user_input
            conversation.intent_recognized = intent_result.intent.intent_name if intent_result.intent else None
            conversation.confidence_score = intent_result.confidence
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
                intent_recognized=intent_result.intent.intent_name if intent_result.intent else None,
                confidence_score=intent_result.confidence,
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
                    intent_result.intent.intent_name if intent_result.intent else None,
                    response.slots
                )
            except Exception as e:
                logger.warning(f"保存对话槽位失败: {str(e)}")
        
        logger.info(f"对话记录保存成功: {conversation.id}")
        
    except Exception as e:
        logger.error(f"保存对话记录失败: {str(e)}")


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
            logger.info(f"检查轮次{i+1}: status={conv.get('status')}, response_type={conv.get('response_type')}, intent={conv.get('intent')}")
            
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
            # 槽位完整，调用功能API
            return await _execute_function_call(
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