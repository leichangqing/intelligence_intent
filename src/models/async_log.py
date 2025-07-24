"""
异步日志队列数据模型
"""
from peewee import *
from playhouse.mysql_ext import JSONField
from .base import BaseModel
from datetime import datetime
from typing import Dict, List, Optional, Any
import json


class AsyncLogQueue(BaseModel):
    """异步日志队列表 - 与MySQL Schema对应"""
    
    id = BigAutoField(primary_key=True, verbose_name="主键ID")
    log_type = CharField(max_length=20, verbose_name="日志类型",
                        constraints=[Check("log_type IN ('api_call', 'security_audit', 'performance', 'error')")])
    log_data = JSONField(verbose_name="日志数据")
    priority = IntegerField(default=1, verbose_name="优先级，数字越大优先级越高")
    status = CharField(max_length=20, default='pending', verbose_name="处理状态",
                      constraints=[Check("status IN ('pending', 'processing', 'completed', 'failed')")])
    retry_count = IntegerField(default=0, verbose_name="重试次数")
    max_retries = IntegerField(default=3, verbose_name="最大重试次数")
    created_at = DateTimeField(default=datetime.now, verbose_name="创建时间")
    processed_at = DateTimeField(null=True, verbose_name="处理时间")
    error_message = TextField(null=True, verbose_name="错误信息")
    
    class Meta:
        table_name = 'async_log_queue'
        indexes = (
            (('log_type', 'status'), False),
            (('priority',), False),
            (('created_at',), False),
        )
    
    # 日志类型常量
    LOG_TYPE_API_CALL = 'api_call'
    LOG_TYPE_SECURITY_AUDIT = 'security_audit'
    LOG_TYPE_PERFORMANCE = 'performance'
    LOG_TYPE_ERROR = 'error'
    
    # 状态常量
    STATUS_PENDING = 'pending'
    STATUS_PROCESSING = 'processing'
    STATUS_COMPLETED = 'completed'
    STATUS_FAILED = 'failed'
    
    # 优先级常量
    PRIORITY_LOW = 1
    PRIORITY_NORMAL = 2
    PRIORITY_HIGH = 3
    PRIORITY_CRITICAL = 4
    
    def get_log_data(self) -> Dict[str, Any]:
        """获取日志数据"""
        if self.log_data:
            return self.log_data if isinstance(self.log_data, dict) else {}
        return {}
    
    def set_log_data(self, data: Dict[str, Any]):
        """设置日志数据"""
        self.log_data = data
    
    def update_log_data(self, key: str, value: Any):
        """更新日志数据中的特定键值"""
        data = self.get_log_data()
        data[key] = value
        self.set_log_data(data)
    
    # 日志类型判断方法
    def is_api_call_log(self) -> bool:
        """判断是否为API调用日志"""
        return self.log_type == self.LOG_TYPE_API_CALL
    
    def is_security_audit_log(self) -> bool:
        """判断是否为安全审计日志"""
        return self.log_type == self.LOG_TYPE_SECURITY_AUDIT
    
    def is_performance_log(self) -> bool:
        """判断是否为性能日志"""
        return self.log_type == self.LOG_TYPE_PERFORMANCE
    
    def is_error_log(self) -> bool:
        """判断是否为错误日志"""
        return self.log_type == self.LOG_TYPE_ERROR
    
    # 状态管理方法
    def is_pending(self) -> bool:
        """判断是否为待处理状态"""
        return self.status == self.STATUS_PENDING
    
    def is_processing(self) -> bool:
        """判断是否为处理中状态"""
        return self.status == self.STATUS_PROCESSING
    
    def is_completed(self) -> bool:
        """判断是否为已完成状态"""
        return self.status == self.STATUS_COMPLETED
    
    def is_failed(self) -> bool:
        """判断是否为失败状态"""
        return self.status == self.STATUS_FAILED
    
    def start_processing(self):
        """开始处理 - 更新状态为处理中"""
        self.status = self.STATUS_PROCESSING
        self.save()
    
    def mark_completed(self):
        """标记为完成"""
        self.status = self.STATUS_COMPLETED
        self.processed_at = datetime.now()
        self.save()
    
    def mark_failed(self, error_message: str = None):
        """标记为失败"""
        self.status = self.STATUS_FAILED
        self.processed_at = datetime.now()
        if error_message:
            self.error_message = error_message
        self.save()
    
    def reset_to_pending(self):
        """重置为待处理状态"""
        self.status = self.STATUS_PENDING
        self.processed_at = None
        self.error_message = None
        self.save()
    
    # 重试逻辑方法
    def can_retry(self) -> bool:
        """判断是否可以重试"""
        return self.retry_count < self.max_retries and self.is_failed()
    
    def increment_retry(self):
        """增加重试次数"""
        self.retry_count += 1
        self.save()
    
    def retry(self, reset_error: bool = True) -> bool:
        """执行重试 - 如果可以重试则重置状态并增加重试次数"""
        if not self.can_retry():
            return False
        
        self.increment_retry()
        self.status = self.STATUS_PENDING
        self.processed_at = None
        if reset_error:
            self.error_message = None
        self.save()
        return True
    
    def is_max_retries_exceeded(self) -> bool:
        """判断是否超过最大重试次数"""
        return self.retry_count >= self.max_retries
    
    # 优先级方法
    def is_high_priority(self) -> bool:
        """判断是否为高优先级"""
        return self.priority >= self.PRIORITY_HIGH
    
    def is_critical_priority(self) -> bool:
        """判断是否为关键优先级"""
        return self.priority >= self.PRIORITY_CRITICAL
    
    def set_priority(self, priority: int):
        """设置优先级"""
        self.priority = priority
        self.save()
    
    def increase_priority(self, amount: int = 1):
        """提高优先级"""
        self.priority += amount
        self.save()
    
    # 类方法 - 队列处理相关
    @classmethod
    def create_log(cls, log_type: str, log_data: Dict[str, Any], 
                   priority: int = PRIORITY_NORMAL, max_retries: int = 3) -> 'AsyncLogQueue':
        """创建新的日志记录"""
        return cls.create(
            log_type=log_type,
            log_data=log_data,
            priority=priority,
            max_retries=max_retries
        )
    
    @classmethod
    def create_api_call_log(cls, log_data: Dict[str, Any], 
                           priority: int = PRIORITY_NORMAL) -> 'AsyncLogQueue':
        """创建API调用日志"""
        return cls.create_log(cls.LOG_TYPE_API_CALL, log_data, priority)
    
    @classmethod
    def create_security_audit_log(cls, log_data: Dict[str, Any], 
                                 priority: int = PRIORITY_HIGH) -> 'AsyncLogQueue':
        """创建安全审计日志"""
        return cls.create_log(cls.LOG_TYPE_SECURITY_AUDIT, log_data, priority)
    
    @classmethod
    def create_performance_log(cls, log_data: Dict[str, Any], 
                              priority: int = PRIORITY_NORMAL) -> 'AsyncLogQueue':
        """创建性能日志"""
        return cls.create_log(cls.LOG_TYPE_PERFORMANCE, log_data, priority)
    
    @classmethod
    def create_error_log(cls, log_data: Dict[str, Any], 
                        priority: int = PRIORITY_HIGH) -> 'AsyncLogQueue':
        """创建错误日志"""
        return cls.create_log(cls.LOG_TYPE_ERROR, log_data, priority)
    
    @classmethod
    def get_pending_logs(cls, limit: int = 100) -> List['AsyncLogQueue']:
        """获取待处理的日志，按优先级和创建时间排序"""
        return list(cls.select()
                   .where(cls.status == cls.STATUS_PENDING)
                   .order_by(cls.priority.desc(), cls.created_at.asc())
                   .limit(limit))
    
    @classmethod
    def get_high_priority_pending(cls, limit: int = 50) -> List['AsyncLogQueue']:
        """获取高优先级的待处理日志"""
        return list(cls.select()
                   .where((cls.status == cls.STATUS_PENDING) & 
                         (cls.priority >= cls.PRIORITY_HIGH))
                   .order_by(cls.priority.desc(), cls.created_at.asc())
                   .limit(limit))
    
    @classmethod
    def get_failed_retryable_logs(cls, limit: int = 50) -> List['AsyncLogQueue']:
        """获取失败但可重试的日志"""
        return list(cls.select()
                   .where((cls.status == cls.STATUS_FAILED) & 
                         (cls.retry_count < cls.max_retries))
                   .order_by(cls.priority.desc(), cls.retry_count.asc())
                   .limit(limit))
    
    @classmethod
    def get_processing_logs(cls) -> List['AsyncLogQueue']:
        """获取正在处理的日志"""
        return list(cls.select().where(cls.status == cls.STATUS_PROCESSING))
    
    @classmethod
    def get_logs_by_type(cls, log_type: str, 
                        status: str = None, limit: int = 100) -> List['AsyncLogQueue']:
        """根据类型获取日志"""
        query = cls.select().where(cls.log_type == log_type)
        if status:
            query = query.where(cls.status == status)
        return list(query.order_by(cls.created_at.desc()).limit(limit))
    
    @classmethod
    def cleanup_completed_logs(cls, days_old: int = 30) -> int:
        """清理指定天数前的已完成日志"""
        from datetime import timedelta
        cutoff_date = datetime.now() - timedelta(days=days_old)
        return cls.delete().where(
            (cls.status == cls.STATUS_COMPLETED) & 
            (cls.processed_at < cutoff_date)
        ).execute()
    
    @classmethod
    def get_queue_stats(cls) -> Dict[str, int]:
        """获取队列统计信息"""
        stats = {}
        
        # 按状态统计
        for status in [cls.STATUS_PENDING, cls.STATUS_PROCESSING, 
                      cls.STATUS_COMPLETED, cls.STATUS_FAILED]:
            stats[f'{status}_count'] = cls.select().where(cls.status == status).count()
        
        # 按类型统计
        for log_type in [cls.LOG_TYPE_API_CALL, cls.LOG_TYPE_SECURITY_AUDIT,
                        cls.LOG_TYPE_PERFORMANCE, cls.LOG_TYPE_ERROR]:
            stats[f'{log_type}_count'] = cls.select().where(cls.log_type == log_type).count()
        
        # 高优先级待处理数量
        stats['high_priority_pending'] = cls.select().where(
            (cls.status == cls.STATUS_PENDING) & 
            (cls.priority >= cls.PRIORITY_HIGH)
        ).count()
        
        # 可重试失败数量
        stats['retryable_failed'] = cls.select().where(
            (cls.status == cls.STATUS_FAILED) & 
            (cls.retry_count < cls.max_retries)
        ).count()
        
        return stats
    
    @classmethod
    def process_next_batch(cls, batch_size: int = 10) -> List['AsyncLogQueue']:
        """处理下一批日志 - 返回开始处理的日志列表"""
        # 获取待处理的日志
        pending_logs = cls.get_pending_logs(limit=batch_size)
        
        # 标记为处理中
        processed_logs = []
        for log in pending_logs:
            log.start_processing()
            processed_logs.append(log)
        
        return processed_logs
    
    def __str__(self):
        return f"AsyncLogQueue({self.id}: {self.log_type} - {self.status})"
    
    def __repr__(self):
        return (f"AsyncLogQueue(id={self.id}, log_type='{self.log_type}', "
                f"status='{self.status}', priority={self.priority}, "
                f"retry_count={self.retry_count})")