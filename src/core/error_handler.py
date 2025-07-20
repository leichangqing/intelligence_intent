"""
标准化错误处理系统 (TASK-036)
提供统一的错误处理、分类、记录和响应机制
"""
import traceback
import sys
from typing import Dict, Any, Optional, List, Type, Union
from datetime import datetime
from enum import Enum
from dataclasses import dataclass, asdict
import logging
import asyncio
from contextlib import asynccontextmanager

from ..utils.logger import get_logger

logger = get_logger(__name__)


class ErrorSeverity(str, Enum):
    """错误严重程度"""
    LOW = "low"                 # 低级别 - 警告信息
    MEDIUM = "medium"           # 中级别 - 需要关注
    HIGH = "high"              # 高级别 - 需要立即处理
    CRITICAL = "critical"      # 关键级别 - 系统性问题


class ErrorCategory(str, Enum):
    """错误分类"""
    VALIDATION = "validation"           # 数据验证错误
    AUTHENTICATION = "authentication"   # 认证错误
    AUTHORIZATION = "authorization"     # 授权错误
    BUSINESS_LOGIC = "business_logic"  # 业务逻辑错误
    EXTERNAL_SERVICE = "external_service"  # 外部服务错误
    DATABASE = "database"              # 数据库错误
    SYSTEM = "system"                  # 系统错误
    NETWORK = "network"                # 网络错误
    RATE_LIMIT = "rate_limit"          # 速率限制错误
    RESOURCE = "resource"              # 资源错误
    CONFIGURATION = "configuration"    # 配置错误
    UNKNOWN = "unknown"                # 未知错误


class ErrorCode(str, Enum):
    """标准错误码"""
    # 通用错误 (1000-1999)
    INTERNAL_SERVER_ERROR = "E1000"
    UNKNOWN_ERROR = "E1001"
    TIMEOUT_ERROR = "E1002"
    RATE_LIMIT_EXCEEDED = "E1003"
    SERVICE_UNAVAILABLE = "E1004"
    
    # 验证错误 (2000-2999)
    VALIDATION_ERROR = "E2000"
    INVALID_INPUT = "E2001"
    MISSING_REQUIRED_FIELD = "E2002"
    INVALID_FORMAT = "E2003"
    VALUE_OUT_OF_RANGE = "E2004"
    
    # 认证和授权错误 (3000-3999)
    AUTHENTICATION_FAILED = "E3000"
    INVALID_TOKEN = "E3001"
    TOKEN_EXPIRED = "E3002"
    AUTHORIZATION_FAILED = "E3003"
    INSUFFICIENT_PERMISSIONS = "E3004"
    
    # 业务逻辑错误 (4000-4999)
    BUSINESS_RULE_VIOLATION = "E4000"
    INVALID_OPERATION = "E4001"
    RESOURCE_NOT_FOUND = "E4002"
    RESOURCE_ALREADY_EXISTS = "E4003"
    INVALID_STATE = "E4004"
    
    # 外部服务错误 (5000-5999)
    EXTERNAL_SERVICE_ERROR = "E5000"
    API_CALL_FAILED = "E5001"
    SERVICE_TIMEOUT = "E5002"
    SERVICE_UNAVAILABLE_ERROR = "E5003"
    
    # 数据库错误 (6000-6999)
    DATABASE_ERROR = "E6000"
    CONNECTION_FAILED = "E6001"
    QUERY_FAILED = "E6002"
    TRANSACTION_FAILED = "E6003"
    CONSTRAINT_VIOLATION = "E6004"
    
    # 配置错误 (7000-7999)
    CONFIGURATION_ERROR = "E7000"
    MISSING_CONFIGURATION = "E7001"
    INVALID_CONFIGURATION = "E7002"
    
    # 网络错误 (8000-8999)
    NETWORK_ERROR = "E8000"
    CONNECTION_TIMEOUT = "E8001"
    DNS_RESOLUTION_FAILED = "E8002"
    
    # 资源错误 (9000-9999)
    RESOURCE_EXHAUSTED = "E9000"
    MEMORY_ERROR = "E9001"
    DISK_SPACE_ERROR = "E9002"


@dataclass
class ErrorDetail:
    """错误详细信息"""
    code: ErrorCode
    message: str
    category: ErrorCategory
    severity: ErrorSeverity
    context: Dict[str, Any]
    timestamp: datetime
    trace_id: Optional[str] = None
    user_id: Optional[str] = None
    request_id: Optional[str] = None
    stack_trace: Optional[str] = None
    remediation: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        result = asdict(self)
        result['timestamp'] = self.timestamp.isoformat()
        return result
    
    def to_user_message(self) -> str:
        """生成用户友好的错误消息"""
        user_messages = {
            ErrorCode.VALIDATION_ERROR: "请检查输入的数据格式是否正确",
            ErrorCode.AUTHENTICATION_FAILED: "用户认证失败，请重新登录",
            ErrorCode.AUTHORIZATION_FAILED: "您没有权限执行此操作",
            ErrorCode.RESOURCE_NOT_FOUND: "请求的资源不存在",
            ErrorCode.RATE_LIMIT_EXCEEDED: "请求过于频繁，请稍后再试",
            ErrorCode.SERVICE_UNAVAILABLE: "服务暂时不可用，请稍后再试",
            ErrorCode.INTERNAL_SERVER_ERROR: "系统内部错误，请联系技术支持"
        }
        
        return user_messages.get(self.code, self.message)


class StandardError(Exception):
    """标准化异常基类"""
    
    def __init__(self, 
                 code: ErrorCode,
                 message: str,
                 category: ErrorCategory = ErrorCategory.UNKNOWN,
                 severity: ErrorSeverity = ErrorSeverity.MEDIUM,
                 context: Optional[Dict[str, Any]] = None,
                 trace_id: Optional[str] = None,
                 user_id: Optional[str] = None,
                 request_id: Optional[str] = None,
                 remediation: Optional[str] = None):
        
        self.error_detail = ErrorDetail(
            code=code,
            message=message,
            category=category,
            severity=severity,
            context=context or {},
            timestamp=datetime.now(),
            trace_id=trace_id,
            user_id=user_id,
            request_id=request_id,
            stack_trace=traceback.format_exc(),
            remediation=remediation
        )
        
        super().__init__(message)
    
    def __str__(self) -> str:
        return f"[{self.error_detail.code.value}] {self.error_detail.message}"


class ValidationError(StandardError):
    """验证错误"""
    
    def __init__(self, message: str, field: Optional[str] = None, **kwargs):
        context = kwargs.pop('context', {})
        if field:
            context['field'] = field
        
        super().__init__(
            code=ErrorCode.VALIDATION_ERROR,
            message=message,
            category=ErrorCategory.VALIDATION,
            severity=ErrorSeverity.LOW,
            context=context,
            **kwargs
        )


class AuthenticationError(StandardError):
    """认证错误"""
    
    def __init__(self, message: str = "认证失败", **kwargs):
        super().__init__(
            code=ErrorCode.AUTHENTICATION_FAILED,
            message=message,
            category=ErrorCategory.AUTHENTICATION,
            severity=ErrorSeverity.HIGH,
            **kwargs
        )


class AuthorizationError(StandardError):
    """授权错误"""
    
    def __init__(self, message: str = "权限不足", **kwargs):
        super().__init__(
            code=ErrorCode.AUTHORIZATION_FAILED,
            message=message,
            category=ErrorCategory.AUTHORIZATION,
            severity=ErrorSeverity.HIGH,
            **kwargs
        )


class BusinessLogicError(StandardError):
    """业务逻辑错误"""
    
    def __init__(self, message: str, **kwargs):
        super().__init__(
            code=ErrorCode.BUSINESS_RULE_VIOLATION,
            message=message,
            category=ErrorCategory.BUSINESS_LOGIC,
            severity=ErrorSeverity.MEDIUM,
            **kwargs
        )


class ExternalServiceError(StandardError):
    """外部服务错误"""
    
    def __init__(self, message: str, service_name: Optional[str] = None, **kwargs):
        context = kwargs.pop('context', {})
        if service_name:
            context['service_name'] = service_name
        
        super().__init__(
            code=ErrorCode.EXTERNAL_SERVICE_ERROR,
            message=message,
            category=ErrorCategory.EXTERNAL_SERVICE,
            severity=ErrorSeverity.HIGH,
            context=context,
            **kwargs
        )


class DatabaseError(StandardError):
    """数据库错误"""
    
    def __init__(self, message: str, **kwargs):
        super().__init__(
            code=ErrorCode.DATABASE_ERROR,
            message=message,
            category=ErrorCategory.DATABASE,
            severity=ErrorSeverity.HIGH,
            **kwargs
        )


class ConfigurationError(StandardError):
    """配置错误"""
    
    def __init__(self, message: str, config_key: Optional[str] = None, **kwargs):
        context = kwargs.pop('context', {})
        if config_key:
            context['config_key'] = config_key
        
        super().__init__(
            code=ErrorCode.CONFIGURATION_ERROR,
            message=message,
            category=ErrorCategory.CONFIGURATION,
            severity=ErrorSeverity.CRITICAL,
            context=context,
            **kwargs
        )


class RateLimitError(StandardError):
    """速率限制错误"""
    
    def __init__(self, message: str = "请求频率超限", **kwargs):
        super().__init__(
            code=ErrorCode.RATE_LIMIT_EXCEEDED,
            message=message,
            category=ErrorCategory.RATE_LIMIT,
            severity=ErrorSeverity.MEDIUM,
            **kwargs
        )


class ErrorHandler:
    """错误处理器"""
    
    def __init__(self):
        self.error_handlers: Dict[Type[Exception], callable] = {}
        self.error_stats: Dict[str, int] = {}
        self.error_history: List[ErrorDetail] = []
        self.max_history_size = 1000
        
        # 注册默认处理器
        self._register_default_handlers()
    
    def _register_default_handlers(self):
        """注册默认错误处理器"""
        self.error_handlers[ValidationError] = self._handle_validation_error
        self.error_handlers[AuthenticationError] = self._handle_authentication_error
        self.error_handlers[AuthorizationError] = self._handle_authorization_error
        self.error_handlers[BusinessLogicError] = self._handle_business_logic_error
        self.error_handlers[ExternalServiceError] = self._handle_external_service_error
        self.error_handlers[DatabaseError] = self._handle_database_error
        self.error_handlers[ConfigurationError] = self._handle_configuration_error
        self.error_handlers[RateLimitError] = self._handle_rate_limit_error
        self.error_handlers[Exception] = self._handle_generic_error
    
    def register_handler(self, exception_type: Type[Exception], handler: callable):
        """注册自定义错误处理器"""
        self.error_handlers[exception_type] = handler
        logger.info(f"注册错误处理器: {exception_type.__name__}")
    
    async def handle_error(self, 
                          error: Exception,
                          context: Optional[Dict[str, Any]] = None) -> ErrorDetail:
        """
        处理错误
        
        Args:
            error: 异常对象
            context: 上下文信息
            
        Returns:
            ErrorDetail: 错误详情
        """
        try:
            # 获取错误类型对应的处理器
            handler = self._get_error_handler(type(error))
            
            # 执行错误处理
            if asyncio.iscoroutinefunction(handler):
                error_detail = await handler(error, context)
            else:
                error_detail = handler(error, context)
            
            # 记录错误
            await self._record_error(error_detail)
            
            # 更新统计
            self._update_error_stats(error_detail)
            
            return error_detail
            
        except Exception as handle_error:
            logger.error(f"错误处理器失败: {str(handle_error)}")
            
            # 创建fallback错误详情
            fallback_detail = ErrorDetail(
                code=ErrorCode.INTERNAL_SERVER_ERROR,
                message=f"错误处理失败: {str(error)}",
                category=ErrorCategory.SYSTEM,
                severity=ErrorSeverity.CRITICAL,
                context=context or {},
                timestamp=datetime.now(),
                stack_trace=traceback.format_exc()
            )
            
            await self._record_error(fallback_detail)
            return fallback_detail
    
    def _get_error_handler(self, error_type: Type[Exception]) -> callable:
        """获取错误处理器"""
        # 首先查找精确匹配
        if error_type in self.error_handlers:
            return self.error_handlers[error_type]
        
        # 查找继承关系匹配
        for registered_type, handler in self.error_handlers.items():
            if issubclass(error_type, registered_type):
                return handler
        
        # 返回通用处理器
        return self.error_handlers[Exception]
    
    async def _handle_validation_error(self, error: ValidationError, context: Optional[Dict[str, Any]]) -> ErrorDetail:
        """处理验证错误"""
        logger.warning(f"验证错误: {str(error)}")
        return error.error_detail
    
    async def _handle_authentication_error(self, error: AuthenticationError, context: Optional[Dict[str, Any]]) -> ErrorDetail:
        """处理认证错误"""
        logger.warning(f"认证错误: {str(error)}")
        return error.error_detail
    
    async def _handle_authorization_error(self, error: AuthorizationError, context: Optional[Dict[str, Any]]) -> ErrorDetail:
        """处理授权错误"""
        logger.warning(f"授权错误: {str(error)}")
        return error.error_detail
    
    async def _handle_business_logic_error(self, error: BusinessLogicError, context: Optional[Dict[str, Any]]) -> ErrorDetail:
        """处理业务逻辑错误"""
        logger.info(f"业务逻辑错误: {str(error)}")
        return error.error_detail
    
    async def _handle_external_service_error(self, error: ExternalServiceError, context: Optional[Dict[str, Any]]) -> ErrorDetail:
        """处理外部服务错误"""
        logger.error(f"外部服务错误: {str(error)}")
        return error.error_detail
    
    async def _handle_database_error(self, error: DatabaseError, context: Optional[Dict[str, Any]]) -> ErrorDetail:
        """处理数据库错误"""
        logger.error(f"数据库错误: {str(error)}")
        return error.error_detail
    
    async def _handle_configuration_error(self, error: ConfigurationError, context: Optional[Dict[str, Any]]) -> ErrorDetail:
        """处理配置错误"""
        logger.critical(f"配置错误: {str(error)}")
        return error.error_detail
    
    async def _handle_rate_limit_error(self, error: RateLimitError, context: Optional[Dict[str, Any]]) -> ErrorDetail:
        """处理速率限制错误"""
        logger.warning(f"速率限制错误: {str(error)}")
        return error.error_detail
    
    async def _handle_generic_error(self, error: Exception, context: Optional[Dict[str, Any]]) -> ErrorDetail:
        """处理通用错误"""
        logger.error(f"未分类错误: {str(error)}")
        
        error_detail = ErrorDetail(
            code=ErrorCode.UNKNOWN_ERROR,
            message=str(error),
            category=ErrorCategory.UNKNOWN,
            severity=ErrorSeverity.MEDIUM,
            context=context or {},
            timestamp=datetime.now(),
            stack_trace=traceback.format_exc()
        )
        
        return error_detail
    
    async def _record_error(self, error_detail: ErrorDetail):
        """记录错误"""
        try:
            # 添加到历史记录
            self.error_history.append(error_detail)
            
            # 限制历史记录大小
            if len(self.error_history) > self.max_history_size:
                self.error_history = self.error_history[-self.max_history_size:]
            
            # 根据严重程度记录日志
            log_data = error_detail.to_dict()
            log_message = f"{error_detail.severity.value}级错误: {error_detail.message}"
            
            if error_detail.severity == ErrorSeverity.CRITICAL:
                logger.critical(log_message, extra={"error_data": log_data})
            elif error_detail.severity == ErrorSeverity.HIGH:
                logger.error(log_message, extra={"error_data": log_data})
            elif error_detail.severity == ErrorSeverity.MEDIUM:
                logger.warning(log_message, extra={"error_data": log_data})
            else:
                logger.info(log_message, extra={"error_data": log_data})
                
        except Exception as e:
            logger.error(f"错误记录失败: {str(e)}")
    
    def _update_error_stats(self, error_detail: ErrorDetail):
        """更新错误统计"""
        try:
            # 按错误码统计
            if error_detail.code.value not in self.error_stats:
                self.error_stats[error_detail.code.value] = 0
            self.error_stats[error_detail.code.value] += 1
            
            # 按类别统计
            category_key = f"category_{error_detail.category.value}"
            if category_key not in self.error_stats:
                self.error_stats[category_key] = 0
            self.error_stats[category_key] += 1
            
            # 按严重程度统计
            severity_key = f"severity_{error_detail.severity.value}"
            if severity_key not in self.error_stats:
                self.error_stats[severity_key] = 0
            self.error_stats[severity_key] += 1
            
        except Exception as e:
            logger.error(f"错误统计更新失败: {str(e)}")
    
    def get_error_stats(self) -> Dict[str, Any]:
        """获取错误统计"""
        try:
            total_errors = sum(count for key, count in self.error_stats.items() 
                             if not key.startswith(('category_', 'severity_')))
            
            return {
                'total_errors': total_errors,
                'error_by_code': {k: v for k, v in self.error_stats.items() 
                                if not k.startswith(('category_', 'severity_'))},
                'error_by_category': {k.replace('category_', ''): v 
                                    for k, v in self.error_stats.items() 
                                    if k.startswith('category_')},
                'error_by_severity': {k.replace('severity_', ''): v 
                                    for k, v in self.error_stats.items() 
                                    if k.startswith('severity_')},
                'recent_errors_count': len(self.error_history),
                'max_history_size': self.max_history_size
            }
            
        except Exception as e:
            logger.error(f"获取错误统计失败: {str(e)}")
            return {}
    
    def get_recent_errors(self, limit: int = 10) -> List[Dict[str, Any]]:
        """获取最近的错误"""
        try:
            recent = self.error_history[-limit:] if limit > 0 else self.error_history
            return [error.to_dict() for error in reversed(recent)]
            
        except Exception as e:
            logger.error(f"获取最近错误失败: {str(e)}")
            return []
    
    @asynccontextmanager
    async def error_context(self, **context_data):
        """错误上下文管理器"""
        try:
            yield
        except Exception as error:
            await self.handle_error(error, context_data)
            raise


# 全局错误处理器实例
global_error_handler = ErrorHandler()