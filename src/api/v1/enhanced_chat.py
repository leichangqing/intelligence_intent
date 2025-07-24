"""
增强对话API接口 - 支持多轮对话和会话管理

实现混合架构设计下的完整多轮对话功能：
1. 会话生命周期管理
2. 历史对话上下文推理
3. 槽位继承和累积
4. 意图转移检测
5. 上下文引用解析
"""
from typing import Dict, Any, List, Optional
from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from fastapi.responses import JSONResponse
import time
import uuid
import json

from src.schemas.chat import (
    ChatRequest, ChatResponse, SessionMetadata,
    SessionManagementRequest, ContextUpdateRequest, SessionAnalyticsRequest
)
from src.schemas.common import StandardResponse
from src.services.conversation_service import ConversationService
from src.services.intent_service import IntentService
from src.api.dependencies import get_conversation_service, get_intent_service
from src.utils.logger import get_logger
from src.utils.response_transformer import get_response_transformer

logger = get_logger(__name__)
router = APIRouter(prefix="/enhanced-chat", tags=["增强对话接口"])


@router.post("/session/create", response_model=StandardResponse[Dict[str, Any]])
async def create_session(
    request: SessionManagementRequest,
    conversation_service: ConversationService = Depends(get_conversation_service)
):
    """
    创建新的对话会话
    
    支持多轮对话的会话生命周期管理：
    1. 创建会话并分配唯一ID
    2. 初始化会话上下文
    3. 设置会话过期时间
    4. 返回会话信息
    """
    try:
        logger.info(f"创建会话请求: 用户={request.user_id}")
        
        # 创建新会话
        session_data = await conversation_service.create_session(
            user_id=request.user_id,
            initial_context=request.initial_context or {},
            expiry_hours=request.expiry_hours or 24
        )
        
        return StandardResponse(
            success=True,
            data={
                "session_id": session_data["session_id"],
                "user_id": session_data["user_id"],
                "session_state": session_data["session_state"],
                "expires_at": session_data["expires_at"],
                "created_at": session_data["created_at"],
                "context": session_data.get("context", {})
            },
            message="会话创建成功"
        )
        
    except Exception as e:
        logger.error(f"创建会话失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"创建会话失败: {str(e)}")


@router.post("/session/update-context", response_model=StandardResponse[Dict[str, Any]])
async def update_session_context(
    request: ContextUpdateRequest,
    conversation_service: ConversationService = Depends(get_conversation_service)
):
    """
    更新会话上下文信息
    
    支持动态上下文更新：
    1. 合并或替换上下文数据
    2. 保留历史记录（可选）
    3. 触发相关缓存更新
    """
    try:
        logger.info(f"更新会话上下文: {request.session_id}")
        
        # 更新会话上下文
        updated_context = await conversation_service.update_session_context(
            session_id=request.session_id,
            context_updates=request.context_updates,
            merge_strategy=request.merge_strategy,
            preserve_history=request.preserve_history
        )
        
        return StandardResponse(
            success=True,
            data={
                "session_id": request.session_id,
                "updated_context": updated_context,
                "merge_strategy": request.merge_strategy,
                "updated_at": time.time()
            },
            message="会话上下文更新成功"
        )
        
    except Exception as e:
        logger.error(f"更新会话上下文失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"更新会话上下文失败: {str(e)}")


@router.get("/session/{session_id}/analytics", response_model=StandardResponse[Dict[str, Any]])
async def get_session_analytics(
    session_id: str,
    include_details: bool = False,
    conversation_service: ConversationService = Depends(get_conversation_service)
):
    """
    获取会话分析数据
    
    提供详细的会话统计信息：
    1. 对话轮次统计
    2. 意图识别分布
    3. 响应时间分析
    4. 槽位填充统计
    5. 错误率统计
    """
    try:
        logger.info(f"获取会话分析: {session_id}")
        
        # 获取会话分析数据
        analytics_data = await conversation_service.get_session_analytics(
            session_id=session_id,
            include_details=include_details
        )
        
        return StandardResponse(
            success=True,
            data=analytics_data,
            message="会话分析获取成功"
        )
        
    except Exception as e:
        logger.error(f"获取会话分析失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"获取会话分析失败: {str(e)}")


@router.get("/session/{session_id}/history", response_model=StandardResponse[List[Dict[str, Any]]])
async def get_conversation_history(
    session_id: str,
    limit: int = 20,
    offset: int = 0,
    conversation_service: ConversationService = Depends(get_conversation_service)
):
    """
    获取对话历史记录
    
    提供完整的对话历史：
    1. 分页查询对话记录
    2. 包含意图识别结果
    3. 包含槽位填充状态
    4. 包含响应类型信息
    """
    try:
        logger.info(f"获取对话历史: {session_id}, limit={limit}, offset={offset}")
        
        # 获取对话历史
        history_data = await conversation_service.get_conversation_history(
            session_id=session_id,
            limit=limit,
            offset=offset
        )
        
        return StandardResponse(
            success=True,
            data=history_data,
            message="对话历史获取成功"
        )
        
    except Exception as e:
        logger.error(f"获取对话历史失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"获取对话历史失败: {str(e)}")


@router.get("/session/{session_id}/current-state", response_model=StandardResponse[Dict[str, Any]])
async def get_session_current_state(
    session_id: str,
    conversation_service: ConversationService = Depends(get_conversation_service)
):
    """
    获取会话当前状态
    
    提供会话的实时状态：
    1. 当前意图状态
    2. 已填充的槽位
    3. 缺失的槽位
    4. 会话元数据
    """
    try:
        logger.info(f"获取会话状态: {session_id}")
        
        # 获取会话当前状态
        current_state = await conversation_service.get_session_current_state(session_id)
        
        return StandardResponse(
            success=True,
            data=current_state,
            message="会话状态获取成功"
        )
        
    except Exception as e:
        logger.error(f"获取会话状态失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"获取会话状态失败: {str(e)}")


@router.post("/session/{session_id}/reset", response_model=StandardResponse[Dict[str, Any]])
async def reset_session(
    session_id: str,
    preserve_context: bool = True,
    conversation_service: ConversationService = Depends(get_conversation_service)
):
    """
    重置会话状态
    
    重置会话到初始状态：
    1. 清除当前意图状态
    2. 清除槽位填充
    3. 可选保留基础上下文
    4. 保留历史记录
    """
    try:
        logger.info(f"重置会话: {session_id}, preserve_context={preserve_context}")
        
        # 重置会话状态
        reset_result = await conversation_service.reset_session_state(
            session_id=session_id,
            preserve_context=preserve_context
        )
        
        return StandardResponse(
            success=True,
            data=reset_result,
            message="会话重置成功"
        )
        
    except Exception as e:
        logger.error(f"重置会话失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"重置会话失败: {str(e)}")


@router.delete("/session/{session_id}", response_model=StandardResponse[Dict[str, Any]])
async def delete_session(
    session_id: str,
    conversation_service: ConversationService = Depends(get_conversation_service)
):
    """
    删除会话
    
    完全删除会话及其相关数据：
    1. 删除会话记录
    2. 删除对话历史
    3. 删除槽位数据
    4. 清理相关缓存
    """
    try:
        logger.info(f"删除会话: {session_id}")
        
        # 删除会话
        delete_result = await conversation_service.delete_session(session_id)
        
        return StandardResponse(
            success=True,
            data=delete_result,
            message="会话删除成功"
        )
        
    except Exception as e:
        logger.error(f"删除会话失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"删除会话失败: {str(e)}")


@router.post("/multi-turn-interact", response_model=StandardResponse[ChatResponse])
async def multi_turn_interact(
    request: ChatRequest,
    background_tasks: BackgroundTasks,
    conversation_service: ConversationService = Depends(get_conversation_service),
    intent_service: IntentService = Depends(get_intent_service)
):
    """
    多轮对话交互接口
    
    专门为多轮对话优化的交互接口：
    1. 自动会话管理
    2. 智能上下文推理
    3. 槽位继承和累积
    4. 意图转移检测
    5. 对话状态跟踪
    """
    start_time = time.time()
    request_id = f"multi_req_{int(time.time())}_{uuid.uuid4().hex[:8]}"
    
    try:
        logger.info(f"多轮对话请求: {request_id}, 用户: {request.user_id}")
        
        # 如果没有session_id，自动创建新会话
        if not request.session_id:
            session_data = await conversation_service.create_session(
                user_id=request.user_id,
                initial_context=request.context.model_dump() if request.context else {}
            )
            session_id = session_data["session_id"]
        else:
            session_id = request.session_id
        
        # 获取完整的会话上下文和历史
        session_context = await conversation_service.get_full_session_context(session_id)
        
        # 执行多轮对话推理
        response = await _execute_multi_turn_reasoning(
            request.input, session_context, intent_service, conversation_service
        )
        
        # 更新会话状态
        await conversation_service.update_session_state_after_turn(
            session_id, response, session_context
        )
        
        # 记录处理时间
        processing_time = int((time.time() - start_time) * 1000)
        response.processing_time_ms = processing_time
        response.request_id = request_id
        
        return StandardResponse(
            success=True,
            data=response,
            message="多轮对话处理成功"
        )
        
    except Exception as e:
        logger.error(f"多轮对话处理失败: {request_id}, 错误: {str(e)}")
        raise HTTPException(status_code=500, detail=f"多轮对话处理失败: {str(e)}")


async def _execute_multi_turn_reasoning(
    user_input: str,
    session_context: Dict[str, Any],
    intent_service: IntentService,
    conversation_service: ConversationService
) -> ChatResponse:
    """
    执行多轮对话推理
    
    这是多轮对话的核心推理引擎：
    1. 分析用户输入的上下文语义
    2. 解析代词和引用
    3. 继承历史槽位
    4. 执行意图识别和槽位提取
    5. 生成适当的响应
    """
    # 1. 上下文语义分析
    context_analysis = await conversation_service.analyze_input_context(
        user_input, session_context
    )
    
    # 2. 意图识别（基于历史上下文）
    intent_result = await intent_service.recognize_intent_with_context(
        user_input, session_context, context_analysis
    )
    
    # 3. 槽位处理（继承和更新）
    slot_result = await conversation_service.process_slots_with_inheritance(
        intent_result, user_input, session_context
    )
    
    # 4. 生成响应
    if slot_result.is_complete:
        # 执行业务逻辑
        response = await conversation_service.execute_business_logic(
            intent_result, slot_result, session_context
        )
    else:
        # 生成槽位询问
        response = await conversation_service.generate_smart_slot_prompt(
            intent_result, slot_result, session_context
        )
    
    return response


@router.get("/session/{session_id}/context-resolution", response_model=StandardResponse[List[Dict[str, Any]]])
async def get_context_resolution_history(
    session_id: str,
    conversation_service: ConversationService = Depends(get_conversation_service)
):
    """
    获取上下文解析历史
    
    显示系统如何解析代词引用和上下文：
    1. 代词引用解析记录
    2. 槽位继承链路
    3. 上下文推理过程
    """
    try:
        logger.info(f"获取上下文解析历史: {session_id}")
        
        resolution_history = await conversation_service.get_context_resolution_history(session_id)
        
        return StandardResponse(
            success=True,
            data=resolution_history,
            message="上下文解析历史获取成功"
        )
        
    except Exception as e:
        logger.error(f"获取上下文解析历史失败: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))