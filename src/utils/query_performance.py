"""
查询性能优化工具 (TASK-031)
提供查询性能监控、分析和优化功能
"""
import time
import asyncio
from typing import Dict, List, Any, Optional, Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from collections import defaultdict, deque
import json
import hashlib
import statistics

from src.services.cache_service import CacheService
from src.utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class QueryMetrics:
    """查询指标"""
    query_hash: str
    query_text: str
    start_time: float
    end_time: float
    duration: float
    success: bool
    error_message: Optional[str] = None
    cache_hit: bool = False
    cache_key: Optional[str] = None
    query_type: Optional[str] = None
    query_intent: Optional[str] = None
    complexity: Optional[str] = None
    processing_stages: Dict[str, float] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class PerformanceStats:
    """性能统计"""
    total_queries: int
    successful_queries: int
    failed_queries: int
    cache_hits: int
    cache_misses: int
    average_duration: float
    p95_duration: float
    p99_duration: float
    min_duration: float
    max_duration: float
    error_rate: float
    cache_hit_rate: float
    queries_per_second: float
    stage_durations: Dict[str, float]
    error_distribution: Dict[str, int]
    query_type_distribution: Dict[str, int]


class QueryPerformanceMonitor:
    """查询性能监控器"""
    
    def __init__(self, cache_service: CacheService, window_size: int = 1000):
        self.cache_service = cache_service
        self.cache_namespace = "query_performance"
        self.window_size = window_size
        self.metrics_buffer = deque(maxlen=window_size)
        self.stage_timings = defaultdict(list)
        self.error_counts = defaultdict(int)
        self.query_type_counts = defaultdict(int)
        self.start_time = time.time()
        
    def start_query(self, query_text: str, metadata: Dict[str, Any] = None) -> str:
        """开始查询监控"""
        query_hash = hashlib.md5(query_text.encode()).hexdigest()
        
        metric = QueryMetrics(
            query_hash=query_hash,
            query_text=query_text,
            start_time=time.time(),
            end_time=0.0,
            duration=0.0,
            success=False,
            metadata=metadata or {}
        )
        
        # 存储当前查询
        self.metrics_buffer.append(metric)
        
        return query_hash
    
    def stage_timing(self, query_hash: str, stage_name: str, duration: float):
        """记录阶段耗时"""
        for metric in reversed(self.metrics_buffer):
            if metric.query_hash == query_hash:
                metric.processing_stages[stage_name] = duration
                self.stage_timings[stage_name].append(duration)
                break
    
    def end_query(self, query_hash: str, success: bool = True, 
                  error_message: str = None, cache_hit: bool = False,
                  cache_key: str = None, query_type: str = None,
                  query_intent: str = None, complexity: str = None):
        """结束查询监控"""
        end_time = time.time()
        
        for metric in reversed(self.metrics_buffer):
            if metric.query_hash == query_hash:
                metric.end_time = end_time
                metric.duration = end_time - metric.start_time
                metric.success = success
                metric.error_message = error_message
                metric.cache_hit = cache_hit
                metric.cache_key = cache_key
                metric.query_type = query_type
                metric.query_intent = query_intent
                metric.complexity = complexity
                
                # 更新统计
                if not success and error_message:
                    self.error_counts[error_message] += 1
                
                if query_type:
                    self.query_type_counts[query_type] += 1
                
                break
    
    def get_current_stats(self) -> PerformanceStats:
        """获取当前性能统计"""
        if not self.metrics_buffer:
            return PerformanceStats(
                total_queries=0,
                successful_queries=0,
                failed_queries=0,
                cache_hits=0,
                cache_misses=0,
                average_duration=0.0,
                p95_duration=0.0,
                p99_duration=0.0,
                min_duration=0.0,
                max_duration=0.0,
                error_rate=0.0,
                cache_hit_rate=0.0,
                queries_per_second=0.0,
                stage_durations={},
                error_distribution={},
                query_type_distribution={}
            )
        
        metrics = list(self.metrics_buffer)
        total_queries = len(metrics)
        successful_queries = sum(1 for m in metrics if m.success)
        failed_queries = total_queries - successful_queries
        cache_hits = sum(1 for m in metrics if m.cache_hit)
        cache_misses = total_queries - cache_hits
        
        durations = [m.duration for m in metrics]
        average_duration = statistics.mean(durations)
        
        # 计算百分位数
        sorted_durations = sorted(durations)
        p95_duration = sorted_durations[int(0.95 * len(sorted_durations))] if sorted_durations else 0.0
        p99_duration = sorted_durations[int(0.99 * len(sorted_durations))] if sorted_durations else 0.0
        min_duration = min(durations) if durations else 0.0
        max_duration = max(durations) if durations else 0.0
        
        # 计算QPS
        time_window = time.time() - self.start_time
        queries_per_second = total_queries / time_window if time_window > 0 else 0.0
        
        # 计算阶段平均耗时
        stage_durations = {}
        for stage, timings in self.stage_timings.items():
            if timings:
                stage_durations[stage] = statistics.mean(timings)
        
        return PerformanceStats(
            total_queries=total_queries,
            successful_queries=successful_queries,
            failed_queries=failed_queries,
            cache_hits=cache_hits,
            cache_misses=cache_misses,
            average_duration=average_duration,
            p95_duration=p95_duration,
            p99_duration=p99_duration,
            min_duration=min_duration,
            max_duration=max_duration,
            error_rate=failed_queries / total_queries if total_queries > 0 else 0.0,
            cache_hit_rate=cache_hits / total_queries if total_queries > 0 else 0.0,
            queries_per_second=queries_per_second,
            stage_durations=stage_durations,
            error_distribution=dict(self.error_counts),
            query_type_distribution=dict(self.query_type_counts)
        )
    
    async def save_metrics(self, metrics: List[QueryMetrics]):
        """保存指标到缓存"""
        try:
            # 按时间窗口保存指标
            timestamp = datetime.now().strftime("%Y%m%d_%H")
            cache_key = f"metrics_{timestamp}"
            
            # 获取现有指标
            existing_metrics = await self.cache_service.get(cache_key, namespace=self.cache_namespace) or []
            
            # 转换为字典格式
            metrics_data = []
            for metric in metrics:
                metrics_data.append({
                    'query_hash': metric.query_hash,
                    'query_text': metric.query_text,
                    'start_time': metric.start_time,
                    'end_time': metric.end_time,
                    'duration': metric.duration,
                    'success': metric.success,
                    'error_message': metric.error_message,
                    'cache_hit': metric.cache_hit,
                    'cache_key': metric.cache_key,
                    'query_type': metric.query_type,
                    'query_intent': metric.query_intent,
                    'complexity': metric.complexity,
                    'processing_stages': metric.processing_stages,
                    'metadata': metric.metadata
                })
            
            # 合并指标
            existing_metrics.extend(metrics_data)
            
            # 保存到缓存，TTL为24小时
            await self.cache_service.set(cache_key, existing_metrics, ttl=86400, namespace=self.cache_namespace)
            
        except Exception as e:
            logger.error(f"保存性能指标失败: {str(e)}")
    
    async def get_historical_stats(self, hours: int = 24) -> Dict[str, Any]:
        """获取历史性能统计"""
        try:
            stats = {
                'total_queries': 0,
                'successful_queries': 0,
                'failed_queries': 0,
                'cache_hits': 0,
                'average_duration': 0.0,
                'hourly_stats': [],
                'error_trends': {},
                'performance_trends': []
            }
            
            # 获取指定时间范围内的指标
            now = datetime.now()
            for i in range(hours):
                hour_time = now - timedelta(hours=i)
                timestamp = hour_time.strftime("%Y%m%d_%H")
                cache_key = f"metrics_{timestamp}"
                
                hour_metrics = await self.cache_service.get(cache_key, namespace=self.cache_namespace) or []
                
                if hour_metrics:
                    hour_stats = self._analyze_hour_metrics(hour_metrics)
                    hour_stats['timestamp'] = timestamp
                    stats['hourly_stats'].append(hour_stats)
                    
                    # 累计统计
                    stats['total_queries'] += hour_stats['total_queries']
                    stats['successful_queries'] += hour_stats['successful_queries']
                    stats['failed_queries'] += hour_stats['failed_queries']
                    stats['cache_hits'] += hour_stats['cache_hits']
            
            # 计算平均值
            if stats['total_queries'] > 0:
                stats['average_duration'] = sum(h['average_duration'] for h in stats['hourly_stats']) / len(stats['hourly_stats'])
            
            return stats
            
        except Exception as e:
            logger.error(f"获取历史统计失败: {str(e)}")
            return {}
    
    def _analyze_hour_metrics(self, metrics: List[Dict]) -> Dict[str, Any]:
        """分析单小时指标"""
        if not metrics:
            return {
                'total_queries': 0,
                'successful_queries': 0,
                'failed_queries': 0,
                'cache_hits': 0,
                'average_duration': 0.0,
                'error_rate': 0.0,
                'cache_hit_rate': 0.0
            }
        
        total_queries = len(metrics)
        successful_queries = sum(1 for m in metrics if m['success'])
        failed_queries = total_queries - successful_queries
        cache_hits = sum(1 for m in metrics if m['cache_hit'])
        
        durations = [m['duration'] for m in metrics]
        average_duration = statistics.mean(durations) if durations else 0.0
        
        return {
            'total_queries': total_queries,
            'successful_queries': successful_queries,
            'failed_queries': failed_queries,
            'cache_hits': cache_hits,
            'average_duration': average_duration,
            'error_rate': failed_queries / total_queries if total_queries > 0 else 0.0,
            'cache_hit_rate': cache_hits / total_queries if total_queries > 0 else 0.0
        }


class QueryOptimizer:
    """查询优化器"""
    
    def __init__(self, cache_service: CacheService):
        self.cache_service = cache_service
        self.cache_namespace = "query_optimization"
        self.optimization_rules = self._load_optimization_rules()
        self.performance_thresholds = self._load_performance_thresholds()
    
    def _load_optimization_rules(self) -> Dict[str, Any]:
        """加载优化规则"""
        return {
            'cache_duration_rules': {
                'factual': 3600,      # 事实性查询缓存1小时
                'procedural': 1800,   # 程序性查询缓存30分钟
                'comparative': 900,   # 比较性查询缓存15分钟
                'personal': 300       # 个人化查询缓存5分钟
            },
            'query_simplification': {
                'max_length': 200,
                'remove_redundant_words': True,
                'merge_similar_queries': True
            },
            'parallel_processing': {
                'max_concurrent_queries': 10,
                'timeout_seconds': 30
            },
            'smart_routing': {
                'simple_queries': 'fast_config',
                'complex_queries': 'powerful_config',
                'technical_queries': 'technical_config'
            }
        }
    
    def _load_performance_thresholds(self) -> Dict[str, float]:
        """加载性能阈值"""
        return {
            'response_time_warning': 3.0,      # 响应时间警告阈值
            'response_time_critical': 10.0,    # 响应时间严重阈值
            'error_rate_warning': 0.05,        # 错误率警告阈值
            'error_rate_critical': 0.15,       # 错误率严重阈值
            'cache_hit_rate_warning': 0.3,     # 缓存命中率警告阈值
            'cache_hit_rate_critical': 0.1     # 缓存命中率严重阈值
        }
    
    def optimize_query(self, query: str, query_type: str, metadata: Dict[str, Any] = None) -> Dict[str, Any]:
        """优化查询"""
        optimizations = {}
        
        # 1. 查询长度优化
        if len(query) > self.optimization_rules['query_simplification']['max_length']:
            optimizations['truncate_query'] = True
            optimizations['original_length'] = len(query)
            optimizations['truncated_length'] = self.optimization_rules['query_simplification']['max_length']
        
        # 2. 缓存策略优化
        cache_duration = self.optimization_rules['cache_duration_rules'].get(query_type, 1800)
        optimizations['cache_duration'] = cache_duration
        
        # 3. 路由优化
        routing_config = self._get_optimal_routing(query, query_type, metadata)
        optimizations['routing_config'] = routing_config
        
        # 4. 并行处理优化
        if self._should_use_parallel_processing(query, query_type):
            optimizations['parallel_processing'] = True
            optimizations['max_concurrent'] = self.optimization_rules['parallel_processing']['max_concurrent_queries']
        
        return optimizations
    
    def _get_optimal_routing(self, query: str, query_type: str, metadata: Dict[str, Any] = None) -> str:
        """获取最优路由配置"""
        # 根据查询复杂度选择配置
        if metadata and metadata.get('complexity') == 'simple':
            return self.optimization_rules['smart_routing']['simple_queries']
        elif metadata and metadata.get('complexity') in ['complex', 'very_complex']:
            return self.optimization_rules['smart_routing']['complex_queries']
        elif metadata and metadata.get('domain') == 'technical':
            return self.optimization_rules['smart_routing']['technical_queries']
        else:
            return 'default'
    
    def _should_use_parallel_processing(self, query: str, query_type: str) -> bool:
        """判断是否应该使用并行处理"""
        # 复杂查询使用并行处理
        parallel_query_types = ['comparative', 'causal', 'procedural']
        return query_type in parallel_query_types or len(query) > 100
    
    async def analyze_performance_issues(self, stats: PerformanceStats) -> List[Dict[str, Any]]:
        """分析性能问题"""
        issues = []
        
        # 1. 响应时间问题
        if stats.average_duration > self.performance_thresholds['response_time_critical']:
            issues.append({
                'type': 'response_time',
                'severity': 'critical',
                'message': f"平均响应时间过长: {stats.average_duration:.2f}s",
                'recommendation': "考虑增加缓存、优化查询或增加计算资源"
            })
        elif stats.average_duration > self.performance_thresholds['response_time_warning']:
            issues.append({
                'type': 'response_time',
                'severity': 'warning',
                'message': f"平均响应时间偏高: {stats.average_duration:.2f}s",
                'recommendation': "监控查询性能，考虑优化策略"
            })
        
        # 2. 错误率问题
        if stats.error_rate > self.performance_thresholds['error_rate_critical']:
            issues.append({
                'type': 'error_rate',
                'severity': 'critical',
                'message': f"错误率过高: {stats.error_rate:.2%}",
                'recommendation': "检查服务稳定性，修复主要错误"
            })
        elif stats.error_rate > self.performance_thresholds['error_rate_warning']:
            issues.append({
                'type': 'error_rate',
                'severity': 'warning',
                'message': f"错误率偏高: {stats.error_rate:.2%}",
                'recommendation': "分析错误类型，改进错误处理"
            })
        
        # 3. 缓存命中率问题
        if stats.cache_hit_rate < self.performance_thresholds['cache_hit_rate_critical']:
            issues.append({
                'type': 'cache_hit_rate',
                'severity': 'critical',
                'message': f"缓存命中率过低: {stats.cache_hit_rate:.2%}",
                'recommendation': "优化缓存策略，增加缓存时间或改进缓存键"
            })
        elif stats.cache_hit_rate < self.performance_thresholds['cache_hit_rate_warning']:
            issues.append({
                'type': 'cache_hit_rate',
                'severity': 'warning',
                'message': f"缓存命中率偏低: {stats.cache_hit_rate:.2%}",
                'recommendation': "监控缓存使用情况，考虑优化缓存策略"
            })
        
        # 4. 查询类型分析
        if stats.query_type_distribution:
            slow_types = []
            for query_type, count in stats.query_type_distribution.items():
                if query_type in stats.stage_durations:
                    avg_duration = stats.stage_durations[query_type]
                    if avg_duration > 5.0:  # 超过5秒的查询类型
                        slow_types.append((query_type, avg_duration))
            
            if slow_types:
                issues.append({
                    'type': 'slow_query_types',
                    'severity': 'warning',
                    'message': f"发现慢查询类型: {slow_types}",
                    'recommendation': "针对慢查询类型进行专门优化"
                })
        
        return issues
    
    async def generate_optimization_suggestions(self, stats: PerformanceStats) -> List[Dict[str, Any]]:
        """生成优化建议"""
        suggestions = []
        
        # 1. 基于缓存命中率的建议
        if stats.cache_hit_rate < 0.5:
            suggestions.append({
                'type': 'cache_optimization',
                'priority': 'high',
                'suggestion': "增加缓存时间，优化缓存键生成策略",
                'expected_improvement': "提高缓存命中率20-30%"
            })
        
        # 2. 基于查询类型分布的建议
        if stats.query_type_distribution:
            dominant_type = max(stats.query_type_distribution.items(), key=lambda x: x[1])
            suggestions.append({
                'type': 'query_specialization',
                'priority': 'medium',
                'suggestion': f"针对主要查询类型 {dominant_type[0]} 进行专门优化",
                'expected_improvement': "提高主要查询类型性能15-25%"
            })
        
        # 3. 基于错误分布的建议
        if stats.error_distribution:
            top_error = max(stats.error_distribution.items(), key=lambda x: x[1])
            suggestions.append({
                'type': 'error_handling',
                'priority': 'high',
                'suggestion': f"重点解决主要错误: {top_error[0]}",
                'expected_improvement': "降低错误率5-10%"
            })
        
        # 4. 基于响应时间的建议
        if stats.p95_duration > 8.0:
            suggestions.append({
                'type': 'performance_optimization',
                'priority': 'high',
                'suggestion': "优化长尾查询性能，考虑查询分解或并行处理",
                'expected_improvement': "降低P95响应时间30-40%"
            })
        
        return suggestions


class PerformanceReporter:
    """性能报告生成器"""
    
    def __init__(self, monitor: QueryPerformanceMonitor):
        self.monitor = monitor
    
    async def generate_report(self, report_type: str = "summary") -> Dict[str, Any]:
        """生成性能报告"""
        current_stats = self.monitor.get_current_stats()
        historical_stats = await self.monitor.get_historical_stats(hours=24)
        
        report = {
            'report_type': report_type,
            'generated_at': datetime.now().isoformat(),
            'current_stats': self._format_stats(current_stats),
            'historical_stats': historical_stats,
            'performance_trends': self._analyze_trends(historical_stats),
            'recommendations': []
        }
        
        # 添加优化建议
        optimizer = QueryOptimizer(self.monitor.cache_service)
        issues = await optimizer.analyze_performance_issues(current_stats)
        suggestions = await optimizer.generate_optimization_suggestions(current_stats)
        
        report['issues'] = issues
        report['recommendations'] = suggestions
        
        return report
    
    def _format_stats(self, stats: PerformanceStats) -> Dict[str, Any]:
        """格式化统计数据"""
        return {
            'total_queries': stats.total_queries,
            'success_rate': f"{(stats.successful_queries / stats.total_queries * 100):.1f}%" if stats.total_queries > 0 else "0%",
            'error_rate': f"{(stats.error_rate * 100):.1f}%",
            'cache_hit_rate': f"{(stats.cache_hit_rate * 100):.1f}%",
            'average_duration': f"{stats.average_duration:.2f}s",
            'p95_duration': f"{stats.p95_duration:.2f}s",
            'p99_duration': f"{stats.p99_duration:.2f}s",
            'queries_per_second': f"{stats.queries_per_second:.2f}",
            'query_type_distribution': stats.query_type_distribution,
            'error_distribution': stats.error_distribution
        }
    
    def _analyze_trends(self, historical_stats: Dict[str, Any]) -> Dict[str, Any]:
        """分析性能趋势"""
        trends = {
            'query_volume_trend': 'stable',
            'performance_trend': 'stable',
            'error_trend': 'stable',
            'cache_trend': 'stable'
        }
        
        hourly_stats = historical_stats.get('hourly_stats', [])
        if len(hourly_stats) >= 6:  # 至少6小时数据
            # 分析查询量趋势
            recent_queries = sum(h['total_queries'] for h in hourly_stats[:3])
            earlier_queries = sum(h['total_queries'] for h in hourly_stats[-3:])
            
            if recent_queries > earlier_queries * 1.2:
                trends['query_volume_trend'] = 'increasing'
            elif recent_queries < earlier_queries * 0.8:
                trends['query_volume_trend'] = 'decreasing'
            
            # 分析性能趋势
            recent_duration = sum(h['average_duration'] for h in hourly_stats[:3]) / 3
            earlier_duration = sum(h['average_duration'] for h in hourly_stats[-3:]) / 3
            
            if recent_duration > earlier_duration * 1.2:
                trends['performance_trend'] = 'degrading'
            elif recent_duration < earlier_duration * 0.8:
                trends['performance_trend'] = 'improving'
            
            # 分析错误趋势
            recent_errors = sum(h['error_rate'] for h in hourly_stats[:3]) / 3
            earlier_errors = sum(h['error_rate'] for h in hourly_stats[-3:]) / 3
            
            if recent_errors > earlier_errors * 1.5:
                trends['error_trend'] = 'increasing'
            elif recent_errors < earlier_errors * 0.5:
                trends['error_trend'] = 'decreasing'
        
        return trends


def performance_monitor(cache_service: CacheService):
    """性能监控装饰器"""
    monitor = QueryPerformanceMonitor(cache_service)
    
    def decorator(func: Callable):
        async def wrapper(*args, **kwargs):
            # 提取查询文本
            query_text = ""
            if args:
                query_text = str(args[0])
            
            # 开始监控
            query_hash = monitor.start_query(query_text)
            
            try:
                # 执行原函数
                result = await func(*args, **kwargs)
                
                # 结束监控
                monitor.end_query(query_hash, success=True)
                
                return result
                
            except Exception as e:
                # 记录错误
                monitor.end_query(query_hash, success=False, error_message=str(e))
                raise
        
        return wrapper
    return decorator