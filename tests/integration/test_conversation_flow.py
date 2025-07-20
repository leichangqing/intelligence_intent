"""
完整对话流程集成测试
"""
import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime
import json

from src.services.intent_service import IntentService
from src.services.conversation_service import ConversationService
from src.services.slot_service import SlotService
from src.services.function_service import FunctionService
from src.services.cache_service import CacheService
from src.services.query_processor import QueryProcessor
from src.models.conversation import Session, Conversation
from src.models.intent import Intent
from src.models.slot import Slot, SlotValue
from src.models.function import Function


class TestConversationFlow:
    """完整对话流程集成测试类"""
    
    @pytest.fixture
    def mock_services(self):
        """创建模拟服务"""
        services = {
            'intent_service': MagicMock(spec=IntentService),
            'conversation_service': MagicMock(spec=ConversationService),
            'slot_service': MagicMock(spec=SlotService),
            'function_service': MagicMock(spec=FunctionService),
            'cache_service': MagicMock(spec=CacheService),
            'query_processor': MagicMock(spec=QueryProcessor)
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
    def mock_session(self):
        """创建模拟会话"""
        session = MagicMock(spec=Session)
        session.session_id = "test_session_001"
        session.user_id = "test_user_001"
        session.status = "active"
        session.context = json.dumps({
            "current_intent": None,
            "slots": {},
            "conversation_state": "new"
        })
        session.get_context.return_value = {
            "current_intent": None,
            "slots": {},
            "conversation_state": "new"
        }
        session.set_context = MagicMock()
        session.update_context = MagicMock()
        session.save = MagicMock()
        return session
    
    @pytest.mark.asyncio
    async def test_simple_intent_recognition_flow(self, mock_services, mock_session):
        """测试简单意图识别流程"""
        # 准备测试数据
        user_input = "我要订机票"
        
        # 设置模拟响应
        mock_intent = MagicMock(spec=Intent)
        mock_intent.id = 1
        mock_intent.intent_name = "book_flight"
        mock_intent.confidence = 0.9
        mock_intent.description = "预订机票"
        
        mock_services['intent_service'].recognize_intent.return_value = mock_intent
        mock_services['conversation_service'].get_or_create_session.return_value = mock_session
        mock_services['slot_service'].extract_slots.return_value = {}
        
        # 执行对话流程
        conversation_flow = ConversationFlowOrchestrator(mock_services)
        result = await conversation_flow.process_user_input(
            user_input=user_input,
            session_id="test_session_001",
            user_id="test_user_001"
        )
        
        # 验证结果
        assert result['success'] == True
        assert result['intent'] == "book_flight"
        assert result['confidence'] >= 0.9
        assert 'response' in result
        
        # 验证服务调用
        mock_services['intent_service'].recognize_intent.assert_called_once_with(user_input)
        mock_services['conversation_service'].get_or_create_session.assert_called_once()
        mock_services['slot_service'].extract_slots.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_slot_filling_flow(self, mock_services, mock_session):
        """测试槽位填充流程"""
        # 准备测试数据
        user_input = "我要从北京到上海"
        
        # 设置模拟响应
        mock_intent = MagicMock(spec=Intent)
        mock_intent.id = 1
        mock_intent.intent_name = "book_flight"
        mock_intent.confidence = 0.9
        
        mock_slots = {
            "origin": {"value": "北京", "confidence": 0.95},
            "destination": {"value": "上海", "confidence": 0.9}
        }
        
        mock_required_slots = ["origin", "destination", "date"]
        mock_missing_slots = ["date"]
        
        mock_services['intent_service'].recognize_intent.return_value = mock_intent
        mock_services['conversation_service'].get_or_create_session.return_value = mock_session
        mock_services['slot_service'].extract_slots.return_value = mock_slots
        mock_services['slot_service'].get_required_slots.return_value = mock_required_slots
        mock_services['slot_service'].get_missing_slots.return_value = mock_missing_slots
        mock_services['slot_service'].generate_slot_question.return_value = "请问您希望什么时候出发？"
        
        # 执行对话流程
        conversation_flow = ConversationFlowOrchestrator(mock_services)
        result = await conversation_flow.process_user_input(
            user_input=user_input,
            session_id="test_session_001",
            user_id="test_user_001"
        )
        
        # 验证结果
        assert result['success'] == True
        assert result['intent'] == "book_flight"
        assert result['slots_filled'] == {"origin": "北京", "destination": "上海"}
        assert result['missing_slots'] == ["date"]
        assert result['response'] == "请问您希望什么时候出发？"
        assert result['conversation_state'] == "collecting_slots"
        
        # 验证服务调用
        mock_services['slot_service'].extract_slots.assert_called_once()
        mock_services['slot_service'].get_required_slots.assert_called_once()
        mock_services['slot_service'].get_missing_slots.assert_called_once()
        mock_services['slot_service'].generate_slot_question.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_slot_completion_and_function_call_flow(self, mock_services, mock_session):
        """测试槽位完成和功能调用流程"""
        # 准备测试数据
        user_input = "明天"
        
        # 设置会话上下文
        mock_session.get_context.return_value = {
            "current_intent": "book_flight",
            "slots": {
                "origin": {"value": "北京", "confidence": 0.95},
                "destination": {"value": "上海", "confidence": 0.9}
            },
            "conversation_state": "collecting_slots"
        }
        
        # 设置模拟响应
        mock_intent = MagicMock(spec=Intent)
        mock_intent.id = 1
        mock_intent.intent_name = "book_flight"
        mock_intent.confidence = 0.9
        
        mock_slots = {
            "date": {"value": "2024-01-02", "confidence": 0.8}
        }
        
        mock_all_slots = {
            "origin": {"value": "北京", "confidence": 0.95},
            "destination": {"value": "上海", "confidence": 0.9},
            "date": {"value": "2024-01-02", "confidence": 0.8}
        }
        
        mock_function = MagicMock(spec=Function)
        mock_function.id = 1
        mock_function.function_name = "book_flight_api"
        
        mock_function_result = {
            "success": True,
            "booking_id": "BK123456",
            "message": "机票预订成功",
            "details": {
                "origin": "北京",
                "destination": "上海",
                "date": "2024-01-02",
                "price": 1200.50
            }
        }
        
        mock_services['intent_service'].recognize_intent.return_value = mock_intent
        mock_services['conversation_service'].get_or_create_session.return_value = mock_session
        mock_services['slot_service'].extract_slots.return_value = mock_slots
        mock_services['slot_service'].merge_slots.return_value = mock_all_slots
        mock_services['slot_service'].are_all_required_slots_filled.return_value = True
        mock_services['function_service'].get_function_for_intent.return_value = mock_function
        mock_services['function_service'].call_function.return_value = mock_function_result
        
        # 执行对话流程
        conversation_flow = ConversationFlowOrchestrator(mock_services)
        result = await conversation_flow.process_user_input(
            user_input=user_input,
            session_id="test_session_001",
            user_id="test_user_001"
        )
        
        # 验证结果
        assert result['success'] == True
        assert result['intent'] == "book_flight"
        assert result['slots_complete'] == True
        assert result['function_called'] == True
        assert result['function_result'] == mock_function_result
        assert result['conversation_state'] == "completed"
        assert "机票预订成功" in result['response']
        
        # 验证服务调用
        mock_services['slot_service'].merge_slots.assert_called_once()
        mock_services['slot_service'].are_all_required_slots_filled.assert_called_once()
        mock_services['function_service'].get_function_for_intent.assert_called_once()
        mock_services['function_service'].call_function.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_intent_ambiguity_resolution_flow(self, mock_services, mock_session):
        """测试意图歧义解决流程"""
        # 准备测试数据
        user_input = "我要处理机票"
        
        # 设置模拟响应
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
        mock_services['conversation_service'].get_or_create_session.return_value = mock_session
        mock_services['conversation_service'].save_ambiguity.return_value = None
        
        # 执行对话流程
        conversation_flow = ConversationFlowOrchestrator(mock_services)
        result = await conversation_flow.process_user_input(
            user_input=user_input,
            session_id="test_session_001",
            user_id="test_user_001"
        )
        
        # 验证结果
        assert result['success'] == True
        assert result['is_ambiguous'] == True
        assert len(result['candidates']) == 3
        assert result['clarification_question'] == "请问您是要预订机票、查询机票还是取消机票？"
        assert result['conversation_state'] == "waiting_for_clarification"
        
        # 验证服务调用
        mock_services['intent_service'].recognize_intent.assert_called_once_with(user_input)
        mock_services['conversation_service'].save_ambiguity.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_intent_clarification_flow(self, mock_services, mock_session):
        """测试意图澄清流程"""
        # 准备测试数据
        user_input = "我要预订机票"
        
        # 设置会话上下文
        mock_session.get_context.return_value = {
            "current_intent": None,
            "slots": {},
            "conversation_state": "waiting_for_clarification",
            "ambiguity_candidates": [
                {"intent": "book_flight", "confidence": 0.7, "description": "预订机票"},
                {"intent": "check_flight", "confidence": 0.65, "description": "查询机票"}
            ]
        }
        
        # 设置模拟响应
        mock_intent = MagicMock(spec=Intent)
        mock_intent.id = 1
        mock_intent.intent_name = "book_flight"
        mock_intent.confidence = 0.9
        
        mock_services['intent_service'].resolve_ambiguity.return_value = mock_intent
        mock_services['conversation_service'].get_or_create_session.return_value = mock_session
        mock_services['conversation_service'].resolve_ambiguity.return_value = None
        mock_services['slot_service'].extract_slots.return_value = {}
        
        # 执行对话流程
        conversation_flow = ConversationFlowOrchestrator(mock_services)
        result = await conversation_flow.process_user_input(
            user_input=user_input,
            session_id="test_session_001",
            user_id="test_user_001"
        )
        
        # 验证结果
        assert result['success'] == True
        assert result['intent'] == "book_flight"
        assert result['ambiguity_resolved'] == True
        assert result['conversation_state'] == "intent_resolved"
        
        # 验证服务调用
        mock_services['intent_service'].resolve_ambiguity.assert_called_once()
        mock_services['conversation_service'].resolve_ambiguity.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_conversation_context_preservation_flow(self, mock_services, mock_session):
        """测试对话上下文保持流程"""
        # 准备测试数据
        user_inputs = [
            "我要订机票",
            "从北京到上海",
            "明天出发",
            "经济舱"
        ]
        
        expected_contexts = [
            {"current_intent": "book_flight", "slots": {}, "conversation_state": "collecting_slots"},
            {"current_intent": "book_flight", "slots": {"origin": "北京", "destination": "上海"}, "conversation_state": "collecting_slots"},
            {"current_intent": "book_flight", "slots": {"origin": "北京", "destination": "上海", "date": "2024-01-02"}, "conversation_state": "collecting_slots"},
            {"current_intent": "book_flight", "slots": {"origin": "北京", "destination": "上海", "date": "2024-01-02", "class": "economy"}, "conversation_state": "completed"}
        ]
        
        conversation_flow = ConversationFlowOrchestrator(mock_services)
        
        for i, user_input in enumerate(user_inputs):
            # 设置每轮的模拟响应
            if i == 0:
                mock_intent = MagicMock(spec=Intent)
                mock_intent.intent_name = "book_flight"
                mock_intent.confidence = 0.9
                mock_services['intent_service'].recognize_intent.return_value = mock_intent
                mock_services['slot_service'].extract_slots.return_value = {}
                mock_services['slot_service'].get_missing_slots.return_value = ["origin", "destination", "date"]
                mock_services['slot_service'].generate_slot_question.return_value = "请问您要从哪里到哪里？"
            
            elif i == 1:
                mock_services['slot_service'].extract_slots.return_value = {
                    "origin": {"value": "北京", "confidence": 0.95},
                    "destination": {"value": "上海", "confidence": 0.9}
                }
                mock_services['slot_service'].get_missing_slots.return_value = ["date"]
                mock_services['slot_service'].generate_slot_question.return_value = "请问您希望什么时候出发？"
            
            elif i == 2:
                mock_services['slot_service'].extract_slots.return_value = {
                    "date": {"value": "2024-01-02", "confidence": 0.8}
                }
                mock_services['slot_service'].get_missing_slots.return_value = ["class"]
                mock_services['slot_service'].generate_slot_question.return_value = "请问您希望选择什么舱位？"
            
            elif i == 3:
                mock_services['slot_service'].extract_slots.return_value = {
                    "class": {"value": "economy", "confidence": 0.9}
                }
                mock_services['slot_service'].are_all_required_slots_filled.return_value = True
                mock_function_result = {"success": True, "booking_id": "BK123456"}
                mock_services['function_service'].call_function.return_value = mock_function_result
            
            # 设置会话上下文
            if i > 0:
                mock_session.get_context.return_value = expected_contexts[i-1]
            
            # 执行对话流程
            result = await conversation_flow.process_user_input(
                user_input=user_input,
                session_id="test_session_001",
                user_id="test_user_001"
            )
            
            # 验证结果
            assert result['success'] == True
            assert result['conversation_state'] == expected_contexts[i]['conversation_state']
            
            # 验证上下文更新
            if i < len(user_inputs) - 1:
                mock_session.update_context.assert_called()
    
    @pytest.mark.asyncio
    async def test_error_handling_flow(self, mock_services, mock_session):
        """测试错误处理流程"""
        # 准备测试数据
        user_input = "我要订机票"
        
        # 设置模拟错误
        mock_services['intent_service'].recognize_intent.side_effect = Exception("NLU服务不可用")
        mock_services['conversation_service'].get_or_create_session.return_value = mock_session
        
        # 执行对话流程
        conversation_flow = ConversationFlowOrchestrator(mock_services)
        result = await conversation_flow.process_user_input(
            user_input=user_input,
            session_id="test_session_001",
            user_id="test_user_001"
        )
        
        # 验证结果
        assert result['success'] == False
        assert 'error' in result
        assert result['error_type'] == "service_error"
        assert "NLU服务不可用" in result['error_message']
        assert result['response'] == "抱歉，系统暂时无法处理您的请求，请稍后重试。"
        
        # 验证错误记录
        mock_services['conversation_service'].save_error.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_function_call_error_handling_flow(self, mock_services, mock_session):
        """测试功能调用错误处理流程"""
        # 准备测试数据
        user_input = "我要订机票"
        
        # 设置会话上下文
        mock_session.get_context.return_value = {
            "current_intent": "book_flight",
            "slots": {
                "origin": {"value": "北京", "confidence": 0.95},
                "destination": {"value": "上海", "confidence": 0.9},
                "date": {"value": "2024-01-02", "confidence": 0.8}
            },
            "conversation_state": "collecting_slots"
        }
        
        # 设置模拟响应
        mock_intent = MagicMock(spec=Intent)
        mock_intent.intent_name = "book_flight"
        mock_intent.confidence = 0.9
        
        mock_function = MagicMock(spec=Function)
        mock_function.function_name = "book_flight_api"
        
        mock_services['intent_service'].recognize_intent.return_value = mock_intent
        mock_services['conversation_service'].get_or_create_session.return_value = mock_session
        mock_services['slot_service'].extract_slots.return_value = {}
        mock_services['slot_service'].are_all_required_slots_filled.return_value = True
        mock_services['function_service'].get_function_for_intent.return_value = mock_function
        mock_services['function_service'].call_function.side_effect = Exception("外部API调用失败")
        
        # 执行对话流程
        conversation_flow = ConversationFlowOrchestrator(mock_services)
        result = await conversation_flow.process_user_input(
            user_input=user_input,
            session_id="test_session_001",
            user_id="test_user_001"
        )
        
        # 验证结果
        assert result['success'] == False
        assert result['function_called'] == False
        assert 'error' in result
        assert result['error_type'] == "function_error"
        assert "外部API调用失败" in result['error_message']
        assert result['response'] == "抱歉，机票预订服务暂时不可用，请稍后重试。"
        
        # 验证错误记录
        mock_services['conversation_service'].save_error.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_concurrent_conversations_flow(self, mock_services):
        """测试并发对话流程"""
        # 准备测试数据
        session_ids = ["session_001", "session_002", "session_003"]
        user_inputs = ["我要订机票", "查询余额", "取消订单"]
        
        # 为每个会话创建模拟
        mock_sessions = []
        for i, session_id in enumerate(session_ids):
            mock_session = MagicMock(spec=Session)
            mock_session.session_id = session_id
            mock_session.user_id = f"user_{i+1:03d}"
            mock_session.get_context.return_value = {
                "current_intent": None,
                "slots": {},
                "conversation_state": "new"
            }
            mock_sessions.append(mock_session)
        
        # 设置模拟响应
        mock_intents = [
            MagicMock(spec=Intent, intent_name="book_flight", confidence=0.9),
            MagicMock(spec=Intent, intent_name="check_balance", confidence=0.85),
            MagicMock(spec=Intent, intent_name="cancel_order", confidence=0.8)
        ]
        
        mock_services['intent_service'].recognize_intent.side_effect = mock_intents
        mock_services['conversation_service'].get_or_create_session.side_effect = mock_sessions
        mock_services['slot_service'].extract_slots.return_value = {}
        
        # 执行并发对话流程
        conversation_flow = ConversationFlowOrchestrator(mock_services)
        tasks = []
        
        for i, (session_id, user_input) in enumerate(zip(session_ids, user_inputs)):
            task = conversation_flow.process_user_input(
                user_input=user_input,
                session_id=session_id,
                user_id=f"user_{i+1:03d}"
            )
            tasks.append(task)
        
        results = await asyncio.gather(*tasks)
        
        # 验证结果
        assert len(results) == 3
        for i, result in enumerate(results):
            assert result['success'] == True
            assert result['session_id'] == session_ids[i]
            assert result['intent'] == mock_intents[i].intent_name
        
        # 验证服务调用次数
        assert mock_services['intent_service'].recognize_intent.call_count == 3
        assert mock_services['conversation_service'].get_or_create_session.call_count == 3
    
    @pytest.mark.asyncio
    async def test_conversation_timeout_handling(self, mock_services, mock_session):
        """测试对话超时处理"""
        # 准备测试数据
        user_input = "我要订机票"
        
        # 设置会话超时
        mock_session.get_context.return_value = {
            "current_intent": "book_flight",
            "slots": {"origin": {"value": "北京", "confidence": 0.95}},
            "conversation_state": "collecting_slots",
            "last_activity": "2024-01-01 10:00:00"
        }
        
        # 设置模拟响应
        mock_services['conversation_service'].is_session_expired.return_value = True
        mock_services['conversation_service'].get_or_create_session.return_value = mock_session
        
        # 执行对话流程
        conversation_flow = ConversationFlowOrchestrator(mock_services)
        result = await conversation_flow.process_user_input(
            user_input=user_input,
            session_id="test_session_001",
            user_id="test_user_001"
        )
        
        # 验证结果
        assert result['success'] == True
        assert result['session_expired'] == True
        assert result['conversation_state'] == "new"
        assert "会话已过期" in result['response']
        
        # 验证会话重置
        mock_services['conversation_service'].reset_session.assert_called_once()


class ConversationFlowOrchestrator:
    """对话流程编排器"""
    
    def __init__(self, services):
        self.services = services
    
    async def process_user_input(self, user_input: str, session_id: str, user_id: str) -> dict:
        """处理用户输入的完整流程"""
        try:
            # 1. 获取或创建会话
            session = await self.services['conversation_service'].get_or_create_session(
                session_id=session_id,
                user_id=user_id
            )
            
            # 2. 检查会话是否过期
            if await self.services['conversation_service'].is_session_expired(session):
                await self.services['conversation_service'].reset_session(session)
                return {
                    'success': True,
                    'session_expired': True,
                    'conversation_state': 'new',
                    'response': '会话已过期，请重新开始对话。'
                }
            
            # 3. 获取会话上下文
            context = session.get_context()
            
            # 4. 处理意图澄清状态
            if context.get('conversation_state') == 'waiting_for_clarification':
                return await self._handle_clarification(user_input, session, context)
            
            # 5. 意图识别
            intent_result = await self.services['intent_service'].recognize_intent(user_input)
            
            # 6. 处理意图歧义
            if isinstance(intent_result, dict) and intent_result.get('is_ambiguous'):
                return await self._handle_ambiguity(intent_result, session, user_input)
            
            # 7. 槽位提取
            slots = await self.services['slot_service'].extract_slots(
                user_input, intent_result.intent_name
            )
            
            # 8. 合并槽位
            if context.get('current_intent') == intent_result.intent_name:
                all_slots = await self.services['slot_service'].merge_slots(
                    context.get('slots', {}), slots
                )
            else:
                all_slots = slots
            
            # 9. 检查必需槽位
            if not await self.services['slot_service'].are_all_required_slots_filled(
                intent_result.intent_name, all_slots
            ):
                return await self._handle_slot_filling(
                    intent_result, all_slots, session, user_input
                )
            
            # 10. 执行功能调用
            return await self._handle_function_call(
                intent_result, all_slots, session, user_input
            )
            
        except Exception as e:
            return await self._handle_error(e, session, user_input)
    
    async def _handle_clarification(self, user_input: str, session, context: dict) -> dict:
        """处理意图澄清"""
        candidates = context.get('ambiguity_candidates', [])
        intent = await self.services['intent_service'].resolve_ambiguity(
            user_input, candidates
        )
        
        await self.services['conversation_service'].resolve_ambiguity(
            session, intent.intent_name
        )
        
        # 提取槽位
        slots = await self.services['slot_service'].extract_slots(
            user_input, intent.intent_name
        )
        
        return {
            'success': True,
            'intent': intent.intent_name,
            'ambiguity_resolved': True,
            'slots': slots,
            'conversation_state': 'intent_resolved',
            'response': f'好的，我理解您要{intent.intent_name}。'
        }
    
    async def _handle_ambiguity(self, intent_result: dict, session, user_input: str) -> dict:
        """处理意图歧义"""
        await self.services['conversation_service'].save_ambiguity(
            session, user_input, intent_result['candidates']
        )
        
        # 更新会话状态
        session.update_context({
            'conversation_state': 'waiting_for_clarification',
            'ambiguity_candidates': intent_result['candidates']
        })
        
        return {
            'success': True,
            'is_ambiguous': True,
            'candidates': intent_result['candidates'],
            'clarification_question': intent_result['clarification_question'],
            'conversation_state': 'waiting_for_clarification',
            'response': intent_result['clarification_question']
        }
    
    async def _handle_slot_filling(self, intent, slots: dict, session, user_input: str) -> dict:
        """处理槽位填充"""
        # 获取缺失的槽位
        missing_slots = await self.services['slot_service'].get_missing_slots(
            intent.intent_name, slots
        )
        
        # 生成槽位询问
        question = await self.services['slot_service'].generate_slot_question(
            intent.intent_name, missing_slots[0]
        )
        
        # 更新会话上下文
        session.update_context({
            'current_intent': intent.intent_name,
            'slots': slots,
            'conversation_state': 'collecting_slots'
        })
        
        return {
            'success': True,
            'intent': intent.intent_name,
            'slots_filled': {k: v['value'] for k, v in slots.items()},
            'missing_slots': missing_slots,
            'conversation_state': 'collecting_slots',
            'response': question
        }
    
    async def _handle_function_call(self, intent, slots: dict, session, user_input: str) -> dict:
        """处理功能调用"""
        try:
            # 获取意图对应的功能
            function = await self.services['function_service'].get_function_for_intent(
                intent.intent_name
            )
            
            # 调用功能
            function_result = await self.services['function_service'].call_function(
                function, {k: v['value'] for k, v in slots.items()}
            )
            
            # 更新会话状态
            session.update_context({
                'current_intent': intent.intent_name,
                'slots': slots,
                'conversation_state': 'completed'
            })
            
            return {
                'success': True,
                'intent': intent.intent_name,
                'slots_complete': True,
                'function_called': True,
                'function_result': function_result,
                'conversation_state': 'completed',
                'response': self._generate_success_response(intent.intent_name, function_result)
            }
            
        except Exception as e:
            await self.services['conversation_service'].save_error(
                session, user_input, str(e), 'function_error'
            )
            
            return {
                'success': False,
                'function_called': False,
                'error': str(e),
                'error_type': 'function_error',
                'error_message': str(e),
                'response': self._generate_error_response(intent.intent_name)
            }
    
    async def _handle_error(self, error: Exception, session, user_input: str) -> dict:
        """处理错误"""
        await self.services['conversation_service'].save_error(
            session, user_input, str(error), 'service_error'
        )
        
        return {
            'success': False,
            'error': str(error),
            'error_type': 'service_error',
            'error_message': str(error),
            'response': '抱歉，系统暂时无法处理您的请求，请稍后重试。'
        }
    
    def _generate_success_response(self, intent_name: str, function_result: dict) -> str:
        """生成成功响应"""
        if intent_name == 'book_flight':
            return f"机票预订成功！订单号：{function_result.get('booking_id', 'N/A')}"
        elif intent_name == 'check_balance':
            return f"您的余额是：{function_result.get('balance', 'N/A')}元"
        else:
            return f"操作成功完成！"
    
    def _generate_error_response(self, intent_name: str) -> str:
        """生成错误响应"""
        if intent_name == 'book_flight':
            return "抱歉，机票预订服务暂时不可用，请稍后重试。"
        elif intent_name == 'check_balance':
            return "抱歉，余额查询服务暂时不可用，请稍后重试。"
        else:
            return "抱歉，服务暂时不可用，请稍后重试。"