"""
管理API接口单元测试
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient
from fastapi import FastAPI
import json
from datetime import datetime

from src.api.v1.admin import router as admin_router


@pytest.fixture
def app():
    """创建测试FastAPI应用"""
    app = FastAPI()
    app.include_router(admin_router, prefix="/api/v1")
    return app


@pytest.fixture
def client(app):
    """创建测试客户端"""
    return TestClient(app)


@pytest.fixture
def mock_dependencies():
    """模拟依赖"""
    with patch('src.api.v1.admin.require_admin_auth') as mock_auth, \
         patch('src.api.v1.admin.get_cache_service_dependency') as mock_cache, \
         patch('src.api.v1.admin.get_intent_service_dependency') as mock_intent, \
         patch('src.api.v1.admin.get_conversation_service_dependency') as mock_conv:
        
        # 设置模拟返回值
        mock_auth.return_value = {"user_id": "admin_user", "is_admin": True}
        mock_cache.return_value = AsyncMock()
        mock_intent.return_value = AsyncMock()
        mock_conv.return_value = AsyncMock()
        
        yield {
            "auth": mock_auth,
            "cache": mock_cache,
            "intent": mock_intent,
            "conversation": mock_conv
        }


class TestAdminAPI:
    """管理API测试类"""
    
    def test_get_system_stats(self, client, mock_dependencies):
        """测试获取系统统计"""
        # 模拟统计数据
        mock_stats = {
            "total_users": 100,
            "active_sessions": 25,
            "total_conversations": 500,
            "total_intents": 20,
            "cache_hit_rate": 0.85
        }
        
        with patch('src.api.v1.admin.get_system_stats', return_value=mock_stats):
            # 发送请求
            response = client.get("/api/v1/admin/stats")
            
            # 验证响应
            assert response.status_code == 200
            data = response.json()
            assert data["code"] == 200
            assert "data" in data
            assert data["data"]["total_users"] == 100
            assert data["data"]["active_sessions"] == 25
            assert data["data"]["cache_hit_rate"] == 0.85
    
    def test_get_intent_config(self, client, mock_dependencies):
        """测试获取意图配置"""
        # 模拟意图配置
        mock_intents = [
            {
                "id": 1,
                "intent_name": "book_flight",
                "description": "预订机票",
                "is_active": True,
                "confidence_threshold": 0.7,
                "examples": ["我要订机票", "预订航班"]
            },
            {
                "id": 2,
                "intent_name": "check_balance",
                "description": "查询余额",
                "is_active": True,
                "confidence_threshold": 0.8,
                "examples": ["查看余额", "余额查询"]
            }
        ]
        
        with patch('src.models.intent.Intent') as mock_intent_model:
            mock_intent_model.select.return_value = mock_intents
            
            # 发送请求
            response = client.get("/api/v1/admin/intents")
            
            # 验证响应
            assert response.status_code == 200
            data = response.json()
            assert data["code"] == 200
            assert "data" in data
            assert len(data["data"]["intents"]) == 2
            assert data["data"]["intents"][0]["intent_name"] == "book_flight"
    
    def test_create_intent(self, client, mock_dependencies):
        """测试创建意图"""
        # 准备测试数据
        intent_data = {
            "intent_name": "cancel_booking",
            "description": "取消预订",
            "examples": ["取消预订", "我要取消"],
            "confidence_threshold": 0.7,
            "is_active": True
        }
        
        # 模拟创建结果
        mock_intent = MagicMock()
        mock_intent.id = 3
        mock_intent.intent_name = "cancel_booking"
        mock_intent.description = "取消预订"
        
        with patch('src.models.intent.Intent') as mock_intent_model:
            mock_intent_model.create.return_value = mock_intent
            
            # 发送请求
            response = client.post("/api/v1/admin/intents", json=intent_data)
            
            # 验证响应
            assert response.status_code == 201
            data = response.json()
            assert data["code"] == 201
            assert "data" in data
            assert data["data"]["intent_name"] == "cancel_booking"
    
    def test_update_intent(self, client, mock_dependencies):
        """测试更新意图"""
        # 准备测试数据
        intent_id = 1
        update_data = {
            "description": "更新后的描述",
            "confidence_threshold": 0.8,
            "is_active": False
        }
        
        # 模拟更新结果
        mock_intent = MagicMock()
        mock_intent.id = intent_id
        mock_intent.intent_name = "book_flight"
        mock_intent.description = "更新后的描述"
        mock_intent.confidence_threshold = 0.8
        mock_intent.is_active = False
        
        with patch('src.models.intent.Intent') as mock_intent_model:
            mock_intent_model.get_by_id.return_value = mock_intent
            
            # 发送请求
            response = client.put(f"/api/v1/admin/intents/{intent_id}", json=update_data)
            
            # 验证响应
            assert response.status_code == 200
            data = response.json()
            assert data["code"] == 200
            assert "data" in data
            assert data["data"]["description"] == "更新后的描述"
            assert data["data"]["confidence_threshold"] == 0.8
            assert data["data"]["is_active"] == False
    
    def test_delete_intent(self, client, mock_dependencies):
        """测试删除意图"""
        # 准备测试数据
        intent_id = 1
        
        # 模拟删除
        mock_intent = MagicMock()
        mock_intent.id = intent_id
        mock_intent.intent_name = "book_flight"
        
        with patch('src.models.intent.Intent') as mock_intent_model:
            mock_intent_model.get_by_id.return_value = mock_intent
            
            # 发送请求
            response = client.delete(f"/api/v1/admin/intents/{intent_id}")
            
            # 验证响应
            assert response.status_code == 200
            data = response.json()
            assert data["code"] == 200
            assert "已删除" in data["message"]
    
    def test_get_conversations(self, client, mock_dependencies):
        """测试获取对话记录"""
        # 模拟对话记录
        mock_conversations = [
            {
                "id": 1,
                "session_id": "sess_123",
                "user_id": "user_456",
                "user_input": "我要订机票",
                "intent_name": "book_flight",
                "confidence": 0.9,
                "response": "好的，我帮您预订机票",
                "created_at": datetime.now().isoformat()
            },
            {
                "id": 2,
                "session_id": "sess_789",
                "user_id": "user_123",
                "user_input": "查看余额",
                "intent_name": "check_balance",
                "confidence": 0.85,
                "response": "您的余额是1000元",
                "created_at": datetime.now().isoformat()
            }
        ]
        
        with patch('src.models.conversation.Conversation') as mock_conv_model:
            mock_query = MagicMock()
            mock_query.order_by.return_value.limit.return_value.offset.return_value = mock_conversations
            mock_conv_model.select.return_value = mock_query
            
            # 发送请求
            response = client.get("/api/v1/admin/conversations")
            
            # 验证响应
            assert response.status_code == 200
            data = response.json()
            assert data["code"] == 200
            assert "data" in data
            assert len(data["data"]["conversations"]) == 2
            assert data["data"]["conversations"][0]["user_input"] == "我要订机票"
    
    def test_get_conversations_with_filters(self, client, mock_dependencies):
        """测试带过滤条件的对话记录获取"""
        # 查询参数
        params = {
            "user_id": "user_123",
            "intent_name": "book_flight",
            "start_date": "2024-01-01",
            "end_date": "2024-01-31",
            "page": 1,
            "size": 10
        }
        
        # 模拟过滤后的对话记录
        mock_conversations = [
            {
                "id": 1,
                "session_id": "sess_123",
                "user_id": "user_123",
                "user_input": "我要订机票",
                "intent_name": "book_flight",
                "confidence": 0.9,
                "response": "好的，我帮您预订机票",
                "created_at": "2024-01-15T10:00:00Z"
            }
        ]
        
        with patch('src.models.conversation.Conversation') as mock_conv_model:
            mock_query = MagicMock()
            mock_query.where.return_value.order_by.return_value.limit.return_value.offset.return_value = mock_conversations
            mock_conv_model.select.return_value = mock_query
            
            # 发送请求
            response = client.get("/api/v1/admin/conversations", params=params)
            
            # 验证响应
            assert response.status_code == 200
            data = response.json()
            assert data["code"] == 200
            assert "data" in data
            assert len(data["data"]["conversations"]) == 1
            assert data["data"]["conversations"][0]["user_id"] == "user_123"
    
    def test_get_user_sessions(self, client, mock_dependencies):
        """测试获取用户会话"""
        # 准备测试数据
        user_id = "user_123"
        
        # 模拟用户会话
        mock_sessions = [
            {
                "id": 1,
                "session_id": "sess_123",
                "user_id": user_id,
                "status": "active",
                "created_at": datetime.now().isoformat(),
                "last_activity": datetime.now().isoformat()
            },
            {
                "id": 2,
                "session_id": "sess_456",
                "user_id": user_id,
                "status": "inactive",
                "created_at": datetime.now().isoformat(),
                "last_activity": datetime.now().isoformat()
            }
        ]
        
        with patch('src.models.conversation.Session') as mock_session_model:
            mock_query = MagicMock()
            mock_query.where.return_value.order_by.return_value = mock_sessions
            mock_session_model.select.return_value = mock_query
            
            # 发送请求
            response = client.get(f"/api/v1/admin/users/{user_id}/sessions")
            
            # 验证响应
            assert response.status_code == 200
            data = response.json()
            assert data["code"] == 200
            assert "data" in data
            assert len(data["data"]["sessions"]) == 2
            assert data["data"]["sessions"][0]["session_id"] == "sess_123"
    
    def test_clear_cache(self, client, mock_dependencies):
        """测试清空缓存"""
        # 模拟缓存清理
        mock_dependencies["cache"].return_value.clear.return_value = True
        
        # 发送请求
        response = client.delete("/api/v1/admin/cache")
        
        # 验证响应
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 200
        assert "缓存已清空" in data["message"]
    
    def test_get_cache_stats(self, client, mock_dependencies):
        """测试获取缓存统计"""
        # 模拟缓存统计
        mock_stats = {
            "total_keys": 150,
            "hit_rate": 0.85,
            "miss_rate": 0.15,
            "memory_usage": "50MB",
            "connected_clients": 5
        }
        
        mock_dependencies["cache"].return_value.get_stats.return_value = mock_stats
        
        # 发送请求
        response = client.get("/api/v1/admin/cache/stats")
        
        # 验证响应
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 200
        assert "data" in data
        assert data["data"]["total_keys"] == 150
        assert data["data"]["hit_rate"] == 0.85
    
    def test_export_conversations(self, client, mock_dependencies):
        """测试导出对话记录"""
        # 准备测试数据
        export_params = {
            "format": "json",
            "start_date": "2024-01-01",
            "end_date": "2024-01-31"
        }
        
        # 模拟导出数据
        mock_export_data = [
            {
                "id": 1,
                "session_id": "sess_123",
                "user_input": "我要订机票",
                "response": "好的，我帮您预订机票",
                "created_at": "2024-01-15T10:00:00Z"
            }
        ]
        
        with patch('src.api.v1.admin.export_conversations', return_value=mock_export_data):
            # 发送请求
            response = client.get("/api/v1/admin/conversations/export", params=export_params)
            
            # 验证响应
            assert response.status_code == 200
            data = response.json()
            assert data["code"] == 200
            assert "data" in data
            assert len(data["data"]["conversations"]) == 1
    
    def test_admin_auth_required(self, client):
        """测试管理员权限验证"""
        # 不提供管理员权限
        with patch('src.api.v1.admin.require_admin_auth', side_effect=Exception("权限不足")):
            # 发送请求
            response = client.get("/api/v1/admin/stats")
            
            # 验证响应
            assert response.status_code == 403
    
    def test_get_system_health(self, client, mock_dependencies):
        """测试获取系统健康状态"""
        # 模拟健康状态
        mock_health = {
            "status": "healthy",
            "database": "connected",
            "cache": "connected",
            "nlu_engine": "ready",
            "uptime": "24h 30m",
            "memory_usage": "512MB",
            "cpu_usage": "15%"
        }
        
        with patch('src.api.v1.admin.get_system_health', return_value=mock_health):
            # 发送请求
            response = client.get("/api/v1/admin/health")
            
            # 验证响应
            assert response.status_code == 200
            data = response.json()
            assert data["code"] == 200
            assert "data" in data
            assert data["data"]["status"] == "healthy"
            assert data["data"]["database"] == "connected"
    
    def test_restart_service(self, client, mock_dependencies):
        """测试重启服务"""
        # 模拟重启操作
        with patch('src.api.v1.admin.restart_service', return_value=True):
            # 发送请求
            response = client.post("/api/v1/admin/restart")
            
            # 验证响应
            assert response.status_code == 200
            data = response.json()
            assert data["code"] == 200
            assert "重启" in data["message"]
    
    def test_backup_data(self, client, mock_dependencies):
        """测试数据备份"""
        # 准备测试数据
        backup_config = {
            "include_conversations": True,
            "include_intents": True,
            "include_users": False,
            "format": "json"
        }
        
        # 模拟备份结果
        mock_backup_result = {
            "backup_id": "backup_123",
            "file_path": "/backups/backup_123.json",
            "size": "10MB",
            "created_at": datetime.now().isoformat()
        }
        
        with patch('src.api.v1.admin.create_backup', return_value=mock_backup_result):
            # 发送请求
            response = client.post("/api/v1/admin/backup", json=backup_config)
            
            # 验证响应
            assert response.status_code == 200
            data = response.json()
            assert data["code"] == 200
            assert "data" in data
            assert data["data"]["backup_id"] == "backup_123"
            assert data["data"]["size"] == "10MB"