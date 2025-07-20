"""
意图转移场景集成测试 - TASK-047
测试各种意图转移和上下文切换场景
"""
import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timedelta
import json

from src.services.intent_transfer_service import IntentTransferService, TransferTrigger, TransferCondition
from src.services.intent_stack_service import IntentStackService, IntentStackStatus, IntentInterruptionType
from src.services.intent_service import IntentService
from src.services.conversation_service import ConversationService
from src.services.slot_service import SlotService
from src.services.cache_service import CacheService
from src.models.conversation import Session, IntentTransfer
from src.models.intent import Intent


class TestIntentTransferScenarios:
    """意图转移场景集成测试类"""
    
    @pytest.fixture
    def mock_services(self):
        """创建模拟服务"""
        services = {
            'intent_transfer_service': MagicMock(spec=IntentTransferService),
            'intent_stack_service': MagicMock(spec=IntentStackService),
            'intent_service': MagicMock(spec=IntentService),
            'conversation_service': MagicMock(spec=ConversationService),
            'slot_service': MagicMock(spec=SlotService),
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
    def mock_session(self):
        """创建模拟会话"""
        session = MagicMock(spec=Session)
        session.session_id = "test_session_001"
        session.user_id = "test_user_001"
        session.status = "active"
        session.context = json.dumps({
            "current_intent": "book_flight",
            "slots": {
                "origin": {"value": "北京", "confidence": 0.95}
            },
            "conversation_state": "collecting_slots"
        })
        session.get_context.return_value = {
            "current_intent": "book_flight",
            "slots": {
                "origin": {"value": "北京", "confidence": 0.95}
            },
            "conversation_state": "collecting_slots"
        }
        session.save = AsyncMock()
        session.update_context = MagicMock()
        return session
    
    @pytest.mark.asyncio
    async def test_explicit_intent_change_scenario(self, mock_services, mock_session):
        """测试明确意图切换场景"""
        # 场景：用户在订机票过程中明确要求查询余额
        user_input = "我要查询余额"
        
        # 设置模拟响应
        new_intent = MagicMock(spec=Intent)
        new_intent.id = 2
        new_intent.intent_name = "check_balance"
        new_intent.confidence = 0.9
        
        transfer_decision = {
            "should_transfer": True,
            "target_intent": "check_balance",
            "transfer_type": "explicit_change",
            "confidence": 0.9,
            "reasoning": "用户明确要求查询余额"
        }
        
        mock_services['intent_service'].recognize_intent.return_value = new_intent
        mock_services['intent_transfer_service'].evaluate_transfer.return_value = transfer_decision
        mock_services['intent_stack_service'].push_intent.return_value = True
        mock_services['conversation_service'].record_intent_transfer.return_value = None
        
        # 执行意图转移
        transfer_orchestrator = IntentTransferOrchestrator(mock_services)
        result = await transfer_orchestrator.process_intent_transfer(
            user_input=user_input,
            session=mock_session,
            current_intent="book_flight"
        )
        
        # 验证结果
        assert result['success'] == True
        assert result['transfer_occurred'] == True
        assert result['transfer_type'] == "explicit_change"
        assert result['from_intent'] == "book_flight"
        assert result['to_intent'] == "check_balance"
        assert result['confidence'] >= 0.9
        
        # 验证服务调用
        mock_services['intent_transfer_service'].evaluate_transfer.assert_called_once()
        mock_services['intent_stack_service'].push_intent.assert_called_once()
        mock_services['conversation_service'].record_intent_transfer.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_interruption_with_context_preservation(self, mock_services, mock_session):
        """测试打岔场景并保持上下文"""
        # 场景：用户在订机票过程中被电话打岔，询问余额
        user_input = "等等，先告诉我账户余额"
        
        # 设置模拟响应
        interrupt_intent = MagicMock(spec=Intent)
        interrupt_intent.id = 2
        interrupt_intent.intent_name = "check_balance"
        interrupt_intent.confidence = 0.85
        
        transfer_decision = {
            "should_transfer": True,
            "target_intent": "check_balance",
            "transfer_type": "interruption",
            "confidence": 0.85,
            "reasoning": "用户请求暂时中断当前任务查询余额"
        }
        
        saved_context = {
            "intent": "book_flight",
            "slots": {"origin": {"value": "北京", "confidence": 0.95}},
            "progress": 0.3,
            "timestamp": datetime.now().isoformat()
        }
        
        mock_services['intent_service'].recognize_intent.return_value = interrupt_intent
        mock_services['intent_transfer_service'].evaluate_transfer.return_value = transfer_decision
        mock_services['intent_stack_service'].interrupt_current_intent.return_value = saved_context
        mock_services['intent_stack_service'].push_intent.return_value = True
        
        # 执行打岔处理
        transfer_orchestrator = IntentTransferOrchestrator(mock_services)
        result = await transfer_orchestrator.process_intent_transfer(
            user_input=user_input,
            session=mock_session,
            current_intent="book_flight"
        )
        
        # 验证结果
        assert result['success'] == True
        assert result['transfer_occurred'] == True
        assert result['transfer_type'] == "interruption"
        assert result['context_preserved'] == True
        assert result['saved_context'] == saved_context
        assert result['from_intent'] == "book_flight"
        assert result['to_intent'] == "check_balance"
        
        # 验证服务调用
        mock_services['intent_stack_service'].interrupt_current_intent.assert_called_once()
        mock_services['intent_stack_service'].push_intent.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_context_driven_transfer(self, mock_services, mock_session):
        """测试上下文驱动的意图转移"""
        # 场景：用户在查询机票过程中，根据查询结果自动转移到预订意图
        user_input = "这个航班不错，我要预订"
        
        # 设置当前上下文
        mock_session.get_context.return_value = {
            "current_intent": "search_flight",
            "slots": {
                "origin": {"value": "北京", "confidence": 0.95},
                "destination": {"value": "上海", "confidence": 0.9},
                "flight_info": {"value": "CA1234", "confidence": 0.9}
            },
            "conversation_state": "search_completed"
        }
        
        # 设置模拟响应
        target_intent = MagicMock(spec=Intent)
        target_intent.id = 1
        target_intent.intent_name = "book_flight"
        target_intent.confidence = 0.88
        
        transfer_decision = {
            "should_transfer": True,
            "target_intent": "book_flight",
            "transfer_type": "context_driven",
            "confidence": 0.88,
            "reasoning": "用户基于查询结果决定预订航班"
        }
        
        mock_services['intent_service'].recognize_intent.return_value = target_intent
        mock_services['intent_transfer_service'].evaluate_transfer.return_value = transfer_decision
        mock_services['slot_service'].inherit_relevant_slots.return_value = {
            "origin": {"value": "北京", "confidence": 0.95},
            "destination": {"value": "上海", "confidence": 0.9},
            "flight_number": {"value": "CA1234", "confidence": 0.9}
        }
        
        # 执行上下文驱动转移
        transfer_orchestrator = IntentTransferOrchestrator(mock_services)
        result = await transfer_orchestrator.process_intent_transfer(
            user_input=user_input,
            session=mock_session,
            current_intent="search_flight"
        )
        
        # 验证结果
        assert result['success'] == True
        assert result['transfer_occurred'] == True
        assert result['transfer_type'] == "context_driven"
        assert result['slots_inherited'] == True
        assert len(result['inherited_slots']) == 3
        assert result['from_intent'] == "search_flight"
        assert result['to_intent'] == "book_flight"
        
        # 验证槽位继承
        mock_services['slot_service'].inherit_relevant_slots.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_system_suggestion_transfer(self, mock_services, mock_session):
        """测试系统建议的意图转移"""
        # 场景：系统根据用户行为模式建议转移到相关意图
        user_input = "好的"
        
        # 设置系统建议
        system_suggestion = {
            "should_transfer": True,
            "target_intent": "check_flight_status",
            "transfer_type": "system_suggestion",
            "confidence": 0.75,
            "reasoning": "基于用户历史行为，建议查询航班状态",
            "suggestion_source": "user_behavior_analysis"
        }
        
        mock_services['intent_transfer_service'].get_system_suggestion.return_value = system_suggestion
        mock_services['intent_transfer_service'].evaluate_transfer.return_value = system_suggestion
        
        # 执行系统建议转移
        transfer_orchestrator = IntentTransferOrchestrator(mock_services)
        result = await transfer_orchestrator.process_intent_transfer(
            user_input=user_input,
            session=mock_session,
            current_intent="book_flight",
            enable_system_suggestions=True
        )
        
        # 验证结果
        assert result['success'] == True
        assert result['transfer_occurred'] == True
        assert result['transfer_type'] == "system_suggestion"
        assert result['suggestion_source'] == "user_behavior_analysis"
        assert result['to_intent'] == "check_flight_status"
        assert result['confidence'] >= 0.75
        
        # 验证系统建议调用
        mock_services['intent_transfer_service'].get_system_suggestion.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_return_to_previous_intent(self, mock_services, mock_session):
        """测试返回到前一个意图"""
        # 场景：用户完成打岔任务后返回原任务
        user_input = "好的，现在继续订机票"
        
        # 设置意图栈状态
        stack_state = {
            "current_intent": "check_balance",
            "previous_intents": [
                {
                    "intent": "book_flight",
                    "slots": {"origin": {"value": "北京", "confidence": 0.95}},
                    "progress": 0.3,
                    "saved_at": datetime.now().isoformat()
                }
            ]
        }
        
        return_decision = {
            "should_transfer": True,
            "target_intent": "book_flight",
            "transfer_type": "return_to_previous",
            "confidence": 0.9,
            "reasoning": "用户明确要求返回订机票任务"
        }
        
        restored_context = {
            "intent": "book_flight",
            "slots": {"origin": {"value": "北京", "confidence": 0.95}},
            "progress": 0.3
        }
        
        mock_services['intent_stack_service'].get_stack_state.return_value = stack_state
        mock_services['intent_transfer_service'].evaluate_transfer.return_value = return_decision
        mock_services['intent_stack_service'].pop_intent.return_value = True
        mock_services['intent_stack_service'].restore_previous_context.return_value = restored_context
        
        # 执行返回操作
        transfer_orchestrator = IntentTransferOrchestrator(mock_services)
        result = await transfer_orchestrator.process_intent_transfer(
            user_input=user_input,
            session=mock_session,
            current_intent="check_balance"
        )
        
        # 验证结果
        assert result['success'] == True
        assert result['transfer_occurred'] == True
        assert result['transfer_type'] == "return_to_previous"
        assert result['context_restored'] == True
        assert result['restored_context'] == restored_context
        assert result['to_intent'] == "book_flight"
        
        # 验证栈操作
        mock_services['intent_stack_service'].pop_intent.assert_called_once()
        mock_services['intent_stack_service'].restore_previous_context.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_multiple_interruption_scenario(self, mock_services, mock_session):
        """测试多层打岔场景"""
        # 场景：订机票 -> 查余额 -> 查航班状态 -> 回到查余额 -> 回到订机票
        
        # 第一次打岔：订机票 -> 查余额
        first_interrupt_result = await self._execute_interruption(
            mock_services, mock_session,
            from_intent="book_flight",
            to_intent="check_balance",
            user_input="先查一下余额"
        )
        assert first_interrupt_result['transfer_occurred'] == True
        
        # 第二次打岔：查余额 -> 查航班状态
        second_interrupt_result = await self._execute_interruption(
            mock_services, mock_session,
            from_intent="check_balance",
            to_intent="check_flight_status",
            user_input="顺便查一下航班状态"
        )
        assert second_interrupt_result['transfer_occurred'] == True
        
        # 第一次返回：查航班状态 -> 查余额
        first_return_result = await self._execute_return(
            mock_services, mock_session,
            from_intent="check_flight_status",
            to_intent="check_balance",
            user_input="好的，继续查余额"
        )
        assert first_return_result['transfer_occurred'] == True
        
        # 第二次返回：查余额 -> 订机票
        second_return_result = await self._execute_return(
            mock_services, mock_session,
            from_intent="check_balance",
            to_intent="book_flight",
            user_input="余额足够，继续订机票"
        )
        assert second_return_result['transfer_occurred'] == True
        
        # 验证最终状态
        mock_services['intent_stack_service'].get_stack_depth.return_value = 1
        stack_depth = await mock_services['intent_stack_service'].get_stack_depth(mock_session.session_id)
        assert stack_depth == 1  # 只剩下原始的订机票意图
    
    @pytest.mark.asyncio
    async def test_timeout_driven_transfer(self, mock_services, mock_session):
        """测试超时驱动的意图转移"""
        # 场景：用户长时间未响应，系统主动转移到超时处理
        user_input = ""  # 空输入表示超时
        
        # 设置超时检测
        timeout_info = {
            "is_timeout": True,
            "last_activity": (datetime.now() - timedelta(minutes=31)).isoformat(),
            "timeout_duration": 1800  # 30分钟
        }
        
        timeout_decision = {
            "should_transfer": True,
            "target_intent": "session_timeout",
            "transfer_type": "timeout",
            "confidence": 1.0,
            "reasoning": "用户会话超时，转移到超时处理流程"
        }
        
        mock_services['conversation_service'].check_timeout.return_value = timeout_info
        mock_services['intent_transfer_service'].evaluate_transfer.return_value = timeout_decision
        mock_services['intent_stack_service'].handle_timeout.return_value = True
        
        # 执行超时处理
        transfer_orchestrator = IntentTransferOrchestrator(mock_services)
        result = await transfer_orchestrator.process_intent_transfer(
            user_input=user_input,
            session=mock_session,
            current_intent="book_flight",
            check_timeout=True
        )
        
        # 验证结果
        assert result['success'] == True
        assert result['transfer_occurred'] == True
        assert result['transfer_type'] == "timeout"
        assert result['timeout_info'] == timeout_info
        assert result['to_intent'] == "session_timeout"
        
        # 验证超时处理
        mock_services['conversation_service'].check_timeout.assert_called_once()
        mock_services['intent_stack_service'].handle_timeout.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_error_recovery_transfer(self, mock_services, mock_session):
        """测试错误恢复的意图转移"""
        # 场景：连续错误后自动转移到错误恢复流程
        user_input = "我要订机票"
        
        # 设置错误历史
        error_history = [
            {"error": "NLU服务不可用", "timestamp": datetime.now().isoformat()},
            {"error": "槽位提取失败", "timestamp": datetime.now().isoformat()},
            {"error": "函数调用超时", "timestamp": datetime.now().isoformat()}
        ]
        
        recovery_decision = {
            "should_transfer": True,
            "target_intent": "error_recovery",
            "transfer_type": "error_recovery",
            "confidence": 1.0,
            "reasoning": "连续错误超过阈值，启动错误恢复流程",
            "error_count": 3
        }
        
        mock_services['conversation_service'].get_error_history.return_value = error_history
        mock_services['intent_transfer_service'].evaluate_transfer.return_value = recovery_decision
        mock_services['intent_stack_service'].initiate_error_recovery.return_value = True
        
        # 执行错误恢复
        transfer_orchestrator = IntentTransferOrchestrator(mock_services)
        result = await transfer_orchestrator.process_intent_transfer(
            user_input=user_input,
            session=mock_session,
            current_intent="book_flight",
            check_errors=True
        )
        
        # 验证结果
        assert result['success'] == True
        assert result['transfer_occurred'] == True
        assert result['transfer_type'] == "error_recovery"
        assert result['error_count'] == 3
        assert result['to_intent'] == "error_recovery"
        
        # 验证错误恢复处理
        mock_services['conversation_service'].get_error_history.assert_called_once()
        mock_services['intent_stack_service'].initiate_error_recovery.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_concurrent_intent_transfers(self, mock_services):
        """测试并发意图转移场景"""
        # 准备多个会话
        sessions = []
        for i in range(3):
            session = MagicMock(spec=Session)
            session.session_id = f"session_{i+1:03d}"
            session.user_id = f"user_{i+1:03d}"
            session.get_context.return_value = {
                "current_intent": "book_flight",
                "slots": {},
                "conversation_state": "collecting_slots"
            }
            sessions.append(session)
        
        # 设置并发转移场景
        transfer_scenarios = [
            ("我要查余额", "check_balance"),
            ("我要取消订单", "cancel_order"),
            ("我要修改行程", "modify_booking")
        ]
        
        # 设置模拟响应
        mock_intents = []
        for intent_name in ["check_balance", "cancel_order", "modify_booking"]:
            intent = MagicMock(spec=Intent)
            intent.intent_name = intent_name
            intent.confidence = 0.9
            mock_intents.append(intent)
        
        mock_services['intent_service'].recognize_intent.side_effect = mock_intents
        
        transfer_decisions = []
        for intent_name in ["check_balance", "cancel_order", "modify_booking"]:
            decision = {
                "should_transfer": True,
                "target_intent": intent_name,
                "transfer_type": "explicit_change",
                "confidence": 0.9,
                "reasoning": f"用户明确要求{intent_name}"
            }
            transfer_decisions.append(decision)
        
        mock_services['intent_transfer_service'].evaluate_transfer.side_effect = transfer_decisions
        
        # 执行并发转移
        transfer_orchestrator = IntentTransferOrchestrator(mock_services)
        tasks = []
        
        for i, (user_input, _) in enumerate(transfer_scenarios):
            task = transfer_orchestrator.process_intent_transfer(
                user_input=user_input,
                session=sessions[i],
                current_intent="book_flight"
            )
            tasks.append(task)
        
        results = await asyncio.gather(*tasks)
        
        # 验证结果
        assert len(results) == 3
        for i, result in enumerate(results):
            assert result['success'] == True
            assert result['transfer_occurred'] == True
            assert result['to_intent'] == transfer_scenarios[i][1]
        
        # 验证服务调用次数
        assert mock_services['intent_service'].recognize_intent.call_count == 3
        assert mock_services['intent_transfer_service'].evaluate_transfer.call_count == 3
    
    async def _execute_interruption(self, mock_services, mock_session, from_intent, to_intent, user_input):
        """执行打岔操作的辅助方法"""
        intent = MagicMock(spec=Intent)
        intent.intent_name = to_intent
        intent.confidence = 0.85
        
        decision = {
            "should_transfer": True,
            "target_intent": to_intent,
            "transfer_type": "interruption",
            "confidence": 0.85,
            "reasoning": f"用户中断{from_intent}转向{to_intent}"
        }
        
        mock_services['intent_service'].recognize_intent.return_value = intent
        mock_services['intent_transfer_service'].evaluate_transfer.return_value = decision
        mock_services['intent_stack_service'].interrupt_current_intent.return_value = {"saved": True}
        mock_services['intent_stack_service'].push_intent.return_value = True
        
        transfer_orchestrator = IntentTransferOrchestrator(mock_services)
        return await transfer_orchestrator.process_intent_transfer(
            user_input=user_input,
            session=mock_session,
            current_intent=from_intent
        )
    
    async def _execute_return(self, mock_services, mock_session, from_intent, to_intent, user_input):
        """执行返回操作的辅助方法"""
        decision = {
            "should_transfer": True,
            "target_intent": to_intent,
            "transfer_type": "return_to_previous",
            "confidence": 0.9,
            "reasoning": f"用户从{from_intent}返回{to_intent}"
        }
        
        mock_services['intent_transfer_service'].evaluate_transfer.return_value = decision
        mock_services['intent_stack_service'].pop_intent.return_value = True
        mock_services['intent_stack_service'].restore_previous_context.return_value = {"restored": True}
        
        transfer_orchestrator = IntentTransferOrchestrator(mock_services)
        return await transfer_orchestrator.process_intent_transfer(
            user_input=user_input,
            session=mock_session,
            current_intent=from_intent
        )


class IntentTransferOrchestrator:
    """意图转移编排器"""
    
    def __init__(self, services):
        self.services = services
    
    async def process_intent_transfer(
        self, 
        user_input: str, 
        session, 
        current_intent: str,
        enable_system_suggestions: bool = False,
        check_timeout: bool = False,
        check_errors: bool = False
    ) -> dict:
        """处理意图转移的完整流程"""
        try:
            # 1. 检查超时
            if check_timeout and not user_input:
                timeout_info = await self.services['conversation_service'].check_timeout(session)
                if timeout_info.get('is_timeout'):
                    return await self._handle_timeout_transfer(session, timeout_info)
            
            # 2. 检查错误历史
            if check_errors:
                error_history = await self.services['conversation_service'].get_error_history(session)
                if len(error_history) >= 3:
                    return await self._handle_error_recovery_transfer(session, error_history)
            
            # 3. 意图识别
            if user_input:
                recognized_intent = await self.services['intent_service'].recognize_intent(user_input)
            else:
                recognized_intent = None
            
            # 4. 获取系统建议
            system_suggestion = None
            if enable_system_suggestions:
                system_suggestion = await self.services['intent_transfer_service'].get_system_suggestion(
                    session, current_intent
                )
            
            # 5. 判断是否需要转移
            transfer_decision = await self.services['intent_transfer_service'].evaluate_transfer(
                current_intent=current_intent,
                user_input=user_input,
                recognized_intent=recognized_intent,
                session_context=session.get_context(),
                system_suggestion=system_suggestion
            )
            
            if not transfer_decision.get('should_transfer'):
                return {
                    'success': True,
                    'transfer_occurred': False,
                    'reason': 'No transfer needed'
                }
            
            # 6. 执行转移
            return await self._execute_transfer(
                session, current_intent, transfer_decision, user_input
            )
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'transfer_occurred': False
            }
    
    async def _handle_timeout_transfer(self, session, timeout_info: dict) -> dict:
        """处理超时转移"""
        await self.services['intent_stack_service'].handle_timeout(session)
        
        return {
            'success': True,
            'transfer_occurred': True,
            'transfer_type': 'timeout',
            'timeout_info': timeout_info,
            'to_intent': 'session_timeout'
        }
    
    async def _handle_error_recovery_transfer(self, session, error_history: list) -> dict:
        """处理错误恢复转移"""
        await self.services['intent_stack_service'].initiate_error_recovery(session)
        
        return {
            'success': True,
            'transfer_occurred': True,
            'transfer_type': 'error_recovery',
            'error_count': len(error_history),
            'to_intent': 'error_recovery'
        }
    
    async def _execute_transfer(self, session, from_intent: str, decision: dict, user_input: str) -> dict:
        """执行意图转移"""
        transfer_type = decision['transfer_type']
        target_intent = decision['target_intent']
        
        result = {
            'success': True,
            'transfer_occurred': True,
            'transfer_type': transfer_type,
            'from_intent': from_intent,
            'to_intent': target_intent,
            'confidence': decision['confidence'],
            'reasoning': decision.get('reasoning', '')
        }
        
        if transfer_type == 'interruption':
            # 打岔：保存当前上下文，推入新意图
            saved_context = await self.services['intent_stack_service'].interrupt_current_intent(
                session, from_intent
            )
            await self.services['intent_stack_service'].push_intent(
                session, target_intent, IntentInterruptionType.USER_INITIATED
            )
            result.update({
                'context_preserved': True,
                'saved_context': saved_context
            })
        
        elif transfer_type == 'explicit_change':
            # 明确切换：直接推入新意图
            await self.services['intent_stack_service'].push_intent(
                session, target_intent, IntentInterruptionType.USER_INITIATED
            )
        
        elif transfer_type == 'context_driven':
            # 上下文驱动：继承相关槽位
            inherited_slots = await self.services['slot_service'].inherit_relevant_slots(
                from_intent, target_intent, session.get_context()
            )
            await self.services['intent_stack_service'].push_intent(
                session, target_intent, IntentInterruptionType.CONTEXT_SWITCH
            )
            result.update({
                'slots_inherited': True,
                'inherited_slots': inherited_slots
            })
        
        elif transfer_type == 'system_suggestion':
            # 系统建议：推入建议的意图
            await self.services['intent_stack_service'].push_intent(
                session, target_intent, IntentInterruptionType.SYSTEM_SUGGESTION
            )
            result.update({
                'suggestion_source': decision.get('suggestion_source', 'system')
            })
        
        elif transfer_type == 'return_to_previous':
            # 返回前一个意图：弹出当前，恢复前一个
            await self.services['intent_stack_service'].pop_intent(session)
            restored_context = await self.services['intent_stack_service'].restore_previous_context(session)
            result.update({
                'context_restored': True,
                'restored_context': restored_context
            })
        
        # 记录转移
        await self.services['conversation_service'].record_intent_transfer(
            session, from_intent, target_intent, transfer_type, decision['confidence']
        )
        
        return result