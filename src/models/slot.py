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
        """获取枚举选项列表"""
        if self.is_enum_type():
            rules = self.get_validation_rules()
            return rules.get('options', [])
        return []
    
    def get_default_value(self):
        """获取默认值"""
        rules = self.get_validation_rules()
        return rules.get('default')
    
    def format_prompt(self, context: dict = None) -> str:
        """格式化询问模板"""
        if not self.prompt_template:
            return f"请提供{self.slot_name}的值："
        
        # 简单的模板变量替换
        prompt = self.prompt_template
        if context:
            for key, value in context.items():
                prompt = prompt.replace(f"{{{key}}}", str(value))
        
        return prompt
    
    @classmethod
    def get_required_slots_for_intent(cls, intent_id: int):
        """获取指定意图的必填槽位"""
        return cls.select().where(
            cls.intent == intent_id,
            cls.is_required == True
        )
    
    @classmethod  
    def get_slots_by_type(cls, slot_type: str):
        """按类型获取槽位"""
        return cls.select().where(cls.slot_type == slot_type)
    
    def __str__(self):
        return f"Slot({self.intent.intent_name}.{self.slot_name})"


class SlotValue(CommonModel):
    """槽位值存储表"""
    
    conversation_id = BigIntegerField(verbose_name="对话ID")
    slot = ForeignKeyField(Slot, backref='values', on_delete='CASCADE', verbose_name="关联槽位")
    slot_name = CharField(max_length=100, verbose_name="槽位名称")
    original_text = TextField(null=True, verbose_name="原始文本")
    extracted_value = TextField(null=True, verbose_name="提取的值")
    normalized_value = TextField(null=True, verbose_name="标准化后的值")
    confidence = DecimalField(max_digits=5, decimal_places=4, null=True, verbose_name="提取置信度")
    extraction_method = CharField(max_length=50, null=True, verbose_name="提取方法")
    validation_status = CharField(max_length=20, default='pending', verbose_name="验证状态",
                                 constraints=[Check("validation_status IN ('valid', 'invalid', 'pending', 'corrected')")])
    validation_error = TextField(null=True, verbose_name="验证错误信息")
    is_confirmed = BooleanField(default=False, verbose_name="是否已确认")
    
    class Meta:
        table_name = 'slot_values'
        indexes = (
            (('conversation_id', 'slot'), False),
            (('slot_name',), False),
            (('extraction_method',), False),
            (('validation_status',), False),
        )
    
    def get_normalized_value(self):
        """获取标准化值，如果没有则返回原值"""
        return self.normalized_value if self.normalized_value is not None else self.value
    
    def validate(self):
        """验证槽位值"""
        if not self.slot:
            return False, "槽位信息缺失"
        
        return self.slot.validate_value(self.value)
    
    def normalize_value(self):
        """根据槽位类型标准化值"""
        if not self.slot:
            return
        
        if self.slot.slot_type == 'NUMBER':
            try:
                # 尝试转换为数字
                if '.' in str(self.value):
                    self.normalized_value = str(float(self.value))
                else:
                    self.normalized_value = str(int(float(self.value)))
            except (ValueError, TypeError):
                pass
        
        elif self.slot.slot_type == 'TEXT':
            # 文本类型标准化：去除首尾空格，统一换行
            self.normalized_value = str(self.value).strip()
        
        elif self.slot.slot_type == 'DATE':
            # 日期标准化逻辑
            self.normalized_value = self._normalize_date_value()
        
        elif self.slot.slot_type == 'ENUM':
            # 枚举类型：查找最匹配的选项
            self.normalized_value = self._normalize_enum_value()
    
    def _normalize_date_value(self) -> str:
        """标准化日期值"""
        from datetime import datetime, timedelta
        import re
        
        value_str = str(self.value).lower().strip()
        today = datetime.now().date()
        
        # 相对日期处理
        if value_str in ['今天', 'today', '今日']:
            return today.isoformat()
        elif value_str in ['明天', 'tomorrow', '明日']:
            return (today + timedelta(days=1)).isoformat()
        elif value_str in ['后天', 'day after tomorrow']:
            return (today + timedelta(days=2)).isoformat()
        elif value_str in ['昨天', 'yesterday', '昨日']:
            return (today - timedelta(days=1)).isoformat()
        elif value_str in ['大后天']:
            return (today + timedelta(days=3)).isoformat()
        
        # 星期处理
        weekdays = {
            '周一': 0, '星期一': 0, 'monday': 0, '周二': 1, '星期二': 1, 'tuesday': 1,
            '周三': 2, '星期三': 2, 'wednesday': 2, '周四': 3, '星期四': 3, 'thursday': 3,
            '周五': 4, '星期五': 4, 'friday': 4, '周六': 5, '星期六': 5, 'saturday': 5,
            '周日': 6, '星期日': 6, 'sunday': 6
        }
        
        for weekday_name, weekday_num in weekdays.items():
            if weekday_name in value_str:
                days_ahead = weekday_num - today.weekday()
                if days_ahead <= 0:  # 下周的这一天
                    days_ahead += 7
                target_date = today + timedelta(days=days_ahead)
                return target_date.isoformat()
        
        # 尝试解析标准日期格式
        date_patterns = [
            r'(\d{4})-(\d{1,2})-(\d{1,2})',  # YYYY-MM-DD
            r'(\d{1,2})/(\d{1,2})/(\d{4})',  # MM/DD/YYYY
            r'(\d{1,2})-(\d{1,2})',          # MM-DD (当年)
        ]
        
        for pattern in date_patterns:
            match = re.search(pattern, value_str)
            if match:
                try:
                    if len(match.groups()) == 3:
                        if pattern.startswith(r'(\d{4})'):  # YYYY-MM-DD
                            year, month, day = match.groups()
                        else:  # MM/DD/YYYY
                            month, day, year = match.groups()
                        parsed_date = datetime(int(year), int(month), int(day)).date()
                    else:  # MM-DD
                        month, day = match.groups()
                        year = today.year
                        parsed_date = datetime(year, int(month), int(day)).date()
                        # 如果日期已过，使用下一年
                        if parsed_date < today:
                            parsed_date = datetime(year + 1, int(month), int(day)).date()
                    
                    return parsed_date.isoformat()
                except ValueError:
                    continue
        
        # 如果无法解析，返回原值
        return str(self.value)
    
    def _normalize_enum_value(self) -> str:
        """标准化枚举值 - 查找最匹配的选项"""
        options = self.slot.get_enum_options()
        if not options:
            return str(self.value)
        
        value_str = str(self.value).lower().strip()
        
        # 精确匹配
        for option in options:
            if str(option).lower() == value_str:
                return str(option)
        
        # 模糊匹配
        for option in options:
            if value_str in str(option).lower() or str(option).lower() in value_str:
                return str(option)
        
        # 如果都不匹配，返回第一个选项作为默认值
        return str(options[0]) if options else str(self.value)
    
    def __str__(self):
        return f"SlotValue({self.slot.slot_name}={self.value})"


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
            parent_slot = Slot.get_by_id(self.parent_slot_id)
            child_slot = Slot.get_by_id(self.child_slot_id)
            
            parent_slot_name = parent_slot.slot_name
            child_slot_name = child_slot.slot_name
        except Slot.DoesNotExist:
            return False, "依赖关系中的槽位不存在"
        
        # 基本依赖检查：被依赖的槽位必须有值
        if self.dependency_type == 'required':
            if parent_slot_name not in slot_values or slot_values[parent_slot_name] is None:
                return False, f"槽位 {child_slot_name} 需要先填写 {parent_slot_name}"
        
        # 条件依赖检查
        elif self.dependency_type == 'conditional':
            condition = self.get_condition()
            if not self._evaluate_condition(condition, slot_values):
                condition_desc = condition.get('description', '特定条件')
                return False, f"槽位 {child_slot_name} 在 {condition_desc} 时才需要填写"
        
        # 互斥依赖检查
        elif self.dependency_type == 'mutex':
            if (parent_slot_name in slot_values and slot_values[parent_slot_name] is not None and
                child_slot_name in slot_values and slot_values[child_slot_name] is not None):
                return False, f"槽位 {child_slot_name} 和 {parent_slot_name} 不能同时填写"
        
        return True, ""
    
    def _evaluate_condition(self, condition: dict, slot_values: dict) -> bool:
        """评估条件表达式"""
        if not condition:
            return True
        
        try:
            parent_slot = Slot.get_by_id(self.parent_slot_id)
            default_target_slot = parent_slot.slot_name
        except Slot.DoesNotExist:
            default_target_slot = "unknown_slot"
        
        condition_type = condition.get('type', 'value_equals')
        target_slot = condition.get('slot', default_target_slot)
        expected_value = condition.get('value')
        
        if target_slot not in slot_values:
            return False
        
        actual_value = slot_values[target_slot]
        
        if condition_type == 'value_equals':
            return str(actual_value) == str(expected_value)
        elif condition_type == 'value_in':
            return actual_value in expected_value if isinstance(expected_value, list) else False
        elif condition_type == 'value_not_equals':
            return str(actual_value) != str(expected_value)
        elif condition_type == 'has_value':
            return actual_value is not None and str(actual_value).strip() != ''
        
        return True
    
    @classmethod
    def get_dependencies_for_slot(cls, slot_id: int):
        """获取指定槽位的所有依赖关系"""
        return cls.select().where(cls.child_slot_id == slot_id)
    
    @classmethod
    def check_all_dependencies(cls, intent_id: int, slot_values: dict):
        """
        检查意图下所有槽位的依赖关系
        
        Args:
            intent_id: 意图ID
            slot_values: 已提取的槽位值
        
        Returns:
            tuple: (是否全部满足, 错误信息列表)
        """
        # 获取该意图下所有的依赖关系
        dependencies = cls.select().join(Slot, on=(cls.child_slot_id == Slot.id)).where(
            Slot.intent == intent_id
        )
        
        errors = []
        for dependency in dependencies:
            is_satisfied, error_msg = dependency.check_dependency(slot_values)
            if not is_satisfied:
                errors.append(error_msg)
        
        return len(errors) == 0, errors
    
    def __str__(self):
        try:
            parent_slot = Slot.get_by_id(self.parent_slot_id)
            child_slot = Slot.get_by_id(self.child_slot_id)
            return f"SlotDependency({child_slot.slot_name} depends on {parent_slot.slot_name})"
        except Slot.DoesNotExist:
            return f"SlotDependency(child_id={self.child_slot_id} depends on parent_id={self.parent_slot_id})"


