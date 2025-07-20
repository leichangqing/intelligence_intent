"""
歧义解决相关的Pydantic数据验证模型 (TASK-035)
定义歧义检测、解决和交互的数据结构
"""
from typing import Dict, List, Optional, Any, Union
from pydantic import BaseModel, Field, field_validator
from datetime import datetime
from enum import Enum


class AmbiguityResolutionStatus(str, Enum):
    """歧义解决状态"""
    NO_AMBIGUITY = "no_ambiguity"                   # 无歧义
    PENDING_USER_INPUT = "pending_user_input"       # 等待用户输入
    PENDING_CLARIFICATION = "pending_clarification" # 等待澄清
    RESOLVED = "resolved"                           # 已解决
    FAILED = "failed"                              # 解决失败
    TIMEOUT = "timeout"                            # 超时


class AmbiguityDetectionRequest(BaseModel):
    """歧义检测请求"""
    user_id: str = Field(..., description="用户ID", min_length=1, max_length=100)
    user_input: str = Field(..., description="用户输入", min_length=1, max_length=1000)
    candidates: List[Dict[str, Any]] = Field(..., description="候选意图列表", min_items=1)
    conversation_context: Optional[Dict[str, Any]] = Field(None, description="对话上下文")
    force_redetect: bool = Field(False, description="强制重新检测")
    detection_settings: Optional[Dict[str, Any]] = Field(None, description="检测设置")
    
    @field_validator('user_input')
    @classmethod
    def validate_user_input(cls, v):
        if not v or not v.strip():
            raise ValueError('用户输入不能为空')
        return v.strip()
    
    @field_validator('candidates')
    @classmethod
    def validate_candidates(cls, v):
        if not v:
            raise ValueError('候选意图列表不能为空')
        
        for candidate in v:
            if 'intent_name' not in candidate:
                raise ValueError('候选意图必须包含intent_name字段')
            if 'confidence' not in candidate:
                raise ValueError('候选意图必须包含confidence字段')
        
        return v


class AmbiguitySignal(BaseModel):
    """歧义信号"""
    type: str = Field(..., description="歧义类型")
    level: str = Field(..., description="歧义级别")
    score: float = Field(..., description="歧义得分", ge=0.0, le=1.0)
    evidence: Dict[str, Any] = Field(..., description="证据信息")
    explanation: str = Field(..., description="解释说明")
    confidence: float = Field(..., description="信号置信度", ge=0.0, le=1.0)


class AmbiguityDetectionResponse(BaseModel):
    """歧义检测响应"""
    request_id: str = Field(..., description="请求ID")
    user_id: str = Field(..., description="用户ID")
    is_ambiguous: bool = Field(..., description="是否存在歧义")
    ambiguity_score: float = Field(..., description="歧义得分", ge=0.0, le=1.0)
    primary_ambiguity_type: str = Field(..., description="主要歧义类型")
    ambiguity_signals: List[AmbiguitySignal] = Field(..., description="歧义信号列表")
    candidates: List[Dict[str, Any]] = Field(..., description="候选意图")
    recommended_action: str = Field(..., description="推荐行动")
    analysis_metadata: Dict[str, Any] = Field(..., description="分析元数据")
    processing_time_ms: int = Field(..., description="处理时间(毫秒)")
    timestamp: str = Field(..., description="时间戳")
    cached: bool = Field(False, description="是否来自缓存")


class DisambiguationRequest(BaseModel):
    """歧义解决请求"""
    user_id: str = Field(..., description="用户ID", min_length=1, max_length=100)
    user_input: str = Field(..., description="用户输入", min_length=1, max_length=1000)
    candidates: List[Dict[str, Any]] = Field(..., description="候选意图列表", min_items=1)
    conversation_context: Optional[Dict[str, Any]] = Field(None, description="对话上下文")
    user_preferences: Optional[Dict[str, Any]] = Field(None, description="用户偏好")
    missing_slots: Optional[List[str]] = Field(None, description="缺失的槽位")
    conflicting_values: Optional[Dict[str, List[Any]]] = Field(None, description="冲突的值")
    resolution_strategy: str = Field("interactive", description="解决策略")
    timeout_seconds: int = Field(300, description="超时时间(秒)", ge=30, le=3600)
    
    @field_validator('resolution_strategy')
    @classmethod
    def validate_resolution_strategy(cls, v):
        valid_strategies = ["interactive", "automatic", "guided"]
        if v not in valid_strategies:
            raise ValueError(f'解决策略必须是: {", ".join(valid_strategies)}')
        return v


class ClarificationQuestion(BaseModel):
    """澄清问题"""
    question: str = Field(..., description="澄清问题文本")
    type: str = Field(..., description="澄清类型")
    style: str = Field(..., description="澄清风格")
    suggested_values: List[str] = Field(default_factory=list, description="建议值")
    expected_response_type: str = Field(..., description="预期响应类型")
    urgency: float = Field(..., description="紧急度", ge=0.0, le=1.0)
    follow_up_questions: List[str] = Field(default_factory=list, description="后续问题")


class DisambiguationResponse(BaseModel):
    """歧义解决响应"""
    session_id: str = Field(..., description="会话ID")
    user_id: str = Field(..., description="用户ID")
    status: AmbiguityResolutionStatus = Field(..., description="解决状态")
    resolved_intent: Optional[str] = Field(None, description="解决的意图")
    confidence: float = Field(..., description="置信度", ge=0.0, le=1.0)
    resolution_method: str = Field(..., description="解决方法")
    clarification_question: Optional[ClarificationQuestion] = Field(None, description="澄清问题")
    suggested_responses: List[str] = Field(default_factory=list, description="建议响应")
    analysis_summary: Dict[str, Any] = Field(..., description="分析摘要")
    processing_time_ms: int = Field(..., description="处理时间(毫秒)")
    timestamp: str = Field(..., description="时间戳")


class InteractiveDisambiguationRequest(BaseModel):
    """交互式歧义解决请求"""
    user_response: str = Field(..., description="用户响应", min_length=1, max_length=500)
    response_type: str = Field("text", description="响应类型")
    context_session_id: Optional[str] = Field(None, description="上下文会话ID")
    update_context: bool = Field(True, description="是否更新上下文")
    additional_context: Optional[Dict[str, Any]] = Field(None, description="额外上下文")
    
    @field_validator('response_type')
    @classmethod
    def validate_response_type(cls, v):
        valid_types = ["text", "intent_selection", "confirmation", "slot_value"]
        if v not in valid_types:
            raise ValueError(f'响应类型必须是: {", ".join(valid_types)}')
        return v


class InteractiveDisambiguationResponse(BaseModel):
    """交互式歧义解决响应"""
    session_id: str = Field(..., description="会话ID")
    user_id: str = Field(..., description="用户ID")
    status: AmbiguityResolutionStatus = Field(..., description="解决状态")
    resolved_intent: Optional[str] = Field(None, description="解决的意图")
    confidence: float = Field(..., description="置信度", ge=0.0, le=1.0)
    resolution_explanation: str = Field(..., description="解决说明")
    next_steps: List[str] = Field(default_factory=list, description="下一步操作")
    context_updates: Dict[str, Any] = Field(default_factory=dict, description="上下文更新")
    follow_up_needed: bool = Field(..., description="是否需要后续处理")
    follow_up_question: Optional[str] = Field(None, description="后续问题")
    processing_time_ms: int = Field(..., description="处理时间(毫秒)")
    timestamp: str = Field(..., description="时间戳")


class AmbiguitySessionRequest(BaseModel):
    """歧义会话请求"""
    user_id: str = Field(..., description="用户ID", min_length=1, max_length=100)
    session_type: str = Field("disambiguation", description="会话类型")
    initial_context: Optional[Dict[str, Any]] = Field(None, description="初始上下文")
    preferences: Optional[Dict[str, Any]] = Field(None, description="用户偏好")
    metadata: Optional[Dict[str, Any]] = Field(None, description="元数据")
    
    @field_validator('session_type')
    @classmethod
    def validate_session_type(cls, v):
        valid_types = ["disambiguation", "clarification", "guided_resolution"]
        if v not in valid_types:
            raise ValueError(f'会话类型必须是: {", ".join(valid_types)}')
        return v


class AmbiguitySessionResponse(BaseModel):
    """歧义会话响应"""
    session_id: str = Field(..., description="会话ID")
    user_id: str = Field(..., description="用户ID")
    status: str = Field(..., description="会话状态")
    created_at: str = Field(..., description="创建时间")
    expires_at: float = Field(..., description="过期时间戳")
    session_capabilities: Dict[str, bool] = Field(..., description="会话能力")


class DisambiguationHistoryItem(BaseModel):
    """歧义解决历史项"""
    session_id: str = Field(..., description="会话ID")
    created_at: str = Field(..., description="创建时间")
    status: str = Field(..., description="状态")
    resolved_intent: Optional[str] = Field(None, description="解决的意图")
    original_input: Optional[str] = Field(None, description="原始输入")
    resolution_confidence: Optional[float] = Field(None, description="解决置信度")
    interaction_count: int = Field(0, description="交互次数")


class DisambiguationHistoryResponse(BaseModel):
    """歧义解决历史响应"""
    user_id: str = Field(..., description="用户ID")
    total_sessions: int = Field(..., description="总会话数")
    sessions: List[DisambiguationHistoryItem] = Field(..., description="会话列表")
    pagination: Dict[str, Any] = Field(..., description="分页信息")
    statistics: Dict[str, Any] = Field(..., description="统计信息")


class SmartSuggestion(BaseModel):
    """智能建议"""
    type: str = Field(..., description="建议类型")
    value: str = Field(..., description="建议值")
    display_name: Optional[str] = Field(None, description="显示名称")
    confidence: float = Field(..., description="置信度", ge=0.0, le=1.0)
    reasoning: str = Field(..., description="推理说明")
    metadata: Optional[Dict[str, Any]] = Field(None, description="元数据")


class SmartSuggestionResponse(BaseModel):
    """智能建议响应"""
    session_id: str = Field(..., description="会话ID")
    suggestion_type: str = Field(..., description="建议类型")
    suggestions: List[SmartSuggestion] = Field(..., description="建议列表")
    confidence_scores: List[float] = Field(..., description="置信度分数")
    reasoning: List[str] = Field(..., description="推理说明")
    generated_at: str = Field(..., description="生成时间")


class AmbiguityAnalyticsResponse(BaseModel):
    """歧义分析响应"""
    total_detections: int = Field(0, description="总检测数")
    ambiguous_detections: int = Field(0, description="歧义检测数")
    resolution_success_rate: float = Field(0.0, description="解决成功率", ge=0.0, le=1.0)
    average_resolution_time: float = Field(0.0, description="平均解决时间(秒)")
    top_ambiguity_types: List[Dict[str, Any]] = Field(default_factory=list, description="主要歧义类型")
    clarification_effectiveness: Dict[str, Any] = Field(default_factory=dict, description="澄清有效性")
    system_performance: Dict[str, Any] = Field(default_factory=dict, description="系统性能")
    trends: Dict[str, Any] = Field(default_factory=dict, description="趋势数据")
    generated_at: str = Field(..., description="生成时间")


class BatchAmbiguityDetectionRequest(BaseModel):
    """批量歧义检测请求"""
    requests: List[AmbiguityDetectionRequest] = Field(..., description="检测请求列表", max_items=50)
    batch_id: Optional[str] = Field(None, description="批次ID")
    parallel_processing: bool = Field(True, description="是否并行处理")
    
    @field_validator('requests')
    @classmethod
    def validate_requests(cls, v):
        if not v:
            raise ValueError('检测请求列表不能为空')
        if len(v) > 50:
            raise ValueError('单次批量检测不能超过50个请求')
        return v


class BatchAmbiguityDetectionResponse(BaseModel):
    """批量歧义检测响应"""
    batch_id: str = Field(..., description="批次ID")
    total_requests: int = Field(..., description="总请求数")
    successful_detections: int = Field(..., description="成功检测数")
    failed_detections: int = Field(..., description="失败检测数")
    results: List[Union[AmbiguityDetectionResponse, Dict[str, Any]]] = Field(..., description="检测结果")
    processing_time_ms: int = Field(..., description="总处理时间(毫秒)")
    timestamp: str = Field(..., description="时间戳")


class AmbiguityResolutionConfig(BaseModel):
    """歧义解决配置"""
    detection_threshold: float = Field(0.5, description="检测阈值", ge=0.0, le=1.0)
    auto_resolution_threshold: float = Field(0.8, description="自动解决阈值", ge=0.0, le=1.0)
    max_clarification_rounds: int = Field(3, description="最大澄清轮数", ge=1, le=10)
    session_timeout_minutes: int = Field(30, description="会话超时时间(分钟)", ge=5, le=120)
    enable_smart_suggestions: bool = Field(True, description="启用智能建议")
    enable_context_learning: bool = Field(True, description="启用上下文学习")
    clarification_style: str = Field("adaptive", description="澄清风格")
    user_preference_weight: float = Field(0.3, description="用户偏好权重", ge=0.0, le=1.0)


class AmbiguityResolutionMetrics(BaseModel):
    """歧义解决指标"""
    detection_accuracy: float = Field(0.0, description="检测准确率", ge=0.0, le=1.0)
    resolution_success_rate: float = Field(0.0, description="解决成功率", ge=0.0, le=1.0)
    user_satisfaction_score: float = Field(0.0, description="用户满意度", ge=0.0, le=1.0)
    average_clarification_rounds: float = Field(0.0, description="平均澄清轮数")
    response_time_p95: float = Field(0.0, description="95%响应时间(毫秒)")
    false_positive_rate: float = Field(0.0, description="误报率", ge=0.0, le=1.0)
    false_negative_rate: float = Field(0.0, description="漏报率", ge=0.0, le=1.0)
    context_utilization_rate: float = Field(0.0, description="上下文利用率", ge=0.0, le=1.0)


class AmbiguityResolutionHealthCheck(BaseModel):
    """歧义解决健康检查"""
    status: str = Field(..., description="健康状态")
    timestamp: str = Field(..., description="检查时间")
    components: Dict[str, str] = Field(..., description="组件状态")
    metrics: AmbiguityResolutionMetrics = Field(..., description="性能指标")
    active_sessions: int = Field(0, description="活跃会话数")
    error_rate: float = Field(0.0, description="错误率", ge=0.0, le=1.0)
    dependencies: Dict[str, str] = Field(default_factory=dict, description="依赖状态")
    recommendations: List[str] = Field(default_factory=list, description="优化建议")


class AmbiguityFeedback(BaseModel):
    """歧义反馈"""
    session_id: str = Field(..., description="会话ID")
    user_id: str = Field(..., description="用户ID")
    feedback_type: str = Field(..., description="反馈类型")
    rating: int = Field(..., description="评分", ge=1, le=5)
    comments: Optional[str] = Field(None, description="评论", max_length=500)
    resolution_accuracy: bool = Field(..., description="解决准确性")
    clarification_helpfulness: int = Field(..., description="澄清有用性", ge=1, le=5)
    response_time_satisfaction: int = Field(..., description="响应时间满意度", ge=1, le=5)
    suggestions_for_improvement: Optional[str] = Field(None, description="改进建议", max_length=1000)
    
    @field_validator('feedback_type')
    @classmethod
    def validate_feedback_type(cls, v):
        valid_types = ["resolution_quality", "user_experience", "system_performance", "feature_request"]
        if v not in valid_types:
            raise ValueError(f'反馈类型必须是: {", ".join(valid_types)}')
        return v


class AmbiguityFeedbackResponse(BaseModel):
    """歧义反馈响应"""
    feedback_id: str = Field(..., description="反馈ID")
    session_id: str = Field(..., description="会话ID")
    user_id: str = Field(..., description="用户ID")
    status: str = Field(..., description="处理状态")
    acknowledgment: str = Field(..., description="确认信息")
    follow_up_actions: List[str] = Field(default_factory=list, description="后续行动")
    estimated_improvement_time: Optional[str] = Field(None, description="预计改进时间")
    timestamp: str = Field(..., description="时间戳")