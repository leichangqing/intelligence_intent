"""
槽位服务单元测试
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from typing import Dict, List, Optional, Any
import json

from src.services.slot_service import SlotService, SlotExtractionResult
from src.models.slot import Slot, SlotValue, SlotDependency
from src.models.intent import Intent
from src.services.cache_service import CacheService
from src.core.nlu_engine import NLUEngine


class TestSlotExtractionResult:
    """槽位提取结果测试类"""
    
    def test_init_complete_slots(self):
        """测试完整槽位提取结果初始化"""
        slots = {
            'destination': {'value': '北京', 'confidence': 0.9},
            'date': {'value': '明天', 'confidence': 0.8}
        }
        missing_slots = []
        
        result = SlotExtractionResult(slots, missing_slots)
        
        assert result.slots == slots
        assert result.missing_slots == missing_slots
        assert result.is_complete == True
        assert result.has_errors == False
        assert result.validation_errors == {}
    
    def test_init_incomplete_slots(self):
        """测试不完整槽位提取结果初始化"""
        slots = {
            'destination': {'value': '北京', 'confidence': 0.9}
        }
        missing_slots = ['date', 'departure_time']
        
        result = SlotExtractionResult(slots, missing_slots)
        
        assert result.slots == slots
        assert result.missing_slots == missing_slots
        assert result.is_complete == False
        assert result.has_errors == False
    
    def test_init_with_validation_errors(self):
        """测试带验证错误的槽位提取结果初始化"""
        slots = {
            'destination': {'value': '北京', 'confidence': 0.9},
            'date': {'value': '无效日期', 'confidence': 0.7}
        }
        missing_slots = []
        validation_errors = {
            'date': '日期格式无效'
        }
        
        result = SlotExtractionResult(slots, missing_slots, validation_errors)
        
        assert result.slots == slots
        assert result.missing_slots == missing_slots
        assert result.validation_errors == validation_errors
        assert result.is_complete == True
        assert result.has_errors == True
    
    def test_to_dict(self):
        """测试转换为字典格式"""
        slots = {
            'destination': {'value': '上海', 'confidence': 0.95}
        }
        missing_slots = ['date']
        validation_errors = {}
        
        result = SlotExtractionResult(slots, missing_slots, validation_errors)
        result_dict = result.to_dict()
        
        assert result_dict['slots'] == slots
        assert result_dict['missing_slots'] == missing_slots
        assert result_dict['validation_errors'] == validation_errors
        assert result_dict['is_complete'] == False
        assert result_dict['has_errors'] == False


class TestSlotService:
    """槽位服务测试类"""
    
    @pytest.fixture
    def mock_cache_service(self):
        """模拟缓存服务"""
        return AsyncMock(spec=CacheService)
    
    @pytest.fixture
    def mock_nlu_engine(self):
        """模拟NLU引擎"""
        return AsyncMock(spec=NLUEngine)
    
    @pytest.fixture
    def mock_intent(self):
        """模拟意图对象"""
        intent = MagicMock()
        intent.id = 1
        intent.intent_name = "book_flight"
        intent.is_active = True
        return intent
    
    @pytest.fixture
    def slot_service(self, mock_cache_service, mock_nlu_engine):
        """创建槽位服务实例"""
        service = SlotService(mock_cache_service, mock_nlu_engine)
        return service
    
    @pytest.mark.asyncio
    async def test_extract_slots_complete(self, slot_service, mock_intent, mock_nlu_engine):
        """测试完整槽位提取"""
        # 准备测试数据
        user_input = "我要订从北京到上海明天的机票"
        existing_slots = {}
        context = {}
        
        # 模拟槽位定义
        slot_definitions = [
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
        ]
        
        # 模拟NLU引擎提取结果
        extracted_slots = {
            'origin': {
                'value': '北京',
                'confidence': 0.9,
                'source': 'llm',
                'original_text': '北京'
            },
            'destination': {
                'value': '上海',
                'confidence': 0.95,
                'source': 'llm',
                'original_text': '上海'
            },
            'date': {
                'value': '明天',
                'confidence': 0.8,
                'source': 'llm',
                'original_text': '明天'
            }
        }
        
        # 设置模拟行为
        mock_nlu_engine.extract_slots.return_value = extracted_slots
        
        with patch.object(slot_service, '_get_slot_definitions', return_value=slot_definitions), \
             patch.object(slot_service, '_get_or_build_dependency_graph', return_value=MagicMock()), \
             patch.object(slot_service, '_apply_slot_inheritance', return_value=MagicMock(inherited_values={})), \
             patch.object(slot_service, '_validate_slots', return_value={}), \
             patch.object(slot_service, '_find_missing_slots', return_value=[]):
            
            # 调用方法
            result = await slot_service.extract_slots(mock_intent, user_input, existing_slots, context)
            
            # 验证结果
            assert result.is_complete == True
            assert result.has_errors == False
            assert len(result.slots) == 3
            assert result.slots['origin']['value'] == '北京'
            assert result.slots['destination']['value'] == '上海'
            assert result.slots['date']['value'] == '明天'
    
    @pytest.mark.asyncio
    async def test_extract_slots_incomplete(self, slot_service, mock_intent, mock_nlu_engine):
        """测试不完整槽位提取"""
        # 准备测试数据
        user_input = "我要订机票到上海"
        existing_slots = {}
        context = {}
        
        # 模拟槽位定义
        slot_definitions = [
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
        ]
        
        # 模拟NLU引擎提取结果（只提取到目的地）
        extracted_slots = {
            'destination': {
                'value': '上海',
                'confidence': 0.95,
                'source': 'llm',
                'original_text': '上海'
            }
        }
        
        # 设置模拟行为
        mock_nlu_engine.extract_slots.return_value = extracted_slots
        
        with patch.object(slot_service, '_get_slot_definitions', return_value=slot_definitions), \
             patch.object(slot_service, '_get_or_build_dependency_graph', return_value=MagicMock()), \
             patch.object(slot_service, '_apply_slot_inheritance', return_value=MagicMock(inherited_values={})), \
             patch.object(slot_service, '_validate_slots', return_value={}), \
             patch.object(slot_service, '_find_missing_slots', return_value=['origin', 'date']):
            
            # 调用方法
            result = await slot_service.extract_slots(mock_intent, user_input, existing_slots, context)
            
            # 验证结果
            assert result.is_complete == False
            assert result.has_errors == False
            assert len(result.slots) == 1
            assert result.slots['destination']['value'] == '上海'
            assert 'origin' in result.missing_slots
            assert 'date' in result.missing_slots
    
    @pytest.mark.asyncio
    async def test_extract_slots_with_existing_slots(self, slot_service, mock_intent, mock_nlu_engine):
        """测试有现有槽位时的槽位提取"""
        # 准备测试数据
        user_input = "明天出发"
        existing_slots = {
            'origin': {'value': '北京', 'confidence': 0.9},
            'destination': {'value': '上海', 'confidence': 0.95}
        }
        context = {}
        
        # 模拟槽位定义
        slot_definitions = [
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
        ]
        
        # 模拟NLU引擎提取结果（只提取到日期）
        extracted_slots = {
            'date': {
                'value': '明天',
                'confidence': 0.8,
                'source': 'llm',
                'original_text': '明天'
            }
        }
        
        # 设置模拟行为
        mock_nlu_engine.extract_slots.return_value = extracted_slots
        
        with patch.object(slot_service, '_get_slot_definitions', return_value=slot_definitions), \
             patch.object(slot_service, '_get_or_build_dependency_graph', return_value=MagicMock()), \
             patch.object(slot_service, '_apply_slot_inheritance', return_value=MagicMock(inherited_values={})), \
             patch.object(slot_service, '_validate_slots', return_value={}), \
             patch.object(slot_service, '_find_missing_slots', return_value=[]):
            
            # 调用方法
            result = await slot_service.extract_slots(mock_intent, user_input, existing_slots, context)
            
            # 验证结果
            assert result.is_complete == True
            assert result.has_errors == False
            assert len(result.slots) == 3
            assert result.slots['origin']['value'] == '北京'  # 保留现有值
            assert result.slots['destination']['value'] == '上海'  # 保留现有值
            assert result.slots['date']['value'] == '明天'  # 新提取的值
    
    @pytest.mark.asyncio
    async def test_extract_slots_with_validation_errors(self, slot_service, mock_intent, mock_nlu_engine):
        """测试带验证错误的槽位提取"""
        # 准备测试数据
        user_input = "我要订机票到上海，后天出发"
        existing_slots = {}
        context = {}
        
        # 模拟槽位定义
        slot_definitions = [
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
        ]
        
        # 模拟NLU引擎提取结果
        extracted_slots = {
            'destination': {
                'value': '上海',
                'confidence': 0.95,
                'source': 'llm',
                'original_text': '上海'
            },
            'date': {
                'value': '后天',
                'confidence': 0.7,
                'source': 'llm',
                'original_text': '后天'
            }
        }
        
        # 模拟验证错误
        validation_errors = {
            'date': '日期格式需要更具体，请提供具体日期'
        }
        
        # 设置模拟行为
        mock_nlu_engine.extract_slots.return_value = extracted_slots
        
        with patch.object(slot_service, '_get_slot_definitions', return_value=slot_definitions), \
             patch.object(slot_service, '_get_or_build_dependency_graph', return_value=MagicMock()), \
             patch.object(slot_service, '_apply_slot_inheritance', return_value=MagicMock(inherited_values={})), \
             patch.object(slot_service, '_validate_slots', return_value=validation_errors), \
             patch.object(slot_service, '_find_missing_slots', return_value=[]):
            
            # 调用方法
            result = await slot_service.extract_slots(mock_intent, user_input, existing_slots, context)
            
            # 验证结果
            assert result.is_complete == True
            assert result.has_errors == True
            assert len(result.slots) == 2
            assert result.validation_errors['date'] == '日期格式需要更具体，请提供具体日期'
    
    @pytest.mark.asyncio
    async def test_extract_slots_no_slot_definitions(self, slot_service, mock_intent):
        """测试没有槽位定义时的处理"""
        # 准备测试数据
        user_input = "测试输入"
        existing_slots = {}
        context = {}
        
        # 设置模拟行为
        with patch.object(slot_service, '_get_slot_definitions', return_value=[]):
            
            # 调用方法
            result = await slot_service.extract_slots(mock_intent, user_input, existing_slots, context)
            
            # 验证结果
            assert result.is_complete == True
            assert result.has_errors == False
            assert len(result.slots) == 0
            assert len(result.missing_slots) == 0
    
    @pytest.mark.asyncio
    async def test_generate_question_for_missing_slots(self, slot_service, mock_intent):
        """测试为缺失槽位生成问题"""
        # 准备测试数据
        missing_slots = ['origin', 'date']
        existing_slots = {
            'destination': {'value': '上海', 'confidence': 0.95}
        }
        context = {}
        
        # 模拟槽位定义
        slot_definitions = [
            {
                'slot_name': 'origin',
                'slot_type': 'text',
                'is_required': True,
                'description': '出发地',
                'question_template': '请问您从哪里出发？'
            },
            {
                'slot_name': 'date',
                'slot_type': 'date',
                'is_required': True,
                'description': '出发日期',
                'question_template': '请问您什么时候出发？'
            }
        ]
        
        expected_question = "请问您从哪里出发？另外，请问您什么时候出发？"
        
        # 设置模拟行为
        with patch.object(slot_service, '_get_slot_definitions', return_value=slot_definitions), \
             patch.object(slot_service.clarification_generator, 'generate_clarification_question', 
                         return_value=expected_question):
            
            # 调用方法
            result = await slot_service.generate_question_for_missing_slots(
                mock_intent, missing_slots, existing_slots, context)
            
            # 验证结果
            assert result == expected_question
    
    @pytest.mark.asyncio
    async def test_validate_slot_value(self, slot_service):
        """测试槽位值验证"""
        # 准备测试数据
        slot_definition = {
            'slot_name': 'passenger_count',
            'slot_type': 'number',
            'validation_rules': {
                'min_value': 1,
                'max_value': 10
            }
        }
        
        # 测试有效值
        valid_value = {'value': 2, 'confidence': 0.9}
        result = await slot_service._validate_slot_value(slot_definition, valid_value)
        assert result is None  # 没有验证错误
        
        # 测试无效值
        invalid_value = {'value': 15, 'confidence': 0.9}
        result = await slot_service._validate_slot_value(slot_definition, invalid_value)
        assert result is not None  # 有验证错误
        assert "超出范围" in result or "invalid" in result.lower()
    
    @pytest.mark.asyncio
    async def test_get_slot_definitions_from_cache(self, slot_service, mock_cache_service, mock_intent):
        """测试从缓存获取槽位定义"""
        # 准备测试数据
        cached_definitions = [
            {
                'slot_name': 'destination',
                'slot_type': 'text',
                'is_required': True,
                'description': '目的地'
            }
        ]
        
        # 设置模拟行为
        mock_cache_service.get.return_value = cached_definitions
        
        # 调用方法
        result = await slot_service._get_slot_definitions(mock_intent)
        
        # 验证结果
        assert result == cached_definitions
        expected_cache_key = f"slot_definitions:{mock_intent.intent_name}"
        mock_cache_service.get.assert_called_once_with(expected_cache_key)
    
    @pytest.mark.asyncio
    async def test_get_slot_definitions_from_database(self, slot_service, mock_cache_service, mock_intent):
        """测试从数据库获取槽位定义"""
        # 准备测试数据
        mock_cache_service.get.return_value = None
        
        # 创建模拟槽位对象
        mock_slot = MagicMock()
        mock_slot.slot_name = 'destination'
        mock_slot.slot_type = 'text'
        mock_slot.is_required = True
        mock_slot.description = '目的地'
        mock_slot.validation_rules = '{}'
        mock_slot.question_template = '请问您要去哪里？'
        
        # 设置模拟行为
        with patch('src.services.slot_service.Slot') as mock_slot_model:
            mock_slot_model.select.return_value.where.return_value = [mock_slot]
            
            # 调用方法
            result = await slot_service._get_slot_definitions(mock_intent)
            
            # 验证结果
            assert len(result) == 1
            assert result[0]['slot_name'] == 'destination'
            assert result[0]['slot_type'] == 'text'
            assert result[0]['is_required'] == True
            
            # 验证缓存被设置
            mock_cache_service.set.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_save_slot_values(self, slot_service):
        """测试保存槽位值"""
        # 准备测试数据
        session_id = "sess_123"
        intent_name = "book_flight"
        slots = {
            'destination': {'value': '上海', 'confidence': 0.95},
            'date': {'value': '明天', 'confidence': 0.8}
        }
        
        # 创建模拟SlotValue对象
        mock_slot_value = MagicMock()
        mock_slot_value.id = 1
        
        with patch('src.services.slot_service.SlotValue') as mock_slot_value_model:
            mock_slot_value_model.create.return_value = mock_slot_value
            
            # 调用方法
            await slot_service.save_slot_values(session_id, intent_name, slots)
            
            # 验证SlotValue.create被调用了正确的次数
            assert mock_slot_value_model.create.call_count == 2
    
    @pytest.mark.asyncio
    async def test_get_slot_values_from_session(self, slot_service, mock_cache_service):
        """测试从会话获取槽位值"""
        # 准备测试数据
        session_id = "sess_456"
        intent_name = "book_flight"
        
        # 设置模拟行为 - 缓存中没有数据
        mock_cache_service.get.return_value = None
        
        # 创建模拟SlotValue对象
        mock_slot_value1 = MagicMock()
        mock_slot_value1.slot_name = 'destination'
        mock_slot_value1.slot_value = '上海'
        mock_slot_value1.confidence = 0.95
        
        mock_slot_value2 = MagicMock()
        mock_slot_value2.slot_name = 'date'
        mock_slot_value2.slot_value = '明天'
        mock_slot_value2.confidence = 0.8
        
        slot_values = [mock_slot_value1, mock_slot_value2]
        
        with patch('src.services.slot_service.SlotValue') as mock_slot_value_model:
            mock_query = MagicMock()
            mock_query.where.return_value = slot_values
            mock_slot_value_model.select.return_value = mock_query
            
            # 调用方法
            result = await slot_service.get_slot_values_from_session(session_id, intent_name)
            
            # 验证结果
            assert len(result) == 2
            assert result['destination']['value'] == '上海'
            assert result['date']['value'] == '明天'
            
            # 验证缓存被设置
            mock_cache_service.set.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_error_handling(self, slot_service, mock_intent, mock_nlu_engine):
        """测试错误处理"""
        # 准备测试数据
        user_input = "测试输入"
        existing_slots = {}
        context = {}
        
        # 设置模拟行为 - NLU引擎抛出异常
        mock_nlu_engine.extract_slots.side_effect = Exception("NLU engine error")
        
        with patch.object(slot_service, '_get_slot_definitions', return_value=[]):
            
            # 调用方法
            result = await slot_service.extract_slots(mock_intent, user_input, existing_slots, context)
            
            # 验证结果 - 应该返回空结果
            assert result.is_complete == True
            assert result.has_errors == False
            assert len(result.slots) == 0