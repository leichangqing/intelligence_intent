"""
系统配置相关数据模型
"""
from peewee import *
from playhouse.mysql_ext import JSONField
from .base import CommonModel
import json


class SystemConfig(CommonModel):
    """系统配置表"""
    
    config_category = CharField(max_length=50, verbose_name="配置分类")
    config_key = CharField(max_length=100, verbose_name="配置键")
    config_value = TextField(null=True, verbose_name="配置值")
    value_type = CharField(max_length=20, default='string', verbose_name="值类型",
                          constraints=[Check("value_type IN ('string', 'number', 'boolean', 'json', 'array')")])
    description = TextField(null=True, verbose_name="配置描述")
    is_encrypted = BooleanField(default=False, verbose_name="是否加密")
    is_public = BooleanField(default=False, verbose_name="是否公开")
    validation_rule = CharField(max_length=500, null=True, verbose_name="验证规则")
    default_value = TextField(null=True, verbose_name="默认值")
    is_active = BooleanField(default=True, verbose_name="是否有效")
    created_by = CharField(max_length=100, null=True, verbose_name="创建人")
    
    class Meta:
        table_name = 'system_configs'
        indexes = (
            (('config_category', 'config_key'), True),  # 联合唯一索引
            (('is_active',), False),
            (('is_public',), False),
        )
    
    def get_typed_value(self):
        """获取类型化的配置值"""
        if not self.config_value:
            return self.get_default_value()
        
        try:
            if self.value_type == 'boolean':
                return self.config_value.lower() in ('true', '1', 'yes', 'on')
            elif self.value_type == 'number':
                if '.' in self.config_value:
                    return float(self.config_value)
                else:
                    return int(self.config_value)
            elif self.value_type == 'json':
                return json.loads(self.config_value)
            elif self.value_type == 'array':
                return json.loads(self.config_value) if self.config_value.startswith('[') else self.config_value.split(',')
            else:  # string
                return self.config_value
        except (ValueError, json.JSONDecodeError):
            return self.get_default_value()
    
    def get_default_value(self):
        """获取默认值"""
        if not self.default_value:
            return None
        
        try:
            if self.value_type == 'boolean':
                return self.default_value.lower() in ('true', '1', 'yes', 'on')
            elif self.value_type == 'number':
                if '.' in self.default_value:
                    return float(self.default_value)
                else:
                    return int(self.default_value)
            elif self.value_type == 'json':
                return json.loads(self.default_value)
            elif self.value_type == 'array':
                return json.loads(self.default_value) if self.default_value.startswith('[') else self.default_value.split(',')
            else:  # string
                return self.default_value
        except (ValueError, json.JSONDecodeError):
            return self.default_value
    
    def set_typed_value(self, value):
        """设置类型化的配置值"""
        if value is None:
            self.config_value = None
            return
        
        if self.value_type == 'boolean':
            self.config_value = 'true' if value else 'false'
        elif self.value_type == 'number':
            self.config_value = str(value)
        elif self.value_type in ('json', 'array'):
            self.config_value = json.dumps(value, ensure_ascii=False)
        else:  # string
            self.config_value = str(value)
    
    def validate_value(self, value) -> tuple:
        """
        验证配置值
        
        Returns:
            tuple: (是否有效, 错误信息)
        """
        if self.validation_rule:
            # TODO: 实现验证规则检查
            pass
        
        # 基本类型验证
        try:
            if self.value_type == 'number':
                float(str(value))
            elif self.value_type == 'boolean':
                if str(value).lower() not in ('true', 'false', '1', '0', 'yes', 'no', 'on', 'off'):
                    return False, "布尔值格式不正确"
            elif self.value_type in ('json', 'array'):
                if isinstance(value, str):
                    json.loads(value)
        except (ValueError, json.JSONDecodeError) as e:
            return False, f"值格式不正确: {str(e)}"
        
        return True, ""
    
    def is_sensitive(self) -> bool:
        """判断是否为敏感配置"""
        return self.is_encrypted or 'password' in self.config_key.lower() or 'secret' in self.config_key.lower()
    
    @classmethod
    def get_by_category(cls, category: str):
        """获取指定分类的所有配置"""
        return cls.select().where(
            cls.config_category == category,
            cls.is_active == True
        ).order_by(cls.config_key)
    
    @classmethod
    def get_config(cls, category: str, key: str, default=None):
        """获取配置值"""
        try:
            config = cls.get(
                cls.config_category == category,
                cls.config_key == key,
                cls.is_active == True
            )
            return config.get_typed_value()
        except cls.DoesNotExist:
            return default
    
    @classmethod
    def set_config(cls, category: str, key: str, value, description: str = None, value_type: str = 'string'):
        """设置配置值"""
        config, _ = cls.get_or_create(
            config_category=category,
            config_key=key,
            defaults={
                'value_type': value_type,
                'description': description,
                'is_active': True
            }
        )
        
        config.set_typed_value(value)
        if description:
            config.description = description
        config.save()
        
        return config
    
    @classmethod
    def get_public_configs(cls):
        """获取所有公开配置"""
        return cls.select().where(
            cls.is_public == True,
            cls.is_active == True
        ).order_by(cls.config_category, cls.config_key)
    
    @classmethod
    def search_configs(cls, keyword: str):
        """搜索配置"""
        return cls.select().where(
            (cls.config_key.contains(keyword)) |
            (cls.description.contains(keyword)),
            cls.is_active == True
        )
    
    def __str__(self):
        return f"SystemConfig({self.config_category}.{self.config_key})"


class RagflowConfig(CommonModel):
    """RAG Flow集成配置表"""
    
    config_name = CharField(max_length=100, unique=True, verbose_name="配置名称")
    api_endpoint = CharField(max_length=500, verbose_name="API端点")
    api_key_encrypted = TextField(null=True, verbose_name="加密的API密钥")
    api_version = CharField(max_length=20, default='v1', verbose_name="API版本")
    timeout_seconds = IntegerField(default=30, verbose_name="超时秒数")
    max_retries = IntegerField(default=3, verbose_name="最大重试次数")
    rate_limit_per_minute = IntegerField(default=60, verbose_name="每分钟限制")
    connection_pool_size = IntegerField(default=10, verbose_name="连接池大小")
    health_check_interval = IntegerField(default=300, verbose_name="健康检查间隔(秒)")
    last_health_check = DateTimeField(null=True, verbose_name="最后健康检查时间")
    health_status = CharField(max_length=20, default='unknown', verbose_name="健康状态",
                             constraints=[Check("health_status IN ('healthy', 'unhealthy', 'unknown')")])
    config_metadata = JSONField(null=True, verbose_name="配置元数据")
    is_active = BooleanField(default=True, verbose_name="是否激活")
    
    class Meta:
        table_name = 'ragflow_configs'
        indexes = (
            (('config_name',), False),
            (('is_active',), False),
            (('health_status',), False),
            (('last_health_check',), False),
        )
    
    def get_config_metadata(self) -> dict:
        """获取配置元数据"""
        if self.config_metadata:
            return self.config_metadata if isinstance(self.config_metadata, dict) else {}
        return {}
    
    def set_config_metadata(self, metadata: dict):
        """设置配置元数据"""
        self.config_metadata = metadata
    
    def get_headers(self) -> dict:
        """从元数据中获取请求头"""
        metadata = self.get_config_metadata()
        return metadata.get('headers', {})
    
    def get_fallback_config(self) -> dict:
        """获取兜底配置"""
        metadata = self.get_config_metadata()
        return metadata.get('fallback_config', {})
    
    def get_health_check_url(self) -> str:
        """获取健康检查URL"""
        metadata = self.get_config_metadata()
        return metadata.get('health_check_url', '')
    
    def is_healthy(self) -> bool:
        """判断是否健康"""
        return self.health_status == 'healthy'
    
    def mark_healthy(self):
        """标记为健康"""
        from datetime import datetime
        self.health_status = 'healthy'
        self.last_health_check = datetime.now()
    
    def mark_unhealthy(self):
        """标记为不健康"""
        from datetime import datetime
        self.health_status = 'unhealthy'
        self.last_health_check = datetime.now()
    
    def needs_health_check(self) -> bool:
        """判断是否需要健康检查"""
        if not self.last_health_check:
            return True
        
        from datetime import datetime, timedelta
        check_interval = timedelta(seconds=self.health_check_interval)
        return datetime.now() - self.last_health_check > check_interval
    
    @classmethod
    def get_active_configs(cls):
        """获取所有激活的配置"""
        return cls.select().where(cls.is_active == True).order_by(cls.config_name)
    
    @classmethod
    def get_healthy_configs(cls):
        """获取所有健康的配置"""
        return cls.select().where(
            cls.is_active == True,
            cls.health_status == 'healthy'
        ).order_by(cls.config_name)
    
    @classmethod
    def get_primary_config(cls):
        """获取主要配置"""
        configs = cls.get_healthy_configs()
        return configs.first() if configs.exists() else None
    
    def __str__(self):
        return f"RagflowConfig({self.config_name}: {self.health_status})"