#!/usr/bin/env python3
"""
TASK-015 依赖系统测试运行器
不依赖pytest，直接运行核心功能测试
"""

import sys
import asyncio
from datetime import datetime
from typing import Dict, List, Any

# 添加项目路径
sys.path.insert(0, '.')

# 兼容性AsyncMock
class AsyncMock:
    def __init__(self, return_value=None):
        self.return_value = return_value
        self.call_count = 0
        self.call_args_list = []
    
    async def __call__(self, *args, **kwargs):
        self.call_count += 1
        self.call_args_list.append((args, kwargs))
        return self.return_value

# 导入要测试的模块
from src.core.dependency_graph import (
    DependencyGraph, DependencyNode, DependencyEdge, 
    DependencyType, DependencyGraphResult, DependencyGraphManager
)
from src.core.slot_inheritance import (
    SlotInheritanceEngine, ConversationInheritanceManager,
    InheritanceType, InheritanceStrategy, InheritanceRule, InheritanceResult
)


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


def test_dependency_graph_basic():
    """测试依赖图基本功能"""
    print("=== 测试依赖图基本功能 ===")
    
    # 创建测试数据
    slots = [
        MockSlot(1, "departure_city", "TEXT", True),
        MockSlot(2, "arrival_city", "TEXT", True),
        MockSlot(3, "departure_date", "DATE", True),
    ]
    
    dependencies = [
        MockSlotDependency(slots[0], slots[1], "required"),
        MockSlotDependency(slots[1], slots[2], "conditional", {"type": "has_value"})
    ]
    
    # 测试图创建
    graph = DependencyGraph()
    
    for slot in slots:
        graph.add_node(slot)
    
    for dep in dependencies:
        graph.add_edge(dep)
    
    assert len(graph.nodes) == 3
    assert len(graph.edges) == 2
    print("✓ 依赖图创建成功")
    
    # 测试拓扑排序
    order = graph.topological_sort()
    assert len(order) == 3
    assert order.index("departure_city") < order.index("arrival_city")
    print("✓ 拓扑排序正确")
    
    # 测试依赖验证
    slot_values = {
        "departure_city": "北京",
        "arrival_city": "上海"
    }
    
    result = graph.validate_dependencies(slot_values)
    assert result.is_valid is True
    print("✓ 依赖验证通过")
    
    # 测试下一个可填充槽位
    slot_values = {"departure_city": "北京"}
    fillable = graph.get_next_fillable_slots(slot_values)
    assert "arrival_city" in fillable
    print("✓ 下一个可填充槽位识别正确")


def test_cycle_detection():
    """测试循环依赖检测"""
    print("\n=== 测试循环依赖检测 ===")
    
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
    print("✓ 循环依赖检测成功")


def test_slot_inheritance_engine():
    """测试槽位继承引擎"""
    print("\n=== 测试槽位继承引擎 ===")
    
    engine = SlotInheritanceEngine()
    
    # 测试值转换器
    phone = engine._format_phone_number("13800138000")
    assert phone == "138-0013-8000"
    print("✓ 电话号码格式化正确")
    
    city = engine._extract_city_name("北京")
    assert city == "北京市"
    print("✓ 城市名提取正确")
    
    name = engine._normalize_person_name("  zhang san  ")
    assert name == "Zhang San"
    print("✓ 人名标准化正确")
    
    # 测试继承规则
    rule = InheritanceRule(
        source_slot="departure_city",
        target_slot="departure_city",
        inheritance_type=InheritanceType.SESSION,
        strategy=InheritanceStrategy.SUPPLEMENT,
        priority=10
    )
    
    engine.add_rule(rule)
    assert len(engine.inheritance_rules) == 1
    print("✓ 继承规则添加成功")


async def test_value_inheritance():
    """测试值继承功能"""
    print("\n=== 测试值继承功能 ===")
    
    engine = SlotInheritanceEngine()
    
    # 添加测试规则
    rules = [
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
    
    for rule in rules:
        engine.add_rule(rule)
    
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
    
    result = await engine.inherit_slot_values(intent_slots, current_values, context)
    
    assert "departure_city" in result.inherited_values
    assert result.inherited_values["departure_city"] == "北京"
    assert "phone_number" in result.inherited_values
    assert result.inherited_values["phone_number"] == "138-0013-8000"
    assert len(result.applied_rules) == 2
    print("✓ 值继承功能正常")


async def test_conditional_inheritance():
    """测试条件继承"""
    print("\n=== 测试条件继承 ===")
    
    engine = SlotInheritanceEngine()
    
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
    
    engine.add_rule(rule)
    
    intent_slots = [MockSlot(1, "departure_city")]
    
    # 测试目标槽位为空的情况
    current_values = {}
    context = {
        "conversation_context": {"last_departure": "上海"},
        "current_values": current_values
    }
    
    result = await engine.inherit_slot_values(intent_slots, current_values, context)
    
    assert "departure_city" in result.inherited_values
    assert result.inherited_values["departure_city"] == "上海"
    print("✓ 条件继承（槽位为空）正常")
    
    # 测试目标槽位已有值的情况
    current_values = {"departure_city": "北京"}
    context["current_values"] = current_values
    
    result = await engine.inherit_slot_values(intent_slots, current_values, context)
    
    # 应该跳过继承
    assert len(result.skipped_rules) > 0
    print("✓ 条件继承（槽位已有值）正常跳过")


def test_advanced_dependency_scenarios():
    """测试高级依赖场景"""
    print("\n=== 测试高级依赖场景 ===")
    
    # 测试互斥依赖
    graph = DependencyGraph()
    
    slots = [
        MockSlot(1, "one_way", "BOOLEAN"),
        MockSlot(2, "round_trip", "BOOLEAN")
    ]
    
    for slot in slots:
        graph.add_node(slot)
    
    # 创建互斥依赖
    mutex_dep = MockSlotDependency(slots[0], slots[1], "mutex")
    graph.add_edge(mutex_dep)
    
    # 测试互斥冲突
    slot_values = {
        "one_way": True,
        "round_trip": True
    }
    
    result = graph.validate_dependencies(slot_values)
    # 应该检测到冲突
    assert len(result.unsatisfied_dependencies) > 0
    print("✓ 互斥依赖冲突检测正常")
    
    # 测试层次依赖
    graph2 = DependencyGraph()
    
    slots2 = [
        MockSlot(1, "country", "TEXT"),
        MockSlot(2, "city", "TEXT"),
        MockSlot(3, "address", "TEXT")
    ]
    
    for slot in slots2:
        graph2.add_node(slot)
    
    # 创建层次依赖：country -> city -> address
    deps = [
        MockSlotDependency(slots2[0], slots2[1], "hierarchical"),
        MockSlotDependency(slots2[1], slots2[2], "hierarchical")
    ]
    
    for dep in deps:
        graph2.add_edge(dep)
    
    # 测试层次依赖解析顺序
    order = graph2.topological_sort()
    assert order.index("country") < order.index("city")
    assert order.index("city") < order.index("address")
    print("✓ 层次依赖排序正常")


async def test_dependency_graph_manager():
    """测试依赖图管理器"""
    print("\n=== 测试依赖图管理器 ===")
    
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
    print("✓ 依赖图管理器构建图成功")
    
    # 验证缓存
    cached_graph = manager.get_graph(1)
    assert cached_graph is graph
    print("✓ 依赖图缓存正常")
    
    # 测试缓存失效
    manager.invalidate_graph(1)
    assert manager.get_graph(1) is None
    print("✓ 依赖图缓存失效正常")


async def main():
    """主测试函数"""
    print("开始TASK-015依赖系统综合测试...\n")
    
    try:
        # 同步测试
        test_dependency_graph_basic()
        test_cycle_detection()
        test_slot_inheritance_engine()
        test_advanced_dependency_scenarios()
        
        # 异步测试
        await test_value_inheritance()
        await test_conditional_inheritance()
        await test_dependency_graph_manager()
        
        print("\n" + "="*50)
        print("🎉 所有依赖系统测试通过！")
        print("✅ TASK-015 槽位依赖关系处理 - 测试完成")
        print("="*50)
        
        return True
        
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    # 运行测试
    success = asyncio.run(main())
    sys.exit(0 if success else 1)