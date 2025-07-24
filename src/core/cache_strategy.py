"""
统一的缓存策略和命名规范
规范化缓存键命名、TTL策略、序列化方式等
"""
from typing import Dict, Any, Optional, Union, List
from enum import Enum
from datetime import timedelta
import hashlib
import json
import pickle
from dataclasses import dataclass

from src.utils.logger import get_logger

logger = get_logger(__name__)


class CacheNamespace(str, Enum):
    """缓存命名空间枚举"""
    # 核心业务
    INTENT = "intent"           # 意图识别相关
    CONVERSATION = "conv"       # 对话管理相关  
    SESSION = "sess"           # 会话状态相关
    USER = "user"              # 用户配置相关
    
    # 配置和元数据
    CONFIG = "cfg"             # 系统配置相关
    METADATA = "meta"          # 元数据相关
    SCHEMA = "schema"          # 数据结构定义
    
    # 统计和分析
    STATS = "stats"            # 统计数据相关
    ANALYTICS = "analytics"    # 分析数据相关
    MONITORING = "monitor"     # 监控数据相关
    
    # 外部服务
    EXTERNAL = "ext"           # 外部服务调用结果
    RAGFLOW = "ragflow"        # RAG流相关
    
    # 临时和计算
    TEMP = "temp"              # 临时数据
    COMPUTE = "compute"        # 计算结果缓存


class CacheTTL(int, Enum):
    """标准化TTL时间（秒）"""
    # 短期缓存 - 频繁变化的数据
    VERY_SHORT = 60         # 1分钟
    SHORT = 300             # 5分钟
    
    # 中期缓存 - 会话期间相对稳定的数据
    MEDIUM = 1800           # 30分钟
    LONG = 3600             # 1小时
    
    # 长期缓存 - 配置类不常变化的数据
    VERY_LONG = 14400       # 4小时
    PERSISTENT = 86400      # 24小时
    
    # 特殊用途
    SESSION_LIFETIME = 7200  # 2小时 - 会话生命周期
    CONFIG_CACHE = 21600    # 6小时 - 配置缓存
    TEMP_CALC = 900         # 15分钟 - 临时计算结果


class SerializationMethod(str, Enum):
    """序列化方法"""
    JSON = "json"           # JSON序列化，适合简单数据结构
    PICKLE = "pickle"       # Python pickle，适合复杂对象
    STRING = "string"       # 字符串存储，适合纯文本
    HASH = "hash"          # 哈希值存储，适合去重和索引


@dataclass
class CacheKeyTemplate:
    """缓存键模板定义"""
    namespace: CacheNamespace
    category: str
    pattern: str
    ttl: CacheTTL
    serialization: SerializationMethod
    description: str
    
    def generate_key(self, system_prefix: str = "intent_system", **kwargs) -> str:
        """生成具体的缓存键"""
        try:
            key = f"{system_prefix}:{self.namespace.value}:{self.category}:{self.pattern.format(**kwargs)}"
            return key
        except KeyError as e:
            raise ValueError(f"缓存键模板参数缺失: {e}")


class UnifiedCacheStrategy:
    """统一缓存策略管理器"""
    
    def __init__(self, system_prefix: str = "intent_system"):
        self.system_prefix = system_prefix
        self.logger = logger
        
        # 定义所有缓存键模板
        self.templates = {
            # === 意图识别相关 ===
            'intent_recognition': CacheKeyTemplate(
                namespace=CacheNamespace.INTENT,
                category="recognition",
                pattern="{input_hash}:{user_id}",
                ttl=CacheTTL.MEDIUM,
                serialization=SerializationMethod.JSON,
                description="意图识别结果缓存"
            ),
            
            'intent_recognition_with_history': CacheKeyTemplate(
                namespace=CacheNamespace.INTENT,
                category="recognition_hist",
                pattern="{input_hash}:{user_id}:{context_hash}",
                ttl=CacheTTL.MEDIUM,
                serialization=SerializationMethod.JSON,
                description="基于历史的意图识别结果"
            ),
            
            'intent_config': CacheKeyTemplate(
                namespace=CacheNamespace.INTENT,
                category="config",
                pattern="{intent_name}",
                ttl=CacheTTL.CONFIG_CACHE,
                serialization=SerializationMethod.JSON,
                description="意图配置信息"
            ),
            
            # === 会话管理相关 ===
            'session_basic': CacheKeyTemplate(
                namespace=CacheNamespace.SESSION,
                category="basic",
                pattern="{session_id}",
                ttl=CacheTTL.SESSION_LIFETIME,
                serialization=SerializationMethod.JSON,
                description="基础会话信息"
            ),
            
            'session_context': CacheKeyTemplate(
                namespace=CacheNamespace.SESSION,
                category="context",
                pattern="{session_id}",
                ttl=CacheTTL.SESSION_LIFETIME,
                serialization=SerializationMethod.JSON,
                description="完整会话上下文"
            ),
            
            'session_stack': CacheKeyTemplate(
                namespace=CacheNamespace.SESSION,
                category="stack",
                pattern="{session_id}",
                ttl=CacheTTL.SESSION_LIFETIME,
                serialization=SerializationMethod.JSON,
                description="会话意图栈"
            ),
            
            # === 对话历史相关 ===
            'conversation_history': CacheKeyTemplate(
                namespace=CacheNamespace.CONVERSATION,
                category="history",
                pattern="{session_id}:{limit}",
                ttl=CacheTTL.LONG,
                serialization=SerializationMethod.JSON,
                description="对话历史记录"
            ),
            
            'conversation_transfer_history': CacheKeyTemplate(
                namespace=CacheNamespace.CONVERSATION,
                category="transfer_hist",
                pattern="{session_id}:{limit}",
                ttl=CacheTTL.LONG,
                serialization=SerializationMethod.JSON,
                description="意图转移历史"
            ),
            
            # === 用户相关 ===
            'user_profile': CacheKeyTemplate(
                namespace=CacheNamespace.USER,
                category="profile",
                pattern="{user_id}",
                ttl=CacheTTL.VERY_LONG,
                serialization=SerializationMethod.JSON,
                description="用户配置文件"
            ),
            
            'user_preferences': CacheKeyTemplate(
                namespace=CacheNamespace.USER,
                category="preferences",
                pattern="{user_id}",
                ttl=CacheTTL.PERSISTENT,
                serialization=SerializationMethod.JSON,
                description="用户偏好设置"
            ),
            
            # === 槽位相关 ===
            'slot_definitions': CacheKeyTemplate(
                namespace=CacheNamespace.METADATA,
                category="slot_def",
                pattern="{intent_name}",
                ttl=CacheTTL.CONFIG_CACHE,
                serialization=SerializationMethod.JSON,
                description="槽位定义"
            ),
            
            'slot_dependencies': CacheKeyTemplate(
                namespace=CacheNamespace.METADATA,
                category="slot_deps",
                pattern="{intent_id}",
                ttl=CacheTTL.CONFIG_CACHE,
                serialization=SerializationMethod.JSON,
                description="槽位依赖关系"
            ),
            
            'slot_values': CacheKeyTemplate(
                namespace=CacheNamespace.SESSION,
                category="slot_values",
                pattern="{session_id}:{intent_name}",
                ttl=CacheTTL.SESSION_LIFETIME,
                serialization=SerializationMethod.JSON,
                description="会话槽位值"
            ),
            
            # === 函数调用相关 ===
            'function_definition': CacheKeyTemplate(
                namespace=CacheNamespace.METADATA,
                category="func_def",
                pattern="{function_name}",
                ttl=CacheTTL.CONFIG_CACHE,
                serialization=SerializationMethod.JSON,
                description="函数定义"
            ),
            
            'function_parameters': CacheKeyTemplate(
                namespace=CacheNamespace.METADATA,
                category="func_params",
                pattern="{function_name}",
                ttl=CacheTTL.CONFIG_CACHE,
                serialization=SerializationMethod.JSON,
                description="函数参数模式"
            ),
            
            # === 配置相关 ===
            'system_config': CacheKeyTemplate(
                namespace=CacheNamespace.CONFIG,
                category="system",
                pattern="{config_key}",
                ttl=CacheTTL.CONFIG_CACHE,
                serialization=SerializationMethod.JSON,
                description="系统配置项"
            ),
            
            'ragflow_config': CacheKeyTemplate(
                namespace=CacheNamespace.RAGFLOW,
                category="config",
                pattern="{config_name}",
                ttl=CacheTTL.CONFIG_CACHE,
                serialization=SerializationMethod.JSON,
                description="RAGFlow配置"
            ),
            
            # === 统计分析相关 ===
            'stats_session': CacheKeyTemplate(
                namespace=CacheNamespace.STATS,
                category="session",
                pattern="{user_id}",
                ttl=CacheTTL.LONG,
                serialization=SerializationMethod.JSON,
                description="会话统计数据"
            ),
            
            'analytics_intent_usage': CacheKeyTemplate(
                namespace=CacheNamespace.ANALYTICS,
                category="intent_usage",
                pattern="{time_period}",
                ttl=CacheTTL.LONG,
                serialization=SerializationMethod.JSON,
                description="意图使用分析"
            ),
            
            # === 外部服务相关 ===
            'external_api_response': CacheKeyTemplate(
                namespace=CacheNamespace.EXTERNAL,
                category="api_resp",
                pattern="{service_name}:{request_hash}",
                ttl=CacheTTL.MEDIUM,
                serialization=SerializationMethod.JSON,
                description="外部API响应缓存"
            ),
            
            # === 限流相关 ===
            'rate_limit': CacheKeyTemplate(
                namespace=CacheNamespace.TEMP,
                category="rate_limit",
                pattern="{identifier}:{window}",
                ttl=CacheTTL.SHORT,
                serialization=SerializationMethod.STRING,
                description="限流计数器"
            ),
            
            # === 临时计算结果 ===
            'computation_result': CacheKeyTemplate(
                namespace=CacheNamespace.COMPUTE,
                category="result",
                pattern="{computation_hash}",
                ttl=CacheTTL.TEMP_CALC,
                serialization=SerializationMethod.PICKLE,
                description="计算结果缓存"
            ),
        }
    
    def get_cache_key(self, template_name: str, **kwargs) -> str:
        """
        生成标准化缓存键
        
        Args:
            template_name: 模板名称
            **kwargs: 模板参数
            
        Returns:
            str: 标准化的缓存键
        """
        if template_name not in self.templates:
            raise ValueError(f"未知的缓存键模板: {template_name}")
        
        template = self.templates[template_name]
        return template.generate_key(self.system_prefix, **kwargs)
    
    def get_ttl(self, template_name: str) -> int:
        """获取模板对应的TTL"""
        if template_name not in self.templates:
            raise ValueError(f"未知的缓存键模板: {template_name}")
        
        return self.templates[template_name].ttl.value
    
    def get_serialization_method(self, template_name: str) -> SerializationMethod:
        """获取模板对应的序列化方法"""
        if template_name not in self.templates:
            raise ValueError(f"未知的缓存键模板: {template_name}")
        
        return self.templates[template_name].serialization
    
    def serialize_data(self, data: Any, method: SerializationMethod) -> Union[str, bytes]:
        """根据序列化方法序列化数据"""
        try:
            if method == SerializationMethod.JSON:
                return json.dumps(data, ensure_ascii=False, default=str)
            elif method == SerializationMethod.PICKLE:
                return pickle.dumps(data)
            elif method == SerializationMethod.STRING:
                return str(data)
            elif method == SerializationMethod.HASH:
                return hashlib.md5(str(data).encode()).hexdigest()
            else:
                raise ValueError(f"不支持的序列化方法: {method}")
        except Exception as e:
            self.logger.error(f"数据序列化失败: {e}")
            raise
    
    def deserialize_data(self, data: Union[str, bytes], method: SerializationMethod) -> Any:
        """根据序列化方法反序列化数据"""
        try:
            if method == SerializationMethod.JSON:
                return json.loads(data) if isinstance(data, str) else json.loads(data.decode())
            elif method == SerializationMethod.PICKLE:
                return pickle.loads(data) if isinstance(data, bytes) else pickle.loads(data.encode())
            elif method == SerializationMethod.STRING:
                return str(data)
            elif method == SerializationMethod.HASH:
                return data  # 哈希值直接返回
            else:
                raise ValueError(f"不支持的反序列化方法: {method}")
        except Exception as e:
            self.logger.warning(f"数据反序列化失败: {e}, 返回原始数据")
            return data
    
    def generate_hash(self, *args) -> str:
        """生成数据哈希值"""
        content = "|".join(str(arg) for arg in args)
        return hashlib.md5(content.encode()).hexdigest()[:16]  # 取前16位
    
    def validate_template_params(self, template_name: str, **kwargs) -> bool:
        """验证模板参数是否完整"""
        if template_name not in self.templates:
            return False
        
        template = self.templates[template_name]
        try:
            # 尝试格式化模板以验证参数
            template.pattern.format(**kwargs)
            return True
        except KeyError:
            return False
    
    def get_template_info(self, template_name: str) -> Dict[str, Any]:
        """获取模板详细信息"""
        if template_name not in self.templates:
            raise ValueError(f"未知的缓存键模板: {template_name}")
        
        template = self.templates[template_name]
        return {
            "namespace": template.namespace.value,
            "category": template.category,
            "pattern": template.pattern,
            "ttl_seconds": template.ttl.value,
            "serialization": template.serialization.value,
            "description": template.description
        }
    
    def list_all_templates(self) -> Dict[str, Dict[str, Any]]:
        """列出所有缓存模板"""
        return {
            name: self.get_template_info(name) 
            for name in self.templates.keys()
        }
    
    def get_templates_by_namespace(self, namespace: CacheNamespace) -> List[str]:
        """根据命名空间获取模板列表"""
        return [
            name for name, template in self.templates.items()
            if template.namespace == namespace
        ]


# 全局缓存策略实例
_cache_strategy = UnifiedCacheStrategy()


def get_cache_strategy() -> UnifiedCacheStrategy:
    """获取全局缓存策略实例"""
    return _cache_strategy


def generate_cache_key(template_name: str, **kwargs) -> str:
    """便捷函数：生成缓存键"""
    return _cache_strategy.get_cache_key(template_name, **kwargs)


def get_cache_ttl(template_name: str) -> int:
    """便捷函数：获取TTL"""
    return _cache_strategy.get_ttl(template_name)


def serialize_cache_data(data: Any, template_name: str) -> Union[str, bytes]:
    """便捷函数：序列化缓存数据"""
    method = _cache_strategy.get_serialization_method(template_name)
    return _cache_strategy.serialize_data(data, method)


def deserialize_cache_data(data: Union[str, bytes], template_name: str) -> Any:
    """便捷函数：反序列化缓存数据"""
    method = _cache_strategy.get_serialization_method(template_name)
    return _cache_strategy.deserialize_data(data, method)


# 导出常用枚举和类
__all__ = [
    'UnifiedCacheStrategy',
    'CacheNamespace', 
    'CacheTTL',
    'SerializationMethod',
    'get_cache_strategy',
    'generate_cache_key',
    'get_cache_ttl',
    'serialize_cache_data',
    'deserialize_cache_data'
]