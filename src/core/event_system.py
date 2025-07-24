"""
事件发布订阅系统 (V2.2重构)
用于配置变更通知和缓存失效的事件驱动架构
"""
import asyncio
from typing import Dict, Any, List, Callable, Optional
from datetime import datetime
from enum import Enum
import json
import uuid
from dataclasses import dataclass, asdict
from abc import ABC, abstractmethod

from src.utils.logger import get_logger

logger = get_logger(__name__)


class EventType(Enum):
    """事件类型枚举"""
    # 配置变更事件
    INTENT_CREATED = "intent.created"
    INTENT_UPDATED = "intent.updated"
    INTENT_DELETED = "intent.deleted"
    
    SLOT_CREATED = "slot.created"
    SLOT_UPDATED = "slot.updated"
    SLOT_DELETED = "slot.deleted"
    
    SYSTEM_CONFIG_UPDATED = "system_config.updated"
    PROMPT_TEMPLATE_UPDATED = "prompt_template.updated"
    FUNCTION_CALL_UPDATED = "function_call.updated"
    
    # 配置管理事件
    CONFIG_CHANGED = "config.changed"
    CONFIG_BATCH_CHANGED = "config.batch_changed"
    
    # 业务事件
    CONVERSATION_STARTED = "conversation.started"
    CONVERSATION_COMPLETED = "conversation.completed"
    SLOT_VALUE_EXTRACTED = "slot_value.extracted"
    INTENT_RECOGNIZED = "intent.recognized"
    
    # 系统事件
    CACHE_INVALIDATION_REQUESTED = "cache.invalidation_requested"
    AUDIT_LOG_CREATED = "audit_log.created"
    SYSTEM_HEALTH_CHECK = "system.health_check"


@dataclass
class Event:
    """事件数据类"""
    event_type: EventType
    event_id: str
    source: str
    data: Dict[str, Any]
    timestamp: datetime
    correlation_id: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            'event_type': self.event_type.value,
            'event_id': self.event_id,
            'source': self.source,
            'data': self.data,
            'timestamp': self.timestamp.isoformat(),
            'correlation_id': self.correlation_id,
            'metadata': self.metadata
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Event':
        """从字典创建事件对象"""
        return cls(
            event_type=EventType(data['event_type']),
            event_id=data['event_id'],
            source=data['source'],
            data=data['data'],
            timestamp=datetime.fromisoformat(data['timestamp']),
            correlation_id=data.get('correlation_id'),
            metadata=data.get('metadata', {})
        )


class EventHandler(ABC):
    """事件处理器基类"""
    
    @abstractmethod
    async def handle(self, event: Event) -> bool:
        """
        处理事件
        
        Args:
            event: 事件对象
            
        Returns:
            bool: 处理是否成功
        """
        pass
    
    @property
    @abstractmethod
    def supported_events(self) -> List[EventType]:
        """支持的事件类型"""
        pass
    
    @property
    def handler_name(self) -> str:
        """处理器名称"""
        return self.__class__.__name__


class CacheInvalidationHandler(EventHandler):
    """缓存失效事件处理器"""
    
    def __init__(self, cache_invalidation_service):
        self.cache_invalidation_service = cache_invalidation_service
        self.logger = logger.getChild(self.handler_name)
    
    @property
    def supported_events(self) -> List[EventType]:
        return [
            EventType.INTENT_CREATED,
            EventType.INTENT_UPDATED,
            EventType.INTENT_DELETED,
            EventType.SLOT_CREATED,
            EventType.SLOT_UPDATED,
            EventType.SLOT_DELETED,
            EventType.SYSTEM_CONFIG_UPDATED,
            EventType.PROMPT_TEMPLATE_UPDATED,
            EventType.FUNCTION_CALL_UPDATED,
            EventType.CACHE_INVALIDATION_REQUESTED
        ]
    
    async def handle(self, event: Event) -> bool:
        """处理缓存失效事件"""
        try:
            if event.event_type == EventType.CACHE_INVALIDATION_REQUESTED:
                # 直接处理缓存失效请求
                pattern = event.data.get('pattern')
                if pattern:
                    await self.cache_invalidation_service.invalidate_by_pattern(
                        pattern, 
                        reason=event.data.get('reason', 'event_triggered')
                    )
                else:
                    cache_keys = event.data.get('cache_keys', [])
                    for key in cache_keys:
                        await self.cache_invalidation_service.cache_service.delete(key)
                
            elif event.event_type in [EventType.INTENT_CREATED, EventType.INTENT_UPDATED, EventType.INTENT_DELETED]:
                # 处理意图相关的缓存失效
                intent_id = event.data.get('intent_id')
                intent_name = event.data.get('intent_name')
                
                if intent_id:
                    await self.cache_invalidation_service.invalidate_intent_cache(
                        intent_id=intent_id,
                        intent_name=intent_name,
                        operation_type=event.event_type.value.split('.')[1].upper()
                    )
            
            elif event.event_type in [EventType.SLOT_CREATED, EventType.SLOT_UPDATED, EventType.SLOT_DELETED]:
                # 处理槽位相关的缓存失效
                slot_id = event.data.get('slot_id')
                intent_id = event.data.get('intent_id')
                
                if slot_id and intent_id:
                    await self.cache_invalidation_service.invalidate_slot_cache(
                        slot_id=slot_id,
                        intent_id=intent_id,
                        operation_type=event.event_type.value.split('.')[1].upper()
                    )
            
            elif event.event_type == EventType.SYSTEM_CONFIG_UPDATED:
                # 处理系统配置相关的缓存失效
                config_id = event.data.get('config_id')
                category = event.data.get('category')
                key = event.data.get('key')
                
                if config_id:
                    await self.cache_invalidation_service.invalidate_system_config_cache(
                        config_id=config_id,
                        category=category,
                        key=key
                    )
            
            self.logger.debug(f"缓存失效事件处理成功: {event.event_type.value}")
            return True
            
        except Exception as e:
            self.logger.error(f"缓存失效事件处理失败: {event.event_type.value}, 错误: {str(e)}")
            return False


class AuditLogHandler(EventHandler):
    """审计日志事件处理器"""
    
    def __init__(self, audit_service):
        self.audit_service = audit_service
        self.logger = logger.getChild(self.handler_name)
    
    @property
    def supported_events(self) -> List[EventType]:
        return [
            EventType.INTENT_CREATED,
            EventType.INTENT_UPDATED,
            EventType.INTENT_DELETED,
            EventType.SLOT_CREATED,
            EventType.SLOT_UPDATED,
            EventType.SLOT_DELETED,
            EventType.SYSTEM_CONFIG_UPDATED,
            EventType.PROMPT_TEMPLATE_UPDATED,
            EventType.FUNCTION_CALL_UPDATED
        ]
    
    async def handle(self, event: Event) -> bool:
        """处理审计日志事件"""
        try:
            # 解析事件类型和操作
            event_parts = event.event_type.value.split('.')
            table_name = event_parts[0] + 's'  # intent -> intents
            action = event_parts[1].upper()
            
            # 获取记录ID和数据
            record_id = event.data.get('id') or event.data.get(f'{event_parts[0]}_id')
            old_values = event.data.get('old_values')
            new_values = event.data.get('new_values')
            operator_id = event.metadata.get('operator_id', 'system')
            
            if record_id:
                await self.audit_service.log_config_change(
                    table_name=table_name,
                    record_id=record_id,
                    action=getattr(self.audit_service.AuditAction, action, self.audit_service.AuditAction.UPDATE),
                    old_values=old_values,
                    new_values=new_values,
                    operator_id=operator_id
                )
            
            self.logger.debug(f"审计日志事件处理成功: {event.event_type.value}")
            return True
            
        except Exception as e:
            self.logger.error(f"审计日志事件处理失败: {event.event_type.value}, 错误: {str(e)}")
            return False


class EventBus:
    """事件总线"""
    
    def __init__(self):
        self.handlers: Dict[EventType, List[EventHandler]] = {}
        self.event_queue = asyncio.Queue()
        self.is_running = False
        self.worker_task: Optional[asyncio.Task] = None
        self.logger = logger.getChild(self.__class__.__name__)
        
        # 统计信息
        self.stats = {
            'events_published': 0,
            'events_processed': 0,
            'events_failed': 0,
            'handlers_registered': 0
        }
    
    def register_handler(self, handler: EventHandler):
        """注册事件处理器"""
        for event_type in handler.supported_events:
            if event_type not in self.handlers:
                self.handlers[event_type] = []
            self.handlers[event_type].append(handler)
            
        self.stats['handlers_registered'] += 1
        self.logger.info(f"注册事件处理器: {handler.handler_name}")
    
    def unregister_handler(self, handler: EventHandler):
        """注销事件处理器"""
        for event_type in handler.supported_events:
            if event_type in self.handlers and handler in self.handlers[event_type]:
                self.handlers[event_type].remove(handler)
                
        self.logger.info(f"注销事件处理器: {handler.handler_name}")
    
    async def publish(self, event: Event):
        """发布事件"""
        try:
            await self.event_queue.put(event)
            self.stats['events_published'] += 1
            
            self.logger.debug(
                f"事件发布成功: {event.event_type.value}, "
                f"ID: {event.event_id}, "
                f"队列大小: {self.event_queue.qsize()}"
            )
            
        except Exception as e:
            self.logger.error(f"事件发布失败: {event.event_type.value}, 错误: {str(e)}")
            raise
    
    async def publish_config_change(
        self,
        table_name: str,
        record_id: int,
        action: str,
        old_values: Optional[Dict[str, Any]] = None,
        new_values: Optional[Dict[str, Any]] = None,
        operator_id: str = "system"
    ):
        """发布配置变更事件"""
        # 根据表名和操作构造事件类型
        event_type_map = {
            'intents': {
                'created': EventType.INTENT_CREATED,
                'updated': EventType.INTENT_UPDATED,
                'deleted': EventType.INTENT_DELETED
            },
            'slots': {
                'created': EventType.SLOT_CREATED,
                'updated': EventType.SLOT_UPDATED,
                'deleted': EventType.SLOT_DELETED
            },
            'system_configs': {
                'updated': EventType.SYSTEM_CONFIG_UPDATED
            }
        }
        
        action_lower = action.lower()
        if table_name in event_type_map and action_lower in event_type_map[table_name]:
            event_type = event_type_map[table_name][action_lower]
            
            event = Event(
                event_type=event_type,
                event_id=str(uuid.uuid4()),
                source=f"{table_name}.service",
                data={
                    'id': record_id,
                    'old_values': old_values,
                    'new_values': new_values,
                    'table_name': table_name,
                    'action': action
                },
                timestamp=datetime.now(),
                metadata={'operator_id': operator_id}
            )
            
            await self.publish(event)
    
    async def publish_event(
        self,
        event_type: EventType,
        data: Dict[str, Any],
        source: str = "system",
        correlation_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        发布事件（兼容性方法）
        
        Args:
            event_type: 事件类型
            data: 事件数据
            source: 事件源
            correlation_id: 关联ID
            metadata: 元数据
            
        Returns:
            str: 事件ID
        """
        event = Event(
            event_type=event_type,
            event_id=str(uuid.uuid4()),
            source=source,
            data=data,
            timestamp=datetime.now(),
            correlation_id=correlation_id,
            metadata=metadata or {}
        )
        
        await self.publish(event)
        return event.event_id
    
    async def start(self):
        """启动事件总线"""
        if self.is_running:
            self.logger.warning("事件总线已在运行中")
            return
        
        self.is_running = True
        self.worker_task = asyncio.create_task(self._process_events())
        self.logger.info("事件总线启动成功")
    
    async def stop(self):
        """停止事件总线"""
        if not self.is_running:
            return
        
        self.is_running = False
        
        if self.worker_task:
            self.worker_task.cancel()
            try:
                await self.worker_task
            except asyncio.CancelledError:
                pass
        
        # 处理队列中剩余的事件
        while not self.event_queue.empty():
            try:
                event = self.event_queue.get_nowait()
                await self._handle_event(event)
            except asyncio.QueueEmpty:
                break
            except Exception as e:
                self.logger.error(f"处理剩余事件失败: {str(e)}")
        
        self.logger.info("事件总线停止成功")
    
    async def _process_events(self):
        """处理事件的工作循环"""
        while self.is_running:
            try:
                # 等待事件，设置超时避免无限等待
                event = await asyncio.wait_for(self.event_queue.get(), timeout=1.0)
                await self._handle_event(event)
                
            except asyncio.TimeoutError:
                # 超时是正常的，继续循环
                continue
            except asyncio.CancelledError:
                # 任务被取消
                break
            except Exception as e:
                self.logger.error(f"处理事件循环异常: {str(e)}")
                await asyncio.sleep(0.1)  # 短暂休眠避免高频错误
    
    async def _handle_event(self, event: Event):
        """处理单个事件"""
        try:
            handlers = self.handlers.get(event.event_type, [])
            
            if not handlers:
                self.logger.debug(f"没有处理器处理事件: {event.event_type.value}")
                return
            
            # 并行处理所有处理器
            tasks = [handler.handle(event) for handler in handlers]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # 统计处理结果
            success_count = 0
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    self.logger.error(
                        f"事件处理器异常: {handlers[i].handler_name}, "
                        f"事件: {event.event_type.value}, "
                        f"错误: {str(result)}"
                    )
                elif result:
                    success_count += 1
            
            if success_count > 0:
                self.stats['events_processed'] += 1
            else:
                self.stats['events_failed'] += 1
            
            self.logger.debug(
                f"事件处理完成: {event.event_type.value}, "
                f"成功: {success_count}/{len(handlers)}"
            )
            
        except Exception as e:
            self.stats['events_failed'] += 1
            self.logger.error(f"处理事件异常: {event.event_type.value}, 错误: {str(e)}")
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        return {
            **self.stats,
            'queue_size': self.event_queue.qsize(),
            'is_running': self.is_running,
            'registered_event_types': list(self.handlers.keys()),
            'handler_count': sum(len(handlers) for handlers in self.handlers.values())
        }


# 全局事件总线实例
_event_bus = None


def get_event_bus() -> EventBus:
    """获取事件总线实例（单例模式）"""
    global _event_bus
    if _event_bus is None:
        _event_bus = EventBus()
    return _event_bus


def get_event_system() -> EventBus:
    """获取事件系统实例（别名，兼容性）"""
    return get_event_bus()


async def initialize_event_system(
    audit_service=None,
    cache_invalidation_service=None
):
    """初始化事件系统"""
    event_bus = get_event_bus()
    
    # 注册默认处理器
    if audit_service:
        audit_handler = AuditLogHandler(audit_service)
        event_bus.register_handler(audit_handler)
    
    if cache_invalidation_service:
        cache_handler = CacheInvalidationHandler(cache_invalidation_service)
        event_bus.register_handler(cache_handler)
    
    # 启动事件总线
    await event_bus.start()
    
    logger.info("事件系统初始化完成")


async def shutdown_event_system():
    """关闭事件系统"""
    global _event_bus
    if _event_bus:
        await _event_bus.stop()
        _event_bus = None
    
    logger.info("事件系统关闭完成")