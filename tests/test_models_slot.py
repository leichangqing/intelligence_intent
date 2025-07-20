"""
槽位模型单元测试
"""
import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime
import json

from src.models.slot import Slot, SlotValue, SlotDependency


class TestSlotModel:
    """槽位模型测试类"""
    
    def test_slot_creation(self):
        """测试槽位创建"""
        # 创建槽位实例
        slot = Slot()
        slot.intent_id = 1
        slot.slot_name = "destination"
        slot.slot_type = "text"
        slot.is_required = True
        slot.description = "目的地"
        slot.validation_rules = json.dumps({"min_length": 2, "max_length": 50})
        slot.default_value = None
        slot.question_template = "请问您要去哪里？"
        
        # 验证槽位属性
        assert slot.intent_id == 1
        assert slot.slot_name == "destination"
        assert slot.slot_type == "text"
        assert slot.is_required == True
        assert slot.description == "目的地"
        assert isinstance(slot.validation_rules, str)
        assert slot.default_value is None
        assert slot.question_template == "请问您要去哪里？"
    
    def test_slot_get_validation_rules(self):
        """测试获取槽位验证规则"""
        # 创建槽位实例
        slot = Slot()
        rules = {
            "min_length": 2,
            "max_length": 50,
            "pattern": "^[a-zA-Z\u4e00-\u9fa5]+$"
        }
        slot.validation_rules = json.dumps(rules)
        
        # 获取验证规则
        validation_rules = slot.get_validation_rules()
        
        # 验证规则
        assert isinstance(validation_rules, dict)
        assert validation_rules["min_length"] == 2
        assert validation_rules["max_length"] == 50
        assert validation_rules["pattern"] == "^[a-zA-Z\u4e00-\u9fa5]+$"
    
    def test_slot_set_validation_rules(self):
        """测试设置槽位验证规则"""
        # 创建槽位实例
        slot = Slot()
        rules = {
            "type": "number",
            "min_value": 0,
            "max_value": 100
        }
        
        # 设置验证规则
        slot.set_validation_rules(rules)
        
        # 验证规则
        stored_rules = slot.get_validation_rules()
        assert stored_rules == rules
    
    def test_slot_validate_value(self):
        """测试槽位值验证"""
        # 创建槽位实例
        slot = Slot()
        slot.slot_type = "text"
        slot.validation_rules = json.dumps({
            "min_length": 2,
            "max_length": 50
        })
        
        # 验证有效值
        assert slot.validate_value("北京") == True
        assert slot.validate_value("上海") == True
        
        # 验证无效值
        assert slot.validate_value("") == False
        assert slot.validate_value("A") == False
        assert slot.validate_value("A" * 51) == False
    
    def test_slot_validate_number_value(self):
        """测试数字槽位值验证"""
        # 创建数字槽位实例
        slot = Slot()
        slot.slot_type = "number"
        slot.validation_rules = json.dumps({
            "min_value": 0,
            "max_value": 100
        })
        
        # 验证有效数字
        assert slot.validate_value(50) == True
        assert slot.validate_value(0) == True
        assert slot.validate_value(100) == True
        
        # 验证无效数字
        assert slot.validate_value(-1) == False
        assert slot.validate_value(101) == False
        assert slot.validate_value("not_a_number") == False
    
    def test_slot_validate_date_value(self):
        """测试日期槽位值验证"""
        # 创建日期槽位实例
        slot = Slot()
        slot.slot_type = "date"
        slot.validation_rules = json.dumps({
            "format": "YYYY-MM-DD"
        })
        
        # 验证有效日期
        assert slot.validate_value("2024-01-01") == True
        assert slot.validate_value("2024-12-31") == True
        
        # 验证无效日期
        assert slot.validate_value("2024-13-01") == False
        assert slot.validate_value("invalid-date") == False
        assert slot.validate_value("01-01-2024") == False
    
    def test_slot_get_intent(self):
        """测试获取槽位所属意图"""
        # 创建槽位实例
        slot = Slot()
        slot.intent_id = 1
        
        # 模拟意图数据
        mock_intent = MagicMock(
            id=1,
            intent_name="book_flight",
            description="预订机票"
        )
        
        with patch('src.models.intent.Intent') as mock_intent_model:
            mock_intent_model.get_by_id.return_value = mock_intent
            
            # 获取意图
            intent = slot.get_intent()
            
            # 验证意图
            assert intent.id == 1
            assert intent.intent_name == "book_flight"
            assert intent.description == "预订机票"
    
    def test_slot_get_dependencies(self):
        """测试获取槽位依赖"""
        # 创建槽位实例
        slot = Slot()
        slot.id = 1
        slot.slot_name = "destination"
        
        # 模拟依赖数据
        mock_dependencies = [
            MagicMock(
                dependent_slot_id=1,
                dependency_slot_id=2,
                dependency_type="requires"
            )
        ]
        
        with patch('src.models.slot.SlotDependency') as mock_dependency_model:
            mock_query = MagicMock()
            mock_query.where.return_value = mock_dependencies
            mock_dependency_model.select.return_value = mock_query
            
            # 获取依赖
            dependencies = slot.get_dependencies()
            
            # 验证依赖
            assert len(dependencies) == 1
            assert dependencies[0].dependent_slot_id == 1
            assert dependencies[0].dependency_type == "requires"
    
    def test_slot_get_dependents(self):
        """测试获取依赖此槽位的其他槽位"""
        # 创建槽位实例
        slot = Slot()
        slot.id = 1
        slot.slot_name = "origin"
        
        # 模拟依赖此槽位的其他槽位
        mock_dependents = [
            MagicMock(
                dependent_slot_id=2,
                dependency_slot_id=1,
                dependency_type="requires"
            )
        ]
        
        with patch('src.models.slot.SlotDependency') as mock_dependency_model:
            mock_query = MagicMock()
            mock_query.where.return_value = mock_dependents
            mock_dependency_model.select.return_value = mock_query
            
            # 获取依赖此槽位的其他槽位
            dependents = slot.get_dependents()
            
            # 验证依赖
            assert len(dependents) == 1
            assert dependents[0].dependent_slot_id == 2
            assert dependents[0].dependency_slot_id == 1
    
    def test_slot_has_default_value(self):
        """测试检查是否有默认值"""
        # 创建有默认值的槽位
        slot = Slot()
        slot.default_value = "Beijing"
        assert slot.has_default_value() == True
        
        # 创建没有默认值的槽位
        slot.default_value = None
        assert slot.has_default_value() == False
    
    def test_slot_get_default_value(self):
        """测试获取默认值"""
        # 创建槽位实例
        slot = Slot()
        slot.default_value = "Beijing"
        
        # 获取默认值
        default_value = slot.get_default_value()
        
        # 验证默认值
        assert default_value == "Beijing"
    
    def test_slot_to_dict(self):
        """测试槽位转字典"""
        # 创建槽位实例
        slot = Slot()
        slot.id = 1
        slot.intent_id = 1
        slot.slot_name = "destination"
        slot.slot_type = "text"
        slot.is_required = True
        slot.description = "目的地"
        slot.validation_rules = json.dumps({"min_length": 2})
        slot.default_value = None
        slot.question_template = "请问您要去哪里？"
        slot.created_at = datetime(2024, 1, 1, 10, 0, 0)
        
        # 转换为字典
        slot_dict = slot.to_dict()
        
        # 验证字典内容
        assert slot_dict['id'] == 1
        assert slot_dict['intent_id'] == 1
        assert slot_dict['slot_name'] == "destination"
        assert slot_dict['slot_type'] == "text"
        assert slot_dict['is_required'] == True
        assert slot_dict['description'] == "目的地"
        assert isinstance(slot_dict['validation_rules'], dict)
        assert slot_dict['default_value'] is None
        assert slot_dict['question_template'] == "请问您要去哪里？"


class TestSlotValueModel:
    """槽位值模型测试类"""
    
    def test_slot_value_creation(self):
        """测试槽位值创建"""
        # 创建槽位值实例
        slot_value = SlotValue()
        slot_value.session_id = "sess_123"
        slot_value.intent_name = "book_flight"
        slot_value.slot_name = "destination"
        slot_value.slot_value = "上海"
        slot_value.confidence = 0.9
        slot_value.source = "user_input"
        slot_value.original_text = "我要去上海"
        slot_value.normalized_value = "上海"
        slot_value.is_confirmed = True
        
        # 验证槽位值属性
        assert slot_value.session_id == "sess_123"
        assert slot_value.intent_name == "book_flight"
        assert slot_value.slot_name == "destination"
        assert slot_value.slot_value == "上海"
        assert slot_value.confidence == 0.9
        assert slot_value.source == "user_input"
        assert slot_value.original_text == "我要去上海"
        assert slot_value.normalized_value == "上海"
        assert slot_value.is_confirmed == True
    
    def test_slot_value_is_high_confidence(self):
        """测试检查槽位值是否高置信度"""
        # 创建高置信度槽位值
        slot_value = SlotValue()
        slot_value.confidence = 0.9
        assert slot_value.is_high_confidence() == True
        
        # 创建低置信度槽位值
        slot_value.confidence = 0.5
        assert slot_value.is_high_confidence() == False
    
    def test_slot_value_is_confirmed(self):
        """测试检查槽位值是否已确认"""
        # 创建已确认槽位值
        slot_value = SlotValue()
        slot_value.is_confirmed = True
        assert slot_value.is_confirmed == True
        
        # 创建未确认槽位值
        slot_value.is_confirmed = False
        assert slot_value.is_confirmed == False
    
    def test_slot_value_confirm(self):
        """测试确认槽位值"""
        # 创建槽位值实例
        slot_value = SlotValue()
        slot_value.is_confirmed = False
        
        # 确认槽位值
        slot_value.confirm()
        
        # 验证确认
        assert slot_value.is_confirmed == True
        assert slot_value.confirmed_at is not None
    
    def test_slot_value_get_normalized_value(self):
        """测试获取标准化值"""
        # 创建槽位值实例
        slot_value = SlotValue()
        slot_value.slot_value = "明天"
        slot_value.normalized_value = "2024-01-02"
        
        # 获取标准化值
        normalized = slot_value.get_normalized_value()
        
        # 验证标准化值
        assert normalized == "2024-01-02"
    
    def test_slot_value_set_normalized_value(self):
        """测试设置标准化值"""
        # 创建槽位值实例
        slot_value = SlotValue()
        slot_value.slot_value = "后天"
        
        # 设置标准化值
        slot_value.set_normalized_value("2024-01-03")
        
        # 验证标准化值
        assert slot_value.normalized_value == "2024-01-03"
    
    def test_slot_value_get_session(self):
        """测试获取槽位值所属会话"""
        # 创建槽位值实例
        slot_value = SlotValue()
        slot_value.session_id = "sess_123"
        
        # 模拟会话数据
        mock_session = MagicMock(
            session_id="sess_123",
            user_id="user_456",
            status="active"
        )
        
        with patch('src.models.conversation.Session') as mock_session_model:
            mock_session_model.get.return_value = mock_session
            
            # 获取会话
            session = slot_value.get_session()
            
            # 验证会话
            assert session.session_id == "sess_123"
            assert session.user_id == "user_456"
            assert session.status == "active"
    
    def test_slot_value_to_dict(self):
        """测试槽位值转字典"""
        # 创建槽位值实例
        slot_value = SlotValue()
        slot_value.id = 1
        slot_value.session_id = "sess_123"
        slot_value.intent_name = "book_flight"
        slot_value.slot_name = "destination"
        slot_value.slot_value = "上海"
        slot_value.confidence = 0.9
        slot_value.source = "user_input"
        slot_value.original_text = "我要去上海"
        slot_value.normalized_value = "上海"
        slot_value.is_confirmed = True
        slot_value.created_at = datetime(2024, 1, 1, 10, 0, 0)
        
        # 转换为字典
        slot_value_dict = slot_value.to_dict()
        
        # 验证字典内容
        assert slot_value_dict['id'] == 1
        assert slot_value_dict['session_id'] == "sess_123"
        assert slot_value_dict['intent_name'] == "book_flight"
        assert slot_value_dict['slot_name'] == "destination"
        assert slot_value_dict['slot_value'] == "上海"
        assert slot_value_dict['confidence'] == 0.9
        assert slot_value_dict['source'] == "user_input"
        assert slot_value_dict['original_text'] == "我要去上海"
        assert slot_value_dict['normalized_value'] == "上海"
        assert slot_value_dict['is_confirmed'] == True


class TestSlotDependencyModel:
    """槽位依赖模型测试类"""
    
    def test_slot_dependency_creation(self):
        """测试槽位依赖创建"""
        # 创建槽位依赖实例
        dependency = SlotDependency()
        dependency.dependent_slot_id = 1
        dependency.dependency_slot_id = 2
        dependency.dependency_type = "requires"
        dependency.condition = json.dumps({"operator": "equals", "value": "Beijing"})
        dependency.description = "目的地依赖于出发地"
        
        # 验证槽位依赖属性
        assert dependency.dependent_slot_id == 1
        assert dependency.dependency_slot_id == 2
        assert dependency.dependency_type == "requires"
        assert isinstance(dependency.condition, str)
        assert dependency.description == "目的地依赖于出发地"
    
    def test_slot_dependency_get_condition(self):
        """测试获取依赖条件"""
        # 创建槽位依赖实例
        dependency = SlotDependency()
        condition = {
            "operator": "not_equals",
            "value": "Beijing",
            "message": "目的地不能与出发地相同"
        }
        dependency.condition = json.dumps(condition)
        
        # 获取条件
        condition_dict = dependency.get_condition()
        
        # 验证条件
        assert isinstance(condition_dict, dict)
        assert condition_dict["operator"] == "not_equals"
        assert condition_dict["value"] == "Beijing"
        assert condition_dict["message"] == "目的地不能与出发地相同"
    
    def test_slot_dependency_set_condition(self):
        """测试设置依赖条件"""
        # 创建槽位依赖实例
        dependency = SlotDependency()
        condition = {
            "operator": "in",
            "values": ["Beijing", "Shanghai", "Guangzhou"]
        }
        
        # 设置条件
        dependency.set_condition(condition)
        
        # 验证条件
        stored_condition = dependency.get_condition()
        assert stored_condition == condition
    
    def test_slot_dependency_get_dependent_slot(self):
        """测试获取依赖槽位"""
        # 创建槽位依赖实例
        dependency = SlotDependency()
        dependency.dependent_slot_id = 1
        
        # 模拟依赖槽位数据
        mock_slot = MagicMock(
            id=1,
            slot_name="destination",
            slot_type="text"
        )
        
        with patch('src.models.slot.Slot') as mock_slot_model:
            mock_slot_model.get_by_id.return_value = mock_slot
            
            # 获取依赖槽位
            dependent_slot = dependency.get_dependent_slot()
            
            # 验证依赖槽位
            assert dependent_slot.id == 1
            assert dependent_slot.slot_name == "destination"
            assert dependent_slot.slot_type == "text"
    
    def test_slot_dependency_get_dependency_slot(self):
        """测试获取被依赖槽位"""
        # 创建槽位依赖实例
        dependency = SlotDependency()
        dependency.dependency_slot_id = 2
        
        # 模拟被依赖槽位数据
        mock_slot = MagicMock(
            id=2,
            slot_name="origin",
            slot_type="text"
        )
        
        with patch('src.models.slot.Slot') as mock_slot_model:
            mock_slot_model.get_by_id.return_value = mock_slot
            
            # 获取被依赖槽位
            dependency_slot = dependency.get_dependency_slot()
            
            # 验证被依赖槽位
            assert dependency_slot.id == 2
            assert dependency_slot.slot_name == "origin"
            assert dependency_slot.slot_type == "text"
    
    def test_slot_dependency_evaluate_condition(self):
        """测试评估依赖条件"""
        # 创建槽位依赖实例
        dependency = SlotDependency()
        dependency.dependency_type = "requires"
        dependency.condition = json.dumps({
            "operator": "not_equals",
            "message": "目的地不能与出发地相同"
        })
        
        # 评估条件
        assert dependency.evaluate_condition("Beijing", "Shanghai") == True
        assert dependency.evaluate_condition("Beijing", "Beijing") == False
    
    def test_slot_dependency_is_required_dependency(self):
        """测试检查是否为必需依赖"""
        # 创建必需依赖
        dependency = SlotDependency()
        dependency.dependency_type = "requires"
        assert dependency.is_required_dependency() == True
        
        # 创建可选依赖
        dependency.dependency_type = "optional"
        assert dependency.is_required_dependency() == False
    
    def test_slot_dependency_is_conditional_dependency(self):
        """测试检查是否为条件依赖"""
        # 创建条件依赖
        dependency = SlotDependency()
        dependency.dependency_type = "conditional"
        assert dependency.is_conditional_dependency() == True
        
        # 创建普通依赖
        dependency.dependency_type = "requires"
        assert dependency.is_conditional_dependency() == False
    
    def test_slot_dependency_to_dict(self):
        """测试槽位依赖转字典"""
        # 创建槽位依赖实例
        dependency = SlotDependency()
        dependency.id = 1
        dependency.dependent_slot_id = 1
        dependency.dependency_slot_id = 2
        dependency.dependency_type = "requires"
        dependency.condition = json.dumps({"operator": "not_equals"})
        dependency.description = "目的地依赖于出发地"
        dependency.created_at = datetime(2024, 1, 1, 10, 0, 0)
        
        # 转换为字典
        dependency_dict = dependency.to_dict()
        
        # 验证字典内容
        assert dependency_dict['id'] == 1
        assert dependency_dict['dependent_slot_id'] == 1
        assert dependency_dict['dependency_slot_id'] == 2
        assert dependency_dict['dependency_type'] == "requires"
        assert isinstance(dependency_dict['condition'], dict)
        assert dependency_dict['description'] == "目的地依赖于出发地"