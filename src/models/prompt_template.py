"""
模板相关数据模型
"""
from peewee import *
from playhouse.mysql_ext import JSONField
from .base import CommonModel
from .intent import Intent
import json


class PromptTemplate(CommonModel):
    """Prompt模板配置表"""
    
    template_name = CharField(max_length=100, unique=True, verbose_name="模板名称")
    template_type = CharField(max_length=20, verbose_name="模板类型",
                             constraints=[Check("template_type IN ('intent_recognition', 'slot_filling', 'response_generation', 'disambiguation', 'fallback')")])
    intent = ForeignKeyField(Intent, null=True, on_delete='SET NULL', verbose_name="关联意图ID")
    template_content = TextField(verbose_name="模板内容")
    variables = JSONField(null=True, verbose_name="模板变量")
    language = CharField(max_length=10, default='zh-CN', verbose_name="语言")
    version = CharField(max_length=20, default='1.0', verbose_name="版本号")
    priority = IntegerField(default=1, verbose_name="优先级")
    usage_count = IntegerField(default=0, verbose_name="使用次数")
    success_rate = DecimalField(max_digits=5, decimal_places=4, default=0.0000, verbose_name="成功率")
    is_active = BooleanField(default=True, verbose_name="是否激活")
    created_by = CharField(max_length=100, null=True, verbose_name="创建人")
    
    class Meta:
        table_name = 'prompt_templates'
        indexes = (
            (('template_type',), False),
            (('intent', 'template_type'), False),
            (('priority',), False),
            (('is_active',), False),
            (('language',), False),
        )
    
    def get_variables(self) -> list:
        """获取模板变量列表"""
        if self.variables:
            return self.variables if isinstance(self.variables, list) else []
        return []
    
    def set_variables(self, variables: list):
        """设置模板变量"""
        self.variables = variables
    
    def is_intent_recognition_template(self) -> bool:
        """判断是否为意图识别模板"""
        return self.template_type == 'intent_recognition'
    
    def is_slot_filling_template(self) -> bool:
        """判断是否为槽位填充模板"""
        return self.template_type == 'slot_filling'
    
    def is_response_generation_template(self) -> bool:
        """判断是否为响应生成模板"""
        return self.template_type == 'response_generation'
    
    def is_disambiguation_template(self) -> bool:
        """判断是否为歧义澄清模板"""
        return self.template_type == 'disambiguation'
    
    def is_fallback_template(self) -> bool:
        """判断是否为兜底模板"""
        return self.template_type == 'fallback'
    
    def render(self, context: dict = None) -> str:
        """
        渲染模板
        
        Args:
            context: 上下文变量字典
            
        Returns:
            str: 渲染后的文本
        """
        if not context:
            context = {}
        
        content = self.template_content
        
        # 简单的变量替换
        for key, value in context.items():
            placeholder = f"{{{key}}}"
            content = content.replace(placeholder, str(value))
        
        return content
    
    def validate_template(self) -> tuple:
        """
        验证模板格式
        
        Returns:
            tuple: (是否有效, 错误信息)
        """
        if not self.template_content:
            return False, "模板内容不能为空"
        
        # 检查变量是否在模板中使用
        variables = self.get_variables()
        content = self.template_content
        
        missing_vars = []
        for var in variables:
            if f"{{{var}}}" not in content:
                missing_vars.append(var)
        
        if missing_vars:
            return False, f"模板中缺少变量: {', '.join(missing_vars)}"
        
        return True, ""
    
    def increment_usage(self, success: bool = True):
        """增加使用次数并更新成功率"""
        self.usage_count += 1
        
        if success:
            # 更新成功率（简单的移动平均）
            current_success_count = float(self.success_rate) * (self.usage_count - 1)
            new_success_count = current_success_count + 1
            self.success_rate = new_success_count / self.usage_count
        else:
            # 重新计算成功率
            current_success_count = float(self.success_rate) * (self.usage_count - 1)
            self.success_rate = current_success_count / self.usage_count
    
    def is_high_performing(self, threshold: float = 0.8) -> bool:
        """判断是否为高性能模板"""
        return float(self.success_rate) >= threshold and self.usage_count >= 10
    
    @classmethod
    def get_by_type(cls, template_type: str, intent_id: int = None):
        """获取指定类型的模板"""
        query = cls.select().where(
            cls.template_type == template_type,
            cls.is_active == True
        )
        
        if intent_id:
            query = query.where(cls.intent == intent_id)
        
        return query.order_by(cls.priority.desc(), cls.success_rate.desc())
    
    @classmethod
    def get_best_template(cls, template_type: str, intent_id: int = None):
        """获取最佳模板"""
        templates = cls.get_by_type(template_type, intent_id)
        
        if templates.exists():
            return templates.first()
        
        # 如果没找到指定意图的模板，尝试获取通用模板
        if intent_id:
            return cls.get_best_template(template_type, None)
        
        return None
    
    @classmethod
    def search_templates(cls, keyword: str):
        """搜索模板"""
        return cls.select().where(
            (cls.template_name.contains(keyword)) |
            (cls.template_content.contains(keyword)),
            cls.is_active == True
        )
    
    def __str__(self):
        return f"PromptTemplate({self.template_name}: {self.template_type})"