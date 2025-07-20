"""
槽位管理服务
"""
from typing import Dict, List, Optional, Any, Tuple
import re
import json
from datetime import datetime

from src.models.slot import Slot, SlotValue, SlotDependency
from src.models.intent import Intent
from src.models.conversation import Conversation
from src.services.cache_service import CacheService
from src.core.nlu_engine import NLUEngine
from src.core.dependency_graph import dependency_graph_manager, DependencyGraph
from src.core.slot_inheritance import inheritance_manager, InheritanceResult
from src.core.clarification_question_generator import ClarificationQuestionGenerator, ClarificationType
from src.utils.logger import get_logger

logger = get_logger(__name__)


class SlotExtractionResult:
    """槽位提取结果类"""
    
    def __init__(self, slots: Dict[str, Any], missing_slots: List[str], 
                 validation_errors: Dict[str, str] = None):
        self.slots = slots
        self.missing_slots = missing_slots
        self.validation_errors = validation_errors or {}
        self.is_complete = len(missing_slots) == 0
        self.has_errors = len(self.validation_errors) > 0
    
    def to_dict(self) -> Dict:
        """转换为字典格式"""
        return {
            "slots": self.slots,
            "missing_slots": self.missing_slots,
            "validation_errors": self.validation_errors,
            "is_complete": self.is_complete,
            "has_errors": self.has_errors
        }


class SlotService:
    """槽位管理服务类"""
    
    def __init__(self, cache_service: CacheService, nlu_engine: NLUEngine):
        self.cache_service = cache_service
        self.nlu_engine = nlu_engine
        self.clarification_generator = ClarificationQuestionGenerator()
    
    async def extract_slots(self, intent: Intent, user_input: str, 
                          existing_slots: Dict[str, Any] = None,
                          context: Dict = None) -> SlotExtractionResult:
        """
        增强的槽位提取，集成依赖图和继承系统
        
        Args:
            intent: 意图对象
            user_input: 用户输入文本
            existing_slots: 已存在的槽位值
            context: 对话上下文
            
        Returns:
            SlotExtractionResult: 槽位提取结果
        """
        try:
            # 1. 获取意图的槽位定义
            slot_definitions = await self._get_slot_definitions(intent)
            if not slot_definitions:
                return SlotExtractionResult({}, [])
            
            # 2. 获取或构建依赖图
            dependency_graph = await self._get_or_build_dependency_graph(intent, slot_definitions)
            
            # 3. 初始化槽位值字典
            slots = existing_slots.copy() if existing_slots else {}
            
            # 4. 应用槽位继承
            inheritance_result = await self._apply_slot_inheritance(
                intent, slot_definitions, slots, context
            )
            slots.update(inheritance_result.inherited_values)
            
            # 5. 使用NLU引擎提取槽位
            extracted_slots = await self.nlu_engine.extract_slots(
                user_input, slot_definitions, context
            )
            
            # 6. 合并提取的槽位值
            for slot_name, slot_info in extracted_slots.items():
                if slot_info.get('value') is not None:
                    slots[slot_name] = {
                        'value': slot_info['value'],
                        'confidence': slot_info.get('confidence', 0.0),
                        'source': slot_info.get('source', 'llm'),
                        'original_text': slot_info.get('original_text', user_input)
                    }
            
            # 7. 验证槽位值（含上下文验证）
            validated_slots, validation_errors = await self._validate_slots(
                slot_definitions, slots, context
            )
            
            # 8. 使用依赖图进行高级依赖验证
            dependency_result = await self._validate_with_dependency_graph(
                dependency_graph, validated_slots
            )
            
            # 9. 获取智能填充顺序
            missing_slots = self._get_missing_slots_with_graph(
                dependency_graph, validated_slots, slot_definitions
            )
            
            # 10. 构建增强结果
            result = SlotExtractionResult(
                validated_slots, missing_slots, validation_errors
            )
            
            # 添加依赖图分析结果
            if hasattr(result, 'dependency_analysis'):
                result.dependency_analysis = dependency_result
            else:
                result.__dict__['dependency_analysis'] = dependency_result
            
            # 添加继承信息
            if hasattr(result, 'inheritance_info'):
                result.inheritance_info = inheritance_result
            else:
                result.__dict__['inheritance_info'] = inheritance_result
            
            logger.info(f"增强槽位提取完成: {intent.intent_name}, "
                       f"提取={len(validated_slots)}个, 继承={len(inheritance_result.inherited_values)}个, "
                       f"缺失={len(missing_slots)}个")
            return result
            
        except Exception as e:
            logger.error(f"槽位提取失败: {str(e)}")
            return SlotExtractionResult({}, [])
    
    async def _get_slot_definitions(self, intent: Intent) -> List[Slot]:
        """获取意图的槽位定义"""
        # 首先尝试从缓存获取
        cache_key = f"slot_definitions:{intent.intent_name}"
        cached_slots = await self.cache_service.get(cache_key)
        if cached_slots:
            return cached_slots
        
        # 从数据库查询槽位定义
        slots = list(intent.slots.order_by(Slot.sort_order))
        
        # 缓存结果
        await self.cache_service.set(cache_key, slots, ttl=3600)
        
        return slots
    
    async def _validate_slots(self, slot_definitions: List[Slot], 
                            slots: Dict[str, Any], context: Dict = None) -> Tuple[Dict[str, Any], Dict[str, str]]:
        """
        增强的槽位验证
        
        Args:
            slot_definitions: 槽位定义列表
            slots: 待验证的槽位值字典
            context: 验证上下文
            
        Returns:
            Tuple[Dict, Dict]: (验证后的槽位值, 验证错误)
        """
        validated_slots = {}
        validation_errors = {}
        
        # 创建槽位定义映射
        slot_def_map = {slot.slot_name: slot for slot in slot_definitions}
        
        # 构建验证上下文
        validation_context = {
            'slots': {name: info.get('value') for name, info in slots.items()},
            **(context or {})
        }
        
        for slot_name, slot_info in slots.items():
            if slot_name not in slot_def_map:
                continue
            
            slot_def = slot_def_map[slot_name]
            slot_value = slot_info.get('value')
            
            # 使用增强的槽位验证
            is_valid, error_message, normalized_value = await self.validate_slot_value(
                slot_def, slot_value, validation_context
            )
            
            if is_valid:
                validated_slots[slot_name] = {
                    **slot_info,
                    'value': normalized_value,
                    'is_validated': True,
                    'validation_error': None
                }
            else:
                validation_errors[slot_name] = error_message
                # 保留原值但标记为未验证
                validated_slots[slot_name] = {
                    **slot_info,
                    'value': normalized_value,  # 即使验证失败也使用标准化值
                    'is_validated': False,
                    'validation_error': error_message
                }
        
        return validated_slots, validation_errors
    
    async def _normalize_slot_value(self, slot_def: Slot, value: Any) -> Any:
        """
        标准化槽位值
        
        Args:
            slot_def: 槽位定义
            value: 原始值
            
        Returns:
            Any: 标准化后的值
        """
        if value is None:
            return value
        
        try:
            # 根据槽位类型进行标准化
            if slot_def.slot_type == 'NUMBER':
                # 数字类型标准化
                if isinstance(value, str):
                    # 移除数字中的非数字字符（除了小数点和负号）
                    cleaned = re.sub(r'[^\d.-]', '', value)
                    return float(cleaned) if '.' in cleaned else int(cleaned)
                return float(value)
            
            elif slot_def.slot_type == 'DATE':
                # 日期类型标准化
                return await self._normalize_date_value(value)
            
            elif slot_def.slot_type == 'TEXT':
                # 文本类型清理
                if isinstance(value, str):
                    return value.strip()
                return str(value)
            
            elif slot_def.slot_type == 'ENUM':
                # 枚举类型标准化
                return await self._normalize_enum_value(slot_def, value)
            
            else:
                return value
                
        except Exception as e:
            logger.warning(f"槽位值标准化失败: {slot_def.slot_name}, {str(e)}")
            return value
    
    async def _normalize_date_value(self, value: Any) -> str:
        """标准化日期值"""
        # 实现日期标准化逻辑，转换为YYYY-MM-DD格式
        # 这里简化实现，实际应该使用更复杂的日期解析逻辑
        if isinstance(value, str):
            # 处理相对日期
            if '今天' in value or '今日' in value:
                return datetime.now().strftime('%Y-%m-%d')
            elif '明天' in value or '明日' in value:
                from datetime import timedelta
                return (datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d')
            elif '后天' in value:
                from datetime import timedelta
                return (datetime.now() + timedelta(days=2)).strftime('%Y-%m-%d')
        
        return str(value)
    
    async def _normalize_enum_value(self, slot_def: Slot, value: Any) -> str:
        """标准化枚举值"""
        rules = slot_def.get_validation_rules()
        options = rules.get('options', [])
        
        if not options:
            return str(value)
        
        value_str = str(value).lower()
        
        # 精确匹配
        for option in options:
            if value_str == option.lower():
                return option
        
        # 模糊匹配
        for option in options:
            if value_str in option.lower() or option.lower() in value_str:
                return option
        
        return str(value)
    
    async def _check_missing_required_slots(self, slot_definitions: List[Slot], 
                                          slots: Dict[str, Any]) -> List[str]:
        """检查缺失的必需槽位"""
        missing_slots = []
        
        for slot_def in slot_definitions:
            if slot_def.is_required:
                slot_info = slots.get(slot_def.slot_name)
                if not slot_info or slot_info.get('value') is None:
                    missing_slots.append(slot_def.slot_name)
                elif not slot_info.get('is_validated', True):
                    # 验证失败的必需槽位也算作缺失
                    missing_slots.append(slot_def.slot_name)
        
        return missing_slots
    
    async def _handle_slot_dependencies(self, intent: Intent, 
                                      slots: Dict[str, Any], 
                                      missing_slots: List[str]):
        """处理槽位依赖关系"""
        try:
            # 构建槽位值字典用于依赖检查
            slot_values = {name: info.get('value') for name, info in slots.items()}
            
            # 验证所有槽位依赖关系
            is_satisfied, dependency_errors = await self.validate_slot_dependencies(
                intent, slot_values
            )
            
            if not is_satisfied:
                logger.info(f"槽位依赖未满足: {dependency_errors}")
                
                # 基于依赖错误，调整缺失槽位列表
                dependencies = await self.get_slot_dependencies(intent)
                
                for dependency in dependencies:
                    # 检查单个依赖
                    dep_satisfied, dep_error = dependency.check_dependency(slot_values)
                    if not dep_satisfied:
                        dependent_slot_name = dependency.dependent_slot.slot_name
                        
                        # 如果依赖槽位还没有在缺失列表中，添加它
                        if (dependent_slot_name not in missing_slots and 
                            dependent_slot_name not in slot_values):
                            missing_slots.append(dependent_slot_name)
                        
                        # 如果是条件依赖，可能需要先满足被依赖的槽位
                        if (dependency.dependency_type == 'conditional' and
                            dependency.required_slot.slot_name not in slot_values and
                            dependency.required_slot.slot_name not in missing_slots):
                            missing_slots.append(dependency.required_slot.slot_name)
            
        except Exception as e:
            logger.error(f"处理槽位依赖关系失败: {str(e)}")
    
    async def generate_slot_prompt(self, intent: Intent, missing_slots: List[str],
                                 context: Dict = None) -> str:
        """
        生成槽位询问提示（保持向后兼容）
        
        Args:
            intent: 意图对象
            missing_slots: 缺失的槽位列表
            context: 对话上下文
            
        Returns:
            str: 槽位询问提示
        """
        try:
            # 获取槽位定义
            slot_definitions = await self._get_slot_definitions(intent)
            slot_def_map = {slot.slot_name: slot for slot in slot_definitions}
            
            # 过滤出有效的槽位对象
            missing_slot_objects = [
                slot_def_map[slot_name] for slot_name in missing_slots 
                if slot_name in slot_def_map
            ]
            
            if not missing_slot_objects:
                return "请提供更多信息以完成您的请求。"
            
            # 使用智能问题生成
            question_candidate = await self.generate_intelligent_question(
                intent, missing_slot_objects, context or {}
            )
            
            return question_candidate.question
            
        except Exception as e:
            logger.error(f"生成槽位提示失败: {str(e)}")
            return "请提供更多信息以完成您的请求。"
    
    async def generate_intelligent_question(self,
                                          intent: Intent,
                                          missing_slots: List[Slot],
                                          context: Dict = None,
                                          user_id: str = None) -> 'QuestionCandidate':
        """
        使用智能问题生成引擎生成问题
        
        Args:
            intent: 意图对象
            missing_slots: 缺失的槽位对象列表
            context: 对话上下文
            user_id: 用户ID
            
        Returns:
            QuestionCandidate: 智能生成的问题候选
        """
        try:
            from ..core.question_generator import question_generator
            
            # 准备问题生成上下文
            question_context = context or {}
            
            # 添加用户档案信息
            if user_id:
                try:
                    from ..services.user_profile_service import get_user_profile_service
                    profile_service = await get_user_profile_service(self.cache_service)
                    user_profile = await profile_service.get_user_profile(user_id)
                    question_context["user_profile"] = user_profile
                except Exception as e:
                    logger.warning(f"获取用户档案失败: {e}")
            
            # 生成智能问题
            question_candidate = await question_generator.generate_question(
                intent, missing_slots, question_context, user_id
            )
            
            return question_candidate
            
        except Exception as e:
            logger.error(f"智能问题生成失败: {e}")
            # 降级到简单问题生成
            from ..core.question_generator import QuestionCandidate, QuestionType, QuestionStyle
            
            if len(missing_slots) == 1:
                question = f"请提供{missing_slots[0].slot_name}："
            else:
                question = "请提供以下信息：" + "、".join([slot.slot_name for slot in missing_slots[:3]])
            
            return QuestionCandidate(
                question=question,
                question_type=QuestionType.DIRECT,
                style=QuestionStyle.FRIENDLY,
                confidence=0.5,
                context_relevance=0.5,
                personalization_score=0.5,
                slot_names=[slot.slot_name for slot in missing_slots],
                metadata={"source": "fallback"}
            )
    
    async def generate_contextual_question(self,
                                         intent: Intent,
                                         missing_slots: List[Slot],
                                         conversation_context: Dict,
                                         user_id: str = None) -> 'QuestionCandidate':
        """
        生成上下文感知的问题
        
        Args:
            intent: 意图对象
            missing_slots: 缺失的槽位列表
            conversation_context: 对话上下文
            user_id: 用户ID
            
        Returns:
            QuestionCandidate: 上下文感知的问题候选
        """
        try:
            from ..core.question_generator import question_generator
            from ..core.context_aware_questioning import (
                ConversationContext, DialogueState, get_context_aware_engine
            )
            
            # 构建对话上下文对象
            conv_context = ConversationContext(
                user_id=user_id or "anonymous",
                conversation_id=conversation_context.get("conversation_id", "default"),
                turn_count=conversation_context.get("turn_count", 1),
                dialogue_state=DialogueState(conversation_context.get("dialogue_state", "collecting")),
                failed_attempts=conversation_context.get("failed_attempts", {}),
                collected_slots=conversation_context.get("collected_slots", {}),
                partial_slots=conversation_context.get("partial_slots", {}),
                user_preferences=conversation_context.get("user_preferences", {}),
                conversation_history=conversation_context.get("history", []),
                time_pressure=conversation_context.get("time_pressure", 0.5),
                user_engagement=conversation_context.get("user_engagement", 0.7)
            )
            
            # 使用上下文感知引擎
            context_engine = get_context_aware_engine(question_generator)
            question_candidate = await context_engine.generate_contextual_question(
                intent, missing_slots, conv_context
            )
            
            return question_candidate
            
        except Exception as e:
            logger.error(f"上下文问题生成失败: {e}")
            # 降级到智能问题生成
            return await self.generate_intelligent_question(
                intent, missing_slots, conversation_context, user_id
            )
    
    async def generate_followup_question(self,
                                       user_input: str,
                                       expected_slots: List[Slot],
                                       conversation_context: Dict,
                                       user_id: str = None) -> 'FollowUpQuestion':
        """
        生成追问问题
        
        Args:
            user_input: 用户输入
            expected_slots: 期望的槽位
            conversation_context: 对话上下文
            user_id: 用户ID
            
        Returns:
            FollowUpQuestion: 追问问题
        """
        try:
            from ..core.followup_question_engine import followup_engine
            from ..core.context_aware_questioning import ConversationContext, DialogueState
            
            # 构建对话上下文
            conv_context = ConversationContext(
                user_id=user_id or "anonymous",
                conversation_id=conversation_context.get("conversation_id", "default"),
                turn_count=conversation_context.get("turn_count", 1),
                dialogue_state=DialogueState(conversation_context.get("dialogue_state", "collecting")),
                failed_attempts=conversation_context.get("failed_attempts", {}),
                collected_slots=conversation_context.get("collected_slots", {}),
                partial_slots=conversation_context.get("partial_slots", {}),
                user_preferences=conversation_context.get("user_preferences", {}),
                conversation_history=conversation_context.get("history", []),
                time_pressure=conversation_context.get("time_pressure", 0.5),
                user_engagement=conversation_context.get("user_engagement", 0.7)
            )
            
            # 分析用户回应
            user_response = await followup_engine.analyze_user_response(
                user_input, expected_slots, conv_context
            )
            
            # 生成追问问题
            followup_question = await followup_engine.generate_followup_question(
                user_response, expected_slots, conv_context
            )
            
            return followup_question
            
        except Exception as e:
            logger.error(f"追问生成失败: {e}")
            # 降级到简单追问
            from ..core.followup_question_engine import FollowUpQuestion, FollowUpType
            
            return FollowUpQuestion(
                question="能再详细说明一下吗？",
                followup_type=FollowUpType.CLARIFICATION,
                target_slots=[slot.slot_name for slot in expected_slots],
                context_hints={},
                urgency=0.5,
                patience_level=0.5
            )
    
    async def inherit_slots_from_context(self, intent: Intent, context: Dict) -> Dict[str, Any]:
        """
        从上下文继承槽位值
        
        Args:
            intent: 当前意图
            context: 对话上下文
            
        Returns:
            Dict: 继承的槽位值
        """
        try:
            inherited_slots = {}
            
            # 获取当前意图的槽位定义
            slot_definitions = await self._get_slot_definitions(intent)
            current_slot_names = {slot.slot_name for slot in slot_definitions}
            
            # 从会话历史中查找可继承的槽位值
            session_id = context.get('session_id')
            if session_id:
                recent_conversations = list(
                    Conversation.select()
                    .where(Conversation.session_id == session_id)
                    .order_by(Conversation.created_at.desc())
                    .limit(5)
                )
                
                for conv in recent_conversations:
                    slots_filled = conv.get_slots_filled()
                    for slot_name, slot_info in slots_filled.items():
                        if (slot_name in current_slot_names and 
                            slot_name not in inherited_slots and
                            slot_info.get('value') is not None):
                            
                            # 检查槽位值是否仍然有效（比如时间敏感的槽位）
                            if await self._is_slot_value_still_valid(slot_name, slot_info, context):
                                inherited_slots[slot_name] = {
                                    **slot_info,
                                    'source': 'inherited',
                                    'inherited_from': conv.id
                                }
            
            logger.info(f"从上下文继承了{len(inherited_slots)}个槽位值")
            return inherited_slots
            
        except Exception as e:
            logger.error(f"槽位继承失败: {str(e)}")
            return {}
    
    async def _is_slot_value_still_valid(self, slot_name: str, slot_info: Dict, 
                                       context: Dict) -> bool:
        """检查槽位值是否仍然有效"""
        # 实现槽位值有效性检查逻辑
        # 例如：日期类型的槽位值不能是过去的日期
        # 用户偏好类型的槽位值可以长期有效
        
        slot_type = slot_info.get('type', 'TEXT')
        
        if slot_type == 'DATE':
            # 日期类型：检查是否为未来日期
            try:
                slot_date = datetime.strptime(slot_info['value'], '%Y-%m-%d')
                return slot_date.date() >= datetime.now().date()
            except:
                return False
        
        # 其他类型暂时认为都有效
        return True
    
    async def save_slot_values(self, conversation_id: int, intent: Intent, 
                             slots: Dict[str, Any]):
        """
        保存槽位值到数据库
        
        Args:
            conversation_id: 对话ID
            intent: 意图对象
            slots: 槽位值字典
        """
        try:
            # 获取槽位定义
            slot_definitions = await self._get_slot_definitions(intent)
            slot_def_map = {slot.slot_name: slot for slot in slot_definitions}
            
            # 保存每个槽位值
            for slot_name, slot_info in slots.items():
                slot_def = slot_def_map.get(slot_name)
                if not slot_def:
                    continue
                
                # 检查是否已存在槽位值记录
                try:
                    slot_value = SlotValue.get(
                        SlotValue.conversation_id == conversation_id,
                        SlotValue.slot == slot_def
                    )
                    # 更新现有记录
                    slot_value.value = str(slot_info['value'])
                    slot_value.confidence = slot_info.get('confidence')
                    slot_value.extraction_method = slot_info.get('source', 'llm')
                    slot_value.normalized_value = str(slot_info['value'])
                    slot_value.is_validated = slot_info.get('is_validated', True)
                    slot_value.validation_error = slot_info.get('validation_error')
                    
                except SlotValue.DoesNotExist:
                    # 创建新记录
                    slot_value = SlotValue.create(
                        conversation_id=conversation_id,
                        slot=slot_def,
                        value=str(slot_info['value']),
                        original_text=slot_info.get('original_text', ''),
                        confidence=slot_info.get('confidence'),
                        extraction_method=slot_info.get('source', 'llm'),
                        normalized_value=str(slot_info['value']),
                        is_validated=slot_info.get('is_validated', True),
                        validation_error=slot_info.get('validation_error')
                    )
                
                slot_value.save()
            
            logger.info(f"槽位值保存完成: {conversation_id}, {len(slots)}个槽位")
            
        except Exception as e:
            logger.error(f"保存槽位值失败: {str(e)}")
    
    async def validate_slot_dependencies(self, intent: Intent, 
                                       slots: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """
        验证槽位依赖关系
        
        Args:
            intent: 意图对象
            slots: 已提取的槽位值字典
            
        Returns:
            tuple: (是否全部满足, 错误信息列表)
        """
        try:
            # 使用模型的类方法检查所有依赖关系
            is_satisfied, errors = SlotDependency.check_all_dependencies(
                intent.id, slots
            )
            
            if not is_satisfied:
                logger.warning(f"槽位依赖验证失败: {intent.intent_name}, 错误: {errors}")
            
            return is_satisfied, errors
            
        except Exception as e:
            logger.error(f"槽位依赖验证异常: {str(e)}")
            return False, [f"依赖验证异常: {str(e)}"]
    
    async def validate_slot_value(self, slot: Slot, value: Any, 
                                context: Dict = None) -> Tuple[bool, str, Any]:
        """
        增强的槽位值验证
        
        Args:
            slot: 槽位配置
            value: 待验证的值
            context: 验证上下文
            
        Returns:
            tuple: (是否有效, 错误信息, 标准化值)
        """
        try:
            # 基本验证
            is_valid, error_msg = slot.validate_value(value)
            if not is_valid:
                return False, error_msg, value
            
            # 创建临时SlotValue对象进行标准化
            slot_value = SlotValue(
                slot=slot,
                value=str(value),
                normalized_value=None
            )
            
            # 执行标准化
            slot_value.normalize_value()
            normalized_value = slot_value.get_normalized_value()
            
            # 额外的上下文验证
            if context:
                context_valid, context_error = self._validate_with_context(
                    slot, normalized_value, context
                )
                if not context_valid:
                    return False, context_error, normalized_value
            
            logger.debug(f"槽位验证成功: {slot.slot_name} = {value} -> {normalized_value}")
            return True, "", normalized_value
            
        except Exception as e:
            logger.error(f"槽位验证异常: {slot.slot_name}, 错误: {str(e)}")
            return False, f"验证异常: {str(e)}", value
    
    def _validate_with_context(self, slot: Slot, value: Any, 
                             context: Dict) -> Tuple[bool, str]:
        """
        基于上下文的额外验证
        
        Args:
            slot: 槽位配置
            value: 标准化后的值
            context: 验证上下文
            
        Returns:
            tuple: (是否有效, 错误信息)
        """
        try:
            # 日期相关的上下文验证
            if slot.slot_type == 'DATE':
                return self._validate_date_with_context(slot, value, context)
            
            # 数字相关的上下文验证
            elif slot.slot_type == 'NUMBER':
                return self._validate_number_with_context(slot, value, context)
            
            # 文本相关的上下文验证
            elif slot.slot_type == 'TEXT':
                return self._validate_text_with_context(slot, value, context)
            
            return True, ""
            
        except Exception as e:
            return False, f"上下文验证异常: {str(e)}"
    
    def _validate_date_with_context(self, slot: Slot, value: str, 
                                  context: Dict) -> Tuple[bool, str]:
        """验证日期与上下文的一致性"""
        from datetime import datetime, date
        
        try:
            # 解析日期
            if isinstance(value, str):
                target_date = datetime.fromisoformat(value).date()
            else:
                target_date = value
            
            today = date.today()
            
            # 检查最小日期限制
            rules = slot.get_validation_rules()
            min_date_rule = rules.get('min_date')
            
            if min_date_rule == 'today' and target_date < today:
                return False, f"{slot.slot_name}不能是过去的日期"
            
            # 检查与其他日期槽位的关系
            if 'slots' in context:
                other_slots = context['slots']
                
                # 返程日期必须晚于出发日期
                if slot.slot_name == 'return_date' and 'departure_date' in other_slots:
                    departure_str = other_slots['departure_date']
                    if isinstance(departure_str, str):
                        departure_date = datetime.fromisoformat(departure_str).date()
                        if target_date <= departure_date:
                            return False, "返程日期必须晚于出发日期"
            
            return True, ""
            
        except Exception as e:
            return False, f"日期上下文验证失败: {str(e)}"
    
    def _validate_number_with_context(self, slot: Slot, value: Any, 
                                    context: Dict) -> Tuple[bool, str]:
        """验证数字与上下文的一致性"""
        try:
            num_value = float(value)
            rules = slot.get_validation_rules()
            
            # 检查数值范围
            min_val = rules.get('min', 0)
            max_val = rules.get('max', float('inf'))
            
            if num_value < min_val:
                return False, f"{slot.slot_name}不能小于{min_val}"
            if num_value > max_val:
                return False, f"{slot.slot_name}不能大于{max_val}"
            
            # 乘客人数的业务逻辑验证
            if slot.slot_name == 'passenger_count':
                if num_value != int(num_value):
                    return False, "乘客人数必须是整数"
                if num_value > 9:
                    return False, "单次预订乘客人数不能超过9人"
            
            return True, ""
            
        except Exception as e:
            return False, f"数字上下文验证失败: {str(e)}"
    
    def _validate_text_with_context(self, slot: Slot, value: str, 
                                  context: Dict) -> Tuple[bool, str]:
        """验证文本与上下文的一致性"""
        try:
            # 城市名称验证
            if slot.slot_name in ['departure_city', 'arrival_city']:
                # 检查出发城市和到达城市不能相同
                if 'slots' in context:
                    other_slots = context['slots']
                    if (slot.slot_name == 'arrival_city' and 
                        'departure_city' in other_slots and
                        other_slots['departure_city'].strip().lower() == value.strip().lower()):
                        return False, "出发城市和到达城市不能相同"
                    
                    if (slot.slot_name == 'departure_city' and 
                        'arrival_city' in other_slots and
                        other_slots['arrival_city'].strip().lower() == value.strip().lower()):
                        return False, "出发城市和到达城市不能相同"
            
            # 银行卡号验证
            if slot.slot_name == 'card_number':
                # 简单的Luhn算法验证（可选）
                clean_number = ''.join(filter(str.isdigit, value))
                if len(clean_number) != 16:
                    return False, "银行卡号必须是16位数字"
            
            return True, ""
            
        except Exception as e:
            return False, f"文本上下文验证失败: {str(e)}"
    
    async def get_slot_dependencies(self, intent: Intent) -> List[SlotDependency]:
        """
        获取意图的所有槽位依赖关系
        
        Args:
            intent: 意图对象
            
        Returns:
            List[SlotDependency]: 依赖关系列表
        """
        try:
            # 缓存键
            cache_key = f"slot_dependencies:{intent.id}"
            
            # 尝试从缓存获取
            cached_dependencies = await self.cache_service.get(cache_key)
            if cached_dependencies:
                return cached_dependencies
            
            # 从数据库查询
            dependencies = list(
                SlotDependency.select()
                .join(Slot, on=(SlotDependency.dependent_slot == Slot.id))
                .where(Slot.intent == intent.id)
                .order_by(SlotDependency.priority)
            )
            
            # 缓存结果
            await self.cache_service.set(cache_key, dependencies, ttl=3600)
            
            return dependencies
            
        except Exception as e:
            logger.error(f"获取槽位依赖关系失败: {str(e)}")
            return []
    
    async def suggest_next_slot(self, intent: Intent, current_slots: Dict[str, Any]) -> Optional[Slot]:
        """
        基于依赖关系建议下一个需要填充的槽位
        
        Args:
            intent: 意图对象
            current_slots: 当前已填充的槽位
            
        Returns:
            Optional[Slot]: 建议的下一个槽位，如果没有则返回None
        """
        try:
            # 获取所有槽位定义
            all_slots = await self._get_slot_definitions(intent)
            
            # 获取依赖关系
            dependencies = await self.get_slot_dependencies(intent)
            
            # 找出未填充的必需槽位
            unfilled_required = []
            unfilled_optional = []
            
            for slot in all_slots:
                if slot.slot_name not in current_slots:
                    if slot.is_required:
                        unfilled_required.append(slot)
                    else:
                        unfilled_optional.append(slot)
            
            # 优先处理必需槽位
            candidates = unfilled_required if unfilled_required else unfilled_optional
            
            if not candidates:
                return None
            
            # 基于依赖关系排序
            def can_fill_slot(slot):
                # 检查该槽位的所有依赖是否都已满足
                for dep in dependencies:
                    if dep.dependent_slot.id == slot.id:
                        is_satisfied, _ = dep.check_dependency(current_slots)
                        if not is_satisfied:
                            return False
                return True
            
            # 找出可以填充的槽位
            fillable_slots = [slot for slot in candidates if can_fill_slot(slot)]
            
            if fillable_slots:
                # 返回第一个可填充的槽位
                return fillable_slots[0]
            
            # 如果没有可填充的，返回第一个必需槽位
            return candidates[0] if candidates else None
            
        except Exception as e:
            logger.error(f"建议下一个槽位失败: {str(e)}")
            return None
    
    async def get_slot_values_for_conversation(self, conversation_id: int) -> Dict[str, Any]:
        """
        获取对话的所有槽位值
        
        Args:
            conversation_id: 对话ID
            
        Returns:
            Dict[str, Any]: 槽位值字典
        """
        try:
            # 查询槽位值
            slot_values = list(
                SlotValue.select(SlotValue, Slot)
                .join(Slot)
                .where(SlotValue.conversation_id == conversation_id)
                .order_by(SlotValue.created_at)
            )
            
            result = {}
            for slot_value in slot_values:
                result[slot_value.slot.slot_name] = {
                    'value': slot_value.get_normalized_value(),
                    'original_text': slot_value.original_text,
                    'confidence': float(slot_value.confidence),
                    'extraction_method': slot_value.extraction_method,
                    'is_validated': slot_value.is_validated,
                    'validation_error': slot_value.validation_error,
                    'source_turn': slot_value.source_turn,
                    'created_at': slot_value.created_at.isoformat() if slot_value.created_at else None
                }
            
            return result
            
        except Exception as e:
            logger.error(f"获取对话槽位值失败: {str(e)}")
            return {}
    
    async def _get_or_build_dependency_graph(self, intent: Intent, 
                                           slot_definitions: List[Slot]) -> DependencyGraph:
        """获取或构建依赖图"""
        try:
            # 尝试从缓存获取
            graph = dependency_graph_manager.get_graph(intent.id)
            if graph:
                return graph
            
            # 获取依赖关系
            dependencies = await self.get_slot_dependencies(intent)
            
            # 构建新的依赖图
            graph = await dependency_graph_manager.build_graph(
                intent.id, slot_definitions, dependencies
            )
            
            return graph
            
        except Exception as e:
            logger.error(f"构建依赖图失败: {str(e)}")
            # 返回空的依赖图
            graph = DependencyGraph()
            for slot in slot_definitions:
                graph.add_node(slot)
            return graph
    
    async def _apply_slot_inheritance(self, intent: Intent, 
                                    slot_definitions: List[Slot],
                                    current_slots: Dict[str, Any],
                                    context: Dict = None) -> InheritanceResult:
        """应用槽位继承"""
        try:
            user_id = context.get('user_id') if context else None
            if not user_id:
                # 没有用户ID，返回空继承结果
                from src.core.slot_inheritance import InheritanceResult
                return InheritanceResult(
                    inherited_values={},
                    inheritance_sources={},
                    applied_rules=[],
                    skipped_rules=[]
                )
            
            # 使用继承管理器进行继承
            result = await inheritance_manager.inherit_from_conversation_history(
                user_id, slot_definitions, current_slots
            )
            
            logger.debug(f"槽位继承完成: 继承了{len(result.inherited_values)}个槽位")
            return result
            
        except Exception as e:
            logger.error(f"槽位继承失败: {str(e)}")
            # 返回空继承结果
            from src.core.slot_inheritance import InheritanceResult
            return InheritanceResult(
                inherited_values={},
                inheritance_sources={},
                applied_rules=[],
                skipped_rules=[]
            )
    
    async def _validate_with_dependency_graph(self, dependency_graph: DependencyGraph,
                                            slot_values: Dict[str, Any]):
        """使用依赖图进行验证"""
        try:
            # 构建验证用的值字典
            values_for_validation = {
                name: info.get('value') if isinstance(info, dict) else info
                for name, info in slot_values.items()
            }
            
            # 执行依赖图验证
            result = dependency_graph.validate_dependencies(values_for_validation)
            
            if not result.is_valid:
                logger.warning(f"依赖图验证失败: {result.error_messages}")
            
            return result
            
        except Exception as e:
            logger.error(f"依赖图验证失败: {str(e)}")
            # 返回基本验证结果
            from src.core.dependency_graph import DependencyGraphResult
            return DependencyGraphResult(
                is_valid=True,
                has_cycles=False,
                cycles=[],
                resolution_order=[],
                unsatisfied_dependencies=[],
                conflicts=[],
                error_messages=[]
            )
    
    def _get_missing_slots_with_graph(self, dependency_graph: DependencyGraph,
                                    validated_slots: Dict[str, Any],
                                    slot_definitions: List[Slot]) -> List[str]:
        """使用依赖图获取缺失槽位列表"""
        try:
            # 获取当前槽位值
            current_values = {
                name: info.get('value') if isinstance(info, dict) else info
                for name, info in validated_slots.items()
                if info is not None
            }
            
            # 使用依赖图获取下一个可填充的槽位
            fillable_slots = dependency_graph.get_next_fillable_slots(current_values)
            
            # 过滤出必需的缺失槽位
            missing_required = []
            missing_optional = []
            
            slot_names = {slot.slot_name for slot in slot_definitions}
            
            for slot_name in fillable_slots:
                if slot_name not in current_values and slot_name in slot_names:
                    # 找到对应的槽位定义
                    slot_def = next((s for s in slot_definitions if s.slot_name == slot_name), None)
                    if slot_def:
                        if slot_def.is_required:
                            missing_required.append(slot_name)
                        else:
                            missing_optional.append(slot_name)
            
            # 返回必需槽位优先的列表
            return missing_required + missing_optional
            
        except Exception as e:
            logger.error(f"获取缺失槽位失败: {str(e)}")
            # 回退到基本方法
            return [
                slot.slot_name for slot in slot_definitions
                if slot.is_required and slot.slot_name not in validated_slots
            ]
    
    async def get_optimal_slot_filling_order(self, intent: Intent,
                                           current_slots: Dict[str, Any]) -> List[str]:
        """
        获取最优的槽位填充顺序
        
        Args:
            intent: 意图对象
            current_slots: 当前槽位值
            
        Returns:
            List[str]: 优化后的槽位填充顺序
        """
        try:
            # 获取槽位定义和依赖图
            slot_definitions = await self._get_slot_definitions(intent)
            dependency_graph = await self._get_or_build_dependency_graph(intent, slot_definitions)
            
            # 构建当前值字典
            current_values = {
                name: info.get('value') if isinstance(info, dict) else info
                for name, info in current_slots.items()
                if info is not None
            }
            
            # 获取优化的解析顺序
            optimal_order = dependency_graph.optimize_resolution_order(current_values)
            
            logger.debug(f"优化槽位填充顺序: {optimal_order}")
            return optimal_order
            
        except Exception as e:
            logger.error(f"获取最优槽位顺序失败: {str(e)}")
            # 回退到基本顺序
            slot_definitions = await self._get_slot_definitions(intent)
            return [slot.slot_name for slot in slot_definitions if slot.is_required]
    
    async def validate_slot_dependency_graph(self, intent: Intent) -> Dict[str, Any]:
        """
        验证意图的槽位依赖图
        
        Args:
            intent: 意图对象
            
        Returns:
            Dict[str, Any]: 验证结果
        """
        try:
            slot_definitions = await self._get_slot_definitions(intent)
            dependency_graph = await self._get_or_build_dependency_graph(intent, slot_definitions)
            
            # 检测循环依赖
            has_cycles, cycles = dependency_graph.detect_cycles()
            
            # 获取拓扑排序
            resolution_order = dependency_graph.topological_sort()
            
            # 检查冲突
            validation_result = dependency_graph.validate_dependencies({})
            
            result = {
                'intent_id': intent.id,
                'intent_name': intent.intent_name,
                'has_cycles': has_cycles,
                'cycles': cycles,
                'resolution_order': resolution_order,
                'conflicts': [
                    {'edge1': str(c[0]), 'edge2': str(c[1])}
                    for c in validation_result.conflicts
                ],
                'graph_summary': dependency_graph.to_dict(),
                'is_valid': not has_cycles and not validation_result.conflicts
            }
            
            return result
            
        except Exception as e:
            logger.error(f"依赖图验证失败: {str(e)}")
            return {
                'intent_id': intent.id,
                'error': str(e),
                'is_valid': False
            }
    
    async def get_dependency_graph_visualization(self, intent: Intent) -> Dict[str, Any]:
        """
        获取依赖图可视化数据
        
        Args:
            intent: 意图对象
            
        Returns:
            Dict[str, Any]: 可视化数据
        """
        try:
            slot_definitions = await self._get_slot_definitions(intent)
            dependency_graph = await self._get_or_build_dependency_graph(intent, slot_definitions)
            
            # 构建节点数据
            nodes = []
            for name, node in dependency_graph.nodes.items():
                nodes.append({
                    'id': name,
                    'label': name,
                    'type': node.slot_type,
                    'required': node.is_required,
                    'dependencies_count': len(node.dependencies),
                    'dependents_count': len(node.dependents)
                })
            
            # 构建边数据
            edges = []
            for edge in dependency_graph.edges:
                edges.append({
                    'from': edge.from_slot,
                    'to': edge.to_slot,
                    'type': edge.dependency_type.value,
                    'priority': edge.priority,
                    'condition': edge.condition
                })
            
            return {
                'intent_name': intent.intent_name,
                'nodes': nodes,
                'edges': edges,
                'metadata': {
                    'node_count': len(nodes),
                    'edge_count': len(edges),
                    'has_cycles': dependency_graph.detect_cycles()[0]
                }
            }
            
        except Exception as e:
            logger.error(f"生成依赖图可视化数据失败: {str(e)}")
            return {
                'intent_name': intent.intent_name,
                'error': str(e),
                'nodes': [],
                'edges': []
            }
    
    async def generate_slot_clarification_question(self,
                                                 slot: Slot,
                                                 context: Optional[Dict] = None,
                                                 user_id: Optional[str] = None) -> str:
        """
        生成槽位澄清问题（TASK-023实现）
        
        Args:
            slot: 槽位对象
            context: 对话上下文
            user_id: 用户ID
            
        Returns:
            str: 槽位澄清问题文本
        """
        try:
            # 构建澄清上下文
            clarification_context = {
                'conversation_history': context.get('history', []) if context else [],
                'user_preferences': context.get('user_preferences', {}) if context else {},
                'current_intent': context.get('current_intent') if context else None,
                'turn_count': context.get('turn_count', 1) if context else 1,
                'user_engagement': context.get('user_engagement', 0.7) if context else 0.7,
                'time_pressure': context.get('time_pressure', 0.3) if context else 0.3,
                'failed_attempts': context.get('failed_attempts', 0) if context else 0,
                'slot_type': slot.slot_type,
                'slot_name': slot.slot_name,
                'is_required': slot.is_required,
                'validation_rules': slot.get_validation_rules(),
                'examples': slot.get_examples()
            }
            
            # 根据槽位类型选择澄清类型
            if slot.slot_type == 'ENUM':
                clarification_type = ClarificationType.VALUE
            elif slot.is_required:
                clarification_type = ClarificationType.SLOT
            else:
                clarification_type = ClarificationType.INCOMPLETE_INFO
            
            # 生成澄清问题
            clarification_question = await self.clarification_generator.generate_clarification_question(
                clarification_type, [{'slot': slot}], clarification_context, user_id
            )
            
            logger.info(f"生成槽位澄清问题: 槽位={slot.slot_name}, "
                       f"类型={clarification_type.value}, "
                       f"风格={clarification_question.style.value}")
            
            return clarification_question.question_text
            
        except Exception as e:
            logger.error(f"槽位澄清问题生成失败: {str(e)}")
            return await self._generate_fallback_slot_question(slot)
    
    async def _generate_fallback_slot_question(self, slot: Slot) -> str:
        """
        生成回退槽位问题
        
        Args:
            slot: 槽位对象
            
        Returns:
            str: 回退槽位问题
        """
        try:
            # 槽位显示名称映射
            display_names = {
                'departure_city': '出发城市',
                'arrival_city': '到达城市',
                'departure_date': '出发日期',
                'return_date': '返程日期',
                'passenger_count': '乘客人数',
                'phone_number': '手机号码',
                'passenger_name': '乘客姓名',
                'card_number': '银行卡号'
            }
            
            display_name = display_names.get(slot.slot_name, slot.slot_name)
            
            # 基于槽位类型生成适当的问题
            if slot.slot_type == 'DATE':
                return f"请提供{display_name}（如：明天、下周一、2024-01-15）："
            elif slot.slot_type == 'NUMBER':
                return f"请输入{display_name}："
            elif slot.slot_type == 'ENUM':
                examples = slot.get_examples()
                if examples:
                    return f"请选择{display_name}（{', '.join(examples[:3])}）："
                else:
                    return f"请选择{display_name}："
            else:
                return f"请提供{display_name}："
                
        except Exception as e:
            logger.error(f"回退槽位问题生成失败: {str(e)}")
            return f"请提供{slot.slot_name}："
    
    async def detect_slot_value_clarification_need(self,
                                                 slot: Slot,
                                                 value: Any,
                                                 context: Optional[Dict] = None) -> Tuple[bool, Optional[ClarificationType], str]:
        """
        检测槽位值是否需要澄清
        
        Args:
            slot: 槽位对象
            value: 槽位值
            context: 对话上下文
            
        Returns:
            Tuple[bool, Optional[ClarificationType], str]: (是否需要澄清, 澄清类型, 描述)
        """
        try:
            # 检查值是否为空
            if not value or (isinstance(value, str) and len(value.strip()) == 0):
                return True, ClarificationType.INCOMPLETE_INFO, "槽位值为空"
            
            # 验证槽位值
            is_valid, error_msg = await self.validate_slot_value(slot, value, context)
            if not is_valid:
                return True, ClarificationType.VALUE, f"验证失败: {error_msg}"
            
            # 检查是否需要确认
            if slot.slot_type == 'ENUM':
                examples = slot.get_examples()
                if examples and str(value).lower() not in [ex.lower() for ex in examples]:
                    return True, ClarificationType.VALUE, "枚举值不在选项中"
            
            # 检查上下文一致性
            if context and slot.slot_type == 'DATE':
                # 检查日期逻辑
                if slot.slot_name == 'return_date' and 'departure_date' in context.get('slots', {}):
                    try:
                        from datetime import datetime
                        return_date = datetime.fromisoformat(str(value)).date()
                        departure_date = datetime.fromisoformat(str(context['slots']['departure_date'])).date()
                        if return_date <= departure_date:
                            return True, ClarificationType.CONFLICTING_INFO, "返程日期不能早于或等于出发日期"
                    except Exception:
                        pass
            
            return False, None, "无需澄清"
            
        except Exception as e:
            logger.error(f"槽位值澄清需求检测失败: {str(e)}")
            return False, None, f"检测失败: {str(e)}"