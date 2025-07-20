"""
并发负载测试 - TASK-049
测试系统在高并发负载下的性能表现和稳定性
"""
import pytest
import asyncio
import time
import statistics
from typing import List, Dict, Any, Tuple, Optional
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timedelta
import json
import random
import concurrent.futures
from dataclasses import dataclass
import threading
import queue
import psutil

from src.services.intent_service import IntentService
from src.services.conversation_service import ConversationService
from src.services.slot_service import SlotService
from src.services.function_service import FunctionService
from src.services.cache_service import CacheService


@dataclass
class ConcurrentLoadMetrics:
    """并发负载测试指标"""
    test_name: str
    concurrent_users: int
    total_requests: int
    successful_requests: int
    failed_requests: int
    duration: float
    throughput_rps: float
    avg_response_time: float
    p95_response_time: float
    p99_response_time: float
    min_response_time: float
    max_response_time: float
    success_rate: float
    error_rate: float
    peak_memory_mb: float
    avg_cpu_percent: float
    connection_errors: int
    timeout_errors: int


@dataclass
class LoadTestScenario:
    """负载测试场景"""
    name: str
    concurrent_users: int
    ramp_up_time: int
    test_duration: int
    operations_per_user: int
    think_time_range: Tuple[float, float]  # 用户思考时间范围


class TestConcurrentLoadTesting:
    """并发负载测试类"""
    
    @pytest.fixture
    def load_test_config(self):
        """负载测试配置"""
        return {
            'scenarios': [
                LoadTestScenario("light_load", 10, 5, 30, 20, (0.1, 0.5)),
                LoadTestScenario("medium_load", 25, 10, 60, 30, (0.1, 1.0)),
                LoadTestScenario("heavy_load", 50, 15, 90, 40, (0.1, 2.0)),
                LoadTestScenario("stress_test", 100, 20, 120, 50, (0.05, 0.5))
            ],
            'performance_thresholds': {
                'max_response_time': 5.0,
                'min_success_rate': 0.95,
                'max_error_rate': 0.05,
                'max_memory_mb': 1024,
                'max_cpu_percent': 85
            }
        }
    
    @pytest.fixture
    def mock_services(self):
        """创建高并发模拟服务"""
        services = {
            'intent_service': MagicMock(spec=IntentService),
            'conversation_service': MagicMock(spec=ConversationService),
            'slot_service': MagicMock(spec=SlotService),
            'function_service': MagicMock(spec=FunctionService),
            'cache_service': MagicMock(spec=CacheService)
        }
        
        # 设置具有变化延迟的异步方法，模拟真实服务
        for service in services.values():
            common_methods = [
                'recognize_intent', 'save_conversation', 'extract_slots',
                'call_function', 'get', 'set', 'process_message'
            ]
            for method_name in common_methods:
                mock_method = AsyncMock()
                async def variable_latency_operation(*args, **kwargs):
                    # 模拟变化的延迟：80%快速响应，20%慢响应
                    if random.random() < 0.8:
                        await asyncio.sleep(random.uniform(0.01, 0.1))  # 10-100ms
                    else:
                        await asyncio.sleep(random.uniform(0.2, 0.8))   # 200-800ms
                    
                    # 随机模拟错误（5%错误率）
                    if random.random() < 0.05:
                        raise Exception("Simulated service error")
                    
                    return {"status": "success", "data": f"result_{time.time()}"}
                
                mock_method.side_effect = variable_latency_operation
                setattr(service, method_name, mock_method)
        
        return services
    
    @pytest.mark.asyncio
    async def test_light_load_performance(self, mock_services, load_test_config):
        """测试轻负载性能"""
        scenario = load_test_config['scenarios'][0]  # light_load
        thresholds = load_test_config['performance_thresholds']
        
        load_runner = ConcurrentLoadRunner(mock_services)
        metrics = await load_runner.run_load_test(scenario)
        
        # 验证轻负载下的性能表现
        assert metrics.success_rate >= thresholds['min_success_rate']
        assert metrics.avg_response_time <= thresholds['max_response_time']
        assert metrics.error_rate <= thresholds['max_error_rate']
        
        print(f"轻负载性能测试结果:")
        print(f"  并发用户: {metrics.concurrent_users}")
        print(f"  总请求数: {metrics.total_requests}")
        print(f"  吞吐量: {metrics.throughput_rps:.2f} RPS")
        print(f"  平均响应时间: {metrics.avg_response_time:.3f}s")
        print(f"  P95响应时间: {metrics.p95_response_time:.3f}s")
        print(f"  成功率: {metrics.success_rate:.2%}")
    
    @pytest.mark.asyncio
    async def test_medium_load_performance(self, mock_services, load_test_config):
        """测试中等负载性能"""
        scenario = load_test_config['scenarios'][1]  # medium_load
        thresholds = load_test_config['performance_thresholds']
        
        load_runner = ConcurrentLoadRunner(mock_services)
        metrics = await load_runner.run_load_test(scenario)
        
        # 验证中等负载下的性能表现
        assert metrics.success_rate >= 0.90  # 稍微降低成功率要求
        assert metrics.avg_response_time <= thresholds['max_response_time'] * 1.5
        assert metrics.error_rate <= thresholds['max_error_rate'] * 2
        
        print(f"中等负载性能测试结果:")
        print(f"  并发用户: {metrics.concurrent_users}")
        print(f"  总请求数: {metrics.total_requests}")
        print(f"  吞吐量: {metrics.throughput_rps:.2f} RPS")
        print(f"  平均响应时间: {metrics.avg_response_time:.3f}s")
        print(f"  P95响应时间: {metrics.p95_response_time:.3f}s")
        print(f"  成功率: {metrics.success_rate:.2%}")
    
    @pytest.mark.asyncio
    async def test_heavy_load_performance(self, mock_services, load_test_config):
        """测试重负载性能"""
        scenario = load_test_config['scenarios'][2]  # heavy_load
        
        load_runner = ConcurrentLoadRunner(mock_services)
        metrics = await load_runner.run_load_test(scenario)
        
        # 验证重负载下的基本可用性
        assert metrics.success_rate >= 0.80  # 80%成功率
        assert metrics.avg_response_time <= 10.0  # 10秒内响应
        assert metrics.throughput_rps > 0  # 有一定吞吐量
        
        print(f"重负载性能测试结果:")
        print(f"  并发用户: {metrics.concurrent_users}")
        print(f"  总请求数: {metrics.total_requests}")
        print(f"  吞吐量: {metrics.throughput_rps:.2f} RPS")
        print(f"  平均响应时间: {metrics.avg_response_time:.3f}s")
        print(f"  P95响应时间: {metrics.p95_response_time:.3f}s")
        print(f"  成功率: {metrics.success_rate:.2%}")
        print(f"  峰值内存: {metrics.peak_memory_mb:.2f} MB")
    
    @pytest.mark.asyncio
    async def test_stress_test_breaking_point(self, mock_services, load_test_config):
        """测试压力测试和系统极限"""
        scenario = load_test_config['scenarios'][3]  # stress_test
        
        load_runner = ConcurrentLoadRunner(mock_services)
        metrics = await load_runner.run_load_test(scenario)
        
        # 压力测试主要观察系统行为，不严格要求性能指标
        print(f"压力测试结果:")
        print(f"  并发用户: {metrics.concurrent_users}")
        print(f"  总请求数: {metrics.total_requests}")
        print(f"  吞吐量: {metrics.throughput_rps:.2f} RPS")
        print(f"  平均响应时间: {metrics.avg_response_time:.3f}s")
        print(f"  P99响应时间: {metrics.p99_response_time:.3f}s")
        print(f"  成功率: {metrics.success_rate:.2%}")
        print(f"  错误率: {metrics.error_rate:.2%}")
        print(f"  峰值内存: {metrics.peak_memory_mb:.2f} MB")
        print(f"  平均CPU: {metrics.avg_cpu_percent:.1f}%")
        
        # 验证系统在极限负载下没有完全崩溃
        assert metrics.success_rate > 0.5  # 至少50%请求成功
        assert metrics.throughput_rps > 0  # 仍有处理能力
    
    @pytest.mark.asyncio
    async def test_ramp_up_load_pattern(self, mock_services):
        """测试渐增负载模式"""
        ramp_up_runner = RampUpLoadRunner(mock_services)
        
        # 定义渐增负载模式：从5个用户增加到50个用户
        ramp_up_pattern = [
            (5, 30),   # 5个用户，30秒
            (15, 30),  # 15个用户，30秒  
            (30, 30),  # 30个用户，30秒
            (50, 30)   # 50个用户，30秒
        ]
        
        ramp_up_metrics = await ramp_up_runner.run_ramp_up_test(ramp_up_pattern)
        
        # 验证渐增过程中的性能变化
        assert len(ramp_up_metrics) == len(ramp_up_pattern)
        
        # 验证性能随负载变化的趋势
        throughputs = [metric.throughput_rps for metric in ramp_up_metrics]
        response_times = [metric.avg_response_time for metric in ramp_up_metrics]
        
        print(f"渐增负载测试结果:")
        for i, metric in enumerate(ramp_up_metrics):
            users, duration = ramp_up_pattern[i]
            print(f"  阶段{i+1} ({users}用户): 吞吐量 {metric.throughput_rps:.2f} RPS, "
                  f"响应时间 {metric.avg_response_time:.3f}s, 成功率 {metric.success_rate:.2%}")
        
        # 验证吞吐量总体趋势（可能在高负载时下降）
        max_throughput = max(throughputs)
        assert max_throughput > 0
    
    @pytest.mark.asyncio
    async def test_sustained_load_endurance(self, mock_services):
        """测试持续负载耐久性"""
        endurance_runner = EnduranceLoadRunner(mock_services)
        
        # 10分钟持续中等负载
        endurance_scenario = LoadTestScenario(
            name="endurance_test",
            concurrent_users=20,
            ramp_up_time=30,
            test_duration=600,  # 10分钟
            operations_per_user=100,
            think_time_range=(0.5, 2.0)
        )
        
        # 分段监控耐久性测试
        segment_duration = 120  # 每2分钟一个监控段
        endurance_metrics = await endurance_runner.run_endurance_test(
            endurance_scenario, segment_duration
        )
        
        # 验证持续负载下的稳定性
        success_rates = [metric.success_rate for metric in endurance_metrics]
        response_times = [metric.avg_response_time for metric in endurance_metrics]
        
        # 成功率不应显著下降
        success_rate_variance = statistics.variance(success_rates) if len(success_rates) > 1 else 0
        assert success_rate_variance < 0.01  # 成功率方差小于1%
        
        # 响应时间不应持续增长（内存泄漏等问题）
        first_half_avg = statistics.mean(response_times[:len(response_times)//2])
        second_half_avg = statistics.mean(response_times[len(response_times)//2:])
        response_time_degradation = (second_half_avg - first_half_avg) / first_half_avg
        
        assert response_time_degradation < 0.5  # 响应时间增长不超过50%
        
        print(f"持续负载耐久性测试结果:")
        for i, metric in enumerate(endurance_metrics):
            print(f"  时段{i+1}: 吞吐量 {metric.throughput_rps:.2f} RPS, "
                  f"响应时间 {metric.avg_response_time:.3f}s, 成功率 {metric.success_rate:.2%}")
        print(f"  成功率方差: {success_rate_variance:.4f}")
        print(f"  响应时间变化: {response_time_degradation:.2%}")
    
    @pytest.mark.asyncio
    async def test_spike_load_recovery(self, mock_services):
        """测试突发负载恢复能力"""
        spike_runner = SpikeLoadRunner(mock_services)
        
        # 定义突发负载模式
        spike_pattern = [
            (10, 60),   # 基线：10用户，60秒
            (100, 30),  # 突发：100用户，30秒
            (10, 60)    # 恢复：10用户，60秒
        ]
        
        spike_metrics = await spike_runner.run_spike_test(spike_pattern)
        
        # 验证突发负载处理和恢复
        baseline_metric = spike_metrics[0]
        spike_metric = spike_metrics[1]
        recovery_metric = spike_metrics[2]
        
        # 验证系统在突发负载下没有完全失效
        assert spike_metric.success_rate > 0.3  # 突发时至少30%成功率
        
        # 验证系统能够恢复到基线性能
        recovery_ratio = recovery_metric.success_rate / baseline_metric.success_rate
        assert recovery_ratio > 0.8  # 恢复到基线80%性能
        
        print(f"突发负载恢复测试结果:")
        print(f"  基线性能: 吞吐量 {baseline_metric.throughput_rps:.2f} RPS, "
              f"成功率 {baseline_metric.success_rate:.2%}")
        print(f"  突发负载: 吞吐量 {spike_metric.throughput_rps:.2f} RPS, "
              f"成功率 {spike_metric.success_rate:.2%}")
        print(f"  恢复性能: 吞吐量 {recovery_metric.throughput_rps:.2f} RPS, "
              f"成功率 {recovery_metric.success_rate:.2%}")
        print(f"  恢复率: {recovery_ratio:.2%}")
    
    @pytest.mark.asyncio
    async def test_mixed_workload_concurrency(self, mock_services):
        """测试混合工作负载并发"""
        workload_runner = MixedWorkloadRunner(mock_services)
        
        # 定义不同类型的工作负载
        workload_types = [
            {"name": "intent_recognition", "weight": 0.4, "complexity": "low"},
            {"name": "conversation_flow", "weight": 0.3, "complexity": "medium"},
            {"name": "slot_extraction", "weight": 0.2, "complexity": "medium"},
            {"name": "function_calls", "weight": 0.1, "complexity": "high"}
        ]
        
        mixed_metrics = await workload_runner.run_mixed_workload_test(
            concurrent_users=30,
            test_duration=90,
            workload_types=workload_types
        )
        
        # 验证混合工作负载的整体性能
        assert mixed_metrics.success_rate >= 0.85
        assert mixed_metrics.avg_response_time <= 3.0
        assert mixed_metrics.throughput_rps > 0
        
        print(f"混合工作负载并发测试结果:")
        print(f"  总吞吐量: {mixed_metrics.throughput_rps:.2f} RPS")
        print(f"  平均响应时间: {mixed_metrics.avg_response_time:.3f}s")
        print(f"  P95响应时间: {mixed_metrics.p95_response_time:.3f}s")
        print(f"  成功率: {mixed_metrics.success_rate:.2%}")
        print(f"  峰值内存: {mixed_metrics.peak_memory_mb:.2f} MB")
    
    @pytest.mark.asyncio
    async def test_connection_pool_saturation(self, mock_services):
        """测试连接池饱和处理"""
        connection_runner = ConnectionPoolTestRunner(mock_services)
        
        # 测试连接池在高并发下的表现
        connection_metrics = await connection_runner.test_connection_pool_limits(
            max_concurrent_connections=50,
            connection_attempts=200,
            test_duration=60
        )
        
        # 验证连接池管理
        assert connection_metrics['connection_errors'] < connection_metrics['total_attempts'] * 0.2
        assert connection_metrics['successful_connections'] > 0
        
        print(f"连接池饱和测试结果:")
        print(f"  总连接尝试: {connection_metrics['total_attempts']}")
        print(f"  成功连接: {connection_metrics['successful_connections']}")
        print(f"  连接错误: {connection_metrics['connection_errors']}")
        print(f"  超时错误: {connection_metrics['timeout_errors']}")
        print(f"  连接成功率: {connection_metrics['connection_success_rate']:.2%}")
    
    @pytest.mark.asyncio
    async def test_memory_pressure_under_load(self, mock_services):
        """测试负载下的内存压力"""
        memory_runner = MemoryPressureTestRunner(mock_services)
        
        # 在内存压力下测试系统表现
        memory_metrics = await memory_runner.test_memory_pressure_performance(
            concurrent_users=40,
            memory_pressure_mb=800,  # 800MB内存压力
            test_duration=120
        )
        
        # 验证内存压力下的系统稳定性
        assert memory_metrics.success_rate > 0.7  # 70%成功率
        assert memory_metrics.peak_memory_mb < 1200  # 内存使用不超过1.2GB
        
        print(f"内存压力负载测试结果:")
        print(f"  内存压力下成功率: {memory_metrics.success_rate:.2%}")
        print(f"  峰值内存使用: {memory_metrics.peak_memory_mb:.2f} MB")
        print(f"  平均响应时间: {memory_metrics.avg_response_time:.3f}s")
        print(f"  吞吐量: {memory_metrics.throughput_rps:.2f} RPS")


class ConcurrentLoadRunner:
    """并发负载测试运行器"""
    
    def __init__(self, services):
        self.services = services
        self.response_times = []
        self.errors = []
        self.results_queue = queue.Queue()
    
    async def run_load_test(self, scenario: LoadTestScenario) -> ConcurrentLoadMetrics:
        """运行负载测试"""
        start_time = time.time()
        
        # 启动资源监控
        monitor_task = asyncio.create_task(self._monitor_resources())
        
        # 创建用户任务
        user_tasks = []
        for user_id in range(scenario.concurrent_users):
            # 分散启动时间（ramp-up）
            start_delay = (user_id / scenario.concurrent_users) * scenario.ramp_up_time
            task = asyncio.create_task(
                self._simulate_user(user_id, scenario, start_delay)
            )
            user_tasks.append(task)
        
        # 等待所有用户完成
        await asyncio.gather(*user_tasks, return_exceptions=True)
        
        # 停止监控
        monitor_task.cancel()
        try:
            monitor_data = await monitor_task
        except asyncio.CancelledError:
            monitor_data = {'peak_memory': 0, 'avg_cpu': 0}
        
        # 计算指标
        total_duration = time.time() - start_time
        return self._calculate_metrics(scenario, total_duration, monitor_data)
    
    async def _simulate_user(self, user_id: int, scenario: LoadTestScenario, start_delay: float):
        """模拟单个用户的行为"""
        await asyncio.sleep(start_delay)
        
        user_start_time = time.time()
        end_time = user_start_time + scenario.test_duration
        operations_completed = 0
        
        while time.time() < end_time and operations_completed < scenario.operations_per_user:
            operation_start = time.time()
            
            try:
                # 随机选择操作类型
                operation = random.choice([
                    self._intent_recognition_operation,
                    self._conversation_operation,
                    self._slot_extraction_operation
                ])
                
                await operation(user_id, operations_completed)
                
                operation_time = time.time() - operation_start
                self.response_times.append(operation_time)
                
            except Exception as e:
                self.errors.append({
                    'user_id': user_id,
                    'operation': operations_completed,
                    'error': str(e),
                    'timestamp': time.time()
                })
            
            operations_completed += 1
            
            # 用户思考时间
            think_time = random.uniform(*scenario.think_time_range)
            await asyncio.sleep(think_time)
    
    async def _intent_recognition_operation(self, user_id: int, operation_id: int):
        """意图识别操作"""
        message = f"用户{user_id}的第{operation_id}条消息"
        return await self.services['intent_service'].recognize_intent(message)
    
    async def _conversation_operation(self, user_id: int, operation_id: int):
        """对话操作"""
        await self.services['conversation_service'].process_message()
        return await self.services['conversation_service'].save_conversation()
    
    async def _slot_extraction_operation(self, user_id: int, operation_id: int):
        """槽位提取操作"""
        return await self.services['slot_service'].extract_slots()
    
    async def _monitor_resources(self):
        """监控系统资源"""
        peak_memory = 0
        cpu_readings = []
        
        try:
            while True:
                # 内存监控
                memory_mb = psutil.Process().memory_info().rss / 1024 / 1024
                peak_memory = max(peak_memory, memory_mb)
                
                # CPU监控
                cpu_percent = psutil.cpu_percent(interval=1)
                cpu_readings.append(cpu_percent)
                
                await asyncio.sleep(1)
        except asyncio.CancelledError:
            pass
        
        return {
            'peak_memory': peak_memory,
            'avg_cpu': statistics.mean(cpu_readings) if cpu_readings else 0
        }
    
    def _calculate_metrics(self, scenario: LoadTestScenario, duration: float, 
                          monitor_data: Dict) -> ConcurrentLoadMetrics:
        """计算负载测试指标"""
        total_requests = len(self.response_times) + len(self.errors)
        successful_requests = len(self.response_times)
        failed_requests = len(self.errors)
        
        if not self.response_times:
            return ConcurrentLoadMetrics(
                test_name=scenario.name,
                concurrent_users=scenario.concurrent_users,
                total_requests=total_requests,
                successful_requests=0,
                failed_requests=failed_requests,
                duration=duration,
                throughput_rps=0,
                avg_response_time=0,
                p95_response_time=0,
                p99_response_time=0,
                min_response_time=0,
                max_response_time=0,
                success_rate=0,
                error_rate=1.0,
                peak_memory_mb=monitor_data.get('peak_memory', 0),
                avg_cpu_percent=monitor_data.get('avg_cpu', 0),
                connection_errors=0,
                timeout_errors=0
            )
        
        sorted_times = sorted(self.response_times)
        
        return ConcurrentLoadMetrics(
            test_name=scenario.name,
            concurrent_users=scenario.concurrent_users,
            total_requests=total_requests,
            successful_requests=successful_requests,
            failed_requests=failed_requests,
            duration=duration,
            throughput_rps=successful_requests / duration if duration > 0 else 0,
            avg_response_time=statistics.mean(self.response_times),
            p95_response_time=sorted_times[int(len(sorted_times) * 0.95)],
            p99_response_time=sorted_times[int(len(sorted_times) * 0.99)],
            min_response_time=min(self.response_times),
            max_response_time=max(self.response_times),
            success_rate=successful_requests / total_requests if total_requests > 0 else 0,
            error_rate=failed_requests / total_requests if total_requests > 0 else 0,
            peak_memory_mb=monitor_data.get('peak_memory', 0),
            avg_cpu_percent=monitor_data.get('avg_cpu', 0),
            connection_errors=len([e for e in self.errors if 'connection' in e.get('error', '').lower()]),
            timeout_errors=len([e for e in self.errors if 'timeout' in e.get('error', '').lower()])
        )


class RampUpLoadRunner:
    """渐增负载测试运行器"""
    
    def __init__(self, services):
        self.services = services
    
    async def run_ramp_up_test(self, ramp_up_pattern: List[Tuple[int, int]]) -> List[ConcurrentLoadMetrics]:
        """运行渐增负载测试"""
        metrics_list = []
        
        for users, duration in ramp_up_pattern:
            scenario = LoadTestScenario(
                name=f"ramp_up_{users}_users",
                concurrent_users=users,
                ramp_up_time=min(10, duration // 3),  # 渐增时间为总时间的1/3
                test_duration=duration,
                operations_per_user=duration // 2,  # 每2秒一个操作
                think_time_range=(1.0, 3.0)
            )
            
            load_runner = ConcurrentLoadRunner(self.services)
            metrics = await load_runner.run_load_test(scenario)
            metrics_list.append(metrics)
            
            # 阶段间短暂休息
            await asyncio.sleep(5)
        
        return metrics_list


class EnduranceLoadRunner:
    """耐久性负载测试运行器"""
    
    def __init__(self, services):
        self.services = services
    
    async def run_endurance_test(self, scenario: LoadTestScenario, 
                                segment_duration: int) -> List[ConcurrentLoadMetrics]:
        """运行耐久性测试"""
        total_segments = scenario.test_duration // segment_duration
        metrics_list = []
        
        for segment in range(total_segments):
            segment_scenario = LoadTestScenario(
                name=f"{scenario.name}_segment_{segment}",
                concurrent_users=scenario.concurrent_users,
                ramp_up_time=min(30, segment_duration // 4),
                test_duration=segment_duration,
                operations_per_user=segment_duration // 6,  # 每6秒一个操作
                think_time_range=scenario.think_time_range
            )
            
            load_runner = ConcurrentLoadRunner(self.services)
            segment_metrics = await load_runner.run_load_test(segment_scenario)
            metrics_list.append(segment_metrics)
        
        return metrics_list


class SpikeLoadRunner:
    """突发负载测试运行器"""
    
    def __init__(self, services):
        self.services = services
    
    async def run_spike_test(self, spike_pattern: List[Tuple[int, int]]) -> List[ConcurrentLoadMetrics]:
        """运行突发负载测试"""
        metrics_list = []
        
        for i, (users, duration) in enumerate(spike_pattern):
            phase_name = ["baseline", "spike", "recovery"][i] if i < 3 else f"phase_{i}"
            
            scenario = LoadTestScenario(
                name=f"spike_{phase_name}",
                concurrent_users=users,
                ramp_up_time=5 if phase_name == "spike" else 15,  # 突发阶段快速启动
                test_duration=duration,
                operations_per_user=duration // 3,
                think_time_range=(0.1, 1.0) if phase_name == "spike" else (1.0, 3.0)
            )
            
            load_runner = ConcurrentLoadRunner(self.services)
            metrics = await load_runner.run_load_test(scenario)
            metrics_list.append(metrics)
        
        return metrics_list


class MixedWorkloadRunner:
    """混合工作负载测试运行器"""
    
    def __init__(self, services):
        self.services = services
    
    async def run_mixed_workload_test(self, concurrent_users: int, test_duration: int, 
                                    workload_types: List[Dict]) -> ConcurrentLoadMetrics:
        """运行混合工作负载测试"""
        # 根据权重分配用户到不同工作负载
        user_workloads = []
        total_weight = sum(wl['weight'] for wl in workload_types)
        
        start_user = 0
        for workload in workload_types:
            users_for_workload = int(concurrent_users * workload['weight'] / total_weight)
            user_workloads.extend([workload] * users_for_workload)
        
        # 确保用户数匹配
        while len(user_workloads) < concurrent_users:
            user_workloads.append(workload_types[0])
        
        load_runner = ConcurrentLoadRunner(self.services)
        
        # 自定义用户模拟以支持不同工作负载
        async def mixed_user_simulation(user_id: int):
            workload = user_workloads[user_id % len(user_workloads)]
            operations_per_user = test_duration // (3 if workload['complexity'] == 'high' else 
                                                   2 if workload['complexity'] == 'medium' else 1)
            
            scenario = LoadTestScenario(
                name=workload['name'],
                concurrent_users=1,
                ramp_up_time=0,
                test_duration=test_duration,
                operations_per_user=operations_per_user,
                think_time_range=(0.5, 2.0)
            )
            
            await load_runner._simulate_user(user_id, scenario, 0)
        
        # 启动混合工作负载
        start_time = time.time()
        monitor_task = asyncio.create_task(load_runner._monitor_resources())
        
        user_tasks = [mixed_user_simulation(i) for i in range(concurrent_users)]
        await asyncio.gather(*user_tasks, return_exceptions=True)
        
        monitor_task.cancel()
        try:
            monitor_data = await monitor_task
        except asyncio.CancelledError:
            monitor_data = {'peak_memory': 0, 'avg_cpu': 0}
        
        duration = time.time() - start_time
        
        # 创建虚拟场景用于指标计算
        virtual_scenario = LoadTestScenario(
            name="mixed_workload",
            concurrent_users=concurrent_users,
            ramp_up_time=30,
            test_duration=test_duration,
            operations_per_user=0,
            think_time_range=(0.5, 2.0)
        )
        
        return load_runner._calculate_metrics(virtual_scenario, duration, monitor_data)


class ConnectionPoolTestRunner:
    """连接池测试运行器"""
    
    def __init__(self, services):
        self.services = services
    
    async def test_connection_pool_limits(self, max_concurrent_connections: int, 
                                        connection_attempts: int, test_duration: int) -> Dict[str, Any]:
        """测试连接池限制"""
        successful_connections = 0
        connection_errors = 0
        timeout_errors = 0
        
        async def attempt_connection(attempt_id: int):
            nonlocal successful_connections, connection_errors, timeout_errors
            
            try:
                # 模拟连接操作
                await self.services['cache_service'].get(f"connection_test_{attempt_id}")
                successful_connections += 1
            except asyncio.TimeoutError:
                timeout_errors += 1
            except Exception:
                connection_errors += 1
        
        # 并发连接尝试
        connection_tasks = [
            attempt_connection(i) for i in range(connection_attempts)
        ]
        
        # 限制并发连接数
        semaphore = asyncio.Semaphore(max_concurrent_connections)
        
        async def limited_connection(task):
            async with semaphore:
                await task
        
        limited_tasks = [limited_connection(task) for task in connection_tasks]
        await asyncio.gather(*limited_tasks, return_exceptions=True)
        
        return {
            'total_attempts': connection_attempts,
            'successful_connections': successful_connections,
            'connection_errors': connection_errors,
            'timeout_errors': timeout_errors,
            'connection_success_rate': successful_connections / connection_attempts
        }


class MemoryPressureTestRunner:
    """内存压力测试运行器"""
    
    def __init__(self, services):
        self.services = services
        self.memory_ballast = []
    
    async def test_memory_pressure_performance(self, concurrent_users: int, 
                                             memory_pressure_mb: int, test_duration: int) -> ConcurrentLoadMetrics:
        """测试内存压力下的性能"""
        # 创建内存压力
        self._create_memory_pressure(memory_pressure_mb)
        
        try:
            # 在内存压力下运行负载测试
            scenario = LoadTestScenario(
                name="memory_pressure_test",
                concurrent_users=concurrent_users,
                ramp_up_time=30,
                test_duration=test_duration,
                operations_per_user=test_duration // 3,
                think_time_range=(1.0, 3.0)
            )
            
            load_runner = ConcurrentLoadRunner(self.services)
            return await load_runner.run_load_test(scenario)
            
        finally:
            # 清理内存压力
            self._cleanup_memory_pressure()
    
    def _create_memory_pressure(self, memory_mb: int):
        """创建内存压力"""
        # 分配指定大小的内存
        chunk_size = 1024 * 1024  # 1MB chunks
        chunks_needed = memory_mb
        
        for _ in range(chunks_needed):
            # 创建1MB的字节数组
            chunk = bytearray(chunk_size)
            self.memory_ballast.append(chunk)
    
    def _cleanup_memory_pressure(self):
        """清理内存压力"""
        self.memory_ballast.clear()
        import gc
        gc.collect()