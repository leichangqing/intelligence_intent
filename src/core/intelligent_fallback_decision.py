"""
智能回退决策系统 (TASK-032)
基于机器学习和规则引擎的智能回退决策，提供最优的回退策略选择
"""
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from enum import Enum
import json
import time
import statistics
from datetime import datetime, timedelta
from collections import defaultdict, deque

from src.core.fallback_manager import FallbackType, FallbackStrategy, FallbackContext, FallbackResult
from src.services.cache_service import CacheService
from src.utils.logger import get_logger

logger = get_logger(__name__)


class DecisionFactor(Enum):
    """决策因子枚举"""
    ERROR_FREQUENCY = "error_frequency"          # 错误频率
    HISTORICAL_SUCCESS = "historical_success"    # 历史成功率
    RESPONSE_TIME = "response_time"             # 响应时间
    USER_CONTEXT = "user_context"               # 用户上下文
    SYSTEM_LOAD = "system_load"                 # 系统负载
    TIME_OF_DAY = "time_of_day"                 # 一天中的时间
    ERROR_PATTERN = "error_pattern"             # 错误模式
    BUSINESS_PRIORITY = "business_priority"     # 业务优先级
    COST_EFFECTIVENESS = "cost_effectiveness"   # 成本效益
    USER_SATISFACTION = "user_satisfaction"     # 用户满意度


@dataclass
class DecisionContext:
    """决策上下文"""
    fallback_context: FallbackContext
    available_strategies: List[FallbackStrategy]
    historical_performance: Dict[str, float]
    system_metrics: Dict[str, Any]
    user_profile: Dict[str, Any]
    business_rules: Dict[str, Any]
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class StrategyScore:
    """策略评分"""
    strategy: FallbackStrategy
    score: float
    confidence: float
    reasoning: List[str]
    factors: Dict[DecisionFactor, float]
    estimated_success_rate: float
    estimated_response_time: float
    estimated_cost: float


@dataclass
class DecisionResult:
    """决策结果"""
    recommended_strategy: FallbackStrategy
    alternative_strategies: List[FallbackStrategy]
    confidence: float
    reasoning: List[str]
    strategy_scores: List[StrategyScore]
    decision_time: float
    metadata: Dict[str, Any] = field(default_factory=dict)


class IntelligentFallbackDecisionEngine:
    """智能回退决策引擎"""
    
    def __init__(self, cache_service: CacheService):
        self.cache_service = cache_service
        self.cache_namespace = "fallback_decision"
        
        # 决策因子权重
        self.decision_weights = {
            DecisionFactor.ERROR_FREQUENCY: 0.15,
            DecisionFactor.HISTORICAL_SUCCESS: 0.20,
            DecisionFactor.RESPONSE_TIME: 0.15,
            DecisionFactor.USER_CONTEXT: 0.10,
            DecisionFactor.SYSTEM_LOAD: 0.10,
            DecisionFactor.TIME_OF_DAY: 0.05,
            DecisionFactor.ERROR_PATTERN: 0.10,
            DecisionFactor.BUSINESS_PRIORITY: 0.08,
            DecisionFactor.COST_EFFECTIVENESS: 0.04,
            DecisionFactor.USER_SATISFACTION: 0.03
        }
        
        # 策略历史性能数据
        self.strategy_performance = defaultdict(lambda: {
            'success_rate': 0.5,
            'avg_response_time': 5.0,
            'cost_score': 0.5,
            'usage_count': 0,
            'recent_performance': deque(maxlen=100)
        })
        
        # 用户满意度评分
        self.user_satisfaction_scores = defaultdict(lambda: 0.5)
        
        # 系统负载监控
        self.system_load_metrics = {
            'cpu_usage': 0.5,
            'memory_usage': 0.5,
            'network_latency': 0.5,
            'concurrent_requests': 0.5
        }
        
        # 业务规则
        self.business_rules = self._load_business_rules()
        
        # 初始化决策模型
        self._initialize_decision_model()
    
    def _load_business_rules(self) -> Dict[str, Any]:
        """加载业务规则"""
        return {
            'vip_user_priority': {
                'enabled': True,
                'vip_levels': ['gold', 'platinum', 'diamond'],
                'priority_bonus': 0.2
            },
            'critical_hours': {
                'enabled': True,
                'hours': [9, 10, 11, 14, 15, 16, 17],  # 工作时间
                'priority_bonus': 0.1
            },
            'error_type_priority': {
                FallbackType.RAGFLOW_QUERY: 0.8,
                FallbackType.INTENT_RECOGNITION: 0.9,
                FallbackType.FUNCTION_CALL: 0.7,
                FallbackType.NLU_ENGINE: 0.9,
                FallbackType.EXTERNAL_SERVICE: 0.6,
                FallbackType.NETWORK_ERROR: 0.5,
                FallbackType.TIMEOUT_ERROR: 0.8,
                FallbackType.RATE_LIMIT_ERROR: 0.4
            },
            'strategy_cost_weights': {
                FallbackStrategy.IMMEDIATE: 0.1,
                FallbackStrategy.RETRY_THEN_FALLBACK: 0.3,
                FallbackStrategy.CIRCUIT_BREAKER: 0.2,
                FallbackStrategy.GRACEFUL_DEGRADATION: 0.4,
                FallbackStrategy.CACHE_FALLBACK: 0.1,
                FallbackStrategy.ALTERNATIVE_SERVICE: 0.8,
                FallbackStrategy.DEFAULT_RESPONSE: 0.1
            }
        }
    
    def _initialize_decision_model(self):
        """初始化决策模型"""
        # 设置策略的默认性能指标
        default_performance = {
            FallbackStrategy.IMMEDIATE: {
                'success_rate': 0.95,
                'avg_response_time': 0.1,
                'cost_score': 0.1,
                'user_satisfaction': 0.3
            },
            FallbackStrategy.RETRY_THEN_FALLBACK: {
                'success_rate': 0.7,
                'avg_response_time': 3.0,
                'cost_score': 0.3,
                'user_satisfaction': 0.6
            },
            FallbackStrategy.CIRCUIT_BREAKER: {
                'success_rate': 0.8,
                'avg_response_time': 0.5,
                'cost_score': 0.2,
                'user_satisfaction': 0.5
            },
            FallbackStrategy.GRACEFUL_DEGRADATION: {
                'success_rate': 0.6,
                'avg_response_time': 1.0,
                'cost_score': 0.4,
                'user_satisfaction': 0.7
            },
            FallbackStrategy.CACHE_FALLBACK: {
                'success_rate': 0.4,
                'avg_response_time': 0.2,
                'cost_score': 0.1,
                'user_satisfaction': 0.8
            },
            FallbackStrategy.ALTERNATIVE_SERVICE: {
                'success_rate': 0.8,
                'avg_response_time': 5.0,
                'cost_score': 0.8,
                'user_satisfaction': 0.7
            },
            FallbackStrategy.DEFAULT_RESPONSE: {
                'success_rate': 1.0,
                'avg_response_time': 0.1,
                'cost_score': 0.1,
                'user_satisfaction': 0.2
            }
        }
        
        for strategy, metrics in default_performance.items():
            self.strategy_performance[strategy].update(metrics)
    
    async def make_decision(self, context: DecisionContext) -> DecisionResult:
        """做出智能决策"""
        start_time = time.time()
        
        try:
            # 1. 收集决策所需的数据
            decision_data = await self._collect_decision_data(context)
            
            # 2. 为每个策略计算评分
            strategy_scores = []
            for strategy in context.available_strategies:
                score = await self._calculate_strategy_score(strategy, context, decision_data)
                strategy_scores.append(score)
            
            # 3. 根据评分排序
            strategy_scores.sort(key=lambda x: x.score, reverse=True)
            
            # 4. 选择最佳策略
            best_strategy = strategy_scores[0]
            alternative_strategies = [s.strategy for s in strategy_scores[1:3]]
            
            # 5. 生成决策推理
            reasoning = self._generate_reasoning(best_strategy, strategy_scores, context)
            
            # 6. 计算决策置信度
            decision_confidence = self._calculate_decision_confidence(strategy_scores)
            
            decision_result = DecisionResult(
                recommended_strategy=best_strategy.strategy,
                alternative_strategies=alternative_strategies,
                confidence=decision_confidence,
                reasoning=reasoning,
                strategy_scores=strategy_scores,
                decision_time=time.time() - start_time,
                metadata={
                    'decision_factors': list(self.decision_weights.keys()),
                    'total_strategies_evaluated': len(strategy_scores),
                    'decision_timestamp': datetime.now().isoformat()
                }
            )
            
            # 7. 记录决策结果
            await self._record_decision(context, decision_result)
            
            return decision_result
            
        except Exception as e:
            logger.error(f"智能决策失败: {str(e)}")
            
            # 返回默认决策
            return DecisionResult(
                recommended_strategy=context.available_strategies[0] if context.available_strategies else FallbackStrategy.DEFAULT_RESPONSE,
                alternative_strategies=[],
                confidence=0.1,
                reasoning=[f"决策失败，使用默认策略: {str(e)}"],
                strategy_scores=[],
                decision_time=time.time() - start_time
            )
    
    async def _collect_decision_data(self, context: DecisionContext) -> Dict[str, Any]:
        """收集决策数据"""
        data = {
            'error_frequency': await self._get_error_frequency(context),
            'historical_performance': await self._get_historical_performance(context),
            'system_metrics': await self._get_system_metrics(),
            'user_profile': self._analyze_user_profile(context),
            'time_factors': self._analyze_time_factors(),
            'error_patterns': await self._analyze_error_patterns(context),
            'business_context': self._analyze_business_context(context)
        }
        
        return data
    
    async def _calculate_strategy_score(self, strategy: FallbackStrategy, 
                                      context: DecisionContext, 
                                      decision_data: Dict[str, Any]) -> StrategyScore:
        """计算策略评分"""
        factors = {}
        reasoning = []
        
        # 1. 错误频率因子
        error_freq_score = self._calculate_error_frequency_score(strategy, decision_data['error_frequency'])
        factors[DecisionFactor.ERROR_FREQUENCY] = error_freq_score
        
        # 2. 历史成功率因子
        historical_score = self._calculate_historical_success_score(strategy, decision_data['historical_performance'])
        factors[DecisionFactor.HISTORICAL_SUCCESS] = historical_score
        
        # 3. 响应时间因子
        response_time_score = self._calculate_response_time_score(strategy, decision_data['system_metrics'])
        factors[DecisionFactor.RESPONSE_TIME] = response_time_score
        
        # 4. 用户上下文因子
        user_context_score = self._calculate_user_context_score(strategy, decision_data['user_profile'])
        factors[DecisionFactor.USER_CONTEXT] = user_context_score
        
        # 5. 系统负载因子
        system_load_score = self._calculate_system_load_score(strategy, decision_data['system_metrics'])
        factors[DecisionFactor.SYSTEM_LOAD] = system_load_score
        
        # 6. 时间因子
        time_score = self._calculate_time_score(strategy, decision_data['time_factors'])
        factors[DecisionFactor.TIME_OF_DAY] = time_score
        
        # 7. 错误模式因子
        error_pattern_score = self._calculate_error_pattern_score(strategy, decision_data['error_patterns'])
        factors[DecisionFactor.ERROR_PATTERN] = error_pattern_score
        
        # 8. 业务优先级因子
        business_priority_score = self._calculate_business_priority_score(strategy, decision_data['business_context'])
        factors[DecisionFactor.BUSINESS_PRIORITY] = business_priority_score
        
        # 9. 成本效益因子
        cost_effectiveness_score = self._calculate_cost_effectiveness_score(strategy, context)
        factors[DecisionFactor.COST_EFFECTIVENESS] = cost_effectiveness_score
        
        # 10. 用户满意度因子
        user_satisfaction_score = self._calculate_user_satisfaction_score(strategy, decision_data['user_profile'])
        factors[DecisionFactor.USER_SATISFACTION] = user_satisfaction_score
        
        # 计算加权总分
        total_score = sum(
            factors[factor] * self.decision_weights[factor]
            for factor in factors
        )
        
        # 生成推理
        reasoning = self._generate_factor_reasoning(strategy, factors)
        
        # 估算指标
        performance = self.strategy_performance[strategy]
        estimated_success_rate = performance['success_rate']
        estimated_response_time = performance['avg_response_time']
        estimated_cost = performance['cost_score']
        
        # 计算置信度
        confidence = self._calculate_strategy_confidence(factors, total_score)
        
        return StrategyScore(
            strategy=strategy,
            score=total_score,
            confidence=confidence,
            reasoning=reasoning,
            factors=factors,
            estimated_success_rate=estimated_success_rate,
            estimated_response_time=estimated_response_time,
            estimated_cost=estimated_cost
        )
    
    def _calculate_error_frequency_score(self, strategy: FallbackStrategy, error_frequency: Dict[str, int]) -> float:
        """计算错误频率评分"""
        error_type = strategy.value  # 简化处理
        recent_errors = error_frequency.get(error_type, 0)
        
        # 错误越频繁，需要更可靠的策略
        if recent_errors > 10:
            reliability_bonus = {
                FallbackStrategy.IMMEDIATE: 0.8,
                FallbackStrategy.CIRCUIT_BREAKER: 0.9,
                FallbackStrategy.CACHE_FALLBACK: 0.7,
                FallbackStrategy.DEFAULT_RESPONSE: 0.9
            }
            return reliability_bonus.get(strategy, 0.5)
        elif recent_errors > 5:
            return 0.6
        else:
            return 0.8
    
    def _calculate_historical_success_score(self, strategy: FallbackStrategy, historical_data: Dict[str, float]) -> float:
        """计算历史成功率评分"""
        performance = self.strategy_performance[strategy]
        success_rate = performance['success_rate']
        
        # 考虑最近的性能趋势
        recent_performance = performance['recent_performance']
        if len(recent_performance) > 0:
            recent_avg = statistics.mean(recent_performance)
            # 加权平均：70%历史，30%最近
            adjusted_score = 0.7 * success_rate + 0.3 * recent_avg
        else:
            adjusted_score = success_rate
        
        return min(1.0, max(0.0, adjusted_score))
    
    def _calculate_response_time_score(self, strategy: FallbackStrategy, system_metrics: Dict[str, Any]) -> float:
        """计算响应时间评分"""
        performance = self.strategy_performance[strategy]
        avg_response_time = performance['avg_response_time']
        
        # 系统负载高时，偏向快速响应的策略
        system_load = system_metrics.get('overall_load', 0.5)
        
        # 响应时间越短，评分越高
        time_score = max(0.1, 1.0 - (avg_response_time / 10.0))
        
        # 系统负载调整
        if system_load > 0.8:
            # 高负载时，更偏向快速策略
            fast_strategy_bonus = {
                FallbackStrategy.IMMEDIATE: 0.3,
                FallbackStrategy.CACHE_FALLBACK: 0.2,
                FallbackStrategy.DEFAULT_RESPONSE: 0.3
            }
            time_score += fast_strategy_bonus.get(strategy, 0.0)
        
        return min(1.0, time_score)
    
    def _calculate_user_context_score(self, strategy: FallbackStrategy, user_profile: Dict[str, Any]) -> float:
        """计算用户上下文评分"""
        base_score = 0.5
        
        # VIP用户偏好
        if user_profile.get('is_vip', False):
            vip_preferred_strategies = {
                FallbackStrategy.ALTERNATIVE_SERVICE: 0.3,
                FallbackStrategy.GRACEFUL_DEGRADATION: 0.2,
                FallbackStrategy.RETRY_THEN_FALLBACK: 0.2
            }
            base_score += vip_preferred_strategies.get(strategy, 0.0)
        
        # 用户耐心度
        user_patience = user_profile.get('patience_level', 0.5)
        if user_patience > 0.7:
            # 高耐心用户可以接受较慢但质量更好的策略
            quality_strategies = {
                FallbackStrategy.RETRY_THEN_FALLBACK: 0.2,
                FallbackStrategy.ALTERNATIVE_SERVICE: 0.3,
                FallbackStrategy.GRACEFUL_DEGRADATION: 0.2
            }
            base_score += quality_strategies.get(strategy, 0.0)
        else:
            # 低耐心用户需要快速响应
            fast_strategies = {
                FallbackStrategy.IMMEDIATE: 0.3,
                FallbackStrategy.CACHE_FALLBACK: 0.2,
                FallbackStrategy.DEFAULT_RESPONSE: 0.2
            }
            base_score += fast_strategies.get(strategy, 0.0)
        
        return min(1.0, base_score)
    
    def _calculate_system_load_score(self, strategy: FallbackStrategy, system_metrics: Dict[str, Any]) -> float:
        """计算系统负载评分"""
        cpu_usage = system_metrics.get('cpu_usage', 0.5)
        memory_usage = system_metrics.get('memory_usage', 0.5)
        network_latency = system_metrics.get('network_latency', 0.5)
        
        overall_load = (cpu_usage + memory_usage + network_latency) / 3
        
        # 系统负载高时，偏向轻量级策略
        if overall_load > 0.8:
            lightweight_bonus = {
                FallbackStrategy.IMMEDIATE: 0.4,
                FallbackStrategy.CACHE_FALLBACK: 0.3,
                FallbackStrategy.DEFAULT_RESPONSE: 0.4,
                FallbackStrategy.CIRCUIT_BREAKER: 0.2
            }
            return lightweight_bonus.get(strategy, 0.1)
        elif overall_load > 0.6:
            return 0.5
        else:
            return 0.8
    
    def _calculate_time_score(self, strategy: FallbackStrategy, time_factors: Dict[str, Any]) -> float:
        """计算时间因子评分"""
        current_hour = time_factors.get('current_hour', 12)
        is_business_hour = time_factors.get('is_business_hour', True)
        
        base_score = 0.5
        
        # 工作时间内，偏向高质量策略
        if is_business_hour:
            business_hour_strategies = {
                FallbackStrategy.ALTERNATIVE_SERVICE: 0.2,
                FallbackStrategy.GRACEFUL_DEGRADATION: 0.3,
                FallbackStrategy.RETRY_THEN_FALLBACK: 0.2
            }
            base_score += business_hour_strategies.get(strategy, 0.0)
        else:
            # 非工作时间，偏向快速策略
            off_hour_strategies = {
                FallbackStrategy.IMMEDIATE: 0.3,
                FallbackStrategy.CACHE_FALLBACK: 0.2,
                FallbackStrategy.DEFAULT_RESPONSE: 0.3
            }
            base_score += off_hour_strategies.get(strategy, 0.0)
        
        return min(1.0, base_score)
    
    def _calculate_error_pattern_score(self, strategy: FallbackStrategy, error_patterns: Dict[str, Any]) -> float:
        """计算错误模式评分"""
        error_trend = error_patterns.get('trend', 'stable')
        error_type = error_patterns.get('primary_type', 'unknown')
        
        base_score = 0.5
        
        # 根据错误趋势调整
        if error_trend == 'increasing':
            # 错误增加时，偏向稳定策略
            stable_strategies = {
                FallbackStrategy.CIRCUIT_BREAKER: 0.3,
                FallbackStrategy.CACHE_FALLBACK: 0.2,
                FallbackStrategy.DEFAULT_RESPONSE: 0.3
            }
            base_score += stable_strategies.get(strategy, 0.0)
        elif error_trend == 'decreasing':
            # 错误减少时，可以尝试更复杂的策略
            complex_strategies = {
                FallbackStrategy.RETRY_THEN_FALLBACK: 0.2,
                FallbackStrategy.ALTERNATIVE_SERVICE: 0.3,
                FallbackStrategy.GRACEFUL_DEGRADATION: 0.2
            }
            base_score += complex_strategies.get(strategy, 0.0)
        
        return min(1.0, base_score)
    
    def _calculate_business_priority_score(self, strategy: FallbackStrategy, business_context: Dict[str, Any]) -> float:
        """计算业务优先级评分"""
        error_type = business_context.get('error_type')
        user_tier = business_context.get('user_tier', 'standard')
        
        # 基于错误类型的优先级
        priority = self.business_rules['error_type_priority'].get(error_type, 0.5)
        
        # 用户等级调整
        if user_tier in ['gold', 'platinum', 'diamond']:
            priority += 0.2
        
        # 策略与优先级的匹配度
        strategy_priority_match = {
            FallbackStrategy.ALTERNATIVE_SERVICE: 0.9,
            FallbackStrategy.GRACEFUL_DEGRADATION: 0.8,
            FallbackStrategy.RETRY_THEN_FALLBACK: 0.7,
            FallbackStrategy.CACHE_FALLBACK: 0.6,
            FallbackStrategy.CIRCUIT_BREAKER: 0.5,
            FallbackStrategy.IMMEDIATE: 0.4,
            FallbackStrategy.DEFAULT_RESPONSE: 0.3
        }
        
        match_score = strategy_priority_match.get(strategy, 0.5)
        
        return min(1.0, priority * match_score)
    
    def _calculate_cost_effectiveness_score(self, strategy: FallbackStrategy, context: DecisionContext) -> float:
        """计算成本效益评分"""
        cost_weight = self.business_rules['strategy_cost_weights'].get(strategy, 0.5)
        
        # 成本越低，评分越高
        cost_score = 1.0 - cost_weight
        
        # 考虑预期成功率
        performance = self.strategy_performance[strategy]
        success_rate = performance['success_rate']
        
        # 成本效益 = 成功率 / 成本
        effectiveness = success_rate / max(0.1, cost_weight)
        
        return min(1.0, effectiveness / 2.0)  # 归一化到0-1
    
    def _calculate_user_satisfaction_score(self, strategy: FallbackStrategy, user_profile: Dict[str, Any]) -> float:
        """计算用户满意度评分"""
        user_id = user_profile.get('user_id', 'unknown')
        current_satisfaction = self.user_satisfaction_scores.get(user_id, 0.5)
        
        # 基于策略的用户满意度影响
        satisfaction_impact = {
            FallbackStrategy.GRACEFUL_DEGRADATION: 0.8,
            FallbackStrategy.CACHE_FALLBACK: 0.7,
            FallbackStrategy.ALTERNATIVE_SERVICE: 0.7,
            FallbackStrategy.RETRY_THEN_FALLBACK: 0.6,
            FallbackStrategy.CIRCUIT_BREAKER: 0.5,
            FallbackStrategy.IMMEDIATE: 0.4,
            FallbackStrategy.DEFAULT_RESPONSE: 0.3
        }
        
        strategy_satisfaction = satisfaction_impact.get(strategy, 0.5)
        
        # 综合当前满意度和策略满意度
        combined_score = 0.6 * current_satisfaction + 0.4 * strategy_satisfaction
        
        return min(1.0, combined_score)
    
    def _calculate_strategy_confidence(self, factors: Dict[DecisionFactor, float], total_score: float) -> float:
        """计算策略置信度"""
        # 基于因子分布的置信度
        factor_values = list(factors.values())
        factor_variance = statistics.variance(factor_values) if len(factor_values) > 1 else 0
        
        # 方差越小，置信度越高
        variance_confidence = max(0.1, 1.0 - factor_variance)
        
        # 基于总分的置信度
        score_confidence = min(1.0, total_score)
        
        # 综合置信度
        combined_confidence = 0.7 * score_confidence + 0.3 * variance_confidence
        
        return min(1.0, combined_confidence)
    
    def _calculate_decision_confidence(self, strategy_scores: List[StrategyScore]) -> float:
        """计算决策置信度"""
        if not strategy_scores:
            return 0.0
        
        # 最佳策略的置信度
        best_confidence = strategy_scores[0].confidence
        
        # 分数差异
        if len(strategy_scores) > 1:
            score_diff = strategy_scores[0].score - strategy_scores[1].score
            diff_confidence = min(1.0, score_diff * 2)  # 差异越大，置信度越高
        else:
            diff_confidence = 0.5
        
        # 综合置信度
        combined_confidence = 0.7 * best_confidence + 0.3 * diff_confidence
        
        return min(1.0, combined_confidence)
    
    def _generate_factor_reasoning(self, strategy: FallbackStrategy, factors: Dict[DecisionFactor, float]) -> List[str]:
        """生成因子推理"""
        reasoning = []
        
        # 找出最强的因子
        sorted_factors = sorted(factors.items(), key=lambda x: x[1], reverse=True)
        
        for factor, score in sorted_factors[:3]:  # 取前3个最强因子
            if score > 0.7:
                reasoning.append(f"{factor.value}: {score:.2f} - 强支持 {strategy.value}")
            elif score > 0.5:
                reasoning.append(f"{factor.value}: {score:.2f} - 支持 {strategy.value}")
            elif score < 0.3:
                reasoning.append(f"{factor.value}: {score:.2f} - 不支持 {strategy.value}")
        
        return reasoning
    
    def _generate_reasoning(self, best_strategy: StrategyScore, all_scores: List[StrategyScore], context: DecisionContext) -> List[str]:
        """生成决策推理"""
        reasoning = []
        
        # 基本选择原因
        reasoning.append(f"选择 {best_strategy.strategy.value}，总分: {best_strategy.score:.3f}")
        
        # 主要支持因子
        top_factors = sorted(best_strategy.factors.items(), key=lambda x: x[1], reverse=True)[:2]
        for factor, score in top_factors:
            reasoning.append(f"主要因子: {factor.value} ({score:.3f})")
        
        # 预期指标
        reasoning.append(f"预期成功率: {best_strategy.estimated_success_rate:.2%}")
        reasoning.append(f"预期响应时间: {best_strategy.estimated_response_time:.1f}s")
        
        # 与其他策略的比较
        if len(all_scores) > 1:
            second_best = all_scores[1]
            score_diff = best_strategy.score - second_best.score
            reasoning.append(f"优于 {second_best.strategy.value} {score_diff:.3f}分")
        
        return reasoning
    
    async def _get_error_frequency(self, context: DecisionContext) -> Dict[str, int]:
        """获取错误频率"""
        try:
            # 从缓存获取最近的错误统计
            cache_key = f"error_frequency_{context.fallback_context.error_type.value}"
            cached_data = await self.cache_service.get(cache_key, namespace=self.cache_namespace)
            
            if cached_data:
                return cached_data
            
            # 默认错误频率
            return {
                context.fallback_context.error_type.value: 1
            }
            
        except Exception as e:
            logger.error(f"获取错误频率失败: {str(e)}")
            return {}
    
    async def _get_historical_performance(self, context: DecisionContext) -> Dict[str, Any]:
        """获取历史性能数据"""
        try:
            # 从缓存获取历史性能数据
            cache_key = f"historical_performance_{context.fallback_context.session_id}"
            cached_data = await self.cache_service.get(cache_key, namespace=self.cache_namespace)
            
            if cached_data:
                return cached_data
            
            # 返回默认历史性能
            return {
                'success_rates': {strategy.value: 0.5 for strategy in context.available_strategies},
                'response_times': {strategy.value: 2.0 for strategy in context.available_strategies}
            }
            
        except Exception as e:
            logger.error(f"获取历史性能失败: {str(e)}")
            return {}
    
    async def _get_system_metrics(self) -> Dict[str, Any]:
        """获取系统指标"""
        try:
            # 模拟系统指标
            import random
            
            return {
                'cpu_usage': random.uniform(0.3, 0.8),
                'memory_usage': random.uniform(0.4, 0.7),
                'network_latency': random.uniform(0.2, 0.6),
                'concurrent_requests': random.randint(10, 100),
                'overall_load': random.uniform(0.3, 0.8)
            }
            
        except Exception as e:
            logger.error(f"获取系统指标失败: {str(e)}")
            return self.system_load_metrics
    
    def _analyze_user_profile(self, context: DecisionContext) -> Dict[str, Any]:
        """分析用户画像"""
        session_context = context.fallback_context.session_context
        
        return {
            'user_id': context.fallback_context.user_id,
            'is_vip': session_context.get('user_tier') in ['gold', 'platinum', 'diamond'],
            'patience_level': session_context.get('patience_level', 0.5),
            'user_tier': session_context.get('user_tier', 'standard'),
            'historical_satisfaction': self.user_satisfaction_scores.get(context.fallback_context.user_id, 0.5)
        }
    
    def _analyze_time_factors(self) -> Dict[str, Any]:
        """分析时间因子"""
        now = datetime.now()
        
        return {
            'current_hour': now.hour,
            'is_business_hour': 9 <= now.hour <= 17,
            'is_weekend': now.weekday() >= 5,
            'time_of_day': 'morning' if now.hour < 12 else 'afternoon' if now.hour < 18 else 'evening'
        }
    
    async def _analyze_error_patterns(self, context: DecisionContext) -> Dict[str, Any]:
        """分析错误模式"""
        try:
            error_type = context.fallback_context.error_type
            
            # 从缓存获取错误模式
            cache_key = f"error_patterns_{error_type.value}"
            cached_patterns = await self.cache_service.get(cache_key, namespace=self.cache_namespace)
            
            if cached_patterns:
                return cached_patterns
            
            # 默认错误模式
            return {
                'trend': 'stable',
                'primary_type': error_type.value,
                'frequency': 'low',
                'severity': 'medium'
            }
            
        except Exception as e:
            logger.error(f"分析错误模式失败: {str(e)}")
            return {'trend': 'stable', 'primary_type': 'unknown'}
    
    def _analyze_business_context(self, context: DecisionContext) -> Dict[str, Any]:
        """分析业务上下文"""
        return {
            'error_type': context.fallback_context.error_type,
            'user_tier': context.fallback_context.session_context.get('user_tier', 'standard'),
            'business_hour': 9 <= datetime.now().hour <= 17,
            'priority_level': self.business_rules['error_type_priority'].get(
                context.fallback_context.error_type, 0.5
            )
        }
    
    async def _record_decision(self, context: DecisionContext, result: DecisionResult):
        """记录决策结果"""
        try:
            decision_record = {
                'timestamp': datetime.now().isoformat(),
                'user_id': context.fallback_context.user_id,
                'session_id': context.fallback_context.session_id,
                'error_type': context.fallback_context.error_type.value,
                'recommended_strategy': result.recommended_strategy.value,
                'confidence': result.confidence,
                'decision_time': result.decision_time,
                'reasoning': result.reasoning
            }
            
            cache_key = f"decision_record_{context.fallback_context.session_id}_{int(context.timestamp.timestamp())}"
            await self.cache_service.set(cache_key, decision_record, ttl=3600, namespace=self.cache_namespace)
            
        except Exception as e:
            logger.error(f"记录决策失败: {str(e)}")
    
    async def update_strategy_performance(self, strategy: FallbackStrategy, result: FallbackResult):
        """更新策略性能"""
        try:
            performance = self.strategy_performance[strategy]
            
            # 更新成功率
            success_value = 1.0 if result.success else 0.0
            performance['recent_performance'].append(success_value)
            
            # 更新计数
            performance['usage_count'] += 1
            
            # 重新计算平均成功率
            if performance['recent_performance']:
                performance['success_rate'] = statistics.mean(performance['recent_performance'])
            
            # 更新响应时间
            if result.response_time > 0:
                performance['avg_response_time'] = (
                    performance['avg_response_time'] * 0.9 + result.response_time * 0.1
                )
            
            logger.info(f"更新策略性能: {strategy.value}, 成功率: {performance['success_rate']:.3f}")
            
        except Exception as e:
            logger.error(f"更新策略性能失败: {str(e)}")
    
    async def update_user_satisfaction(self, user_id: str, satisfaction_score: float):
        """更新用户满意度"""
        try:
            current_score = self.user_satisfaction_scores[user_id]
            # 指数移动平均
            self.user_satisfaction_scores[user_id] = current_score * 0.8 + satisfaction_score * 0.2
            
            logger.info(f"更新用户满意度: {user_id}, 新分数: {self.user_satisfaction_scores[user_id]:.3f}")
            
        except Exception as e:
            logger.error(f"更新用户满意度失败: {str(e)}")
    
    async def get_decision_analytics(self) -> Dict[str, Any]:
        """获取决策分析数据"""
        try:
            analytics = {
                'strategy_performance': dict(self.strategy_performance),
                'user_satisfaction': dict(self.user_satisfaction_scores),
                'decision_weights': {factor.value: weight for factor, weight in self.decision_weights.items()},
                'system_metrics': self.system_load_metrics,
                'business_rules': self.business_rules
            }
            
            return analytics
            
        except Exception as e:
            logger.error(f"获取决策分析失败: {str(e)}")
            return {}
    
    def update_decision_weights(self, new_weights: Dict[DecisionFactor, float]):
        """更新决策权重"""
        try:
            # 验证权重总和为1
            total_weight = sum(new_weights.values())
            if abs(total_weight - 1.0) > 0.01:
                logger.warning(f"权重总和不为1: {total_weight}")
                # 归一化
                new_weights = {factor: weight / total_weight for factor, weight in new_weights.items()}
            
            self.decision_weights.update(new_weights)
            logger.info("决策权重更新成功")
            
        except Exception as e:
            logger.error(f"更新决策权重失败: {str(e)}")


# 全局智能决策引擎实例
_decision_engine: Optional[IntelligentFallbackDecisionEngine] = None


def get_decision_engine(cache_service: CacheService) -> IntelligentFallbackDecisionEngine:
    """获取全局智能决策引擎实例"""
    global _decision_engine
    
    if _decision_engine is None:
        _decision_engine = IntelligentFallbackDecisionEngine(cache_service)
    
    return _decision_engine