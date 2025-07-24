"""
RAGFLOW服务回退处理
"""
from typing import Dict, Any, Optional
from src.utils.logger import get_logger

logger = get_logger(__name__)

class RagflowFallbackHandler:
    """RAGFLOW服务回退处理器"""
    
    def __init__(self):
        self.fallback_responses = {
            "default": "抱歉，我暂时无法回答您的问题，请稍后再试。",
            "flight_booking": "您好，我了解您想预订机票。请提供出发地、目的地和出行日期，我将为您查询。",
            "balance_inquiry": "您好，请提供您的账户信息，我将为您查询余额。",
            "greeting": "您好！我是智能助手，很高兴为您服务。"
        }
    
    def get_fallback_response(self, user_input: str, intent: Optional[str] = None) -> str:
        """
        获取回退响应
        
        Args:
            user_input: 用户输入
            intent: 识别的意图
            
        Returns:
            str: 回退响应文本
        """
        try:
            # 根据意图返回相应的回退响应
            if intent and intent in self.fallback_responses:
                return self.fallback_responses[intent]
            
            # 根据关键词匹配
            user_input_lower = user_input.lower()
            if any(word in user_input_lower for word in ['机票', '航班', '飞机']):
                return self.fallback_responses["flight_booking"]
            elif any(word in user_input_lower for word in ['余额', '查询', '账户']):
                return self.fallback_responses["balance_inquiry"]
            elif any(word in user_input_lower for word in ['你好', '您好', 'hello', 'hi']):
                return self.fallback_responses["greeting"]
            
            # 默认回退响应
            return self.fallback_responses["default"]
            
        except Exception as e:
            logger.error(f"获取回退响应失败: {str(e)}")
            return self.fallback_responses["default"]

# 全局实例
_fallback_handler = None

def get_ragflow_fallback_handler() -> RagflowFallbackHandler:
    """获取RAGFLOW回退处理器实例"""
    global _fallback_handler
    if _fallback_handler is None:
        _fallback_handler = RagflowFallbackHandler()
    return _fallback_handler
