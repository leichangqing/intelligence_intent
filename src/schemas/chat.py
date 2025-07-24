"""
对话相关的Pydantic数据验证模型
"""
from typing import Dict, List, Optional, Any, Generic, TypeVar
from pydantic import BaseModel, Field, field_validator
from datetime import datetime

T = TypeVar('T')

class DeviceInfo(BaseModel):
    """设备信息"""
    platform: Optional[str] = Field(None, description="平台类型", example="web")
    user_agent: Optional[str] = Field(None, description="用户代理", max_length=500)
    ip_address: Optional[str] = Field(None, description="IP地址")
    screen_resolution: Optional[str] = Field(None, description="屏幕分辨率")
    language: Optional[str] = Field("zh-CN", description="语言偏好")


class ChatContext(BaseModel):
    """对话上下文 - B2B架构优化版"""
    # 前端可以提供的信息
    device_info: Optional[DeviceInfo] = Field(None, description="设备信息")
    location: Optional[Dict[str, Any]] = Field(None, description="位置信息") 
    
    # B2B系统特有字段
    client_system_id: Optional[str] = Field(None, description="客户端系统标识")
    request_trace_id: Optional[str] = Field(None, description="请求追踪ID")
    business_context: Optional[Dict[str, Any]] = Field(None, description="业务上下文")
    
    # 临时会话覆盖（可选，用于特殊场景）
    temp_preferences: Optional[Dict[str, Any]] = Field(None, description="临时偏好覆盖")


class ChatRequest(BaseModel):
    """对话请求"""
    user_id: str = Field(..., description="用户ID", min_length=1, max_length=100)
    input: Optional[str] = Field(None, description="用户输入", min_length=1, max_length=1000)
    session_id: Optional[str] = Field(None, description="会话ID", max_length=50, example="sess_a1b2c3d4e5f6")
    context: Optional[ChatContext] = Field(None, description="对话上下文")
    
    # 向后兼容字段（可选）
    message: Optional[str] = Field(None, description="用户消息（兼容字段）", exclude=True)
    
    @field_validator('input', mode='before')
    @classmethod
    def validate_input(cls, v, info):
        """验证用户输入 - 支持message字段向后兼容"""
        # 如果没有input但有message，使用message
        if not v and info.data and info.data.get('message'):
            v = info.data['message']
        
        # 如果仍然没有值，抛出错误
        if not v:
            raise ValueError('用户输入不能为空（input或message字段必须提供一个）')
            
        if not str(v).strip():
            raise ValueError('用户输入不能为空')
        return str(v).strip()
    
    @field_validator('user_id')
    @classmethod
    def validate_user_id(cls, v):
        """验证用户ID"""
        if not v or not v.strip():
            raise ValueError('用户ID不能为空')
        return v.strip()
    
    def model_post_init(self, __context) -> None:
        """模型初始化后处理"""
        # 确保input字段存在且有值
        if not self.input and hasattr(self, 'message') and self.message:
            object.__setattr__(self, 'input', self.message)


# 向后兼容别名
ChatInteractRequest = ChatRequest


class SlotInfo(BaseModel):
    """槽位信息 - 支持多轮对话的完整槽位结构"""
    name: str = Field(..., description="槽位名称")
    original_text: Optional[str] = Field(None, description="原始文本")
    extracted_value: Any = Field(..., description="提取的值")
    normalized_value: Any = Field(..., description="标准化后的值")
    confidence: Optional[float] = Field(None, description="置信度", ge=0.0, le=1.0)
    extraction_method: Optional[str] = Field(None, description="提取方法", example="user_input")
    validation: Optional[Dict[str, Any]] = Field(None, description="验证状态")
    is_confirmed: Optional[bool] = Field(False, description="是否已确认")
    
    # 向后兼容字段
    value: Optional[Any] = Field(None, description="槽位值（兼容字段）")
    source: Optional[str] = Field(None, description="数据来源（兼容字段）")
    is_validated: Optional[bool] = Field(True, description="是否已验证（兼容字段）")
    validation_error: Optional[str] = Field(None, description="验证错误信息（兼容字段）")
    
    def model_post_init(self, __context) -> None:
        """模型初始化后处理 - 确保向后兼容"""
        if self.value is None and self.normalized_value is not None:
            self.value = self.normalized_value
        if self.source is None and self.extraction_method is not None:
            self.source = self.extraction_method


class IntentCandidate(BaseModel):
    """意图候选"""
    intent_name: str = Field(..., description="意图名称")
    display_name: str = Field(..., description="显示名称")
    confidence: float = Field(..., description="置信度", ge=0.0, le=1.0)
    description: Optional[str] = Field(None, description="意图描述")


class ApiResultData(BaseModel):
    """API调用结果数据"""
    order_id: Optional[str] = Field(None, description="订单ID")
    balance: Optional[float] = Field(None, description="余额")
    flight_info: Optional[Dict[str, Any]] = Field(None, description="航班信息")
    success_message: Optional[str] = Field(None, description="成功消息")
    error_code: Optional[str] = Field(None, description="错误代码")


class SessionMetadata(BaseModel):
    """会话元数据"""
    total_turns: int = Field(0, description="总对话轮次")
    session_duration_seconds: int = Field(0, description="会话持续时间(秒)")
    context_history: Optional[List[Dict[str, Any]]] = Field(None, description="上下文历史")


class ChatResponse(BaseModel):
    """对话响应 - 支持多轮对话的完整响应结构"""
    response: str = Field(..., description="系统响应文本")
    session_id: str = Field(..., description="会话ID")
    conversation_turn: int = Field(1, description="当前对话轮次")
    intent: Optional[str] = Field(None, description="识别的意图名称")
    confidence: float = Field(0.0, description="置信度", ge=0.0, le=1.0)
    slots: Dict[str, SlotInfo] = Field(default_factory=dict, description="已填充的槽位")
    status: str = Field(..., description="处理状态")
    response_type: str = Field(..., description="响应类型")
    next_action: str = Field("none", description="下一步操作")
    
    # 可选字段
    ambiguous_intents: Optional[List[IntentCandidate]] = Field(None, description="歧义意图候选")
    missing_slots: Optional[List[str]] = Field(None, description="缺失的槽位")
    validation_errors: Optional[Dict[str, str]] = Field(None, description="验证错误")
    api_result: Optional[ApiResultData] = Field(None, description="API调用结果")
    suggestions: Optional[List[str]] = Field(None, description="建议操作")
    
    # 会话元数据
    session_metadata: Optional[SessionMetadata] = Field(None, description="会话元数据")
    
    # 元数据
    processing_time_ms: Optional[int] = Field(None, description="处理时间(毫秒)")
    request_id: Optional[str] = Field(None, description="请求ID")


class DisambiguationRequest(BaseModel):
    """歧义解决请求"""
    conversation_id: int = Field(..., description="对话ID", gt=0)
    user_choice: str = Field(..., description="用户选择", min_length=1, max_length=100)
    
    @field_validator('user_choice')
    @classmethod
    def validate_user_choice(cls, v):
        """验证用户选择"""
        if not v or not v.strip():
            raise ValueError('用户选择不能为空')
        return v.strip()


class DisambiguationResponse(BaseModel):
    """歧义解决响应"""
    resolved_intent: Optional[str] = Field(None, description="解决的意图")
    display_name: Optional[str] = Field(None, description="意图显示名称")
    next_step: str = Field(..., description="下一步操作")
    message: Optional[str] = Field(None, description="提示消息")




class ChatSessionInfo(BaseModel):
    """会话信息"""
    session_id: str = Field(..., description="会话ID")
    user_id: str = Field(..., description="用户ID")
    current_intent: Optional[str] = Field(None, description="当前意图")
    session_state: str = Field(..., description="会话状态")
    created_at: datetime = Field(..., description="创建时间")
    expires_at: Optional[datetime] = Field(None, description="过期时间")
    turn_count: int = Field(0, description="对话轮数")


class ConversationHistory(BaseModel):
    """对话历史"""
    conversation_id: int = Field(..., description="对话ID")
    user_input: str = Field(..., description="用户输入")
    response: str = Field(..., description="系统响应")
    intent_recognized: Optional[str] = Field(None, description="识别的意图")
    confidence_score: Optional[float] = Field(None, description="置信度")
    response_type: Optional[str] = Field(None, description="响应类型")
    status: Optional[str] = Field(None, description="处理状态")
    processing_time_ms: Optional[int] = Field(None, description="处理时间")
    created_at: datetime = Field(..., description="创建时间")


class BatchChatRequest(BaseModel):
    """批量对话请求"""
    requests: List[ChatRequest] = Field(..., description="请求列表", max_items=10)
    
    @field_validator('requests')
    @classmethod
    def validate_requests(cls, v):
        """验证请求列表"""
        if not v:
            raise ValueError('请求列表不能为空')
        if len(v) > 10:
            raise ValueError('单次批量请求不能超过10个')
        return v


class BatchChatResponse(BaseModel):
    """批量对话响应"""
    responses: List[ChatResponse] = Field(..., description="响应列表")
    total_count: int = Field(..., description="总数")
    success_count: int = Field(..., description="成功数")
    error_count: int = Field(..., description="错误数")
    processing_time_ms: int = Field(..., description="总处理时间")


class ChatMetrics(BaseModel):
    """对话指标"""
    total_conversations: int = Field(0, description="总对话数")
    successful_conversations: int = Field(0, description="成功对话数")
    failed_conversations: int = Field(0, description="失败对话数")
    average_processing_time: float = Field(0.0, description="平均处理时间")
    average_confidence: float = Field(0.0, description="平均置信度")
    top_intents: List[Dict[str, Any]] = Field(default_factory=list, description="热门意图")
    response_type_distribution: Dict[str, int] = Field(default_factory=dict, description="响应类型分布")


class ConversationAnalytics(BaseModel):
    """对话分析"""
    date_range: str = Field(..., description="日期范围")
    metrics: ChatMetrics = Field(..., description="指标数据")
    charts: Dict[str, Any] = Field(default_factory=dict, description="图表数据")
    insights: List[str] = Field(default_factory=list, description="洞察分析")


class StreamChatRequest(BaseModel):
    """流式聊天请求"""
    user_id: str = Field(..., description="用户ID", min_length=1, max_length=100)
    input: str = Field(..., description="用户输入", min_length=1, max_length=1000)
    context: Optional[Dict[str, Any]] = Field(None, description="对话上下文")
    stream_config: Optional[Dict[str, Any]] = Field(None, description="流式配置")
    
    @field_validator('input')
    @classmethod
    def validate_input(cls, v):
        if not v or not v.strip():
            raise ValueError('用户输入不能为空')
        return v.strip()


class StreamChatResponse(BaseModel):
    """流式聊天响应"""
    response: str = Field(..., description="系统响应文本")
    intent: Optional[str] = Field(None, description="识别的意图名称")
    confidence: float = Field(0.0, description="置信度", ge=0.0, le=1.0)
    slots: Dict[str, Any] = Field(default_factory=dict, description="已填充的槽位")
    status: str = Field(..., description="处理状态")
    response_type: str = Field(..., description="响应类型")
    next_action: str = Field("none", description="下一步操作")
    
    # 流式特有字段
    is_streaming: bool = Field(False, description="是否为流式响应")
    chunk_count: Optional[int] = Field(None, description="分块数量")
    stream_id: Optional[str] = Field(None, description="流ID")
    
    # 可选字段
    ambiguous_intents: Optional[List[Dict[str, Any]]] = Field(None, description="歧义意图候选")
    missing_slots: Optional[List[str]] = Field(None, description="缺失的槽位")
    api_result: Optional[Dict[str, Any]] = Field(None, description="API调用结果")
    error_message: Optional[str] = Field(None, description="错误消息")
    
    # 元数据
    processing_time_ms: Optional[int] = Field(None, description="处理时间(毫秒)")
    request_id: Optional[str] = Field(None, description="请求ID")
    timestamp: Optional[str] = Field(None, description="时间戳")


class SessionManagementRequest(BaseModel):
    """会话管理请求"""
    user_id: str = Field(..., description="用户ID", min_length=1, max_length=100)
    action: str = Field(..., description="操作类型", pattern=r'^(create|update|delete|refresh)$')
    session_id: Optional[str] = Field(None, description="会话ID")
    initial_context: Optional[Dict[str, Any]] = Field(None, description="初始上下文")
    expiry_hours: Optional[int] = Field(24, description="过期时间(小时)", ge=1, le=168)
    
    @field_validator('action')
    @classmethod
    def validate_action(cls, v):
        if v not in ['create', 'update', 'delete', 'refresh']:
            raise ValueError('无效的操作类型')
        return v


class ContextUpdateRequest(BaseModel):
    """上下文更新请求"""
    session_id: str = Field(..., description="会话ID", min_length=1)
    context_updates: Dict[str, Any] = Field(..., description="上下文更新内容")
    merge_strategy: str = Field("merge", description="合并策略", pattern=r'^(merge|replace|append)$')
    preserve_history: bool = Field(True, description="是否保留历史")
    
    @field_validator('merge_strategy')
    @classmethod
    def validate_merge_strategy(cls, v):
        if v not in ['merge', 'replace', 'append']:
            raise ValueError('无效的合并策略')
        return v


class SessionAnalyticsRequest(BaseModel):
    """会话分析请求"""
    session_id: str = Field(..., description="会话ID")
    metrics: List[str] = Field(default_factory=list, description="指标类型")
    date_range: Optional[str] = Field(None, description="日期范围")
    include_details: bool = Field(False, description="是否包含详细信息")


class EnhancedChatMetrics(BaseModel):
    """增强聊天指标"""
    total_requests: int = Field(0, description="总请求数")
    streaming_requests: int = Field(0, description="流式请求数")
    batch_requests: int = Field(0, description="批量请求数")
    average_stream_chunks: float = Field(0.0, description="平均流式分块数")
    session_count: int = Field(0, description="活跃会话数")
    context_update_count: int = Field(0, description="上下文更新次数")
    error_rate: float = Field(0.0, description="错误率")
    p95_response_time: float = Field(0.0, description="95%响应时间")
    throughput_qps: float = Field(0.0, description="吞吐量(QPS)")


class QualityMetrics(BaseModel):
    """质量指标"""
    user_satisfaction_score: float = Field(0.0, description="用户满意度分数", ge=0.0, le=1.0)
    intent_accuracy: float = Field(0.0, description="意图识别准确率", ge=0.0, le=1.0)
    slot_filling_accuracy: float = Field(0.0, description="槽位填充准确率", ge=0.0, le=1.0)
    response_relevance: float = Field(0.0, description="响应相关性", ge=0.0, le=1.0)
    conversation_completion_rate: float = Field(0.0, description="对话完成率", ge=0.0, le=1.0)
    average_turns_to_completion: float = Field(0.0, description="平均完成轮数")


class PerformanceMetrics(BaseModel):
    """性能指标"""
    average_response_time: float = Field(0.0, description="平均响应时间(ms)")
    p50_response_time: float = Field(0.0, description="50%响应时间(ms)")
    p95_response_time: float = Field(0.0, description="95%响应时间(ms)")
    p99_response_time: float = Field(0.0, description="99%响应时间(ms)")
    throughput: float = Field(0.0, description="吞吐量(requests/second)")
    concurrent_users: int = Field(0, description="并发用户数")
    memory_usage: float = Field(0.0, description="内存使用率")
    cpu_usage: float = Field(0.0, description="CPU使用率")


class ChatHealthStatus(BaseModel):
    """聊天健康状态"""
    status: str = Field(..., description="健康状态")
    timestamp: str = Field(..., description="检查时间")
    version: str = Field(..., description="版本号")
    uptime: str = Field(..., description="运行时间")
    features: Dict[str, bool] = Field(default_factory=dict, description="功能状态")
    performance: PerformanceMetrics = Field(..., description="性能指标")
    quality: QualityMetrics = Field(..., description="质量指标")
    dependencies: Dict[str, str] = Field(default_factory=dict, description="依赖状态")
    errors: List[str] = Field(default_factory=list, description="错误列表")