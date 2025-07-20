"""
核心服务集成测试套件
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import asyncio
from typing import Dict, List, Optional, Any

from src.services.intent_service import IntentService
from src.services.conversation_service import ConversationService
from src.services.slot_service import SlotService
from src.services.function_service import FunctionService
from src.services.query_processor import QueryProcessor
from src.services.cache_service import CacheService


class TestCoreServicesIntegration:
    """核心服务集成测试"""
    
    @pytest.fixture
    def mock_cache_service(self):
        """模拟缓存服务"""
        cache_service = AsyncMock(spec=CacheService)
        cache_service.get.return_value = None
        cache_service.set.return_value = True
        cache_service.delete.return_value = True
        return cache_service
    
    @pytest.fixture
    def mock_nlu_engine(self):
        """模拟NLU引擎"""
        engine = AsyncMock()
        engine.extract_intent.return_value = {
            "intent": "book_flight",
            "confidence": 0.9,
            "entities": []
        }
        engine.extract_slots.return_value = {
            "destination": {
                "value": "北京",
                "confidence": 0.9,
                "source": "llm"
            }
        }
        return engine
    
    @pytest.fixture
    def mock_ragflow_service(self):
        """模拟RAGFLOW服务"""
        service = AsyncMock()
        service.query.return_value = {
            "answer": "测试答案",
            "confidence": 0.8
        }
        return service
    
    @pytest.fixture
    def intent_service(self, mock_cache_service, mock_nlu_engine):
        """创建意图服务"""
        with patch('src.services.intent_service.settings'):
            return IntentService(mock_cache_service, mock_nlu_engine)
    
    @pytest.fixture
    def conversation_service(self, mock_cache_service, mock_ragflow_service):
        """创建对话服务"""
        with patch('src.services.conversation_service.get_fallback_manager'), \
             patch('src.services.conversation_service.get_decision_engine'):
            return ConversationService(mock_cache_service, mock_ragflow_service)
    
    @pytest.fixture
    def slot_service(self, mock_cache_service, mock_nlu_engine):
        """创建槽位服务"""
        return SlotService(mock_cache_service, mock_nlu_engine)
    
    @pytest.fixture
    def function_service(self, mock_cache_service):
        """创建功能服务"""
        with patch('src.services.function_service.get_function_registry'), \
             patch('src.services.function_service.get_api_wrapper_manager'), \
             patch('src.services.function_service.get_parameter_validator'), \
             patch('src.services.function_service.get_parameter_mapper'):
            return FunctionService(mock_cache_service)
    
    @pytest.fixture
    def query_processor(self, mock_cache_service):
        """创建查询处理器"""
        return QueryProcessor(mock_cache_service)
    
    @pytest.mark.asyncio
    async def test_intent_and_slot_integration(self, intent_service, slot_service):
        """测试意图服务和槽位服务集成"""
        # 准备测试数据
        user_input = "我要订从北京到上海的机票"
        user_id = "user_123"
        
        # 创建模拟意图
        mock_intent = MagicMock()
        mock_intent.intent_name = "book_flight"
        mock_intent.id = 1
        
        # 模拟意图识别
        with patch.object(intent_service, '_get_active_intents', return_value=[mock_intent]), \
             patch.object(intent_service, '_perform_intent_recognition') as mock_perform:
            
            # 设置意图识别结果
            from src.services.intent_service import IntentRecognitionResult
            mock_perform.return_value = IntentRecognitionResult(mock_intent, 0.9)
            
            # 识别意图
            intent_result = await intent_service.recognize_intent(user_input, user_id)
            
            # 验证意图识别结果
            assert intent_result.intent == mock_intent
            assert intent_result.confidence == 0.9
            
            # 模拟槽位提取
            with patch.object(slot_service, '_get_slot_definitions', return_value=[
                {
                    'slot_name': 'origin',
                    'slot_type': 'text',
                    'is_required': True,
                    'description': '出发地'
                },
                {
                    'slot_name': 'destination',
                    'slot_type': 'text',
                    'is_required': True,
                    'description': '目的地'
                }
            ]), \
                 patch.object(slot_service, '_get_or_build_dependency_graph'), \
                 patch.object(slot_service, '_apply_slot_inheritance'), \
                 patch.object(slot_service, '_validate_slots', return_value={}), \
                 patch.object(slot_service, '_find_missing_slots', return_value=[]):
                
                # 提取槽位
                slot_result = await slot_service.extract_slots(mock_intent, user_input)
                
                # 验证槽位提取结果
                assert slot_result.is_complete == True
                assert len(slot_result.slots) > 0
    
    @pytest.mark.asyncio
    async def test_conversation_and_function_integration(self, conversation_service, function_service):
        """测试对话服务和功能服务集成"""
        # 准备测试数据
        user_id = "user_456"
        session_id = "sess_789"
        
        # 创建模拟会话
        mock_session = MagicMock()
        mock_session.session_id = session_id
        mock_session.user_id = user_id
        
        with patch('src.services.conversation_service.Session') as mock_session_model:
            mock_session_model.create.return_value = mock_session
            
            # 创建会话
            session = await conversation_service.get_or_create_session(user_id, session_id)
            
            # 验证会话创建
            assert session.session_id == session_id
            assert session.user_id == user_id
            
            # 模拟功能调用
            function_name = "book_flight"
            parameters = {
                "origin": "北京",
                "destination": "上海",
                "date": "2024-01-01"
            }
            
            # 创建模拟功能
            mock_function = MagicMock()
            mock_function.function_name = function_name
            mock_function.function_type = "api"
            
            with patch.object(function_service, '_get_function_by_name', return_value=mock_function), \
                 patch.object(function_service, '_validate_parameters', return_value=None), \
                 patch.object(function_service, '_execute_function', return_value={"success": True}), \
                 patch.object(function_service, '_save_function_call'):
                
                # 调用功能
                result = await function_service.call_function(function_name, parameters, {})
                
                # 验证功能调用结果
                assert result["success"] == True
    
    @pytest.mark.asyncio
    async def test_query_processor_integration(self, query_processor):
        """测试查询处理器集成"""
        # 准备测试数据
        query = "北京天气怎么样"
        
        from src.services.query_processor import QueryContext
        context = QueryContext(
            session_id="sess_123",
            user_id="user_456",
            conversation_history=[],
            user_preferences={}
        )
        
        # 模拟查询处理各个环节
        with patch.object(query_processor, '_analyze_query') as mock_analyze, \
             patch.object(query_processor, '_enhance_query', return_value="北京 天气 预报"), \
             patch.object(query_processor, '_determine_search_strategies', return_value=["semantic_search"]), \
             patch.object(query_processor, '_extract_filters', return_value={"location": "北京"}), \
             patch.object(query_processor, '_identify_boost_terms', return_value=["天气"]), \
             patch.object(query_processor, '_get_context_terms', return_value=["预报"]), \
             patch.object(query_processor, '_determine_answer_type', return_value="weather_info"), \
             patch.object(query_processor, '_determine_routing', return_value="weather_kb"):
            
            # 设置查询分析结果
            from src.services.query_processor import QueryAnalysis, QueryType, QueryComplexity, QueryIntent
            mock_analyze.return_value = QueryAnalysis(
                original_query=query,
                normalized_query="北京 天气 怎么样",
                query_type=QueryType.FACTUAL,
                query_complexity=QueryComplexity.SIMPLE,
                query_intent=QueryIntent.SEARCH,
                entities=[],
                keywords=["北京", "天气"],
                semantic_keywords=["天气预报"],
                confidence=0.9
            )
            
            # 处理查询
            result = await query_processor.process_query(query, context)
            
            # 验证查询处理结果
            assert result.original_query == query
            assert result.enhanced_query == "北京 天气 预报"
            assert result.search_strategies == ["semantic_search"]
            assert result.filters == {"location": "北京"}
            assert result.boost_terms == ["天气"]
            assert result.context_terms == ["预报"]
            assert result.expected_answer_type == "weather_info"
            assert result.routing_config == "weather_kb"
    
    @pytest.mark.asyncio
    async def test_full_pipeline_integration(self, intent_service, slot_service, conversation_service, 
                                           function_service, query_processor):
        """测试完整管道集成"""
        # 准备测试数据
        user_input = "我要订明天从北京到上海的机票"
        user_id = "user_123"
        session_id = "sess_456"
        
        # 1. 创建会话
        mock_session = MagicMock()
        mock_session.session_id = session_id
        mock_session.user_id = user_id
        
        with patch('src.services.conversation_service.Session') as mock_session_model:
            mock_session_model.create.return_value = mock_session
            
            session = await conversation_service.get_or_create_session(user_id, session_id)
            assert session.session_id == session_id
        
        # 2. 识别意图
        mock_intent = MagicMock()
        mock_intent.intent_name = "book_flight"
        mock_intent.id = 1
        
        with patch.object(intent_service, '_get_active_intents', return_value=[mock_intent]), \
             patch.object(intent_service, '_perform_intent_recognition') as mock_perform:
            
            from src.services.intent_service import IntentRecognitionResult
            mock_perform.return_value = IntentRecognitionResult(mock_intent, 0.9)
            
            intent_result = await intent_service.recognize_intent(user_input, user_id)
            assert intent_result.intent == mock_intent
            assert intent_result.confidence == 0.9
        
        # 3. 提取槽位
        with patch.object(slot_service, '_get_slot_definitions', return_value=[
            {
                'slot_name': 'origin',
                'slot_type': 'text',
                'is_required': True,
                'description': '出发地'
            },
            {
                'slot_name': 'destination',
                'slot_type': 'text',
                'is_required': True,
                'description': '目的地'
            },
            {
                'slot_name': 'date',
                'slot_type': 'date',
                'is_required': True,
                'description': '出发日期'
            }
        ]), \
             patch.object(slot_service, '_get_or_build_dependency_graph'), \
             patch.object(slot_service, '_apply_slot_inheritance'), \
             patch.object(slot_service, '_validate_slots', return_value={}), \
             patch.object(slot_service, '_find_missing_slots', return_value=[]):
            
            slot_result = await slot_service.extract_slots(mock_intent, user_input)
            assert slot_result.is_complete == True
        
        # 4. 调用功能
        function_name = "book_flight"
        parameters = {
            "origin": "北京",
            "destination": "上海",
            "date": "明天"
        }
        
        mock_function = MagicMock()
        mock_function.function_name = function_name
        mock_function.function_type = "api"
        
        with patch.object(function_service, '_get_function_by_name', return_value=mock_function), \
             patch.object(function_service, '_validate_parameters', return_value=None), \
             patch.object(function_service, '_execute_function', 
                         return_value={"success": True, "booking_id": "BK123456"}), \
             patch.object(function_service, '_save_function_call'):
            
            function_result = await function_service.call_function(function_name, parameters, {})
            assert function_result["success"] == True
            assert function_result["booking_id"] == "BK123456"
        
        # 5. 保存对话记录
        conversation_data = {
            'session_id': session_id,
            'user_id': user_id,
            'user_input': user_input,
            'intent_name': mock_intent.intent_name,
            'confidence': 0.9,
            'entities': [],
            'response': f"机票预订成功，订单号：{function_result['booking_id']}"
        }
        
        mock_conversation = MagicMock()
        mock_conversation.id = 1
        
        with patch('src.services.conversation_service.Conversation') as mock_conversation_model:
            mock_conversation_model.create.return_value = mock_conversation
            
            saved_conversation = await conversation_service.save_conversation(conversation_data)
            assert saved_conversation.id == 1
    
    @pytest.mark.asyncio
    async def test_error_handling_across_services(self, intent_service, slot_service, 
                                                 conversation_service, function_service):
        """测试跨服务错误处理"""
        # 测试意图服务错误处理
        with patch.object(intent_service, '_get_active_intents', side_effect=Exception("Database error")):
            result = await intent_service.recognize_intent("测试输入", "user_123")
            assert result.intent is None
            assert result.confidence == 0.0
        
        # 测试槽位服务错误处理
        mock_intent = MagicMock()
        with patch.object(slot_service, '_get_slot_definitions', side_effect=Exception("Config error")):
            result = await slot_service.extract_slots(mock_intent, "测试输入")
            assert result.is_complete == True
            assert len(result.slots) == 0
        
        # 测试功能服务错误处理
        with patch.object(function_service, '_get_function_by_name', side_effect=Exception("Registry error")):
            result = await function_service.call_function("test_function", {}, {})
            assert result["success"] == False
            assert "error" in result
        
        # 测试对话服务错误处理
        with patch('src.services.conversation_service.Session') as mock_session_model:
            mock_session_model.get.side_effect = Exception("Session error")
            mock_session_model.create.side_effect = Exception("Create error")
            
            with pytest.raises(Exception):
                await conversation_service.get_or_create_session("user_123", "sess_456")
    
    @pytest.mark.asyncio
    async def test_caching_across_services(self, intent_service, slot_service, 
                                         function_service, query_processor, mock_cache_service):
        """测试跨服务缓存"""
        # 设置缓存返回值
        mock_cache_service.get.return_value = {
            "intent": "book_flight",
            "confidence": 0.9,
            "recognition_type": "confident",
            "alternatives": [],
            "is_ambiguous": False
        }
        
        # 测试意图服务缓存
        result = await intent_service.recognize_intent("我要订机票", "user_123")
        assert result.intent == "book_flight"
        assert result.confidence == 0.9
        
        # 验证缓存被调用
        mock_cache_service.get.assert_called()
        
        # 重置mock
        mock_cache_service.reset_mock()
        
        # 测试槽位服务缓存
        mock_cache_service.get.return_value = [
            {
                'slot_name': 'destination',
                'slot_type': 'text',
                'is_required': True,
                'description': '目的地'
            }
        ]
        
        mock_intent = MagicMock()
        mock_intent.intent_name = "book_flight"
        
        with patch.object(slot_service, '_get_slot_definitions') as mock_get_slots:
            mock_get_slots.return_value = mock_cache_service.get.return_value
            
            result = await slot_service._get_slot_definitions(mock_intent)
            assert len(result) == 1
            assert result[0]['slot_name'] == 'destination'
    
    @pytest.mark.asyncio
    async def test_concurrent_service_calls(self, intent_service, slot_service, 
                                          function_service, query_processor):
        """测试并发服务调用"""
        # 准备测试数据
        user_inputs = [
            "我要订机票",
            "查看天气",
            "预定酒店",
            "租车服务",
            "查询余额"
        ]
        
        # 模拟意图识别
        with patch.object(intent_service, '_get_active_intents', return_value=[]), \
             patch.object(intent_service, '_perform_intent_recognition') as mock_perform:
            
            from src.services.intent_service import IntentRecognitionResult
            mock_perform.return_value = IntentRecognitionResult(None, 0.5)
            
            # 并发调用意图识别
            tasks = [
                intent_service.recognize_intent(input_text, f"user_{i}")
                for i, input_text in enumerate(user_inputs)
            ]
            
            results = await asyncio.gather(*tasks)
            
            # 验证结果
            assert len(results) == len(user_inputs)
            for result in results:
                assert result.confidence == 0.5
    
    @pytest.mark.asyncio
    async def test_service_performance(self, intent_service, slot_service, 
                                     function_service, query_processor):
        """测试服务性能"""
        import time
        
        # 测试意图服务性能
        start_time = time.time()
        
        with patch.object(intent_service, '_get_active_intents', return_value=[]), \
             patch.object(intent_service, '_perform_intent_recognition') as mock_perform:
            
            from src.services.intent_service import IntentRecognitionResult
            mock_perform.return_value = IntentRecognitionResult(None, 0.8)
            
            # 执行多次意图识别
            for i in range(10):
                await intent_service.recognize_intent(f"测试输入{i}", f"user_{i}")
        
        end_time = time.time()
        execution_time = end_time - start_time
        
        # 验证性能（应该在合理时间内完成）
        assert execution_time < 5.0  # 应该在5秒内完成
        
        # 测试槽位服务性能
        mock_intent = MagicMock()
        mock_intent.intent_name = "test_intent"
        
        start_time = time.time()
        
        with patch.object(slot_service, '_get_slot_definitions', return_value=[]), \
             patch.object(slot_service, '_get_or_build_dependency_graph'), \
             patch.object(slot_service, '_apply_slot_inheritance'), \
             patch.object(slot_service, '_validate_slots', return_value={}), \
             patch.object(slot_service, '_find_missing_slots', return_value=[]):
            
            # 执行多次槽位提取
            for i in range(10):
                await slot_service.extract_slots(mock_intent, f"测试输入{i}")
        
        end_time = time.time()
        execution_time = end_time - start_time
        
        # 验证性能
        assert execution_time < 3.0  # 应该在3秒内完成