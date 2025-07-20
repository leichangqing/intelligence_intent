#!/usr/bin/env python3
"""
测试重试和错误处理功能 (TASK-029)
"""
import asyncio
import sys
import os
sys.path.insert(0, os.path.abspath('.'))

from src.services.function_service import FunctionService, FunctionRetryConfig
from src.services.cache_service import CacheService
from src.utils.logger import get_logger
import random

logger = get_logger(__name__)


class MockFailureFunction:
    """模拟失败的函数"""
    
    def __init__(self, failure_rate: float = 0.5):
        self.failure_rate = failure_rate
        self.call_count = 0
    
    def __call__(self, *args, **kwargs):
        self.call_count += 1
        if random.random() < self.failure_rate:
            raise Exception(f"模拟失败 (调用次数: {self.call_count})")
        return f"成功调用 (第{self.call_count}次)"


class MockTimeoutFunction:
    """模拟超时的函数"""
    
    def __init__(self, timeout_rate: float = 0.3):
        self.timeout_rate = timeout_rate
        self.call_count = 0
    
    async def __call__(self, *args, **kwargs):
        self.call_count += 1
        if random.random() < self.timeout_rate:
            # 模拟超时
            await asyncio.sleep(0.1)
            raise asyncio.TimeoutError(f"模拟超时 (调用次数: {self.call_count})")
        return f"成功调用 (第{self.call_count}次)"


async def test_basic_retry():
    """测试基本重试功能"""
    print("\n=== 测试基本重试功能 ===")
    
    # 创建服务
    cache_service = CacheService()
    function_service = FunctionService(cache_service)
    
    # 注册测试函数
    test_func = MockFailureFunction(failure_rate=0.7)
    await function_service.register_function("test_retry", test_func)
    
    # 配置重试
    retry_config = FunctionRetryConfig(
        max_attempts=3,
        base_delay=0.1,
        backoff_factor=2.0,
        jitter=True
    )
    function_service.set_function_retry_config("test_retry", retry_config)
    
    # 执行函数
    result = await function_service.execute_function("test_retry", {})
    
    print(f"执行结果: {result.to_dict()}")
    print(f"错误统计: {function_service.get_function_error_stats('test_retry')}")


async def test_circuit_breaker():
    """测试熔断器功能"""
    print("\n=== 测试熔断器功能 ===")
    
    # 创建服务
    cache_service = CacheService()
    function_service = FunctionService(cache_service)
    
    # 注册测试函数
    test_func = MockFailureFunction(failure_rate=0.9)  # 90% 失败率
    await function_service.register_function("test_circuit", test_func)
    
    # 启用熔断器
    function_service.enable_circuit_breaker("test_circuit", failure_threshold=3)
    
    # 配置重试
    retry_config = FunctionRetryConfig(
        max_attempts=2,
        base_delay=0.1,
        circuit_breaker=True
    )
    function_service.set_function_retry_config("test_circuit", retry_config)
    
    # 多次调用，触发熔断器
    for i in range(8):
        result = await function_service.execute_function("test_circuit", {})
        print(f"第{i+1}次调用: {result.success}, 错误: {result.error}")
        
        # 检查熔断器状态
        cb_status = function_service.get_circuit_breaker_status("test_circuit")
        if cb_status:
            print(f"熔断器状态: {cb_status['state']}, 失败次数: {cb_status['failure_count']}")
        
        if result.error_type == "CircuitBreakerOpen":
            print("熔断器已开启，停止调用")
            break
    
    print(f"最终错误统计: {function_service.get_function_error_stats('test_circuit')}")


async def test_async_timeout_retry():
    """测试异步超时重试"""
    print("\n=== 测试异步超时重试 ===")
    
    # 创建服务
    cache_service = CacheService()
    function_service = FunctionService(cache_service)
    
    # 注册测试函数
    test_func = MockTimeoutFunction(timeout_rate=0.6)
    await function_service.register_function("test_async_retry", test_func)
    
    # 配置重试
    retry_config = FunctionRetryConfig(
        max_attempts=4,
        base_delay=0.1,
        backoff_factor=1.5,
        retry_exceptions=[asyncio.TimeoutError, Exception]
    )
    function_service.set_function_retry_config("test_async_retry", retry_config)
    
    # 执行函数
    result = await function_service.execute_function("test_async_retry", {})
    
    print(f"执行结果: {result.to_dict()}")
    print(f"错误统计: {function_service.get_function_error_stats('test_async_retry')}")


async def test_health_check():
    """测试健康检查"""
    print("\n=== 测试健康检查 ===")
    
    # 创建服务
    cache_service = CacheService()
    function_service = FunctionService(cache_service)
    
    # 注册测试函数
    test_func = MockFailureFunction(failure_rate=0.3)
    await function_service.register_function("test_health", test_func)
    
    # 多次调用以产生统计数据
    for i in range(10):
        await function_service.execute_function("test_health", {})
    
    # 检查健康状态
    health_status = await function_service.health_check_function("test_health")
    print(f"健康状态: {health_status}")
    
    # 测试未注册函数的健康检查
    health_status = await function_service.health_check_function("non_existent")
    print(f"未注册函数健康状态: {health_status}")


async def test_error_statistics():
    """测试错误统计"""
    print("\n=== 测试错误统计 ===")
    
    # 创建服务
    cache_service = CacheService()
    function_service = FunctionService(cache_service)
    
    # 注册多个测试函数
    functions = {
        "func1": MockFailureFunction(failure_rate=0.2),
        "func2": MockFailureFunction(failure_rate=0.5),
        "func3": MockTimeoutFunction(timeout_rate=0.3)
    }
    
    for name, func in functions.items():
        await function_service.register_function(name, func)
    
    # 多次调用
    for i in range(5):
        for name in functions.keys():
            await function_service.execute_function(name, {})
    
    # 显示所有错误统计
    all_stats = function_service.get_all_error_stats()
    for func_name, stats in all_stats.items():
        print(f"\n{func_name} 统计:")
        print(f"  总调用: {stats['total_calls']}")
        print(f"  成功: {stats['success_calls']}")
        print(f"  错误: {stats['error_calls']}")
        print(f"  平均执行时间: {stats['avg_execution_time']:.3f}s")
        print(f"  错误类型: {stats['error_types']}")


async def main():
    """主测试函数"""
    print("开始测试重试和错误处理功能...")
    
    try:
        await test_basic_retry()
        await test_circuit_breaker()
        await test_async_timeout_retry()
        await test_health_check()
        await test_error_statistics()
        
        print("\n=== 所有测试完成 ===")
        
    except Exception as e:
        logger.error(f"测试失败: {str(e)}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())