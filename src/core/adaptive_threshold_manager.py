"""
自适应阈值管理器
实现动态阈值调整和分类阈值管理
"""

from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
from enum import Enum
from datetime import datetime, timedelta
import statistics
import logging
import json
from collections import defaultdict, deque

from ..config.settings import Settings
from ..utils.logger import get_logger

logger = get_logger(__name__)


class ThresholdType(Enum):
    """阈值类型"""
    CONFIDENCE = "confidence"       # 置信度阈值
    AMBIGUITY = "ambiguity"        # 歧义检测阈值
    SIMILARITY = "similarity"       # 相似度阈值
    RELEVANCE = "relevance"        # 相关性阈值


class AdaptationStrategy(Enum):
    """自适应策略"""
    CONSERVATIVE = "conservative"   # 保守策略
    AGGRESSIVE = "aggressive"       # 激进策略
    BALANCED = "balanced"          # 平衡策略
    CUSTOM = "custom"              # 自定义策略


@dataclass
class ThresholdPerformance:
    """阈值性能指标"""
    success_rate: float
    false_positive_rate: float
    false_negative_rate: float
    avg_confidence_gap: float
    user_satisfaction: float
    total_samples: int
    last_updated: datetime


@dataclass
class AdaptationConfig:
    """自适应配置"""
    strategy: AdaptationStrategy
    learning_rate: float
    min_samples: int
    max_adjustment: float
    stability_window: int
    performance_weight: Dict[str, float]


class AdaptiveThresholdManager:
    """自适应阈值管理器"""
    
    def __init__(self, settings: Settings):
        self.settings = settings
        
        # 基础阈值配置
        self.base_thresholds = {
            ThresholdType.CONFIDENCE: {
                'global': settings.INTENT_CONFIDENCE_THRESHOLD,
                'high': settings.CONFIDENCE_THRESHOLD_HIGH,
                'medium': settings.CONFIDENCE_THRESHOLD_MEDIUM,
                'low': settings.CONFIDENCE_THRESHOLD_LOW
            },
            ThresholdType.AMBIGUITY: {
                'global': settings.AMBIGUITY_DETECTION_THRESHOLD,
                'semantic': 0.8,
                'contextual': 0.6,
                'confidence_gap': 0.15
            },
            ThresholdType.SIMILARITY: {
                'global': 0.7,
                'intent_similarity': 0.8,
                'example_similarity': 0.6
            },
            ThresholdType.RELEVANCE: {
                'global': 0.6,
                'context_relevance': 0.6,
                'domain_relevance': 0.5
            }
        }
        
        # 自适应阈值存储
        self.adaptive_thresholds: Dict[str, Dict[str, float]] = {}
        
        # 意图分类阈值
        self.intent_category_thresholds: Dict[str, Dict[str, float]] = {}
        
        # 用户个性化阈值
        self.user_thresholds: Dict[str, Dict[str, float]] = {}
        
        # 性能历史
        self.performance_history: Dict[str, deque] = defaultdict(lambda: deque(maxlen=100))
        
        # 自适应配置
        self.adaptation_configs = {
            'default': AdaptationConfig(
                strategy=AdaptationStrategy.BALANCED,
                learning_rate=0.1,
                min_samples=10,
                max_adjustment=0.2,
                stability_window=20,
                performance_weight={
                    'success_rate': 0.4,
                    'false_positive_rate': 0.2,
                    'false_negative_rate': 0.2,
                    'user_satisfaction': 0.2
                }
            )
        }
        
        # 最近的调整历史
        self.adjustment_history: Dict[str, List[Dict]] = defaultdict(list)
    
    def get_threshold(self, 
                     threshold_type: ThresholdType,
                     context: Optional[Dict] = None,
                     intent_name: Optional[str] = None,
                     user_id: Optional[str] = None) -> float:
        """
        获取自适应阈值
        
        Args:
            threshold_type: 阈值类型
            context: 上下文信息
            intent_name: 意图名称
            user_id: 用户ID
            
        Returns:
            float: 计算后的阈值
        """
        try:
            # 基础阈值
            base_value = self.base_thresholds[threshold_type]['global']
            
            # 构建阈值键
            threshold_key = self._build_threshold_key(threshold_type, intent_name, user_id)
            
            # 检查自适应阈值
            if threshold_key in self.adaptive_thresholds:
                adaptive_value = self.adaptive_thresholds[threshold_key].get('value', base_value)
            else:
                adaptive_value = base_value
            
            # 检查意图分类阈值
            if intent_name:
                category = self._get_intent_category(intent_name)
                if category in self.intent_category_thresholds:
                    category_threshold = self.intent_category_thresholds[category].get(
                        threshold_type.value, adaptive_value
                    )
                    adaptive_value = (adaptive_value + category_threshold) / 2
            
            # 检查用户个性化阈值
            if user_id and user_id in self.user_thresholds:
                user_threshold = self.user_thresholds[user_id].get(
                    threshold_type.value, adaptive_value
                )
                adaptive_value = (adaptive_value + user_threshold) / 2
            
            # 上下文调整
            if context:
                context_adjustment = self._calculate_context_adjustment(
                    threshold_type, context, adaptive_value
                )
                adaptive_value += context_adjustment
            
            # 确保阈值在合理范围内
            adaptive_value = max(0.1, min(0.95, adaptive_value))
            
            logger.debug(f"获取阈值: {threshold_type.value} -> {adaptive_value:.3f} "
                        f"(基础: {base_value:.3f}, 意图: {intent_name}, 用户: {user_id})")
            
            return adaptive_value
            
        except Exception as e:
            logger.error(f"获取阈值失败: {str(e)}")
            return self.base_thresholds[threshold_type]['global']
    
    async def update_threshold_performance(self,
                                         threshold_type: ThresholdType,
                                         threshold_value: float,
                                         actual_outcome: bool,
                                         predicted_outcome: bool,
                                         confidence_gap: float,
                                         user_satisfaction: Optional[float] = None,
                                         intent_name: Optional[str] = None,
                                         user_id: Optional[str] = None):
        """
        更新阈值性能数据
        
        Args:
            threshold_type: 阈值类型
            threshold_value: 使用的阈值
            actual_outcome: 实际结果
            predicted_outcome: 预测结果
            confidence_gap: 置信度差值
            user_satisfaction: 用户满意度
            intent_name: 意图名称
            user_id: 用户ID
        """
        try:
            threshold_key = self._build_threshold_key(threshold_type, intent_name, user_id)
            
            # 创建性能记录
            performance_record = {
                'timestamp': datetime.now(),
                'threshold_value': threshold_value,
                'actual_outcome': actual_outcome,
                'predicted_outcome': predicted_outcome,
                'confidence_gap': confidence_gap,
                'user_satisfaction': user_satisfaction or 0.7,
                'is_correct': actual_outcome == predicted_outcome
            }
            
            # 添加到历史记录
            self.performance_history[threshold_key].append(performance_record)
            
            # 检查是否需要调整阈值
            if len(self.performance_history[threshold_key]) >= self.adaptation_configs['default'].min_samples:
                await self._consider_threshold_adjustment(threshold_key, threshold_type)
            
        except Exception as e:
            logger.error(f"更新阈值性能失败: {str(e)}")
    
    async def _consider_threshold_adjustment(self, threshold_key: str, threshold_type: ThresholdType):
        """考虑是否需要调整阈值"""
        try:
            recent_records = list(self.performance_history[threshold_key])[-20:]  # 最近20条记录
            
            if len(recent_records) < 10:
                return
            
            # 计算性能指标
            performance = self._calculate_performance_metrics(recent_records)
            
            # 判断是否需要调整
            adjustment_needed, adjustment_direction, adjustment_magnitude = self._analyze_adjustment_need(
                performance, threshold_type
            )
            
            if adjustment_needed:
                await self._adjust_threshold(
                    threshold_key, threshold_type, adjustment_direction, adjustment_magnitude
                )
            
        except Exception as e:
            logger.error(f"阈值调整考虑失败: {str(e)}")
    
    def _calculate_performance_metrics(self, records: List[Dict]) -> ThresholdPerformance:
        """计算性能指标"""
        try:
            total_samples = len(records)
            
            if total_samples == 0:
                return ThresholdPerformance(0, 0, 0, 0, 0, 0, datetime.now())
            
            # 计算各种指标
            correct_predictions = sum(1 for r in records if r['is_correct'])
            success_rate = correct_predictions / total_samples
            
            # 假阳性率：预测为正但实际为负
            false_positives = sum(1 for r in records if r['predicted_outcome'] and not r['actual_outcome'])
            false_positive_rate = false_positives / total_samples
            
            # 假阴性率：预测为负但实际为正
            false_negatives = sum(1 for r in records if not r['predicted_outcome'] and r['actual_outcome'])
            false_negative_rate = false_negatives / total_samples
            
            # 平均置信度差值
            avg_confidence_gap = statistics.mean(r['confidence_gap'] for r in records)
            
            # 平均用户满意度
            avg_user_satisfaction = statistics.mean(r['user_satisfaction'] for r in records)
            
            return ThresholdPerformance(
                success_rate=success_rate,
                false_positive_rate=false_positive_rate,
                false_negative_rate=false_negative_rate,
                avg_confidence_gap=avg_confidence_gap,
                user_satisfaction=avg_user_satisfaction,
                total_samples=total_samples,
                last_updated=datetime.now()
            )
            
        except Exception as e:
            logger.error(f"性能指标计算失败: {str(e)}")
            return ThresholdPerformance(0, 0, 0, 0, 0, 0, datetime.now())
    
    def _analyze_adjustment_need(self, 
                               performance: ThresholdPerformance,
                               threshold_type: ThresholdType) -> Tuple[bool, str, float]:
        """分析是否需要调整阈值"""
        try:
            config = self.adaptation_configs['default']
            
            # 目标性能指标
            target_success_rate = 0.85
            target_false_positive_rate = 0.1
            target_false_negative_rate = 0.1
            
            # 计算偏差
            success_rate_diff = target_success_rate - performance.success_rate
            fp_rate_diff = performance.false_positive_rate - target_false_positive_rate
            fn_rate_diff = performance.false_negative_rate - target_false_negative_rate
            
            # 综合评分（负数表示需要调整）
            performance_score = (
                config.performance_weight['success_rate'] * success_rate_diff -
                config.performance_weight['false_positive_rate'] * fp_rate_diff -
                config.performance_weight['false_negative_rate'] * fn_rate_diff +
                config.performance_weight['user_satisfaction'] * (performance.user_satisfaction - 0.7)
            )
            
            # 如果性能分数足够低，需要调整
            if abs(performance_score) < 0.1:
                return False, "none", 0.0
            
            # 确定调整方向和幅度
            if threshold_type in [ThresholdType.CONFIDENCE, ThresholdType.RELEVANCE]:
                # 对于置信度和相关性阈值
                if performance.false_positive_rate > target_false_positive_rate * 1.5:
                    # 假阳性率过高，提高阈值
                    direction = "increase"
                    magnitude = min(config.max_adjustment, fp_rate_diff * config.learning_rate)
                elif performance.false_negative_rate > target_false_negative_rate * 1.5:
                    # 假阴性率过高，降低阈值
                    direction = "decrease"
                    magnitude = min(config.max_adjustment, fn_rate_diff * config.learning_rate)
                else:
                    return False, "none", 0.0
            else:
                # 对于歧义和相似性阈值
                if performance.success_rate < target_success_rate * 0.8:
                    # 成功率过低，调整阈值
                    direction = "decrease" if performance.false_negative_rate > performance.false_positive_rate else "increase"
                    magnitude = min(config.max_adjustment, abs(success_rate_diff) * config.learning_rate)
                else:
                    return False, "none", 0.0
            
            logger.info(f"阈值调整分析: {threshold_type.value} 需要{direction} {magnitude:.3f} "
                       f"(性能分数: {performance_score:.3f})")
            
            return True, direction, magnitude
            
        except Exception as e:
            logger.error(f"调整需求分析失败: {str(e)}")
            return False, "none", 0.0
    
    async def _adjust_threshold(self, 
                              threshold_key: str, 
                              threshold_type: ThresholdType,
                              direction: str, 
                              magnitude: float):
        """调整阈值"""
        try:
            # 获取当前阈值
            current_threshold = self.adaptive_thresholds.get(threshold_key, {}).get(
                'value', self.base_thresholds[threshold_type]['global']
            )
            
            # 计算新阈值
            if direction == "increase":
                new_threshold = current_threshold + magnitude
            elif direction == "decrease":
                new_threshold = current_threshold - magnitude
            else:
                return
            
            # 确保在合理范围内
            new_threshold = max(0.1, min(0.95, new_threshold))
            
            # 更新阈值
            if threshold_key not in self.adaptive_thresholds:
                self.adaptive_thresholds[threshold_key] = {}
            
            self.adaptive_thresholds[threshold_key].update({
                'value': new_threshold,
                'last_updated': datetime.now(),
                'adjustment_count': self.adaptive_thresholds[threshold_key].get('adjustment_count', 0) + 1,
                'previous_value': current_threshold
            })
            
            # 记录调整历史
            adjustment_record = {
                'timestamp': datetime.now(),
                'threshold_type': threshold_type.value,
                'direction': direction,
                'magnitude': magnitude,
                'old_value': current_threshold,
                'new_value': new_threshold,
                'reason': f"{direction} by {magnitude:.3f}"
            }
            
            self.adjustment_history[threshold_key].append(adjustment_record)
            
            # 限制历史记录长度
            if len(self.adjustment_history[threshold_key]) > 50:
                self.adjustment_history[threshold_key] = self.adjustment_history[threshold_key][-50:]
            
            logger.info(f"阈值已调整: {threshold_key} {current_threshold:.3f} -> {new_threshold:.3f} "
                       f"({direction} {magnitude:.3f})")
            
        except Exception as e:
            logger.error(f"阈值调整失败: {str(e)}")
    
    def set_intent_category_threshold(self, 
                                    category: str, 
                                    threshold_type: ThresholdType, 
                                    value: float):
        """设置意图分类阈值"""
        try:
            if category not in self.intent_category_thresholds:
                self.intent_category_thresholds[category] = {}
            
            self.intent_category_thresholds[category][threshold_type.value] = value
            
            logger.info(f"设置分类阈值: {category}.{threshold_type.value} = {value:.3f}")
            
        except Exception as e:
            logger.error(f"设置分类阈值失败: {str(e)}")
    
    def set_user_threshold(self, 
                          user_id: str, 
                          threshold_type: ThresholdType, 
                          value: float):
        """设置用户个性化阈值"""
        try:
            if user_id not in self.user_thresholds:
                self.user_thresholds[user_id] = {}
            
            self.user_thresholds[user_id][threshold_type.value] = value
            
            logger.info(f"设置用户阈值: {user_id}.{threshold_type.value} = {value:.3f}")
            
        except Exception as e:
            logger.error(f"设置用户阈值失败: {str(e)}")
    
    def _build_threshold_key(self, 
                           threshold_type: ThresholdType,
                           intent_name: Optional[str] = None,
                           user_id: Optional[str] = None) -> str:
        """构建阈值键"""
        parts = [threshold_type.value]
        
        if intent_name:
            parts.append(f"intent_{intent_name}")
        
        if user_id:
            parts.append(f"user_{user_id}")
        
        return ":".join(parts)
    
    def _get_intent_category(self, intent_name: str) -> str:
        """获取意图分类"""
        # 简单的分类逻辑，可以根据实际需要扩展
        if 'flight' in intent_name.lower() or 'book' in intent_name.lower():
            return 'travel'
        elif 'balance' in intent_name.lower() or 'account' in intent_name.lower():
            return 'financial'
        elif 'weather' in intent_name.lower():
            return 'weather'
        else:
            return 'general'
    
    def _calculate_context_adjustment(self, 
                                    threshold_type: ThresholdType,
                                    context: Dict,
                                    base_threshold: float) -> float:
        """计算上下文调整"""
        try:
            adjustment = 0.0
            
            # 基于对话轮次调整
            turn_count = context.get('turn_count', 1)
            if turn_count > 5:
                # 对话轮次多，适当降低阈值
                adjustment -= 0.05
            
            # 基于时间压力调整
            time_pressure = context.get('time_pressure', 0.5)
            if time_pressure > 0.7:
                # 时间压力大，降低阈值加快响应
                adjustment -= 0.1
            
            # 基于用户参与度调整
            user_engagement = context.get('user_engagement', 0.7)
            if user_engagement < 0.3:
                # 用户参与度低，提高阈值确保准确性
                adjustment += 0.05
            
            # 基于历史成功率调整
            success_rate = context.get('recent_success_rate', 0.8)
            if success_rate < 0.6:
                # 最近成功率低，提高阈值
                adjustment += 0.1
            elif success_rate > 0.9:
                # 最近成功率高，可以降低阈值
                adjustment -= 0.05
            
            return adjustment
            
        except Exception as e:
            logger.error(f"上下文调整计算失败: {str(e)}")
            return 0.0
    
    def get_threshold_statistics(self) -> Dict[str, Any]:
        """获取阈值统计信息"""
        try:
            stats = {
                'base_thresholds': {k.value: v for k, v in self.base_thresholds.items()},
                'adaptive_thresholds_count': len(self.adaptive_thresholds),
                'category_thresholds_count': len(self.intent_category_thresholds),
                'user_thresholds_count': len(self.user_thresholds),
                'performance_histories': {k: len(v) for k, v in self.performance_history.items()},
                'recent_adjustments': sum(len(v) for v in self.adjustment_history.values()),
                'threshold_details': {}
            }
            
            # 添加详细的阈值信息
            for key, threshold_data in self.adaptive_thresholds.items():
                stats['threshold_details'][key] = {
                    'current_value': threshold_data.get('value'),
                    'adjustment_count': threshold_data.get('adjustment_count', 0),
                    'last_updated': threshold_data.get('last_updated').isoformat() if threshold_data.get('last_updated') else None
                }
            
            return stats
            
        except Exception as e:
            logger.error(f"获取阈值统计失败: {str(e)}")
            return {'error': str(e)}
    
    def export_thresholds(self) -> Dict[str, Any]:
        """导出阈值配置"""
        try:
            export_data = {
                'base_thresholds': {k.value: v for k, v in self.base_thresholds.items()},
                'adaptive_thresholds': self.adaptive_thresholds,
                'intent_category_thresholds': self.intent_category_thresholds,
                'user_thresholds': self.user_thresholds,
                'export_timestamp': datetime.now().isoformat()
            }
            
            return export_data
            
        except Exception as e:
            logger.error(f"导出阈值配置失败: {str(e)}")
            return {}
    
    def import_thresholds(self, import_data: Dict[str, Any]) -> bool:
        """导入阈值配置"""
        try:
            if 'adaptive_thresholds' in import_data:
                self.adaptive_thresholds.update(import_data['adaptive_thresholds'])
            
            if 'intent_category_thresholds' in import_data:
                self.intent_category_thresholds.update(import_data['intent_category_thresholds'])
            
            if 'user_thresholds' in import_data:
                self.user_thresholds.update(import_data['user_thresholds'])
            
            logger.info("阈值配置导入成功")
            return True
            
        except Exception as e:
            logger.error(f"导入阈值配置失败: {str(e)}")
            return False