"""
槽位值数据模型 (V2.2)
用于替代conversations表中的slots_filled和slots_missing字段
"""
from peewee import *
from datetime import datetime
from typing import Dict, Any, List, Optional

from src.models.base import CommonModel
from src.models.conversation import Conversation
from src.models.slot import Slot


class SlotValue(CommonModel):
    """槽位值存储表 - 与MySQL Schema V2.2对应"""
    
    id = AutoField(primary_key=True)
    conversation = ForeignKeyField(Conversation, on_delete='CASCADE', verbose_name="对话ID")
    slot = ForeignKeyField(Slot, on_delete='CASCADE', verbose_name="槽位ID")
    slot_name = CharField(max_length=100, verbose_name="槽位名称")
    original_text = TextField(null=True, verbose_name="原始文本")
    extracted_value = TextField(null=True, verbose_name="提取的值")
    normalized_value = TextField(null=True, verbose_name="标准化后的值")
    confidence = DecimalField(max_digits=5, decimal_places=4, null=True, verbose_name="提取置信度")
    extraction_method = CharField(max_length=50, null=True, verbose_name="提取方法")
    validation_status = CharField(max_length=20, default='pending', verbose_name="验证状态")  # valid, invalid, pending, corrected
    validation_error = TextField(null=True, verbose_name="验证错误信息")
    is_confirmed = BooleanField(default=False, verbose_name="是否已确认")
    
    class Meta:
        table_name = 'slot_values'
        indexes = (
            (('conversation', 'slot'), True),  # 对话和槽位的组合唯一
            (('slot_name', 'normalized_value'), False),
            (('confidence',), False),
            (('validation_status',), False),
        )
    
    def __str__(self):
        return f"SlotValue({self.slot_name}: {self.normalized_value or self.extracted_value})"
    
    def is_valid(self) -> bool:
        """检查槽位值是否有效"""
        return self.validation_status == 'valid'
    
    def is_invalid(self) -> bool:
        """检查槽位值是否无效"""
        return self.validation_status == 'invalid'
    
    def is_pending(self) -> bool:
        """检查槽位值是否待验证"""
        return self.validation_status == 'pending'
    
    def is_corrected(self) -> bool:
        """检查槽位值是否已修正"""
        return self.validation_status == 'corrected'
    
    def get_final_value(self) -> Any:
        """获取最终值（优先使用标准化值）"""
        return self.normalized_value or self.extracted_value
    
    def set_valid(self, normalized_value: str = None):
        """设置为有效状态"""
        self.validation_status = 'valid'
        self.validation_error = None
        if normalized_value:
            self.normalized_value = normalized_value
        self.save()
    
    def set_invalid(self, error_message: str):
        """设置为无效状态"""
        self.validation_status = 'invalid'
        self.validation_error = error_message
        self.save()
    
    def set_corrected(self, corrected_value: str):
        """设置修正值"""
        self.validation_status = 'corrected'
        self.normalized_value = corrected_value
        self.validation_error = None
        self.save()
    
    def confirm(self):
        """确认槽位值"""
        self.is_confirmed = True
        if self.validation_status == 'pending':
            self.validation_status = 'valid'
        self.save()
    
    @classmethod
    def create_slot_value(
        cls,
        conversation: Conversation,
        slot: Slot,
        original_text: str = None,
        extracted_value: str = None,
        confidence: float = None,
        extraction_method: str = None
    ) -> 'SlotValue':
        """创建槽位值记录"""
        return cls.create(
            conversation=conversation,
            slot=slot,
            slot_name=slot.slot_name,
            original_text=original_text,
            extracted_value=extracted_value,
            confidence=confidence,
            extraction_method=extraction_method,
            validation_status='pending'
        )
    
    @classmethod
    def get_by_conversation_and_slot(
        cls,
        conversation: Conversation,
        slot: Slot
    ) -> Optional['SlotValue']:
        """根据对话和槽位获取槽位值"""
        try:
            return cls.get(
                (cls.conversation == conversation) &
                (cls.slot == slot)
            )
        except cls.DoesNotExist:
            return None
    
    @classmethod
    def get_conversation_slots(
        cls,
        conversation: Conversation,
        include_invalid: bool = False
    ) -> List['SlotValue']:
        """获取对话的所有槽位值"""
        query = cls.select().where(cls.conversation == conversation)
        
        if not include_invalid:
            query = query.where(cls.validation_status.in_(['valid', 'corrected', 'pending']))
        
        return list(query.order_by(cls.created_at))
    
    @classmethod
    def get_slots_by_names(
        cls,
        conversation: Conversation,
        slot_names: List[str]
    ) -> Dict[str, 'SlotValue']:
        """根据槽位名称获取槽位值字典"""
        slot_values = cls.select().where(
            (cls.conversation == conversation) &
            (cls.slot_name.in_(slot_names))
        )
        
        return {sv.slot_name: sv for sv in slot_values}
    
    @classmethod
    def get_filled_slots_dict(
        cls,
        conversation: Conversation,
        only_valid: bool = True
    ) -> Dict[str, Any]:
        """获取已填充槽位的字典格式"""
        query = cls.select().where(cls.conversation == conversation)
        
        if only_valid:
            query = query.where(cls.validation_status.in_(['valid', 'corrected']))
        
        result = {}
        for slot_value in query:
            result[slot_value.slot_name] = slot_value.get_final_value()
        
        return result
    
    @classmethod
    def get_missing_required_slots(
        cls,
        conversation: Conversation,
        intent_id: int
    ) -> List[str]:
        """获取缺失的必填槽位列表"""
        from src.models.slot import Slot
        
        # 获取意图的所有必填槽位
        required_slots = list(
            Slot.select()
            .where(
                (Slot.intent_id == intent_id) &
                (Slot.is_required == True) &
                (Slot.is_active == True)
            )
        )
        
        # 获取已填充的有效槽位
        filled_slots = cls.get_slots_by_names(
            conversation,
            [slot.slot_name for slot in required_slots]
        )
        
        # 找出缺失的必填槽位
        missing_slots = []
        for slot in required_slots:
            if (slot.slot_name not in filled_slots or 
                not filled_slots[slot.slot_name].is_valid()):
                missing_slots.append(slot.slot_name)
        
        return missing_slots
    
    @classmethod
    def update_or_create_slot_value(
        cls,
        conversation: Conversation,
        slot: Slot,
        extracted_value: str,
        original_text: str = None,
        confidence: float = None,
        extraction_method: str = None
    ) -> 'SlotValue':
        """更新或创建槽位值"""
        existing = cls.get_by_conversation_and_slot(conversation, slot)
        
        if existing:
            # 更新现有记录
            existing.original_text = original_text or existing.original_text
            existing.extracted_value = extracted_value
            existing.confidence = confidence
            existing.extraction_method = extraction_method or existing.extraction_method
            existing.validation_status = 'pending'  # 重新验证
            existing.validation_error = None
            existing.save()
            return existing
        else:
            # 创建新记录
            return cls.create_slot_value(
                conversation=conversation,
                slot=slot,
                original_text=original_text,
                extracted_value=extracted_value,
                confidence=confidence,
                extraction_method=extraction_method
            )
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            'id': self.id,
            'slot_name': self.slot_name,
            'original_text': self.original_text,
            'extracted_value': self.extracted_value,
            'normalized_value': self.normalized_value,
            'final_value': self.get_final_value(),
            'confidence': float(self.confidence) if self.confidence else None,
            'extraction_method': self.extraction_method,
            'validation_status': self.validation_status,
            'validation_error': self.validation_error,
            'is_confirmed': self.is_confirmed,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }