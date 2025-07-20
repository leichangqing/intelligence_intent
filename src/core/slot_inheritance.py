"""
槽位继承系统
处理槽位值的继承机制，包括上下文继承、依赖继承和模板继承
"""

from typing import Dict, List, Optional, Any, Set, Tuple
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
import logging

from ..models.slot import Slot, SlotValue, SlotDependency
from ..models.conversation import Conversation
from ..utils.logger import get_logger

logger = get_logger(__name__)


class InheritanceType(Enum):
    """继承类型"""
    CONTEXT = "context"           # 上下文继承
    SESSION = "session"           # 会话继承
    USER_PROFILE = "user_profile" # 用户档案继承
    DEPENDENCY = "dependency"     # 依赖继承
    TEMPLATE = "template"         # 模板继承
    DEFAULT = "default"           # 默认值继承


class InheritanceStrategy(Enum):
    """继承策略"""
    OVERRIDE = "override"         # 覆盖现有值
    MERGE = "merge"              # 合并值
    SUPPLEMENT = "supplement"     # 补充缺失值
    CONDITIONAL = "conditional"   # 条件继承


@dataclass
class InheritanceRule:
    """继承规则"""
    source_slot: str
    target_slot: str
    inheritance_type: InheritanceType
    strategy: InheritanceStrategy
    condition: Optional[Dict[str, Any]] = None
    transformation: Optional[str] = None  # 值转换函数名
    priority: int = 0
    ttl_seconds: Optional[int] = None     # 继承值的有效期


@dataclass
class InheritanceResult:
    """继承结果"""
    inherited_values: Dict[str, Any]
    inheritance_sources: Dict[str, str]  # slot_name -> source_description
    applied_rules: List[InheritanceRule]
    skipped_rules: List[Tuple[InheritanceRule, str]]  # rule, reason


class SlotInheritanceEngine:
    """槽位继承引擎"""
    
    def __init__(self):
        self.inheritance_rules: List[InheritanceRule] = []
        self.value_transformers: Dict[str, callable] = {}
        self._setup_default_transformers()
    
    def _setup_default_transformers(self):
        """设置默认的值转换器"""
        self.value_transformers.update({
            'to_lowercase': lambda x: str(x).lower(),
            'to_uppercase': lambda x: str(x).upper(),
            'normalize_date': self._normalize_date_value,
            'extract_city': self._extract_city_name,
            'format_phone': self._format_phone_number,
            'normalize_name': self._normalize_person_name
        })
    
    def add_rule(self, rule: InheritanceRule):
        """添加继承规则"""
        self.inheritance_rules.append(rule)
        # 按优先级排序
        self.inheritance_rules.sort(key=lambda r: r.priority, reverse=True)
        logger.debug(f"添加继承规则: {rule.source_slot} -> {rule.target_slot}")
    
    def add_transformer(self, name: str, transformer: callable):
        """添加值转换器"""
        self.value_transformers[name] = transformer
    
    async def inherit_slot_values(self, 
                                 intent_slots: List[Slot],
                                 current_values: Dict[str, Any],
                                 context: Dict[str, Any]) -> InheritanceResult:
        """
        执行槽位值继承
        
        Args:
            intent_slots: 意图的槽位定义
            current_values: 当前已有的槽位值
            context: 继承上下文
            
        Returns:
            InheritanceResult: 继承结果
        """
        inherited_values = current_values.copy()
        inheritance_sources = {}
        applied_rules = []
        skipped_rules = []
        
        # 按优先级处理继承规则
        for rule in self.inheritance_rules:
            try:
                # 检查目标槽位是否存在于当前意图中
                target_slot_names = [slot.slot_name for slot in intent_slots]
                if rule.target_slot not in target_slot_names:
                    continue
                
                # 检查是否应用此规则
                should_apply, reason = self._should_apply_rule(
                    rule, inherited_values, context
                )
                
                if not should_apply:
                    skipped_rules.append((rule, reason))
                    continue
                
                # 获取源值
                source_value = self._get_source_value(rule, context)
                if source_value is None:
                    skipped_rules.append((rule, "源值为空"))
                    continue
                
                # 应用值转换
                transformed_value = self._transform_value(rule, source_value)
                
                # 应用继承策略
                final_value = self._apply_inheritance_strategy(
                    rule, transformed_value, inherited_values.get(rule.target_slot)
                )
                
                if final_value is not None:
                    inherited_values[rule.target_slot] = final_value
                    inheritance_sources[rule.target_slot] = self._get_source_description(rule, context)
                    applied_rules.append(rule)
                    
                    logger.debug(f"应用继承规则: {rule.target_slot} = {final_value} "
                               f"(from {rule.source_slot})")
                
            except Exception as e:
                logger.error(f"继承规则执行失败: {rule.source_slot} -> {rule.target_slot}, 错误: {e}")
                skipped_rules.append((rule, f"执行异常: {e}"))
        
        return InheritanceResult(
            inherited_values=inherited_values,
            inheritance_sources=inheritance_sources,
            applied_rules=applied_rules,
            skipped_rules=skipped_rules
        )
    
    def _should_apply_rule(self, rule: InheritanceRule, 
                          current_values: Dict[str, Any],
                          context: Dict[str, Any]):
        """判断是否应用继承规则"""
        # 检查策略
        if rule.strategy == InheritanceStrategy.SUPPLEMENT:
            # 补充策略：只有目标槽位为空时才继承
            if rule.target_slot in current_values and current_values[rule.target_slot] is not None:
                return False, "目标槽位已有值（补充策略）"
        
        # 检查条件
        if rule.condition:
            if not self._evaluate_condition(rule.condition, context):
                return False, "继承条件不满足"
        
        # 检查TTL
        if rule.ttl_seconds:
            source_timestamp = context.get('source_timestamp')
            if source_timestamp:
                if isinstance(source_timestamp, str):
                    source_timestamp = datetime.fromisoformat(source_timestamp)
                
                if datetime.now() - source_timestamp > timedelta(seconds=rule.ttl_seconds):
                    return False, "继承值已过期"
        
        return True, ""
    
    def _get_source_value(self, rule: InheritanceRule, context: Dict[str, Any]) -> Any:
        """获取源值"""
        if rule.inheritance_type == InheritanceType.CONTEXT:
            return context.get('conversation_context', {}).get(rule.source_slot)
        
        elif rule.inheritance_type == InheritanceType.SESSION:
            return context.get('session_context', {}).get(rule.source_slot)
        
        elif rule.inheritance_type == InheritanceType.USER_PROFILE:
            return context.get('user_profile', {}).get(rule.source_slot)
        
        elif rule.inheritance_type == InheritanceType.DEPENDENCY:
            return context.get('dependency_values', {}).get(rule.source_slot)
        
        elif rule.inheritance_type == InheritanceType.DEFAULT:
            return context.get('default_values', {}).get(rule.source_slot)
        
        return None
    
    def _transform_value(self, rule: InheritanceRule, value: Any) -> Any:
        """转换值"""
        if not rule.transformation:
            return value
        
        transformer = self.value_transformers.get(rule.transformation)
        if transformer:
            try:
                return transformer(value)
            except Exception as e:
                logger.warning(f"值转换失败: {rule.transformation}, 值: {value}, 错误: {e}")
                return value
        
        return value
    
    def _apply_inheritance_strategy(self, rule: InheritanceRule, 
                                  new_value: Any, existing_value: Any) -> Any:
        """应用继承策略"""
        if rule.strategy == InheritanceStrategy.OVERRIDE:
            return new_value
        
        elif rule.strategy == InheritanceStrategy.SUPPLEMENT:
            return new_value if existing_value is None else existing_value
        
        elif rule.strategy == InheritanceStrategy.MERGE:
            # 简单合并策略
            if isinstance(existing_value, list) and isinstance(new_value, list):
                # 列表合并
                return list(set(existing_value + new_value))
            elif isinstance(existing_value, dict) and isinstance(new_value, dict):
                # 字典合并
                merged = existing_value.copy()
                merged.update(new_value)
                return merged
            else:
                # 其他类型优先使用新值
                return new_value
        
        elif rule.strategy == InheritanceStrategy.CONDITIONAL:
            # 条件策略在 _should_apply_rule 中处理
            return new_value
        
        return new_value
    
    def _evaluate_condition(self, condition: Dict[str, Any], context: Dict[str, Any]) -> bool:
        """评估继承条件"""
        condition_type = condition.get('type', 'always')
        
        if condition_type == 'always':
            return True
        
        elif condition_type == 'slot_empty':
            slot_name = condition.get('slot')
            values = context.get('current_values', {})
            return slot_name not in values or values[slot_name] is None
        
        elif condition_type == 'slot_equals':
            slot_name = condition.get('slot')
            expected_value = condition.get('value')
            values = context.get('current_values', {})
            return str(values.get(slot_name)) == str(expected_value)
        
        elif condition_type == 'user_attribute':
            attr_name = condition.get('attribute')
            expected_value = condition.get('value')
            user_profile = context.get('user_profile', {})
            return str(user_profile.get(attr_name)) == str(expected_value)
        
        elif condition_type == 'time_window':
            # 时间窗口条件
            max_age_seconds = condition.get('max_age_seconds', 3600)
            source_timestamp = context.get('source_timestamp')
            if source_timestamp:
                if isinstance(source_timestamp, str):
                    source_timestamp = datetime.fromisoformat(source_timestamp)
                age = (datetime.now() - source_timestamp).total_seconds()
                return age <= max_age_seconds
        
        return False
    
    def _get_source_description(self, rule: InheritanceRule, context: Dict[str, Any]) -> str:
        """获取源描述"""
        type_descriptions = {
            InheritanceType.CONTEXT: "对话上下文",
            InheritanceType.SESSION: "会话历史",
            InheritanceType.USER_PROFILE: "用户档案",
            InheritanceType.DEPENDENCY: "依赖槽位",
            InheritanceType.DEFAULT: "默认值"
        }
        
        base_desc = type_descriptions.get(rule.inheritance_type, "未知来源")
        return f"{base_desc}({rule.source_slot})"
    
    # 默认值转换器实现
    def _normalize_date_value(self, value: Any) -> str:
        """标准化日期值"""
        if isinstance(value, datetime):
            return value.date().isoformat()
        elif isinstance(value, str):
            # 尝试解析各种日期格式
            try:
                dt = datetime.fromisoformat(value)
                return dt.date().isoformat()
            except:
                pass
        return str(value)
    
    def _extract_city_name(self, value: Any) -> str:
        """提取城市名称"""
        value_str = str(value).strip()
        # 简单的城市名提取逻辑
        city_suffixes = ['市', '区', '县', '镇']
        for suffix in city_suffixes:
            if value_str.endswith(suffix):
                return value_str
        
        # 如果没有后缀，可能是简称
        city_mapping = {
            '北京': '北京市',
            '上海': '上海市',
            '广州': '广州市',
            '深圳': '深圳市',
            '杭州': '杭州市',
            '南京': '南京市'
        }
        return city_mapping.get(value_str, value_str)
    
    def _format_phone_number(self, value: Any) -> str:
        """格式化电话号码"""
        phone_str = ''.join(filter(str.isdigit, str(value)))
        if len(phone_str) == 11:
            return f"{phone_str[:3]}-{phone_str[3:7]}-{phone_str[7:]}"
        return phone_str
    
    def _normalize_person_name(self, value: Any) -> str:
        """标准化人名"""
        return str(value).strip().title()


class ConversationInheritanceManager:
    """对话继承管理器"""
    
    def __init__(self, inheritance_engine: SlotInheritanceEngine):
        self.inheritance_engine = inheritance_engine
        self._setup_default_rules()
    
    def _setup_default_rules(self):
        """设置默认继承规则"""
        default_rules = [
            # 城市继承规则
            InheritanceRule(
                source_slot="departure_city",
                target_slot="departure_city",
                inheritance_type=InheritanceType.SESSION,
                strategy=InheritanceStrategy.SUPPLEMENT,
                priority=10,
                ttl_seconds=3600  # 1小时内有效
            ),
            InheritanceRule(
                source_slot="arrival_city",
                target_slot="departure_city",
                inheritance_type=InheritanceType.SESSION,
                strategy=InheritanceStrategy.SUPPLEMENT,
                condition={
                    'type': 'slot_empty',
                    'slot': 'departure_city'
                },
                transformation="extract_city",
                priority=5
            ),
            
            # 用户信息继承
            InheritanceRule(
                source_slot="passenger_name",
                target_slot="passenger_name",
                inheritance_type=InheritanceType.USER_PROFILE,
                strategy=InheritanceStrategy.SUPPLEMENT,
                transformation="normalize_name",
                priority=15
            ),
            InheritanceRule(
                source_slot="phone_number",
                target_slot="phone_number",
                inheritance_type=InheritanceType.USER_PROFILE,
                strategy=InheritanceStrategy.SUPPLEMENT,
                transformation="format_phone",
                priority=15
            ),
            
            # 银行卡信息继承
            InheritanceRule(
                source_slot="card_number",
                target_slot="card_number",
                inheritance_type=InheritanceType.SESSION,
                strategy=InheritanceStrategy.SUPPLEMENT,
                condition={
                    'type': 'time_window',
                    'max_age_seconds': 1800  # 30分钟内
                },
                priority=20
            )
        ]
        
        for rule in default_rules:
            self.inheritance_engine.add_rule(rule)
    
    async def inherit_from_conversation_history(self, 
                                              user_id: str,
                                              intent_slots: List[Slot],
                                              current_values: Dict[str, Any],
                                              max_history: int = 10,
                                              use_cache: bool = True) -> InheritanceResult:
        """
        从对话历史继承槽位值
        
        Args:
            user_id: 用户ID
            intent_slots: 当前意图的槽位定义
            current_values: 当前已有的槽位值
            max_history: 最大历史记录数
            use_cache: 是否使用缓存
            
        Returns:
            InheritanceResult: 继承结果
        """
        # 准备槽位名称列表用于缓存键
        slot_names = [slot.slot_name for slot in intent_slots]
        intent_id = intent_slots[0].intent_id if intent_slots else 0
        
        # 尝试从缓存获取结果
        cached_result = None
        if use_cache:
            try:
                from .inheritance_cache_manager import get_inheritance_cache_manager
                from ..services.cache_service import get_cache_service
                
                cache_service = await get_cache_service()
                cache_manager = await get_inheritance_cache_manager(cache_service)
                
                # 构建临时上下文用于缓存键生成
                temp_context = {
                    'current_values': current_values,
                    'user_id': user_id,
                    'max_history': max_history
                }
                
                cached_result = await cache_manager.get_cached_inheritance(
                    user_id, intent_id, slot_names, temp_context
                )
                
                if cached_result:
                    logger.debug(f"使用缓存的继承结果: 用户={user_id}")
                    return InheritanceResult(
                        inherited_values=cached_result['inherited_values'],
                        inheritance_sources=cached_result['inheritance_sources'],
                        applied_rules=[],  # 缓存不包含规则详情
                        skipped_rules=[]
                    )
                    
            except Exception as e:
                logger.warning(f"获取继承缓存失败: {e}")
        
        # 获取对话历史和上下文
        conversation_context = await self._get_conversation_context(user_id, max_history)
        session_context = await self._get_session_context(user_id)
        user_profile = await self._get_user_profile(user_id)
        
        # 构建继承上下文
        context = {
            'conversation_context': conversation_context,
            'session_context': session_context,
            'user_profile': user_profile,
            'current_values': current_values,
            'source_timestamp': datetime.now(),
            'user_id': user_id,
            'max_history': max_history
        }
        
        # 执行继承
        result = await self.inheritance_engine.inherit_slot_values(
            intent_slots, current_values, context
        )
        
        # 缓存结果
        if use_cache and result.inherited_values:
            try:
                cache_service = await get_cache_service()
                cache_manager = await get_inheritance_cache_manager(cache_service)
                
                await cache_manager.cache_inheritance_result(
                    user_id, intent_id, slot_names, context,
                    result.inherited_values, result.inheritance_sources
                )
                
                # 更新用户行为模式
                from .inheritance_cache_manager import get_smart_inheritance_cache
                smart_cache = await get_smart_inheritance_cache(cache_service)
                await smart_cache.update_user_pattern(user_id, slot_names, context)
                
            except Exception as e:
                logger.warning(f"缓存继承结果失败: {e}")
        
        logger.info(f"完成继承处理: 用户={user_id}, "
                   f"继承槽位={len(result.inherited_values)}, "
                   f"应用规则={len(result.applied_rules)}")
        
        return result
    
    async def _get_conversation_context(self, user_id: str, max_history: int) -> Dict[str, Any]:
        """获取对话上下文"""
        try:
            # 查询最近的对话记录
            recent_conversations = list(
                Conversation.select()
                .where(Conversation.user_id == user_id)
                .order_by(Conversation.created_at.desc())
                .limit(max_history)
            )
            
            context = {}
            for conv in recent_conversations:
                if conv.slots_filled:
                    # 解析槽位值
                    import json
                    slots = json.loads(conv.slots_filled)
                    for slot_name, slot_value in slots.items():
                        if slot_name not in context:  # 使用最新的值
                            context[slot_name] = slot_value
                            context[f"{slot_name}_timestamp"] = conv.created_at
            
            return context
            
        except Exception as e:
            logger.error(f"获取对话上下文失败: {e}")
            return {}
    
    async def _get_session_context(self, user_id: str) -> Dict[str, Any]:
        """获取会话上下文"""
        try:
            # 查询当前会话的槽位值
            from ..models.conversation import Session
            
            active_session = Session.select().where(
                Session.user_id == user_id,
                Session.session_state == 'active'
            ).order_by(Session.created_at.desc()).first()
            
            if active_session and active_session.context:
                import json
                return json.loads(active_session.context)
            
            return {}
            
        except Exception as e:
            logger.error(f"获取会话上下文失败: {e}")
            return {}
    
    async def _get_user_profile(self, user_id: str) -> Dict[str, Any]:
        """获取用户档案"""
        try:
            # 集成用户档案服务
            from ..services.user_profile_service import get_user_profile_service
            from ..services.cache_service import get_cache_service
            
            cache_service = await get_cache_service()
            profile_service = await get_user_profile_service(cache_service)
            
            profile = await profile_service.get_user_profile(user_id)
            
            # 转换为继承系统期望的格式
            user_profile = {
                'user_id': user_id,
                'preferred_departure_city': '',
                'phone_number': '',
                'passenger_name': ''
            }
            
            # 从用户偏好中提取信息
            preferences = profile.get('preferences', {})
            frequent_values = profile.get('frequent_values', {})
            
            # 首选出发城市
            if preferences.get('preferred_departure_cities'):
                user_profile['preferred_departure_city'] = preferences['preferred_departure_cities'][0]
            
            # 联系信息
            contact_info = preferences.get('contact_info', {})
            user_profile['phone_number'] = contact_info.get('phone', '')
            user_profile['passenger_name'] = contact_info.get('name', '')
            
            # 从常用值中补充信息
            if 'phone_number' in frequent_values:
                user_profile['phone_number'] = frequent_values['phone_number']['most_frequent']
            if 'passenger_name' in frequent_values:
                user_profile['passenger_name'] = frequent_values['passenger_name']['most_frequent']
            
            return user_profile
            
        except Exception as e:
            logger.error(f"获取用户档案失败: {e}")
            # 返回基础模拟数据作为后备
            return {
                'user_id': user_id,
                'preferred_departure_city': '北京',
                'phone_number': '138-0013-8000',
                'passenger_name': '张三'
            }


# 全局继承管理器实例
inheritance_engine = SlotInheritanceEngine()
inheritance_manager = ConversationInheritanceManager(inheritance_engine)