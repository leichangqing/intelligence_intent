"""
歧义处理编排器
实现端到端歧义处理流程和质量监控
"""

from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from enum import Enum
import logging
from datetime import datetime, timedelta
import asyncio
import json
from collections import defaultdict

from .ambiguity_detector import EnhancedAmbiguityDetector, AmbiguityAnalysis
from .intelligent_question_generator import IntelligentQuestionGenerator, QuestionContext, GeneratedQuestion
from .advanced_choice_parser import AdvancedChoiceParser, ParseResult
from .multi_strategy_resolver import MultiStrategyResolver, ResolutionContext, ResolutionAttempt
from .adaptive_threshold_manager import AdaptiveThresholdManager
from ..utils.logger import get_logger

logger = get_logger(__name__)


class ProcessingStage(Enum):
    """处理阶段"""
    DETECTION = "detection"         # 歧义检测
    ANALYSIS = "analysis"           # 分析阶段
    RESOLUTION = "resolution"       # 解决阶段
    INTERACTION = "interaction"     # 交互阶段
    VALIDATION = "validation"       # 验证阶段
    COMPLETION = "completion"       # 完成阶段


class QualityMetric(Enum):
    """质量指标"""
    ACCURACY = "accuracy"           # 准确率
    EFFICIENCY = "efficiency"       # 效率
    USER_SATISFACTION = "user_satisfaction"  # 用户满意度
    RESOLUTION_RATE = "resolution_rate"      # 解决率
    RESPONSE_TIME = "response_time"          # 响应时间
    ERROR_RATE = "error_rate"               # 错误率


@dataclass
class ProcessingStep:
    """处理步骤"""
    stage: ProcessingStage
    step_name: str
    start_time: datetime
    end_time: Optional[datetime] = None
    duration: Optional[float] = None
    success: bool = False
    error_message: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class QualityScore:
    """质量评分"""
    metric: QualityMetric
    score: float
    confidence: float
    calculation_method: str
    timestamp: datetime
    details: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AmbiguitySession:
    """歧义处理会话"""
    session_id: str
    user_id: str
    conversation_id: int
    start_time: datetime
    end_time: Optional[datetime] = None
    total_duration: Optional[float] = None
    
    # 处理流程
    processing_steps: List[ProcessingStep] = field(default_factory=list)
    
    # 分析结果
    ambiguity_analysis: Optional[AmbiguityAnalysis] = None
    
    # 解决结果
    resolution_attempts: List[ResolutionAttempt] = field(default_factory=list)
    final_resolution: Optional[ResolutionAttempt] = None
    
    # 交互记录
    generated_questions: List[GeneratedQuestion] = field(default_factory=list)
    user_responses: List[ParseResult] = field(default_factory=list)
    
    # 质量评分
    quality_scores: List[QualityScore] = field(default_factory=list)
    
    # 最终状态
    success: bool = False
    selected_intent: Optional[str] = None
    user_satisfaction: Optional[float] = None
    
    # 元数据
    metadata: Dict[str, Any] = field(default_factory=dict)


class AmbiguityOrchestrator:
    """歧义处理编排器"""
    
    def __init__(self, settings):
        self.settings = settings
        
        # 初始化组件
        self.ambiguity_detector = EnhancedAmbiguityDetector(settings)
        self.question_generator = IntelligentQuestionGenerator()
        self.choice_parser = AdvancedChoiceParser()
        self.multi_resolver = MultiStrategyResolver()
        self.threshold_manager = AdaptiveThresholdManager(settings)
        
        # 会话管理
        self.active_sessions: Dict[str, AmbiguitySession] = {}
        self.completed_sessions: List[AmbiguitySession] = []
        
        # 质量监控
        self.quality_metrics: Dict[QualityMetric, List[float]] = defaultdict(list)
        self.performance_baselines = self._initialize_baselines()
        
        # 配置参数
        self.max_resolution_attempts = 3
        self.max_interaction_rounds = 5
        self.session_timeout = 300  # 5分钟
        
        # 统计信息
        self.processing_statistics = {
            'total_sessions': 0,
            'successful_sessions': 0,
            'auto_resolved_sessions': 0,
            'interactive_resolved_sessions': 0,
            'failed_sessions': 0,
            'avg_processing_time': 0.0,
            'avg_user_satisfaction': 0.0
        }
    
    def _initialize_baselines(self) -> Dict[QualityMetric, float]:
        """初始化质量基线"""
        return {
            QualityMetric.ACCURACY: 0.85,
            QualityMetric.EFFICIENCY: 0.8,
            QualityMetric.USER_SATISFACTION: 0.75,
            QualityMetric.RESOLUTION_RATE: 0.9,
            QualityMetric.RESPONSE_TIME: 2.0,  # 秒
            QualityMetric.ERROR_RATE: 0.1
        }
    
    async def process_ambiguity(self,
                              candidates: List[Dict],
                              user_input: str,
                              conversation_context: Dict,
                              user_id: str,
                              conversation_id: int) -> Tuple[Optional[str], AmbiguitySession]:
        """
        端到端歧义处理
        
        Args:
            candidates: 候选意图列表
            user_input: 用户输入
            conversation_context: 对话上下文
            user_id: 用户ID
            conversation_id: 对话ID
            
        Returns:
            Tuple[Optional[str], AmbiguitySession]: (解决的意图名称, 处理会话)
        """
        # 创建会话
        session = AmbiguitySession(
            session_id=f"{user_id}_{conversation_id}_{datetime.now().timestamp()}",
            user_id=user_id,
            conversation_id=conversation_id,
            start_time=datetime.now(),
            metadata={
                'user_input': user_input,
                'candidate_count': len(candidates),
                'initial_confidence': candidates[0].get('confidence', 0) if candidates else 0
            }
        )
        
        self.active_sessions[session.session_id] = session
        
        try:
            # 阶段1：歧义检测和分析
            ambiguity_analysis = await self._detect_and_analyze_ambiguity(
                session, candidates, user_input, conversation_context
            )
            
            if not ambiguity_analysis.is_ambiguous:
                # 没有歧义，直接返回最高置信度的候选
                return await self._complete_session_without_ambiguity(session, candidates)
            
            # 阶段2：尝试自动解决
            auto_resolved = await self._attempt_automatic_resolution(
                session, candidates, ambiguity_analysis, conversation_context
            )
            
            if auto_resolved:
                return await self._complete_session_with_resolution(session, auto_resolved)
            
            # 阶段3：交互式解决
            interactive_resolved = await self._attempt_interactive_resolution(
                session, candidates, ambiguity_analysis, conversation_context
            )
            
            if interactive_resolved:
                return await self._complete_session_with_resolution(session, interactive_resolved)
            
            # 所有方法都失败
            return await self._complete_session_with_failure(session)
            
        except Exception as e:
            logger.error(f"歧义处理失败: {str(e)}")
            return await self._complete_session_with_error(session, str(e))
        finally:
            # 移除活跃会话
            if session.session_id in self.active_sessions:
                del self.active_sessions[session.session_id]
    
    async def _detect_and_analyze_ambiguity(self,
                                          session: AmbiguitySession,
                                          candidates: List[Dict],
                                          user_input: str,
                                          conversation_context: Dict) -> AmbiguityAnalysis:
        """检测和分析歧义"""
        step = ProcessingStep(
            stage=ProcessingStage.DETECTION,
            step_name="ambiguity_detection",
            start_time=datetime.now()
        )
        
        try:
            # 使用增强的歧义检测器
            analysis = await self.ambiguity_detector.detect_ambiguity(
                candidates, user_input, conversation_context
            )
            
            session.ambiguity_analysis = analysis
            
            # 记录成功步骤
            step.end_time = datetime.now()
            step.duration = (step.end_time - step.start_time).total_seconds()
            step.success = True
            step.metadata = {
                'is_ambiguous': analysis.is_ambiguous,
                'ambiguity_score': analysis.ambiguity_score,
                'primary_type': analysis.primary_type.value if analysis.primary_type else None,
                'signal_count': len(analysis.signals)
            }
            
            # 计算质量指标
            await self._calculate_detection_quality(session, analysis)
            
            return analysis
            
        except Exception as e:
            step.end_time = datetime.now()
            step.duration = (step.end_time - step.start_time).total_seconds()
            step.success = False
            step.error_message = str(e)
            
            logger.error(f"歧义检测失败: {str(e)}")
            raise
        finally:
            session.processing_steps.append(step)
    
    async def _attempt_automatic_resolution(self,
                                          session: AmbiguitySession,
                                          candidates: List[Dict],
                                          analysis: AmbiguityAnalysis,
                                          conversation_context: Dict) -> Optional[str]:
        """尝试自动解决"""
        step = ProcessingStep(
            stage=ProcessingStage.RESOLUTION,
            step_name="automatic_resolution",
            start_time=datetime.now()
        )
        
        try:
            # 构建解决上下文
            resolution_context = ResolutionContext(
                user_id=session.user_id,
                conversation_id=session.conversation_id,
                ambiguity_analysis=analysis,
                candidates=candidates,
                conversation_history=conversation_context.get('history', []),
                user_preferences=conversation_context.get('user_preferences', {}),
                time_constraints=conversation_context.get('time_constraints', {}),
                current_session_data=conversation_context
            )
            
            # 使用多策略解决器
            resolved_intent, resolution_attempt = await self.multi_resolver.resolve_ambiguity(
                resolution_context
            )
            
            session.resolution_attempts.append(resolution_attempt)
            
            # 记录步骤
            step.end_time = datetime.now()
            step.duration = (step.end_time - step.start_time).total_seconds()
            step.success = resolved_intent is not None
            step.metadata = {
                'strategy': resolution_attempt.strategy.value,
                'result': resolution_attempt.result.value,
                'confidence': resolution_attempt.confidence,
                'selected_intent': resolved_intent.intent_name if resolved_intent else None
            }
            
            if resolved_intent:
                # 计算解决质量
                await self._calculate_resolution_quality(session, resolution_attempt)
                
                return resolved_intent.intent_name
            
            return None
            
        except Exception as e:
            step.end_time = datetime.now()
            step.duration = (step.end_time - step.start_time).total_seconds()
            step.success = False
            step.error_message = str(e)
            
            logger.error(f"自动解决失败: {str(e)}")
            return None
        finally:
            session.processing_steps.append(step)
    
    async def _attempt_interactive_resolution(self,
                                            session: AmbiguitySession,
                                            candidates: List[Dict],
                                            analysis: AmbiguityAnalysis,
                                            conversation_context: Dict) -> Optional[str]:
        """尝试交互式解决"""
        step = ProcessingStep(
            stage=ProcessingStage.INTERACTION,
            step_name="interactive_resolution",
            start_time=datetime.now()
        )
        
        try:
            # 生成歧义问题
            question_context = QuestionContext(
                conversation_history=conversation_context.get('history', []),
                current_intent_confidence=conversation_context.get('confidence', 0.5),
                ambiguity_analysis=analysis,
                user_engagement=conversation_context.get('user_engagement', 0.7),
                time_pressure=conversation_context.get('time_pressure', 0.3),
                turn_count=conversation_context.get('turn_count', 1)
            )
            
            generated_question = await self.question_generator.generate_disambiguation_question(
                candidates, analysis, question_context, session.user_id
            )
            
            session.generated_questions.append(generated_question)
            
            # 记录问题生成步骤
            step.end_time = datetime.now()
            step.duration = (step.end_time - step.start_time).total_seconds()
            step.success = True
            step.metadata = {
                'question_style': generated_question.style.value,
                'question_complexity': generated_question.complexity.value,
                'question_confidence': generated_question.confidence,
                'question_text': generated_question.question_text[:100]
            }
            
            # 计算交互质量
            await self._calculate_interaction_quality(session, generated_question)
            
            # 这里应该等待用户回应，但在演示中直接返回生成的问题
            # 实际应用中需要外部系统提供用户回应
            return None
            
        except Exception as e:
            step.end_time = datetime.now()
            step.duration = (step.end_time - step.start_time).total_seconds()
            step.success = False
            step.error_message = str(e)
            
            logger.error(f"交互式解决失败: {str(e)}")
            return None
        finally:
            session.processing_steps.append(step)
    
    async def handle_user_response(self,
                                 session_id: str,
                                 user_response: str,
                                 candidates: List[Dict]) -> Tuple[Optional[str], bool]:
        """
        处理用户回应
        
        Args:
            session_id: 会话ID
            user_response: 用户回应
            candidates: 候选意图列表
            
        Returns:
            Tuple[Optional[str], bool]: (解决的意图名称, 是否完成)
        """
        if session_id not in self.active_sessions:
            logger.warning(f"会话不存在: {session_id}")
            return None, False
        
        session = self.active_sessions[session_id]
        
        step = ProcessingStep(
            stage=ProcessingStage.VALIDATION,
            step_name="user_response_parsing",
            start_time=datetime.now()
        )
        
        try:
            # 解析用户回应
            parse_result = await self.choice_parser.parse_user_choice(
                user_response, candidates, session.user_id, session.metadata
            )
            
            session.user_responses.append(parse_result)
            
            # 记录解析步骤
            step.end_time = datetime.now()
            step.duration = (step.end_time - step.start_time).total_seconds()
            step.success = True
            step.metadata = {
                'choice_type': parse_result.choice_type.value,
                'selected_option': parse_result.selected_option,
                'confidence': parse_result.confidence,
                'confidence_level': parse_result.confidence_level.value
            }
            
            # 根据解析结果处理
            if parse_result.choice_type.value == 'negative':
                # 用户表示都不符合
                return await self._handle_negative_response(session)
            
            elif parse_result.choice_type.value == 'uncertain':
                # 用户不确定，需要更多帮助
                return await self._handle_uncertain_response(session, candidates)
            
            elif parse_result.selected_option:
                # 用户有明确选择
                return await self._handle_positive_response(session, parse_result, candidates)
            
            # 解析失败，需要重新询问
            return await self._handle_parse_failure(session, parse_result)
            
        except Exception as e:
            step.end_time = datetime.now()
            step.duration = (step.end_time - step.start_time).total_seconds()
            step.success = False
            step.error_message = str(e)
            
            logger.error(f"用户回应处理失败: {str(e)}")
            return None, False
        finally:
            session.processing_steps.append(step)
    
    async def _complete_session_without_ambiguity(self,
                                                session: AmbiguitySession,
                                                candidates: List[Dict]) -> Tuple[Optional[str], AmbiguitySession]:
        """完成无歧义会话"""
        session.end_time = datetime.now()
        session.total_duration = (session.end_time - session.start_time).total_seconds()
        session.success = True
        session.selected_intent = candidates[0]['intent_name'] if candidates else None
        
        # 计算最终质量分数
        await self._calculate_final_quality_scores(session)
        
        # 更新统计信息
        self._update_statistics(session)
        
        self.completed_sessions.append(session)
        
        return session.selected_intent, session
    
    async def _complete_session_with_resolution(self,
                                              session: AmbiguitySession,
                                              resolved_intent: str) -> Tuple[Optional[str], AmbiguitySession]:
        """完成已解决会话"""
        session.end_time = datetime.now()
        session.total_duration = (session.end_time - session.start_time).total_seconds()
        session.success = True
        session.selected_intent = resolved_intent
        
        # 设置最终解决方案
        if session.resolution_attempts:
            session.final_resolution = session.resolution_attempts[-1]
        
        # 计算最终质量分数
        await self._calculate_final_quality_scores(session)
        
        # 更新统计信息
        self._update_statistics(session)
        
        self.completed_sessions.append(session)
        
        return resolved_intent, session
    
    async def _complete_session_with_failure(self,
                                           session: AmbiguitySession) -> Tuple[Optional[str], AmbiguitySession]:
        """完成失败会话"""
        session.end_time = datetime.now()
        session.total_duration = (session.end_time - session.start_time).total_seconds()
        session.success = False
        
        # 计算最终质量分数
        await self._calculate_final_quality_scores(session)
        
        # 更新统计信息
        self._update_statistics(session)
        
        self.completed_sessions.append(session)
        
        return None, session
    
    async def _complete_session_with_error(self,
                                         session: AmbiguitySession,
                                         error_message: str) -> Tuple[Optional[str], AmbiguitySession]:
        """完成错误会话"""
        session.end_time = datetime.now()
        session.total_duration = (session.end_time - session.start_time).total_seconds()
        session.success = False
        session.metadata['error'] = error_message
        
        # 计算最终质量分数
        await self._calculate_final_quality_scores(session)
        
        # 更新统计信息
        self._update_statistics(session)
        
        self.completed_sessions.append(session)
        
        return None, session
    
    async def _calculate_detection_quality(self, session: AmbiguitySession, analysis: AmbiguityAnalysis):
        """计算检测质量"""
        try:
            # 准确率：基于歧义信号的质量
            accuracy = min(1.0, analysis.ambiguity_score)
            
            quality_score = QualityScore(
                metric=QualityMetric.ACCURACY,
                score=accuracy,
                confidence=0.8,
                calculation_method="ambiguity_signal_analysis",
                timestamp=datetime.now(),
                details={
                    'ambiguity_score': analysis.ambiguity_score,
                    'signal_count': len(analysis.signals),
                    'primary_type': analysis.primary_type.value if analysis.primary_type else None
                }
            )
            
            session.quality_scores.append(quality_score)
            self.quality_metrics[QualityMetric.ACCURACY].append(accuracy)
            
        except Exception as e:
            logger.error(f"检测质量计算失败: {str(e)}")
    
    async def _calculate_resolution_quality(self, session: AmbiguitySession, attempt: ResolutionAttempt):
        """计算解决质量"""
        try:
            # 效率：基于执行时间
            efficiency = max(0.0, 1.0 - (attempt.execution_time / 5.0))  # 5秒为基准
            
            quality_score = QualityScore(
                metric=QualityMetric.EFFICIENCY,
                score=efficiency,
                confidence=attempt.confidence,
                calculation_method="execution_time_analysis",
                timestamp=datetime.now(),
                details={
                    'execution_time': attempt.execution_time,
                    'strategy': attempt.strategy.value,
                    'result': attempt.result.value
                }
            )
            
            session.quality_scores.append(quality_score)
            self.quality_metrics[QualityMetric.EFFICIENCY].append(efficiency)
            
        except Exception as e:
            logger.error(f"解决质量计算失败: {str(e)}")
    
    async def _calculate_interaction_quality(self, session: AmbiguitySession, question: GeneratedQuestion):
        """计算交互质量"""
        try:
            # 用户满意度预测（基于问题质量）
            satisfaction = question.confidence * 0.8 + 0.2  # 基础满意度
            
            quality_score = QualityScore(
                metric=QualityMetric.USER_SATISFACTION,
                score=satisfaction,
                confidence=question.confidence,
                calculation_method="question_quality_prediction",
                timestamp=datetime.now(),
                details={
                    'question_style': question.style.value,
                    'question_complexity': question.complexity.value,
                    'question_confidence': question.confidence
                }
            )
            
            session.quality_scores.append(quality_score)
            self.quality_metrics[QualityMetric.USER_SATISFACTION].append(satisfaction)
            
        except Exception as e:
            logger.error(f"交互质量计算失败: {str(e)}")
    
    async def _calculate_final_quality_scores(self, session: AmbiguitySession):
        """计算最终质量分数"""
        try:
            # 解决率
            resolution_rate = 1.0 if session.success else 0.0
            
            # 响应时间
            response_time_score = max(0.0, 1.0 - (session.total_duration / 10.0))  # 10秒为基准
            
            # 错误率
            error_rate = 1.0 - len([s for s in session.processing_steps if s.success]) / len(session.processing_steps) if session.processing_steps else 0.0
            
            # 添加最终质量分数
            final_scores = [
                QualityScore(
                    metric=QualityMetric.RESOLUTION_RATE,
                    score=resolution_rate,
                    confidence=1.0,
                    calculation_method="session_outcome",
                    timestamp=datetime.now()
                ),
                QualityScore(
                    metric=QualityMetric.RESPONSE_TIME,
                    score=response_time_score,
                    confidence=1.0,
                    calculation_method="total_duration",
                    timestamp=datetime.now(),
                    details={'total_duration': session.total_duration}
                ),
                QualityScore(
                    metric=QualityMetric.ERROR_RATE,
                    score=1.0 - error_rate,  # 转换为成功率
                    confidence=1.0,
                    calculation_method="step_success_rate",
                    timestamp=datetime.now(),
                    details={'error_rate': error_rate}
                )
            ]
            
            session.quality_scores.extend(final_scores)
            
            # 更新全局质量指标
            for score in final_scores:
                self.quality_metrics[score.metric].append(score.score)
            
        except Exception as e:
            logger.error(f"最终质量分数计算失败: {str(e)}")
    
    def _update_statistics(self, session: AmbiguitySession):
        """更新统计信息"""
        try:
            self.processing_statistics['total_sessions'] += 1
            
            if session.success:
                self.processing_statistics['successful_sessions'] += 1
                
                # 判断是自动解决还是交互解决
                if session.resolution_attempts and session.resolution_attempts[-1].strategy.value != 'interactive':
                    self.processing_statistics['auto_resolved_sessions'] += 1
                else:
                    self.processing_statistics['interactive_resolved_sessions'] += 1
            else:
                self.processing_statistics['failed_sessions'] += 1
            
            # 更新平均处理时间
            total_time = sum(s.total_duration for s in self.completed_sessions if s.total_duration)
            total_count = len([s for s in self.completed_sessions if s.total_duration])
            
            if total_count > 0:
                self.processing_statistics['avg_processing_time'] = total_time / total_count
            
            # 更新平均用户满意度
            satisfaction_scores = [s.user_satisfaction for s in self.completed_sessions if s.user_satisfaction]
            if satisfaction_scores:
                self.processing_statistics['avg_user_satisfaction'] = sum(satisfaction_scores) / len(satisfaction_scores)
            
        except Exception as e:
            logger.error(f"统计信息更新失败: {str(e)}")
    
    async def _handle_negative_response(self, session: AmbiguitySession) -> Tuple[Optional[str], bool]:
        """处理否定回应"""
        session.metadata['user_rejected_all'] = True
        return None, True
    
    async def _handle_uncertain_response(self, session: AmbiguitySession, candidates: List[Dict]) -> Tuple[Optional[str], bool]:
        """处理不确定回应"""
        # 可以尝试提供更多帮助或简化选择
        return None, False
    
    async def _handle_positive_response(self, session: AmbiguitySession, parse_result: ParseResult, candidates: List[Dict]) -> Tuple[Optional[str], bool]:
        """处理正面回应"""
        if parse_result.selected_option and 1 <= parse_result.selected_option <= len(candidates):
            selected_intent = candidates[parse_result.selected_option - 1]['intent_name']
            return selected_intent, True
        return None, False
    
    async def _handle_parse_failure(self, session: AmbiguitySession, parse_result: ParseResult) -> Tuple[Optional[str], bool]:
        """处理解析失败"""
        # 可以尝试重新询问或提供帮助
        return None, False
    
    def get_quality_report(self) -> Dict[str, Any]:
        """获取质量报告"""
        try:
            report = {
                'timestamp': datetime.now().isoformat(),
                'processing_statistics': self.processing_statistics,
                'quality_metrics': {},
                'performance_vs_baseline': {},
                'trends': {},
                'recommendations': []
            }
            
            # 计算质量指标
            for metric, scores in self.quality_metrics.items():
                if scores:
                    report['quality_metrics'][metric.value] = {
                        'current_average': sum(scores) / len(scores),
                        'sample_count': len(scores),
                        'min_score': min(scores),
                        'max_score': max(scores),
                        'recent_average': sum(scores[-10:]) / len(scores[-10:]) if len(scores) >= 10 else sum(scores) / len(scores)
                    }
            
            # 与基线比较
            for metric, baseline in self.performance_baselines.items():
                if metric in self.quality_metrics and self.quality_metrics[metric]:
                    current = sum(self.quality_metrics[metric]) / len(self.quality_metrics[metric])
                    report['performance_vs_baseline'][metric.value] = {
                        'baseline': baseline,
                        'current': current,
                        'difference': current - baseline,
                        'performance': 'above' if current > baseline else 'below' if current < baseline else 'at'
                    }
            
            # 生成建议
            report['recommendations'] = self._generate_recommendations()
            
            return report
            
        except Exception as e:
            logger.error(f"质量报告生成失败: {str(e)}")
            return {'error': str(e)}
    
    def _generate_recommendations(self) -> List[str]:
        """生成优化建议"""
        recommendations = []
        
        try:
            # 基于质量指标生成建议
            if QualityMetric.ACCURACY in self.quality_metrics:
                accuracy_scores = self.quality_metrics[QualityMetric.ACCURACY]
                if accuracy_scores:
                    avg_accuracy = sum(accuracy_scores) / len(accuracy_scores)
                    if avg_accuracy < 0.8:
                        recommendations.append("建议优化歧义检测算法，提高检测准确率")
            
            if QualityMetric.EFFICIENCY in self.quality_metrics:
                efficiency_scores = self.quality_metrics[QualityMetric.EFFICIENCY]
                if efficiency_scores:
                    avg_efficiency = sum(efficiency_scores) / len(efficiency_scores)
                    if avg_efficiency < 0.7:
                        recommendations.append("建议优化自动解决策略，提高处理效率")
            
            if QualityMetric.USER_SATISFACTION in self.quality_metrics:
                satisfaction_scores = self.quality_metrics[QualityMetric.USER_SATISFACTION]
                if satisfaction_scores:
                    avg_satisfaction = sum(satisfaction_scores) / len(satisfaction_scores)
                    if avg_satisfaction < 0.7:
                        recommendations.append("建议改进问题生成质量，提高用户满意度")
            
            # 基于统计信息生成建议
            if self.processing_statistics['failed_sessions'] / max(1, self.processing_statistics['total_sessions']) > 0.2:
                recommendations.append("失败率过高，建议检查和优化整体处理流程")
            
            if self.processing_statistics['avg_processing_time'] > 5.0:
                recommendations.append("处理时间过长，建议优化算法性能")
            
        except Exception as e:
            logger.error(f"建议生成失败: {str(e)}")
        
        return recommendations
    
    def get_orchestrator_statistics(self) -> Dict[str, Any]:
        """获取编排器统计信息"""
        try:
            return {
                'active_sessions': len(self.active_sessions),
                'completed_sessions': len(self.completed_sessions),
                'total_processing_time': sum(s.total_duration for s in self.completed_sessions if s.total_duration),
                'average_steps_per_session': sum(len(s.processing_steps) for s in self.completed_sessions) / len(self.completed_sessions) if self.completed_sessions else 0,
                'quality_metrics_count': {metric.value: len(scores) for metric, scores in self.quality_metrics.items()},
                'component_statistics': {
                    'ambiguity_detector': self.ambiguity_detector.get_detection_statistics(),
                    'question_generator': self.question_generator.get_generator_statistics(),
                    'choice_parser': self.choice_parser.get_parser_statistics(),
                    'multi_resolver': self.multi_resolver.get_resolver_statistics(),
                    'threshold_manager': self.threshold_manager.get_threshold_statistics()
                }
            }
        except Exception as e:
            logger.error(f"获取编排器统计失败: {str(e)}")
            return {'error': str(e)}