"""
歧义解决API端点 (TASK-035)
实现专门的歧义解决接口，提升意图识别准确性和用户体验
"""
from typing import Dict, List, Optional, Any
from fastapi import APIRouter, HTTPException, Depends, Query, Path
from fastapi.responses import JSONResponse
import logging
from datetime import datetime
import asyncio
from uuid import uuid4

from ...core.ambiguity_detector import EnhancedAmbiguityDetector, AmbiguityAnalysis
from ...core.clarification_question_generator import (
    ClarificationQuestionGenerator, ClarificationContext, ClarificationQuestion
)
from ...schemas.ambiguity_resolution import (
    AmbiguityDetectionRequest, AmbiguityDetectionResponse,
    DisambiguationRequest, DisambiguationResponse,
    InteractiveDisambiguationRequest, InteractiveDisambiguationResponse,
    AmbiguitySessionRequest, AmbiguitySessionResponse,
    DisambiguationHistoryResponse, SmartSuggestionResponse,
    AmbiguityAnalyticsResponse, AmbiguityResolutionStatus
)
from ...services.conversation_service import ConversationService
from ...services.intent_service import IntentService
from ...config.settings import get_settings
from ...utils.logger import get_logger
from ...utils.cache_service import CacheService
from ...utils.context_manager import ContextManager

logger = get_logger(__name__)
router = APIRouter(prefix="/ambiguity", tags=["歧义解决"])

# 依赖注入
def get_ambiguity_detector() -> EnhancedAmbiguityDetector:
    settings = get_settings()
    return EnhancedAmbiguityDetector(settings)

def get_clarification_generator() -> ClarificationQuestionGenerator:
    return ClarificationQuestionGenerator()

def get_cache_service() -> CacheService:
    return CacheService()

def get_context_manager() -> ContextManager:
    return ContextManager()

# 活跃的歧义解决会话
active_disambiguation_sessions: Dict[str, Dict[str, Any]] = {}


@router.post("/detect", response_model=AmbiguityDetectionResponse)
async def detect_ambiguity(
    request: AmbiguityDetectionRequest,
    detector: EnhancedAmbiguityDetector = Depends(get_ambiguity_detector),
    cache: CacheService = Depends(get_cache_service)
):
    """
    检测用户输入中的歧义
    
    Args:
        request: 歧义检测请求
        detector: 歧义检测器
        cache: 缓存服务
        
    Returns:
        AmbiguityDetectionResponse: 歧义检测结果
    """
    try:
        start_time = datetime.now()
        
        # 生成请求ID
        request_id = str(uuid4())
        
        logger.info(f"开始歧义检测: 请求ID={request_id}, 用户={request.user_id}")
        
        # 检查缓存
        cache_key = f"ambiguity_detection:{hash(request.user_input + str(request.candidates))}"
        cached_result = await cache.get(cache_key)
        
        if cached_result and not request.force_redetect:
            logger.info(f"返回缓存的歧义检测结果: {request_id}")
            cached_result['request_id'] = request_id
            cached_result['cached'] = True
            return AmbiguityDetectionResponse(**cached_result)
        
        # 执行歧义检测
        analysis = await detector.detect_ambiguity(
            candidates=request.candidates,
            user_input=request.user_input,
            conversation_context=request.conversation_context
        )
        
        # 计算处理时间
        processing_time = int((datetime.now() - start_time).total_seconds() * 1000)
        
        # 准备响应
        response = AmbiguityDetectionResponse(
            request_id=request_id,
            user_id=request.user_id,
            is_ambiguous=analysis.is_ambiguous,
            ambiguity_score=analysis.ambiguity_score,
            primary_ambiguity_type=analysis.primary_type.value,
            ambiguity_signals=[
                {
                    "type": signal.type.value,
                    "level": signal.level.value,
                    "score": signal.score,
                    "evidence": signal.evidence,
                    "explanation": signal.explanation,
                    "confidence": signal.confidence
                }
                for signal in analysis.signals
            ],
            candidates=analysis.candidates,
            recommended_action=analysis.recommended_action,
            analysis_metadata=analysis.analysis_metadata,
            processing_time_ms=processing_time,
            timestamp=datetime.now().isoformat(),
            cached=False
        )
        
        # 缓存结果
        if analysis.is_ambiguous:
            cache_data = response.dict()
            await cache.set(cache_key, cache_data, expire=300)  # 5分钟缓存
        
        logger.info(f"歧义检测完成: 请求ID={request_id}, 歧义={analysis.is_ambiguous}, "
                   f"得分={analysis.ambiguity_score:.3f}, 耗时={processing_time}ms")
        
        return response
        
    except Exception as e:
        logger.error(f"歧义检测失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"歧义检测失败: {str(e)}")


@router.post("/disambiguate", response_model=DisambiguationResponse)
async def disambiguate_intent(
    request: DisambiguationRequest,
    detector: EnhancedAmbiguityDetector = Depends(get_ambiguity_detector),
    generator: ClarificationQuestionGenerator = Depends(get_clarification_generator)
):
    """
    执行歧义解决，生成澄清问题
    
    Args:
        request: 歧义解决请求
        detector: 歧义检测器
        generator: 澄清问题生成器
        
    Returns:
        DisambiguationResponse: 歧义解决响应
    """
    try:
        start_time = datetime.now()
        session_id = str(uuid4())
        
        logger.info(f"开始歧义解决: 会话ID={session_id}, 用户={request.user_id}")
        
        # 首先进行歧义检测
        analysis = await detector.detect_ambiguity(
            candidates=request.candidates,
            user_input=request.user_input,
            conversation_context=request.conversation_context
        )
        
        if not analysis.is_ambiguous:
            # 没有歧义，返回最佳候选
            best_candidate = max(request.candidates, key=lambda x: x.get('confidence', 0.0))
            
            return DisambiguationResponse(
                session_id=session_id,
                user_id=request.user_id,
                status=AmbiguityResolutionStatus.NO_AMBIGUITY,
                resolved_intent=best_candidate.get('intent_name'),
                confidence=best_candidate.get('confidence', 0.0),
                resolution_method="automatic",
                clarification_question=None,
                suggested_responses=[],
                analysis_summary={
                    "is_ambiguous": False,
                    "best_candidate": best_candidate,
                    "reason": "sufficient_confidence"
                },
                processing_time_ms=int((datetime.now() - start_time).total_seconds() * 1000),
                timestamp=datetime.now().isoformat()
            )
        
        # 构建澄清上下文
        clarification_context = ClarificationContext(
            user_input=request.user_input,
            parsed_intents=request.candidates,
            extracted_slots=request.conversation_context.get('current_slots', {}) if request.conversation_context else {},
            ambiguity_analysis=analysis,
            conversation_history=request.conversation_context.get('history', []) if request.conversation_context else [],
            user_preferences=request.user_preferences or {},
            current_intent=request.conversation_context.get('current_intent') if request.conversation_context else None,
            incomplete_slots=request.missing_slots or [],
            conflicting_values=request.conflicting_values or {},
            confidence_scores={
                candidate['intent_name']: candidate.get('confidence', 0.0)
                for candidate in request.candidates
            }
        )
        
        # 生成澄清问题
        clarification = await generator.generate_clarification_question(
            context=clarification_context,
            user_id=request.user_id
        )
        
        # 生成建议响应
        suggested_responses = await _generate_suggested_responses(
            clarification, request.candidates, request.user_input
        )
        
        # 保存会话状态
        active_disambiguation_sessions[session_id] = {
            'user_id': request.user_id,
            'original_input': request.user_input,
            'candidates': request.candidates,
            'analysis': analysis,
            'clarification': clarification,
            'context': clarification_context,
            'created_at': datetime.now().isoformat(),
            'status': AmbiguityResolutionStatus.PENDING_USER_INPUT
        }
        
        processing_time = int((datetime.now() - start_time).total_seconds() * 1000)
        
        response = DisambiguationResponse(
            session_id=session_id,
            user_id=request.user_id,
            status=AmbiguityResolutionStatus.PENDING_USER_INPUT,
            resolved_intent=None,
            confidence=0.0,
            resolution_method="interactive",
            clarification_question={
                "question": clarification.question,
                "type": clarification.clarification_type.value,
                "style": clarification.style.value,
                "suggested_values": clarification.suggested_values,
                "expected_response_type": clarification.expected_response_type,
                "urgency": clarification.urgency,
                "follow_up_questions": clarification.follow_up_questions
            },
            suggested_responses=suggested_responses,
            analysis_summary={
                "ambiguity_score": analysis.ambiguity_score,
                "primary_type": analysis.primary_type.value,
                "signal_count": len(analysis.signals),
                "recommended_action": analysis.recommended_action
            },
            processing_time_ms=processing_time,
            timestamp=datetime.now().isoformat()
        )
        
        logger.info(f"歧义解决生成: 会话ID={session_id}, 问题类型={clarification.clarification_type.value}, "
                   f"耗时={processing_time}ms")
        
        return response
        
    except Exception as e:
        logger.error(f"歧义解决失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"歧义解决失败: {str(e)}")


@router.post("/interactive/{session_id}", response_model=InteractiveDisambiguationResponse)
async def handle_interactive_disambiguation(
    session_id: str = Path(..., description="歧义解决会话ID"),
    request: InteractiveDisambiguationRequest = None,
    context_manager: ContextManager = Depends(get_context_manager)
):
    """
    处理交互式歧义解决用户响应
    
    Args:
        session_id: 歧义解决会话ID
        request: 交互式歧义解决请求
        context_manager: 上下文管理器
        
    Returns:
        InteractiveDisambiguationResponse: 交互式歧义解决响应
    """
    try:
        start_time = datetime.now()
        
        # 检查会话是否存在
        if session_id not in active_disambiguation_sessions:
            raise HTTPException(status_code=404, detail="歧义解决会话不存在或已过期")
        
        session = active_disambiguation_sessions[session_id]
        
        logger.info(f"处理交互式歧义解决: 会话ID={session_id}, 用户响应={request.user_response}")
        
        # 解析用户响应
        resolution_result = await _parse_user_response(
            user_response=request.user_response,
            session=session,
            response_type=request.response_type
        )
        
        processing_time = int((datetime.now() - start_time).total_seconds() * 1000)
        
        if resolution_result['success']:
            # 歧义已解决
            resolved_intent = resolution_result['resolved_intent']
            confidence = resolution_result['confidence']
            
            # 更新会话状态
            session['status'] = AmbiguityResolutionStatus.RESOLVED
            session['resolved_intent'] = resolved_intent
            session['resolution_confidence'] = confidence
            session['resolved_at'] = datetime.now().isoformat()
            
            # 更新用户上下文
            if hasattr(context_manager, 'update_context') and request.update_context:
                await context_manager.update_context(
                    session_id=request.context_session_id or session_id,
                    updates={
                        'current_intent': resolved_intent,
                        'disambiguation_history': {
                            'session_id': session_id,
                            'resolved_intent': resolved_intent,
                            'confidence': confidence,
                            'resolution_method': 'interactive',
                            'timestamp': datetime.now().isoformat()
                        }
                    }
                )
            
            response = InteractiveDisambiguationResponse(
                session_id=session_id,
                user_id=session['user_id'],
                status=AmbiguityResolutionStatus.RESOLVED,
                resolved_intent=resolved_intent,
                confidence=confidence,
                resolution_explanation=resolution_result.get('explanation', ''),
                next_steps=resolution_result.get('next_steps', []),
                context_updates=resolution_result.get('context_updates', {}),
                follow_up_needed=False,
                processing_time_ms=processing_time,
                timestamp=datetime.now().isoformat()
            )
            
            logger.info(f"歧义已解决: 会话ID={session_id}, 意图={resolved_intent}, "
                       f"置信度={confidence:.3f}")
            
            # 清理会话（延迟清理以便后续查询）
            asyncio.create_task(_cleanup_session_later(session_id, delay=300))
            
        else:
            # 需要进一步澄清
            session['status'] = AmbiguityResolutionStatus.PENDING_CLARIFICATION
            
            response = InteractiveDisambiguationResponse(
                session_id=session_id,
                user_id=session['user_id'],
                status=AmbiguityResolutionStatus.PENDING_CLARIFICATION,
                resolved_intent=None,
                confidence=0.0,
                resolution_explanation=resolution_result.get('explanation', ''),
                next_steps=resolution_result.get('next_steps', []),
                context_updates={},
                follow_up_needed=True,
                follow_up_question=resolution_result.get('follow_up_question'),
                processing_time_ms=processing_time,
                timestamp=datetime.now().isoformat()
            )
            
            logger.info(f"需要进一步澄清: 会话ID={session_id}")
        
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"交互式歧义解决失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"交互式歧义解决失败: {str(e)}")


@router.post("/session", response_model=AmbiguitySessionResponse)
async def create_disambiguation_session(request: AmbiguitySessionRequest):
    """
    创建歧义解决会话
    
    Args:
        request: 歧义会话请求
        
    Returns:
        AmbiguitySessionResponse: 歧义会话响应
    """
    try:
        session_id = str(uuid4())
        
        session_data = {
            'user_id': request.user_id,
            'session_type': request.session_type,
            'initial_context': request.initial_context or {},
            'preferences': request.preferences or {},
            'created_at': datetime.now().isoformat(),
            'status': 'active',
            'interactions': [],
            'metadata': request.metadata or {}
        }
        
        active_disambiguation_sessions[session_id] = session_data
        
        logger.info(f"创建歧义解决会话: 会话ID={session_id}, 用户={request.user_id}")
        
        return AmbiguitySessionResponse(
            session_id=session_id,
            user_id=request.user_id,
            status="active",
            created_at=datetime.now().isoformat(),
            expires_at=(datetime.now().timestamp() + 3600),  # 1小时后过期
            session_capabilities={
                "interactive_disambiguation": True,
                "smart_suggestions": True,
                "context_awareness": True,
                "history_tracking": True
            }
        )
        
    except Exception as e:
        logger.error(f"创建歧义会话失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"创建歧义会话失败: {str(e)}")


@router.get("/session/{session_id}/status")
async def get_session_status(session_id: str = Path(..., description="会话ID")):
    """获取歧义解决会话状态"""
    try:
        if session_id not in active_disambiguation_sessions:
            raise HTTPException(status_code=404, detail="会话不存在")
        
        session = active_disambiguation_sessions[session_id]
        
        return {
            "session_id": session_id,
            "status": session.get('status'),
            "created_at": session.get('created_at'),
            "user_id": session.get('user_id'),
            "interaction_count": len(session.get('interactions', [])),
            "resolved_intent": session.get('resolved_intent'),
            "resolution_confidence": session.get('resolution_confidence')
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取会话状态失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"获取会话状态失败: {str(e)}")


@router.get("/suggestions/{session_id}", response_model=SmartSuggestionResponse)
async def get_smart_suggestions(
    session_id: str = Path(..., description="会话ID"),
    suggestion_type: str = Query("intent", description="建议类型")
):
    """
    获取智能建议
    
    Args:
        session_id: 会话ID
        suggestion_type: 建议类型
        
    Returns:
        SmartSuggestionResponse: 智能建议响应
    """
    try:
        if session_id not in active_disambiguation_sessions:
            raise HTTPException(status_code=404, detail="会话不存在")
        
        session = active_disambiguation_sessions[session_id]
        
        suggestions = await _generate_smart_suggestions(
            session=session,
            suggestion_type=suggestion_type
        )
        
        return SmartSuggestionResponse(
            session_id=session_id,
            suggestion_type=suggestion_type,
            suggestions=suggestions,
            confidence_scores=[s.get('confidence', 0.0) for s in suggestions],
            reasoning=[s.get('reasoning', '') for s in suggestions],
            generated_at=datetime.now().isoformat()
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取智能建议失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"获取智能建议失败: {str(e)}")


@router.get("/history/{user_id}", response_model=DisambiguationHistoryResponse)
async def get_disambiguation_history(
    user_id: str = Path(..., description="用户ID"),
    limit: int = Query(10, ge=1, le=100, description="返回数量限制"),
    offset: int = Query(0, ge=0, description="偏移量")
):
    """
    获取用户的歧义解决历史
    
    Args:
        user_id: 用户ID
        limit: 返回数量限制
        offset: 偏移量
        
    Returns:
        DisambiguationHistoryResponse: 歧义解决历史响应
    """
    try:
        # 从活跃会话中筛选用户的历史记录
        user_sessions = []
        for session_id, session_data in active_disambiguation_sessions.items():
            if session_data.get('user_id') == user_id:
                user_sessions.append({
                    'session_id': session_id,
                    'created_at': session_data.get('created_at'),
                    'status': session_data.get('status'),
                    'resolved_intent': session_data.get('resolved_intent'),
                    'original_input': session_data.get('original_input'),
                    'resolution_confidence': session_data.get('resolution_confidence'),
                    'interaction_count': len(session_data.get('interactions', []))
                })
        
        # 按时间排序
        user_sessions.sort(key=lambda x: x['created_at'], reverse=True)
        
        # 应用分页
        paginated_sessions = user_sessions[offset:offset + limit]
        
        return DisambiguationHistoryResponse(
            user_id=user_id,
            total_sessions=len(user_sessions),
            sessions=paginated_sessions,
            pagination={
                "limit": limit,
                "offset": offset,
                "has_more": offset + limit < len(user_sessions)
            },
            statistics={
                "total_disambiguations": len(user_sessions),
                "resolved_count": sum(1 for s in user_sessions if s['status'] == 'resolved'),
                "success_rate": (sum(1 for s in user_sessions if s['status'] == 'resolved') / len(user_sessions)) if user_sessions else 0.0
            }
        )
        
    except Exception as e:
        logger.error(f"获取歧义历史失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"获取歧义历史失败: {str(e)}")


@router.get("/analytics", response_model=AmbiguityAnalyticsResponse)
async def get_ambiguity_analytics(
    detector: EnhancedAmbiguityDetector = Depends(get_ambiguity_detector),
    generator: ClarificationQuestionGenerator = Depends(get_clarification_generator)
):
    """
    获取歧义解决系统分析数据
    
    Args:
        detector: 歧义检测器
        generator: 澄清问题生成器
        
    Returns:
        AmbiguityAnalyticsResponse: 歧义分析响应
    """
    try:
        # 获取检测器统计
        detection_stats = await detector.get_detection_statistics()
        
        # 获取生成器统计
        generation_stats = generator.get_generator_statistics()
        
        # 计算活跃会话统计
        session_stats = _calculate_session_statistics()
        
        return AmbiguityAnalyticsResponse(
            total_detections=detection_stats.get('total_detections', 0),
            ambiguous_detections=detection_stats.get('ambiguous_detections', 0),
            resolution_success_rate=session_stats.get('success_rate', 0.0),
            average_resolution_time=session_stats.get('avg_resolution_time', 0.0),
            top_ambiguity_types=detection_stats.get('top_ambiguity_types', []),
            clarification_effectiveness=generation_stats.get('clarification_effectiveness', {}),
            system_performance={
                "detection_accuracy": detection_stats.get('accuracy', 0.0),
                "generation_confidence": generation_stats.get('avg_confidence', 0.0),
                "user_satisfaction": session_stats.get('user_satisfaction', 0.0)
            },
            trends={
                "daily_ambiguity_rate": session_stats.get('daily_trends', []),
                "resolution_patterns": session_stats.get('resolution_patterns', {})
            },
            generated_at=datetime.now().isoformat()
        )
        
    except Exception as e:
        logger.error(f"获取歧义分析失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"获取歧义分析失败: {str(e)}")


# 辅助函数

async def _generate_suggested_responses(
    clarification: ClarificationQuestion,
    candidates: List[Dict],
    user_input: str
) -> List[str]:
    """生成建议响应"""
    try:
        suggestions = []
        
        if clarification.clarification_type.value == "intent_clarification":
            for i, candidate in enumerate(candidates[:3], 1):
                display_name = candidate.get('display_name', candidate.get('intent_name', ''))
                suggestions.append(f"{i}. {display_name}")
        elif clarification.clarification_type.value == "slot_clarification":
            suggestions.extend(clarification.suggested_values[:3])
        else:
            suggestions = ["是", "不是", "我需要更多选项"]
        
        return suggestions
        
    except Exception as e:
        logger.error(f"生成建议响应失败: {str(e)}")
        return ["请选择一个选项"]


async def _parse_user_response(
    user_response: str,
    session: Dict[str, Any],
    response_type: str
) -> Dict[str, Any]:
    """解析用户响应"""
    try:
        candidates = session.get('candidates', [])
        clarification = session.get('clarification')
        
        # 添加交互记录
        if 'interactions' not in session:
            session['interactions'] = []
        
        session['interactions'].append({
            'user_response': user_response,
            'response_type': response_type,
            'timestamp': datetime.now().isoformat()
        })
        
        if response_type == "intent_selection":
            # 解析意图选择
            try:
                # 尝试解析数字选择
                choice_num = int(user_response.strip())
                if 1 <= choice_num <= len(candidates):
                    selected_candidate = candidates[choice_num - 1]
                    return {
                        'success': True,
                        'resolved_intent': selected_candidate['intent_name'],
                        'confidence': selected_candidate.get('confidence', 0.8),
                        'explanation': f"用户选择了选项 {choice_num}: {selected_candidate.get('display_name', selected_candidate['intent_name'])}",
                        'next_steps': ["继续处理所选意图"],
                        'context_updates': {
                            'resolved_ambiguity': True,
                            'selection_method': 'explicit_choice'
                        }
                    }
            except ValueError:
                # 尝试文本匹配
                for candidate in candidates:
                    intent_name = candidate.get('display_name', candidate['intent_name']).lower()
                    if intent_name in user_response.lower():
                        return {
                            'success': True,
                            'resolved_intent': candidate['intent_name'],
                            'confidence': candidate.get('confidence', 0.7),
                            'explanation': f"用户通过文本描述选择了: {candidate.get('display_name', candidate['intent_name'])}",
                            'next_steps': ["继续处理所选意图"],
                            'context_updates': {
                                'resolved_ambiguity': True,
                                'selection_method': 'text_match'
                            }
                        }
        
        elif response_type == "confirmation":
            # 解析确认响应
            positive_responses = ["是", "对", "好", "确认", "yes", "y", "OK", "ok"]
            negative_responses = ["不是", "不对", "错", "不", "no", "n"]
            
            if any(pos in user_response for pos in positive_responses):
                # 确认最高置信度的候选
                best_candidate = max(candidates, key=lambda x: x.get('confidence', 0.0))
                return {
                    'success': True,
                    'resolved_intent': best_candidate['intent_name'],
                    'confidence': best_candidate.get('confidence', 0.8),
                    'explanation': f"用户确认了推荐的意图: {best_candidate.get('display_name', best_candidate['intent_name'])}",
                    'next_steps': ["继续处理确认的意图"],
                    'context_updates': {
                        'resolved_ambiguity': True,
                        'selection_method': 'confirmation'
                    }
                }
            elif any(neg in user_response for neg in negative_responses):
                return {
                    'success': False,
                    'explanation': "用户拒绝了推荐的意图",
                    'next_steps': ["提供更多选项"],
                    'follow_up_question': "请告诉我您具体想要什么服务？"
                }
        
        # 默认处理
        return {
            'success': False,
            'explanation': "无法理解用户的响应",
            'next_steps': ["请求更明确的回答"],
            'follow_up_question': "请选择一个具体的选项或提供更详细的说明。"
        }
        
    except Exception as e:
        logger.error(f"解析用户响应失败: {str(e)}")
        return {
            'success': False,
            'explanation': f"响应解析错误: {str(e)}",
            'next_steps': ["请重新输入"],
            'follow_up_question': "请重新选择或提供更明确的答案。"
        }


async def _generate_smart_suggestions(
    session: Dict[str, Any],
    suggestion_type: str
) -> List[Dict[str, Any]]:
    """生成智能建议"""
    try:
        suggestions = []
        candidates = session.get('candidates', [])
        
        if suggestion_type == "intent":
            # 基于置信度和用户偏好排序
            sorted_candidates = sorted(candidates, key=lambda x: x.get('confidence', 0.0), reverse=True)
            
            for candidate in sorted_candidates[:3]:
                suggestions.append({
                    'type': 'intent',
                    'value': candidate['intent_name'],
                    'display_name': candidate.get('display_name', candidate['intent_name']),
                    'confidence': candidate.get('confidence', 0.0),
                    'reasoning': f"基于语义分析，置信度: {candidate.get('confidence', 0.0):.2f}"
                })
        
        elif suggestion_type == "clarification":
            # 生成澄清建议
            clarification = session.get('clarification')
            if clarification:
                for value in clarification.suggested_values[:3]:
                    suggestions.append({
                        'type': 'clarification',
                        'value': value,
                        'confidence': 0.8,
                        'reasoning': "基于上下文分析的建议选项"
                    })
        
        return suggestions
        
    except Exception as e:
        logger.error(f"生成智能建议失败: {str(e)}")
        return []


def _calculate_session_statistics() -> Dict[str, Any]:
    """计算会话统计"""
    try:
        total_sessions = len(active_disambiguation_sessions)
        resolved_sessions = sum(
            1 for session in active_disambiguation_sessions.values()
            if session.get('status') == 'resolved'
        )
        
        success_rate = resolved_sessions / total_sessions if total_sessions > 0 else 0.0
        
        # 计算平均解决时间
        resolution_times = []
        for session in active_disambiguation_sessions.values():
            if session.get('resolved_at') and session.get('created_at'):
                try:
                    created = datetime.fromisoformat(session['created_at'])
                    resolved = datetime.fromisoformat(session['resolved_at'])
                    resolution_times.append((resolved - created).total_seconds())
                except Exception:
                    continue
        
        avg_resolution_time = sum(resolution_times) / len(resolution_times) if resolution_times else 0.0
        
        return {
            'total_sessions': total_sessions,
            'resolved_sessions': resolved_sessions,
            'success_rate': success_rate,
            'avg_resolution_time': avg_resolution_time,
            'user_satisfaction': 0.85,  # 模拟数据
            'daily_trends': [],  # 实际实现中需要从数据库获取
            'resolution_patterns': {}  # 实际实现中需要分析历史数据
        }
        
    except Exception as e:
        logger.error(f"计算会话统计失败: {str(e)}")
        return {}


async def _cleanup_session_later(session_id: str, delay: int = 300):
    """延迟清理会话"""
    try:
        await asyncio.sleep(delay)
        if session_id in active_disambiguation_sessions:
            del active_disambiguation_sessions[session_id]
            logger.info(f"清理会话: {session_id}")
    except Exception as e:
        logger.error(f"会话清理失败: {str(e)}")