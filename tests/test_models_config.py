"""
配置模型单元测试
"""
import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime
import json

from src.models.config import SystemConfig, IntentConfig, SlotConfig, FunctionConfig, RagflowConfig


class TestSystemConfigModel:
    """系统配置模型测试类"""
    
    def test_system_config_creation(self):
        """测试系统配置创建"""
        # 创建系统配置实例
        config = SystemConfig()
        config.config_key = "nlu_confidence_threshold"
        config.config_value = "0.7"
        config.config_type = "float"
        config.description = "NLU置信度阈值"
        config.category = "nlu"
        config.is_active = True
        config.is_system = True
        
        # 验证系统配置属性
        assert config.config_key == "nlu_confidence_threshold"
        assert config.config_value == "0.7"
        assert config.config_type == "float"
        assert config.description == "NLU置信度阈值"
        assert config.category == "nlu"
        assert config.is_active == True
        assert config.is_system == True
    
    def test_system_config_get_typed_value(self):
        """测试获取类型化值"""
        # 测试字符串类型
        config = SystemConfig()
        config.config_value = "hello"
        config.config_type = "string"
        assert config.get_typed_value() == "hello"
        
        # 测试整数类型
        config.config_value = "123"
        config.config_type = "int"
        assert config.get_typed_value() == 123
        
        # 测试浮点数类型
        config.config_value = "3.14"
        config.config_type = "float"
        assert config.get_typed_value() == 3.14
        
        # 测试布尔类型
        config.config_value = "true"
        config.config_type = "bool"
        assert config.get_typed_value() == True
        
        config.config_value = "false"
        config.config_type = "bool"
        assert config.get_typed_value() == False
        
        # 测试JSON类型
        config.config_value = '{"key": "value"}'
        config.config_type = "json"
        assert config.get_typed_value() == {"key": "value"}
    
    def test_system_config_set_typed_value(self):
        """测试设置类型化值"""
        # 创建系统配置实例
        config = SystemConfig()
        
        # 设置字符串值
        config.set_typed_value("hello", "string")
        assert config.config_value == "hello"
        assert config.config_type == "string"
        
        # 设置整数值
        config.set_typed_value(123, "int")
        assert config.config_value == "123"
        assert config.config_type == "int"
        
        # 设置浮点数值
        config.set_typed_value(3.14, "float")
        assert config.config_value == "3.14"
        assert config.config_type == "float"
        
        # 设置布尔值
        config.set_typed_value(True, "bool")
        assert config.config_value == "true"
        assert config.config_type == "bool"
        
        # 设置JSON值
        config.set_typed_value({"key": "value"}, "json")
        assert config.config_value == '{"key": "value"}'
        assert config.config_type == "json"
    
    def test_system_config_is_system_config(self):
        """测试检查是否为系统配置"""
        # 创建系统配置
        config = SystemConfig()
        config.is_system = True
        assert config.is_system_config() == True
        
        # 创建用户配置
        config.is_system = False
        assert config.is_system_config() == False
    
    def test_system_config_get_category_configs(self):
        """测试获取分类配置"""
        # 模拟分类配置
        mock_configs = [
            MagicMock(config_key="nlu_threshold", config_value="0.7", category="nlu"),
            MagicMock(config_key="nlu_timeout", config_value="30", category="nlu")
        ]
        
        with patch.object(SystemConfig, 'select') as mock_select:
            mock_query = MagicMock()
            mock_query.where.return_value = mock_configs
            mock_select.return_value = mock_query
            
            # 获取分类配置
            configs = SystemConfig.get_category_configs("nlu")
            
            # 验证配置
            assert len(configs) == 2
            assert all(config.category == "nlu" for config in configs)
    
    def test_system_config_get_config_value(self):
        """测试获取配置值"""
        # 模拟配置
        mock_config = MagicMock()
        mock_config.config_value = "0.7"
        mock_config.config_type = "float"
        mock_config.get_typed_value.return_value = 0.7
        
        with patch.object(SystemConfig, 'get_or_none', return_value=mock_config):
            # 获取配置值
            value = SystemConfig.get_config_value("nlu_threshold")
            
            # 验证值
            assert value == 0.7
    
    def test_system_config_set_config_value(self):
        """测试设置配置值"""
        # 模拟配置
        mock_config = MagicMock()
        
        with patch.object(SystemConfig, 'get_or_none', return_value=mock_config):
            # 设置配置值
            SystemConfig.set_config_value("nlu_threshold", 0.8, "float")
            
            # 验证设置
            mock_config.set_typed_value.assert_called_once_with(0.8, "float")
            mock_config.save.assert_called_once()
    
    def test_system_config_to_dict(self):
        """测试系统配置转字典"""
        # 创建系统配置实例
        config = SystemConfig()
        config.id = 1
        config.config_key = "nlu_threshold"
        config.config_value = "0.7"
        config.config_type = "float"
        config.description = "NLU置信度阈值"
        config.category = "nlu"
        config.is_active = True
        config.is_system = True
        config.created_at = datetime(2024, 1, 1, 10, 0, 0)
        
        # 转换为字典
        config_dict = config.to_dict()
        
        # 验证字典内容
        assert config_dict['id'] == 1
        assert config_dict['config_key'] == "nlu_threshold"
        assert config_dict['config_value'] == "0.7"
        assert config_dict['config_type'] == "float"
        assert config_dict['description'] == "NLU置信度阈值"
        assert config_dict['category'] == "nlu"
        assert config_dict['is_active'] == True
        assert config_dict['is_system'] == True


class TestIntentConfigModel:
    """意图配置模型测试类"""
    
    def test_intent_config_creation(self):
        """测试意图配置创建"""
        # 创建意图配置实例
        config = IntentConfig()
        config.intent_id = 1
        config.config_key = "confidence_threshold"
        config.config_value = "0.8"
        config.config_type = "float"
        config.description = "意图置信度阈值"
        config.is_active = True
        
        # 验证意图配置属性
        assert config.intent_id == 1
        assert config.config_key == "confidence_threshold"
        assert config.config_value == "0.8"
        assert config.config_type == "float"
        assert config.description == "意图置信度阈值"
        assert config.is_active == True
    
    def test_intent_config_get_intent(self):
        """测试获取配置所属意图"""
        # 创建意图配置实例
        config = IntentConfig()
        config.intent_id = 1
        
        # 模拟意图数据
        mock_intent = MagicMock(
            id=1,
            intent_name="book_flight",
            description="预订机票"
        )
        
        with patch('src.models.intent.Intent') as mock_intent_model:
            mock_intent_model.get_by_id.return_value = mock_intent
            
            # 获取意图
            intent = config.get_intent()
            
            # 验证意图
            assert intent.id == 1
            assert intent.intent_name == "book_flight"
            assert intent.description == "预订机票"
    
    def test_intent_config_get_intent_configs(self):
        """测试获取意图配置列表"""
        # 模拟意图配置
        mock_configs = [
            MagicMock(config_key="confidence_threshold", config_value="0.8"),
            MagicMock(config_key="max_retries", config_value="3")
        ]
        
        with patch.object(IntentConfig, 'select') as mock_select:
            mock_query = MagicMock()
            mock_query.where.return_value = mock_configs
            mock_select.return_value = mock_query
            
            # 获取意图配置
            configs = IntentConfig.get_intent_configs(1)
            
            # 验证配置
            assert len(configs) == 2
            assert configs[0].config_key == "confidence_threshold"
            assert configs[1].config_key == "max_retries"
    
    def test_intent_config_to_dict(self):
        """测试意图配置转字典"""
        # 创建意图配置实例
        config = IntentConfig()
        config.id = 1
        config.intent_id = 1
        config.config_key = "confidence_threshold"
        config.config_value = "0.8"
        config.config_type = "float"
        config.description = "意图置信度阈值"
        config.is_active = True
        config.created_at = datetime(2024, 1, 1, 10, 0, 0)
        
        # 转换为字典
        config_dict = config.to_dict()
        
        # 验证字典内容
        assert config_dict['id'] == 1
        assert config_dict['intent_id'] == 1
        assert config_dict['config_key'] == "confidence_threshold"
        assert config_dict['config_value'] == "0.8"
        assert config_dict['config_type'] == "float"
        assert config_dict['description'] == "意图置信度阈值"
        assert config_dict['is_active'] == True


class TestSlotConfigModel:
    """槽位配置模型测试类"""
    
    def test_slot_config_creation(self):
        """测试槽位配置创建"""
        # 创建槽位配置实例
        config = SlotConfig()
        config.slot_id = 1
        config.config_key = "validation_enabled"
        config.config_value = "true"
        config.config_type = "bool"
        config.description = "启用槽位验证"
        config.is_active = True
        
        # 验证槽位配置属性
        assert config.slot_id == 1
        assert config.config_key == "validation_enabled"
        assert config.config_value == "true"
        assert config.config_type == "bool"
        assert config.description == "启用槽位验证"
        assert config.is_active == True
    
    def test_slot_config_get_slot(self):
        """测试获取配置所属槽位"""
        # 创建槽位配置实例
        config = SlotConfig()
        config.slot_id = 1
        
        # 模拟槽位数据
        mock_slot = MagicMock(
            id=1,
            slot_name="destination",
            slot_type="text"
        )
        
        with patch('src.models.slot.Slot') as mock_slot_model:
            mock_slot_model.get_by_id.return_value = mock_slot
            
            # 获取槽位
            slot = config.get_slot()
            
            # 验证槽位
            assert slot.id == 1
            assert slot.slot_name == "destination"
            assert slot.slot_type == "text"
    
    def test_slot_config_to_dict(self):
        """测试槽位配置转字典"""
        # 创建槽位配置实例
        config = SlotConfig()
        config.id = 1
        config.slot_id = 1
        config.config_key = "validation_enabled"
        config.config_value = "true"
        config.config_type = "bool"
        config.description = "启用槽位验证"
        config.is_active = True
        config.created_at = datetime(2024, 1, 1, 10, 0, 0)
        
        # 转换为字典
        config_dict = config.to_dict()
        
        # 验证字典内容
        assert config_dict['id'] == 1
        assert config_dict['slot_id'] == 1
        assert config_dict['config_key'] == "validation_enabled"
        assert config_dict['config_value'] == "true"
        assert config_dict['config_type'] == "bool"
        assert config_dict['description'] == "启用槽位验证"
        assert config_dict['is_active'] == True


class TestFunctionConfigModel:
    """功能配置模型测试类"""
    
    def test_function_config_creation(self):
        """测试功能配置创建"""
        # 创建功能配置实例
        config = FunctionConfig()
        config.function_id = 1
        config.config_key = "timeout"
        config.config_value = "30"
        config.config_type = "int"
        config.description = "功能超时时间"
        config.is_active = True
        
        # 验证功能配置属性
        assert config.function_id == 1
        assert config.config_key == "timeout"
        assert config.config_value == "30"
        assert config.config_type == "int"
        assert config.description == "功能超时时间"
        assert config.is_active == True
    
    def test_function_config_get_function(self):
        """测试获取配置所属功能"""
        # 创建功能配置实例
        config = FunctionConfig()
        config.function_id = 1
        
        # 模拟功能数据
        mock_function = MagicMock(
            id=1,
            function_name="book_flight",
            function_type="api"
        )
        
        with patch('src.models.function.Function') as mock_function_model:
            mock_function_model.get_by_id.return_value = mock_function
            
            # 获取功能
            function = config.get_function()
            
            # 验证功能
            assert function.id == 1
            assert function.function_name == "book_flight"
            assert function.function_type == "api"
    
    def test_function_config_to_dict(self):
        """测试功能配置转字典"""
        # 创建功能配置实例
        config = FunctionConfig()
        config.id = 1
        config.function_id = 1
        config.config_key = "timeout"
        config.config_value = "30"
        config.config_type = "int"
        config.description = "功能超时时间"
        config.is_active = True
        config.created_at = datetime(2024, 1, 1, 10, 0, 0)
        
        # 转换为字典
        config_dict = config.to_dict()
        
        # 验证字典内容
        assert config_dict['id'] == 1
        assert config_dict['function_id'] == 1
        assert config_dict['config_key'] == "timeout"
        assert config_dict['config_value'] == "30"
        assert config_dict['config_type'] == "int"
        assert config_dict['description'] == "功能超时时间"
        assert config_dict['is_active'] == True


class TestRagflowConfigModel:
    """RAGFLOW配置模型测试类"""
    
    def test_ragflow_config_creation(self):
        """测试RAGFLOW配置创建"""
        # 创建RAGFLOW配置实例
        config = RagflowConfig()
        config.config_name = "default"
        config.base_url = "http://localhost:8080"
        config.api_key = "test_api_key"
        config.timeout = 30
        config.max_retries = 3
        config.enable_ssl = True
        config.is_active = True
        
        # 验证RAGFLOW配置属性
        assert config.config_name == "default"
        assert config.base_url == "http://localhost:8080"
        assert config.api_key == "test_api_key"
        assert config.timeout == 30
        assert config.max_retries == 3
        assert config.enable_ssl == True
        assert config.is_active == True
    
    def test_ragflow_config_get_full_url(self):
        """测试获取完整URL"""
        # 创建RAGFLOW配置实例
        config = RagflowConfig()
        config.base_url = "http://localhost:8080"
        
        # 获取完整URL
        full_url = config.get_full_url("/api/v1/query")
        
        # 验证URL
        assert full_url == "http://localhost:8080/api/v1/query"
    
    def test_ragflow_config_get_headers(self):
        """测试获取请求头"""
        # 创建RAGFLOW配置实例
        config = RagflowConfig()
        config.api_key = "test_api_key"
        
        # 获取请求头
        headers = config.get_headers()
        
        # 验证请求头
        assert isinstance(headers, dict)
        assert "Authorization" in headers
        assert headers["Authorization"] == "Bearer test_api_key"
        assert headers["Content-Type"] == "application/json"
    
    def test_ragflow_config_is_ssl_enabled(self):
        """测试检查是否启用SSL"""
        # 创建启用SSL的配置
        config = RagflowConfig()
        config.enable_ssl = True
        assert config.is_ssl_enabled() == True
        
        # 创建未启用SSL的配置
        config.enable_ssl = False
        assert config.is_ssl_enabled() == False
    
    def test_ragflow_config_validate_config(self):
        """测试验证配置"""
        # 创建有效配置
        config = RagflowConfig()
        config.config_name = "test"
        config.base_url = "http://localhost:8080"
        config.api_key = "test_key"
        config.timeout = 30
        
        # 验证配置
        assert config.validate_config() == True
        
        # 创建无效配置（缺少必需字段）
        config.base_url = None
        assert config.validate_config() == False
    
    def test_ragflow_config_get_active_config(self):
        """测试获取活跃配置"""
        # 模拟活跃配置
        mock_config = MagicMock(
            config_name="default",
            base_url="http://localhost:8080",
            is_active=True
        )
        
        with patch.object(RagflowConfig, 'get_or_none', return_value=mock_config):
            # 获取活跃配置
            active_config = RagflowConfig.get_active_config()
            
            # 验证配置
            assert active_config.config_name == "default"
            assert active_config.base_url == "http://localhost:8080"
            assert active_config.is_active == True
    
    def test_ragflow_config_to_dict(self):
        """测试RAGFLOW配置转字典"""
        # 创建RAGFLOW配置实例
        config = RagflowConfig()
        config.id = 1
        config.config_name = "default"
        config.base_url = "http://localhost:8080"
        config.api_key = "test_api_key"
        config.timeout = 30
        config.max_retries = 3
        config.enable_ssl = True
        config.is_active = True
        config.created_at = datetime(2024, 1, 1, 10, 0, 0)
        
        # 转换为字典
        config_dict = config.to_dict()
        
        # 验证字典内容
        assert config_dict['id'] == 1
        assert config_dict['config_name'] == "default"
        assert config_dict['base_url'] == "http://localhost:8080"
        assert config_dict['api_key'] == "test_api_key"
        assert config_dict['timeout'] == 30
        assert config_dict['max_retries'] == 3
        assert config_dict['enable_ssl'] == True
        assert config_dict['is_active'] == True
    
    def test_ragflow_config_export_config(self):
        """测试导出配置"""
        # 创建RAGFLOW配置实例
        config = RagflowConfig()
        config.config_name = "default"
        config.base_url = "http://localhost:8080"
        config.api_key = "test_api_key"
        config.timeout = 30
        config.max_retries = 3
        config.enable_ssl = True
        
        # 导出配置
        export_data = config.export_config()
        
        # 验证导出数据
        assert export_data['config_name'] == "default"
        assert export_data['base_url'] == "http://localhost:8080"
        assert export_data['timeout'] == 30
        assert export_data['max_retries'] == 3
        assert export_data['enable_ssl'] == True
        # API key应该被脱敏
        assert export_data['api_key'] == "test_***"
    
    def test_ragflow_config_import_config(self):
        """测试导入配置"""
        # 准备导入数据
        import_data = {
            'config_name': 'imported',
            'base_url': 'http://localhost:9090',
            'api_key': 'imported_key',
            'timeout': 60,
            'max_retries': 5,
            'enable_ssl': False
        }
        
        # 导入配置
        config = RagflowConfig.import_config(import_data)
        
        # 验证导入
        assert config.config_name == 'imported'
        assert config.base_url == 'http://localhost:9090'
        assert config.api_key == 'imported_key'
        assert config.timeout == 60
        assert config.max_retries == 5
        assert config.enable_ssl == False