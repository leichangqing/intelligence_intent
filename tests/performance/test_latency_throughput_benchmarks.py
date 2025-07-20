"""
延迟和吞吐量基准测试 - TASK-049
测试系统的响应时间、吞吐量和并发处理能力
"""
import pytest
import asyncio
import time
import statistics
from typing import List, Dict, Any, Tuple
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timedelta
import json
import aiohttp
import concurrent.futures
from dataclasses import dataclass

from src.services.intent_service import IntentService
from src.services.conversation_service import ConversationService
from src.services.slot_service import SlotService
from src.services.function_service import FunctionService
from src.services.cache_service import CacheService


@dataclass
class PerformanceMetrics:
    """性能指标数据类"""
    operation: str
    response_times: List[float]
    throughput: float
    success_rate: float
    error_count: int
    p50_latency: float
    p95_latency: float
    p99_latency: float
    min_latency: float
    max_latency: float
    avg_latency: float


class TestLatencyThroughputBenchmarks:
    """延迟和吞吐量基准测试类"""
    
    @pytest.fixture
    def performance_config(self):
        """性能测试配置"""
        return {
            'warm_up_requests': 10,
            'benchmark_requests': 100,
            'concurrent_users': 20,
            'timeout_seconds': 30,
            'target_response_time_ms': 2000,
            'target_throughput_rps': 100,
            'target_error_rate': 0.05
        }
    
    @pytest.fixture
    def mock_services(self):
        """创建高性能模拟服务"""
        services = {
            'intent_service': MagicMock(spec=IntentService),
            'conversation_service': MagicMock(spec=ConversationService),
            'slot_service': MagicMock(spec=SlotService),
            'function_service': MagicMock(spec=FunctionService),
            'cache_service': MagicMock(spec=CacheService)
        }
        
        # 设置快速响应的异步方法
        for service in services.values():
            common_methods = [
                'recognize_intent', 'save_conversation', 'extract_slots',
                'call_function', 'get', 'set', 'process_message'
            ]
            for method_name in common_methods:
                # 创建快速响应的AsyncMock (10-50ms模拟延迟)
                mock_method = AsyncMock()
                async def fast_response(*args, **kwargs):
                    await asyncio.sleep(0.01 + 0.04 * time.time() % 1)  # 10-50ms随机延迟
                    return {"status": "success", "data": f"result_{time.time()}"}
                mock_method.side_effect = fast_response
                setattr(service, method_name, mock_method)
        
        return services
    
    @pytest.mark.asyncio
    async def test_intent_recognition_latency_benchmark(self, mock_services, performance_config):
        """测试意图识别延迟基准"""
        benchmark = LatencyBenchmarkRunner(mock_services)
        
        # 预热阶段
        await benchmark.warm_up(
            operation='intent_recognition',
            requests=performance_config['warm_up_requests']
        )
        
        # 执行基准测试
        metrics = await benchmark.run_latency_test(
            operation='intent_recognition',
            test_data_generator=self._generate_intent_test_data,
            requests=performance_config['benchmark_requests']
        )
        
        # 验证延迟性能
        assert metrics.avg_latency < performance_config['target_response_time_ms'] / 1000
        assert metrics.p95_latency < 2.0  # P95 < 2秒
        assert metrics.p99_latency < 5.0  # P99 < 5秒
        assert metrics.success_rate >= 0.95  # 95%成功率
        
        # 验证延迟分布合理性
        assert metrics.min_latency >= 0.01  # 最小10ms
        assert metrics.max_latency <= 10.0  # 最大不超过10秒
        assert metrics.p50_latency <= metrics.p95_latency <= metrics.p99_latency
        
        print(f"意图识别延迟基准结果:")
        print(f"  平均延迟: {metrics.avg_latency:.3f}s")
        print(f"  P95延迟: {metrics.p95_latency:.3f}s") 
        print(f"  P99延迟: {metrics.p99_latency:.3f}s")
        print(f"  成功率: {metrics.success_rate:.2%}")
    
    @pytest.mark.asyncio
    async def test_conversation_flow_latency_benchmark(self, mock_services, performance_config):
        """测试完整对话流程延迟基准"""
        benchmark = LatencyBenchmarkRunner(mock_services)
        
        # 测试完整对话流程延迟
        metrics = await benchmark.run_latency_test(
            operation='conversation_flow',
            test_data_generator=self._generate_conversation_test_data,
            requests=performance_config['benchmark_requests'] // 2  # 减少请求数因为对话流程更复杂
        )
        
        # 验证对话流程性能（允许更高延迟）
        assert metrics.avg_latency < 5.0  # 平均小于5秒
        assert metrics.p95_latency < 10.0  # P95小于10秒
        assert metrics.success_rate >= 0.90  # 90%成功率
        
        print(f"对话流程延迟基准结果:")
        print(f"  平均延迟: {metrics.avg_latency:.3f}s")
        print(f"  P95延迟: {metrics.p95_latency:.3f}s")
        print(f"  成功率: {metrics.success_rate:.2%}")
    
    @pytest.mark.asyncio
    async def test_single_user_throughput_benchmark(self, mock_services, performance_config):
        """测试单用户吞吐量基准"""
        benchmark = ThroughputBenchmarkRunner(mock_services)
        
        # 执行吞吐量测试
        metrics = await benchmark.run_throughput_test(
            operation='intent_recognition',
            test_data_generator=self._generate_intent_test_data,
            duration_seconds=30,
            concurrent_requests=1
        )
        
        # 验证单用户吞吐量
        assert metrics.throughput >= 10  # 至少10 RPS
        assert metrics.success_rate >= 0.95
        
        print(f"单用户吞吐量基准结果:")
        print(f"  吞吐量: {metrics.throughput:.2f} RPS")
        print(f"  总请求数: {len(metrics.response_times)}")
        print(f"  成功率: {metrics.success_rate:.2%}")
    
    @pytest.mark.asyncio
    async def test_concurrent_throughput_benchmark(self, mock_services, performance_config):
        """测试并发吞吐量基准"""
        benchmark = ThroughputBenchmarkRunner(mock_services)
        
        # 测试不同并发级别的吞吐量
        concurrency_levels = [5, 10, 20, 50]
        throughput_results = []
        
        for concurrency in concurrency_levels:
            metrics = await benchmark.run_throughput_test(
                operation='intent_recognition',
                test_data_generator=self._generate_intent_test_data,
                duration_seconds=20,
                concurrent_requests=concurrency
            )
            
            throughput_results.append({
                'concurrency': concurrency,
                'throughput': metrics.throughput,
                'avg_latency': metrics.avg_latency,
                'success_rate': metrics.success_rate
            })
        
        # 验证吞吐量随并发数增长
        max_throughput = max(result['throughput'] for result in throughput_results)
        assert max_throughput >= 50  # 最大吞吐量至少50 RPS
        
        # 验证在高并发下仍保持合理的成功率
        high_concurrency_result = next(r for r in throughput_results if r['concurrency'] == 50)
        assert high_concurrency_result['success_rate'] >= 0.85  # 85%成功率
        
        print(f"并发吞吐量基准结果:")
        for result in throughput_results:
            print(f"  并发数 {result['concurrency']:2d}: {result['throughput']:6.2f} RPS, "
                  f"延迟 {result['avg_latency']:.3f}s, 成功率 {result['success_rate']:.2%}")
    
    @pytest.mark.asyncio
    async def test_cache_performance_benchmark(self, mock_services, performance_config):
        """测试缓存性能基准"""
        # 模拟缓存命中和未命中场景
        cache_service = mock_services['cache_service']
        
        # 设置缓存命中场景（更快响应）
        async def cache_hit(*args, **kwargs):
            await asyncio.sleep(0.001)  # 1ms缓存命中延迟
            return {"cached": True, "data": "cached_result"}
        
        # 设置缓存未命中场景（较慢响应）
        async def cache_miss(*args, **kwargs):
            await asyncio.sleep(0.05)  # 50ms数据库查询延迟
            return {"cached": False, "data": "db_result"}
        
        benchmark = CachePerformanceBenchmarkRunner(mock_services)
        
        # 测试100%缓存命中性能
        cache_service.get.side_effect = cache_hit
        hit_metrics = await benchmark.run_cache_test(
            cache_hit_ratio=1.0,
            requests=100
        )
        
        # 测试0%缓存命中性能
        cache_service.get.side_effect = cache_miss
        miss_metrics = await benchmark.run_cache_test(
            cache_hit_ratio=0.0,
            requests=100
        )
        
        # 验证缓存性能提升
        assert hit_metrics.avg_latency < miss_metrics.avg_latency
        assert hit_metrics.throughput > miss_metrics.throughput
        
        # 缓存命中应显著提高性能
        performance_improvement = (miss_metrics.avg_latency - hit_metrics.avg_latency) / miss_metrics.avg_latency
        assert performance_improvement >= 0.8  # 至少80%性能提升
        
        print(f"缓存性能基准结果:")
        print(f"  缓存命中延迟: {hit_metrics.avg_latency:.4f}s")
        print(f"  缓存未命中延迟: {miss_metrics.avg_latency:.4f}s")
        print(f"  性能提升: {performance_improvement:.1%}")
    
    @pytest.mark.asyncio
    async def test_database_query_performance_benchmark(self, mock_services, performance_config):
        """测试数据库查询性能基准"""
        # 模拟不同复杂度的数据库查询
        conversation_service = mock_services['conversation_service']
        
        async def simple_query(*args, **kwargs):
            await asyncio.sleep(0.02)  # 20ms简单查询
            return {"type": "simple", "result": "data"}
        
        async def complex_query(*args, **kwargs):
            await asyncio.sleep(0.1)   # 100ms复杂查询
            return {"type": "complex", "result": "data"}
        
        benchmark = DatabaseBenchmarkRunner(mock_services)
        
        # 测试简单查询性能
        conversation_service.process_message.side_effect = simple_query
        simple_metrics = await benchmark.run_db_query_test(
            query_type='simple',
            requests=100
        )
        
        # 测试复杂查询性能
        conversation_service.process_message.side_effect = complex_query
        complex_metrics = await benchmark.run_db_query_test(
            query_type='complex',
            requests=50
        )
        
        # 验证查询性能
        assert simple_metrics.avg_latency < 0.1  # 简单查询小于100ms
        assert complex_metrics.avg_latency < 0.5  # 复杂查询小于500ms
        assert simple_metrics.throughput > complex_metrics.throughput
        
        print(f"数据库查询性能基准结果:")
        print(f"  简单查询延迟: {simple_metrics.avg_latency:.3f}s, 吞吐量: {simple_metrics.throughput:.1f} RPS")
        print(f"  复杂查询延迟: {complex_metrics.avg_latency:.3f}s, 吞吐量: {complex_metrics.throughput:.1f} RPS")
    
    @pytest.mark.asyncio
    async def test_api_endpoint_performance_benchmark(self, mock_services, performance_config):
        """测试API端点性能基准"""
        # 模拟不同API端点的性能特征
        endpoint_configs = {
            '/api/v1/chat': {'target_latency': 2.0, 'complexity': 'medium'},
            '/api/v1/health': {'target_latency': 0.1, 'complexity': 'simple'},
            '/api/v1/ambiguity/resolve': {'target_latency': 1.0, 'complexity': 'medium'},
            '/api/v1/admin/config': {'target_latency': 0.5, 'complexity': 'simple'}
        }
        
        benchmark = APIEndpointBenchmarkRunner(mock_services)
        endpoint_results = []
        
        for endpoint, config in endpoint_configs.items():
            metrics = await benchmark.run_endpoint_test(
                endpoint=endpoint,
                complexity=config['complexity'],
                requests=50
            )
            
            endpoint_results.append({
                'endpoint': endpoint,
                'avg_latency': metrics.avg_latency,
                'p95_latency': metrics.p95_latency,
                'target_latency': config['target_latency'],
                'success_rate': metrics.success_rate
            })
            
            # 验证端点性能满足目标
            assert metrics.avg_latency < config['target_latency']
            assert metrics.success_rate >= 0.95
        
        print(f"API端点性能基准结果:")
        for result in endpoint_results:
            print(f"  {result['endpoint']:25s}: {result['avg_latency']:.3f}s "
                  f"(目标: {result['target_latency']:.1f}s), 成功率: {result['success_rate']:.2%}")
    
    def _generate_intent_test_data(self, request_id: int) -> Dict[str, Any]:
        """生成意图识别测试数据"""
        test_messages = [
            "我要订机票",
            "查询余额",
            "取消订单",
            "修改预订",
            "客服咨询",
            "投诉建议"
        ]
        
        return {
            'message': test_messages[request_id % len(test_messages)],
            'session_id': f'session_{request_id}',
            'user_id': f'user_{request_id % 10}'
        }
    
    def _generate_conversation_test_data(self, request_id: int) -> Dict[str, Any]:
        """生成对话流程测试数据"""
        conversation_flows = [
            {
                'messages': ["我要订机票", "从北京到上海", "明天出发"],
                'intent': 'book_flight'
            },
            {
                'messages': ["查询余额", "主账户", "谢谢"],
                'intent': 'check_balance'
            },
            {
                'messages': ["取消订单", "订单号12345", "确认取消"],
                'intent': 'cancel_order'
            }
        ]
        
        flow = conversation_flows[request_id % len(conversation_flows)]
        return {
            'conversation_flow': flow,
            'session_id': f'session_{request_id}',
            'user_id': f'user_{request_id % 5}'
        }


class LatencyBenchmarkRunner:
    """延迟基准测试运行器"""
    
    def __init__(self, services):
        self.services = services
    
    async def warm_up(self, operation: str, requests: int):
        """预热系统"""
        for i in range(requests):
            await self._execute_operation(operation, i)
    
    async def run_latency_test(self, operation: str, test_data_generator, requests: int) -> PerformanceMetrics:
        """运行延迟测试"""
        response_times = []
        errors = 0
        
        for i in range(requests):
            start_time = time.time()
            try:
                test_data = test_data_generator(i)
                await self._execute_operation(operation, i, test_data)
            except Exception:
                errors += 1
            
            response_time = time.time() - start_time
            response_times.append(response_time)
        
        return self._calculate_metrics(operation, response_times, errors)
    
    async def _execute_operation(self, operation: str, request_id: int, test_data: Dict = None):
        """执行指定操作"""
        if operation == 'intent_recognition':
            message = f'test message {request_id}'
            if test_data:
                message = test_data.get('message', message)
            return await self.services['intent_service'].recognize_intent(message)
        elif operation == 'conversation_flow':
            # 模拟完整对话流程
            await self.services['conversation_service'].process_message()
            await self.services['intent_service'].recognize_intent()
            await self.services['slot_service'].extract_slots()
            return await self.services['conversation_service'].save_conversation()
        else:
            return await self.services['intent_service'].recognize_intent(f'test {request_id}')
    
    def _calculate_metrics(self, operation: str, response_times: List[float], errors: int) -> PerformanceMetrics:
        """计算性能指标"""
        if not response_times:
            return PerformanceMetrics(
                operation=operation,
                response_times=[],
                throughput=0,
                success_rate=0,
                error_count=errors,
                p50_latency=0, p95_latency=0, p99_latency=0,
                min_latency=0, max_latency=0, avg_latency=0
            )
        
        sorted_times = sorted(response_times)
        total_requests = len(response_times)
        
        return PerformanceMetrics(
            operation=operation,
            response_times=response_times,
            throughput=total_requests / sum(response_times) if sum(response_times) > 0 else 0,
            success_rate=(total_requests - errors) / total_requests,
            error_count=errors,
            p50_latency=sorted_times[int(total_requests * 0.5)],
            p95_latency=sorted_times[int(total_requests * 0.95)],
            p99_latency=sorted_times[int(total_requests * 0.99)],
            min_latency=min(response_times),
            max_latency=max(response_times),
            avg_latency=statistics.mean(response_times)
        )


class ThroughputBenchmarkRunner:
    """吞吐量基准测试运行器"""
    
    def __init__(self, services):
        self.services = services
    
    async def run_throughput_test(self, operation: str, test_data_generator, 
                                 duration_seconds: int, concurrent_requests: int) -> PerformanceMetrics:
        """运行吞吐量测试"""
        end_time = time.time() + duration_seconds
        response_times = []
        errors = 0
        request_id = 0
        
        async def worker():
            nonlocal request_id, errors
            while time.time() < end_time:
                start_time = time.time()
                try:
                    test_data = test_data_generator(request_id)
                    await self._execute_operation(operation, request_id, test_data)
                except Exception:
                    errors += 1
                
                response_time = time.time() - start_time
                response_times.append(response_time)
                request_id += 1
                
                # 小延迟避免过度占用CPU
                await asyncio.sleep(0.001)
        
        # 并发执行工作者
        tasks = [worker() for _ in range(concurrent_requests)]
        await asyncio.gather(*tasks)
        
        # 计算吞吐量
        total_requests = len(response_times)
        throughput = total_requests / duration_seconds if duration_seconds > 0 else 0
        
        return self._calculate_metrics(operation, response_times, errors, throughput)
    
    async def _execute_operation(self, operation: str, request_id: int, test_data: Dict = None):
        """执行指定操作"""
        if operation == 'intent_recognition':
            message = f'test message {request_id}'
            if test_data:
                message = test_data.get('message', message)
            return await self.services['intent_service'].recognize_intent(message)
        else:
            return await self.services['intent_service'].recognize_intent(f'test {request_id}')
    
    def _calculate_metrics(self, operation: str, response_times: List[float], 
                          errors: int, throughput: float) -> PerformanceMetrics:
        """计算性能指标"""
        if not response_times:
            return PerformanceMetrics(
                operation=operation,
                response_times=[],
                throughput=0,
                success_rate=0,
                error_count=errors,
                p50_latency=0, p95_latency=0, p99_latency=0,
                min_latency=0, max_latency=0, avg_latency=0
            )
        
        sorted_times = sorted(response_times)
        total_requests = len(response_times)
        
        return PerformanceMetrics(
            operation=operation,
            response_times=response_times,
            throughput=throughput,
            success_rate=(total_requests - errors) / total_requests,
            error_count=errors,
            p50_latency=sorted_times[int(total_requests * 0.5)],
            p95_latency=sorted_times[int(total_requests * 0.95)],
            p99_latency=sorted_times[int(total_requests * 0.99)],
            min_latency=min(response_times),
            max_latency=max(response_times),
            avg_latency=statistics.mean(response_times)
        )


class CachePerformanceBenchmarkRunner:
    """缓存性能基准测试运行器"""
    
    def __init__(self, services):
        self.services = services
    
    async def run_cache_test(self, cache_hit_ratio: float, requests: int) -> PerformanceMetrics:
        """运行缓存性能测试"""
        response_times = []
        errors = 0
        
        for i in range(requests):
            start_time = time.time()
            try:
                # 根据缓存命中率决定是否使用缓存
                if i / requests < cache_hit_ratio:
                    await self.services['cache_service'].get(f'key_{i}')
                else:
                    await self.services['conversation_service'].process_message()
            except Exception:
                errors += 1
            
            response_time = time.time() - start_time
            response_times.append(response_time)
        
        return self._calculate_metrics(response_times, errors)
    
    def _calculate_metrics(self, response_times: List[float], errors: int) -> PerformanceMetrics:
        """计算缓存性能指标"""
        if not response_times:
            return PerformanceMetrics(
                operation="cache_test",
                response_times=[],
                throughput=0,
                success_rate=0,
                error_count=errors,
                p50_latency=0, p95_latency=0, p99_latency=0,
                min_latency=0, max_latency=0, avg_latency=0
            )
        
        total_requests = len(response_times)
        return PerformanceMetrics(
            operation="cache_test",
            response_times=response_times,
            throughput=total_requests / sum(response_times) if sum(response_times) > 0 else 0,
            success_rate=(total_requests - errors) / total_requests,
            error_count=errors,
            p50_latency=statistics.quantiles(response_times, n=2)[0],
            p95_latency=statistics.quantiles(response_times, n=20)[18],
            p99_latency=statistics.quantiles(response_times, n=100)[98],
            min_latency=min(response_times),
            max_latency=max(response_times),
            avg_latency=statistics.mean(response_times)
        )


class DatabaseBenchmarkRunner:
    """数据库性能基准测试运行器"""
    
    def __init__(self, services):
        self.services = services
    
    async def run_db_query_test(self, query_type: str, requests: int) -> PerformanceMetrics:
        """运行数据库查询性能测试"""
        response_times = []
        errors = 0
        
        for i in range(requests):
            start_time = time.time()
            try:
                await self.services['conversation_service'].process_message()
            except Exception:
                errors += 1
            
            response_time = time.time() - start_time
            response_times.append(response_time)
        
        total_time = sum(response_times)
        throughput = requests / total_time if total_time > 0 else 0
        
        return PerformanceMetrics(
            operation=f"db_query_{query_type}",
            response_times=response_times,
            throughput=throughput,
            success_rate=(requests - errors) / requests,
            error_count=errors,
            p50_latency=statistics.median(response_times),
            p95_latency=statistics.quantiles(response_times, n=20)[18] if len(response_times) >= 20 else max(response_times),
            p99_latency=statistics.quantiles(response_times, n=100)[98] if len(response_times) >= 100 else max(response_times),
            min_latency=min(response_times),
            max_latency=max(response_times),
            avg_latency=statistics.mean(response_times)
        )


class APIEndpointBenchmarkRunner:
    """API端点性能基准测试运行器"""
    
    def __init__(self, services):
        self.services = services
    
    async def run_endpoint_test(self, endpoint: str, complexity: str, requests: int) -> PerformanceMetrics:
        """运行API端点性能测试"""
        response_times = []
        errors = 0
        
        for i in range(requests):
            start_time = time.time()
            try:
                await self._simulate_endpoint_call(endpoint, complexity)
            except Exception:
                errors += 1
            
            response_time = time.time() - start_time
            response_times.append(response_time)
        
        return PerformanceMetrics(
            operation=f"api_{endpoint.replace('/', '_')}",
            response_times=response_times,
            throughput=requests / sum(response_times) if sum(response_times) > 0 else 0,
            success_rate=(requests - errors) / requests,
            error_count=errors,
            p50_latency=statistics.median(response_times),
            p95_latency=statistics.quantiles(response_times, n=20)[18] if len(response_times) >= 20 else max(response_times),
            p99_latency=statistics.quantiles(response_times, n=100)[98] if len(response_times) >= 100 else max(response_times),
            min_latency=min(response_times),
            max_latency=max(response_times),
            avg_latency=statistics.mean(response_times)
        )
    
    async def _simulate_endpoint_call(self, endpoint: str, complexity: str):
        """模拟API端点调用"""
        if complexity == 'simple':
            await asyncio.sleep(0.01)  # 10ms简单操作
        elif complexity == 'medium':
            await self.services['intent_service'].recognize_intent("test")
            await self.services['slot_service'].extract_slots()
        else:  # complex
            await self.services['conversation_service'].process_message()
            await self.services['intent_service'].recognize_intent("test")
            await self.services['slot_service'].extract_slots()
            await self.services['function_service'].call_function()