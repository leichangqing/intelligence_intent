"""
功能模型单元测试
"""
import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime
import json

from src.models.function import Function, FunctionParameter
from src.models.function_call import FunctionCall


class TestFunctionModel:
    """功能模型测试类"""
    
    def test_function_creation(self):
        """测试功能创建"""
        # 创建功能实例
        function = Function()
        function.function_name = "book_flight"
        function.function_type = "api"
        function.description = "预订机票功能"
        function.parameters = json.dumps([
            {"name": "origin", "type": "string", "required": True},
            {"name": "destination", "type": "string", "required": True}
        ])
        function.implementation = "https://api.airline.com/book"
        function.timeout = 30
        function.retry_count = 3
        function.is_active = True
        
        # 验证功能属性
        assert function.function_name == "book_flight"
        assert function.function_type == "api"
        assert function.description == "预订机票功能"
        assert isinstance(function.parameters, str)
        assert function.implementation == "https://api.airline.com/book"
        assert function.timeout == 30
        assert function.retry_count == 3
        assert function.is_active == True
    
    def test_function_get_parameters(self):
        """测试获取功能参数"""
        # 创建功能实例
        function = Function()
        parameters = [
            {"name": "origin", "type": "string", "required": True, "description": "出发地"},
            {"name": "destination", "type": "string", "required": True, "description": "目的地"},
            {"name": "date", "type": "string", "required": True, "description": "出发日期"}
        ]
        function.parameters = json.dumps(parameters)
        
        # 获取参数
        params_list = function.get_parameters()
        
        # 验证参数
        assert isinstance(params_list, list)
        assert len(params_list) == 3
        assert params_list[0]["name"] == "origin"
        assert params_list[1]["name"] == "destination"
        assert params_list[2]["name"] == "date"
    
    def test_function_set_parameters(self):
        """测试设置功能参数"""
        # 创建功能实例
        function = Function()
        parameters = [
            {"name": "account_id", "type": "string", "required": True},
            {"name": "amount", "type": "number", "required": False, "default": 100}
        ]
        
        # 设置参数
        function.set_parameters(parameters)
        
        # 验证参数
        stored_params = function.get_parameters()
        assert stored_params == parameters
    
    def test_function_get_required_parameters(self):
        """测试获取必需参数"""
        # 创建功能实例
        function = Function()
        parameters = [
            {"name": "origin", "type": "string", "required": True},
            {"name": "destination", "type": "string", "required": True},
            {"name": "class", "type": "string", "required": False}
        ]
        function.parameters = json.dumps(parameters)
        
        # 获取必需参数
        required_params = function.get_required_parameters()
        
        # 验证必需参数
        assert len(required_params) == 2
        assert required_params[0]["name"] == "origin"
        assert required_params[1]["name"] == "destination"
        assert all(param["required"] for param in required_params)
    
    def test_function_get_optional_parameters(self):
        """测试获取可选参数"""
        # 创建功能实例
        function = Function()
        parameters = [
            {"name": "origin", "type": "string", "required": True},
            {"name": "class", "type": "string", "required": False},
            {"name": "seat", "type": "string", "required": False}
        ]
        function.parameters = json.dumps(parameters)
        
        # 获取可选参数
        optional_params = function.get_optional_parameters()
        
        # 验证可选参数
        assert len(optional_params) == 2
        assert optional_params[0]["name"] == "class"
        assert optional_params[1]["name"] == "seat"
        assert all(not param["required"] for param in optional_params)
    
    def test_function_validate_parameters(self):
        """测试参数验证"""
        # 创建功能实例
        function = Function()
        parameters = [
            {"name": "origin", "type": "string", "required": True},
            {"name": "destination", "type": "string", "required": True},
            {"name": "passengers", "type": "number", "required": False, "default": 1}
        ]
        function.parameters = json.dumps(parameters)
        
        # 验证有效参数
        valid_params = {
            "origin": "Beijing",
            "destination": "Shanghai",
            "passengers": 2
        }
        assert function.validate_parameters(valid_params) == True
        
        # 验证缺少必需参数
        invalid_params = {
            "origin": "Beijing"
            # 缺少 destination
        }
        assert function.validate_parameters(invalid_params) == False
    
    def test_function_get_parameter_schema(self):
        """测试获取参数模式"""
        # 创建功能实例
        function = Function()
        parameters = [
            {"name": "origin", "type": "string", "required": True},
            {"name": "destination", "type": "string", "required": True}
        ]
        function.parameters = json.dumps(parameters)
        
        # 获取参数模式
        schema = function.get_parameter_schema()
        
        # 验证模式
        assert isinstance(schema, dict)
        assert "origin" in schema
        assert "destination" in schema
        assert schema["origin"]["type"] == "string"
        assert schema["origin"]["required"] == True
    
    def test_function_is_api_function(self):
        """测试检查是否为API功能"""
        # 创建API功能
        function = Function()
        function.function_type = "api"
        assert function.is_api_function() == True
        
        # 创建Python功能
        function.function_type = "python"
        assert function.is_api_function() == False
    
    def test_function_is_python_function(self):
        """测试检查是否为Python功能"""
        # 创建Python功能
        function = Function()
        function.function_type = "python"
        assert function.is_python_function() == True
        
        # 创建API功能
        function.function_type = "api"
        assert function.is_python_function() == False
    
    def test_function_get_call_history(self):
        """测试获取调用历史"""
        # 创建功能实例
        function = Function()
        function.id = 1
        function.function_name = "book_flight"
        
        # 模拟调用历史
        mock_calls = [
            MagicMock(
                function_id=1,
                session_id="sess_123",
                parameters='{"origin": "Beijing", "destination": "Shanghai"}',
                result='{"success": true, "booking_id": "BK123"}',
                success=True
            ),
            MagicMock(
                function_id=1,
                session_id="sess_456",
                parameters='{"origin": "Shanghai", "destination": "Beijing"}',
                result='{"success": false, "error": "No flights available"}',
                success=False
            )
        ]
        
        with patch('src.models.function_call.FunctionCall') as mock_call_model:
            mock_query = MagicMock()
            mock_query.where.return_value.order_by.return_value.limit.return_value = mock_calls
            mock_call_model.select.return_value = mock_query
            
            # 获取调用历史
            history = function.get_call_history(limit=10)
            
            # 验证历史
            assert len(history) == 2
            assert history[0].success == True
            assert history[1].success == False
    
    def test_function_get_success_rate(self):
        """测试获取成功率"""
        # 创建功能实例
        function = Function()
        function.id = 1
        
        # 模拟调用统计
        with patch('src.models.function_call.FunctionCall') as mock_call_model:
            mock_query = MagicMock()
            mock_query.where.return_value.count.return_value = 100  # 总调用次数
            mock_call_model.select.return_value = mock_query
            
            # 模拟成功调用次数
            mock_success_query = MagicMock()
            mock_success_query.where.return_value.count.return_value = 85
            mock_call_model.select.return_value = mock_success_query
            
            # 获取成功率
            success_rate = function.get_success_rate()
            
            # 验证成功率
            assert success_rate == 0.85
    
    def test_function_get_average_response_time(self):
        """测试获取平均响应时间"""
        # 创建功能实例
        function = Function()
        function.id = 1
        
        # 模拟响应时间统计
        mock_calls = [
            MagicMock(response_time=0.1),
            MagicMock(response_time=0.2),
            MagicMock(response_time=0.3)
        ]
        
        with patch('src.models.function_call.FunctionCall') as mock_call_model:
            mock_query = MagicMock()
            mock_query.where.return_value = mock_calls
            mock_call_model.select.return_value = mock_query
            
            # 获取平均响应时间
            avg_time = function.get_average_response_time()
            
            # 验证平均响应时间
            assert avg_time == 0.2
    
    def test_function_clone(self):
        """测试克隆功能"""
        # 创建功能实例
        function = Function()
        function.function_name = "book_flight"
        function.function_type = "api"
        function.description = "预订机票功能"
        function.parameters = json.dumps([{"name": "origin", "type": "string"}])
        function.implementation = "https://api.airline.com/book"
        function.is_active = True
        
        # 克隆功能
        cloned_function = function.clone()
        
        # 验证克隆
        assert cloned_function.function_name == function.function_name
        assert cloned_function.function_type == function.function_type
        assert cloned_function.description == function.description
        assert cloned_function.parameters == function.parameters
        assert cloned_function.implementation == function.implementation
        assert cloned_function.is_active == function.is_active
        assert cloned_function.id != function.id  # ID应该不同
    
    def test_function_to_dict(self):
        """测试功能转字典"""
        # 创建功能实例
        function = Function()
        function.id = 1
        function.function_name = "book_flight"
        function.function_type = "api"
        function.description = "预订机票功能"
        function.parameters = json.dumps([{"name": "origin", "type": "string"}])
        function.implementation = "https://api.airline.com/book"
        function.timeout = 30
        function.retry_count = 3
        function.is_active = True
        function.created_at = datetime(2024, 1, 1, 10, 0, 0)
        
        # 转换为字典
        function_dict = function.to_dict()
        
        # 验证字典内容
        assert function_dict['id'] == 1
        assert function_dict['function_name'] == "book_flight"
        assert function_dict['function_type'] == "api"
        assert function_dict['description'] == "预订机票功能"
        assert isinstance(function_dict['parameters'], list)
        assert function_dict['implementation'] == "https://api.airline.com/book"
        assert function_dict['timeout'] == 30
        assert function_dict['retry_count'] == 3
        assert function_dict['is_active'] == True


class TestFunctionParameterModel:
    """功能参数模型测试类"""
    
    def test_function_parameter_creation(self):
        """测试功能参数创建"""
        # 创建功能参数实例
        parameter = FunctionParameter()
        parameter.function_id = 1
        parameter.parameter_name = "origin"
        parameter.parameter_type = "string"
        parameter.is_required = True
        parameter.default_value = None
        parameter.description = "出发地"
        parameter.validation_rules = json.dumps({"min_length": 2, "max_length": 50})
        
        # 验证功能参数属性
        assert parameter.function_id == 1
        assert parameter.parameter_name == "origin"
        assert parameter.parameter_type == "string"
        assert parameter.is_required == True
        assert parameter.default_value is None
        assert parameter.description == "出发地"
        assert isinstance(parameter.validation_rules, str)
    
    def test_function_parameter_get_validation_rules(self):
        """测试获取参数验证规则"""
        # 创建功能参数实例
        parameter = FunctionParameter()
        rules = {
            "min_length": 2,
            "max_length": 50,
            "pattern": "^[a-zA-Z\u4e00-\u9fa5]+$"
        }
        parameter.validation_rules = json.dumps(rules)
        
        # 获取验证规则
        validation_rules = parameter.get_validation_rules()
        
        # 验证规则
        assert isinstance(validation_rules, dict)
        assert validation_rules["min_length"] == 2
        assert validation_rules["max_length"] == 50
        assert validation_rules["pattern"] == "^[a-zA-Z\u4e00-\u9fa5]+$"
    
    def test_function_parameter_validate_value(self):
        """测试参数值验证"""
        # 创建功能参数实例
        parameter = FunctionParameter()
        parameter.parameter_type = "string"
        parameter.validation_rules = json.dumps({
            "min_length": 2,
            "max_length": 50
        })
        
        # 验证有效值
        assert parameter.validate_value("Beijing") == True
        assert parameter.validate_value("Shanghai") == True
        
        # 验证无效值
        assert parameter.validate_value("") == False
        assert parameter.validate_value("A") == False
        assert parameter.validate_value("A" * 51) == False
    
    def test_function_parameter_has_default_value(self):
        """测试检查是否有默认值"""
        # 创建有默认值的参数
        parameter = FunctionParameter()
        parameter.default_value = "Beijing"
        assert parameter.has_default_value() == True
        
        # 创建没有默认值的参数
        parameter.default_value = None
        assert parameter.has_default_value() == False
    
    def test_function_parameter_get_function(self):
        """测试获取参数所属功能"""
        # 创建功能参数实例
        parameter = FunctionParameter()
        parameter.function_id = 1
        
        # 模拟功能数据
        mock_function = MagicMock(
            id=1,
            function_name="book_flight",
            function_type="api"
        )
        
        with patch('src.models.function.Function') as mock_function_model:
            mock_function_model.get_by_id.return_value = mock_function
            
            # 获取功能
            function = parameter.get_function()
            
            # 验证功能
            assert function.id == 1
            assert function.function_name == "book_flight"
            assert function.function_type == "api"
    
    def test_function_parameter_to_dict(self):
        """测试功能参数转字典"""
        # 创建功能参数实例
        parameter = FunctionParameter()
        parameter.id = 1
        parameter.function_id = 1
        parameter.parameter_name = "origin"
        parameter.parameter_type = "string"
        parameter.is_required = True
        parameter.default_value = None
        parameter.description = "出发地"
        parameter.validation_rules = json.dumps({"min_length": 2})
        parameter.created_at = datetime(2024, 1, 1, 10, 0, 0)
        
        # 转换为字典
        parameter_dict = parameter.to_dict()
        
        # 验证字典内容
        assert parameter_dict['id'] == 1
        assert parameter_dict['function_id'] == 1
        assert parameter_dict['parameter_name'] == "origin"
        assert parameter_dict['parameter_type'] == "string"
        assert parameter_dict['is_required'] == True
        assert parameter_dict['default_value'] is None
        assert parameter_dict['description'] == "出发地"
        assert isinstance(parameter_dict['validation_rules'], dict)


class TestFunctionCallModel:
    """功能调用模型测试类"""
    
    def test_function_call_creation(self):
        """测试功能调用创建"""
        # 创建功能调用实例
        call = FunctionCall()
        call.function_id = 1
        call.session_id = "sess_123"
        call.function_name = "book_flight"
        call.parameters = json.dumps({
            "origin": "Beijing",
            "destination": "Shanghai",
            "date": "2024-01-01"
        })
        call.result = json.dumps({
            "success": True,
            "booking_id": "BK123456",
            "message": "预订成功"
        })
        call.success = True
        call.response_time = 0.25
        call.error_message = None
        
        # 验证功能调用属性
        assert call.function_id == 1
        assert call.session_id == "sess_123"
        assert call.function_name == "book_flight"
        assert isinstance(call.parameters, str)
        assert isinstance(call.result, str)
        assert call.success == True
        assert call.response_time == 0.25
        assert call.error_message is None
    
    def test_function_call_get_parameters(self):
        """测试获取调用参数"""
        # 创建功能调用实例
        call = FunctionCall()
        parameters = {
            "origin": "Beijing",
            "destination": "Shanghai",
            "date": "2024-01-01",
            "passengers": 2
        }
        call.parameters = json.dumps(parameters)
        
        # 获取参数
        params_dict = call.get_parameters()
        
        # 验证参数
        assert isinstance(params_dict, dict)
        assert params_dict["origin"] == "Beijing"
        assert params_dict["destination"] == "Shanghai"
        assert params_dict["date"] == "2024-01-01"
        assert params_dict["passengers"] == 2
    
    def test_function_call_get_result(self):
        """测试获取调用结果"""
        # 创建功能调用实例
        call = FunctionCall()
        result = {
            "success": True,
            "booking_id": "BK123456",
            "message": "预订成功",
            "total_price": 1200.50
        }
        call.result = json.dumps(result)
        
        # 获取结果
        result_dict = call.get_result()
        
        # 验证结果
        assert isinstance(result_dict, dict)
        assert result_dict["success"] == True
        assert result_dict["booking_id"] == "BK123456"
        assert result_dict["message"] == "预订成功"
        assert result_dict["total_price"] == 1200.50
    
    def test_function_call_is_successful(self):
        """测试检查调用是否成功"""
        # 创建成功调用
        call = FunctionCall()
        call.success = True
        assert call.is_successful() == True
        
        # 创建失败调用
        call.success = False
        assert call.is_successful() == False
    
    def test_function_call_is_fast_response(self):
        """测试检查是否快速响应"""
        # 创建快速响应调用
        call = FunctionCall()
        call.response_time = 0.1
        assert call.is_fast_response() == True
        
        # 创建慢速响应调用
        call.response_time = 2.0
        assert call.is_fast_response() == False
    
    def test_function_call_get_function(self):
        """测试获取调用的功能"""
        # 创建功能调用实例
        call = FunctionCall()
        call.function_id = 1
        
        # 模拟功能数据
        mock_function = MagicMock(
            id=1,
            function_name="book_flight",
            function_type="api"
        )
        
        with patch('src.models.function.Function') as mock_function_model:
            mock_function_model.get_by_id.return_value = mock_function
            
            # 获取功能
            function = call.get_function()
            
            # 验证功能
            assert function.id == 1
            assert function.function_name == "book_flight"
            assert function.function_type == "api"
    
    def test_function_call_get_session(self):
        """测试获取调用的会话"""
        # 创建功能调用实例
        call = FunctionCall()
        call.session_id = "sess_123"
        
        # 模拟会话数据
        mock_session = MagicMock(
            session_id="sess_123",
            user_id="user_456",
            status="active"
        )
        
        with patch('src.models.conversation.Session') as mock_session_model:
            mock_session_model.get.return_value = mock_session
            
            # 获取会话
            session = call.get_session()
            
            # 验证会话
            assert session.session_id == "sess_123"
            assert session.user_id == "user_456"
            assert session.status == "active"
    
    def test_function_call_get_duration(self):
        """测试获取调用持续时间"""
        # 创建功能调用实例
        call = FunctionCall()
        call.response_time = 0.35
        
        # 获取持续时间
        duration = call.get_duration()
        
        # 验证持续时间
        assert duration == 0.35
    
    def test_function_call_to_dict(self):
        """测试功能调用转字典"""
        # 创建功能调用实例
        call = FunctionCall()
        call.id = 1
        call.function_id = 1
        call.session_id = "sess_123"
        call.function_name = "book_flight"
        call.parameters = json.dumps({"origin": "Beijing", "destination": "Shanghai"})
        call.result = json.dumps({"success": True, "booking_id": "BK123456"})
        call.success = True
        call.response_time = 0.25
        call.error_message = None
        call.created_at = datetime(2024, 1, 1, 10, 0, 0)
        
        # 转换为字典
        call_dict = call.to_dict()
        
        # 验证字典内容
        assert call_dict['id'] == 1
        assert call_dict['function_id'] == 1
        assert call_dict['session_id'] == "sess_123"
        assert call_dict['function_name'] == "book_flight"
        assert isinstance(call_dict['parameters'], dict)
        assert isinstance(call_dict['result'], dict)
        assert call_dict['success'] == True
        assert call_dict['response_time'] == 0.25
        assert call_dict['error_message'] is None