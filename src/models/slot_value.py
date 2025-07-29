"""
槽位值数据模型 (V2.2)
用于替代conversations表中的slots_filled和slots_missing字段
"""
from peewee import *
from playhouse.mysql_ext import JSONField
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
            existing.normalized_value = None  # 清空标准化值，强制重新标准化
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
    
    def normalize_value(self) -> None:
        """标准化槽位值"""
        if self.extracted_value:
            # 基本的值标准化逻辑
            normalized = str(self.extracted_value).strip()
            
            # 根据槽位类型进行标准化
            if hasattr(self.slot, 'slot_type'):
                if self.slot.slot_type == 'date':
                    # 日期标准化逻辑
                    normalized = self._normalize_date(normalized)
                elif self.slot.slot_type == 'number':
                    # 数字标准化逻辑，特别处理乘客人数
                    if self.slot.slot_name == 'passenger_count':
                        normalized = self._normalize_passenger_count(normalized)
                    else:
                        # 通用数字标准化
                        try:
                            # 移除非数字字符，提取数字
                            import re
                            numbers = re.findall(r'\d+', normalized)
                            if numbers:
                                normalized = numbers[0]
                            else:
                                # 如果没有找到数字，尝试转换为浮点数验证
                                float(normalized)
                        except ValueError:
                            pass
            
            self.normalized_value = normalized
    
    def _normalize_date(self, date_text: str) -> str:
        """标准化日期文本"""
        from datetime import datetime, timedelta
        import re
        
        date_text = date_text.strip()
        today = datetime.now()
        
        # 处理相对日期
        if date_text in ['今天', '今日']:
            return today.strftime('%Y-%m-%d')
        elif date_text in ['明天', '明日']:
            return (today + timedelta(days=1)).strftime('%Y-%m-%d')
        elif date_text in ['后天']:
            return (today + timedelta(days=2)).strftime('%Y-%m-%d')
        elif date_text in ['昨天', '昨日']:
            return (today - timedelta(days=1)).strftime('%Y-%m-%d')
        elif date_text in ['前天']:
            return (today - timedelta(days=2)).strftime('%Y-%m-%d')
        
        # 处理"X天后"、"X天前"的格式
        pattern_after = r'(\d+)天后'
        pattern_before = r'(\d+)天前'
        
        match_after = re.match(pattern_after, date_text)
        if match_after:
            days = int(match_after.group(1))
            return (today + timedelta(days=days)).strftime('%Y-%m-%d')
        
        match_before = re.match(pattern_before, date_text)
        if match_before:
            days = int(match_before.group(1))
            return (today - timedelta(days=days)).strftime('%Y-%m-%d')
        
        # 处理具体日期格式，如果已经是标准格式就直接返回
        try:
            # 尝试解析各种日期格式
            for fmt in ['%Y-%m-%d', '%Y/%m/%d', '%m/%d', '%m-%d']:
                try:
                    parsed_date = datetime.strptime(date_text, fmt)
                    if fmt in ['%m/%d', '%m-%d']:  # 补全年份
                        parsed_date = parsed_date.replace(year=today.year)
                    return parsed_date.strftime('%Y-%m-%d')
                except ValueError:
                    continue
        except:
            pass
        
        # 如果无法解析，返回原始文本
        return date_text
    
    def _normalize_passenger_count(self, value: str) -> str:
        """标准化乘客数量"""
        try:
            # 使用 slot_inheritance.py 中相同的逻辑
            if isinstance(value, (int, float)):
                return str(int(value))
            
            value_str = str(value).strip()
            
            # 移除常见后缀
            for suffix in ['个人', '人', '位', '名', '个']:
                if value_str.endswith(suffix):
                    value_str = value_str[:-len(suffix)]
                    break
            
            # 中文数字转换
            chinese_numbers = {
                '一': 1, '二': 2, '三': 3, '四': 4, '五': 5,
                '六': 6, '七': 7, '八': 8, '九': 9, '十': 10
            }
            
            if value_str in chinese_numbers:
                return str(chinese_numbers[value_str])
            
            # 尝试直接转换为数字
            try:
                return str(int(float(value_str)))
            except (ValueError, TypeError):
                # 默认返回1
                return '1'
                
        except Exception:
            # 默认返回1
            return '1'
    
    def get_normalized_value(self) -> str:
        """获取标准化后的值"""
        return self.normalized_value or self.extracted_value


class SlotDependency(CommonModel):
    """槽位依赖关系表"""
    
    parent_slot_id = IntegerField(verbose_name="父槽位ID")
    child_slot_id = IntegerField(verbose_name="子槽位ID")
    dependency_type = CharField(max_length=50, default='required_if', verbose_name="依赖类型")
    conditions = JSONField(null=True, verbose_name="依赖条件")
    
    class Meta:
        table_name = 'slot_dependencies'
        indexes = (
            (('parent_slot_id', 'child_slot_id'), True),  # 联合唯一索引
            (('dependency_type',), False),
        )
    
    def get_condition(self) -> dict:
        """获取依赖条件"""
        if self.conditions:
            return self.conditions if isinstance(self.conditions, dict) else {}
        return {}
    
    def set_condition(self, condition: dict):
        """设置依赖条件"""
        self.conditions = condition
    
    def check_dependency(self, slot_values: dict):
        """
        检查依赖条件是否满足
        
        Args:
            slot_values: 当前已提取的槽位值字典 {slot_name: value}
        
        Returns:
            tuple: (是否满足, 错误信息)
        """
        try:
            # 通过ID获取槽位对象
            from .slot import Slot
            parent_slot = Slot.get_by_id(self.parent_slot_id)
            child_slot = Slot.get_by_id(self.child_slot_id)
            
            parent_slot_name = parent_slot.slot_name
            child_slot_name = child_slot.slot_name
        except Exception:
            return False, "依赖关系中的槽位不存在"
        
        # 基本依赖检查：被依赖的槽位必须有值
        parent_value = slot_values.get(parent_slot_name)
        child_value = slot_values.get(child_slot_name)
        
        if self.dependency_type == 'required_if':
            # 如果父槽位有值，子槽位也必须有值
            if parent_value and not child_value:
                return False, f"当{parent_slot_name}有值时，{child_slot_name}也必须有值"
        
        elif self.dependency_type == 'conditional':
            # 基于条件的依赖
            condition = self.get_condition()
            expected_value = condition.get('value')
            
            if parent_value == expected_value and not child_value:
                return False, f"当{parent_slot_name}={expected_value}时，{child_slot_name}必须有值"
        
        elif self.dependency_type == 'mutual_exclusive':
            # 互斥：两个槽位不能同时有值
            if parent_value and child_value:
                return False, f"{parent_slot_name}和{child_slot_name}不能同时有值"
        
        return True, ""
    
    def __str__(self):
        return f"SlotDependency({self.parent_slot_id}->{self.child_slot_id}:{self.dependency_type})"