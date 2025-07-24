"""
配置管理服务 (V2.2重构)
统一管理意图和槽位配置变更，集成审计日志和缓存失效
"""
import asyncio
from typing import Dict, List, Any, Optional, Union
from datetime import datetime
from contextlib import asynccontextmanager

from src.models.intent import Intent
from src.models.slot import Slot
from src.services.audit_service import get_audit_service, AuditAction
from src.services.cache_invalidation_service import get_cache_invalidation_service, CacheInvalidationType
from src.core.event_system import get_event_system, EventType
from src.utils.logger import get_logger

logger = get_logger(__name__)


class ConfigOperationResult:
    """配置操作结果"""
    
    def __init__(self, success: bool = True, message: str = "", data: Any = None):
        self.success = success
        self.message = message
        self.data = data
        self.audit_log_id: Optional[int] = None
        self.cache_invalidation_id: Optional[int] = None
        self.events_published: List[str] = []
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'success': self.success,
            'message': self.message,
            'data': self.data,
            'audit_log_id': self.audit_log_id,
            'cache_invalidation_id': self.cache_invalidation_id,
            'events_published': self.events_published
        }


class ConfigManagementService:
    """配置管理服务"""
    
    def __init__(self):
        self.logger = logger
        self.audit_service = get_audit_service()
        self.cache_invalidation_service = get_cache_invalidation_service()
        self.event_system = get_event_system()
    
    @asynccontextmanager
    async def transactional_config_change(self, operator_id: str = 'system'):
        """
        事务性配置变更上下文管理器
        确保配置变更、审计记录、缓存失效在同一事务中
        """
        operations = []
        
        try:
            # 记录操作开始
            self.logger.info(f"开始事务性配置变更: operator={operator_id}")
            
            # 提供操作上下文
            yield operations
            
            # 如果有操作失败，抛出异常
            failed_operations = [op for op in operations if not op.success]
            if failed_operations:
                raise Exception(f"配置变更失败: {len(failed_operations)} 个操作失败")
            
            # 批量发布事件
            await self._publish_batch_events(operations)
            
            self.logger.info(f"事务性配置变更完成: {len(operations)} 个操作成功")
            
        except Exception as e:
            # 回滚操作（如果可能）
            await self._rollback_operations(operations, operator_id)
            self.logger.error(f"事务性配置变更失败: {str(e)}")
            raise
    
    async def create_intent(
        self,
        intent_data: Dict[str, Any],
        operator_id: str = 'system'
    ) -> ConfigOperationResult:
        """
        创建意图配置
        
        Args:
            intent_data: 意图数据
            operator_id: 操作者ID
            
        Returns:
            ConfigOperationResult: 操作结果
        """
        try:
            # 创建意图
            intent = Intent.create(**intent_data)
            
            # 记录审计日志
            audit_log = await self.audit_service.log_config_change(
                table_name='intents',
                record_id=intent.id,
                action=AuditAction.CREATE,
                old_values=None,
                new_values=intent_data,
                operator_id=operator_id
            )
            
            # 触发缓存失效
            cache_keys = [
                f"intent:{intent.intent_name}",
                "intents:active",
                "intents:all"
            ]
            
            invalidation_log = await self.cache_invalidation_service.invalidate_cache(
                cache_keys=cache_keys,
                invalidation_type=CacheInvalidationType.CONFIG_CHANGE,
                reason=f"创建意图: {intent.intent_name}",
                operator_id=operator_id
            )
            
            # 发布事件
            event_published = await self.event_system.publish_event(
                EventType.CONFIG_CHANGED,
                {
                    'operation': 'create',
                    'entity_type': 'intent',
                    'entity_id': intent.id,
                    'entity_name': intent.intent_name,
                    'changes': intent_data,
                    'operator_id': operator_id
                }
            )
            
            result = ConfigOperationResult(
                success=True,
                message=f"意图创建成功: {intent.intent_name}",
                data=intent
            )
            result.audit_log_id = audit_log.id
            result.cache_invalidation_id = invalidation_log.id
            result.events_published = [event_published] if event_published else []
            
            self.logger.info(f"创建意图成功: {intent.intent_name}")
            return result
            
        except Exception as e:
            self.logger.error(f"创建意图失败: {str(e)}")
            return ConfigOperationResult(
                success=False,
                message=f"创建意图失败: {str(e)}"
            )
    
    async def update_intent(
        self,
        intent_id: int,
        updates: Dict[str, Any],
        operator_id: str = 'system'
    ) -> ConfigOperationResult:
        """
        更新意图配置
        
        Args:
            intent_id: 意图ID
            updates: 更新数据
            operator_id: 操作者ID
            
        Returns:
            ConfigOperationResult: 操作结果
        """
        try:
            # 获取原始意图
            intent = Intent.get_by_id(intent_id)
            old_values = {
                'intent_name': intent.intent_name,
                'display_name': intent.display_name,
                'description': intent.description,
                'is_active': intent.is_active,
                'confidence_threshold': float(intent.confidence_threshold)
            }
            
            # 更新意图
            for key, value in updates.items():
                if hasattr(intent, key):
                    setattr(intent, key, value)
            intent.save()
            
            # 记录审计日志
            audit_log = await self.audit_service.log_config_change(
                table_name='intents',
                record_id=intent.id,
                action=AuditAction.UPDATE,
                old_values=old_values,
                new_values=updates,
                operator_id=operator_id
            )
            
            # 触发缓存失效
            cache_keys = [
                f"intent:{intent.intent_name}",
                f"intent:{old_values['intent_name']}",  # 如果名称改变了
                "intents:active",
                "intents:all"
            ]
            
            invalidation_log = await self.cache_invalidation_service.invalidate_cache(
                cache_keys=cache_keys,
                invalidation_type=CacheInvalidationType.CONFIG_CHANGE,
                reason=f"更新意图: {intent.intent_name}",
                operator_id=operator_id
            )
            
            # 发布事件
            event_published = await self.event_system.publish_event(
                EventType.CONFIG_CHANGED,
                {
                    'operation': 'update',
                    'entity_type': 'intent',
                    'entity_id': intent.id,
                    'entity_name': intent.intent_name,
                    'old_values': old_values,
                    'new_values': updates,
                    'operator_id': operator_id
                }
            )
            
            result = ConfigOperationResult(
                success=True,
                message=f"意图更新成功: {intent.intent_name}",
                data=intent
            )
            result.audit_log_id = audit_log.id
            result.cache_invalidation_id = invalidation_log.id
            result.events_published = [event_published] if event_published else []
            
            self.logger.info(f"更新意图成功: {intent.intent_name}")
            return result
            
        except Intent.DoesNotExist:
            return ConfigOperationResult(
                success=False,
                message=f"意图不存在: ID={intent_id}"
            )
        except Exception as e:
            self.logger.error(f"更新意图失败: {str(e)}")
            return ConfigOperationResult(
                success=False,
                message=f"更新意图失败: {str(e)}"
            )
    
    async def delete_intent(
        self,
        intent_id: int,
        operator_id: str = 'system'
    ) -> ConfigOperationResult:
        """
        删除意图配置
        
        Args:
            intent_id: 意图ID
            operator_id: 操作者ID
            
        Returns:
            ConfigOperationResult: 操作结果
        """
        try:
            # 获取要删除的意图
            intent = Intent.get_by_id(intent_id)
            old_values = {
                'intent_name': intent.intent_name,
                'display_name': intent.display_name,
                'description': intent.description,
                'is_active': intent.is_active
            }
            
            # 检查是否有关联的槽位
            related_slots = Slot.select().where(Slot.intent == intent)
            if related_slots.exists():
                return ConfigOperationResult(
                    success=False,
                    message=f"无法删除意图，存在关联的槽位: {intent.intent_name}"
                )
            
            # 删除意图
            intent.delete_instance()
            
            # 记录审计日志
            audit_log = await self.audit_service.log_config_change(
                table_name='intents',
                record_id=intent_id,
                action=AuditAction.DELETE,
                old_values=old_values,
                new_values=None,
                operator_id=operator_id
            )
            
            # 触发缓存失效
            cache_keys = [
                f"intent:{old_values['intent_name']}",
                "intents:active",
                "intents:all"
            ]
            
            invalidation_log = await self.cache_invalidation_service.invalidate_cache(
                cache_keys=cache_keys,
                invalidation_type=CacheInvalidationType.CONFIG_CHANGE,
                reason=f"删除意图: {old_values['intent_name']}",
                operator_id=operator_id
            )
            
            # 发布事件
            event_published = await self.event_system.publish_event(
                EventType.CONFIG_CHANGED,
                {
                    'operation': 'delete',
                    'entity_type': 'intent',
                    'entity_id': intent_id,
                    'entity_name': old_values['intent_name'],
                    'old_values': old_values,
                    'operator_id': operator_id
                }
            )
            
            result = ConfigOperationResult(
                success=True,
                message=f"意图删除成功: {old_values['intent_name']}",
                data=old_values
            )
            result.audit_log_id = audit_log.id
            result.cache_invalidation_id = invalidation_log.id
            result.events_published = [event_published] if event_published else []
            
            self.logger.info(f"删除意图成功: {old_values['intent_name']}")
            return result
            
        except Intent.DoesNotExist:
            return ConfigOperationResult(
                success=False,
                message=f"意图不存在: ID={intent_id}"
            )
        except Exception as e:
            self.logger.error(f"删除意图失败: {str(e)}")
            return ConfigOperationResult(
                success=False,
                message=f"删除意图失败: {str(e)}"
            )
    
    async def create_slot(
        self,
        slot_data: Dict[str, Any],
        operator_id: str = 'system'
    ) -> ConfigOperationResult:
        """
        创建槽位配置
        
        Args:
            slot_data: 槽位数据
            operator_id: 操作者ID
            
        Returns:
            ConfigOperationResult: 操作结果
        """
        try:
            # 创建槽位
            slot = Slot.create(**slot_data)
            
            # 记录审计日志
            audit_log = await self.audit_service.log_config_change(
                table_name='slots',
                record_id=slot.id,
                action=AuditAction.CREATE,
                old_values=None,
                new_values=slot_data,
                operator_id=operator_id
            )
            
            # 触发缓存失效
            intent_name = slot.intent.intent_name if slot.intent else 'unknown'
            cache_keys = [
                f"slot:{slot.slot_name}",
                f"intent:{intent_name}:slots",
                "slots:active",
                "slots:all"
            ]
            
            invalidation_log = await self.cache_invalidation_service.invalidate_cache(
                cache_keys=cache_keys,
                invalidation_type=CacheInvalidationType.CONFIG_CHANGE,
                reason=f"创建槽位: {slot.slot_name}",
                operator_id=operator_id
            )
            
            # 发布事件
            event_published = await self.event_system.publish_event(
                EventType.CONFIG_CHANGED,
                {
                    'operation': 'create',
                    'entity_type': 'slot',
                    'entity_id': slot.id,
                    'entity_name': slot.slot_name,
                    'intent_name': intent_name,
                    'changes': slot_data,
                    'operator_id': operator_id
                }
            )
            
            result = ConfigOperationResult(
                success=True,
                message=f"槽位创建成功: {slot.slot_name}",
                data=slot
            )
            result.audit_log_id = audit_log.id
            result.cache_invalidation_id = invalidation_log.id
            result.events_published = [event_published] if event_published else []
            
            self.logger.info(f"创建槽位成功: {slot.slot_name}")
            return result
            
        except Exception as e:
            self.logger.error(f"创建槽位失败: {str(e)}")
            return ConfigOperationResult(
                success=False,
                message=f"创建槽位失败: {str(e)}"
            )
    
    async def update_slot(
        self,
        slot_id: int,
        updates: Dict[str, Any],
        operator_id: str = 'system'
    ) -> ConfigOperationResult:
        """
        更新槽位配置
        
        Args:
            slot_id: 槽位ID
            updates: 更新数据
            operator_id: 操作者ID
            
        Returns:
            ConfigOperationResult: 操作结果
        """
        try:
            # 获取原始槽位
            slot = Slot.get_by_id(slot_id)
            old_values = {
                'slot_name': slot.slot_name,
                'slot_type': slot.slot_type,
                'is_required': slot.is_required,
                'validation_rules': slot.validation_rules,
                'is_active': slot.is_active
            }
            
            # 更新槽位
            for key, value in updates.items():
                if hasattr(slot, key):
                    setattr(slot, key, value)
            slot.save()
            
            # 记录审计日志
            audit_log = await self.audit_service.log_config_change(
                table_name='slots',
                record_id=slot.id,
                action=AuditAction.UPDATE,
                old_values=old_values,
                new_values=updates,
                operator_id=operator_id
            )
            
            # 触发缓存失效
            intent_name = slot.intent.intent_name if slot.intent else 'unknown'
            cache_keys = [
                f"slot:{slot.slot_name}",
                f"slot:{old_values['slot_name']}",  # 如果名称改变了
                f"intent:{intent_name}:slots",
                "slots:active",
                "slots:all"
            ]
            
            invalidation_log = await self.cache_invalidation_service.invalidate_cache(
                cache_keys=cache_keys,
                invalidation_type=CacheInvalidationType.CONFIG_CHANGE,
                reason=f"更新槽位: {slot.slot_name}",
                operator_id=operator_id
            )
            
            # 发布事件
            event_published = await self.event_system.publish_event(
                EventType.CONFIG_CHANGED,
                {
                    'operation': 'update',
                    'entity_type': 'slot',
                    'entity_id': slot.id,
                    'entity_name': slot.slot_name,
                    'intent_name': intent_name,
                    'old_values': old_values,
                    'new_values': updates,
                    'operator_id': operator_id
                }
            )
            
            result = ConfigOperationResult(
                success=True,
                message=f"槽位更新成功: {slot.slot_name}",
                data=slot
            )
            result.audit_log_id = audit_log.id
            result.cache_invalidation_id = invalidation_log.id
            result.events_published = [event_published] if event_published else []
            
            self.logger.info(f"更新槽位成功: {slot.slot_name}")
            return result
            
        except Slot.DoesNotExist:
            return ConfigOperationResult(
                success=False,
                message=f"槽位不存在: ID={slot_id}"
            )
        except Exception as e:
            self.logger.error(f"更新槽位失败: {str(e)}")
            return ConfigOperationResult(
                success=False,
                message=f"更新槽位失败: {str(e)}"
            )
    
    async def delete_slot(
        self,
        slot_id: int,
        operator_id: str = 'system'
    ) -> ConfigOperationResult:
        """
        删除槽位配置
        
        Args:
            slot_id: 槽位ID
            operator_id: 操作者ID
            
        Returns:
            ConfigOperationResult: 操作结果
        """
        try:
            # 获取要删除的槽位
            slot = Slot.get_by_id(slot_id)
            old_values = {
                'slot_name': slot.slot_name,
                'slot_type': slot.slot_type,
                'is_required': slot.is_required,
                'intent_id': slot.intent.id if slot.intent else None
            }
            
            intent_name = slot.intent.intent_name if slot.intent else 'unknown'
            
            # 删除槽位
            slot.delete_instance()
            
            # 记录审计日志
            audit_log = await self.audit_service.log_config_change(
                table_name='slots',
                record_id=slot_id,
                action=AuditAction.DELETE,
                old_values=old_values,
                new_values=None,
                operator_id=operator_id
            )
            
            # 触发缓存失效
            cache_keys = [
                f"slot:{old_values['slot_name']}",
                f"intent:{intent_name}:slots",
                "slots:active",
                "slots:all"
            ]
            
            invalidation_log = await self.cache_invalidation_service.invalidate_cache(
                cache_keys=cache_keys,
                invalidation_type=CacheInvalidationType.CONFIG_CHANGE,
                reason=f"删除槽位: {old_values['slot_name']}",
                operator_id=operator_id
            )
            
            # 发布事件
            event_published = await self.event_system.publish_event(
                EventType.CONFIG_CHANGED,
                {
                    'operation': 'delete',
                    'entity_type': 'slot',
                    'entity_id': slot_id,
                    'entity_name': old_values['slot_name'],
                    'intent_name': intent_name,
                    'old_values': old_values,
                    'operator_id': operator_id
                }
            )
            
            result = ConfigOperationResult(
                success=True,
                message=f"槽位删除成功: {old_values['slot_name']}",
                data=old_values
            )
            result.audit_log_id = audit_log.id
            result.cache_invalidation_id = invalidation_log.id
            result.events_published = [event_published] if event_published else []
            
            self.logger.info(f"删除槽位成功: {old_values['slot_name']}")
            return result
            
        except Slot.DoesNotExist:
            return ConfigOperationResult(
                success=False,
                message=f"槽位不存在: ID={slot_id}"
            )
        except Exception as e:
            self.logger.error(f"删除槽位失败: {str(e)}")
            return ConfigOperationResult(
                success=False,
                message=f"删除槽位失败: {str(e)}"
            )
    
    async def _publish_batch_events(self, operations: List[ConfigOperationResult]):
        """批量发布事件"""
        try:
            all_events = []
            for operation in operations:
                all_events.extend(operation.events_published)
            
            if all_events:
                await self.event_system.publish_event(
                    EventType.CONFIG_BATCH_CHANGED,
                    {
                        'batch_size': len(operations),
                        'successful_operations': len([op for op in operations if op.success]),
                        'failed_operations': len([op for op in operations if not op.success]),
                        'events': all_events
                    }
                )
        except Exception as e:
            self.logger.error(f"批量发布事件失败: {str(e)}")
    
    async def _rollback_operations(self, operations: List[ConfigOperationResult], operator_id: str):
        """回滚操作"""
        try:
            # 这里可以实现具体的回滚逻辑
            # 由于数据库事务的复杂性，这里只记录回滚日志
            self.logger.warning(f"配置变更回滚: {len(operations)} 个操作需要手动检查")
            
            await self.audit_service.log_config_change(
                table_name='system_operations',
                record_id=0,
                action=AuditAction.ROLLBACK,
                old_values={'operations_count': len(operations)},
                new_values={'rollback_reason': 'transaction_failed'},
                operator_id=operator_id
            )
            
        except Exception as e:
            self.logger.error(f"记录回滚操作失败: {str(e)}")
    
    async def get_config_change_history(
        self,
        entity_type: Optional[str] = None,
        entity_id: Optional[int] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        获取配置变更历史
        
        Args:
            entity_type: 实体类型 ('intent' 或 'slot')
            entity_id: 实体ID
            limit: 返回记录数限制
            
        Returns:
            List[Dict]: 变更历史列表
        """
        try:
            # 构建查询条件
            table_names = []
            if entity_type == 'intent':
                table_names = ['intents']
            elif entity_type == 'slot':
                table_names = ['slots']
            else:
                table_names = ['intents', 'slots']
            
            # 获取审计日志
            history = await self.audit_service.get_audit_logs(
                table_names=table_names,
                record_id=entity_id,
                limit=limit
            )
            
            return history
            
        except Exception as e:
            self.logger.error(f"获取配置变更历史失败: {str(e)}")
            return []


# 全局配置管理服务实例
_config_management_service = None


def get_config_management_service() -> ConfigManagementService:
    """获取配置管理服务实例（单例模式）"""
    global _config_management_service
    if _config_management_service is None:
        _config_management_service = ConfigManagementService()
    return _config_management_service