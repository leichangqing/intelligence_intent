"""
模板配置相关数据模型
"""
from peewee import *
from .base import CommonModel
from .intent import Intent
import json


class PromptTemplate(CommonModel):
    """Prompt模板配置表"""
    
    template_name = CharField(max_length=100, verbose_name="模板名称")
    template_type = CharField(max_length=50, verbose_name="模板类型")  # intent_recognition, slot_extraction, disambiguation
    intent = ForeignKeyField(Intent, null=True, backref='templates', on_delete='CASCADE', verbose_name="关联意图")
    template_content = TextField(verbose_name="模板内容")
    variables = TextField(null=True, verbose_name="模板变量JSON")
    version = CharField(max_length=20, default='1.0', verbose_name="模板版本")
    priority = IntegerField(default=0, verbose_name="模板优先级")
    is_active = BooleanField(default=True, verbose_name="是否激活")
    is_default = BooleanField(default=False, verbose_name="是否为默认模板")
    ab_test_config = TextField(null=True, verbose_name="A/B测试配置JSON")
    performance_metrics = TextField(null=True, verbose_name="性能指标JSON")
    description = TextField(null=True, verbose_name="模板描述")
    
    class Meta:
        table_name = 'prompt_templates'
        indexes = (
            (('template_name', 'intent', 'template_type'), True),  # 联合唯一索引
            (('template_type',), False),
            (('intent',), False),
            (('is_active',), False),
            (('priority',), False),
        )
    
    def get_variables(self) -> list:
        """获取模板变量列表"""
        if self.variables:
            try:
                return json.loads(self.variables)
            except json.JSONDecodeError:
                return []
        return []
    
    def set_variables(self, variables: list):
        """设置模板变量列表"""
        self.variables = json.dumps(variables, ensure_ascii=False)
    
    def get_ab_test_config(self) -> dict:
        """获取A/B测试配置"""
        if self.ab_test_config:
            try:
                return json.loads(self.ab_test_config)
            except json.JSONDecodeError:
                return {}
        return {}
    
    def set_ab_test_config(self, config: dict):
        """设置A/B测试配置"""
        self.ab_test_config = json.dumps(config, ensure_ascii=False)
    
    def get_performance_metrics(self) -> dict:
        """获取性能指标"""
        if self.performance_metrics:
            try:
                return json.loads(self.performance_metrics)
            except json.JSONDecodeError:
                return {}
        return {}
    
    def set_performance_metrics(self, metrics: dict):
        """设置性能指标"""
        self.performance_metrics = json.dumps(metrics, ensure_ascii=False)
    
    def render_template(self, context: dict) -> str:
        """
        渲染模板内容
        
        Args:
            context: 模板上下文变量
            
        Returns:
            str: 渲染后的模板内容
        """
        content = self.template_content
        
        # 简单的变量替换
        for variable in self.get_variables():
            if variable in context:
                placeholder = f"{{{variable}}}"
                content = content.replace(placeholder, str(context[variable]))
        
        return content
    
    def is_intent_specific(self) -> bool:
        """判断是否为特定意图的模板"""
        return self.intent is not None
    
    def is_global_template(self) -> bool:
        """判断是否为全局模板"""
        return self.intent is None
    
    def __str__(self):
        intent_name = self.intent.intent_name if self.intent else "global"
        return f"PromptTemplate({intent_name}.{self.template_name})"


class TemplateVersion(CommonModel):
    """模板版本历史表"""
    
    template = ForeignKeyField(PromptTemplate, backref='versions', on_delete='CASCADE', verbose_name="模板")
    version_number = CharField(max_length=20, verbose_name="版本号")
    template_content = TextField(verbose_name="模板内容")
    variables = TextField(null=True, verbose_name="模板变量JSON")
    change_log = TextField(null=True, verbose_name="变更日志")
    created_by = CharField(max_length=100, null=True, verbose_name="创建者")
    is_published = BooleanField(default=False, verbose_name="是否已发布")
    
    class Meta:
        table_name = 'template_versions'
        indexes = (
            (('template', 'version_number'), True),  # 联合唯一索引
            (('template', 'is_published'), False),
            (('created_at',), False),
        )
    
    def get_variables(self) -> list:
        """获取模板变量列表"""
        if self.variables:
            try:
                return json.loads(self.variables)
            except json.JSONDecodeError:
                return []
        return []
    
    def publish(self):
        """发布版本"""
        # 将其他版本设为未发布
        TemplateVersion.update(is_published=False).where(
            TemplateVersion.template == self.template
        ).execute()
        
        # 发布当前版本
        self.is_published = True
        self.save()
        
        # 更新主模板
        self.template.template_content = self.template_content
        self.template.variables = self.variables
        self.template.version = self.version_number
        self.template.save()
    
    def __str__(self):
        return f"TemplateVersion({self.template.template_name} v{self.version_number})"


class ABTestConfig(CommonModel):
    """A/B测试配置表"""
    
    test_name = CharField(max_length=100, unique=True, verbose_name="测试名称")
    template = ForeignKeyField(PromptTemplate, backref='ab_tests', on_delete='CASCADE', verbose_name="模板")
    version_a = CharField(max_length=20, verbose_name="版本A")
    version_b = CharField(max_length=20, verbose_name="版本B")
    traffic_split = DecimalField(max_digits=3, decimal_places=2, default=0.5, verbose_name="流量分割比例")
    test_duration_days = IntegerField(default=7, verbose_name="测试持续天数")
    start_date = DateTimeField(null=True, verbose_name="开始日期")
    end_date = DateTimeField(null=True, verbose_name="结束日期")
    is_active = BooleanField(default=True, verbose_name="是否激活")
    test_results = TextField(null=True, verbose_name="测试结果JSON")
    winner_version = CharField(max_length=20, null=True, verbose_name="获胜版本")
    
    class Meta:
        table_name = 'ab_test_configs'
        indexes = (
            (('template',), False),
            (('is_active',), False),
            (('start_date', 'end_date'), False),
        )
    
    def get_test_results(self) -> dict:
        """获取测试结果"""
        if self.test_results:
            try:
                return json.loads(self.test_results)
            except json.JSONDecodeError:
                return {}
        return {}
    
    def set_test_results(self, results: dict):
        """设置测试结果"""
        self.test_results = json.dumps(results, ensure_ascii=False)
    
    def is_running(self) -> bool:
        """判断测试是否正在运行"""
        from datetime import datetime
        now = datetime.now()
        return (self.is_active and 
                self.start_date and self.start_date <= now and
                (not self.end_date or self.end_date >= now))
    
    def should_use_version_b(self, user_hash: str) -> bool:
        """判断是否应该使用版本B"""
        # 基于用户哈希值确定版本
        import hashlib
        hash_value = int(hashlib.md5(user_hash.encode()).hexdigest(), 16)
        return (hash_value % 100) / 100 < float(self.traffic_split)
    
    def complete_test(self, winner_version: str):
        """完成测试"""
        self.is_active = False
        self.winner_version = winner_version
        from datetime import datetime
        self.end_date = datetime.now()
        self.save()
    
    def __str__(self):
        return f"ABTest({self.test_name}: {self.version_a} vs {self.version_b})"