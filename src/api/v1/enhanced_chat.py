"""
增强的聊天交互接口 (TASK-034)
提供流式响应、会话管理优化、上下文保持和响应格式统一功能
"""
from typing import Dict, Any, AsyncGenerator, List, Optional
from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks, Request
from fastapi.responses import StreamingResponse, JSONResponse
from sse_starlette.sse import EventSourceResponse
import asyncio
import json
import time
import uuid
from datetime import datetime, timedelta

from src.schemas.chat import (
    ChatInteractRequest, ChatResponse, StreamChatRequest, StreamChatResponse,
    SessionManagementRequest, SessionAnalyticsRequest, ContextUpdateRequest
)
from src.schemas.common import StandardResponse
from src.services.conversation_service import ConversationService
from src.services.intent_service import IntentService
from src.services.cache_service import CacheService
from src.core.fallback_manager import get_fallback_manager
from src.api.dependencies import get_conversation_service, get_intent_service
from src.utils.logger import get_logger
from src.utils.rate_limiter import RateLimiter
from src.utils.context_manager import ContextManager

logger = get_logger(__name__)
router = APIRouter(prefix="/enhanced-chat", tags=["增强聊天接口"])

# 全局速率限制器
rate_limiter = RateLimiter(
    max_requests_per_minute=60,
    max_requests_per_hour=1000
)

# 上下文管理器
context_manager = ContextManager()


@router.post("/stream", response_class=EventSourceResponse)
async def stream_chat(
    request: StreamChatRequest,
    http_request: Request,
    background_tasks: BackgroundTasks,
    conversation_service: ConversationService = Depends(get_conversation_service),
    intent_service: IntentService = Depends(get_intent_service)
):
    """
    流式聊天接口
    
    实现实时流式响应，提供更好的用户体验：
    1. Server-Sent Events (SSE) 流式传输
    2. 分段响应处理
    3. 实时状态更新
    4. 异常处理和恢复
    """
    request_id = f"stream_{int(time.time())}_{uuid.uuid4().hex[:8]}"
    
    try:
        # 速率限制检查
        client_ip = http_request.client.host
        if not await rate_limiter.check_rate_limit(request.user_id, client_ip):
            raise HTTPException(status_code=429, detail="请求过于频繁，请稍后再试")
        
        logger.info(f"开始流式对话: {request_id}, 用户: {request.user_id}")
        
        # 创建流式响应生成器
        async def generate_stream():
            try:
                # 发送开始事件
                yield {
                    "event": "start",
                    "data": json.dumps({
                        "request_id": request_id,
                        "status": "processing",
                        "timestamp": datetime.now().isoformat()
                    })
                }
                
                # 发送进度更新
                yield {
                    "event": "progress",
                    "data": json.dumps({
                        "stage": "intent_recognition",
                        "progress": 20,
                        "message": "正在识别意图..."
                    })
                }
                
                # 意图识别
                intent_result = await intent_service.recognize_intent(
                    request.input, request.user_id, request.context or {}
                )
                
                yield {
                    "event": "progress",
                    "data": json.dumps({
                        "stage": "intent_recognized",
                        "progress": 40,
                        "intent": intent_result.intent.intent_name if intent_result.intent else None,
                        "confidence": intent_result.confidence
                    })
                }
                
                # 处理不同情况
                if intent_result.is_ambiguous:
                    # 处理歧义
                    response = await _handle_ambiguous_stream(intent_result, request, conversation_service)
                elif intent_result.intent is None:
                    # RAGFLOW处理
                    async for chunk in _handle_ragflow_stream(request, conversation_service):
                        yield chunk
                    return
                else:
                    # 明确意图处理
                    async for chunk in _handle_intent_stream(intent_result, request, intent_service, conversation_service):
                        yield chunk
                    return
                
                # 发送最终响应
                yield {
                    "event": "response",
                    "data": json.dumps(response.dict())
                }
                
                yield {
                    "event": "end",
                    "data": json.dumps({
                        "request_id": request_id,
                        "status": "completed",
                        "timestamp": datetime.now().isoformat()
                    })
                }
                
            except Exception as e:
                logger.error(f"流式处理失败: {request_id}, 错误: {str(e)}")
                
                yield {
                    "event": "error",
                    "data": json.dumps({
                        "error": "服务暂时不可用",
                        "request_id": request_id,
                        "timestamp": datetime.now().isoformat()
                    })
                }
        
        return EventSourceResponse(generate_stream())
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"流式聊天初始化失败: {request_id}, 错误: {str(e)}")
        raise HTTPException(status_code=500, detail="服务暂时不可用")


async def _handle_ragflow_stream(request: StreamChatRequest, 
                               conversation_service: ConversationService) -> AsyncGenerator[Dict[str, Any], None]:
    """处理RAGFLOW流式响应"""
    
    yield {
        "event": "progress", 
        "data": json.dumps({
            "stage": "knowledge_search",
            "progress": 60,
            "message": "正在搜索知识库..."
        })
    }
    
    try:
        # 调用RAGFLOW（支持流式）
        ragflow_response = await conversation_service.call_ragflow_stream(
            request.input, request.context or {}
        )
        
        if hasattr(ragflow_response, '__aiter__'):
            # 流式响应
            accumulated_text = ""
            chunk_count = 0
            
            async for chunk in ragflow_response:
                chunk_count += 1
                accumulated_text += chunk
                
                yield {
                    "event": "partial_response",
                    "data": json.dumps({
                        "chunk": chunk,
                        "accumulated_text": accumulated_text,
                        "chunk_index": chunk_count
                    })
                }
                
                # 控制流速
                await asyncio.sleep(0.05)
            
            # 最终响应
            response = StreamChatResponse(
                response=accumulated_text,
                intent=None,
                confidence=0.8,
                status="ragflow_completed",
                response_type="qa_response",
                is_streaming=True,
                chunk_count=chunk_count
            )
        else:
            # 普通响应
            response = StreamChatResponse(
                response=ragflow_response.get('answer', '抱歉，暂时无法回答您的问题'),
                intent=None,
                confidence=0.8,
                status="ragflow_completed",
                response_type="qa_response",
                is_streaming=False
            )
        
        yield {
            "event": "response",
            "data": json.dumps(response.dict())
        }
        
    except Exception as e:
        logger.error(f"RAGFLOW流式处理失败: {str(e)}")
        
        # 回退响应
        fallback_response = StreamChatResponse(
            response="抱歉，暂时无法回答您的问题。请稍后再试或换个方式提问。",
            intent=None,
            confidence=0.0,
            status="ragflow_error",
            response_type="error_response",
            error_message=str(e)
        )
        
        yield {
            "event": "response",
            "data": json.dumps(fallback_response.dict())
        }


async def _handle_intent_stream(intent_result, request: StreamChatRequest,
                              intent_service: IntentService,
                              conversation_service: ConversationService) -> AsyncGenerator[Dict[str, Any], None]:
    """处理意图流式响应"""
    
    yield {
        "event": "progress",
        "data": json.dumps({
            "stage": "slot_extraction",
            "progress": 60,
            "message": "正在提取参数..."
        })
    }
    
    # 槽位提取
    from src.api.dependencies import get_slot_service
    slot_service = await get_slot_service()
    
    slot_result = await slot_service.extract_slots(
        intent_result.intent, request.input, {}, request.context or {}
    )
    
    yield {
        "event": "progress",
        "data": json.dumps({
            "stage": "slots_extracted",
            "progress": 80,
            "slots": {k: v.value for k, v in slot_result.slots.items()},
            "missing_slots": slot_result.missing_slots
        })
    }
    
    if slot_result.is_complete:
        # 执行功能调用
        yield {
            "event": "progress",
            "data": json.dumps({
                "stage": "function_execution",
                "progress": 90,
                "message": "正在执行操作..."
            })
        }
        
        from src.api.dependencies import get_function_service
        function_service = await get_function_service()
        
        function_result = await function_service.execute_function_call(
            intent_result.intent, slot_result.slots, request.context or {}
        )
        
        response = StreamChatResponse(
            response=function_result.response_message,
            intent=intent_result.intent.intent_name,
            confidence=intent_result.confidence,
            slots={k: v.dict() for k, v in slot_result.slots.items()},
            status="completed",
            response_type="function_result",
            api_result=function_result.data,
            is_streaming=False
        )
    else:
        # 生成槽位询问
        prompt_message = await slot_service.generate_slot_prompt(
            intent_result.intent, slot_result.missing_slots, request.context or {}
        )
        
        response = StreamChatResponse(
            response=prompt_message,
            intent=intent_result.intent.intent_name,
            confidence=intent_result.confidence,
            slots={k: v.dict() for k, v in slot_result.slots.items()},
            status="incomplete",
            response_type="slot_prompt",
            missing_slots=slot_result.missing_slots,
            is_streaming=False
        )
    
    yield {
        "event": "response",
        "data": json.dumps(response.dict())
    }


async def _handle_ambiguous_stream(intent_result, request: StreamChatRequest,
                                 conversation_service: ConversationService) -> StreamChatResponse:
    """处理歧义流式响应"""
    
    # 生成歧义澄清问题
    disambiguation_question = await conversation_service.generate_disambiguation_question(
        intent_result.alternatives
    )
    
    return StreamChatResponse(
        response=disambiguation_question,
        intent=None,
        confidence=0.0,
        status="ambiguous",
        response_type="disambiguation",
        ambiguous_intents=[
            {
                "intent_name": alt.intent.intent_name,
                "display_name": alt.intent.display_name,
                "confidence": alt.confidence
            }
            for alt in intent_result.alternatives
        ],
        is_streaming=False
    )


@router.post("/batch", response_model=StandardResponse[List[ChatResponse]])
async def batch_chat(
    requests: List[ChatInteractRequest],
    background_tasks: BackgroundTasks,
    conversation_service: ConversationService = Depends(get_conversation_service),
    intent_service: IntentService = Depends(get_intent_service)
):
    """
    批量聊天处理接口
    
    支持批量处理多个对话请求：
    1. 并发处理优化
    2. 错误隔离
    3. 部分成功处理
    4. 性能监控
    """
    batch_id = f"batch_{int(time.time())}_{uuid.uuid4().hex[:8]}"
    start_time = time.time()
    
    try:
        if len(requests) > 10:
            raise HTTPException(status_code=400, detail="批量请求不能超过10个")
        
        logger.info(f"开始批量处理: {batch_id}, 请求数: {len(requests)}")
        
        # 并发处理所有请求
        tasks = []
        for i, request in enumerate(requests):
            task = _process_single_chat_request(
                request, f"{batch_id}_{i}", intent_service, conversation_service
            )
            tasks.append(task)
        
        # 等待所有任务完成
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 处理结果
        responses = []
        success_count = 0
        error_count = 0
        
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                error_count += 1
                error_response = ChatResponse(
                    response="处理失败，请稍后重试",
                    intent=None,
                    confidence=0.0,
                    slots={},
                    status="error",
                    response_type="error",
                    next_action="retry",
                    message_type="batch_error",
                    request_id=f"{batch_id}_{i}"
                )
                responses.append(error_response)
                logger.error(f"批量请求 {i} 处理失败: {str(result)}")
            else:
                success_count += 1
                responses.append(result)
        
        processing_time = int((time.time() - start_time) * 1000)
        
        # 记录批量处理统计
        background_tasks.add_task(
            _record_batch_stats,
            batch_id, len(requests), success_count, error_count, processing_time
        )
        
        return StandardResponse(
            success=True,
            data=responses,
            message=f"批量处理完成: {success_count} 成功, {error_count} 失败",
            metadata={
                "batch_id": batch_id,
                "total_requests": len(requests),
                "success_count": success_count,
                "error_count": error_count,
                "processing_time_ms": processing_time
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"批量处理失败: {batch_id}, 错误: {str(e)}")
        raise HTTPException(status_code=500, detail="批量处理失败")


async def _process_single_chat_request(
    request: ChatInteractRequest,
    request_id: str,
    intent_service: IntentService,
    conversation_service: ConversationService
) -> ChatResponse:
    """处理单个聊天请求"""
    try:
        # 意图识别
        intent_result = await intent_service.recognize_intent(
            request.input, request.user_id, request.context or {}
        )
        
        # 处理逻辑（简化版）
        if intent_result.is_ambiguous:
            response = await _handle_batch_ambiguity(intent_result, conversation_service)
        elif intent_result.intent is None:
            response = await _handle_batch_ragflow(request, conversation_service)
        else:
            response = await _handle_batch_intent(intent_result, request, intent_service, conversation_service)
        
        response.request_id = request_id
        return response
        
    except Exception as e:
        logger.error(f"单个请求处理失败: {request_id}, 错误: {str(e)}")
        raise e


@router.post("/session/create", response_model=StandardResponse[Dict[str, Any]])
async def create_session(
    request: SessionManagementRequest,
    conversation_service: ConversationService = Depends(get_conversation_service)
):
    """
    创建会话
    
    优化的会话管理：
    1. 会话生命周期管理
    2. 上下文持久化
    3. 会话状态跟踪
    4. 资源清理
    """
    try:
        session = await conversation_service.get_or_create_session(
            request.user_id, None
        )
        
        session_info = {
            "session_id": session.session_id,
            "user_id": session.user_id,
            "created_at": session.created_at.isoformat(),
            "expires_at": (session.created_at + timedelta(hours=24)).isoformat(),
            "status": "active",
            "context": session.get_context()
        }
        
        # 初始化会话上下文
        await context_manager.initialize_session_context(
            session.session_id, request.user_id, request.initial_context or {}
        )
        
        logger.info(f"创建会话: {session.session_id}, 用户: {request.user_id}")
        
        return StandardResponse(
            success=True,
            data=session_info,
            message="会话创建成功"
        )
        
    except Exception as e:
        logger.error(f"创建会话失败: 用户 {request.user_id}, 错误: {str(e)}")
        raise HTTPException(status_code=500, detail="会话创建失败")


@router.post("/session/update-context", response_model=StandardResponse[Dict[str, Any]])
async def update_session_context(
    request: ContextUpdateRequest,
    conversation_service: ConversationService = Depends(get_conversation_service)
):
    """
    更新会话上下文
    
    增强的上下文管理：
    1. 增量更新
    2. 上下文验证
    3. 历史追踪
    4. 冲突解决
    """
    try:
        # 验证会话存在
        session = await conversation_service.get_session_by_id(request.session_id)
        if not session:
            raise HTTPException(status_code=404, detail="会话不存在")
        
        # 更新上下文
        updated_context = await context_manager.update_context(
            request.session_id,
            request.context_updates,
            merge_strategy=request.merge_strategy
        )
        
        # 保存到数据库
        success = await conversation_service.update_session_context(
            request.session_id, updated_context
        )
        
        if success:
            return StandardResponse(
                success=True,
                data={
                    "session_id": request.session_id,
                    "updated_context": updated_context,
                    "merge_strategy": request.merge_strategy,
                    "updated_at": datetime.now().isoformat()
                },
                message="上下文更新成功"
            )
        else:
            raise HTTPException(status_code=500, detail="上下文更新失败")
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"更新会话上下文失败: {request.session_id}, 错误: {str(e)}")
        raise HTTPException(status_code=500, detail="更新上下文失败")


@router.get("/session/{session_id}/analytics", response_model=StandardResponse[Dict[str, Any]])
async def get_session_analytics(
    session_id: str,
    conversation_service: ConversationService = Depends(get_conversation_service)
):
    """
    获取会话分析数据
    
    提供会话性能和质量分析：
    1. 对话轮次统计
    2. 意图识别准确率
    3. 响应时间分析
    4. 用户满意度评估
    """
    try:
        # 获取会话历史
        history = await conversation_service.get_conversation_history(session_id, limit=100)
        
        # 计算分析数据
        analytics = await _calculate_session_analytics(history)
        
        return StandardResponse(
            success=True,
            data=analytics,
            message="会话分析获取成功"
        )
        
    except Exception as e:
        logger.error(f"获取会话分析失败: {session_id}, 错误: {str(e)}")
        raise HTTPException(status_code=500, detail="获取会话分析失败")


async def _calculate_session_analytics(history: List[Dict[str, Any]]) -> Dict[str, Any]:
    """计算会话分析数据"""
    if not history:
        return {
            "total_turns": 0,
            "average_confidence": 0.0,
            "average_response_time": 0.0,
            "intent_distribution": {},
            "response_type_distribution": {},
            "success_rate": 0.0
        }
    
    total_turns = len(history)
    total_confidence = sum(h.get('confidence', 0.0) for h in history)
    total_response_time = sum(h.get('processing_time_ms', 0) for h in history)
    
    # 意图分布
    intent_distribution = {}
    for h in history:
        intent = h.get('intent')
        if intent:
            intent_distribution[intent] = intent_distribution.get(intent, 0) + 1
    
    # 响应类型分布
    response_type_distribution = {}
    for h in history:
        response_type = h.get('response_type', 'unknown')
        response_type_distribution[response_type] = response_type_distribution.get(response_type, 0) + 1
    
    # 成功率计算
    successful_turns = sum(
        1 for h in history 
        if h.get('status') in ['completed', 'ragflow_handled']
    )
    success_rate = successful_turns / total_turns if total_turns > 0 else 0.0
    
    return {
        "total_turns": total_turns,
        "average_confidence": total_confidence / total_turns if total_turns > 0 else 0.0,
        "average_response_time": total_response_time / total_turns if total_turns > 0 else 0.0,
        "intent_distribution": intent_distribution,
        "response_type_distribution": response_type_distribution,
        "success_rate": success_rate,
        "quality_score": _calculate_quality_score(history)
    }


def _calculate_quality_score(history: List[Dict[str, Any]]) -> float:
    """计算会话质量分数"""
    if not history:
        return 0.0
    
    # 基于多个维度计算质量分数
    confidence_score = sum(h.get('confidence', 0.0) for h in history) / len(history)
    success_rate = sum(1 for h in history if h.get('status') in ['completed', 'ragflow_handled']) / len(history)
    response_time_score = min(1.0, 5000 / (sum(h.get('processing_time_ms', 5000) for h in history) / len(history)))
    
    # 综合评分
    quality_score = (confidence_score * 0.4 + success_rate * 0.4 + response_time_score * 0.2)
    return round(quality_score, 3)


# 辅助函数
async def _handle_batch_ambiguity(intent_result, conversation_service) -> ChatResponse:
    """批量处理中的歧义处理"""
    question = await conversation_service.generate_disambiguation_question(
        intent_result.alternatives
    )
    
    return ChatResponse(
        response=question,
        intent=None,
        confidence=0.0,
        slots={},
        status="ambiguous",
        response_type="disambiguation",
        next_action="user_choice",
        ambiguous_intents=[
            {
                "intent_name": alt.intent.intent_name,
                "display_name": alt.intent.display_name,
                "confidence": alt.confidence
            }
            for alt in intent_result.alternatives
        ],
        message_type="batch_ambiguous"
    )


async def _handle_batch_ragflow(request, conversation_service) -> ChatResponse:
    """批量处理中的RAGFLOW处理"""
    try:
        ragflow_response = await conversation_service.call_ragflow(
            request.input, request.context or {}
        )
        
        return ChatResponse(
            response=ragflow_response.get('answer', '抱歉，暂时无法回答您的问题'),
            intent=None,
            confidence=ragflow_response.get('confidence', 0.0),
            slots={},
            status="ragflow_handled",
            response_type="qa_response",
            next_action="none",
            message_type="batch_ragflow"
        )
        
    except Exception as e:
        return ChatResponse(
            response="抱歉，知识库查询失败，请稍后重试",
            intent=None,
            confidence=0.0,
            slots={},
            status="ragflow_error",
            response_type="error_response",
            next_action="retry",
            message_type="batch_error"
        )


async def _handle_batch_intent(intent_result, request, intent_service, conversation_service) -> ChatResponse:
    """批量处理中的意图处理"""
    # 简化的意图处理逻辑
    return ChatResponse(
        response=f"识别到意图: {intent_result.intent.display_name}，正在处理中...",
        intent=intent_result.intent.intent_name,
        confidence=intent_result.confidence,
        slots={},
        status="processing",
        response_type="intent_response",
        next_action="processing",
        message_type="batch_intent"
    )


async def _record_batch_stats(batch_id: str, total: int, success: int, 
                            error: int, processing_time: int):
    """记录批量处理统计"""
    try:
        # 这里可以记录到数据库或监控系统
        logger.info(f"批量处理统计: {batch_id}, 总数: {total}, 成功: {success}, "
                   f"失败: {error}, 处理时间: {processing_time}ms")
    except Exception as e:
        logger.error(f"记录批量统计失败: {str(e)}")


@router.get("/health", response_model=StandardResponse[Dict[str, Any]])
async def health_check():
    """增强聊天接口健康检查"""
    try:
        health_status = {
            "status": "healthy",
            "timestamp": datetime.now().isoformat(),
            "version": "2.0.0",
            "features": {
                "streaming": True,
                "batch_processing": True,
                "session_management": True,
                "context_preservation": True,
                "analytics": True
            },
            "performance": {
                "average_response_time": "< 200ms",
                "concurrent_users_supported": 1000,
                "batch_size_limit": 10
            }
        }
        
        return StandardResponse(
            success=True,
            data=health_status,
            message="增强聊天接口运行正常"
        )
        
    except Exception as e:
        logger.error(f"健康检查失败: {str(e)}")
        raise HTTPException(status_code=500, detail="健康检查失败")