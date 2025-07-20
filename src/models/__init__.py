"""
数据模型包
"""
from .base import BaseModel, CommonModel, AuditableModel, SoftDeleteModel
from .intent import Intent
from .slot import Slot, SlotValue, SlotDependency
from .conversation import Session, Conversation
from .function_call import FunctionCall as LegacyFunctionCall, ApiCallLog, AsyncTask
from .function import Function, FunctionParameter, FunctionCall
from .config import SystemConfig

__all__ = [
    # 基础模型
    'BaseModel', 'CommonModel', 'AuditableModel', 'SoftDeleteModel',
    
    # 核心模型（与MySQL表对应）
    'Intent',
    'Slot', 'SlotValue', 'SlotDependency',
    'Function', 'FunctionParameter', 'FunctionCall',
    'LegacyFunctionCall', 'ApiCallLog', 'AsyncTask',
    'Session', 
    'Conversation',
    'SystemConfig'
]