"""
歧义解决API接口单元测试
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient
from fastapi import FastAPI
import json
from datetime import datetime

from src.api.v1.ambiguity_resolution import router as ambiguity_router


@pytest.fixture
def app():
    """创建测试FastAPI应用"""
    app = FastAPI()
    app.include_router(ambiguity_router, prefix="/api/v1")
    return app


@pytest.fixture
def client(app):
    """创建测试客户端"""
    return TestClient(app)


@pytest.fixture
def mock_dependencies():
    """模拟依赖"""
    with patch('src.api.v1.ambiguity_resolution.get_current_user') as mock_user, \
         patch('src.api.v1.ambiguity_resolution.get_cache_service_dependency') as mock_cache, \
         patch('src.api.v1.ambiguity_resolution.get_conversation_service_dependency') as mock_conv:
        
        mock_user.return_value = {"user_id": "test_user", "is_admin": False}
        mock_cache.return_value = AsyncMock()
        mock_conv.return_value = AsyncMock()
        
        yield {
            "user": mock_user,
            "cache": mock_cache,
            "conversation": mock_conv
        }


class TestAmbiguityResolutionAPI:
    """歧义解决API测试类"""
    
    def test_resolve_ambiguity_with_choice(self, client, mock_dependencies):
        """测试通过选择解决歧义"""
        # 准备测试数据
        request_data = {
            "session_id": "sess_123",
            "user_input": "第一个",
            "ambiguity_id": "amb_456",
            "candidates": [
                {"intent": "book_flight", "confidence": 0.7, "description": "预订机票"},
                {"intent": "check_flight", "confidence": 0.6, "description": "查询机票"}
            ]
        }
        
        # 模拟选择解析结果
        mock_parse_result = {
            "selected_intent": "book_flight",
            "confidence": 0.9,
            "parse_success": True,
            "selection_method": "index"
        }
        
        with patch('src.api.v1.ambiguity_resolution.parse_user_choice', return_value=mock_parse_result):
            
            # 发送请求
            response = client.post("/api/v1/ambiguity/resolve", json=request_data)
            
            # 验证响应
            assert response.status_code == 200
            data = response.json()
            assert data["code"] == 200
            assert "data" in data
            assert data["data"]["resolved"] == True
            assert data["data"]["selected_intent"] == "book_flight"
            assert data["data"]["confidence"] == 0.9
            assert data["data"]["resolution_method"] == "user_choice"
    
    def test_resolve_ambiguity_with_clarification(self, client, mock_dependencies):
        """测试通过澄清解决歧义"""
        # 准备测试数据
        request_data = {
            "session_id": "sess_123",
            "user_input": "我想预订航班",
            "ambiguity_id": "amb_456",
            "candidates": [
                {"intent": "book_flight", "confidence": 0.7, "description": "预订机票"},
                {"intent": "book_hotel", "confidence": 0.6, "description": "预订酒店"}
            ]
        }
        
        # 模拟澄清解析结果
        mock_parse_result = {
            "selected_intent": "book_flight",
            "confidence": 0.85,
            "parse_success": True,
            "selection_method": "clarification"
        }
        
        with patch('src.api.v1.ambiguity_resolution.parse_user_choice', return_value=mock_parse_result):
            
            # 发送请求
            response = client.post("/api/v1/ambiguity/resolve", json=request_data)
            
            # 验证响应
            assert response.status_code == 200
            data = response.json()
            assert data["code"] == 200
            assert "data" in data
            assert data["data"]["resolved"] == True
            assert data["data"]["selected_intent"] == "book_flight"
            assert data["data"]["confidence"] == 0.85
    
    def test_resolve_ambiguity_failed_parsing(self, client, mock_dependencies):
        """测试歧义解决解析失败"""
        # 准备测试数据
        request_data = {
            "session_id": "sess_123",
            "user_input": "不清楚的回答",
            "ambiguity_id": "amb_456",
            "candidates": [
                {"intent": "book_flight", "confidence": 0.7},
                {"intent": "check_flight", "confidence": 0.6}
            ]
        }
        
        # 模拟解析失败
        mock_parse_result = {
            "selected_intent": None,
            "confidence": 0.0,
            "parse_success": False,
            "error_message": "无法理解用户选择"
        }
        
        with patch('src.api.v1.ambiguity_resolution.parse_user_choice', return_value=mock_parse_result):
            
            # 发送请求
            response = client.post("/api/v1/ambiguity/resolve", json=request_data)
            
            # 验证响应
            assert response.status_code == 200
            data = response.json()
            assert data["code"] == 200
            assert "data" in data
            assert data["data"]["resolved"] == False
            assert data["data"]["error_message"] == "无法理解用户选择"
            assert "clarification_question" in data["data"]
    
    def test_generate_clarification_question(self, client, mock_dependencies):
        """测试生成澄清问题"""
        # 准备测试数据
        request_data = {
            "session_id": "sess_123",
            "user_input": "我想处理机票",
            "candidates": [
                {"intent": "book_flight", "confidence": 0.7, "description": "预订机票"},
                {"intent": "check_flight", "confidence": 0.6, "description": "查询机票"},
                {"intent": "cancel_flight", "confidence": 0.5, "description": "取消机票"}
            ]
        }
        
        # 模拟澄清问题生成
        mock_clarification = {
            "question": "请问您是要：\n1. 预订机票\n2. 查询机票\n3. 取消机票",
            "question_type": "multiple_choice",
            "options": [
                {"index": 1, "intent": "book_flight", "description": "预订机票"},
                {"index": 2, "intent": "check_flight", "description": "查询机票"},
                {"index": 3, "intent": "cancel_flight", "description": "取消机票"}
            ]
        }
        
        with patch('src.api.v1.ambiguity_resolution.generate_clarification_question', 
                  return_value=mock_clarification):
            
            # 发送请求
            response = client.post("/api/v1/ambiguity/clarify", json=request_data)
            
            # 验证响应
            assert response.status_code == 200
            data = response.json()
            assert data["code"] == 200
            assert "data" in data
            assert data["data"]["question"] == mock_clarification["question"]
            assert data["data"]["question_type"] == "multiple_choice"
            assert len(data["data"]["options"]) == 3
    
    def test_get_ambiguity_history(self, client, mock_dependencies):
        """测试获取歧义历史"""
        # 准备测试数据
        session_id = "sess_123"
        
        # 模拟歧义历史
        mock_history = [
            {
                "id": 1,
                "session_id": session_id,
                "user_input": "我想处理机票",
                "candidates": [
                    {"intent": "book_flight", "confidence": 0.7},
                    {"intent": "check_flight", "confidence": 0.6}
                ],
                "resolved_intent": "book_flight",
                "resolution_method": "user_choice",
                "created_at": datetime.now().isoformat()
            },
            {
                "id": 2,
                "session_id": session_id,
                "user_input": "预订",
                "candidates": [
                    {"intent": "book_flight", "confidence": 0.6},
                    {"intent": "book_hotel", "confidence": 0.55}
                ],
                "resolved_intent": "book_flight",
                "resolution_method": "clarification",
                "created_at": datetime.now().isoformat()
            }
        ]
        
        with patch('src.models.conversation.IntentAmbiguity') as mock_ambiguity_model:
            mock_query = MagicMock()
            mock_query.where.return_value.order_by.return_value.limit.return_value = mock_history
            mock_ambiguity_model.select.return_value = mock_query
            
            # 发送请求
            response = client.get(f"/api/v1/ambiguity/history/{session_id}")
            
            # 验证响应
            assert response.status_code == 200
            data = response.json()
            assert data["code"] == 200
            assert "data" in data
            assert len(data["data"]["ambiguities"]) == 2
            assert data["data"]["ambiguities"][0]["resolved_intent"] == "book_flight"
    
    def test_get_ambiguity_stats(self, client, mock_dependencies):
        """测试获取歧义统计"""
        # 准备测试数据
        mock_stats = {
            "total_ambiguities": 100,
            "resolved_count": 85,
            "unresolved_count": 15,
            "resolution_rate": 0.85,
            "resolution_methods": {
                "user_choice": 60,
                "clarification": 25,
                "auto_resolution": 0
            },
            "top_ambiguous_intents": [
                {"intent_pair": "book_flight,check_flight", "count": 25},
                {"intent_pair": "book_hotel,check_hotel", "count": 15}
            ]
        }
        
        with patch('src.api.v1.ambiguity_resolution.get_ambiguity_stats', return_value=mock_stats):
            
            # 发送请求
            response = client.get("/api/v1/ambiguity/stats")
            
            # 验证响应
            assert response.status_code == 200
            data = response.json()
            assert data["code"] == 200
            assert "data" in data
            assert data["data"]["total_ambiguities"] == 100
            assert data["data"]["resolved_count"] == 85
            assert data["data"]["resolution_rate"] == 0.85
            assert len(data["data"]["top_ambiguous_intents"]) == 2
    
    def test_save_ambiguity_resolution(self, client, mock_dependencies):
        """测试保存歧义解决记录"""
        # 准备测试数据
        request_data = {
            "session_id": "sess_123",
            "user_input": "我想处理机票",
            "candidates": [
                {"intent": "book_flight", "confidence": 0.7},
                {"intent": "check_flight", "confidence": 0.6}
            ],
            "resolved_intent": "book_flight",
            "resolution_method": "user_choice",
            "confidence": 0.9
        }
        
        # 模拟保存结果
        mock_ambiguity = MagicMock()
        mock_ambiguity.id = 1
        mock_ambiguity.session_id = "sess_123"
        mock_ambiguity.resolved_intent = "book_flight"
        
        with patch('src.models.conversation.IntentAmbiguity') as mock_ambiguity_model:
            mock_ambiguity_model.create.return_value = mock_ambiguity
            
            # 发送请求
            response = client.post("/api/v1/ambiguity/save", json=request_data)
            
            # 验证响应
            assert response.status_code == 200
            data = response.json()
            assert data["code"] == 200
            assert "data" in data
            assert data["data"]["ambiguity_id"] == 1
            assert data["data"]["resolved_intent"] == "book_flight"
    
    def test_update_ambiguity_resolution(self, client, mock_dependencies):
        """测试更新歧义解决记录"""
        # 准备测试数据
        ambiguity_id = 1
        request_data = {
            "resolved_intent": "check_flight",
            "resolution_method": "clarification",
            "confidence": 0.88,
            "user_feedback": "用户确认为查询机票"
        }
        
        # 模拟更新结果
        mock_ambiguity = MagicMock()
        mock_ambiguity.id = ambiguity_id
        mock_ambiguity.resolved_intent = "check_flight"
        mock_ambiguity.resolution_method = "clarification"
        mock_ambiguity.confidence = 0.88
        
        with patch('src.models.conversation.IntentAmbiguity') as mock_ambiguity_model:
            mock_ambiguity_model.get_by_id.return_value = mock_ambiguity
            
            # 发送请求
            response = client.put(f"/api/v1/ambiguity/{ambiguity_id}", json=request_data)
            
            # 验证响应
            assert response.status_code == 200
            data = response.json()
            assert data["code"] == 200
            assert "data" in data
            assert data["data"]["resolved_intent"] == "check_flight"
            assert data["data"]["resolution_method"] == "clarification"
    
    def test_get_similar_ambiguities(self, client, mock_dependencies):
        """测试获取相似歧义"""
        # 准备测试数据
        request_data = {
            "user_input": "我想处理机票",
            "candidates": [
                {"intent": "book_flight", "confidence": 0.7},
                {"intent": "check_flight", "confidence": 0.6}
            ],
            "similarity_threshold": 0.8
        }
        
        # 模拟相似歧义
        mock_similar_ambiguities = [
            {
                "id": 5,
                "user_input": "我要处理航班",
                "candidates": [
                    {"intent": "book_flight", "confidence": 0.75},
                    {"intent": "check_flight", "confidence": 0.65}
                ],
                "resolved_intent": "book_flight",
                "similarity_score": 0.85
            },
            {
                "id": 8,
                "user_input": "处理机票事务",
                "candidates": [
                    {"intent": "book_flight", "confidence": 0.68},
                    {"intent": "check_flight", "confidence": 0.62}
                ],
                "resolved_intent": "check_flight",
                "similarity_score": 0.82
            }
        ]
        
        with patch('src.api.v1.ambiguity_resolution.find_similar_ambiguities', 
                  return_value=mock_similar_ambiguities):
            
            # 发送请求
            response = client.post("/api/v1/ambiguity/similar", json=request_data)
            
            # 验证响应
            assert response.status_code == 200
            data = response.json()
            assert data["code"] == 200
            assert "data" in data
            assert len(data["data"]["similar_ambiguities"]) == 2
            assert data["data"]["similar_ambiguities"][0]["similarity_score"] == 0.85
    
    def test_auto_resolve_ambiguity(self, client, mock_dependencies):
        """测试自动解决歧义"""
        # 准备测试数据
        request_data = {
            "session_id": "sess_123",
            "user_input": "我想订机票",
            "candidates": [
                {"intent": "book_flight", "confidence": 0.75},
                {"intent": "check_flight", "confidence": 0.65}
            ],
            "context": {
                "previous_intent": "greeting",
                "user_preferences": {"frequent_action": "book_flight"}
            }
        }
        
        # 模拟自动解决结果
        mock_auto_resolution = {
            "resolved": True,
            "selected_intent": "book_flight",
            "confidence": 0.85,
            "resolution_method": "context_based",
            "reasoning": "基于用户历史偏好和上下文选择预订机票"
        }
        
        with patch('src.api.v1.ambiguity_resolution.auto_resolve_ambiguity', 
                  return_value=mock_auto_resolution):
            
            # 发送请求
            response = client.post("/api/v1/ambiguity/auto-resolve", json=request_data)
            
            # 验证响应
            assert response.status_code == 200
            data = response.json()
            assert data["code"] == 200
            assert "data" in data
            assert data["data"]["resolved"] == True
            assert data["data"]["selected_intent"] == "book_flight"
            assert data["data"]["resolution_method"] == "context_based"
            assert data["data"]["confidence"] == 0.85
    
    def test_get_ambiguity_patterns(self, client, mock_dependencies):
        """测试获取歧义模式"""
        # 准备测试数据
        mock_patterns = {
            "common_patterns": [
                {
                    "pattern": "处理+机票",
                    "frequency": 25,
                    "common_resolutions": [
                        {"intent": "book_flight", "percentage": 60},
                        {"intent": "check_flight", "percentage": 40}
                    ]
                },
                {
                    "pattern": "预订+酒店",
                    "frequency": 15,
                    "common_resolutions": [
                        {"intent": "book_hotel", "percentage": 80},
                        {"intent": "check_hotel", "percentage": 20}
                    ]
                }
            ],
            "trending_patterns": [
                {
                    "pattern": "查看+余额",
                    "frequency": 10,
                    "growth_rate": 2.5
                }
            ]
        }
        
        with patch('src.api.v1.ambiguity_resolution.get_ambiguity_patterns', 
                  return_value=mock_patterns):
            
            # 发送请求
            response = client.get("/api/v1/ambiguity/patterns")
            
            # 验证响应
            assert response.status_code == 200
            data = response.json()
            assert data["code"] == 200
            assert "data" in data
            assert len(data["data"]["common_patterns"]) == 2
            assert data["data"]["common_patterns"][0]["pattern"] == "处理+机票"
            assert data["data"]["common_patterns"][0]["frequency"] == 25
    
    def test_batch_resolve_ambiguities(self, client, mock_dependencies):
        """测试批量解决歧义"""
        # 准备测试数据
        request_data = {
            "resolutions": [
                {
                    "ambiguity_id": 1,
                    "resolved_intent": "book_flight",
                    "resolution_method": "user_choice"
                },
                {
                    "ambiguity_id": 2,
                    "resolved_intent": "check_balance",
                    "resolution_method": "clarification"
                }
            ]
        }
        
        # 模拟批量解决结果
        mock_batch_result = {
            "resolved_count": 2,
            "failed_count": 0,
            "results": [
                {"ambiguity_id": 1, "success": True},
                {"ambiguity_id": 2, "success": True}
            ]
        }
        
        with patch('src.api.v1.ambiguity_resolution.batch_resolve_ambiguities', 
                  return_value=mock_batch_result):
            
            # 发送请求
            response = client.post("/api/v1/ambiguity/batch-resolve", json=request_data)
            
            # 验证响应
            assert response.status_code == 200
            data = response.json()
            assert data["code"] == 200
            assert "data" in data
            assert data["data"]["resolved_count"] == 2
            assert data["data"]["failed_count"] == 0
            assert len(data["data"]["results"]) == 2
    
    def test_error_handling(self, client, mock_dependencies):
        """测试错误处理"""
        # 准备测试数据
        request_data = {
            "session_id": "sess_123",
            "user_input": "测试输入",
            "candidates": []
        }
        
        # 模拟服务错误
        with patch('src.api.v1.ambiguity_resolution.parse_user_choice', 
                  side_effect=Exception("解析服务不可用")):
            
            # 发送请求
            response = client.post("/api/v1/ambiguity/resolve", json=request_data)
            
            # 验证响应
            assert response.status_code == 500
            data = response.json()
            assert data["code"] == 500
            assert "解析服务不可用" in data["detail"]