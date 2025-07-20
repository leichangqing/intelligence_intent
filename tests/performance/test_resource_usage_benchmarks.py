"""
内存和CPU使用率基准测试 - TASK-049
测试系统的资源使用情况和内存泄漏检测
"""
import pytest
import asyncio
import time
import psutil
import gc
import sys
import threading
from typing import List, Dict, Any, Tuple
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timedelta
import json
from dataclasses import dataclass
import tracemalloc
import resource
import concurrent.futures

from src.services.intent_service import IntentService
from src.services.conversation_service import ConversationService
from src.services.slot_service import SlotService
from src.services.function_service import FunctionService
from src.services.cache_service import CacheService


@dataclass
class ResourceMetrics:
    """资源使用指标数据类"""
    operation: str
    duration: float
    cpu_usage_percent: List[float]
    memory_usage_mb: List[float]
    peak_memory_mb: float
    memory_growth_mb: float
    gc_collections: Dict[int, int]
    thread_count: List[int]
    file_descriptors: List[int]
    avg_cpu_usage: float
    avg_memory_usage: float
    memory_leak_detected: bool


class TestResourceUsageBenchmarks:
    """内存和CPU使用率基准测试类"""
    
    @pytest.fixture
    def resource_config(self):
        """资源测试配置"""
        return {
            'monitoring_interval': 0.1,  # 100ms监控间隔
            'test_duration': 30,  # 30秒测试时长
            'memory_threshold_mb': 512,  # 512MB内存阈值
            'cpu_threshold_percent': 80,  # 80% CPU阈值
            'memory_leak_threshold_mb': 50,  # 50MB内存泄漏阈值
            'warmup_time': 5  # 5秒预热时间
        }
    
    @pytest.fixture
    def mock_services(self):
        """创建资源感知的模拟服务"""
        services = {
            'intent_service': MagicMock(spec=IntentService),
            'conversation_service': MagicMock(spec=ConversationService),
            'slot_service': MagicMock(spec=SlotService),
            'function_service': MagicMock(spec=FunctionService),
            'cache_service': MagicMock(spec=CacheService)
        }
        
        # 设置模拟内存和CPU消耗的方法
        for service in services.values():
            common_methods = [
                'recognize_intent', 'save_conversation', 'extract_slots',
                'call_function', 'get', 'set', 'process_message'
            ]
            for method_name in common_methods:
                mock_method = AsyncMock()
                async def resource_consuming_operation(*args, **kwargs):
                    # 模拟CPU和内存使用
                    await asyncio.sleep(0.01)  # IO等待
                    dummy_data = [i for i in range(1000)]  # 小内存分配
                    return {"status": "success", "data": dummy_data}
                mock_method.side_effect = resource_consuming_operation
                setattr(service, method_name, mock_method)
        
        return services
    
    @pytest.mark.asyncio
    async def test_memory_usage_baseline_benchmark(self, mock_services, resource_config):
        """测试内存使用基线基准"""
        monitor = ResourceMonitor()
        
        # 启动内存监控
        monitoring_task = asyncio.create_task(
            monitor.monitor_resources(
                interval=resource_config['monitoring_interval'],
                duration=resource_config['test_duration']
            )
        )
        
        # 执行基线操作
        baseline_runner = BaselineResourceRunner(mock_services)
        await baseline_runner.run_baseline_operations(
            operations_per_second=10,
            duration=resource_config['test_duration']
        )
        
        # 获取监控结果
        metrics = await monitoring_task
        
        # 验证内存使用
        assert metrics.peak_memory_mb < resource_config['memory_threshold_mb']
        assert metrics.memory_growth_mb < resource_config['memory_leak_threshold_mb']
        assert not metrics.memory_leak_detected
        
        print(f"内存使用基线基准结果:")
        print(f"  峰值内存: {metrics.peak_memory_mb:.2f} MB")
        print(f"  内存增长: {metrics.memory_growth_mb:.2f} MB")
        print(f"  平均内存: {metrics.avg_memory_usage:.2f} MB")
        print(f"  内存泄漏: {'是' if metrics.memory_leak_detected else '否'}")
    
    @pytest.mark.asyncio
    async def test_cpu_usage_under_load_benchmark(self, mock_services, resource_config):
        """测试负载下CPU使用率基准"""
        monitor = ResourceMonitor()
        
        # 启动CPU监控
        monitoring_task = asyncio.create_task(
            monitor.monitor_resources(
                interval=resource_config['monitoring_interval'],
                duration=resource_config['test_duration']
            )
        )
        
        # 执行高负载操作
        load_runner = CPULoadRunner(mock_services)
        await load_runner.run_cpu_intensive_operations(
            concurrent_tasks=20,
            operations_per_task=100
        )
        
        # 获取监控结果
        metrics = await monitoring_task
        
        # 验证CPU使用
        assert metrics.avg_cpu_usage < resource_config['cpu_threshold_percent']
        assert max(metrics.cpu_usage_percent) < 95  # CPU峰值不超过95%
        
        print(f"CPU使用负载基准结果:")
        print(f"  平均CPU: {metrics.avg_cpu_usage:.2f}%")
        print(f"  峰值CPU: {max(metrics.cpu_usage_percent):.2f}%")
        print(f"  CPU波动: {max(metrics.cpu_usage_percent) - min(metrics.cpu_usage_percent):.2f}%")
    
    @pytest.mark.asyncio
    async def test_memory_leak_detection_benchmark(self, mock_services, resource_config):
        """测试内存泄漏检测基准"""
        # 开启内存追踪
        tracemalloc.start()
        
        monitor = ResourceMonitor()
        leak_detector = MemoryLeakDetector()
        
        # 运行可能导致内存泄漏的操作
        leak_runner = MemoryLeakTestRunner(mock_services)
        
        # 分阶段执行，监控内存变化
        phases = [
            {"operations": 100, "description": "阶段1: 正常操作"},
            {"operations": 200, "description": "阶段2: 中等负载"},
            {"operations": 300, "description": "阶段3: 高负载"}
        ]
        
        memory_snapshots = []
        
        for i, phase in enumerate(phases):
            # 记录阶段开始内存
            start_memory = psutil.Process().memory_info().rss / 1024 / 1024
            
            # 执行阶段操作
            await leak_runner.run_operations(phase["operations"])
            
            # 强制垃圾回收
            gc.collect()
            await asyncio.sleep(1)
            
            # 记录阶段结束内存
            end_memory = psutil.Process().memory_info().rss / 1024 / 1024
            
            memory_snapshots.append({
                'phase': i + 1,
                'description': phase["description"],
                'start_memory': start_memory,
                'end_memory': end_memory,
                'growth': end_memory - start_memory
            })
        
        # 分析内存泄漏
        leak_analysis = leak_detector.analyze_memory_leaks(memory_snapshots)
        
        # 验证内存泄漏检测
        total_growth = sum(snapshot['growth'] for snapshot in memory_snapshots)
        assert total_growth < resource_config['memory_leak_threshold_mb']
        
        print(f"内存泄漏检测基准结果:")
        for snapshot in memory_snapshots:
            print(f"  {snapshot['description']}: {snapshot['growth']:+.2f} MB")
        print(f"  总内存增长: {total_growth:.2f} MB")
        print(f"  泄漏检测: {'检测到泄漏' if leak_analysis['leak_detected'] else '无泄漏'}")
        
        tracemalloc.stop()
    
    @pytest.mark.asyncio
    async def test_garbage_collection_impact_benchmark(self, mock_services, resource_config):
        """测试垃圾回收影响基准"""
        gc_monitor = GarbageCollectionMonitor()
        
        # 记录GC开始状态
        gc_start_stats = gc.get_stats()
        
        # 执行会产生大量对象的操作
        gc_runner = GarbageCollectionTestRunner(mock_services)
        
        await gc_runner.run_object_intensive_operations(
            iterations=1000,
            objects_per_iteration=1000
        )
        
        # 记录GC结束状态
        gc_end_stats = gc.get_stats()
        
        # 分析GC影响
        gc_impact = gc_monitor.analyze_gc_impact(gc_start_stats, gc_end_stats)
        
        # 验证GC性能
        assert gc_impact['total_collections'] < 100  # 总GC次数合理
        assert gc_impact['avg_pause_time'] < 0.1  # 平均暂停时间小于100ms
        
        print(f"垃圾回收影响基准结果:")
        print(f"  总GC次数: {gc_impact['total_collections']}")
        print(f"  第0代GC: {gc_impact['gen0_collections']}")
        print(f"  第1代GC: {gc_impact['gen1_collections']}")
        print(f"  第2代GC: {gc_impact['gen2_collections']}")
        print(f"  估计暂停时间: {gc_impact['avg_pause_time']:.3f}s")
    
    @pytest.mark.asyncio
    async def test_thread_usage_benchmark(self, mock_services, resource_config):
        """测试线程使用基准"""
        thread_monitor = ThreadUsageMonitor()
        
        # 记录初始线程数
        initial_thread_count = threading.active_count()
        
        # 执行多线程操作
        thread_runner = ThreadUsageTestRunner(mock_services)
        
        thread_metrics = await thread_runner.run_concurrent_operations(
            max_threads=50,
            operations_per_thread=20,
            monitoring_interval=resource_config['monitoring_interval']
        )
        
        # 验证线程使用
        peak_threads = max(thread_metrics['thread_counts'])
        final_thread_count = threading.active_count()
        
        # 验证线程清理
        assert final_thread_count <= initial_thread_count + 2  # 允许少量线程增长
        assert peak_threads <= 100  # 峰值线程数合理
        
        print(f"线程使用基准结果:")
        print(f"  初始线程数: {initial_thread_count}")
        print(f"  峰值线程数: {peak_threads}")
        print(f"  最终线程数: {final_thread_count}")
        print(f"  平均线程数: {sum(thread_metrics['thread_counts']) / len(thread_metrics['thread_counts']):.1f}")
    
    @pytest.mark.asyncio
    async def test_file_descriptor_usage_benchmark(self, mock_services, resource_config):
        """测试文件描述符使用基准"""
        if sys.platform == 'win32':
            pytest.skip("文件描述符测试在Windows上不适用")
        
        fd_monitor = FileDescriptorMonitor()
        
        # 记录初始文件描述符数
        initial_fd_count = fd_monitor.get_fd_count()
        
        # 执行文件操作密集的任务
        fd_runner = FileDescriptorTestRunner(mock_services)
        
        fd_metrics = await fd_runner.run_io_intensive_operations(
            concurrent_operations=30,
            operations_per_task=10
        )
        
        # 记录最终文件描述符数
        final_fd_count = fd_monitor.get_fd_count()
        
        # 验证文件描述符清理
        fd_growth = final_fd_count - initial_fd_count
        assert fd_growth <= 10  # 文件描述符增长合理
        
        print(f"文件描述符使用基准结果:")
        print(f"  初始FD数: {initial_fd_count}")
        print(f"  峰值FD数: {max(fd_metrics['fd_counts'])}")
        print(f"  最终FD数: {final_fd_count}")
        print(f"  FD增长: {fd_growth}")
    
    @pytest.mark.asyncio
    async def test_sustained_load_memory_stability(self, mock_services, resource_config):
        """测试持续负载下的内存稳定性"""
        stability_monitor = MemoryStabilityMonitor()
        
        # 执行长时间持续负载
        stability_runner = SustainedLoadRunner(mock_services)
        
        stability_metrics = await stability_runner.run_sustained_load(
            duration_minutes=5,  # 5分钟持续负载
            operations_per_second=20,
            monitoring_interval=resource_config['monitoring_interval']
        )
        
        # 分析内存稳定性
        stability_analysis = stability_monitor.analyze_stability(stability_metrics)
        
        # 验证内存稳定性
        assert stability_analysis['memory_trend'] in ['stable', 'decreasing']  # 内存趋势稳定或下降
        assert stability_analysis['memory_variance'] < 50  # 内存方差小于50MB
        assert not stability_analysis['leak_detected']  # 无内存泄漏
        
        print(f"持续负载内存稳定性基准结果:")
        print(f"  内存趋势: {stability_analysis['memory_trend']}")
        print(f"  内存方差: {stability_analysis['memory_variance']:.2f} MB")
        print(f"  最大内存: {max(stability_metrics['memory_usage']):.2f} MB")
        print(f"  内存波动: {max(stability_metrics['memory_usage']) - min(stability_metrics['memory_usage']):.2f} MB")
    
    @pytest.mark.asyncio
    async def test_resource_cleanup_benchmark(self, mock_services, resource_config):
        """测试资源清理基准"""
        cleanup_monitor = ResourceCleanupMonitor()
        
        # 记录清理前资源状态
        pre_cleanup_state = cleanup_monitor.get_resource_state()
        
        # 执行资源密集操作
        cleanup_runner = ResourceCleanupTestRunner(mock_services)
        
        await cleanup_runner.run_resource_intensive_operations(
            iterations=100,
            resources_per_iteration=50
        )
        
        # 记录清理前状态
        post_operations_state = cleanup_monitor.get_resource_state()
        
        # 执行清理操作
        await cleanup_runner.cleanup_resources()
        
        # 等待清理完成
        await asyncio.sleep(2)
        gc.collect()
        
        # 记录清理后状态
        post_cleanup_state = cleanup_monitor.get_resource_state()
        
        # 验证资源清理效果
        memory_cleanup_ratio = (post_operations_state['memory'] - post_cleanup_state['memory']) / post_operations_state['memory']
        
        assert memory_cleanup_ratio > 0.5  # 至少清理50%内存
        assert post_cleanup_state['threads'] <= pre_cleanup_state['threads'] + 2
        
        print(f"资源清理基准结果:")
        print(f"  操作前内存: {pre_cleanup_state['memory']:.2f} MB")
        print(f"  操作后内存: {post_operations_state['memory']:.2f} MB")
        print(f"  清理后内存: {post_cleanup_state['memory']:.2f} MB")
        print(f"  清理效率: {memory_cleanup_ratio:.1%}")


class ResourceMonitor:
    """资源监控器"""
    
    async def monitor_resources(self, interval: float, duration: int) -> ResourceMetrics:
        """监控资源使用"""
        cpu_usage = []
        memory_usage = []
        thread_counts = []
        fd_counts = []
        
        start_time = time.time()
        start_memory = psutil.Process().memory_info().rss / 1024 / 1024
        
        while time.time() - start_time < duration:
            # 收集CPU使用率
            cpu_percent = psutil.cpu_percent(interval=0.1)
            cpu_usage.append(cpu_percent)
            
            # 收集内存使用
            memory_mb = psutil.Process().memory_info().rss / 1024 / 1024
            memory_usage.append(memory_mb)
            
            # 收集线程数
            thread_count = threading.active_count()
            thread_counts.append(thread_count)
            
            # 收集文件描述符数（Linux/Mac）
            if hasattr(psutil.Process(), 'num_fds'):
                try:
                    fd_count = psutil.Process().num_fds()
                    fd_counts.append(fd_count)
                except:
                    fd_counts.append(0)
            
            await asyncio.sleep(interval)
        
        end_memory = psutil.Process().memory_info().rss / 1024 / 1024
        memory_growth = end_memory - start_memory
        
        # 检测内存泄漏
        memory_leak_detected = memory_growth > 50 and memory_growth > start_memory * 0.2
        
        return ResourceMetrics(
            operation="resource_monitoring",
            duration=duration,
            cpu_usage_percent=cpu_usage,
            memory_usage_mb=memory_usage,
            peak_memory_mb=max(memory_usage) if memory_usage else 0,
            memory_growth_mb=memory_growth,
            gc_collections=dict(enumerate(gc.get_stats())),
            thread_count=thread_counts,
            file_descriptors=fd_counts,
            avg_cpu_usage=sum(cpu_usage) / len(cpu_usage) if cpu_usage else 0,
            avg_memory_usage=sum(memory_usage) / len(memory_usage) if memory_usage else 0,
            memory_leak_detected=memory_leak_detected
        )


class BaselineResourceRunner:
    """基线资源测试运行器"""
    
    def __init__(self, services):
        self.services = services
    
    async def run_baseline_operations(self, operations_per_second: int, duration: int):
        """运行基线操作"""
        interval = 1.0 / operations_per_second
        end_time = time.time() + duration
        
        while time.time() < end_time:
            await self.services['intent_service'].recognize_intent("test message")
            await asyncio.sleep(interval)


class CPULoadRunner:
    """CPU负载测试运行器"""
    
    def __init__(self, services):
        self.services = services
    
    async def run_cpu_intensive_operations(self, concurrent_tasks: int, operations_per_task: int):
        """运行CPU密集操作"""
        async def cpu_task():
            for _ in range(operations_per_task):
                await self.services['intent_service'].recognize_intent("cpu intensive test")
                await self.services['slot_service'].extract_slots()
                # 模拟CPU计算
                _ = sum(i * i for i in range(1000))
        
        tasks = [cpu_task() for _ in range(concurrent_tasks)]
        await asyncio.gather(*tasks)


class MemoryLeakTestRunner:
    """内存泄漏测试运行器"""
    
    def __init__(self, services):
        self.services = services
        self.data_store = []  # 模拟可能导致泄漏的数据存储
    
    async def run_operations(self, operations: int):
        """运行可能导致内存泄漏的操作"""
        for i in range(operations):
            await self.services['conversation_service'].process_message()
            
            # 模拟数据积累（潜在内存泄漏）
            if i % 10 == 0:
                self.data_store.append([j for j in range(1000)])


class MemoryLeakDetector:
    """内存泄漏检测器"""
    
    def analyze_memory_leaks(self, memory_snapshots: List[Dict]) -> Dict[str, Any]:
        """分析内存泄漏"""
        total_growth = sum(snapshot['growth'] for snapshot in memory_snapshots)
        
        # 简单的泄漏检测逻辑
        leak_detected = total_growth > 50 or any(snapshot['growth'] > 30 for snapshot in memory_snapshots)
        
        return {
            'leak_detected': leak_detected,
            'total_growth': total_growth,
            'max_single_growth': max(snapshot['growth'] for snapshot in memory_snapshots),
            'growth_trend': 'increasing' if total_growth > 0 else 'stable'
        }


class GarbageCollectionMonitor:
    """垃圾回收监控器"""
    
    def analyze_gc_impact(self, start_stats: List[Dict], end_stats: List[Dict]) -> Dict[str, Any]:
        """分析垃圾回收影响"""
        gen0_collections = end_stats[0]['collections'] - start_stats[0]['collections']
        gen1_collections = end_stats[1]['collections'] - start_stats[1]['collections'] 
        gen2_collections = end_stats[2]['collections'] - start_stats[2]['collections']
        
        total_collections = gen0_collections + gen1_collections + gen2_collections
        
        # 估计GC暂停时间
        avg_pause_time = total_collections * 0.001  # 估计每次GC 1ms
        
        return {
            'total_collections': total_collections,
            'gen0_collections': gen0_collections,
            'gen1_collections': gen1_collections,
            'gen2_collections': gen2_collections,
            'avg_pause_time': avg_pause_time
        }


class GarbageCollectionTestRunner:
    """垃圾回收测试运行器"""
    
    def __init__(self, services):
        self.services = services
    
    async def run_object_intensive_operations(self, iterations: int, objects_per_iteration: int):
        """运行对象密集操作"""
        for i in range(iterations):
            # 创建大量临时对象
            temp_objects = []
            for j in range(objects_per_iteration):
                temp_objects.append({
                    'id': f'{i}_{j}',
                    'data': [k for k in range(100)],
                    'timestamp': time.time()
                })
            
            await self.services['intent_service'].recognize_intent(f"test {i}")
            
            # 让对象超出作用域
            del temp_objects


class ThreadUsageMonitor:
    """线程使用监控器"""
    pass


class ThreadUsageTestRunner:
    """线程使用测试运行器"""
    
    def __init__(self, services):
        self.services = services
    
    async def run_concurrent_operations(self, max_threads: int, operations_per_thread: int, 
                                      monitoring_interval: float) -> Dict[str, List]:
        """运行并发操作"""
        thread_counts = []
        
        async def thread_task():
            for _ in range(operations_per_thread):
                await self.services['intent_service'].recognize_intent("thread test")
                await asyncio.sleep(0.01)
        
        # 监控线程数变化
        async def monitor_threads():
            while True:
                thread_counts.append(threading.active_count())
                await asyncio.sleep(monitoring_interval)
        
        monitor_task = asyncio.create_task(monitor_threads())
        
        # 执行并发任务
        tasks = [thread_task() for _ in range(max_threads)]
        await asyncio.gather(*tasks)
        
        monitor_task.cancel()
        try:
            await monitor_task
        except asyncio.CancelledError:
            pass
        
        return {'thread_counts': thread_counts}


class FileDescriptorMonitor:
    """文件描述符监控器"""
    
    def get_fd_count(self) -> int:
        """获取当前文件描述符数量"""
        try:
            return psutil.Process().num_fds()
        except:
            return 0


class FileDescriptorTestRunner:
    """文件描述符测试运行器"""
    
    def __init__(self, services):
        self.services = services
    
    async def run_io_intensive_operations(self, concurrent_operations: int, 
                                        operations_per_task: int) -> Dict[str, List]:
        """运行IO密集操作"""
        fd_counts = []
        
        async def io_task():
            for _ in range(operations_per_task):
                await self.services['cache_service'].get(f"key_{time.time()}")
                await self.services['conversation_service'].save_conversation()
        
        # 监控文件描述符
        async def monitor_fds():
            monitor = FileDescriptorMonitor()
            while True:
                fd_counts.append(monitor.get_fd_count())
                await asyncio.sleep(0.1)
        
        monitor_task = asyncio.create_task(monitor_fds())
        
        # 执行IO任务
        tasks = [io_task() for _ in range(concurrent_operations)]
        await asyncio.gather(*tasks)
        
        monitor_task.cancel()
        try:
            await monitor_task
        except asyncio.CancelledError:
            pass
        
        return {'fd_counts': fd_counts}


class MemoryStabilityMonitor:
    """内存稳定性监控器"""
    
    def analyze_stability(self, metrics: Dict[str, List]) -> Dict[str, Any]:
        """分析内存稳定性"""
        memory_usage = metrics['memory_usage']
        
        if len(memory_usage) < 2:
            return {'memory_trend': 'insufficient_data', 'memory_variance': 0, 'leak_detected': False}
        
        # 分析趋势
        first_half = memory_usage[:len(memory_usage)//2]
        second_half = memory_usage[len(memory_usage)//2:]
        
        first_avg = sum(first_half) / len(first_half)
        second_avg = sum(second_half) / len(second_half)
        
        if second_avg > first_avg * 1.1:
            trend = 'increasing'
        elif second_avg < first_avg * 0.9:
            trend = 'decreasing'
        else:
            trend = 'stable'
        
        # 计算方差
        avg_memory = sum(memory_usage) / len(memory_usage)
        variance = sum((x - avg_memory) ** 2 for x in memory_usage) / len(memory_usage)
        
        # 检测泄漏
        leak_detected = trend == 'increasing' and variance > 100
        
        return {
            'memory_trend': trend,
            'memory_variance': variance ** 0.5,  # 标准差
            'leak_detected': leak_detected
        }


class SustainedLoadRunner:
    """持续负载测试运行器"""
    
    def __init__(self, services):
        self.services = services
    
    async def run_sustained_load(self, duration_minutes: int, operations_per_second: int, 
                                monitoring_interval: float) -> Dict[str, List]:
        """运行持续负载"""
        memory_usage = []
        cpu_usage = []
        
        duration_seconds = duration_minutes * 60
        interval = 1.0 / operations_per_second
        
        # 监控资源
        async def monitor_resources():
            while True:
                memory_mb = psutil.Process().memory_info().rss / 1024 / 1024
                cpu_percent = psutil.cpu_percent()
                memory_usage.append(memory_mb)
                cpu_usage.append(cpu_percent)
                await asyncio.sleep(monitoring_interval)
        
        monitor_task = asyncio.create_task(monitor_resources())
        
        # 执行持续操作
        async def sustained_operations():
            end_time = time.time() + duration_seconds
            while time.time() < end_time:
                await self.services['intent_service'].recognize_intent("sustained test")
                await asyncio.sleep(interval)
        
        await sustained_operations()
        
        monitor_task.cancel()
        try:
            await monitor_task
        except asyncio.CancelledError:
            pass
        
        return {
            'memory_usage': memory_usage,
            'cpu_usage': cpu_usage
        }


class ResourceCleanupMonitor:
    """资源清理监控器"""
    
    def get_resource_state(self) -> Dict[str, float]:
        """获取当前资源状态"""
        return {
            'memory': psutil.Process().memory_info().rss / 1024 / 1024,
            'threads': threading.active_count(),
            'fds': self._get_fd_count()
        }
    
    def _get_fd_count(self) -> int:
        """获取文件描述符数量"""
        try:
            return psutil.Process().num_fds()
        except:
            return 0


class ResourceCleanupTestRunner:
    """资源清理测试运行器"""
    
    def __init__(self, services):
        self.services = services
        self.resources = []
    
    async def run_resource_intensive_operations(self, iterations: int, resources_per_iteration: int):
        """运行资源密集操作"""
        for i in range(iterations):
            # 创建资源
            iteration_resources = []
            for j in range(resources_per_iteration):
                resource = {
                    'id': f'{i}_{j}',
                    'data': bytearray(1024),  # 1KB数据
                    'timestamp': time.time()
                }
                iteration_resources.append(resource)
            
            self.resources.extend(iteration_resources)
            await self.services['intent_service'].recognize_intent(f"resource test {i}")
    
    async def cleanup_resources(self):
        """清理资源"""
        self.resources.clear()
        gc.collect()