"""
增强歧义解决服务 (TASK-035)
集成歧义检测、澄清问题生成和交互式解决流程的统一服务
"""
from typing import Dict, List, Optional, Any, Tuple
import asyncio
import logging
from datetime import datetime, timedelta
from uuid import uuid4
from dataclasses import dataclass
from enum import Enum

from ..core.ambiguity_detector import EnhancedAmbiguityDetector, AmbiguityAnalysis, AmbiguityType
from ..core.clarification_question_generator import (
    ClarificationQuestionGenerator, ClarificationContext, ClarificationQuestion,
    ClarificationType, ClarificationLevel, ClarificationStyle
)
from ..schemas.ambiguity_resolution import (
    AmbiguityResolutionStatus, AmbiguityResolutionMetrics
)
from ..config.settings import get_settings
from ..utils.logger import get_logger
from ..utils.cache_service import CacheService
from ..utils.context_manager import ContextManager

logger = get_logger(__name__)


class DisambiguationStrategy(Enum):
    """歧义解决策略"""
    AUTOMATIC = "automatic"           # 自动解决
    INTERACTIVE = "interactive"       # 交互式解决
    GUIDED = "guided"                # 引导式解决
    HYBRID = "hybrid"                # 混合策略


class ResolutionPriority(Enum):
    """解决优先级"""
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"


@dataclass
class DisambiguationContext:
    """歧义解决上下文"""
    user_id: str
    session_id: str
    original_input: str
    candidates: List[Dict[str, Any]]
    conversation_context: Optional[Dict[str, Any]]
    user_preferences: Dict[str, Any]
    resolution_strategy: DisambiguationStrategy
    priority: ResolutionPriority
    timeout_minutes: int = 30
    max_clarification_rounds: int = 3
    current_round: int = 0
    created_at: datetime = None
    metadata: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now()
        if self.metadata is None:
            self.metadata = {}


@dataclass
class DisambiguationResult:
    """歧义解决结果"""
    session_id: str
    status: AmbiguityResolutionStatus
    resolved_intent: Optional[str]
    confidence: float
    resolution_method: str
    clarification_history: List[Dict[str, Any]]
    user_interactions: List[Dict[str, Any]]
    processing_time_seconds: float
    error_message: Optional[str] = None
    metadata: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


class EnhancedDisambiguationService:
    """增强歧义解决服务"""
    
    def __init__(self):
        self.settings = get_settings()
        self.detector = EnhancedAmbiguityDetector(self.settings)
        self.generator = ClarificationQuestionGenerator()
        self.cache_service = CacheService()
        self.context_manager = ContextManager()
        
        # 活跃的歧义解决会话
        self.active_sessions: Dict[str, DisambiguationContext] = {}
        
        # 性能指标跟踪
        self.metrics = AmbiguityResolutionMetrics()
        
        # 用户学习配置文件
        self.user_profiles: Dict[str, Dict[str, Any]] = {}
        
        # 策略配置
        self.strategy_configs = self._initialize_strategy_configs()
        
        # 启动清理任务
        asyncio.create_task(self._session_cleanup_task())
    
    def _initialize_strategy_configs(self) -> Dict[str, Dict[str, Any]]:
        """初始化策略配置"""
        return {
            DisambiguationStrategy.AUTOMATIC.value: {
                "confidence_threshold": 0.8,
                "max_candidates": 5,
                "timeout_seconds": 30,
                "fallback_to_interactive": True
            },
            DisambiguationStrategy.INTERACTIVE.value: {
                "max_clarification_rounds": 3,
                "response_timeout_seconds": 300,
                "enable_smart_suggestions": True,
                "adaptive_clarification_style": True
            },
            DisambiguationStrategy.GUIDED.value: {
                "step_by_step_clarification": True,
                "provide_explanations": True,
                "show_confidence_scores": True,
                "allow_backtracking": True
            },
            DisambiguationStrategy.HYBRID.value: {
                "auto_threshold": 0.9,
                "interactive_threshold": 0.3,
                "guided_threshold": 0.6,
                "dynamic_strategy_switching": True
            }
        }
    
    async def start_disambiguation(self, 
                                 user_id: str,
                                 user_input: str,
                                 candidates: List[Dict[str, Any]],
                                 conversation_context: Optional[Dict[str, Any]] = None,
                                 user_preferences: Optional[Dict[str, Any]] = None,
                                 strategy: DisambiguationStrategy = DisambiguationStrategy.HYBRID,
                                 priority: ResolutionPriority = ResolutionPriority.NORMAL) -> DisambiguationResult:
        """
        开始歧义解决流程
        
        Args:
            user_id: 用户ID
            user_input: 用户输入
            candidates: 候选意图列表
            conversation_context: 对话上下文
            user_preferences: 用户偏好
            strategy: 解决策略
            priority: 优先级
            
        Returns:
            DisambiguationResult: 解决结果
        """
        start_time = datetime.now()
        session_id = str(uuid4())
        
        try:
            logger.info(f"开始歧义解决: 会话ID={session_id}, 用户={user_id}, 策略={strategy.value}")
            
            # 创建解决上下文
            context = DisambiguationContext(
                user_id=user_id,
                session_id=session_id,
                original_input=user_input,
                candidates=candidates,
                conversation_context=conversation_context,
                user_preferences=user_preferences or {},
                resolution_strategy=strategy,
                priority=priority,
                created_at=start_time
            )
            
            # 保存活跃会话
            self.active_sessions[session_id] = context
            
            # 首先进行歧义检测
            ambiguity_analysis = await self.detector.detect_ambiguity(
                candidates=candidates,
                user_input=user_input,
                conversation_context=conversation_context
            )
            
            # 根据检测结果和策略选择解决方法
            result = await self._resolve_ambiguity(context, ambiguity_analysis)
            
            # 更新性能指标
            processing_time = (datetime.now() - start_time).total_seconds()
            result.processing_time_seconds = processing_time
            
            await self._update_metrics(result)
            await self._update_user_profile(user_id, result)
            
            logger.info(f"歧义解决完成: 会话ID={session_id}, 状态={result.status.value}, "
                       f"耗时={processing_time:.2f}s")
            
            return result
            
        except Exception as e:
            logger.error(f"歧义解决失败: 会话ID={session_id}, 错误={str(e)}")
            
            # 清理会话
            if session_id in self.active_sessions:
                del self.active_sessions[session_id]
            
            # 返回错误结果
            return DisambiguationResult(
                session_id=session_id,
                status=AmbiguityResolutionStatus.FAILED,
                resolved_intent=None,
                confidence=0.0,
                resolution_method="error",
                clarification_history=[],
                user_interactions=[],
                processing_time_seconds=(datetime.now() - start_time).total_seconds(),
                error_message=str(e)
            )
    
    async def _resolve_ambiguity(self, 
                               context: DisambiguationContext,
                               analysis: AmbiguityAnalysis) -> DisambiguationResult:
        """
        解决歧义
        
        Args:
            context: 解决上下文
            analysis: 歧义分析结果
            
        Returns:
            DisambiguationResult: 解决结果
        """
        try:
            # 如果没有歧义，直接返回最佳候选
            if not analysis.is_ambiguous:
                best_candidate = max(context.candidates, key=lambda x: x.get('confidence', 0.0))
                
                return DisambiguationResult(
                    session_id=context.session_id,
                    status=AmbiguityResolutionStatus.NO_AMBIGUITY,
                    resolved_intent=best_candidate['intent_name'],
                    confidence=best_candidate.get('confidence', 0.0),
                    resolution_method="automatic_no_ambiguity",
                    clarification_history=[],
                    user_interactions=[],
                    processing_time_seconds=0.0,
                    metadata={"analysis": analysis.analysis_metadata}
                )
            
            # 根据策略选择解决方法
            if context.resolution_strategy == DisambiguationStrategy.AUTOMATIC:
                return await self._resolve_automatically(context, analysis)
            elif context.resolution_strategy == DisambiguationStrategy.INTERACTIVE:
                return await self._resolve_interactively(context, analysis)
            elif context.resolution_strategy == DisambiguationStrategy.GUIDED:
                return await self._resolve_with_guidance(context, analysis)
            elif context.resolution_strategy == DisambiguationStrategy.HYBRID:
                return await self._resolve_with_hybrid_strategy(context, analysis)
            else:
                raise ValueError(f"未知的解决策略: {context.resolution_strategy}")
                
        except Exception as e:
            logger.error(f"解决歧义失败: {str(e)}")
            raise
    
    async def _resolve_automatically(self, 
                                   context: DisambiguationContext,
                                   analysis: AmbiguityAnalysis) -> DisambiguationResult:
        """自动解决歧义"""
        try:
            config = self.strategy_configs[DisambiguationStrategy.AUTOMATIC.value]
            
            # 检查是否有足够高置信度的候选
            confidence_threshold = config["confidence_threshold"]
            best_candidate = max(context.candidates, key=lambda x: x.get('confidence', 0.0))
            
            if best_candidate.get('confidence', 0.0) >= confidence_threshold:
                return DisambiguationResult(
                    session_id=context.session_id,
                    status=AmbiguityResolutionStatus.RESOLVED,
                    resolved_intent=best_candidate['intent_name'],
                    confidence=best_candidate.get('confidence', 0.0),
                    resolution_method="automatic_high_confidence",
                    clarification_history=[],
                    user_interactions=[],
                    processing_time_seconds=0.0,
                    metadata={"threshold": confidence_threshold}
                )
            
            # 尝试基于用户偏好和历史进行自动解决
            auto_resolved = await self._attempt_preference_based_resolution(context, analysis)
            if auto_resolved:
                return auto_resolved
            
            # 如果配置允许，回退到交互式解决
            if config.get("fallback_to_interactive", False):
                context.resolution_strategy = DisambiguationStrategy.INTERACTIVE
                return await self._resolve_interactively(context, analysis)
            
            # 无法自动解决
            return DisambiguationResult(
                session_id=context.session_id,
                status=AmbiguityResolutionStatus.FAILED,
                resolved_intent=None,
                confidence=0.0,
                resolution_method="automatic_failed",
                clarification_history=[],
                user_interactions=[],
                processing_time_seconds=0.0,
                error_message="无法自动解决歧义"
            )
            
        except Exception as e:
            logger.error(f"自动解决歧义失败: {str(e)}")
            raise
    
    async def _resolve_interactively(self, 
                                   context: DisambiguationContext,
                                   analysis: AmbiguityAnalysis) -> DisambiguationResult:
        """交互式解决歧义"""
        try:
            # 生成澄清问题
            clarification_context = self._build_clarification_context(context, analysis)
            clarification = await self.generator.generate_clarification_question(
                context=clarification_context,
                user_id=context.user_id
            )
            
            # 创建交互式解决结果（等待用户输入）
            return DisambiguationResult(
                session_id=context.session_id,
                status=AmbiguityResolutionStatus.PENDING_USER_INPUT,
                resolved_intent=None,
                confidence=0.0,
                resolution_method="interactive_clarification",
                clarification_history=[{
                    "question": clarification.question,
                    "type": clarification.clarification_type.value,
                    "style": clarification.style.value,
                    "suggested_values": clarification.suggested_values,
                    "urgency": clarification.urgency,
                    "timestamp": datetime.now().isoformat()
                }],
                user_interactions=[],
                processing_time_seconds=0.0,
                metadata={
                    "clarification": clarification,
                    "analysis": analysis.analysis_metadata
                }
            )
            
        except Exception as e:
            logger.error(f"交互式解决歧义失败: {str(e)}")
            raise
    
    async def _resolve_with_guidance(self, 
                                   context: DisambiguationContext,
                                   analysis: AmbiguityAnalysis) -> DisambiguationResult:
        """引导式解决歧义"""
        try:
            # 分步骤引导用户解决歧义
            guidance_steps = await self._generate_guidance_steps(context, analysis)
            
            return DisambiguationResult(
                session_id=context.session_id,
                status=AmbiguityResolutionStatus.PENDING_USER_INPUT,
                resolved_intent=None,
                confidence=0.0,
                resolution_method="guided_resolution",
                clarification_history=[],
                user_interactions=[],
                processing_time_seconds=0.0,
                metadata={
                    "guidance_steps": guidance_steps,
                    "current_step": 0,
                    "analysis": analysis.analysis_metadata
                }
            )
            
        except Exception as e:
            logger.error(f"引导式解决歧义失败: {str(e)}")
            raise
    
    async def _resolve_with_hybrid_strategy(self, 
                                          context: DisambiguationContext,
                                          analysis: AmbiguityAnalysis) -> DisambiguationResult:
        """混合策略解决歧义"""
        try:
            config = self.strategy_configs[DisambiguationStrategy.HYBRID.value]
            
            # 根据歧义分数和置信度选择最佳策略
            ambiguity_score = analysis.ambiguity_score
            best_confidence = max(candidate.get('confidence', 0.0) for candidate in context.candidates)
            
            if best_confidence >= config["auto_threshold"]:
                # 高置信度，使用自动解决
                context.resolution_strategy = DisambiguationStrategy.AUTOMATIC
                return await self._resolve_automatically(context, analysis)
            elif ambiguity_score <= config["interactive_threshold"]:
                # 低歧义，使用交互式解决
                context.resolution_strategy = DisambiguationStrategy.INTERACTIVE
                return await self._resolve_interactively(context, analysis)
            elif ambiguity_score <= config["guided_threshold"]:
                # 中等歧义，使用引导式解决
                context.resolution_strategy = DisambiguationStrategy.GUIDED
                return await self._resolve_with_guidance(context, analysis)
            else:
                # 高歧义，使用交互式解决
                context.resolution_strategy = DisambiguationStrategy.INTERACTIVE
                return await self._resolve_interactively(context, analysis)
                
        except Exception as e:
            logger.error(f"混合策略解决歧义失败: {str(e)}")
            raise
    
    async def handle_user_response(self, 
                                 session_id: str,
                                 user_response: str,
                                 response_type: str = "text") -> DisambiguationResult:
        """
        处理用户的歧义解决响应
        
        Args:
            session_id: 会话ID
            user_response: 用户响应
            response_type: 响应类型
            
        Returns:
            DisambiguationResult: 处理结果
        """
        try:
            if session_id not in self.active_sessions:
                raise ValueError(f"会话不存在或已过期: {session_id}")
            
            context = self.active_sessions[session_id]
            
            logger.info(f"处理用户响应: 会话ID={session_id}, 响应={user_response[:50]}...")
            
            # 记录用户交互
            interaction = {
                "response": user_response,
                "response_type": response_type,
                "round": context.current_round,
                "timestamp": datetime.now().isoformat()
            }
            
            # 解析用户响应
            parsing_result = await self._parse_user_response(context, user_response, response_type)
            
            if parsing_result["success"]:
                # 歧义已解决
                result = DisambiguationResult(
                    session_id=session_id,
                    status=AmbiguityResolutionStatus.RESOLVED,
                    resolved_intent=parsing_result["resolved_intent"],
                    confidence=parsing_result["confidence"],
                    resolution_method="user_selection",
                    clarification_history=parsing_result.get("clarification_history", []),
                    user_interactions=[interaction],
                    processing_time_seconds=0.0,
                    metadata=parsing_result.get("metadata", {})
                )
                
                # 清理会话
                del self.active_sessions[session_id]
                
                logger.info(f"歧义已解决: 会话ID={session_id}, 意图={parsing_result['resolved_intent']}")
                
                return result
            else:
                # 需要进一步澄清
                context.current_round += 1
                
                if context.current_round >= context.max_clarification_rounds:
                    # 超过最大轮数，解决失败
                    result = DisambiguationResult(
                        session_id=session_id,
                        status=AmbiguityResolutionStatus.FAILED,
                        resolved_intent=None,
                        confidence=0.0,
                        resolution_method="max_rounds_exceeded",
                        clarification_history=parsing_result.get("clarification_history", []),
                        user_interactions=[interaction],
                        processing_time_seconds=0.0,
                        error_message="超过最大澄清轮数"
                    )
                    
                    # 清理会话
                    del self.active_sessions[session_id]
                    
                    return result
                
                # 生成后续澄清问题
                follow_up_result = await self._generate_follow_up_clarification(context, parsing_result)
                
                return DisambiguationResult(
                    session_id=session_id,
                    status=AmbiguityResolutionStatus.PENDING_CLARIFICATION,
                    resolved_intent=None,
                    confidence=0.0,
                    resolution_method="follow_up_clarification",
                    clarification_history=follow_up_result.get("clarification_history", []),
                    user_interactions=[interaction],
                    processing_time_seconds=0.0,
                    metadata=follow_up_result.get("metadata", {})
                )
                
        except Exception as e:
            logger.error(f"处理用户响应失败: 会话ID={session_id}, 错误={str(e)}")
            
            # 清理会话
            if session_id in self.active_sessions:
                del self.active_sessions[session_id]
            
            return DisambiguationResult(
                session_id=session_id,
                status=AmbiguityResolutionStatus.FAILED,
                resolved_intent=None,
                confidence=0.0,
                resolution_method="response_handling_error",
                clarification_history=[],
                user_interactions=[],
                processing_time_seconds=0.0,
                error_message=str(e)
            )
    
    def _build_clarification_context(self, 
                                   context: DisambiguationContext,
                                   analysis: AmbiguityAnalysis) -> ClarificationContext:
        """构建澄清上下文"""
        return ClarificationContext(
            user_input=context.original_input,
            parsed_intents=context.candidates,
            extracted_slots=context.conversation_context.get('current_slots', {}) if context.conversation_context else {},
            ambiguity_analysis=analysis,
            conversation_history=context.conversation_context.get('history', []) if context.conversation_context else [],
            user_preferences=context.user_preferences,
            current_intent=context.conversation_context.get('current_intent') if context.conversation_context else None,
            incomplete_slots=[],
            conflicting_values={},
            confidence_scores={
                candidate['intent_name']: candidate.get('confidence', 0.0)
                for candidate in context.candidates
            }
        )
    
    async def _attempt_preference_based_resolution(self, 
                                                 context: DisambiguationContext,
                                                 analysis: AmbiguityAnalysis) -> Optional[DisambiguationResult]:
        """基于用户偏好尝试自动解决"""
        try:
            user_profile = self.user_profiles.get(context.user_id, {})
            
            # 检查用户历史偏好
            if 'preferred_intents' in user_profile:
                for candidate in context.candidates:
                    intent_name = candidate['intent_name']
                    if intent_name in user_profile['preferred_intents']:
                        preference_score = user_profile['preferred_intents'][intent_name]
                        
                        # 结合偏好分数和原始置信度
                        combined_confidence = (candidate.get('confidence', 0.0) * 0.7 + preference_score * 0.3)
                        
                        if combined_confidence >= 0.8:
                            return DisambiguationResult(
                                session_id=context.session_id,
                                status=AmbiguityResolutionStatus.RESOLVED,
                                resolved_intent=intent_name,
                                confidence=combined_confidence,
                                resolution_method="preference_based",
                                clarification_history=[],
                                user_interactions=[],
                                processing_time_seconds=0.0,
                                metadata={"preference_score": preference_score}
                            )
            
            return None
            
        except Exception as e:
            logger.error(f"基于偏好的解决失败: {str(e)}")
            return None
    
    async def _generate_guidance_steps(self, 
                                     context: DisambiguationContext,
                                     analysis: AmbiguityAnalysis) -> List[Dict[str, Any]]:
        """生成引导步骤"""
        try:
            steps = []
            
            # 第一步：解释检测到的歧义
            steps.append({
                "step": 1,
                "type": "explanation",
                "title": "歧义说明",
                "content": f"我检测到您的需求可能有{len(context.candidates)}种理解方式",
                "details": {
                    "ambiguity_score": analysis.ambiguity_score,
                    "primary_type": analysis.primary_type.value
                }
            })
            
            # 第二步：展示候选选项
            steps.append({
                "step": 2,
                "type": "options_display",
                "title": "可能的选项",
                "content": "以下是我找到的可能匹配：",
                "options": [
                    {
                        "index": i + 1,
                        "intent": candidate['intent_name'],
                        "display_name": candidate.get('display_name', candidate['intent_name']),
                        "confidence": candidate.get('confidence', 0.0),
                        "description": candidate.get('description', '')
                    }
                    for i, candidate in enumerate(context.candidates[:5])
                ]
            })
            
            # 第三步：请求用户选择
            steps.append({
                "step": 3,
                "type": "user_selection",
                "title": "请选择",
                "content": "请选择最符合您需求的选项，或告诉我更多信息",
                "expected_response": "selection_or_clarification"
            })
            
            return steps
            
        except Exception as e:
            logger.error(f"生成引导步骤失败: {str(e)}")
            return []
    
    async def _parse_user_response(self, 
                                 context: DisambiguationContext,
                                 user_response: str,
                                 response_type: str) -> Dict[str, Any]:
        """解析用户响应"""
        try:
            if response_type == "intent_selection":
                # 处理意图选择
                try:
                    choice = int(user_response.strip())
                    if 1 <= choice <= len(context.candidates):
                        selected = context.candidates[choice - 1]
                        return {
                            "success": True,
                            "resolved_intent": selected['intent_name'],
                            "confidence": selected.get('confidence', 0.8),
                            "method": "explicit_selection"
                        }
                except ValueError:
                    # 尝试文本匹配
                    for candidate in context.candidates:
                        display_name = candidate.get('display_name', candidate['intent_name']).lower()
                        if display_name in user_response.lower():
                            return {
                                "success": True,
                                "resolved_intent": candidate['intent_name'],
                                "confidence": candidate.get('confidence', 0.7),
                                "method": "text_matching"
                            }
            
            elif response_type == "confirmation":
                # 处理确认响应
                positive = ["是", "对", "好", "确认", "yes", "y"]
                negative = ["不是", "不对", "错", "no", "n"]
                
                if any(pos in user_response for pos in positive):
                    best = max(context.candidates, key=lambda x: x.get('confidence', 0.0))
                    return {
                        "success": True,
                        "resolved_intent": best['intent_name'],
                        "confidence": best.get('confidence', 0.8),
                        "method": "confirmation"
                    }
                elif any(neg in user_response for neg in negative):
                    return {
                        "success": False,
                        "reason": "user_rejection",
                        "follow_up_needed": True
                    }
            
            # 默认处理
            return {
                "success": False,
                "reason": "unclear_response",
                "follow_up_needed": True,
                "user_response": user_response
            }
            
        except Exception as e:
            logger.error(f"解析用户响应失败: {str(e)}")
            return {
                "success": False,
                "reason": "parsing_error",
                "error": str(e)
            }
    
    async def _generate_follow_up_clarification(self, 
                                              context: DisambiguationContext,
                                              parsing_result: Dict[str, Any]) -> Dict[str, Any]:
        """生成后续澄清"""
        try:
            # 根据解析结果生成适当的后续问题
            if parsing_result.get("reason") == "user_rejection":
                follow_up = "请告诉我您具体想要什么服务？"
            elif parsing_result.get("reason") == "unclear_response":
                follow_up = "请选择一个具体的选项或提供更详细的说明。"
            else:
                follow_up = "请重新选择或提供更明确的答案。"
            
            return {
                "clarification_history": [{
                    "question": follow_up,
                    "type": "follow_up",
                    "round": context.current_round,
                    "timestamp": datetime.now().isoformat()
                }],
                "metadata": {
                    "parsing_result": parsing_result,
                    "round": context.current_round
                }
            }
            
        except Exception as e:
            logger.error(f"生成后续澄清失败: {str(e)}")
            return {}
    
    async def _update_metrics(self, result: DisambiguationResult):
        """更新性能指标"""
        try:
            # 更新解决成功率
            if result.status == AmbiguityResolutionStatus.RESOLVED:
                self.metrics.resolution_success_rate = (
                    self.metrics.resolution_success_rate * 0.9 + 0.1
                )
            
            # 更新平均响应时间
            self.metrics.response_time_p95 = max(
                self.metrics.response_time_p95,
                result.processing_time_seconds * 1000
            )
            
        except Exception as e:
            logger.error(f"更新指标失败: {str(e)}")
    
    async def _update_user_profile(self, user_id: str, result: DisambiguationResult):
        """更新用户配置文件"""
        try:
            if user_id not in self.user_profiles:
                self.user_profiles[user_id] = {
                    "preferred_intents": {},
                    "interaction_count": 0,
                    "success_rate": 0.0
                }
            
            profile = self.user_profiles[user_id]
            profile["interaction_count"] += 1
            
            # 更新偏好
            if result.status == AmbiguityResolutionStatus.RESOLVED and result.resolved_intent:
                intent = result.resolved_intent
                if intent not in profile["preferred_intents"]:
                    profile["preferred_intents"][intent] = 0.5
                else:
                    profile["preferred_intents"][intent] = min(1.0, profile["preferred_intents"][intent] + 0.1)
            
            # 更新成功率
            if result.status == AmbiguityResolutionStatus.RESOLVED:
                success_count = profile["interaction_count"] * profile["success_rate"] + 1
                profile["success_rate"] = success_count / profile["interaction_count"]
            
        except Exception as e:
            logger.error(f"更新用户配置文件失败: {str(e)}")
    
    async def _session_cleanup_task(self):
        """会话清理任务"""
        while True:
            try:
                await asyncio.sleep(300)  # 每5分钟检查一次
                
                current_time = datetime.now()
                expired_sessions = []
                
                for session_id, context in self.active_sessions.items():
                    if current_time - context.created_at > timedelta(minutes=context.timeout_minutes):
                        expired_sessions.append(session_id)
                
                # 清理过期会话
                for session_id in expired_sessions:
                    del self.active_sessions[session_id]
                    logger.info(f"清理过期会话: {session_id}")
                
            except Exception as e:
                logger.error(f"会话清理任务失败: {str(e)}")
                await asyncio.sleep(60)
    
    def get_active_sessions_count(self) -> int:
        """获取活跃会话数"""
        return len(self.active_sessions)
    
    def get_metrics(self) -> AmbiguityResolutionMetrics:
        """获取性能指标"""
        return self.metrics
    
    async def get_session_status(self, session_id: str) -> Optional[Dict[str, Any]]:
        """获取会话状态"""
        if session_id not in self.active_sessions:
            return None
        
        context = self.active_sessions[session_id]
        
        return {
            "session_id": session_id,
            "user_id": context.user_id,
            "status": "active",
            "strategy": context.resolution_strategy.value,
            "priority": context.priority.value,
            "current_round": context.current_round,
            "max_rounds": context.max_clarification_rounds,
            "created_at": context.created_at.isoformat(),
            "timeout_at": (context.created_at + timedelta(minutes=context.timeout_minutes)).isoformat()
        }
    
    async def cancel_session(self, session_id: str) -> bool:
        """取消会话"""
        if session_id in self.active_sessions:
            del self.active_sessions[session_id]
            logger.info(f"取消会话: {session_id}")
            return True
        return False