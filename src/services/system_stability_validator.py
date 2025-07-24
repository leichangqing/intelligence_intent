"""
系统稳定性验证器 (V2.2重构)
对重构后的系统进行全面的稳定性验证和测试
"""
from typing import Dict, List, Any, Optional, Tuple
import asyncio
import time
import random
from datetime import datetime, timedelta

from src.models.intent import Intent
from src.models.slot import Slot
from src.models.conversation import Conversation
from src.models.audit import ConfigAuditLog
from src.services.health_check_service import SystemHealthCheck, HealthStatus
from src.services.monitoring_service import MonitoringService, AlertLevel
from src.services.service_factory import get_enhanced_intent_service, get_enhanced_slot_service
from src.services.cache_service import CacheService
from src.utils.logger import get_logger

logger = get_logger(__name__)


class StabilityTest:
    """稳定性测试"""
    
    def __init__(self, name: str, description: str):
        self.name = name
        self.description = description
        self.start_time: Optional[datetime] = None
        self.end_time: Optional[datetime] = None
        self.status = "pending"
        self.results: Dict[str, Any] = {}
        self.errors: List[str] = []
    
    def start(self):
        """开始测试"""
        self.start_time = datetime.now()
        self.status = "running"
        logger.info(f"开始稳定性测试: {self.name}")
    
    def complete(self, success: bool, results: Dict[str, Any] = None):
        """完成测试"""
        self.end_time = datetime.now()
        self.status = "completed" if success else "failed"
        self.results = results or {}
        
        duration = (self.end_time - self.start_time).total_seconds() if self.start_time else 0
        logger.info(f"稳定性测试完成: {self.name}, 状态: {self.status}, 耗时: {duration:.2f}s")
    
    def add_error(self, error: str):
        """添加错误"""
        self.errors.append(error)
        logger.error(f"稳定性测试错误 [{self.name}]: {error}")
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'name': self.name,
            'description': self.description,
            'status': self.status,
            'start_time': self.start_time.isoformat() if self.start_time else None,
            'end_time': self.end_time.isoformat() if self.end_time else None,
            'duration_seconds': (self.end_time - self.start_time).total_seconds() if self.start_time and self.end_time else 0,
            'results': self.results,
            'errors': self.errors
        }


class SystemStabilityValidator:
    """系统稳定性验证器"""
    
    def __init__(self, cache_service: CacheService, health_check_service: SystemHealthCheck, 
                 monitoring_service: Optional[MonitoringService] = None):
        self.cache_service = cache_service
        self.health_check_service = health_check_service
        self.monitoring_service = monitoring_service
        self.logger = logger
    
    async def run_full_stability_validation(self) -> Dict[str, Any]:
        """
        运行完整的系统稳定性验证
        
        Returns:
            Dict[str, Any]: 验证结果报告
        """
        start_time = datetime.now()
        
        try:
            logger.info("开始系统稳定性验证")
            
            # 定义所有测试
            tests = [
                self._test_database_stability(),
                self._test_cache_stability(),
                self._test_audit_system_stability(),
                self._test_service_integration(),
                self._test_data_consistency(),
                self._test_performance_under_load(),
                self._test_error_handling(),
                self._test_v22_migration_integrity()
            ]
            
            # 并发执行测试
            test_results = await asyncio.gather(*tests, return_exceptions=True)
            
            # 处理测试结果
            completed_tests = []
            for i, result in enumerate(test_results):
                if isinstance(result, Exception):
                    error_test = StabilityTest(f"test_{i}", "Test execution failed")
                    error_test.start()
                    error_test.add_error(str(result))
                    error_test.complete(False)
                    completed_tests.append(error_test)
                else:
                    completed_tests.append(result)
            
            # 生成报告
            report = self._generate_validation_report(completed_tests, start_time)
            
            # 记录验证结果
            if self.monitoring_service:
                await self._record_validation_metrics(report)
            
            logger.info(f"系统稳定性验证完成: {report['summary']['success_rate']:.1f}% 成功率")
            return report
            
        except Exception as e:
            logger.error(f"系统稳定性验证失败: {str(e)}")
            return {
                'overall_status': 'failed',
                'error': str(e),
                'timestamp': start_time.isoformat(),
                'execution_time_seconds': (datetime.now() - start_time).total_seconds()
            }
    
    async def _test_database_stability(self) -> StabilityTest:
        """测试数据库稳定性"""
        test = StabilityTest("database_stability", "数据库连接和查询稳定性测试")
        test.start()
        
        try:
            results = {}
            
            # 测试基本查询
            intents = list(Intent.select().limit(10))
            results['intent_query'] = len(intents)
            
            # 测试写入操作（创建测试记录）
            test_log = ConfigAuditLog.create(
                table_name_field="stability_test",
                record_id=0,
                action="INSERT",
                old_values=None,
                new_values='{"test": true}',
                operator_id="stability_validator"
            )
            results['write_operation'] = True
            
            # 清理测试记录
            test_log.delete_instance()
            
            # 测试事务
            with database.transaction():
                test_conversation = Conversation.create(
                    session_id="stability_test",
                    user_id="test",
                    conversation_turn=1,
                    user_input="test input",
                    user_input_type="text"
                )
                conversation_id = test_conversation.id
                # 立即删除
                test_conversation.delete_instance()
            
            results['transaction_test'] = True
            
            test.complete(True, results)
            
        except Exception as e:
            test.add_error(str(e))
            test.complete(False)
        
        return test
    
    async def _test_cache_stability(self) -> StabilityTest:
        """测试缓存系统稳定性"""
        test = StabilityTest("cache_stability", "缓存系统读写和失效稳定性测试")
        test.start()
        
        try:
            results = {}
            
            # 测试缓存写入和读取
            test_keys = []
            for i in range(10):
                key = f"stability_test_{i}_{int(time.time())}"
                value = {"test_data": f"value_{i}", "timestamp": datetime.now().isoformat()}
                
                # 写入
                await self.cache_service.set(key, value, ttl=300)
                test_keys.append(key)
                
                # 读取验证
                cached_value = await self.cache_service.get(key)
                if cached_value != value:
                    raise Exception(f"Cache read/write mismatch for key {key}")
            
            results['cache_operations'] = len(test_keys)
            
            # 测试批量删除
            for key in test_keys:
                await self.cache_service.delete(key)
            
            # 验证删除
            for key in test_keys:
                cached_value = await self.cache_service.get(key)
                if cached_value is not None:
                    raise Exception(f"Cache key {key} not properly deleted")
            
            results['delete_operations'] = len(test_keys)
            
            test.complete(True, results)
            
        except Exception as e:
            test.add_error(str(e))
            test.complete(False)
        
        return test
    
    async def _test_audit_system_stability(self) -> StabilityTest:
        """测试审计系统稳定性"""
        test = StabilityTest("audit_system_stability", "审计日志系统稳定性和性能测试")
        test.start()
        
        try:
            from src.services.audit_service import AuditService, AuditAction
            
            audit_service = AuditService()
            results = {}
            
            # 测试批量审计日志写入
            batch_size = 50
            successful_writes = 0
            
            for i in range(batch_size):
                try:
                    await audit_service.log_config_change(
                        table_name=f"stability_test_{i % 5}",
                        record_id=i,
                        action=AuditAction.UPDATE,
                        old_values={"test": f"old_value_{i}"},
                        new_values={"test": f"new_value_{i}"},
                        operator_id="stability_validator"
                    )
                    successful_writes += 1
                except Exception as e:
                    test.add_error(f"Audit write {i} failed: {str(e)}")
            
            results['batch_writes'] = successful_writes
            results['success_rate'] = successful_writes / batch_size
            
            # 测试审计日志查询性能
            query_start = time.time()
            recent_logs = list(
                ConfigAuditLog.select()
                .where(ConfigAuditLog.operator_id == "stability_validator")
                .order_by(ConfigAuditLog.created_at.desc())
                .limit(10)
            )
            query_time = (time.time() - query_start) * 1000
            
            results['query_time_ms'] = query_time
            results['queried_logs'] = len(recent_logs)
            
            # 清理测试日志
            cleanup_count = ConfigAuditLog.delete().where(
                ConfigAuditLog.operator_id == "stability_validator"
            ).execute()
            
            results['cleaned_logs'] = cleanup_count
            
            test.complete(True, results)
            
        except Exception as e:
            test.add_error(str(e))
            test.complete(False)
        
        return test
    
    async def _test_service_integration(self) -> StabilityTest:
        """测试服务集成稳定性"""
        test = StabilityTest("service_integration", "增强服务集成和CRUD操作测试")
        test.start()
        
        try:
            results = {}
            
            # 测试意图服务
            intent_service = get_enhanced_intent_service()
            
            # 创建测试意图
            test_intent_data = {
                'intent_name': f'stability_test_{int(time.time())}',
                'display_name': 'Stability Test Intent',
                'description': 'Test intent for stability validation',
                'is_active': True,
                'priority': 1,
                'confidence_threshold': 0.8
            }
            
            created_intent = await intent_service.create_intent(
                test_intent_data, "stability_validator"
            )
            
            if created_intent:
                results['intent_create'] = True
                
                # 更新意图
                update_result = await intent_service.update_intent(
                    created_intent.id, 
                    {'description': 'Updated description for stability test'},
                    "stability_validator"
                )
                results['intent_update'] = update_result
                
                # 测试槽位服务
                slot_service = await get_enhanced_slot_service()
                
                # 创建测试槽位
                test_slot_data = {
                    'slot_name': 'test_slot',
                    'display_name': 'Test Slot',
                    'description': 'Test slot for stability validation',
                    'slot_type': 'TEXT',
                    'is_required': True
                }
                
                created_slot = await slot_service.create_slot(
                    created_intent.id, test_slot_data, "stability_validator"
                )
                
                if created_slot:
                    results['slot_create'] = True
                    
                    # 删除测试槽位
                    slot_delete_result = await slot_service.delete_slot(
                        created_slot.id, "stability_validator"
                    )
                    results['slot_delete'] = slot_delete_result
                
                # 删除测试意图
                intent_delete_result = await intent_service.delete_intent(
                    created_intent.id, "stability_validator"
                )
                results['intent_delete'] = intent_delete_result
            
            else:
                results['intent_create'] = False
                test.add_error("Failed to create test intent")
            
            test.complete(True, results)
            
        except Exception as e:
            test.add_error(str(e))
            test.complete(False)
        
        return test
    
    async def _test_data_consistency(self) -> StabilityTest:
        """测试数据一致性"""
        test = StabilityTest("data_consistency", "V2.2数据结构一致性验证")
        test.start()
        
        try:
            results = {}
            
            # 检查槽位值与对话的一致性
            from src.models.slot_value import SlotValue
            
            orphaned_slots = SlotValue.select().where(
                SlotValue.conversation_id.is_null(False),
                ~SlotValue.conversation_id.in_(
                    Conversation.select(Conversation.id)
                )
            ).count()
            
            results['orphaned_slot_values'] = orphaned_slots
            
            # 检查未迁移的JSON槽位数据
            conversations_with_json = Conversation.select().where(
                (Conversation.slots_filled.is_null(False)) |
                (Conversation.slots_missing.is_null(False))
            ).count()
            
            results['unmigrated_conversations'] = conversations_with_json
            
            # 检查审计日志的数据完整性
            invalid_audit_logs = ConfigAuditLog.select().where(
                (ConfigAuditLog.table_name_field.is_null()) |
                (ConfigAuditLog.action.is_null()) |
                (ConfigAuditLog.operator_id.is_null())
            ).count()
            
            results['invalid_audit_logs'] = invalid_audit_logs
            
            # 评估一致性状态
            consistency_issues = []
            if orphaned_slots > 0:
                consistency_issues.append(f"{orphaned_slots} orphaned slot values")
            if conversations_with_json > 0:
                consistency_issues.append(f"{conversations_with_json} unmigrated conversations")
            if invalid_audit_logs > 0:
                consistency_issues.append(f"{invalid_audit_logs} invalid audit logs")
            
            results['consistency_issues'] = consistency_issues
            results['is_consistent'] = len(consistency_issues) == 0
            
            if consistency_issues:
                test.add_error(f"Data consistency issues found: {'; '.join(consistency_issues)}")
            
            test.complete(len(consistency_issues) == 0, results)
            
        except Exception as e:
            test.add_error(str(e))
            test.complete(False)
        
        return test
    
    async def _test_performance_under_load(self) -> StabilityTest:
        """测试负载下的性能"""
        test = StabilityTest("performance_load", "系统负载性能测试")
        test.start()
        
        try:
            results = {}
            
            # 并发缓存操作测试
            concurrent_operations = 20
            operation_tasks = []
            
            for i in range(concurrent_operations):
                task = self._perform_cache_operations(i)
                operation_tasks.append(task)
            
            # 执行并发操作
            operation_start = time.time()
            operation_results = await asyncio.gather(*operation_tasks, return_exceptions=True)
            operation_duration = (time.time() - operation_start) * 1000
            
            # 分析结果
            successful_operations = sum(1 for r in operation_results if r and not isinstance(r, Exception))
            failed_operations = len(operation_results) - successful_operations
            
            results['concurrent_operations'] = concurrent_operations
            results['successful_operations'] = successful_operations
            results['failed_operations'] = failed_operations
            results['total_duration_ms'] = operation_duration
            results['avg_operation_time_ms'] = operation_duration / concurrent_operations
            
            # 性能阈值检查
            if operation_duration > 5000:  # 5秒阈值
                test.add_error(f"Load test took too long: {operation_duration:.1f}ms")
            
            if failed_operations > concurrent_operations * 0.1:  # 10%失败率阈值
                test.add_error(f"High failure rate under load: {failed_operations}/{concurrent_operations}")
            
            test.complete(failed_operations == 0 and operation_duration <= 5000, results)
            
        except Exception as e:
            test.add_error(str(e))
            test.complete(False)
        
        return test
    
    async def _perform_cache_operations(self, operation_id: int) -> bool:
        """执行缓存操作"""
        try:
            # 随机操作模拟真实负载
            operations = ['set', 'get', 'delete'] * 3  # 偏向读写操作
            random.shuffle(operations)
            
            test_key = f"load_test_{operation_id}"
            test_value = {"id": operation_id, "timestamp": datetime.now().isoformat()}
            
            for op in operations[:5]:  # 每个任务执行5个操作
                if op == 'set':
                    await self.cache_service.set(test_key, test_value, ttl=60)
                elif op == 'get':
                    await self.cache_service.get(test_key)
                elif op == 'delete':
                    await self.cache_service.delete(test_key)
                
                # 短暂延迟模拟真实使用
                await asyncio.sleep(0.01)
            
            return True
            
        except Exception as e:
            logger.warning(f"Load test operation {operation_id} failed: {str(e)}")
            return False
    
    async def _test_error_handling(self) -> StabilityTest:
        """测试错误处理"""
        test = StabilityTest("error_handling", "系统错误处理和恢复能力测试")
        test.start()
        
        try:
            results = {}
            
            # 测试无效数据处理
            intent_service = get_enhanced_intent_service()
            
            # 尝试创建无效意图（缺少必需字段）
            invalid_intent = await intent_service.create_intent(
                {'invalid': 'data'}, "stability_validator"
            )
            
            results['invalid_intent_handled'] = invalid_intent is None
            
            # 测试不存在资源的操作
            nonexistent_update = await intent_service.update_intent(
                99999, {'description': 'test'}, "stability_validator"
            )
            
            results['nonexistent_update_handled'] = not nonexistent_update
            
            # 测试缓存异常处理
            try:
                # 尝试操作可能不存在的键
                await self.cache_service.get("nonexistent_key_stability_test")
                results['cache_get_nonexistent'] = True
            except Exception:
                results['cache_get_nonexistent'] = False
            
            # 测试数据库连接恢复（模拟）
            try:
                # 执行一个简单查询来测试连接状态
                Intent.select().limit(1).execute()
                results['db_connection_stable'] = True
            except Exception as e:
                test.add_error(f"Database connection test failed: {str(e)}")
                results['db_connection_stable'] = False
            
            test.complete(True, results)
            
        except Exception as e:
            test.add_error(str(e))
            test.complete(False)
        
        return test
    
    async def _test_v22_migration_integrity(self) -> StabilityTest:
        """测试V2.2迁移完整性"""
        test = StabilityTest("v22_migration_integrity", "V2.2迁移后的数据完整性验证")
        test.start()
        
        try:
            from src.models.slot_value import SlotValue
            
            results = {}
            
            # 检查迁移标记的数据
            migrated_from_v21 = SlotValue.select().where(
                SlotValue.extracted_from == 'migration_v21'
            ).count()
            
            session_migrated = SlotValue.select().where(
                SlotValue.extracted_from == 'session_migration'
            ).count()
            
            results['migrated_from_v21'] = migrated_from_v21
            results['session_migrated'] = session_migrated
            
            # 检查备份表
            try:
                backup_count = database.execute_sql(
                    "SELECT COUNT(*) as count FROM _backup_conversations_v21"
                ).fetchone()
                results['backup_records'] = backup_count[0] if backup_count else 0
            except Exception as e:
                results['backup_records'] = 0
                test.add_error(f"Backup table check failed: {str(e)}")
            
            # 检查V2.2升级记录
            upgrade_logs = ConfigAuditLog.select().where(
                ConfigAuditLog.table_name_field == 'system_upgrade'
            ).count()
            
            results['upgrade_logs'] = upgrade_logs
            
            # 检查新的数据类型（record_id应该是BIGINT）
            try:
                large_record_id_logs = ConfigAuditLog.select().where(
                    ConfigAuditLog.record_id > 2147483647  # 超过INT最大值
                ).count()
                results['supports_large_record_ids'] = True
            except Exception:
                results['supports_large_record_ids'] = False
            
            # 验证迁移完整性
            migration_complete = (
                migrated_from_v21 > 0 or session_migrated > 0
            ) and upgrade_logs > 0
            
            results['migration_appears_complete'] = migration_complete
            
            if not migration_complete:
                test.add_error("V2.2 migration does not appear to be complete")
            
            test.complete(migration_complete, results)
            
        except Exception as e:
            test.add_error(str(e))
            test.complete(False)
        
        return test
    
    def _generate_validation_report(self, tests: List[StabilityTest], 
                                  start_time: datetime) -> Dict[str, Any]:
        """生成验证报告"""
        end_time = datetime.now()
        execution_time = (end_time - start_time).total_seconds()
        
        # 统计测试结果
        total_tests = len(tests)
        passed_tests = sum(1 for test in tests if test.status == "completed")
        failed_tests = sum(1 for test in tests if test.status == "failed")
        
        # 收集所有错误
        all_errors = []
        for test in tests:
            for error in test.errors:
                all_errors.append(f"[{test.name}] {error}")
        
        # 确定整体状态
        if failed_tests == 0:
            overall_status = "stable"
        elif failed_tests <= total_tests * 0.2:  # 20%失败率以下
            overall_status = "mostly_stable"
        else:
            overall_status = "unstable"
        
        return {
            'overall_status': overall_status,
            'execution_time_seconds': execution_time,
            'timestamp': start_time.isoformat(),
            'summary': {
                'total_tests': total_tests,
                'passed_tests': passed_tests,
                'failed_tests': failed_tests,
                'success_rate': (passed_tests / total_tests * 100) if total_tests > 0 else 0,
                'total_errors': len(all_errors)
            },
            'test_results': [test.to_dict() for test in tests],
            'errors': all_errors,
            'recommendations': self._generate_recommendations(tests)
        }
    
    def _generate_recommendations(self, tests: List[StabilityTest]) -> List[str]:
        """生成改进建议"""
        recommendations = []
        
        # 基于测试结果生成建议
        for test in tests:
            if test.status == "failed":
                if test.name == "database_stability":
                    recommendations.append("检查数据库连接配置和性能优化")
                elif test.name == "cache_stability":
                    recommendations.append("检查缓存服务配置和内存使用情况")
                elif test.name == "data_consistency":
                    recommendations.append("运行数据修复脚本修复一致性问题")
                elif test.name == "performance_load":
                    recommendations.append("考虑增加系统资源或优化性能瓶颈")
                elif test.name == "v22_migration_integrity":
                    recommendations.append("检查V2.2迁移脚本执行情况，可能需要重新运行")
        
        # 通用建议
        failed_count = sum(1 for test in tests if test.status == "failed")
        if failed_count > 0:
            recommendations.append("建议在修复问题后重新运行稳定性验证")
            recommendations.append("监控系统日志以获取更详细的错误信息")
        
        return recommendations
    
    async def _record_validation_metrics(self, report: Dict[str, Any]):
        """记录验证指标到监控服务"""
        try:
            if not self.monitoring_service:
                return
            
            from src.services.monitoring_service import MetricType
            
            # 记录整体稳定性指标
            stability_score = 1.0 if report['overall_status'] == 'stable' else 0.0
            self.monitoring_service.record_metric(
                'system_stability_score',
                MetricType.GAUGE,
                stability_score
            )
            
            # 记录测试通过率
            success_rate = report['summary']['success_rate']
            self.monitoring_service.record_metric(
                'stability_test_success_rate',
                MetricType.GAUGE,
                success_rate
            )
            
            # 记录执行时间
            execution_time = report['execution_time_seconds']
            self.monitoring_service.record_metric(
                'stability_validation_duration',
                MetricType.TIMER,
                execution_time * 1000  # 转换为毫秒
            )
            
            # 如果有问题，创建告警
            if report['overall_status'] != 'stable':
                from src.services.monitoring_service import Alert, AlertLevel
                
                level = AlertLevel.CRITICAL if report['overall_status'] == 'unstable' else AlertLevel.WARNING
                
                alert = Alert(
                    level=level,
                    title="System Stability Issues Detected",
                    message=f"Stability validation found issues: {report['summary']['failed_tests']} failed tests",
                    source="stability_validator",
                    details=report['summary']
                )
                
                await self.monitoring_service._create_alert(
                    level, alert.title, alert.message, alert.source, alert.details
                )
            
        except Exception as e:
            logger.warning(f"记录验证指标失败: {str(e)}")


# 全局稳定性验证器实例
_stability_validator: Optional[SystemStabilityValidator] = None


def get_stability_validator(cache_service: CacheService, 
                          health_check_service: SystemHealthCheck,
                          monitoring_service: Optional[MonitoringService] = None) -> SystemStabilityValidator:
    """
    获取系统稳定性验证器实例
    
    Args:
        cache_service: 缓存服务实例
        health_check_service: 健康检查服务实例
        monitoring_service: 监控服务实例（可选）
        
    Returns:
        SystemStabilityValidator: 稳定性验证器实例
    """
    global _stability_validator
    if _stability_validator is None:
        _stability_validator = SystemStabilityValidator(
            cache_service, health_check_service, monitoring_service
        )
    
    return _stability_validator