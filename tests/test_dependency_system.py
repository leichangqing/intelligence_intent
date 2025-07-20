"""
TASK-015 综合测试：槽位依赖关系处理系统
测试依赖图、槽位继承和高级依赖处理功能
"""

import pytest
import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Any

# 兼容性导入
try:
    from unittest.mock import AsyncMock
except ImportError:
    class AsyncMock:
        def __init__(self, return_value=None):
            self.return_value = return_value
            self.call_count = 0
            self.call_args_list = []
        
        async def __call__(self, *args, **kwargs):
            self.call_count += 1
            self.call_args_list.append((args, kwargs))
            return self.return_value

from src.core.dependency_graph import (
    DependencyGraph, DependencyNode, DependencyEdge, 
    DependencyType, DependencyGraphResult, DependencyGraphManager
)
from src.core.slot_inheritance import (
    SlotInheritanceEngine, ConversationInheritanceManager,
    InheritanceType, InheritanceStrategy, InheritanceRule, InheritanceResult
)
from src.services.slot_service import SlotService, SlotExtractionResult
from src.models.slot import Slot, SlotDependency


class MockSlot:
    """Mock槽位对象"""
    def __init__(self, id: int, slot_name: str, slot_type: str = "TEXT", 
                 is_required: bool = False, intent_id: int = 1):
        self.id = id
        self.slot_name = slot_name
        self.slot_type = slot_type
        self.is_required = is_required
        self.intent_id = intent_id


class MockSlotDependency:
    """Mock槽位依赖对象"""
    def __init__(self, required_slot: MockSlot, dependent_slot: MockSlot,
                 dependency_type: str = "required", condition: Dict = None, priority: int = 1):
        self.required_slot = required_slot
        self.dependent_slot = dependent_slot
        self.dependency_type = dependency_type
        self.condition = condition or {}
        self.priority = priority
    
    def get_condition(self):
        return self.condition


class TestDependencyGraph:
    """测试依赖图功能"""
    
    @pytest.fixture
    def sample_slots(self):
        """示例槽位"""
        return [
            MockSlot(1, "departure_city", "TEXT", True),
            MockSlot(2, "arrival_city", "TEXT", True),
            MockSlot(3, "departure_date", "DATE", True),
            MockSlot(4, "return_date", "DATE", False),
            MockSlot(5, "passenger_count", "NUMBER", False)
        ]
    
    @pytest.fixture
    def sample_dependencies(self, sample_slots):
        """示例依赖关系"""
        return [
            MockSlotDependency(
                sample_slots[0], sample_slots[1], "required"  # departure_city -> arrival_city
            ),
            MockSlotDependency(
                sample_slots[1], sample_slots[2], "conditional",  # arrival_city -> departure_date
                {"type": "has_value"}
            ),
            MockSlotDependency(
                sample_slots[2], sample_slots[3], "conditional",  # departure_date -> return_date
                {"type": "value_equals", "value": "roundtrip"}
            )
        ]
    
    def test_dependency_graph_creation(self, sample_slots, sample_dependencies):
        """测试依赖图创建"""
        graph = DependencyGraph()
        
        # 添加节点
        for slot in sample_slots:
            graph.add_node(slot)
        
        assert len(graph.nodes) == 5
        assert "departure_city" in graph.nodes
        assert graph.nodes["departure_city"].is_required is True
        
        # 添加边
        for dep in sample_dependencies:
            graph.add_edge(dep)
        
        assert len(graph.edges) == 3
        assert len(graph.adjacency_list["departure_city"]) == 1
        assert "arrival_city" in graph.adjacency_list["departure_city"]
    
    def test_cycle_detection(self):
        """测试循环依赖检测"""
        graph = DependencyGraph()
        
        # 创建循环依赖场景
        slots = [
            MockSlot(1, "slot_a"),
            MockSlot(2, "slot_b"),
            MockSlot(3, "slot_c")
        ]
        
        for slot in slots:
            graph.add_node(slot)
        
        # 创建循环：A -> B -> C -> A
        dependencies = [
            MockSlotDependency(slots[0], slots[1], "required"),
            MockSlotDependency(slots[1], slots[2], "required"),
            MockSlotDependency(slots[2], slots[0], "required")
        ]
        
        for dep in dependencies:
            graph.add_edge(dep)
        
        has_cycles, cycles = graph.detect_cycles()
        assert has_cycles is True
        assert len(cycles) > 0
        assert any("slot_a" in cycle for cycle in cycles)
    
    def test_topological_sort(self, sample_slots, sample_dependencies):
        """测试拓扑排序"""
        graph = DependencyGraph()
        
        for slot in sample_slots:
            graph.add_node(slot)
        
        for dep in sample_dependencies:
            graph.add_edge(dep)
        
        order = graph.topological_sort()
        
        # 验证排序结果
        assert len(order) == 5
        assert order.index("departure_city") < order.index("arrival_city")
        assert order.index("arrival_city") < order.index("departure_date")
    
    def test_dependency_validation(self, sample_slots, sample_dependencies):
        """测试依赖验证"""
        graph = DependencyGraph()
        
        for slot in sample_slots:
            graph.add_node(slot)
        
        for dep in sample_dependencies:
            graph.add_edge(dep)
        
        # 测试满足所有依赖的情况
        slot_values = {
            "departure_city": "北京",
            "arrival_city": "上海",
            "departure_date": "2024-01-01"
        }
        
        result = graph.validate_dependencies(slot_values)
        assert result.is_valid is True
        assert result.has_cycles is False
        assert len(result.unsatisfied_dependencies) == 0
    
    def test_next_fillable_slots(self, sample_slots, sample_dependencies):
        """测试获取下一个可填充槽位"""
        graph = DependencyGraph()
        
        for slot in sample_slots:
            graph.add_node(slot)
        
        for dep in sample_dependencies:
            graph.add_edge(dep)
        
        # 初始状态：只有没有依赖的槽位可填充
        slot_values = {}
        fillable = graph.get_next_fillable_slots(slot_values)
        
        # departure_city 和 passenger_count 应该可填充（没有依赖）
        assert "departure_city" in fillable
        assert "passenger_count" in fillable
        assert "arrival_city" not in fillable  # 依赖 departure_city
        
        # 填充 departure_city 后
        slot_values = {"departure_city": "北京"}
        fillable = graph.get_next_fillable_slots(slot_values)
        assert "arrival_city" in fillable


class TestSlotInheritanceEngine:
    """测试槽位继承引擎"""
    
    @pytest.fixture
    def inheritance_engine(self):
        """继承引擎实例"""
        return SlotInheritanceEngine()
    
    @pytest.fixture
    def sample_rules(self):
        """示例继承规则"""
        return [
            InheritanceRule(
                source_slot="departure_city",
                target_slot="departure_city",
                inheritance_type=InheritanceType.SESSION,
                strategy=InheritanceStrategy.SUPPLEMENT,
                priority=10
            ),
            InheritanceRule(
                source_slot="phone_number",
                target_slot="phone_number",
                inheritance_type=InheritanceType.USER_PROFILE,
                strategy=InheritanceStrategy.SUPPLEMENT,
                transformation="format_phone",
                priority=15
            )
        ]
    
    def test_add_rules(self, inheritance_engine, sample_rules):
        """测试添加继承规则"""
        for rule in sample_rules:
            inheritance_engine.add_rule(rule)
        
        assert len(inheritance_engine.inheritance_rules) == 2
        # 验证按优先级排序
        assert inheritance_engine.inheritance_rules[0].priority == 15
        assert inheritance_engine.inheritance_rules[1].priority == 10
    
    @pytest.mark.asyncio
    async def test_value_inheritance(self, inheritance_engine, sample_rules):
        """测试值继承"""
        for rule in sample_rules:
            inheritance_engine.add_rule(rule)
        
        intent_slots = [
            MockSlot(1, "departure_city"),
            MockSlot(2, "phone_number")
        ]
        
        current_values = {}
        
        context = {
            "session_context": {"departure_city": "北京"},
            "user_profile": {"phone_number": "13800138000"},
            "current_values": current_values
        }
        
        result = await inheritance_engine.inherit_slot_values(
            intent_slots, current_values, context
        )
        
        assert "departure_city" in result.inherited_values
        assert result.inherited_values["departure_city"] == "北京"
        assert "phone_number" in result.inherited_values
        assert result.inherited_values["phone_number"] == "138-0013-8000"  # 格式化后
        assert len(result.applied_rules) == 2
    
    def test_value_transformers(self, inheritance_engine):
        """测试值转换器"""
        # 测试电话号码格式化
        phone = inheritance_engine._format_phone_number("13800138000")
        assert phone == "138-0013-8000"
        
        # 测试城市名提取
        city = inheritance_engine._extract_city_name("北京")
        assert city == "北京市"
        
        # 测试人名标准化
        name = inheritance_engine._normalize_person_name("  zhang san  ")
        assert name == "Zhang San"
    
    @pytest.mark.asyncio
    async def test_conditional_inheritance(self, inheritance_engine):
        """测试条件继承"""
        rule = InheritanceRule(
            source_slot="last_departure",
            target_slot="departure_city",
            inheritance_type=InheritanceType.CONTEXT,
            strategy=InheritanceStrategy.SUPPLEMENT,
            condition={
                "type": "slot_empty",
                "slot": "departure_city"
            }
        )
        
        inheritance_engine.add_rule(rule)
        
        intent_slots = [MockSlot(1, "departure_city")]
        
        # 测试目标槽位为空的情况
        current_values = {}
        context = {
            "conversation_context": {"last_departure": "上海"},
            "current_values": current_values
        }
        
        result = await inheritance_engine.inherit_slot_values(
            intent_slots, current_values, context
        )
        
        assert "departure_city" in result.inherited_values
        assert result.inherited_values["departure_city"] == "上海"
        
        # 测试目标槽位已有值的情况
        current_values = {"departure_city": "北京"}
        context["current_values"] = current_values
        
        result = await inheritance_engine.inherit_slot_values(
            intent_slots, current_values, context
        )
        
        # 应该跳过继承
        assert len(result.skipped_rules) > 0
        assert any("目标槽位已有值" in reason for _, reason in result.skipped_rules)


class TestIntegratedSlotService:
    """测试集成的槽位服务"""
    
    @pytest.fixture
    def mock_cache_service(self):
        """Mock缓存服务"""
        mock = AsyncMock()
        mock.get.return_value = None
        mock.set.return_value = True
        return mock
    
    @pytest.fixture
    def mock_nlu_engine(self):
        """Mock NLU引擎"""
        mock = AsyncMock()
        mock.extract_slots.return_value = {
            "departure_city": {
                "value": "北京",
                "confidence": 0.95,
                "source": "llm"
            }
        }
        return mock
    
    @pytest.mark.asyncio
    async def test_enhanced_slot_extraction(self, mock_cache_service, mock_nlu_engine):
        """测试增强的槽位提取"""
        # 创建槽位服务
        slot_service = SlotService(mock_cache_service, mock_nlu_engine)
        
        # Mock意图和槽位
        mock_intent = type('Intent', (), {'id': 1, 'intent_name': 'book_flight'})()
        
        # Mock _get_slot_definitions 方法
        mock_slots = [
            MockSlot(1, "departure_city", "TEXT", True),
            MockSlot(2, "arrival_city", "TEXT", True)
        ]
        
        slot_service._get_slot_definitions = AsyncMock(return_value=mock_slots)
        slot_service._get_or_build_dependency_graph = AsyncMock(return_value=DependencyGraph())
        slot_service._apply_slot_inheritance = AsyncMock(return_value=InheritanceResult({}, {}, [], []))
        slot_service._validate_slots = AsyncMock(return_value=({}, {}))
        slot_service._apply_dependency_validation = AsyncMock(return_value=({}, []))
        slot_service._save_slot_values = AsyncMock()
        
        # 执行测试
        result = await slot_service.extract_slots(
            mock_intent, 
            "我想从北京飞往上海",
            existing_slots={},
            context={"user_id": "test_user"}
        )
        
        # 验证结果
        assert isinstance(result, SlotExtractionResult)
        assert "departure_city" in result.slots


class TestDependencyGraphManager:
    """测试依赖图管理器"""
    
    @pytest.mark.asyncio
    async def test_build_and_cache_graph(self):
        """测试构建和缓存依赖图"""
        manager = DependencyGraphManager()
        
        slots = [
            MockSlot(1, "slot_a"),
            MockSlot(2, "slot_b")
        ]
        
        dependencies = [
            MockSlotDependency(slots[0], slots[1], "required")
        ]
        
        # 构建图
        graph = await manager.build_graph(1, slots, dependencies)
        
        assert len(graph.nodes) == 2
        assert len(graph.edges) == 1
        
        # 验证缓存
        cached_graph = manager.get_graph(1)
        assert cached_graph is graph
        
        # 测试缓存失效
        manager.invalidate_graph(1)
        assert manager.get_graph(1) is None


class TestAdvancedDependencyScenarios:
    """测试高级依赖场景"""
    
    def test_mutex_dependencies(self):
        """测试互斥依赖"""
        graph = DependencyGraph()
        
        slots = [
            MockSlot(1, "one_way", "BOOLEAN"),
            MockSlot(2, "round_trip", "BOOLEAN")
        ]
        
        for slot in slots:
            graph.add_node(slot)
        
        # 创建互斥依赖
        mutex_dep = MockSlotDependency(
            slots[0], slots[1], "mutex"
        )
        graph.add_edge(mutex_dep)
        
        # 测试互斥冲突
        slot_values = {
            "one_way": True,
            "round_trip": True
        }
        
        result = graph.validate_dependencies(slot_values)
        assert len(result.unsatisfied_dependencies) > 0
    
    def test_hierarchical_dependencies(self):
        """测试层次依赖"""
        graph = DependencyGraph()
        
        slots = [
            MockSlot(1, "country", "TEXT"),
            MockSlot(2, "city", "TEXT"),
            MockSlot(3, "address", "TEXT")
        ]
        
        for slot in slots:
            graph.add_node(slot)
        
        # 创建层次依赖：country -> city -> address
        deps = [
            MockSlotDependency(slots[0], slots[1], "hierarchical"),
            MockSlotDependency(slots[1], slots[2], "hierarchical")
        ]
        
        for dep in deps:
            graph.add_edge(dep)
        
        # 测试层次依赖解析顺序
        order = graph.topological_sort()
        assert order.index("country") < order.index("city")
        assert order.index("city") < order.index("address")
    
    def test_conditional_dependencies_with_range(self):
        """测试带范围条件的依赖"""
        graph = DependencyGraph()
        
        slots = [
            MockSlot(1, "age", "NUMBER"),
            MockSlot(2, "discount", "NUMBER")
        ]
        
        for slot in slots:
            graph.add_node(slot)
        
        # 年龄在18-65之间才需要折扣
        conditional_dep = MockSlotDependency(
            slots[0], slots[1], "conditional",
            {
                "type": "value_range",
                "min": 18,
                "max": 65
            }
        )
        graph.add_edge(conditional_dep)
        
        # 测试范围内的值
        slot_values = {"age": 25}
        result = graph.validate_dependencies(slot_values)
        # 在范围内，依赖应该被满足
        satisfied_deps = [e for e in graph.edges if e.is_satisfied]
        assert len(satisfied_deps) > 0
        
        # 测试范围外的值
        slot_values = {"age": 70}
        result = graph.validate_dependencies(slot_values)
        # 不在范围内，依赖不满足但这是正常的


if __name__ == "__main__":
    # 运行特定测试
    pytest.main([__file__, "-v"])