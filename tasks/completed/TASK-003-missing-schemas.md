# 完善缺失的schema文件

## 任务信息

- **任务ID**: TASK-003
- **任务名称**: 完善缺失的schema文件
- **创建时间**: 2024-12-01
- **最后更新**: 2024-12-01
- **状态**: completed
- **优先级**: P0
- **预估工时**: 1小时
- **实际工时**: 0.5小时

## 任务描述

### 背景
在流程图一致性验证中发现`src.schemas.common`模块不存在，导致聊天API无法正常导入。需要创建缺失的schema文件，确保API层可以正常工作。

错误信息：
```
No module named 'src.schemas.common'
```

### 目标
- 创建缺失的`src/schemas/common.py`文件
- 定义通用的数据结构和响应格式
- 确保API层可以正常导入所需的schema
- 为后续API开发提供完整的类型定义

### 范围
**包含**:
- 创建`src/schemas/common.py`
- 定义通用响应格式
- 定义基础数据类型
- 完善现有schema文件

**不包含**:
- 复杂业务逻辑schema（后续任务处理）
- API具体实现（仅schema定义）

## 技术要求

### 依赖项
- [ ] TASK-002 (Pydantic兼容性) - 需要Pydantic正常工作

### 涉及文件
- `src/schemas/common.py` - 新建
- `src/schemas/__init__.py` - 可能需要创建
- `src/schemas/chat.py` - 可能需要补完

### 需要的通用Schema
基于API设计文档和现有代码分析：

1. **响应格式**:
   - BaseResponse
   - SuccessResponse
   - ErrorResponse
   - PaginationResponse

2. **通用数据类型**:
   - TimestampMixin
   - IDMixin
   - StatusEnum
   - PriorityEnum

3. **验证规则**:
   - 常用的验证器
   - 自定义字段类型

## 实现计划

### 步骤分解
1. [ ] 分析现有API文件中使用的schema
2. [ ] 创建`src/schemas/__init__.py`（如果不存在）
3. [ ] 创建`src/schemas/common.py`
4. [ ] 定义基础响应格式
5. [ ] 定义通用数据类型和枚举
6. [ ] 检查并补完`src/schemas/chat.py`
7. [ ] 测试schema导入和使用

### 验收标准
- [ ] `from src.schemas.common import BaseResponse`成功执行
- [ ] 所有定义的schema类可以正常实例化
- [ ] API文件可以正常导入所需schema
- [ ] schema类型注解正确
- [ ] 支持JSON序列化和反序列化

## 代码实现

### src/schemas/__init__.py
```python
"""
Schema包初始化文件
"""
from .common import (
    BaseResponse,
    SuccessResponse, 
    ErrorResponse,
    PaginationResponse,
    TimestampMixin,
    IDMixin
)
from .chat import (
    ChatRequest,
    ChatResponse,
    SlotInfo,
    IntentCandidate
)

__all__ = [
    # Common schemas
    "BaseResponse",
    "SuccessResponse", 
    "ErrorResponse",
    "PaginationResponse",
    "TimestampMixin",
    "IDMixin",
    
    # Chat schemas
    "ChatRequest",
    "ChatResponse", 
    "SlotInfo",
    "IntentCandidate"
]
```

### src/schemas/common.py
```python
"""
通用Schema定义
"""
from datetime import datetime
from typing import Optional, Any, Dict, List, Generic, TypeVar
from enum import Enum
from pydantic import BaseModel, Field

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
```

## 测试计划

### Schema导入测试
```python
def test_schema_imports():
    """测试schema正常导入"""
    try:
        from src.schemas.common import (
            BaseResponse, 
            SuccessResponse,
            ErrorResponse,
            StatusEnum
        )
        from src.schemas import BaseResponse as ImportedResponse
        
        assert BaseResponse == ImportedResponse
        print("✅ Schema imports successful")
        return True
    except ImportError as e:
        print(f"❌ Schema import failed: {e}")
        return False
```

### Schema实例化测试
```python
def test_schema_instantiation():
    """测试schema实例化"""
    from src.schemas.common import SuccessResponse, ErrorResponse, StatusEnum
    
    # 成功响应测试
    success_resp = SuccessResponse[dict](
        message="操作成功",
        data={"result": "test"}
    )
    assert success_resp.status == "success"
    
    # 错误响应测试
    error_resp = ErrorResponse(
        message="操作失败",
        error_code="INVALID_INPUT"
    )
    assert error_resp.status == "error"
    
    print("✅ Schema instantiation test passed")
```

### JSON序列化测试
```python
def test_schema_serialization():
    """测试JSON序列化"""
    from src.schemas.common import SuccessResponse
    
    response = SuccessResponse[str](
        message="测试响应",
        data="测试数据"
    )
    
    # 测试序列化
    json_data = response.model_dump()
    assert "status" in json_data
    assert "data" in json_data
    
    # 测试反序列化
    new_response = SuccessResponse[str](**json_data)
    assert new_response.data == "测试数据"
    
    print("✅ Schema serialization test passed")
```

## 参考资料

- [Pydantic模型定义](https://docs.pydantic.dev/latest/concepts/models/)
- [FastAPI响应模型](https://fastapi.tiangolo.com/tutorial/response-model/)
- [API设计最佳实践](https://docs.microsoft.com/en-us/azure/architecture/best-practices/api-design)

## 风险评估

### 低风险
- Schema定义相对简单
- 基于成熟的Pydantic库
- 不涉及复杂业务逻辑

### 潜在问题
1. **类型注解复杂性** - 泛型类型可能需要调试
2. **循环导入** - schema之间可能存在循环依赖
3. **向后兼容** - 后续修改schema可能影响现有代码

### 缓解措施
1. 从简单schema开始，逐步增加复杂性
2. 仔细设计导入结构，避免循环依赖
3. 设计schema时考虑扩展性

---

**任务负责人**: Claude
**审核人**: 开发者

**注意**: 此任务为API层提供基础类型定义，是后续API开发的前提。