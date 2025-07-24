"""
意图相关数据模型
"""
from peewee import *
from playhouse.mysql_ext import JSONField
from .base import CommonModel, AuditableModel
import json


class Intent(CommonModel):
    """意图配置表"""
    
    intent_name = CharField(max_length=100, unique=True, verbose_name="意图名称")
    display_name = CharField(max_length=200, verbose_name="显示名称")
    description = TextField(null=True, verbose_name="意图描述")
    confidence_threshold = DecimalField(max_digits=5, decimal_places=4, default=0.7000, verbose_name="置信度阈值")
    priority = IntegerField(default=1, verbose_name="意图优先级")
    category = CharField(max_length=50, null=True, verbose_name="意图分类")
    is_active = BooleanField(default=True, verbose_name="是否激活")
    examples = JSONField(null=True, verbose_name="示例语句")
    fallback_response = TextField(null=True, verbose_name="兜底回复")
    created_by = CharField(max_length=100, null=True, verbose_name="创建人")
    
    class Meta:
        table_name = 'intents'
        indexes = (
            (('intent_name',), False),
            (('is_active',), False),
        )
    
    def get_examples(self) -> list:
        """获取示例语句列表"""
        if self.examples:
            return self.examples if isinstance(self.examples, list) else []
        return []
    
    def set_examples(self, examples: list):
        """设置示例语句列表"""
        self.examples = examples
    
    def is_high_priority(self) -> bool:
        """判断是否为高优先级意图"""
        return self.priority >= 10
    
    def meets_threshold(self, confidence: float) -> bool:
        """检查置信度是否达到阈值"""
        return confidence >= float(self.confidence_threshold)
    
    def get_required_slots(self):
        """获取必填槽位"""
        return self.slots.where(self.slots.model.is_required == True)
    
    def get_optional_slots(self):
        """获取可选槽位"""
        return self.slots.where(self.slots.model.is_required == False)
    
    def get_active_function_calls(self):
        """获取激活的功能调用"""
        return self.function_calls.where(self.function_calls.model.is_active == True)
    
    def has_function_calls(self) -> bool:
        """检查是否有功能调用"""
        return self.function_calls.count() > 0
    
    def validate_examples(self) -> bool:
        """验证示例语句格式"""
        examples = self.get_examples()
        if not examples:
            return False
        return all(isinstance(ex, str) and len(ex.strip()) > 0 for ex in examples)
    
    @classmethod
    def get_active_intents(cls):
        """获取所有激活的意图"""
        return cls.select().where(cls.is_active == True).order_by(cls.priority.desc())
    
    @classmethod
    def search_by_name(cls, name: str):
        """按名称搜索意图"""
        return cls.select().where(
            (cls.intent_name.contains(name)) | 
            (cls.display_name.contains(name))
        )
    
    def __str__(self):
        return f"Intent({self.intent_name}: {self.display_name})"


