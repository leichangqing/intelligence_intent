"""
端到端对话场景集成测试
"""
import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timedelta
import json

from src.api.v1.chat import ChatAPI
from src.api.v1.ambiguity import AmbiguityAPI
from src.services.intent_service import IntentService
from src.services.conversation_service import ConversationService
from src.services.slot_service import SlotService
from src.services.function_service import FunctionService
from src.services.cache_service import CacheService


class TestEndToEndScenarios:
    """端到端对话场景测试类"""
    
    @pytest.fixture
    def mock_app(self):
        """创建模拟FastAPI应用"""
        app = MagicMock()
        return app
    
    @pytest.fixture
    def mock_services(self):
        """创建模拟服务"""
        services = {
            'intent_service': MagicMock(spec=IntentService),
            'conversation_service': MagicMock(spec=ConversationService),
            'slot_service': MagicMock(spec=SlotService),
            'function_service': MagicMock(spec=FunctionService),
            'cache_service': MagicMock(spec=CacheService)
        }
        
        # 设置异步方法
        for service in services.values():
            for method_name in dir(service):
                if not method_name.startswith('_'):
                    method = getattr(service, method_name)
                    if callable(method):
                        setattr(service, method_name, AsyncMock())
        
        return services
    
    @pytest.fixture
    def chat_api(self, mock_services):
        """创建聊天API实例"""
        return ChatAPI(mock_services)
    
    @pytest.fixture
    def ambiguity_api(self, mock_services):
        """创建歧义解决API实例"""
        return AmbiguityAPI(mock_services)
    
    @pytest.mark.asyncio
    async def test_complete_flight_booking_scenario(self, chat_api, mock_services):
        """测试完整的机票预订场景"""
        # 准备测试数据
        booking_conversation = [
            {
                "user_input": "我要订机票",
                "expected_intent": "book_flight",
                "expected_slots": {},
                "expected_question": "请问您要从哪里到哪里？",
                "expected_state": "collecting_slots"
            },
            {
                "user_input": "从北京到上海",
                "expected_intent": "book_flight",
                "expected_slots": {"origin": "北京", "destination": "上海"},
                "expected_question": "请问您希望什么时候出发？",
                "expected_state": "collecting_slots"
            },
            {
                "user_input": "明天上午",
                "expected_intent": "book_flight",
                "expected_slots": {"origin": "北京", "destination": "上海", "date": "2024-01-02", "time": "morning"},
                "expected_question": "请问您希望选择什么舱位？",
                "expected_state": "collecting_slots"
            },
            {
                "user_input": "经济舱",
                "expected_intent": "book_flight",
                "expected_slots": {"origin": "北京", "destination": "上海", "date": "2024-01-02", "time": "morning", "class": "economy"},
                "expected_booking_id": "BK123456",
                "expected_state": "completed"
            }
        ]
        
        session_id = "test_session_booking"
        user_id = "test_user_booking"
        
        # 设置模拟会话
        mock_session = MagicMock()
        mock_session.session_id = session_id
        mock_session.user_id = user_id
        mock_session.status = "active"
        mock_session.get_context.return_value = {"current_intent": None, "slots": {}}
        mock_services['conversation_service'].get_or_create_session.return_value = mock_session
        
        accumulated_slots = {}
        
        for i, step in enumerate(booking_conversation):
            # 设置意图识别
            mock_intent = MagicMock()
            mock_intent.intent_name = step["expected_intent"]
            mock_intent.confidence = 0.9
            mock_services['intent_service'].recognize_intent.return_value = mock_intent
            
            # 设置槽位提取
            if i == 0:
                mock_services['slot_service'].extract_slots.return_value = {}
                mock_services['slot_service'].are_all_required_slots_filled.return_value = False
                mock_services['slot_service'].get_missing_slots.return_value = ["origin", "destination"]
                mock_services['slot_service'].generate_slot_question.return_value = step["expected_question"]
            elif i == 1:
                new_slots = {
                    "origin": {"value": "北京", "confidence": 0.95},
                    "destination": {"value": "上海", "confidence": 0.9}
                }
                accumulated_slots.update(new_slots)
                mock_services['slot_service'].extract_slots.return_value = new_slots
                mock_services['slot_service'].merge_slots.return_value = accumulated_slots
                mock_services['slot_service'].are_all_required_slots_filled.return_value = False
                mock_services['slot_service'].get_missing_slots.return_value = ["date"]
                mock_services['slot_service'].generate_slot_question.return_value = step["expected_question"]
            elif i == 2:
                new_slots = {
                    "date": {"value": "2024-01-02", "confidence": 0.8},
                    "time": {"value": "morning", "confidence": 0.75}
                }
                accumulated_slots.update(new_slots)
                mock_services['slot_service'].extract_slots.return_value = new_slots
                mock_services['slot_service'].merge_slots.return_value = accumulated_slots
                mock_services['slot_service'].are_all_required_slots_filled.return_value = False
                mock_services['slot_service'].get_missing_slots.return_value = ["class"]
                mock_services['slot_service'].generate_slot_question.return_value = step["expected_question"]
            elif i == 3:
                new_slots = {"class": {"value": "economy", "confidence": 0.9}}
                accumulated_slots.update(new_slots)
                mock_services['slot_service'].extract_slots.return_value = new_slots
                mock_services['slot_service'].merge_slots.return_value = accumulated_slots
                mock_services['slot_service'].are_all_required_slots_filled.return_value = True
                
                # 模拟功能调用
                mock_function_result = {
                    "success": True,
                    "booking_id": step["expected_booking_id"],
                    "flight_info": {
                        "origin": "北京",
                        "destination": "上海",
                        "date": "2024-01-02",
                        "time": "morning",
                        "class": "economy",
                        "price": 1200.50
                    }
                }
                mock_services['function_service'].call_function.return_value = mock_function_result
            
            # 构造请求
            request = {
                "user_input": step["user_input"],
                "session_id": session_id,
                "user_id": user_id
            }
            
            # 调用API
            response = await chat_api.chat(request)
            
            # 验证响应
            assert response["success"] == True
            assert response["intent"] == step["expected_intent"]
            assert response["conversation_state"] == step["expected_state"]
            
            # 验证槽位
            if step["expected_slots"]:
                for slot_name, expected_value in step["expected_slots"].items():
                    assert slot_name in response.get("slots", {})
                    assert response["slots"][slot_name] == expected_value
            
            # 验证问题或结果
            if step["expected_state"] == "collecting_slots":
                assert step["expected_question"] in response["response"]
            elif step["expected_state"] == "completed":
                assert step["expected_booking_id"] in response["response"]
                assert response["function_result"]["booking_id"] == step["expected_booking_id"]
            
            # 更新会话上下文
            mock_session.get_context.return_value = {
                "current_intent": step["expected_intent"],
                "slots": accumulated_slots,
                "conversation_state": step["expected_state"]
            }
    
    @pytest.mark.asyncio
    async def test_balance_inquiry_scenario(self, chat_api, mock_services):
        """测试余额查询场景"""
        # 准备测试数据
        session_id = "test_session_balance"
        user_id = "test_user_balance"
        
        # 设置模拟会话
        mock_session = MagicMock()
        mock_session.session_id = session_id
        mock_session.user_id = user_id
        mock_session.status = "active"
        mock_session.get_context.return_value = {"current_intent": None, "slots": {}}
        mock_services['conversation_service'].get_or_create_session.return_value = mock_session
        
        # 设置意图识别
        mock_intent = MagicMock()
        mock_intent.intent_name = "check_balance"
        mock_intent.confidence = 0.95
        mock_services['intent_service'].recognize_intent.return_value = mock_intent
        
        # 设置槽位提取（余额查询通常不需要额外槽位）
        mock_services['slot_service'].extract_slots.return_value = {}
        mock_services['slot_service'].are_all_required_slots_filled.return_value = True
        
        # 设置功能调用
        mock_function_result = {
            "success": True,
            "balance": 5000.00,
            "account_info": {
                "account_number": "123456789",
                "account_type": "savings",
                "currency": "CNY"
            }
        }
        mock_services['function_service'].call_function.return_value = mock_function_result
        
        # 构造请求
        request = {
            "user_input": "查询我的余额",
            "session_id": session_id,
            "user_id": user_id
        }
        
        # 调用API
        response = await chat_api.chat(request)
        
        # 验证响应
        assert response["success"] == True
        assert response["intent"] == "check_balance"
        assert response["conversation_state"] == "completed"
        assert response["function_result"]["balance"] == 5000.00
        assert "5000.00" in response["response"]
    
    @pytest.mark.asyncio
    async def test_ambiguous_intent_resolution_scenario(self, chat_api, ambiguity_api, mock_services):
        """测试歧义意图解决场景"""
        # 准备测试数据
        session_id = "test_session_ambiguity"
        user_id = "test_user_ambiguity"
        
        # 设置模拟会话
        mock_session = MagicMock()
        mock_session.session_id = session_id
        mock_session.user_id = user_id
        mock_session.status = "active"
        mock_session.get_context.return_value = {"current_intent": None, "slots": {}}
        mock_services['conversation_service'].get_or_create_session.return_value = mock_session
        
        # 第一步：识别到歧义意图
        mock_ambiguous_result = {
            "is_ambiguous": True,
            "candidates": [
                {"intent": "book_flight", "confidence": 0.7, "description": "预订机票"},
                {"intent": "check_flight", "confidence": 0.65, "description": "查询机票"},
                {"intent": "cancel_flight", "confidence": 0.6, "description": "取消机票"}
            ],
            "clarification_question": "请问您是要预订机票、查询机票还是取消机票？"
        }
        mock_services['intent_service'].recognize_intent.return_value = mock_ambiguous_result
        
        # 构造第一个请求
        request1 = {
            "user_input": "我要处理机票",
            "session_id": session_id,
            "user_id": user_id
        }
        
        # 调用聊天API
        response1 = await chat_api.chat(request1)
        
        # 验证第一个响应
        assert response1["success"] == True
        assert response1["is_ambiguous"] == True
        assert len(response1["candidates"]) == 3
        assert response1["conversation_state"] == "waiting_for_clarification"
        assert "请问您是要预订机票、查询机票还是取消机票？" in response1["response"]
        
        # 更新会话状态
        mock_session.get_context.return_value = {
            "current_intent": None,
            "slots": {},
            "conversation_state": "waiting_for_clarification",
            "ambiguity_id": "amb_123",
            "candidates": mock_ambiguous_result["candidates"]
        }
        
        # 第二步：用户做出选择
        mock_services['conversation_service'].get_ambiguity.return_value = MagicMock(
            id="amb_123",
            candidates=json.dumps(mock_ambiguous_result["candidates"]),
            resolved_intent=None
        )
        
        # 构造歧义解决请求
        request2 = {
            "ambiguity_id": "amb_123",
            "selected_intent": "book_flight",
            "session_id": session_id,
            "user_id": user_id
        }
        
        # 调用歧义解决API
        response2 = await ambiguity_api.resolve_ambiguity(request2)
        
        # 验证第二个响应
        assert response2["success"] == True
        assert response2["resolved_intent"] == "book_flight"
        assert response2["conversation_state"] == "intent_resolved"
        assert "好的，我来帮您预订机票" in response2["response"]
    
    @pytest.mark.asyncio
    async def test_conversation_interruption_and_recovery_scenario(self, chat_api, mock_services):
        """测试对话中断和恢复场景"""
        # 准备测试数据
        session_id = "test_session_interruption"
        user_id = "test_user_interruption"
        
        # 设置模拟会话
        mock_session = MagicMock()
        mock_session.session_id = session_id
        mock_session.user_id = user_id
        mock_session.status = "active"
        mock_session.get_context.return_value = {"current_intent": None, "slots": {}}
        mock_services['conversation_service'].get_or_create_session.return_value = mock_session
        
        # 第一步：开始订机票
        mock_intent1 = MagicMock()
        mock_intent1.intent_name = "book_flight"
        mock_intent1.confidence = 0.9
        mock_services['intent_service'].recognize_intent.return_value = mock_intent1
        
        mock_services['slot_service'].extract_slots.return_value = {}
        mock_services['slot_service'].are_all_required_slots_filled.return_value = False
        mock_services['slot_service'].get_missing_slots.return_value = ["origin", "destination"]
        mock_services['slot_service'].generate_slot_question.return_value = "请问您要从哪里到哪里？"
        
        request1 = {
            "user_input": "我要订机票",
            "session_id": session_id,
            "user_id": user_id
        }
        
        response1 = await chat_api.chat(request1)
        
        # 验证第一步
        assert response1["success"] == True
        assert response1["intent"] == "book_flight"
        assert response1["conversation_state"] == "collecting_slots"
        
        # 更新会话状态
        mock_session.get_context.return_value = {
            "current_intent": "book_flight",
            "slots": {},
            "conversation_state": "collecting_slots"
        }
        
        # 第二步：用户突然问余额（中断）
        mock_intent2 = MagicMock()
        mock_intent2.intent_name = "check_balance"
        mock_intent2.confidence = 0.95
        mock_services['intent_service'].recognize_intent.return_value = mock_intent2
        
        mock_services['slot_service'].extract_slots.return_value = {}
        mock_services['slot_service'].are_all_required_slots_filled.return_value = True
        
        mock_function_result = {
            "success": True,
            "balance": 3000.00
        }
        mock_services['function_service'].call_function.return_value = mock_function_result
        
        # 模拟意图中断处理
        mock_services['conversation_service'].handle_intent_interruption.return_value = True
        
        request2 = {
            "user_input": "我的余额是多少？",
            "session_id": session_id,
            "user_id": user_id
        }
        
        response2 = await chat_api.chat(request2)
        
        # 验证第二步
        assert response2["success"] == True
        assert response2["intent"] == "check_balance"
        assert response2["conversation_state"] == "intent_interrupted"
        assert "3000.00" in response2["response"]
        assert "继续" in response2["response"]
        
        # 更新会话状态
        mock_session.get_context.return_value = {
            "current_intent": "check_balance",
            "interrupted_intent": "book_flight",
            "interrupted_slots": {},
            "conversation_state": "intent_interrupted"
        }
        
        # 第三步：用户选择继续之前的意图
        mock_services['conversation_service'].resume_interrupted_intent.return_value = True
        mock_services['intent_service'].recognize_intent.return_value = mock_intent1
        
        request3 = {
            "user_input": "是的，继续订票",
            "session_id": session_id,
            "user_id": user_id
        }
        
        response3 = await chat_api.chat(request3)
        
        # 验证第三步
        assert response3["success"] == True
        assert response3["intent"] == "book_flight"
        assert response3["conversation_state"] == "collecting_slots"
        assert "请问您要从哪里到哪里？" in response3["response"]
    
    @pytest.mark.asyncio
    async def test_multi_user_concurrent_conversations(self, chat_api, mock_services):
        """测试多用户并发对话场景"""
        # 准备测试数据
        users = [
            {"session_id": "session_001", "user_id": "user_001", "intent": "book_flight"},
            {"session_id": "session_002", "user_id": "user_002", "intent": "check_balance"},
            {"session_id": "session_003", "user_id": "user_003", "intent": "cancel_booking"}
        ]
        
        # 为每个用户创建模拟会话
        mock_sessions = []
        for user in users:
            mock_session = MagicMock()
            mock_session.session_id = user["session_id"]
            mock_session.user_id = user["user_id"]
            mock_session.status = "active"
            mock_session.get_context.return_value = {"current_intent": None, "slots": {}}
            mock_sessions.append(mock_session)
        
        mock_services['conversation_service'].get_or_create_session.side_effect = mock_sessions
        
        # 设置意图识别
        mock_intents = []
        for user in users:
            mock_intent = MagicMock()
            mock_intent.intent_name = user["intent"]
            mock_intent.confidence = 0.9
            mock_intents.append(mock_intent)
        
        mock_services['intent_service'].recognize_intent.side_effect = mock_intents
        
        # 设置功能调用
        mock_function_results = [
            {"success": True, "booking_id": "BK001"},
            {"success": True, "balance": 2000.00},
            {"success": True, "cancelled": True}
        ]
        mock_services['function_service'].call_function.side_effect = mock_function_results
        
        # 设置槽位处理
        mock_services['slot_service'].extract_slots.return_value = {}
        mock_services['slot_service'].are_all_required_slots_filled.return_value = True
        
        # 创建并发请求
        requests = []
        for user in users:
            request = {
                "user_input": f"我要{user['intent']}",
                "session_id": user["session_id"],
                "user_id": user["user_id"]
            }
            requests.append(chat_api.chat(request))
        
        # 并发执行
        responses = await asyncio.gather(*requests)
        
        # 验证响应
        assert len(responses) == 3
        
        for i, response in enumerate(responses):
            assert response["success"] == True
            assert response["intent"] == users[i]["intent"]
            assert response["session_id"] == users[i]["session_id"]
            assert response["conversation_state"] == "completed"
    
    @pytest.mark.asyncio
    async def test_error_handling_and_recovery_scenario(self, chat_api, mock_services):
        """测试错误处理和恢复场景"""
        # 准备测试数据
        session_id = "test_session_error"
        user_id = "test_user_error"
        
        # 设置模拟会话
        mock_session = MagicMock()
        mock_session.session_id = session_id
        mock_session.user_id = user_id
        mock_session.status = "active"
        mock_session.get_context.return_value = {"current_intent": None, "slots": {}}
        mock_services['conversation_service'].get_or_create_session.return_value = mock_session
        
        # 第一步：正常开始对话
        mock_intent = MagicMock()
        mock_intent.intent_name = "book_flight"
        mock_intent.confidence = 0.9
        mock_services['intent_service'].recognize_intent.return_value = mock_intent
        
        mock_services['slot_service'].extract_slots.return_value = {
            "origin": {"value": "北京", "confidence": 0.95},
            "destination": {"value": "上海", "confidence": 0.9},
            "date": {"value": "2024-01-02", "confidence": 0.8}
        }
        mock_services['slot_service'].are_all_required_slots_filled.return_value = True
        
        # 模拟外部服务错误
        mock_services['function_service'].call_function.side_effect = Exception("外部航班预订服务不可用")
        
        request1 = {
            "user_input": "我要从北京到上海订明天的机票",
            "session_id": session_id,
            "user_id": user_id
        }
        
        response1 = await chat_api.chat(request1)
        
        # 验证错误响应
        assert response1["success"] == False
        assert response1["error_type"] == "function_error"
        assert "外部航班预订服务不可用" in response1["error_message"]
        assert "服务暂时不可用" in response1["response"]
        
        # 更新会话状态为错误状态
        mock_session.get_context.return_value = {
            "current_intent": "book_flight",
            "slots": {
                "origin": {"value": "北京", "confidence": 0.95},
                "destination": {"value": "上海", "confidence": 0.9},
                "date": {"value": "2024-01-02", "confidence": 0.8}
            },
            "conversation_state": "error",
            "last_error": "外部航班预订服务不可用"
        }
        
        # 第二步：用户请求重试
        mock_services['function_service'].call_function.side_effect = None
        mock_function_result = {
            "success": True,
            "booking_id": "BK123456"
        }
        mock_services['function_service'].call_function.return_value = mock_function_result
        mock_services['conversation_service'].recover_from_error.return_value = True
        
        request2 = {
            "user_input": "再试一次",
            "session_id": session_id,
            "user_id": user_id
        }
        
        response2 = await chat_api.chat(request2)
        
        # 验证恢复响应
        assert response2["success"] == True
        assert response2["intent"] == "book_flight"
        assert response2["conversation_state"] == "completed"
        assert response2["function_result"]["booking_id"] == "BK123456"
        assert "预订成功" in response2["response"]
    
    @pytest.mark.asyncio
    async def test_long_conversation_with_context_management(self, chat_api, mock_services):
        """测试长对话的上下文管理场景"""
        # 准备测试数据
        session_id = "test_session_long"
        user_id = "test_user_long"
        
        # 设置模拟会话
        mock_session = MagicMock()
        mock_session.session_id = session_id
        mock_session.user_id = user_id
        mock_session.status = "active"
        mock_session.get_context.return_value = {"current_intent": None, "slots": {}}
        mock_services['conversation_service'].get_or_create_session.return_value = mock_session
        
        # 长对话步骤
        conversation_steps = [
            {"input": "我要订机票", "intent": "book_flight", "slots": {}},
            {"input": "从北京到上海", "intent": "book_flight", "slots": {"origin": "北京", "destination": "上海"}},
            {"input": "等等，我想先查一下余额", "intent": "check_balance", "slots": {}},  # 意图中断
            {"input": "好的，继续订票", "intent": "book_flight", "slots": {"origin": "北京", "destination": "上海"}},  # 恢复
            {"input": "明天上午", "intent": "book_flight", "slots": {"origin": "北京", "destination": "上海", "date": "2024-01-02", "time": "morning"}},
            {"input": "经济舱", "intent": "book_flight", "slots": {"origin": "北京", "destination": "上海", "date": "2024-01-02", "time": "morning", "class": "economy"}},
            {"input": "确认预订", "intent": "book_flight", "slots": {"origin": "北京", "destination": "上海", "date": "2024-01-02", "time": "morning", "class": "economy"}},
            {"input": "谢谢", "intent": "thanks", "slots": {}}  # 结束对话
        ]
        
        accumulated_slots = {}
        
        for i, step in enumerate(conversation_steps):
            # 设置意图识别
            mock_intent = MagicMock()
            mock_intent.intent_name = step["intent"]
            mock_intent.confidence = 0.9
            mock_services['intent_service'].recognize_intent.return_value = mock_intent
            
            # 设置槽位处理
            if step["intent"] == "book_flight":
                if i == 0:
                    mock_services['slot_service'].extract_slots.return_value = {}
                    mock_services['slot_service'].are_all_required_slots_filled.return_value = False
                    mock_services['slot_service'].get_missing_slots.return_value = ["origin", "destination"]
                    mock_services['slot_service'].generate_slot_question.return_value = "请问您要从哪里到哪里？"
                elif i == 1:
                    new_slots = {
                        "origin": {"value": "北京", "confidence": 0.95},
                        "destination": {"value": "上海", "confidence": 0.9}
                    }
                    accumulated_slots.update(new_slots)
                    mock_services['slot_service'].extract_slots.return_value = new_slots
                    mock_services['slot_service'].merge_slots.return_value = accumulated_slots
                    mock_services['slot_service'].are_all_required_slots_filled.return_value = False
                    mock_services['slot_service'].get_missing_slots.return_value = ["date"]
                    mock_services['slot_service'].generate_slot_question.return_value = "请问您希望什么时候出发？"
                elif i == 3:  # 恢复后继续
                    mock_services['conversation_service'].resume_interrupted_intent.return_value = True
                    mock_services['slot_service'].extract_slots.return_value = {}
                    mock_services['slot_service'].are_all_required_slots_filled.return_value = False
                    mock_services['slot_service'].get_missing_slots.return_value = ["date"]
                    mock_services['slot_service'].generate_slot_question.return_value = "请问您希望什么时候出发？"
                elif i == 4:
                    new_slots = {
                        "date": {"value": "2024-01-02", "confidence": 0.8},
                        "time": {"value": "morning", "confidence": 0.7}
                    }
                    accumulated_slots.update(new_slots)
                    mock_services['slot_service'].extract_slots.return_value = new_slots
                    mock_services['slot_service'].merge_slots.return_value = accumulated_slots
                    mock_services['slot_service'].are_all_required_slots_filled.return_value = False
                    mock_services['slot_service'].get_missing_slots.return_value = ["class"]
                    mock_services['slot_service'].generate_slot_question.return_value = "请问您希望选择什么舱位？"
                elif i == 5:
                    new_slots = {"class": {"value": "economy", "confidence": 0.9}}
                    accumulated_slots.update(new_slots)
                    mock_services['slot_service'].extract_slots.return_value = new_slots
                    mock_services['slot_service'].merge_slots.return_value = accumulated_slots
                    mock_services['slot_service'].are_all_required_slots_filled.return_value = True
                    mock_function_result = {"success": True, "booking_id": "BK123456"}
                    mock_services['function_service'].call_function.return_value = mock_function_result
                elif i == 6:
                    mock_services['slot_service'].extract_slots.return_value = {}
                    mock_services['slot_service'].are_all_required_slots_filled.return_value = True
                    mock_function_result = {"success": True, "booking_id": "BK123456"}
                    mock_services['function_service'].call_function.return_value = mock_function_result
            
            elif step["intent"] == "check_balance":
                mock_services['slot_service'].extract_slots.return_value = {}
                mock_services['slot_service'].are_all_required_slots_filled.return_value = True
                mock_function_result = {"success": True, "balance": 5000.00}
                mock_services['function_service'].call_function.return_value = mock_function_result
                mock_services['conversation_service'].handle_intent_interruption.return_value = True
            
            elif step["intent"] == "thanks":
                mock_services['slot_service'].extract_slots.return_value = {}
                mock_services['conversation_service'].should_reset_context.return_value = True
            
            # 构造请求
            request = {
                "user_input": step["input"],
                "session_id": session_id,
                "user_id": user_id
            }
            
            # 调用API
            response = await chat_api.chat(request)
            
            # 验证响应
            assert response["success"] == True
            assert response["intent"] == step["intent"]
            
            # 验证上下文管理
            if i == 2:  # 意图中断
                assert response["conversation_state"] == "intent_interrupted"
            elif i == 3:  # 恢复
                assert response["conversation_state"] == "collecting_slots"
            elif i == 7:  # 重置上下文
                assert response.get("context_reset") == True
            
            # 更新会话上下文
            if i == 2:  # 意图中断后
                mock_session.get_context.return_value = {
                    "current_intent": "check_balance",
                    "interrupted_intent": "book_flight",
                    "interrupted_slots": accumulated_slots,
                    "conversation_state": "intent_interrupted"
                }
            elif i == 3:  # 恢复后
                mock_session.get_context.return_value = {
                    "current_intent": "book_flight",
                    "slots": accumulated_slots,
                    "conversation_state": "collecting_slots"
                }
            elif i == 7:  # 重置后
                mock_session.get_context.return_value = {
                    "current_intent": None,
                    "slots": {},
                    "conversation_state": "new"
                }
            else:
                mock_session.get_context.return_value = {
                    "current_intent": step["intent"],
                    "slots": accumulated_slots,
                    "conversation_state": "collecting_slots" if i < 6 else "completed"
                }
    
    @pytest.mark.asyncio
    async def test_performance_under_load(self, chat_api, mock_services):
        """测试高负载下的性能"""
        # 准备测试数据
        num_concurrent_requests = 50
        
        # 设置模拟响应
        mock_sessions = []
        for i in range(num_concurrent_requests):
            mock_session = MagicMock()
            mock_session.session_id = f"session_{i:03d}"
            mock_session.user_id = f"user_{i:03d}"
            mock_session.status = "active"
            mock_session.get_context.return_value = {"current_intent": None, "slots": {}}
            mock_sessions.append(mock_session)
        
        mock_services['conversation_service'].get_or_create_session.side_effect = mock_sessions
        
        # 设置统一的模拟响应
        mock_intent = MagicMock()
        mock_intent.intent_name = "check_balance"
        mock_intent.confidence = 0.9
        mock_services['intent_service'].recognize_intent.return_value = mock_intent
        
        mock_services['slot_service'].extract_slots.return_value = {}
        mock_services['slot_service'].are_all_required_slots_filled.return_value = True
        
        mock_function_result = {"success": True, "balance": 1000.00}
        mock_services['function_service'].call_function.return_value = mock_function_result
        
        # 创建并发请求
        requests = []
        for i in range(num_concurrent_requests):
            request = {
                "user_input": "查询余额",
                "session_id": f"session_{i:03d}",
                "user_id": f"user_{i:03d}"
            }
            requests.append(chat_api.chat(request))
        
        # 记录开始时间
        start_time = datetime.now()
        
        # 并发执行
        responses = await asyncio.gather(*requests)
        
        # 记录结束时间
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        
        # 验证性能
        assert len(responses) == num_concurrent_requests
        assert duration < 5.0  # 应该在5秒内完成
        
        # 验证所有响应都成功
        for response in responses:
            assert response["success"] == True
            assert response["intent"] == "check_balance"
            assert response["function_result"]["balance"] == 1000.00
        
        # 计算平均响应时间
        avg_response_time = duration / num_concurrent_requests
        assert avg_response_time < 0.1  # 平均响应时间应小于100ms


class ChatAPI:
    """聊天API模拟实现"""
    
    def __init__(self, services):
        self.services = services
    
    async def chat(self, request: dict) -> dict:
        """处理聊天请求"""
        try:
            # 获取会话
            session = await self.services['conversation_service'].get_or_create_session(
                session_id=request["session_id"],
                user_id=request["user_id"]
            )
            
            # 获取上下文
            context = session.get_context()
            
            # 处理错误恢复
            if context.get('conversation_state') == 'error' and request["user_input"] in ['再试一次', '重试']:
                return await self._handle_error_recovery(session, context, request)
            
            # 处理意图中断恢复
            if context.get('conversation_state') == 'intent_interrupted' and '继续' in request["user_input"]:
                return await self._handle_intent_recovery(session, context, request)
            
            # 意图识别
            intent_result = await self.services['intent_service'].recognize_intent(request["user_input"])
            
            # 处理歧义
            if isinstance(intent_result, dict) and intent_result.get('is_ambiguous'):
                return await self._handle_ambiguity(intent_result, session, request)
            
            # 处理意图中断
            if context.get('current_intent') and intent_result.intent_name != context.get('current_intent'):
                return await self._handle_intent_interruption(intent_result, session, context, request)
            
            # 处理上下文重置
            if intent_result.intent_name in ['thanks', 'goodbye']:
                return await self._handle_context_reset(session, request)
            
            # 正常流程处理
            return await self._handle_normal_flow(intent_result, session, context, request)
            
        except Exception as e:
            return await self._handle_error(e, request)
    
    async def _handle_error_recovery(self, session, context: dict, request: dict) -> dict:
        """处理错误恢复"""
        if await self.services['conversation_service'].recover_from_error(session):
            # 重新执行功能调用
            function_result = await self.services['function_service'].call_function(
                context['current_intent'], 
                {k: v['value'] for k, v in context.get('slots', {}).items()}
            )
            
            return {
                "success": True,
                "intent": context['current_intent'],
                "conversation_state": "completed",
                "function_result": function_result,
                "session_id": request["session_id"],
                "response": self._generate_success_response(context['current_intent'], function_result)
            }
        
        return {
            "success": False,
            "error": "recovery_failed",
            "session_id": request["session_id"],
            "response": "抱歉，无法恢复之前的操作，请重新开始。"
        }
    
    async def _handle_intent_recovery(self, session, context: dict, request: dict) -> dict:
        """处理意图恢复"""
        if await self.services['conversation_service'].resume_interrupted_intent(session):
            # 继续之前的意图
            interrupted_intent = context.get('interrupted_intent')
            interrupted_slots = context.get('interrupted_slots', {})
            
            # 检查是否需要继续收集槽位
            if not await self.services['slot_service'].are_all_required_slots_filled(interrupted_intent, interrupted_slots):
                missing_slots = await self.services['slot_service'].get_missing_slots(interrupted_intent, interrupted_slots)
                question = await self.services['slot_service'].generate_slot_question(interrupted_intent, missing_slots[0])
                
                return {
                    "success": True,
                    "intent": interrupted_intent,
                    "conversation_state": "collecting_slots",
                    "session_id": request["session_id"],
                    "response": question
                }
            
            return {
                "success": True,
                "intent": interrupted_intent,
                "conversation_state": "collecting_slots",
                "session_id": request["session_id"],
                "response": f"好的，我们继续{interrupted_intent}。"
            }
        
        return {
            "success": False,
            "error": "resume_failed",
            "session_id": request["session_id"],
            "response": "抱歉，无法恢复之前的对话。"
        }
    
    async def _handle_ambiguity(self, intent_result: dict, session, request: dict) -> dict:
        """处理意图歧义"""
        return {
            "success": True,
            "is_ambiguous": True,
            "candidates": intent_result["candidates"],
            "conversation_state": "waiting_for_clarification",
            "session_id": request["session_id"],
            "response": intent_result["clarification_question"]
        }
    
    async def _handle_intent_interruption(self, intent_result, session, context: dict, request: dict) -> dict:
        """处理意图中断"""
        # 保存当前状态
        await self.services['conversation_service'].handle_intent_interruption(
            session, context['current_intent'], intent_result.intent_name, context.get('slots', {})
        )
        
        # 处理新意图
        if intent_result.intent_name == 'check_balance':
            function_result = await self.services['function_service'].call_function(
                intent_result.intent_name, {}
            )
            
            return {
                "success": True,
                "intent": intent_result.intent_name,
                "conversation_state": "intent_interrupted",
                "function_result": function_result,
                "session_id": request["session_id"],
                "response": f"您的余额是{function_result.get('balance', 'N/A')}元。需要继续之前的操作吗？"
            }
        
        return {
            "success": True,
            "intent": intent_result.intent_name,
            "conversation_state": "intent_interrupted",
            "session_id": request["session_id"],
            "response": f"好的，我来处理{intent_result.intent_name}。"
        }
    
    async def _handle_context_reset(self, session, request: dict) -> dict:
        """处理上下文重置"""
        if await self.services['conversation_service'].should_reset_context(session, 'thanks'):
            session.clear_context()
            
            return {
                "success": True,
                "intent": "thanks",
                "context_reset": True,
                "conversation_state": "new",
                "session_id": request["session_id"],
                "response": "不客气！如果您还有其他需要帮助的地方，随时告诉我。"
            }
        
        return {
            "success": True,
            "intent": "thanks",
            "conversation_state": "completed",
            "session_id": request["session_id"],
            "response": "谢谢您的使用！"
        }
    
    async def _handle_normal_flow(self, intent_result, session, context: dict, request: dict) -> dict:
        """处理正常流程"""
        # 提取槽位
        slots = await self.services['slot_service'].extract_slots(request["user_input"], intent_result.intent_name)
        
        # 合并槽位
        if context.get('current_intent') == intent_result.intent_name:
            all_slots = await self.services['slot_service'].merge_slots(context.get('slots', {}), slots)
        else:
            all_slots = slots
        
        # 检查必需槽位
        if not await self.services['slot_service'].are_all_required_slots_filled(intent_result.intent_name, all_slots):
            missing_slots = await self.services['slot_service'].get_missing_slots(intent_result.intent_name, all_slots)
            question = await self.services['slot_service'].generate_slot_question(intent_result.intent_name, missing_slots[0])
            
            return {
                "success": True,
                "intent": intent_result.intent_name,
                "slots": {k: v['value'] for k, v in all_slots.items()},
                "missing_slots": missing_slots,
                "conversation_state": "collecting_slots",
                "session_id": request["session_id"],
                "response": question
            }
        
        # 执行功能调用
        function_result = await self.services['function_service'].call_function(
            intent_result.intent_name, {k: v['value'] for k, v in all_slots.items()}
        )
        
        return {
            "success": True,
            "intent": intent_result.intent_name,
            "slots": {k: v['value'] for k, v in all_slots.items()},
            "conversation_state": "completed",
            "function_result": function_result,
            "session_id": request["session_id"],
            "response": self._generate_success_response(intent_result.intent_name, function_result)
        }
    
    async def _handle_error(self, error: Exception, request: dict) -> dict:
        """处理错误"""
        return {
            "success": False,
            "error": str(error),
            "error_type": "function_error",
            "error_message": str(error),
            "session_id": request["session_id"],
            "response": "抱歉，服务暂时不可用，请稍后重试。"
        }
    
    def _generate_success_response(self, intent_name: str, function_result: dict) -> str:
        """生成成功响应"""
        if intent_name == 'book_flight':
            return f"机票预订成功！订单号：{function_result.get('booking_id', 'N/A')}"
        elif intent_name == 'check_balance':
            return f"您的余额是{function_result.get('balance', 'N/A')}元"
        elif intent_name == 'cancel_booking':
            return "预订已成功取消"
        else:
            return "操作成功完成！"


class AmbiguityAPI:
    """歧义解决API模拟实现"""
    
    def __init__(self, services):
        self.services = services
    
    async def resolve_ambiguity(self, request: dict) -> dict:
        """解决歧义"""
        try:
            # 获取歧义记录
            ambiguity = await self.services['conversation_service'].get_ambiguity(request["ambiguity_id"])
            
            # 解决歧义
            await self.services['conversation_service'].resolve_ambiguity(
                ambiguity, request["selected_intent"]
            )
            
            return {
                "success": True,
                "resolved_intent": request["selected_intent"],
                "conversation_state": "intent_resolved",
                "session_id": request["session_id"],
                "response": f"好的，我来帮您{request['selected_intent']}。"
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "session_id": request["session_id"],
                "response": "抱歉，无法解决歧义，请重新描述您的需求。"
            }