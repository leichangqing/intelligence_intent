"""
FastAPI依赖注入
"""
from typing import Generator, Optional
from fastapi import Depends, HTTPException, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import jwt
from datetime import datetime, timedelta

from src.config.settings import settings
from src.config.database import get_database
from src.services.cache_service import CacheService, get_cache_service
from src.services.intent_service import IntentService
from src.services.slot_service import SlotService
from src.services.conversation_service import ConversationService
from src.services.function_service import FunctionService
from src.services.ragflow_service import RagflowService
from src.services.user_profile_service import UserProfileService, get_user_profile_service
from src.core.nlu_engine import NLUEngine
from src.utils.logger import get_logger

logger = get_logger(__name__)

# JWT认证配置
security = HTTPBearer(auto_error=False)


# ============ 数据库依赖 ============

async def get_db() -> Generator:
    """获取数据库连接依赖"""
    async for db in get_database():
        yield db


# ============ 缓存服务依赖 ============

_cache_service: Optional[CacheService] = None

async def get_cache_service_dependency() -> CacheService:
    """获取缓存服务依赖"""
    global _cache_service
    
    if _cache_service is None:
        _cache_service = CacheService()
        await _cache_service.initialize()
    
    return _cache_service


# ============ NLU引擎依赖 ============

_nlu_engine: Optional[NLUEngine] = None

async def get_nlu_engine() -> NLUEngine:
    """获取NLU引擎依赖"""
    global _nlu_engine
    
    if _nlu_engine is None:
        _nlu_engine = NLUEngine()
        await _nlu_engine.initialize()
    
    return _nlu_engine


# ============ 业务服务依赖 ============

async def get_intent_service(
    cache_service: CacheService = Depends(get_cache_service_dependency),
    nlu_engine: NLUEngine = Depends(get_nlu_engine)
) -> IntentService:
    """获取意图识别服务依赖"""
    return IntentService(cache_service, nlu_engine)


async def get_slot_service(
    cache_service: CacheService = Depends(get_cache_service_dependency),
    nlu_engine: NLUEngine = Depends(get_nlu_engine)
) -> SlotService:
    """获取槽位管理服务依赖"""
    return SlotService(cache_service, nlu_engine)


async def get_ragflow_service(
    cache_service: CacheService = Depends(get_cache_service_dependency)
) -> RagflowService:
    """获取RAGFLOW服务依赖"""
    return RagflowService(cache_service)


async def get_conversation_service(
    cache_service: CacheService = Depends(get_cache_service_dependency),
    ragflow_service: RagflowService = Depends(get_ragflow_service)
) -> ConversationService:
    """获取对话管理服务依赖"""
    return ConversationService(cache_service, ragflow_service)


async def get_function_service(
    cache_service: CacheService = Depends(get_cache_service_dependency)
) -> FunctionService:
    """获取功能调用服务依赖"""
    return FunctionService(cache_service)


async def get_user_profile_service_dependency(
    cache_service: CacheService = Depends(get_cache_service_dependency)
) -> UserProfileService:
    """获取用户档案服务依赖"""
    return await get_user_profile_service(cache_service)


# ============ 认证和权限依赖 ============

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """创建访问令牌"""
    to_encode = data.copy()
    
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt


def verify_token(token: str) -> dict:
    """验证JWT令牌"""
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token已过期",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except jwt.JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token无效",
            headers={"WWW-Authenticate": "Bearer"},
        )


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)
) -> Optional[dict]:
    """获取当前用户信息（可选认证）"""
    if not credentials:
        return None
    
    try:
        payload = verify_token(credentials.credentials)
        return payload
    except HTTPException:
        # 可选认证，认证失败返回None而不是抛出异常
        return None


async def require_auth(
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> dict:
    """强制要求认证"""
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="需要认证",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    return verify_token(credentials.credentials)


async def require_admin_auth(
    current_user: dict = Depends(require_auth)
) -> dict:
    """要求管理员权限"""
    if not current_user.get("is_admin", False):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="需要管理员权限"
        )
    
    return current_user


# ============ 请求上下文依赖 ============

async def get_request_id(request: Request) -> str:
    """获取请求ID"""
    request_id = request.headers.get("X-Request-ID")
    if not request_id:
        import uuid
        request_id = f"req_{uuid.uuid4().hex[:8]}"
    
    return request_id


async def get_user_ip(request: Request) -> str:
    """获取用户IP地址"""
    # 检查代理头
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    
    real_ip = request.headers.get("X-Real-IP")
    if real_ip:
        return real_ip
    
    # 返回客户端IP
    if hasattr(request, "client") and request.client:
        return request.client.host
    
    return "unknown"


async def get_user_agent(request: Request) -> str:
    """获取用户代理"""
    return request.headers.get("User-Agent", "unknown")


# ============ 速率限制依赖 ============

class RateLimiter:
    """速率限制器"""
    
    def __init__(self, max_requests: int = 100, window_seconds: int = 60):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
    
    async def check_rate_limit(
        self, 
        key: str, 
        cache_service: CacheService = Depends(get_cache_service_dependency)
    ) -> bool:
        """检查速率限制"""
        from datetime import datetime
        import json
        
        now = datetime.now()
        window_start = now.timestamp() - self.window_seconds
        
        # 获取当前窗口的请求记录
        cache_key = f"rate_limit:{key}"
        requests = await cache_service.get(cache_key) or []
        
        if isinstance(requests, str):
            try:
                requests = json.loads(requests)
            except:
                requests = []
        
        # 清理过期的请求记录
        requests = [req_time for req_time in requests if req_time > window_start]
        
        # 检查是否超出限制
        if len(requests) >= self.max_requests:
            return False
        
        # 添加当前请求
        requests.append(now.timestamp())
        
        # 更新缓存
        await cache_service.set(cache_key, requests, ttl=self.window_seconds)
        
        return True


# 创建全局速率限制器实例
api_rate_limiter = RateLimiter(max_requests=settings.MAX_CONCURRENT_REQUESTS, window_seconds=60)
user_rate_limiter = RateLimiter(max_requests=100, window_seconds=60)


async def check_api_rate_limit(
    request: Request,
    user_ip: str = Depends(get_user_ip)
) -> bool:
    """检查API速率限制"""
    rate_limit_key = f"api:{user_ip}"
    
    if not await api_rate_limiter.check_rate_limit(rate_limit_key):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="请求频率过高，请稍后重试"
        )
    
    return True


async def check_user_rate_limit(
    user_id: str,
    cache_service: CacheService = Depends(get_cache_service_dependency)
) -> bool:
    """检查用户速率限制"""
    rate_limit_key = f"user:{user_id}"
    
    if not await user_rate_limiter.check_rate_limit(rate_limit_key, cache_service):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="用户请求频率过高，请稍后重试"
        )
    
    return True


# ============ 健康检查依赖 ============

async def check_system_health() -> dict:
    """检查系统健康状态"""
    health_status = {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "services": {}
    }
    
    try:
        # 检查数据库连接
        from src.config.database import database
        if not database.is_closed():
            health_status["services"]["database"] = "healthy"
        else:
            health_status["services"]["database"] = "unhealthy"
            health_status["status"] = "unhealthy"
    except Exception as e:
        health_status["services"]["database"] = f"error: {str(e)}"
        health_status["status"] = "unhealthy"
    
    try:
        # 检查Redis连接
        cache_service = await get_cache_service_dependency()
        await cache_service.redis_client.ping()
        health_status["services"]["redis"] = "healthy"
    except Exception as e:
        health_status["services"]["redis"] = f"error: {str(e)}"
        health_status["status"] = "unhealthy"
    
    try:
        # 检查NLU引擎
        nlu_engine = await get_nlu_engine()
        if nlu_engine._initialized:
            health_status["services"]["nlu_engine"] = "healthy"
        else:
            health_status["services"]["nlu_engine"] = "not_initialized"
            health_status["status"] = "degraded"
    except Exception as e:
        health_status["services"]["nlu_engine"] = f"error: {str(e)}"
        health_status["status"] = "unhealthy"
    
    return health_status


# ============ 监控和指标依赖 ============

async def get_system_metrics() -> dict:
    """获取系统指标"""
    import psutil
    import time
    
    return {
        "cpu_percent": psutil.cpu_percent(interval=1),
        "memory_percent": psutil.virtual_memory().percent,
        "disk_percent": psutil.disk_usage('/').percent,
        "network_io": psutil.net_io_counters()._asdict(),
        "timestamp": time.time()
    }