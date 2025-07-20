"""
功能调用服务
"""
from typing import Dict, List, Optional, Any, Callable, Union
import json
import asyncio
import inspect
import time
from datetime import datetime
import random
import traceback
from functools import wraps
from contextlib import asynccontextmanager

from src.models.function import Function, FunctionCall, FunctionParameter
from src.services.cache_service import CacheService
from src.core.dynamic_function_registry import (
    DynamicFunctionRegistry, get_function_registry, RegistrationRequest, 
    FunctionMetadata, FunctionType, RegistrationSource
)
from src.services.api_wrapper_manager import (
    ApiWrapperManager, get_api_wrapper_manager
)
from src.core.api_wrapper import (
    ApiWrapperConfig, HttpMethod, AuthType, AuthConfig, 
    RetryConfig, RateLimitConfig, CacheConfig
)
from src.utils.logger import get_logger
from src.core.parameter_validator import (
    get_parameter_validator, get_parameter_mapper, 
    ParameterSchema, ParameterType, ValidationRule, ValidationSeverity,
    ValidationType, ValidationResult,
    create_required_rule, create_length_rule, create_range_rule, 
    create_pattern_rule, create_enum_rule, create_custom_rule,
    ParameterMappingRule
)

logger = get_logger(__name__)


class FunctionRetryConfig:
    """函数重试配置"""
    
    def __init__(self, max_attempts: int = 3, base_delay: float = 1.0, 
                 max_delay: float = 60.0, backoff_factor: float = 2.0,
                 retry_exceptions: List[type] = None, 
                 retry_on_status: List[int] = None,
                 jitter: bool = True, circuit_breaker: bool = False):
        self.max_attempts = max_attempts
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.backoff_factor = backoff_factor
        self.retry_exceptions = retry_exceptions or [Exception]
        self.retry_on_status = retry_on_status or [500, 502, 503, 504, 429]
        self.jitter = jitter
        self.circuit_breaker = circuit_breaker


class CircuitBreaker:
    """熔断器实现"""
    
    def __init__(self, failure_threshold: int = 5, recovery_timeout: float = 60.0,
                 expected_exception: type = Exception):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.expected_exception = expected_exception
        
        self.failure_count = 0
        self.last_failure_time = None
        self.state = 'closed'  # closed, open, half_open
        
    def call(self, func: Callable):
        """调用函数并处理熔断逻辑"""
        if self.state == 'open':
            if self._should_attempt_reset():
                self.state = 'half_open'
            else:
                raise Exception("Circuit breaker is open")
        
        try:
            result = func()
            self._on_success()
            return result
        except self.expected_exception as e:
            self._on_failure()
            raise e
    
    def _should_attempt_reset(self) -> bool:
        """判断是否应该尝试重置熔断器"""
        return (self.last_failure_time is not None and 
                time.time() - self.last_failure_time >= self.recovery_timeout)
    
    def _on_success(self):
        """成功时的处理"""
        self.failure_count = 0
        self.state = 'closed'
    
    def _on_failure(self):
        """失败时的处理"""
        self.failure_count += 1
        self.last_failure_time = time.time()
        
        if self.failure_count >= self.failure_threshold:
            self.state = 'open'


class FunctionExecutionResult:
    """功能执行结果类"""
    
    def __init__(self, success: bool, result: Any = None, error: str = None, 
                 execution_time: float = 0.0, metadata: Dict = None,
                 retry_count: int = 0, error_type: str = None, traceback_info: str = None):
        self.success = success
        self.result = result
        self.error = error
        self.execution_time = execution_time
        self.metadata = metadata or {}
        self.retry_count = retry_count
        self.error_type = error_type
        self.traceback_info = traceback_info
    
    def to_dict(self) -> Dict:
        """转换为字典格式"""
        return {
            'success': self.success,
            'result': self.result,
            'error': self.error,
            'execution_time': self.execution_time,
            'metadata': self.metadata,
            'retry_count': self.retry_count,
            'error_type': self.error_type,
            'traceback_info': self.traceback_info
        }


class FunctionService:
    """功能调用服务类"""
    
    def __init__(self, cache_service: CacheService):
        self.cache_service = cache_service
        self.cache_namespace = "function"
        
        # 使用动态函数注册器
        self.registry = get_function_registry()
        
        # 使用API包装器管理器 (TASK-027新增)
        self.api_wrapper_manager = get_api_wrapper_manager(cache_service)
        
        # 使用参数验证器和映射器 (TASK-028新增)
        self.parameter_validator = get_parameter_validator()
        self.parameter_mapper = get_parameter_mapper()
        
        # 保持向后兼容
        self._registered_functions: Dict[str, Callable] = {}
        self._function_metadata: Dict[str, Dict] = {}
        
        # 初始化时从数据库加载函数 - 延迟到有事件循环时执行
        self._initialization_started = False
        
        # TASK-029: 重试和错误处理配置
        self.retry_configs: Dict[str, FunctionRetryConfig] = {}
        self.circuit_breakers: Dict[str, CircuitBreaker] = {}
        self.global_retry_config = FunctionRetryConfig()
        
        # 错误统计
        self.error_stats: Dict[str, Dict] = {}
    
    async def register_function(self, function_name: str, func: Callable, 
                              metadata: Dict = None):
        """注册功能函数
        
        Args:
            function_name: 功能名称
            func: 功能函数
            metadata: 功能元数据
        """
        try:
            # 验证函数签名
            signature = inspect.signature(func)
            parameters = []
            
            for param_name, param in signature.parameters.items():
                if param_name == 'self':
                    continue
                    
                param_info = {
                    'name': param_name,
                    'type': param.annotation.__name__ if param.annotation != inspect.Parameter.empty else 'Any',
                    'required': param.default == inspect.Parameter.empty,
                    'default': param.default if param.default != inspect.Parameter.empty else None
                }
                parameters.append(param_info)
            
            # 存储函数引用和元数据
            self._registered_functions[function_name] = func
            self._function_metadata[function_name] = {
                'parameters': parameters,
                'is_async': asyncio.iscoroutinefunction(func),
                'description': func.__doc__ or '',
                'metadata': metadata or {}
            }
            
            # 清除相关缓存
            await self.cache_service.delete(f"function_def:{function_name}", 
                                          namespace=self.cache_namespace)
            
            logger.info(f"功能函数注册成功: {function_name}")
            
        except Exception as e:
            logger.error(f"功能函数注册失败: {function_name}, {str(e)}")
            raise
    
    async def execute_function(self, function_name: str, parameters: Dict[str, Any],
                             context: Optional[Dict[str, Any]] = None,
                             user_id: Optional[str] = None,
                             retry_config: Optional[FunctionRetryConfig] = None) -> FunctionExecutionResult:
        """执行功能函数 (TASK-029: 增强的重试和错误处理)
        
        Args:
            function_name: 功能名称
            parameters: 执行参数
            context: 执行上下文
            user_id: 用户ID
            retry_config: 重试配置（可选）
            
        Returns:
            FunctionExecutionResult: 执行结果
        """
        await self._ensure_initialization()
        
        # 获取重试配置
        retry_cfg = retry_config or self.retry_configs.get(function_name, self.global_retry_config)
        
        # 使用熔断器（如果启用）
        if retry_cfg.circuit_breaker:
            circuit_breaker = self.circuit_breakers.get(function_name)
            if not circuit_breaker:
                circuit_breaker = CircuitBreaker()
                self.circuit_breakers[function_name] = circuit_breaker
            
            if circuit_breaker.state == 'open':
                return FunctionExecutionResult(
                    False, 
                    error=f"熔断器开启，函数 {function_name} 暂时不可用",
                    error_type="CircuitBreakerOpen"
                )
        
        return await self._execute_function_with_retry(
            function_name, parameters, context, user_id, retry_cfg
        )
    
    async def _execute_function_with_retry(self, function_name: str, parameters: Dict[str, Any],
                                         context: Optional[Dict[str, Any]], user_id: Optional[str],
                                         retry_config: FunctionRetryConfig) -> FunctionExecutionResult:
        """带重试的函数执行 (TASK-029)"""
        last_exception = None
        last_result = None
        total_start_time = datetime.now()
        
        for attempt in range(retry_config.max_attempts):
            try:
                # 执行单次函数调用
                result = await self._execute_single_function_call(
                    function_name, parameters, context, user_id, attempt
                )
                
                # 如果成功，更新熔断器状态
                if result.success and retry_config.circuit_breaker:
                    circuit_breaker = self.circuit_breakers.get(function_name)
                    if circuit_breaker:
                        circuit_breaker._on_success()
                
                # 记录成功统计
                await self._record_success_stats(function_name, result.execution_time)
                
                # 返回成功结果
                result.retry_count = attempt
                return result
                
            except Exception as e:
                last_exception = e
                last_result = None
                
                # 判断是否应该重试
                should_retry = self._should_retry_exception(e, retry_config)
                
                if should_retry and attempt < retry_config.max_attempts - 1:
                    # 计算重试延迟
                    delay = self._calculate_retry_delay(retry_config, attempt)
                    
                    # 记录重试日志
                    logger.warning(
                        f"函数 {function_name} 执行失败 (第{attempt + 1}次尝试): {str(e)}, "
                        f"{delay:.2f}秒后重试"
                    )
                    
                    # 等待重试
                    await asyncio.sleep(delay)
                    continue
                else:
                    # 不需要重试或重试次数已用完
                    break
        
        # 所有重试都失败了
        total_execution_time = (datetime.now() - total_start_time).total_seconds()
        error_message = str(last_exception) if last_exception else "未知错误"
        error_type = type(last_exception).__name__ if last_exception else "UnknownError"
        
        # 更新熔断器状态
        if retry_config.circuit_breaker:
            circuit_breaker = self.circuit_breakers.get(function_name)
            if circuit_breaker:
                circuit_breaker._on_failure()
        
        # 记录失败统计
        await self._record_error_stats(function_name, error_type, error_message)
        
        # 记录错误日志
        logger.error(f"函数 {function_name} 执行失败，已用尽所有重试次数: {error_message}")
        
        return FunctionExecutionResult(
            False, 
            error=error_message,
            error_type=error_type,
            execution_time=total_execution_time,
            retry_count=retry_config.max_attempts - 1,
            traceback_info=traceback.format_exc() if last_exception else None
        )
    
    async def _execute_single_function_call(self, function_name: str, parameters: Dict[str, Any],
                                          context: Optional[Dict[str, Any]], user_id: Optional[str],
                                          attempt: int) -> FunctionExecutionResult:
        """执行单次函数调用 (TASK-029)"""
        start_time = datetime.now()
        
        try:
            # 优先从动态注册器获取函数
            func = self.registry.get_function(function_name)
            
            if not func:
                # 尝试从数据库加载功能定义
                await self._load_function_from_registry(function_name)
                func = self.registry.get_function(function_name)
                
                if not func:
                    # 回退到传统方式
                    await self._load_function_from_db(function_name)
                    func = self._registered_functions.get(function_name)
                    
                    if not func:
                        raise ValueError(f"功能未注册: {function_name}")
            
            # 获取功能元数据
            registry_metadata = self.registry.get_metadata(function_name)
            if registry_metadata and registry_metadata.signature:
                # 使用注册器的元数据
                func_metadata = {
                    'parameters': registry_metadata.signature.parameters,
                    'is_async': registry_metadata.signature.is_async
                }
            else:
                # 回退到传统元数据
                func_metadata = self._function_metadata.get(function_name, {
                    'parameters': [],
                    'is_async': asyncio.iscoroutinefunction(func)
                })
            
            # 验证和准备参数 (使用新的参数验证系统)
            try:
                validated_params = await self.validate_and_convert_parameters(
                    function_name, parameters, context
                )
            except ValueError:
                # 如果新系统无法找到参数模式，回退到旧方法
                validated_params = await self._validate_and_prepare_parameters(
                    function_name, parameters, func_metadata
                )
            
            # 记录功能调用
            call_record = await self._record_function_call(
                function_name, validated_params, user_id, context
            )
            
            # 执行功能函数
            if func_metadata['is_async']:
                result = await func(**validated_params)
            else:
                result = func(**validated_params)
            
            # 计算执行时间
            execution_time = (datetime.now() - start_time).total_seconds()
            
            # 更新调用记录
            await self._update_function_call_result(
                call_record, True, result, execution_time
            )
            
            logger.info(f"功能执行成功: {function_name}, 耗时: {execution_time:.3f}s (尝试 {attempt + 1})")
            
            return FunctionExecutionResult(
                True, 
                result=result, 
                execution_time=execution_time,
                metadata={'call_id': call_record.id if call_record else None}
            )
            
        except Exception as e:
            execution_time = (datetime.now() - start_time).total_seconds()
            error_message = str(e)
            error_type = type(e).__name__
            
            # 更新调用记录
            if 'call_record' in locals():
                await self._update_function_call_result(
                    locals()['call_record'], False, None, execution_time, error_message
                )
            
            logger.error(f"功能执行失败: {function_name}, {error_message} (尝试 {attempt + 1})")
            
            # 对于单次调用，我们抛出异常让上层处理重试
            raise e
    
    def _should_retry_exception(self, exception: Exception, retry_config: FunctionRetryConfig) -> bool:
        """判断异常是否应该重试 (TASK-029)"""
        exception_type = type(exception)
        
        # 检查是否在重试异常列表中
        for retry_exception in retry_config.retry_exceptions:
            if issubclass(exception_type, retry_exception):
                return True
        
        # 检查是否是网络相关异常
        network_exceptions = [
            'ConnectionError', 'TimeoutError', 'ConnectTimeoutError',
            'ReadTimeoutError', 'aiohttp.ClientTimeout', 'aiohttp.ClientConnectionError'
        ]
        
        if exception_type.__name__ in network_exceptions:
            return True
        
        # 检查错误消息中的特定模式
        error_message = str(exception).lower()
        retry_patterns = [
            'timeout', 'connection', 'network', 'unavailable',
            'service unavailable', 'too many requests', 'rate limit'
        ]
        
        for pattern in retry_patterns:
            if pattern in error_message:
                return True
        
        return False
    
    def _calculate_retry_delay(self, retry_config: FunctionRetryConfig, attempt: int) -> float:
        """计算重试延迟 (TASK-029)"""
        # 基础延迟计算（指数退避）
        delay = retry_config.base_delay * (retry_config.backoff_factor ** attempt)
        
        # 限制最大延迟
        delay = min(delay, retry_config.max_delay)
        
        # 添加随机抖动（避免惊群效应）
        if retry_config.jitter:
            jitter = random.uniform(0, delay * 0.1)  # 最多10%的抖动
            delay += jitter
        
        return delay
    
    async def _record_success_stats(self, function_name: str, execution_time: float):
        """记录成功统计 (TASK-029)"""
        try:
            if function_name not in self.error_stats:
                self.error_stats[function_name] = {
                    'total_calls': 0,
                    'success_calls': 0,
                    'error_calls': 0,
                    'avg_execution_time': 0.0,
                    'error_types': {},
                    'last_success_time': None,
                    'last_error_time': None
                }
            
            stats = self.error_stats[function_name]
            stats['total_calls'] += 1
            stats['success_calls'] += 1
            stats['last_success_time'] = datetime.now()
            
            # 更新平均执行时间
            total_calls = stats['total_calls']
            current_avg = stats['avg_execution_time']
            stats['avg_execution_time'] = ((current_avg * (total_calls - 1)) + execution_time) / total_calls
            
        except Exception as e:
            logger.warning(f"记录成功统计失败: {str(e)}")
    
    async def _record_error_stats(self, function_name: str, error_type: str, error_message: str):
        """记录错误统计 (TASK-029)"""
        try:
            if function_name not in self.error_stats:
                self.error_stats[function_name] = {
                    'total_calls': 0,
                    'success_calls': 0,
                    'error_calls': 0,
                    'avg_execution_time': 0.0,
                    'error_types': {},
                    'last_success_time': None,
                    'last_error_time': None
                }
            
            stats = self.error_stats[function_name]
            stats['total_calls'] += 1
            stats['error_calls'] += 1
            stats['last_error_time'] = datetime.now()
            
            # 记录错误类型
            if error_type not in stats['error_types']:
                stats['error_types'][error_type] = {
                    'count': 0,
                    'last_message': None,
                    'last_time': None
                }
            
            error_type_stats = stats['error_types'][error_type]
            error_type_stats['count'] += 1
            error_type_stats['last_message'] = error_message
            error_type_stats['last_time'] = datetime.now()
            
        except Exception as e:
            logger.warning(f"记录错误统计失败: {str(e)}")
    
    # ========== TASK-029: 重试和错误处理配置管理方法 ==========
    
    def set_function_retry_config(self, function_name: str, config: FunctionRetryConfig):
        """设置函数重试配置 (TASK-029)"""
        self.retry_configs[function_name] = config
        logger.info(f"设置函数 {function_name} 的重试配置: 最大重试{config.max_attempts}次")
    
    def set_global_retry_config(self, config: FunctionRetryConfig):
        """设置全局重试配置 (TASK-029)"""
        self.global_retry_config = config
        logger.info(f"设置全局重试配置: 最大重试{config.max_attempts}次")
    
    def get_function_retry_config(self, function_name: str) -> FunctionRetryConfig:
        """获取函数重试配置 (TASK-029)"""
        return self.retry_configs.get(function_name, self.global_retry_config)
    
    def enable_circuit_breaker(self, function_name: str, failure_threshold: int = 5,
                              recovery_timeout: float = 60.0):
        """启用熔断器 (TASK-029)"""
        circuit_breaker = CircuitBreaker(failure_threshold, recovery_timeout)
        self.circuit_breakers[function_name] = circuit_breaker
        
        # 更新重试配置以启用熔断器
        if function_name in self.retry_configs:
            self.retry_configs[function_name].circuit_breaker = True
        else:
            config = FunctionRetryConfig()
            config.circuit_breaker = True
            self.retry_configs[function_name] = config
        
        logger.info(f"为函数 {function_name} 启用熔断器")
    
    def disable_circuit_breaker(self, function_name: str):
        """禁用熔断器 (TASK-029)"""
        if function_name in self.circuit_breakers:
            del self.circuit_breakers[function_name]
        
        if function_name in self.retry_configs:
            self.retry_configs[function_name].circuit_breaker = False
        
        logger.info(f"为函数 {function_name} 禁用熔断器")
    
    def get_circuit_breaker_status(self, function_name: str) -> Optional[Dict[str, Any]]:
        """获取熔断器状态 (TASK-029)"""
        circuit_breaker = self.circuit_breakers.get(function_name)
        if not circuit_breaker:
            return None
        
        return {
            'state': circuit_breaker.state,
            'failure_count': circuit_breaker.failure_count,
            'failure_threshold': circuit_breaker.failure_threshold,
            'last_failure_time': circuit_breaker.last_failure_time,
            'recovery_timeout': circuit_breaker.recovery_timeout
        }
    
    def reset_circuit_breaker(self, function_name: str):
        """重置熔断器 (TASK-029)"""
        circuit_breaker = self.circuit_breakers.get(function_name)
        if circuit_breaker:
            circuit_breaker.failure_count = 0
            circuit_breaker.last_failure_time = None
            circuit_breaker.state = 'closed'
            logger.info(f"重置函数 {function_name} 的熔断器")
    
    def get_function_error_stats(self, function_name: str) -> Optional[Dict[str, Any]]:
        """获取函数错误统计 (TASK-029)"""
        return self.error_stats.get(function_name)
    
    def get_all_error_stats(self) -> Dict[str, Dict[str, Any]]:
        """获取所有错误统计 (TASK-029)"""
        return self.error_stats.copy()
    
    def clear_error_stats(self, function_name: str = None):
        """清除错误统计 (TASK-029)"""
        if function_name:
            if function_name in self.error_stats:
                del self.error_stats[function_name]
                logger.info(f"清除函数 {function_name} 的错误统计")
        else:
            self.error_stats.clear()
            logger.info("清除所有错误统计")
    
    async def health_check_function(self, function_name: str) -> Dict[str, Any]:
        """函数健康检查 (TASK-029)"""
        try:
            # 检查函数是否注册
            func = self.registry.get_function(function_name)
            if not func:
                func = self._registered_functions.get(function_name)
            
            if not func:
                return {
                    'status': 'unhealthy',
                    'reason': 'Function not registered',
                    'available': False
                }
            
            # 检查熔断器状态
            circuit_breaker = self.circuit_breakers.get(function_name)
            if circuit_breaker and circuit_breaker.state == 'open':
                return {
                    'status': 'unhealthy',
                    'reason': 'Circuit breaker is open',
                    'available': False,
                    'circuit_breaker_status': self.get_circuit_breaker_status(function_name)
                }
            
            # 获取错误统计
            error_stats = self.get_function_error_stats(function_name)
            
            # 计算健康分数
            health_score = 100.0
            if error_stats:
                total_calls = error_stats['total_calls']
                error_calls = error_stats['error_calls']
                
                if total_calls > 0:
                    error_rate = error_calls / total_calls
                    health_score = max(0, 100 - (error_rate * 100))
            
            status = 'healthy' if health_score > 70 else 'degraded' if health_score > 30 else 'unhealthy'
            
            return {
                'status': status,
                'health_score': health_score,
                'available': True,
                'stats': error_stats,
                'circuit_breaker_status': self.get_circuit_breaker_status(function_name)
            }
            
        except Exception as e:
            logger.error(f"健康检查失败: {function_name}, {str(e)}")
            return {
                'status': 'unhealthy',
                'reason': f'Health check failed: {str(e)}',
                'available': False
            }
    
    async def _load_function_from_db(self, function_name: str):
        """从数据库加载功能定义"""
        try:
            # 尝试从缓存获取
            cache_key = f"function_def:{function_name}"
            cached_def = await self.cache_service.get(cache_key, namespace=self.cache_namespace)
            
            if cached_def:
                logger.debug(f"从缓存加载功能定义: {function_name}")
                return
            
            # 从数据库查询功能定义
            function_def = Function.get(
                Function.function_name == function_name,
                Function.is_active == True
            )
            
            # 解析功能定义并注册
            await self._register_function_from_definition(function_def)
            
            # 缓存功能定义
            function_data = {
                'id': function_def.id,
                'function_name': function_def.function_name,
                'implementation': function_def.implementation,
                'description': function_def.description
            }
            await self.cache_service.set(cache_key, function_data, 
                                       ttl=3600, namespace=self.cache_namespace)
            
        except Function.DoesNotExist:
            logger.warning(f"功能定义不存在: {function_name}")
        except Exception as e:
            logger.error(f"加载功能定义失败: {function_name}, {str(e)}")
    
    async def _register_function_from_definition(self, function_def: Function):
        """根据数据库定义注册功能"""
        try:
            # 解析实现代码
            implementation = function_def.get_implementation()
            
            if implementation.get('type') == 'python_code':
                # 执行Python代码定义的功能
                code = implementation.get('code', '')
                namespace = {}
                exec(code, namespace)
                
                # 查找功能函数
                func_name = implementation.get('entry_point', function_def.function_name)
                if func_name in namespace:
                    func = namespace[func_name]
                    await self.register_function(
                        function_def.function_name, 
                        func, 
                        {'source': 'database', 'function_id': function_def.id}
                    )
            
            elif implementation.get('type') == 'api_call':
                # 创建API调用包装器
                api_config = implementation.get('config', {})
                func = self._create_api_wrapper(api_config)
                await self.register_function(
                    function_def.function_name, 
                    func, 
                    {'source': 'api', 'function_id': function_def.id}
                )
            
            else:
                logger.warning(f"不支持的功能实现类型: {implementation.get('type')}")
                
        except Exception as e:
            logger.error(f"注册功能定义失败: {function_def.function_name}, {str(e)}")
    
    def _create_api_wrapper(self, api_config: Dict) -> Callable:
        """创建API调用包装器"""
        async def api_wrapper(**kwargs):
            """API调用包装器函数"""
            import aiohttp
            
            try:
                url = api_config.get('url')
                method = api_config.get('method', 'POST').upper()
                headers = api_config.get('headers', {})
                timeout = api_config.get('timeout', 30)
                
                # 准备请求数据
                if method == 'GET':
                    params = kwargs
                    data = None
                else:
                    params = None
                    data = json.dumps(kwargs) if kwargs else None
                    headers['Content-Type'] = 'application/json'
                
                # 发送API请求
                async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=timeout)) as session:
                    async with session.request(
                        method, url, params=params, data=data, headers=headers
                    ) as response:
                        if response.status == 200:
                            result = await response.json()
                            return result
                        else:
                            error_text = await response.text()
                            raise Exception(f"API调用失败: {response.status}, {error_text}")
                            
            except Exception as e:
                logger.error(f"API包装器执行失败: {str(e)}")
                raise
        
        # 设置函数元数据
        api_wrapper.__doc__ = api_config.get('description', 'API调用功能')
        
        return api_wrapper
    
    async def _validate_and_prepare_parameters(self, function_name: str, 
                                             parameters: Dict[str, Any],
                                             func_metadata: Dict) -> Dict[str, Any]:
        """验证和准备功能参数"""
        param_definitions = func_metadata['parameters']
        validated_params = {}
        
        # 创建参数定义映射
        param_def_map = {p['name']: p for p in param_definitions}
        
        # 验证必需参数
        for param_def in param_definitions:
            param_name = param_def['name']
            param_type = param_def['type']
            is_required = param_def['required']
            default_value = param_def['default']
            
            if param_name in parameters:
                # 验证和转换参数类型
                value = parameters[param_name]
                validated_value = await self._convert_parameter_type(
                    value, param_type, param_name
                )
                validated_params[param_name] = validated_value
                
            elif is_required:
                raise ValueError(f"缺少必需参数: {param_name}")
            elif default_value is not None:
                validated_params[param_name] = default_value
        
        # 检查是否有未定义的参数
        extra_params = set(parameters.keys()) - set(param_def_map.keys())
        if extra_params:
            logger.warning(f"功能 {function_name} 收到未定义的参数: {extra_params}")
        
        return validated_params
    
    async def _convert_parameter_type(self, value: Any, param_type: str, 
                                    param_name: str) -> Any:
        """转换参数类型"""
        try:
            if param_type == 'str':
                return str(value)
            elif param_type == 'int':
                return int(value)
            elif param_type == 'float':
                return float(value)
            elif param_type == 'bool':
                if isinstance(value, bool):
                    return value
                elif isinstance(value, str):
                    return value.lower() in ('true', '1', 'yes', 'on')
                else:
                    return bool(value)
            elif param_type == 'list':
                if isinstance(value, list):
                    return value
                elif isinstance(value, str):
                    try:
                        return json.loads(value)
                    except:
                        return [value]
                else:
                    return [value]
            elif param_type == 'dict':
                if isinstance(value, dict):
                    return value
                elif isinstance(value, str):
                    return json.loads(value)
                else:
                    raise ValueError(f"无法将 {type(value)} 转换为 dict")
            else:
                # 其他类型或Any类型直接返回
                return value
                
        except Exception as e:
            raise ValueError(f"参数 {param_name} 类型转换失败: {str(e)}")
    
    async def _record_function_call(self, function_name: str, parameters: Dict[str, Any],
                                  user_id: Optional[str], context: Optional[Dict]) -> Optional[FunctionCall]:
        """记录功能调用"""
        try:
            # 获取功能定义
            function_def = Function.get(Function.function_name == function_name)
            
            # 创建调用记录
            call_record = FunctionCall.create(
                function=function_def,
                user_id=user_id,
                input_parameters=json.dumps(parameters, ensure_ascii=False),
                context_data=json.dumps(context or {}, ensure_ascii=False),
                status='executing'
            )
            
            return call_record
            
        except Function.DoesNotExist:
            logger.warning(f"功能定义不存在，无法记录调用: {function_name}")
            return None
        except Exception as e:
            logger.error(f"记录功能调用失败: {str(e)}")
            return None
    
    async def _update_function_call_result(self, call_record: Optional[FunctionCall],
                                         success: bool, result: Any, 
                                         execution_time: float, error: str = None):
        """更新功能调用结果"""
        if not call_record:
            return
        
        try:
            call_record.status = 'completed' if success else 'failed'
            call_record.execution_time = execution_time
            call_record.completed_at = datetime.now()
            
            if success:
                call_record.output_result = json.dumps(result, ensure_ascii=False) if result else None
            else:
                call_record.error_message = error
            
            call_record.save()
            
        except Exception as e:
            logger.error(f"更新功能调用结果失败: {str(e)}")
    
    async def get_available_functions(self, category: Optional[str] = None) -> List[Dict[str, Any]]:
        """获取可用功能列表
        
        Args:
            category: 功能分类过滤
            
        Returns:
            List[Dict]: 功能列表
        """
        try:
            # 构建查询条件
            conditions = [Function.is_active == True]
            if category:
                conditions.append(Function.category == category)
            
            # 查询功能定义
            functions = list(Function.select().where(*conditions))
            
            function_list = []
            for func in functions:
                # 获取参数定义
                parameters = []
                for param in func.parameters:
                    param_info = {
                        'name': param.parameter_name,
                        'type': param.parameter_type,
                        'description': param.description,
                        'required': param.is_required,
                        'default_value': param.default_value
                    }
                    parameters.append(param_info)
                
                function_info = {
                    'function_name': func.function_name,
                    'description': func.description,
                    'category': func.category,
                    'parameters': parameters,
                    'is_registered': func.function_name in self._registered_functions
                }
                function_list.append(function_info)
            
            return function_list
            
        except Exception as e:
            logger.error(f"获取可用功能列表失败: {str(e)}")
            return []
    
    async def get_function_call_history(self, user_id: Optional[str] = None,
                                      function_name: Optional[str] = None,
                                      limit: int = 50) -> List[Dict[str, Any]]:
        """获取功能调用历史
        
        Args:
            user_id: 用户ID过滤
            function_name: 功能名称过滤
            limit: 返回记录数限制
            
        Returns:
            List[Dict]: 调用历史
        """
        try:
            # 构建查询条件
            conditions = []
            if user_id:
                conditions.append(FunctionCall.user_id == user_id)
            if function_name:
                conditions.append(FunctionCall.function.function_name == function_name)
            
            # 查询调用记录
            calls = (FunctionCall
                    .select()
                    .join(Function)
                    .where(*conditions)
                    .order_by(FunctionCall.created_at.desc())
                    .limit(limit))
            
            history = []
            for call in calls:
                call_info = {
                    'id': call.id,
                    'function_name': call.function.function_name,
                    'user_id': call.user_id,
                    'input_parameters': call.get_input_parameters(),
                    'output_result': call.get_output_result(),
                    'status': call.status,
                    'execution_time': call.execution_time,
                    'error_message': call.error_message,
                    'created_at': call.created_at.isoformat(),
                    'completed_at': call.completed_at.isoformat() if call.completed_at else None
                }
                history.append(call_info)
            
            return history
            
        except Exception as e:
            logger.error(f"获取功能调用历史失败: {str(e)}")
            return []
    
    async def clear_function_cache(self, function_name: Optional[str] = None):
        """清理功能缓存
        
        Args:
            function_name: 功能名称，为None时清理所有缓存
        """
        if function_name:
            cache_key = f"function_def:{function_name}"
            await self.cache_service.delete(cache_key, namespace=self.cache_namespace)
            
            # 如果功能已注册，移除注册
            if function_name in self._registered_functions:
                del self._registered_functions[function_name]
                del self._function_metadata[function_name]
        else:
            await self.cache_service.clear_namespace(self.cache_namespace)
            self._registered_functions.clear()
            self._function_metadata.clear()
        
        logger.info(f"清理功能缓存: {function_name or 'all'}")
    
    def get_registered_functions(self) -> Dict[str, Dict]:
        """获取已注册的功能函数信息"""
        return self._function_metadata.copy()
    
    async def validate_function_call(self, function_name: str, parameters: Dict[str, Any]) -> bool:
        """验证功能调用参数
        
        Args:
            function_name: 功能名称
            parameters: 调用参数
            
        Returns:
            bool: 验证是否通过
        """
        try:
            if function_name not in self._function_metadata:
                await self._load_function_from_db(function_name)
                
                if function_name not in self._function_metadata:
                    return False
            
            func_metadata = self._function_metadata[function_name]
            await self._validate_and_prepare_parameters(
                function_name, parameters, func_metadata
            )
            
            return True
            
        except Exception as e:
            logger.warning(f"功能调用验证失败: {function_name}, {str(e)}")
            return False
    
    # ========== 新增：动态函数注册系统方法 ==========
    
    async def _ensure_initialization(self):
        """确保已初始化"""
        if not self._initialization_started:
            self._initialization_started = True
            await self._initialize_from_database()
    
    async def _initialize_from_database(self):
        """从数据库初始化函数注册"""
        try:
            # 加载所有活跃的函数定义 - 由于测试环境可能没有数据库，这里要处理异常
            try:
                active_functions = Function.select().where(Function.is_active == True)
                
                for function_def in active_functions:
                    try:
                        await self._load_function_from_registry(function_def.function_name)
                    except Exception as e:
                        logger.warning(f"初始化函数失败: {function_def.function_name}, {str(e)}")
                
                logger.info(f"从数据库初始化了 {len(active_functions)} 个函数")
            except Exception as db_error:
                logger.warning(f"数据库不可用，跳过函数初始化: {str(db_error)}")
            
        except Exception as e:
            logger.error(f"从数据库初始化函数失败: {str(e)}")
    
    async def _load_function_from_registry(self, function_name: str) -> bool:
        """从注册器加载函数"""
        try:
            # 检查注册器中是否已有该函数
            if self.registry.get_function(function_name):
                return True
            
            # 从数据库加载
            function_def = Function.get(
                Function.function_name == function_name,
                Function.is_active == True
            )
            
            implementation = function_def.get_implementation()
            
            if implementation.get('type') == 'python_code':
                # Python代码实现
                config = implementation.get('config', {})
                success = await self.registry.register_from_code(
                    function_name,
                    config.get('code', ''),
                    config.get('entry_point'),
                    {
                        'display_name': function_def.display_name,
                        'description': function_def.description,
                        'category': function_def.category,
                        'version': function_def.version,
                        'source': RegistrationSource.DATABASE
                    }
                )
            
            elif implementation.get('type') == 'api_call':
                # API调用实现
                api_config = implementation.get('config', {})
                success = await self.registry.register_api_wrapper(
                    function_name,
                    api_config,
                    {
                        'display_name': function_def.display_name,
                        'description': function_def.description,
                        'category': function_def.category,
                        'version': function_def.version,
                        'source': RegistrationSource.DATABASE
                    }
                )
            
            else:
                logger.warning(f"不支持的函数实现类型: {implementation.get('type')}")
                return False
            
            if success:
                logger.debug(f"从注册器加载函数成功: {function_name}")
            
            return success
            
        except Function.DoesNotExist:
            logger.warning(f"函数定义不存在: {function_name}")
            return False
        except Exception as e:
            logger.error(f"从注册器加载函数失败: {function_name}, {str(e)}")
            return False
    
    async def register_python_function(self, name: str, func: Callable, 
                                     category: Optional[str] = None,
                                     description: Optional[str] = None,
                                     tags: Optional[List[str]] = None) -> bool:
        """注册Python函数 (TASK-026新增)"""
        try:
            metadata = {
                'display_name': name,
                'description': description or func.__doc__,
                'category': category,
                'tags': tags or [],
                'source': RegistrationSource.MANUAL
            }
            
            success = await self.registry.register_from_callable(name, func, metadata)
            
            if success:
                # 保持向后兼容
                await self.register_function(name, func, metadata)
                logger.info(f"Python函数注册成功: {name}")
            
            return success
            
        except Exception as e:
            logger.error(f"注册Python函数失败: {name}, {str(e)}")
            return False
    
    async def register_code_function(self, name: str, code: str, 
                                   entry_point: Optional[str] = None,
                                   category: Optional[str] = None,
                                   description: Optional[str] = None) -> bool:
        """注册代码函数 (TASK-026新增)"""
        try:
            metadata = {
                'display_name': name,
                'description': description,
                'category': category,
                'source': RegistrationSource.MANUAL
            }
            
            success = await self.registry.register_from_code(
                name, code, entry_point, metadata
            )
            
            if success:
                logger.info(f"代码函数注册成功: {name}")
            
            return success
            
        except Exception as e:
            logger.error(f"注册代码函数失败: {name}, {str(e)}")
            return False
    
    async def register_api_function(self, name: str, api_config: Dict[str, Any],
                                  category: Optional[str] = None,
                                  description: Optional[str] = None) -> bool:
        """注册API函数 (TASK-026新增)"""
        try:
            metadata = {
                'display_name': name,
                'description': description,
                'category': category,
                'source': RegistrationSource.MANUAL
            }
            
            success = await self.registry.register_api_wrapper(name, api_config, metadata)
            
            if success:
                logger.info(f"API函数注册成功: {name}")
            
            return success
            
        except Exception as e:
            logger.error(f"注册API函数失败: {name}, {str(e)}")
            return False
    
    async def discover_and_register_functions(self, source: str, 
                                            category: Optional[str] = None) -> int:
        """发现并注册函数 (TASK-026新增)"""
        try:
            # 定义过滤函数
            def filter_func(func: Callable) -> bool:
                # 检查函数是否有注册标记
                if hasattr(func, 'register_function') and func.register_function:
                    return True
                
                # 检查函数名是否符合约定
                if func.__name__.startswith('api_') or func.__name__.startswith('func_'):
                    return True
                
                return False
            
            # 批量注册
            registered_count = await self.registry.batch_register_from_discovery(source, filter_func)
            
            # 如果指定了分类，更新元数据
            if category and registered_count > 0:
                functions = self.registry.list_functions()
                for func_name in functions[-registered_count:]:  # 获取最新注册的函数
                    metadata = self.registry.get_metadata(func_name)
                    if metadata:
                        metadata.category = category
            
            logger.info(f"发现并注册函数: {registered_count} 个，来源: {source}")
            return registered_count
            
        except Exception as e:
            logger.error(f"发现并注册函数失败: {source}, {str(e)}")
            return 0
    
    async def unregister_function(self, name: str) -> bool:
        """注销函数 (TASK-026新增)"""
        try:
            success = await self.registry.unregister_function(name)
            
            if success:
                # 保持向后兼容
                if name in self._registered_functions:
                    del self._registered_functions[name]
                if name in self._function_metadata:
                    del self._function_metadata[name]
                
                # 清除缓存
                await self.cache_service.delete(f"function_def:{name}", namespace=self.cache_namespace)
                
                logger.info(f"函数注销成功: {name}")
            
            return success
            
        except Exception as e:
            logger.error(f"注销函数失败: {name}, {str(e)}")
            return False
    
    async def reload_function(self, name: str) -> bool:
        """重新加载函数 (TASK-026新增)"""
        try:
            # 先从注册器重新加载
            success = await self.registry.reload_function(name)
            
            if success:
                # 清除相关缓存
                await self.cache_service.delete(f"function_def:{name}", namespace=self.cache_namespace)
                
                # 重新加载到本地缓存
                await self._load_function_from_db(name)
                
                logger.info(f"函数重新加载成功: {name}")
            
            return success
            
        except Exception as e:
            logger.error(f"重新加载函数失败: {name}, {str(e)}")
            return False
    
    def list_registered_functions(self, category: Optional[str] = None, 
                                tags: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        """列出已注册的函数 (TASK-026新增)"""
        try:
            function_names = self.registry.list_functions(category, tags)
            
            function_list = []
            for name in function_names:
                metadata = self.registry.get_metadata(name)
                if metadata:
                    function_info = {
                        'name': name,
                        'display_name': metadata.display_name,
                        'description': metadata.description,
                        'category': metadata.category,
                        'function_type': metadata.function_type.value,
                        'source': metadata.source.value,
                        'tags': metadata.tags,
                        'version': metadata.version,
                        'is_async': metadata.signature.is_async if metadata.signature else False,
                        'parameter_count': len(metadata.signature.parameters) if metadata.signature else 0,
                        'created_at': metadata.created_at.isoformat(),
                        'updated_at': metadata.updated_at.isoformat()
                    }
                    function_list.append(function_info)
            
            return function_list
            
        except Exception as e:
            logger.error(f"列出已注册函数失败: {str(e)}")
            return []
    
    def get_function_metadata_detailed(self, name: str) -> Optional[Dict[str, Any]]:
        """获取函数详细元数据 (TASK-026新增)"""
        try:
            metadata = self.registry.get_metadata(name)
            if not metadata:
                return None
            
            return {
                'name': metadata.name,
                'display_name': metadata.display_name,
                'description': metadata.description,
                'category': metadata.category,
                'version': metadata.version,
                'function_type': metadata.function_type.value,
                'source': metadata.source.value,
                'tags': metadata.tags,
                'dependencies': metadata.dependencies,
                'config': metadata.config,
                'signature': {
                    'parameters': metadata.signature.parameters,
                    'return_type': metadata.signature.return_type,
                    'is_async': metadata.signature.is_async,
                    'is_generator': metadata.signature.is_generator,
                    'docstring': metadata.signature.docstring
                } if metadata.signature else None,
                'created_at': metadata.created_at.isoformat(),
                'updated_at': metadata.updated_at.isoformat(),
                'hash_value': metadata.hash_value
            }
            
        except Exception as e:
            logger.error(f"获取函数详细元数据失败: {name}, {str(e)}")
            return None
    
    def get_registry_statistics(self) -> Dict[str, Any]:
        """获取注册器统计信息 (TASK-026新增)"""
        try:
            return self.registry.get_statistics()
        except Exception as e:
            logger.error(f"获取注册器统计信息失败: {str(e)}")
            return {}
    
    async def bulk_register_from_config(self, config_data: List[Dict[str, Any]]) -> Dict[str, bool]:
        """批量从配置注册函数 (TASK-026新增)"""
        results = {}
        
        for config in config_data:
            try:
                name = config.get('name')
                function_type = config.get('type', 'python_code')
                
                if function_type == 'python_code':
                    success = await self.register_code_function(
                        name,
                        config.get('code', ''),
                        config.get('entry_point'),
                        config.get('category'),
                        config.get('description')
                    )
                elif function_type == 'api_call':
                    success = await self.register_api_function(
                        name,
                        config.get('api_config', {}),
                        config.get('category'),
                        config.get('description')
                    )
                else:
                    logger.warning(f"不支持的函数类型: {function_type}")
                    success = False
                
                results[name] = success
                
            except Exception as e:
                logger.error(f"批量注册函数失败: {config.get('name', 'unknown')}, {str(e)}")
                results[config.get('name', 'unknown')] = False
        
        successful_count = sum(1 for success in results.values() if success)
        logger.info(f"批量注册完成: {successful_count}/{len(config_data)} 个函数成功")
        
        return results
    
    async def export_function_definitions(self, category: Optional[str] = None) -> List[Dict[str, Any]]:
        """导出函数定义 (TASK-026新增)"""
        try:
            function_names = self.registry.list_functions(category)
            definitions = []
            
            for name in function_names:
                metadata = self.registry.get_metadata(name)
                if metadata:
                    definition = {
                        'name': name,
                        'type': metadata.function_type.value,
                        'display_name': metadata.display_name,
                        'description': metadata.description,
                        'category': metadata.category,
                        'version': metadata.version,
                        'config': metadata.config,
                        'tags': metadata.tags,
                        'dependencies': metadata.dependencies
                    }
                    
                    # 添加签名信息
                    if metadata.signature:
                        definition['signature'] = {
                            'parameters': metadata.signature.parameters,
                            'return_type': metadata.signature.return_type,
                            'is_async': metadata.signature.is_async
                        }
                    
                    definitions.append(definition)
            
            logger.info(f"导出函数定义: {len(definitions)} 个函数")
            return definitions
            
        except Exception as e:
            logger.error(f"导出函数定义失败: {str(e)}")
            return []
    
    # ========== 新增：API包装器集成方法 (TASK-027) ==========
    
    async def create_api_wrapper(self, config: Dict[str, Any]) -> bool:
        """创建API包装器 (TASK-027新增)"""
        try:
            wrapper = await self.api_wrapper_manager.create_wrapper_from_config(config)
            
            # 同时注册为函数
            if config.get('register_as_function', True):
                await self._register_wrapper_as_function(wrapper, config)
            
            logger.info(f"创建API包装器成功: {config.get('name', 'default')}")
            return True
            
        except Exception as e:
            logger.error(f"创建API包装器失败: {str(e)}")
            return False
    
    async def _register_wrapper_as_function(self, wrapper, config: Dict[str, Any]):
        """将API包装器注册为函数"""
        try:
            wrapper_name = config.get('name', 'default')
            
            # 创建包装器函数
            async def wrapper_function(**kwargs):
                endpoint = kwargs.pop('endpoint', '')
                method = kwargs.pop('method', config.get('default_method', 'POST'))
                
                response = await self.api_wrapper_manager.call_api(
                    wrapper_name, endpoint, method, params=kwargs
                )
                
                if response.error:
                    raise Exception(f"API调用失败: {response.error}")
                
                return response.data
            
            # 注册到动态注册器
            await self.registry.register_from_callable(
                f"api_{wrapper_name}",
                wrapper_function,
                {
                    'display_name': f"API调用: {config.get('description', wrapper_name)}",
                    'description': f"通过{wrapper_name}包装器调用API",
                    'category': 'api',
                    'source': RegistrationSource.MANUAL,
                    'tags': ['api', 'wrapper']
                }
            )
            
        except Exception as e:
            logger.error(f"注册包装器函数失败: {str(e)}")
    
    async def create_api_wrapper_from_template(self, name: str, base_url: str, 
                                             template: str = "rest_api",
                                             auth_config: Optional[Dict[str, Any]] = None) -> bool:
        """从模板创建API包装器 (TASK-027新增)"""
        try:
            config = {
                'name': name,
                'base_url': base_url,
                'template': template,
                'description': f'API包装器: {name}'
            }
            
            if auth_config:
                config['auth'] = auth_config
            
            return await self.create_api_wrapper(config)
            
        except Exception as e:
            logger.error(f"从模板创建API包装器失败: {name}, {str(e)}")
            return False
    
    async def call_api_wrapper(self, wrapper_name: str, endpoint: str,
                             method: str = "POST", params: Dict[str, Any] = None,
                             data: Any = None, **kwargs) -> Any:
        """调用API包装器 (TASK-027新增)"""
        try:
            response = await self.api_wrapper_manager.call_api(
                wrapper_name, endpoint, method, params, data, **kwargs
            )
            
            if response.error:
                raise Exception(f"API调用失败: {response.error}")
            
            return response.data
            
        except Exception as e:
            logger.error(f"调用API包装器失败: {wrapper_name}, {str(e)}")
            raise
    
    async def execute_api_function_call(self, function_call_config, slots: Dict[str, Any],
                                      user_id: str = None, conversation_id: int = None) -> Any:
        """执行API函数调用 (TASK-027新增)"""
        try:
            response = await self.api_wrapper_manager.call_api_by_function_config(
                function_call_config, slots, user_id, conversation_id
            )
            
            if response.error:
                raise Exception(f"API函数调用失败: {response.error}")
            
            return response.data
            
        except Exception as e:
            logger.error(f"执行API函数调用失败: {str(e)}")
            raise
    
    async def get_api_wrapper_metrics(self, wrapper_name: str) -> Optional[Dict[str, Any]]:
        """获取API包装器指标 (TASK-027新增)"""
        try:
            return await self.api_wrapper_manager.get_wrapper_metrics(wrapper_name)
        except Exception as e:
            logger.error(f"获取API包装器指标失败: {wrapper_name}, {str(e)}")
            return None
    
    async def get_all_api_metrics(self) -> Dict[str, Dict[str, Any]]:
        """获取所有API包装器指标 (TASK-027新增)"""
        try:
            return await self.api_wrapper_manager.get_all_metrics()
        except Exception as e:
            logger.error(f"获取所有API指标失败: {str(e)}")
            return {}
    
    def list_api_wrappers(self) -> List[Dict[str, Any]]:
        """列出所有API包装器 (TASK-027新增)"""
        try:
            return self.api_wrapper_manager.list_wrappers()
        except Exception as e:
            logger.error(f"列出API包装器失败: {str(e)}")
            return []
    
    async def test_api_wrapper_connection(self, wrapper_name: str, 
                                        test_endpoint: str = "") -> Dict[str, Any]:
        """测试API包装器连接 (TASK-027新增)"""
        try:
            return await self.api_wrapper_manager.test_wrapper_connection(wrapper_name, test_endpoint)
        except Exception as e:
            logger.error(f"测试API包装器连接失败: {wrapper_name}, {str(e)}")
            return {'success': False, 'error': str(e)}
    
    async def reload_api_wrapper(self, name: str, config: Dict[str, Any]) -> bool:
        """重新加载API包装器 (TASK-027新增)"""
        try:
            success = await self.api_wrapper_manager.reload_wrapper(name, config)
            
            if success:
                # 重新注册为函数
                wrapper = await self.api_wrapper_manager.get_wrapper(name)
                if wrapper and config.get('register_as_function', True):
                    await self._register_wrapper_as_function(wrapper, config)
            
            return success
            
        except Exception as e:
            logger.error(f"重新加载API包装器失败: {name}, {str(e)}")
            return False
    
    async def remove_api_wrapper(self, name: str) -> bool:
        """移除API包装器 (TASK-027新增)"""
        try:
            # 移除对应的函数
            await self.unregister_function(f"api_{name}")
            
            # 移除包装器
            return await self.api_wrapper_manager.remove_wrapper(name)
            
        except Exception as e:
            logger.error(f"移除API包装器失败: {name}, {str(e)}")
            return False
    
    async def batch_create_api_wrappers(self, configs: List[Dict[str, Any]]) -> Dict[str, bool]:
        """批量创建API包装器 (TASK-027新增)"""
        results = {}
        
        for config in configs:
            try:
                name = config.get('name', 'unknown')
                success = await self.create_api_wrapper(config)
                results[name] = success
            except Exception as e:
                logger.error(f"批量创建API包装器失败: {config.get('name', 'unknown')}, {str(e)}")
                results[config.get('name', 'unknown')] = False
        
        successful_count = sum(1 for success in results.values() if success)
        logger.info(f"批量创建API包装器完成: {successful_count}/{len(configs)} 个成功")
        
        return results
    
    def export_api_wrapper_configurations(self) -> List[Dict[str, Any]]:
        """导出API包装器配置 (TASK-027新增)"""
        try:
            return self.api_wrapper_manager.export_configurations()
        except Exception as e:
            logger.error(f"导出API包装器配置失败: {str(e)}")
            return []
    
    async def import_api_wrapper_configurations(self, configurations: List[Dict[str, Any]]) -> Dict[str, bool]:
        """导入API包装器配置 (TASK-027新增)"""
        try:
            results = await self.api_wrapper_manager.import_configurations(configurations)
            
            # 为成功导入的包装器注册函数
            for name, success in results.items():
                if success:
                    try:
                        wrapper = await self.api_wrapper_manager.get_wrapper(name)
                        config = next((c for c in configurations if c.get('name') == name), {})
                        if wrapper and config.get('register_as_function', True):
                            await self._register_wrapper_as_function(wrapper, config)
                    except Exception as e:
                        logger.warning(f"导入后注册函数失败: {name}, {str(e)}")
            
            return results
            
        except Exception as e:
            logger.error(f"导入API包装器配置失败: {str(e)}")
            return {}
    
    async def create_function_call_wrapper(self, intent_name: str, function_name: str,
                                         api_endpoint: str, method: str = "POST",
                                         headers: Dict[str, str] = None,
                                         param_mapping: Dict[str, str] = None,
                                         timeout: int = 30, retry_times: int = 3) -> bool:
        """创建函数调用包装器 (TASK-027新增)"""
        try:
            wrapper_name = f"func_{intent_name}_{function_name}"
            
            config = {
                'name': wrapper_name,
                'base_url': api_endpoint,
                'method': method,
                'timeout': timeout,
                'headers': headers or {},
                'parameter_mapping': param_mapping or {},
                'retry': {
                    'max_attempts': retry_times,
                    'strategy': 'exponential'
                },
                'description': f'函数调用包装器: {intent_name}.{function_name}'
            }
            
            return await self.create_api_wrapper(config)
            
        except Exception as e:
            logger.error(f"创建函数调用包装器失败: {intent_name}.{function_name}, {str(e)}")
            return False
    
    # ========== 新增：参数验证和映射方法 (TASK-028) ==========
    
    async def validate_parameters(self, function_name: str, parameters: Dict[str, Any],
                                context: Dict[str, Any] = None) -> Dict[str, Any]:
        """验证函数参数 (TASK-028新增)"""
        try:
            # 获取函数参数模式
            param_schemas = await self._get_parameter_schemas(function_name)
            
            if not param_schemas:
                logger.warning(f"未找到函数参数模式: {function_name}")
                return {'is_valid': False, 'errors': ['未找到参数模式']}
            
            # 执行参数验证
            validation_results = await self.parameter_validator.validate_parameters(
                parameters, param_schemas, context
            )
            
            # 汇总验证结果
            all_valid = all(result.is_valid for result in validation_results.values())
            all_errors = []
            all_warnings = []
            validated_data = {}
            
            for param_name, result in validation_results.items():
                if result.is_valid:
                    validated_data[param_name] = result.converted_value
                else:
                    all_errors.extend(result.errors)
                
                all_warnings.extend(result.warnings)
            
            return {
                'is_valid': all_valid,
                'validated_data': validated_data,
                'errors': all_errors,
                'warnings': all_warnings,
                'results': validation_results
            }
            
        except Exception as e:
            logger.error(f"参数验证失败: {function_name}, {str(e)}")
            return {'is_valid': False, 'errors': [f'验证过程异常: {str(e)}']}
    
    async def _get_parameter_schemas(self, function_name: str) -> Dict[str, ParameterSchema]:
        """获取函数参数模式"""
        try:
            # 首先尝试从缓存获取
            cache_key = f"param_schemas:{function_name}"
            cached_schemas = await self.cache_service.get(cache_key, namespace=self.cache_namespace)
            if cached_schemas:
                # 反序列化缓存的模式
                return self._deserialize_schemas(cached_schemas)
            
            # 从动态注册器获取元数据
            metadata = self.registry.get_metadata(function_name)
            if metadata and metadata.signature:
                return self._convert_signature_to_schemas(metadata.signature)
            
            # 尝试从数据库获取参数定义
            try:
                function_def = Function.get(
                    Function.function_name == function_name,
                    Function.is_active == True
                )
                
                schemas = {}
                for param in function_def.parameters:
                    schema = ParameterSchema(
                        name=param.parameter_name,
                        parameter_type=self._map_parameter_type(param.parameter_type),
                        description=param.description,
                        has_default=param.default_value is not None,
                        default_value=json.loads(param.default_value) if param.default_value else None
                    )
                    
                    # 添加基础验证规则
                    if param.is_required:
                        schema.rules.append(create_required_rule())
                    
                    schemas[param.parameter_name] = schema
                
                return schemas
            
            except Exception as db_error:
                logger.warning(f"从数据库获取参数模式失败: {function_name}, {str(db_error)}")
                return {}
            
        except Exception as e:
            logger.error(f"获取参数模式失败: {function_name}, {str(e)}")
            return {}
    
    def _convert_signature_to_schemas(self, signature) -> Dict[str, ParameterSchema]:
        """将函数签名转换为参数模式"""
        schemas = {}
        
        for param_info in signature.parameters:
            param_type = self._map_parameter_type(param_info.get('type', 'Any'))
            
            schema = ParameterSchema(
                name=param_info['name'],
                parameter_type=param_type,
                has_default=not param_info.get('required', True),
                default_value=param_info.get('default')
            )
            
            # 添加基础验证规则
            if param_info.get('required', True):
                schema.rules.append(create_required_rule())
            
            schemas[param_info['name']] = schema
        
        return schemas
    
    def _map_parameter_type(self, type_name: str) -> ParameterType:
        """映射参数类型"""
        type_mapping = {
            'str': ParameterType.STRING,
            'string': ParameterType.STRING,
            'int': ParameterType.INTEGER,
            'integer': ParameterType.INTEGER,
            'float': ParameterType.FLOAT,
            'bool': ParameterType.BOOLEAN,
            'boolean': ParameterType.BOOLEAN,
            'list': ParameterType.LIST,
            'dict': ParameterType.DICT,
            'datetime': ParameterType.DATETIME,
            'date': ParameterType.DATE,
            'email': ParameterType.EMAIL,
            'url': ParameterType.URL,
            'phone': ParameterType.PHONE,
            'uuid': ParameterType.UUID,
            'json': ParameterType.JSON
        }
        return type_mapping.get(type_name.lower(), ParameterType.ANY)
    
    async def map_parameters(self, source_params: Dict[str, Any], 
                           mapping_rules: List[Dict[str, Any]] = None,
                           context: Dict[str, Any] = None) -> Dict[str, Any]:
        """映射参数 (TASK-028新增)"""
        try:
            # 添加映射规则
            if mapping_rules:
                for rule_config in mapping_rules:
                    rule = ParameterMappingRule(
                        source_name=rule_config['source_name'],
                        target_name=rule_config['target_name'],
                        transformation=rule_config.get('transformation'),
                        default_value=rule_config.get('default_value'),
                        condition=rule_config.get('condition'),
                        description=rule_config.get('description')
                    )
                    self.parameter_mapper.add_mapping_rule(rule)
            
            # 执行参数映射
            mapped_params = await self.parameter_mapper.map_parameters(source_params, context)
            
            logger.debug(f"参数映射完成: {len(source_params)} -> {len(mapped_params)}")
            return mapped_params
            
        except Exception as e:
            logger.error(f"参数映射失败: {str(e)}")
            return source_params
    
    async def create_parameter_schema(self, function_name: str, 
                                    parameter_definitions: List[Dict[str, Any]]) -> bool:
        """创建参数模式 (TASK-028新增)"""
        try:
            schemas = {}
            
            for param_def in parameter_definitions:
                param_name = param_def['name']
                param_type = self._map_parameter_type(param_def.get('type', 'string'))
                
                schema = ParameterSchema(
                    name=param_name,
                    parameter_type=param_type,
                    description=param_def.get('description'),
                    has_default=param_def.get('has_default', False),
                    default_value=param_def.get('default_value'),
                    auto_convert=param_def.get('auto_convert', True),
                    source_name=param_def.get('source_name'),
                    aliases=param_def.get('aliases', [])
                )
                
                # 添加验证规则
                rules = param_def.get('validation_rules', [])
                for rule_def in rules:
                    rule = self._create_validation_rule(rule_def)
                    if rule:
                        schema.rules.append(rule)
                
                # 设置嵌套模式
                if param_def.get('nested_schema'):
                    schema.nested_schema = await self._create_nested_schemas(
                        param_def['nested_schema']
                    )
                
                schemas[param_name] = schema
            
            # 保存到缓存 - 序列化后保存
            cache_key = f"param_schemas:{function_name}"
            serialized_schemas = self._serialize_schemas(schemas)
            await self.cache_service.set(
                cache_key, serialized_schemas, ttl=3600, namespace=self.cache_namespace
            )
            
            logger.info(f"创建参数模式成功: {function_name}, {len(schemas)} 个参数")
            return True
            
        except Exception as e:
            logger.error(f"创建参数模式失败: {function_name}, {str(e)}")
            return False
    
    def _create_validation_rule(self, rule_def: Dict[str, Any]) -> Optional[ValidationRule]:
        """创建验证规则"""
        try:
            rule_type = rule_def.get('type')
            
            if rule_type == 'required':
                return create_required_rule(rule_def.get('name', 'required'))
            
            elif rule_type == 'length':
                return create_length_rule(
                    rule_def.get('name', 'length'),
                    rule_def.get('min_length'),
                    rule_def.get('max_length')
                )
            
            elif rule_type == 'range':
                return create_range_rule(
                    rule_def.get('name', 'range'),
                    rule_def.get('min_value'),
                    rule_def.get('max_value')
                )
            
            elif rule_type == 'pattern':
                return create_pattern_rule(
                    rule_def.get('name', 'pattern'),
                    rule_def.get('pattern'),
                    rule_def.get('flags', 0)
                )
            
            elif rule_type == 'enum':
                return create_enum_rule(
                    rule_def.get('name', 'enum'),
                    rule_def.get('values', []),
                    rule_def.get('case_sensitive', True)
                )
            
            elif rule_type == 'custom':
                return create_custom_rule(
                    rule_def.get('name', 'custom'),
                    rule_def.get('validator'),
                    rule_def.get('message')
                )
            
            else:
                logger.warning(f"不支持的验证规则类型: {rule_type}")
                return None
                
        except Exception as e:
            logger.error(f"创建验证规则失败: {str(e)}")
            return None
    
    async def _create_nested_schemas(self, nested_def: Dict[str, Any]) -> Dict[str, ParameterSchema]:
        """创建嵌套参数模式"""
        nested_schemas = {}
        
        for param_name, param_def in nested_def.items():
            param_type = self._map_parameter_type(param_def.get('type', 'string'))
            
            schema = ParameterSchema(
                name=param_name,
                parameter_type=param_type,
                description=param_def.get('description'),
                has_default=param_def.get('has_default', False),
                default_value=param_def.get('default_value')
            )
            
            # 添加验证规则
            rules = param_def.get('validation_rules', [])
            for rule_def in rules:
                rule = self._create_validation_rule(rule_def)
                if rule:
                    schema.rules.append(rule)
            
            nested_schemas[param_name] = schema
        
        return nested_schemas
    
    async def validate_and_convert_parameters(self, function_name: str, 
                                            parameters: Dict[str, Any],
                                            context: Dict[str, Any] = None) -> Dict[str, Any]:
        """验证并转换参数 (TASK-028新增，替换旧的验证方法)"""
        try:
            # 参数映射（如果需要）
            mapped_params = await self.map_parameters(parameters, context=context)
            
            # 参数验证
            validation_result = await self.validate_parameters(
                function_name, mapped_params, context
            )
            
            if not validation_result['is_valid']:
                errors = validation_result.get('errors', [])
                raise ValueError(f"参数验证失败: {'; '.join(errors)}")
            
            # 返回验证后的数据
            validated_data = validation_result.get('validated_data', mapped_params)
            
            # 记录警告
            warnings = validation_result.get('warnings', [])
            if warnings:
                logger.warning(f"参数验证警告 {function_name}: {'; '.join(warnings)}")
            
            return validated_data
            
        except Exception as e:
            logger.error(f"参数验证和转换失败: {function_name}, {str(e)}")
            raise
    
    def get_parameter_validation_statistics(self) -> Dict[str, Any]:
        """获取参数验证统计信息 (TASK-028新增)"""
        try:
            stats = self.parameter_validator.get_statistics()
            return stats
        except Exception as e:
            logger.error(f"获取参数验证统计失败: {str(e)}")
            return {}
    
    async def test_parameter_validation(self, function_name: str, 
                                      test_cases: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """测试参数验证 (TASK-028新增)"""
        try:
            results = []
            
            for i, test_case in enumerate(test_cases):
                test_params = test_case.get('parameters', {})
                expected_result = test_case.get('expected_result', 'success')
                description = test_case.get('description', f'测试用例 {i+1}')
                
                try:
                    validation_result = await self.validate_parameters(
                        function_name, test_params
                    )
                    
                    actual_result = 'success' if validation_result['is_valid'] else 'failure'
                    test_passed = (actual_result == expected_result)
                    
                    results.append({
                        'test_case': i + 1,
                        'description': description,
                        'parameters': test_params,
                        'expected': expected_result,
                        'actual': actual_result,
                        'passed': test_passed,
                        'details': validation_result
                    })
                    
                except Exception as e:
                    results.append({
                        'test_case': i + 1,
                        'description': description,
                        'parameters': test_params,
                        'expected': expected_result,
                        'actual': 'error',
                        'passed': False,
                        'error': str(e)
                    })
            
            # 统计测试结果
            passed_count = sum(1 for r in results if r.get('passed', False))
            logger.info(f"参数验证测试完成: {passed_count}/{len(results)} 通过")
            
            return results
            
        except Exception as e:
            logger.error(f"测试参数验证失败: {function_name}, {str(e)}")
            return []
    
    async def export_parameter_schemas(self, function_name: str = None) -> Dict[str, Any]:
        """导出参数模式 (TASK-028新增)"""
        try:
            if function_name:
                # 导出单个函数的参数模式
                schemas = await self._get_parameter_schemas(function_name)
                return {function_name: self._serialize_schemas(schemas)}
            else:
                # 导出所有函数的参数模式
                all_schemas = {}
                function_names = self.registry.list_functions()
                
                for name in function_names:
                    schemas = await self._get_parameter_schemas(name)
                    if schemas:
                        all_schemas[name] = self._serialize_schemas(schemas)
                
                return all_schemas
                
        except Exception as e:
            logger.error(f"导出参数模式失败: {function_name}, {str(e)}")
            return {}
    
    def _serialize_schemas(self, schemas: Dict[str, ParameterSchema]) -> Dict[str, Any]:
        """序列化参数模式"""
        serialized = {}
        
        for name, schema in schemas.items():
            serialized[name] = {
                'name': schema.name,
                'parameter_type': schema.parameter_type.value,
                'description': schema.description,
                'has_default': schema.has_default,
                'default_value': schema.default_value,
                'auto_convert': schema.auto_convert,
                'source_name': schema.source_name,
                'aliases': schema.aliases,
                'rules': [
                    {
                        'name': rule.name,
                        'validation_type': rule.validation_type.value,
                        'severity': rule.severity.value,
                        'enabled': rule.enabled,
                        'required': rule.required,
                        'nullable': rule.nullable,
                        'min_length': rule.min_length,
                        'max_length': rule.max_length,
                        'min_value': rule.min_value,
                        'max_value': rule.max_value,
                        'pattern': rule.pattern,
                        'enum_values': rule.enum_values,
                        'case_sensitive': rule.case_sensitive,
                        'custom_message': rule.custom_message,
                        'description': rule.description,
                        'error_message': rule.error_message
                    }
                    for rule in schema.rules
                ],
                'nested_schema': self._serialize_schemas(schema.nested_schema) if schema.nested_schema else None,
                'item_type': schema.item_type.value if schema.item_type else None,
                'metadata': schema.metadata
            }
        
        return serialized
    
    def _deserialize_schemas(self, serialized_schemas: Dict[str, Any]) -> Dict[str, ParameterSchema]:
        """反序列化参数模式"""
        schemas = {}
        
        for name, schema_data in serialized_schemas.items():
            try:
                schema = ParameterSchema(
                    name=schema_data['name'],
                    parameter_type=ParameterType(schema_data['parameter_type']),
                    description=schema_data.get('description'),
                    has_default=schema_data.get('has_default', False),
                    default_value=schema_data.get('default_value'),
                    auto_convert=schema_data.get('auto_convert', True),
                    source_name=schema_data.get('source_name'),
                    aliases=schema_data.get('aliases', [])
                )
                
                # 重建验证规则
                for rule_data in schema_data.get('rules', []):
                    rule = ValidationRule(
                        name=rule_data['name'],
                        validation_type=ValidationType(rule_data['validation_type']),
                        severity=ValidationSeverity(rule_data['severity']),
                        enabled=rule_data.get('enabled', True),
                        required=rule_data.get('required', False),
                        nullable=rule_data.get('nullable', True),
                        min_length=rule_data.get('min_length'),
                        max_length=rule_data.get('max_length'),
                        min_value=rule_data.get('min_value'),
                        max_value=rule_data.get('max_value'),
                        pattern=rule_data.get('pattern'),
                        enum_values=rule_data.get('enum_values'),
                        case_sensitive=rule_data.get('case_sensitive', True),
                        custom_message=rule_data.get('custom_message'),
                        description=rule_data.get('description'),
                        error_message=rule_data.get('error_message')
                    )
                    schema.rules.append(rule)
                
                # 处理嵌套模式
                if schema_data.get('nested_schema'):
                    schema.nested_schema = self._deserialize_schemas(schema_data['nested_schema'])
                
                # 处理列表元素类型
                if schema_data.get('item_type'):
                    schema.item_type = ParameterType(schema_data['item_type'])
                
                schema.metadata = schema_data.get('metadata', {})
                schemas[name] = schema
                
            except Exception as e:
                logger.warning(f"反序列化参数模式失败: {name}, {str(e)}")
                continue
        
        return schemas