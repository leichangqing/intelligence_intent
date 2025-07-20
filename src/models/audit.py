"""
审计日志相关数据模型
"""
from peewee import *
from .base import CommonModel
import json


class ConfigAuditLog(CommonModel):
    """配置审计日志表"""
    
    table_name_field = CharField(max_length=50, verbose_name="表名")
    record_id = IntegerField(verbose_name="记录ID")
    action = CharField(max_length=20, verbose_name="操作类型")  # INSERT, UPDATE, DELETE
    old_values = TextField(null=True, verbose_name="修改前的值JSON")
    new_values = TextField(null=True, verbose_name="修改后的值JSON")
    operator_id = CharField(max_length=100, verbose_name="操作者ID")
    operator_name = CharField(max_length=100, null=True, verbose_name="操作者姓名")
    ip_address = CharField(max_length=45, null=True, verbose_name="操作者IP")
    user_agent = TextField(null=True, verbose_name="用户代理")
    
    class Meta:
        table_name = 'config_audit_logs'
        indexes = (
            (('table_name_field', 'record_id'), False),
            (('operator_id',), False),
            (('action',), False),
            (('created_at',), False),
        )
    
    def get_old_values(self) -> dict:
        """获取修改前的值"""
        if self.old_values:
            try:
                return json.loads(self.old_values)
            except json.JSONDecodeError:
                return {}
        return {}
    
    def set_old_values(self, values: dict):
        """设置修改前的值"""
        self.old_values = json.dumps(values, ensure_ascii=False)
    
    def get_new_values(self) -> dict:
        """获取修改后的值"""
        if self.new_values:
            try:
                return json.loads(self.new_values)
            except json.JSONDecodeError:
                return {}
        return {}
    
    def set_new_values(self, values: dict):
        """设置修改后的值"""
        self.new_values = json.dumps(values, ensure_ascii=False)
    
    def get_changes(self) -> dict:
        """获取变更详情"""
        old_vals = self.get_old_values()
        new_vals = self.get_new_values()
        
        changes = {}
        all_keys = set(old_vals.keys()) | set(new_vals.keys())
        
        for key in all_keys:
            old_val = old_vals.get(key)
            new_val = new_vals.get(key)
            
            if old_val != new_val:
                changes[key] = {
                    'old': old_val,
                    'new': new_val
                }
        
        return changes
    
    def is_creation(self) -> bool:
        """判断是否为创建操作"""
        return self.action == 'INSERT'
    
    def is_update(self) -> bool:
        """判断是否为更新操作"""
        return self.action == 'UPDATE'
    
    def is_deletion(self) -> bool:
        """判断是否为删除操作"""
        return self.action == 'DELETE'
    
    def __str__(self):
        return f"ConfigAuditLog({self.table_name_field}.{self.record_id}: {self.action})"


class SecurityAuditLog(CommonModel):
    """安全审计日志表"""
    
    user_id = CharField(max_length=100, null=True, verbose_name="用户ID")
    ip_address = CharField(max_length=45, null=True, verbose_name="IP地址")
    user_agent = TextField(null=True, verbose_name="用户代理")
    action_type = CharField(max_length=50, verbose_name="操作类型")  # login, logout, api_call, security_violation
    resource_type = CharField(max_length=50, null=True, verbose_name="资源类型")
    resource_id = CharField(max_length=100, null=True, verbose_name="资源ID")
    action_details = TextField(null=True, verbose_name="操作详情JSON")
    risk_level = CharField(max_length=20, default='low', verbose_name="风险等级")  # low, medium, high, critical
    status = CharField(max_length=20, verbose_name="操作状态")  # success, failure, blocked
    error_message = TextField(null=True, verbose_name="错误信息")
    
    class Meta:
        table_name = 'security_audit_logs'
        indexes = (
            (('user_id',), False),
            (('ip_address',), False),
            (('action_type',), False),
            (('risk_level',), False),
            (('status',), False),
            (('created_at',), False),
        )
    
    def get_action_details(self) -> dict:
        """获取操作详情"""
        if self.action_details:
            try:
                return json.loads(self.action_details)
            except json.JSONDecodeError:
                return {}
        return {}
    
    def set_action_details(self, details: dict):
        """设置操作详情"""
        self.action_details = json.dumps(details, ensure_ascii=False)
    
    def is_high_risk(self) -> bool:
        """判断是否为高风险操作"""
        return self.risk_level in ['high', 'critical']
    
    def is_security_violation(self) -> bool:
        """判断是否为安全违规"""
        return self.action_type == 'security_violation'
    
    def is_successful(self) -> bool:
        """判断操作是否成功"""
        return self.status == 'success'
    
    def is_blocked(self) -> bool:
        """判断操作是否被阻断"""
        return self.status == 'blocked'
    
    def __str__(self):
        return f"SecurityAuditLog({self.user_id}: {self.action_type})"


class CacheInvalidationLog(CommonModel):
    """缓存失效日志表"""
    
    table_name_field = CharField(max_length=50, verbose_name="变更的表名")
    record_id = CharField(max_length=100, verbose_name="记录ID")
    operation_type = CharField(max_length=20, verbose_name="操作类型")  # INSERT, UPDATE, DELETE
    cache_keys = TextField(verbose_name="需要失效的缓存键列表JSON")
    invalidation_status = CharField(max_length=20, default='pending', verbose_name="失效状态")  # pending, processing, completed, failed
    processed_at = DateTimeField(null=True, verbose_name="处理时间")
    error_message = TextField(null=True, verbose_name="错误信息")
    
    class Meta:
        table_name = 'cache_invalidation_logs'
        indexes = (
            (('table_name_field', 'record_id'), False),
            (('invalidation_status',), False),
            (('created_at',), False),
        )
    
    def get_cache_keys(self) -> list:
        """获取缓存键列表"""
        if self.cache_keys:
            try:
                return json.loads(self.cache_keys)
            except json.JSONDecodeError:
                return []
        return []
    
    def set_cache_keys(self, keys: list):
        """设置缓存键列表"""
        self.cache_keys = json.dumps(keys, ensure_ascii=False)
    
    def mark_processing(self):
        """标记为处理中"""
        self.invalidation_status = 'processing'
        self.save()
    
    def mark_completed(self):
        """标记为处理完成"""
        from datetime import datetime
        self.invalidation_status = 'completed'
        self.processed_at = datetime.now()
        self.error_message = None
        self.save()
    
    def mark_failed(self, error_message: str):
        """标记为处理失败"""
        from datetime import datetime
        self.invalidation_status = 'failed'
        self.processed_at = datetime.now()
        self.error_message = error_message
        self.save()
    
    def is_pending(self) -> bool:
        """判断是否待处理"""
        return self.invalidation_status == 'pending'
    
    def is_completed(self) -> bool:
        """判断是否处理完成"""
        return self.invalidation_status == 'completed'
    
    def __str__(self):
        return f"CacheInvalidationLog({self.table_name_field}.{self.record_id})"


class AsyncLogQueue(CommonModel):
    """异步日志队列表"""
    
    log_type = CharField(max_length=50, verbose_name="日志类型")  # api_call, security_audit, performance, error
    log_data = TextField(verbose_name="日志数据JSON")
    priority = IntegerField(default=1, verbose_name="优先级")
    status = CharField(max_length=20, default='pending', verbose_name="处理状态")  # pending, processing, completed, failed
    retry_count = IntegerField(default=0, verbose_name="重试次数")
    max_retries = IntegerField(default=3, verbose_name="最大重试次数")
    processed_at = DateTimeField(null=True, verbose_name="处理时间")
    error_message = TextField(null=True, verbose_name="错误信息")
    
    class Meta:
        table_name = 'async_log_queue'
        indexes = (
            (('log_type', 'status'), False),
            (('priority',), False),
            (('created_at',), False),
            (('status',), False),
        )
    
    def get_log_data(self) -> dict:
        """获取日志数据"""
        if self.log_data:
            try:
                return json.loads(self.log_data)
            except json.JSONDecodeError:
                return {}
        return {}
    
    def set_log_data(self, data: dict):
        """设置日志数据"""
        self.log_data = json.dumps(data, ensure_ascii=False)
    
    def start_processing(self):
        """开始处理"""
        self.status = 'processing'
        self.save()
    
    def mark_completed(self):
        """标记为处理完成"""
        from datetime import datetime
        self.status = 'completed'
        self.processed_at = datetime.now()
        self.error_message = None
        self.save()
    
    def mark_failed(self, error_message: str):
        """标记为处理失败"""
        from datetime import datetime
        self.status = 'failed'
        self.processed_at = datetime.now()
        self.error_message = error_message
        self.retry_count += 1
        self.save()
    
    def can_retry(self) -> bool:
        """判断是否可以重试"""
        return self.retry_count < self.max_retries
    
    def reset_for_retry(self):
        """重置为重试状态"""
        if self.can_retry():
            self.status = 'pending'
            self.error_message = None
            self.save()
            return True
        return False
    
    def is_high_priority(self) -> bool:
        """判断是否为高优先级"""
        return self.priority >= 5
    
    def __str__(self):
        return f"AsyncLogQueue({self.log_type}: {self.status})"


class PerformanceLog(CommonModel):
    """性能监控日志表"""
    
    endpoint = CharField(max_length=200, verbose_name="API端点")
    method = CharField(max_length=10, verbose_name="HTTP方法")
    user_id = CharField(max_length=100, null=True, verbose_name="用户ID")
    request_id = CharField(max_length=100, null=True, verbose_name="请求ID")
    response_time_ms = IntegerField(verbose_name="响应时间毫秒")
    status_code = IntegerField(verbose_name="HTTP状态码")
    request_size_bytes = IntegerField(null=True, verbose_name="请求大小字节")
    response_size_bytes = IntegerField(null=True, verbose_name="响应大小字节")
    cpu_usage_percent = DecimalField(max_digits=5, decimal_places=2, null=True, verbose_name="CPU使用率")
    memory_usage_mb = DecimalField(max_digits=10, decimal_places=2, null=True, verbose_name="内存使用MB")
    cache_hit = BooleanField(null=True, verbose_name="是否缓存命中")
    database_queries = IntegerField(default=0, verbose_name="数据库查询次数")
    external_api_calls = IntegerField(default=0, verbose_name="外部API调用次数")
    
    class Meta:
        table_name = 'performance_logs'
        indexes = (
            (('endpoint', 'method'), False),
            (('response_time_ms',), False),
            (('status_code',), False),
            (('created_at',), False),
            (('user_id',), False),
        )
    
    def is_slow_request(self, threshold_ms: int = 2000) -> bool:
        """判断是否为慢请求"""
        return self.response_time_ms > threshold_ms
    
    def is_successful(self) -> bool:
        """判断是否请求成功"""
        return 200 <= self.status_code < 400
    
    def is_error(self) -> bool:
        """判断是否错误响应"""
        return self.status_code >= 400
    
    def get_performance_grade(self) -> str:
        """获取性能等级"""
        if self.response_time_ms < 500:
            return 'excellent'
        elif self.response_time_ms < 1000:
            return 'good'
        elif self.response_time_ms < 2000:
            return 'fair'
        else:
            return 'poor'
    
    def __str__(self):
        return f"PerformanceLog({self.endpoint}: {self.response_time_ms}ms)"