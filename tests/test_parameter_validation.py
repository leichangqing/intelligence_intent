"""
TASK-028: 参数验证和映射测试
测试参数验证系统的各种功能
"""
import pytest
import asyncio
from datetime import datetime, date
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

from src.core.parameter_validator import (
    ParameterValidator, ParameterMapper, ParameterSchema, ParameterType,
    ValidationRule, ValidationType, ValidationSeverity, ParameterMappingRule,
    TypeConverter, create_required_rule, create_length_rule, create_range_rule,
    create_pattern_rule, create_enum_rule, create_custom_rule
)


class TestParameterType:
    """测试参数类型枚举"""
    
    def test_parameter_types(self):
        """测试参数类型定义"""
        assert ParameterType.STRING.value == "string"
        assert ParameterType.INTEGER.value == "integer"
        assert ParameterType.FLOAT.value == "float"
        assert ParameterType.BOOLEAN.value == "boolean"
        assert ParameterType.DATE.value == "date"
        assert ParameterType.EMAIL.value == "email"
        assert ParameterType.URL.value == "url"
        assert ParameterType.PHONE.value == "phone"
        assert ParameterType.UUID.value == "uuid"


class TestValidationRule:
    """测试验证规则"""
    
    def test_create_required_rule(self):
        """测试创建必需验证规则"""
        rule = create_required_rule("test_required")
        assert rule.name == "test_required"
        assert rule.validation_type == ValidationType.REQUIRED
        assert rule.required == True
        assert rule.severity == ValidationSeverity.ERROR
    
    def test_create_length_rule(self):
        """测试创建长度验证规则"""
        rule = create_length_rule("test_length", 5, 50)
        assert rule.name == "test_length"
        assert rule.validation_type == ValidationType.LENGTH
        assert rule.min_length == 5
        assert rule.max_length == 50
    
    def test_create_range_rule(self):
        """测试创建范围验证规则"""
        rule = create_range_rule("test_range", 0, 100)
        assert rule.name == "test_range"
        assert rule.validation_type == ValidationType.RANGE
        assert rule.min_value == 0
        assert rule.max_value == 100
    
    def test_create_pattern_rule(self):
        """测试创建模式验证规则"""
        pattern = r"^[a-zA-Z0-9]+$"
        rule = create_pattern_rule("test_pattern", pattern)
        assert rule.name == "test_pattern"
        assert rule.validation_type == ValidationType.PATTERN
        assert rule.pattern == pattern
    
    def test_create_enum_rule(self):
        """测试创建枚举验证规则"""
        values = ["option1", "option2", "option3"]
        rule = create_enum_rule("test_enum", values)
        assert rule.name == "test_enum"
        assert rule.validation_type == ValidationType.ENUM_VALUES
        assert rule.enum_values == values
    
    def test_create_custom_rule(self):
        """测试创建自定义验证规则"""
        def custom_validator(value, context):
            return value > 0, "Value must be positive"
        
        rule = create_custom_rule("test_custom", custom_validator, "Custom validation")
        assert rule.name == "test_custom"
        assert rule.validation_type == ValidationType.CUSTOM
        assert rule.custom_validator == custom_validator
        assert rule.custom_message == "Custom validation"


class TestParameterSchema:
    """测试参数模式"""
    
    def test_basic_schema(self):
        """测试基础参数模式"""
        schema = ParameterSchema(
            name="test_param",
            parameter_type=ParameterType.STRING,
            description="Test parameter",
            has_default=True,
            default_value="default"
        )
        
        assert schema.name == "test_param"
        assert schema.parameter_type == ParameterType.STRING
        assert schema.description == "Test parameter"
        assert schema.has_default == True
        assert schema.default_value == "default"
        assert schema.auto_convert == True
        assert len(schema.rules) == 0
    
    def test_schema_with_rules(self):
        """测试带验证规则的参数模式"""
        schema = ParameterSchema(
            name="email_param",
            parameter_type=ParameterType.EMAIL
        )
        
        # 添加验证规则
        schema.rules.append(create_required_rule())
        schema.rules.append(create_length_rule("email_length", 5, 100))
        
        assert len(schema.rules) == 2
        assert schema.rules[0].validation_type == ValidationType.REQUIRED
        assert schema.rules[1].validation_type == ValidationType.LENGTH
    
    def test_nested_schema(self):
        """测试嵌套参数模式"""
        nested_schema = {
            "name": ParameterSchema(
                name="name",
                parameter_type=ParameterType.STRING
            ),
            "age": ParameterSchema(
                name="age",
                parameter_type=ParameterType.INTEGER
            )
        }
        
        schema = ParameterSchema(
            name="user_info",
            parameter_type=ParameterType.DICT,
            nested_schema=nested_schema
        )
        
        assert schema.nested_schema is not None
        assert "name" in schema.nested_schema
        assert "age" in schema.nested_schema
        assert schema.nested_schema["name"].parameter_type == ParameterType.STRING
        assert schema.nested_schema["age"].parameter_type == ParameterType.INTEGER


class TestTypeConverter:
    """测试类型转换器"""
    
    @pytest.mark.asyncio
    async def test_string_conversion(self):
        """测试字符串转换"""
        converter = TypeConverter()
        
        # 测试各种类型到字符串的转换
        result, success, error = await converter.convert(123, ParameterType.STRING)
        assert success == True
        assert result == "123"
        assert error == ""
        
        result, success, error = await converter.convert(True, ParameterType.STRING)
        assert success == True
        assert result == "True"
    
    @pytest.mark.asyncio
    async def test_integer_conversion(self):
        """测试整数转换"""
        converter = TypeConverter()
        
        # 字符串到整数
        result, success, error = await converter.convert("123", ParameterType.INTEGER)
        assert success == True
        assert result == 123
        
        # 浮点数到整数
        result, success, error = await converter.convert(123.7, ParameterType.INTEGER)
        assert success == True
        assert result == 123
        
        # 布尔值到整数
        result, success, error = await converter.convert(True, ParameterType.INTEGER)
        assert success == True
        assert result == 1
        
        # 无效转换
        result, success, error = await converter.convert("invalid", ParameterType.INTEGER)
        assert success == False
        assert "类型转换失败" in error
    
    @pytest.mark.asyncio
    async def test_float_conversion(self):
        """测试浮点数转换"""
        converter = TypeConverter()
        
        result, success, error = await converter.convert("123.45", ParameterType.FLOAT)
        assert success == True
        assert result == 123.45
        
        result, success, error = await converter.convert("123", ParameterType.FLOAT)
        assert success == True
        assert result == 123.0
    
    @pytest.mark.asyncio
    async def test_boolean_conversion(self):
        """测试布尔值转换"""
        converter = TypeConverter()
        
        # 真值测试
        for true_value in ["true", "True", "1", "yes", "on", "是", "真"]:
            result, success, error = await converter.convert(true_value, ParameterType.BOOLEAN)
            assert success == True
            assert result == True
        
        # 假值测试
        for false_value in ["false", "False", "0", "no", "off", "否", "假"]:
            result, success, error = await converter.convert(false_value, ParameterType.BOOLEAN)
            assert success == True
            assert result == False
    
    @pytest.mark.asyncio
    async def test_date_conversion(self):
        """测试日期转换"""
        converter = TypeConverter()
        
        # 标准日期格式
        result, success, error = await converter.convert("2023-12-25", ParameterType.DATE)
        assert success == True
        assert isinstance(result, date)
        assert result.year == 2023
        assert result.month == 12
        assert result.day == 25
        
        # 其他日期格式
        result, success, error = await converter.convert("2023/12/25", ParameterType.DATE)
        assert success == True
        assert isinstance(result, date)
        
        # 相对日期
        result, success, error = await converter.convert("今天", ParameterType.DATE)
        assert success == True
        assert isinstance(result, date)
    
    @pytest.mark.asyncio
    async def test_list_conversion(self):
        """测试列表转换"""
        converter = TypeConverter()
        
        # JSON字符串到列表
        result, success, error = await converter.convert('["a", "b", "c"]', ParameterType.LIST)
        assert success == True
        assert result == ["a", "b", "c"]
        
        # 逗号分隔字符串到列表
        result, success, error = await converter.convert("a,b,c", ParameterType.LIST)
        assert success == True
        assert result == ["a", "b", "c"]
        
        # 单个值到列表
        result, success, error = await converter.convert("single", ParameterType.LIST)
        assert success == True
        assert result == ["single"]
    
    @pytest.mark.asyncio
    async def test_dict_conversion(self):
        """测试字典转换"""
        converter = TypeConverter()
        
        # JSON字符串到字典
        json_str = '{"key": "value", "number": 123}'
        result, success, error = await converter.convert(json_str, ParameterType.DICT)
        assert success == True
        assert result == {"key": "value", "number": 123}
        
        # 其他值到字典
        result, success, error = await converter.convert("test", ParameterType.DICT)
        assert success == True
        assert result == {"value": "test"}
    
    @pytest.mark.asyncio
    async def test_custom_converter(self):
        """测试自定义转换器"""
        converter = TypeConverter()
        
        def custom_converter(value):
            return value.upper()
        
        result, success, error = await converter.convert(
            "hello", ParameterType.STRING, custom_converter
        )
        assert success == True
        assert result == "HELLO"


class TestParameterValidator:
    """测试参数验证器"""
    
    @pytest.fixture
    def validator(self):
        """创建参数验证器实例"""
        return ParameterValidator()
    
    @pytest.mark.asyncio
    async def test_basic_validation(self, validator):
        """测试基础参数验证"""
        schema = ParameterSchema(
            name="username",
            parameter_type=ParameterType.STRING
        )
        schema.rules.append(create_required_rule())
        schema.rules.append(create_length_rule("length", 3, 20))
        
        # 有效值
        result = await validator.validate_parameter("testuser", schema)
        assert result.is_valid == True
        assert result.converted_value == "testuser"
        assert len(result.errors) == 0
        
        # 太短的值
        result = await validator.validate_parameter("ab", schema)
        assert result.is_valid == False
        assert len(result.errors) > 0
        assert "长度不能少于" in result.errors[0]
        
        # 空值
        result = await validator.validate_parameter(None, schema)
        assert result.is_valid == False
        assert len(result.errors) > 0
    
    @pytest.mark.asyncio
    async def test_type_validation(self, validator):
        """测试类型验证"""
        # 字符串类型验证
        string_schema = ParameterSchema(
            name="text",
            parameter_type=ParameterType.STRING
        )
        result = await validator.validate_parameter("hello", string_schema)
        assert result.is_valid == True
        assert result.converted_value == "hello"
        
        # 整数类型验证
        int_schema = ParameterSchema(
            name="number",
            parameter_type=ParameterType.INTEGER
        )
        result = await validator.validate_parameter(123, int_schema)
        assert result.is_valid == True
        assert result.converted_value == 123
        
        # 字符串到整数的转换
        result = await validator.validate_parameter("456", int_schema)
        assert result.is_valid == True
        assert result.converted_value == 456
    
    @pytest.mark.asyncio
    async def test_email_validation(self, validator):
        """测试邮箱验证"""
        schema = ParameterSchema(
            name="email",
            parameter_type=ParameterType.EMAIL
        )
        # Add a type check rule to trigger email validation
        schema.rules.append(ValidationRule(
            name="type_check",
            validation_type=ValidationType.TYPE_CHECK
        ))
        
        # 有效邮箱
        result = await validator.validate_parameter("test@example.com", schema)
        assert result.is_valid == True
        
        # 无效邮箱
        result = await validator.validate_parameter("invalid-email", schema)
        assert result.is_valid == False
    
    @pytest.mark.asyncio
    async def test_url_validation(self, validator):
        """测试URL验证"""
        schema = ParameterSchema(
            name="website",
            parameter_type=ParameterType.URL
        )
        # Add a type check rule to trigger URL validation
        schema.rules.append(ValidationRule(
            name="type_check",
            validation_type=ValidationType.TYPE_CHECK
        ))
        
        # 有效URL
        valid_urls = [
            "https://www.example.com",
            "http://example.com",
            "https://api.example.com/v1/users"
        ]
        
        for url in valid_urls:
            result = await validator.validate_parameter(url, schema)
            assert result.is_valid == True, f"URL应该有效: {url}"
        
        # 无效URL
        invalid_urls = [
            "not-a-url",
            "ftp://example.com",
            "javascript:alert('xss')"
        ]
        
        for url in invalid_urls:
            result = await validator.validate_parameter(url, schema)
            assert result.is_valid == False, f"URL应该无效: {url}"
    
    @pytest.mark.asyncio
    async def test_range_validation(self, validator):
        """测试范围验证"""
        schema = ParameterSchema(
            name="score",
            parameter_type=ParameterType.INTEGER
        )
        schema.rules.append(create_range_rule("score_range", 0, 100))
        
        # 有效范围
        for value in [0, 50, 100]:
            result = await validator.validate_parameter(value, schema)
            assert result.is_valid == True, f"值应该在范围内: {value}"
        
        # 超出范围
        for value in [-1, 101]:
            result = await validator.validate_parameter(value, schema)
            assert result.is_valid == False, f"值应该超出范围: {value}"
    
    @pytest.mark.asyncio
    async def test_pattern_validation(self, validator):
        """测试模式验证"""
        schema = ParameterSchema(
            name="code",
            parameter_type=ParameterType.STRING
        )
        schema.rules.append(create_pattern_rule("code_pattern", r"^[A-Z]{2}\d{4}$"))
        
        # 匹配模式
        result = await validator.validate_parameter("AB1234", schema)
        assert result.is_valid == True
        
        # 不匹配模式
        invalid_codes = ["ab1234", "AB12", "AB12345", "1234AB"]
        for code in invalid_codes:
            result = await validator.validate_parameter(code, schema)
            assert result.is_valid == False, f"代码应该不匹配模式: {code}"
    
    @pytest.mark.asyncio
    async def test_enum_validation(self, validator):
        """测试枚举验证"""
        schema = ParameterSchema(
            name="status",
            parameter_type=ParameterType.STRING
        )
        schema.rules.append(create_enum_rule("status_enum", ["active", "inactive", "pending"]))
        
        # 有效枚举值
        for status in ["active", "inactive", "pending"]:
            result = await validator.validate_parameter(status, schema)
            assert result.is_valid == True, f"状态应该有效: {status}"
        
        # 无效枚举值
        result = await validator.validate_parameter("invalid", schema)
        assert result.is_valid == False
    
    @pytest.mark.asyncio
    async def test_custom_validation(self, validator):
        """测试自定义验证"""
        def validate_even_number(value, context):
            if isinstance(value, int) and value % 2 == 0:
                return True, "Valid even number"
            return False, "Must be an even number"
        
        schema = ParameterSchema(
            name="even_num",
            parameter_type=ParameterType.INTEGER
        )
        schema.rules.append(create_custom_rule("even_check", validate_even_number))
        
        # 偶数
        result = await validator.validate_parameter(4, schema)
        assert result.is_valid == True
        
        # 奇数
        result = await validator.validate_parameter(3, schema)
        assert result.is_valid == False
    
    @pytest.mark.asyncio
    async def test_nested_validation(self, validator):
        """测试嵌套验证"""
        nested_schema = {
            "name": ParameterSchema(
                name="name",
                parameter_type=ParameterType.STRING,
                rules=[create_required_rule(), create_length_rule("name_length", 2, 50)]
            ),
            "age": ParameterSchema(
                name="age",
                parameter_type=ParameterType.INTEGER,
                rules=[create_required_rule(), create_range_rule("age_range", 0, 150)]
            )
        }
        
        schema = ParameterSchema(
            name="user",
            parameter_type=ParameterType.DICT,
            nested_schema=nested_schema
        )
        
        # 有效嵌套数据
        valid_data = {"name": "John", "age": 30}
        result = await validator.validate_parameter(valid_data, schema)
        assert result.is_valid == True
        
        # 无效嵌套数据
        invalid_data = {"name": "J", "age": 200}  # 名字太短，年龄超出范围
        result = await validator.validate_parameter(invalid_data, schema)
        assert result.is_valid == False
        assert len(result.errors) > 0
    
    @pytest.mark.asyncio
    async def test_list_validation(self, validator):
        """测试列表验证"""
        item_schema = ParameterSchema(
            name="item",
            parameter_type=ParameterType.STRING,
            rules=[create_length_rule("item_length", 1, 10)]
        )
        
        schema = ParameterSchema(
            name="items",
            parameter_type=ParameterType.LIST,
            item_schema=item_schema
        )
        
        # 有效列表
        valid_list = ["apple", "banana", "cherry"]
        result = await validator.validate_parameter(valid_list, schema)
        assert result.is_valid == True
        
        # 包含无效项的列表
        invalid_list = ["apple", "very_long_item_name", "cherry"]
        result = await validator.validate_parameter(invalid_list, schema)
        assert result.is_valid == False
    
    @pytest.mark.asyncio
    async def test_multiple_parameters(self, validator):
        """测试多参数验证"""
        schemas = {
            "username": ParameterSchema(
                name="username",
                parameter_type=ParameterType.STRING,
                rules=[create_required_rule(), create_length_rule("username_length", 3, 20)]
            ),
            "email": ParameterSchema(
                name="email",
                parameter_type=ParameterType.EMAIL,
                rules=[create_required_rule(), ValidationRule(name="type_check", validation_type=ValidationType.TYPE_CHECK)]
            ),
            "age": ParameterSchema(
                name="age",
                parameter_type=ParameterType.INTEGER,
                rules=[create_range_rule("age_range", 18, 100)]
            )
        }
        
        # 有效参数
        valid_params = {
            "username": "johndoe",
            "email": "john@example.com",
            "age": 25
        }
        
        results = await validator.validate_parameters(valid_params, schemas)
        assert all(result.is_valid for result in results.values())
        
        # 无效参数
        invalid_params = {
            "username": "jd",  # 太短
            "email": "invalid-email",  # 无效邮箱
            "age": 15  # 太小
        }
        
        results = await validator.validate_parameters(invalid_params, schemas)
        assert not all(result.is_valid for result in results.values())
        assert not results["username"].is_valid
        assert not results["email"].is_valid
        assert not results["age"].is_valid


class TestParameterMapper:
    """测试参数映射器"""
    
    @pytest.fixture
    def mapper(self):
        """创建参数映射器实例"""
        return ParameterMapper()
    
    @pytest.mark.asyncio
    async def test_basic_mapping(self, mapper):
        """测试基础参数映射"""
        # 添加映射规则
        mapper.add_mapping("old_name", "new_name")
        mapper.add_mapping("user_id", "userId")
        
        source_params = {
            "old_name": "test_value",
            "user_id": "12345",
            "unchanged_param": "unchanged"
        }
        
        mapped_params = await mapper.map_parameters(source_params)
        
        assert "new_name" in mapped_params
        assert "userId" in mapped_params
        assert "unchanged_param" in mapped_params
        assert mapped_params["new_name"] == "test_value"
        assert mapped_params["userId"] == "12345"
        assert mapped_params["unchanged_param"] == "unchanged"
    
    @pytest.mark.asyncio
    async def test_transformation_mapping(self, mapper):
        """测试带转换的参数映射"""
        def to_upper(value, context):
            return value.upper() if isinstance(value, str) else value
        
        def add_prefix(value, context):
            return f"prefix_{value}"
        
        mapper.add_mapping("name", "upper_name", transformation=to_upper)
        mapper.add_mapping("code", "prefixed_code", transformation=add_prefix)
        
        source_params = {
            "name": "john",
            "code": "ABC123"
        }
        
        mapped_params = await mapper.map_parameters(source_params)
        
        assert mapped_params["upper_name"] == "JOHN"
        assert mapped_params["prefixed_code"] == "prefix_ABC123"
    
    @pytest.mark.asyncio
    async def test_conditional_mapping(self, mapper):
        """测试条件映射"""
        def only_if_admin(source_params, context):
            return source_params.get("role") == "admin"
        
        mapper.add_mapping("secret_key", "admin_key", condition=only_if_admin)
        
        # 管理员用户 - 应该映射
        admin_params = {
            "role": "admin",
            "secret_key": "secret123"
        }
        
        mapped_params = await mapper.map_parameters(admin_params)
        assert "admin_key" in mapped_params
        assert mapped_params["admin_key"] == "secret123"
        
        # 普通用户 - 不应该映射
        user_params = {
            "role": "user",
            "secret_key": "secret123"
        }
        
        mapped_params = await mapper.map_parameters(user_params)
        assert "admin_key" not in mapped_params
        assert "secret_key" in mapped_params  # 原参数保留
    
    @pytest.mark.asyncio
    async def test_default_value_mapping(self, mapper):
        """测试默认值映射"""
        mapper.add_mapping("optional_param", "required_param", default_value="default_value")
        
        # 源参数存在
        source_params = {"optional_param": "actual_value"}
        mapped_params = await mapper.map_parameters(source_params)
        assert mapped_params["required_param"] == "actual_value"
        
        # 源参数不存在，使用默认值
        empty_params = {}
        mapped_params = await mapper.map_parameters(empty_params)
        assert mapped_params["required_param"] == "default_value"
    
    def test_mapping_info(self, mapper):
        """测试映射信息获取"""
        mapper.add_mapping("source1", "target1", description="Test mapping 1")
        mapper.add_mapping("source2", "target2", default_value="default", description="Test mapping 2")
        
        mapping_info = mapper.get_mapping_info()
        
        assert len(mapping_info) == 2
        assert mapping_info[0]["source_name"] == "source1"
        assert mapping_info[0]["target_name"] == "target1"
        assert mapping_info[0]["description"] == "Test mapping 1"
        assert mapping_info[1]["default_value"] == "default"


class TestIntegratedValidationAndMapping:
    """测试验证和映射的集成功能"""
    
    @pytest.mark.asyncio
    async def test_full_pipeline(self):
        """测试完整的验证和映射流程"""
        # 创建映射器
        mapper = ParameterMapper()
        mapper.add_mapping("user_name", "username")
        mapper.add_mapping("user_email", "email")
        mapper.add_mapping("user_age", "age")
        
        # 创建验证器
        validator = ParameterValidator()
        
        # 创建参数模式
        schemas = {
            "username": ParameterSchema(
                name="username",
                parameter_type=ParameterType.STRING,
                rules=[create_required_rule(), create_length_rule("username_length", 3, 20)]
            ),
            "email": ParameterSchema(
                name="email",
                parameter_type=ParameterType.EMAIL,
                rules=[create_required_rule()]
            ),
            "age": ParameterSchema(
                name="age",
                parameter_type=ParameterType.INTEGER,
                rules=[create_range_rule("age_range", 18, 100)]
            )
        }
        
        # 源参数（使用旧的参数名）
        source_params = {
            "user_name": "johndoe",
            "user_email": "john@example.com",
            "user_age": "25"  # 字符串形式的年龄
        }
        
        # 1. 执行参数映射
        mapped_params = await mapper.map_parameters(source_params)
        
        # 2. 执行参数验证
        validation_results = await validator.validate_parameters(mapped_params, schemas)
        
        # 验证映射结果
        assert "username" in mapped_params
        assert "email" in mapped_params
        assert "age" in mapped_params
        
        # 验证验证结果
        assert all(result.is_valid for result in validation_results.values())
        assert validation_results["username"].converted_value == "johndoe"
        assert validation_results["email"].converted_value == "john@example.com"
        assert validation_results["age"].converted_value == 25  # 应该转换为整数
    
    @pytest.mark.asyncio
    async def test_complex_nested_validation(self):
        """测试复杂嵌套验证"""
        validator = ParameterValidator()
        
        # 创建复杂的嵌套模式
        address_schema = {
            "street": ParameterSchema(
                name="street",
                parameter_type=ParameterType.STRING,
                rules=[create_required_rule(), create_length_rule("street_length", 5, 100)]
            ),
            "city": ParameterSchema(
                name="city",
                parameter_type=ParameterType.STRING,
                rules=[create_required_rule(), create_length_rule("city_length", 2, 50)]
            ),
            "zip_code": ParameterSchema(
                name="zip_code",
                parameter_type=ParameterType.STRING,
                rules=[create_pattern_rule("zip_pattern", r"^\d{5}(-\d{4})?$")]
            )
        }
        
        contact_schema = {
            "email": ParameterSchema(
                name="email",
                parameter_type=ParameterType.EMAIL,
                rules=[create_required_rule()]
            ),
            "phone": ParameterSchema(
                name="phone",
                parameter_type=ParameterType.PHONE,
                rules=[create_required_rule()]
            )
        }
        
        schemas = {
            "name": ParameterSchema(
                name="name",
                parameter_type=ParameterType.STRING,
                rules=[create_required_rule(), create_length_rule("name_length", 2, 50)]
            ),
            "address": ParameterSchema(
                name="address",
                parameter_type=ParameterType.DICT,
                nested_schema=address_schema
            ),
            "contact": ParameterSchema(
                name="contact",
                parameter_type=ParameterType.DICT,
                nested_schema=contact_schema
            ),
            "tags": ParameterSchema(
                name="tags",
                parameter_type=ParameterType.LIST,
                item_schema=ParameterSchema(
                    name="tag",
                    parameter_type=ParameterType.STRING,
                    rules=[create_length_rule("tag_length", 1, 20)]
                )
            )
        }
        
        # 有效的复杂数据
        valid_data = {
            "name": "John Doe",
            "address": {
                "street": "123 Main Street",
                "city": "Anytown",
                "zip_code": "12345"
            },
            "contact": {
                "email": "john@example.com",
                "phone": "555-1234"
            },
            "tags": ["customer", "vip", "active"]
        }
        
        results = await validator.validate_parameters(valid_data, schemas)
        assert all(result.is_valid for result in results.values())
        
        # 无效的复杂数据
        invalid_data = {
            "name": "J",  # 太短
            "address": {
                "street": "123",  # 太短
                "city": "A",  # 太短
                "zip_code": "invalid"  # 无效格式
            },
            "contact": {
                "email": "invalid-email",  # 无效邮箱
                "phone": "invalid-phone"  # 无效电话
            },
            "tags": ["customer", "this_is_a_very_long_tag_name"]  # 包含太长的标签
        }
        
        results = await validator.validate_parameters(invalid_data, schemas)
        assert not all(result.is_valid for result in results.values())


if __name__ == "__main__":
    pytest.main([__file__, "-v"])