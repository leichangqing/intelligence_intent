"""
API包装器实现
提供统一的API调用接口，支持多种认证方式、重试机制、参数映射等功能
"""

import asyncio
import aiohttp
import json
import ssl
import time
from typing import Dict, List, Optional, Any, Union, Callable, Tuple
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime, timedelta
import hashlib
import base64
from urllib.parse import urljoin, urlparse
import re

from src.utils.logger import get_logger

logger = get_logger(__name__)


class HttpMethod(Enum):
    """HTTP方法枚举"""
    GET = "GET"
    POST = "POST"
    PUT = "PUT"
    DELETE = "DELETE"
    PATCH = "PATCH"
    HEAD = "HEAD"
    OPTIONS = "OPTIONS"


class AuthType(Enum):
    """认证类型枚举"""
    NONE = "none"
    API_KEY = "api_key"
    BEARER_TOKEN = "bearer_token"
    BASIC_AUTH = "basic_auth"
    OAUTH2 = "oauth2"
    CUSTOM_HEADER = "custom_header"
    DIGEST_AUTH = "digest_auth"
    JWT = "jwt"


class ContentType(Enum):
    """内容类型枚举"""
    JSON = "application/json"
    FORM_DATA = "application/x-www-form-urlencoded"
    MULTIPART = "multipart/form-data"
    XML = "application/xml"
    TEXT = "text/plain"
    BINARY = "application/octet-stream"


class RetryStrategy(Enum):
    """重试策略枚举"""
    NONE = "none"
    FIXED = "fixed"
    EXPONENTIAL = "exponential"
    LINEAR = "linear"
    CUSTOM = "custom"


@dataclass
class AuthConfig:
    """认证配置"""
    auth_type: AuthType = AuthType.NONE
    api_key: Optional[str] = None
    api_key_header: str = "X-API-Key"
    token: Optional[str] = None
    username: Optional[str] = None
    password: Optional[str] = None
    oauth2_url: Optional[str] = None
    custom_headers: Dict[str, str] = field(default_factory=dict)
    jwt_secret: Optional[str] = None
    jwt_algorithm: str = "HS256"


@dataclass
class RetryConfig:
    """重试配置"""
    strategy: RetryStrategy = RetryStrategy.EXPONENTIAL
    max_attempts: int = 3
    base_delay: float = 1.0
    max_delay: float = 60.0
    backoff_factor: float = 2.0
    retry_on_status: List[int] = field(default_factory=lambda: [500, 502, 503, 504, 429])
    retry_on_exceptions: List[str] = field(default_factory=lambda: [
        "aiohttp.ClientTimeout", "aiohttp.ClientConnectionError", "ConnectionResetError"
    ])


@dataclass
class RateLimitConfig:
    """限流配置"""
    enabled: bool = False
    requests_per_second: float = 10.0
    requests_per_minute: Optional[int] = None
    requests_per_hour: Optional[int] = None
    burst_size: int = 10
    window_size: int = 60  # 滑动窗口大小(秒)


@dataclass
class CacheConfig:
    """缓存配置"""
    enabled: bool = False
    ttl_seconds: int = 300
    max_size: int = 1000
    cache_key_include_headers: bool = False
    cache_key_include_params: bool = True
    cache_get_only: bool = True


@dataclass
class ApiWrapperConfig:
    """API包装器配置"""
    base_url: str
    name: str = "default"
    description: Optional[str] = None
    
    # HTTP配置
    default_method: HttpMethod = HttpMethod.POST
    default_headers: Dict[str, str] = field(default_factory=dict)
    default_params: Dict[str, str] = field(default_factory=dict)
    content_type: ContentType = ContentType.JSON
    timeout: float = 30.0
    max_connections: int = 100
    max_connections_per_host: int = 30
    
    # 认证配置
    auth: AuthConfig = field(default_factory=AuthConfig)
    
    # 重试配置
    retry: RetryConfig = field(default_factory=RetryConfig)
    
    # 限流配置
    rate_limit: RateLimitConfig = field(default_factory=RateLimitConfig)
    
    # 缓存配置
    cache: CacheConfig = field(default_factory=CacheConfig)
    
    # SSL配置
    verify_ssl: bool = True
    ssl_context: Optional[ssl.SSLContext] = None
    
    # 参数映射
    parameter_mapping: Dict[str, str] = field(default_factory=dict)
    response_mapping: Dict[str, str] = field(default_factory=dict)
    
    # 请求/响应处理
    request_preprocessor: Optional[Callable] = None
    response_postprocessor: Optional[Callable] = None
    
    # 调试和监控
    debug: bool = False
    log_requests: bool = True
    log_responses: bool = False
    metrics_enabled: bool = True


@dataclass
class ApiRequest:
    """API请求数据"""
    endpoint: str
    method: HttpMethod = HttpMethod.POST
    headers: Dict[str, str] = field(default_factory=dict)
    params: Dict[str, Any] = field(default_factory=dict)
    data: Any = None
    files: Dict[str, Any] = field(default_factory=dict)
    timeout: Optional[float] = None
    auth_override: Optional[AuthConfig] = None
    cache_override: Optional[CacheConfig] = None
    retry_override: Optional[RetryConfig] = None


@dataclass
class ApiResponse:
    """API响应数据"""
    status_code: int
    headers: Dict[str, str]
    data: Any
    raw_content: bytes
    url: str
    method: str
    request_time: float
    response_time: float
    from_cache: bool = False
    retry_count: int = 0
    error: Optional[str] = None


class RateLimiter:
    """限流器"""
    
    def __init__(self, config: RateLimitConfig):
        self.config = config
        self.requests = []  # 请求时间戳列表
        self.lock = asyncio.Lock()
    
    async def can_proceed(self) -> bool:
        """检查是否可以继续请求"""
        if not self.config.enabled:
            return True
        
        async with self.lock:
            now = time.time()
            
            # 清理过期的请求记录
            cutoff = now - self.config.window_size
            self.requests = [req_time for req_time in self.requests if req_time > cutoff]
            
            # 检查请求限制
            if len(self.requests) >= self.config.burst_size:
                return False
            
            # 检查每秒限制
            recent_requests = [req_time for req_time in self.requests if req_time > now - 1.0]
            if len(recent_requests) >= self.config.requests_per_second:
                return False
            
            # 检查每分钟限制
            if self.config.requests_per_minute:
                minute_requests = [req_time for req_time in self.requests if req_time > now - 60.0]
                if len(minute_requests) >= self.config.requests_per_minute:
                    return False
            
            # 检查每小时限制
            if self.config.requests_per_hour:
                hour_requests = [req_time for req_time in self.requests if req_time > now - 3600.0]
                if len(hour_requests) >= self.config.requests_per_hour:
                    return False
            
            return True
    
    async def record_request(self):
        """记录请求"""
        if self.config.enabled:
            async with self.lock:
                self.requests.append(time.time())


class ResponseCache:
    """响应缓存"""
    
    def __init__(self, config: CacheConfig):
        self.config = config
        self.cache = {}
        self.access_times = {}
        self.lock = asyncio.Lock()
    
    def _generate_cache_key(self, request: ApiRequest, config: ApiWrapperConfig) -> str:
        """生成缓存键"""
        key_parts = [
            request.endpoint,
            request.method.value
        ]
        
        if self.config.cache_key_include_params:
            params_str = json.dumps(request.params, sort_keys=True)
            key_parts.append(params_str)
        
        if self.config.cache_key_include_headers:
            headers_str = json.dumps(request.headers, sort_keys=True)
            key_parts.append(headers_str)
        
        key = "|".join(key_parts)
        return hashlib.md5(key.encode()).hexdigest()
    
    async def get(self, request: ApiRequest, config: ApiWrapperConfig) -> Optional[ApiResponse]:
        """获取缓存响应"""
        if not self.config.enabled:
            return None
        
        if self.config.cache_get_only and request.method != HttpMethod.GET:
            return None
        
        async with self.lock:
            cache_key = self._generate_cache_key(request, config)
            
            if cache_key in self.cache:
                cached_response, cache_time = self.cache[cache_key]
                
                # 检查是否过期
                if time.time() - cache_time < self.config.ttl_seconds:
                    self.access_times[cache_key] = time.time()
                    cached_response.from_cache = True
                    return cached_response
                else:
                    # 清理过期缓存
                    del self.cache[cache_key]
                    if cache_key in self.access_times:
                        del self.access_times[cache_key]
        
        return None
    
    async def set(self, request: ApiRequest, response: ApiResponse, config: ApiWrapperConfig):
        """设置缓存响应"""
        if not self.config.enabled:
            return
        
        if self.config.cache_get_only and request.method != HttpMethod.GET:
            return
        
        async with self.lock:
            # 检查缓存大小限制
            if len(self.cache) >= self.config.max_size:
                # 删除最少使用的缓存项
                oldest_key = min(self.access_times.keys(), key=lambda k: self.access_times[k])
                del self.cache[oldest_key]
                del self.access_times[oldest_key]
            
            cache_key = self._generate_cache_key(request, config)
            self.cache[cache_key] = (response, time.time())
            self.access_times[cache_key] = time.time()


class ApiMetrics:
    """API指标收集"""
    
    def __init__(self):
        self.metrics = {
            'total_requests': 0,
            'success_count': 0,
            'error_count': 0,
            'cache_hits': 0,
            'retry_count': 0,
            'avg_response_time': 0.0,
            'status_codes': {},
            'error_types': {},
            'endpoints': {}
        }
        self.lock = asyncio.Lock()
    
    async def record_request(self, request: ApiRequest, response: ApiResponse):
        """记录请求指标"""
        async with self.lock:
            self.metrics['total_requests'] += 1
            
            if response.from_cache:
                self.metrics['cache_hits'] += 1
            
            if response.error:
                self.metrics['error_count'] += 1
                error_type = type(response.error).__name__
                self.metrics['error_types'][error_type] = self.metrics['error_types'].get(error_type, 0) + 1
            else:
                self.metrics['success_count'] += 1
            
            # 状态码统计
            status_code = str(response.status_code)
            self.metrics['status_codes'][status_code] = self.metrics['status_codes'].get(status_code, 0) + 1
            
            # 端点统计
            endpoint = request.endpoint
            if endpoint not in self.metrics['endpoints']:
                self.metrics['endpoints'][endpoint] = {
                    'count': 0,
                    'avg_response_time': 0.0,
                    'success_count': 0,
                    'error_count': 0
                }
            
            endpoint_metrics = self.metrics['endpoints'][endpoint]
            endpoint_metrics['count'] += 1
            
            if response.error:
                endpoint_metrics['error_count'] += 1
            else:
                endpoint_metrics['success_count'] += 1
            
            # 响应时间统计
            response_time = response.response_time - response.request_time
            if response_time > 0:
                total_requests = self.metrics['total_requests']
                current_avg = self.metrics['avg_response_time']
                self.metrics['avg_response_time'] = ((current_avg * (total_requests - 1)) + response_time) / total_requests
                
                # 端点响应时间
                endpoint_count = endpoint_metrics['count']
                endpoint_avg = endpoint_metrics['avg_response_time']
                endpoint_metrics['avg_response_time'] = ((endpoint_avg * (endpoint_count - 1)) + response_time) / endpoint_count
            
            self.metrics['retry_count'] += response.retry_count
    
    def get_metrics(self) -> Dict[str, Any]:
        """获取指标数据"""
        return self.metrics.copy()


class ApiWrapper:
    """API包装器主类"""
    
    def __init__(self, config: ApiWrapperConfig):
        self.config = config
        self.session: Optional[aiohttp.ClientSession] = None
        self.rate_limiter = RateLimiter(config.rate_limit)
        self.cache = ResponseCache(config.cache)
        self.metrics = ApiMetrics() if config.metrics_enabled else None
        self._session_lock = asyncio.Lock()
    
    async def __aenter__(self):
        """异步上下文管理器入口"""
        await self._ensure_session()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """异步上下文管理器出口"""
        await self.close()
    
    async def _ensure_session(self):
        """确保会话已创建"""
        if self.session is None or self.session.closed:
            async with self._session_lock:
                if self.session is None or self.session.closed:
                    await self._create_session()
    
    async def _create_session(self):
        """创建HTTP会话"""
        # 创建连接器
        connector = aiohttp.TCPConnector(
            limit=self.config.max_connections,
            limit_per_host=self.config.max_connections_per_host,
            ssl=self.config.ssl_context if self.config.ssl_context else self.config.verify_ssl
        )
        
        # 创建超时配置
        timeout = aiohttp.ClientTimeout(total=self.config.timeout)
        
        # 创建会话
        self.session = aiohttp.ClientSession(
            connector=connector,
            timeout=timeout,
            headers=self.config.default_headers
        )
        
        logger.debug(f"创建API会话: {self.config.name}")
    
    async def close(self):
        """关闭API包装器"""
        if self.session and not self.session.closed:
            await self.session.close()
            self.session = None
            logger.debug(f"关闭API会话: {self.config.name}")
    
    async def call(self, request: ApiRequest) -> ApiResponse:
        """执行API调用"""
        await self._ensure_session()
        
        # 检查缓存
        cached_response = await self.cache.get(request, self.config)
        if cached_response:
            if self.metrics:
                await self.metrics.record_request(request, cached_response)
            return cached_response
        
        # 限流检查
        if not await self.rate_limiter.can_proceed():
            raise Exception("请求频率超过限制")
        
        # 执行请求（带重试）
        response = await self._execute_with_retry(request)
        
        # 记录请求
        await self.rate_limiter.record_request()
        
        # 缓存响应
        if not response.error:
            await self.cache.set(request, response, self.config)
        
        # 记录指标
        if self.metrics:
            await self.metrics.record_request(request, response)
        
        return response
    
    async def _execute_with_retry(self, request: ApiRequest) -> ApiResponse:
        """带重试的执行请求"""
        retry_config = request.retry_override or self.config.retry
        
        last_exception = None
        for attempt in range(retry_config.max_attempts):
            try:
                response = await self._execute_single_request(request)
                
                # 检查是否需要重试
                if response.status_code in retry_config.retry_on_status:
                    if attempt < retry_config.max_attempts - 1:
                        delay = self._calculate_retry_delay(retry_config, attempt)
                        logger.warning(f"请求失败 (状态码: {response.status_code}), {delay:.2f}秒后重试 (第{attempt + 1}次)")
                        await asyncio.sleep(delay)
                        continue
                
                response.retry_count = attempt
                return response
                
            except Exception as e:
                last_exception = e
                exception_name = type(e).__name__
                
                # 检查是否应该重试此异常
                should_retry = any(
                    exception_name in exc_type for exc_type in retry_config.retry_on_exceptions
                )
                
                if should_retry and attempt < retry_config.max_attempts - 1:
                    delay = self._calculate_retry_delay(retry_config, attempt)
                    logger.warning(f"请求异常: {str(e)}, {delay:.2f}秒后重试 (第{attempt + 1}次)")
                    await asyncio.sleep(delay)
                    continue
                else:
                    break
        
        # 所有重试都失败了
        return ApiResponse(
            status_code=0,
            headers={},
            data=None,
            raw_content=b'',
            url=request.endpoint,
            method=request.method.value,
            request_time=time.time(),
            response_time=time.time(),
            retry_count=retry_config.max_attempts - 1,
            error=str(last_exception) if last_exception else "重试次数已用尽"
        )
    
    def _calculate_retry_delay(self, retry_config: RetryConfig, attempt: int) -> float:
        """计算重试延迟"""
        if retry_config.strategy == RetryStrategy.FIXED:
            return retry_config.base_delay
        elif retry_config.strategy == RetryStrategy.LINEAR:
            return retry_config.base_delay * (attempt + 1)
        elif retry_config.strategy == RetryStrategy.EXPONENTIAL:
            delay = retry_config.base_delay * (retry_config.backoff_factor ** attempt)
            return min(delay, retry_config.max_delay)
        else:
            return retry_config.base_delay
    
    async def _execute_single_request(self, request: ApiRequest) -> ApiResponse:
        """执行单次请求"""
        request_start_time = time.time()
        
        # 构建URL
        url = urljoin(self.config.base_url, request.endpoint)
        
        # 准备头部
        headers = {**self.config.default_headers, **request.headers}
        
        # 认证处理
        auth_config = request.auth_override or self.config.auth
        await self._apply_authentication(headers, auth_config)
        
        # 参数映射
        params = self._map_parameters(request.params)
        
        # 数据处理
        data, content_type = await self._prepare_request_data(request.data, request.files)
        if content_type:
            headers['Content-Type'] = content_type
        
        # 超时设置
        timeout = request.timeout or self.config.timeout
        
        # 请求预处理
        if self.config.request_preprocessor:
            headers, params, data = await self.config.request_preprocessor(headers, params, data)
        
        # 日志记录
        if self.config.log_requests:
            logger.info(f"API请求: {request.method.value} {url}")
            if self.config.debug:
                logger.debug(f"请求头: {headers}")
                logger.debug(f"请求参数: {params}")
                if data and self.config.debug:
                    logger.debug(f"请求数据: {data}")
        
        try:
            # 执行HTTP请求
            async with self.session.request(
                method=request.method.value,
                url=url,
                headers=headers,
                params=params,
                data=data,
                timeout=aiohttp.ClientTimeout(total=timeout)
            ) as response:
                response_time = time.time()
                raw_content = await response.read()
                
                # 解析响应数据
                response_data = await self._parse_response_data(response, raw_content)
                
                # 响应后处理
                if self.config.response_postprocessor:
                    response_data = await self.config.response_postprocessor(response_data, response.status)
                
                # 响应映射
                if self.config.response_mapping:
                    response_data = self._map_response(response_data)
                
                # 日志记录
                if self.config.log_responses:
                    logger.info(f"API响应: {response.status} ({response_time - request_start_time:.3f}s)")
                    if self.config.debug:
                        logger.debug(f"响应头: {dict(response.headers)}")
                        logger.debug(f"响应数据: {response_data}")
                
                return ApiResponse(
                    status_code=response.status,
                    headers=dict(response.headers),
                    data=response_data,
                    raw_content=raw_content,
                    url=str(response.url),
                    method=request.method.value,
                    request_time=request_start_time,
                    response_time=response_time
                )
                
        except Exception as e:
            logger.error(f"API请求失败: {str(e)}")
            raise
    
    async def _apply_authentication(self, headers: Dict[str, str], auth_config: AuthConfig):
        """应用认证"""
        if auth_config.auth_type == AuthType.API_KEY:
            if auth_config.api_key:
                headers[auth_config.api_key_header] = auth_config.api_key
        
        elif auth_config.auth_type == AuthType.BEARER_TOKEN:
            if auth_config.token:
                headers['Authorization'] = f"Bearer {auth_config.token}"
        
        elif auth_config.auth_type == AuthType.BASIC_AUTH:
            if auth_config.username and auth_config.password:
                credentials = base64.b64encode(
                    f"{auth_config.username}:{auth_config.password}".encode()
                ).decode()
                headers['Authorization'] = f"Basic {credentials}"
        
        elif auth_config.auth_type == AuthType.JWT:
            if auth_config.jwt_secret:
                # 简单的JWT实现（生产环境应使用专业库）
                import jwt
                payload = {
                    'iss': 'api-wrapper',
                    'exp': datetime.utcnow() + timedelta(hours=1)
                }
                token = jwt.encode(payload, auth_config.jwt_secret, algorithm=auth_config.jwt_algorithm)
                headers['Authorization'] = f"Bearer {token}"
        
        elif auth_config.auth_type == AuthType.CUSTOM_HEADER:
            headers.update(auth_config.custom_headers)
    
    def _map_parameters(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """映射参数"""
        if not self.config.parameter_mapping:
            return params
        
        mapped_params = {}
        for key, value in params.items():
            mapped_key = self.config.parameter_mapping.get(key, key)
            mapped_params[mapped_key] = value
        
        return mapped_params
    
    def _map_response(self, data: Any) -> Any:
        """映射响应数据"""
        if not isinstance(data, dict):
            return data
        
        mapped_data = {}
        for key, value in data.items():
            mapped_key = self.config.response_mapping.get(key, key)
            mapped_data[mapped_key] = value
        
        return mapped_data
    
    async def _prepare_request_data(self, data: Any, files: Dict[str, Any]) -> Tuple[Any, Optional[str]]:
        """准备请求数据"""
        if files:
            # 多部分表单数据
            form_data = aiohttp.FormData()
            
            # 添加普通字段
            if data:
                if isinstance(data, dict):
                    for key, value in data.items():
                        form_data.add_field(key, str(value))
                else:
                    form_data.add_field('data', str(data))
            
            # 添加文件
            for name, file_data in files.items():
                if isinstance(file_data, (str, bytes)):
                    form_data.add_field(name, file_data)
                else:
                    form_data.add_field(name, file_data)
            
            return form_data, None  # Content-Type will be set automatically
        
        elif self.config.content_type == ContentType.JSON:
            if data is not None:
                return json.dumps(data, ensure_ascii=False), ContentType.JSON.value
            return None, None
        
        elif self.config.content_type == ContentType.FORM_DATA:
            if isinstance(data, dict):
                form_data = aiohttp.FormData()
                for key, value in data.items():
                    form_data.add_field(key, str(value))
                return form_data, None
            return str(data), ContentType.FORM_DATA.value
        
        else:
            return data, self.config.content_type.value
    
    async def _parse_response_data(self, response, raw_content: bytes) -> Any:
        """解析响应数据"""
        content_type = response.headers.get('Content-Type', '').lower()
        
        try:
            if 'application/json' in content_type:
                text = raw_content.decode('utf-8')
                return json.loads(text) if text else None
            elif 'text/' in content_type or 'application/xml' in content_type:
                return raw_content.decode('utf-8')
            else:
                return raw_content
        except Exception as e:
            logger.warning(f"解析响应数据失败: {str(e)}")
            return raw_content.decode('utf-8', errors='ignore')
    
    # 便捷方法
    async def get(self, endpoint: str, params: Dict[str, Any] = None, **kwargs) -> ApiResponse:
        """GET请求"""
        request = ApiRequest(endpoint=endpoint, method=HttpMethod.GET, params=params or {}, **kwargs)
        return await self.call(request)
    
    async def post(self, endpoint: str, data: Any = None, **kwargs) -> ApiResponse:
        """POST请求"""
        request = ApiRequest(endpoint=endpoint, method=HttpMethod.POST, data=data, **kwargs)
        return await self.call(request)
    
    async def put(self, endpoint: str, data: Any = None, **kwargs) -> ApiResponse:
        """PUT请求"""
        request = ApiRequest(endpoint=endpoint, method=HttpMethod.PUT, data=data, **kwargs)
        return await self.call(request)
    
    async def delete(self, endpoint: str, **kwargs) -> ApiResponse:
        """DELETE请求"""
        request = ApiRequest(endpoint=endpoint, method=HttpMethod.DELETE, **kwargs)
        return await self.call(request)
    
    async def patch(self, endpoint: str, data: Any = None, **kwargs) -> ApiResponse:
        """PATCH请求"""
        request = ApiRequest(endpoint=endpoint, method=HttpMethod.PATCH, data=data, **kwargs)
        return await self.call(request)
    
    def get_metrics(self) -> Optional[Dict[str, Any]]:
        """获取API指标"""
        return self.metrics.get_metrics() if self.metrics else None


class ApiWrapperFactory:
    """API包装器工厂"""
    
    _instances: Dict[str, ApiWrapper] = {}
    
    @classmethod
    async def create_wrapper(cls, config: ApiWrapperConfig) -> ApiWrapper:
        """创建API包装器实例"""
        if config.name in cls._instances:
            wrapper = cls._instances[config.name]
            if wrapper.session and not wrapper.session.closed:
                return wrapper
        
        wrapper = ApiWrapper(config)
        cls._instances[config.name] = wrapper
        return wrapper
    
    @classmethod
    async def get_wrapper(cls, name: str) -> Optional[ApiWrapper]:
        """获取API包装器实例"""
        return cls._instances.get(name)
    
    @classmethod
    async def close_all(cls):
        """关闭所有API包装器"""
        for wrapper in cls._instances.values():
            await wrapper.close()
        cls._instances.clear()


# 便捷函数
async def create_simple_wrapper(
    base_url: str,
    name: str = "default",
    auth_type: AuthType = AuthType.NONE,
    api_key: str = None,
    token: str = None,
    timeout: float = 30.0
) -> ApiWrapper:
    """创建简单的API包装器"""
    auth_config = AuthConfig(auth_type=auth_type, api_key=api_key, token=token)
    config = ApiWrapperConfig(
        base_url=base_url,
        name=name,
        auth=auth_config,
        timeout=timeout
    )
    return await ApiWrapperFactory.create_wrapper(config)