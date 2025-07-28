"""
数据模型包
"""
from .base import BaseModel, CommonModel, AuditableModel, SoftDeleteModel
from .intent import Intent
from .slot import Slot
from .slot_value import SlotDependency
from .slot_value import SlotValue
from .conversation import User, Session, Conversation, IntentAmbiguity, IntentTransfer, UserContext
from .conversation_status import ConversationStatus
from .function_call import FunctionCall as LegacyFunctionCall, ApiCallLog, AsyncTask
from .function import Function, FunctionParameter, FunctionCall
from .response_type import ResponseType
from .system_config import SystemConfig, RagflowConfig
from .entity import EntityType, EntityDictionary
from .extraction import SlotExtractionRule
from .template import PromptTemplate
from .audit import SecurityAuditLog
from .async_log import AsyncLogQueue
from .cache import CacheInvalidationLog
from .synonym import SynonymGroup, SynonymTerm, StopWord, EntityPattern

__all__ = [
    # 基础模型
    'BaseModel', 'CommonModel', 'AuditableModel', 'SoftDeleteModel',
    
    # 核心模型（与MySQL表对应）
    'User',
    'Intent',
    'Slot', 'SlotValue', 'SlotDependency',
    'Function', 'FunctionParameter', 'FunctionCall',
    'LegacyFunctionCall', 'ApiCallLog', 'AsyncTask',
    'ResponseType',
    'Session', 
    'Conversation',
    'ConversationStatus',
    'IntentAmbiguity',
    'IntentTransfer',
    'UserContext',
    'SystemConfig', 'RagflowConfig',
    
    # 实体和提取规则模型
    'EntityType', 'EntityDictionary',
    'SlotExtractionRule',
    'PromptTemplate',
    
    # 审计和日志模型
    'SecurityAuditLog', 'CacheInvalidationLog', 'AsyncLogQueue',
    
    # 同义词管理模型
    'SynonymGroup', 'SynonymTerm', 'StopWord', 'EntityPattern'
]