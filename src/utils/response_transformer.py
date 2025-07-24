"""
统一响应转换层
将不同的数据格式转换为标准化的API响应格式
"""
from typing import Dict, List, Any, Optional, Union, TypeVar, Type
from datetime import datetime
from enum import Enum
from pydantic import BaseModel

from src.schemas.common import StandardResponse, ResponseStatusEnum
from src.schemas.chat import ChatResponse, StreamChatResponse, SlotInfo
from src.schemas.api_response import ApiResponse, ResponseStatus, ResponseMetadata
from src.utils.slot_data_transformer import SlotDataTransformer
from src.utils.logger import get_logger

logger = get_logger(__name__)

# 类型变量
T = TypeVar('T')

class ResponseType(str, Enum):
    """响应类型枚举"""
    CHAT = "chat"
    STREAM_CHAT = "stream_chat"
    BATCH = "batch"
    ANALYTICS = "analytics"
    HEALTH = "health"
    ERROR = "error"
    VALIDATION = "validation"
    API_RESULT = "api_result"


class ResponseTransformer:
    """统一响应转换器"""
    
    def __init__(self):
        """初始化转换器"""
        self.slot_transformer = SlotDataTransformer()
    
    def to_standard_response(self, 
                           data: Any = None,
                           success: bool = True,
                           message: str = "",
                           error_code: Optional[str] = None,
                           request_id: Optional[str] = None,
                           metadata: Optional[Dict[str, Any]] = None) -> StandardResponse[Any]:
        """
        转换为标准响应格式
        
        Args:
            data: 响应数据
            success: 是否成功
            message: 响应消息
            error_code: 错误代码
            request_id: 请求ID
            metadata: 附加元数据
            
        Returns:
            StandardResponse: 标准响应格式
        """
        return StandardResponse(
            success=success,
            message=message or ("操作成功" if success else "操作失败"),
            data=data,
            error=error_code if not success else None,
            request_id=request_id,
            timestamp=datetime.now()
        )
    
    def chat_to_standard(self, 
                        chat_response: ChatResponse,
                        request_id: Optional[str] = None) -> StandardResponse[Dict[str, Any]]:
        """
        将ChatResponse转换为标准格式
        
        Args:
            chat_response: 聊天响应对象
            request_id: 请求ID
            
        Returns:
            StandardResponse: 标准响应格式
        """
        try:
            # 转换槽位数据格式
            transformed_slots = {}
            if chat_response.slots:
                for slot_name, slot_data in chat_response.slots.items():
                    if isinstance(slot_data, dict):
                        transformed_slots[slot_name] = slot_data
                    else:
                        # 如果是SlotInfo对象，转换为字典
                        transformed_slots[slot_name] = slot_data.dict()
            
            # 构建标准化数据
            response_data = {
                "response": chat_response.response,
                "session_id": chat_response.session_id,
                "intent": chat_response.intent,
                "confidence": chat_response.confidence,
                "slots": transformed_slots,
                "status": chat_response.status,
                "response_type": chat_response.response_type,
                "next_action": chat_response.next_action
            }
            
            # 添加可选字段
            if hasattr(chat_response, 'missing_slots') and chat_response.missing_slots:
                response_data["missing_slots"] = chat_response.missing_slots
                
            if hasattr(chat_response, 'validation_errors') and chat_response.validation_errors:
                response_data["validation_errors"] = chat_response.validation_errors
                
            if hasattr(chat_response, 'ambiguous_intents') and chat_response.ambiguous_intents:
                response_data["ambiguous_intents"] = chat_response.ambiguous_intents
                
            if hasattr(chat_response, 'api_result') and chat_response.api_result:
                response_data["api_result"] = chat_response.api_result
            
            # 判断成功状态
            success = chat_response.status not in ['api_error', 'system_error', 'validation_error']
            
            return self.to_standard_response(
                data=response_data,
                success=success,
                message="处理成功" if success else "处理失败",
                request_id=request_id
            )
            
        except Exception as e:
            logger.error(f"聊天响应转换失败: {str(e)}")
            return self.to_standard_response(
                success=False,
                message="响应格式转换失败",
                error_code="RESPONSE_TRANSFORM_ERROR",
                request_id=request_id
            )
    
    def stream_chat_to_standard(self, 
                               stream_response: StreamChatResponse,
                               request_id: Optional[str] = None) -> StandardResponse[Dict[str, Any]]:
        """
        将StreamChatResponse转换为标准格式
        
        Args:
            stream_response: 流式聊天响应对象
            request_id: 请求ID
            
        Returns:
            StandardResponse: 标准响应格式
        """
        try:
            # 构建流式响应数据
            response_data = {
                "response": stream_response.response,
                "intent": stream_response.intent,
                "confidence": stream_response.confidence,
                "status": stream_response.status,
                "response_type": stream_response.response_type,
                "is_streaming": stream_response.is_streaming,
            }
            
            # 添加槽位数据
            if hasattr(stream_response, 'slots') and stream_response.slots:
                response_data["slots"] = stream_response.slots
                
            # 添加流式特定字段
            if hasattr(stream_response, 'chunk_count') and stream_response.chunk_count:
                response_data["chunk_count"] = stream_response.chunk_count
                
            if hasattr(stream_response, 'missing_slots') and stream_response.missing_slots:
                response_data["missing_slots"] = stream_response.missing_slots
                
            if hasattr(stream_response, 'ambiguous_intents') and stream_response.ambiguous_intents:
                response_data["ambiguous_intents"] = stream_response.ambiguous_intents
                
            if hasattr(stream_response, 'error_message') and stream_response.error_message:
                response_data["error_message"] = stream_response.error_message
            
            success = stream_response.status not in ['ragflow_error', 'api_timeout', 'system_error']
            
            return self.to_standard_response(
                data=response_data,
                success=success,
                message="流式处理完成" if success else "流式处理失败",
                request_id=request_id
            )
            
        except Exception as e:
            logger.error(f"流式响应转换失败: {str(e)}")
            return self.to_standard_response(
                success=False,
                message="流式响应格式转换失败",
                error_code="STREAM_RESPONSE_TRANSFORM_ERROR",
                request_id=request_id
            )
    
    def analytics_to_standard(self, 
                             analytics_data: Dict[str, Any],
                             request_id: Optional[str] = None) -> StandardResponse[Dict[str, Any]]:
        """
        将分析数据转换为标准格式
        
        Args:
            analytics_data: 原始分析数据
            request_id: 请求ID
            
        Returns:
            StandardResponse: 标准响应格式
        """
        try:
            # 标准化分析数据格式
            standardized_data = {
                "session_id": analytics_data.get("session_id"),
                "metrics": {
                    "total_turns": analytics_data.get("total_turns", 0),
                    "average_confidence": round(analytics_data.get("average_confidence", 0.0), 3),
                    "average_response_time": round(analytics_data.get("average_response_time", 0.0), 2),
                    "success_rate": round(analytics_data.get("success_rate", 0.0), 3),
                    "quality_score": round(analytics_data.get("quality_score", 0.0), 3)
                },
                "distributions": {
                    "intent_distribution": analytics_data.get("intent_distribution", {}),
                    "response_type_distribution": analytics_data.get("response_type_distribution", {})
                },
                "interaction_stats": analytics_data.get("interaction_stats", {}),
                "confidence_metrics": analytics_data.get("confidence_metrics", {}),
                "error_stats": analytics_data.get("error_stats", {})
            }
            
            # 添加会话元数据
            if "session_metadata" in analytics_data:
                standardized_data["session_metadata"] = analytics_data["session_metadata"]
            
            return self.to_standard_response(
                data=standardized_data,
                success=True,
                message="会话分析获取成功",
                request_id=request_id
            )
            
        except Exception as e:
            logger.error(f"分析数据转换失败: {str(e)}")
            return self.to_standard_response(
                success=False,
                message="分析数据格式转换失败",
                error_code="ANALYTICS_TRANSFORM_ERROR",
                request_id=request_id
            )
    
    def batch_to_standard(self, 
                         batch_results: List[Any],
                         batch_metadata: Optional[Dict[str, Any]] = None,
                         request_id: Optional[str] = None) -> StandardResponse[List[Dict[str, Any]]]:
        """
        将批量处理结果转换为标准格式
        
        Args:
            batch_results: 批量处理结果列表
            batch_metadata: 批量处理元数据
            request_id: 请求ID
            
        Returns:
            StandardResponse: 标准响应格式
        """
        try:
            standardized_results = []
            success_count = 0
            error_count = 0
            
            for result in batch_results:
                if isinstance(result, ChatResponse):
                    # 转换ChatResponse
                    transformed = self.chat_to_standard(result, request_id)
                    standardized_results.append(transformed.data)
                    if transformed.success:
                        success_count += 1
                    else:
                        error_count += 1
                elif isinstance(result, dict):
                    # 已经是字典格式
                    standardized_results.append(result)
                    if result.get('status') in ['completed', 'api_result']:
                        success_count += 1
                    else:
                        error_count += 1
                else:
                    # 其他类型尝试转换为字典
                    standardized_results.append({"result": str(result)})
                    success_count += 1
            
            # 构建响应数据
            response_data = {
                "results": standardized_results,
                "summary": {
                    "total_requests": len(batch_results),
                    "success_count": success_count,
                    "error_count": error_count,
                    "success_rate": round(success_count / len(batch_results), 3) if batch_results else 0.0
                }
            }
            
            # 添加批量元数据
            if batch_metadata:
                response_data["metadata"] = batch_metadata
            
            return self.to_standard_response(
                data=response_data,
                success=True,
                message=f"批量处理完成: {success_count} 成功, {error_count} 失败",
                request_id=request_id
            )
            
        except Exception as e:
            logger.error(f"批量结果转换失败: {str(e)}")
            return self.to_standard_response(
                success=False,
                message="批量结果格式转换失败",
                error_code="BATCH_TRANSFORM_ERROR",
                request_id=request_id
            )
    
    def health_to_standard(self, 
                          health_data: Dict[str, Any],
                          request_id: Optional[str] = None) -> StandardResponse[Dict[str, Any]]:
        """
        将健康检查数据转换为标准格式
        
        Args:
            health_data: 健康检查数据
            request_id: 请求ID
            
        Returns:
            StandardResponse: 标准响应格式
        """
        try:
            # 标准化健康检查数据
            standardized_data = {
                "status": health_data.get("status", "unknown"),
                "timestamp": health_data.get("timestamp", datetime.now().isoformat()),
                "version": health_data.get("version", "unknown"),
                "uptime": health_data.get("uptime"),
                "components": health_data.get("components", {}),
                "metrics": health_data.get("metrics", {}),
                "features": health_data.get("features", {}),
                "performance": health_data.get("performance", {})
            }
            
            is_healthy = health_data.get("status") == "healthy"
            
            return self.to_standard_response(
                data=standardized_data,
                success=is_healthy,
                message="系统运行正常" if is_healthy else "系统状态异常",
                request_id=request_id
            )
            
        except Exception as e:
            logger.error(f"健康检查数据转换失败: {str(e)}")
            return self.to_standard_response(
                success=False,
                message="健康检查数据格式转换失败",
                error_code="HEALTH_TRANSFORM_ERROR",
                request_id=request_id
            )
    
    def error_to_standard(self, 
                         error_message: str,
                         error_code: Optional[str] = None,
                         error_details: Optional[Dict[str, Any]] = None,
                         request_id: Optional[str] = None) -> StandardResponse[None]:
        """
        将错误信息转换为标准格式
        
        Args:
            error_message: 错误消息
            error_code: 错误代码
            error_details: 错误详情
            request_id: 请求ID
            
        Returns:
            StandardResponse: 标准错误响应格式
        """
        return StandardResponse(
            success=False,
            message=error_message,
            data=None,
            error=error_code,
            request_id=request_id,
            timestamp=datetime.now()
        )
    
    def transform_response(self, 
                          response: Any, 
                          response_type: ResponseType,
                          request_id: Optional[str] = None,
                          **kwargs) -> StandardResponse[Any]:
        """
        根据响应类型自动转换响应格式
        
        Args:
            response: 原始响应对象
            response_type: 响应类型
            request_id: 请求ID
            **kwargs: 额外参数
            
        Returns:
            StandardResponse: 标准响应格式
        """
        try:
            if response_type == ResponseType.CHAT:
                return self.chat_to_standard(response, request_id)
            elif response_type == ResponseType.STREAM_CHAT:
                return self.stream_chat_to_standard(response, request_id)
            elif response_type == ResponseType.ANALYTICS:
                return self.analytics_to_standard(response, request_id)
            elif response_type == ResponseType.BATCH:
                batch_metadata = kwargs.get('batch_metadata')
                return self.batch_to_standard(response, batch_metadata, request_id)
            elif response_type == ResponseType.HEALTH:
                return self.health_to_standard(response, request_id)
            elif response_type == ResponseType.ERROR:
                error_code = kwargs.get('error_code')
                error_details = kwargs.get('error_details')
                return self.error_to_standard(response, error_code, error_details, request_id)
            else:
                # 默认处理
                return self.to_standard_response(
                    data=response,
                    success=True,
                    message="处理成功",
                    request_id=request_id
                )
                
        except Exception as e:
            logger.error(f"响应转换失败: response_type={response_type}, error={str(e)}")
            return self.error_to_standard(
                f"响应转换失败: {str(e)}",
                "RESPONSE_TRANSFORM_ERROR",
                request_id=request_id
            )


class SlotResponseTransformer:
    """槽位响应专用转换器"""
    
    def __init__(self):
        """初始化槽位响应转换器"""
        self.slot_transformer = SlotDataTransformer()
    
    def normalize_slot_response(self, 
                               slots: Union[Dict[str, SlotInfo], Dict[str, Any]],
                               include_metadata: bool = True) -> Dict[str, Any]:
        """
        标准化槽位响应格式
        
        Args:
            slots: 槽位数据
            include_metadata: 是否包含元数据
            
        Returns:
            Dict[str, Any]: 标准化的槽位响应
        """
        try:
            if not slots:
                return {}
            
            normalized = {}
            for slot_name, slot_data in slots.items():
                if isinstance(slot_data, SlotInfo):
                    # SlotInfo对象标准化
                    slot_dict = {
                        "value": slot_data.value,
                        "confidence": slot_data.confidence,
                        "source": slot_data.source,
                        "is_validated": slot_data.is_validated
                    }
                    
                    if include_metadata:
                        slot_dict.update({
                            "original_text": slot_data.original_text,
                            "validation_error": slot_data.validation_error
                        })
                        
                elif isinstance(slot_data, dict):
                    # 字典格式标准化
                    slot_dict = {
                        "value": slot_data.get("value"),
                        "confidence": slot_data.get("confidence"),
                        "source": slot_data.get("source", "unknown"),
                        "is_validated": slot_data.get("is_validated", True)
                    }
                    
                    if include_metadata:
                        slot_dict.update({
                            "original_text": slot_data.get("original_text"),
                            "validation_error": slot_data.get("validation_error")
                        })
                else:
                    # 简单值处理
                    slot_dict = {
                        "value": slot_data,
                        "confidence": None,
                        "source": "unknown",
                        "is_validated": True
                    }
                    
                    if include_metadata:
                        slot_dict.update({
                            "original_text": None,
                            "validation_error": None
                        })
                
                normalized[slot_name] = slot_dict
            
            return normalized
            
        except Exception as e:
            logger.error(f"槽位响应标准化失败: {str(e)}")
            return {}


# 全局转换器实例
_response_transformer = None
_slot_response_transformer = None

def get_response_transformer() -> ResponseTransformer:
    """获取全局响应转换器实例"""
    global _response_transformer
    if _response_transformer is None:
        _response_transformer = ResponseTransformer()
    return _response_transformer

def get_slot_response_transformer() -> SlotResponseTransformer:
    """获取全局槽位响应转换器实例"""
    global _slot_response_transformer
    if _slot_response_transformer is None:
        _slot_response_transformer = SlotResponseTransformer()
    return _slot_response_transformer