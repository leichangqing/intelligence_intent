"""
同义词管理模型
用于维护系统中的同义词词典
"""
from peewee import *
from playhouse.mysql_ext import JSONField
from .base import CommonModel
import json


class SynonymGroup(CommonModel):
    """同义词组表"""
    
    group_name = CharField(max_length=100, unique=True, verbose_name="同义词组名称")
    standard_term = CharField(max_length=100, verbose_name="标准词汇")
    description = TextField(null=True, verbose_name="描述")
    category = CharField(max_length=50, null=True, verbose_name="分类")
    is_active = BooleanField(default=True, verbose_name="是否激活")
    priority = IntegerField(default=1, verbose_name="优先级")
    created_by = CharField(max_length=100, null=True, verbose_name="创建人")
    
    class Meta:
        table_name = 'synonym_groups'
        indexes = (
            (('standard_term',), False),
            (('category',), False),
            (('is_active',), False),
            (('priority',), False),
        )
    
    def __str__(self):
        return f"SynonymGroup({self.group_name}: {self.standard_term})"


class SynonymTerm(CommonModel):
    """同义词条表"""
    
    group = ForeignKeyField(SynonymGroup, backref='terms', on_delete='CASCADE', verbose_name="同义词组")
    term = CharField(max_length=100, verbose_name="同义词")
    confidence = DecimalField(max_digits=5, decimal_places=4, default=1.0000, verbose_name="相似度")
    context_tags = JSONField(null=True, verbose_name="上下文标签")
    usage_count = BigIntegerField(default=0, verbose_name="使用次数")
    is_active = BooleanField(default=True, verbose_name="是否激活")
    created_by = CharField(max_length=100, null=True, verbose_name="创建人")
    
    class Meta:
        table_name = 'synonym_terms'
        indexes = (
            (('group', 'term'), True),  # 组合唯一索引
            (('term',), False),
            (('confidence',), False),
            (('usage_count',), False),
            (('is_active',), False),
        )
    
    def get_context_tags(self) -> list:
        """获取上下文标签列表"""
        if self.context_tags:
            return self.context_tags if isinstance(self.context_tags, list) else []
        return []
    
    def add_context_tag(self, tag: str):
        """添加上下文标签"""
        tags = self.get_context_tags()
        if tag not in tags:
            tags.append(tag)
            self.context_tags = tags
            self.save()
    
    def increment_usage(self):
        """增加使用次数"""
        self.usage_count += 1
        self.save()
    
    def __str__(self):
        return f"SynonymTerm({self.term} -> {self.group.standard_term})"


class StopWord(CommonModel):
    """停用词表"""
    
    word = CharField(max_length=50, unique=True, verbose_name="停用词")
    category = CharField(max_length=30, null=True, verbose_name="分类")
    language = CharField(max_length=10, default='zh', verbose_name="语言")
    is_active = BooleanField(default=True, verbose_name="是否激活")
    created_by = CharField(max_length=100, null=True, verbose_name="创建人")
    
    class Meta:
        table_name = 'stop_words'
        indexes = (
            (('word',), True),
            (('category',), False),
            (('language',), False),
            (('is_active',), False),
        )
    
    def __str__(self):
        return f"StopWord({self.word})"
    
    @classmethod
    def get_active_words(cls, language: str = 'zh', category: str = None) -> set:
        """获取激活的停用词集合"""
        query = cls.select().where(
            (cls.is_active == True) & 
            (cls.language == language)
        )
        
        if category:
            query = query.where(cls.category == category)
        
        return {word.word for word in query}


class EntityPattern(CommonModel):
    """实体识别模式表"""
    
    pattern_name = CharField(max_length=50, unique=True, verbose_name="模式名称")
    pattern_regex = TextField(verbose_name="正则表达式")
    entity_type = CharField(max_length=50, verbose_name="实体类型")
    description = TextField(null=True, verbose_name="描述")
    examples = JSONField(null=True, verbose_name="示例")
    confidence = DecimalField(max_digits=5, decimal_places=4, default=0.9000, verbose_name="置信度")
    is_active = BooleanField(default=True, verbose_name="是否激活")
    priority = IntegerField(default=1, verbose_name="优先级")
    created_by = CharField(max_length=100, null=True, verbose_name="创建人")
    
    class Meta:
        table_name = 'entity_patterns'
        indexes = (
            (('pattern_name',), True),
            (('entity_type',), False),
            (('is_active',), False),
            (('priority',), False),
        )
    
    def get_examples(self) -> list:
        """获取示例列表"""
        if self.examples:
            return self.examples if isinstance(self.examples, list) else []
        return []
    
    def set_examples(self, examples: list):
        """设置示例列表"""
        self.examples = examples
        self.save()
    
    def __str__(self):
        return f"EntityPattern({self.pattern_name}: {self.entity_type})"
    
    @classmethod
    def get_active_patterns(cls) -> dict:
        """获取激活的实体模式字典"""
        patterns = cls.select().where(cls.is_active == True).order_by(cls.priority.desc())
        return {pattern.pattern_name: pattern.pattern_regex for pattern in patterns}