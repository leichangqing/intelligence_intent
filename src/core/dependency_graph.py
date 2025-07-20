"""
槽位依赖关系图引擎
处理复杂的槽位依赖关系，包括循环检测、依赖解析和优化处理
"""

from typing import Dict, List, Set, Tuple, Optional, Any
from collections import defaultdict, deque
from dataclasses import dataclass
from enum import Enum
import logging

from ..models.slot import Slot, SlotDependency
from ..utils.logger import get_logger

logger = get_logger(__name__)


class DependencyType(Enum):
    """扩展的依赖类型"""
    REQUIRED = "required"
    CONDITIONAL = "conditional"
    MUTEX = "mutex"
    HIERARCHICAL = "hierarchical"      # 层次依赖 A->B->C
    GROUP_ANY = "group_any"           # 组依赖：任一满足
    GROUP_ALL = "group_all"           # 组依赖：全部满足
    CROSS_INTENT = "cross_intent"     # 跨意图依赖
    TEMPORAL = "temporal"             # 时间依赖
    COMPUTED = "computed"             # 计算依赖


@dataclass
class DependencyNode:
    """依赖节点"""
    slot_id: int
    slot_name: str
    slot_type: str
    is_required: bool
    dependencies: List['DependencyEdge']
    dependents: List['DependencyEdge']
    
    def __post_init__(self):
        if self.dependencies is None:
            self.dependencies = []
        if self.dependents is None:
            self.dependents = []


@dataclass
class DependencyEdge:
    """依赖边"""
    from_slot: str
    to_slot: str
    dependency_type: DependencyType
    condition: Dict[str, Any]
    priority: int
    is_satisfied: bool = False
    
    def __str__(self):
        return f"{self.from_slot} -> {self.to_slot} ({self.dependency_type.value})"


@dataclass
class DependencyGraphResult:
    """依赖图分析结果"""
    is_valid: bool
    has_cycles: bool
    cycles: List[List[str]]
    resolution_order: List[str]
    unsatisfied_dependencies: List[DependencyEdge]
    conflicts: List[Tuple[DependencyEdge, DependencyEdge]]
    error_messages: List[str]


class DependencyGraph:
    """槽位依赖关系图"""
    
    def __init__(self):
        self.nodes: Dict[str, DependencyNode] = {}
        self.edges: List[DependencyEdge] = []
        self.adjacency_list: Dict[str, List[str]] = defaultdict(list)
        self.reverse_adjacency_list: Dict[str, List[str]] = defaultdict(list)
        
    def add_node(self, slot: Slot):
        """添加槽位节点"""
        node = DependencyNode(
            slot_id=slot.id,
            slot_name=slot.slot_name,
            slot_type=slot.slot_type,
            is_required=slot.is_required,
            dependencies=[],
            dependents=[]
        )
        self.nodes[slot.slot_name] = node
        logger.debug(f"添加依赖节点: {slot.slot_name}")
    
    def add_edge(self, dependency: SlotDependency):
        """添加依赖边"""
        from_slot = dependency.required_slot.slot_name
        to_slot = dependency.dependent_slot.slot_name
        
        # 转换依赖类型
        dep_type = DependencyType(dependency.dependency_type)
        
        edge = DependencyEdge(
            from_slot=from_slot,
            to_slot=to_slot,
            dependency_type=dep_type,
            condition=dependency.get_condition(),
            priority=dependency.priority
        )
        
        self.edges.append(edge)
        self.adjacency_list[from_slot].append(to_slot)
        self.reverse_adjacency_list[to_slot].append(from_slot)
        
        # 更新节点的依赖关系
        if from_slot in self.nodes:
            self.nodes[from_slot].dependents.append(edge)
        if to_slot in self.nodes:
            self.nodes[to_slot].dependencies.append(edge)
        
        logger.debug(f"添加依赖边: {edge}")
    
    def detect_cycles(self) -> Tuple[bool, List[List[str]]]:
        """检测循环依赖"""
        cycles = []
        visited = set()
        rec_stack = set()
        path = []
        
        def dfs(node: str) -> bool:
            if node in rec_stack:
                # 找到循环，提取循环路径
                cycle_start = path.index(node)
                cycle = path[cycle_start:] + [node]
                cycles.append(cycle)
                return True
            
            if node in visited:
                return False
            
            visited.add(node)
            rec_stack.add(node)
            path.append(node)
            
            for neighbor in self.adjacency_list[node]:
                if dfs(neighbor):
                    return True
            
            rec_stack.remove(node)
            path.pop()
            return False
        
        # 检查所有节点
        for node in self.nodes:
            if node not in visited:
                dfs(node)
        
        has_cycles = len(cycles) > 0
        if has_cycles:
            logger.warning(f"检测到循环依赖: {cycles}")
        
        return has_cycles, cycles
    
    def topological_sort(self) -> List[str]:
        """拓扑排序获取依赖解析顺序"""
        in_degree = defaultdict(int)
        
        # 计算入度
        for node in self.nodes:
            in_degree[node] = 0
        
        for edge in self.edges:
            in_degree[edge.to_slot] += 1
        
        # 使用优先队列（按优先级排序）
        queue = deque()
        for node in self.nodes:
            if in_degree[node] == 0:
                queue.append(node)
        
        result = []
        while queue:
            # 按优先级排序（必需槽位优先）
            queue = deque(sorted(queue, key=lambda x: (
                not self.nodes[x].is_required,  # 必需槽位优先
                self.nodes[x].slot_name        # 字典序
            )))
            
            current = queue.popleft()
            result.append(current)
            
            # 更新邻接节点的入度
            for neighbor in self.adjacency_list[current]:
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)
        
        # 检查是否有环（未处理的节点）
        if len(result) != len(self.nodes):
            logger.error("拓扑排序失败，可能存在循环依赖")
            # 返回部分结果
            remaining = [node for node in self.nodes if node not in result]
            result.extend(remaining)
        
        return result
    
    def validate_dependencies(self, slot_values: Dict[str, Any]) -> DependencyGraphResult:
        """验证依赖关系图"""
        # 检测循环
        has_cycles, cycles = self.detect_cycles()
        
        # 获取解析顺序
        resolution_order = self.topological_sort()
        
        # 检查未满足的依赖
        unsatisfied_dependencies = []
        conflicts = []
        error_messages = []
        
        for edge in self.edges:
            is_satisfied = self._evaluate_dependency(edge, slot_values)
            edge.is_satisfied = is_satisfied
            
            if not is_satisfied:
                unsatisfied_dependencies.append(edge)
        
        # 检测冲突
        conflicts = self._detect_conflicts()
        
        # 生成错误消息
        if has_cycles:
            error_messages.extend([f"循环依赖: {' -> '.join(cycle)}" for cycle in cycles])
        
        if unsatisfied_dependencies:
            error_messages.extend([
                f"未满足依赖: {dep.from_slot} -> {dep.to_slot}" 
                for dep in unsatisfied_dependencies
            ])
        
        if conflicts:
            error_messages.extend([
                f"依赖冲突: {dep1} vs {dep2}" 
                for dep1, dep2 in conflicts
            ])
        
        is_valid = not (has_cycles or conflicts)
        
        return DependencyGraphResult(
            is_valid=is_valid,
            has_cycles=has_cycles,
            cycles=cycles,
            resolution_order=resolution_order,
            unsatisfied_dependencies=unsatisfied_dependencies,
            conflicts=conflicts,
            error_messages=error_messages
        )
    
    def _evaluate_dependency(self, edge: DependencyEdge, slot_values: Dict[str, Any]) -> bool:
        """评估单个依赖是否满足"""
        from_value = slot_values.get(edge.from_slot)
        to_value = slot_values.get(edge.to_slot)
        
        if edge.dependency_type == DependencyType.REQUIRED:
            return from_value is not None
        
        elif edge.dependency_type == DependencyType.CONDITIONAL:
            return self._evaluate_conditional_dependency(edge, slot_values)
        
        elif edge.dependency_type == DependencyType.MUTEX:
            # 互斥：两个槽位不能同时有值
            return not (from_value is not None and to_value is not None)
        
        elif edge.dependency_type == DependencyType.HIERARCHICAL:
            # 层次依赖：需要检查整个链
            return self._evaluate_hierarchical_dependency(edge, slot_values)
        
        return True
    
    def _evaluate_conditional_dependency(self, edge: DependencyEdge, 
                                       slot_values: Dict[str, Any]) -> bool:
        """评估条件依赖"""
        condition = edge.condition
        if not condition:
            return True
        
        condition_type = condition.get('type', 'has_value')
        target_slot = condition.get('slot', edge.from_slot)
        expected_value = condition.get('value')
        
        actual_value = slot_values.get(target_slot)
        
        if condition_type == 'value_equals':
            return str(actual_value) == str(expected_value)
        elif condition_type == 'value_in':
            return actual_value in expected_value if isinstance(expected_value, list) else False
        elif condition_type == 'has_value':
            return actual_value is not None and str(actual_value).strip() != ''
        elif condition_type == 'value_range':
            # 新增：范围条件
            min_val = condition.get('min')
            max_val = condition.get('max')
            try:
                num_val = float(actual_value)
                return (min_val is None or num_val >= min_val) and \
                       (max_val is None or num_val <= max_val)
            except (ValueError, TypeError):
                return False
        
        return True
    
    def _evaluate_hierarchical_dependency(self, edge: DependencyEdge, 
                                        slot_values: Dict[str, Any]) -> bool:
        """评估层次依赖"""
        # 简化实现：检查直接依赖
        from_value = slot_values.get(edge.from_slot)
        return from_value is not None
    
    def _detect_conflicts(self) -> List[Tuple[DependencyEdge, DependencyEdge]]:
        """检测依赖冲突"""
        conflicts = []
        
        # 检查互斥冲突
        mutex_edges = [e for e in self.edges if e.dependency_type == DependencyType.MUTEX]
        required_edges = [e for e in self.edges if e.dependency_type == DependencyType.REQUIRED]
        
        for mutex_edge in mutex_edges:
            for req_edge in required_edges:
                # 如果互斥的两个槽位都被要求，这是冲突
                if ((mutex_edge.from_slot == req_edge.to_slot and 
                     mutex_edge.to_slot in [e.to_slot for e in required_edges]) or
                    (mutex_edge.to_slot == req_edge.to_slot and 
                     mutex_edge.from_slot in [e.to_slot for e in required_edges])):
                    conflicts.append((mutex_edge, req_edge))
        
        return conflicts
    
    def get_next_fillable_slots(self, slot_values: Dict[str, Any]) -> List[str]:
        """获取下一个可填充的槽位列表"""
        fillable = []
        
        for slot_name, node in self.nodes.items():
            # 跳过已填充的槽位
            if slot_name in slot_values:
                continue
            
            # 检查是否所有依赖都已满足
            all_deps_satisfied = True
            for dep_edge in node.dependencies:
                if not self._evaluate_dependency(dep_edge, slot_values):
                    all_deps_satisfied = False
                    break
            
            if all_deps_satisfied:
                fillable.append(slot_name)
        
        # 按优先级排序（必需槽位优先）
        fillable.sort(key=lambda x: (
            not self.nodes[x].is_required,
            self.nodes[x].slot_name
        ))
        
        return fillable
    
    def get_dependency_chain(self, slot_name: str) -> List[str]:
        """获取槽位的完整依赖链"""
        chain = []
        visited = set()
        
        def dfs(current: str):
            if current in visited:
                return
            visited.add(current)
            
            # 添加当前槽位的所有依赖
            for dep_edge in self.nodes.get(current, DependencyNode(0, "", "", False, [], [])).dependencies:
                dfs(dep_edge.from_slot)
                if dep_edge.from_slot not in chain:
                    chain.append(dep_edge.from_slot)
        
        dfs(slot_name)
        chain.append(slot_name)  # 添加目标槽位
        
        return chain
    
    def optimize_resolution_order(self, slot_values: Dict[str, Any]) -> List[str]:
        """优化槽位解析顺序"""
        # 基于当前状态和依赖关系优化顺序
        fillable = self.get_next_fillable_slots(slot_values)
        
        # 按影响的依赖数量排序（影响更多槽位的优先）
        def impact_score(slot_name: str) -> int:
            score = 0
            # 必需槽位加分
            if self.nodes[slot_name].is_required:
                score += 100
            
            # 依赖此槽位的槽位数量
            dependents_count = len(self.nodes[slot_name].dependents)
            score += dependents_count * 10
            
            # 优先级
            max_priority = max(
                (edge.priority for edge in self.nodes[slot_name].dependents), 
                default=0
            )
            score += max_priority
            
            return score
        
        fillable.sort(key=impact_score, reverse=True)
        return fillable
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式用于序列化"""
        return {
            'nodes': {
                name: {
                    'slot_id': node.slot_id,
                    'slot_name': node.slot_name,
                    'slot_type': node.slot_type,
                    'is_required': node.is_required,
                    'dependency_count': len(node.dependencies),
                    'dependent_count': len(node.dependents)
                }
                for name, node in self.nodes.items()
            },
            'edges': [
                {
                    'from': edge.from_slot,
                    'to': edge.to_slot,
                    'type': edge.dependency_type.value,
                    'priority': edge.priority,
                    'is_satisfied': edge.is_satisfied
                }
                for edge in self.edges
            ]
        }


class DependencyGraphManager:
    """依赖图管理器"""
    
    def __init__(self):
        self._graphs: Dict[int, DependencyGraph] = {}  # intent_id -> graph
    
    async def build_graph(self, intent_id: int, slots: List[Slot], 
                         dependencies: List[SlotDependency]) -> DependencyGraph:
        """构建意图的依赖图"""
        graph = DependencyGraph()
        
        # 添加所有槽位节点
        for slot in slots:
            graph.add_node(slot)
        
        # 添加所有依赖边
        for dependency in dependencies:
            graph.add_edge(dependency)
        
        # 缓存图
        self._graphs[intent_id] = graph
        
        logger.info(f"构建依赖图完成: intent_id={intent_id}, "
                   f"节点数={len(graph.nodes)}, 边数={len(graph.edges)}")
        
        return graph
    
    def get_graph(self, intent_id: int) -> Optional[DependencyGraph]:
        """获取缓存的依赖图"""
        return self._graphs.get(intent_id)
    
    def invalidate_graph(self, intent_id: int):
        """使依赖图缓存失效"""
        if intent_id in self._graphs:
            del self._graphs[intent_id]
            logger.info(f"依赖图缓存失效: intent_id={intent_id}")
    
    def clear_cache(self):
        """清空所有缓存"""
        self._graphs.clear()
        logger.info("清空依赖图缓存")


# 全局依赖图管理器实例
dependency_graph_manager = DependencyGraphManager()