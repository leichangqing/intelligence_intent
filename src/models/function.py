"""
函数相关数据模型
"""
from peewee import *
from .base import CommonModel
import json
from datetime import datetime
from typing import Dict, List, Any, Optional


class Function(CommonModel):
    """函数定义表"""
    
    function_name = CharField(max_length=100, unique=True, verbose_name="函数名称")
    display_name = CharField(max_length=200, null=True, verbose_name="显示名称")
    description = TextField(null=True, verbose_name="函数描述")
    category = CharField(max_length=50, null=True, verbose_name="函数分类")
    implementation = TextField(null=True, verbose_name="实现配置JSON")
    is_active = BooleanField(default=True, verbose_name="是否激活")
    version = CharField(max_length=20, default="1.0.0", verbose_name="版本号")
    
    class Meta:
        table_name = 'functions'
        indexes = (
            (('function_name',), True),  # 唯一索引
            (('category',), False),
            (('is_active',), False),
        )
    
    def get_implementation(self) -> Dict[str, Any]:
        """获取实现配置"""
        if self.implementation:
            try:
                return json.loads(self.implementation)
            except json.JSONDecodeError:
                return {}
        return {}
    
    def set_implementation(self, config: Dict[str, Any]):
        """设置实现配置"""
        self.implementation = json.dumps(config, ensure_ascii=False)
    
    def is_python_function(self) -> bool:
        """检查是否为Python函数实现"""
        impl = self.get_implementation()
        return impl.get('type') == 'python_code'
    
    def is_api_function(self) -> bool:
        """检查是否为API函数实现"""
        impl = self.get_implementation()
        return impl.get('type') == 'api_call'
    
    def get_entry_point(self) -> str:
        """获取入口点函数名"""
        impl = self.get_implementation()
        return impl.get('entry_point', self.function_name)
    
    def __str__(self):
        return f"Function({self.function_name})"


class FunctionParameter(CommonModel):
    """函数参数定义表"""
    
    function = ForeignKeyField(Function, backref='parameters', on_delete='CASCADE', verbose_name="所属函数")
    parameter_name = CharField(max_length=100, verbose_name="参数名称")
    parameter_type = CharField(max_length=50, default='str', verbose_name="参数类型")
    description = TextField(null=True, verbose_name="参数描述")
    is_required = BooleanField(default=True, verbose_name="是否必需")
    default_value = TextField(null=True, verbose_name="默认值")
    validation_rule = TextField(null=True, verbose_name="验证规则JSON")
    
    class Meta:
        table_name = 'function_parameters'
        indexes = (
            (('function', 'parameter_name'), True),  # 联合唯一索引
            (('parameter_name',), False),
            (('is_required',), False),
        )
    
    def get_validation_rule(self) -> Dict[str, Any]:
        """获取验证规则"""
        if self.validation_rule:
            try:
                return json.loads(self.validation_rule)
            except json.JSONDecodeError:
                return {}
        return {}
    
    def set_validation_rule(self, rule: Dict[str, Any]):
        """设置验证规则"""
        self.validation_rule = json.dumps(rule, ensure_ascii=False)
    
    def get_parsed_default_value(self) -> Any:
        """获取解析后的默认值"""
        if not self.default_value:
            return None
        
        try:
            # 尝试解析JSON
            return json.loads(self.default_value)
        except json.JSONDecodeError:
            # 如果不是JSON，返回原始字符串
            return self.default_value
    
    def validate_value(self, value: Any) -> bool:
        """验证参数值"""
        try:
            # 基本类型检查
            if self.parameter_type == 'int':
                int(value)
            elif self.parameter_type == 'float':
                float(value)
            elif self.parameter_type == 'bool':
                if not isinstance(value, bool):
                    raise ValueError("Value must be boolean")
            elif self.parameter_type == 'list':
                if not isinstance(value, list):
                    raise ValueError("Value must be list")
            elif self.parameter_type == 'dict':
                if not isinstance(value, dict):
                    raise ValueError("Value must be dict")
            
            # 验证规则检查
            validation_rule = self.get_validation_rule()
            if validation_rule:
                if 'min_length' in validation_rule and len(str(value)) < validation_rule['min_length']:
                    return False
                if 'max_length' in validation_rule and len(str(value)) > validation_rule['max_length']:
                    return False
                if 'min_value' in validation_rule and float(value) < validation_rule['min_value']:
                    return False
                if 'max_value' in validation_rule and float(value) > validation_rule['max_value']:
                    return False
                if 'pattern' in validation_rule:
                    import re
                    if not re.match(validation_rule['pattern'], str(value)):
                        return False
            
            return True
            
        except (ValueError, TypeError):
            return False
    
    def __str__(self):
        return f"FunctionParameter({self.function.function_name}.{self.parameter_name})"


class FunctionCall(CommonModel):
    """函数调用记录表"""
    
    function = ForeignKeyField(Function, backref='call_logs', on_delete='SET NULL', null=True, verbose_name="函数定义")
    user_id = CharField(max_length=100, null=True, verbose_name="用户ID")
    input_parameters = TextField(null=True, verbose_name="输入参数JSON")
    output_result = TextField(null=True, verbose_name="输出结果JSON")
    context_data = TextField(null=True, verbose_name="上下文数据JSON")
    status = CharField(max_length=20, default='pending', verbose_name="执行状态")
    execution_time = FloatField(null=True, verbose_name="执行时间(秒)")
    error_message = TextField(null=True, verbose_name="错误信息")
    completed_at = DateTimeField(null=True, verbose_name="完成时间")
    
    class Meta:
        table_name = 'function_call_logs'
        indexes = (
            (('function',), False),
            (('user_id',), False),
            (('status',), False),
            (('created_at',), False),
        )
    
    def get_input_parameters(self) -> Dict[str, Any]:
        """获取输入参数"""
        if self.input_parameters:
            try:
                return json.loads(self.input_parameters)
            except json.JSONDecodeError:
                return {}
        return {}
    
    def set_input_parameters(self, params: Dict[str, Any]):
        """设置输入参数"""
        self.input_parameters = json.dumps(params, ensure_ascii=False)
    
    def get_output_result(self) -> Any:
        """获取输出结果"""
        if self.output_result:
            try:
                return json.loads(self.output_result)
            except json.JSONDecodeError:
                return self.output_result
        return None
    
    def set_output_result(self, result: Any):
        """设置输出结果"""
        if result is not None:
            self.output_result = json.dumps(result, ensure_ascii=False, default=str)
    
    def get_context_data(self) -> Dict[str, Any]:
        """获取上下文数据"""
        if self.context_data:
            try:
                return json.loads(self.context_data)
            except json.JSONDecodeError:
                return {}
        return {}
    
    def set_context_data(self, context: Dict[str, Any]):
        """设置上下文数据"""
        self.context_data = json.dumps(context, ensure_ascii=False)
    
    def mark_executing(self):
        """标记为执行中"""
        self.status = 'executing'
    
    def mark_completed(self, result: Any, execution_time: float):
        """标记为已完成"""
        self.status = 'completed'
        self.set_output_result(result)
        self.execution_time = execution_time
        self.completed_at = datetime.now()
        self.error_message = None
    
    def mark_failed(self, error_message: str, execution_time: float = None):
        """标记为失败"""
        self.status = 'failed'
        self.error_message = error_message
        if execution_time is not None:
            self.execution_time = execution_time
        self.completed_at = datetime.now()
    
    def is_pending(self) -> bool:
        """检查是否为待执行状态"""
        return self.status == 'pending'
    
    def is_executing(self) -> bool:
        """检查是否为执行中状态"""
        return self.status == 'executing'
    
    def is_completed(self) -> bool:
        """检查是否为已完成状态"""
        return self.status == 'completed'
    
    def is_failed(self) -> bool:
        """检查是否为失败状态"""
        return self.status == 'failed'
    
    def __str__(self):
        function_name = self.function.function_name if self.function else 'Unknown'
        return f"FunctionCall({function_name}: {self.status})"