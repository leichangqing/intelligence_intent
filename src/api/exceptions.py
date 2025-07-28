"""
FastAPI异常处理器
"""
from fastapi import FastAPI, Request, HTTPException, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from pydantic import ValidationError
import traceback
from datetime import datetime

from src.utils.logger import get_logger, security_logger
from src.schemas.common import StandardResponse

logger = get_logger(__name__)


def setup_exception_handlers(app: FastAPI):
    """设置全局异常处理器"""
    
    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException):
        """HTTP异常处理器"""
        
        # 记录异常日志
        logger.warning(f"HTTP异常: {exc.status_code} - {exc.detail} - {request.url}")
        
        # 安全相关的异常需要特殊记录
        if exc.status_code in [401, 403, 429]:
            security_logger.log_security_violation(
                violation_type=f"http_{exc.status_code}",
                details=str(exc.detail),
                ip_address=_get_client_ip(request)
            )
        
        return JSONResponse(
            status_code=exc.status_code,
            content=StandardResponse(
                code=exc.status_code,
                message=str(exc.detail),
                success=False,
                timestamp=datetime.utcnow(),
                request_id=_get_request_id(request)
            ).model_dump(mode='json')
        )
    
    @app.exception_handler(StarletteHTTPException)
    async def starlette_exception_handler(request: Request, exc: StarletteHTTPException):
        """Starlette HTTP异常处理器"""
        
        logger.warning(f"Starlette异常: {exc.status_code} - {exc.detail} - {request.url}")
        
        return JSONResponse(
            status_code=exc.status_code,
            content=StandardResponse(
                code=exc.status_code,
                message=str(exc.detail),
                success=False,
                timestamp=datetime.utcnow(),
                request_id=_get_request_id(request)
            ).model_dump(mode='json')
        )
    
    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        """请求验证异常处理器"""
        
        # 格式化验证错误信息
        error_details = []
        for error in exc.errors():
            field = " -> ".join(str(loc) for loc in error["loc"])
            message = error["msg"]
            error_details.append(f"{field}: {message}")
        
        error_message = "请求参数验证失败: " + "; ".join(error_details)
        
        logger.warning(f"参数验证失败: {error_message} - {request.url}")
        
        response_obj = StandardResponse(
            code=422,
            message="请求参数验证失败",
            success=False,
            data={
                "validation_errors": error_details,
                "details": error_message
            },
            timestamp=datetime.utcnow(),
            request_id=_get_request_id(request)
        )
        
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content=response_obj.model_dump(mode='json')  # 使用model_dump而不是dict()
        )
    
    @app.exception_handler(ValidationError)
    async def pydantic_validation_exception_handler(request: Request, exc: ValidationError):
        """Pydantic验证异常处理器"""
        
        error_details = []
        for error in exc.errors():
            field = " -> ".join(str(loc) for loc in error["loc"])
            message = error["msg"]
            error_details.append(f"{field}: {message}")
        
        error_message = "数据验证失败: " + "; ".join(error_details)
        
        logger.warning(f"Pydantic验证失败: {error_message} - {request.url}")
        
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content=StandardResponse(
                code=422,
                message="数据验证失败",
                success=False,
                data={
                    "validation_errors": error_details,
                    "details": error_message
                },
                timestamp=datetime.utcnow(),
                request_id=_get_request_id(request)
            ).model_dump(mode='json')
        )
    
    @app.exception_handler(ValueError)
    async def value_error_handler(request: Request, exc: ValueError):
        """值错误异常处理器"""
        
        logger.warning(f"值错误: {str(exc)} - {request.url}")
        
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content=StandardResponse(
                code=400,
                message="请求参数值错误",
                success=False,
                data={
                    "error_type": "ValueError",
                    "details": str(exc)
                },
                timestamp=datetime.utcnow(),
                request_id=_get_request_id(request)
            ).model_dump(mode='json')
        )
    
    @app.exception_handler(KeyError)
    async def key_error_handler(request: Request, exc: KeyError):
        """键错误异常处理器"""
        
        logger.warning(f"键错误: {str(exc)} - {request.url}")
        
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content=StandardResponse(
                code=400,
                message="缺少必需的参数或字段",
                success=False,
                data={
                    "error_type": "KeyError",
                    "missing_key": str(exc),
                    "details": f"缺少必需字段: {str(exc)}"
                },
                timestamp=datetime.utcnow(),
                request_id=_get_request_id(request)
            ).model_dump(mode='json')
        )
    
    @app.exception_handler(PermissionError)
    async def permission_error_handler(request: Request, exc: PermissionError):
        """权限错误异常处理器"""
        
        logger.warning(f"权限错误: {str(exc)} - {request.url}")
        
        # 记录安全审计日志
        security_logger.log_permission_denied(
            resource=str(request.url.path),
            action=request.method,
            user_id=getattr(request.state, 'user_id', 'unknown')
        )
        
        return JSONResponse(
            status_code=status.HTTP_403_FORBIDDEN,
            content=StandardResponse(
                code=403,
                message="权限不足",
                success=False,
                data={
                    "error_type": "PermissionError",
                    "details": "您没有执行此操作的权限"
                },
                timestamp=datetime.utcnow(),
                request_id=_get_request_id(request)
            ).model_dump(mode='json')
        )
    
    @app.exception_handler(TimeoutError)
    async def timeout_error_handler(request: Request, exc: TimeoutError):
        """超时错误异常处理器"""
        
        logger.error(f"请求超时: {str(exc)} - {request.url}")
        
        return JSONResponse(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            content=StandardResponse(
                code=504,
                message="请求处理超时",
                success=False,
                data={
                    "error_type": "TimeoutError",
                    "details": "请求处理时间过长，请稍后重试"
                },
                timestamp=datetime.utcnow(),
                request_id=_get_request_id(request)
            ).model_dump(mode='json')
        )
    
    @app.exception_handler(ConnectionError)
    async def connection_error_handler(request: Request, exc: ConnectionError):
        """连接错误异常处理器"""
        
        logger.error(f"连接错误: {str(exc)} - {request.url}")
        
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content=StandardResponse(
                code=503,
                message="服务暂时不可用",
                success=False,
                data={
                    "error_type": "ConnectionError",
                    "details": "外部服务连接失败，请稍后重试"
                },
                timestamp=datetime.utcnow(),
                request_id=_get_request_id(request)
            ).model_dump(mode='json')
        )
    
    @app.exception_handler(Exception)
    async def general_exception_handler(request: Request, exc: Exception):
        """通用异常处理器"""
        
        # 获取异常详细信息
        error_traceback = traceback.format_exc()
        error_type = type(exc).__name__
        error_message = str(exc)
        
        # 记录详细错误日志
        logger.error(f"未处理异常: {error_type} - {error_message}")
        logger.error(f"异常堆栈: {error_traceback}")
        logger.error(f"请求URL: {request.url}")
        logger.error(f"请求方法: {request.method}")
        
        # 记录安全审计（如果可能是攻击）
        if _is_potential_attack(exc, request):
            security_logger.log_security_violation(
                violation_type="potential_attack",
                details=f"可能的攻击尝试: {error_type} - {error_message}",
                ip_address=_get_client_ip(request)
            )
        
        # 返回通用错误响应（不暴露内部错误详情）
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=StandardResponse(
                code=500,
                message="服务器内部错误",
                success=False,
                data={
                    "error_type": error_type,
                    "details": "服务器处理请求时发生错误，请稍后重试",
                    "support_info": "如果问题持续存在，请联系技术支持"
                },
                timestamp=datetime.utcnow(),
                request_id=_get_request_id(request)
            ).model_dump(mode='json')
        )


# 自定义异常类
class BusinessLogicError(Exception):
    """业务逻辑错误"""
    
    def __init__(self, message: str, code: int = 400, details: dict = None):
        self.message = message
        self.code = code
        self.details = details or {}
        super().__init__(self.message)


class ConfigurationError(Exception):
    """配置错误"""
    
    def __init__(self, message: str, config_key: str = None):
        self.message = message
        self.config_key = config_key
        super().__init__(self.message)


class IntentRecognitionError(Exception):
    """意图识别错误"""
    
    def __init__(self, message: str, user_input: str = None, confidence: float = 0.0):
        self.message = message
        self.user_input = user_input
        self.confidence = confidence
        super().__init__(self.message)


class SlotExtractionError(Exception):
    """槽位提取错误"""
    
    def __init__(self, message: str, slot_name: str = None, slot_value: str = None):
        self.message = message
        self.slot_name = slot_name
        self.slot_value = slot_value
        super().__init__(self.message)


class ExternalServiceError(Exception):
    """外部服务错误"""
    
    def __init__(self, message: str, service_name: str = None, status_code: int = None):
        self.message = message
        self.service_name = service_name
        self.status_code = status_code
        super().__init__(self.message)


# 工具函数
def _get_client_ip(request: Request) -> str:
    """获取客户端IP地址"""
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    
    real_ip = request.headers.get("X-Real-IP")
    if real_ip:
        return real_ip
    
    if hasattr(request, "client") and request.client:
        return request.client.host
    
    return "unknown"


def _get_request_id(request: Request) -> str:
    """获取请求ID"""
    return request.headers.get("X-Request-ID", f"req_{int(datetime.utcnow().timestamp() * 1000)}")


def _is_potential_attack(exc: Exception, request: Request) -> bool:
    """判断异常是否可能是攻击尝试"""
    
    # 检查异常类型
    attack_exception_types = [
        "SyntaxError",           # 可能的代码注入
        "NameError",            # 可能的代码注入
        "ImportError",          # 可能的模块注入
        "AttributeError",       # 可能的属性访问攻击
    ]
    
    if type(exc).__name__ in attack_exception_types:
        return True
    
    # 检查异常消息中的可疑内容
    error_message = str(exc).lower()
    suspicious_patterns = [
        "eval",
        "exec",
        "import",
        "__",
        "subprocess",
        "os.system",
        "shell",
        "script",
        "union select",
        "drop table",
        "insert into",
        "delete from"
    ]
    
    if any(pattern in error_message for pattern in suspicious_patterns):
        return True
    
    # 检查请求路径和参数
    url_str = str(request.url).lower()
    if any(pattern in url_str for pattern in suspicious_patterns):
        return True
    
    return False


# 自定义异常处理器注册函数
def register_custom_exception_handlers(app: FastAPI):
    """注册自定义异常处理器"""
    
    @app.exception_handler(BusinessLogicError)
    async def business_logic_error_handler(request: Request, exc: BusinessLogicError):
        """业务逻辑错误处理器"""
        
        logger.warning(f"业务逻辑错误: {exc.message} - {request.url}")
        
        return JSONResponse(
            status_code=exc.code,
            content=StandardResponse(
                code=exc.code,
                message=exc.message,
                success=False,
                data=exc.details,
                timestamp=datetime.utcnow(),
                request_id=_get_request_id(request)
            ).model_dump(mode='json')
        )
    
    @app.exception_handler(ConfigurationError)
    async def configuration_error_handler(request: Request, exc: ConfigurationError):
        """配置错误处理器"""
        
        logger.error(f"配置错误: {exc.message} - 配置键: {exc.config_key}")
        
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=StandardResponse(
                code=500,
                message="系统配置错误",
                success=False,
                data={
                    "config_key": exc.config_key,
                    "details": "系统配置存在问题，请联系管理员"
                },
                timestamp=datetime.utcnow(),
                request_id=_get_request_id(request)
            ).model_dump(mode='json')
        )
    
    @app.exception_handler(IntentRecognitionError)
    async def intent_recognition_error_handler(request: Request, exc: IntentRecognitionError):
        """意图识别错误处理器"""
        
        logger.warning(f"意图识别错误: {exc.message} - 输入: {exc.user_input}")
        
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content=StandardResponse(
                code=422,
                message="意图识别失败",
                success=False,
                data={
                    "user_input": exc.user_input,
                    "confidence": exc.confidence,
                    "details": exc.message
                },
                timestamp=datetime.utcnow(),
                request_id=_get_request_id(request)
            ).model_dump(mode='json')
        )
    
    @app.exception_handler(SlotExtractionError)
    async def slot_extraction_error_handler(request: Request, exc: SlotExtractionError):
        """槽位提取错误处理器"""
        
        logger.warning(f"槽位提取错误: {exc.message} - 槽位: {exc.slot_name}")
        
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content=StandardResponse(
                code=422,
                message="槽位提取失败",
                success=False,
                data={
                    "slot_name": exc.slot_name,
                    "slot_value": exc.slot_value,
                    "details": exc.message
                },
                timestamp=datetime.utcnow(),
                request_id=_get_request_id(request)
            ).model_dump(mode='json')
        )
    
    @app.exception_handler(ExternalServiceError)
    async def external_service_error_handler(request: Request, exc: ExternalServiceError):
        """外部服务错误处理器"""
        
        logger.error(f"外部服务错误: {exc.message} - 服务: {exc.service_name}")
        
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content=StandardResponse(
                code=503,
                message="外部服务暂时不可用",
                success=False,
                data={
                    "service_name": exc.service_name,
                    "status_code": exc.status_code,
                    "details": "外部服务连接失败，请稍后重试"
                },
                timestamp=datetime.utcnow(),
                request_id=_get_request_id(request)
            ).model_dump(mode='json')
        )


def enhanced_setup_exception_handlers(app: FastAPI):
    """增强版异常处理器设置（包含自定义异常）"""
    setup_exception_handlers(app)
    register_custom_exception_handlers(app)