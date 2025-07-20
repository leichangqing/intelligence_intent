"""
复杂对话场景集成测试
"""
import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timedelta
import json

from src.services.intent_service import IntentService
from src.services.conversation_service import ConversationService
from src.services.slot_service import SlotService
from src.services.function_service import FunctionService
from src.services.cache_service import CacheService
from src.models.conversation import Session, Conversation
from src.models.intent import Intent
from src.models.slot import Slot, SlotValue


class TestComplexConversationScenarios:
    """复杂对话场景测试类"""
    
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
    def conversation_orchestrator(self, mock_services):
        """创建对话编排器"""
        return ComplexConversationOrchestrator(mock_services)
    
    @pytest.mark.asyncio
    async def test_intent_interruption_scenario(self, mock_services, conversation_orchestrator):
        """测试意图打断场景"""
        # 场景：用户在订机票过程中突然问余额
        conversation_steps = [
            {
                "input": "我要订机票",
                "expected_intent": "book_flight",
                "expected_state": "collecting_slots",
                "expected_response": "请问您要从哪里到哪里？"
            },
            {
                "input": "我的余额是多少？",
                "expected_intent": "check_balance",
                "expected_state": "intent_interrupted",
                "expected_response": "您的余额是1000元。需要继续预订机票吗？"
            },
            {
                "input": "是的，继续订票",
                "expected_intent": "book_flight",
                "expected_state": "collecting_slots",
                "expected_response": "好的，请问您要从哪里到哪里？"
            }
        ]
        
        session_id = "test_session_interruption"
        user_id = "test_user_interruption"
        
        # 设置模拟会话
        mock_session = MagicMock(spec=Session)
        mock_session.session_id = session_id
        mock_session.user_id = user_id
        mock_session.get_context.return_value = {"current_intent": None, "slots": {}}
        mock_services['conversation_service'].get_or_create_session.return_value = mock_session
        
        for i, step in enumerate(conversation_steps):
            # 设置模拟响应
            if step["expected_intent"] == "book_flight":
                mock_intent = MagicMock(spec=Intent)
                mock_intent.intent_name = "book_flight"
                mock_intent.confidence = 0.9
                mock_services['intent_service'].recognize_intent.return_value = mock_intent
                
                if i == 0:
                    mock_services['slot_service'].extract_slots.return_value = {}
                    mock_services['slot_service'].get_missing_slots.return_value = ["origin", "destination"]
                    mock_services['slot_service'].generate_slot_question.return_value = "请问您要从哪里到哪里？"
                elif i == 2:
                    mock_services['conversation_service'].resume_interrupted_intent.return_value = True
                    mock_services['slot_service'].extract_slots.return_value = {}
                    mock_services['slot_service'].get_missing_slots.return_value = ["origin", "destination"]
                    mock_services['slot_service'].generate_slot_question.return_value = "好的，请问您要从哪里到哪里？"
            
            elif step["expected_intent"] == "check_balance":
                mock_intent = MagicMock(spec=Intent)
                mock_intent.intent_name = "check_balance"
                mock_intent.confidence = 0.85
                mock_services['intent_service'].recognize_intent.return_value = mock_intent
                
                mock_function_result = {"success": True, "balance": 1000}
                mock_services['function_service'].call_function.return_value = mock_function_result
                mock_services['conversation_service'].handle_intent_interruption.return_value = True
            
            # 执行对话流程
            result = await conversation_orchestrator.process_user_input(
                user_input=step["input"],
                session_id=session_id,
                user_id=user_id
            )
            
            # 验证结果
            assert result['success'] == True
            assert result['intent'] == step["expected_intent"]
            assert result['conversation_state'] == step["expected_state"]
            assert step["expected_response"] in result['response']
            
            # 更新会话上下文用于下一步
            if i == 0:
                mock_session.get_context.return_value = {
                    "current_intent": "book_flight",
                    "slots": {},
                    "conversation_state": "collecting_slots"
                }
            elif i == 1:
                mock_session.get_context.return_value = {
                    "current_intent": "check_balance",
                    "interrupted_intent": "book_flight",
                    "interrupted_slots": {},
                    "conversation_state": "intent_interrupted"
                }
    
    @pytest.mark.asyncio
    async def test_multi_turn_slot_correction_scenario(self, mock_services, conversation_orchestrator):
        """测试多轮槽位修正场景"""
        # 场景：用户在多轮对话中修正之前填写的槽位
        conversation_steps = [
            {
                "input": "我要从北京到上海订机票",
                "expected_slots": {"origin": "北京", "destination": "上海"},
                "expected_missing": ["date"],
                "expected_response": "请问您希望什么时候出发？"
            },
            {
                "input": "明天",
                "expected_slots": {"origin": "北京", "destination": "上海", "date": "2024-01-02"},
                "expected_missing": [],
                "expected_response": "机票预订成功！"
            },
            {
                "input": "等等，我要改成后天",
                "expected_slots": {"origin": "北京", "destination": "上海", "date": "2024-01-03"},
                "expected_missing": [],
                "expected_response": "好的，已为您修改为后天出发。机票预订成功！"
            }
        ]
        
        session_id = "test_session_correction"
        user_id = "test_user_correction"
        
        # 设置模拟会话
        mock_session = MagicMock(spec=Session)
        mock_session.session_id = session_id
        mock_session.user_id = user_id
        mock_session.get_context.return_value = {"current_intent": None, "slots": {}}
        mock_services['conversation_service'].get_or_create_session.return_value = mock_session
        
        # 设置意图识别
        mock_intent = MagicMock(spec=Intent)
        mock_intent.intent_name = "book_flight"
        mock_intent.confidence = 0.9
        mock_services['intent_service'].recognize_intent.return_value = mock_intent
        
        accumulated_slots = {}
        
        for i, step in enumerate(conversation_steps):
            # 设置槽位提取
            if i == 0:
                extracted_slots = {
                    "origin": {"value": "北京", "confidence": 0.95},
                    "destination": {"value": "上海", "confidence": 0.9}
                }
            elif i == 1:
                extracted_slots = {
                    "date": {"value": "2024-01-02", "confidence": 0.8}
                }
            elif i == 2:
                extracted_slots = {
                    "date": {"value": "2024-01-03", "confidence": 0.8}
                }
            
            mock_services['slot_service'].extract_slots.return_value = extracted_slots
            
            # 合并槽位
            accumulated_slots.update(extracted_slots)
            mock_services['slot_service'].merge_slots.return_value = accumulated_slots
            
            # 设置缺失槽位
            if i == 0:
                mock_services['slot_service'].are_all_required_slots_filled.return_value = False
                mock_services['slot_service'].get_missing_slots.return_value = ["date"]
                mock_services['slot_service'].generate_slot_question.return_value = "请问您希望什么时候出发？"
            else:
                mock_services['slot_service'].are_all_required_slots_filled.return_value = True
                mock_function_result = {"success": True, "booking_id": f"BK{i+1}23456"}
                mock_services['function_service'].call_function.return_value = mock_function_result
                
                if i == 2:
                    mock_services['slot_service'].detect_slot_correction.return_value = True
            
            # 执行对话流程
            result = await conversation_orchestrator.process_user_input(
                user_input=step["input"],
                session_id=session_id,
                user_id=user_id
            )
            
            # 验证结果
            assert result['success'] == True
            assert result['intent'] == "book_flight"
            
            # 验证槽位
            for slot_name, expected_value in step["expected_slots"].items():
                assert slot_name in result.get('slots_filled', {})
                assert result['slots_filled'][slot_name] == expected_value
            
            # 验证响应
            assert step["expected_response"] in result['response']
            
            # 更新会话上下文
            mock_session.get_context.return_value = {
                "current_intent": "book_flight",
                "slots": accumulated_slots,
                "conversation_state": "collecting_slots" if i == 0 else "completed"
            }
    
    @pytest.mark.asyncio
    async def test_context_switch_with_slot_inheritance(self, mock_services, conversation_orchestrator):
        """测试上下文切换与槽位继承场景"""
        # 场景：用户订完机票后立即订酒店，部分槽位可以继承
        conversation_steps = [
            {
                "input": "我要从北京到上海订机票，明天出发",
                "expected_intent": "book_flight",
                "expected_slots": {"origin": "北京", "destination": "上海", "date": "2024-01-02"},
                "expected_response": "机票预订成功！"
            },
            {
                "input": "再帮我订个酒店",
                "expected_intent": "book_hotel",
                "expected_inherited_slots": {"destination": "上海", "date": "2024-01-02"},
                "expected_response": "好的，我为您在上海预订2024-01-02的酒店。还需要什么要求吗？"
            }
        ]
        
        session_id = "test_session_inheritance"
        user_id = "test_user_inheritance"
        
        # 设置模拟会话
        mock_session = MagicMock(spec=Session)
        mock_session.session_id = session_id
        mock_session.user_id = user_id
        mock_session.get_context.return_value = {"current_intent": None, "slots": {}}
        mock_services['conversation_service'].get_or_create_session.return_value = mock_session
        
        for i, step in enumerate(conversation_steps):
            # 设置意图识别
            mock_intent = MagicMock(spec=Intent)
            mock_intent.intent_name = step["expected_intent"]
            mock_intent.confidence = 0.9
            mock_services['intent_service'].recognize_intent.return_value = mock_intent
            
            if i == 0:
                # 第一步：订机票
                mock_services['slot_service'].extract_slots.return_value = {
                    "origin": {"value": "北京", "confidence": 0.95},
                    "destination": {"value": "上海", "confidence": 0.9},
                    "date": {"value": "2024-01-02", "confidence": 0.8}
                }
                mock_services['slot_service'].are_all_required_slots_filled.return_value = True
                mock_function_result = {"success": True, "booking_id": "BK123456"}
                mock_services['function_service'].call_function.return_value = mock_function_result
            
            elif i == 1:
                # 第二步：订酒店，继承相关槽位
                mock_services['slot_service'].extract_slots.return_value = {}
                mock_services['slot_service'].inherit_slots.return_value = {
                    "destination": {"value": "上海", "confidence": 0.9},
                    "date": {"value": "2024-01-02", "confidence": 0.8}
                }
                mock_services['slot_service'].are_all_required_slots_filled.return_value = True
                mock_function_result = {"success": True, "booking_id": "HT789012"}
                mock_services['function_service'].call_function.return_value = mock_function_result
            
            # 执行对话流程
            result = await conversation_orchestrator.process_user_input(
                user_input=step["input"],
                session_id=session_id,
                user_id=user_id
            )
            
            # 验证结果
            assert result['success'] == True
            assert result['intent'] == step["expected_intent"]
            
            # 验证槽位
            if i == 0:
                for slot_name, expected_value in step["expected_slots"].items():
                    assert slot_name in result.get('slots_filled', {})
                    assert result['slots_filled'][slot_name] == expected_value
            elif i == 1:
                for slot_name, expected_value in step["expected_inherited_slots"].items():
                    assert slot_name in result.get('inherited_slots', {})
                    assert result['inherited_slots'][slot_name] == expected_value
            
            # 验证响应
            assert step["expected_response"] in result['response']
            
            # 更新会话上下文
            if i == 0:
                mock_session.get_context.return_value = {
                    "current_intent": "book_flight",
                    "slots": {
                        "origin": {"value": "北京", "confidence": 0.95},
                        "destination": {"value": "上海", "confidence": 0.9},
                        "date": {"value": "2024-01-02", "confidence": 0.8}
                    },
                    "conversation_state": "completed",
                    "previous_intent": "book_flight"
                }
    
    @pytest.mark.asyncio
    async def test_error_recovery_scenario(self, mock_services, conversation_orchestrator):
        """测试错误恢复场景"""
        # 场景：外部服务调用失败后的恢复处理
        conversation_steps = [
            {
                "input": "我要从北京到上海订机票，明天出发",
                "service_error": True,
                "expected_response": "抱歉，机票预订服务暂时不可用"
            },
            {
                "input": "再试一次",
                "service_error": False,
                "expected_response": "机票预订成功！"
            }
        ]
        
        session_id = "test_session_recovery"
        user_id = "test_user_recovery"
        
        # 设置模拟会话
        mock_session = MagicMock(spec=Session)
        mock_session.session_id = session_id
        mock_session.user_id = user_id
        mock_session.get_context.return_value = {"current_intent": None, "slots": {}}
        mock_services['conversation_service'].get_or_create_session.return_value = mock_session
        
        # 设置意图识别
        mock_intent = MagicMock(spec=Intent)
        mock_intent.intent_name = "book_flight"
        mock_intent.confidence = 0.9
        mock_services['intent_service'].recognize_intent.return_value = mock_intent
        
        # 设置槽位提取
        mock_services['slot_service'].extract_slots.return_value = {
            "origin": {"value": "北京", "confidence": 0.95},
            "destination": {"value": "上海", "confidence": 0.9},
            "date": {"value": "2024-01-02", "confidence": 0.8}
        }
        mock_services['slot_service'].are_all_required_slots_filled.return_value = True
        
        for i, step in enumerate(conversation_steps):
            if step["service_error"]:
                # 模拟服务错误
                mock_services['function_service'].call_function.side_effect = Exception("外部服务不可用")
            else:
                # 恢复正常
                mock_services['function_service'].call_function.side_effect = None
                mock_function_result = {"success": True, "booking_id": "BK123456"}
                mock_services['function_service'].call_function.return_value = mock_function_result
                
                # 设置错误恢复
                mock_services['conversation_service'].recover_from_error.return_value = True
            
            # 执行对话流程
            result = await conversation_orchestrator.process_user_input(
                user_input=step["input"],
                session_id=session_id,
                user_id=user_id
            )
            
            # 验证结果
            if step["service_error"]:
                assert result['success'] == False
                assert result['error_type'] == "function_error"
                assert step["expected_response"] in result['response']
            else:
                assert result['success'] == True
                assert result['intent'] == "book_flight"
                assert step["expected_response"] in result['response']
            
            # 更新会话上下文
            if i == 0:
                mock_session.get_context.return_value = {
                    "current_intent": "book_flight",
                    "slots": {
                        "origin": {"value": "北京", "confidence": 0.95},
                        "destination": {"value": "上海", "confidence": 0.9},
                        "date": {"value": "2024-01-02", "confidence": 0.8}
                    },
                    "conversation_state": "error",
                    "last_error": "外部服务不可用"
                }
    
    @pytest.mark.asyncio
    async def test_ambiguous_intent_with_context_scenario(self, mock_services, conversation_orchestrator):
        """测试基于上下文的意图歧义消解场景"""
        # 场景：用户在特定上下文中的模糊表达
        conversation_steps = [
            {
                "input": "我要订机票",
                "expected_intent": "book_flight",
                "expected_response": "请问您要从哪里到哪里？"
            },
            {
                "input": "取消",
                "ambiguous": True,
                "candidates": ["cancel_flight", "cancel_booking"],
                "context_resolved": "cancel_booking",
                "expected_response": "好的，已为您取消当前的机票预订。"
            }
        ]
        
        session_id = "test_session_context_ambiguity"
        user_id = "test_user_context_ambiguity"
        
        # 设置模拟会话
        mock_session = MagicMock(spec=Session)
        mock_session.session_id = session_id
        mock_session.user_id = user_id
        mock_session.get_context.return_value = {"current_intent": None, "slots": {}}
        mock_services['conversation_service'].get_or_create_session.return_value = mock_session
        
        for i, step in enumerate(conversation_steps):
            if i == 0:
                # 第一步：正常意图识别
                mock_intent = MagicMock(spec=Intent)
                mock_intent.intent_name = "book_flight"
                mock_intent.confidence = 0.9
                mock_services['intent_service'].recognize_intent.return_value = mock_intent
                
                mock_services['slot_service'].extract_slots.return_value = {}
                mock_services['slot_service'].get_missing_slots.return_value = ["origin", "destination"]
                mock_services['slot_service'].generate_slot_question.return_value = "请问您要从哪里到哪里？"
            
            elif i == 1:
                # 第二步：基于上下文的歧义消解
                if step["ambiguous"]:
                    # 返回歧义结果
                    ambiguous_result = {
                        "is_ambiguous": True,
                        "candidates": [
                            {"intent": "cancel_flight", "confidence": 0.6},
                            {"intent": "cancel_booking", "confidence": 0.65}
                        ]
                    }
                    mock_services['intent_service'].recognize_intent.return_value = ambiguous_result
                    
                    # 使用上下文消解歧义
                    mock_resolved_intent = MagicMock(spec=Intent)
                    mock_resolved_intent.intent_name = step["context_resolved"]
                    mock_resolved_intent.confidence = 0.9
                    mock_services['intent_service'].resolve_with_context.return_value = mock_resolved_intent
                    
                    mock_function_result = {"success": True, "cancelled": True}
                    mock_services['function_service'].call_function.return_value = mock_function_result
            
            # 执行对话流程
            result = await conversation_orchestrator.process_user_input(
                user_input=step["input"],
                session_id=session_id,
                user_id=user_id
            )
            
            # 验证结果
            assert result['success'] == True
            
            if i == 0:
                assert result['intent'] == step["expected_intent"]
                assert result['conversation_state'] == "collecting_slots"
            elif i == 1:
                assert result['intent'] == step["context_resolved"]
                assert result['context_resolved'] == True
            
            assert step["expected_response"] in result['response']
            
            # 更新会话上下文
            if i == 0:
                mock_session.get_context.return_value = {
                    "current_intent": "book_flight",
                    "slots": {},
                    "conversation_state": "collecting_slots"
                }
    
    @pytest.mark.asyncio
    async def test_long_conversation_with_context_management(self, mock_services, conversation_orchestrator):
        """测试长对话的上下文管理场景"""
        # 场景：长对话中的上下文保持和清理
        conversation_steps = [
            {"input": "我要订机票", "expected_intent": "book_flight"},
            {"input": "从北京到上海", "expected_intent": "book_flight"},
            {"input": "明天出发", "expected_intent": "book_flight"},
            {"input": "经济舱", "expected_intent": "book_flight"},
            {"input": "确认预订", "expected_intent": "book_flight"},
            {"input": "谢谢", "expected_intent": "thanks", "context_reset": True}
        ]
        
        session_id = "test_session_long_conversation"
        user_id = "test_user_long_conversation"
        
        # 设置模拟会话
        mock_session = MagicMock(spec=Session)
        mock_session.session_id = session_id
        mock_session.user_id = user_id
        mock_session.get_context.return_value = {"current_intent": None, "slots": {}}
        mock_services['conversation_service'].get_or_create_session.return_value = mock_session
        
        accumulated_slots = {}
        
        for i, step in enumerate(conversation_steps):
            # 设置意图识别
            mock_intent = MagicMock(spec=Intent)
            mock_intent.intent_name = step["expected_intent"]
            mock_intent.confidence = 0.9
            mock_services['intent_service'].recognize_intent.return_value = mock_intent
            
            # 设置槽位提取
            if i == 0:
                mock_services['slot_service'].extract_slots.return_value = {}
                mock_services['slot_service'].get_missing_slots.return_value = ["origin", "destination"]
            elif i == 1:
                extracted = {
                    "origin": {"value": "北京", "confidence": 0.95},
                    "destination": {"value": "上海", "confidence": 0.9}
                }
                accumulated_slots.update(extracted)
                mock_services['slot_service'].extract_slots.return_value = extracted
                mock_services['slot_service'].get_missing_slots.return_value = ["date"]
            elif i == 2:
                extracted = {"date": {"value": "2024-01-02", "confidence": 0.8}}
                accumulated_slots.update(extracted)
                mock_services['slot_service'].extract_slots.return_value = extracted
                mock_services['slot_service'].get_missing_slots.return_value = ["class"]
            elif i == 3:
                extracted = {"class": {"value": "economy", "confidence": 0.9}}
                accumulated_slots.update(extracted)
                mock_services['slot_service'].extract_slots.return_value = extracted
                mock_services['slot_service'].are_all_required_slots_filled.return_value = True
            elif i == 4:
                mock_services['slot_service'].extract_slots.return_value = {}
                mock_function_result = {"success": True, "booking_id": "BK123456"}
                mock_services['function_service'].call_function.return_value = mock_function_result
            elif i == 5:
                # 感谢意图，重置上下文
                mock_services['slot_service'].extract_slots.return_value = {}
                mock_services['conversation_service'].should_reset_context.return_value = True
            
            # 执行对话流程
            result = await conversation_orchestrator.process_user_input(
                user_input=step["input"],
                session_id=session_id,
                user_id=user_id
            )
            
            # 验证结果
            assert result['success'] == True
            assert result['intent'] == step["expected_intent"]
            
            if step.get("context_reset"):
                assert result['context_reset'] == True
            
            # 更新会话上下文
            if i < 4:
                mock_session.get_context.return_value = {
                    "current_intent": "book_flight",
                    "slots": accumulated_slots,
                    "conversation_state": "collecting_slots" if i < 3 else "ready_to_execute"
                }
            elif i == 4:
                mock_session.get_context.return_value = {
                    "current_intent": "book_flight",
                    "slots": accumulated_slots,
                    "conversation_state": "completed"
                }
            else:
                mock_session.get_context.return_value = {
                    "current_intent": None,
                    "slots": {},
                    "conversation_state": "new"
                }


class ComplexConversationOrchestrator:
    """复杂对话编排器"""
    
    def __init__(self, services):
        self.services = services
    
    async def process_user_input(self, user_input: str, session_id: str, user_id: str) -> dict:
        """处理用户输入的复杂对话流程"""
        try:
            # 获取会话
            session = await self.services['conversation_service'].get_or_create_session(
                session_id=session_id,
                user_id=user_id
            )
            
            # 获取上下文
            context = session.get_context()
            current_intent = context.get('current_intent')
            conversation_state = context.get('conversation_state', 'new')
            
            # 处理错误恢复
            if conversation_state == 'error' and user_input in ['再试一次', '重试']:
                return await self._handle_error_recovery(session, context)
            
            # 处理意图打断
            if current_intent and conversation_state == 'collecting_slots':
                intent_result = await self.services['intent_service'].recognize_intent(user_input)
                if isinstance(intent_result, dict) and intent_result.get('is_ambiguous'):
                    # 使用上下文消解歧义
                    resolved_intent = await self.services['intent_service'].resolve_with_context(
                        user_input, intent_result['candidates'], context
                    )
                    return await self._handle_context_resolved_intent(resolved_intent, session, user_input)
                elif hasattr(intent_result, 'intent_name') and intent_result.intent_name != current_intent:
                    return await self._handle_intent_interruption(intent_result, session, user_input, context)
            
            # 正常意图处理
            intent_result = await self.services['intent_service'].recognize_intent(user_input)
            
            # 处理歧义
            if isinstance(intent_result, dict) and intent_result.get('is_ambiguous'):
                # 尝试使用上下文消解
                if context.get('current_intent'):
                    resolved_intent = await self.services['intent_service'].resolve_with_context(
                        user_input, intent_result['candidates'], context
                    )
                    return await self._handle_context_resolved_intent(resolved_intent, session, user_input)
                else:
                    return await self._handle_ambiguity(intent_result, session, user_input)
            
            # 处理槽位继承
            if current_intent and hasattr(intent_result, 'intent_name') and intent_result.intent_name != current_intent:
                inherited_slots = await self.services['slot_service'].inherit_slots(
                    current_intent, intent_result.intent_name, context.get('slots', {})
                )
                return await self._handle_slot_inheritance(intent_result, inherited_slots, session, user_input)
            
            # 处理槽位修正
            if current_intent and hasattr(intent_result, 'intent_name') and intent_result.intent_name == current_intent:
                slots = await self.services['slot_service'].extract_slots(user_input, intent_result.intent_name)
                if await self.services['slot_service'].detect_slot_correction(slots, context.get('slots', {})):
                    return await self._handle_slot_correction(intent_result, slots, session, user_input, context)
            
            # 处理上下文重置
            if intent_result.intent_name in ['thanks', 'goodbye', 'end']:
                if await self.services['conversation_service'].should_reset_context(session, intent_result.intent_name):
                    return await self._handle_context_reset(session, user_input)
            
            # 正常流程处理
            return await self._handle_normal_flow(intent_result, session, user_input, context)
            
        except Exception as e:
            return await self._handle_error(e, session, user_input)
    
    async def _handle_intent_interruption(self, intent_result, session, user_input: str, context: dict) -> dict:
        """处理意图打断"""
        # 保存当前意图状态
        await self.services['conversation_service'].handle_intent_interruption(
            session, context['current_intent'], intent_result.intent_name, context.get('slots', {})
        )
        
        # 处理新意图
        if intent_result.intent_name == 'check_balance':
            function_result = await self.services['function_service'].call_function(
                intent_result.intent_name, {}
            )
            
            # 询问是否继续之前的意图
            return {
                'success': True,
                'intent': intent_result.intent_name,
                'conversation_state': 'intent_interrupted',
                'function_result': function_result,
                'response': f"您的余额是{function_result.get('balance', 'N/A')}元。需要继续{context['current_intent']}吗？"
            }
        
        return {
            'success': True,
            'intent': intent_result.intent_name,
            'conversation_state': 'intent_interrupted',
            'response': f"好的，我来帮您{intent_result.intent_name}。"
        }
    
    async def _handle_slot_correction(self, intent_result, slots: dict, session, user_input: str, context: dict) -> dict:
        """处理槽位修正"""
        # 合并并更新槽位
        updated_slots = await self.services['slot_service'].merge_slots(
            context.get('slots', {}), slots
        )
        
        # 检查是否满足所有必需槽位
        if await self.services['slot_service'].are_all_required_slots_filled(intent_result.intent_name, updated_slots):
            # 执行功能调用
            function_result = await self.services['function_service'].call_function(
                intent_result.intent_name, {k: v['value'] for k, v in updated_slots.items()}
            )
            
            return {
                'success': True,
                'intent': intent_result.intent_name,
                'slots_filled': {k: v['value'] for k, v in updated_slots.items()},
                'conversation_state': 'completed',
                'function_result': function_result,
                'response': f"好的，已为您修改相关信息。{self._generate_success_response(intent_result.intent_name, function_result)}"
            }
        
        return {
            'success': True,
            'intent': intent_result.intent_name,
            'slots_filled': {k: v['value'] for k, v in updated_slots.items()},
            'conversation_state': 'collecting_slots',
            'response': "好的，已为您修改相关信息。"
        }
    
    async def _handle_slot_inheritance(self, intent_result, inherited_slots: dict, session, user_input: str) -> dict:
        """处理槽位继承"""
        # 提取当前输入的槽位
        current_slots = await self.services['slot_service'].extract_slots(user_input, intent_result.intent_name)
        
        # 合并继承的槽位
        all_slots = await self.services['slot_service'].merge_slots(inherited_slots, current_slots)
        
        # 检查是否满足所有必需槽位
        if await self.services['slot_service'].are_all_required_slots_filled(intent_result.intent_name, all_slots):
            # 执行功能调用
            function_result = await self.services['function_service'].call_function(
                intent_result.intent_name, {k: v['value'] for k, v in all_slots.items()}
            )
            
            return {
                'success': True,
                'intent': intent_result.intent_name,
                'inherited_slots': {k: v['value'] for k, v in inherited_slots.items()},
                'slots_filled': {k: v['value'] for k, v in all_slots.items()},
                'conversation_state': 'completed',
                'function_result': function_result,
                'response': f"好的，我为您{self._get_intent_description(intent_result.intent_name)}。{self._generate_success_response(intent_result.intent_name, function_result)}"
            }
        
        return {
            'success': True,
            'intent': intent_result.intent_name,
            'inherited_slots': {k: v['value'] for k, v in inherited_slots.items()},
            'conversation_state': 'collecting_slots',
            'response': f"好的，我为您{self._get_intent_description(intent_result.intent_name)}。还需要什么信息吗？"
        }
    
    async def _handle_context_resolved_intent(self, resolved_intent, session, user_input: str) -> dict:
        """处理基于上下文解决的意图"""
        # 执行功能调用
        function_result = await self.services['function_service'].call_function(
            resolved_intent.intent_name, {}
        )
        
        return {
            'success': True,
            'intent': resolved_intent.intent_name,
            'context_resolved': True,
            'conversation_state': 'completed',
            'function_result': function_result,
            'response': self._generate_success_response(resolved_intent.intent_name, function_result)
        }
    
    async def _handle_error_recovery(self, session, context: dict) -> dict:
        """处理错误恢复"""
        # 尝试恢复上一次操作
        if await self.services['conversation_service'].recover_from_error(session):
            # 重新执行功能调用
            function_result = await self.services['function_service'].call_function(
                context['current_intent'], {k: v['value'] for k, v in context.get('slots', {}).items()}
            )
            
            return {
                'success': True,
                'intent': context['current_intent'],
                'conversation_state': 'completed',
                'function_result': function_result,
                'response': self._generate_success_response(context['current_intent'], function_result)
            }
        
        return {
            'success': False,
            'error': 'recovery_failed',
            'response': '抱歉，无法恢复之前的操作，请重新开始。'
        }
    
    async def _handle_context_reset(self, session, user_input: str) -> dict:
        """处理上下文重置"""
        # 清理会话上下文
        session.clear_context()
        
        return {
            'success': True,
            'intent': 'thanks',
            'context_reset': True,
            'conversation_state': 'new',
            'response': '不客气！如果您还有其他需要帮助的地方，随时告诉我。'
        }
    
    async def _handle_normal_flow(self, intent_result, session, user_input: str, context: dict) -> dict:
        """处理正常流程"""
        # 提取槽位
        slots = await self.services['slot_service'].extract_slots(user_input, intent_result.intent_name)
        
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
                'success': True,
                'intent': intent_result.intent_name,
                'slots_filled': {k: v['value'] for k, v in all_slots.items()},
                'missing_slots': missing_slots,
                'conversation_state': 'collecting_slots',
                'response': question
            }
        
        # 执行功能调用
        function_result = await self.services['function_service'].call_function(
            intent_result.intent_name, {k: v['value'] for k, v in all_slots.items()}
        )
        
        return {
            'success': True,
            'intent': intent_result.intent_name,
            'slots_filled': {k: v['value'] for k, v in all_slots.items()},
            'conversation_state': 'completed',
            'function_result': function_result,
            'response': self._generate_success_response(intent_result.intent_name, function_result)
        }
    
    async def _handle_ambiguity(self, intent_result: dict, session, user_input: str) -> dict:
        """处理意图歧义"""
        return {
            'success': True,
            'is_ambiguous': True,
            'candidates': intent_result['candidates'],
            'conversation_state': 'waiting_for_clarification',
            'response': intent_result.get('clarification_question', '请选择您的意图')
        }
    
    async def _handle_error(self, error: Exception, session, user_input: str) -> dict:
        """处理错误"""
        return {
            'success': False,
            'error': str(error),
            'error_type': 'function_error',
            'error_message': str(error),
            'response': '抱歉，服务暂时不可用，请稍后重试。'
        }
    
    def _generate_success_response(self, intent_name: str, function_result: dict) -> str:
        """生成成功响应"""
        if intent_name == 'book_flight':
            return f"机票预订成功！订单号：{function_result.get('booking_id', 'N/A')}"
        elif intent_name == 'book_hotel':
            return f"酒店预订成功！订单号：{function_result.get('booking_id', 'N/A')}"
        elif intent_name == 'check_balance':
            return f"您的余额是{function_result.get('balance', 'N/A')}元"
        elif intent_name == 'cancel_booking':
            return "预订已成功取消"
        else:
            return "操作成功完成！"
    
    def _get_intent_description(self, intent_name: str) -> str:
        """获取意图描述"""
        descriptions = {
            'book_flight': '预订机票',
            'book_hotel': '预订酒店',
            'check_balance': '查询余额',
            'cancel_booking': '取消预订'
        }
        return descriptions.get(intent_name, intent_name)