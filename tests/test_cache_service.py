"""
缓存服务单元测试
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import asyncio
import json
from datetime import datetime, timedelta
import time

from src.services.cache_service import CacheService


class TestCacheService:
    """缓存服务测试类"""
    
    @pytest.fixture
    def mock_redis(self):
        """模拟Redis连接"""
        redis_mock = AsyncMock()
        redis_mock.ping.return_value = True
        redis_mock.get.return_value = None
        redis_mock.set.return_value = True
        redis_mock.delete.return_value = 1
        redis_mock.exists.return_value = False
        redis_mock.expire.return_value = True
        redis_mock.ttl.return_value = 3600
        redis_mock.keys.return_value = []
        redis_mock.flushdb.return_value = True
        return redis_mock
    
    @pytest.fixture
    def cache_service(self, mock_redis):
        """创建缓存服务实例"""
        with patch('src.services.cache_service.redis.Redis.from_url', return_value=mock_redis):
            service = CacheService()
            service.redis = mock_redis
            return service
    
    @pytest.mark.asyncio
    async def test_cache_service_initialization(self, mock_redis):
        """测试缓存服务初始化"""
        with patch('src.services.cache_service.redis.Redis.from_url', return_value=mock_redis):
            # 创建缓存服务
            service = CacheService()
            
            # 初始化服务
            await service.initialize()
            
            # 验证初始化
            assert service.redis is not None
            assert service.is_connected == True
            mock_redis.ping.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_cache_service_initialization_failure(self, mock_redis):
        """测试缓存服务初始化失败"""
        # 模拟连接失败
        mock_redis.ping.side_effect = Exception("Connection failed")
        
        with patch('src.services.cache_service.redis.Redis.from_url', return_value=mock_redis):
            service = CacheService()
            
            # 初始化应该失败
            await service.initialize()
            
            # 验证初始化失败
            assert service.is_connected == False
    
    @pytest.mark.asyncio
    async def test_get_cache_hit(self, cache_service, mock_redis):
        """测试缓存命中"""
        # 准备测试数据
        key = "test_key"
        value = {"data": "test_value", "timestamp": time.time()}
        
        # 设置Redis返回值
        mock_redis.get.return_value = json.dumps(value)
        
        # 获取缓存
        result = await cache_service.get(key)
        
        # 验证结果
        assert result == value
        mock_redis.get.assert_called_once_with("default:test_key")
    
    @pytest.mark.asyncio
    async def test_get_cache_miss(self, cache_service, mock_redis):
        """测试缓存未命中"""
        # 准备测试数据
        key = "nonexistent_key"
        
        # 设置Redis返回值
        mock_redis.get.return_value = None
        
        # 获取缓存
        result = await cache_service.get(key)
        
        # 验证结果
        assert result is None
        mock_redis.get.assert_called_once_with("default:nonexistent_key")
    
    @pytest.mark.asyncio
    async def test_get_with_namespace(self, cache_service, mock_redis):
        """测试带命名空间的缓存获取"""
        # 准备测试数据
        key = "test_key"
        namespace = "custom"
        value = {"data": "test_value"}
        
        # 设置Redis返回值
        mock_redis.get.return_value = json.dumps(value)
        
        # 获取缓存
        result = await cache_service.get(key, namespace=namespace)
        
        # 验证结果
        assert result == value
        mock_redis.get.assert_called_once_with("custom:test_key")
    
    @pytest.mark.asyncio
    async def test_set_cache(self, cache_service, mock_redis):
        """测试设置缓存"""
        # 准备测试数据
        key = "test_key"
        value = {"data": "test_value"}
        ttl = 3600
        
        # 设置Redis返回值
        mock_redis.set.return_value = True
        
        # 设置缓存
        result = await cache_service.set(key, value, ttl=ttl)
        
        # 验证结果
        assert result == True
        mock_redis.set.assert_called_once_with("default:test_key", json.dumps(value), ex=ttl)
    
    @pytest.mark.asyncio
    async def test_set_cache_with_namespace(self, cache_service, mock_redis):
        """测试带命名空间的缓存设置"""
        # 准备测试数据
        key = "test_key"
        value = {"data": "test_value"}
        namespace = "custom"
        ttl = 1800
        
        # 设置Redis返回值
        mock_redis.set.return_value = True
        
        # 设置缓存
        result = await cache_service.set(key, value, ttl=ttl, namespace=namespace)
        
        # 验证结果
        assert result == True
        mock_redis.set.assert_called_once_with("custom:test_key", json.dumps(value), ex=ttl)
    
    @pytest.mark.asyncio
    async def test_set_cache_without_ttl(self, cache_service, mock_redis):
        """测试不带TTL的缓存设置"""
        # 准备测试数据
        key = "test_key"
        value = {"data": "test_value"}
        
        # 设置Redis返回值
        mock_redis.set.return_value = True
        
        # 设置缓存
        result = await cache_service.set(key, value)
        
        # 验证结果
        assert result == True
        mock_redis.set.assert_called_once_with("default:test_key", json.dumps(value), ex=None)
    
    @pytest.mark.asyncio
    async def test_delete_cache(self, cache_service, mock_redis):
        """测试删除缓存"""
        # 准备测试数据
        key = "test_key"
        
        # 设置Redis返回值
        mock_redis.delete.return_value = 1
        
        # 删除缓存
        result = await cache_service.delete(key)
        
        # 验证结果
        assert result == True
        mock_redis.delete.assert_called_once_with("default:test_key")
    
    @pytest.mark.asyncio
    async def test_delete_cache_not_found(self, cache_service, mock_redis):
        """测试删除不存在的缓存"""
        # 准备测试数据
        key = "nonexistent_key"
        
        # 设置Redis返回值
        mock_redis.delete.return_value = 0
        
        # 删除缓存
        result = await cache_service.delete(key)
        
        # 验证结果
        assert result == False
        mock_redis.delete.assert_called_once_with("default:nonexistent_key")
    
    @pytest.mark.asyncio
    async def test_exists_cache(self, cache_service, mock_redis):
        """测试检查缓存是否存在"""
        # 准备测试数据
        key = "test_key"
        
        # 设置Redis返回值
        mock_redis.exists.return_value = 1
        
        # 检查缓存是否存在
        result = await cache_service.exists(key)
        
        # 验证结果
        assert result == True
        mock_redis.exists.assert_called_once_with("default:test_key")
    
    @pytest.mark.asyncio
    async def test_exists_cache_not_found(self, cache_service, mock_redis):
        """测试检查不存在的缓存"""
        # 准备测试数据
        key = "nonexistent_key"
        
        # 设置Redis返回值
        mock_redis.exists.return_value = 0
        
        # 检查缓存是否存在
        result = await cache_service.exists(key)
        
        # 验证结果
        assert result == False
        mock_redis.exists.assert_called_once_with("default:nonexistent_key")
    
    @pytest.mark.asyncio
    async def test_expire_cache(self, cache_service, mock_redis):
        """测试设置缓存过期时间"""
        # 准备测试数据
        key = "test_key"
        ttl = 3600
        
        # 设置Redis返回值
        mock_redis.expire.return_value = True
        
        # 设置过期时间
        result = await cache_service.expire(key, ttl)
        
        # 验证结果
        assert result == True
        mock_redis.expire.assert_called_once_with("default:test_key", ttl)
    
    @pytest.mark.asyncio
    async def test_ttl_cache(self, cache_service, mock_redis):
        """测试获取缓存TTL"""
        # 准备测试数据
        key = "test_key"
        
        # 设置Redis返回值
        mock_redis.ttl.return_value = 3600
        
        # 获取TTL
        result = await cache_service.ttl(key)
        
        # 验证结果
        assert result == 3600
        mock_redis.ttl.assert_called_once_with("default:test_key")
    
    @pytest.mark.asyncio
    async def test_ttl_cache_no_expiry(self, cache_service, mock_redis):
        """测试获取没有过期时间的缓存TTL"""
        # 准备测试数据
        key = "test_key"
        
        # 设置Redis返回值
        mock_redis.ttl.return_value = -1
        
        # 获取TTL
        result = await cache_service.ttl(key)
        
        # 验证结果
        assert result == -1
        mock_redis.ttl.assert_called_once_with("default:test_key")
    
    @pytest.mark.asyncio
    async def test_keys_cache(self, cache_service, mock_redis):
        """测试获取缓存键列表"""
        # 准备测试数据
        pattern = "test_*"
        
        # 设置Redis返回值
        mock_redis.keys.return_value = [b"default:test_key1", b"default:test_key2"]
        
        # 获取键列表
        result = await cache_service.keys(pattern)
        
        # 验证结果
        assert result == ["test_key1", "test_key2"]
        mock_redis.keys.assert_called_once_with("default:test_*")
    
    @pytest.mark.asyncio
    async def test_keys_cache_with_namespace(self, cache_service, mock_redis):
        """测试带命名空间获取缓存键列表"""
        # 准备测试数据
        pattern = "user_*"
        namespace = "session"
        
        # 设置Redis返回值
        mock_redis.keys.return_value = [b"session:user_123", b"session:user_456"]
        
        # 获取键列表
        result = await cache_service.keys(pattern, namespace=namespace)
        
        # 验证结果
        assert result == ["user_123", "user_456"]
        mock_redis.keys.assert_called_once_with("session:user_*")
    
    @pytest.mark.asyncio
    async def test_clear_cache(self, cache_service, mock_redis):
        """测试清空缓存"""
        # 设置Redis返回值
        mock_redis.flushdb.return_value = True
        
        # 清空缓存
        result = await cache_service.clear()
        
        # 验证结果
        assert result == True
        mock_redis.flushdb.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_clear_namespace_cache(self, cache_service, mock_redis):
        """测试清空命名空间缓存"""
        # 准备测试数据
        namespace = "session"
        
        # 设置Redis返回值
        mock_redis.keys.return_value = [b"session:key1", b"session:key2"]
        mock_redis.delete.return_value = 2
        
        # 清空命名空间缓存
        result = await cache_service.clear_namespace(namespace)
        
        # 验证结果
        assert result == 2
        mock_redis.keys.assert_called_once_with("session:*")
        mock_redis.delete.assert_called_once_with("session:key1", "session:key2")
    
    @pytest.mark.asyncio
    async def test_get_stats(self, cache_service, mock_redis):
        """测试获取缓存统计"""
        # 设置Redis返回值
        mock_redis.info.return_value = {
            'used_memory': 1048576,
            'used_memory_human': '1.00M',
            'connected_clients': 5,
            'total_connections_received': 100,
            'total_commands_processed': 1000,
            'keyspace_hits': 800,
            'keyspace_misses': 200,
            'db0': {'keys': 50, 'expires': 20}
        }
        
        # 获取统计信息
        result = await cache_service.get_stats()
        
        # 验证结果
        assert result is not None
        assert result['memory_usage'] == 1048576
        assert result['connected_clients'] == 5
        assert result['total_connections'] == 100
        assert result['total_commands'] == 1000
        assert result['hit_rate'] == 0.8
        assert result['miss_rate'] == 0.2
        assert result['total_keys'] == 50
        assert result['keys_with_expiry'] == 20
        mock_redis.info.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_increment_counter(self, cache_service, mock_redis):
        """测试递增计数器"""
        # 准备测试数据
        key = "counter_key"
        
        # 设置Redis返回值
        mock_redis.incr.return_value = 1
        
        # 递增计数器
        result = await cache_service.increment(key)
        
        # 验证结果
        assert result == 1
        mock_redis.incr.assert_called_once_with("default:counter_key")
    
    @pytest.mark.asyncio
    async def test_increment_counter_with_amount(self, cache_service, mock_redis):
        """测试按指定数量递增计数器"""
        # 准备测试数据
        key = "counter_key"
        amount = 5
        
        # 设置Redis返回值
        mock_redis.incr.return_value = 5
        
        # 递增计数器
        result = await cache_service.increment(key, amount)
        
        # 验证结果
        assert result == 5
        mock_redis.incr.assert_called_once_with("default:counter_key", amount)
    
    @pytest.mark.asyncio
    async def test_decrement_counter(self, cache_service, mock_redis):
        """测试递减计数器"""
        # 准备测试数据
        key = "counter_key"
        
        # 设置Redis返回值
        mock_redis.decr.return_value = 4
        
        # 递减计数器
        result = await cache_service.decrement(key)
        
        # 验证结果
        assert result == 4
        mock_redis.decr.assert_called_once_with("default:counter_key")
    
    @pytest.mark.asyncio
    async def test_decrement_counter_with_amount(self, cache_service, mock_redis):
        """测试按指定数量递减计数器"""
        # 准备测试数据
        key = "counter_key"
        amount = 3
        
        # 设置Redis返回值
        mock_redis.decr.return_value = 2
        
        # 递减计数器
        result = await cache_service.decrement(key, amount)
        
        # 验证结果
        assert result == 2
        mock_redis.decr.assert_called_once_with("default:counter_key", amount)
    
    @pytest.mark.asyncio
    async def test_set_hash(self, cache_service, mock_redis):
        """测试设置哈希字段"""
        # 准备测试数据
        key = "hash_key"
        field = "field1"
        value = "value1"
        
        # 设置Redis返回值
        mock_redis.hset.return_value = 1
        
        # 设置哈希字段
        result = await cache_service.hset(key, field, value)
        
        # 验证结果
        assert result == True
        mock_redis.hset.assert_called_once_with("default:hash_key", field, json.dumps(value))
    
    @pytest.mark.asyncio
    async def test_get_hash(self, cache_service, mock_redis):
        """测试获取哈希字段"""
        # 准备测试数据
        key = "hash_key"
        field = "field1"
        value = "value1"
        
        # 设置Redis返回值
        mock_redis.hget.return_value = json.dumps(value)
        
        # 获取哈希字段
        result = await cache_service.hget(key, field)
        
        # 验证结果
        assert result == value
        mock_redis.hget.assert_called_once_with("default:hash_key", field)
    
    @pytest.mark.asyncio
    async def test_get_hash_all(self, cache_service, mock_redis):
        """测试获取所有哈希字段"""
        # 准备测试数据
        key = "hash_key"
        hash_data = {
            b"field1": json.dumps("value1"),
            b"field2": json.dumps("value2")
        }
        
        # 设置Redis返回值
        mock_redis.hgetall.return_value = hash_data
        
        # 获取所有哈希字段
        result = await cache_service.hgetall(key)
        
        # 验证结果
        assert result == {"field1": "value1", "field2": "value2"}
        mock_redis.hgetall.assert_called_once_with("default:hash_key")
    
    @pytest.mark.asyncio
    async def test_delete_hash_field(self, cache_service, mock_redis):
        """测试删除哈希字段"""
        # 准备测试数据
        key = "hash_key"
        field = "field1"
        
        # 设置Redis返回值
        mock_redis.hdel.return_value = 1
        
        # 删除哈希字段
        result = await cache_service.hdel(key, field)
        
        # 验证结果
        assert result == True
        mock_redis.hdel.assert_called_once_with("default:hash_key", field)
    
    @pytest.mark.asyncio
    async def test_list_push(self, cache_service, mock_redis):
        """测试列表推送"""
        # 准备测试数据
        key = "list_key"
        value = "list_item"
        
        # 设置Redis返回值
        mock_redis.lpush.return_value = 1
        
        # 推送到列表
        result = await cache_service.lpush(key, value)
        
        # 验证结果
        assert result == 1
        mock_redis.lpush.assert_called_once_with("default:list_key", json.dumps(value))
    
    @pytest.mark.asyncio
    async def test_list_pop(self, cache_service, mock_redis):
        """测试列表弹出"""
        # 准备测试数据
        key = "list_key"
        value = "list_item"
        
        # 设置Redis返回值
        mock_redis.lpop.return_value = json.dumps(value)
        
        # 从列表弹出
        result = await cache_service.lpop(key)
        
        # 验证结果
        assert result == value
        mock_redis.lpop.assert_called_once_with("default:list_key")
    
    @pytest.mark.asyncio
    async def test_list_range(self, cache_service, mock_redis):
        """测试列表范围获取"""
        # 准备测试数据
        key = "list_key"
        list_data = [json.dumps("item1"), json.dumps("item2"), json.dumps("item3")]
        
        # 设置Redis返回值
        mock_redis.lrange.return_value = list_data
        
        # 获取列表范围
        result = await cache_service.lrange(key, 0, -1)
        
        # 验证结果
        assert result == ["item1", "item2", "item3"]
        mock_redis.lrange.assert_called_once_with("default:list_key", 0, -1)
    
    @pytest.mark.asyncio
    async def test_set_add(self, cache_service, mock_redis):
        """测试集合添加"""
        # 准备测试数据
        key = "set_key"
        value = "set_item"
        
        # 设置Redis返回值
        mock_redis.sadd.return_value = 1
        
        # 添加到集合
        result = await cache_service.sadd(key, value)
        
        # 验证结果
        assert result == 1
        mock_redis.sadd.assert_called_once_with("default:set_key", json.dumps(value))
    
    @pytest.mark.asyncio
    async def test_set_members(self, cache_service, mock_redis):
        """测试获取集合成员"""
        # 准备测试数据
        key = "set_key"
        set_data = {json.dumps("item1"), json.dumps("item2"), json.dumps("item3")}
        
        # 设置Redis返回值
        mock_redis.smembers.return_value = set_data
        
        # 获取集合成员
        result = await cache_service.smembers(key)
        
        # 验证结果
        assert set(result) == {"item1", "item2", "item3"}
        mock_redis.smembers.assert_called_once_with("default:set_key")
    
    @pytest.mark.asyncio
    async def test_set_remove(self, cache_service, mock_redis):
        """测试集合移除"""
        # 准备测试数据
        key = "set_key"
        value = "set_item"
        
        # 设置Redis返回值
        mock_redis.srem.return_value = 1
        
        # 从集合移除
        result = await cache_service.srem(key, value)
        
        # 验证结果
        assert result == 1
        mock_redis.srem.assert_called_once_with("default:set_key", json.dumps(value))
    
    @pytest.mark.asyncio
    async def test_cache_with_json_serialization(self, cache_service, mock_redis):
        """测试JSON序列化缓存"""
        # 准备测试数据
        key = "json_key"
        value = {
            "string": "test",
            "number": 123,
            "boolean": True,
            "array": [1, 2, 3],
            "object": {"nested": "value"}
        }
        
        # 设置缓存
        mock_redis.set.return_value = True
        await cache_service.set(key, value)
        
        # 获取缓存
        mock_redis.get.return_value = json.dumps(value)
        result = await cache_service.get(key)
        
        # 验证结果
        assert result == value
        assert result["string"] == "test"
        assert result["number"] == 123
        assert result["boolean"] == True
        assert result["array"] == [1, 2, 3]
        assert result["object"]["nested"] == "value"
    
    @pytest.mark.asyncio
    async def test_cache_error_handling(self, cache_service, mock_redis):
        """测试缓存错误处理"""
        # 准备测试数据
        key = "error_key"
        
        # 模拟Redis错误
        mock_redis.get.side_effect = Exception("Redis connection error")
        
        # 获取缓存应该返回None而不是抛出异常
        result = await cache_service.get(key)
        
        # 验证结果
        assert result is None
    
    @pytest.mark.asyncio
    async def test_cache_connection_check(self, cache_service, mock_redis):
        """测试缓存连接检查"""
        # 设置Redis返回值
        mock_redis.ping.return_value = True
        
        # 检查连接
        result = await cache_service.ping()
        
        # 验证结果
        assert result == True
        mock_redis.ping.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_cache_connection_check_failure(self, cache_service, mock_redis):
        """测试缓存连接检查失败"""
        # 模拟ping失败
        mock_redis.ping.side_effect = Exception("Connection failed")
        
        # 检查连接
        result = await cache_service.ping()
        
        # 验证结果
        assert result == False
    
    @pytest.mark.asyncio
    async def test_cache_close(self, cache_service, mock_redis):
        """测试关闭缓存连接"""
        # 关闭连接
        await cache_service.close()
        
        # 验证连接状态
        assert cache_service.is_connected == False
        mock_redis.close.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_cache_batch_operations(self, cache_service, mock_redis):
        """测试批量操作"""
        # 准备测试数据
        operations = [
            ("set", "key1", "value1"),
            ("set", "key2", "value2"),
            ("get", "key1"),
            ("delete", "key2")
        ]
        
        # 设置Redis返回值
        mock_redis.pipeline.return_value = mock_redis
        mock_redis.execute.return_value = [True, True, "value1", 1]
        
        # 执行批量操作
        results = await cache_service.batch_operations(operations)
        
        # 验证结果
        assert len(results) == 4
        assert results[0] == True
        assert results[1] == True
        assert results[2] == "value1"
        assert results[3] == 1
        mock_redis.pipeline.assert_called_once()
        mock_redis.execute.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_cache_health_check(self, cache_service, mock_redis):
        """测试缓存健康检查"""
        # 设置Redis返回值
        mock_redis.ping.return_value = True
        mock_redis.info.return_value = {
            'used_memory': 1048576,
            'connected_clients': 5,
            'total_connections_received': 100
        }
        
        # 执行健康检查
        result = await cache_service.health_check()
        
        # 验证结果
        assert result['status'] == 'healthy'
        assert result['connected'] == True
        assert result['memory_usage'] == 1048576
        assert result['connected_clients'] == 5
        assert result['total_connections'] == 100
    
    @pytest.mark.asyncio
    async def test_cache_performance_metrics(self, cache_service, mock_redis):
        """测试缓存性能指标"""
        # 设置测试数据
        cache_service.hit_count = 80
        cache_service.miss_count = 20
        cache_service.total_requests = 100
        
        # 获取性能指标
        metrics = await cache_service.get_performance_metrics()
        
        # 验证指标
        assert metrics['hit_count'] == 80
        assert metrics['miss_count'] == 20
        assert metrics['total_requests'] == 100
        assert metrics['hit_rate'] == 0.8
        assert metrics['miss_rate'] == 0.2
    
    @pytest.mark.asyncio
    async def test_cache_concurrency(self, cache_service, mock_redis):
        """测试缓存并发操作"""
        # 准备测试数据
        keys = [f"key_{i}" for i in range(10)]
        values = [f"value_{i}" for i in range(10)]
        
        # 设置Redis返回值
        mock_redis.set.return_value = True
        mock_redis.get.return_value = json.dumps("test_value")
        
        # 并发设置缓存
        set_tasks = [cache_service.set(key, value) for key, value in zip(keys, values)]
        set_results = await asyncio.gather(*set_tasks)
        
        # 验证设置结果
        assert all(result == True for result in set_results)
        
        # 并发获取缓存
        get_tasks = [cache_service.get(key) for key in keys]
        get_results = await asyncio.gather(*get_tasks)
        
        # 验证获取结果
        assert all(result == "test_value" for result in get_results)
    
    @pytest.mark.asyncio
    async def test_cache_memory_management(self, cache_service, mock_redis):
        """测试缓存内存管理"""
        # 设置Redis返回值
        mock_redis.info.return_value = {
            'used_memory': 100 * 1024 * 1024,  # 100MB
            'maxmemory': 1024 * 1024 * 1024,   # 1GB
            'used_memory_peak': 150 * 1024 * 1024  # 150MB
        }
        
        # 获取内存信息
        memory_info = await cache_service.get_memory_info()
        
        # 验证内存信息
        assert memory_info['used_memory'] == 100 * 1024 * 1024
        assert memory_info['max_memory'] == 1024 * 1024 * 1024
        assert memory_info['memory_usage_ratio'] == 0.09765625  # 100MB / 1GB
        assert memory_info['peak_memory'] == 150 * 1024 * 1024
    
    @pytest.mark.asyncio
    async def test_cache_expiration_management(self, cache_service, mock_redis):
        """测试缓存过期管理"""
        # 准备测试数据
        key = "expiring_key"
        
        # 设置Redis返回值
        mock_redis.keys.return_value = [b"default:expiring_key"]
        mock_redis.ttl.return_value = 30  # 30秒后过期
        
        # 获取即将过期的键
        expiring_keys = await cache_service.get_expiring_keys(threshold=60)
        
        # 验证结果
        assert len(expiring_keys) == 1
        assert expiring_keys[0]['key'] == 'expiring_key'
        assert expiring_keys[0]['ttl'] == 30
    
    @pytest.mark.asyncio
    async def test_cache_cleanup(self, cache_service, mock_redis):
        """测试缓存清理"""
        # 设置Redis返回值
        mock_redis.keys.return_value = [b"default:expired_key1", b"default:expired_key2"]
        mock_redis.delete.return_value = 2
        
        # 清理过期缓存
        cleaned_count = await cache_service.cleanup_expired_keys()
        
        # 验证结果
        assert cleaned_count == 2
        mock_redis.keys.assert_called()
        mock_redis.delete.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_cache_configuration(self, cache_service):
        """测试缓存配置"""
        # 验证默认配置
        assert cache_service.default_namespace == "default"
        assert cache_service.default_ttl == 3600
        assert cache_service.max_connections == 20
        
        # 更新配置
        cache_service.configure(
            default_namespace="custom",
            default_ttl=7200,
            max_connections=50
        )
        
        # 验证配置更新
        assert cache_service.default_namespace == "custom"
        assert cache_service.default_ttl == 7200
        assert cache_service.max_connections == 50