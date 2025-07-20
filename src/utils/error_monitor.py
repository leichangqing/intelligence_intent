"""
错误监控和报警系统 (TASK-036)
提供错误统计、报警、通知和分析功能
"""
import asyncio
import json
from typing import Dict, List, Any, Optional, Callable
from datetime import datetime, timedelta
from collections import defaultdict, deque
from dataclasses import dataclass, asdict
from enum import Enum
import logging

from ..core.error_handler import ErrorDetail, ErrorSeverity, ErrorCategory
from ..utils.logger import get_logger

logger = get_logger(__name__)


class AlertLevel(str, Enum):
    """报警级别"""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class MonitoringMetric(str, Enum):
    """监控指标"""
    ERROR_RATE = "error_rate"                    # 错误率
    ERROR_COUNT = "error_count"                  # 错误数量
    CRITICAL_ERROR_COUNT = "critical_error_count"  # 关键错误数量
    ERROR_TREND = "error_trend"                  # 错误趋势
    RESPONSE_TIME = "response_time"              # 响应时间
    AVAILABILITY = "availability"                # 可用性


@dataclass
class Alert:
    """报警信息"""
    id: str
    level: AlertLevel
    title: str
    message: str
    metric: MonitoringMetric
    value: float
    threshold: float
    timestamp: datetime
    error_details: List[ErrorDetail]
    metadata: Dict[str, Any]
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        result = asdict(self)
        result['timestamp'] = self.timestamp.isoformat()
        result['error_details'] = [error.to_dict() for error in self.error_details]
        return result


@dataclass
class MonitoringRule:
    """监控规则"""
    name: str
    metric: MonitoringMetric
    threshold: float
    window_minutes: int
    alert_level: AlertLevel
    condition: str  # 'greater_than', 'less_than', 'equals'
    enabled: bool = True
    cooldown_minutes: int = 5
    description: Optional[str] = None


class ErrorMonitor:
    """错误监控器"""
    
    def __init__(self):
        # 错误统计数据
        self.error_counts: Dict[str, int] = defaultdict(int)
        self.error_history: deque = deque(maxlen=10000)
        self.error_by_category: Dict[str, int] = defaultdict(int)
        self.error_by_severity: Dict[str, int] = defaultdict(int)
        self.error_trends: Dict[str, List[int]] = defaultdict(list)
        
        # 监控规则
        self.monitoring_rules: List[MonitoringRule] = []
        self.alert_history: List[Alert] = []
        self.last_alert_time: Dict[str, datetime] = {}
        
        # 回调函数
        self.alert_callbacks: List[Callable[[Alert], None]] = []
        
        # 性能指标
        self.performance_metrics: Dict[str, List[float]] = defaultdict(list)
        
        # 初始化默认监控规则
        self._setup_default_rules()
        
        # 监控任务将在需要时启动
        self._monitoring_task_started = False
    
    def _setup_default_rules(self):
        """设置默认监控规则"""
        default_rules = [
            MonitoringRule(
                name="高错误率报警",
                metric=MonitoringMetric.ERROR_RATE,
                threshold=0.05,  # 5%
                window_minutes=5,
                alert_level=AlertLevel.WARNING,
                condition="greater_than",
                description="5分钟内错误率超过5%"
            ),
            MonitoringRule(
                name="关键错误报警",
                metric=MonitoringMetric.CRITICAL_ERROR_COUNT,
                threshold=1,
                window_minutes=1,
                alert_level=AlertLevel.CRITICAL,
                condition="greater_than",
                description="1分钟内出现关键错误"
            ),
            MonitoringRule(
                name="大量错误报警",
                metric=MonitoringMetric.ERROR_COUNT,
                threshold=100,
                window_minutes=10,
                alert_level=AlertLevel.ERROR,
                condition="greater_than",
                description="10分钟内错误数量超过100"
            )
        ]
        
        self.monitoring_rules.extend(default_rules)
    
    async def record_error(self, error_detail: ErrorDetail):
        """记录错误"""
        try:
            # 启动监控任务（如果还没有启动）
            if not self._monitoring_task_started:
                try:
                    asyncio.create_task(self._monitoring_task())
                    self._monitoring_task_started = True
                except RuntimeError:
                    # 没有运行的事件循环，跳过后台任务
                    pass
            
            # 添加到历史记录
            self.error_history.append(error_detail)
            
            # 更新统计计数
            self.error_counts[error_detail.code.value] += 1
            self.error_by_category[error_detail.category.value] += 1
            self.error_by_severity[error_detail.severity.value] += 1
            
            # 更新趋势数据
            current_hour = datetime.now().hour
            if len(self.error_trends[str(current_hour)]) == 0:
                self.error_trends[str(current_hour)] = [0] * 60
            
            current_minute = datetime.now().minute
            self.error_trends[str(current_hour)][current_minute] += 1
            
            # 检查监控规则
            await self._check_monitoring_rules()
            
        except Exception as e:
            logger.error(f"记录错误失败: {str(e)}")
    
    async def record_performance_metric(self, metric_name: str, value: float):
        """记录性能指标"""
        try:
            self.performance_metrics[metric_name].append(value)
            
            # 限制历史数据大小
            if len(self.performance_metrics[metric_name]) > 1000:
                self.performance_metrics[metric_name] = self.performance_metrics[metric_name][-1000:]
                
        except Exception as e:
            logger.error(f"记录性能指标失败: {str(e)}")
    
    async def _check_monitoring_rules(self):
        """检查监控规则"""
        try:
            current_time = datetime.now()
            
            for rule in self.monitoring_rules:
                if not rule.enabled:
                    continue
                
                # 检查冷却时间
                if rule.name in self.last_alert_time:
                    time_since_last_alert = current_time - self.last_alert_time[rule.name]
                    if time_since_last_alert < timedelta(minutes=rule.cooldown_minutes):
                        continue
                
                # 计算指标值
                metric_value = await self._calculate_metric(rule.metric, rule.window_minutes)
                
                # 检查条件
                if self._evaluate_condition(metric_value, rule.threshold, rule.condition):
                    # 触发报警
                    await self._trigger_alert(rule, metric_value, current_time)
                    
        except Exception as e:
            logger.error(f"检查监控规则失败: {str(e)}")
    
    async def _calculate_metric(self, metric: MonitoringMetric, window_minutes: int) -> float:
        """计算监控指标"""
        try:
            cutoff_time = datetime.now() - timedelta(minutes=window_minutes)
            
            # 筛选时间窗口内的错误
            window_errors = [
                error for error in self.error_history
                if error.timestamp >= cutoff_time
            ]
            
            if metric == MonitoringMetric.ERROR_COUNT:
                return len(window_errors)
            
            elif metric == MonitoringMetric.CRITICAL_ERROR_COUNT:
                return len([
                    error for error in window_errors
                    if error.severity == ErrorSeverity.CRITICAL
                ])
            
            elif metric == MonitoringMetric.ERROR_RATE:
                # 假设有总请求数统计（这里简化处理）
                total_requests = len(window_errors) * 10  # 简化假设
                if total_requests == 0:
                    return 0.0
                return len(window_errors) / total_requests
            
            elif metric == MonitoringMetric.ERROR_TREND:
                # 计算错误趋势（当前窗口与前一个窗口的比较）
                prev_cutoff = cutoff_time - timedelta(minutes=window_minutes)
                prev_errors = [
                    error for error in self.error_history
                    if prev_cutoff <= error.timestamp < cutoff_time
                ]
                
                current_count = len(window_errors)
                prev_count = len(prev_errors)
                
                if prev_count == 0:
                    return current_count
                
                return (current_count - prev_count) / prev_count
            
            return 0.0
            
        except Exception as e:
            logger.error(f"计算监控指标失败: {str(e)}")
            return 0.0
    
    def _evaluate_condition(self, value: float, threshold: float, condition: str) -> bool:
        """评估条件"""
        if condition == "greater_than":
            return value > threshold
        elif condition == "less_than":
            return value < threshold
        elif condition == "equals":
            return abs(value - threshold) < 0.001
        else:
            return False
    
    async def _trigger_alert(self, rule: MonitoringRule, metric_value: float, timestamp: datetime):
        """触发报警"""
        try:
            # 获取相关错误详情
            cutoff_time = timestamp - timedelta(minutes=rule.window_minutes)
            related_errors = [
                error for error in self.error_history
                if error.timestamp >= cutoff_time
            ]
            
            # 创建报警
            alert = Alert(
                id=f"alert_{timestamp.strftime('%Y%m%d_%H%M%S')}_{rule.name}",
                level=rule.alert_level,
                title=f"监控报警: {rule.name}",
                message=f"{rule.description} - 当前值: {metric_value:.2f}, 阈值: {rule.threshold}",
                metric=rule.metric,
                value=metric_value,
                threshold=rule.threshold,
                timestamp=timestamp,
                error_details=related_errors[-10:],  # 最近10个错误
                metadata={
                    "rule_name": rule.name,
                    "window_minutes": rule.window_minutes,
                    "condition": rule.condition
                }
            )
            
            # 记录报警
            self.alert_history.append(alert)
            self.last_alert_time[rule.name] = timestamp
            
            # 限制报警历史大小
            if len(self.alert_history) > 1000:
                self.alert_history = self.alert_history[-1000:]
            
            # 执行回调
            for callback in self.alert_callbacks:
                try:
                    if asyncio.iscoroutinefunction(callback):
                        await callback(alert)
                    else:
                        callback(alert)
                except Exception as e:
                    logger.error(f"报警回调执行失败: {str(e)}")
            
            # 记录报警日志
            if alert.level == AlertLevel.CRITICAL:
                logger.critical(f"关键报警: {alert.message}")
            elif alert.level == AlertLevel.ERROR:
                logger.error(f"错误报警: {alert.message}")
            elif alert.level == AlertLevel.WARNING:
                logger.warning(f"警告报警: {alert.message}")
            else:
                logger.info(f"信息报警: {alert.message}")
                
        except Exception as e:
            logger.error(f"触发报警失败: {str(e)}")
    
    def add_alert_callback(self, callback: Callable[[Alert], None]):
        """添加报警回调"""
        self.alert_callbacks.append(callback)
        logger.info(f"添加报警回调: {callback.__name__}")
    
    def add_monitoring_rule(self, rule: MonitoringRule):
        """添加监控规则"""
        self.monitoring_rules.append(rule)
        logger.info(f"添加监控规则: {rule.name}")
    
    def remove_monitoring_rule(self, rule_name: str) -> bool:
        """移除监控规则"""
        for i, rule in enumerate(self.monitoring_rules):
            if rule.name == rule_name:
                del self.monitoring_rules[i]
                logger.info(f"移除监控规则: {rule_name}")
                return True
        return False
    
    def get_error_statistics(self) -> Dict[str, Any]:
        """获取错误统计"""
        try:
            current_time = datetime.now()
            
            # 计算时间窗口统计
            last_hour_errors = [
                error for error in self.error_history
                if error.timestamp >= current_time - timedelta(hours=1)
            ]
            
            last_day_errors = [
                error for error in self.error_history
                if error.timestamp >= current_time - timedelta(days=1)
            ]
            
            return {
                "total_errors": len(self.error_history),
                "errors_last_hour": len(last_hour_errors),
                "errors_last_day": len(last_day_errors),
                "errors_by_code": dict(self.error_counts),
                "errors_by_category": dict(self.error_by_category),
                "errors_by_severity": dict(self.error_by_severity),
                "error_trends": dict(self.error_trends),
                "active_monitoring_rules": len([r for r in self.monitoring_rules if r.enabled]),
                "recent_alerts": len([a for a in self.alert_history if a.timestamp >= current_time - timedelta(hours=1)])
            }
            
        except Exception as e:
            logger.error(f"获取错误统计失败: {str(e)}")
            return {}
    
    def get_recent_alerts(self, limit: int = 10) -> List[Dict[str, Any]]:
        """获取最近的报警"""
        try:
            recent = sorted(self.alert_history, key=lambda x: x.timestamp, reverse=True)[:limit]
            return [alert.to_dict() for alert in recent]
            
        except Exception as e:
            logger.error(f"获取最近报警失败: {str(e)}")
            return []
    
    async def _monitoring_task(self):
        """监控后台任务"""
        while True:
            try:
                await asyncio.sleep(60)  # 每分钟检查一次
                
                # 清理过期数据
                await self._cleanup_expired_data()
                
                # 生成监控报告（如果需要）
                await self._generate_monitoring_report()
                
            except Exception as e:
                logger.error(f"监控任务失败: {str(e)}")
                await asyncio.sleep(60)
    
    async def _cleanup_expired_data(self):
        """清理过期数据"""
        try:
            current_time = datetime.now()
            
            # 清理7天前的错误历史
            cutoff_time = current_time - timedelta(days=7)
            self.error_history = deque([
                error for error in self.error_history
                if error.timestamp >= cutoff_time
            ], maxlen=10000)
            
            # 清理30天前的报警历史
            alert_cutoff = current_time - timedelta(days=30)
            self.alert_history = [
                alert for alert in self.alert_history
                if alert.timestamp >= alert_cutoff
            ]
            
        except Exception as e:
            logger.error(f"清理过期数据失败: {str(e)}")
    
    async def _generate_monitoring_report(self):
        """生成监控报告"""
        try:
            # 这里可以实现定期报告生成逻辑
            # 比如每小时、每天的统计报告
            pass
            
        except Exception as e:
            logger.error(f"生成监控报告失败: {str(e)}")


# 全局错误监控器实例
global_error_monitor = ErrorMonitor()


async def email_alert_callback(alert: Alert):
    """邮件报警回调（示例）"""
    try:
        # 这里实现邮件发送逻辑
        logger.info(f"发送邮件报警: {alert.title}")
        
    except Exception as e:
        logger.error(f"邮件报警发送失败: {str(e)}")


async def webhook_alert_callback(alert: Alert):
    """Webhook报警回调（示例）"""
    try:
        # 这里实现Webhook调用逻辑
        logger.info(f"发送Webhook报警: {alert.title}")
        
    except Exception as e:
        logger.error(f"Webhook报警发送失败: {str(e)}")


# 注册默认报警回调
global_error_monitor.add_alert_callback(email_alert_callback)
global_error_monitor.add_alert_callback(webhook_alert_callback)