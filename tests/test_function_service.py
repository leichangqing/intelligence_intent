"""
功能服务单元测试
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from typing import Dict, List, Optional, Any
import json
import asyncio
from datetime import datetime

from src.services.function_service import FunctionService, FunctionRetryConfig, CircuitBreaker
from src.models.function import Function, FunctionCall, FunctionParameter
from src.services.cache_service import CacheService


class TestFunctionRetryConfig:
    """函数重试配置测试类"""
    
    def test_init_default_values(self):
        """测试默认值初始化"""
        config = FunctionRetryConfig()
        
        assert config.max_attempts == 3
        assert config.base_delay == 1.0
        assert config.max_delay == 60.0
        assert config.backoff_factor == 2.0
        assert config.retry_exceptions == [Exception]
        assert config.retry_on_status == [500, 502, 503, 504, 429]
        assert config.jitter == True
        assert config.circuit_breaker == False
    
    def test_init_custom_values(self):
        """测试自定义值初始化"""
        custom_exceptions = [ValueError, TypeError]
        custom_status = [500, 503]
        
        config = FunctionRetryConfig(
            max_attempts=5,
            base_delay=2.0,
            max_delay=120.0,
            backoff_factor=3.0,
            retry_exceptions=custom_exceptions,
            retry_on_status=custom_status,
            jitter=False,
            circuit_breaker=True
        )
        
        assert config.max_attempts == 5
        assert config.base_delay == 2.0
        assert config.max_delay == 120.0
        assert config.backoff_factor == 3.0
        assert config.retry_exceptions == custom_exceptions
        assert config.retry_on_status == custom_status
        assert config.jitter == False
        assert config.circuit_breaker == True


class TestCircuitBreaker:
    """熔断器测试类"""
    
    def test_init_default_values(self):
        """测试默认值初始化"""
        circuit_breaker = CircuitBreaker()
        
        assert circuit_breaker.failure_threshold == 5
        assert circuit_breaker.recovery_timeout == 60.0
        assert circuit_breaker.expected_exception == Exception
        assert circuit_breaker.failure_count == 0
        assert circuit_breaker.last_failure_time is None
        assert circuit_breaker.state == 'closed'
    
    def test_init_custom_values(self):
        """测试自定义值初始化"""
        circuit_breaker = CircuitBreaker(
            failure_threshold=3,
            recovery_timeout=30.0,
            expected_exception=ValueError
        )
        
        assert circuit_breaker.failure_threshold == 3
        assert circuit_breaker.recovery_timeout == 30.0
        assert circuit_breaker.expected_exception == ValueError
    
    def test_call_success(self):
        """测试成功调用"""
        circuit_breaker = CircuitBreaker()
        
        def mock_func():
            return "success"
        
        result = circuit_breaker.call(mock_func)
        
        assert result == "success"
        assert circuit_breaker.failure_count == 0
        assert circuit_breaker.state == 'closed'
    
    def test_call_failure(self):
        """测试失败调用"""
        circuit_breaker = CircuitBreaker()
        
        def mock_func():
            raise ValueError("test error")
        
        with pytest.raises(ValueError):
            circuit_breaker.call(mock_func)
        
        assert circuit_breaker.failure_count == 1
        assert circuit_breaker.last_failure_time is not None
    
    def test_circuit_breaker_open(self):
        """测试熔断器打开状态"""
        circuit_breaker = CircuitBreaker(failure_threshold=2)
        
        def mock_func():
            raise ValueError("test error")
        
        # 触发失败次数达到阈值
        for _ in range(2):
            with pytest.raises(ValueError):
                circuit_breaker.call(mock_func)
        
        assert circuit_breaker.state == 'open'
        
        # 熔断器打开后，再次调用应该抛出熔断异常
        with pytest.raises(Exception, match="Circuit breaker is open"):
            circuit_breaker.call(mock_func)
    
    def test_should_attempt_reset(self):
        """测试是否应该尝试重置熔断器"""
        circuit_breaker = CircuitBreaker(recovery_timeout=0.1)
        
        # 模拟失败
        circuit_breaker.failure_count = 5
        circuit_breaker.last_failure_time = 0  # 设置为很早的时间
        
        # 应该尝试重置
        assert circuit_breaker._should_attempt_reset() == True
        
        # 设置为当前时间
        import time
        circuit_breaker.last_failure_time = time.time()
        
        # 不应该尝试重置
        assert circuit_breaker._should_attempt_reset() == False


class TestFunctionService:
    """功能服务测试类"""
    
    @pytest.fixture
    def mock_cache_service(self):
        """模拟缓存服务"""
        return AsyncMock(spec=CacheService)
    
    @pytest.fixture
    def function_service(self, mock_cache_service):
        """创建功能服务实例"""
        with patch('src.services.function_service.get_function_registry'), \
             patch('src.services.function_service.get_api_wrapper_manager'), \
             patch('src.services.function_service.get_parameter_validator'), \
             patch('src.services.function_service.get_parameter_mapper'):
            service = FunctionService(mock_cache_service)
            return service
    
    @pytest.fixture
    def mock_function(self):
        """模拟功能对象"""
        function = MagicMock()
        function.id = 1
        function.function_name = "book_flight"
        function.function_type = "api"
        function.description = "预订机票"
        function.parameters = json.dumps([
            {
                "name": "destination",
                "type": "string",
                "required": True,
                "description": "目的地"
            },
            {
                "name": "date",
                "type": "string",
                "required": True,
                "description": "出发日期"
            }
        ])
        function.is_active = True
        return function
    
    @pytest.mark.asyncio
    async def test_register_function(self, function_service):
        """测试注册函数"""
        # 准备测试数据
        function_data = {
            "function_name": "get_weather",
            "function_type": "api",
            "description": "获取天气信息",
            "parameters": [
                {
                    "name": "city",
                    "type": "string",
                    "required": True,
                    "description": "城市名称"
                }
            ],
            "implementation": "https://api.weather.com/current"
        }
        
        # 创建模拟Function对象
        mock_function = MagicMock()
        mock_function.id = 1
        mock_function.function_name = "get_weather"
        
        with patch('src.services.function_service.Function') as mock_function_model:
            mock_function_model.create.return_value = mock_function
            
            # 调用方法
            result = await function_service.register_function(function_data)
            
            # 验证结果
            assert result == mock_function
            
            # 验证Function.create被调用
            mock_function_model.create.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_call_function_success(self, function_service, mock_function):
        """测试成功调用函数"""
        # 准备测试数据
        function_name = "book_flight"
        parameters = {
            "destination": "上海",
            "date": "2024-01-01"
        }
        context = {}
        
        # 模拟函数调用结果
        expected_result = {
            "success": True,
            "booking_id": "BK123456",
            "message": "机票预订成功"
        }
        
        # 设置模拟行为
        with patch.object(function_service, '_get_function_by_name', return_value=mock_function), \
             patch.object(function_service, '_validate_parameters', return_value=None), \
             patch.object(function_service, '_execute_function', return_value=expected_result), \
             patch.object(function_service, '_save_function_call'):
            
            # 调用方法
            result = await function_service.call_function(function_name, parameters, context)
            
            # 验证结果
            assert result["success"] == True
            assert result["booking_id"] == "BK123456"
            assert result["message"] == "机票预订成功"
    
    @pytest.mark.asyncio
    async def test_call_function_validation_error(self, function_service, mock_function):
        """测试函数调用参数验证错误"""
        # 准备测试数据
        function_name = "book_flight"
        parameters = {
            "destination": "上海"
            # 缺少required参数"date"
        }
        context = {}
        
        # 模拟验证错误
        validation_error = "Missing required parameter: date"
        
        # 设置模拟行为
        with patch.object(function_service, '_get_function_by_name', return_value=mock_function), \
             patch.object(function_service, '_validate_parameters', return_value=validation_error):
            
            # 调用方法
            result = await function_service.call_function(function_name, parameters, context)
            
            # 验证结果
            assert result["success"] == False
            assert "validation_error" in result
            assert result["validation_error"] == validation_error
    
    @pytest.mark.asyncio
    async def test_call_function_not_found(self, function_service):
        """测试调用不存在的函数"""
        # 准备测试数据
        function_name = "nonexistent_function"
        parameters = {}
        context = {}
        
        # 设置模拟行为
        with patch.object(function_service, '_get_function_by_name', return_value=None):
            
            # 调用方法
            result = await function_service.call_function(function_name, parameters, context)
            
            # 验证结果
            assert result["success"] == False
            assert "error" in result
            assert "not found" in result["error"].lower()
    
    @pytest.mark.asyncio
    async def test_call_function_execution_error(self, function_service, mock_function):
        """测试函数执行错误"""
        # 准备测试数据
        function_name = "book_flight"
        parameters = {
            "destination": "上海",
            "date": "2024-01-01"
        }
        context = {}
        
        # 模拟执行错误
        execution_error = Exception("API call failed")
        
        # 设置模拟行为
        with patch.object(function_service, '_get_function_by_name', return_value=mock_function), \
             patch.object(function_service, '_validate_parameters', return_value=None), \
             patch.object(function_service, '_execute_function', side_effect=execution_error), \
             patch.object(function_service, '_save_function_call'):
            
            # 调用方法
            result = await function_service.call_function(function_name, parameters, context)
            
            # 验证结果
            assert result["success"] == False
            assert "error" in result
            assert "API call failed" in result["error"]
    
    @pytest.mark.asyncio
    async def test_call_function_with_retry(self, function_service, mock_function):
        """测试带重试的函数调用"""
        # 准备测试数据
        function_name = "book_flight"
        parameters = {
            "destination": "上海",
            "date": "2024-01-01"
        }
        context = {}
        
        # 设置重试配置
        retry_config = FunctionRetryConfig(max_attempts=3, base_delay=0.1)
        
        # 模拟前两次失败，第三次成功
        call_count = 0
        def mock_execute(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise Exception("Temporary failure")
            return {"success": True, "result": "success"}
        
        # 设置模拟行为
        with patch.object(function_service, '_get_function_by_name', return_value=mock_function), \
             patch.object(function_service, '_validate_parameters', return_value=None), \
             patch.object(function_service, '_execute_function', side_effect=mock_execute), \
             patch.object(function_service, '_save_function_call'):
            
            # 调用方法
            result = await function_service.call_function_with_retry(
                function_name, parameters, context, retry_config)
            
            # 验证结果
            assert result["success"] == True
            assert result["result"] == "success"
            assert call_count == 3  # 确认重试了3次
    
    @pytest.mark.asyncio
    async def test_get_function_by_name_from_cache(self, function_service, mock_cache_service):
        """测试从缓存获取函数"""
        # 准备测试数据
        function_name = "book_flight"
        cached_function = {
            "id": 1,
            "function_name": "book_flight",
            "function_type": "api",
            "description": "预订机票"
        }
        
        # 设置模拟行为
        mock_cache_service.get.return_value = cached_function
        
        # 调用方法
        result = await function_service._get_function_by_name(function_name)
        
        # 验证结果
        assert result == cached_function
        expected_cache_key = f"function:{function_name}"
        mock_cache_service.get.assert_called_once_with(expected_cache_key)
    
    @pytest.mark.asyncio
    async def test_get_function_by_name_from_database(self, function_service, mock_cache_service, mock_function):
        """测试从数据库获取函数"""
        # 准备测试数据
        function_name = "book_flight"
        
        # 设置模拟行为
        mock_cache_service.get.return_value = None
        
        with patch('src.services.function_service.Function') as mock_function_model:
            mock_function_model.get.return_value = mock_function
            
            # 调用方法
            result = await function_service._get_function_by_name(function_name)
            
            # 验证结果
            assert result == mock_function
            
            # 验证缓存被设置
            mock_cache_service.set.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_get_function_by_name_not_found(self, function_service, mock_cache_service):
        """测试获取不存在的函数"""
        # 准备测试数据
        function_name = "nonexistent_function"
        
        # 设置模拟行为
        mock_cache_service.get.return_value = None
        
        with patch('src.services.function_service.Function') as mock_function_model:
            mock_function_model.get.side_effect = mock_function_model.DoesNotExist
            
            # 调用方法
            result = await function_service._get_function_by_name(function_name)
            
            # 验证结果
            assert result is None
    
    @pytest.mark.asyncio
    async def test_validate_parameters_success(self, function_service, mock_function):
        """测试参数验证成功"""
        # 准备测试数据
        parameters = {
            "destination": "上海",
            "date": "2024-01-01"
        }
        
        # 模拟参数验证器返回成功
        mock_validator = MagicMock()
        mock_validator.validate_parameters.return_value = None
        
        function_service.parameter_validator = mock_validator
        
        # 调用方法
        result = await function_service._validate_parameters(mock_function, parameters)
        
        # 验证结果
        assert result is None
    
    @pytest.mark.asyncio
    async def test_validate_parameters_failure(self, function_service, mock_function):
        """测试参数验证失败"""
        # 准备测试数据
        parameters = {
            "destination": "上海"
            # 缺少required参数"date"
        }
        
        # 模拟参数验证器返回错误
        mock_validator = MagicMock()
        mock_validator.validate_parameters.return_value = "Missing required parameter: date"
        
        function_service.parameter_validator = mock_validator
        
        # 调用方法
        result = await function_service._validate_parameters(mock_function, parameters)
        
        # 验证结果
        assert result == "Missing required parameter: date"
    
    @pytest.mark.asyncio
    async def test_execute_function_api_type(self, function_service, mock_function):
        """测试执行API类型函数"""
        # 准备测试数据
        mock_function.function_type = "api"
        parameters = {
            "destination": "上海",
            "date": "2024-01-01"
        }
        
        expected_result = {
            "success": True,
            "booking_id": "BK123456"
        }
        
        # 模拟API包装器管理器
        mock_api_manager = MagicMock()
        mock_api_manager.execute_api_call.return_value = expected_result
        
        function_service.api_wrapper_manager = mock_api_manager
        
        # 调用方法
        result = await function_service._execute_function(mock_function, parameters)
        
        # 验证结果
        assert result == expected_result
    
    @pytest.mark.asyncio
    async def test_execute_function_python_type(self, function_service, mock_function):
        """测试执行Python类型函数"""
        # 准备测试数据
        mock_function.function_type = "python"
        mock_function.implementation = "def test_func(x, y): return x + y"
        parameters = {"x": 1, "y": 2}
        
        # 模拟函数注册表
        mock_registry = MagicMock()
        mock_registry.get_function.return_value = lambda x, y: x + y
        
        function_service.function_registry = mock_registry
        
        # 调用方法
        result = await function_service._execute_function(mock_function, parameters)
        
        # 验证结果
        assert result == 3
    
    @pytest.mark.asyncio
    async def test_save_function_call(self, function_service, mock_function):
        """测试保存函数调用记录"""
        # 准备测试数据
        parameters = {
            "destination": "上海",
            "date": "2024-01-01"
        }
        result = {
            "success": True,
            "booking_id": "BK123456"
        }
        session_id = "sess_123"
        
        # 创建模拟FunctionCall对象
        mock_function_call = MagicMock()
        mock_function_call.id = 1
        
        with patch('src.services.function_service.FunctionCall') as mock_function_call_model:
            mock_function_call_model.create.return_value = mock_function_call
            
            # 调用方法
            await function_service._save_function_call(
                mock_function, parameters, result, session_id)
            
            # 验证FunctionCall.create被调用
            mock_function_call_model.create.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_get_available_functions(self, function_service, mock_cache_service):
        """测试获取可用函数列表"""
        # 准备测试数据
        mock_cache_service.get.return_value = None
        
        # 创建模拟Function对象列表
        mock_function1 = MagicMock()
        mock_function1.function_name = "book_flight"
        mock_function1.description = "预订机票"
        mock_function1.is_active = True
        
        mock_function2 = MagicMock()
        mock_function2.function_name = "check_weather"
        mock_function2.description = "查看天气"
        mock_function2.is_active = True
        
        functions = [mock_function1, mock_function2]
        
        with patch('src.services.function_service.Function') as mock_function_model:
            mock_function_model.select.return_value.where.return_value = functions
            
            # 调用方法
            result = await function_service.get_available_functions()
            
            # 验证结果
            assert len(result) == 2
            assert result[0].function_name == "book_flight"
            assert result[1].function_name == "check_weather"
            
            # 验证缓存被设置
            mock_cache_service.set.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_get_function_call_history(self, function_service, mock_cache_service):
        """测试获取函数调用历史"""
        # 准备测试数据
        session_id = "sess_123"
        limit = 10
        
        mock_cache_service.get.return_value = None
        
        # 创建模拟FunctionCall对象
        mock_call = MagicMock()
        mock_call.id = 1
        mock_call.function_name = "book_flight"
        mock_call.parameters = '{"destination": "上海"}'
        mock_call.result = '{"success": true}'
        mock_call.created_at = datetime.now()
        
        function_calls = [mock_call]
        
        with patch('src.services.function_service.FunctionCall') as mock_function_call_model:
            mock_query = MagicMock()
            mock_query.where.return_value.order_by.return_value.limit.return_value = function_calls
            mock_function_call_model.select.return_value = mock_query
            
            # 调用方法
            result = await function_service.get_function_call_history(session_id, limit)
            
            # 验证结果
            assert len(result) == 1
            assert result[0] == mock_call
            
            # 验证缓存被设置
            mock_cache_service.set.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_error_handling(self, function_service, mock_function):
        """测试错误处理"""
        # 准备测试数据
        function_name = "book_flight"
        parameters = {
            "destination": "上海",
            "date": "2024-01-01"
        }
        context = {}
        
        # 设置模拟行为 - 获取函数时抛出异常
        with patch.object(function_service, '_get_function_by_name', side_effect=Exception("Database error")):
            
            # 调用方法
            result = await function_service.call_function(function_name, parameters, context)
            
            # 验证结果
            assert result["success"] == False
            assert "error" in result
            assert "Database error" in result["error"]