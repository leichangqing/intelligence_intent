"""
参数验证和映射系统
提供统一的参数验证、类型转换、映射和约束检查功能
"""

import re
import json
import asyncio
from typing import Dict, List, Optional, Any, Union, Callable, Tuple, Type
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime, date, time, timedelta
from decimal import Decimal, InvalidOperation
import inspect
from abc import ABC, abstractmethod

from src.utils.logger import get_logger

logger = get_logger(__name__)


class ParameterType(Enum):
    """参数类型枚举"""
    STRING = "string"
    INTEGER = "integer"
    FLOAT = "float"
    BOOLEAN = "boolean"
    DATE = "date"
    DATETIME = "datetime"
    TIME = "time"
    DECIMAL = "decimal"
    LIST = "list"
    DICT = "dict"
    OBJECT = "object"
    ANY = "any"
    EMAIL = "email"
    URL = "url"
    PHONE = "phone"
    UUID = "uuid"
    JSON = "json"
    ENUM = "enum"
    FILE = "file"


class ValidationType(Enum):
    """验证类型枚举"""
    REQUIRED = "required"
    TYPE_CHECK = "type_check"
    LENGTH = "length"
    RANGE = "range"
    PATTERN = "pattern"
    ENUM_VALUES = "enum_values"
    CUSTOM = "custom"
    DEPENDENCY = "dependency"
    BUSINESS_RULE = "business_rule"
    CONDITIONAL = "conditional"


class ValidationSeverity(Enum):
    """验证严重程度"""
    ERROR = "error"       # 阻止执行
    WARNING = "warning"   # 记录但继续
    INFO = "info"        # 仅记录


@dataclass
class ValidationRule:
    """验证规则"""
    name: str
    validation_type: ValidationType
    severity: ValidationSeverity = ValidationSeverity.ERROR
    enabled: bool = True
    
    # 基础约束
    required: bool = False
    nullable: bool = True
    
    # 长度约束
    min_length: Optional[int] = None
    max_length: Optional[int] = None
    
    # 数值约束
    min_value: Optional[Union[int, float, Decimal]] = None
    max_value: Optional[Union[int, float, Decimal]] = None
    
    # 模式约束
    pattern: Optional[str] = None
    pattern_flags: int = 0
    
    # 枚举约束
    enum_values: Optional[List[Any]] = None
    case_sensitive: bool = True
    
    # 自定义验证
    custom_validator: Optional[Callable] = None
    custom_message: Optional[str] = None
    
    # 条件验证
    condition: Optional[Callable] = None
    
    # 元数据
    description: Optional[str] = None
    error_message: Optional[str] = None


@dataclass
class ParameterSchema:
    """参数模式定义"""
    name: str
    parameter_type: ParameterType
    description: Optional[str] = None
    
    # 默认值
    default_value: Any = None
    has_default: bool = False
    
    # 验证规则
    rules: List[ValidationRule] = field(default_factory=list)
    
    # 类型转换
    auto_convert: bool = True
    converter: Optional[Callable] = None
    
    # 映射配置
    source_name: Optional[str] = None  # 源参数名
    aliases: List[str] = field(default_factory=list)  # 别名
    
    # 嵌套参数（for object/dict types）
    nested_schema: Optional[Dict[str, 'ParameterSchema']] = None
    
    # 列表元素类型（for list type）
    item_type: Optional[ParameterType] = None
    item_schema: Optional['ParameterSchema'] = None
    
    # 元数据
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ValidationResult:
    """验证结果"""
    is_valid: bool
    parameter_name: str
    value: Any
    converted_value: Any = None
    
    # 错误和警告
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    
    # 规则检查结果
    rule_results: Dict[str, bool] = field(default_factory=dict)
    
    # 元数据
    processing_time: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ParameterMappingRule:
    """参数映射规则"""
    source_name: str
    target_name: str
    transformation: Optional[Callable] = None
    default_value: Any = None
    condition: Optional[Callable] = None
    description: Optional[str] = None


class BaseValidator(ABC):
    """基础验证器抽象类"""
    
    @abstractmethod
    async def validate(self, value: Any, rule: ValidationRule, context: Dict[str, Any] = None) -> Tuple[bool, str]:
        """执行验证"""
        pass


class TypeValidator(BaseValidator):
    """类型验证器"""
    
    async def validate(self, value: Any, rule: ValidationRule, context: Dict[str, Any] = None) -> Tuple[bool, str]:
        """类型验证"""
        if value is None and rule.nullable:
            return True, ""
        
        try:
            parameter_type = context.get('parameter_type', ParameterType.ANY)
            
            if parameter_type == ParameterType.STRING:
                return isinstance(value, str), f"期望字符串类型，得到 {type(value).__name__}"
            elif parameter_type == ParameterType.INTEGER:
                return isinstance(value, int) and not isinstance(value, bool), f"期望整数类型，得到 {type(value).__name__}"
            elif parameter_type == ParameterType.FLOAT:
                return isinstance(value, (int, float)) and not isinstance(value, bool), f"期望浮点数类型，得到 {type(value).__name__}"
            elif parameter_type == ParameterType.BOOLEAN:
                return isinstance(value, bool), f"期望布尔类型，得到 {type(value).__name__}"
            elif parameter_type == ParameterType.LIST:
                return isinstance(value, list), f"期望列表类型，得到 {type(value).__name__}"
            elif parameter_type == ParameterType.DICT:
                return isinstance(value, dict), f"期望字典类型，得到 {type(value).__name__}"
            elif parameter_type == ParameterType.DATE:
                return isinstance(value, (date, datetime, str)), f"期望日期类型，得到 {type(value).__name__}"
            elif parameter_type == ParameterType.EMAIL:
                if not isinstance(value, str):
                    return False, f"邮箱必须是字符串类型，得到 {type(value).__name__}"
                pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
                return bool(re.match(pattern, value)), "无效的邮箱格式"
            elif parameter_type == ParameterType.URL:
                if not isinstance(value, str):
                    return False, f"URL必须是字符串类型，得到 {type(value).__name__}"
                pattern = r'^https?://(?:[-\w.])+(?:[:\d]+)?(?:/(?:[\w/_.])*(?:\?(?:[\w&=%.])*)?(?:#(?:\w*))?)?$'
                return bool(re.match(pattern, value)), "无效的URL格式"
            elif parameter_type == ParameterType.PHONE:
                if not isinstance(value, str):
                    return False, f"电话号码必须是字符串类型，得到 {type(value).__name__}"
                # 支持多种电话格式
                patterns = [
                    r'^\d{11}$',  # 11位手机号
                    r'^\d{3}-\d{4}-\d{4}$',  # xxx-xxxx-xxxx
                    r'^\(\d{3}\) \d{3}-\d{4}$',  # (xxx) xxx-xxxx
                ]
                return any(re.match(pattern, value) for pattern in patterns), "无效的电话号码格式"
            elif parameter_type == ParameterType.UUID:
                if not isinstance(value, str):
                    return False, f"UUID必须是字符串类型，得到 {type(value).__name__}"
                pattern = r'^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$'
                return bool(re.match(pattern, value, re.IGNORECASE)), "无效的UUID格式"
            
            return True, ""
            
        except Exception as e:
            return False, f"类型验证错误: {str(e)}"


class LengthValidator(BaseValidator):
    """长度验证器"""
    
    async def validate(self, value: Any, rule: ValidationRule, context: Dict[str, Any] = None) -> Tuple[bool, str]:
        """长度验证"""
        if value is None and rule.nullable:
            return True, ""
        
        try:
            length = len(value) if hasattr(value, '__len__') else len(str(value))
            
            if rule.min_length is not None and length < rule.min_length:
                return False, f"长度不能少于 {rule.min_length}，当前长度 {length}"
            
            if rule.max_length is not None and length > rule.max_length:
                return False, f"长度不能超过 {rule.max_length}，当前长度 {length}"
            
            return True, ""
            
        except Exception as e:
            return False, f"长度验证错误: {str(e)}"


class RangeValidator(BaseValidator):
    """范围验证器"""
    
    async def validate(self, value: Any, rule: ValidationRule, context: Dict[str, Any] = None) -> Tuple[bool, str]:
        """范围验证"""
        if value is None and rule.nullable:
            return True, ""
        
        try:
            numeric_value = float(value) if not isinstance(value, (int, float)) else value
            
            if rule.min_value is not None and numeric_value < rule.min_value:
                return False, f"值不能小于 {rule.min_value}，当前值 {numeric_value}"
            
            if rule.max_value is not None and numeric_value > rule.max_value:
                return False, f"值不能大于 {rule.max_value}，当前值 {numeric_value}"
            
            return True, ""
            
        except (ValueError, TypeError) as e:
            return False, f"范围验证错误: 无法转换为数值类型"
        except Exception as e:
            return False, f"范围验证错误: {str(e)}"


class PatternValidator(BaseValidator):
    """模式验证器"""
    
    async def validate(self, value: Any, rule: ValidationRule, context: Dict[str, Any] = None) -> Tuple[bool, str]:
        """模式验证"""
        if value is None and rule.nullable:
            return True, ""
        
        if not rule.pattern:
            return True, ""
        
        try:
            str_value = str(value)
            flags = rule.pattern_flags or 0
            
            if re.match(rule.pattern, str_value, flags):
                return True, ""
            else:
                return False, f"值不匹配模式 {rule.pattern}"
                
        except Exception as e:
            return False, f"模式验证错误: {str(e)}"


class EnumValidator(BaseValidator):
    """枚举验证器"""
    
    async def validate(self, value: Any, rule: ValidationRule, context: Dict[str, Any] = None) -> Tuple[bool, str]:
        """枚举验证"""
        if value is None and rule.nullable:
            return True, ""
        
        if not rule.enum_values:
            return True, ""
        
        try:
            if rule.case_sensitive:
                valid = value in rule.enum_values
            else:
                # 不区分大小写的比较
                str_value = str(value).lower()
                valid = any(str(enum_val).lower() == str_value for enum_val in rule.enum_values)
            
            if valid:
                return True, ""
            else:
                return False, f"值必须是 {rule.enum_values} 中的一个，当前值 {value}"
                
        except Exception as e:
            return False, f"枚举验证错误: {str(e)}"


class CustomValidator(BaseValidator):
    """自定义验证器"""
    
    async def validate(self, value: Any, rule: ValidationRule, context: Dict[str, Any] = None) -> Tuple[bool, str]:
        """自定义验证"""
        if not rule.custom_validator:
            return True, ""
        
        try:
            if asyncio.iscoroutinefunction(rule.custom_validator):
                result = await rule.custom_validator(value, context)
            else:
                result = rule.custom_validator(value, context)
            
            if isinstance(result, bool):
                return result, rule.custom_message or ("验证通过" if result else "自定义验证失败")
            elif isinstance(result, tuple) and len(result) == 2:
                return result[0], result[1]
            else:
                return bool(result), rule.custom_message or ("验证通过" if result else "自定义验证失败")
                
        except Exception as e:
            return False, f"自定义验证错误: {str(e)}"


class TypeConverter:
    """类型转换器"""
    
    @staticmethod
    async def convert(value: Any, target_type: ParameterType, 
                     converter: Optional[Callable] = None) -> Tuple[Any, bool, str]:
        """类型转换"""
        if value is None:
            return None, True, ""
        
        # 使用自定义转换器
        if converter:
            try:
                if asyncio.iscoroutinefunction(converter):
                    converted = await converter(value)
                else:
                    converted = converter(value)
                return converted, True, ""
            except Exception as e:
                return value, False, f"自定义转换错误: {str(e)}"
        
        try:
            # 内置类型转换
            if target_type == ParameterType.STRING:
                return str(value), True, ""
            
            elif target_type == ParameterType.INTEGER:
                if isinstance(value, bool):
                    return int(value), True, ""
                if isinstance(value, str):
                    # 处理数字字符串
                    cleaned = re.sub(r'[,\s]', '', value)
                    return int(float(cleaned)), True, ""
                return int(value), True, ""
            
            elif target_type == ParameterType.FLOAT:
                if isinstance(value, str):
                    cleaned = re.sub(r'[,\s]', '', value)
                    return float(cleaned), True, ""
                return float(value), True, ""
            
            elif target_type == ParameterType.BOOLEAN:
                if isinstance(value, str):
                    lower_val = value.lower().strip()
                    if lower_val in ('true', '1', 'yes', 'on', '是', '真'):
                        return True, True, ""
                    elif lower_val in ('false', '0', 'no', 'off', '否', '假'):
                        return False, True, ""
                    else:
                        return bool(value), True, ""
                return bool(value), True, ""
            
            elif target_type == ParameterType.DECIMAL:
                if isinstance(value, str):
                    cleaned = re.sub(r'[,\s]', '', value)
                    return Decimal(cleaned), True, ""
                return Decimal(str(value)), True, ""
            
            elif target_type == ParameterType.DATE:
                if isinstance(value, str):
                    # 尝试多种日期格式
                    date_formats = [
                        '%Y-%m-%d',
                        '%Y/%m/%d',
                        '%d/%m/%Y',
                        '%m/%d/%Y',
                        '%Y年%m月%d日',
                        '%m月%d日',
                    ]
                    
                    # 处理相对日期
                    if value in ['今天', 'today']:
                        return date.today(), True, ""
                    elif value in ['明天', 'tomorrow']:
                        return date.today() + timedelta(days=1), True, ""
                    elif value in ['昨天', 'yesterday']:
                        return date.today() - timedelta(days=1), True, ""
                    
                    # 尝试解析标准格式
                    for fmt in date_formats:
                        try:
                            return datetime.strptime(value, fmt).date(), True, ""
                        except ValueError:
                            continue
                    
                    return value, False, f"无法解析日期格式: {value}"
                
                elif isinstance(value, datetime):
                    return value.date(), True, ""
                elif isinstance(value, date):
                    return value, True, ""
                
                return value, False, f"无法转换为日期类型: {type(value)}"
            
            elif target_type == ParameterType.DATETIME:
                if isinstance(value, str):
                    datetime_formats = [
                        '%Y-%m-%d %H:%M:%S',
                        '%Y-%m-%d %H:%M',
                        '%Y/%m/%d %H:%M:%S',
                        '%Y/%m/%d %H:%M',
                        '%Y-%m-%dT%H:%M:%S',
                        '%Y-%m-%dT%H:%M:%SZ',
                    ]
                    
                    for fmt in datetime_formats:
                        try:
                            return datetime.strptime(value, fmt), True, ""
                        except ValueError:
                            continue
                    
                    return value, False, f"无法解析日期时间格式: {value}"
                
                elif isinstance(value, date):
                    return datetime.combine(value, time.min), True, ""
                elif isinstance(value, datetime):
                    return value, True, ""
                
                return value, False, f"无法转换为日期时间类型: {type(value)}"
            
            elif target_type == ParameterType.LIST:
                if isinstance(value, str):
                    try:
                        # 尝试JSON解析
                        return json.loads(value), True, ""
                    except json.JSONDecodeError:
                        # 尝试逗号分割
                        return [item.strip() for item in value.split(',')], True, ""
                elif isinstance(value, (list, tuple)):
                    return list(value), True, ""
                else:
                    return [value], True, ""
            
            elif target_type == ParameterType.DICT:
                if isinstance(value, str):
                    try:
                        return json.loads(value), True, ""
                    except json.JSONDecodeError:
                        return {'value': value}, True, ""
                elif isinstance(value, dict):
                    return value, True, ""
                else:
                    return {'value': value}, True, ""
            
            elif target_type == ParameterType.JSON:
                if isinstance(value, str):
                    return json.loads(value), True, ""
                else:
                    return value, True, ""
            
            else:
                # 其他类型或ANY类型直接返回
                return value, True, ""
                
        except (ValueError, TypeError, InvalidOperation, json.JSONDecodeError) as e:
            return value, False, f"类型转换失败: {str(e)}"
        except Exception as e:
            return value, False, f"转换错误: {str(e)}"


class ParameterValidator:
    """参数验证器主类"""
    
    def __init__(self):
        self.validators = {
            ValidationType.TYPE_CHECK: TypeValidator(),
            ValidationType.LENGTH: LengthValidator(),
            ValidationType.RANGE: RangeValidator(),
            ValidationType.PATTERN: PatternValidator(),
            ValidationType.ENUM_VALUES: EnumValidator(),
            ValidationType.CUSTOM: CustomValidator(),
        }
        
        self.converter = TypeConverter()
        
        # 验证统计
        self.stats = {
            'total_validations': 0,
            'successful_validations': 0,
            'failed_validations': 0,
            'conversion_count': 0,
            'average_processing_time': 0.0
        }
    
    async def validate_parameter(self, value: Any, schema: ParameterSchema, 
                               context: Dict[str, Any] = None) -> ValidationResult:
        """验证单个参数"""
        start_time = datetime.now()
        context = context or {}
        
        result = ValidationResult(
            is_valid=True,
            parameter_name=schema.name,
            value=value,
            converted_value=value
        )
        
        try:
            self.stats['total_validations'] += 1
            
            # 1. 检查是否为空值
            if value is None:
                if any(rule.required for rule in schema.rules):
                    result.is_valid = False
                    result.errors.append(f"参数 {schema.name} 是必需的")
                    return result
                
                # 使用默认值
                if schema.has_default:
                    result.converted_value = schema.default_value
                    return result
            
            # 2. 类型转换
            if schema.auto_convert and value is not None:
                converted_value, conversion_success, conversion_error = await self.converter.convert(
                    value, schema.parameter_type, schema.converter
                )
                
                if conversion_success:
                    result.converted_value = converted_value
                    self.stats['conversion_count'] += 1
                else:
                    result.warnings.append(f"类型转换失败: {conversion_error}")
                    # 继续使用原值进行验证
            
            # 3. 执行验证规则
            validation_context = {
                **context,
                'parameter_type': schema.parameter_type,
                'schema': schema
            }
            
            for rule in schema.rules:
                if not rule.enabled:
                    continue
                
                # 检查条件
                if rule.condition and not rule.condition(result.converted_value, validation_context):
                    continue
                
                # 处理必需验证规则
                if rule.validation_type == ValidationType.REQUIRED:
                    if result.converted_value is None:
                        result.is_valid = False
                        result.errors.append(rule.error_message or f"参数 {schema.name} 是必需的")
                        result.rule_results[rule.name] = False
                        continue
                    else:
                        result.rule_results[rule.name] = True
                        continue
                
                validator = self.validators.get(rule.validation_type)
                if not validator:
                    continue
                
                rule_valid, rule_message = await validator.validate(
                    result.converted_value, rule, validation_context
                )
                
                result.rule_results[rule.name] = rule_valid
                
                if not rule_valid:
                    error_message = rule.error_message or rule_message
                    
                    if rule.severity == ValidationSeverity.ERROR:
                        result.is_valid = False
                        result.errors.append(error_message)
                    elif rule.severity == ValidationSeverity.WARNING:
                        result.warnings.append(error_message)
            
            # 4. 嵌套验证（for object/dict types）
            if schema.parameter_type in [ParameterType.DICT, ParameterType.OBJECT] and schema.nested_schema:
                if isinstance(result.converted_value, dict):
                    nested_results = await self.validate_parameters(
                        result.converted_value, schema.nested_schema, context
                    )
                    
                    for nested_result in nested_results.values():
                        if not nested_result.is_valid:
                            result.is_valid = False
                            result.errors.extend([f"{schema.name}.{err}" for err in nested_result.errors])
                        result.warnings.extend([f"{schema.name}.{warn}" for warn in nested_result.warnings])
            
            # 5. 列表元素验证（for list type）
            if schema.parameter_type == ParameterType.LIST and schema.item_schema:
                if isinstance(result.converted_value, list):
                    for i, item in enumerate(result.converted_value):
                        item_result = await self.validate_parameter(
                            item, schema.item_schema, context
                        )
                        
                        if not item_result.is_valid:
                            result.is_valid = False
                            result.errors.extend([f"{schema.name}[{i}].{err}" for err in item_result.errors])
                        result.warnings.extend([f"{schema.name}[{i}].{warn}" for warn in item_result.warnings])
            
            # 更新统计
            if result.is_valid:
                self.stats['successful_validations'] += 1
            else:
                self.stats['failed_validations'] += 1
                
        except Exception as e:
            result.is_valid = False
            result.errors.append(f"验证过程发生错误: {str(e)}")
            logger.error(f"参数验证错误: {schema.name}, {str(e)}")
        
        finally:
            # 记录处理时间
            processing_time = (datetime.now() - start_time).total_seconds()
            result.processing_time = processing_time
            
            # 更新平均处理时间
            total_validations = self.stats['total_validations']
            current_avg = self.stats['average_processing_time']
            self.stats['average_processing_time'] = (
                (current_avg * (total_validations - 1)) + processing_time
            ) / total_validations
        
        return result
    
    async def validate_parameters(self, parameters: Dict[str, Any], 
                                schemas: Dict[str, ParameterSchema],
                                context: Dict[str, Any] = None) -> Dict[str, ValidationResult]:
        """验证多个参数"""
        results = {}
        
        # 并行验证
        validation_tasks = []
        for param_name, schema in schemas.items():
            param_value = parameters.get(param_name)
            
            # 检查别名
            if param_value is None and schema.aliases:
                for alias in schema.aliases:
                    if alias in parameters:
                        param_value = parameters[alias]
                        break
            
            # 检查源名称映射
            if param_value is None and schema.source_name:
                param_value = parameters.get(schema.source_name)
            
            task = self.validate_parameter(param_value, schema, context)
            validation_tasks.append((param_name, task))
        
        # 等待所有验证完成
        for param_name, task in validation_tasks:
            results[param_name] = await task
        
        return results
    
    def get_statistics(self) -> Dict[str, Any]:
        """获取验证统计信息"""
        return self.stats.copy()


class ParameterMapper:
    """参数映射器"""
    
    def __init__(self):
        self.mapping_rules: List[ParameterMappingRule] = []
        self.cached_mappings: Dict[str, Dict[str, Any]] = {}
    
    def add_mapping_rule(self, rule: ParameterMappingRule):
        """添加映射规则"""
        self.mapping_rules.append(rule)
        # 清除缓存
        self.cached_mappings.clear()
    
    def add_mapping(self, source_name: str, target_name: str, 
                   transformation: Optional[Callable] = None,
                   default_value: Any = None,
                   condition: Optional[Callable] = None,
                   description: Optional[str] = None):
        """添加参数映射"""
        rule = ParameterMappingRule(
            source_name=source_name,
            target_name=target_name,
            transformation=transformation,
            default_value=default_value,
            condition=condition,
            description=description
        )
        self.add_mapping_rule(rule)
    
    async def map_parameters(self, source_params: Dict[str, Any], 
                           context: Dict[str, Any] = None) -> Dict[str, Any]:
        """执行参数映射"""
        context = context or {}
        mapped_params = {}
        
        for rule in self.mapping_rules:
            try:
                # 检查条件
                if rule.condition and not rule.condition(source_params, context):
                    continue
                
                # 获取源值
                source_value = source_params.get(rule.source_name, rule.default_value)
                
                if source_value is not None:
                    # 应用转换
                    if rule.transformation:
                        if asyncio.iscoroutinefunction(rule.transformation):
                            mapped_value = await rule.transformation(source_value, context)
                        else:
                            mapped_value = rule.transformation(source_value, context)
                    else:
                        mapped_value = source_value
                    
                    mapped_params[rule.target_name] = mapped_value
                
            except Exception as e:
                logger.warning(f"参数映射失败: {rule.source_name} -> {rule.target_name}, {str(e)}")
        
        # 复制未映射的参数
        mapped_source_names = [rule.source_name for rule in self.mapping_rules]
        for key, value in source_params.items():
            if key not in mapped_source_names:
                mapped_params[key] = value
        
        return mapped_params
    
    def get_mapping_info(self) -> List[Dict[str, Any]]:
        """获取映射信息"""
        return [
            {
                'source_name': rule.source_name,
                'target_name': rule.target_name,
                'has_transformation': rule.transformation is not None,
                'has_condition': rule.condition is not None,
                'default_value': rule.default_value,
                'description': rule.description
            }
            for rule in self.mapping_rules
        ]


# 预定义验证规则创建函数
def create_required_rule(name: str = "required") -> ValidationRule:
    """创建必需验证规则"""
    return ValidationRule(
        name=name,
        validation_type=ValidationType.REQUIRED,
        required=True,
        error_message="该字段是必需的"
    )


def create_length_rule(name: str = "length", min_len: int = None, max_len: int = None) -> ValidationRule:
    """创建长度验证规则"""
    return ValidationRule(
        name=name,
        validation_type=ValidationType.LENGTH,
        min_length=min_len,
        max_length=max_len,
        error_message=f"长度必须在 {min_len or 0} 和 {max_len or '∞'} 之间"
    )


def create_range_rule(name: str = "range", min_val: Union[int, float] = None, 
                     max_val: Union[int, float] = None) -> ValidationRule:
    """创建范围验证规则"""
    return ValidationRule(
        name=name,
        validation_type=ValidationType.RANGE,
        min_value=min_val,
        max_value=max_val,
        error_message=f"值必须在 {min_val or '-∞'} 和 {max_val or '∞'} 之间"
    )


def create_pattern_rule(name: str = "pattern", pattern: str = None, 
                       flags: int = 0) -> ValidationRule:
    """创建模式验证规则"""
    return ValidationRule(
        name=name,
        validation_type=ValidationType.PATTERN,
        pattern=pattern,
        pattern_flags=flags,
        error_message=f"值必须匹配模式: {pattern}"
    )


def create_enum_rule(name: str = "enum", values: List[Any] = None, 
                    case_sensitive: bool = True) -> ValidationRule:
    """创建枚举验证规则"""
    return ValidationRule(
        name=name,
        validation_type=ValidationType.ENUM_VALUES,
        enum_values=values or [],
        case_sensitive=case_sensitive,
        error_message=f"值必须是 {values} 中的一个"
    )


def create_custom_rule(name: str = "custom", validator: Callable = None, 
                      message: str = None) -> ValidationRule:
    """创建自定义验证规则"""
    return ValidationRule(
        name=name,
        validation_type=ValidationType.CUSTOM,
        custom_validator=validator,
        custom_message=message,
        error_message=message or "自定义验证失败"
    )


# 全局验证器实例
_global_validator: Optional[ParameterValidator] = None
_global_mapper: Optional[ParameterMapper] = None


def get_parameter_validator() -> ParameterValidator:
    """获取全局参数验证器实例"""
    global _global_validator
    if _global_validator is None:
        _global_validator = ParameterValidator()
    return _global_validator


def get_parameter_mapper() -> ParameterMapper:
    """获取全局参数映射器实例"""
    global _global_mapper
    if _global_mapper is None:
        _global_mapper = ParameterMapper()
    return _global_mapper