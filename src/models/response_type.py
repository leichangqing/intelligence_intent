"""
响应类型数据模型
"""
from peewee import *
from playhouse.mysql_ext import JSONField
from .base import CommonModel
from datetime import datetime
from typing import Dict, List, Optional


class ResponseType(CommonModel):
    """响应类型表 - 与MySQL Schema对应"""
    
    type_code = CharField(max_length=50, unique=True, verbose_name="类型代码")
    type_name = CharField(max_length=100, verbose_name="类型名称")
    description = TextField(null=True, verbose_name="类型描述")
    category = CharField(max_length=50, null=True, verbose_name="类型分类")
    template_format = CharField(max_length=100, null=True, verbose_name="模板格式")
    default_template = TextField(null=True, verbose_name="默认模板")
    metadata = JSONField(null=True, verbose_name="元数据")
    sort_order = IntegerField(default=1, verbose_name="排序")
    is_active = BooleanField(default=True, verbose_name="是否激活")
    
    class Meta:
        table_name = 'response_types'
        indexes = (
            (('type_code',), False),
            (('category',), False),
            (('is_active', 'sort_order'), False),
            (('category', 'sort_order'), False),
        )
    
    def get_metadata(self) -> dict:
        """获取元数据"""
        if self.metadata:
            return self.metadata if isinstance(self.metadata, dict) else {}
        return {}
    
    def set_metadata(self, metadata: dict):
        """设置元数据"""
        self.metadata = metadata
    
    def update_metadata(self, key: str, value: any):
        """更新元数据中的特定键值"""
        meta = self.get_metadata()
        meta[key] = value
        self.set_metadata(meta)
    
    def get_template_variables(self) -> List[str]:
        """获取模板中的变量名列表"""
        if not self.default_template:
            return []
        
        import re
        # 匹配 {{variable}} 格式的变量
        pattern = r'\{\{([^}]+)\}\}'
        matches = re.findall(pattern, self.default_template)
        return [var.strip() for var in matches]
    
    def format_template(self, variables: Dict[str, any]) -> str:
        """使用给定变量格式化模板"""
        if not self.default_template:
            return ""
        
        template = self.default_template
        for key, value in variables.items():
            placeholder = f"{{{{{key}}}}}"
            template = template.replace(placeholder, str(value))
        
        return template
    
    def validate_template_variables(self, variables: Dict[str, any]) -> List[str]:
        """验证模板变量，返回缺失的变量列表"""
        required_vars = self.get_template_variables()
        missing_vars = []
        
        for var in required_vars:
            if var not in variables or variables[var] is None:
                missing_vars.append(var)
        
        return missing_vars
    
    def is_success_type(self) -> bool:
        """判断是否为成功类型的响应"""
        return self.category == 'success'
    
    def is_interaction_type(self) -> bool:
        """判断是否为交互类型的响应"""
        return self.category == 'interaction'
    
    def is_error_type(self) -> bool:
        """判断是否为错误类型的响应"""
        return self.category in ['error', 'security']
    
    def is_transfer_type(self) -> bool:
        """判断是否为转移类型的响应"""
        return self.category == 'transfer'
    
    def is_control_type(self) -> bool:
        """判断是否为控制类型的响应"""
        return self.category == 'control'
    
    def is_complex_type(self) -> bool:
        """判断是否为复杂类型的响应"""
        return self.category == 'complex'
    
    def is_fallback_type(self) -> bool:
        """判断是否为回退类型的响应"""
        return self.category == 'fallback'
    
    def is_information_type(self) -> bool:
        """判断是否为信息类型的响应"""
        return self.category == 'information'
    
    @classmethod
    def get_by_code(cls, type_code: str) -> Optional['ResponseType']:
        """根据类型代码获取响应类型"""
        try:
            return cls.get(cls.type_code == type_code, cls.is_active == True)
        except cls.DoesNotExist:
            return None
    
    @classmethod
    def get_by_category(cls, category: str, active_only: bool = True) -> List['ResponseType']:
        """根据分类获取响应类型列表"""
        query = cls.select()
        if category:
            query = query.where(cls.category == category)
        if active_only:
            query = query.where(cls.is_active == True)
        
        return list(query.order_by(cls.sort_order, cls.type_name))
    
    @classmethod
    def get_all_categories(cls, active_only: bool = True) -> List[str]:
        """获取所有分类列表"""
        query = cls.select(cls.category).distinct()
        if active_only:
            query = query.where(cls.is_active == True)
        
        categories = [row.category for row in query if row.category]
        return sorted(categories)
    
    @classmethod
    def get_ordered_by_category(cls, active_only: bool = True) -> Dict[str, List['ResponseType']]:
        """按分类获取有序的响应类型字典"""
        query = cls.select()
        if active_only:
            query = query.where(cls.is_active == True)
        
        response_types = list(query.order_by(cls.category, cls.sort_order, cls.type_name))
        
        categorized = {}
        for rt in response_types:
            category = rt.category or 'uncategorized'
            if category not in categorized:
                categorized[category] = []
            categorized[category].append(rt)
        
        return categorized
    
    @classmethod
    def search_by_name_or_description(cls, keyword: str, active_only: bool = True) -> List['ResponseType']:
        """根据名称或描述搜索响应类型"""
        query = cls.select()
        if keyword:
            query = query.where(
                (cls.type_name.contains(keyword)) |
                (cls.description.contains(keyword)) |
                (cls.type_code.contains(keyword))
            )
        if active_only:
            query = query.where(cls.is_active == True)
        
        return list(query.order_by(cls.sort_order, cls.type_name))
    
    @classmethod
    def get_default_for_category(cls, category: str) -> Optional['ResponseType']:
        """获取分类的默认响应类型（排序最前的）"""
        try:
            return cls.select().where(
                cls.category == category,
                cls.is_active == True
            ).order_by(cls.sort_order, cls.type_name).get()
        except cls.DoesNotExist:
            return None
    
    @classmethod
    def bulk_update_sort_order(cls, type_code_order_map: Dict[str, int]):
        """批量更新排序顺序"""
        for type_code, sort_order in type_code_order_map.items():
            try:
                response_type = cls.get(cls.type_code == type_code)
                response_type.sort_order = sort_order
                response_type.save()
            except cls.DoesNotExist:
                continue
    
    @classmethod
    def activate(cls, type_code: str) -> bool:
        """激活响应类型"""
        try:
            response_type = cls.get(cls.type_code == type_code)
            response_type.is_active = True
            response_type.save()
            return True
        except cls.DoesNotExist:
            return False
    
    @classmethod
    def deactivate(cls, type_code: str) -> bool:
        """停用响应类型"""
        try:
            response_type = cls.get(cls.type_code == type_code)
            response_type.is_active = False
            response_type.save()
            return True
        except cls.DoesNotExist:
            return False
    
    def clone_with_new_code(self, new_type_code: str, new_type_name: str = None) -> 'ResponseType':
        """克隆当前响应类型并生成新的类型代码"""
        new_response_type = ResponseType(
            type_code=new_type_code,
            type_name=new_type_name or f"{self.type_name} (Copy)",
            description=self.description,
            category=self.category,
            template_format=self.template_format,
            default_template=self.default_template,
            metadata=self.get_metadata(),
            sort_order=self.sort_order,
            is_active=self.is_active
        )
        new_response_type.save()
        return new_response_type
    
    def __str__(self):
        return f"ResponseType({self.type_code}: {self.type_name})"
    
    def __repr__(self):
        return f"<ResponseType(id={self.id}, code='{self.type_code}', name='{self.type_name}', category='{self.category}')>"