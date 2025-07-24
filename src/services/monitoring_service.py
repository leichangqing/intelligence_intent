"""
监控服务 (V2.2重构)
实时监控系统性能、错误率和关键指标
"""
from typing import Dict, List, Any, Optional, Callable
import asyncio
import time
from datetime import datetime, timedelta
from enum import Enum
from collections import deque, defaultdict

from src.services.health_check_service import SystemHealthCheck, HealthStatus
from src.services.audit_service import AuditService
from src.utils.logger import get_logger

logger = get_logger(__name__)


class AlertLevel(Enum):
    """告警级别"""
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class MetricType(Enum):
    """指标类型"""
    COUNTER = "counter"
    GAUGE = "gauge"
    HISTOGRAM = "histogram"
    TIMER = "timer"


class Alert:
    """告警信息"""
    
    def __init__(self, level: AlertLevel, title: str, message: str, 
                 source: str, details: Dict[str, Any] = None):
        self.level = level
        self.title = title
        self.message = message
        self.source = source
        self.details = details or {}
        self.timestamp = datetime.now()
        self.id = f"{source}_{int(self.timestamp.timestamp())}"
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            'id': self.id,
            'level': self.level.value,
            'title': self.title,
            'message': self.message,
            'source': self.source,
            'details': self.details,
            'timestamp': self.timestamp.isoformat()
        }


class Metric:
    """指标数据"""
    
    def __init__(self, name: str, metric_type: MetricType, value: float, 
                 tags: Dict[str, str] = None, timestamp: datetime = None):
        self.name = name
        self.type = metric_type
        self.value = value
        self.tags = tags or {}
        self.timestamp = timestamp or datetime.now()
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            'name': self.name,
            'type': self.type.value,
            'value': self.value,
            'tags': self.tags,
            'timestamp': self.timestamp.isoformat()
        }


class MonitoringService:
    """监控服务"""
    
    def __init__(self, health_check_service: SystemHealthCheck, 
                 audit_service: Optional[AuditService] = None):
        self.health_check_service = health_check_service
        self.audit_service = audit_service or AuditService()
        self.logger = logger
        
        # 告警存储（内存，实际部署时应使用持久化存储）
        self.alerts = deque(maxlen=1000)  # 最多保存1000个告警
        self.alert_handlers: List[Callable[[Alert], None]] = []
        
        # 指标存储（滑动窗口）
        self.metrics_window_size = 1000
        self.metrics = defaultdict(lambda: deque(maxlen=self.metrics_window_size))
        
        # 监控配置
        self.monitoring_enabled = True
        self.health_check_interval = 300  # 5分钟
        self.metrics_collection_interval = 60  # 1分钟
        
        # 告警规则
        self.alert_rules = {
            'database_response_time': {'threshold': 1000, 'level': AlertLevel.WARNING},
            'cache_response_time': {'threshold': 100, 'level': AlertLevel.WARNING},
            'critical_health_components': {'threshold': 1, 'level': AlertLevel.CRITICAL},
            'warning_health_components': {'threshold': 3, 'level': AlertLevel.WARNING},
            'audit_log_volume': {'threshold': 1000, 'level': AlertLevel.WARNING},
            'data_consistency_issues': {'threshold': 0, 'level': AlertLevel.CRITICAL}
        }
        
        # 监控任务
        self._monitoring_task: Optional[asyncio.Task] = None
        self._health_check_task: Optional[asyncio.Task] = None
    
    async def start_monitoring(self):
        """启动监控服务"""
        if not self.monitoring_enabled:
            return
        
        try:
            self.logger.info("启动监控服务")
            
            # 启动健康检查任务
            self._health_check_task = asyncio.create_task(
                self._periodic_health_check()
            )
            
            # 启动指标收集任务
            self._monitoring_task = asyncio.create_task(
                self._periodic_metrics_collection()
            )
            
            self.logger.info("监控服务启动成功")
            
        except Exception as e:
            self.logger.error(f"启动监控服务失败: {str(e)}")
            raise
    
    async def stop_monitoring(self):
        """停止监控服务"""
        try:
            self.logger.info("停止监控服务")
            
            if self._health_check_task:
                self._health_check_task.cancel()
                try:
                    await self._health_check_task
                except asyncio.CancelledError:
                    pass
            
            if self._monitoring_task:
                self._monitoring_task.cancel()
                try:
                    await self._monitoring_task
                except asyncio.CancelledError:
                    pass
            
            self.logger.info("监控服务已停止")
            
        except Exception as e:
            self.logger.error(f"停止监控服务失败: {str(e)}")
    
    async def _periodic_health_check(self):
        """周期性健康检查"""
        while self.monitoring_enabled:
            try:
                health_report = await self.health_check_service.check_overall_health()
                await self._process_health_report(health_report)
                
                await asyncio.sleep(self.health_check_interval)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"周期性健康检查失败: {str(e)}")
                await asyncio.sleep(30)  # 短暂等待后重试
    
    async def _periodic_metrics_collection(self):
        """周期性指标收集"""
        while self.monitoring_enabled:
            try:
                metrics_data = await self.health_check_service.get_system_metrics()
                await self._process_metrics_data(metrics_data)
                
                await asyncio.sleep(self.metrics_collection_interval)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"周期性指标收集失败: {str(e)}")
                await asyncio.sleep(30)  # 短暂等待后重试
    
    async def _process_health_report(self, health_report: Dict[str, Any]):
        """处理健康检查报告"""
        try:
            overall_status = health_report.get('overall_status')
            components = health_report.get('components', [])
            
            # 记录健康状态指标
            self.record_metric(
                'system_health_status',
                MetricType.GAUGE,
                1 if overall_status == 'healthy' else 0,
                {'status': overall_status}
            )
            
            # 统计各状态的组件数量
            status_counts = defaultdict(int)
            for component in components:
                status = component.get('status', 'unknown')
                status_counts[status] += 1
                
                # 记录组件响应时间
                if 'response_time_ms' in component:
                    self.record_metric(
                        'component_response_time',
                        MetricType.TIMER,
                        component['response_time_ms'],
                        {'component': component.get('name', 'unknown')}
                    )
            
            # 检查告警规则
            critical_components = status_counts.get('critical', 0)
            warning_components = status_counts.get('warning', 0)
            
            if critical_components > 0:
                await self._create_alert(
                    AlertLevel.CRITICAL,
                    "System Health Critical",
                    f"{critical_components} components in critical state",
                    "health_monitor",
                    {'critical_components': critical_components, 'components': components}
                )
            
            elif warning_components >= self.alert_rules['warning_health_components']['threshold']:
                await self._create_alert(
                    AlertLevel.WARNING,
                    "System Health Warning",
                    f"{warning_components} components in warning state",
                    "health_monitor",
                    {'warning_components': warning_components, 'components': components}
                )
            
            # 检查响应时间告警
            for component in components:
                name = component.get('name', 'unknown')
                response_time = component.get('response_time_ms', 0)
                
                if name == 'database' and response_time > self.alert_rules['database_response_time']['threshold']:
                    await self._create_alert(
                        AlertLevel.WARNING,
                        "Database Response Time High",
                        f"Database response time: {response_time:.1f}ms",
                        "performance_monitor",
                        {'component': name, 'response_time_ms': response_time}
                    )
                
                elif name == 'cache' and response_time > self.alert_rules['cache_response_time']['threshold']:
                    await self._create_alert(
                        AlertLevel.WARNING,
                        "Cache Response Time High",
                        f"Cache response time: {response_time:.1f}ms",
                        "performance_monitor",
                        {'component': name, 'response_time_ms': response_time}
                    )
            
            # 检查数据一致性告警
            for component in components:
                if component.get('name') == 'data_consistency':
                    details = component.get('details', {})
                    issues = details.get('issues', [])
                    
                    if issues:
                        await self._create_alert(
                            AlertLevel.CRITICAL,
                            "Data Consistency Issues",
                            f"Found data consistency issues: {'; '.join(issues)}",
                            "data_consistency_monitor",
                            {'issues': issues, 'details': details}
                        )
            
        except Exception as e:
            self.logger.error(f"处理健康检查报告失败: {str(e)}")
    
    async def _process_metrics_data(self, metrics_data: Dict[str, Any]):
        """处理指标数据"""
        try:
            if 'error' in metrics_data:
                return
            
            # 处理数据库统计指标
            db_stats = metrics_data.get('database_stats', {})
            if 'intents' in db_stats:
                self.record_metric(
                    'intents_total',
                    MetricType.GAUGE,
                    db_stats['intents']['total']
                )
                self.record_metric(
                    'intents_active',
                    MetricType.GAUGE,
                    db_stats['intents']['active']
                )
            
            if 'conversations' in db_stats:
                self.record_metric(
                    'conversations_total',
                    MetricType.GAUGE,
                    db_stats['conversations']['total']
                )
                self.record_metric(
                    'conversations_daily',
                    MetricType.GAUGE,
                    db_stats['conversations']['last_24h']
                )
            
            if 'slot_values' in db_stats:
                self.record_metric(
                    'slot_values_total',
                    MetricType.GAUGE,
                    db_stats['slot_values']['total']
                )
            
            # 处理审计统计指标
            audit_stats = metrics_data.get('audit_stats', {})
            if 'config_changes' in audit_stats:
                daily_config_changes = audit_stats['config_changes']['last_24h']
                self.record_metric(
                    'config_changes_daily',
                    MetricType.GAUGE,
                    daily_config_changes
                )
                
                # 检查配置变更量告警
                if daily_config_changes > self.alert_rules['audit_log_volume']['threshold']:
                    await self._create_alert(
                        AlertLevel.WARNING,
                        "High Configuration Change Volume",
                        f"High volume of configuration changes: {daily_config_changes} in last 24h",
                        "audit_monitor",
                        {'config_changes_24h': daily_config_changes}
                    )
            
            if 'cache_invalidations' in audit_stats:
                self.record_metric(
                    'cache_invalidations_daily',
                    MetricType.GAUGE,
                    audit_stats['cache_invalidations']['last_24h']
                )
            
        except Exception as e:
            self.logger.error(f"处理指标数据失败: {str(e)}")
    
    def record_metric(self, name: str, metric_type: MetricType, value: float, 
                     tags: Dict[str, str] = None):
        """记录指标"""
        try:
            metric = Metric(name, metric_type, value, tags)
            self.metrics[name].append(metric)
            
            # 异步记录到审计日志（可选）
            # asyncio.create_task(self._log_metric_to_audit(metric))
            
        except Exception as e:
            self.logger.error(f"记录指标失败: {str(e)}")
    
    async def _create_alert(self, level: AlertLevel, title: str, message: str, 
                          source: str, details: Dict[str, Any] = None):
        """创建告警"""
        try:
            alert = Alert(level, title, message, source, details)
            self.alerts.append(alert)
            
            # 调用告警处理器
            for handler in self.alert_handlers:
                try:
                    handler(alert)
                except Exception as e:
                    self.logger.error(f"告警处理器执行失败: {str(e)}")
            
            # 记录到审计日志
            await self.audit_service.log_config_change(
                table_name="monitoring_alerts",
                record_id=0,
                action=self.audit_service.AuditAction.INSERT,
                old_values=None,
                new_values=alert.to_dict(),
                operator_id="monitoring_service"
            )
            
            self.logger.warning(f"监控告警: [{level.value.upper()}] {title} - {message}")
            
        except Exception as e:
            self.logger.error(f"创建告警失败: {str(e)}")
    
    def add_alert_handler(self, handler: Callable[[Alert], None]):
        """添加告警处理器"""
        self.alert_handlers.append(handler)
    
    def remove_alert_handler(self, handler: Callable[[Alert], None]):
        """移除告警处理器"""
        if handler in self.alert_handlers:
            self.alert_handlers.remove(handler)
    
    def get_recent_alerts(self, hours: int = 24, level: Optional[AlertLevel] = None) -> List[Dict[str, Any]]:
        """获取最近的告警"""
        cutoff_time = datetime.now() - timedelta(hours=hours)
        
        recent_alerts = [
            alert.to_dict() for alert in self.alerts
            if alert.timestamp >= cutoff_time and (level is None or alert.level == level)
        ]
        
        return sorted(recent_alerts, key=lambda x: x['timestamp'], reverse=True)
    
    def get_metrics(self, name: str, hours: int = 1) -> List[Dict[str, Any]]:
        """获取指定时间范围内的指标"""
        cutoff_time = datetime.now() - timedelta(hours=hours)
        
        if name not in self.metrics:
            return []
        
        recent_metrics = [
            metric.to_dict() for metric in self.metrics[name]
            if metric.timestamp >= cutoff_time
        ]
        
        return sorted(recent_metrics, key=lambda x: x['timestamp'])
    
    def get_monitoring_status(self) -> Dict[str, Any]:
        """获取监控服务状态"""
        return {
            'monitoring_enabled': self.monitoring_enabled,
            'health_check_interval': self.health_check_interval,
            'metrics_collection_interval': self.metrics_collection_interval,
            'health_check_task_running': self._health_check_task is not None and not self._health_check_task.done(),
            'monitoring_task_running': self._monitoring_task is not None and not self._monitoring_task.done(),
            'alerts_count': len(self.alerts),
            'metrics_count': sum(len(metrics) for metrics in self.metrics.values()),
            'alert_handlers_count': len(self.alert_handlers),
            'uptime': datetime.now().isoformat()
        }
    
    async def update_alert_rules(self, rules: Dict[str, Dict[str, Any]]):
        """更新告警规则"""
        try:
            old_rules = self.alert_rules.copy()
            self.alert_rules.update(rules)
            
            # 记录规则变更到审计日志
            await self.audit_service.log_config_change(
                table_name="monitoring_alert_rules",
                record_id=0,
                action=self.audit_service.AuditAction.UPDATE,
                old_values=old_rules,
                new_values=self.alert_rules,
                operator_id="monitoring_admin"
            )
            
            self.logger.info("告警规则已更新")
            
        except Exception as e:
            self.logger.error(f"更新告警规则失败: {str(e)}")
            raise


# 默认告警处理器
def default_alert_handler(alert: Alert):
    """默认告警处理器 - 记录到日志"""
    logger_level = {
        AlertLevel.INFO: logger.info,
        AlertLevel.WARNING: logger.warning,
        AlertLevel.CRITICAL: logger.error
    }.get(alert.level, logger.info)
    
    logger_level(f"ALERT [{alert.level.value.upper()}] {alert.title}: {alert.message}")


# 全局监控服务实例
_monitoring_service: Optional[MonitoringService] = None


def get_monitoring_service(health_check_service: SystemHealthCheck) -> MonitoringService:
    """
    获取监控服务实例
    
    Args:
        health_check_service: 健康检查服务实例
        
    Returns:
        MonitoringService: 监控服务实例
    """
    global _monitoring_service
    if _monitoring_service is None:
        _monitoring_service = MonitoringService(health_check_service)
        _monitoring_service.add_alert_handler(default_alert_handler)
    
    return _monitoring_service