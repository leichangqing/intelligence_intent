"""
安全依赖注入 (TASK-037)
集成API密钥认证、威胁检测、输入净化等安全机制
"""
from typing import Optional, List, Any
from fastapi import Request, HTTPException, Depends, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from ..services.cache_service import get_cache_service_dependency, CacheService
from .api_key_manager import get_api_key_manager, ApiKeyManager, ApiKeyScope
from .threat_detector import get_threat_detector, ThreatDetector
from .input_sanitizer import global_input_sanitizer, SanitizationResult
from ..utils.logger import get_logger

logger = get_logger(__name__)

# 安全认证方案
security = HTTPBearer(auto_error=False)
api_key_security = HTTPBearer(auto_error=False, scheme_name="ApiKey")


async def get_api_key_manager_dependency(
    cache_service: CacheService = Depends(get_cache_service_dependency)
) -> ApiKeyManager:
    """获取API密钥管理器依赖"""
    return await get_api_key_manager(cache_service)


async def get_threat_detector_dependency(
    cache_service: CacheService = Depends(get_cache_service_dependency)
) -> ThreatDetector:
    """获取威胁检测器依赖"""
    return await get_threat_detector(cache_service)


async def get_client_info(request: Request) -> dict:
    """获取客户端信息"""
    # 获取真实IP地址
    client_ip = "unknown"
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        client_ip = forwarded_for.split(",")[0].strip()
    elif request.headers.get("X-Real-IP"):
        client_ip = request.headers.get("X-Real-IP")
    elif hasattr(request, "client") and request.client:
        client_ip = request.client.host
    
    # 获取User-Agent
    user_agent = request.headers.get("User-Agent", "unknown")
    
    # 获取其他请求信息
    endpoint = request.url.path
    method = request.method
    
    return {
        "ip_address": client_ip,
        "user_agent": user_agent,
        "endpoint": endpoint,
        "method": method,
        "headers": dict(request.headers)
    }


async def verify_api_key(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(api_key_security),
    api_key_manager: ApiKeyManager = Depends(get_api_key_manager_dependency),
    required_scopes: Optional[List[ApiKeyScope]] = None
) -> Optional[dict]:
    """验证API密钥（可选）"""
    if not credentials:
        return None
    
    try:
        # 解析API密钥
        auth_header = credentials.credentials
        if ":" not in auth_header:
            logger.warning("无效的API密钥格式")
            return None
        
        public_key, secret_key = auth_header.split(":", 1)
        
        # 获取客户端信息
        client_info = await get_client_info(request)
        
        # 验证API密钥
        api_key_info = await api_key_manager.verify_api_key(
            public_key=public_key,
            secret_key=secret_key,
            ip_address=client_info["ip_address"],
            required_scopes=required_scopes
        )
        
        if api_key_info:
            # 记录API使用情况
            await api_key_manager.record_api_usage(
                key_id=api_key_info.key_id,
                ip_address=client_info["ip_address"],
                user_agent=client_info["user_agent"],
                endpoint=client_info["endpoint"],
                method=client_info["method"],
                success=True,
                response_code=200,
                response_time_ms=0,  # 会在中间件中更新
                request_size=0,
                response_size=0
            )
            
            return {
                "api_key_id": api_key_info.key_id,
                "client_id": api_key_info.client_id,
                "scopes": [scope.value for scope in api_key_info.scopes],
                "rate_limit": api_key_info.rate_limit_per_hour
            }
        
        return None
        
    except Exception as e:
        logger.error(f"API密钥验证失败: {str(e)}")
        return None


async def require_api_key(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(api_key_security),
    api_key_manager: ApiKeyManager = Depends(get_api_key_manager_dependency),
    required_scopes: Optional[List[ApiKeyScope]] = None
) -> dict:
    """强制要求API密钥认证"""
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="需要API密钥认证",
            headers={"WWW-Authenticate": "ApiKey"}
        )
    
    api_key_info = await verify_api_key(request, credentials, api_key_manager, required_scopes)
    
    if not api_key_info:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="无效的API密钥",
            headers={"WWW-Authenticate": "ApiKey"}
        )
    
    return api_key_info


def require_api_key_scopes(scopes: List[ApiKeyScope]):
    """要求特定API密钥权限"""
    async def check_scopes(
        api_key_info: dict = Depends(lambda req, creds, mgr: require_api_key(req, creds, mgr, scopes))
    ) -> dict:
        return api_key_info
    
    return check_scopes


async def security_middleware_dependency(
    request: Request,
    threat_detector: ThreatDetector = Depends(get_threat_detector_dependency)
) -> dict:
    """安全中间件依赖"""
    try:
        # 获取客户端信息
        client_info = await get_client_info(request)
        
        # 威胁检测
        threats = await threat_detector.analyze_request(
            ip_address=client_info["ip_address"],
            user_agent=client_info["user_agent"],
            endpoint=client_info["endpoint"],
            method=client_info["method"]
        )
        
        # 检查IP信誉
        ip_reputation = await threat_detector.check_ip_reputation(client_info["ip_address"])
        
        # 如果检测到严重威胁，拒绝请求
        critical_threats = [t for t in threats if t.severity.value == "critical"]
        if critical_threats:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="检测到安全威胁，请求被拒绝"
            )
        
        # 如果IP信誉为恶意，拒绝请求
        if ip_reputation.get("reputation") == "malicious":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="IP地址已被列入黑名单"
            )
        
        return {
            "client_info": client_info,
            "threats_detected": len(threats),
            "ip_reputation": ip_reputation,
            "security_score": 100 - sum(t.risk_score for t in threats)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"安全中间件处理失败: {str(e)}")
        return {
            "client_info": await get_client_info(request),
            "threats_detected": 0,
            "ip_reputation": {"reputation": "unknown"},
            "security_score": 50
        }


async def sanitize_request_data(
    request: Request,
    max_body_size: int = 1024 * 1024  # 1MB
) -> dict:
    """净化请求数据"""
    try:
        sanitized_data = {}
        
        # 检查请求体大小
        content_length = request.headers.get("content-length")
        if content_length and int(content_length) > max_body_size:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"请求体过大，最大允许 {max_body_size} 字节"
            )
        
        # 净化查询参数
        sanitized_query_params = {}
        for key, value in request.query_params.items():
            result = global_input_sanitizer.sanitize_input(
                value=value,
                input_type="text",
                allow_html=False
            )
            
            if not result.is_safe:
                logger.warning(f"查询参数包含安全威胁: {key} - {result.threats_detected}")
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"查询参数 '{key}' 包含不安全内容"
                )
            
            sanitized_query_params[key] = result.sanitized_value
        
        sanitized_data["query_params"] = sanitized_query_params
        
        # 净化路径参数
        sanitized_path_params = {}
        for key, value in request.path_params.items():
            result = global_input_sanitizer.sanitize_input(
                value=str(value),
                input_type="text",
                allow_html=False
            )
            
            if not result.is_safe:
                logger.warning(f"路径参数包含安全威胁: {key} - {result.threats_detected}")
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"路径参数 '{key}' 包含不安全内容"
                )
            
            sanitized_path_params[key] = result.sanitized_value
        
        sanitized_data["path_params"] = sanitized_path_params
        
        # 净化请求头
        sanitized_headers = {}
        security_headers = ["user-agent", "referer", "origin", "x-forwarded-for"]
        
        for header_name in security_headers:
            header_value = request.headers.get(header_name)
            if header_value:
                result = global_input_sanitizer.sanitize_input(
                    value=header_value,
                    input_type="text",
                    allow_html=False
                )
                
                if not result.is_safe:
                    logger.warning(f"请求头包含安全威胁: {header_name} - {result.threats_detected}")
                    # 对于请求头，我们记录但不阻止请求
                
                sanitized_headers[header_name] = result.sanitized_value
        
        sanitized_data["headers"] = sanitized_headers
        
        return sanitized_data
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"请求数据净化失败: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="请求处理异常"
        )


def sanitize_json_body(allow_html: bool = False, max_depth: int = 10):
    """净化JSON请求体的依赖工厂"""
    async def _sanitize_json_body(request: Request) -> dict:
        try:
            # 读取请求体
            body = await request.body()
            if not body:
                return {}
            
            body_str = body.decode('utf-8')
            
            # 验证JSON格式和深度
            is_valid, parsed_json = global_input_sanitizer.validate_json(body_str, max_depth)
            if not is_valid:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="无效的JSON格式或嵌套过深"
                )
            
            # 递归净化JSON数据
            def sanitize_json_recursive(obj: Any) -> Any:
                if isinstance(obj, dict):
                    sanitized = {}
                    for key, value in obj.items():
                        # 净化键
                        key_result = global_input_sanitizer.sanitize_input(
                            str(key), "text", allow_html=False
                        )
                        if not key_result.is_safe:
                            logger.warning(f"JSON键包含威胁: {key}")
                            continue
                        
                        # 递归净化值
                        sanitized_value = sanitize_json_recursive(value)
                        sanitized[key_result.sanitized_value] = sanitized_value
                    
                    return sanitized
                
                elif isinstance(obj, list):
                    return [sanitize_json_recursive(item) for item in obj]
                
                elif isinstance(obj, str):
                    result = global_input_sanitizer.sanitize_input(
                        obj, "text", allow_html=allow_html
                    )
                    if not result.is_safe:
                        logger.warning(f"JSON字符串包含威胁: {result.threats_detected}")
                        return result.sanitized_value  # 返回净化后的值而不是拒绝
                    return result.sanitized_value
                
                else:
                    return obj  # 数字、布尔值等直接返回
            
            sanitized_json = sanitize_json_recursive(parsed_json)
            return sanitized_json
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"JSON净化失败: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="JSON数据处理失败"
            )
    
    return _sanitize_json_body


async def check_rate_limit(
    request: Request,
    max_requests: int = 100,
    window_minutes: int = 60,
    threat_detector: ThreatDetector = Depends(get_threat_detector_dependency)
) -> bool:
    """检查速率限制"""
    try:
        client_info = await get_client_info(request)
        
        # 使用威胁检测器检查速率限制
        # 这里可以添加更复杂的逻辑
        
        return True  # 暂时允许所有请求通过
        
    except Exception as e:
        logger.error(f"速率限制检查失败: {str(e)}")
        return True  # 出错时允许请求通过


def require_security_headers():
    """要求特定安全头的依赖"""
    async def _check_security_headers(request: Request) -> dict:
        required_headers = {
            "X-API-Version": "API版本头缺失",
            "X-Client-ID": "客户端ID头缺失"
        }
        
        missing_headers = []
        for header, error_msg in required_headers.items():
            if header not in request.headers:
                missing_headers.append(error_msg)
        
        if missing_headers:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"缺少必需的安全头: {', '.join(missing_headers)}"
            )
        
        return {
            "api_version": request.headers.get("X-API-Version"),
            "client_id": request.headers.get("X-Client-ID")
        }
    
    return _check_security_headers


class SecurityLevel:
    """安全级别"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


def require_security_level(level: str):
    """要求特定安全级别的依赖工厂"""
    async def _check_security_level(
        request: Request,
        security_info: dict = Depends(security_middleware_dependency),
        api_key_info: Optional[dict] = Depends(verify_api_key)
    ) -> dict:
        
        current_security_score = security_info.get("security_score", 0)
        
        # 根据安全级别设置最低分数要求
        min_scores = {
            SecurityLevel.LOW: 30,
            SecurityLevel.MEDIUM: 50,
            SecurityLevel.HIGH: 70,
            SecurityLevel.CRITICAL: 90
        }
        
        min_score = min_scores.get(level, 50)
        
        if current_security_score < min_score:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"安全级别不足，当前分数: {current_security_score}, 需要: {min_score}"
            )
        
        # 对于高安全级别，要求API密钥认证
        if level in [SecurityLevel.HIGH, SecurityLevel.CRITICAL] and not api_key_info:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"安全级别 '{level}' 需要API密钥认证"
            )
        
        return {
            "security_level": level,
            "security_score": current_security_score,
            "api_authenticated": bool(api_key_info)
        }
    
    return _check_security_level


# 预定义的安全级别依赖
require_low_security = require_security_level(SecurityLevel.LOW)
require_medium_security = require_security_level(SecurityLevel.MEDIUM)
require_high_security = require_security_level(SecurityLevel.HIGH)
require_critical_security = require_security_level(SecurityLevel.CRITICAL)

# 预定义的API密钥范围依赖
require_read_access = require_api_key_scopes([ApiKeyScope.READ_ONLY, ApiKeyScope.READ_WRITE])
require_write_access = require_api_key_scopes([ApiKeyScope.WRITE_ONLY, ApiKeyScope.READ_WRITE])
require_admin_access = require_api_key_scopes([ApiKeyScope.ADMIN])
require_analytics_access = require_api_key_scopes([ApiKeyScope.ANALYTICS])
require_intent_management = require_api_key_scopes([ApiKeyScope.INTENT_MANAGEMENT])
require_user_management = require_api_key_scopes([ApiKeyScope.USER_MANAGEMENT])