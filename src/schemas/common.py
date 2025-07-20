"""
通用Schema定义
"""
from datetime import datetime
from typing import Optional, Any, Dict, List, Generic, TypeVar
from enum import Enum
from pydantic import BaseModel, Field, ConfigDict

# 泛型类型变量
T = TypeVar('T')

class StatusEnum(str, Enum):
    """通用状态枚举"""
    PENDING = "pending"
    IN_PROGRESS = "in_progress" 
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

class PriorityEnum(str, Enum):
    """优先级枚举"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"

class ResponseStatusEnum(str, Enum):
    """响应状态枚举"""
    SUCCESS = "success"
    ERROR = "error"
    WARNING = "warning"

# Mixin类
class TimestampMixin(BaseModel):
    """时间戳混入类"""
    created_at: Optional[datetime] = Field(default_factory=datetime.now)
    updated_at: Optional[datetime] = Field(default_factory=datetime.now)

class IDMixin(BaseModel):
    """ID混入类"""
    id: Optional[str] = Field(None, description="唯一标识符")

# 基础响应类
class BaseResponse(BaseModel):
    """基础响应格式"""
    status: ResponseStatusEnum = Field(..., description="响应状态")
    message: str = Field("", description="响应消息")
    timestamp: datetime = Field(default_factory=datetime.now, description="响应时间")
    request_id: Optional[str] = Field(None, description="请求ID")

class SuccessResponse(BaseResponse, Generic[T]):
    """成功响应格式"""
    status: ResponseStatusEnum = Field(ResponseStatusEnum.SUCCESS, description="成功状态")
    data: Optional[T] = Field(None, description="响应数据")

class ErrorResponse(BaseResponse):
    """错误响应格式"""
    status: ResponseStatusEnum = Field(ResponseStatusEnum.ERROR, description="错误状态") 
    error_code: Optional[str] = Field(None, description="错误代码")
    error_details: Optional[Dict[str, Any]] = Field(None, description="错误详情")

# 标准响应格式（兼容现有API）
class StandardResponse(BaseModel, Generic[T]):
    """标准响应格式 - 兼容现有API"""
    success: bool = Field(..., description="操作是否成功")
    message: str = Field("", description="响应消息")
    data: Optional[Any] = Field(None, description="响应数据")
    error: Optional[str] = Field(None, description="错误信息")
    timestamp: datetime = Field(default_factory=datetime.now, description="响应时间")
    request_id: Optional[str] = Field(None, description="请求ID")
    
    model_config = ConfigDict(
        json_encoders={
            datetime: lambda v: v.isoformat()
        }
    )

class PaginationMeta(BaseModel):
    """分页元信息"""
    page: int = Field(1, ge=1, description="当前页码")
    page_size: int = Field(20, ge=1, le=100, description="每页大小")
    total: int = Field(0, ge=0, description="总记录数")
    total_pages: int = Field(0, ge=0, description="总页数")
    has_next: bool = Field(False, description="是否有下一页")
    has_prev: bool = Field(False, description="是否有上一页")

class PaginationResponse(SuccessResponse[List[T]]):
    """分页响应格式"""
    meta: PaginationMeta = Field(..., description="分页信息")

# 验证相关
class ValidationError(BaseModel):
    """验证错误"""
    field: str = Field(..., description="字段名")
    message: str = Field(..., description="错误消息")
    value: Optional[Any] = Field(None, description="错误值")

# 健康检查
class HealthCheckResponse(BaseModel):
    """健康检查响应"""
    status: str = Field("healthy", description="健康状态")
    version: str = Field("1.0.0", description="版本号")
    timestamp: datetime = Field(default_factory=datetime.now)
    services: Dict[str, str] = Field(default_factory=dict, description="服务状态")

# API信息
class APIInfo(BaseModel):
    """API信息"""
    name: str = Field(..., description="API名称")
    version: str = Field(..., description="API版本")
    description: str = Field("", description="API描述") 
    base_url: str = Field(..., description="基础URL")

# 通用列表响应
class ListResponse(BaseModel, Generic[T]):
    """通用列表响应"""
    items: List[T] = Field(..., description="列表项")
    total: int = Field(..., description="总数")
    page: Optional[int] = Field(None, description="页码")
    page_size: Optional[int] = Field(None, description="页大小")

# 操作结果
class OperationResult(BaseModel):
    """操作结果"""
    success: bool = Field(..., description="是否成功")
    message: str = Field("", description="结果消息")
    data: Optional[Any] = Field(None, description="结果数据")
    errors: Optional[List[str]] = Field(None, description="错误列表")

# 文件信息
class FileInfo(BaseModel):
    """文件信息"""
    filename: str = Field(..., description="文件名")
    size: int = Field(..., description="文件大小")
    content_type: str = Field(..., description="内容类型")
    upload_time: datetime = Field(default_factory=datetime.now, description="上传时间")
    url: Optional[str] = Field(None, description="访问URL")

# 配置信息
class ConfigInfo(BaseModel):
    """配置信息"""
    key: str = Field(..., description="配置键")
    value: Any = Field(..., description="配置值")
    description: Optional[str] = Field(None, description="配置描述")
    category: Optional[str] = Field(None, description="配置分类")
    is_readonly: bool = Field(False, description="是否只读")