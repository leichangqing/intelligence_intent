"""
审计日志相关数据模型
"""
from peewee import *
from playhouse.mysql_ext import JSONField as MySQLJSONField
from playhouse.mysql_ext import JSONField
from src.config.database import BaseModel
from .conversation import User
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
import json


class ConfigAuditLog(BaseModel):
    """配置审计日志表 - 与MySQL Schema对应"""
    
    id = BigAutoField(primary_key=True)  # BIGINT AUTO_INCREMENT PRIMARY KEY
    table_name = CharField(max_length=50, verbose_name="表名")  # 数据库字段名是table_name
    record_id = BigIntegerField(verbose_name="记录ID")  # BIGINT NOT NULL 
    action = CharField(max_length=20, verbose_name="操作类型",
                      constraints=[Check("action IN ('INSERT','UPDATE','DELETE')")])  # ENUM
    old_values = MySQLJSONField(null=True, verbose_name="修改前的值")  # JSON
    new_values = MySQLJSONField(null=True, verbose_name="修改后的值")  # JSON
    operator_id = CharField(max_length=100, verbose_name="操作者ID")  # VARCHAR(100) NOT NULL
    operator_name = CharField(max_length=100, null=True, verbose_name="操作者姓名")  # VARCHAR(100)
    created_at = DateTimeField(null=True, verbose_name="创建时间")  # TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    
    class Meta:
        table_name = 'config_audit_logs'
        indexes = (
            (('table_name', 'record_id'), False),
            (('operator_id',), False),
            (('action',), False),
            (('created_at',), False),
        )
    
    def get_old_values(self) -> dict:
        """获取修改前的值"""
        if self.old_values:
            if isinstance(self.old_values, dict):
                return self.old_values
            try:
                return json.loads(self.old_values) if isinstance(self.old_values, str) else self.old_values
            except (json.JSONDecodeError, TypeError):
                return {}
        return {}
    
    def set_old_values(self, values: dict):
        """设置修改前的值"""
        self.old_values = values  # JSONField可以直接存储dict
    
    def get_new_values(self) -> dict:
        """获取修改后的值"""
        if self.new_values:
            if isinstance(self.new_values, dict):
                return self.new_values
            try:
                return json.loads(self.new_values) if isinstance(self.new_values, str) else self.new_values
            except (json.JSONDecodeError, TypeError):
                return {}
        return {}
    
    def set_new_values(self, values: dict):
        """设置修改后的值"""
        self.new_values = values  # JSONField可以直接存储dict
    
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
        return f"ConfigAuditLog({self.table_name}.{self.record_id}: {self.action})"


class SecurityAuditLog(BaseModel):
    """安全审计日志表 - 与MySQL Schema对应"""
    
    id = BigAutoField(primary_key=True)  # BIGINT AUTO_INCREMENT PRIMARY KEY
    user_id = CharField(max_length=100, null=True, verbose_name="用户ID")  # VARCHAR(100) COMMENT '用户ID'
    ip_address = CharField(max_length=45, null=True, verbose_name="IP地址")  # VARCHAR(45) COMMENT 'IP地址'
    user_agent = TextField(null=True, verbose_name="用户代理")  # TEXT COMMENT '用户代理'
    action_type = CharField(max_length=50, null=True, verbose_name="操作类型",
                           constraints=[Check("action_type IN ('login', 'logout', 'api_call', 'config_change', 'security_violation')")]) # ENUM
    resource_type = CharField(max_length=50, null=True, verbose_name="资源类型")  # VARCHAR(50) COMMENT '资源类型'
    resource_id = CharField(max_length=100, null=True, verbose_name="资源ID")  # VARCHAR(100) COMMENT '资源ID'
    action_details = MySQLJSONField(null=True, verbose_name="操作详情")  # JSON COMMENT '操作详情'
    risk_level = CharField(max_length=20, null=True, default='low', verbose_name="风险等级",
                          constraints=[Check("risk_level IN ('low', 'medium', 'high', 'critical')")]) # ENUM DEFAULT 'low'
    status = CharField(max_length=20, null=True, verbose_name="操作状态",
                      constraints=[Check("status IN ('success', 'failure', 'blocked')")]) # ENUM
    created_at = DateTimeField(null=True, verbose_name="创建时间")  # 数据库中允许NULL
    
    class Meta:
        table_name = 'security_audit_logs'
        indexes = (
            (('user_id',), False),
            (('ip_address',), False),
            (('action_type',), False),
            (('risk_level',), False),
            (('created_at',), False),
            (('risk_level', 'created_at'), False),  # 复合索引
        )

    # Action Type Constants
    ACTION_LOGIN = 'login'
    ACTION_LOGOUT = 'logout'
    ACTION_API_CALL = 'api_call'
    ACTION_CONFIG_CHANGE = 'config_change'
    ACTION_SECURITY_VIOLATION = 'security_violation'

    # Risk Level Constants
    RISK_LOW = 'low'
    RISK_MEDIUM = 'medium'
    RISK_HIGH = 'high'
    RISK_CRITICAL = 'critical'

    # Status Constants
    STATUS_SUCCESS = 'success'
    STATUS_FAILURE = 'failure'
    STATUS_BLOCKED = 'blocked'

    def get_action_details(self) -> dict:
        """获取操作详情"""
        if self.action_details:
            return self.action_details if isinstance(self.action_details, dict) else {}
        return {}

    def set_action_details(self, details: dict):
        """设置操作详情"""
        self.action_details = details

    def update_action_details(self, key: str, value: Any):
        """更新操作详情中的特定键值"""
        details = self.get_action_details()
        details[key] = value
        self.set_action_details(details)

    # Helper methods for checking action types
    def is_login_action(self) -> bool:
        """检查是否为登录操作"""
        return self.action_type == self.ACTION_LOGIN

    def is_logout_action(self) -> bool:
        """检查是否为登出操作"""
        return self.action_type == self.ACTION_LOGOUT

    def is_api_call_action(self) -> bool:
        """检查是否为API调用操作"""
        return self.action_type == self.ACTION_API_CALL

    def is_config_change_action(self) -> bool:
        """检查是否为配置变更操作"""
        return self.action_type == self.ACTION_CONFIG_CHANGE

    def is_security_violation_action(self) -> bool:
        """检查是否为安全违规操作"""
        return self.action_type == self.ACTION_SECURITY_VIOLATION

    # Helper methods for checking risk levels
    def is_low_risk(self) -> bool:
        """检查是否为低风险"""
        return self.risk_level == self.RISK_LOW

    def is_medium_risk(self) -> bool:
        """检查是否为中等风险"""
        return self.risk_level == self.RISK_MEDIUM

    def is_high_risk(self) -> bool:
        """检查是否为高风险"""
        return self.risk_level == self.RISK_HIGH

    def is_critical_risk(self) -> bool:
        """检查是否为严重风险"""
        return self.risk_level == self.RISK_CRITICAL

    def is_elevated_risk(self) -> bool:
        """检查是否为提升的风险（中等或以上）"""
        return self.risk_level in [self.RISK_MEDIUM, self.RISK_HIGH, self.RISK_CRITICAL]

    # Helper methods for checking status
    def is_successful(self) -> bool:
        """检查操作是否成功"""
        return self.status == self.STATUS_SUCCESS

    def is_failed(self) -> bool:
        """检查操作是否失败"""
        return self.status == self.STATUS_FAILURE

    def is_blocked(self) -> bool:
        """检查操作是否被阻止"""
        return self.status == self.STATUS_BLOCKED

    def is_suspicious(self) -> bool:
        """检查是否为可疑操作"""
        return self.is_failed() or self.is_blocked() or self.is_elevated_risk()

    # Class methods for querying common patterns
    @classmethod
    def get_security_violations(cls, days: int = 7) -> List['SecurityAuditLog']:
        """获取指定天数内的安全违规记录"""
        since = datetime.now() - timedelta(days=days)
        return list(cls.select().where(
            (cls.action_type == cls.ACTION_SECURITY_VIOLATION) &
            (cls.created_at >= since)
        ).order_by(cls.created_at.desc()))

    @classmethod
    def get_failed_logins(cls, days: int = 1, user_id: Optional[str] = None) -> List['SecurityAuditLog']:
        """获取指定天数内的失败登录记录"""
        since = datetime.now() - timedelta(days=days)
        query = cls.select().where(
            (cls.action_type == cls.ACTION_LOGIN) &
            (cls.status == cls.STATUS_FAILURE) &
            (cls.created_at >= since)
        )
        
        if user_id:
            query = query.where(cls.user_id == user_id)
        
        return list(query.order_by(cls.created_at.desc()))

    @classmethod
    def get_blocked_operations(cls, days: int = 7) -> List['SecurityAuditLog']:
        """获取指定天数内被阻止的操作"""
        since = datetime.now() - timedelta(days=days)
        return list(cls.select().where(
            (cls.status == cls.STATUS_BLOCKED) &
            (cls.created_at >= since)
        ).order_by(cls.created_at.desc()))

    @classmethod
    def get_high_risk_activities(cls, days: int = 7) -> List['SecurityAuditLog']:
        """获取指定天数内的高风险活动"""
        since = datetime.now() - timedelta(days=days)
        return list(cls.select().where(
            (cls.risk_level.in_([cls.RISK_HIGH, cls.RISK_CRITICAL])) &
            (cls.created_at >= since)
        ).order_by(cls.created_at.desc()))

    @classmethod
    def get_user_activities(cls, user_id: str, days: int = 30) -> List['SecurityAuditLog']:
        """获取指定用户的活动记录"""
        since = datetime.now() - timedelta(days=days)
        return list(cls.select().where(
            (cls.user_id == user_id) &
            (cls.created_at >= since)
        ).order_by(cls.created_at.desc()))

    @classmethod
    def get_ip_activities(cls, ip_address: str, days: int = 7) -> List['SecurityAuditLog']:
        """获取指定IP地址的活动记录"""
        since = datetime.now() - timedelta(days=days)
        return list(cls.select().where(
            (cls.ip_address == ip_address) &
            (cls.created_at >= since)
        ).order_by(cls.created_at.desc()))

    @classmethod
    def get_config_changes(cls, days: int = 30) -> List['SecurityAuditLog']:
        """获取指定天数内的配置变更记录"""
        since = datetime.now() - timedelta(days=days)
        return list(cls.select().where(
            (cls.action_type == cls.ACTION_CONFIG_CHANGE) &
            (cls.created_at >= since)
        ).order_by(cls.created_at.desc()))

    @classmethod
    def count_failed_logins_by_ip(cls, ip_address: str, hours: int = 1) -> int:
        """统计指定IP在指定小时内的失败登录次数"""
        since = datetime.now() - timedelta(hours=hours)
        return cls.select().where(
            (cls.ip_address == ip_address) &
            (cls.action_type == cls.ACTION_LOGIN) &
            (cls.status == cls.STATUS_FAILURE) &
            (cls.created_at >= since)
        ).count()

    @classmethod
    def count_failed_logins_by_user(cls, user_id: str, hours: int = 1) -> int:
        """统计指定用户在指定小时内的失败登录次数"""
        since = datetime.now() - timedelta(hours=hours)
        return cls.select().where(
            (cls.user_id == user_id) &
            (cls.action_type == cls.ACTION_LOGIN) &
            (cls.status == cls.STATUS_FAILURE) &
            (cls.created_at >= since)
        ).count()

    @classmethod
    def get_suspicious_activities(cls, days: int = 7) -> List['SecurityAuditLog']:
        """获取可疑活动（失败或被阻止的操作，以及高风险操作）"""
        since = datetime.now() - timedelta(days=days)
        return list(cls.select().where(
            (cls.created_at >= since) &
            (
                (cls.status.in_([cls.STATUS_FAILURE, cls.STATUS_BLOCKED])) |
                (cls.risk_level.in_([cls.RISK_HIGH, cls.RISK_CRITICAL]))
            )
        ).order_by(cls.created_at.desc()))

    @classmethod
    def get_activity_summary_by_user(cls, days: int = 30) -> Dict[str, Dict[str, int]]:
        """获取用户活动汇总统计"""
        since = datetime.now() - timedelta(days=days)
        
        # 使用原始SQL进行聚合查询
        query = """
        SELECT user_id, action_type, status, COUNT(*) as count
        FROM security_audit_logs 
        WHERE created_at >= %s AND user_id IS NOT NULL
        GROUP BY user_id, action_type, status
        """
        
        result = {}
        cursor = cls._meta.database.execute_sql(query, [since])
        
        for row in cursor.fetchall():
            user_id, action_type, status, count = row
            if user_id not in result:
                result[user_id] = {}
            key = f"{action_type}_{status}"
            result[user_id][key] = count
            
        return result

    @classmethod
    def log_login_attempt(cls, user_id: str, ip_address: str, user_agent: str, 
                         success: bool, details: Optional[Dict] = None) -> 'SecurityAuditLog':
        """记录登录尝试"""
        return cls.create(
            user_id=user_id,
            ip_address=ip_address,
            user_agent=user_agent,
            action_type=cls.ACTION_LOGIN,
            status=cls.STATUS_SUCCESS if success else cls.STATUS_FAILURE,
            risk_level=cls.RISK_LOW if success else cls.RISK_MEDIUM,
            action_details=details or {}
        )

    @classmethod
    def log_logout(cls, user_id: str, ip_address: str, user_agent: str, 
                  details: Optional[Dict] = None) -> 'SecurityAuditLog':
        """记录登出操作"""
        return cls.create(
            user_id=user_id,
            ip_address=ip_address,
            user_agent=user_agent,
            action_type=cls.ACTION_LOGOUT,
            status=cls.STATUS_SUCCESS,
            risk_level=cls.RISK_LOW,
            action_details=details or {}
        )

    @classmethod
    def log_api_call(cls, user_id: str, ip_address: str, user_agent: str,
                    resource_type: str, resource_id: str, success: bool,
                    risk_level: str = RISK_LOW, details: Optional[Dict] = None) -> 'SecurityAuditLog':
        """记录API调用"""
        return cls.create(
            user_id=user_id,
            ip_address=ip_address,
            user_agent=user_agent,
            action_type=cls.ACTION_API_CALL,
            resource_type=resource_type,
            resource_id=resource_id,
            status=cls.STATUS_SUCCESS if success else cls.STATUS_FAILURE,
            risk_level=risk_level,
            action_details=details or {}
        )

    @classmethod
    def log_config_change(cls, user_id: str, ip_address: str, user_agent: str,
                         resource_type: str, resource_id: str, 
                         risk_level: str = RISK_MEDIUM, details: Optional[Dict] = None) -> 'SecurityAuditLog':
        """记录配置变更"""
        return cls.create(
            user_id=user_id,
            ip_address=ip_address,
            user_agent=user_agent,
            action_type=cls.ACTION_CONFIG_CHANGE,
            resource_type=resource_type,
            resource_id=resource_id,
            status=cls.STATUS_SUCCESS,
            risk_level=risk_level,
            action_details=details or {}
        )

    @classmethod
    def log_security_violation(cls, user_id: Optional[str], ip_address: str, user_agent: str,
                              violation_type: str, risk_level: str = RISK_HIGH,
                              details: Optional[Dict] = None) -> 'SecurityAuditLog':
        """记录安全违规"""
        violation_details = details or {}
        violation_details['violation_type'] = violation_type
        
        return cls.create(
            user_id=user_id,
            ip_address=ip_address,
            user_agent=user_agent,
            action_type=cls.ACTION_SECURITY_VIOLATION,
            status=cls.STATUS_BLOCKED,
            risk_level=risk_level,
            action_details=violation_details
        )

    def __str__(self):
        return f"SecurityAuditLog({self.action_type}: {self.user_id or 'anonymous'} @ {self.ip_address})"

    def __repr__(self):
        return (f"SecurityAuditLog(id={self.id}, user_id='{self.user_id}', "
                f"action_type='{self.action_type}', status='{self.status}', "
                f"risk_level='{self.risk_level}', created_at='{self.created_at}')")


class CacheInvalidationLog(BaseModel):
    """缓存失效日志表 - 与MySQL Schema对应"""
    
    id = BigAutoField(primary_key=True)  # BIGINT AUTO_INCREMENT PRIMARY KEY
    table_name = CharField(max_length=50, verbose_name="变更的表名")  # VARCHAR(50) NOT NULL
    record_id = CharField(max_length=100, verbose_name="记录ID")  # VARCHAR(100) NOT NULL
    operation_type = CharField(max_length=20, verbose_name="操作类型",
                              constraints=[Check("operation_type IN ('INSERT','UPDATE','DELETE')")])  # ENUM
    cache_keys = MySQLJSONField(verbose_name="需要失效的缓存键列表")  # JSON NOT NULL
    invalidation_status = CharField(max_length=20, null=True, default='pending', verbose_name="失效状态",
                                   constraints=[Check("invalidation_status IN ('pending','processing','completed','failed')")])  # ENUM DEFAULT 'pending'
    created_at = DateTimeField(null=True, verbose_name="创建时间")  # TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    processed_at = DateTimeField(null=True, verbose_name="处理时间")  # TIMESTAMP NULL
    error_message = TextField(null=True, verbose_name="错误信息")  # TEXT
    
    class Meta:
        table_name = 'cache_invalidation_logs'
        indexes = (
            (('table_name', 'record_id'), False),
            (('invalidation_status',), False),
            (('created_at',), False),
        )
    
    def get_cache_keys(self) -> list:
        """获取缓存键列表"""
        if self.cache_keys:
            if isinstance(self.cache_keys, list):
                return self.cache_keys
            try:
                return json.loads(self.cache_keys) if isinstance(self.cache_keys, str) else []
            except (json.JSONDecodeError, TypeError):
                return []
        return []
    
    def set_cache_keys(self, keys: list):
        """设置缓存键列表"""
        self.cache_keys = keys  # JSONField可以直接存储list
    
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
        return f"CacheInvalidationLog({self.table_name}.{self.record_id})"


class AsyncLogQueue(BaseModel):
    """异步日志队列表 - 与MySQL Schema对应"""
    
    id = BigAutoField(primary_key=True)  # BIGINT AUTO_INCREMENT PRIMARY KEY
    log_type = CharField(max_length=50, null=True, verbose_name="日志类型",
                        constraints=[Check("log_type IN ('api_call','security_audit','performance','error')")])  # ENUM NOT NULL
    log_data = MySQLJSONField(verbose_name="日志数据")  # JSON NOT NULL
    priority = IntegerField(null=True, default=1, verbose_name="优先级")  # INT DEFAULT 1
    status = CharField(max_length=20, null=True, default='pending', verbose_name="处理状态",
                      constraints=[Check("status IN ('pending','processing','completed','failed')")])  # ENUM DEFAULT 'pending'
    retry_count = IntegerField(null=True, default=0, verbose_name="重试次数")  # INT DEFAULT 0
    max_retries = IntegerField(null=True, default=3, verbose_name="最大重试次数")  # INT DEFAULT 3
    created_at = DateTimeField(null=True, verbose_name="创建时间")  # TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    processed_at = DateTimeField(null=True, verbose_name="处理时间")  # TIMESTAMP NULL
    error_message = TextField(null=True, verbose_name="错误信息")  # TEXT
    
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
            if isinstance(self.log_data, dict):
                return self.log_data
            try:
                return json.loads(self.log_data) if isinstance(self.log_data, str) else {}
            except (json.JSONDecodeError, TypeError):
                return {}
        return {}
    
    def set_log_data(self, data: dict):
        """设置日志数据"""
        self.log_data = data  # JSONField可以直接存储dict
    
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


class PerformanceLog(BaseModel):
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
    created_at = DateTimeField(default=datetime.now, verbose_name="创建时间")
    updated_at = DateTimeField(default=datetime.now, verbose_name="更新时间")
    
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