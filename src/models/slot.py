"""
槽位相关数据模型
"""
from peewee import *
from playhouse.mysql_ext import JSONField
from .base import CommonModel
from .intent import Intent
import json


class Slot(CommonModel):
    """槽位配置表"""
    
    intent = ForeignKeyField(Intent, backref='slots', on_delete='CASCADE', verbose_name="关联意图")
    slot_name = CharField(max_length=100, verbose_name="槽位名称")
    display_name = CharField(max_length=200, null=True, verbose_name="显示名称")
    slot_type = CharField(max_length=50, verbose_name="槽位类型",
                         constraints=[Check("slot_type IN ('text', 'number', 'date', 'time', 'email', 'phone', 'entity', 'boolean')")])
    is_required = BooleanField(default=False, verbose_name="是否必填")
    is_list = BooleanField(default=False, verbose_name="是否为列表类型")
    validation_rules = JSONField(null=True, verbose_name="验证规则")
    default_value = TextField(null=True, verbose_name="默认值")
    prompt_template = TextField(null=True, verbose_name="询问模板")
    error_message = TextField(null=True, verbose_name="错误提示")
    extraction_priority = IntegerField(default=1, verbose_name="提取优先级")
    sort_order = IntegerField(default=1, verbose_name="排序顺序")
    is_active = BooleanField(default=True, verbose_name="是否激活")
    
    class Meta:
        table_name = 'slots'
        indexes = (
            (('intent', 'slot_name'), True),  # 联合唯一索引
            (('intent', 'is_required'), False),
            (('slot_type',), False),
        )
    
    def get_validation_rules(self) -> dict:
        """获取验证规则字典"""
        if self.validation_rules:
            return self.validation_rules if isinstance(self.validation_rules, dict) else {}
        return {}
    
    def set_validation_rules(self, rules: dict):
        """设置验证规则"""
        self.validation_rules = rules
    
    def get_examples(self) -> list:
        """从验证规则中获取示例值"""
        rules = self.get_validation_rules()
        return rules.get('examples', [])
    
    def validate_value(self, value):
        """验证槽位值"""
        # 根据槽位类型和验证规则验证值的有效性
        rules = self.get_validation_rules()
        
        # 基本类型验证
        if self.slot_type == 'NUMBER':
            try:
                float(value)
            except (ValueError, TypeError):
                return False, "值必须是数字"
        
        elif self.slot_type == 'DATE':
            # 日期格式验证逻辑
            pass
        
        elif self.slot_type == 'ENUM':
            # 枚举值验证
            allowed_values = rules.get('options', [])
            if allowed_values and value not in allowed_values:
                return False, f"值必须是以下之一: {', '.join(allowed_values)}"
        
        # 长度验证
        if isinstance(value, str):
            min_length = rules.get('min_length', 0)
            max_length = rules.get('max_length', 1000)
            if len(value) < min_length:
                return False, f"长度不能少于{min_length}字符"
            if len(value) > max_length:
                return False, f"长度不能超过{max_length}字符"
        
        # 正则表达式验证
        pattern = rules.get('pattern')
        if pattern and isinstance(value, str):
            import re
            if not re.match(pattern, value):
                return False, rules.get('pattern_message', '格式不正确')
        
        return True, ""
    
    def is_text_type(self) -> bool:
        """判断是否为文本类型"""
        return self.slot_type == 'TEXT'
    
    def is_enum_type(self) -> bool:
        """判断是否为枚举类型"""
        return self.slot_type == 'ENUM'
    
    def is_date_type(self) -> bool:
        """判断是否为日期类型"""
        return self.slot_type == 'DATE'
    
    def is_number_type(self) -> bool:
        """判断是否为数字类型"""
        return self.slot_type == 'NUMBER'
    
    def get_enum_options(self) -> list:
        """获取枚举类型的选项"""
        if self.is_enum_type():
            rules = self.get_validation_rules()
            return rules.get('options', [])
        return []
    
    def get_regex_pattern(self) -> str:
        """获取正则表达式模式"""
        rules = self.get_validation_rules()
        return rules.get('pattern', '')
    
    def is_dependent_slot(self) -> bool:
        """检查是否为依赖槽位"""
        # 检查是否有其他槽位依赖于这个槽位
        from .slot_value import SlotDependency
        return SlotDependency.select().where(
            SlotDependency.parent_slot_id == self.id
        ).exists()
    
    def get_dependent_slots(self) -> list:
        """获取依赖于此槽位的子槽位"""
        from .slot_value import SlotDependency
        dependencies = list(
            SlotDependency.select()
            .where(SlotDependency.parent_slot_id == self.id)
        )
        child_slot_ids = [dep.child_slot_id for dep in dependencies]
        return list(Slot.select().where(Slot.id.in_(child_slot_ids)))
    
    def has_dependencies(self) -> bool:
        """检查此槽位是否依赖其他槽位"""
        from .slot_value import SlotDependency
        return SlotDependency.select().where(
            SlotDependency.child_slot_id == self.id
        ).exists()
    
    def get_dependencies(self) -> list:
        """获取此槽位依赖的父槽位"""
        from .slot_value import SlotDependency
        dependencies = list(
            SlotDependency.select()
            .where(SlotDependency.child_slot_id == self.id)
        )
        parent_slot_ids = [dep.parent_slot_id for dep in dependencies]
        return list(Slot.select().where(Slot.id.in_(parent_slot_ids)))
    
    @classmethod  
    def get_slots_by_type(cls, slot_type: str):
        """按类型获取槽位"""
        return cls.select().where(cls.slot_type == slot_type)
    
    def format_prompt(self, context: dict = None) -> str:
        """格式化提示模板"""
        if not self.prompt_template:
            return f"请提供{self.display_name or self.slot_name}："
        
        template = self.prompt_template
        if context:
            try:
                # 使用简单的字符串格式化
                return template.format(**context)
            except (KeyError, ValueError):
                # 如果格式化失败，返回原始模板
                return template
        return template
    
    def __str__(self):
        return f"Slot({self.intent.intent_name}.{self.slot_name})"


# SlotValue和SlotDependency类现在在slot_value.py中定义