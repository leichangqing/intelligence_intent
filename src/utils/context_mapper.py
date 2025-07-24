"""
上下文映射工具类 (V2.2重构)
统一处理API请求、Redis缓存、MySQL存储之间的上下文数据映射
"""
from typing import Dict, Any, Optional, List
from datetime import datetime
from pydantic import BaseModel

from src.schemas.chat import ChatContext, DeviceInfo
from src.utils.logger import get_logger

logger = get_logger(__name__)


class SessionDataStructure(BaseModel):
    """标准化的会话数据结构"""
    id: int
    session_id: str
    user_id: str
    context: Dict[str, Any]
    created_at: str
    
    # 扩展字段（从context中提取的快捷访问字段）
    current_intent: Optional[str] = None
    current_slots: Optional[Dict[str, Any]] = None
    conversation_history: Optional[List[Dict[str, Any]]] = None
    device_info: Optional[Dict[str, Any]] = None
    location: Optional[Dict[str, Any]] = None
    user_preferences: Optional[Dict[str, Any]] = None


class ContextMapper:
    """上下文映射器"""
    
    @staticmethod
    def map_chat_context_to_session(
        chat_context: Optional[ChatContext],
        session_id: str,
        user_id: str
    ) -> Dict[str, Any]:
        """
        将API请求中的ChatContext映射为会话初始化上下文
        
        Args:
            chat_context: API请求中的上下文
            session_id: 会话ID
            user_id: 用户ID
            
        Returns:
            Dict: 会话初始化上下文
        """
        initial_context = {
            'session_id': session_id,
            'user_id': user_id,
            'created_at': datetime.now().isoformat(),
            'current_intent': None,
            'current_slots': {},
            'conversation_history': []
        }
        
        if not chat_context:
            return initial_context
        
        try:
            # 直接映射设备信息（保持与API结构一致）
            if chat_context.device_info:
                initial_context['device_info'] = {
                    'platform': chat_context.device_info.platform,
                    'user_agent': chat_context.device_info.user_agent,
                    'ip_address': chat_context.device_info.ip_address,
                    'screen_resolution': chat_context.device_info.screen_resolution,
                    'language': chat_context.device_info.language
                }
            
            # 直接映射位置信息（保持与API结构一致）
            if chat_context.location:
                initial_context['location'] = chat_context.location
            
            # B2B系统特有字段
            if chat_context.client_system_id:
                initial_context['client_system_id'] = chat_context.client_system_id
            
            if chat_context.request_trace_id:
                initial_context['request_trace_id'] = chat_context.request_trace_id
                
            if chat_context.business_context:
                initial_context['business_context'] = chat_context.business_context
            
            # 临时偏好覆盖（用于特殊场景）
            if chat_context.temp_preferences:
                initial_context['temp_preferences'] = chat_context.temp_preferences
            
            logger.debug(f"ChatContext映射完成: session_id={session_id}")
            return initial_context
            
        except Exception as e:
            logger.error(f"ChatContext映射失败: {str(e)}")
            return initial_context
    
    @staticmethod
    def build_session_cache_data(
        session_id: str,
        user_id: str,
        database_id: int,
        context: Dict[str, Any],
        created_at: datetime
    ) -> SessionDataStructure:
        """
        构建标准化的会话缓存数据结构
        
        Args:
            session_id: 会话ID
            user_id: 用户ID
            database_id: 数据库ID
            context: 会话上下文
            created_at: 创建时间
            
        Returns:
            SessionDataStructure: 标准化会话数据
        """
        return SessionDataStructure(
            id=database_id,
            session_id=session_id,
            user_id=user_id,
            context=context,
            created_at=created_at.isoformat(),
            current_intent=context.get('current_intent'),
            current_slots=context.get('current_slots', {}),
            conversation_history=context.get('conversation_history', []),
            device_info=context.get('device_info'),
            location=context.get('location'),
            user_preferences=context.get('user_preferences')
        )
    
    @staticmethod
    def extract_user_context_data(
        chat_context: Optional[ChatContext],
        user_id: str
    ) -> List[Dict[str, Any]]:
        """
        从ChatContext中提取需要存储到UserContext表的数据
        
        Args:
            chat_context: API请求中的上下文
            user_id: 用户ID
            
        Returns:
            List[Dict]: UserContext表记录列表
        """
        user_contexts = []
        
        if not chat_context:
            return user_contexts
        
        try:
            # 位置信息（临时会话级）
            if chat_context.location:
                user_contexts.append({
                    'user_id': user_id,
                    'context_type': 'session',
                    'context_key': 'current_location',
                    'context_value': chat_context.location,
                    'scope': 'session',
                    'priority': 2
                })
            
            # 设备信息（会话级临时数据）
            if chat_context.device_info:
                user_contexts.append({
                    'user_id': user_id,
                    'context_type': 'session',
                    'context_key': 'device_info',
                    'context_value': {
                        'platform': chat_context.device_info.platform,
                        'user_agent': chat_context.device_info.user_agent,
                        'ip_address': chat_context.device_info.ip_address,
                        'screen_resolution': chat_context.device_info.screen_resolution,
                        'language': chat_context.device_info.language
                    },
                    'scope': 'session',
                    'priority': 3
                })
            
            # B2B业务上下文
            if chat_context.business_context:
                user_contexts.append({
                    'user_id': user_id,
                    'context_type': 'session',
                    'context_key': 'business_context',
                    'context_value': chat_context.business_context,
                    'scope': 'session',
                    'priority': 1
                })
            
            # 临时偏好覆盖
            if chat_context.temp_preferences:
                for key, value in chat_context.temp_preferences.items():
                    user_contexts.append({
                        'user_id': user_id,
                        'context_type': 'temporary',
                        'context_key': f'temp_{key}',
                        'context_value': value,
                        'scope': 'session',
                        'priority': 5  # 高优先级，覆盖系统配置
                    })
            
            logger.debug(f"提取UserContext数据: user_id={user_id}, count={len(user_contexts)}")
            return user_contexts
            
        except Exception as e:
            logger.error(f"提取UserContext数据失败: {str(e)}")
            return []
    
    @staticmethod
    def merge_context_layers(
        session_context: Dict[str, Any],
        user_contexts: List[Dict[str, Any]],
        request_context: Optional[ChatContext] = None
    ) -> Dict[str, Any]:
        """
        合并多层上下文数据
        优先级: request_context > session_context > user_contexts
        
        Args:
            session_context: 会话级上下文
            user_contexts: 用户级上下文列表
            request_context: 请求级上下文
            
        Returns:
            Dict: 合并后的完整上下文
        """
        merged_context = {}
        
        try:
            # 1. 基础层：用户级上下文
            user_context_dict = {}
            for ctx in user_contexts:
                context_type = ctx.get('context_type', 'unknown')
                context_key = ctx.get('context_key', 'unknown')
                context_value = ctx.get('context_value')
                
                if context_type not in user_context_dict:
                    user_context_dict[context_type] = {}
                user_context_dict[context_type][context_key] = context_value
            
            merged_context['user_context'] = user_context_dict
            
            # 2. 中间层：会话级上下文
            merged_context.update(session_context)
            
            # 3. 顶层：请求级上下文（最高优先级）
            if request_context:
                request_mapped = ContextMapper.map_chat_context_to_session(
                    request_context, 
                    session_context.get('session_id', ''),
                    session_context.get('user_id', '')
                )
                
                # 只覆盖非空值
                for key, value in request_mapped.items():
                    if value is not None and value != {} and value != []:
                        merged_context[key] = value
            
            logger.debug("上下文层次合并完成")
            return merged_context
            
        except Exception as e:
            logger.error(f"上下文层次合并失败: {str(e)}")
            return session_context
    
    @staticmethod
    def validate_context_structure(context: Dict[str, Any]) -> bool:
        """
        验证上下文结构的完整性
        
        Args:
            context: 上下文数据
            
        Returns:
            bool: 是否有效
        """
        required_fields = ['session_id', 'user_id', 'created_at']
        
        try:
            # 检查必需字段
            for field in required_fields:
                if field not in context:
                    logger.warning(f"上下文缺少必需字段: {field}")
                    return False
            
            # 检查数据类型
            if not isinstance(context.get('current_slots', {}), dict):
                logger.warning("current_slots字段类型错误")
                return False
            
            if not isinstance(context.get('conversation_history', []), list):
                logger.warning("conversation_history字段类型错误")
                return False
            
            if context.get('device_info') is not None and not isinstance(context.get('device_info'), dict):
                logger.warning("device_info字段类型错误")
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"上下文结构验证失败: {str(e)}")
            return False


# 便捷函数
def map_chat_context_to_session(
    chat_context: Optional[ChatContext],
    session_id: str,
    user_id: str
) -> Dict[str, Any]:
    """便捷函数：将ChatContext映射为会话上下文"""
    return ContextMapper.map_chat_context_to_session(chat_context, session_id, user_id)


def build_session_cache_data(
    session_id: str,
    user_id: str,
    database_id: int,
    context: Dict[str, Any],
    created_at: datetime
) -> SessionDataStructure:
    """便捷函数：构建会话缓存数据"""
    return ContextMapper.build_session_cache_data(
        session_id, user_id, database_id, context, created_at
    )


def extract_user_context_data(
    chat_context: Optional[ChatContext],
    user_id: str
) -> List[Dict[str, Any]]:
    """便捷函数：提取用户上下文数据"""
    return ContextMapper.extract_user_context_data(chat_context, user_id)