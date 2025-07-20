"""
缓存服务 (TASK-035)
提供内存和Redis缓存功能
"""
import json
import time
import asyncio
from typing import Any, Optional, Dict
from datetime import datetime, timedelta

from .logger import get_logger

logger = get_logger(__name__)


class CacheService:
    """缓存服务"""
    
    def __init__(self):
        # 内存缓存
        self._memory_cache: Dict[str, Dict[str, Any]] = {}
        self._cache_stats = {
            'hits': 0,
            'misses': 0,
            'sets': 0,
            'deletes': 0
        }
        
        # 启动清理任务
        asyncio.create_task(self._cleanup_expired_keys())
    
    async def get(self, key: str) -> Optional[Any]:
        """
        获取缓存值
        
        Args:
            key: 缓存键
            
        Returns:
            缓存值或None
        """
        try:
            if key in self._memory_cache:
                cache_entry = self._memory_cache[key]
                
                # 检查是否过期
                if cache_entry['expires_at'] and time.time() > cache_entry['expires_at']:
                    del self._memory_cache[key]
                    self._cache_stats['misses'] += 1
                    return None
                
                self._cache_stats['hits'] += 1
                return cache_entry['value']
            
            self._cache_stats['misses'] += 1
            return None
            
        except Exception as e:
            logger.error(f"缓存获取失败: {key}, 错误: {str(e)}")
            return None
    
    async def set(self, key: str, value: Any, expire: Optional[int] = None) -> bool:
        """
        设置缓存值
        
        Args:
            key: 缓存键
            value: 缓存值
            expire: 过期时间(秒)
            
        Returns:
            是否成功
        """
        try:
            expires_at = None
            if expire:
                expires_at = time.time() + expire
            
            self._memory_cache[key] = {
                'value': value,
                'created_at': time.time(),
                'expires_at': expires_at
            }
            
            self._cache_stats['sets'] += 1
            return True
            
        except Exception as e:
            logger.error(f"缓存设置失败: {key}, 错误: {str(e)}")
            return False
    
    async def delete(self, key: str) -> bool:
        """
        删除缓存键
        
        Args:
            key: 缓存键
            
        Returns:
            是否成功
        """
        try:
            if key in self._memory_cache:
                del self._memory_cache[key]
                self._cache_stats['deletes'] += 1
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"缓存删除失败: {key}, 错误: {str(e)}")
            return False
    
    async def exists(self, key: str) -> bool:
        """
        检查缓存键是否存在
        
        Args:
            key: 缓存键
            
        Returns:
            是否存在
        """
        try:
            if key in self._memory_cache:
                cache_entry = self._memory_cache[key]
                
                # 检查是否过期
                if cache_entry['expires_at'] and time.time() > cache_entry['expires_at']:
                    del self._memory_cache[key]
                    return False
                
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"缓存检查失败: {key}, 错误: {str(e)}")
            return False
    
    async def clear(self) -> bool:
        """
        清空所有缓存
        
        Returns:
            是否成功
        """
        try:
            self._memory_cache.clear()
            logger.info("缓存已清空")
            return True
            
        except Exception as e:
            logger.error(f"缓存清空失败: {str(e)}")
            return False
    
    async def get_stats(self) -> Dict[str, Any]:
        """
        获取缓存统计信息
        
        Returns:
            统计信息
        """
        try:
            total_requests = self._cache_stats['hits'] + self._cache_stats['misses']
            hit_rate = self._cache_stats['hits'] / total_requests if total_requests > 0 else 0.0
            
            return {
                'total_keys': len(self._memory_cache),
                'hits': self._cache_stats['hits'],
                'misses': self._cache_stats['misses'],
                'hit_rate': hit_rate,
                'sets': self._cache_stats['sets'],
                'deletes': self._cache_stats['deletes'],
                'memory_usage_mb': self._calculate_memory_usage()
            }
            
        except Exception as e:
            logger.error(f"获取缓存统计失败: {str(e)}")
            return {}
    
    def _calculate_memory_usage(self) -> float:
        """计算内存使用量(MB)"""
        try:
            total_size = 0
            for key, entry in self._memory_cache.items():
                # 简单估算
                key_size = len(str(key))
                value_size = len(str(entry['value']))
                total_size += key_size + value_size
            
            return total_size / (1024 * 1024)  # 转换为MB
            
        except Exception:
            return 0.0
    
    async def _cleanup_expired_keys(self):
        """清理过期键的后台任务"""
        while True:
            try:
                await asyncio.sleep(60)  # 每分钟清理一次
                
                current_time = time.time()
                expired_keys = []
                
                for key, entry in self._memory_cache.items():
                    if entry['expires_at'] and current_time > entry['expires_at']:
                        expired_keys.append(key)
                
                # 删除过期键
                for key in expired_keys:
                    del self._memory_cache[key]
                
                if expired_keys:
                    logger.info(f"清理过期缓存键: {len(expired_keys)} 个")
                    
            except Exception as e:
                logger.error(f"缓存清理任务失败: {str(e)}")
                await asyncio.sleep(60)