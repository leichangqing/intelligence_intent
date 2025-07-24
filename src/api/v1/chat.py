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
        
        # 4. 计算当前对话轮次
        current_turn = len(conversation_history) + 1
        session_context['current_turn'] = current_turn
        session_context['conversation_history'] = conversation_history
        session_context['current_slots'] = current_slot_values
        
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
        background_tasks.add_task(
            _save_conversation_record,
            request.user_id, session_context['session_id'], sanitized_input,
            intent_result, response, processing_time, request_id, current_turn
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
    try:
        # 调用RAGFLOW API
        ragflow_response = await conversation_service.call_ragflow(
            user_input, session_context
        )
        
        return ChatResponse(
            response=ragflow_response.get('answer', '抱歉，我暂时无法理解您的问题。'),
            session_id=session_context['session_id'],
            intent=None,
            confidence=0.0,
            slots={},
            status="ragflow_handled",
            response_type="qa_response",
            next_action="none",
            message_type="non_intent_input"
        )
        
    except Exception as e:
        logger.error(f"RAGFLOW调用失败: {str(e)}")
        
        # RAGFLOW失败时的降级处理
        fallback_response = "抱歉，我暂时无法理解您的问题。请明确描述您的需求，或者尝试以下操作："
        fallback_response += "\n• 订机票"
        fallback_response += "\n• 查银行卡余额"
        fallback_response += "\n• 其他服务咨询"
        
        return ChatResponse(
            response=fallback_response,
            session_id=session_context['session_id'],
            intent=None,
            confidence=0.0,
            slots={},
            status="ragflow_error",
            response_type="error_with_alternatives",
            next_action="clarification",
            message_type="service_error"
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
    enhanced_slot_service = get_enhanced_slot_service()
    
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
                message_type="intent_completion"
            )
        else:
            # API调用失败
            error_response = f"很抱歉，{intent.display_name}服务暂时不可用"
            if function_result.error_message:
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
                message_type="api_error"
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
            message_type="system_error"
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
    enhanced_slot_service = get_enhanced_slot_service()
    
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
    
    return ChatResponse(
        response=prompt_message,
        session_id=session_context['session_id'],
        intent=intent.intent_name,
        confidence=0.95,
        slots=slot_result.slots,
        status="incomplete",
        response_type="slot_prompt",
        next_action="collect_missing_slots",
        missing_slots=slot_result.missing_slots,
        validation_errors=slot_result.validation_errors,
        message_type="slot_filling"
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
        
        conversation = Conversation.create(
            session=session,
            user_id=session.user_id,
            user_input=user_input,
            intent_name=intent_result.intent.intent_name if intent_result.intent else None,
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
            session=error_session,
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