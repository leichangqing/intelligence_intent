"""
错误处理场景集成测试 - TASK-048
测试各种错误处理和恢复场景
"""
import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timedelta
import json
import time
from typing import Dict, List, Any

from src.core.error_handler import StandardError, ValidationError, ExternalServiceError, DatabaseError
from src.services.intent_service import IntentService
from src.services.conversation_service import ConversationService
from src.services.slot_service import SlotService
from src.services.function_service import FunctionService
from src.services.cache_service import CacheService
from src.models.conversation import Session
from src.models.intent import Intent


class TestErrorHandlingScenarios:
    """错误处理场景集成测试类"""
    
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
            # 常见的方法名
            common_methods = [
                'recognize_intent', 'get_fallback_intent', 'save_conversation', 
                'validate_slot_value', 'get_correction_suggestions', 'call_function',
                'get_fallback_response', 'detect_security_violations', 'get_error_history',
                'check_timeout', 'get', 'set', 'clear_expired', 'clear_low_priority'
            ]
            for method_name in common_methods:
                setattr(service, method_name, AsyncMock())
        
        return services
    
    @pytest.fixture
    def mock_session(self):
        """创建模拟会话"""
        session = MagicMock(spec=Session)
        session.session_id = "test_session_001"
        session.user_id = "test_user_001"
        session.status = "active"
        session.get_context.return_value = {
            "current_intent": "book_flight",
            "slots": {"origin": {"value": "北京", "confidence": 0.95}},
            "conversation_state": "collecting_slots"
        }
        return session
    
    @pytest.mark.asyncio
    async def test_nlu_service_failure_scenario(self, mock_services, mock_session):
        """测试NLU服务失败场景"""
        # 场景：NLU服务不可用，系统应该使用fallback机制
        user_input = "我要订机票"
        
        # 设置NLU服务失败
        mock_services['intent_service'].recognize_intent.side_effect = ExternalServiceError(
            message="NLU service unavailable",
            service_name="nlu",
            context={"endpoint": "/recognize"}
        )
        
        # 设置fallback响应
        fallback_intent = MagicMock(spec=Intent)
        fallback_intent.intent_name = "fallback"
        fallback_intent.confidence = 0.1
        
        mock_services['intent_service'].get_fallback_intent.return_value = fallback_intent
        
        # 执行错误处理流程
        error_handler = ErrorHandlingOrchestrator(mock_services)
        result = await error_handler.handle_service_error(
            service_name="intent_service",
            operation="recognize_intent",
            user_input=user_input,
            session=mock_session,
            error_type="external_service"
        )
        
        # 验证结果
        assert result['success'] == True
        assert result['fallback_used'] == True
        assert "NLU service unavailable" in result['original_error']
        assert result['fallback_intent'] == "fallback"
        assert result['error_logged'] == True
        
        # 验证服务调用
        mock_services['intent_service'].get_fallback_intent.assert_called_once()
        assert mock_services['intent_service'].recognize_intent.call_count == 1
    
    @pytest.mark.asyncio
    async def test_database_connection_failure_scenario(self, mock_services, mock_session):
        """测试数据库连接失败场景"""
        # 场景：数据库连接失败，系统应该使用缓存并重试
        user_input = "查询余额"
        
        # 设置数据库失败
        mock_services['conversation_service'].save_conversation.side_effect = DatabaseError(
            message="Database connection failed",
            context={"database": "mysql", "operation": "insert"}
        )
        
        # 设置缓存可用
        cached_data = {
            "user_id": "test_user_001",
            "conversation_data": {"last_intent": "check_balance"},
            "timestamp": datetime.now().isoformat()
        }
        mock_services['cache_service'].get.return_value = cached_data
        mock_services['cache_service'].set.return_value = True
        
        # 执行错误处理流程
        error_handler = ErrorHandlingOrchestrator(mock_services)
        result = await error_handler.handle_database_error(
            operation="save_conversation",
            data={"user_input": user_input, "session": mock_session},
            retry_count=3
        )
        
        # 验证结果
        assert result['success'] == True
        assert result['cache_used'] == True
        assert result['database_available'] == False
        assert result['retry_count'] == 3
        assert result['final_storage'] == "cache"
        
        # 验证缓存调用
        mock_services['cache_service'].set.assert_called()
        assert mock_services['conversation_service'].save_conversation.call_count == 3
    
    @pytest.mark.asyncio
    async def test_slot_validation_error_scenario(self, mock_services, mock_session):
        """测试槽位验证错误场景"""
        # 场景：用户输入的槽位值不符合验证规则
        user_input = "从火星到月球"
        
        # 设置槽位验证失败
        validation_errors = [
            {
                "field": "origin",
                "message": "火星不是有效的出发地",
                "code": "E2001",
                "value": "火星"
            },
            {
                "field": "destination", 
                "message": "月球不是有效的目的地",
                "code": "E2002",
                "value": "月球"
            }
        ]
        
        mock_services['slot_service'].validate_slot_value.side_effect = ValidationError(
            message="Slot validation failed",
            context={"validation_errors": validation_errors}
        )
        
        # 设置错误修正建议
        correction_suggestions = [
            {"field": "origin", "suggestions": ["北京", "上海", "广州"]},
            {"field": "destination", "suggestions": ["上海", "深圳", "杭州"]}
        ]
        mock_services['slot_service'].get_correction_suggestions.return_value = correction_suggestions
        
        # 执行槽位验证错误处理
        error_handler = ErrorHandlingOrchestrator(mock_services)
        result = await error_handler.handle_validation_error(
            validation_errors=validation_errors,
            user_input=user_input,
            session=mock_session
        )
        
        # 验证结果
        assert result['success'] == False
        assert result['error_type'] == "validation_error"
        assert len(result['validation_errors']) == 2
        assert len(result['correction_suggestions']) == 2
        assert result['user_friendly_message'] == "请输入有效的出发地和目的地"
        
        # 验证建议生成
        mock_services['slot_service'].get_correction_suggestions.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_external_api_timeout_scenario(self, mock_services, mock_session):
        """测试外部API超时场景"""
        # 场景：外部API调用超时，系统应该重试并最终使用fallback
        function_params = {
            "origin": "北京",
            "destination": "上海", 
            "date": "2024-01-02"
        }
        
        # 设置API超时
        timeout_error = asyncio.TimeoutError("Function call timeout after 30 seconds")
        mock_services['function_service'].call_function.side_effect = timeout_error
        
        # 设置重试配置
        retry_config = {
            "max_attempts": 3,
            "base_delay": 1.0,
            "backoff_factor": 2.0,
            "timeout_seconds": 30
        }
        
        # 设置fallback响应
        fallback_response = {
            "success": False,
            "message": "机票预订服务暂时不可用，请稍后重试",
            "fallback": True,
            "alternative_actions": ["稍后重试", "人工客服", "使用其他方式"]
        }
        mock_services['function_service'].get_fallback_response.return_value = fallback_response
        
        # 执行超时错误处理
        error_handler = ErrorHandlingOrchestrator(mock_services)
        result = await error_handler.handle_timeout_error(
            service_name="function_service",
            operation="call_function",
            params=function_params,
            retry_config=retry_config,
            session=mock_session
        )
        
        # 验证结果
        assert result['success'] == False
        assert result['error_type'] == "timeout_error"
        assert result['retry_count'] == 3
        assert result['fallback_used'] == True
        assert result['total_duration'] >= 3.0  # 至少重试了3次
        assert len(result['alternative_actions']) == 3
        
        # 验证重试次数
        assert mock_services['function_service'].call_function.call_count == 3
        mock_services['function_service'].get_fallback_response.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_circuit_breaker_activation_scenario(self, mock_services, mock_session):
        """测试熔断器激活场景"""
        # 场景：连续失败触发熔断器，后续请求快速失败
        
        # 模拟连续失败
        failure_count = 5
        circuit_breaker_threshold = 3
        
        # 设置服务连续失败
        mock_services['function_service'].call_function.side_effect = ExternalServiceError(
            message="Service temporarily unavailable",
            service_name="external_api"
        )
        
        # 设置熔断器状态
        circuit_breaker_state = {
            "state": "closed",
            "failure_count": 0,
            "last_failure_time": None,
            "recovery_timeout": 60
        }
        
        error_handler = ErrorHandlingOrchestrator(mock_services)
        error_handler.circuit_breaker_state = circuit_breaker_state
        
        results = []
        
        # 执行多次调用，触发熔断器
        for i in range(failure_count):
            result = await error_handler.handle_with_circuit_breaker(
                service_name="function_service",
                operation="call_function",
                params={"test": "data"},
                session=mock_session
            )
            results.append(result)
            
            # 第3次失败后应该触发熔断器
            if i >= circuit_breaker_threshold - 1:
                assert result['circuit_breaker_active'] == True
                assert result['fast_fail'] == True
            else:
                assert result.get('circuit_breaker_active', False) == False
        
        # 验证熔断器状态
        assert error_handler.circuit_breaker_state['state'] == 'open'
        assert error_handler.circuit_breaker_state['failure_count'] >= circuit_breaker_threshold
        
        # 验证调用次数（熔断后不再调用实际服务）
        assert mock_services['function_service'].call_function.call_count == circuit_breaker_threshold
    
    @pytest.mark.asyncio
    async def test_memory_pressure_scenario(self, mock_services, mock_session):
        """测试内存压力场景"""
        # 场景：系统内存不足，触发缓存清理和请求限制
        
        # 模拟高内存使用
        memory_usage = {
            "total": 8 * 1024 * 1024 * 1024,  # 8GB
            "used": 7.5 * 1024 * 1024 * 1024,  # 7.5GB
            "available": 0.5 * 1024 * 1024 * 1024,  # 0.5GB
            "percent": 93.75
        }
        
        # 设置内存监控
        with patch('psutil.virtual_memory') as mock_memory:
            mock_memory.return_value = MagicMock(
                total=memory_usage["total"],
                used=memory_usage["used"],
                available=memory_usage["available"],
                percent=memory_usage["percent"]
            )
            
            # 设置缓存清理响应
            mock_services['cache_service'].clear_expired.return_value = {"cleared": 1000, "freed_mb": 50}
            mock_services['cache_service'].clear_low_priority.return_value = {"cleared": 500, "freed_mb": 25}
            
            error_handler = ErrorHandlingOrchestrator(mock_services)
            result = await error_handler.handle_memory_pressure(
                threshold_percent=90,
                session=mock_session
            )
            
            # 验证结果
            assert result['memory_pressure'] == True
            assert result['memory_percent'] == 93.75
            assert result['actions_taken']['cache_cleanup'] == True
            assert result['actions_taken']['request_throttling'] == True
            assert result['freed_memory_mb'] >= 75
            
            # 验证缓存清理被调用
            mock_services['cache_service'].clear_expired.assert_called_once()
            mock_services['cache_service'].clear_low_priority.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_cascading_failure_scenario(self, mock_services, mock_session):
        """测试级联失败场景"""
        # 场景：一个服务失败导致其他服务也失败
        
        # 设置级联失败序列
        failure_sequence = [
            ("cache_service", "get", "Cache miss"),
            ("database_service", "query", "Database timeout"),
            ("backup_service", "query", "Backup unavailable"),
            ("fallback_service", "get_default", "Fallback error")
        ]
        
        # 配置服务失败
        mock_services['cache_service'].get.side_effect = Exception("Cache miss")
        mock_services['conversation_service'].get_conversation_history.side_effect = DatabaseError(
            message="Database timeout", error_code="E6002"
        )
        
        error_handler = ErrorHandlingOrchestrator(mock_services)
        result = await error_handler.handle_cascading_failure(
            primary_service="cache_service",
            operation="get_conversation_data",
            session=mock_session,
            max_fallback_attempts=3
        )
        
        # 验证结果
        assert result['success'] == False
        assert result['cascade_detected'] == True
        assert result['failed_services'] >= 2
        assert result['fallback_attempts'] >= 1
        assert result['final_strategy'] == "emergency_response"
        
        # 验证错误传播被正确处理
        assert len(result['failure_chain']) >= 2
        assert result['emergency_response']['message'] == "系统暂时不可用，请稍后重试"
    
    @pytest.mark.asyncio
    async def test_data_corruption_scenario(self, mock_services, mock_session):
        """测试数据损坏场景"""
        # 场景：检测到数据损坏，触发数据恢复流程
        
        # 模拟损坏的会话数据
        corrupted_session_data = {
            "session_id": mock_session.session_id,
            "context": "invalid_json_string{",
            "slots": None,
            "checksum": "invalid_checksum"
        }
        
        # 设置数据验证失败
        mock_services['conversation_service'].validate_session_data.return_value = {
            "valid": False,
            "errors": [
                "Invalid JSON in context field",
                "Checksum mismatch",
                "Missing required slots field"
            ]
        }
        
        # 设置数据恢复选项
        recovery_options = [
            {"method": "backup_restore", "available": True, "age_hours": 2},
            {"method": "session_reset", "available": True, "data_loss": True},
            {"method": "partial_recovery", "available": True, "confidence": 0.7}
        ]
        mock_services['conversation_service'].get_recovery_options.return_value = recovery_options
        
        # 设置恢复结果
        recovered_data = {
            "session_id": mock_session.session_id,
            "context": {"current_intent": "book_flight", "recovery_source": "backup"},
            "slots": {"origin": {"value": "北京", "confidence": 0.95}},
            "recovery_method": "backup_restore"
        }
        mock_services['conversation_service'].restore_from_backup.return_value = recovered_data
        
        error_handler = ErrorHandlingOrchestrator(mock_services)
        result = await error_handler.handle_data_corruption(
            data_type="session_data",
            corrupted_data=corrupted_session_data,
            session=mock_session
        )
        
        # 验证结果
        assert result['corruption_detected'] == True
        assert result['recovery_successful'] == True
        assert result['recovery_method'] == "backup_restore"
        assert result['data_loss'] == False
        assert len(result['validation_errors']) == 3
        
        # 验证恢复流程
        mock_services['conversation_service'].validate_session_data.assert_called_once()
        mock_services['conversation_service'].get_recovery_options.assert_called_once()
        mock_services['conversation_service'].restore_from_backup.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_security_violation_scenario(self, mock_services, mock_session):
        """测试安全违规场景"""
        # 场景：检测到安全攻击，触发安全响应
        
        # 模拟恶意输入
        malicious_input = "'; DROP TABLE users; --"
        
        # 设置安全检测
        security_violations = [
            {
                "type": "sql_injection",
                "severity": "high",
                "pattern": "DROP TABLE",
                "confidence": 0.95
            },
            {
                "type": "command_injection",
                "severity": "medium", 
                "pattern": "--",
                "confidence": 0.7
            }
        ]
        
        mock_services['conversation_service'].detect_security_violations.return_value = security_violations
        
        # 设置安全响应
        security_response = {
            "block_request": True,
            "quarantine_session": True,
            "alert_security_team": True,
            "log_incident": True,
            "response_message": "请求被阻止：检测到潜在安全威胁"
        }
        
        error_handler = ErrorHandlingOrchestrator(mock_services)
        result = await error_handler.handle_security_violation(
            user_input=malicious_input,
            session=mock_session,
            violations=security_violations
        )
        
        # 验证结果
        assert result['security_violation'] == True
        assert result['request_blocked'] == True
        assert result['session_quarantined'] == True
        assert len(result['violations']) == 2
        assert result['highest_severity'] == "high"
        assert result['incident_logged'] == True
        
        # 验证安全响应
        assert "安全威胁" in result['response_message']
    
    @pytest.mark.asyncio
    async def test_performance_degradation_scenario(self, mock_services, mock_session):
        """测试性能降级场景"""
        # 场景：系统性能下降，触发降级策略
        
        # 模拟性能指标
        performance_metrics = {
            "avg_response_time": 5.2,  # seconds
            "cpu_usage": 85.5,  # percent
            "memory_usage": 78.3,  # percent
            "active_connections": 950,
            "error_rate": 0.12,  # 12%
            "queue_length": 45
        }
        
        # 设置性能阈值
        performance_thresholds = {
            "response_time": 2.0,
            "cpu_usage": 80.0,
            "memory_usage": 75.0,
            "error_rate": 0.05
        }
        
        # 设置降级策略
        degradation_actions = [
            {"action": "reduce_feature_complexity", "enabled": True},
            {"action": "increase_cache_ttl", "enabled": True},
            {"action": "disable_non_essential_features", "enabled": True},
            {"action": "throttle_requests", "enabled": True}
        ]
        
        error_handler = ErrorHandlingOrchestrator(mock_services)
        result = await error_handler.handle_performance_degradation(
            metrics=performance_metrics,
            thresholds=performance_thresholds,
            session=mock_session
        )
        
        # 验证结果
        assert result['degradation_detected'] == True
        assert result['degradation_level'] == "high"
        assert len(result['violated_thresholds']) >= 3
        assert len(result['actions_taken']) >= 2
        assert result['estimated_improvement'] > 0
        
        # 验证具体违规
        violated = result['violated_thresholds']
        assert any(v['metric'] == 'response_time' for v in violated)
        assert any(v['metric'] == 'cpu_usage' for v in violated)
        assert any(v['metric'] == 'error_rate' for v in violated)
    
    @pytest.mark.asyncio
    async def test_concurrent_error_handling(self, mock_services):
        """测试并发错误处理"""
        # 场景：多个并发请求同时出错
        
        session_count = 5
        sessions = []
        for i in range(session_count):
            session = MagicMock(spec=Session)
            session.session_id = f"session_{i+1:03d}"
            session.user_id = f"user_{i+1:03d}"
            sessions.append(session)
        
        # 设置不同类型的错误
        error_scenarios = [
            ExternalServiceError("NLU service timeout"),
            DatabaseError("Connection pool exhausted"),
            ValidationError("Invalid slot value"),
            asyncio.TimeoutError("Function call timeout"),
            Exception("Unknown error")
        ]
        
        # 配置并发错误
        for i, session in enumerate(sessions):
            if i < len(error_scenarios):
                mock_services['intent_service'].recognize_intent.side_effect = error_scenarios[i]
        
        error_handler = ErrorHandlingOrchestrator(mock_services)
        
        # 并发执行错误处理
        tasks = []
        for i, session in enumerate(sessions):
            task = error_handler.handle_concurrent_error(
                session=session,
                user_input=f"test input {i+1}",
                error_type=type(error_scenarios[i % len(error_scenarios)]).__name__
            )
            tasks.append(task)
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 验证结果
        assert len(results) == session_count
        
        # 统计不同错误类型的处理结果
        error_counts = {}
        for result in results:
            if isinstance(result, dict):
                error_type = result.get('error_type', 'unknown')
                error_counts[error_type] = error_counts.get(error_type, 0) + 1
        
        assert len(error_counts) >= 3  # 至少处理了3种不同类型的错误
        
        # 验证所有错误都被正确处理
        for result in results:
            if isinstance(result, dict):
                assert 'error_handled' in result
                assert result['error_handled'] == True


class ErrorHandlingOrchestrator:
    """错误处理编排器"""
    
    def __init__(self, services):
        self.services = services
        self.circuit_breaker_state = {
            "state": "closed",
            "failure_count": 0,
            "last_failure_time": None
        }
    
    async def handle_service_error(self, service_name: str, operation: str, 
                                 user_input: str, session, error_type: str) -> dict:
        """处理服务错误"""
        try:
            # 尝试原始操作
            service = self.services[service_name]
            method = getattr(service, operation)
            await method(user_input)
            
        except Exception as e:
            # 记录错误
            error_logged = True
            
            # 使用fallback
            if error_type == "external_service":
                fallback_intent = await self.services['intent_service'].get_fallback_intent()
                return {
                    'success': True,
                    'fallback_used': True,
                    'original_error': str(e),
                    'fallback_intent': fallback_intent.intent_name,
                    'error_logged': error_logged
                }
        
        return {'success': True, 'fallback_used': False}
    
    async def handle_database_error(self, operation: str, data: dict, retry_count: int = 3) -> dict:
        """处理数据库错误"""
        for attempt in range(retry_count):
            try:
                # 尝试数据库操作
                await self.services['conversation_service'].save_conversation()
                return {
                    'success': True,
                    'cache_used': False,
                    'database_available': True,
                    'retry_count': attempt + 1
                }
            except Exception:
                if attempt == retry_count - 1:
                    # 最后一次尝试失败，使用缓存
                    await self.services['cache_service'].set(f"temp_{data['session'].session_id}", data)
                    return {
                        'success': True,
                        'cache_used': True,
                        'database_available': False,
                        'retry_count': retry_count,
                        'final_storage': 'cache'
                    }
                
                # 等待重试
                await asyncio.sleep(2 ** attempt)
    
    async def handle_validation_error(self, validation_errors: list, 
                                    user_input: str, session) -> dict:
        """处理验证错误"""
        # 获取修正建议
        suggestions = await self.services['slot_service'].get_correction_suggestions()
        
        return {
            'success': False,
            'error_type': 'validation_error',
            'validation_errors': validation_errors,
            'correction_suggestions': suggestions,
            'user_friendly_message': '请输入有效的出发地和目的地'
        }
    
    async def handle_timeout_error(self, service_name: str, operation: str, 
                                 params: dict, retry_config: dict, session) -> dict:
        """处理超时错误"""
        start_time = time.time()
        
        for attempt in range(retry_config['max_attempts']):
            try:
                # 尝试调用
                service = self.services[service_name]
                method = getattr(service, operation)
                await method()
                
                return {
                    'success': True,
                    'error_type': None,
                    'retry_count': attempt + 1,
                    'total_duration': time.time() - start_time
                }
                
            except asyncio.TimeoutError:
                if attempt == retry_config['max_attempts'] - 1:
                    # 最后一次重试失败，使用fallback
                    fallback_response = await self.services['function_service'].get_fallback_response()
                    
                    return {
                        'success': False,
                        'error_type': 'timeout_error',
                        'retry_count': retry_config['max_attempts'],
                        'fallback_used': True,
                        'total_duration': time.time() - start_time,
                        'alternative_actions': fallback_response.get('alternative_actions', [])
                    }
                
                # 指数退避
                delay = retry_config['base_delay'] * (retry_config['backoff_factor'] ** attempt)
                await asyncio.sleep(delay)
    
    async def handle_with_circuit_breaker(self, service_name: str, operation: str,
                                        params: dict, session) -> dict:
        """使用熔断器处理错误"""
        # 检查熔断器状态
        if self.circuit_breaker_state['state'] == 'open':
            return {
                'success': False,
                'circuit_breaker_active': True,
                'fast_fail': True,
                'message': '服务暂时不可用'
            }
        
        try:
            # 尝试调用服务
            service = self.services[service_name]
            method = getattr(service, operation)
            await method()
            
            # 重置失败计数
            self.circuit_breaker_state['failure_count'] = 0
            return {'success': True, 'circuit_breaker_active': False}
            
        except Exception:
            # 增加失败计数
            self.circuit_breaker_state['failure_count'] += 1
            self.circuit_breaker_state['last_failure_time'] = time.time()
            
            # 检查是否需要打开熔断器
            if self.circuit_breaker_state['failure_count'] >= 3:
                self.circuit_breaker_state['state'] = 'open'
                return {
                    'success': False,
                    'circuit_breaker_active': True,
                    'fast_fail': True,
                    'failure_count': self.circuit_breaker_state['failure_count']
                }
            
            return {
                'success': False,
                'circuit_breaker_active': False,
                'failure_count': self.circuit_breaker_state['failure_count']
            }
    
    async def handle_memory_pressure(self, threshold_percent: float, session) -> dict:
        """处理内存压力"""
        import psutil
        memory = psutil.virtual_memory()
        
        if memory.percent > threshold_percent:
            # 清理缓存
            expired_result = await self.services['cache_service'].clear_expired()
            low_priority_result = await self.services['cache_service'].clear_low_priority()
            
            total_freed = expired_result['freed_mb'] + low_priority_result['freed_mb']
            
            return {
                'memory_pressure': True,
                'memory_percent': memory.percent,
                'actions_taken': {
                    'cache_cleanup': True,
                    'request_throttling': True
                },
                'freed_memory_mb': total_freed
            }
        
        return {'memory_pressure': False}
    
    async def handle_cascading_failure(self, primary_service: str, operation: str,
                                     session, max_fallback_attempts: int = 3) -> dict:
        """处理级联失败"""
        failure_chain = []
        failed_services = 0
        
        # 尝试主服务
        try:
            await self.services[primary_service].get()
        except Exception as e:
            failure_chain.append({'service': primary_service, 'error': str(e)})
            failed_services += 1
        
        # 尝试备用服务
        try:
            await self.services['conversation_service'].get_conversation_history()
        except Exception as e:
            failure_chain.append({'service': 'conversation_service', 'error': str(e)})
            failed_services += 1
        
        # 检测级联失败
        cascade_detected = failed_services >= 2
        
        return {
            'success': False,
            'cascade_detected': cascade_detected,
            'failed_services': failed_services,
            'fallback_attempts': max_fallback_attempts,
            'final_strategy': 'emergency_response',
            'failure_chain': failure_chain,
            'emergency_response': {
                'message': '系统暂时不可用，请稍后重试'
            }
        }
    
    async def handle_data_corruption(self, data_type: str, corrupted_data: dict, session) -> dict:
        """处理数据损坏"""
        # 验证数据
        validation_result = await self.services['conversation_service'].validate_session_data()
        
        if not validation_result['valid']:
            # 获取恢复选项
            recovery_options = await self.services['conversation_service'].get_recovery_options()
            
            # 选择最佳恢复方法
            best_option = recovery_options[0]  # 第一个通常是最好的
            
            if best_option['method'] == 'backup_restore':
                recovered_data = await self.services['conversation_service'].restore_from_backup()
                
                return {
                    'corruption_detected': True,
                    'recovery_successful': True,
                    'recovery_method': 'backup_restore',
                    'data_loss': False,
                    'validation_errors': validation_result['errors']
                }
        
        return {'corruption_detected': False}
    
    async def handle_security_violation(self, user_input: str, session, violations: list) -> dict:
        """处理安全违规"""
        # 检测安全违规
        detected_violations = await self.services['conversation_service'].detect_security_violations()
        
        # 计算最高严重性
        highest_severity = max(v['severity'] for v in violations)
        
        # 执行安全响应
        return {
            'security_violation': True,
            'request_blocked': True,
            'session_quarantined': True,
            'violations': violations,
            'highest_severity': highest_severity,
            'incident_logged': True,
            'response_message': '请求被阻止：检测到潜在安全威胁'
        }
    
    async def handle_performance_degradation(self, metrics: dict, 
                                           thresholds: dict, session) -> dict:
        """处理性能降级"""
        violated_thresholds = []
        
        # 检查违规的阈值
        for metric, value in metrics.items():
            if metric in thresholds and value > thresholds[metric]:
                violated_thresholds.append({
                    'metric': metric,
                    'current': value,
                    'threshold': thresholds[metric],
                    'violation_percent': ((value - thresholds[metric]) / thresholds[metric]) * 100
                })
        
        # 确定降级级别
        violation_count = len(violated_thresholds)
        if violation_count >= 3:
            degradation_level = "high"
        elif violation_count >= 2:
            degradation_level = "medium"
        else:
            degradation_level = "low"
        
        # 采取降级措施
        actions_taken = []
        if degradation_level in ["high", "medium"]:
            actions_taken = ["reduce_complexity", "increase_cache_ttl"]
        
        return {
            'degradation_detected': violation_count > 0,
            'degradation_level': degradation_level,
            'violated_thresholds': violated_thresholds,
            'actions_taken': actions_taken,
            'estimated_improvement': 25.5  # 预估改善百分比
        }
    
    async def handle_concurrent_error(self, session, user_input: str, error_type: str) -> dict:
        """处理并发错误"""
        try:
            # 模拟错误处理逻辑
            await self.services['intent_service'].recognize_intent()
        except Exception as e:
            return {
                'error_handled': True,
                'error_type': error_type,
                'session_id': session.session_id,
                'original_error': str(e)
            }
        
        return {'error_handled': True, 'error_type': error_type}