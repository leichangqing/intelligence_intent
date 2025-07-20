"""
FastAPI中间件
"""
from fastapi import Request, Response, HTTPException
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp
import time
import json
from datetime import datetime
from typing import Callable, Dict, Any

from src.utils.logger import get_logger, request_logger, security_logger, performance_logger
from src.config.settings import settings

logger = get_logger(__name__)


class LoggingMiddleware(BaseHTTPMiddleware):
    """请求日志中间件"""
    
    def __init__(self, app: ASGIApp):
        super().__init__(app)
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """处理请求并记录日志"""
        start_time = time.time()
        
        # 生成请求ID
        request_id = request.headers.get("X-Request-ID") or f"req_{int(time.time() * 1000)}"
        
        # 获取用户信息
        user_id = getattr(request.state, 'user_id', None)
        
        # 记录请求开始
        request_logger.log_request(
            method=request.method,
            url=str(request.url),
            user_id=user_id,
            request_id=request_id
        )
        
        try:
            # 执行请求
            response = await call_next(request)
            
            # 计算响应时间
            response_time_ms = int((time.time() - start_time) * 1000)
            
            # 记录响应
            request_logger.log_response(
                status_code=response.status_code,
                response_time_ms=response_time_ms,
                request_id=request_id
            )
            
            # 记录性能日志
            performance_logger.log_api_call(
                api_name=f"{request.method} {request.url.path}",
                duration_ms=response_time_ms,
                success=response.status_code < 400
            )
            
            # 添加响应头
            response.headers["X-Request-ID"] = request_id
            response.headers["X-Response-Time"] = str(response_time_ms)
            
            return response
            
        except Exception as e:
            response_time_ms = int((time.time() - start_time) * 1000)
            
            # 记录错误
            request_logger.log_error(error=e, request_id=request_id)
            
            # 记录性能日志
            performance_logger.log_api_call(
                api_name=f"{request.method} {request.url.path}",
                duration_ms=response_time_ms,
                success=False
            )
            
            raise


class SecurityMiddleware(BaseHTTPMiddleware):
    """安全中间件"""
    
    def __init__(self, app: ASGIApp):
        super().__init__(app)
        self.max_request_size = settings.MAX_REQUEST_SIZE if hasattr(settings, 'MAX_REQUEST_SIZE') else 1024 * 1024  # 1MB
        self.blocked_ips = set()
        self.suspicious_patterns = [
            r'<script[^>]*>.*?</script>',  # XSS
            r'union\s+select',             # SQL注入
            r'drop\s+table',               # SQL注入
            r'exec\s*\(',                  # 代码注入
        ]
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """安全检查和处理"""
        
        # 获取客户端IP
        client_ip = self._get_client_ip(request)
        
        # IP黑名单检查
        if client_ip in self.blocked_ips:
            security_logger.log_security_violation(
                violation_type="blocked_ip_access",
                details=f"被阻止的IP尝试访问: {client_ip}",
                ip_address=client_ip
            )
            return JSONResponse(
                status_code=403,
                content={"error": "Access denied"}
            )
        
        # 请求大小检查
        content_length = request.headers.get("content-length")
        if content_length and int(content_length) > self.max_request_size:
            security_logger.log_security_violation(
                violation_type="oversized_request",
                details=f"请求大小超限: {content_length} bytes",
                ip_address=client_ip
            )
            return JSONResponse(
                status_code=413,
                content={"error": "Request too large"}
            )
        
        # User-Agent检查
        user_agent = request.headers.get("user-agent", "")
        if self._is_suspicious_user_agent(user_agent):
            security_logger.log_security_violation(
                violation_type="suspicious_user_agent",
                details=f"可疑的User-Agent: {user_agent}",
                ip_address=client_ip
            )
        
        try:
            response = await call_next(request)
            
            # 添加安全响应头
            response.headers["X-Content-Type-Options"] = "nosniff"
            response.headers["X-Frame-Options"] = "DENY"
            response.headers["X-XSS-Protection"] = "1; mode=block"
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
            
            return response
            
        except Exception as e:
            logger.error(f"安全中间件处理异常: {str(e)}")
            raise
    
    def _get_client_ip(self, request: Request) -> str:
        """获取客户端真实IP"""
        # 检查代理头
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            return forwarded_for.split(",")[0].strip()
        
        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip
        
        # 返回直接连接IP
        if hasattr(request, "client") and request.client:
            return request.client.host
        
        return "unknown"
    
    def _is_suspicious_user_agent(self, user_agent: str) -> bool:
        """检查User-Agent是否可疑"""
        suspicious_agents = [
            "sqlmap",
            "nmap",
            "nikto",
            "dirb",
            "gobuster",
            "masscan"
        ]
        
        user_agent_lower = user_agent.lower()
        return any(agent in user_agent_lower for agent in suspicious_agents)


class RateLimitMiddleware(BaseHTTPMiddleware):
    """速率限制中间件"""
    
    def __init__(self, app: ASGIApp):
        super().__init__(app)
        self.request_counts: Dict[str, Dict[str, Any]] = {}
        self.max_requests = getattr(settings, 'RATE_LIMIT_PER_MINUTE', 60)
        self.window_size = 60  # 60秒窗口
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """速率限制检查"""
        
        # 获取客户端标识
        client_id = self._get_client_id(request)
        
        # 检查速率限制
        if await self._is_rate_limited(client_id, request):
            security_logger.log_security_violation(
                violation_type="rate_limit_exceeded",
                details=f"速率限制超出: {client_id}",
                ip_address=self._get_client_ip(request)
            )
            
            return JSONResponse(
                status_code=429,
                content={
                    "error": "Rate limit exceeded",
                    "message": "请求频率过高，请稍后重试"
                },
                headers={"Retry-After": "60"}
            )
        
        # 记录请求
        await self._record_request(client_id)
        
        return await call_next(request)
    
    def _get_client_id(self, request: Request) -> str:
        """获取客户端标识"""
        # 优先使用用户ID（如果已认证）
        user_id = getattr(request.state, 'user_id', None)
        if user_id:
            return f"user:{user_id}"
        
        # 使用IP地址
        client_ip = self._get_client_ip(request)
        return f"ip:{client_ip}"
    
    def _get_client_ip(self, request: Request) -> str:
        """获取客户端IP"""
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            return forwarded_for.split(",")[0].strip()
        
        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip
        
        if hasattr(request, "client") and request.client:
            return request.client.host
        
        return "unknown"
    
    async def _is_rate_limited(self, client_id: str, request: Request) -> bool:
        """检查是否超出速率限制"""
        now = time.time()
        
        # 清理过期记录
        if client_id in self.request_counts:
            client_data = self.request_counts[client_id]
            client_data['requests'] = [
                req_time for req_time in client_data['requests']
                if now - req_time < self.window_size
            ]
        
        # 检查当前请求数
        if client_id not in self.request_counts:
            return False
        
        client_requests = self.request_counts[client_id]['requests']
        
        # 对管理员接口使用更严格的限制
        if request.url.path.startswith('/api/v1/admin'):
            admin_limit = max(10, self.max_requests // 6)  # 管理接口限制更严格
            return len(client_requests) >= admin_limit
        
        return len(client_requests) >= self.max_requests
    
    async def _record_request(self, client_id: str):
        """记录请求"""
        now = time.time()
        
        if client_id not in self.request_counts:
            self.request_counts[client_id] = {
                'requests': [],
                'first_request': now
            }
        
        self.request_counts[client_id]['requests'].append(now)
        
        # 定期清理旧数据
        if len(self.request_counts) > 10000:  # 防止内存泄漏
            await self._cleanup_old_records()
    
    async def _cleanup_old_records(self):
        """清理旧的请求记录"""
        now = time.time()
        clients_to_remove = []
        
        for client_id, data in self.request_counts.items():
            # 移除1小时前的记录
            if now - data['first_request'] > 3600:
                clients_to_remove.append(client_id)
        
        for client_id in clients_to_remove:
            del self.request_counts[client_id]
        
        logger.info(f"清理了 {len(clients_to_remove)} 个过期的速率限制记录")


class CacheMiddleware(BaseHTTPMiddleware):
    """缓存中间件"""
    
    def __init__(self, app: ASGIApp):
        super().__init__(app)
        self.cacheable_paths = [
            "/api/v1/health",
            "/api/v1/analytics",
        ]
        self.cache_ttl = 60  # 缓存60秒
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """缓存处理"""
        
        # 只对GET请求进行缓存
        if request.method != "GET":
            return await call_next(request)
        
        # 检查是否为可缓存路径
        path = request.url.path
        if not any(path.startswith(cacheable_path) for cacheable_path in self.cacheable_paths):
            return await call_next(request)
        
        # 生成缓存键
        cache_key = self._generate_cache_key(request)
        
        # 尝试从缓存获取
        try:
            from src.services.cache_service import CacheService
            cache_service = CacheService()
            
            cached_response = await cache_service.get(cache_key, namespace="http_cache")
            if cached_response:
                logger.debug(f"缓存命中: {cache_key}")
                return JSONResponse(
                    content=cached_response['content'],
                    status_code=cached_response['status_code'],
                    headers={
                        **cached_response['headers'],
                        "X-Cache": "HIT"
                    }
                )
        
        except Exception as e:
            logger.warning(f"缓存获取失败: {str(e)}")
        
        # 执行请求
        response = await call_next(request)
        
        # 缓存响应（只缓存成功响应）
        if response.status_code == 200:
            try:
                response_body = b""
                async for chunk in response.body_iterator:
                    response_body += chunk
                
                # 重建响应
                from fastapi.responses import Response as FastAPIResponse
                new_response = FastAPIResponse(
                    content=response_body,
                    status_code=response.status_code,
                    headers=dict(response.headers),
                    media_type=response.media_type
                )
                
                # 缓存响应数据
                cache_data = {
                    'content': json.loads(response_body.decode()),
                    'status_code': response.status_code,
                    'headers': {k: v for k, v in response.headers.items() if k.lower() not in ['content-length', 'date']},
                }
                
                await cache_service.set(cache_key, cache_data, ttl=self.cache_ttl, namespace="http_cache")
                new_response.headers["X-Cache"] = "MISS"
                
                return new_response
                
            except Exception as e:
                logger.warning(f"缓存存储失败: {str(e)}")
        
        response.headers["X-Cache"] = "BYPASS"
        return response
    
    def _generate_cache_key(self, request: Request) -> str:
        """生成缓存键"""
        path = request.url.path
        query_params = str(request.query_params)
        user_id = getattr(request.state, 'user_id', 'anonymous')
        
        return f"{path}:{query_params}:{user_id}"


class CompressionMiddleware(BaseHTTPMiddleware):
    """压缩中间件"""
    
    def __init__(self, app: ASGIApp):
        super().__init__(app)
        self.min_size = 1024  # 最小压缩大小
        self.compression_level = 6  # 压缩级别
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """响应压缩处理"""
        
        # 检查客户端是否支持压缩
        accept_encoding = request.headers.get("accept-encoding", "").lower()
        supports_gzip = "gzip" in accept_encoding
        
        if not supports_gzip:
            return await call_next(request)
        
        response = await call_next(request)
        
        # 检查响应是否适合压缩
        content_type = response.headers.get("content-type", "").lower()
        if not self._should_compress(content_type):
            return response
        
        # 获取响应内容
        try:
            response_body = b""
            async for chunk in response.body_iterator:
                response_body += chunk
            
            # 检查内容大小
            if len(response_body) < self.min_size:
                from fastapi.responses import Response as FastAPIResponse
                return FastAPIResponse(
                    content=response_body,
                    status_code=response.status_code,
                    headers=dict(response.headers),
                    media_type=response.media_type
                )
            
            # 压缩内容
            import gzip
            compressed_content = gzip.compress(response_body, compresslevel=self.compression_level)
            
            # 创建压缩响应
            from fastapi.responses import Response as FastAPIResponse
            compressed_response = FastAPIResponse(
                content=compressed_content,
                status_code=response.status_code,
                headers=dict(response.headers),
                media_type=response.media_type
            )
            
            # 设置压缩头
            compressed_response.headers["content-encoding"] = "gzip"
            compressed_response.headers["content-length"] = str(len(compressed_content))
            
            logger.debug(f"响应压缩: {len(response_body)} -> {len(compressed_content)} bytes")
            
            return compressed_response
            
        except Exception as e:
            logger.warning(f"响应压缩失败: {str(e)}")
            return response
    
    def _should_compress(self, content_type: str) -> bool:
        """判断内容类型是否应该压缩"""
        compressible_types = [
            "application/json",
            "application/xml",
            "text/html",
            "text/css",
            "text/javascript",
            "text/plain"
        ]
        
        return any(comp_type in content_type for comp_type in compressible_types)