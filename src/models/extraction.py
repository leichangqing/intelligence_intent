"""
槽位提取规则相关数据模型
"""
from peewee import *
from playhouse.mysql_ext import JSONField
from .base import CommonModel
from .slot import Slot
import json


class SlotExtractionRule(CommonModel):
    """槽位提取规则表"""
    
    slot = ForeignKeyField(Slot, backref='extraction_rules', on_delete='CASCADE', verbose_name="槽位ID")
    rule_type = CharField(max_length=20, verbose_name="规则类型",
                         constraints=[Check("rule_type IN ('regex', 'entity', 'keyword', 'ml_model', 'api_call')")])
    rule_pattern = TextField(verbose_name="规则模式")
    rule_config = JSONField(null=True, verbose_name="规则配置")
    priority = IntegerField(default=1, verbose_name="优先级")
    confidence_boost = DecimalField(max_digits=5, decimal_places=4, default=0.0000, verbose_name="置信度加成")
    is_active = BooleanField(default=True, verbose_name="是否激活")
    
    class Meta:
        table_name = 'slot_extraction_rules'
        indexes = (
            (('slot', 'priority'), False),
            (('rule_type',), False),
            (('is_active',), False),
        )
    
    def get_rule_config(self) -> dict:
        """获取规则配置"""
        if self.rule_config:
            return self.rule_config if isinstance(self.rule_config, dict) else {}
        return {}
    
    def set_rule_config(self, config: dict):
        """设置规则配置"""
        self.rule_config = config
    
    def is_regex_rule(self) -> bool:
        """判断是否为正则表达式规则"""
        return self.rule_type == 'regex'
    
    def is_entity_rule(self) -> bool:
        """判断是否为实体识别规则"""
        return self.rule_type == 'entity'
    
    def is_keyword_rule(self) -> bool:
        """判断是否为关键词规则"""
        return self.rule_type == 'keyword'
    
    def is_ml_model_rule(self) -> bool:
        """判断是否为机器学习模型规则"""
        return self.rule_type == 'ml_model'
    
    def is_api_call_rule(self) -> bool:
        """判断是否为API调用规则"""
        return self.rule_type == 'api_call'
    
    def extract_value(self, text: str) -> tuple:
        """
        从文本中提取值
        
        Args:
            text: 输入文本
            
        Returns:
            tuple: (是否成功, 提取的值, 置信度)
        """
        try:
            if self.is_regex_rule():
                return self._extract_by_regex(text)
            elif self.is_keyword_rule():
                return self._extract_by_keyword(text)
            elif self.is_entity_rule():
                return self._extract_by_entity(text)
            elif self.is_ml_model_rule():
                return self._extract_by_ml_model(text)
            elif self.is_api_call_rule():
                return self._extract_by_api_call(text)
            else:
                return False, None, 0.0
        except Exception as e:
            return False, None, 0.0
    
    def _extract_by_regex(self, text: str) -> tuple:
        """使用正则表达式提取"""
        import re
        
        try:
            pattern = self.rule_pattern
            config = self.get_rule_config()
            flags = 0
            
            if config.get('ignore_case', False):
                flags |= re.IGNORECASE
            
            match = re.search(pattern, text, flags)
            if match:
                # 如果有捕获组，返回第一个捕获组
                value = match.group(1) if match.groups() else match.group(0)
                confidence = min(1.0, 0.8 + float(self.confidence_boost))
                return True, value.strip(), confidence
            
            return False, None, 0.0
        except re.error:
            return False, None, 0.0
    
    def _extract_by_keyword(self, text: str) -> tuple:
        """使用关键词提取"""
        config = self.get_rule_config()
        keywords = config.get('keywords', [])
        exact_match = config.get('exact_match', False)
        
        text_lower = text.lower()
        
        for keyword in keywords:
            keyword_lower = str(keyword).lower()
            
            if exact_match:
                if keyword_lower == text_lower:
                    confidence = min(1.0, 0.9 + float(self.confidence_boost))
                    return True, str(keyword), confidence
            else:
                if keyword_lower in text_lower:
                    confidence = min(1.0, 0.7 + float(self.confidence_boost))
                    return True, str(keyword), confidence
        
        return False, None, 0.0
    
    def _extract_by_entity(self, text: str) -> tuple:
        """使用实体识别提取"""
        from .entity import EntityDictionary, EntityType
        
        config = self.get_rule_config()
        entity_type_code = config.get('entity_type')
        min_confidence = config.get('min_confidence', 0.5)
        
        if not entity_type_code:
            return False, None, 0.0
        
        # 搜索匹配的实体
        entities = EntityDictionary.search_by_value(text, entity_type_code)
        
        for entity in entities:
            if entity.matches_text(text):
                # 根据匹配类型计算置信度
                confidence = 0.6  # 基础置信度
                
                if entity.entity_value.lower() == text.lower():
                    confidence = 0.95  # 精确匹配
                elif entity.canonical_form and entity.canonical_form.lower() == text.lower():
                    confidence = 0.9   # 标准形式匹配
                elif text.lower() in [str(alias).lower() for alias in entity.get_aliases()]:
                    confidence = 0.85  # 别名匹配
                
                # 加上置信度加成
                confidence = min(1.0, confidence + float(self.confidence_boost))
                
                if confidence >= min_confidence:
                    # 增加使用次数
                    entity.increment_usage()
                    entity.save()
                    
                    return True, entity.get_canonical_value(), confidence
        
        return False, None, 0.0
    
    def _extract_by_ml_model(self, text: str) -> tuple:
        """使用机器学习模型提取"""
        # TODO: 实现机器学习模型调用
        # 这里需要根据具体的ML模型服务来实现
        config = self.get_rule_config()
        model_endpoint = config.get('model_endpoint')
        
        if not model_endpoint:
            return False, None, 0.0
        
        # 暂时返回失败，等待具体实现
        return False, None, 0.0
    
    def _extract_by_api_call(self, text: str) -> tuple:
        """使用API调用提取"""
        # TODO: 实现API调用
        # 这里需要根据具体的API服务来实现
        config = self.get_rule_config()
        api_endpoint = config.get('api_endpoint')
        
        if not api_endpoint:
            return False, None, 0.0
        
        # 暂时返回失败，等待具体实现
        return False, None, 0.0
    
    @classmethod
    def get_rules_for_slot(cls, slot_id: int):
        """获取指定槽位的所有提取规则"""
        return cls.select().where(
            cls.slot == slot_id,
            cls.is_active == True
        ).order_by(cls.priority.desc())
    
    @classmethod
    def extract_slot_value(cls, slot_id: int, text: str) -> tuple:
        """
        为指定槽位提取值
        
        Args:
            slot_id: 槽位ID
            text: 输入文本
            
        Returns:
            tuple: (是否成功, 提取的值, 置信度, 使用的规则)
        """
        rules = cls.get_rules_for_slot(slot_id)
        
        best_result = None
        best_confidence = 0.0
        best_rule = None
        
        for rule in rules:
            success, value, confidence = rule.extract_value(text)
            
            if success and confidence > best_confidence:
                best_result = value
                best_confidence = confidence
                best_rule = rule
        
        if best_result is not None:
            return True, best_result, best_confidence, best_rule
        
        return False, None, 0.0, None
    
    def __str__(self):
        return f"ExtractionRule({self.slot.slot_name}.{self.rule_type})"