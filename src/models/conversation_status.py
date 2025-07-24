"""
对话状态模型
"""
from peewee import *
from playhouse.mysql_ext import JSONField
from .base import CommonModel
from datetime import datetime
from typing import List, Dict, Optional, Set
import json


class ConversationStatus(CommonModel):
    """对话状态表 - 与MySQL Schema对应"""
    
    # 主键字段
    id = AutoField(primary_key=True, verbose_name="主键ID")
    
    # 核心状态字段
    status_code = CharField(max_length=50, unique=True, verbose_name="状态代码")
    status_name = CharField(max_length=100, verbose_name="状态名称")
    description = TextField(null=True, verbose_name="状态描述")
    category = CharField(max_length=50, null=True, verbose_name="状态分类")
    
    # 流程控制字段
    is_final = BooleanField(default=False, verbose_name="是否为最终状态")
    next_allowed_statuses = JSONField(null=True, verbose_name="允许的下一状态列表")
    auto_transition_rules = JSONField(null=True, verbose_name="自动转换规则")
    
    # 业务字段
    notification_required = BooleanField(default=False, verbose_name="是否需要通知")
    sort_order = IntegerField(default=1, verbose_name="排序顺序")
    is_active = BooleanField(default=True, verbose_name="是否激活")
    
    class Meta:
        table_name = 'conversation_statuses'
        indexes = (
            (('status_code',), True),  # 唯一索引
            (('category',), False),
            (('is_active', 'sort_order'), False),
            (('is_final',), False),
        )
    
    def get_next_allowed_statuses(self) -> List[str]:
        """获取允许的下一状态代码列表"""
        if self.next_allowed_statuses:
            return self.next_allowed_statuses if isinstance(self.next_allowed_statuses, list) else []
        return []
    
    def set_next_allowed_statuses(self, status_codes: List[str]):
        """设置允许的下一状态代码列表"""
        self.next_allowed_statuses = status_codes
    
    def add_next_allowed_status(self, status_code: str):
        """添加一个允许的下一状态"""
        current_statuses = self.get_next_allowed_statuses()
        if status_code not in current_statuses:
            current_statuses.append(status_code)
            self.set_next_allowed_statuses(current_statuses)
    
    def remove_next_allowed_status(self, status_code: str):
        """移除一个允许的下一状态"""
        current_statuses = self.get_next_allowed_statuses()
        if status_code in current_statuses:
            current_statuses.remove(status_code)
            self.set_next_allowed_statuses(current_statuses)
    
    def get_auto_transition_rules(self) -> Dict:
        """获取自动转换规则"""
        if self.auto_transition_rules:
            return self.auto_transition_rules if isinstance(self.auto_transition_rules, dict) else {}
        return {}
    
    def set_auto_transition_rules(self, rules: Dict):
        """设置自动转换规则"""
        self.auto_transition_rules = rules
    
    def can_transition_to(self, target_status_code: str) -> bool:
        """检查是否可以转换到目标状态"""
        if self.is_final:
            return False
        
        allowed_statuses = self.get_next_allowed_statuses()
        if not allowed_statuses:  # 如果没有限制，允许转换到任何状态
            return True
        
        return target_status_code in allowed_statuses
    
    def should_auto_transition(self, context: Dict = None) -> Optional[str]:
        """
        检查是否应该自动转换状态
        返回目标状态代码，如果不需要自动转换则返回None
        """
        rules = self.get_auto_transition_rules()
        if not rules:
            return None
        
        context = context or {}
        
        # 检查时间条件
        if 'timeout' in rules:
            timeout_rule = rules['timeout']
            if isinstance(timeout_rule, dict):
                timeout_minutes = timeout_rule.get('minutes', 0)
                target_status = timeout_rule.get('target_status')
                
                if timeout_minutes > 0 and target_status:
                    time_diff = datetime.now() - self.updated_at
                    if time_diff.total_seconds() / 60 >= timeout_minutes:
                        return target_status
        
        # 检查条件规则
        if 'conditions' in rules:
            conditions = rules['conditions']
            if isinstance(conditions, list):
                for condition in conditions:
                    if self._check_condition(condition, context):
                        return condition.get('target_status')
        
        return None
    
    def _check_condition(self, condition: Dict, context: Dict) -> bool:
        """检查单个条件是否满足"""
        if not isinstance(condition, dict):
            return False
        
        # 检查上下文条件
        if 'context_key' in condition:
            context_key = condition['context_key']
            expected_value = condition.get('expected_value')
            operator = condition.get('operator', 'eq')  # eq, ne, gt, lt, in, not_in
            
            actual_value = context.get(context_key)
            
            if operator == 'eq':
                return actual_value == expected_value
            elif operator == 'ne':
                return actual_value != expected_value
            elif operator == 'gt':
                return actual_value and actual_value > expected_value
            elif operator == 'lt':
                return actual_value and actual_value < expected_value
            elif operator == 'in':
                return actual_value in expected_value if isinstance(expected_value, list) else False
            elif operator == 'not_in':
                return actual_value not in expected_value if isinstance(expected_value, list) else True
        
        return False
    
    def is_initial_status(self) -> bool:
        """检查是否为初始状态"""
        return self.category == 'initial' or self.status_code in ['new', 'created', 'initiated']
    
    def is_processing_status(self) -> bool:
        """检查是否为处理中状态"""
        return self.category == 'processing' or self.status_code in ['processing', 'in_progress', 'analyzing']
    
    def is_waiting_status(self) -> bool:
        """检查是否为等待状态"""
        return self.category == 'waiting' or self.status_code in ['waiting', 'pending', 'awaiting_input']
    
    def is_completed_status(self) -> bool:
        """检查是否为完成状态"""
        return self.category == 'completed' or self.is_final
    
    def is_error_status(self) -> bool:
        """检查是否为错误状态"""
        return self.category == 'error' or self.status_code in ['error', 'failed', 'exception']
    
    @classmethod
    def get_by_code(cls, status_code: str) -> Optional['ConversationStatus']:
        """根据状态代码获取状态"""
        try:
            return cls.select().where(cls.status_code == status_code, cls.is_active == True).get()
        except cls.DoesNotExist:
            return None
    
    @classmethod
    def get_initial_statuses(cls) -> List['ConversationStatus']:
        """获取所有初始状态"""
        return list(cls.select().where(
            cls.is_active == True,
            ((cls.category == 'initial') | (cls.status_code.in_(['new', 'created', 'initiated'])))
        ).order_by(cls.sort_order))
    
    @classmethod
    def get_final_statuses(cls) -> List['ConversationStatus']:
        """获取所有最终状态"""
        return list(cls.select().where(
            cls.is_active == True,
            cls.is_final == True
        ).order_by(cls.sort_order))
    
    @classmethod
    def get_by_category(cls, category: str) -> List['ConversationStatus']:
        """根据分类获取状态列表"""
        return list(cls.select().where(
            cls.category == category,
            cls.is_active == True
        ).order_by(cls.sort_order))
    
    @classmethod
    def get_active_statuses(cls) -> List['ConversationStatus']:
        """获取所有激活的状态"""
        return list(cls.select().where(cls.is_active == True).order_by(cls.sort_order))
    
    @classmethod
    def create_status_flow(cls, status_flow_config: List[Dict]) -> List['ConversationStatus']:
        """
        创建状态流
        
        Args:
            status_flow_config: 状态流配置列表，每个元素包含状态定义
        
        Returns:
            创建的状态列表
        
        Example:
            config = [
                {
                    'status_code': 'new',
                    'status_name': '新建',
                    'category': 'initial',
                    'next_allowed': ['processing']
                },
                {
                    'status_code': 'processing',
                    'status_name': '处理中',
                    'category': 'processing',
                    'next_allowed': ['completed', 'error']
                }
            ]
        """
        created_statuses = []
        
        for config in status_flow_config:
            # 检查状态是否已存在
            existing = cls.get_by_code(config['status_code'])
            if existing:
                # 更新现有状态
                for key, value in config.items():
                    if key == 'next_allowed':
                        existing.set_next_allowed_statuses(value)
                    elif hasattr(existing, key):
                        setattr(existing, key, value)
                existing.save()
                created_statuses.append(existing)
            else:
                # 创建新状态
                next_allowed = config.pop('next_allowed', [])
                status = cls.create(**config)
                if next_allowed:
                    status.set_next_allowed_statuses(next_allowed)
                    status.save()
                created_statuses.append(status)
        
        return created_statuses
    
    @classmethod
    def validate_status_flow(cls, status_codes: List[str]) -> Dict[str, List[str]]:
        """
        验证状态流的有效性
        
        Returns:
            验证结果字典，包含错误和警告信息
        """
        result = {
            'errors': [],
            'warnings': []
        }
        
        # 检查状态是否存在
        existing_codes = set()
        for code in status_codes:
            status = cls.get_by_code(code)
            if not status:
                result['errors'].append(f"状态代码 '{code}' 不存在")
            else:
                existing_codes.add(code)
        
        if result['errors']:
            return result
        
        # 检查流程连通性
        statuses = {code: cls.get_by_code(code) for code in existing_codes}
        
        # 检查是否有初始状态
        initial_statuses = [code for code, status in statuses.items() if status.is_initial_status()]
        if not initial_statuses:
            result['warnings'].append("没有找到初始状态")
        
        # 检查是否有最终状态
        final_statuses = [code for code, status in statuses.items() if status.is_final]
        if not final_statuses:
            result['warnings'].append("没有找到最终状态")
        
        # 检查状态转换的连通性
        unreachable_statuses = cls._find_unreachable_statuses(statuses)
        if unreachable_statuses:
            result['warnings'].append(f"无法到达的状态: {', '.join(unreachable_statuses)}")
        
        return result
    
    @classmethod
    def _find_unreachable_statuses(cls, statuses: Dict[str, 'ConversationStatus']) -> List[str]:
        """找出无法到达的状态"""
        if not statuses:
            return []
        
        # 使用BFS查找所有可达状态
        initial_statuses = [code for code, status in statuses.items() if status.is_initial_status()]
        if not initial_statuses:
            # 如果没有明确的初始状态，使用第一个状态
            initial_statuses = [list(statuses.keys())[0]]
        
        reachable = set()
        queue = list(initial_statuses)
        
        while queue:
            current = queue.pop(0)
            if current in reachable:
                continue
            
            reachable.add(current)
            status = statuses.get(current)
            if status:
                next_statuses = status.get_next_allowed_statuses()
                for next_status in next_statuses:
                    if next_status in statuses and next_status not in reachable:
                        queue.append(next_status)
        
        # 返回无法到达的状态
        all_statuses = set(statuses.keys())
        return list(all_statuses - reachable)
    
    @classmethod
    def get_status_transition_graph(cls) -> Dict[str, List[str]]:
        """获取状态转换图"""
        statuses = cls.get_active_statuses()
        graph = {}
        
        for status in statuses:
            graph[status.status_code] = status.get_next_allowed_statuses()
        
        return graph
    
    def __str__(self):
        return f"ConversationStatus({self.status_code}: {self.status_name})"
    
    def __repr__(self):
        return f"<ConversationStatus id={self.id} code='{self.status_code}' name='{self.status_name}'>"