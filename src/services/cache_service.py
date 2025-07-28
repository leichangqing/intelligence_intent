"""
Redis缓存服务
"""
import json
import asyncio
from typing import Any, Optional, Dict, List, Union
import redis.asyncio as redis
from redis.asyncio import ConnectionPool
import pickle
import hashlib
from datetime import datetime, timedelta

from src.config.settings import settings
from src.core.cache_strategy import get_cache_strategy, UnifiedCacheStrategy
from src.utils.logger import get_logger

logger = get_logger(__name__)


class CacheService:
    """Redis缓存服务类"""
    
    def __init__(self):
        self.redis_client: Optional[redis.Redis] = None
        self.connection_pool: Optional[ConnectionPool] = None
        self._initialized = False
        self.default_namespace = "intent_system"
        
        # 使用统一的缓存策略
        self.cache_strategy = get_cache_strategy()
        
        # 保持向后兼容的模板字典（废弃，将逐步移除）
        self.CACHE_KEY_TEMPLATES = {
            template_name: template_info["pattern"] 
            for template_name, template_info in self.cache_strategy.list_all_templates().items()
        }
    
    def get_cache_key(self, template_name: str, **kwargs) -> str:
        """
        生成统一格式的缓存键
        
        Args:
            template_name: 模板名称
            **kwargs: 模板参数
            
        Returns:
            str: 格式化的缓存键
        """
        return self.cache_strategy.get_cache_key(template_name, **kwargs)
    
    async def initialize(self):
        """初始化Redis连接"""
        try:
            # 创建连接池
            self.connection_pool = ConnectionPool(
                host=settings.REDIS_HOST,
                port=settings.REDIS_PORT,
                db=settings.REDIS_DB,
                password=settings.REDIS_PASSWORD,
                encoding='utf-8',
                decode_responses=False,  # 用于支持二进制数据
                max_connections=20,
                retry_on_timeout=True
            )
            
            # 创建Redis客户端
            self.redis_client = redis.Redis(connection_pool=self.connection_pool)
            
            # 测试连接
            await self.redis_client.ping()
            
            self._initialized = True
            logger.info("Redis缓存服务初始化成功")
            
        except Exception as e:
            logger.error(f"Redis缓存服务初始化失败: {str(e)}")
            raise
    
    async def close(self):
        """关闭Redis连接"""
        if self.redis_client:
            await self.redis_client.close()
        if self.connection_pool:
            await self.connection_pool.disconnect()
        
        self._initialized = False
        logger.info("Redis连接已关闭")
    
    def _ensure_initialized(self):
        """确保服务已初始化"""
        if not self._initialized or not self.redis_client:
            raise RuntimeError("Redis缓存服务未初始化")
    
    def _generate_key(self, key: str, namespace: str = "intent_system") -> str:
        """生成带命名空间的缓存键"""
        return f"{namespace}:{key}"
    
    def _serialize_data(self, data: Any, method=None) -> bytes:
        """序列化数据"""
        try:
            if method is None:
                # 兼容性默认行为
                if isinstance(data, (str, int, float, bool)):
                    return json.dumps(data).encode('utf-8')
                else:
                    return pickle.dumps(data)
            else:
                # 使用统一的序列化策略
                result = self.cache_strategy.serialize_data(data, method)
                return result.encode('utf-8') if isinstance(result, str) else result
        except Exception as e:
            logger.warning(f"数据序列化失败: {str(e)}")
            return pickle.dumps(data)
    
    def _deserialize_data(self, data: bytes, method=None) -> Any:
        """反序列化数据"""
        try:
            if method is None:
                # 兼容性默认行为
                try:
                    return json.loads(data.decode('utf-8'))
                except (json.JSONDecodeError, UnicodeDecodeError):
                    return pickle.loads(data)
            else:
                # 使用统一的反序列化策略
                return self.cache_strategy.deserialize_data(data, method)
        except Exception as e:
            logger.warning(f"数据反序列化失败: {str(e)}")
            return None
    
    async def set(self, key: str, value: Any, ttl: Optional[int] = None, 
                  namespace: str = "intent_system") -> bool:
        """
        设置缓存值
        
        Args:
            key: 缓存键
            value: 缓存值
            ttl: 过期时间（秒），None表示永不过期
            namespace: 命名空间
            
        Returns:
            bool: 是否设置成功
        """
        self._ensure_initialized()
        
        try:
            cache_key = self._generate_key(key, namespace)
            serialized_data = self._serialize_data(value)
            
            if ttl:
                result = await self.redis_client.setex(cache_key, ttl, serialized_data)
            else:
                result = await self.redis_client.set(cache_key, serialized_data)
            
            logger.debug(f"缓存设置: {cache_key}, TTL: {ttl}")
            return bool(result)
            
        except Exception as e:
            logger.error(f"设置缓存失败: {key}, 错误: {str(e)}")
            return False
    
    async def get(self, key: str, namespace: str = "intent_system") -> Optional[Any]:
        """
        获取缓存值
        
        Args:
            key: 缓存键
            namespace: 命名空间
            
        Returns:
            Any: 缓存值，不存在时返回None
        """
        self._ensure_initialized()
        
        try:
            cache_key = self._generate_key(key, namespace)
            cached_data = await self.redis_client.get(cache_key)
            
            if cached_data is None:
                logger.debug(f"缓存未命中: {cache_key}")
                return None
            
            deserialized_data = self._deserialize_data(cached_data)
            logger.debug(f"缓存命中: {cache_key}")
            return deserialized_data
            
        except Exception as e:
            logger.error(f"获取缓存失败: {key}, 错误: {str(e)}")
            return None
    
    async def delete(self, key: str, namespace: str = "intent_system") -> bool:
        """
        删除缓存
        
        Args:
            key: 缓存键
            namespace: 命名空间
            
        Returns:
            bool: 是否删除成功
        """
        self._ensure_initialized()
        
        try:
            cache_key = self._generate_key(key, namespace)
            result = await self.redis_client.delete(cache_key)
            
            logger.debug(f"缓存删除: {cache_key}")
            return bool(result)
            
        except Exception as e:
            logger.error(f"删除缓存失败: {key}, 错误: {str(e)}")
            return False
    
    async def exists(self, key: str, namespace: str = "intent_system") -> bool:
        """
        检查缓存是否存在
        
        Args:
            key: 缓存键
            namespace: 命名空间
            
        Returns:
            bool: 是否存在
        """
        self._ensure_initialized()
        
        try:
            cache_key = self._generate_key(key, namespace)
            result = await self.redis_client.exists(cache_key)
            return bool(result)
            
        except Exception as e:
            logger.error(f"检查缓存存在性失败: {key}, 错误: {str(e)}")
            return False
    
    async def expire(self, key: str, ttl: int, namespace: str = "intent_system") -> bool:
        """
        设置缓存过期时间
        
        Args:
            key: 缓存键
            ttl: 过期时间（秒）
            namespace: 命名空间
            
        Returns:
            bool: 是否设置成功
        """
        self._ensure_initialized()
        
        try:
            cache_key = self._generate_key(key, namespace)
            result = await self.redis_client.expire(cache_key, ttl)
            
            logger.debug(f"设置缓存过期时间: {cache_key}, TTL: {ttl}")
            return bool(result)
            
        except Exception as e:
            logger.error(f"设置缓存过期时间失败: {key}, 错误: {str(e)}")
            return False
    
    async def get_ttl(self, key: str, namespace: str = "intent_system") -> int:
        """
        获取缓存剩余过期时间
        
        Args:
            key: 缓存键
            namespace: 命名空间
            
        Returns:
            int: 剩余时间（秒），-1表示永不过期，-2表示不存在
        """
        self._ensure_initialized()
        
        try:
            cache_key = self._generate_key(key, namespace)
            ttl = await self.redis_client.ttl(cache_key)
            return ttl
            
        except Exception as e:
            logger.error(f"获取缓存TTL失败: {key}, 错误: {str(e)}")
            return -2
    
    async def increment(self, key: str, amount: int = 1, 
                       namespace: str = "intent_system") -> Optional[int]:
        """
        原子递增操作
        
        Args:
            key: 缓存键
            amount: 递增量
            namespace: 命名空间
            
        Returns:
            int: 递增后的值
        """
        self._ensure_initialized()
        
        try:
            cache_key = self._generate_key(key, namespace)
            result = await self.redis_client.incrby(cache_key, amount)
            
            logger.debug(f"缓存递增: {cache_key}, 增量: {amount}, 结果: {result}")
            return result
            
        except Exception as e:
            logger.error(f"缓存递增失败: {key}, 错误: {str(e)}")
            return None
    
    async def get_keys_by_pattern(self, pattern: str, 
                                namespace: str = "intent_system") -> List[str]:
        """
        根据模式获取键列表
        
        Args:
            pattern: 键模式
            namespace: 命名空间
            
        Returns:
            List[str]: 匹配的键列表
        """
        self._ensure_initialized()
        
        try:
            search_pattern = self._generate_key(pattern, namespace)
            keys = await self.redis_client.keys(search_pattern)
            
            # 移除命名空间前缀
            namespace_prefix = f"{namespace}:"
            cleaned_keys = [
                key.decode('utf-8').replace(namespace_prefix, '') 
                for key in keys
            ]
            
            return cleaned_keys
            
        except Exception as e:
            logger.error(f"根据模式获取键失败: {pattern}, 错误: {str(e)}")
            return []
    
    async def delete_by_pattern(self, pattern: str, 
                              namespace: str = "intent_system") -> int:
        """
        根据模式删除缓存
        
        Args:
            pattern: 键模式
            namespace: 命名空间
            
        Returns:
            int: 删除的键数量
        """
        self._ensure_initialized()
        
        try:
            search_pattern = self._generate_key(pattern, namespace)
            keys = await self.redis_client.keys(search_pattern)
            
            if keys:
                deleted_count = await self.redis_client.delete(*keys)
                logger.debug(f"批量删除缓存: {len(keys)}个键")
                return deleted_count
            
            return 0
            
        except Exception as e:
            logger.error(f"根据模式删除缓存失败: {pattern}, 错误: {str(e)}")
            return 0
    
    async def set_hash(self, key: str, field: str, value: Any, 
                      namespace: str = "intent_system") -> bool:
        """
        设置哈希字段
        
        Args:
            key: 哈希键
            field: 字段名
            value: 字段值
            namespace: 命名空间
            
        Returns:
            bool: 是否设置成功
        """
        self._ensure_initialized()
        
        try:
            cache_key = self._generate_key(key, namespace)
            serialized_data = self._serialize_data(value)
            
            result = await self.redis_client.hset(cache_key, field, serialized_data)
            logger.debug(f"哈希字段设置: {cache_key}.{field}")
            return bool(result)
            
        except Exception as e:
            logger.error(f"设置哈希字段失败: {key}.{field}, 错误: {str(e)}")
            return False
    
    async def get_hash(self, key: str, field: str, 
                      namespace: str = "intent_system") -> Optional[Any]:
        """
        获取哈希字段值
        
        Args:
            key: 哈希键
            field: 字段名
            namespace: 命名空间
            
        Returns:
            Any: 字段值
        """
        self._ensure_initialized()
        
        try:
            cache_key = self._generate_key(key, namespace)
            cached_data = await self.redis_client.hget(cache_key, field)
            
            if cached_data is None:
                return None
            
            return self._deserialize_data(cached_data)
            
        except Exception as e:
            logger.error(f"获取哈希字段失败: {key}.{field}, 错误: {str(e)}")
            return None
    
    async def get_all_hash(self, key: str, 
                          namespace: str = "intent_system") -> Dict[str, Any]:
        """
        获取所有哈希字段
        
        Args:
            key: 哈希键
            namespace: 命名空间
            
        Returns:
            Dict[str, Any]: 所有字段的字典
        """
        self._ensure_initialized()
        
        try:
            cache_key = self._generate_key(key, namespace)
            hash_data = await self.redis_client.hgetall(cache_key)
            
            result = {}
            for field, value in hash_data.items():
                field_name = field.decode('utf-8')
                result[field_name] = self._deserialize_data(value)
            
            return result
            
        except Exception as e:
            logger.error(f"获取所有哈希字段失败: {key}, 错误: {str(e)}")
            return {}
    
    async def cache_intent_config(self, intent_name: str, config_data: Dict) -> bool:
        """
        缓存意图配置
        
        Args:
            intent_name: 意图名称
            config_data: 配置数据
            
        Returns:
            bool: 是否缓存成功
        """
        cache_key = self.get_cache_key("intent_config", intent_name=intent_name)
        ttl = self.cache_strategy.get_ttl("intent_config")
        return await self.set(cache_key, config_data, ttl=ttl)
    
    async def get_intent_config(self, intent_name: str) -> Optional[Dict]:
        """
        获取意图配置缓存
        
        Args:
            intent_name: 意图名称
            
        Returns:
            Dict: 配置数据
        """
        cache_key = self.get_cache_key("intent_config", intent_name=intent_name)
        return await self.get(cache_key)
    
    async def cache_nlu_result(self, input_hash: str, result_data: Dict, user_id: str = "") -> bool:
        """
        缓存NLU识别结果
        
        Args:
            input_hash: 输入文本的哈希值
            result_data: 识别结果
            user_id: 用户ID（可选）
            
        Returns:
            bool: 是否缓存成功
        """
        cache_key = self.get_cache_key("intent_recognition", input_hash=input_hash, user_id=user_id or "anonymous")
        ttl = self.cache_strategy.get_ttl("intent_recognition")
        return await self.set(cache_key, result_data, ttl=ttl)
    
    async def get_nlu_result(self, input_hash: str, user_id: str = "") -> Optional[Dict]:
        """
        获取NLU识别结果缓存
        
        Args:
            input_hash: 输入文本的哈希值
            user_id: 用户ID（可选）
            
        Returns:
            Dict: 识别结果
        """
        cache_key = self.get_cache_key("intent_recognition", input_hash=input_hash, user_id=user_id or "anonymous")
        return await self.get(cache_key)
    
    async def cache_session_context(self, session_id: str, context_data: Dict) -> bool:
        """
        缓存会话上下文
        
        Args:
            session_id: 会话ID
            context_data: 上下文数据
            
        Returns:
            bool: 是否缓存成功
        """
        cache_key = self.get_cache_key("session_context", session_id=session_id)
        ttl = self.cache_strategy.get_ttl("session_context")
        return await self.set(cache_key, context_data, ttl=ttl)
    
    async def get_session_context(self, session_id: str) -> Optional[Dict]:
        """
        获取会话上下文缓存
        
        Args:
            session_id: 会话ID
            
        Returns:
            Dict: 上下文数据
        """
        cache_key = self.get_cache_key("session_context", session_id=session_id)
        return await self.get(cache_key)
    
    async def get_cache_stats(self) -> Dict[str, Any]:
        """
        获取缓存统计信息
        
        Returns:
            Dict: 统计信息
        """
        self._ensure_initialized()
        
        try:
            info = await self.redis_client.info()
            
            stats = {
                "redis_version": info.get("redis_version"),
                "used_memory": info.get("used_memory_human"),
                "used_memory_peak": info.get("used_memory_peak_human"),
                "connected_clients": info.get("connected_clients"),
                "total_commands_processed": info.get("total_commands_processed"),
                "keyspace_hits": info.get("keyspace_hits", 0),
                "keyspace_misses": info.get("keyspace_misses", 0),
                "expired_keys": info.get("expired_keys", 0),
                "evicted_keys": info.get("evicted_keys", 0)
            }
            
            # 计算命中率
            hits = stats["keyspace_hits"]
            misses = stats["keyspace_misses"]
            total_requests = hits + misses
            
            if total_requests > 0:
                stats["hit_rate"] = round(hits / total_requests, 4)
            else:
                stats["hit_rate"] = 0.0
            
            return stats
            
        except Exception as e:
            logger.error(f"获取缓存统计信息失败: {str(e)}")
            return {}
    
    async def clear_cache_namespace(self, namespace: str = "intent_system") -> int:
        """
        清空指定命名空间的所有缓存
        
        Args:
            namespace: 命名空间
            
        Returns:
            int: 删除的键数量
        """
        pattern = f"{namespace}:*"
        return await self.delete_by_pattern(pattern, "")
    
    def generate_input_hash(self, user_input: str, user_id: str = "") -> str:
        """
        生成用户输入的哈希值（用于缓存NLU结果）
        
        Args:
            user_input: 用户输入
            user_id: 用户ID（可选）
            
        Returns:
            str: 哈希值
        """
        return self.cache_strategy.generate_hash(user_input, user_id)
    
    async def cache_conversation_history(self, session_id: str, history_data: List[Dict], limit: int = 50) -> bool:
        """
        缓存对话历史
        
        Args:
            session_id: 会话ID
            history_data: 历史对话数据
            limit: 历史记录限制数
            
        Returns:
            bool: 是否缓存成功
        """
        cache_key = self.get_cache_key("conversation_history", session_id=session_id, limit=limit)
        ttl = self.cache_strategy.get_ttl("conversation_history")
        return await self.set(cache_key, history_data, ttl=ttl)
    
    async def get_conversation_history(self, session_id: str, limit: int = 50) -> Optional[List[Dict]]:
        """
        获取对话历史缓存
        
        Args:
            session_id: 会话ID
            limit: 历史记录限制数
            
        Returns:
            List[Dict]: 历史对话数据
        """
        cache_key = self.get_cache_key("conversation_history", session_id=session_id, limit=limit)
        return await self.get(cache_key)
    
    async def cache_slot_values(self, session_id: str, intent_name: str, slot_values: Dict) -> bool:
        """
        缓存会话槽位值
        
        Args:
            session_id: 会话ID
            intent_name: 意图名称
            slot_values: 槽位值数据
            
        Returns:
            bool: 是否缓存成功
        """
        cache_key = self.get_cache_key("slot_values", session_id=session_id, intent_name=intent_name)
        ttl = self.cache_strategy.get_ttl("slot_values")
        return await self.set(cache_key, slot_values, ttl=ttl)
    
    async def get_slot_values(self, session_id: str, intent_name: str) -> Optional[Dict]:
        """
        获取会话槽位值缓存
        
        Args:
            session_id: 会话ID
            intent_name: 意图名称
            
        Returns:
            Dict: 槽位值数据
        """
        cache_key = self.get_cache_key("slot_values", session_id=session_id, intent_name=intent_name)
        return await self.get(cache_key)
    
    async def cache_user_profile(self, user_id: str, profile_data: Dict) -> bool:
        """
        缓存用户配置文件
        
        Args:
            user_id: 用户ID
            profile_data: 用户配置数据
            
        Returns:
            bool: 是否缓存成功
        """
        cache_key = self.get_cache_key("user_profile", user_id=user_id)
        ttl = self.cache_strategy.get_ttl("user_profile")
        return await self.set(cache_key, profile_data, ttl=ttl)
    
    async def get_user_profile(self, user_id: str) -> Optional[Dict]:
        """
        获取用户配置文件缓存
        
        Args:
            user_id: 用户ID
            
        Returns:
            Dict: 用户配置数据
        """
        cache_key = self.get_cache_key("user_profile", user_id=user_id)
        return await self.get(cache_key)


# 全局缓存服务实例
_cache_service: Optional[CacheService] = None


async def get_cache_service() -> CacheService:
    """获取缓存服务实例（依赖注入）"""
    global _cache_service
    
    if _cache_service is None:
        _cache_service = CacheService()
        await _cache_service.initialize()
    
    return _cache_service


# 同步访问的缓存服务实例（向后兼容）
cache_service: Optional[CacheService] = None