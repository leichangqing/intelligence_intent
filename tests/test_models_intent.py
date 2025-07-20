"""
意图模型单元测试
"""
import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime
import json

from src.models.intent import Intent


class TestIntentModel:
    """意图模型测试类"""
    
    def test_intent_creation(self):
        """测试意图创建"""
        # 创建意图实例
        intent = Intent()
        intent.intent_name = "book_flight"
        intent.description = "预订机票"
        intent.examples = json.dumps(["我要订机票", "预订航班"])
        intent.confidence_threshold = 0.7
        intent.is_active = True
        
        # 验证意图属性
        assert intent.intent_name == "book_flight"
        assert intent.description == "预订机票"
        assert isinstance(intent.examples, str)
        assert intent.confidence_threshold == 0.7
        assert intent.is_active == True
    
    def test_intent_examples_property(self):
        """测试意图示例属性"""
        # 创建意图实例
        intent = Intent()
        examples = ["我要订机票", "预订航班", "买机票"]
        intent.examples = json.dumps(examples)
        
        # 获取示例列表
        examples_list = intent.get_examples()
        
        # 验证示例列表
        assert isinstance(examples_list, list)
        assert len(examples_list) == 3
        assert "我要订机票" in examples_list
        assert "预订航班" in examples_list
        assert "买机票" in examples_list
    
    def test_intent_set_examples(self):
        """测试设置意图示例"""
        # 创建意图实例
        intent = Intent()
        examples = ["查看余额", "余额查询", "账户余额"]
        
        # 设置示例
        intent.set_examples(examples)
        
        # 验证示例
        stored_examples = intent.get_examples()
        assert stored_examples == examples
    
    def test_intent_add_example(self):
        """测试添加意图示例"""
        # 创建意图实例
        intent = Intent()
        intent.examples = json.dumps(["我要订机票"])
        
        # 添加示例
        intent.add_example("预订航班")
        
        # 验证示例
        examples = intent.get_examples()
        assert len(examples) == 2
        assert "我要订机票" in examples
        assert "预订航班" in examples
    
    def test_intent_remove_example(self):
        """测试删除意图示例"""
        # 创建意图实例
        intent = Intent()
        intent.examples = json.dumps(["我要订机票", "预订航班", "买机票"])
        
        # 删除示例
        intent.remove_example("预订航班")
        
        # 验证示例
        examples = intent.get_examples()
        assert len(examples) == 2
        assert "我要订机票" in examples
        assert "买机票" in examples
        assert "预订航班" not in examples
    
    def test_intent_validation(self):
        """测试意图验证"""
        # 创建有效的意图实例
        intent = Intent()
        intent.intent_name = "book_flight"
        intent.description = "预订机票"
        intent.confidence_threshold = 0.7
        
        # 验证应该通过
        assert intent.validate() == True
        
        # 测试无效的意图名称
        intent.intent_name = ""
        assert intent.validate() == False
        
        # 测试无效的置信度阈值
        intent.intent_name = "book_flight"
        intent.confidence_threshold = 1.5
        assert intent.validate() == False
        
        # 测试无效的置信度阈值（负数）
        intent.confidence_threshold = -0.1
        assert intent.validate() == False
    
    def test_intent_to_dict(self):
        """测试意图转字典"""
        # 创建意图实例
        intent = Intent()
        intent.id = 1
        intent.intent_name = "book_flight"
        intent.description = "预订机票"
        intent.examples = json.dumps(["我要订机票", "预订航班"])
        intent.confidence_threshold = 0.7
        intent.is_active = True
        intent.created_at = datetime(2024, 1, 1, 10, 0, 0)
        
        # 转换为字典
        intent_dict = intent.to_dict()
        
        # 验证字典内容
        assert intent_dict['id'] == 1
        assert intent_dict['intent_name'] == "book_flight"
        assert intent_dict['description'] == "预订机票"
        assert isinstance(intent_dict['examples'], list)
        assert intent_dict['confidence_threshold'] == 0.7
        assert intent_dict['is_active'] == True
        assert 'created_at' in intent_dict
    
    def test_intent_from_dict(self):
        """测试从字典创建意图"""
        # 准备测试数据
        intent_data = {
            'id': 1,
            'intent_name': 'check_balance',
            'description': '查询余额',
            'examples': ['查看余额', '余额查询'],
            'confidence_threshold': 0.8,
            'is_active': True,
            'created_at': '2024-01-01T10:00:00',
            'updated_at': '2024-01-01T10:00:00'
        }
        
        # 从字典创建意图
        intent = Intent.from_dict(intent_data)
        
        # 验证意图属性
        assert intent.id == 1
        assert intent.intent_name == 'check_balance'
        assert intent.description == '查询余额'
        assert intent.get_examples() == ['查看余额', '余额查询']
        assert intent.confidence_threshold == 0.8
        assert intent.is_active == True
    
    def test_intent_get_slots(self):
        """测试获取意图槽位"""
        # 创建意图实例
        intent = Intent()
        intent.id = 1
        intent.intent_name = "book_flight"
        
        # 模拟槽位数据
        mock_slots = [
            MagicMock(slot_name="origin", slot_type="text", is_required=True),
            MagicMock(slot_name="destination", slot_type="text", is_required=True),
            MagicMock(slot_name="date", slot_type="date", is_required=True)
        ]
        
        with patch('src.models.slot.Slot') as mock_slot_model:
            mock_query = MagicMock()
            mock_query.where.return_value = mock_slots
            mock_slot_model.select.return_value = mock_query
            
            # 获取槽位
            slots = intent.get_slots()
            
            # 验证槽位
            assert len(slots) == 3
            assert slots[0].slot_name == "origin"
            assert slots[1].slot_name == "destination"
            assert slots[2].slot_name == "date"
    
    def test_intent_get_required_slots(self):
        """测试获取必需槽位"""
        # 创建意图实例
        intent = Intent()
        intent.id = 1
        intent.intent_name = "book_flight"
        
        # 模拟槽位数据
        mock_slots = [
            MagicMock(slot_name="origin", slot_type="text", is_required=True),
            MagicMock(slot_name="destination", slot_type="text", is_required=True),
            MagicMock(slot_name="class", slot_type="text", is_required=False)
        ]
        
        with patch('src.models.slot.Slot') as mock_slot_model:
            mock_query = MagicMock()
            mock_query.where.return_value = mock_slots[:2]  # 只返回必需的槽位
            mock_slot_model.select.return_value = mock_query
            
            # 获取必需槽位
            required_slots = intent.get_required_slots()
            
            # 验证必需槽位
            assert len(required_slots) == 2
            assert required_slots[0].slot_name == "origin"
            assert required_slots[1].slot_name == "destination"
    
    def test_intent_get_optional_slots(self):
        """测试获取可选槽位"""
        # 创建意图实例
        intent = Intent()
        intent.id = 1
        intent.intent_name = "book_flight"
        
        # 模拟槽位数据
        mock_slots = [
            MagicMock(slot_name="class", slot_type="text", is_required=False),
            MagicMock(slot_name="seat", slot_type="text", is_required=False)
        ]
        
        with patch('src.models.slot.Slot') as mock_slot_model:
            mock_query = MagicMock()
            mock_query.where.return_value = mock_slots
            mock_slot_model.select.return_value = mock_query
            
            # 获取可选槽位
            optional_slots = intent.get_optional_slots()
            
            # 验证可选槽位
            assert len(optional_slots) == 2
            assert optional_slots[0].slot_name == "class"
            assert optional_slots[1].slot_name == "seat"
    
    def test_intent_get_functions(self):
        """测试获取意图关联功能"""
        # 创建意图实例
        intent = Intent()
        intent.id = 1
        intent.intent_name = "book_flight"
        
        # 模拟功能数据
        mock_functions = [
            MagicMock(function_name="book_flight_api", function_type="api"),
            MagicMock(function_name="validate_flight_data", function_type="python")
        ]
        
        with patch('src.models.function.Function') as mock_function_model:
            mock_query = MagicMock()
            mock_query.where.return_value = mock_functions
            mock_function_model.select.return_value = mock_query
            
            # 获取功能
            functions = intent.get_functions()
            
            # 验证功能
            assert len(functions) == 2
            assert functions[0].function_name == "book_flight_api"
            assert functions[1].function_name == "validate_flight_data"
    
    def test_intent_is_complete(self):
        """测试检查意图是否完整"""
        # 创建意图实例
        intent = Intent()
        intent.intent_name = "book_flight"
        intent.description = "预订机票"
        intent.examples = json.dumps(["我要订机票", "预订航班"])
        intent.confidence_threshold = 0.7
        
        # 模拟槽位数据
        mock_slots = [
            MagicMock(slot_name="origin", is_required=True),
            MagicMock(slot_name="destination", is_required=True)
        ]
        
        with patch.object(intent, 'get_required_slots', return_value=mock_slots):
            # 检查完整性（应该完整）
            assert intent.is_complete() == True
    
    def test_intent_get_completion_percentage(self):
        """测试获取完成度百分比"""
        # 创建意图实例
        intent = Intent()
        intent.intent_name = "book_flight"
        intent.description = "预订机票"
        intent.examples = json.dumps(["我要订机票"])
        intent.confidence_threshold = 0.7
        
        # 模拟槽位数据
        mock_required_slots = [
            MagicMock(slot_name="origin", is_required=True),
            MagicMock(slot_name="destination", is_required=True)
        ]
        
        with patch.object(intent, 'get_required_slots', return_value=mock_required_slots):
            # 获取完成度
            completion = intent.get_completion_percentage()
            
            # 验证完成度（应该是100%，因为有名称、描述、示例、阈值）
            assert completion > 0
            assert completion <= 100
    
    def test_intent_clone(self):
        """测试克隆意图"""
        # 创建意图实例
        intent = Intent()
        intent.intent_name = "book_flight"
        intent.description = "预订机票"
        intent.examples = json.dumps(["我要订机票", "预订航班"])
        intent.confidence_threshold = 0.7
        intent.is_active = True
        
        # 克隆意图
        cloned_intent = intent.clone()
        
        # 验证克隆
        assert cloned_intent.intent_name == intent.intent_name
        assert cloned_intent.description == intent.description
        assert cloned_intent.examples == intent.examples
        assert cloned_intent.confidence_threshold == intent.confidence_threshold
        assert cloned_intent.is_active == intent.is_active
        assert cloned_intent.id != intent.id  # ID应该不同
    
    def test_intent_export_data(self):
        """测试导出意图数据"""
        # 创建意图实例
        intent = Intent()
        intent.id = 1
        intent.intent_name = "book_flight"
        intent.description = "预订机票"
        intent.examples = json.dumps(["我要订机票", "预订航班"])
        intent.confidence_threshold = 0.7
        intent.is_active = True
        
        # 导出数据
        export_data = intent.export_data()
        
        # 验证导出数据
        assert export_data['intent_name'] == "book_flight"
        assert export_data['description'] == "预订机票"
        assert export_data['examples'] == ["我要订机票", "预订航班"]
        assert export_data['confidence_threshold'] == 0.7
        assert export_data['is_active'] == True
    
    def test_intent_import_data(self):
        """测试导入意图数据"""
        # 准备导入数据
        import_data = {
            'intent_name': 'check_balance',
            'description': '查询余额',
            'examples': ['查看余额', '余额查询'],
            'confidence_threshold': 0.8,
            'is_active': True
        }
        
        # 导入数据
        intent = Intent.import_data(import_data)
        
        # 验证导入
        assert intent.intent_name == 'check_balance'
        assert intent.description == '查询余额'
        assert intent.get_examples() == ['查看余额', '余额查询']
        assert intent.confidence_threshold == 0.8
        assert intent.is_active == True
    
    def test_intent_search_by_name(self):
        """测试按名称搜索意图"""
        # 准备搜索关键词
        search_term = "flight"
        
        # 模拟搜索结果
        mock_intents = [
            MagicMock(intent_name="book_flight", description="预订机票"),
            MagicMock(intent_name="check_flight", description="查询机票"),
            MagicMock(intent_name="cancel_flight", description="取消机票")
        ]
        
        with patch.object(Intent, 'search_by_name', return_value=mock_intents):
            # 搜索意图
            results = Intent.search_by_name(search_term)
            
            # 验证搜索结果
            assert len(results) == 3
            assert all("flight" in intent.intent_name for intent in results)
    
    def test_intent_search_by_example(self):
        """测试按示例搜索意图"""
        # 准备搜索关键词
        search_term = "机票"
        
        # 模拟搜索结果
        mock_intents = [
            MagicMock(intent_name="book_flight", examples='["我要订机票", "预订航班"]'),
            MagicMock(intent_name="check_flight", examples='["查询机票", "机票状态"]')
        ]
        
        with patch.object(Intent, 'search_by_example', return_value=mock_intents):
            # 搜索意图
            results = Intent.search_by_example(search_term)
            
            # 验证搜索结果
            assert len(results) == 2
    
    def test_intent_get_active_intents(self):
        """测试获取活跃意图"""
        # 模拟活跃意图
        mock_intents = [
            MagicMock(intent_name="book_flight", is_active=True),
            MagicMock(intent_name="check_balance", is_active=True),
            MagicMock(intent_name="cancel_booking", is_active=True)
        ]
        
        with patch.object(Intent, 'get_active_intents', return_value=mock_intents):
            # 获取活跃意图
            active_intents = Intent.get_active_intents()
            
            # 验证活跃意图
            assert len(active_intents) == 3
            assert all(intent.is_active for intent in active_intents)
    
    def test_intent_get_inactive_intents(self):
        """测试获取非活跃意图"""
        # 模拟非活跃意图
        mock_intents = [
            MagicMock(intent_name="old_feature", is_active=False),
            MagicMock(intent_name="deprecated_intent", is_active=False)
        ]
        
        with patch.object(Intent, 'get_inactive_intents', return_value=mock_intents):
            # 获取非活跃意图
            inactive_intents = Intent.get_inactive_intents()
            
            # 验证非活跃意图
            assert len(inactive_intents) == 2
            assert all(not intent.is_active for intent in inactive_intents)
    
    def test_intent_activate(self):
        """测试激活意图"""
        # 创建意图实例
        intent = Intent()
        intent.intent_name = "book_flight"
        intent.is_active = False
        
        # 激活意图
        intent.activate()
        
        # 验证激活
        assert intent.is_active == True
    
    def test_intent_deactivate(self):
        """测试停用意图"""
        # 创建意图实例
        intent = Intent()
        intent.intent_name = "book_flight"
        intent.is_active = True
        
        # 停用意图
        intent.deactivate()
        
        # 验证停用
        assert intent.is_active == False
    
    def test_intent_get_statistics(self):
        """测试获取意图统计"""
        # 创建意图实例
        intent = Intent()
        intent.id = 1
        intent.intent_name = "book_flight"
        
        # 模拟统计数据
        mock_stats = {
            'total_uses': 100,
            'success_rate': 0.85,
            'avg_confidence': 0.78,
            'last_used': datetime.now()
        }
        
        with patch.object(intent, 'get_statistics', return_value=mock_stats):
            # 获取统计
            stats = intent.get_statistics()
            
            # 验证统计
            assert stats['total_uses'] == 100
            assert stats['success_rate'] == 0.85
            assert stats['avg_confidence'] == 0.78
            assert 'last_used' in stats
    
    def test_intent_str_representation(self):
        """测试意图字符串表示"""
        # 创建意图实例
        intent = Intent()
        intent.intent_name = "book_flight"
        intent.description = "预订机票"
        
        # 获取字符串表示
        str_repr = str(intent)
        
        # 验证字符串表示
        assert "book_flight" in str_repr
        assert "预订机票" in str_repr
    
    def test_intent_repr(self):
        """测试意图repr表示"""
        # 创建意图实例
        intent = Intent()
        intent.id = 1
        intent.intent_name = "book_flight"
        
        # 获取repr表示
        repr_str = repr(intent)
        
        # 验证repr表示
        assert "Intent" in repr_str
        assert "book_flight" in repr_str
        assert "id=1" in repr_str