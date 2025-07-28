"""
统一API响应格式 (TASK-036)
定义标准化的API响应结构和数据模型
"""
from typing import Any, Dict, List, Optional, Union, Generic, TypeVar
from pydantic import BaseModel, Field
from datetime import datetime
from enum import Enum

from src.core.error_handler import ErrorDetail, ErrorCode

T = TypeVar('T')


class ResponseStatus(str, Enum):
    """响应状态"""
    SUCCESS = "success"         # 成功
    ERROR = "error"            # 错误
    WARNING = "warning"        # 警告
    PARTIAL = "partial"        # 部分成功


class ResponseMetadata(BaseModel):
    """响应元数据"""
    timestamp: str = Field(..., description="响应时间戳")
    request_id: Optional[str] = Field(None, description="请求ID")
    trace_id: Optional[str] = Field(None, description="追踪ID")
    version: str = Field("1.0", description="API版本")
    processing_time_ms: Optional[int] = Field(None, description="处理时间(毫秒)")
    server_id: Optional[str] = Field(None, description="服务器ID")
    environment: Optional[str] = Field(None, description="环境信息")


class PaginationInfo(BaseModel):
    """分页信息"""
    page: int = Field(..., description="当前页码", ge=1)
    size: int = Field(..., description="每页大小", ge=1, le=100)
    total: int = Field(..., description="总记录数", ge=0)
    total_pages: int = Field(..., description="总页数", ge=0)
    has_next: bool = Field(..., description="是否有下一页")
    has_prev: bool = Field(..., description="是否有上一页")


class ValidationErrorDetail(BaseModel):
    """验证错误详情"""
    field: str = Field(..., description="字段名")
    message: str = Field(..., description="错误消息")
    code: str = Field(..., description="错误码")
    value: Optional[Any] = Field(None, description="错误值")


class ApiError(BaseModel):
    """API错误信息"""
    code: str = Field(..., description="错误码")
    message: str = Field(..., description="错误消息")
    details: Optional[Union[str, Dict[str, Any], List[ValidationErrorDetail]]] = Field(None, description="错误详情")
    category: Optional[str] = Field(None, description="错误类别")
    severity: Optional[str] = Field(None, description="严重程度")
    remediation: Optional[str] = Field(None, description="解决建议")
    documentation_url: Optional[str] = Field(None, description="文档链接")
    
    @classmethod
    def from_error_detail(cls, error_detail: ErrorDetail) -> "ApiError":
        """从ErrorDetail创建ApiError"""
        return cls(
            code=error_detail.code.value,
            message=error_detail.to_user_message(),
            details=error_detail.context,
            category=error_detail.category.value,
            severity=error_detail.severity.value,
            remediation=error_detail.remediation
        )


class ApiResponse(BaseModel, Generic[T]):
    """统一API响应格式"""
    status: ResponseStatus = Field(..., description="响应状态")
    data: Optional[T] = Field(None, description="响应数据")
    error: Optional[ApiError] = Field(None, description="错误信息")
    message: Optional[str] = Field(None, description="响应消息")
    metadata: ResponseMetadata = Field(..., description="响应元数据")
    pagination: Optional[PaginationInfo] = Field(None, description="分页信息")
    warnings: Optional[List[str]] = Field(None, description="警告信息")
    debug_info: Optional[Dict[str, Any]] = Field(None, description="调试信息")
    
    @classmethod
    def success(cls,
               data: Optional[T] = None,
               message: Optional[str] = None,
               metadata: Optional[Dict[str, Any]] = None,
               pagination: Optional[PaginationInfo] = None,
               warnings: Optional[List[str]] = None,
               request_id: Optional[str] = None,
               processing_time_ms: Optional[int] = None) -> "ApiResponse[T]":
        """创建成功响应"""
        
        response_metadata = ResponseMetadata(
            timestamp=datetime.now().isoformat(),
            request_id=request_id,
            processing_time_ms=processing_time_ms,
            **(metadata or {})
        )
        
        return cls(
            status=ResponseStatus.SUCCESS,
            data=data,
            message=message or "操作成功",
            metadata=response_metadata,
            pagination=pagination,
            warnings=warnings
        )
    
    @classmethod
    def error_response(cls,
                      error_data: Union[ApiError, ErrorDetail, Exception, str],
                      message: Optional[str] = None,
                      metadata: Optional[Dict[str, Any]] = None,
                      request_id: Optional[str] = None,
                      processing_time_ms: Optional[int] = None,
                      debug_info: Optional[Dict[str, Any]] = None) -> "ApiResponse[None]":
        """创建错误响应"""
        
        response_metadata = ResponseMetadata(
            timestamp=datetime.now().isoformat(),
            request_id=request_id,
            processing_time_ms=processing_time_ms,
            **(metadata or {})
        )
        
        # 处理不同类型的错误
        if isinstance(error_data, ApiError):
            api_error = error_data
        elif isinstance(error_data, ErrorDetail):
            api_error = ApiError.from_error_detail(error_data)
        elif isinstance(error_data, Exception):
            api_error = ApiError(
                code=ErrorCode.INTERNAL_SERVER_ERROR.value,
                message=str(error_data),
                category="system",
                severity="high"
            )
        else:
            api_error = ApiError(
                code=ErrorCode.UNKNOWN_ERROR.value,
                message=str(error_data),
                category="unknown",
                severity="medium"
            )
        
        return cls(
            status=ResponseStatus.ERROR,
            error=api_error,
            message=message or "操作失败",
            metadata=response_metadata,
            debug_info=debug_info
        )
    
    @classmethod
    def error(cls, **kwargs) -> "ApiResponse[None]":
        """Backward compatibility alias for error_response"""
        return cls.error_response(**kwargs)
    
    @classmethod
    def warning(cls,
               data: Optional[T] = None,
               message: Optional[str] = None,
               warnings: Optional[List[str]] = None,
               metadata: Optional[Dict[str, Any]] = None,
               request_id: Optional[str] = None,
               processing_time_ms: Optional[int] = None) -> "ApiResponse[T]":
        """创建警告响应"""
        
        response_metadata = ResponseMetadata(
            timestamp=datetime.now().isoformat(),
            request_id=request_id,
            processing_time_ms=processing_time_ms,
            **(metadata or {})
        )
        
        return cls(
            status=ResponseStatus.WARNING,
            data=data,
            message=message or "操作完成但有警告",
            metadata=response_metadata,
            warnings=warnings
        )
    
    @classmethod
    def partial(cls,
               data: Optional[T] = None,
               message: Optional[str] = None,
               warnings: Optional[List[str]] = None,
               errors: Optional[List[ApiError]] = None,
               metadata: Optional[Dict[str, Any]] = None,
               request_id: Optional[str] = None,
               processing_time_ms: Optional[int] = None) -> "ApiResponse[T]":
        """创建部分成功响应"""
        
        response_metadata = ResponseMetadata(
            timestamp=datetime.now().isoformat(),
            request_id=request_id,
            processing_time_ms=processing_time_ms,
            **(metadata or {})
        )
        
        return cls(
            status=ResponseStatus.PARTIAL,
            data=data,
            message=message or "操作部分成功",
            metadata=response_metadata,
            warnings=warnings
        )


class HealthCheckResponse(BaseModel):
    """健康检查响应"""
    status: str = Field(..., description="健康状态")
    timestamp: str = Field(..., description="检查时间")
    version: str = Field(..., description="版本信息")
    uptime: str = Field(..., description="运行时间")
    components: Dict[str, str] = Field(default_factory=dict, description="组件状态")
    dependencies: Dict[str, str] = Field(default_factory=dict, description="依赖状态")
    metrics: Dict[str, Any] = Field(default_factory=dict, description="性能指标")
    errors: List[str] = Field(default_factory=list, description="错误列表")


class BatchResponse(BaseModel, Generic[T]):
    """批量操作响应"""
    total_items: int = Field(..., description="总项目数")
    successful_items: int = Field(..., description="成功项目数")
    failed_items: int = Field(..., description="失败项目数")
    results: List[ApiResponse[T]] = Field(..., description="结果列表")
    summary: Dict[str, Any] = Field(default_factory=dict, description="汇总信息")
    processing_time_ms: int = Field(..., description="总处理时间")


class StreamResponse(BaseModel):
    """流式响应"""
    event: str = Field(..., description="事件类型")
    data: Optional[Any] = Field(None, description="数据内容")
    timestamp: str = Field(..., description="时间戳")
    sequence: Optional[int] = Field(None, description="序列号")
    metadata: Optional[Dict[str, Any]] = Field(None, description="元数据")


class OperationResult(BaseModel):
    """操作结果"""
    operation: str = Field(..., description="操作名称")
    success: bool = Field(..., description="是否成功")
    result: Optional[Any] = Field(None, description="操作结果")
    error: Optional[ApiError] = Field(None, description="错误信息")
    duration_ms: Optional[int] = Field(None, description="执行时间")
    metadata: Optional[Dict[str, Any]] = Field(None, description="元数据")


class ValidationResponse(BaseModel):
    """验证响应"""
    is_valid: bool = Field(..., description="是否有效")
    errors: List[ValidationErrorDetail] = Field(default_factory=list, description="验证错误")
    warnings: List[str] = Field(default_factory=list, description="警告信息")
    suggestions: List[str] = Field(default_factory=list, description="改进建议")


class AsyncTaskResponse(BaseModel):
    """异步任务响应"""
    task_id: str = Field(..., description="任务ID")
    status: str = Field(..., description="任务状态")
    progress: Optional[float] = Field(None, description="进度百分比", ge=0.0, le=100.0)
    result: Optional[Any] = Field(None, description="任务结果")
    error: Optional[ApiError] = Field(None, description="错误信息")
    created_at: str = Field(..., description="创建时间")
    updated_at: Optional[str] = Field(None, description="更新时间")
    estimated_completion: Optional[str] = Field(None, description="预计完成时间")


class MetricsResponse(BaseModel):
    """指标响应"""
    metrics: Dict[str, Any] = Field(..., description="指标数据")
    period: str = Field(..., description="统计周期")
    start_time: str = Field(..., description="开始时间")
    end_time: str = Field(..., description="结束时间")
    aggregation: str = Field(..., description="聚合方式")
    
    
class SearchResponse(BaseModel, Generic[T]):
    """搜索响应"""
    results: List[T] = Field(..., description="搜索结果")
    total_hits: int = Field(..., description="总命中数")
    query: str = Field(..., description="查询语句")
    facets: Optional[Dict[str, Any]] = Field(None, description="分面信息")
    suggestions: Optional[List[str]] = Field(None, description="搜索建议")
    search_time_ms: int = Field(..., description="搜索耗时")
    pagination: Optional[PaginationInfo] = Field(None, description="分页信息")


# 常用响应类型别名
ListResponse = ApiResponse[List[T]]
DictResponse = ApiResponse[Dict[str, Any]]
StringResponse = ApiResponse[str]
IntResponse = ApiResponse[int]
BoolResponse = ApiResponse[bool]