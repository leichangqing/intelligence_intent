"""
意图服务单元测试
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from typing import Dict, List, Optional
import json

from src.services.intent_service import IntentService, IntentRecognitionResult
from src.models.intent import Intent
from src.services.cache_service import CacheService
from src.core.nlu_engine import NLUEngine
from src.config.settings import Settings


class TestIntentRecognitionResult:
    """意图识别结果测试类"""
    
    def test_init_with_confident_intent(self):
        """测试置信度高的意图识别结果初始化"""
        mock_intent = MagicMock()
        mock_intent.intent_name = "book_flight"
        
        result = IntentRecognitionResult(mock_intent, 0.9)
        
        assert result.intent == mock_intent
        assert result.confidence == 0.9
        assert result.recognition_type == "confident"
        assert result.alternatives == []
        assert result.is_ambiguous == False
    
    def test_init_with_uncertain_intent(self):
        """测试置信度中等的意图识别结果初始化"""
        mock_intent = MagicMock()
        mock_intent.intent_name = "check_balance"
        
        result = IntentRecognitionResult(mock_intent, 0.6)
        
        assert result.intent == mock_intent
        assert result.confidence == 0.6
        assert result.recognition_type == "uncertain"
    
    def test_init_with_ambiguous_intent(self):
        """测试歧义意图识别结果初始化"""
        mock_intent = MagicMock()
        alternatives = [{"intent": "book_flight", "confidence": 0.7}]
        
        result = IntentRecognitionResult(mock_intent, 0.7, alternatives, True)
        
        assert result.intent == mock_intent
        assert result.confidence == 0.7
        assert result.recognition_type == "ambiguous"
        assert result.alternatives == alternatives
        assert result.is_ambiguous == True
    
    def test_init_with_unrecognized_intent(self):
        """测试未识别意图结果初始化"""
        result = IntentRecognitionResult(None, 0.2)
        
        assert result.intent is None
        assert result.confidence == 0.2
        assert result.recognition_type == "unrecognized"
    
    def test_to_dict(self):
        """测试转换为字典格式"""
        mock_intent = MagicMock()
        mock_intent.intent_name = "book_flight"
        alternatives = [{"intent": "check_flight", "confidence": 0.6}]
        
        result = IntentRecognitionResult(mock_intent, 0.8, alternatives)
        result_dict = result.to_dict()
        
        assert result_dict["intent"] == "book_flight"
        assert result_dict["confidence"] == 0.8
        assert result_dict["recognition_type"] == "confident"
        assert result_dict["alternatives"] == alternatives
        assert result_dict["is_ambiguous"] == False


class TestIntentService:
    """意图服务测试类"""
    
    @pytest.fixture
    def mock_cache_service(self):
        """模拟缓存服务"""
        return AsyncMock(spec=CacheService)
    
    @pytest.fixture
    def mock_nlu_engine(self):
        """模拟NLU引擎"""
        return AsyncMock(spec=NLUEngine)
    
    @pytest.fixture
    def mock_settings(self):
        """模拟设置"""
        settings = MagicMock()
        settings.AMBIGUITY_DETECTION_THRESHOLD = 0.1
        settings.CONFIDENCE_THRESHOLD = 0.7
        settings.MIN_CONFIDENCE = 0.3
        return settings
    
    @pytest.fixture
    def intent_service(self, mock_cache_service, mock_nlu_engine, mock_settings):
        """创建意图服务实例"""
        with patch('src.services.intent_service.settings', mock_settings):
            service = IntentService(mock_cache_service, mock_nlu_engine)
            return service
    
    @pytest.mark.asyncio
    async def test_recognize_intent_from_cache(self, intent_service, mock_cache_service):
        """测试从缓存获取意图识别结果"""
        # 准备测试数据
        user_input = "我想订机票"
        user_id = "user123"
        cached_result = {
            "intent": "book_flight",
            "confidence": 0.9,
            "recognition_type": "confident",
            "alternatives": [],
            "is_ambiguous": False
        }
        
        # 设置模拟行为
        mock_cache_service.get.return_value = cached_result
        
        # 调用方法
        result = await intent_service.recognize_intent(user_input, user_id)
        
        # 验证结果
        assert result.intent == "book_flight"
        assert result.confidence == 0.9
        assert result.recognition_type == "confident"
        
        # 验证缓存被调用
        expected_cache_key = f"intent_recognition:{hash(user_input)}:{user_id}"
        mock_cache_service.get.assert_called_once_with(expected_cache_key)
    
    @pytest.mark.asyncio
    async def test_recognize_intent_no_cache(self, intent_service, mock_cache_service):
        """测试缓存中没有结果时的意图识别"""
        # 准备测试数据
        user_input = "我想查余额"
        user_id = "user456"
        
        # 设置模拟行为
        mock_cache_service.get.return_value = None
        
        # 模拟获取活跃意图
        mock_intent = MagicMock()
        mock_intent.intent_name = "check_balance"
        
        with patch.object(intent_service, '_get_active_intents', return_value=[mock_intent]):
            with patch.object(intent_service, '_perform_intent_recognition', 
                            return_value=IntentRecognitionResult(mock_intent, 0.85)):
                
                result = await intent_service.recognize_intent(user_input, user_id)
                
                # 验证结果
                assert result.intent == mock_intent
                assert result.confidence == 0.85
                assert result.recognition_type == "confident"
    
    @pytest.mark.asyncio
    async def test_recognize_intent_no_active_intents(self, intent_service, mock_cache_service):
        """测试没有活跃意图时的处理"""
        # 准备测试数据
        user_input = "测试输入"
        user_id = "user789"
        
        # 设置模拟行为
        mock_cache_service.get.return_value = None
        
        # 模拟没有活跃意图
        with patch.object(intent_service, '_get_active_intents', return_value=[]):
            result = await intent_service.recognize_intent(user_input, user_id)
            
            # 验证结果
            assert result.intent is None
            assert result.confidence == 0.0
            assert result.recognition_type == "unrecognized"
    
    @pytest.mark.asyncio
    async def test_get_active_intents_from_cache(self, intent_service, mock_cache_service):
        """测试从缓存获取活跃意图"""
        # 准备测试数据
        cached_intents = [
            {"id": 1, "intent_name": "book_flight", "is_active": True},
            {"id": 2, "intent_name": "check_balance", "is_active": True}
        ]
        
        # 设置模拟行为
        mock_cache_service.get.return_value = cached_intents
        
        # 调用方法
        result = await intent_service._get_active_intents()
        
        # 验证结果
        assert len(result) == 2
        mock_cache_service.get.assert_called_once_with("active_intents")
    
    @pytest.mark.asyncio
    async def test_get_active_intents_from_database(self, intent_service, mock_cache_service):
        """测试从数据库获取活跃意图"""
        # 设置模拟行为
        mock_cache_service.get.return_value = None
        
        # 创建模拟意图
        mock_intent1 = MagicMock()
        mock_intent1.id = 1
        mock_intent1.intent_name = "book_flight"
        mock_intent1.is_active = True
        
        mock_intent2 = MagicMock()
        mock_intent2.id = 2
        mock_intent2.intent_name = "check_balance"
        mock_intent2.is_active = True
        
        # 模拟数据库查询
        with patch('src.services.intent_service.Intent') as mock_intent_model:
            mock_intent_model.select.return_value.where.return_value = [mock_intent1, mock_intent2]
            
            # 调用方法
            result = await intent_service._get_active_intents()
            
            # 验证结果
            assert len(result) == 2
            assert result[0] == mock_intent1
            assert result[1] == mock_intent2
            
            # 验证缓存被设置
            mock_cache_service.set.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_perform_intent_recognition(self, intent_service, mock_nlu_engine):
        """测试执行意图识别"""
        # 准备测试数据
        user_input = "我想订机票到北京"
        active_intents = [
            MagicMock(intent_name="book_flight", confidence_threshold=0.7),
            MagicMock(intent_name="check_balance", confidence_threshold=0.7)
        ]
        
        # 设置模拟行为
        mock_nlu_engine.extract_intent.return_value = {
            "intent": "book_flight",
            "confidence": 0.85,
            "entities": [{"entity": "destination", "value": "北京"}]
        }
        
        # 调用方法
        result = await intent_service._perform_intent_recognition(user_input, active_intents)
        
        # 验证结果
        assert result.intent.intent_name == "book_flight"
        assert result.confidence == 0.85
        assert result.recognition_type == "confident"
    
    @pytest.mark.asyncio
    async def test_detect_ambiguity(self, intent_service):
        """测试歧义检测"""
        # 准备测试数据
        candidates = [
            {"intent": "book_flight", "confidence": 0.8},
            {"intent": "check_flight", "confidence": 0.75},
            {"intent": "cancel_flight", "confidence": 0.7}
        ]
        
        # 模拟歧义检测器
        mock_analysis = MagicMock()
        mock_analysis.is_ambiguous = True
        mock_analysis.ambiguity_score = 0.15
        mock_analysis.confidence_gap = 0.05
        
        with patch.object(intent_service.enhanced_ambiguity_detector, 'analyze_ambiguity', 
                         return_value=mock_analysis):
            
            result = await intent_service._detect_ambiguity(candidates, "test input")
            
            # 验证结果
            assert result.is_ambiguous == True
            assert result.ambiguity_score == 0.15
            assert result.confidence_gap == 0.05
    
    @pytest.mark.asyncio
    async def test_generate_clarification_question(self, intent_service):
        """测试澄清问题生成"""
        # 准备测试数据
        candidates = [
            {"intent": "book_flight", "confidence": 0.8},
            {"intent": "check_flight", "confidence": 0.75}
        ]
        user_input = "我想处理机票"
        
        # 模拟问题生成器
        mock_context = MagicMock()
        expected_question = "您是要预订机票还是查询机票信息？"
        
        with patch.object(intent_service.intelligent_question_generator, 'generate_question', 
                         return_value=expected_question):
            
            result = await intent_service._generate_clarification_question(
                candidates, user_input, {})
            
            # 验证结果
            assert result == expected_question
    
    @pytest.mark.asyncio
    async def test_parse_user_choice(self, intent_service):
        """测试用户选择解析"""
        # 准备测试数据
        user_input = "我选择第一个"
        candidates = [
            {"intent": "book_flight", "confidence": 0.8},
            {"intent": "check_flight", "confidence": 0.75}
        ]
        
        # 模拟选择解析器
        mock_parse_result = MagicMock()
        mock_parse_result.selected_intent = "book_flight"
        mock_parse_result.confidence = 0.9
        mock_parse_result.parse_success = True
        
        with patch.object(intent_service.advanced_choice_parser, 'parse_choice', 
                         return_value=mock_parse_result):
            
            result = await intent_service._parse_user_choice(user_input, candidates)
            
            # 验证结果
            assert result.selected_intent == "book_flight"
            assert result.confidence == 0.9
            assert result.parse_success == True
    
    @pytest.mark.asyncio
    async def test_serialize_result(self, intent_service):
        """测试结果序列化"""
        # 准备测试数据
        mock_intent = MagicMock()
        mock_intent.intent_name = "book_flight"
        result = IntentRecognitionResult(mock_intent, 0.9)
        
        # 调用方法
        serialized = intent_service._serialize_result(result)
        
        # 验证结果
        assert serialized["intent"] == "book_flight"
        assert serialized["confidence"] == 0.9
        assert serialized["recognition_type"] == "confident"
        assert serialized["is_ambiguous"] == False
    
    @pytest.mark.asyncio
    async def test_deserialize_result(self, intent_service):
        """测试结果反序列化"""
        # 准备测试数据
        serialized_data = {
            "intent": "book_flight",
            "confidence": 0.9,
            "recognition_type": "confident",
            "alternatives": [],
            "is_ambiguous": False
        }
        
        # 调用方法
        result = intent_service._deserialize_result(serialized_data)
        
        # 验证结果
        assert result.intent == "book_flight"
        assert result.confidence == 0.9
        assert result.recognition_type == "confident"
        assert result.is_ambiguous == False
    
    @pytest.mark.asyncio
    async def test_error_handling(self, intent_service, mock_cache_service):
        """测试错误处理"""
        # 准备测试数据
        user_input = "测试输入"
        user_id = "user123"
        
        # 设置模拟行为 - 缓存抛出异常
        mock_cache_service.get.side_effect = Exception("Cache error")
        
        # 调用方法
        result = await intent_service.recognize_intent(user_input, user_id)
        
        # 验证结果 - 应该返回未识别结果
        assert result.intent is None
        assert result.confidence == 0.0
        assert result.recognition_type == "unrecognized"