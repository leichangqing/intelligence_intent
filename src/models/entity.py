"""
实体相关数据模型
"""
from peewee import *
from playhouse.mysql_ext import JSONField
from .base import CommonModel
import json


class EntityType(CommonModel):
    """实体类型定义表"""
    
    entity_type_code = CharField(max_length=50, unique=True, verbose_name="实体类型代码")
    entity_type_name = CharField(max_length=100, verbose_name="实体类型名称")
    description = TextField(null=True, verbose_name="类型描述")
    category = CharField(max_length=50, null=True, verbose_name="实体分类")
    extraction_patterns = JSONField(null=True, verbose_name="提取模式")
    validation_rules = JSONField(null=True, verbose_name="验证规则")
    normalization_rules = JSONField(null=True, verbose_name="标准化规则")
    synonyms = JSONField(null=True, verbose_name="同义词")
    parent_type = ForeignKeyField('self', null=True, on_delete='SET NULL', verbose_name="父类型ID")
    is_system_type = BooleanField(default=False, verbose_name="是否为系统类型")
    is_active = BooleanField(default=True, verbose_name="是否激活")
    
    class Meta:
        table_name = 'entity_types'
        indexes = (
            (('entity_type_code',), False),
            (('category',), False),
            (('parent_type',), False),
            (('is_system_type',), False),
            (('is_active',), False),
        )
    
    def get_extraction_patterns(self) -> list:
        """获取提取模式"""
        if self.extraction_patterns:
            return self.extraction_patterns if isinstance(self.extraction_patterns, list) else []
        return []
    
    def get_validation_rules(self) -> dict:
        """获取验证规则"""
        if self.validation_rules:
            return self.validation_rules if isinstance(self.validation_rules, dict) else {}
        return {}
    
    def get_normalization_rules(self) -> dict:
        """获取标准化规则"""
        if self.normalization_rules:
            return self.normalization_rules if isinstance(self.normalization_rules, dict) else {}
        return {}
    
    def get_synonyms(self) -> list:
        """获取同义词列表"""
        if self.synonyms:
            return self.synonyms if isinstance(self.synonyms, list) else []
        return []
    
    def is_system(self) -> bool:
        """判断是否为系统内置类型"""
        return self.is_system_type
    
    def has_parent(self) -> bool:
        """判断是否有父类型"""
        return self.parent_type is not None
    
    @classmethod
    def get_system_types(cls):
        """获取所有系统类型"""
        return cls.select().where(cls.is_system_type == True, cls.is_active == True)
    
    @classmethod
    def get_by_category(cls, category: str):
        """按分类获取实体类型"""
        return cls.select().where(cls.category == category, cls.is_active == True)
    
    def __str__(self):
        return f"EntityType({self.entity_type_code}: {self.entity_type_name})"


class EntityDictionary(CommonModel):
    """实体词典表"""
    
    entity_type = ForeignKeyField(EntityType, backref='entities', on_delete='CASCADE', verbose_name="实体类型ID")
    entity_value = CharField(max_length=200, verbose_name="实体值")
    canonical_form = CharField(max_length=200, null=True, verbose_name="标准形式")
    aliases = JSONField(null=True, verbose_name="别名列表")
    confidence_weight = DecimalField(max_digits=5, decimal_places=4, default=1.0000, verbose_name="置信度权重")
    context_hints = JSONField(null=True, verbose_name="上下文提示")
    metadata = JSONField(null=True, verbose_name="元数据")
    frequency_count = IntegerField(default=0, verbose_name="使用频次")
    last_used_at = DateTimeField(null=True, verbose_name="最后使用时间")
    is_active = BooleanField(default=True, verbose_name="是否激活")
    created_by = CharField(max_length=100, null=True, verbose_name="创建人")
    
    class Meta:
        table_name = 'entity_dictionary'
        indexes = (
            (('entity_type', 'entity_value'), False),
            (('canonical_form',), False),
            (('frequency_count',), False),
            (('last_used_at',), False),
            (('is_active',), False),
        )
    
    def get_aliases(self) -> list:
        """获取别名列表"""
        if self.aliases:
            return self.aliases if isinstance(self.aliases, list) else []
        return []
    
    def get_context_hints(self) -> dict:
        """获取上下文提示"""
        if self.context_hints:
            return self.context_hints if isinstance(self.context_hints, dict) else {}
        return {}
    
    def get_metadata(self) -> dict:
        """获取元数据"""
        if self.metadata:
            return self.metadata if isinstance(self.metadata, dict) else {}
        return {}
    
    def get_canonical_value(self) -> str:
        """获取标准形式，如果没有则返回原值"""
        return self.canonical_form if self.canonical_form else self.entity_value
    
    def increment_usage(self):
        """增加使用次数"""
        from datetime import datetime
        self.frequency_count += 1
        self.last_used_at = datetime.now()
    
    def is_frequently_used(self, threshold: int = 10) -> bool:
        """判断是否为高频使用实体"""
        return self.frequency_count >= threshold
    
    def matches_text(self, text: str) -> bool:
        """检查文本是否匹配此实体"""
        text_lower = text.lower()
        # 检查主值
        if self.entity_value.lower() in text_lower:
            return True
        # 检查标准形式
        if self.canonical_form and self.canonical_form.lower() in text_lower:
            return True
        # 检查别名
        for alias in self.get_aliases():
            if str(alias).lower() in text_lower:
                return True
        return False
    
    @classmethod
    def search_by_value(cls, value: str, entity_type_code: str = None):
        """按值搜索实体"""
        query = cls.select().where(cls.is_active == True)
        
        if entity_type_code:
            query = query.join(EntityType).where(EntityType.entity_type_code == entity_type_code)
        
        # 精确匹配
        exact_matches = query.where(
            (cls.entity_value == value) |
            (cls.canonical_form == value)
        )
        
        if exact_matches.exists():
            return exact_matches
        
        # 模糊匹配
        fuzzy_matches = query.where(
            (cls.entity_value.contains(value)) |
            (cls.canonical_form.contains(value))
        )
        
        return fuzzy_matches
    
    @classmethod
    def get_by_type(cls, entity_type_code: str):
        """获取指定类型的所有实体"""
        return cls.select().join(EntityType).where(
            EntityType.entity_type_code == entity_type_code,
            cls.is_active == True
        ).order_by(cls.frequency_count.desc())
    
    @classmethod
    def get_popular_entities(cls, limit: int = 100):
        """获取热门实体"""
        return cls.select().where(cls.is_active == True).order_by(
            cls.frequency_count.desc()
        ).limit(limit)
    
    def __str__(self):
        return f"Entity({self.entity_type.entity_type_code}.{self.entity_value})"