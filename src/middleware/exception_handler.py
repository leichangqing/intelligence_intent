"""
全局异常处理中间件 (TASK-036)
提供FastAPI应用的全局异常捕获和统一错误响应
"""
import traceback
from typing import Any, Dict, Optional
from datetime import datetime
import logging
import asyncio
from uuid import uuid4

from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError, ResponseValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response
from pydantic import ValidationError

from ..core.error_handler import (
    ErrorHandler, StandardError, ValidationError as CustomValidationError,
    ErrorCode, ErrorCategory, ErrorSeverity, global_error_handler
)
from ..schemas.api_response import ApiResponse, ApiError, ValidationErrorDetail
from ..utils.logger import get_logger

logger = get_logger(__name__)


class ExceptionHandlerMiddleware(BaseHTTPMiddleware):
    """异常处理中间件"""
    
    def __init__(self, app: FastAPI, error_handler: Optional[ErrorHandler] = None):
        super().__init__(app)
        self.error_handler = error_handler or global_error_handler
        self.app_start_time = datetime.now()
    
    async def dispatch(self, request: Request, call_next) -> Response:
        """处理请求并捕获异常"""
        start_time = datetime.now()
        request_id = str(uuid4())
        
        # 添加请求ID到请求状态
        request.state.request_id = request_id
        request.state.start_time = start_time
        
        try:
            # 记录请求信息
            await self._log_request(request, request_id)
            
            # 调用下一个中间件或路由处理器
            response = await call_next(request)
            
            # 记录响应信息
            processing_time = (datetime.now() - start_time).total_seconds() * 1000
            await self._log_response(request, response, processing_time, request_id)
            
            # 添加响应头
            response.headers["X-Request-ID"] = request_id
            response.headers["X-Processing-Time"] = str(int(processing_time))
            
            return response
            
        except Exception as error:
            # 处理异常
            processing_time = (datetime.now() - start_time).total_seconds() * 1000
            return await self._handle_exception(error, request, request_id, processing_time)
    
    async def _log_request(self, request: Request, request_id: str):
        """记录请求信息"""
        try:
            logger.info(
                f"请求开始: {request.method} {request.url.path}",
                extra={
                    "request_id": request_id,
                    "method": request.method,
                    "url": str(request.url),
                    "headers": dict(request.headers),
                    "client_ip": request.client.host if request.client else None
                }
            )
        except Exception as e:
            logger.error(f"记录请求信息失败: {str(e)}")
    
    async def _log_response(self, request: Request, response: Response, 
                           processing_time: float, request_id: str):
        """记录响应信息"""
        try:
            logger.info(
                f"请求完成: {request.method} {request.url.path} - {response.status_code}",
                extra={
                    "request_id": request_id,
                    "status_code": response.status_code,
                    "processing_time_ms": processing_time,
                    "response_size": len(response.body) if hasattr(response, 'body') else None
                }
            )
        except Exception as e:
            logger.error(f"记录响应信息失败: {str(e)}")
    
    async def _handle_exception(self, error: Exception, request: Request, 
                               request_id: str, processing_time: float) -> JSONResponse:
        """处理异常并返回标准错误响应"""
        try:
            # 构建上下文信息
            context = {
                "request_id": request_id,
                "method": request.method,
                "url": str(request.url),
                "user_agent": request.headers.get("user-agent"),
                "client_ip": request.client.host if request.client else None,
                "processing_time_ms": processing_time
            }
            
            # 使用错误处理器处理异常
            error_detail = await self.error_handler.handle_error(error, context)
            
            # 创建API错误响应
            api_error = ApiError.from_error_detail(error_detail)
            
            # 确定HTTP状态码
            status_code = self._get_http_status_code(error, error_detail.code)
            
            # 创建统一响应格式
            response_data = ApiResponse.error_response(
                error_data=api_error,
                request_id=request_id,
                processing_time_ms=int(processing_time)
            )
            
            # 记录异常
            logger.error(
                f"请求异常: {request.method} {request.url.path} - {str(error)}",
                extra={
                    "request_id": request_id,
                    "error_code": error_detail.code.value,
                    "error_category": error_detail.category.value,
                    "stack_trace": error_detail.stack_trace
                }
            )
            
            return JSONResponse(
                status_code=status_code,
                content=response_data.dict(),
                headers={
                    "X-Request-ID": request_id,
                    "X-Processing-Time": str(int(processing_time)),
                    "X-Error-Code": error_detail.code.value
                }
            )
            
        except Exception as handle_error:
            # 处理异常处理器本身的错误
            logger.critical(f"异常处理器失败: {str(handle_error)}")
            
            # 返回最基本的错误响应
            fallback_response = {
                "status": "error",
                "error": {
                    "code": "E1000",
                    "message": "内部服务器错误",
                    "category": "system",
                    "severity": "critical"
                },
                "metadata": {
                    "timestamp": datetime.now().isoformat(),
                    "request_id": request_id,
                    "processing_time_ms": int(processing_time)
                }
            }
            
            return JSONResponse(
                status_code=500,
                content=fallback_response,
                headers={"X-Request-ID": request_id}
            )
    
    def _get_http_status_code(self, error: Exception, error_code: ErrorCode) -> int:
        """根据错误类型确定HTTP状态码"""
        # FastAPI和Starlette的HTTP异常
        if isinstance(error, (HTTPException, StarletteHTTPException)):
            return error.status_code
        
        # 根据错误码映射状态码
        error_code_mapping = {
            # 验证错误 -> 400
            ErrorCode.VALIDATION_ERROR: 400,
            ErrorCode.INVALID_INPUT: 400,
            ErrorCode.MISSING_REQUIRED_FIELD: 400,
            ErrorCode.INVALID_FORMAT: 400,
            ErrorCode.VALUE_OUT_OF_RANGE: 400,
            
            # 认证错误 -> 401
            ErrorCode.AUTHENTICATION_FAILED: 401,
            ErrorCode.INVALID_TOKEN: 401,
            ErrorCode.TOKEN_EXPIRED: 401,
            
            # 授权错误 -> 403
            ErrorCode.AUTHORIZATION_FAILED: 403,
            ErrorCode.INSUFFICIENT_PERMISSIONS: 403,
            
            # 资源不存在 -> 404
            ErrorCode.RESOURCE_NOT_FOUND: 404,
            
            # 业务逻辑错误 -> 409
            ErrorCode.BUSINESS_RULE_VIOLATION: 409,
            ErrorCode.RESOURCE_ALREADY_EXISTS: 409,
            ErrorCode.INVALID_STATE: 409,
            
            # 速率限制 -> 429
            ErrorCode.RATE_LIMIT_EXCEEDED: 429,
            
            # 外部服务错误 -> 502
            ErrorCode.EXTERNAL_SERVICE_ERROR: 502,
            ErrorCode.SERVICE_UNAVAILABLE_ERROR: 503,
            
            # 系统错误 -> 500
            ErrorCode.INTERNAL_SERVER_ERROR: 500,
            ErrorCode.DATABASE_ERROR: 500,
            ErrorCode.CONFIGURATION_ERROR: 500,
        }
        
        return error_code_mapping.get(error_code, 500)


def setup_exception_handlers(app: FastAPI, error_handler: Optional[ErrorHandler] = None):
    """设置全局异常处理器"""
    
    handler = error_handler or global_error_handler
    
    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        """处理请求验证错误"""
        request_id = getattr(request.state, 'request_id', str(uuid4()))
        
        # 转换验证错误
        validation_errors = []
        for error in exc.errors():
            field_path = ".".join(str(loc) for loc in error["loc"])
            validation_errors.append(
                ValidationErrorDetail(
                    field=field_path,
                    message=error["msg"],
                    code=error["type"],
                    value=error.get("input")
                )
            )
        
        # 创建自定义验证错误
        custom_error = CustomValidationError(
            message="请求数据验证失败",
            context={"validation_errors": [e.dict() for e in validation_errors]},
            request_id=request_id
        )
        
        error_detail = await handler.handle_error(custom_error, {
            "request_id": request_id,
            "url": str(request.url),
            "method": request.method
        })
        
        api_error = ApiError.from_error_detail(error_detail)
        api_error.details = validation_errors
        
        response_data = ApiResponse.error_response(
            error_data=api_error,
            request_id=request_id
        )
        
        return JSONResponse(
            status_code=400,
            content=response_data.dict(),
            headers={"X-Request-ID": request_id}
        )
    
    @app.exception_handler(ResponseValidationError)
    async def response_validation_exception_handler(request: Request, exc: ResponseValidationError):
        """处理响应验证错误"""
        request_id = getattr(request.state, 'request_id', str(uuid4()))
        
        logger.critical(f"响应验证失败: {str(exc)}", extra={
            "request_id": request_id,
            "url": str(request.url),
            "method": request.method
        })
        
        error_detail = await handler.handle_error(exc, {
            "request_id": request_id,
            "error_type": "response_validation"
        })
        
        response_data = ApiResponse.error_response(
            error_data=ApiError.from_error_detail(error_detail),
            request_id=request_id
        )
        
        return JSONResponse(
            status_code=500,
            content=response_data.dict(),
            headers={"X-Request-ID": request_id}
        )
    
    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException):
        """处理HTTP异常"""
        request_id = getattr(request.state, 'request_id', str(uuid4()))
        
        # 映射HTTP异常到自定义错误
        error_mapping = {
            400: ErrorCode.VALIDATION_ERROR,
            401: ErrorCode.AUTHENTICATION_FAILED,
            403: ErrorCode.AUTHORIZATION_FAILED,
            404: ErrorCode.RESOURCE_NOT_FOUND,
            429: ErrorCode.RATE_LIMIT_EXCEEDED,
            500: ErrorCode.INTERNAL_SERVER_ERROR,
            502: ErrorCode.EXTERNAL_SERVICE_ERROR,
            503: ErrorCode.SERVICE_UNAVAILABLE
        }
        
        error_code = error_mapping.get(exc.status_code, ErrorCode.UNKNOWN_ERROR)
        
        api_error = ApiError(
            code=error_code.value,
            message=exc.detail,
            category="http",
            severity="medium"
        )
        
        response_data = ApiResponse.error_response(
            error_data=api_error,
            request_id=request_id
        )
        
        return JSONResponse(
            status_code=exc.status_code,
            content=response_data.dict(),
            headers={"X-Request-ID": request_id}
        )
    
    @app.exception_handler(StandardError)
    async def standard_exception_handler(request: Request, exc: StandardError):
        """处理自定义标准异常"""
        request_id = getattr(request.state, 'request_id', str(uuid4()))
        
        # 直接使用异常中的错误详情
        api_error = ApiError.from_error_detail(exc.error_detail)
        
        status_code = ExceptionHandlerMiddleware(app)._get_http_status_code(exc, exc.error_detail.code)
        
        response_data = ApiResponse.error_response(
            error_data=api_error,
            request_id=request_id
        )
        
        return JSONResponse(
            status_code=status_code,
            content=response_data.dict(),
            headers={"X-Request-ID": request_id}
        )
    
    @app.exception_handler(Exception)
    async def general_exception_handler(request: Request, exc: Exception):
        """处理通用异常"""
        request_id = getattr(request.state, 'request_id', str(uuid4()))
        
        error_detail = await handler.handle_error(exc, {
            "request_id": request_id,
            "url": str(request.url),
            "method": request.method
        })
        
        api_error = ApiError.from_error_detail(error_detail)
        
        response_data = ApiResponse.error_response(
            error_data=api_error,
            request_id=request_id
        )
        
        return JSONResponse(
            status_code=500,
            content=response_data.dict(),
            headers={"X-Request-ID": request_id}
        )
    
    # 添加异常处理中间件
    app.add_middleware(ExceptionHandlerMiddleware, error_handler=handler)
    
    logger.info("全局异常处理器设置完成")


def add_error_monitoring_endpoints(app: FastAPI, error_handler: Optional[ErrorHandler] = None):
    """添加错误监控端点"""
    
    handler = error_handler or global_error_handler
    
    @app.get("/health/errors")
    async def get_error_stats():
        """获取错误统计"""
        stats = handler.get_error_stats()
        return ApiResponse.success(data=stats, message="错误统计获取成功")
    
    @app.get("/health/errors/recent")
    async def get_recent_errors(limit: int = 10):
        """获取最近的错误"""
        recent_errors = handler.get_recent_errors(limit)
        return ApiResponse.success(data=recent_errors, message="最近错误获取成功")
    
    logger.info("错误监控端点添加完成")