"""
置信度管理器 - 处理置信度计算和阈值决策
"""

from enum import Enum
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
import logging
import statistics
from datetime import datetime, timedelta

from ..config.settings import Settings
from ..models.intent import Intent
from .adaptive_threshold_manager import AdaptiveThresholdManager, ThresholdType

logger = logging.getLogger(__name__)


class ConfidenceLevel(Enum):
    """置信度等级"""
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    REJECT = "reject"


class ConfidenceSource(Enum):
    """置信度来源"""
    LLM = "llm"
    RULE = "rule"
    CONTEXT = "context"
    HYBRID = "hybrid"


@dataclass
class ConfidenceScore:
    """置信度分数详情"""
    value: float
    source: ConfidenceSource
    components: Dict[str, float]  # 各组件的置信度贡献
    explanation: str = ""
    metadata: Dict[str, Any] = None


@dataclass
class ThresholdDecision:
    """阈值决策结果"""
    level: ConfidenceLevel
    passed: bool
    threshold_used: float
    confidence_score: float
    reason: str
    alternatives: List[Tuple[str, float]] = None


class ConfidenceManager:
    """置信度管理器"""
    
    def __init__(self, settings: Settings):
        self.settings = settings
        self._intent_stats: Dict[str, List[float]] = {}  # 意图历史置信度统计
        self._adaptive_thresholds: Dict[str, float] = {}  # 自适应阈值（保留兼容性）
        
        # 初始化自适应阈值管理器
        self.adaptive_threshold_manager = AdaptiveThresholdManager(settings)
        
        # 预定义阈值
        self.thresholds = {
            ConfidenceLevel.HIGH: settings.CONFIDENCE_THRESHOLD_HIGH,
            ConfidenceLevel.MEDIUM: settings.CONFIDENCE_THRESHOLD_MEDIUM,
            ConfidenceLevel.LOW: settings.CONFIDENCE_THRESHOLD_LOW,
            ConfidenceLevel.REJECT: settings.CONFIDENCE_THRESHOLD_REJECT
        }
        
        # 权重配置
        self.weights = {
            ConfidenceSource.LLM: settings.CONFIDENCE_WEIGHT_LLM,
            ConfidenceSource.RULE: settings.CONFIDENCE_WEIGHT_RULE,
            ConfidenceSource.CONTEXT: settings.CONFIDENCE_WEIGHT_CONTEXT
        }
    
    def calculate_hybrid_confidence(
        self,
        llm_confidence: Optional[float] = None,
        rule_confidence: Optional[float] = None,
        context_confidence: Optional[float] = None,
        intent_name: Optional[str] = None
    ) -> ConfidenceScore:
        """
        计算混合置信度分数
        
        Args:
            llm_confidence: LLM置信度
            rule_confidence: 规则置信度
            context_confidence: 上下文置信度
            intent_name: 意图名称（用于自适应调整）
        
        Returns:
            ConfidenceScore: 综合置信度分数
        """
        components = {}
        total_weight = 0.0
        weighted_sum = 0.0
        
        # 计算各组件贡献
        if llm_confidence is not None:
            weight = self.weights[ConfidenceSource.LLM]
            components['llm'] = llm_confidence
            weighted_sum += llm_confidence * weight
            total_weight += weight
        
        if rule_confidence is not None:
            weight = self.weights[ConfidenceSource.RULE]
            components['rule'] = rule_confidence
            weighted_sum += rule_confidence * weight
            total_weight += weight
        
        if context_confidence is not None:
            weight = self.weights[ConfidenceSource.CONTEXT]
            components['context'] = context_confidence
            weighted_sum += context_confidence * weight
            total_weight += weight
        
        # 标准化权重
        if total_weight > 0:
            final_confidence = weighted_sum / total_weight
        else:
            final_confidence = 0.0
        
        # 自适应调整
        if intent_name and self.settings.ENABLE_ADAPTIVE_THRESHOLDS:
            final_confidence = self._apply_adaptive_adjustment(
                final_confidence, intent_name
            )
        
        # 确保置信度在合理范围内
        final_confidence = max(0.0, min(1.0, final_confidence))
        
        # 生成解释
        explanation = self._generate_confidence_explanation(components, final_confidence)
        
        return ConfidenceScore(
            value=final_confidence,
            source=ConfidenceSource.HYBRID,
            components=components,
            explanation=explanation,
            metadata={
                'weights_used': dict(self.weights),
                'total_weight': total_weight,
                'intent_name': intent_name
            }
        )
    
    def make_threshold_decision(
        self,
        confidence_score: ConfidenceScore,
        intent: Optional[Intent] = None,
        alternatives: Optional[List[Tuple[str, float]]] = None,
        context: Optional[Dict] = None,
        user_id: Optional[str] = None
    ) -> ThresholdDecision:
        """
        基于置信度进行阈值决策（增强版）
        
        Args:
            confidence_score: 置信度分数
            intent: 意图对象
            alternatives: 替代意图列表
            context: 对话上下文
            user_id: 用户ID
        
        Returns:
            ThresholdDecision: 决策结果
        """
        confidence = confidence_score.value
        
        # 使用自适应阈值管理器获取阈值
        if intent and hasattr(intent, 'confidence_threshold') and intent.confidence_threshold:
            threshold = float(intent.confidence_threshold)
            threshold_source = f"intent-specific ({intent.intent_name})"
        else:
            # 使用自适应阈值管理器
            threshold = self.adaptive_threshold_manager.get_threshold(
                ThresholdType.CONFIDENCE,
                context=context,
                intent_name=intent.intent_name if intent else None,
                user_id=user_id
            )
            threshold_source = "adaptive"
        
        # 确定置信度等级
        level = self._get_confidence_level(confidence)
        
        # 判断是否通过阈值
        passed = confidence >= threshold
        
        # 生成决策理由
        reason = self._generate_decision_reason(
            confidence, threshold, level, threshold_source, passed
        )
        
        # 检查歧义性（使用自适应歧义阈值）
        if alternatives and len(alternatives) > 1:
            top_alt_confidence = alternatives[0][1] if alternatives else 0.0
            second_alt_confidence = alternatives[1][1] if len(alternatives) > 1 else 0.0
            
            # 使用自适应歧义检测阈值
            ambiguity_threshold = self.adaptive_threshold_manager.get_threshold(
                ThresholdType.AMBIGUITY,
                context=context,
                intent_name=intent.intent_name if intent else None,
                user_id=user_id
            )
            
            if (top_alt_confidence - second_alt_confidence < ambiguity_threshold):
                reason += f" | 检测到歧义 (差值: {top_alt_confidence - second_alt_confidence:.3f}, 阈值: {ambiguity_threshold:.3f})"
        
        return ThresholdDecision(
            level=level,
            passed=passed,
            threshold_used=threshold,
            confidence_score=confidence,
            reason=reason,
            alternatives=alternatives or []
        )
    
    def calibrate_confidence(
        self,
        raw_confidence: float,
        source: ConfidenceSource,
        metadata: Optional[Dict[str, Any]] = None
    ) -> float:
        """
        校准置信度分数以确保一致性
        
        Args:
            raw_confidence: 原始置信度
            source: 置信度来源
            metadata: 额外元数据
        
        Returns:
            float: 校准后的置信度
        """
        calibrated = raw_confidence
        
        # 基于来源的校准
        if source == ConfidenceSource.LLM:
            # LLM置信度通常偏高，进行保守调整
            calibrated = raw_confidence * 0.95
        elif source == ConfidenceSource.RULE:
            # 规则置信度相对可靠，但设置上限
            calibrated = min(raw_confidence, 0.90)
        elif source == ConfidenceSource.CONTEXT:
            # 上下文置信度作为辅助，适度降权
            calibrated = raw_confidence * 0.8
        
        # 确保在合理范围内
        calibrated = max(0.0, min(1.0, calibrated))
        
        logger.debug(
            f"校准置信度: {source.value} {raw_confidence:.3f} -> {calibrated:.3f}"
        )
        
        return calibrated
    
    def update_intent_statistics(self, intent_name: str, confidence: float, success: bool):
        """
        更新意图统计信息用于自适应阈值调整
        
        Args:
            intent_name: 意图名称
            confidence: 置信度
            success: 是否成功（用户确认）
        """
        if intent_name not in self._intent_stats:
            self._intent_stats[intent_name] = []
        
        # 记录置信度（如果成功则保持原值，失败则记录负值用于区分）
        recorded_confidence = confidence if success else -confidence
        self._intent_stats[intent_name].append(recorded_confidence)
        
        # 限制历史记录长度
        if len(self._intent_stats[intent_name]) > 100:
            self._intent_stats[intent_name] = self._intent_stats[intent_name][-100:]
        
        # 触发自适应阈值更新
        if self.settings.ENABLE_ADAPTIVE_THRESHOLDS:
            self._update_adaptive_threshold(intent_name)
    
    async def update_threshold_performance_async(self,
                                               intent_name: str,
                                               threshold_value: float,
                                               confidence: float,
                                               actual_success: bool,
                                               predicted_success: bool,
                                               user_satisfaction: Optional[float] = None,
                                               user_id: Optional[str] = None):
        """
        异步更新阈值性能数据
        
        Args:
            intent_name: 意图名称
            threshold_value: 使用的阈值
            confidence: 实际置信度
            actual_success: 实际是否成功
            predicted_success: 预测是否成功
            user_satisfaction: 用户满意度
            user_id: 用户ID
        """
        try:
            # 计算置信度差值（这里简化为与阈值的差值）
            confidence_gap = abs(confidence - threshold_value)
            
            # 更新阈值性能
            await self.adaptive_threshold_manager.update_threshold_performance(
                ThresholdType.CONFIDENCE,
                threshold_value,
                actual_success,
                predicted_success,
                confidence_gap,
                user_satisfaction,
                intent_name,
                user_id
            )
            
        except Exception as e:
            logger.error(f"更新阈值性能失败: {str(e)}")
    
    def _get_confidence_level(self, confidence: float) -> ConfidenceLevel:
        """获取置信度等级"""
        if confidence >= self.thresholds[ConfidenceLevel.HIGH]:
            return ConfidenceLevel.HIGH
        elif confidence >= self.thresholds[ConfidenceLevel.MEDIUM]:
            return ConfidenceLevel.MEDIUM
        elif confidence >= self.thresholds[ConfidenceLevel.LOW]:
            return ConfidenceLevel.LOW
        else:
            return ConfidenceLevel.REJECT
    
    def _apply_adaptive_adjustment(self, confidence: float, intent_name: str) -> float:
        """应用自适应调整"""
        if intent_name not in self._intent_stats:
            return confidence
        
        stats = self._intent_stats[intent_name]
        if len(stats) < self.settings.MIN_SAMPLES_FOR_ADAPTATION:
            return confidence
        
        # 计算成功率
        successes = [s for s in stats if s > 0]
        success_rate = len(successes) / len(stats)
        
        # 根据成功率调整置信度
        if success_rate > 0.8:
            # 高成功率，略微提升置信度
            adjustment = 0.05
        elif success_rate < 0.5:
            # 低成功率，降低置信度
            adjustment = -0.1
        else:
            adjustment = 0.0
        
        adjusted = confidence + adjustment
        return max(0.0, min(1.0, adjusted))
    
    def _update_adaptive_threshold(self, intent_name: str):
        """更新自适应阈值"""
        if intent_name not in self._intent_stats:
            return
        
        stats = self._intent_stats[intent_name]
        if len(stats) < self.settings.MIN_SAMPLES_FOR_ADAPTATION:
            return
        
        # 分析成功和失败的置信度分布
        successes = [abs(s) for s in stats if s > 0]
        failures = [abs(s) for s in stats if s < 0]
        
        if not successes:
            return
        
        # 计算新阈值：成功置信度的下四分位数
        success_threshold = statistics.quantile(successes, 0.25)
        
        # 如果有失败案例，确保阈值高于失败置信度的上四分位数
        if failures:
            failure_threshold = statistics.quantile(failures, 0.75)
            success_threshold = max(success_threshold, failure_threshold + 0.1)
        
        # 应用适应率
        current_threshold = self._adaptive_thresholds.get(
            intent_name, self.settings.INTENT_CONFIDENCE_THRESHOLD
        )
        
        new_threshold = (
            current_threshold * (1 - self.settings.THRESHOLD_ADAPTATION_RATE) +
            success_threshold * self.settings.THRESHOLD_ADAPTATION_RATE
        )
        
        # 限制阈值范围
        new_threshold = max(0.3, min(0.9, new_threshold))
        
        self._adaptive_thresholds[intent_name] = new_threshold
        
        logger.info(
            f"更新 {intent_name} 自适应阈值: {current_threshold:.3f} -> {new_threshold:.3f}"
        )
    
    def _generate_confidence_explanation(
        self, components: Dict[str, float], final_confidence: float
    ) -> str:
        """生成置信度解释"""
        parts = []
        
        if 'llm' in components:
            parts.append(f"LLM: {components['llm']:.3f}")
        if 'rule' in components:
            parts.append(f"规则: {components['rule']:.3f}")
        if 'context' in components:
            parts.append(f"上下文: {components['context']:.3f}")
        
        component_str = ", ".join(parts)
        return f"综合置信度 {final_confidence:.3f} (组件: {component_str})"
    
    def _generate_decision_reason(
        self,
        confidence: float,
        threshold: float,
        level: ConfidenceLevel,
        threshold_source: str,
        passed: bool
    ) -> str:
        """生成决策理由"""
        status = "通过" if passed else "未通过"
        return (
            f"置信度 {confidence:.3f} {status} {threshold_source}阈值 {threshold:.3f} "
            f"(等级: {level.value})"
        )
    
    def get_confidence_statistics(self) -> Dict[str, Any]:
        """获取置信度统计信息"""
        stats = {}
        
        for intent_name, values in self._intent_stats.items():
            if not values:
                continue
            
            successes = [s for s in values if s > 0]
            failures = [abs(s) for s in values if s < 0]
            
            stats[intent_name] = {
                'total_samples': len(values),
                'success_count': len(successes),
                'failure_count': len(failures),
                'success_rate': len(successes) / len(values) if values else 0,
                'avg_success_confidence': statistics.mean(successes) if successes else 0,
                'avg_failure_confidence': statistics.mean(failures) if failures else 0,
                'adaptive_threshold': self._adaptive_thresholds.get(intent_name)
            }
        
        return stats