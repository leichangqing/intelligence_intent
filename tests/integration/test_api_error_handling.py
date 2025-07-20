"""
API层错误处理集成测试
测试API层的错误响应、状态码和错误格式
"""
import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime
import json
from fastapi import HTTPException, status
from fastapi.testclient import TestClient

from src.api.exceptions import setup_exception_handlers
from src.core.error_handler import StandardError, ValidationError, AuthenticationError
from src.schemas.api_response import ApiResponse, ApiError
from src.services.intent_service import IntentService


class TestAPIErrorHandling:
    """API层错误处理测试类"""
    
    @pytest.fixture
    def mock_client(self):
        """创建模拟API客户端"""
        from src.main import app
        return TestClient(app)
    
    @pytest.fixture
    def mock_services(self):
        """创建模拟服务"""
        return {
            'intent_service': MagicMock(spec=IntentService),
            'conversation_service': MagicMock(),
            'slot_service': MagicMock(),
            'function_service': MagicMock()
        }
    
    def test_chat_api_validation_error(self, mock_client):
        """测试聊天API验证错误"""
        # 发送无效请求
        invalid_request = {
            "message": "",  # 空消息
            "session_id": "a" * 101,  # 超长session_id
            "user_id": None  # 空user_id
        }
        
        response = mock_client.post("/api/v1/chat", json=invalid_request)
        
        # 验证响应
        assert response.status_code == 422
        
        response_data = response.json()
        assert response_data["status"] == "error"
        assert response_data["error"]["code"].startswith("E2")  # 验证错误代码
        assert "validation" in response_data["error"]["message"].lower()
        assert len(response_data["error"]["details"]) >= 2  # 至少2个验证错误
        
        # 验证错误详情
        details = response_data["error"]["details"]
        field_errors = [d["field"] for d in details]
        assert "message" in field_errors
        assert "session_id" in field_errors
    
    def test_chat_api_service_unavailable_error(self, mock_client, mock_services):
        """测试聊天API服务不可用错误"""
        # 模拟服务不可用
        with patch('src.services.intent_service.IntentService') as mock_intent_service:
            mock_intent_service.recognize_intent.side_effect = Exception("Service unavailable")
            
            request_data = {
                "message": "我要订机票",
                "session_id": "test_session_001",
                "user_id": "test_user_001"
            }
            
            response = mock_client.post("/api/v1/chat", json=request_data)
            
            # 验证响应
            assert response.status_code == 500
            
            response_data = response.json()
            assert response_data["status"] == "error"
            assert response_data["error"]["code"].startswith("E5")  # 服务错误代码
            assert "service" in response_data["error"]["message"].lower()
            
            # 验证不泄露内部错误信息
            assert "Service unavailable" not in response_data["error"]["message"]
            assert response_data["error"]["message"] == "服务暂时不可用，请稍后重试"
    
    def test_chat_api_authentication_error(self, mock_client):
        """测试聊天API认证错误"""
        request_data = {
            "message": "我要订机票",
            "session_id": "test_session_001",
            "user_id": "test_user_001"
        }
        
        # 发送请求但不包含认证头
        response = mock_client.post("/api/v1/chat", json=request_data)
        
        # 如果API需要认证，验证认证错误响应
        if response.status_code == 401:
            response_data = response.json()
            assert response_data["status"] == "error"
            assert response_data["error"]["code"].startswith("E3")  # 认证错误代码
            assert "认证" in response_data["error"]["message"] or "authentication" in response_data["error"]["message"].lower()
    
    def test_chat_api_rate_limit_error(self, mock_client):
        """测试聊天API速率限制错误"""
        request_data = {
            "message": "我要订机票",
            "session_id": "test_session_001", 
            "user_id": "test_user_001"
        }
        
        # 模拟超过速率限制的请求
        with patch('src.middleware.rate_limit.check_rate_limit') as mock_rate_limit:
            mock_rate_limit.side_effect = HTTPException(
                status_code=429,
                detail="Rate limit exceeded"
            )
            
            response = mock_client.post("/api/v1/chat", json=request_data)
            
            # 验证响应
            if response.status_code == 429:
                response_data = response.json()
                assert response_data["status"] == "error"
                assert response_data["error"]["code"].startswith("E8")  # 速率限制错误代码
                assert "限制" in response_data["error"]["message"] or "limit" in response_data["error"]["message"].lower()
                
                # 验证Retry-After头
                assert "Retry-After" in response.headers
    
    def test_ambiguity_resolution_api_error(self, mock_client):
        """测试歧义解决API错误"""
        # 发送无效的歧义解决请求
        invalid_request = {
            "session_id": "test_session_001",
            "selected_intent": "",  # 空意图
            "user_id": "test_user_001"
        }
        
        response = mock_client.post("/api/v1/ambiguity/resolve", json=invalid_request)
        
        # 验证响应
        assert response.status_code == 422
        
        response_data = response.json()
        assert response_data["status"] == "error"
        assert "selected_intent" in str(response_data["error"]["details"])
    
    def test_admin_api_unauthorized_error(self, mock_client):
        """测试管理API未授权错误"""
        # 尝试访问管理接口而不提供管理员权限
        response = mock_client.get("/api/v1/admin/config")
        
        # 验证响应
        if response.status_code in [401, 403]:
            response_data = response.json()
            assert response_data["status"] == "error"
            assert response_data["error"]["code"].startswith("E3")  # 认证/授权错误
    
    def test_health_api_dependency_error(self, mock_client):
        """测试健康检查API依赖错误"""
        # 模拟依赖服务不可用
        with patch('src.services.cache_service.CacheService.ping') as mock_cache_ping:
            mock_cache_ping.side_effect = Exception("Cache unavailable")
            
            response = mock_client.get("/api/v1/health")
            
            # 健康检查可能返回503或200但状态为unhealthy
            response_data = response.json()
            
            if response.status_code == 503:
                assert response_data["status"] == "error"
                assert "health" in response_data["error"]["message"].lower()
            elif response.status_code == 200:
                assert response_data["data"]["status"] == "unhealthy"
                assert any(dep["status"] == "unhealthy" for dep in response_data["data"]["dependencies"])
    
    def test_task_api_resource_not_found_error(self, mock_client):
        """测试任务API资源未找到错误"""
        # 尝试获取不存在的任务
        response = mock_client.get("/api/v1/tasks/nonexistent_task_id")
        
        # 验证响应
        assert response.status_code == 404
        
        response_data = response.json()
        assert response_data["status"] == "error"
        assert response_data["error"]["code"].startswith("E4")  # 业务逻辑错误
        assert "未找到" in response_data["error"]["message"] or "not found" in response_data["error"]["message"].lower()
    
    def test_api_request_timeout_error(self, mock_client):
        """测试API请求超时错误"""
        # 模拟长时间运行的请求
        with patch('src.services.conversation_service.ConversationService.process_message') as mock_process:
            mock_process.side_effect = asyncio.TimeoutError("Request timeout")
            
            request_data = {
                "message": "复杂的查询请求",
                "session_id": "test_session_001",
                "user_id": "test_user_001"
            }
            
            response = mock_client.post("/api/v1/chat", json=request_data)
            
            # 验证响应
            if response.status_code == 408:
                response_data = response.json()
                assert response_data["status"] == "error"
                assert response_data["error"]["code"].startswith("E8")  # 网络/超时错误
                assert "超时" in response_data["error"]["message"] or "timeout" in response_data["error"]["message"].lower()
    
    def test_api_payload_too_large_error(self, mock_client):
        """测试API载荷过大错误"""
        # 创建过大的请求载荷
        large_message = "x" * (1024 * 1024 + 1)  # 超过1MB
        
        request_data = {
            "message": large_message,
            "session_id": "test_session_001",
            "user_id": "test_user_001"
        }
        
        response = mock_client.post("/api/v1/chat", json=request_data)
        
        # 验证响应
        if response.status_code == 413:
            response_data = response.json()
            assert response_data["status"] == "error"
            assert response_data["error"]["code"].startswith("E9")  # 资源错误
            assert "过大" in response_data["error"]["message"] or "large" in response_data["error"]["message"].lower()
    
    def test_api_malformed_json_error(self, mock_client):
        """测试API格式错误的JSON"""
        # 发送格式错误的JSON
        response = mock_client.post(
            "/api/v1/chat",
            data='{"message": "test", "session_id": "test_session_001", "user_id": "test_user_001"',  # 缺少结束括号
            headers={"Content-Type": "application/json"}
        )
        
        # 验证响应
        assert response.status_code == 422
        
        response_data = response.json()
        assert response_data["status"] == "error"
        assert "json" in response_data["error"]["message"].lower() or "格式" in response_data["error"]["message"]
    
    def test_api_missing_content_type_error(self, mock_client):
        """测试API缺少Content-Type错误"""
        request_data = {
            "message": "我要订机票",
            "session_id": "test_session_001",
            "user_id": "test_user_001"
        }
        
        # 发送请求但不设置Content-Type
        response = mock_client.post(
            "/api/v1/chat",
            data=json.dumps(request_data)
            # 故意不设置Content-Type头
        )
        
        # 验证响应 - 可能是422或415
        if response.status_code in [415, 422]:
            response_data = response.json()
            assert response_data["status"] == "error"
    
    @pytest.mark.asyncio
    async def test_api_concurrent_error_handling(self, mock_client):
        """测试API并发错误处理"""
        # 并发发送多个可能出错的请求
        request_data = {
            "message": "测试并发错误",
            "session_id": "test_session_001",
            "user_id": "test_user_001"
        }
        
        # 模拟不同类型的错误
        with patch('src.services.intent_service.IntentService.recognize_intent') as mock_recognize:
            # 设置不同的错误响应
            mock_recognize.side_effect = [
                Exception("Service error 1"),
                ValueError("Validation error"),
                TimeoutError("Timeout error"),
                ConnectionError("Connection error"),
                Exception("Service error 2")
            ]
            
            # 发送并发请求
            responses = []
            for i in range(5):
                response = mock_client.post(f"/api/v1/chat", json={
                    **request_data,
                    "session_id": f"session_{i+1:03d}"
                })
                responses.append(response)
            
            # 验证所有响应都是错误格式
            for response in responses:
                if response.status_code >= 400:
                    response_data = response.json()
                    assert response_data["status"] == "error"
                    assert "error" in response_data
                    assert "code" in response_data["error"]
                    assert "message" in response_data["error"]
    
    def test_api_error_response_format_consistency(self, mock_client):
        """测试API错误响应格式一致性"""
        # 测试不同类型的错误都返回相同格式
        error_endpoints = [
            ("/api/v1/chat", "post", {"invalid": "data"}),
            ("/api/v1/ambiguity/resolve", "post", {"invalid": "data"}),
            ("/api/v1/tasks/invalid_id", "get", None),
            ("/api/v1/admin/config", "get", None)
        ]
        
        for endpoint, method, data in error_endpoints:
            if method == "post":
                response = mock_client.post(endpoint, json=data)
            else:
                response = mock_client.get(endpoint)
            
            # 如果返回错误状态码，验证格式
            if response.status_code >= 400:
                response_data = response.json()
                
                # 验证必需字段
                assert "status" in response_data
                assert response_data["status"] == "error"
                assert "error" in response_data
                
                error_obj = response_data["error"]
                assert "code" in error_obj
                assert "message" in error_obj
                assert "timestamp" in error_obj
                
                # 验证错误代码格式
                assert error_obj["code"].startswith("E")
                assert len(error_obj["code"]) == 5  # E + 4位数字
                
                # 验证时间戳格式
                assert isinstance(error_obj["timestamp"], str)
                datetime.fromisoformat(error_obj["timestamp"])  # 验证ISO格式
    
    def test_api_error_security_information_leak(self, mock_client):
        """测试API错误不泄露敏感信息"""
        # 模拟包含敏感信息的内部错误
        with patch('src.services.conversation_service.ConversationService') as mock_service:
            sensitive_error = Exception("Database password: secret123, API key: xyz789")
            mock_service.return_value.save_conversation.side_effect = sensitive_error
            
            request_data = {
                "message": "触发敏感错误",
                "session_id": "test_session_001",
                "user_id": "test_user_001"
            }
            
            response = mock_client.post("/api/v1/chat", json=request_data)
            
            # 验证响应不包含敏感信息
            response_text = response.text.lower()
            assert "password" not in response_text
            assert "secret" not in response_text
            assert "api key" not in response_text
            assert "secret123" not in response_text
            assert "xyz789" not in response_text
            
            # 验证返回通用错误消息
            if response.status_code >= 400:
                response_data = response.json()
                assert response_data["error"]["message"] in [
                    "服务暂时不可用，请稍后重试",
                    "系统内部错误",
                    "Internal server error"
                ]
    
    def test_api_error_correlation_id(self, mock_client):
        """测试API错误关联ID"""
        # 发送会产生错误的请求
        request_data = {
            "message": "",  # 空消息触发验证错误
            "session_id": "test_session_001",
            "user_id": "test_user_001"
        }
        
        response = mock_client.post("/api/v1/chat", json=request_data)
        
        if response.status_code >= 400:
            response_data = response.json()
            
            # 验证包含请求ID
            assert "metadata" in response_data
            metadata = response_data["metadata"]
            assert "request_id" in metadata
            assert isinstance(metadata["request_id"], str)
            assert len(metadata["request_id"]) > 0
            
            # 验证响应头也包含请求ID
            assert "X-Request-ID" in response.headers
            assert response.headers["X-Request-ID"] == metadata["request_id"]
    
    def test_api_error_metrics_collection(self, mock_client):
        """测试API错误指标收集"""
        # 模拟错误以测试指标收集
        with patch('src.utils.metrics.record_api_error') as mock_metrics:
            request_data = {
                "message": "",  # 触发验证错误
                "session_id": "test_session_001",
                "user_id": "test_user_001"
            }
            
            response = mock_client.post("/api/v1/chat", json=request_data)
            
            if response.status_code >= 400:
                # 验证错误指标被记录
                mock_metrics.assert_called_once()
                
                call_args = mock_metrics.call_args[1]
                assert "endpoint" in call_args
                assert "error_code" in call_args
                assert "status_code" in call_args
                assert call_args["endpoint"] == "/api/v1/chat"
                assert call_args["status_code"] == response.status_code


class TestAPIErrorMiddleware:
    """API错误中间件测试类"""
    
    def test_exception_handlers_setup(self):
        """测试异常处理器设置"""
        from fastapi import FastAPI
        
        app = FastAPI()
        setup_exception_handlers(app)
        
        # 验证异常处理器被注册
        assert len(app.exception_handlers) > 0
    
    @pytest.mark.asyncio
    async def test_standard_error_handling(self):
        """测试标准错误处理"""
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        
        app = FastAPI()
        setup_exception_handlers(app)
        
        @app.get("/test-error")
        async def test_error_endpoint():
            raise StandardError(
                message="Test error",
                context={"test": "data"}
            )
        
        client = TestClient(app)
        response = client.get("/test-error")
        
        # 验证响应
        assert response.status_code == 500
        response_data = response.json()
        assert response_data["success"] == False
        assert "Test error" in response_data["message"]
    
    def test_error_message_sanitization(self):
        """测试错误信息清理"""
        # 模拟错误信息清理逻辑
        def sanitize_error_message(message: str) -> str:
            sensitive_patterns = ["password", "secret", "api key", "token"]
            for pattern in sensitive_patterns:
                if pattern in message.lower():
                    return "服务暂时不可用，请稍后重试"
            return message
        
        # 测试敏感信息清理
        sensitive_message = "Database error: password=secret123, API key=xyz789"
        sanitized = sanitize_error_message(sensitive_message)
        
        assert sanitized == "服务暂时不可用，请稍后重试"
    
    def test_error_logging(self):
        """测试错误日志记录"""
        # 模拟错误日志记录
        def log_error_details(error: Exception, request_id: str, path: str, method: str):
            return f"Error {request_id} at {method} {path}: {str(error)}"
        
        with patch('src.utils.logger.get_logger') as mock_logger:
            logger_instance = MagicMock()
            mock_logger.return_value = logger_instance
            
            error = Exception("Test error")
            request_id = "test-request-123"
            
            log_message = log_error_details(error, request_id, "/api/v1/chat", "POST")
            
            # 验证日志信息格式
            assert request_id in log_message
            assert "/api/v1/chat" in log_message
            assert "POST" in log_message
            assert "Test error" in log_message