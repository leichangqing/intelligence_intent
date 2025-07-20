"""
聊天API接口单元测试
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient
from fastapi import FastAPI
import json
from datetime import datetime

from src.api.v1.chat import router as chat_router
from src.schemas.chat import ChatRequest, ChatResponse
from src.schemas.api_response import StandardResponse


@pytest.fixture
def app():
    """创建测试FastAPI应用"""
    app = FastAPI()
    app.include_router(chat_router, prefix="/api/v1")
    return app


@pytest.fixture
def client(app):
    """创建测试客户端"""
    return TestClient(app)


@pytest.fixture
def mock_dependencies():
    """模拟依赖"""
    with patch('src.api.v1.chat.get_current_user') as mock_user, \
         patch('src.api.v1.chat.get_cache_service_dependency') as mock_cache, \
         patch('src.api.v1.chat.get_intent_service_dependency') as mock_intent, \
         patch('src.api.v1.chat.get_conversation_service_dependency') as mock_conv, \
         patch('src.api.v1.chat.get_slot_service_dependency') as mock_slot, \
         patch('src.api.v1.chat.get_function_service_dependency') as mock_func:
        
        # 设置模拟返回值
        mock_user.return_value = {"user_id": "test_user", "is_admin": False}
        mock_cache.return_value = AsyncMock()
        mock_intent.return_value = AsyncMock()
        mock_conv.return_value = AsyncMock()
        mock_slot.return_value = AsyncMock()
        mock_func.return_value = AsyncMock()
        
        yield {
            "user": mock_user,
            "cache": mock_cache,
            "intent": mock_intent,
            "conversation": mock_conv,
            "slot": mock_slot,
            "function": mock_func
        }


class TestChatAPI:
    """聊天API测试类"""
    
    def test_chat_simple_message(self, client, mock_dependencies):
        """测试简单聊天消息"""
        # 准备测试数据
        request_data = {
            "message": "你好",
            "user_id": "test_user",
            "session_id": "test_session"
        }
        
        # 模拟服务返回
        mock_dependencies["intent"].return_value.recognize_intent.return_value = MagicMock(
            intent=MagicMock(intent_name="greeting"),
            confidence=0.9,
            is_ambiguous=False
        )
        
        mock_dependencies["conversation"].return_value.get_or_create_session.return_value = MagicMock(
            session_id="test_session",
            user_id="test_user"
        )
        
        # 发送请求
        response = client.post("/api/v1/chat", json=request_data)
        
        # 验证响应
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 200
        assert "message" in data
        assert "data" in data
    
    def test_chat_with_intent_recognition(self, client, mock_dependencies):
        """测试带意图识别的聊天"""
        # 准备测试数据
        request_data = {
            "message": "我要订机票",
            "user_id": "test_user",
            "session_id": "test_session"
        }
        
        # 模拟意图识别结果
        mock_intent_result = MagicMock()
        mock_intent_result.intent.intent_name = "book_flight"
        mock_intent_result.confidence = 0.95
        mock_intent_result.is_ambiguous = False
        
        mock_dependencies["intent"].return_value.recognize_intent.return_value = mock_intent_result
        
        # 模拟会话
        mock_session = MagicMock()
        mock_session.session_id = "test_session"
        mock_session.user_id = "test_user"
        
        mock_dependencies["conversation"].return_value.get_or_create_session.return_value = mock_session
        
        # 模拟槽位提取
        mock_slot_result = MagicMock()
        mock_slot_result.is_complete = False
        mock_slot_result.missing_slots = ["destination", "date"]
        
        mock_dependencies["slot"].return_value.extract_slots.return_value = mock_slot_result
        mock_dependencies["slot"].return_value.generate_question_for_missing_slots.return_value = "请问您要去哪里？"
        
        # 发送请求
        response = client.post("/api/v1/chat", json=request_data)
        
        # 验证响应
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 200
        assert "data" in data
        assert "intent" in data["data"]
        assert data["data"]["intent"]["name"] == "book_flight"
        assert data["data"]["intent"]["confidence"] == 0.95
    
    def test_chat_ambiguous_intent(self, client, mock_dependencies):
        """测试歧义意图处理"""
        # 准备测试数据
        request_data = {
            "message": "我想处理机票",
            "user_id": "test_user",
            "session_id": "test_session"
        }
        
        # 模拟歧义意图结果
        mock_intent_result = MagicMock()
        mock_intent_result.intent = None
        mock_intent_result.confidence = 0.5
        mock_intent_result.is_ambiguous = True
        mock_intent_result.alternatives = [
            {"intent": "book_flight", "confidence": 0.7},
            {"intent": "check_flight", "confidence": 0.6}
        ]
        
        mock_dependencies["intent"].return_value.recognize_intent.return_value = mock_intent_result
        
        # 模拟会话
        mock_session = MagicMock()
        mock_session.session_id = "test_session"
        mock_session.user_id = "test_user"
        
        mock_dependencies["conversation"].return_value.get_or_create_session.return_value = mock_session
        
        # 发送请求
        response = client.post("/api/v1/chat", json=request_data)
        
        # 验证响应
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 200
        assert "data" in data
        assert data["data"]["ambiguous"] == True
        assert "alternatives" in data["data"]
        assert len(data["data"]["alternatives"]) == 2
    
    def test_chat_function_call(self, client, mock_dependencies):
        """测试功能调用"""
        # 准备测试数据
        request_data = {
            "message": "订一张明天从北京到上海的机票",
            "user_id": "test_user",
            "session_id": "test_session"
        }
        
        # 模拟意图识别结果
        mock_intent_result = MagicMock()
        mock_intent_result.intent.intent_name = "book_flight"
        mock_intent_result.confidence = 0.95
        mock_intent_result.is_ambiguous = False
        
        mock_dependencies["intent"].return_value.recognize_intent.return_value = mock_intent_result
        
        # 模拟会话
        mock_session = MagicMock()
        mock_session.session_id = "test_session"
        mock_session.user_id = "test_user"
        
        mock_dependencies["conversation"].return_value.get_or_create_session.return_value = mock_session
        
        # 模拟完整槽位提取
        mock_slot_result = MagicMock()
        mock_slot_result.is_complete = True
        mock_slot_result.missing_slots = []
        mock_slot_result.slots = {
            "origin": {"value": "北京", "confidence": 0.9},
            "destination": {"value": "上海", "confidence": 0.9},
            "date": {"value": "明天", "confidence": 0.8}
        }
        
        mock_dependencies["slot"].return_value.extract_slots.return_value = mock_slot_result
        
        # 模拟功能调用结果
        mock_function_result = {
            "success": True,
            "booking_id": "BK123456",
            "message": "机票预订成功"
        }
        
        mock_dependencies["function"].return_value.call_function.return_value = mock_function_result
        
        # 发送请求
        response = client.post("/api/v1/chat", json=request_data)
        
        # 验证响应
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 200
        assert "data" in data
        assert data["data"]["function_called"] == True
        assert data["data"]["function_result"]["success"] == True
        assert data["data"]["function_result"]["booking_id"] == "BK123456"
    
    def test_chat_invalid_request(self, client, mock_dependencies):
        """测试无效请求"""
        # 准备无效数据（缺少必需字段）
        request_data = {
            "message": "你好"
            # 缺少 user_id 和 session_id
        }
        
        # 发送请求
        response = client.post("/api/v1/chat", json=request_data)
        
        # 验证响应
        assert response.status_code == 422  # Validation Error
    
    def test_chat_empty_message(self, client, mock_dependencies):
        """测试空消息"""
        # 准备测试数据
        request_data = {
            "message": "",
            "user_id": "test_user",
            "session_id": "test_session"
        }
        
        # 发送请求
        response = client.post("/api/v1/chat", json=request_data)
        
        # 验证响应
        assert response.status_code == 400
        data = response.json()
        assert data["code"] == 400
        assert "消息不能为空" in data["message"]
    
    def test_chat_service_error(self, client, mock_dependencies):
        """测试服务错误"""
        # 准备测试数据
        request_data = {
            "message": "测试错误",
            "user_id": "test_user",
            "session_id": "test_session"
        }
        
        # 模拟服务错误
        mock_dependencies["intent"].return_value.recognize_intent.side_effect = Exception("服务不可用")
        
        # 发送请求
        response = client.post("/api/v1/chat", json=request_data)
        
        # 验证响应
        assert response.status_code == 500
        data = response.json()
        assert data["code"] == 500
        assert "服务不可用" in data["message"]
    
    def test_chat_with_context(self, client, mock_dependencies):
        """测试带上下文的聊天"""
        # 准备测试数据
        request_data = {
            "message": "改成明天",
            "user_id": "test_user",
            "session_id": "test_session",
            "context": {
                "current_intent": "book_flight",
                "slots": {
                    "origin": {"value": "北京", "confidence": 0.9},
                    "destination": {"value": "上海", "confidence": 0.9}
                }
            }
        }
        
        # 模拟意图识别结果
        mock_intent_result = MagicMock()
        mock_intent_result.intent.intent_name = "book_flight"
        mock_intent_result.confidence = 0.9
        mock_intent_result.is_ambiguous = False
        
        mock_dependencies["intent"].return_value.recognize_intent.return_value = mock_intent_result
        
        # 模拟会话
        mock_session = MagicMock()
        mock_session.session_id = "test_session"
        mock_session.user_id = "test_user"
        
        mock_dependencies["conversation"].return_value.get_or_create_session.return_value = mock_session
        
        # 模拟槽位提取（基于上下文）
        mock_slot_result = MagicMock()
        mock_slot_result.is_complete = True
        mock_slot_result.missing_slots = []
        mock_slot_result.slots = {
            "origin": {"value": "北京", "confidence": 0.9},
            "destination": {"value": "上海", "confidence": 0.9},
            "date": {"value": "明天", "confidence": 0.8}
        }
        
        mock_dependencies["slot"].return_value.extract_slots.return_value = mock_slot_result
        
        # 发送请求
        response = client.post("/api/v1/chat", json=request_data)
        
        # 验证响应
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 200
        assert "data" in data
        assert data["data"]["context_used"] == True
    
    def test_chat_conversation_history(self, client, mock_dependencies):
        """测试获取对话历史"""
        # 准备测试数据
        session_id = "test_session"
        
        # 模拟对话历史
        mock_history = [
            {
                "id": 1,
                "user_input": "你好",
                "response": "您好！有什么可以帮助您的吗？",
                "created_at": datetime.now().isoformat()
            },
            {
                "id": 2,
                "user_input": "我要订机票",
                "response": "好的，我帮您预订机票。请问您要去哪里？",
                "created_at": datetime.now().isoformat()
            }
        ]
        
        mock_dependencies["conversation"].return_value.get_conversation_history.return_value = mock_history
        
        # 发送请求
        response = client.get(f"/api/v1/chat/history/{session_id}")
        
        # 验证响应
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 200
        assert "data" in data
        assert len(data["data"]["conversations"]) == 2
        assert data["data"]["conversations"][0]["user_input"] == "你好"
    
    def test_chat_clear_context(self, client, mock_dependencies):
        """测试清空上下文"""
        # 准备测试数据
        session_id = "test_session"
        
        # 模拟清空上下文
        mock_dependencies["conversation"].return_value.clear_session_context.return_value = True
        
        # 发送请求
        response = client.delete(f"/api/v1/chat/context/{session_id}")
        
        # 验证响应
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 200
        assert "已清空" in data["message"]
    
    def test_chat_get_session_info(self, client, mock_dependencies):
        """测试获取会话信息"""
        # 准备测试数据
        session_id = "test_session"
        
        # 模拟会话信息
        mock_session = MagicMock()
        mock_session.session_id = session_id
        mock_session.user_id = "test_user"
        mock_session.created_at = datetime.now()
        mock_session.get_context.return_value = {
            "current_intent": "book_flight",
            "slots": {}
        }
        
        mock_dependencies["conversation"].return_value.get_or_create_session.return_value = mock_session
        
        # 发送请求
        response = client.get(f"/api/v1/chat/session/{session_id}")
        
        # 验证响应
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 200
        assert "data" in data
        assert data["data"]["session_id"] == session_id
        assert data["data"]["user_id"] == "test_user"