"""
意图识别结果的统一数据模型
统一IntentRecognitionResult类设计，解决不同服务间的不一致问题
"""
from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field
from datetime import datetime
from enum import Enum

from src.models.intent import Intent


class RecognitionType(str, Enum):
    """识别结果类型枚举"""
    CONFIDENT = "confident"      # 高置信度识别
    UNCERTAIN = "uncertain"      # 低置信度识别
    AMBIGUOUS = "ambiguous"      # 存在歧义
    UNRECOGNIZED = "unrecognized"  # 无法识别


class EntityInfo(BaseModel):
    """实体信息结构"""
    name: str = Field(..., description="实体名称")
    value: Any = Field(..., description="实体值")
    confidence: float = Field(..., description="置信度", ge=0.0, le=1.0)
    start_pos: Optional[int] = Field(None, description="起始位置")
    end_pos: Optional[int] = Field(None, description="结束位置")
    entity_type: Optional[str] = Field(None, description="实体类型")


class AlternativeIntent(BaseModel):
    """备选意图信息"""
    intent_name: str = Field(..., description="意图名称")
    confidence: float = Field(..., description="置信度", ge=0.0, le=1.0)
    reasoning: Optional[str] = Field(None, description="选择原因")


class IntentRecognitionResult(BaseModel):
    """
    统一的意图识别结果类
    
    统一了IntentService和NLUEngine中的不同实现，
    提供完整的意图识别结果信息
    """
    
    # 核心识别结果
    intent: Optional[Intent] = Field(None, description="识别的意图对象")
    intent_name: Optional[str] = Field(None, description="意图名称")
    confidence: float = Field(..., description="置信度", ge=0.0, le=1.0)
    
    # 识别类型和状态
    recognition_type: RecognitionType = Field(..., description="识别结果类型")
    is_ambiguous: bool = Field(False, description="是否存在歧义")
    
    # 额外信息
    entities: List[EntityInfo] = Field(default_factory=list, description="提取的实体列表")
    alternatives: List[AlternativeIntent] = Field(default_factory=list, description="备选意图列表")
    reasoning: Optional[str] = Field(None, description="识别推理过程")
    
    # 上下文信息
    user_input: Optional[str] = Field(None, description="用户输入")
    context: Optional[Dict[str, Any]] = Field(None, description="上下文信息")
    
    # 元数据
    timestamp: datetime = Field(default_factory=datetime.now, description="识别时间")
    processing_time_ms: Optional[float] = Field(None, description="处理时间(毫秒)")
    model_version: Optional[str] = Field(None, description="模型版本")
    
    class Config:
        """Pydantic配置"""
        arbitrary_types_allowed = True  # 允许Intent模型对象
        json_encoders = {
            datetime: lambda v: v.isoformat(),
            Intent: lambda v: v.intent_name if v else None
        }
    
    def __init__(self, **data):
        """初始化时自动设置相关字段"""
        # 确保必需的字段有默认值
        if 'recognition_type' not in data:
            data['recognition_type'] = RecognitionType.UNRECOGNIZED
        if 'confidence' not in data:
            data['confidence'] = 0.0
            
        super().__init__(**data)
        
        # 自动设置intent_name
        if self.intent and not self.intent_name:
            self.intent_name = self.intent.intent_name
        elif self.intent_name and not self.intent:
            # 如果只有intent_name，尝试加载Intent对象
            try:
                self.intent = Intent.get(Intent.intent_name == self.intent_name)
            except:
                # 如果找不到，保持None
                pass
        
        # 重新确定识别类型
        self.recognition_type = self._determine_recognition_type()
    
    def _determine_recognition_type(self) -> RecognitionType:
        """自动确定识别类型"""
        if self.is_ambiguous:
            return RecognitionType.AMBIGUOUS
        elif self.intent and self.confidence >= 0.8:
            return RecognitionType.CONFIDENT
        elif self.intent and self.confidence >= 0.5:
            return RecognitionType.UNCERTAIN
        else:
            return RecognitionType.UNRECOGNIZED
    
    @classmethod
    def from_nlu_result(
        cls,
        intent_name: str,
        confidence: float,
        entities: List[Dict] = None,
        alternatives: List[Dict] = None,
        reasoning: str = None,
        user_input: str = None,
        processing_time_ms: float = None
    ) -> 'IntentRecognitionResult':
        """从NLU引擎结果创建"""
        
        # 转换实体格式
        entity_list = []
        if entities:
            for entity in entities:
                entity_list.append(EntityInfo(
                    name=entity.get('name', ''),
                    value=entity.get('value', ''),
                    confidence=entity.get('confidence', 1.0),
                    start_pos=entity.get('start', None),
                    end_pos=entity.get('end', None),
                    entity_type=entity.get('type', None)
                ))
        
        # 转换备选意图格式
        alternative_list = []
        if alternatives:
            for alt in alternatives:
                alternative_list.append(AlternativeIntent(
                    intent_name=alt.get('intent', ''),
                    confidence=alt.get('confidence', 0.0),
                    reasoning=alt.get('reasoning', None)
                ))
        
        return cls(
            intent_name=intent_name,
            confidence=confidence,
            entities=entity_list,
            alternatives=alternative_list,
            reasoning=reasoning,
            user_input=user_input,
            processing_time_ms=processing_time_ms
        )
    
    @classmethod
    def from_intent_service_result(
        cls,
        intent: Optional[Intent],
        confidence: float,
        alternatives: List[Dict] = None,
        is_ambiguous: bool = False,
        user_input: str = None,
        context: Dict[str, Any] = None
    ) -> 'IntentRecognitionResult':
        """从IntentService结果创建"""
        
        # 转换备选意图格式
        alternative_list = []
        if alternatives:
            for alt in alternatives:
                alternative_list.append(AlternativeIntent(
                    intent_name=alt.get('intent_name', alt.get('intent', '')),
                    confidence=alt.get('confidence', 0.0),
                    reasoning=alt.get('reasoning', None)
                ))
        
        return cls(
            intent=intent,
            confidence=confidence,
            alternatives=alternative_list,
            is_ambiguous=is_ambiguous,
            user_input=user_input,
            context=context
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式（向后兼容）"""
        return {
            "intent": self.intent_name,
            "intent_object": self.intent,
            "confidence": self.confidence,
            "recognition_type": self.recognition_type.value,
            "is_ambiguous": self.is_ambiguous,
            "entities": [entity.dict() for entity in self.entities],
            "alternatives": [alt.dict() for alt in self.alternatives],
            "reasoning": self.reasoning,
            "user_input": self.user_input,
            "context": self.context,
            "timestamp": self.timestamp.isoformat(),
            "processing_time_ms": self.processing_time_ms
        }
    
    def to_legacy_intent_service_format(self) -> Dict[str, Any]:
        """转换为IntentService的传统格式（向后兼容）"""
        return {
            "intent": self.intent_name if self.intent else None,
            "confidence": self.confidence,
            "recognition_type": self.recognition_type.value,
            "alternatives": [
                {
                    "intent_name": alt.intent_name,
                    "confidence": alt.confidence,
                    "reasoning": alt.reasoning
                }
                for alt in self.alternatives
            ],
            "is_ambiguous": self.is_ambiguous
        }
    
    def to_legacy_nlu_format(self) -> Dict[str, Any]:
        """转换为NLU引擎的传统格式（向后兼容）"""
        return {
            'intent': self.intent_name or "unknown",
            'confidence': self.confidence,
            'entities': [
                {
                    'name': entity.name,
                    'value': entity.value,
                    'confidence': entity.confidence,
                    'start': entity.start_pos,
                    'end': entity.end_pos,
                    'type': entity.entity_type
                }
                for entity in self.entities
            ],
            'alternatives': [
                {
                    'intent': alt.intent_name,
                    'confidence': alt.confidence,
                    'reasoning': alt.reasoning
                }
                for alt in self.alternatives
            ],
            'reasoning': self.reasoning
        }
    
    def is_successful(self, threshold: float = 0.5) -> bool:
        """判断识别是否成功"""
        return (
            self.intent is not None and 
            self.confidence >= threshold and 
            not self.is_ambiguous
        )
    
    def get_best_alternative(self) -> Optional[AlternativeIntent]:
        """获取最佳备选意图"""
        if not self.alternatives:
            return None
        return max(self.alternatives, key=lambda x: x.confidence)
    
    def add_entity(self, name: str, value: Any, confidence: float = 1.0, **kwargs):
        """添加实体信息"""
        entity = EntityInfo(
            name=name,
            value=value,
            confidence=confidence,
            **kwargs
        )
        self.entities.append(entity)
    
    def add_alternative(self, intent_name: str, confidence: float, reasoning: str = None):
        """添加备选意图"""
        alternative = AlternativeIntent(
            intent_name=intent_name,
            confidence=confidence,
            reasoning=reasoning
        )
        self.alternatives.append(alternative)
    
    def update_confidence(self, new_confidence: float, reason: str = None):
        """更新置信度并记录原因"""
        old_confidence = self.confidence
        self.confidence = new_confidence
        
        # 更新识别类型
        self.recognition_type = self._determine_recognition_type()
        
        # 记录置信度调整原因
        if reason and self.reasoning:
            self.reasoning += f" | 置信度调整: {old_confidence:.3f} -> {new_confidence:.3f} ({reason})"
        elif reason:
            self.reasoning = f"置信度调整: {old_confidence:.3f} -> {new_confidence:.3f} ({reason})"
    
    def __str__(self) -> str:
        """字符串表示"""
        return f"IntentRecognitionResult(intent={self.intent_name}, confidence={self.confidence:.3f}, type={self.recognition_type.value})"
    
    def __repr__(self) -> str:
        """详细字符串表示"""
        return (
            f"IntentRecognitionResult("
            f"intent='{self.intent_name}', "
            f"confidence={self.confidence:.3f}, "
            f"type={self.recognition_type.value}, "
            f"ambiguous={self.is_ambiguous}, "
            f"entities={len(self.entities)}, "
            f"alternatives={len(self.alternatives)})"
        )


# 向后兼容的类型别名
IntentResult = IntentRecognitionResult
NLUResult = IntentRecognitionResult