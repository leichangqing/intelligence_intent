"""
槽位继承缓存管理器
优化继承系统的性能和缓存策略
"""

from typing import Dict, List, Optional, Any, Set
from dataclasses import dataclass
from datetime import datetime, timedelta
import json
import hashlib

from ..services.cache_service import CacheService
from ..utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class InheritanceCacheKey:
    """继承缓存键"""
    user_id: str
    intent_id: int
    slot_names: List[str]
    context_hash: str
    
    def to_string(self) -> str:
        """转换为缓存键字符串"""
        slot_names_str = ",".join(sorted(self.slot_names))
        return f"inheritance:{self.user_id}:{self.intent_id}:{slot_names_str}:{self.context_hash}"


@dataclass
class CachedInheritanceResult:
    """缓存的继承结果"""
    inherited_values: Dict[str, Any]
    inheritance_sources: Dict[str, str]
    cached_at: datetime
    ttl_seconds: int
    
    def is_expired(self) -> bool:
        """检查是否过期"""
        return datetime.now() > self.cached_at + timedelta(seconds=self.ttl_seconds)
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "inherited_values": self.inherited_values,
            "inheritance_sources": self.inheritance_sources,
            "cached_at": self.cached_at.isoformat(),
            "ttl_seconds": self.ttl_seconds
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'CachedInheritanceResult':
        """从字典创建实例"""
        return cls(
            inherited_values=data["inherited_values"],
            inheritance_sources=data["inheritance_sources"],
            cached_at=datetime.fromisoformat(data["cached_at"]),
            ttl_seconds=data["ttl_seconds"]
        )


class InheritanceCacheManager:
    """继承缓存管理器"""
    
    def __init__(self, cache_service: CacheService):
        self.cache_service = cache_service
        self.default_ttl = 1800  # 30分钟默认TTL
        self.max_cache_size = 10000  # 最大缓存条目数
        self.cache_hit_stats = {"hits": 0, "misses": 0}
    
    def _generate_context_hash(self, context: Dict[str, Any]) -> str:
        """生成上下文哈希"""
        try:
            # 只包含影响继承的关键上下文信息
            relevant_context = {
                "current_values": context.get("current_values", {}),
                "user_profile_timestamp": context.get("user_profile", {}).get("last_updated"),
                "session_context_keys": list(context.get("session_context", {}).keys()),
                "conversation_context_keys": list(context.get("conversation_context", {}).keys())
            }
            
            context_str = json.dumps(relevant_context, sort_keys=True, ensure_ascii=False)
            return hashlib.md5(context_str.encode()).hexdigest()[:16]
            
        except Exception as e:
            logger.warning(f"生成上下文哈希失败: {e}")
            return "unknown"
    
    def _create_cache_key(self, user_id: str, intent_id: int, 
                         slot_names: List[str], context: Dict[str, Any]) -> InheritanceCacheKey:
        """创建缓存键"""
        context_hash = self._generate_context_hash(context)
        return InheritanceCacheKey(
            user_id=user_id,
            intent_id=intent_id,
            slot_names=slot_names,
            context_hash=context_hash
        )
    
    async def get_cached_inheritance(self, user_id: str, intent_id: int,
                                   slot_names: List[str], context: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """获取缓存的继承结果"""
        try:
            cache_key = self._create_cache_key(user_id, intent_id, slot_names, context)
            cache_key_str = cache_key.to_string()
            
            cached_data = await self.cache_service.get(cache_key_str)
            if not cached_data:
                self.cache_hit_stats["misses"] += 1
                return None
            
            if isinstance(cached_data, str):
                cached_data = json.loads(cached_data)
            
            cached_result = CachedInheritanceResult.from_dict(cached_data)
            
            # 检查是否过期
            if cached_result.is_expired():
                await self.cache_service.delete(cache_key_str)
                self.cache_hit_stats["misses"] += 1
                return None
            
            self.cache_hit_stats["hits"] += 1
            logger.debug(f"继承缓存命中: {cache_key_str}")
            
            return {
                "inherited_values": cached_result.inherited_values,
                "inheritance_sources": cached_result.inheritance_sources
            }
            
        except Exception as e:
            logger.error(f"获取继承缓存失败: {e}")
            return None
    
    async def cache_inheritance_result(self, user_id: str, intent_id: int,
                                     slot_names: List[str], context: Dict[str, Any],
                                     inherited_values: Dict[str, Any],
                                     inheritance_sources: Dict[str, str],
                                     ttl_seconds: Optional[int] = None) -> bool:
        """缓存继承结果"""
        try:
            cache_key = self._create_cache_key(user_id, intent_id, slot_names, context)
            cache_key_str = cache_key.to_string()
            
            ttl = ttl_seconds or self.default_ttl
            
            cached_result = CachedInheritanceResult(
                inherited_values=inherited_values,
                inheritance_sources=inheritance_sources,
                cached_at=datetime.now(),
                ttl_seconds=ttl
            )
            
            # 缓存数据
            await self.cache_service.set(
                cache_key_str,
                cached_result.to_dict(),
                ttl=ttl
            )
            
            logger.debug(f"继承结果已缓存: {cache_key_str}")
            return True
            
        except Exception as e:
            logger.error(f"缓存继承结果失败: {e}")
            return False
    
    async def invalidate_user_inheritance_cache(self, user_id: str):
        """使用户的所有继承缓存失效"""
        try:
            # 使用模式匹配删除用户相关的缓存
            pattern = f"inheritance:{user_id}:*"
            
            # 注意：这需要Redis支持，如果使用其他缓存可能需要调整
            if hasattr(self.cache_service, 'delete_pattern'):
                deleted_count = await self.cache_service.delete_pattern(pattern)
                logger.info(f"清除用户继承缓存: {user_id}, 删除{deleted_count}个条目")
            else:
                logger.warning("缓存服务不支持模式删除，无法批量清除用户缓存")
            
        except Exception as e:
            logger.error(f"清除用户继承缓存失败: {user_id}, 错误: {e}")
    
    async def invalidate_intent_inheritance_cache(self, intent_id: int):
        """使意图的所有继承缓存失效"""
        try:
            pattern = f"inheritance:*:{intent_id}:*"
            
            if hasattr(self.cache_service, 'delete_pattern'):
                deleted_count = await self.cache_service.delete_pattern(pattern)
                logger.info(f"清除意图继承缓存: {intent_id}, 删除{deleted_count}个条目")
            
        except Exception as e:
            logger.error(f"清除意图继承缓存失败: {intent_id}, 错误: {e}")
    
    async def get_cache_statistics(self) -> Dict[str, Any]:
        """获取缓存统计信息"""
        try:
            total_requests = self.cache_hit_stats["hits"] + self.cache_hit_stats["misses"]
            hit_rate = self.cache_hit_stats["hits"] / total_requests if total_requests > 0 else 0
            
            # 获取缓存使用情况
            cache_info = {}
            if hasattr(self.cache_service, 'get_cache_info'):
                cache_info = await self.cache_service.get_cache_info()
            
            return {
                "hit_rate": hit_rate,
                "total_hits": self.cache_hit_stats["hits"],
                "total_misses": self.cache_hit_stats["misses"],
                "total_requests": total_requests,
                "cache_info": cache_info
            }
            
        except Exception as e:
            logger.error(f"获取缓存统计失败: {e}")
            return {}
    
    async def optimize_cache_performance(self):
        """优化缓存性能"""
        try:
            # 清理过期缓存条目
            if hasattr(self.cache_service, 'cleanup_expired'):
                cleaned_count = await self.cache_service.cleanup_expired()
                logger.info(f"清理过期缓存条目: {cleaned_count}个")
            
            # 检查缓存大小
            if hasattr(self.cache_service, 'get_cache_size'):
                cache_size = await self.cache_service.get_cache_size()
                if cache_size > self.max_cache_size:
                    logger.warning(f"缓存大小超限: {cache_size} > {self.max_cache_size}")
                    # 可以实现LRU清理逻辑
            
        except Exception as e:
            logger.error(f"优化缓存性能失败: {e}")


class SmartInheritanceCache:
    """智能继承缓存
    
    结合用户行为模式优化缓存策略
    """
    
    def __init__(self, cache_manager: InheritanceCacheManager):
        self.cache_manager = cache_manager
        self.user_patterns: Dict[str, Dict] = {}  # 用户行为模式
    
    async def predict_cache_needs(self, user_id: str, current_context: Dict[str, Any]) -> List[str]:
        """预测用户可能需要的缓存内容"""
        try:
            pattern = self.user_patterns.get(user_id, {})
            
            # 基于历史行为预测
            predictions = []
            
            # 如果用户经常查询某些槽位组合，预热缓存
            frequent_combinations = pattern.get("frequent_slot_combinations", [])
            for combination in frequent_combinations[:3]:  # 预热前3个最常用的
                predictions.append(combination)
            
            return predictions
            
        except Exception as e:
            logger.error(f"预测缓存需求失败: {user_id}, 错误: {e}")
            return []
    
    async def update_user_pattern(self, user_id: str, slot_names: List[str], context: Dict[str, Any]):
        """更新用户行为模式"""
        try:
            if user_id not in self.user_patterns:
                self.user_patterns[user_id] = {
                    "frequent_slot_combinations": [],
                    "last_updated": datetime.now()
                }
            
            pattern = self.user_patterns[user_id]
            
            # 更新槽位组合频率
            slot_combination = ",".join(sorted(slot_names))
            combinations = pattern["frequent_slot_combinations"]
            
            # 简单的频率统计
            found = False
            for i, (combo, count) in enumerate(combinations):
                if combo == slot_combination:
                    combinations[i] = (combo, count + 1)
                    found = True
                    break
            
            if not found:
                combinations.append((slot_combination, 1))
            
            # 按频率排序
            combinations.sort(key=lambda x: x[1], reverse=True)
            
            # 保留前10个最常用的组合
            pattern["frequent_slot_combinations"] = combinations[:10]
            pattern["last_updated"] = datetime.now()
            
        except Exception as e:
            logger.error(f"更新用户行为模式失败: {user_id}, 错误: {e}")


# 全局缓存管理器实例
inheritance_cache_manager: Optional[InheritanceCacheManager] = None
smart_inheritance_cache: Optional[SmartInheritanceCache] = None


async def get_inheritance_cache_manager(cache_service: CacheService) -> InheritanceCacheManager:
    """获取继承缓存管理器实例"""
    global inheritance_cache_manager
    if inheritance_cache_manager is None:
        inheritance_cache_manager = InheritanceCacheManager(cache_service)
    return inheritance_cache_manager


async def get_smart_inheritance_cache(cache_service: CacheService) -> SmartInheritanceCache:
    """获取智能继承缓存实例"""
    global smart_inheritance_cache
    if smart_inheritance_cache is None:
        cache_manager = await get_inheritance_cache_manager(cache_service)
        smart_inheritance_cache = SmartInheritanceCache(cache_manager)
    return smart_inheritance_cache