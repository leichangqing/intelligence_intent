"""
多策略歧义解决器
实现自动解决策略和学习优化
"""

from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
from enum import Enum
import logging
from datetime import datetime, timedelta
import json
from collections import defaultdict, deque
import asyncio

from .ambiguity_detector import AmbiguityAnalysis, AmbiguityType
from .advanced_choice_parser import ParseResult, ChoiceType
from ..models.intent import Intent
from ..utils.logger import get_logger

logger = get_logger(__name__)


class ResolutionStrategy(Enum):
    """解决策略类型"""
    AUTOMATIC = "automatic"         # 自动解决
    INTERACTIVE = "interactive"     # 交互式解决
    CONTEXTUAL = "contextual"       # 上下文推理
    STATISTICAL = "statistical"     # 统计学习
    HYBRID = "hybrid"              # 混合策略
    ESCALATION = "escalation"       # 升级处理


class ResolutionResult(Enum):
    """解决结果类型"""
    RESOLVED = "resolved"           # 已解决
    PARTIAL = "partial"            # 部分解决
    FAILED = "failed"              # 解决失败
    ESCALATED = "escalated"        # 已升级
    DEFERRED = "deferred"          # 延期处理


@dataclass
class ResolutionAttempt:
    """解决尝试记录"""
    strategy: ResolutionStrategy
    timestamp: datetime
    confidence: float
    result: ResolutionResult
    selected_intent: Optional[str]
    reasoning: str
    execution_time: float
    metadata: Dict[str, Any]


@dataclass
class ResolutionContext:
    """解决上下文"""
    user_id: str
    conversation_id: int
    ambiguity_analysis: AmbiguityAnalysis
    candidates: List[Dict]
    conversation_history: List[Dict]
    user_preferences: Dict[str, Any]
    time_constraints: Dict[str, float]
    current_session_data: Dict[str, Any]


class MultiStrategyResolver:
    """多策略歧义解决器"""
    
    def __init__(self):
        # 策略权重配置
        self.strategy_weights = {
            ResolutionStrategy.AUTOMATIC: 0.3,
            ResolutionStrategy.CONTEXTUAL: 0.25,
            ResolutionStrategy.STATISTICAL: 0.2,
            ResolutionStrategy.INTERACTIVE: 0.15,
            ResolutionStrategy.HYBRID: 0.1
        }
        
        # 策略成功率统计
        self.strategy_success_rates: Dict[ResolutionStrategy, deque] = {
            strategy: deque(maxlen=100) for strategy in ResolutionStrategy
        }
        
        # 用户偏好学习
        self.user_preference_models: Dict[str, Dict] = {}
        
        # 上下文模式库
        self.context_patterns: Dict[str, List[Dict]] = defaultdict(list)
        
        # 自动解决规则
        self.auto_resolution_rules = self._initialize_auto_rules()
        
        # 解决历史
        self.resolution_history: Dict[str, List[ResolutionAttempt]] = defaultdict(list)
        
        # 学习参数
        self.learning_rate = 0.1
        self.adaptation_threshold = 0.7
        self.confidence_threshold = 0.8
    
    def _initialize_auto_rules(self) -> Dict[str, List[Dict]]:
        """初始化自动解决规则"""
        return {
            'high_confidence_single': [
                {
                    'condition': lambda analysis, candidates: (
                        len(candidates) >= 1 and 
                        candidates[0].get('confidence', 0) > 0.9 and
                        (len(candidates) == 1 or candidates[0].get('confidence', 0) - candidates[1].get('confidence', 0) > 0.3)
                    ),
                    'action': 'select_first',
                    'confidence': 0.9,
                    'reasoning': '单个候选置信度极高'
                }
            ],
            'context_continuation': [
                {
                    'condition': lambda analysis, candidates, context: (
                        context.get('current_intent') in [c['intent_name'] for c in candidates] and
                        analysis.ambiguity_score < 0.6
                    ),
                    'action': 'continue_context',
                    'confidence': 0.8,
                    'reasoning': '延续当前上下文意图'
                }
            ],
            'user_pattern_match': [
                {
                    'condition': lambda analysis, candidates, context, user_patterns: (
                        len(user_patterns.get('frequent_intents', [])) > 0 and
                        any(c['intent_name'] in user_patterns['frequent_intents'] for c in candidates)
                    ),
                    'action': 'select_frequent',
                    'confidence': 0.75,
                    'reasoning': '匹配用户常用意图'
                }
            ],
            'temporal_patterns': [
                {
                    'condition': lambda analysis, candidates, context: (
                        self._check_temporal_pattern(candidates, context)
                    ),
                    'action': 'select_temporal',
                    'confidence': 0.7,
                    'reasoning': '基于时间模式选择'
                }
            ]
        }
    
    async def resolve_ambiguity(self, context: ResolutionContext) -> Tuple[Optional[Intent], ResolutionAttempt]:
        """
        多策略歧义解决
        
        Args:
            context: 解决上下文
            
        Returns:
            Tuple[Optional[Intent], ResolutionAttempt]: (解决的意图, 解决尝试记录)
        """
        try:
            start_time = datetime.now()
            
            # 评估可用策略
            available_strategies = self._evaluate_available_strategies(context)
            
            # 按优先级排序策略
            sorted_strategies = self._prioritize_strategies(available_strategies, context)
            
            # 依次尝试策略
            for strategy in sorted_strategies:
                logger.info(f"尝试策略: {strategy.value}")
                
                attempt = await self._execute_strategy(strategy, context)
                
                if attempt.result == ResolutionResult.RESOLVED:
                    # 成功解决
                    selected_intent = await self._get_intent_by_name(attempt.selected_intent)
                    
                    if selected_intent:
                        # 记录成功
                        self._record_success(strategy, context, attempt)
                        
                        # 学习更新
                        await self._update_learning_models(context, attempt)
                        
                        logger.info(f"歧义解决成功: {strategy.value} -> {selected_intent.intent_name}")
                        return selected_intent, attempt
                
                elif attempt.result == ResolutionResult.PARTIAL:
                    # 部分解决，继续尝试其他策略
                    logger.info(f"策略{strategy.value}部分成功，继续尝试")
                    continue
                
                else:
                    # 失败，记录并继续
                    self._record_failure(strategy, context, attempt)
                    logger.info(f"策略{strategy.value}失败: {attempt.reasoning}")
                    continue
            
            # 所有策略都失败，返回失败结果
            execution_time = (datetime.now() - start_time).total_seconds()
            
            failed_attempt = ResolutionAttempt(
                strategy=ResolutionStrategy.ESCALATION,
                timestamp=datetime.now(),
                confidence=0.0,
                result=ResolutionResult.FAILED,
                selected_intent=None,
                reasoning="所有自动解决策略都失败",
                execution_time=execution_time,
                metadata={
                    'tried_strategies': [s.value for s in sorted_strategies],
                    'ambiguity_score': context.ambiguity_analysis.ambiguity_score
                }
            )
            
            return None, failed_attempt
            
        except Exception as e:
            logger.error(f"多策略歧义解决失败: {str(e)}")
            error_attempt = ResolutionAttempt(
                strategy=ResolutionStrategy.ESCALATION,
                timestamp=datetime.now(),
                confidence=0.0,
                result=ResolutionResult.FAILED,
                selected_intent=None,
                reasoning=f"执行错误: {str(e)}",
                execution_time=0.0,
                metadata={'error': str(e)}
            )
            return None, error_attempt
    
    def _evaluate_available_strategies(self, context: ResolutionContext) -> List[ResolutionStrategy]:
        """评估可用策略"""
        available = []
        
        # 检查自动解决条件
        if self._can_use_automatic(context):
            available.append(ResolutionStrategy.AUTOMATIC)
        
        # 检查上下文推理条件
        if self._can_use_contextual(context):
            available.append(ResolutionStrategy.CONTEXTUAL)
        
        # 检查统计学习条件
        if self._can_use_statistical(context):
            available.append(ResolutionStrategy.STATISTICAL)
        
        # 检查混合策略条件
        if len(available) >= 2:
            available.append(ResolutionStrategy.HYBRID)
        
        # 交互式策略总是可用
        available.append(ResolutionStrategy.INTERACTIVE)
        
        return available
    
    def _prioritize_strategies(self, strategies: List[ResolutionStrategy], context: ResolutionContext) -> List[ResolutionStrategy]:
        """策略优先级排序"""
        try:
            # 基于成功率和权重计算优先级
            priority_scores = {}
            
            for strategy in strategies:
                # 基础权重
                base_weight = self.strategy_weights.get(strategy, 0.1)
                
                # 历史成功率
                success_rate = self._calculate_success_rate(strategy)
                
                # 上下文适应性
                context_score = self._calculate_context_fitness(strategy, context)
                
                # 综合得分
                total_score = base_weight * 0.4 + success_rate * 0.4 + context_score * 0.2
                priority_scores[strategy] = total_score
            
            # 按得分排序
            sorted_strategies = sorted(strategies, key=lambda s: priority_scores[s], reverse=True)
            
            logger.debug(f"策略优先级: {[(s.value, priority_scores[s]) for s in sorted_strategies]}")
            
            return sorted_strategies
            
        except Exception as e:
            logger.error(f"策略优先级排序失败: {str(e)}")
            return strategies
    
    async def _execute_strategy(self, strategy: ResolutionStrategy, context: ResolutionContext) -> ResolutionAttempt:
        """执行特定策略"""
        start_time = datetime.now()
        
        try:
            if strategy == ResolutionStrategy.AUTOMATIC:
                result = await self._execute_automatic_strategy(context)
            elif strategy == ResolutionStrategy.CONTEXTUAL:
                result = await self._execute_contextual_strategy(context)
            elif strategy == ResolutionStrategy.STATISTICAL:
                result = await self._execute_statistical_strategy(context)
            elif strategy == ResolutionStrategy.HYBRID:
                result = await self._execute_hybrid_strategy(context)
            elif strategy == ResolutionStrategy.INTERACTIVE:
                result = await self._execute_interactive_strategy(context)
            else:
                result = ResolutionAttempt(
                    strategy=strategy,
                    timestamp=datetime.now(),
                    confidence=0.0,
                    result=ResolutionResult.FAILED,
                    selected_intent=None,
                    reasoning="未知策略",
                    execution_time=0.0,
                    metadata={}
                )
            
            execution_time = (datetime.now() - start_time).total_seconds()
            result.execution_time = execution_time
            
            return result
            
        except Exception as e:
            logger.error(f"策略{strategy.value}执行失败: {str(e)}")
            execution_time = (datetime.now() - start_time).total_seconds()
            
            return ResolutionAttempt(
                strategy=strategy,
                timestamp=datetime.now(),
                confidence=0.0,
                result=ResolutionResult.FAILED,
                selected_intent=None,
                reasoning=f"执行错误: {str(e)}",
                execution_time=execution_time,
                metadata={'error': str(e)}
            )
    
    async def _execute_automatic_strategy(self, context: ResolutionContext) -> ResolutionAttempt:
        """执行自动解决策略"""
        try:
            # 检查所有自动规则
            for rule_category, rules in self.auto_resolution_rules.items():
                for rule in rules:
                    try:
                        # 评估规则条件
                        if self._evaluate_rule_condition(rule, context):
                            # 执行规则动作
                            selected_intent = self._execute_rule_action(rule, context)
                            
                            if selected_intent:
                                return ResolutionAttempt(
                                    strategy=ResolutionStrategy.AUTOMATIC,
                                    timestamp=datetime.now(),
                                    confidence=rule['confidence'],
                                    result=ResolutionResult.RESOLVED,
                                    selected_intent=selected_intent,
                                    reasoning=rule['reasoning'],
                                    execution_time=0.0,
                                    metadata={
                                        'rule_category': rule_category,
                                        'rule_action': rule['action']
                                    }
                                )
                    except Exception as e:
                        logger.error(f"规则{rule_category}执行失败: {str(e)}")
                        continue
            
            # 没有规则匹配
            return ResolutionAttempt(
                strategy=ResolutionStrategy.AUTOMATIC,
                timestamp=datetime.now(),
                confidence=0.0,
                result=ResolutionResult.FAILED,
                selected_intent=None,
                reasoning="没有匹配的自动规则",
                execution_time=0.0,
                metadata={}
            )
            
        except Exception as e:
            logger.error(f"自动策略执行失败: {str(e)}")
            return ResolutionAttempt(
                strategy=ResolutionStrategy.AUTOMATIC,
                timestamp=datetime.now(),
                confidence=0.0,
                result=ResolutionResult.FAILED,
                selected_intent=None,
                reasoning=f"执行错误: {str(e)}",
                execution_time=0.0,
                metadata={'error': str(e)}
            )
    
    async def _execute_contextual_strategy(self, context: ResolutionContext) -> ResolutionAttempt:
        """执行上下文推理策略"""
        try:
            # 分析对话历史
            context_score = self._analyze_conversation_context(context)
            
            # 找到最符合上下文的候选
            best_candidate = None
            best_score = 0.0
            
            for candidate in context.candidates:
                score = self._calculate_context_relevance(candidate, context)
                if score > best_score:
                    best_score = score
                    best_candidate = candidate
            
            if best_candidate and best_score > self.confidence_threshold:
                return ResolutionAttempt(
                    strategy=ResolutionStrategy.CONTEXTUAL,
                    timestamp=datetime.now(),
                    confidence=best_score,
                    result=ResolutionResult.RESOLVED,
                    selected_intent=best_candidate['intent_name'],
                    reasoning=f"上下文推理选择，相关度: {best_score:.3f}",
                    execution_time=0.0,
                    metadata={
                        'context_score': context_score,
                        'relevance_score': best_score
                    }
                )
            
            return ResolutionAttempt(
                strategy=ResolutionStrategy.CONTEXTUAL,
                timestamp=datetime.now(),
                confidence=best_score,
                result=ResolutionResult.FAILED,
                selected_intent=None,
                reasoning=f"上下文相关度不足: {best_score:.3f}",
                execution_time=0.0,
                metadata={'best_score': best_score}
            )
            
        except Exception as e:
            logger.error(f"上下文策略执行失败: {str(e)}")
            return ResolutionAttempt(
                strategy=ResolutionStrategy.CONTEXTUAL,
                timestamp=datetime.now(),
                confidence=0.0,
                result=ResolutionResult.FAILED,
                selected_intent=None,
                reasoning=f"执行错误: {str(e)}",
                execution_time=0.0,
                metadata={'error': str(e)}
            )
    
    async def _execute_statistical_strategy(self, context: ResolutionContext) -> ResolutionAttempt:
        """执行统计学习策略"""
        try:
            # 获取用户偏好模型
            user_model = self.user_preference_models.get(context.user_id, {})
            
            if not user_model:
                return ResolutionAttempt(
                    strategy=ResolutionStrategy.STATISTICAL,
                    timestamp=datetime.now(),
                    confidence=0.0,
                    result=ResolutionResult.FAILED,
                    selected_intent=None,
                    reasoning="用户偏好模型不存在",
                    execution_time=0.0,
                    metadata={}
                )
            
            # 计算每个候选的统计得分
            candidate_scores = []
            for candidate in context.candidates:
                score = self._calculate_statistical_score(candidate, user_model, context)
                candidate_scores.append((candidate, score))
            
            # 排序并选择最佳候选
            candidate_scores.sort(key=lambda x: x[1], reverse=True)
            
            if candidate_scores and candidate_scores[0][1] > self.confidence_threshold:
                best_candidate, best_score = candidate_scores[0]
                
                return ResolutionAttempt(
                    strategy=ResolutionStrategy.STATISTICAL,
                    timestamp=datetime.now(),
                    confidence=best_score,
                    result=ResolutionResult.RESOLVED,
                    selected_intent=best_candidate['intent_name'],
                    reasoning=f"统计学习选择，得分: {best_score:.3f}",
                    execution_time=0.0,
                    metadata={
                        'all_scores': [(c['intent_name'], s) for c, s in candidate_scores],
                        'user_model_size': len(user_model)
                    }
                )
            
            return ResolutionAttempt(
                strategy=ResolutionStrategy.STATISTICAL,
                timestamp=datetime.now(),
                confidence=candidate_scores[0][1] if candidate_scores else 0.0,
                result=ResolutionResult.FAILED,
                selected_intent=None,
                reasoning="统计得分不足",
                execution_time=0.0,
                metadata={'best_score': candidate_scores[0][1] if candidate_scores else 0.0}
            )
            
        except Exception as e:
            logger.error(f"统计策略执行失败: {str(e)}")
            return ResolutionAttempt(
                strategy=ResolutionStrategy.STATISTICAL,
                timestamp=datetime.now(),
                confidence=0.0,
                result=ResolutionResult.FAILED,
                selected_intent=None,
                reasoning=f"执行错误: {str(e)}",
                execution_time=0.0,
                metadata={'error': str(e)}
            )
    
    async def _execute_hybrid_strategy(self, context: ResolutionContext) -> ResolutionAttempt:
        """执行混合策略"""
        try:
            # 收集各种策略的结果
            strategy_results = {}
            
            # 尝试自动策略
            auto_result = await self._execute_automatic_strategy(context)
            if auto_result.result == ResolutionResult.RESOLVED:
                strategy_results['automatic'] = auto_result
            
            # 尝试上下文策略
            context_result = await self._execute_contextual_strategy(context)
            if context_result.result == ResolutionResult.RESOLVED:
                strategy_results['contextual'] = context_result
            
            # 尝试统计策略
            stats_result = await self._execute_statistical_strategy(context)
            if stats_result.result == ResolutionResult.RESOLVED:
                strategy_results['statistical'] = stats_result
            
            # 如果没有成功的策略
            if not strategy_results:
                return ResolutionAttempt(
                    strategy=ResolutionStrategy.HYBRID,
                    timestamp=datetime.now(),
                    confidence=0.0,
                    result=ResolutionResult.FAILED,
                    selected_intent=None,
                    reasoning="所有子策略都失败",
                    execution_time=0.0,
                    metadata={}
                )
            
            # 投票选择最佳结果
            intent_votes = defaultdict(list)
            for strategy_name, result in strategy_results.items():
                intent_votes[result.selected_intent].append((strategy_name, result.confidence))
            
            # 选择得票最多且综合置信度最高的意图
            best_intent = None
            best_confidence = 0.0
            
            for intent, votes in intent_votes.items():
                avg_confidence = sum(conf for _, conf in votes) / len(votes)
                weighted_confidence = avg_confidence * len(votes)  # 投票数加权
                
                if weighted_confidence > best_confidence:
                    best_confidence = weighted_confidence
                    best_intent = intent
            
            return ResolutionAttempt(
                strategy=ResolutionStrategy.HYBRID,
                timestamp=datetime.now(),
                confidence=best_confidence,
                result=ResolutionResult.RESOLVED,
                selected_intent=best_intent,
                reasoning=f"混合策略投票选择，得票: {len(intent_votes[best_intent])}",
                execution_time=0.0,
                metadata={
                    'strategy_results': {k: v.selected_intent for k, v in strategy_results.items()},
                    'vote_details': dict(intent_votes)
                }
            )
            
        except Exception as e:
            logger.error(f"混合策略执行失败: {str(e)}")
            return ResolutionAttempt(
                strategy=ResolutionStrategy.HYBRID,
                timestamp=datetime.now(),
                confidence=0.0,
                result=ResolutionResult.FAILED,
                selected_intent=None,
                reasoning=f"执行错误: {str(e)}",
                execution_time=0.0,
                metadata={'error': str(e)}
            )
    
    async def _execute_interactive_strategy(self, context: ResolutionContext) -> ResolutionAttempt:
        """执行交互式策略"""
        # 交互式策略需要外部处理，这里返回需要交互的结果
        return ResolutionAttempt(
            strategy=ResolutionStrategy.INTERACTIVE,
            timestamp=datetime.now(),
            confidence=0.5,
            result=ResolutionResult.DEFERRED,
            selected_intent=None,
            reasoning="需要用户交互确认",
            execution_time=0.0,
            metadata={
                'candidates': context.candidates,
                'requires_user_input': True
            }
        )
    
    def _can_use_automatic(self, context: ResolutionContext) -> bool:
        """检查是否可以使用自动解决"""
        return (
            context.ambiguity_analysis.ambiguity_score < 0.8 and
            len(context.candidates) <= 5 and
            any(c.get('confidence', 0) > 0.7 for c in context.candidates)
        )
    
    def _can_use_contextual(self, context: ResolutionContext) -> bool:
        """检查是否可以使用上下文推理"""
        return (
            len(context.conversation_history) > 0 and
            context.ambiguity_analysis.primary_type in [AmbiguityType.CONTEXTUAL, AmbiguityType.SEMANTIC]
        )
    
    def _can_use_statistical(self, context: ResolutionContext) -> bool:
        """检查是否可以使用统计学习"""
        return (
            context.user_id in self.user_preference_models and
            len(self.user_preference_models[context.user_id]) > 10
        )
    
    def _calculate_success_rate(self, strategy: ResolutionStrategy) -> float:
        """计算策略成功率"""
        if strategy not in self.strategy_success_rates:
            return 0.5
        
        attempts = self.strategy_success_rates[strategy]
        if not attempts:
            return 0.5
        
        successes = sum(1 for success in attempts if success)
        return successes / len(attempts)
    
    def _calculate_context_fitness(self, strategy: ResolutionStrategy, context: ResolutionContext) -> float:
        """计算策略与上下文的适应度"""
        fitness = 0.5
        
        if strategy == ResolutionStrategy.AUTOMATIC:
            if context.ambiguity_analysis.ambiguity_score < 0.5:
                fitness += 0.3
        elif strategy == ResolutionStrategy.CONTEXTUAL:
            if len(context.conversation_history) > 3:
                fitness += 0.2
        elif strategy == ResolutionStrategy.STATISTICAL:
            if context.user_id in self.user_preference_models:
                fitness += 0.25
        
        return min(1.0, fitness)
    
    def _evaluate_rule_condition(self, rule: Dict, context: ResolutionContext) -> bool:
        """评估规则条件"""
        try:
            condition = rule['condition']
            
            # 根据条件参数数量调用
            if callable(condition):
                import inspect
                sig = inspect.signature(condition)
                params = list(sig.parameters.keys())
                
                if len(params) == 2:
                    return condition(context.ambiguity_analysis, context.candidates)
                elif len(params) == 3:
                    return condition(context.ambiguity_analysis, context.candidates, context.current_session_data)
                elif len(params) == 4:
                    user_patterns = self.user_preference_models.get(context.user_id, {})
                    return condition(context.ambiguity_analysis, context.candidates, context.current_session_data, user_patterns)
                else:
                    return False
            
            return False
            
        except Exception as e:
            logger.error(f"规则条件评估失败: {str(e)}")
            return False
    
    def _execute_rule_action(self, rule: Dict, context: ResolutionContext) -> Optional[str]:
        """执行规则动作"""
        try:
            action = rule['action']
            
            if action == 'select_first':
                return context.candidates[0]['intent_name'] if context.candidates else None
            elif action == 'continue_context':
                current_intent = context.current_session_data.get('current_intent')
                if current_intent and any(c['intent_name'] == current_intent for c in context.candidates):
                    return current_intent
            elif action == 'select_frequent':
                user_patterns = self.user_preference_models.get(context.user_id, {})
                frequent_intents = user_patterns.get('frequent_intents', [])
                for intent in frequent_intents:
                    if any(c['intent_name'] == intent for c in context.candidates):
                        return intent
            elif action == 'select_temporal':
                return self._select_by_temporal_pattern(context.candidates, context.current_session_data)
            
            return None
            
        except Exception as e:
            logger.error(f"规则动作执行失败: {str(e)}")
            return None
    
    def _check_temporal_pattern(self, candidates: List[Dict], context: Dict) -> bool:
        """检查时间模式"""
        try:
            current_hour = datetime.now().hour
            
            # 简单的时间模式：工作时间偏向工作相关意图
            if 9 <= current_hour <= 17:
                work_related = ['check_balance', 'book_flight']
                return any(c['intent_name'] in work_related for c in candidates)
            
            return False
            
        except Exception:
            return False
    
    def _select_by_temporal_pattern(self, candidates: List[Dict], context: Dict) -> Optional[str]:
        """基于时间模式选择"""
        try:
            current_hour = datetime.now().hour
            
            if 9 <= current_hour <= 17:
                # 工作时间
                work_intents = ['check_balance', 'book_flight']
                for intent in work_intents:
                    if any(c['intent_name'] == intent for c in candidates):
                        return intent
            
            # 默认选择第一个
            return candidates[0]['intent_name'] if candidates else None
            
        except Exception:
            return None
    
    def _analyze_conversation_context(self, context: ResolutionContext) -> float:
        """分析对话上下文"""
        try:
            if not context.conversation_history:
                return 0.0
            
            # 计算上下文连贯性
            coherence_score = 0.0
            
            # 检查最近的意图
            recent_intents = [
                turn.get('intent') for turn in context.conversation_history[-3:]
                if turn.get('intent')
            ]
            
            if recent_intents:
                # 计算意图一致性
                unique_intents = set(recent_intents)
                if len(unique_intents) == 1:
                    coherence_score += 0.8
                elif len(unique_intents) <= 2:
                    coherence_score += 0.5
                else:
                    coherence_score += 0.2
            
            return coherence_score
            
        except Exception as e:
            logger.error(f"对话上下文分析失败: {str(e)}")
            return 0.0
    
    def _calculate_context_relevance(self, candidate: Dict, context: ResolutionContext) -> float:
        """计算候选与上下文的相关性"""
        try:
            relevance = 0.0
            
            # 检查与当前意图的相关性
            current_intent = context.current_session_data.get('current_intent')
            if current_intent == candidate['intent_name']:
                relevance += 0.5
            
            # 检查与历史意图的相关性
            recent_intents = [
                turn.get('intent') for turn in context.conversation_history[-5:]
                if turn.get('intent')
            ]
            
            if candidate['intent_name'] in recent_intents:
                relevance += 0.3
            
            # 检查置信度
            relevance += candidate.get('confidence', 0) * 0.2
            
            return min(1.0, relevance)
            
        except Exception as e:
            logger.error(f"上下文相关性计算失败: {str(e)}")
            return 0.0
    
    def _calculate_statistical_score(self, candidate: Dict, user_model: Dict, context: ResolutionContext) -> float:
        """计算统计得分"""
        try:
            score = 0.0
            
            # 基于频率
            intent_frequency = user_model.get('intent_frequencies', {})
            if candidate['intent_name'] in intent_frequency:
                score += intent_frequency[candidate['intent_name']] * 0.4
            
            # 基于时间模式
            time_patterns = user_model.get('time_patterns', {})
            current_hour = datetime.now().hour
            if str(current_hour) in time_patterns:
                hour_intents = time_patterns[str(current_hour)]
                if candidate['intent_name'] in hour_intents:
                    score += hour_intents[candidate['intent_name']] * 0.3
            
            # 基于成功率
            success_rates = user_model.get('success_rates', {})
            if candidate['intent_name'] in success_rates:
                score += success_rates[candidate['intent_name']] * 0.3
            
            return min(1.0, score)
            
        except Exception as e:
            logger.error(f"统计得分计算失败: {str(e)}")
            return 0.0
    
    async def _get_intent_by_name(self, intent_name: str) -> Optional[Intent]:
        """根据名称获取意图对象"""
        try:
            return Intent.get(Intent.intent_name == intent_name, Intent.is_active == True)
        except Intent.DoesNotExist:
            return None
        except Exception as e:
            logger.error(f"获取意图失败: {str(e)}")
            return None
    
    def _record_success(self, strategy: ResolutionStrategy, context: ResolutionContext, attempt: ResolutionAttempt):
        """记录成功案例"""
        try:
            # 记录策略成功率
            self.strategy_success_rates[strategy].append(True)
            
            # 记录解决历史
            self.resolution_history[context.user_id].append(attempt)
            
            # 限制历史记录长度
            if len(self.resolution_history[context.user_id]) > 100:
                self.resolution_history[context.user_id] = self.resolution_history[context.user_id][-100:]
            
        except Exception as e:
            logger.error(f"记录成功案例失败: {str(e)}")
    
    def _record_failure(self, strategy: ResolutionStrategy, context: ResolutionContext, attempt: ResolutionAttempt):
        """记录失败案例"""
        try:
            # 记录策略失败
            self.strategy_success_rates[strategy].append(False)
            
            # 记录解决历史
            self.resolution_history[context.user_id].append(attempt)
            
        except Exception as e:
            logger.error(f"记录失败案例失败: {str(e)}")
    
    async def _update_learning_models(self, context: ResolutionContext, attempt: ResolutionAttempt):
        """更新学习模型"""
        try:
            user_id = context.user_id
            
            # 初始化用户模型
            if user_id not in self.user_preference_models:
                self.user_preference_models[user_id] = {
                    'intent_frequencies': defaultdict(float),
                    'time_patterns': defaultdict(lambda: defaultdict(float)),
                    'success_rates': defaultdict(float),
                    'context_preferences': defaultdict(float)
                }
            
            model = self.user_preference_models[user_id]
            
            # 更新意图频率
            if attempt.selected_intent:
                model['intent_frequencies'][attempt.selected_intent] += self.learning_rate
            
            # 更新时间模式
            current_hour = datetime.now().hour
            if attempt.selected_intent:
                model['time_patterns'][str(current_hour)][attempt.selected_intent] += self.learning_rate
            
            # 更新成功率
            if attempt.selected_intent:
                model['success_rates'][attempt.selected_intent] += self.learning_rate
            
            # 标准化权重
            self._normalize_user_model(model)
            
        except Exception as e:
            logger.error(f"学习模型更新失败: {str(e)}")
    
    def _normalize_user_model(self, model: Dict):
        """标准化用户模型权重"""
        try:
            # 标准化意图频率
            frequencies = model['intent_frequencies']
            if frequencies:
                max_freq = max(frequencies.values())
                if max_freq > 0:
                    for intent in frequencies:
                        frequencies[intent] /= max_freq
            
            # 标准化成功率
            success_rates = model['success_rates']
            if success_rates:
                for intent in success_rates:
                    success_rates[intent] = min(1.0, success_rates[intent])
            
        except Exception as e:
            logger.error(f"模型标准化失败: {str(e)}")
    
    def get_resolver_statistics(self) -> Dict[str, Any]:
        """获取解决器统计信息"""
        try:
            return {
                'strategy_success_rates': {
                    strategy.value: self._calculate_success_rate(strategy)
                    for strategy in ResolutionStrategy
                },
                'user_models_count': len(self.user_preference_models),
                'resolution_history_count': sum(len(history) for history in self.resolution_history.values()),
                'context_patterns_count': len(self.context_patterns),
                'auto_rules_count': sum(len(rules) for rules in self.auto_resolution_rules.values()),
                'strategy_weights': {k.value: v for k, v in self.strategy_weights.items()}
            }
        except Exception as e:
            logger.error(f"获取解决器统计失败: {str(e)}")
            return {'error': str(e)}