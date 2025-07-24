"""
系统配置相关数据模型
"""
from peewee import *
from .base import CommonModel
import json
from datetime import datetime


class SystemConfig(CommonModel):
    """系统配置表"""
    
    config_key = CharField(max_length=100, unique=True, verbose_name="配置键")
    config_value = TextField(verbose_name="配置值")
    description = TextField(null=True, verbose_name="配置描述")
    category = CharField(max_length=50, null=True, verbose_name="配置分类")
    is_readonly = BooleanField(default=False, verbose_name="是否只读")
    
    class Meta:
        table_name = 'system_configs'
        indexes = (
            (('config_key',), True),  # 唯一索引
            (('category',), False),
            (('is_readonly',), False),
        )
    
    def get_typed_value(self):
        """获取类型化的配置值"""
        # 尝试自动检测值类型
        value = self.config_value.strip()
        
        # 布尔值检测
        if value.lower() in ('true', 'false'):
            return value.lower() == 'true'
        
        # 数字检测
        try:
            if '.' in value:
                return float(value)
            else:
                return int(value)
        except ValueError:
            pass
        
        # JSON检测
        if value.startswith(('{', '[')):
            try:
                return json.loads(value)
            except json.JSONDecodeError:
                pass
        
        # 默认返回字符串
        return self.config_value
    
    def set_typed_value(self, value):
        """设置类型化的配置值"""
        if isinstance(value, bool):
            self.config_value = 'true' if value else 'false'
        elif isinstance(value, (int, float)):
            self.config_value = str(value)
        elif isinstance(value, (dict, list)):
            self.config_value = json.dumps(value, ensure_ascii=False)
        else:
            self.config_value = str(value)
    
    @classmethod
    def get_config(cls, key: str, default=None):
        """获取配置值"""
        try:
            config = cls.get(cls.config_key == key)
            return config.get_typed_value()
        except cls.DoesNotExist:
            return default
    
    @classmethod
    def set_config(cls, key: str, value, description: str = None, category: str = None):
        """设置配置值"""
        try:
            config = cls.get(cls.config_key == key)
            config.set_typed_value(value)
            if description:
                config.description = description
            if category:
                config.category = category
            config.save()
        except cls.DoesNotExist:
            config = cls.create(
                config_key=key,
                description=description,
                category=category
            )
            config.set_typed_value(value)
            config.save()
        
        return config
    
    def __str__(self):
        return f"SystemConfig({self.config_key})"


class RagflowConfig(CommonModel):
    """RAGFLOW配置表"""
    
    config_name = CharField(max_length=100, unique=True, verbose_name="配置名称")
    api_endpoint = CharField(max_length=500, verbose_name="API端点")
    api_key_encrypted = TextField(null=True, verbose_name="加密的API密钥")
    api_version = CharField(max_length=20, default="v1", verbose_name="API版本")
    timeout_seconds = IntegerField(default=30, verbose_name="超时时间(秒)")
    max_retries = IntegerField(default=3, verbose_name="最大重试次数")
    rate_limit_per_minute = IntegerField(default=60, verbose_name="每分钟限制")
    connection_pool_size = IntegerField(default=10, verbose_name="连接池大小")
    health_check_interval = IntegerField(default=300, verbose_name="健康检查间隔(秒)")
    last_health_check = DateTimeField(null=True, verbose_name="最后健康检查时间")
    health_status = CharField(max_length=20, default="unknown", verbose_name="健康状态")
    config_metadata = TextField(null=True, verbose_name="配置元数据")
    is_active = BooleanField(default=True, verbose_name="是否激活")
    
    class Meta:
        table_name = 'ragflow_configs'
        indexes = (
            (('config_name',), True),  # 唯一索引
            (('is_active',), False),
        )
    
    @property
    def api_key(self) -> str:
        """获取API密钥（向后兼容）"""
        # 这里可以添加解密逻辑
        return self.api_key_encrypted
    
    @api_key.setter
    def api_key(self, value: str):
        """设置API密钥（向后兼容）"""
        # 这里可以添加加密逻辑
        self.api_key_encrypted = value
    
    def get_config_metadata(self) -> dict:
        """获取配置元数据"""
        if self.config_metadata:
            try:
                return json.loads(self.config_metadata)
            except json.JSONDecodeError:
                return {}
        return {}
    
    def set_config_metadata(self, metadata: dict):
        """设置配置元数据"""
        self.config_metadata = json.dumps(metadata, ensure_ascii=False) if metadata else None
    
    def __str__(self):
        return f"RagflowConfig({self.config_name})"


class FeatureFlag(CommonModel):
    """功能开关表"""
    
    flag_name = CharField(max_length=100, unique=True, verbose_name="功能名称")
    is_enabled = BooleanField(default=False, verbose_name="是否启用")
    description = TextField(null=True, verbose_name="功能描述")
    target_users = TextField(null=True, verbose_name="目标用户")
    rollout_percentage = IntegerField(default=0, verbose_name="推出百分比")
    start_time = DateTimeField(null=True, verbose_name="开始时间")
    end_time = DateTimeField(null=True, verbose_name="结束时间")
    
    class Meta:
        table_name = 'feature_flags'
        indexes = (
            (('flag_name',), True),  # 唯一索引
            (('is_enabled',), False),
        )
    
    def get_target_users(self) -> list:
        """获取目标用户列表"""
        if self.target_users:
            try:
                return json.loads(self.target_users)
            except json.JSONDecodeError:
                return []
        return []
    
    def set_target_users(self, users: list):
        """设置目标用户列表"""
        self.target_users = json.dumps(users, ensure_ascii=False) if users else None
    
    def is_enabled_for_user(self, user_id: str) -> bool:
        """检查功能是否对指定用户启用"""
        if not self.is_enabled:
            return False
        
        # 检查时间范围
        if self.start_time and self.start_time > datetime.now():
            return False
        if self.end_time and self.end_time < datetime.now():
            return False
        
        # 检查目标用户
        target_users = self.get_target_users()
        if target_users and user_id not in target_users:
            return False
        
        # 检查推出百分比
        if self.rollout_percentage < 100:
            import hashlib
            hash_val = int(hashlib.md5(f"{self.flag_name}{user_id}".encode()).hexdigest(), 16)
            if hash_val % 100 >= self.rollout_percentage:
                return False
        
        return True
    
    def __str__(self):
        return f"FeatureFlag({self.flag_name})"


