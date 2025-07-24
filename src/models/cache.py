"""
缓存失效日志数据模型
"""
from peewee import *
from playhouse.mysql_ext import JSONField
from .base import CommonModel
from datetime import datetime, timedelta
from typing import List, Dict, Optional


class CacheInvalidationLog(CommonModel):
    """缓存失效日志表 - 与MySQL Schema对应"""
    
    id = BigAutoField(primary_key=True)  # 显式定义BIGINT主键
    table_name = CharField(max_length=50, verbose_name="表名")
    record_id = CharField(max_length=100, verbose_name="记录ID")
    operation_type = CharField(max_length=10, verbose_name="操作类型",
                              constraints=[Check("operation_type IN ('INSERT', 'UPDATE', 'DELETE')")])
    cache_keys = JSONField(verbose_name="缓存键列表")
    invalidation_status = CharField(max_length=20, default='pending', verbose_name="失效状态",
                                   constraints=[Check("invalidation_status IN ('pending', 'processing', 'completed', 'failed')")])
    created_at = DateTimeField(default=datetime.now, verbose_name="创建时间")
    processed_at = DateTimeField(null=True, verbose_name="处理时间")
    error_message = TextField(null=True, verbose_name="错误信息")
    
    class Meta:
        table_name = 'cache_invalidation_logs'
        indexes = (
            (('table_name', 'record_id'), False),
            (('operation_type',), False),
            (('invalidation_status', 'created_at'), False),
            (('created_at',), False),
            (('processed_at',), False),
        )
    
    # 操作类型常量
    OPERATION_INSERT = 'INSERT'
    OPERATION_UPDATE = 'UPDATE'
    OPERATION_DELETE = 'DELETE'
    
    # 失效状态常量
    STATUS_PENDING = 'pending'
    STATUS_PROCESSING = 'processing'
    STATUS_COMPLETED = 'completed'
    STATUS_FAILED = 'failed'
    
    def get_cache_keys(self) -> List[str]:
        """获取缓存键列表"""
        if self.cache_keys:
            return self.cache_keys if isinstance(self.cache_keys, list) else []
        return []
    
    def set_cache_keys(self, keys: List[str]):
        """设置缓存键列表"""
        self.cache_keys = keys
    
    def add_cache_key(self, key: str):
        """添加缓存键"""
        keys = self.get_cache_keys()
        if key not in keys:
            keys.append(key)
            self.set_cache_keys(keys)
    
    def is_insert_operation(self) -> bool:
        """检查是否为插入操作"""
        return self.operation_type == self.OPERATION_INSERT
    
    def is_update_operation(self) -> bool:
        """检查是否为更新操作"""
        return self.operation_type == self.OPERATION_UPDATE
    
    def is_delete_operation(self) -> bool:
        """检查是否为删除操作"""
        return self.operation_type == self.OPERATION_DELETE
    
    def is_pending(self) -> bool:
        """检查是否为待处理状态"""
        return self.invalidation_status == self.STATUS_PENDING
    
    def is_processing(self) -> bool:
        """检查是否为处理中状态"""
        return self.invalidation_status == self.STATUS_PROCESSING
    
    def is_completed(self) -> bool:
        """检查是否为已完成状态"""
        return self.invalidation_status == self.STATUS_COMPLETED
    
    def is_failed(self) -> bool:
        """检查是否为失败状态"""
        return self.invalidation_status == self.STATUS_FAILED
    
    def can_process(self) -> bool:
        """检查是否可以处理"""
        return self.is_pending()
    
    def mark_processing(self):
        """标记为处理中"""
        self.invalidation_status = self.STATUS_PROCESSING
        self.processed_at = datetime.now()
    
    def mark_completed(self):
        """标记为已完成"""
        self.invalidation_status = self.STATUS_COMPLETED
        if not self.processed_at:
            self.processed_at = datetime.now()
    
    def mark_failed(self, error_message: str):
        """标记为失败"""
        self.invalidation_status = self.STATUS_FAILED
        self.error_message = error_message
        if not self.processed_at:
            self.processed_at = datetime.now()
    
    @classmethod
    def create_invalidation_record(cls, table_name: str, record_id: str, 
                                  operation_type: str, cache_keys: List[str]) -> 'CacheInvalidationLog':
        """创建缓存失效记录"""
        if operation_type not in [cls.OPERATION_INSERT, cls.OPERATION_UPDATE, cls.OPERATION_DELETE]:
            raise ValueError(f"Invalid operation_type: {operation_type}")
        
        return cls.create(
            table_name=table_name,
            record_id=record_id,
            operation_type=operation_type,
            cache_keys=cache_keys
        )
    
    @classmethod
    def get_pending_records(cls, limit: int = 100) -> List['CacheInvalidationLog']:
        """获取待处理的失效记录"""
        return list(cls.select().where(
            cls.invalidation_status == cls.STATUS_PENDING
        ).order_by(cls.created_at).limit(limit))
    
    @classmethod
    def get_processing_records(cls) -> List['CacheInvalidationLog']:
        """获取处理中的失效记录"""
        return list(cls.select().where(
            cls.invalidation_status == cls.STATUS_PROCESSING
        ).order_by(cls.created_at))
    
    @classmethod
    def get_failed_records(cls, limit: int = 100) -> List['CacheInvalidationLog']:
        """获取失败的失效记录"""
        return list(cls.select().where(
            cls.invalidation_status == cls.STATUS_FAILED
        ).order_by(cls.created_at.desc()).limit(limit))
    
    @classmethod
    def get_records_by_table(cls, table_name: str, 
                           status: Optional[str] = None) -> List['CacheInvalidationLog']:
        """根据表名获取失效记录"""
        query = cls.select().where(cls.table_name == table_name)
        if status:
            query = query.where(cls.invalidation_status == status)
        return list(query.order_by(cls.created_at.desc()))
    
    @classmethod
    def cleanup_old_records(cls, days: int = 30) -> int:
        """清理旧的已完成记录"""
        cutoff_date = datetime.now() - timedelta(days=days)
        return cls.delete().where(
            (cls.invalidation_status == cls.STATUS_COMPLETED) &
            (cls.processed_at < cutoff_date)
        ).execute()
    
    @classmethod
    def get_statistics(cls) -> Dict[str, int]:
        """获取失效日志统计信息"""
        from peewee import fn
        
        stats = {}
        
        # 按状态统计
        status_stats = (cls.select(cls.invalidation_status, fn.COUNT().alias('count'))
                       .group_by(cls.invalidation_status))
        
        for record in status_stats:
            stats[f"status_{record.invalidation_status}"] = record.count
        
        # 按操作类型统计
        operation_stats = (cls.select(cls.operation_type, fn.COUNT().alias('count'))
                          .group_by(cls.operation_type))
        
        for record in operation_stats:
            stats[f"operation_{record.operation_type.lower()}"] = record.count
        
        # 总数统计
        stats['total'] = cls.select().count()
        
        return stats
    
    @classmethod
    def retry_failed_record(cls, record_id: int) -> bool:
        """重试失败的记录"""
        try:
            record = cls.get_by_id(record_id)
            if record.is_failed():
                record.invalidation_status = cls.STATUS_PENDING
                record.error_message = None
                record.processed_at = None
                record.save()
                return True
            return False
        except cls.DoesNotExist:
            return False
    
    def get_processing_duration(self) -> Optional[float]:
        """获取处理耗时（秒）"""
        if self.processed_at and self.created_at:
            return (self.processed_at - self.created_at).total_seconds()
        return None
    
    def __str__(self):
        return f"CacheInvalidation({self.table_name}.{self.record_id}: {self.operation_type} -> {self.invalidation_status})"