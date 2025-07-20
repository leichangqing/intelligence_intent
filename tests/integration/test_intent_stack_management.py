"""
意图栈管理集成测试
测试复杂的意图栈操作和管理场景
"""
import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timedelta
import json

from src.services.intent_stack_service import IntentStackService, IntentStackStatus, IntentInterruptionType
from src.services.intent_service import IntentService
from src.services.conversation_service import ConversationService
from src.services.slot_service import SlotService
from src.services.cache_service import CacheService
from src.models.conversation import Session
from src.models.intent import Intent


class TestIntentStackManagement:
    """意图栈管理集成测试类"""
    
    @pytest.fixture
    def mock_services(self):
        """创建模拟服务"""
        services = {
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
        return session
    
    @pytest.mark.asyncio
    async def test_stack_push_and_pop_operations(self, mock_services, mock_session):
        """测试栈的基本推入和弹出操作"""
        stack_manager = IntentStackManager(mock_services)
        
        # 测试推入多个意图
        intents = ["book_flight", "check_balance", "check_flight_status"]
        
        for i, intent in enumerate(intents):
            result = await stack_manager.push_intent(
                session=mock_session,
                intent_name=intent,
                interruption_type=IntentInterruptionType.USER_INITIATED,
                context={"step": i+1}
            )
            assert result['success'] == True
            assert result['intent'] == intent
            assert result['stack_depth'] == i + 1
        
        # 测试弹出操作
        for i in range(len(intents)):
            expected_depth = len(intents) - i - 1
            result = await stack_manager.pop_intent(mock_session)
            assert result['success'] == True
            assert result['stack_depth'] == expected_depth
        
        # 验证服务调用
        assert mock_services['intent_stack_service'].push_intent.call_count == 3
        assert mock_services['intent_stack_service'].pop_intent.call_count == 3
    
    @pytest.mark.asyncio
    async def test_stack_overflow_protection(self, mock_services, mock_session):
        """测试栈溢出保护机制"""
        stack_manager = IntentStackManager(mock_services)
        
        # 设置栈深度限制
        max_depth = 5
        mock_services['intent_stack_service'].get_max_stack_depth.return_value = max_depth
        mock_services['intent_stack_service'].get_stack_depth.return_value = max_depth
        
        # 尝试超过限制的推入操作
        mock_services['intent_stack_service'].push_intent.side_effect = [
            {"success": True, "stack_depth": 1},
            {"success": True, "stack_depth": 2}, 
            {"success": True, "stack_depth": 3},
            {"success": True, "stack_depth": 4},
            {"success": True, "stack_depth": 5},
            {"success": False, "error": "Stack overflow", "stack_depth": 5}
        ]
        
        # 推入6个意图，第6个应该失败
        for i in range(6):
            result = await stack_manager.push_intent(
                session=mock_session,
                intent_name=f"intent_{i+1}",
                interruption_type=IntentInterruptionType.USER_INITIATED
            )
            
            if i < 5:
                assert result['success'] == True
                assert result['stack_depth'] == i + 1
            else:
                assert result['success'] == False
                assert 'Stack overflow' in result['error']
                assert result['stack_depth'] == 5
        
        # 验证栈深度检查被调用
        mock_services['intent_stack_service'].get_stack_depth.assert_called()
    
    @pytest.mark.asyncio
    async def test_intent_interruption_and_resume(self, mock_services, mock_session):
        """测试意图中断和恢复流程"""
        stack_manager = IntentStackManager(mock_services)
        
        # 设置初始意图上下文
        initial_context = {
            "intent": "book_flight",
            "slots": {
                "origin": {"value": "北京", "confidence": 0.95},
                "destination": {"value": "上海", "confidence": 0.9}
            },
            "progress": 0.6,
            "timestamp": datetime.now().isoformat()
        }
        
        # 执行中断操作
        mock_services['intent_stack_service'].interrupt_current_intent.return_value = initial_context
        mock_services['intent_stack_service'].push_intent.return_value = {"success": True, "stack_depth": 2}
        
        interrupt_result = await stack_manager.interrupt_current_intent(
            session=mock_session,
            interrupting_intent="check_balance",
            interruption_type=IntentInterruptionType.USER_INITIATED,
            reason="用户主动查询余额"
        )
        
        # 验证中断结果
        assert interrupt_result['success'] == True
        assert interrupt_result['interrupted_intent'] == "book_flight"
        assert interrupt_result['interrupting_intent'] == "check_balance"
        assert interrupt_result['saved_context'] == initial_context
        
        # 完成中断任务后恢复
        mock_services['intent_stack_service'].pop_intent.return_value = {"success": True}
        mock_services['intent_stack_service'].restore_previous_context.return_value = initial_context
        
        resume_result = await stack_manager.resume_interrupted_intent(
            session=mock_session,
            completion_data={"balance": 50000}
        )
        
        # 验证恢复结果
        assert resume_result['success'] == True
        assert resume_result['resumed_intent'] == "book_flight"
        assert resume_result['restored_context'] == initial_context
        assert resume_result['completion_data']['balance'] == 50000
        
        # 验证服务调用
        mock_services['intent_stack_service'].interrupt_current_intent.assert_called_once()
        mock_services['intent_stack_service'].restore_previous_context.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_context_preservation_across_stack_operations(self, mock_services, mock_session):
        """测试栈操作中的上下文保持"""
        stack_manager = IntentStackManager(mock_services)
        
        # 创建多层上下文
        contexts = [
            {
                "intent": "book_flight",
                "slots": {"origin": {"value": "北京", "confidence": 0.95}},
                "progress": 0.3
            },
            {
                "intent": "check_balance", 
                "slots": {"account": {"value": "主账户", "confidence": 0.9}},
                "progress": 0.8
            },
            {
                "intent": "check_flight_status",
                "slots": {"flight_number": {"value": "CA1234", "confidence": 0.95}},
                "progress": 0.1
            }
        ]
        
        # 模拟推入操作保存上下文
        push_results = []
        for i, context in enumerate(contexts):
            mock_services['intent_stack_service'].push_intent.return_value = {
                "success": True,
                "stack_depth": i + 1,
                "saved_context": context
            }
            
            result = await stack_manager.push_intent(
                session=mock_session,
                intent_name=context["intent"],
                interruption_type=IntentInterruptionType.USER_INITIATED,
                context=context
            )
            push_results.append(result)
        
        # 验证上下文保存
        for i, result in enumerate(push_results):
            assert result['success'] == True
            assert result['saved_context'] == contexts[i]
        
        # 模拟弹出操作恢复上下文
        pop_results = []
        for i in range(len(contexts)):
            context_to_restore = contexts[len(contexts) - 1 - i]
            mock_services['intent_stack_service'].pop_intent.return_value = {
                "success": True,
                "restored_context": context_to_restore
            }
            
            result = await stack_manager.pop_intent(mock_session)
            pop_results.append(result)
        
        # 验证上下文恢复
        for i, result in enumerate(pop_results):
            expected_context = contexts[len(contexts) - 1 - i]
            assert result['success'] == True
            assert result['restored_context'] == expected_context
    
    @pytest.mark.asyncio
    async def test_stack_state_persistence(self, mock_services, mock_session):
        """测试栈状态持久化"""
        stack_manager = IntentStackManager(mock_services)
        
        # 设置栈状态
        stack_state = {
            "session_id": "test_session_001",
            "stack": [
                {
                    "intent": "book_flight",
                    "status": IntentStackStatus.INTERRUPTED,
                    "context": {"slots": {"origin": "北京"}},
                    "created_at": datetime.now().isoformat()
                },
                {
                    "intent": "check_balance",
                    "status": IntentStackStatus.ACTIVE,
                    "context": {"slots": {"account": "主账户"}},
                    "created_at": datetime.now().isoformat()
                }
            ],
            "depth": 2,
            "last_updated": datetime.now().isoformat()
        }
        
        # 测试保存栈状态
        mock_services['intent_stack_service'].save_stack_state.return_value = {"success": True}
        
        save_result = await stack_manager.save_stack_state(mock_session, stack_state)
        assert save_result['success'] == True
        
        # 测试加载栈状态
        mock_services['intent_stack_service'].load_stack_state.return_value = stack_state
        
        load_result = await stack_manager.load_stack_state(mock_session)
        assert load_result == stack_state
        assert load_result['depth'] == 2
        assert len(load_result['stack']) == 2
        
        # 验证缓存操作
        mock_services['cache_service'].set.assert_called()
        mock_services['cache_service'].get.assert_called()
    
    @pytest.mark.asyncio
    async def test_stack_expiration_and_cleanup(self, mock_services, mock_session):
        """测试栈过期和清理机制"""
        stack_manager = IntentStackManager(mock_services)
        
        # 设置过期的栈状态
        expired_time = datetime.now() - timedelta(hours=2)
        expired_stack_state = {
            "session_id": "test_session_001",
            "stack": [
                {
                    "intent": "book_flight",
                    "status": IntentStackStatus.INTERRUPTED,
                    "created_at": expired_time.isoformat(),
                    "expires_at": (expired_time + timedelta(hours=1)).isoformat()
                }
            ],
            "last_updated": expired_time.isoformat()
        }
        
        # 测试过期检测
        mock_services['intent_stack_service'].is_stack_expired.return_value = True
        mock_services['intent_stack_service'].cleanup_expired_stack.return_value = {"cleaned": True}
        
        cleanup_result = await stack_manager.cleanup_expired_intents(mock_session)
        
        assert cleanup_result['cleaned'] == True
        
        # 验证清理操作
        mock_services['intent_stack_service'].is_stack_expired.assert_called_once()
        mock_services['intent_stack_service'].cleanup_expired_stack.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_stack_recovery_from_corruption(self, mock_services, mock_session):
        """测试栈数据损坏恢复机制"""
        stack_manager = IntentStackManager(mock_services)
        
        # 模拟损坏的栈数据
        corrupted_data = {"invalid": "data", "missing_required_fields": True}
        
        mock_services['intent_stack_service'].load_stack_state.side_effect = [
            Exception("Stack data corrupted"),
            None  # 恢复后返回None表示空栈
        ]
        
        mock_services['intent_stack_service'].recover_corrupted_stack.return_value = {
            "recovered": True,
            "backup_found": False,
            "reset_to_empty": True
        }
        
        # 尝试加载损坏的栈
        recovery_result = await stack_manager.load_stack_state(mock_session)
        
        # 验证恢复结果
        assert recovery_result is None  # 恢复后的空栈
        
        # 验证恢复流程被调用
        mock_services['intent_stack_service'].recover_corrupted_stack.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_concurrent_stack_operations(self, mock_services):
        """测试并发栈操作"""
        stack_manager = IntentStackManager(mock_services)
        
        # 创建多个会话
        sessions = []
        for i in range(3):
            session = MagicMock(spec=Session)
            session.session_id = f"session_{i+1:03d}"
            session.user_id = f"user_{i+1:03d}"
            sessions.append(session)
        
        # 并发推入操作
        push_tasks = []
        for i, session in enumerate(sessions):
            mock_services['intent_stack_service'].push_intent.return_value = {
                "success": True,
                "stack_depth": 1
            }
            
            task = stack_manager.push_intent(
                session=session,
                intent_name=f"intent_{i+1}",
                interruption_type=IntentInterruptionType.USER_INITIATED
            )
            push_tasks.append(task)
        
        push_results = await asyncio.gather(*push_tasks)
        
        # 验证并发推入结果
        assert len(push_results) == 3
        for result in push_results:
            assert result['success'] == True
            assert result['stack_depth'] == 1
        
        # 并发弹出操作
        pop_tasks = []
        for session in sessions:
            mock_services['intent_stack_service'].pop_intent.return_value = {
                "success": True,
                "stack_depth": 0
            }
            
            task = stack_manager.pop_intent(session)
            pop_tasks.append(task)
        
        pop_results = await asyncio.gather(*pop_tasks)
        
        # 验证并发弹出结果
        assert len(pop_results) == 3
        for result in pop_results:
            assert result['success'] == True
            assert result['stack_depth'] == 0
        
        # 验证服务调用次数
        assert mock_services['intent_stack_service'].push_intent.call_count == 3
        assert mock_services['intent_stack_service'].pop_intent.call_count == 3
    
    @pytest.mark.asyncio
    async def test_stack_metrics_collection(self, mock_services, mock_session):
        """测试栈指标收集"""
        stack_manager = IntentStackManager(mock_services)
        
        # 设置指标数据
        metrics = {
            "total_pushes": 150,
            "total_pops": 145,
            "average_stack_depth": 2.3,
            "max_stack_depth_reached": 4,
            "interruption_frequency": 0.35,
            "most_interrupted_intent": "book_flight",
            "average_intent_duration": 180.5,  # seconds
            "stack_operations_per_session": 5.2
        }
        
        mock_services['intent_stack_service'].get_stack_metrics.return_value = metrics
        
        # 收集指标
        collected_metrics = await stack_manager.collect_stack_metrics(mock_session)
        
        # 验证指标
        assert collected_metrics == metrics
        assert collected_metrics['total_pushes'] == 150
        assert collected_metrics['average_stack_depth'] == 2.3
        assert collected_metrics['most_interrupted_intent'] == "book_flight"
        
        # 验证指标收集调用
        mock_services['intent_stack_service'].get_stack_metrics.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_stack_debugging_and_diagnostics(self, mock_services, mock_session):
        """测试栈调试和诊断功能"""
        stack_manager = IntentStackManager(mock_services)
        
        # 设置诊断数据
        diagnostic_info = {
            "stack_health": "healthy",
            "potential_issues": [],
            "stack_trace": [
                {"intent": "book_flight", "status": "interrupted", "depth": 0},
                {"intent": "check_balance", "status": "active", "depth": 1}
            ],
            "memory_usage": "2.1MB",
            "cache_hit_rate": 0.85,
            "last_operation": "push_intent",
            "operation_timestamp": datetime.now().isoformat()
        }
        
        mock_services['intent_stack_service'].get_stack_diagnostics.return_value = diagnostic_info
        
        # 获取诊断信息
        diagnostics = await stack_manager.get_stack_diagnostics(mock_session)
        
        # 验证诊断结果
        assert diagnostics == diagnostic_info
        assert diagnostics['stack_health'] == "healthy"
        assert len(diagnostics['stack_trace']) == 2
        assert diagnostics['cache_hit_rate'] == 0.85
        
        # 验证诊断调用
        mock_services['intent_stack_service'].get_stack_diagnostics.assert_called_once()


class IntentStackManager:
    """意图栈管理器"""
    
    def __init__(self, services):
        self.services = services
    
    async def push_intent(
        self, 
        session, 
        intent_name: str, 
        interruption_type: IntentInterruptionType,
        context: dict = None
    ) -> dict:
        """推入新意图到栈"""
        try:
            # 检查栈深度限制
            current_depth = await self.services['intent_stack_service'].get_stack_depth(session.session_id)
            max_depth = await self.services['intent_stack_service'].get_max_stack_depth()
            
            if current_depth >= max_depth:
                return {
                    'success': False,
                    'error': 'Stack overflow',
                    'stack_depth': current_depth
                }
            
            # 执行推入操作
            result = await self.services['intent_stack_service'].push_intent(
                session, intent_name, interruption_type, context
            )
            
            return {
                'success': True,
                'intent': intent_name,
                'stack_depth': result.get('stack_depth', current_depth + 1),
                'saved_context': result.get('saved_context')
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    async def pop_intent(self, session) -> dict:
        """从栈弹出意图"""
        try:
            result = await self.services['intent_stack_service'].pop_intent(session)
            
            return {
                'success': True,
                'stack_depth': result.get('stack_depth', 0),
                'restored_context': result.get('restored_context')
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    async def interrupt_current_intent(
        self, 
        session, 
        interrupting_intent: str,
        interruption_type: IntentInterruptionType,
        reason: str = None
    ) -> dict:
        """中断当前意图"""
        try:
            # 保存当前意图上下文
            saved_context = await self.services['intent_stack_service'].interrupt_current_intent(
                session, session.get_context().get('current_intent')
            )
            
            # 推入中断意图
            await self.services['intent_stack_service'].push_intent(
                session, interrupting_intent, interruption_type
            )
            
            return {
                'success': True,
                'interrupted_intent': session.get_context().get('current_intent'),
                'interrupting_intent': interrupting_intent,
                'saved_context': saved_context,
                'reason': reason
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    async def resume_interrupted_intent(self, session, completion_data: dict = None) -> dict:
        """恢复被中断的意图"""
        try:
            # 弹出当前意图
            await self.services['intent_stack_service'].pop_intent(session)
            
            # 恢复前一个意图的上下文
            restored_context = await self.services['intent_stack_service'].restore_previous_context(session)
            
            return {
                'success': True,
                'resumed_intent': restored_context.get('intent'),
                'restored_context': restored_context,
                'completion_data': completion_data or {}
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    async def save_stack_state(self, session, stack_state: dict) -> dict:
        """保存栈状态"""
        try:
            await self.services['intent_stack_service'].save_stack_state(session, stack_state)
            await self.services['cache_service'].set(
                f"stack_state:{session.session_id}",
                stack_state,
                ttl=3600
            )
            
            return {'success': True}
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    async def load_stack_state(self, session):
        """加载栈状态"""
        try:
            return await self.services['intent_stack_service'].load_stack_state(session)
            
        except Exception as e:
            # 尝试从损坏中恢复
            await self.services['intent_stack_service'].recover_corrupted_stack(session)
            return None
    
    async def cleanup_expired_intents(self, session) -> dict:
        """清理过期意图"""
        try:
            is_expired = await self.services['intent_stack_service'].is_stack_expired(session)
            
            if is_expired:
                result = await self.services['intent_stack_service'].cleanup_expired_stack(session)
                return result
            
            return {'cleaned': False, 'reason': 'Not expired'}
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    async def collect_stack_metrics(self, session) -> dict:
        """收集栈指标"""
        return await self.services['intent_stack_service'].get_stack_metrics(session)
    
    async def get_stack_diagnostics(self, session) -> dict:
        """获取栈诊断信息"""
        return await self.services['intent_stack_service'].get_stack_diagnostics(session)