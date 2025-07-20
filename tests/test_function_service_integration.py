"""
TASK-028: FunctionService与参数验证系统集成测试
测试FunctionService中参数验证功能的集成使用
"""
import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from src.services.function_service import FunctionService
from src.services.cache_service import CacheService
from src.core.parameter_validator import (
    ParameterSchema, ParameterType, ValidationRule, ValidationType,
    create_required_rule, create_length_rule, create_range_rule
)


class TestFunctionServiceParameterValidation:
    """测试FunctionService参数验证集成"""
    
    @pytest.fixture
    def cache_service(self):
        """创建缓存服务Mock"""
        cache_service = AsyncMock(spec=CacheService)
        
        # 创建一个简单的内存缓存
        cache_data = {}
        
        async def mock_get(key, namespace=None):
            cache_key = f"{namespace}:{key}" if namespace else key
            return cache_data.get(cache_key)
        
        async def mock_set(key, value, ttl=None, namespace=None):
            cache_key = f"{namespace}:{key}" if namespace else key
            cache_data[cache_key] = value
            return True
        
        async def mock_delete(key, namespace=None):
            cache_key = f"{namespace}:{key}" if namespace else key
            cache_data.pop(cache_key, None)
            return True
        
        cache_service.get.side_effect = mock_get
        cache_service.set.side_effect = mock_set
        cache_service.delete.side_effect = mock_delete
        
        return cache_service
    
    @pytest.fixture
    def function_service(self, cache_service):
        """创建FunctionService实例"""
        return FunctionService(cache_service)
    
    @pytest.mark.asyncio
    async def test_parameter_validation_creation(self, function_service):
        """测试参数模式创建"""
        parameter_definitions = [
            {
                "name": "username",
                "type": "string", 
                "description": "用户名",
                "validation_rules": [
                    {"type": "required", "name": "username_required"},
                    {"type": "length", "name": "username_length", "min_length": 3, "max_length": 20}
                ]
            },
            {
                "name": "email",
                "type": "email",
                "description": "邮箱地址", 
                "validation_rules": [
                    {"type": "required", "name": "email_required"}
                ]
            },
            {
                "name": "age",
                "type": "integer",
                "description": "年龄",
                "has_default": True,
                "default_value": 18,
                "validation_rules": [
                    {"type": "range", "name": "age_range", "min_value": 0, "max_value": 150}
                ]
            }
        ]
        
        success = await function_service.create_parameter_schema(
            "test_function", parameter_definitions
        )
        
        assert success == True
    
    @pytest.mark.asyncio 
    async def test_parameter_validation_with_valid_data(self, function_service):
        """测试有效参数验证"""
        # 创建参数模式
        parameter_definitions = [
            {
                "name": "name",
                "type": "string",
                "validation_rules": [
                    {"type": "required", "name": "name_required"},
                    {"type": "length", "name": "name_length", "min_length": 2, "max_length": 50}
                ]
            },
            {
                "name": "score",
                "type": "integer", 
                "validation_rules": [
                    {"type": "range", "name": "score_range", "min_value": 0, "max_value": 100}
                ]
            }
        ]
        
        await function_service.create_parameter_schema("validate_test", parameter_definitions)
        
        # 测试有效参数
        valid_params = {
            "name": "John Doe",
            "score": 85
        }
        
        validation_result = await function_service.validate_parameters(
            "validate_test", valid_params
        )
        
        assert validation_result["is_valid"] == True
        assert "name" in validation_result["validated_data"]
        assert "score" in validation_result["validated_data"]
        assert validation_result["validated_data"]["name"] == "John Doe"
        assert validation_result["validated_data"]["score"] == 85
        assert len(validation_result["errors"]) == 0
    
    @pytest.mark.asyncio
    async def test_parameter_validation_with_invalid_data(self, function_service):
        """测试无效参数验证"""
        # 创建参数模式
        parameter_definitions = [
            {
                "name": "email",
                "type": "email",
                "validation_rules": [
                    {"type": "required", "name": "email_required"}
                ]
            },
            {
                "name": "password",
                "type": "string",
                "validation_rules": [
                    {"type": "required", "name": "password_required"},
                    {"type": "length", "name": "password_length", "min_length": 8, "max_length": 50}
                ]
            }
        ]
        
        await function_service.create_parameter_schema("login_test", parameter_definitions)
        
        # 测试无效参数
        invalid_params = {
            "email": "invalid-email-format",  # 无效邮箱格式
            "password": "123"  # 太短
        }
        
        validation_result = await function_service.validate_parameters(
            "login_test", invalid_params
        )
        
        assert validation_result["is_valid"] == False
        assert len(validation_result["errors"]) > 0
    
    @pytest.mark.asyncio
    async def test_parameter_type_conversion(self, function_service):
        """测试参数类型转换"""
        parameter_definitions = [
            {
                "name": "count",
                "type": "integer",
                "auto_convert": True
            },
            {
                "name": "active",
                "type": "boolean", 
                "auto_convert": True
            },
            {
                "name": "tags",
                "type": "list",
                "auto_convert": True
            }
        ]
        
        await function_service.create_parameter_schema("convert_test", parameter_definitions)
        
        # 需要转换的参数
        params_to_convert = {
            "count": "42",  # 字符串转整数
            "active": "true",  # 字符串转布尔值
            "tags": "tag1,tag2,tag3"  # 逗号分隔字符串转列表
        }
        
        validation_result = await function_service.validate_parameters(
            "convert_test", params_to_convert
        )
        
        assert validation_result["is_valid"] == True
        validated_data = validation_result["validated_data"]
        
        assert isinstance(validated_data["count"], int)
        assert validated_data["count"] == 42
        
        assert isinstance(validated_data["active"], bool)
        assert validated_data["active"] == True
        
        assert isinstance(validated_data["tags"], list)
        assert validated_data["tags"] == ["tag1", "tag2", "tag3"]
    
    @pytest.mark.asyncio
    async def test_parameter_mapping(self, function_service):
        """测试参数映射"""
        mapping_rules = [
            {"source_name": "user_name", "target_name": "username"},
            {"source_name": "user_email", "target_name": "email"},
            {"source_name": "user_age", "target_name": "age"}
        ]
        
        source_params = {
            "user_name": "johndoe",
            "user_email": "john@example.com", 
            "user_age": 25,
            "extra_field": "extra_value"
        }
        
        mapped_params = await function_service.map_parameters(
            source_params, mapping_rules
        )
        
        # 检查映射结果
        assert "username" in mapped_params
        assert "email" in mapped_params
        assert "age" in mapped_params
        assert "extra_field" in mapped_params  # 未映射的参数应该保留
        
        assert mapped_params["username"] == "johndoe"
        assert mapped_params["email"] == "john@example.com"
        assert mapped_params["age"] == 25
        assert mapped_params["extra_field"] == "extra_value"
    
    @pytest.mark.asyncio
    async def test_validate_and_convert_parameters_integration(self, function_service):
        """测试验证和转换参数的集成功能"""
        # 创建参数模式
        parameter_definitions = [
            {
                "name": "product_id",
                "type": "integer",
                "validation_rules": [
                    {"type": "required", "name": "product_id_required"},
                    {"type": "range", "name": "product_id_range", "min_value": 1, "max_value": 999999}
                ]
            },
            {
                "name": "quantity", 
                "type": "integer",
                "has_default": True,
                "default_value": 1,
                "validation_rules": [
                    {"type": "range", "name": "quantity_range", "min_value": 1, "max_value": 100}
                ]
            },
            {
                "name": "customer_email",
                "type": "email",
                "validation_rules": [
                    {"type": "required", "name": "customer_email_required"}
                ]
            }
        ]
        
        await function_service.create_parameter_schema("order_process", parameter_definitions)
        
        # 测试参数（包含类型转换和验证）
        test_params = {
            "product_id": "12345",  # 字符串转整数
            "quantity": "2",        # 字符串转整数 
            "customer_email": "customer@example.com"
        }
        
        # 调用集成的验证和转换方法
        try:
            validated_params = await function_service.validate_and_convert_parameters(
                "order_process", test_params
            )
            
            # 验证结果
            assert isinstance(validated_params["product_id"], int)
            assert validated_params["product_id"] == 12345
            
            assert isinstance(validated_params["quantity"], int) 
            assert validated_params["quantity"] == 2
            
            assert isinstance(validated_params["customer_email"], str)
            assert validated_params["customer_email"] == "customer@example.com"
            
        except ValueError:
            pytest.fail("验证应该成功，但抛出了异常")
    
    @pytest.mark.asyncio
    async def test_parameter_validation_with_missing_required_field(self, function_service):
        """测试缺少必需字段的参数验证"""
        parameter_definitions = [
            {
                "name": "required_field",
                "type": "string",
                "validation_rules": [
                    {"type": "required", "name": "required_field_required"}
                ]
            },
            {
                "name": "optional_field",
                "type": "string",
                "has_default": True,
                "default_value": "default_value"
            }
        ]
        
        await function_service.create_parameter_schema("required_test", parameter_definitions)
        
        # 测试缺少必需字段
        incomplete_params = {
            "optional_field": "some_value"
            # 缺少 required_field
        }
        
        # 这应该抛出ValueError
        with pytest.raises(ValueError, match="参数验证失败"):
            await function_service.validate_and_convert_parameters(
                "required_test", incomplete_params
            )
    
    @pytest.mark.asyncio
    async def test_parameter_validation_statistics(self, function_service):
        """测试参数验证统计信息"""
        # 获取验证统计
        stats = function_service.get_parameter_validation_statistics()
        
        # 检查统计信息结构
        assert isinstance(stats, dict)
        # 由于这是新的实例，可能还没有验证记录，所以主要检查结构
        expected_keys = [
            'total_validations', 'successful_validations', 
            'failed_validations', 'conversion_count', 'average_processing_time'
        ]
        
        for key in expected_keys:
            assert key in stats
    
    @pytest.mark.asyncio
    async def test_parameter_validation_test_cases(self, function_service):
        """测试参数验证测试用例功能"""
        # 创建简单的参数模式
        parameter_definitions = [
            {
                "name": "score",
                "type": "integer",
                "validation_rules": [
                    {"type": "range", "name": "score_range", "min_value": 0, "max_value": 100}
                ]
            }
        ]
        
        await function_service.create_parameter_schema("score_test", parameter_definitions)
        
        # 定义测试用例
        test_cases = [
            {
                "description": "有效分数",
                "parameters": {"score": 85},
                "expected_result": "success"
            },
            {
                "description": "无效分数 - 太高",
                "parameters": {"score": 150},
                "expected_result": "failure"
            },
            {
                "description": "无效分数 - 负数",
                "parameters": {"score": -10},
                "expected_result": "failure"
            }
        ]
        
        # 运行测试用例
        test_results = await function_service.test_parameter_validation(
            "score_test", test_cases
        )
        
        assert len(test_results) == 3
        
        # 检查第一个测试用例（应该通过）
        assert test_results[0]["passed"] == True
        assert test_results[0]["actual"] == "success"
        
        # 检查第二个测试用例（应该失败）
        assert test_results[1]["passed"] == True  # 预期失败，实际失败，所以测试通过
        assert test_results[1]["actual"] == "failure"
        
        # 检查第三个测试用例（应该失败）
        assert test_results[2]["passed"] == True  # 预期失败，实际失败，所以测试通过
        assert test_results[2]["actual"] == "failure"
    
    @pytest.mark.asyncio
    async def test_parameter_schema_export(self, function_service):
        """测试参数模式导出"""
        # 创建参数模式
        parameter_definitions = [
            {
                "name": "username",
                "type": "string",
                "description": "用户名",
                "validation_rules": [
                    {"type": "required", "name": "username_required"},
                    {"type": "length", "name": "username_length", "min_length": 3, "max_length": 20}
                ]
            }
        ]
        
        await function_service.create_parameter_schema("export_test", parameter_definitions)
        
        # 导出参数模式
        exported_schemas = await function_service.export_parameter_schemas("export_test")
        
        assert "export_test" in exported_schemas
        schema_data = exported_schemas["export_test"]
        
        assert "username" in schema_data
        username_schema = schema_data["username"]
        
        assert username_schema["name"] == "username"
        assert username_schema["parameter_type"] == "string"
        assert username_schema["description"] == "用户名"
        assert len(username_schema["rules"]) == 2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])