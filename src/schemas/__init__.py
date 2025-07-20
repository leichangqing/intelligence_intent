"""
Schema包初始化文件
"""
from .common import (
    BaseResponse,
    SuccessResponse, 
    ErrorResponse,
    PaginationResponse,
    TimestampMixin,
    IDMixin,
    StandardResponse
)
from .chat import (
    ChatRequest,
    ChatResponse,
    ChatInteractRequest,
    SlotInfo,
    IntentCandidate,
    DisambiguationRequest,
    DisambiguationResponse,
    BatchChatRequest,
    BatchChatResponse,
    ChatMetrics,
    ConversationHistory
)

__all__ = [
    # Common schemas
    "BaseResponse",
    "SuccessResponse", 
    "ErrorResponse",
    "PaginationResponse",
    "TimestampMixin",
    "IDMixin",
    "StandardResponse",
    
    # Chat schemas
    "ChatRequest",
    "ChatResponse",
    "ChatInteractRequest", 
    "SlotInfo",
    "IntentCandidate",
    "DisambiguationRequest",
    "DisambiguationResponse",
    "BatchChatRequest",
    "BatchChatResponse",
    "ChatMetrics",
    "ConversationHistory"
]