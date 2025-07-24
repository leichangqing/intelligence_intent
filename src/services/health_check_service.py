"""
健康检查服务 (V2.2重构)
确保重构后系统稳定性的监控和健康检查功能
"""
from typing import Dict, List, Any, Optional, Tuple
import asyncio
import time
from datetime import datetime, timedelta
from enum import Enum

from src.models.base import database
from src.models.intent import Intent
from src.models.slot import Slot, SlotValue
from src.models.conversation import Conversation
from src.models.audit import ConfigAuditLog, CacheInvalidationLog
from src.services.cache_service import CacheService
from src.services.audit_service import AuditService
from src.utils.logger import get_logger

logger = get_logger(__name__)


class HealthStatus(Enum):
    """健康状态枚举"""
    HEALTHY = "healthy"
    WARNING = "warning"
    CRITICAL = "critical"
    UNKNOWN = "unknown"


class ComponentHealth:
    """组件健康状态"""
    
    def __init__(self, name: str, status: HealthStatus, message: str = "", 
                 response_time_ms: float = 0.0, details: Dict[str, Any] = None):
        self.name = name
        self.status = status
        self.message = message
        self.response_time_ms = response_time_ms
        self.details = details or {}
        self.timestamp = datetime.now()
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            'name': self.name,
            'status': self.status.value,
            'message': self.message,
            'response_time_ms': self.response_time_ms,
            'details': self.details,
            'timestamp': self.timestamp.isoformat()
        }


class SystemHealthCheck:
    """系统健康检查"""
    
    def __init__(self, cache_service: CacheService, audit_service: Optional[AuditService] = None):
        self.cache_service = cache_service
        self.audit_service = audit_service or AuditService()
        self.logger = logger
    
    async def check_overall_health(self) -> Dict[str, Any]:
        """
        检查系统整体健康状况
        
        Returns:
            Dict[str, Any]: 系统健康检查报告
        """
        start_time = time.time()
        
        try:
            # 执行各组件健康检查
            checks = await asyncio.gather(
                self._check_database_health(),
                self._check_cache_health(),
                self._check_audit_system_health(),
                self._check_data_consistency(),
                self._check_v22_migration_status(),
                self._check_performance_metrics(),
                return_exceptions=True
            )
            
            # 解析检查结果
            components = []
            overall_status = HealthStatus.HEALTHY
            
            for check in checks:
                if isinstance(check, Exception):
                    components.append(ComponentHealth(
                        name="unknown",
                        status=HealthStatus.CRITICAL,
                        message=f"Health check failed: {str(check)}"
                    ))
                    overall_status = HealthStatus.CRITICAL
                else:
                    components.append(check)
                    # 更新整体状态
                    if check.status == HealthStatus.CRITICAL:
                        overall_status = HealthStatus.CRITICAL
                    elif check.status == HealthStatus.WARNING and overall_status != HealthStatus.CRITICAL:
                        overall_status = HealthStatus.WARNING
            
            execution_time = (time.time() - start_time) * 1000
            
            report = {
                'overall_status': overall_status.value,
                'execution_time_ms': execution_time,
                'timestamp': datetime.now().isoformat(),
                'components': [comp.to_dict() for comp in components],
                'summary': {
                    'total_components': len(components),
                    'healthy': sum(1 for c in components if c.status == HealthStatus.HEALTHY),
                    'warning': sum(1 for c in components if c.status == HealthStatus.WARNING),
                    'critical': sum(1 for c in components if c.status == HealthStatus.CRITICAL)
                }
            }
            
            # 记录健康检查审计日志
            try:
                await self.audit_service.log_config_change(
                    table_name="system_health",
                    record_id=0,
                    action=self.audit_service.AuditAction.INSERT,
                    old_values=None,
                    new_values=report['summary'],
                    operator_id="health_check_service"
                )
            except Exception as e:
                self.logger.warning(f"记录健康检查审计日志失败: {str(e)}")
            
            return report
            
        except Exception as e:
            self.logger.error(f"系统健康检查失败: {str(e)}")
            return {
                'overall_status': HealthStatus.CRITICAL.value,
                'execution_time_ms': (time.time() - start_time) * 1000,
                'timestamp': datetime.now().isoformat(),
                'components': [],
                'error': str(e)
            }
    
    async def _check_database_health(self) -> ComponentHealth:
        """检查数据库健康状态"""
        start_time = time.time()
        
        try:
            # 测试数据库连接
            if not database.is_closed():
                database.close()
            database.connect()
            
            # 执行简单查询测试
            intent_count = Intent.select().count()
            slot_count = Slot.select().count()
            conversation_count = Conversation.select().where(
                Conversation.created_at >= datetime.now() - timedelta(days=1)
            ).count()
            
            response_time = (time.time() - start_time) * 1000
            
            # 检查关键表的存在和基本数据
            if intent_count == 0:
                return ComponentHealth(
                    name="database",
                    status=HealthStatus.WARNING,
                    message="No intents configured",
                    response_time_ms=response_time,
                    details={
                        'intent_count': intent_count,
                        'slot_count': slot_count,
                        'recent_conversations': conversation_count
                    }
                )
            
            return ComponentHealth(
                name="database",
                status=HealthStatus.HEALTHY,
                message="Database connection and queries working normally",
                response_time_ms=response_time,
                details={
                    'intent_count': intent_count,
                    'slot_count': slot_count,
                    'recent_conversations': conversation_count,
                    'connection_status': 'connected'
                }
            )
            
        except Exception as e:
            return ComponentHealth(
                name="database",
                status=HealthStatus.CRITICAL,
                message=f"Database health check failed: {str(e)}",
                response_time_ms=(time.time() - start_time) * 1000,
                details={'error': str(e)}
            )
    
    async def _check_cache_health(self) -> ComponentHealth:
        """检查缓存系统健康状态"""
        start_time = time.time()
        
        try:
            # 测试缓存写入和读取
            test_key = f"health_check_test:{int(time.time())}"
            test_value = {"timestamp": datetime.now().isoformat(), "test": True}
            
            # 写入测试
            await self.cache_service.set(test_key, test_value, ttl=60)
            
            # 读取测试
            cached_value = await self.cache_service.get(test_key)
            
            # 清理测试数据
            await self.cache_service.delete(test_key)
            
            response_time = (time.time() - start_time) * 1000
            
            if cached_value is None:
                return ComponentHealth(
                    name="cache",
                    status=HealthStatus.CRITICAL,
                    message="Cache read/write test failed",
                    response_time_ms=response_time,
                    details={'test_key': test_key, 'cached_value': cached_value}
                )
            
            # 检查缓存性能
            if response_time > 100:  # 100ms阈值
                return ComponentHealth(
                    name="cache",
                    status=HealthStatus.WARNING,
                    message="Cache response time is slow",
                    response_time_ms=response_time,
                    details={'threshold_ms': 100}
                )
            
            return ComponentHealth(
                name="cache",
                status=HealthStatus.HEALTHY,
                message="Cache system working normally",
                response_time_ms=response_time,
                details={'test_successful': True}
            )
            
        except Exception as e:
            return ComponentHealth(
                name="cache",
                status=HealthStatus.CRITICAL,
                message=f"Cache health check failed: {str(e)}",
                response_time_ms=(time.time() - start_time) * 1000,
                details={'error': str(e)}
            )
    
    async def _check_audit_system_health(self) -> ComponentHealth:
        """检查审计系统健康状态"""
        start_time = time.time()
        
        try:
            # 检查审计日志表的可访问性
            recent_config_logs = ConfigAuditLog.select().where(
                ConfigAuditLog.created_at >= datetime.now() - timedelta(hours=1)
            ).count()
            
            recent_cache_logs = CacheInvalidationLog.select().where(
                CacheInvalidationLog.created_at >= datetime.now() - timedelta(hours=1)
            ).count()
            
            # 测试审计日志写入
            try:
                test_log = await self.audit_service.log_config_change(
                    table_name="health_check_test",
                    record_id=0,
                    action=self.audit_service.AuditAction.INSERT,
                    old_values=None,
                    new_values={"test": True, "timestamp": datetime.now().isoformat()},
                    operator_id="health_check"
                )
                audit_write_success = True
            except Exception as e:
                audit_write_success = False
                self.logger.warning(f"审计日志写入测试失败: {str(e)}")
            
            response_time = (time.time() - start_time) * 1000
            
            if not audit_write_success:
                return ComponentHealth(
                    name="audit_system",
                    status=HealthStatus.CRITICAL,
                    message="Audit log write test failed",
                    response_time_ms=response_time,
                    details={
                        'recent_config_logs': recent_config_logs,
                        'recent_cache_logs': recent_cache_logs,
                        'write_test_passed': audit_write_success
                    }
                )
            
            return ComponentHealth(
                name="audit_system",
                status=HealthStatus.HEALTHY,
                message="Audit system working normally",
                response_time_ms=response_time,
                details={
                    'recent_config_logs': recent_config_logs,
                    'recent_cache_logs': recent_cache_logs,
                    'write_test_passed': audit_write_success
                }
            )
            
        except Exception as e:
            return ComponentHealth(
                name="audit_system",
                status=HealthStatus.CRITICAL,
                message=f"Audit system health check failed: {str(e)}",
                response_time_ms=(time.time() - start_time) * 1000,
                details={'error': str(e)}
            )
    
    async def _check_data_consistency(self) -> ComponentHealth:
        """检查V2.2数据一致性"""
        start_time = time.time()
        
        try:
            # 检查槽位值数据一致性
            total_slot_values = SlotValue.select().count()
            
            # 检查orphaned slot values（没有对应conversation的槽位值）
            orphaned_slot_values = SlotValue.select().where(
                SlotValue.conversation_id.is_null(False),
                ~SlotValue.conversation_id.in_(
                    Conversation.select(Conversation.id)
                )
            ).count()
            
            # 检查conversations表中是否还有未迁移的JSON槽位数据
            conversations_with_json_slots = Conversation.select().where(
                (Conversation.slots_filled.is_null(False)) |
                (Conversation.slots_missing.is_null(False))
            ).count()
            
            # 检查数据类型一致性（V2.2改进）
            config_logs_with_invalid_record_id = ConfigAuditLog.select().where(
                ConfigAuditLog.record_id < 0
            ).count()
            
            response_time = (time.time() - start_time) * 1000
            
            issues = []
            if orphaned_slot_values > 0:
                issues.append(f"{orphaned_slot_values} orphaned slot values")
            
            if conversations_with_json_slots > 0:
                issues.append(f"{conversations_with_json_slots} conversations with unmigrated JSON slots")
            
            if config_logs_with_invalid_record_id > 0:
                issues.append(f"{config_logs_with_invalid_record_id} audit logs with invalid record IDs")
            
            status = HealthStatus.HEALTHY
            message = "Data consistency checks passed"
            
            if issues:
                if orphaned_slot_values > 100 or conversations_with_json_slots > 0:
                    status = HealthStatus.CRITICAL
                    message = f"Critical data consistency issues: {'; '.join(issues)}"
                else:
                    status = HealthStatus.WARNING
                    message = f"Minor data consistency issues: {'; '.join(issues)}"
            
            return ComponentHealth(
                name="data_consistency",
                status=status,
                message=message,
                response_time_ms=response_time,
                details={
                    'total_slot_values': total_slot_values,
                    'orphaned_slot_values': orphaned_slot_values,
                    'conversations_with_json_slots': conversations_with_json_slots,
                    'invalid_audit_record_ids': config_logs_with_invalid_record_id,
                    'issues': issues
                }
            )
            
        except Exception as e:
            return ComponentHealth(
                name="data_consistency",
                status=HealthStatus.CRITICAL,
                message=f"Data consistency check failed: {str(e)}",
                response_time_ms=(time.time() - start_time) * 1000,
                details={'error': str(e)}
            )
    
    async def _check_v22_migration_status(self) -> ComponentHealth:
        """检查V2.2迁移状态"""
        start_time = time.time()
        
        try:
            # 检查V2.2迁移相关的审计记录
            migration_logs = list(ConfigAuditLog.select().where(
                ConfigAuditLog.table_name_field == 'system_upgrade'
            ).order_by(ConfigAuditLog.created_at.desc()))
            
            # 检查是否有V2.2迁移完成的记录
            v22_completion_log = None
            for log in migration_logs:
                try:
                    new_values = log.get_new_values()
                    if new_values and new_values.get('version') == 'v2.2' and new_values.get('completed_at'):
                        v22_completion_log = log
                        break
                except:
                    continue
            
            # 检查slot_values表中的迁移数据
            migrated_slot_values = SlotValue.select().where(
                SlotValue.extracted_from.in_(['migration_v21', 'session_migration'])
            ).count()
            
            # 检查备份表是否存在
            backup_table_exists = False
            try:
                database.execute_sql("SELECT 1 FROM _backup_conversations_v21 LIMIT 1")
                backup_table_exists = True
            except:
                pass
            
            response_time = (time.time() - start_time) * 1000
            
            # 评估迁移状态
            if v22_completion_log is None:
                status = HealthStatus.WARNING
                message = "V2.2 migration completion not recorded"
            elif migrated_slot_values == 0:
                status = HealthStatus.WARNING
                message = "No migrated slot values found"
            else:
                status = HealthStatus.HEALTHY
                message = "V2.2 migration appears successful"
            
            return ComponentHealth(
                name="v22_migration",
                status=status,
                message=message,
                response_time_ms=response_time,
                details={
                    'migration_logs_count': len(migration_logs),
                    'completion_recorded': v22_completion_log is not None,
                    'completion_date': v22_completion_log.created_at.isoformat() if v22_completion_log else None,
                    'migrated_slot_values': migrated_slot_values,
                    'backup_table_exists': backup_table_exists
                }
            )
            
        except Exception as e:
            return ComponentHealth(
                name="v22_migration",
                status=HealthStatus.CRITICAL,
                message=f"V2.2 migration status check failed: {str(e)}",
                response_time_ms=(time.time() - start_time) * 1000,
                details={'error': str(e)}
            )
    
    async def _check_performance_metrics(self) -> ComponentHealth:
        """检查系统性能指标"""
        start_time = time.time()
        
        try:
            # 检查最近对话的平均处理时间
            recent_conversations = list(
                Conversation.select().where(
                    Conversation.created_at >= datetime.now() - timedelta(hours=1),
                    Conversation.processing_time_ms.is_null(False)
                ).order_by(Conversation.created_at.desc()).limit(100)
            )
            
            if recent_conversations:
                processing_times = [
                    conv.processing_time_ms for conv in recent_conversations
                    if conv.processing_time_ms is not None
                ]
                
                if processing_times:
                    avg_processing_time = sum(processing_times) / len(processing_times)
                    max_processing_time = max(processing_times)
                    min_processing_time = min(processing_times)
                else:
                    avg_processing_time = max_processing_time = min_processing_time = 0
            else:
                avg_processing_time = max_processing_time = min_processing_time = 0
            
            # 检查审计日志增长率
            recent_audit_logs = ConfigAuditLog.select().where(
                ConfigAuditLog.created_at >= datetime.now() - timedelta(hours=1)
            ).count()
            
            response_time = (time.time() - start_time) * 1000
            
            # 性能评估
            issues = []
            if avg_processing_time > 5000:  # 5秒阈值
                issues.append(f"High average processing time: {avg_processing_time:.1f}ms")
            
            if max_processing_time > 30000:  # 30秒阈值
                issues.append(f"Very slow conversation detected: {max_processing_time:.1f}ms")
            
            if recent_audit_logs > 10000:  # 每小时10000条审计日志可能表示问题
                issues.append(f"High audit log volume: {recent_audit_logs} logs/hour")
            
            if issues:
                status = HealthStatus.WARNING
                message = f"Performance issues detected: {'; '.join(issues)}"
            else:
                status = HealthStatus.HEALTHY
                message = "Performance metrics within normal range"
            
            return ComponentHealth(
                name="performance",
                status=status,
                message=message,
                response_time_ms=response_time,
                details={
                    'recent_conversations_count': len(recent_conversations),
                    'avg_processing_time_ms': avg_processing_time,
                    'max_processing_time_ms': max_processing_time,
                    'min_processing_time_ms': min_processing_time,
                    'recent_audit_logs': recent_audit_logs,
                    'issues': issues
                }
            )
            
        except Exception as e:
            return ComponentHealth(
                name="performance",
                status=HealthStatus.CRITICAL,
                message=f"Performance metrics check failed: {str(e)}",
                response_time_ms=(time.time() - start_time) * 1000,
                details={'error': str(e)}
            )
    
    async def get_system_metrics(self) -> Dict[str, Any]:
        """
        获取系统指标
        
        Returns:
            Dict[str, Any]: 系统指标报告
        """
        try:
            # 数据库统计
            intent_count = Intent.select().count()
            active_intent_count = Intent.select().where(Intent.is_active == True).count()
            slot_count = Slot.select().count()
            slot_value_count = SlotValue.select().count()
            
            # 对话统计
            total_conversations = Conversation.select().count()
            recent_conversations = Conversation.select().where(
                Conversation.created_at >= datetime.now() - timedelta(days=1)
            ).count()
            
            # 审计统计
            config_audit_count = ConfigAuditLog.select().count()
            recent_config_changes = ConfigAuditLog.select().where(
                ConfigAuditLog.created_at >= datetime.now() - timedelta(days=1)
            ).count()
            
            cache_invalidation_count = CacheInvalidationLog.select().count()
            recent_cache_invalidations = CacheInvalidationLog.select().where(
                CacheInvalidationLog.created_at >= datetime.now() - timedelta(days=1)
            ).count()
            
            return {
                'timestamp': datetime.now().isoformat(),
                'database_stats': {
                    'intents': {'total': intent_count, 'active': active_intent_count},
                    'slots': {'total': slot_count},
                    'slot_values': {'total': slot_value_count},
                    'conversations': {'total': total_conversations, 'last_24h': recent_conversations}
                },
                'audit_stats': {
                    'config_changes': {'total': config_audit_count, 'last_24h': recent_config_changes},
                    'cache_invalidations': {'total': cache_invalidation_count, 'last_24h': recent_cache_invalidations}
                }
            }
            
        except Exception as e:
            self.logger.error(f"获取系统指标失败: {str(e)}")
            return {'error': str(e), 'timestamp': datetime.now().isoformat()}


# 全局健康检查服务实例
_health_check_service: Optional[SystemHealthCheck] = None


def get_health_check_service(cache_service: CacheService) -> SystemHealthCheck:
    """
    获取健康检查服务实例
    
    Args:
        cache_service: 缓存服务实例
        
    Returns:
        SystemHealthCheck: 健康检查服务实例
    """
    global _health_check_service
    if _health_check_service is None:
        _health_check_service = SystemHealthCheck(cache_service)
    
    return _health_check_service