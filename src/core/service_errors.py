"""
统一的服务层错误处理机制
提供标准化的异常类、错误代码和处理流程
"""
from typing import Dict, Any, Optional, List, Union
from enum import Enum
from datetime import datetime
import traceback
import uuid
from pydantic import BaseModel

from src.utils.logger import get_logger

logger = get_logger(__name__)


class ErrorSeverity(str, Enum):
    """错误严重程度"""
    LOW = "low"           # 轻微错误，不影响核心功能
    MEDIUM = "medium"     # 中等错误，影响部分功能
    HIGH = "high"         # 严重错误，影响核心功能
    CRITICAL = "critical" # 致命错误，系统无法正常运行


class ErrorCategory(str, Enum):
    """错误类别"""
    VALIDATION = "validation"         # 数据验证错误
    AUTHENTICATION = "authentication" # 认证错误
    AUTHORIZATION = "authorization"   # 授权错误
    NOT_FOUND = "not_found"          # 资源未找到
    CONFLICT = "conflict"            # 资源冲突
    RATE_LIMIT = "rate_limit"        # 限流错误
    EXTERNAL_SERVICE = "external_service"  # 外部服务错误
    DATABASE = "database"            # 数据库错误
    CACHE = "cache"                  # 缓存错误
    NETWORK = "network"              # 网络错误
    CONFIGURATION = "configuration"   # 配置错误
    BUSINESS_LOGIC = "business_logic" # 业务逻辑错误
    SYSTEM = "system"                # 系统错误


class ErrorInfo(BaseModel):
    """错误信息结构"""
    error_id: str
    error_code: str
    category: ErrorCategory
    severity: ErrorSeverity
    message: str
    details: Optional[Dict[str, Any]] = None
    timestamp: datetime
    service_name: Optional[str] = None
    method_name: Optional[str] = None
    user_id: Optional[str] = None
    request_id: Optional[str] = None
    stack_trace: Optional[str] = None
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class ServiceException(Exception):
    """服务层基础异常类"""
    
    def __init__(
        self,
        message: str,
        error_code: str = "SERVICE_ERROR",
        category: ErrorCategory = ErrorCategory.SYSTEM,
        severity: ErrorSeverity = ErrorSeverity.MEDIUM,
        details: Optional[Dict[str, Any]] = None,
        service_name: Optional[str] = None,
        method_name: Optional[str] = None,
        user_id: Optional[str] = None,
        request_id: Optional[str] = None,
        cause: Optional[Exception] = None
    ):
        super().__init__(message)
        
        self.error_info = ErrorInfo(
            error_id=str(uuid.uuid4()),
            error_code=error_code,
            category=category,
            severity=severity,
            message=message,
            details=details or {},
            timestamp=datetime.now(),
            service_name=service_name,
            method_name=method_name,
            user_id=user_id,
            request_id=request_id,
            stack_trace=traceback.format_exc() if cause else None
        )
        
        self.cause = cause


class ValidationException(ServiceException):
    """数据验证异常"""
    
    def __init__(self, message: str, field_errors: Dict[str, str] = None, **kwargs):
        super().__init__(
            message=message,
            error_code="VALIDATION_ERROR",
            category=ErrorCategory.VALIDATION,
            severity=ErrorSeverity.LOW,
            details={"field_errors": field_errors or {}},
            **kwargs
        )


class AuthenticationException(ServiceException):
    """认证异常"""
    
    def __init__(self, message: str = "认证失败", **kwargs):
        super().__init__(
            message=message,
            error_code="AUTHENTICATION_ERROR",
            category=ErrorCategory.AUTHENTICATION,
            severity=ErrorSeverity.HIGH,
            **kwargs
        )


class AuthorizationException(ServiceException):
    """授权异常"""
    
    def __init__(self, message: str = "权限不足", **kwargs):
        super().__init__(
            message=message,
            error_code="AUTHORIZATION_ERROR", 
            category=ErrorCategory.AUTHORIZATION,
            severity=ErrorSeverity.HIGH,
            **kwargs
        )


class ResourceNotFoundException(ServiceException):
    """资源未找到异常"""
    
    def __init__(self, resource_type: str, resource_id: str = None, **kwargs):
        message = f"{resource_type}未找到"
        if resource_id:
            message += f": {resource_id}"
        
        super().__init__(
            message=message,
            error_code="RESOURCE_NOT_FOUND",
            category=ErrorCategory.NOT_FOUND,
            severity=ErrorSeverity.LOW,
            details={"resource_type": resource_type, "resource_id": resource_id},
            **kwargs
        )


class BusinessLogicException(ServiceException):
    """业务逻辑异常"""
    
    def __init__(self, message: str, business_rule: str = None, **kwargs):
        super().__init__(
            message=message,
            error_code="BUSINESS_LOGIC_ERROR",
            category=ErrorCategory.BUSINESS_LOGIC,
            severity=ErrorSeverity.MEDIUM,
            details={"business_rule": business_rule},
            **kwargs
        )


class ExternalServiceException(ServiceException):
    """外部服务异常"""
    
    def __init__(self, service_name: str, message: str = None, **kwargs):
        super().__init__(
            message=message or f"外部服务 {service_name} 调用失败",
            error_code="EXTERNAL_SERVICE_ERROR",
            category=ErrorCategory.EXTERNAL_SERVICE,
            severity=ErrorSeverity.HIGH,
            details={"external_service": service_name},
            **kwargs
        )


class DatabaseException(ServiceException):
    """数据库异常"""
    
    def __init__(self, message: str, operation: str = None, **kwargs):
        super().__init__(
            message=message,
            error_code="DATABASE_ERROR",
            category=ErrorCategory.DATABASE,
            severity=ErrorSeverity.HIGH,
            details={"operation": operation},
            **kwargs
        )


class CacheException(ServiceException):
    """缓存异常"""
    
    def __init__(self, message: str, cache_key: str = None, **kwargs):
        super().__init__(
            message=message,
            error_code="CACHE_ERROR",
            category=ErrorCategory.CACHE,
            severity=ErrorSeverity.MEDIUM,
            details={"cache_key": cache_key},
            **kwargs
        )


class RateLimitException(ServiceException):
    """限流异常"""
    
    def __init__(self, limit: int, window: str, **kwargs):
        super().__init__(
            message=f"请求频率超限: {limit}次/{window}",
            error_code="RATE_LIMIT_ERROR",
            category=ErrorCategory.RATE_LIMIT,
            severity=ErrorSeverity.MEDIUM,
            details={"limit": limit, "window": window},
            **kwargs
        )


class ErrorHandler:
    """统一错误处理器"""
    
    def __init__(self):
        self.logger = logger
    
    def handle_exception(
        self,
        exception: Exception,
        service_name: str,
        method_name: str,
        user_id: str = None,
        request_id: str = None,
        context: Dict[str, Any] = None
    ) -> ErrorInfo:
        """
        统一处理异常
        
        Args:
            exception: 异常对象
            service_name: 服务名称
            method_name: 方法名称
            user_id: 用户ID
            request_id: 请求ID
            context: 附加上下文
            
        Returns:
            ErrorInfo: 标准化的错误信息
        """
        
        if isinstance(exception, ServiceException):
            # 已经是标准化的服务异常
            error_info = exception.error_info
            
            # 补充缺失的信息
            if not error_info.service_name:
                error_info.service_name = service_name
            if not error_info.method_name:
                error_info.method_name = method_name
            if not error_info.user_id and user_id:
                error_info.user_id = user_id
            if not error_info.request_id and request_id:
                error_info.request_id = request_id
                
        else:
            # 将普通异常转换为服务异常
            error_info = ErrorInfo(
                error_id=str(uuid.uuid4()),
                error_code="UNEXPECTED_ERROR",
                category=self._categorize_exception(exception),
                severity=self._assess_severity(exception),
                message=str(exception),
                details=context or {},
                timestamp=datetime.now(),
                service_name=service_name,
                method_name=method_name,
                user_id=user_id,
                request_id=request_id,
                stack_trace=traceback.format_exc()
            )
        
        # 记录错误日志
        self._log_error(error_info)
        
        # 触发监控告警（如果是高严重程度错误）
        if error_info.severity in [ErrorSeverity.HIGH, ErrorSeverity.CRITICAL]:
            self._trigger_alert(error_info)
        
        return error_info
    
    def _categorize_exception(self, exception: Exception) -> ErrorCategory:
        """根据异常类型自动分类"""
        exception_type = type(exception).__name__
        
        # 数据库相关异常
        if any(db_error in exception_type.lower() for db_error in 
               ['connection', 'database', 'sql', 'constraint', 'integrity']):
            return ErrorCategory.DATABASE
        
        # 网络相关异常
        if any(net_error in exception_type.lower() for net_error in 
               ['connection', 'timeout', 'network', 'http']):
            return ErrorCategory.NETWORK
        
        # 验证相关异常
        if any(val_error in exception_type.lower() for val_error in 
               ['validation', 'value', 'type', 'format']):
            return ErrorCategory.VALIDATION
        
        # 默认为系统错误
        return ErrorCategory.SYSTEM
    
    def _assess_severity(self, exception: Exception) -> ErrorSeverity:
        """评估异常严重程度"""
        exception_type = type(exception).__name__
        
        # 致命错误类型
        if any(critical in exception_type.lower() for critical in 
               ['memory', 'system', 'os', 'security']):
            return ErrorSeverity.CRITICAL
        
        # 高严重程度错误
        if any(high in exception_type.lower() for high in 
               ['connection', 'database', 'authentication']):
            return ErrorSeverity.HIGH
        
        # 中等严重程度错误
        if any(medium in exception_type.lower() for medium in 
               ['timeout', 'network', 'external']):
            return ErrorSeverity.MEDIUM
        
        # 默认为低严重程度
        return ErrorSeverity.LOW
    
    def _log_error(self, error_info: ErrorInfo):
        """记录错误日志"""
        log_message = (
            f"[{error_info.service_name}.{error_info.method_name}] "
            f"{error_info.error_code}: {error_info.message}"
        )
        
        log_context = {
            "error_id": error_info.error_id,
            "category": error_info.category.value,
            "severity": error_info.severity.value,
            "user_id": error_info.user_id,
            "request_id": error_info.request_id,
            "details": error_info.details
        }
        
        if error_info.severity == ErrorSeverity.CRITICAL:
            self.logger.critical(log_message, extra=log_context)
        elif error_info.severity == ErrorSeverity.HIGH:
            self.logger.error(log_message, extra=log_context)
        elif error_info.severity == ErrorSeverity.MEDIUM:
            self.logger.warning(log_message, extra=log_context)
        else:
            self.logger.info(log_message, extra=log_context)
    
    def _trigger_alert(self, error_info: ErrorInfo):
        """触发监控告警"""
        try:
            # 这里可以集成告警系统，如钉钉、邮件、短信等
            # 暂时只记录日志
            self.logger.warning(
                f"触发告警: {error_info.error_code} - {error_info.message}",
                extra={"error_id": error_info.error_id}
            )
        except Exception as e:
            self.logger.error(f"触发告警失败: {str(e)}")


# 全局错误处理器实例
_error_handler = ErrorHandler()


def get_error_handler() -> ErrorHandler:
    """获取全局错误处理器"""
    return _error_handler


def handle_service_exception(
    service_name: str,
    method_name: str = None,
    user_id: str = None,
    request_id: str = None
):
    """
    服务异常处理装饰器
    
    Usage:
        @handle_service_exception("IntentService", "recognize_intent")
        async def recognize_intent(self, user_input: str):
            # service logic here
            pass
    """
    def decorator(func):
        async def async_wrapper(*args, **kwargs):
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                error_info = _error_handler.handle_exception(
                    exception=e,
                    service_name=service_name,
                    method_name=method_name or func.__name__,
                    user_id=user_id,
                    request_id=request_id,
                    context={"args": str(args), "kwargs": str(kwargs)}
                )
                
                # 根据错误类型决定是否重新抛出异常
                if isinstance(e, ServiceException):
                    raise e
                else:
                    # 将普通异常包装为服务异常后抛出
                    raise ServiceException(
                        message=str(e),
                        error_code=error_info.error_code,
                        category=error_info.category,
                        severity=error_info.severity,
                        service_name=service_name,
                        method_name=method_name or func.__name__,
                        cause=e
                    )
        
        def sync_wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                error_info = _error_handler.handle_exception(
                    exception=e,
                    service_name=service_name,
                    method_name=method_name or func.__name__,
                    user_id=user_id,
                    request_id=request_id,
                    context={"args": str(args), "kwargs": str(kwargs)}
                )
                
                if isinstance(e, ServiceException):
                    raise e
                else:
                    raise ServiceException(
                        message=str(e),
                        error_code=error_info.error_code,
                        category=error_info.category,
                        severity=error_info.severity,
                        service_name=service_name,
                        method_name=method_name or func.__name__,
                        cause=e
                    )
        
        # 检查是否为异步函数
        import asyncio
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    
    return decorator


class ServiceResult:
    """统一的服务结果类"""
    
    def __init__(
        self,
        success: bool,
        data: Any = None,
        error_info: ErrorInfo = None,
        message: str = None
    ):
        self.success = success
        self.data = data
        self.error_info = error_info
        self.message = message or ("操作成功" if success else "操作失败")
    
    @classmethod
    def success_result(cls, data: Any = None, message: str = None) -> 'ServiceResult':
        """创建成功结果"""
        return cls(success=True, data=data, message=message)
    
    @classmethod
    def error_result(cls, error_info: ErrorInfo, message: str = None) -> 'ServiceResult':
        """创建错误结果"""
        return cls(
            success=False, 
            error_info=error_info, 
            message=message or error_info.message
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        result = {
            "success": self.success,
            "message": self.message,
            "data": self.data
        }
        
        if self.error_info:
            result["error"] = {
                "error_id": self.error_info.error_id,
                "error_code": self.error_info.error_code,
                "category": self.error_info.category.value,
                "severity": self.error_info.severity.value,
                "details": self.error_info.details
            }
        
        return result