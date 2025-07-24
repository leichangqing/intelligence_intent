"""
缓存失效管理服务 (V2.2重构)
实现基于事件的缓存清理机制，替代原数据库触发器
"""
from typing import Dict, Any, Optional, List, Set
import json
from datetime import datetime
from enum import Enum

from src.models.audit import CacheInvalidationLog
from src.services.cache_service import CacheService
from src.utils.logger import get_logger

logger = get_logger(__name__)


class CacheInvalidationType(Enum):
    """缓存失效类型"""
    CONFIG_CHANGE = "config_change"
    DATA_UPDATE = "data_update"
    SYSTEM_REFRESH = "system_refresh"
    MANUAL_CLEAR = "manual_clear"


class CacheKeyGenerator:
    """缓存键生成器"""
    
    @staticmethod
    def intent_keys(intent_id: int, intent_name: str = None) -> List[str]:
        """生成意图相关的缓存键"""
        keys = [
            f"intent_config:all",
            f"intent_config:{intent_id}",
            f"active_intents:list"
        ]
        if intent_name:
            keys.append(f"intent_config:name:{intent_name}")
        return keys
    
    @staticmethod
    def slot_keys(slot_id: int, intent_id: int) -> List[str]:
        """生成槽位相关的缓存键"""
        return [
            f"slot_config:{slot_id}",
            f"intent_slots:{intent_id}",
            f"intent_config:{intent_id}",  # 意图配置可能包含槽位信息
            f"intent_config:all"
        ]
    
    @staticmethod
    def system_config_keys(config_id: int, category: str = None, key: str = None) -> List[str]:
        """生成系统配置相关的缓存键"""
        keys = [
            f"system_config:all",
            f"system_config:{config_id}"
        ]
        if category:
            keys.append(f"system_config:category:{category}")
        if category and key:
            keys.append(f"system_config:{category}:{key}")
        return keys
    
    @staticmethod
    def prompt_template_keys(template_id: int, template_type: str = None, intent_id: int = None) -> List[str]:
        """生成prompt模板相关的缓存键"""
        keys = [
            f"template_config:all",
            f"template_config:{template_id}"
        ]
        if template_type:
            keys.append(f"template_config:type:{template_type}")
        if intent_id:
            keys.append(f"template_config:intent:{intent_id}")
        return keys
    
    @staticmethod
    def function_call_keys(function_id: int, intent_id: int) -> List[str]:
        """生成功能调用相关的缓存键"""
        return [
            f"function_config:{function_id}",
            f"intent_functions:{intent_id}",
            f"intent_config:{intent_id}",
            f"intent_config:all"
        ]
    
    @staticmethod
    def user_keys(user_id: str) -> List[str]:
        """生成用户相关的缓存键"""
        return [
            f"user_profile:{user_id}",
            f"user_context:{user_id}",
            f"user_preferences:{user_id}"
        ]
    
    @staticmethod
    def session_keys(session_id: str, user_id: str = None) -> List[str]:
        """生成会话相关的缓存键"""
        keys = [f"session:{session_id}"]
        if user_id:
            keys.extend([
                f"user_sessions:{user_id}",
                f"session_context:{user_id}:{session_id}"
            ])
        return keys


class CacheInvalidationService:
    """缓存失效管理服务"""
    
    def __init__(self, cache_service: CacheService):
        self.cache_service = cache_service
        self.logger = logger
        self.key_generator = CacheKeyGenerator()
    
    async def invalidate_by_table_change(
        self,
        table_name: str,
        record_id: int,
        operation_type: str,
        additional_data: Optional[Dict[str, Any]] = None
    ) -> CacheInvalidationLog:
        """
        根据表变更失效相关缓存
        
        Args:
            table_name: 变更的表名
            record_id: 记录ID
            operation_type: 操作类型 (INSERT, UPDATE, DELETE)
            additional_data: 额外数据，用于生成更精确的缓存键
            
        Returns:
            CacheInvalidationLog: 缓存失效日志记录
        """
        try:
            # 根据表名生成需要失效的缓存键
            cache_keys = self._generate_cache_keys_by_table(
                table_name, record_id, additional_data or {}
            )
            
            # 记录缓存失效日志
            log_record = CacheInvalidationLog.create(
                table_name_field=table_name,
                record_id=str(record_id),
                operation_type=operation_type,
                cache_keys=json.dumps(cache_keys, ensure_ascii=False),
                invalidation_status='pending'
            )
            
            # 异步执行缓存失效
            await self._execute_cache_invalidation(log_record, cache_keys)
            
            self.logger.info(
                f"触发缓存失效: {table_name}.{record_id} {operation_type}, "
                f"影响缓存键: {len(cache_keys)}"
            )
            
            return log_record
            
        except Exception as e:
            self.logger.error(f"缓存失效处理失败: {str(e)}")
            raise
    
    async def invalidate_intent_cache(
        self,
        intent_id: int,
        intent_name: str = None,
        operation_type: str = "UPDATE"
    ) -> CacheInvalidationLog:
        """失效意图相关缓存"""
        cache_keys = self.key_generator.intent_keys(intent_id, intent_name)
        return await self._create_and_execute_invalidation(
            "intents", intent_id, operation_type, cache_keys
        )
    
    async def invalidate_slot_cache(
        self,
        slot_id: int,
        intent_id: int,
        operation_type: str = "UPDATE"
    ) -> CacheInvalidationLog:
        """失效槽位相关缓存"""
        cache_keys = self.key_generator.slot_keys(slot_id, intent_id)
        return await self._create_and_execute_invalidation(
            "slots", slot_id, operation_type, cache_keys
        )
    
    async def invalidate_system_config_cache(
        self,
        config_id: int,
        category: str = None,
        key: str = None,
        operation_type: str = "UPDATE"
    ) -> CacheInvalidationLog:
        """失效系统配置相关缓存"""
        cache_keys = self.key_generator.system_config_keys(config_id, category, key)
        return await self._create_and_execute_invalidation(
            "system_configs", config_id, operation_type, cache_keys
        )
    
    async def invalidate_by_pattern(
        self,
        pattern: str,
        reason: str = "manual_clear"
    ) -> Dict[str, Any]:
        """
        根据模式批量失效缓存
        
        Args:
            pattern: 缓存键模式 (支持通配符)
            reason: 失效原因
            
        Returns:
            Dict: 失效结果统计
        """
        try:
            # 获取匹配的缓存键
            matching_keys = await self.cache_service.get_keys_by_pattern(pattern)
            
            if not matching_keys:
                return {"pattern": pattern, "invalidated_count": 0, "message": "没有匹配的缓存键"}
            
            # 批量删除缓存
            success_count = 0
            for key in matching_keys:
                try:
                    await self.cache_service.delete(key)
                    success_count += 1
                except Exception as e:
                    self.logger.warning(f"删除缓存键失败: {key}, 错误: {str(e)}")
            
            # 记录批量失效日志
            log_record = CacheInvalidationLog.create(
                table_name_field="batch_invalidation",
                record_id="0",
                operation_type="DELETE",
                cache_keys=json.dumps(matching_keys, ensure_ascii=False),
                invalidation_status='completed'
            )
            
            self.logger.info(f"批量缓存失效完成: 模式={pattern}, 成功={success_count}/{len(matching_keys)}")
            
            return {
                "pattern": pattern,
                "total_keys": len(matching_keys),
                "invalidated_count": success_count,
                "log_id": log_record.id
            }
            
        except Exception as e:
            self.logger.error(f"批量缓存失效失败: {str(e)}")
            raise
    
    async def get_pending_invalidations(self, limit: int = 100) -> List[CacheInvalidationLog]:
        """获取待处理的缓存失效记录"""
        try:
            return list(
                CacheInvalidationLog
                .select()
                .where(CacheInvalidationLog.invalidation_status == 'pending')
                .order_by(CacheInvalidationLog.created_at.asc())
                .limit(limit)
            )
        except Exception as e:
            self.logger.error(f"获取待处理缓存失效记录失败: {str(e)}")
            raise
    
    async def process_pending_invalidations(self) -> Dict[str, Any]:
        """处理待处理的缓存失效记录"""
        try:
            pending_logs = await self.get_pending_invalidations()
            
            if not pending_logs:
                return {"processed": 0, "message": "没有待处理的缓存失效记录"}
            
            success_count = 0
            error_count = 0
            
            for log in pending_logs:
                try:
                    # 标记为处理中
                    log.mark_processing()
                    
                    # 获取缓存键并执行失效
                    cache_keys = log.get_cache_keys()
                    await self._execute_cache_invalidation_direct(cache_keys)
                    
                    # 标记为处理完成
                    log.mark_completed()
                    success_count += 1
                    
                except Exception as e:
                    log.mark_failed(str(e))
                    error_count += 1
                    self.logger.error(f"处理缓存失效记录失败: {log.id}, 错误: {str(e)}")
            
            self.logger.info(f"批量处理缓存失效完成: 成功={success_count}, 失败={error_count}")
            
            return {
                "processed": len(pending_logs),
                "success": success_count,
                "error": error_count
            }
            
        except Exception as e:
            self.logger.error(f"批量处理缓存失效失败: {str(e)}")
            raise
    
    async def get_invalidation_statistics(self, days: int = 7) -> Dict[str, Any]:
        """获取缓存失效统计信息"""
        try:
            from datetime import timedelta
            
            cutoff_time = datetime.now() - timedelta(days=days)
            
            query = CacheInvalidationLog.select().where(
                CacheInvalidationLog.created_at >= cutoff_time
            )
            
            # 统计各种状态
            status_stats = {}
            table_stats = {}
            operation_stats = {}
            
            for log in query:
                # 状态统计
                if log.invalidation_status not in status_stats:
                    status_stats[log.invalidation_status] = 0
                status_stats[log.invalidation_status] += 1
                
                # 表名统计
                if log.table_name_field not in table_stats:
                    table_stats[log.table_name_field] = 0
                table_stats[log.table_name_field] += 1
                
                # 操作类型统计
                if log.operation_type not in operation_stats:
                    operation_stats[log.operation_type] = 0
                operation_stats[log.operation_type] += 1
            
            return {
                'period_days': days,
                'total_invalidations': sum(status_stats.values()),
                'status_stats': status_stats,
                'table_stats': table_stats,
                'operation_stats': operation_stats,
                'generated_at': datetime.now().isoformat()
            }
            
        except Exception as e:
            self.logger.error(f"获取缓存失效统计失败: {str(e)}")
            raise
    
    def _generate_cache_keys_by_table(
        self,
        table_name: str,
        record_id: int,
        additional_data: Dict[str, Any]
    ) -> List[str]:
        """根据表名生成需要失效的缓存键"""
        
        if table_name == "intents":
            return self.key_generator.intent_keys(
                record_id, 
                additional_data.get('intent_name')
            )
        elif table_name == "slots":
            return self.key_generator.slot_keys(
                record_id,
                additional_data.get('intent_id', 0)
            )
        elif table_name == "system_configs":
            return self.key_generator.system_config_keys(
                record_id,
                additional_data.get('config_category'),
                additional_data.get('config_key')
            )
        elif table_name == "prompt_templates":
            return self.key_generator.prompt_template_keys(
                record_id,
                additional_data.get('template_type'),
                additional_data.get('intent_id')
            )
        elif table_name == "function_calls":
            return self.key_generator.function_call_keys(
                record_id,
                additional_data.get('intent_id', 0)
            )
        elif table_name == "users":
            return self.key_generator.user_keys(
                additional_data.get('user_id', str(record_id))
            )
        elif table_name == "sessions":
            return self.key_generator.session_keys(
                additional_data.get('session_id', str(record_id)),
                additional_data.get('user_id')
            )
        else:
            # 默认缓存键
            return [
                f"{table_name}:all",
                f"{table_name}:{record_id}"
            ]
    
    async def _create_and_execute_invalidation(
        self,
        table_name: str,
        record_id: int,
        operation_type: str,
        cache_keys: List[str]
    ) -> CacheInvalidationLog:
        """创建并执行缓存失效"""
        log_record = CacheInvalidationLog.create(
            table_name_field=table_name,
            record_id=str(record_id),
            operation_type=operation_type,
            cache_keys=json.dumps(cache_keys, ensure_ascii=False),
            invalidation_status='pending'
        )
        
        await self._execute_cache_invalidation(log_record, cache_keys)
        return log_record
    
    async def _execute_cache_invalidation(
        self,
        log_record: CacheInvalidationLog,
        cache_keys: List[str]
    ):
        """执行缓存失效操作"""
        try:
            log_record.mark_processing()
            
            # 执行实际的缓存删除
            await self._execute_cache_invalidation_direct(cache_keys)
            
            log_record.mark_completed()
            
        except Exception as e:
            log_record.mark_failed(str(e))
            raise
    
    async def _execute_cache_invalidation_direct(self, cache_keys: List[str]):
        """直接执行缓存失效"""
        for key in cache_keys:
            try:
                await self.cache_service.delete(key)
                self.logger.debug(f"删除缓存键成功: {key}")
            except Exception as e:
                self.logger.warning(f"删除缓存键失败: {key}, 错误: {str(e)}")
                # 继续处理其他键，不因单个键失败而中断


# 全局缓存失效服务实例
_cache_invalidation_service = None


async def get_cache_invalidation_service() -> CacheInvalidationService:
    """获取缓存失效服务实例（单例模式）"""
    global _cache_invalidation_service
    if _cache_invalidation_service is None:
        from src.api.dependencies import get_cache_service
        cache_service = await get_cache_service()
        _cache_invalidation_service = CacheInvalidationService(cache_service)
    return _cache_invalidation_service