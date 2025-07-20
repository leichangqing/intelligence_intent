"""
澄清问题生成器
专门用于生成澄清用户意图和信息的问题
"""

from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
from enum import Enum
import logging
from datetime import datetime
import json
import re

from .ambiguity_detector import AmbiguityAnalysis, AmbiguityType
from ..models.slot import Slot
from ..models.intent import Intent
from ..models.conversation import Conversation
from ..utils.logger import get_logger

logger = get_logger(__name__)


class ClarificationType(Enum):
    """澄清类型"""
    INTENT_CLARIFICATION = "intent_clarification"       # 意图澄清
    SLOT_CLARIFICATION = "slot_clarification"           # 槽位澄清
    VALUE_CLARIFICATION = "value_clarification"         # 值澄清
    AMBIGUITY_RESOLUTION = "ambiguity_resolution"       # 歧义解决
    CONTEXT_CLARIFICATION = "context_clarification"     # 上下文澄清
    CONFIRMATION_REQUEST = "confirmation_request"       # 确认请求
    INCOMPLETE_INFO = "incomplete_info"                 # 信息不完整
    CONFLICTING_INFO = "conflicting_info"              # 信息冲突


class ClarificationLevel(Enum):
    """澄清级别"""
    SIMPLE = "simple"           # 简单澄清
    MODERATE = "moderate"       # 中等澄清
    COMPLEX = "complex"         # 复杂澄清
    CRITICAL = "critical"       # 关键澄清


class ClarificationStyle(Enum):
    """澄清风格"""
    DIRECT = "direct"           # 直接询问
    SUGGESTIVE = "suggestive"   # 建议式
    EXPLANATORY = "explanatory" # 解释式
    EXPLORATORY = "exploratory" # 探索式
    CONFIRMATORY = "confirmatory" # 确认式


@dataclass
class ClarificationContext:
    """澄清上下文"""
    user_input: str
    parsed_intents: List[Dict]
    extracted_slots: Dict[str, Any]
    ambiguity_analysis: Optional[AmbiguityAnalysis]
    conversation_history: List[Dict]
    user_preferences: Dict[str, Any]
    current_intent: Optional[str]
    incomplete_slots: List[str]
    conflicting_values: Dict[str, List[Any]]
    confidence_scores: Dict[str, float]


@dataclass
class ClarificationQuestion:
    """澄清问题"""
    question: str
    clarification_type: ClarificationType
    clarification_level: ClarificationLevel
    style: ClarificationStyle
    target_intent: Optional[str]
    target_slots: List[str]
    suggested_values: List[str]
    confidence: float
    urgency: float
    context_hints: Dict[str, Any]
    follow_up_questions: List[str]
    expected_response_type: str
    validation_rules: Dict[str, Any]
    metadata: Dict[str, Any]


class ClarificationQuestionGenerator:
    """澄清问题生成器"""
    
    def __init__(self):
        self.clarification_templates = self._initialize_templates()
        self.context_analyzers = self._initialize_context_analyzers()
        self.response_patterns = self._initialize_response_patterns()
        self.user_adaptation_profiles = {}
        
        # 生成统计
        self.generation_stats = {
            'total_generated': 0,
            'by_type': {ct.value: 0 for ct in ClarificationType},
            'by_level': {cl.value: 0 for cl in ClarificationLevel},
            'success_rates': {},
            'avg_confidence': 0.0
        }
    
    def _initialize_templates(self) -> Dict[str, Dict[str, List[str]]]:
        """初始化澄清问题模板"""
        return {
            ClarificationType.INTENT_CLARIFICATION.value: {
                ClarificationStyle.DIRECT.value: [
                    "您是想{intent1}还是{intent2}？",
                    "请明确您的需求：{intent_options}",
                    "我理解您可能想要：{intent_list}，请选择一个。"
                ],
                ClarificationStyle.SUGGESTIVE.value: [
                    "根据您的描述，我猜您可能想要{suggested_intent}，对吗？",
                    "听起来您想{suggested_intent}，是这样吗？",
                    "您的意思是想{suggested_intent}吗？"
                ],
                ClarificationStyle.EXPLANATORY.value: [
                    "您的需求可能涉及多个服务：{detailed_options}。请让我知道您具体想要哪个。",
                    "根据您的描述，我找到了几个可能的服务：{detailed_options}。请选择最符合您需求的。"
                ]
            },
            ClarificationType.SLOT_CLARIFICATION.value: {
                ClarificationStyle.DIRECT.value: [
                    "请提供{slot_name}：",
                    "我需要知道{slot_name}才能继续。",
                    "您的{slot_name}是什么？"
                ],
                ClarificationStyle.SUGGESTIVE.value: [
                    "您是否想说{slot_name}是{suggested_value}？",
                    "根据上下文，{slot_name}可能是{suggested_value}，对吗？",
                    "我猜{slot_name}是{suggested_value}，请确认。"
                ],
                ClarificationStyle.EXPLANATORY.value: [
                    "为了{purpose}，我需要{slot_name}。{explanation}",
                    "{slot_name}是{description}。请提供这个信息。",
                    "关于{slot_name}：{explanation}。请告诉我。"
                ]
            },
            ClarificationType.VALUE_CLARIFICATION.value: {
                ClarificationStyle.DIRECT.value: [
                    "您说的{value}是指{clarification_options}中的哪个？",
                    "{value}不够明确，请从{options}中选择。",
                    "请明确{value}的具体含义。"
                ],
                ClarificationStyle.CONFIRMATORY.value: [
                    "您说的{value}是{interpreted_value}吗？",
                    "确认一下，{value}指的是{interpreted_value}？",
                    "我理解{value}是{interpreted_value}，对吗？"
                ]
            },
            ClarificationType.AMBIGUITY_RESOLUTION.value: {
                ClarificationStyle.DIRECT.value: [
                    "您的需求有歧义，请从以下选项中选择：{options}",
                    "我检测到多种可能的理解：{options}。请明确您的意思。",
                    "为了避免误解，请从{options}中选择。"
                ],
                ClarificationStyle.EXPLORATORY.value: [
                    "您的需求可能有多种理解，让我逐一确认：{exploration_questions}",
                    "为了更好地理解您的需求，请回答：{exploration_questions}",
                    "让我通过几个问题来理解您的具体需求：{exploration_questions}"
                ]
            },
            ClarificationType.CONTEXT_CLARIFICATION.value: {
                ClarificationStyle.DIRECT.value: [
                    "基于我们之前的对话，您现在想{context_based_intent}吗？",
                    "您是想继续{previous_intent}还是开始{new_intent}？",
                    "请明确您当前的需求是什么。"
                ],
                ClarificationStyle.CONFIRMATORY.value: [
                    "我们刚才在讨论{previous_topic}，您现在想{current_intent}吗？",
                    "确认一下，您想从{previous_context}转到{current_context}吗？"
                ]
            },
            ClarificationType.CONFIRMATION_REQUEST.value: {
                ClarificationStyle.CONFIRMATORY.value: [
                    "请确认：{confirmation_details}",
                    "让我确认一下您的信息：{confirmation_details}",
                    "请核实以下信息：{confirmation_details}"
                ]
            },
            ClarificationType.INCOMPLETE_INFO.value: {
                ClarificationStyle.DIRECT.value: [
                    "您的信息不完整，还需要：{missing_info}",
                    "为了继续，我需要：{missing_info}",
                    "请补充以下信息：{missing_info}"
                ],
                ClarificationStyle.SUGGESTIVE.value: [
                    "我注意到您没有提供{missing_info}，是否需要帮助？",
                    "关于{missing_info}，您是否需要我提供一些建议？",
                    "看起来{missing_info}没有提供，我可以帮您吗？"
                ]
            },
            ClarificationType.CONFLICTING_INFO.value: {
                ClarificationStyle.DIRECT.value: [
                    "您提供的信息存在冲突：{conflict_description}。请澄清。",
                    "我发现矛盾的信息：{conflict_details}。请确认正确的信息。",
                    "请解决以下信息冲突：{conflict_resolution_options}"
                ],
                ClarificationStyle.EXPLANATORY.value: [
                    "您之前说{previous_info}，现在又说{current_info}。{explanation}",
                    "存在信息不一致：{detailed_conflict_explanation}。请澄清。"
                ]
            }
        }
    
    def _initialize_context_analyzers(self) -> Dict[str, callable]:
        """初始化上下文分析器"""
        return {
            'intent_ambiguity': self._analyze_intent_ambiguity,
            'slot_completeness': self._analyze_slot_completeness,
            'value_clarity': self._analyze_value_clarity,
            'context_consistency': self._analyze_context_consistency,
            'information_conflicts': self._analyze_information_conflicts
        }
    
    def _initialize_response_patterns(self) -> Dict[str, List[str]]:
        """初始化预期响应模式"""
        return {
            'intent_selection': [r'\d+', r'第?\d+个?', r'选择?\d+', r'我要.*', r'我想.*'],
            'slot_value': [r'.*', r'\d+', r'[一-龥]+', r'[a-zA-Z]+'],
            'confirmation': [r'是|对|好|确认', r'不是|不对|错', r'修改|更改'],
            'binary_choice': [r'是|对|好|确认|yes|y', r'不是|不对|错|no|n'],
            'selection': [r'\d+', r'第?\d+个?', r'选择?\d+', r'[一二三四五六七八九十]+']
        }
    
    async def generate_clarification_question(self, 
                                            context: ClarificationContext,
                                            user_id: Optional[str] = None) -> ClarificationQuestion:
        """
        生成澄清问题
        
        Args:
            context: 澄清上下文
            user_id: 用户ID
            
        Returns:
            ClarificationQuestion: 生成的澄清问题
        """
        try:
            # 分析澄清需求
            clarification_needs = await self._analyze_clarification_needs(context)
            
            # 选择澄清类型和级别
            clarification_type, level = self._determine_clarification_type_and_level(
                clarification_needs, context
            )
            
            # 选择澄清风格
            style = await self._select_clarification_style(
                clarification_type, level, context, user_id
            )
            
            # 生成问题
            question_text = await self._generate_question_text(
                clarification_type, level, style, context
            )
            
            # 生成建议值
            suggested_values = await self._generate_suggested_values(
                clarification_type, context
            )
            
            # 计算置信度和紧急度
            confidence = self._calculate_generation_confidence(
                clarification_type, level, context
            )
            urgency = self._calculate_urgency(clarification_type, level, context)
            
            # 生成后续问题
            follow_up_questions = await self._generate_follow_up_questions(
                clarification_type, context
            )
            
            # 确定预期响应类型
            expected_response_type = self._determine_expected_response_type(
                clarification_type, style
            )
            
            # 生成验证规则
            validation_rules = self._generate_validation_rules(
                clarification_type, context
            )
            
            # 创建澄清问题
            clarification_question = ClarificationQuestion(
                question=question_text,
                clarification_type=clarification_type,
                clarification_level=level,
                style=style,
                target_intent=context.current_intent,
                target_slots=context.incomplete_slots,
                suggested_values=suggested_values,
                confidence=confidence,
                urgency=urgency,
                context_hints=self._extract_context_hints(context),
                follow_up_questions=follow_up_questions,
                expected_response_type=expected_response_type,
                validation_rules=validation_rules,
                metadata={
                    'generation_timestamp': datetime.now().isoformat(),
                    'user_id': user_id,
                    'context_analysis': clarification_needs
                }
            )
            
            # 更新统计
            self._update_generation_stats(clarification_question)
            
            # 记录用户适应
            if user_id:
                await self._update_user_adaptation(user_id, clarification_question)
            
            logger.info(f"生成澄清问题: 类型={clarification_type.value}, "
                       f"级别={level.value}, 风格={style.value}, "
                       f"置信度={confidence:.3f}")
            
            return clarification_question
            
        except Exception as e:
            logger.error(f"澄清问题生成失败: {str(e)}")
            return self._create_fallback_question(context)
    
    async def _analyze_clarification_needs(self, context: ClarificationContext) -> Dict[str, Any]:
        """分析澄清需求"""
        needs = {}
        
        try:
            # 运行所有上下文分析器
            for analyzer_name, analyzer_func in self.context_analyzers.items():
                needs[analyzer_name] = await analyzer_func(context)
            
            # 综合分析结果
            needs['priority_order'] = self._prioritize_clarification_needs(needs)
            needs['complexity_score'] = self._calculate_complexity_score(needs)
            
            return needs
            
        except Exception as e:
            logger.error(f"澄清需求分析失败: {str(e)}")
            return {'error': str(e)}
    
    async def _analyze_intent_ambiguity(self, context: ClarificationContext) -> Dict[str, Any]:
        """分析意图歧义"""
        analysis = {
            'has_ambiguity': False,
            'ambiguity_score': 0.0,
            'candidate_intents': [],
            'confidence_gaps': []
        }
        
        try:
            if len(context.parsed_intents) > 1:
                analysis['has_ambiguity'] = True
                analysis['candidate_intents'] = context.parsed_intents
                
                # 计算置信度差异
                confidences = [intent.get('confidence', 0.0) for intent in context.parsed_intents]
                if len(confidences) >= 2:
                    top_conf = max(confidences)
                    second_conf = sorted(confidences, reverse=True)[1]
                    analysis['ambiguity_score'] = 1.0 - (top_conf - second_conf)
                    analysis['confidence_gaps'] = confidences
            
            # 检查歧义分析结果
            if context.ambiguity_analysis and context.ambiguity_analysis.is_ambiguous:
                analysis['has_ambiguity'] = True
                analysis['ambiguity_score'] = max(analysis['ambiguity_score'], 
                                                context.ambiguity_analysis.ambiguity_score)
            
            return analysis
            
        except Exception as e:
            logger.error(f"意图歧义分析失败: {str(e)}")
            return analysis
    
    async def _analyze_slot_completeness(self, context: ClarificationContext) -> Dict[str, Any]:
        """分析槽位完整性"""
        analysis = {
            'completeness_score': 0.0,
            'missing_required_slots': [],
            'missing_optional_slots': [],
            'partially_filled_slots': []
        }
        
        try:
            # 分析缺失的槽位
            analysis['missing_required_slots'] = [
                slot for slot in context.incomplete_slots 
                if slot in context.extracted_slots or slot not in context.extracted_slots
            ]
            
            # 分析部分填充的槽位
            for slot_name, value in context.extracted_slots.items():
                if value is None or (isinstance(value, str) and not value.strip()):
                    analysis['partially_filled_slots'].append(slot_name)
            
            # 计算完整性得分
            total_slots = len(context.incomplete_slots) + len(context.extracted_slots)
            if total_slots > 0:
                filled_slots = len([v for v in context.extracted_slots.values() if v is not None])
                analysis['completeness_score'] = filled_slots / total_slots
            
            return analysis
            
        except Exception as e:
            logger.error(f"槽位完整性分析失败: {str(e)}")
            return analysis
    
    async def _analyze_value_clarity(self, context: ClarificationContext) -> Dict[str, Any]:
        """分析值清晰度"""
        analysis = {
            'unclear_values': [],
            'ambiguous_values': [],
            'confidence_issues': []
        }
        
        try:
            # 检查低置信度的值
            for slot_name, confidence in context.confidence_scores.items():
                if confidence < 0.6:
                    analysis['confidence_issues'].append({
                        'slot': slot_name,
                        'confidence': confidence,
                        'value': context.extracted_slots.get(slot_name)
                    })
            
            # 检查模糊的值
            for slot_name, value in context.extracted_slots.items():
                if isinstance(value, str):
                    if self._is_ambiguous_value(value):
                        analysis['ambiguous_values'].append({
                            'slot': slot_name,
                            'value': value,
                            'reason': 'ambiguous_expression'
                        })
            
            return analysis
            
        except Exception as e:
            logger.error(f"值清晰度分析失败: {str(e)}")
            return analysis
    
    async def _analyze_context_consistency(self, context: ClarificationContext) -> Dict[str, Any]:
        """分析上下文一致性"""
        analysis = {
            'consistency_score': 1.0,
            'inconsistencies': [],
            'context_switches': []
        }
        
        try:
            # 检查与历史对话的一致性
            if context.conversation_history:
                # 检查意图切换
                previous_intents = [
                    turn.get('intent') for turn in context.conversation_history[-3:]
                    if turn.get('intent')
                ]
                
                if context.current_intent and previous_intents:
                    if context.current_intent != previous_intents[-1]:
                        analysis['context_switches'].append({
                            'from': previous_intents[-1],
                            'to': context.current_intent,
                            'reason': 'intent_switch'
                        })
                        analysis['consistency_score'] -= 0.3
            
            # 检查槽位值的一致性
            for slot_name, values in context.conflicting_values.items():
                if len(values) > 1:
                    analysis['inconsistencies'].append({
                        'slot': slot_name,
                        'values': values,
                        'reason': 'conflicting_values'
                    })
                    analysis['consistency_score'] -= 0.2
            
            return analysis
            
        except Exception as e:
            logger.error(f"上下文一致性分析失败: {str(e)}")
            return analysis
    
    async def _analyze_information_conflicts(self, context: ClarificationContext) -> Dict[str, Any]:
        """分析信息冲突"""
        analysis = {
            'has_conflicts': False,
            'conflict_details': [],
            'resolution_suggestions': []
        }
        
        try:
            # 检查槽位值冲突
            for slot_name, values in context.conflicting_values.items():
                if len(values) > 1:
                    analysis['has_conflicts'] = True
                    analysis['conflict_details'].append({
                        'type': 'slot_value_conflict',
                        'slot': slot_name,
                        'values': values,
                        'severity': 'high'
                    })
                    
                    # 生成解决建议
                    analysis['resolution_suggestions'].append({
                        'type': 'value_selection',
                        'slot': slot_name,
                        'options': values
                    })
            
            return analysis
            
        except Exception as e:
            logger.error(f"信息冲突分析失败: {str(e)}")
            return analysis
    
    def _determine_clarification_type_and_level(self, 
                                              needs: Dict[str, Any],
                                              context: ClarificationContext) -> Tuple[ClarificationType, ClarificationLevel]:
        """确定澄清类型和级别"""
        try:
            # 优先处理冲突信息
            if needs.get('information_conflicts', {}).get('has_conflicts'):
                return ClarificationType.CONFLICTING_INFO, ClarificationLevel.CRITICAL
            
            # 处理意图歧义
            intent_analysis = needs.get('intent_ambiguity', {})
            if intent_analysis.get('has_ambiguity') and intent_analysis.get('ambiguity_score', 0) > 0.6:
                return ClarificationType.AMBIGUITY_RESOLUTION, ClarificationLevel.COMPLEX
            
            # 处理槽位不完整
            slot_analysis = needs.get('slot_completeness', {})
            if slot_analysis.get('missing_required_slots'):
                return ClarificationType.INCOMPLETE_INFO, ClarificationLevel.MODERATE
            
            # 处理值不清晰
            value_analysis = needs.get('value_clarity', {})
            if value_analysis.get('ambiguous_values') or value_analysis.get('confidence_issues'):
                return ClarificationType.VALUE_CLARIFICATION, ClarificationLevel.MODERATE
            
            # 处理上下文不一致
            context_analysis = needs.get('context_consistency', {})
            if context_analysis.get('consistency_score', 1.0) < 0.7:
                return ClarificationType.CONTEXT_CLARIFICATION, ClarificationLevel.MODERATE
            
            # 默认为意图澄清
            return ClarificationType.INTENT_CLARIFICATION, ClarificationLevel.SIMPLE
            
        except Exception as e:
            logger.error(f"澄清类型级别确定失败: {str(e)}")
            return ClarificationType.INTENT_CLARIFICATION, ClarificationLevel.SIMPLE
    
    async def _select_clarification_style(self, 
                                        clarification_type: ClarificationType,
                                        level: ClarificationLevel,
                                        context: ClarificationContext,
                                        user_id: Optional[str]) -> ClarificationStyle:
        """选择澄清风格"""
        try:
            # 获取用户偏好
            user_profile = self.user_adaptation_profiles.get(user_id, {})
            preferred_style = user_profile.get('preferred_style', ClarificationStyle.DIRECT)
            
            # 根据澄清类型选择风格
            if clarification_type == ClarificationType.CONFLICTING_INFO:
                return ClarificationStyle.EXPLANATORY
            elif clarification_type == ClarificationType.AMBIGUITY_RESOLUTION:
                return ClarificationStyle.DIRECT
            elif clarification_type == ClarificationType.CONFIRMATION_REQUEST:
                return ClarificationStyle.CONFIRMATORY
            elif level == ClarificationLevel.COMPLEX:
                return ClarificationStyle.EXPLANATORY
            else:
                return preferred_style
                
        except Exception as e:
            logger.error(f"澄清风格选择失败: {str(e)}")
            return ClarificationStyle.DIRECT
    
    async def _generate_question_text(self,
                                    clarification_type: ClarificationType,
                                    level: ClarificationLevel,
                                    style: ClarificationStyle,
                                    context: ClarificationContext) -> str:
        """生成问题文本"""
        try:
            # 获取模板
            templates = self.clarification_templates.get(
                clarification_type.value, {}
            ).get(style.value, ["请提供更多信息。"])
            
            # 选择模板
            template = templates[0] if templates else "请提供更多信息。"
            
            # 准备模板变量
            template_vars = await self._prepare_template_variables(
                clarification_type, context
            )
            
            # 格式化模板
            question = self._format_template(template, template_vars)
            
            # 应用级别调整
            if level == ClarificationLevel.COMPLEX:
                question = self._add_complexity_elements(question, context)
            elif level == ClarificationLevel.SIMPLE:
                question = self._simplify_question(question)
            
            return question
            
        except Exception as e:
            logger.error(f"问题文本生成失败: {str(e)}")
            return "请提供更多信息以帮助我理解您的需求。"
    
    async def _prepare_template_variables(self,
                                        clarification_type: ClarificationType,
                                        context: ClarificationContext) -> Dict[str, str]:
        """准备模板变量"""
        variables = {}
        
        try:
            if clarification_type == ClarificationType.INTENT_CLARIFICATION:
                if len(context.parsed_intents) >= 2:
                    variables['intent1'] = context.parsed_intents[0].get('display_name', 
                                                                       context.parsed_intents[0].get('intent_name', ''))
                    variables['intent2'] = context.parsed_intents[1].get('display_name',
                                                                       context.parsed_intents[1].get('intent_name', ''))
                    
                    options = []
                    for i, intent in enumerate(context.parsed_intents[:3], 1):
                        display_name = intent.get('display_name', intent.get('intent_name', ''))
                        options.append(f"{i}. {display_name}")
                    variables['intent_options'] = '\n'.join(options)
                    variables['intent_list'] = ', '.join([intent.get('display_name', intent.get('intent_name', '')) 
                                                        for intent in context.parsed_intents[:3]])
            
            elif clarification_type == ClarificationType.SLOT_CLARIFICATION:
                if context.incomplete_slots:
                    slot_name = context.incomplete_slots[0]
                    variables['slot_name'] = self._get_slot_display_name(slot_name)
                    variables['purpose'] = self._get_slot_purpose(slot_name, context.current_intent)
                    variables['explanation'] = self._get_slot_explanation(slot_name)
                    variables['description'] = self._get_slot_description(slot_name)
            
            elif clarification_type == ClarificationType.VALUE_CLARIFICATION:
                if context.extracted_slots:
                    for slot_name, value in context.extracted_slots.items():
                        if value and self._is_ambiguous_value(str(value)):
                            variables['value'] = str(value)
                            variables['interpreted_value'] = self._interpret_value(value, slot_name)
                            variables['clarification_options'] = self._get_clarification_options(value, slot_name)
                            variables['options'] = variables['clarification_options']
                            break
            
            elif clarification_type == ClarificationType.CONFLICTING_INFO:
                conflicts = []
                for slot_name, values in context.conflicting_values.items():
                    if len(values) > 1:
                        conflicts.append(f"{self._get_slot_display_name(slot_name)}: {' vs '.join(map(str, values))}")
                
                variables['conflict_description'] = '; '.join(conflicts)
                variables['conflict_details'] = '\n'.join(conflicts)
                variables['conflict_resolution_options'] = self._generate_conflict_resolution_options(context.conflicting_values)
            
            elif clarification_type == ClarificationType.INCOMPLETE_INFO:
                missing = [self._get_slot_display_name(slot) for slot in context.incomplete_slots]
                variables['missing_info'] = ', '.join(missing)
            
            return variables
            
        except Exception as e:
            logger.error(f"模板变量准备失败: {str(e)}")
            return {}
    
    def _format_template(self, template: str, variables: Dict[str, str]) -> str:
        """格式化模板"""
        try:
            formatted = template
            for var_name, var_value in variables.items():
                formatted = formatted.replace(f"{{{var_name}}}", str(var_value))
            
            # 清理未替换的变量
            formatted = re.sub(r'\{[^}]+\}', '', formatted)
            
            return formatted.strip()
            
        except Exception as e:
            logger.error(f"模板格式化失败: {str(e)}")
            return template
    
    async def _generate_suggested_values(self,
                                       clarification_type: ClarificationType,
                                       context: ClarificationContext) -> List[str]:
        """生成建议值"""
        suggestions = []
        
        try:
            if clarification_type == ClarificationType.INTENT_CLARIFICATION:
                suggestions = [intent.get('display_name', intent.get('intent_name', '')) 
                             for intent in context.parsed_intents[:3]]
            
            elif clarification_type == ClarificationType.SLOT_CLARIFICATION:
                if context.incomplete_slots:
                    slot_name = context.incomplete_slots[0]
                    suggestions = self._get_slot_suggestions(slot_name, context)
            
            elif clarification_type == ClarificationType.VALUE_CLARIFICATION:
                for slot_name, value in context.extracted_slots.items():
                    if value and self._is_ambiguous_value(str(value)):
                        suggestions = self._get_value_clarification_suggestions(value, slot_name)
                        break
            
            return suggestions[:5]  # 最多5个建议
            
        except Exception as e:
            logger.error(f"建议值生成失败: {str(e)}")
            return []
    
    def _calculate_generation_confidence(self,
                                       clarification_type: ClarificationType,
                                       level: ClarificationLevel,
                                       context: ClarificationContext) -> float:
        """计算生成置信度"""
        try:
            base_confidence = 0.7
            
            # 基于澄清类型调整
            type_confidence = {
                ClarificationType.INTENT_CLARIFICATION: 0.8,
                ClarificationType.SLOT_CLARIFICATION: 0.9,
                ClarificationType.VALUE_CLARIFICATION: 0.7,
                ClarificationType.AMBIGUITY_RESOLUTION: 0.6,
                ClarificationType.CONFLICTING_INFO: 0.8,
                ClarificationType.INCOMPLETE_INFO: 0.9
            }
            
            base_confidence = type_confidence.get(clarification_type, base_confidence)
            
            # 基于级别调整
            if level == ClarificationLevel.SIMPLE:
                base_confidence += 0.1
            elif level == ClarificationLevel.COMPLEX:
                base_confidence -= 0.1
            elif level == ClarificationLevel.CRITICAL:
                base_confidence -= 0.2
            
            # 基于上下文信息质量调整
            if context.ambiguity_analysis:
                base_confidence += 0.1
            
            if context.conversation_history:
                base_confidence += 0.05
            
            return max(0.1, min(0.95, base_confidence))
            
        except Exception as e:
            logger.error(f"置信度计算失败: {str(e)}")
            return 0.7
    
    def _calculate_urgency(self,
                          clarification_type: ClarificationType,
                          level: ClarificationLevel,
                          context: ClarificationContext) -> float:
        """计算紧急度"""
        try:
            base_urgency = 0.5
            
            # 基于类型调整
            if clarification_type == ClarificationType.CONFLICTING_INFO:
                base_urgency = 0.9
            elif clarification_type == ClarificationType.AMBIGUITY_RESOLUTION:
                base_urgency = 0.8
            elif clarification_type == ClarificationType.INCOMPLETE_INFO:
                base_urgency = 0.7
            
            # 基于级别调整
            if level == ClarificationLevel.CRITICAL:
                base_urgency += 0.2
            elif level == ClarificationLevel.COMPLEX:
                base_urgency += 0.1
            
            return max(0.1, min(1.0, base_urgency))
            
        except Exception as e:
            logger.error(f"紧急度计算失败: {str(e)}")
            return 0.5
    
    async def _generate_follow_up_questions(self,
                                          clarification_type: ClarificationType,
                                          context: ClarificationContext) -> List[str]:
        """生成后续问题"""
        follow_ups = []
        
        try:
            if clarification_type == ClarificationType.INTENT_CLARIFICATION:
                follow_ups = [
                    "您需要我解释这些选项的区别吗？",
                    "如果都不符合，请描述您的具体需求。"
                ]
            
            elif clarification_type == ClarificationType.SLOT_CLARIFICATION:
                follow_ups = [
                    "需要我提供一些示例吗？",
                    "如果不确定，我可以帮您选择。"
                ]
            
            elif clarification_type == ClarificationType.VALUE_CLARIFICATION:
                follow_ups = [
                    "您可以提供更具体的信息吗？",
                    "是否需要我列出所有可能的选项？"
                ]
            
            return follow_ups[:3]  # 最多3个后续问题
            
        except Exception as e:
            logger.error(f"后续问题生成失败: {str(e)}")
            return []
    
    def _prioritize_clarification_needs(self, needs: Dict[str, Any]) -> List[str]:
        """优先级排序澄清需求"""
        priorities = []
        
        # 信息冲突最高优先级
        if needs.get('information_conflicts', {}).get('has_conflicts'):
            priorities.append('information_conflicts')
        
        # 意图歧义次之
        if needs.get('intent_ambiguity', {}).get('has_ambiguity'):
            priorities.append('intent_ambiguity')
        
        # 槽位不完整
        if needs.get('slot_completeness', {}).get('missing_required_slots'):
            priorities.append('slot_completeness')
        
        # 值不清晰
        if needs.get('value_clarity', {}).get('ambiguous_values'):
            priorities.append('value_clarity')
        
        # 上下文不一致
        if needs.get('context_consistency', {}).get('consistency_score', 1.0) < 0.7:
            priorities.append('context_consistency')
        
        return priorities
    
    def _calculate_complexity_score(self, needs: Dict[str, Any]) -> float:
        """计算复杂度分数"""
        complexity = 0.0
        
        # 各种需求的复杂度贡献
        if needs.get('information_conflicts', {}).get('has_conflicts'):
            complexity += 0.4
        
        if needs.get('intent_ambiguity', {}).get('has_ambiguity'):
            complexity += 0.3
        
        if needs.get('slot_completeness', {}).get('missing_required_slots'):
            complexity += 0.2
        
        if needs.get('value_clarity', {}).get('ambiguous_values'):
            complexity += 0.2
        
        if needs.get('context_consistency', {}).get('consistency_score', 1.0) < 0.7:
            complexity += 0.1
        
        return min(1.0, complexity)
    
    def _is_ambiguous_value(self, value: str) -> bool:
        """判断值是否模糊"""
        ambiguous_patterns = [
            r'那个|这个|那里|这里',
            r'差不多|大概|可能|应该',
            r'不知道|不确定|不清楚',
            r'随便|都行|无所谓'
        ]
        
        for pattern in ambiguous_patterns:
            if re.search(pattern, value):
                return True
        
        return False
    
    def _get_slot_display_name(self, slot_name: str) -> str:
        """获取槽位显示名称"""
        display_names = {
            "departure_city": "出发城市",
            "arrival_city": "到达城市",
            "departure_date": "出发日期",
            "return_date": "返程日期",
            "passenger_count": "乘客人数",
            "phone_number": "手机号码",
            "passenger_name": "乘客姓名",
            "card_number": "银行卡号"
        }
        return display_names.get(slot_name, slot_name)
    
    def _get_slot_purpose(self, slot_name: str, intent: Optional[str]) -> str:
        """获取槽位用途"""
        purposes = {
            "departure_city": "确定您的出发地点",
            "arrival_city": "确定您的目的地",
            "departure_date": "安排您的出发时间",
            "passenger_count": "预订对应数量的票",
            "phone_number": "联系您确认信息",
            "card_number": "查询账户余额"
        }
        return purposes.get(slot_name, f"完成{intent or '您的请求'}")
    
    def _get_slot_explanation(self, slot_name: str) -> str:
        """获取槽位解释"""
        explanations = {
            "departure_city": "请提供您希望出发的城市名称",
            "arrival_city": "请提供您希望到达的城市名称",
            "departure_date": "请提供具体的出发日期",
            "phone_number": "请提供11位手机号码",
            "card_number": "请提供银行卡号"
        }
        return explanations.get(slot_name, "请提供相关信息")
    
    def _get_slot_description(self, slot_name: str) -> str:
        """获取槽位描述"""
        descriptions = {
            "departure_city": "您要从哪个城市出发",
            "arrival_city": "您要到达哪个城市",
            "departure_date": "您计划的出发日期",
            "phone_number": "您的联系电话",
            "card_number": "您要查询的银行卡"
        }
        return descriptions.get(slot_name, "相关信息")
    
    def _update_generation_stats(self, question: ClarificationQuestion):
        """更新生成统计"""
        try:
            self.generation_stats['total_generated'] += 1
            self.generation_stats['by_type'][question.clarification_type.value] += 1
            self.generation_stats['by_level'][question.clarification_level.value] += 1
            
            # 更新平均置信度
            total = self.generation_stats['total_generated']
            current_avg = self.generation_stats['avg_confidence']
            self.generation_stats['avg_confidence'] = ((current_avg * (total - 1)) + question.confidence) / total
            
        except Exception as e:
            logger.error(f"统计更新失败: {str(e)}")
    
    async def _update_user_adaptation(self, user_id: str, question: ClarificationQuestion):
        """更新用户适应信息"""
        try:
            if user_id not in self.user_adaptation_profiles:
                self.user_adaptation_profiles[user_id] = {
                    'preferred_style': question.style,
                    'successful_types': [],
                    'interaction_count': 0,
                    'average_confidence': 0.0
                }
            
            profile = self.user_adaptation_profiles[user_id]
            profile['interaction_count'] += 1
            
            # 更新平均置信度
            count = profile['interaction_count']
            current_avg = profile['average_confidence']
            profile['average_confidence'] = ((current_avg * (count - 1)) + question.confidence) / count
            
        except Exception as e:
            logger.error(f"用户适应更新失败: {str(e)}")
    
    def _create_fallback_question(self, context: ClarificationContext) -> ClarificationQuestion:
        """创建后备问题"""
        return ClarificationQuestion(
            question="请提供更多信息以帮助我理解您的需求。",
            clarification_type=ClarificationType.INTENT_CLARIFICATION,
            clarification_level=ClarificationLevel.SIMPLE,
            style=ClarificationStyle.DIRECT,
            target_intent=context.current_intent,
            target_slots=context.incomplete_slots,
            suggested_values=[],
            confidence=0.5,
            urgency=0.5,
            context_hints={},
            follow_up_questions=["您可以详细描述一下您的需求吗？"],
            expected_response_type="text",
            validation_rules={},
            metadata={'fallback': True}
        )
    
    def _determine_expected_response_type(self, 
                                        clarification_type: ClarificationType,
                                        style: ClarificationStyle) -> str:
        """确定预期响应类型"""
        if clarification_type == ClarificationType.INTENT_CLARIFICATION:
            return "intent_selection"
        elif clarification_type == ClarificationType.CONFIRMATION_REQUEST:
            return "confirmation"
        elif style == ClarificationStyle.CONFIRMATORY:
            return "binary_choice"
        else:
            return "text"
    
    def _generate_validation_rules(self, 
                                 clarification_type: ClarificationType,
                                 context: ClarificationContext) -> Dict[str, Any]:
        """生成验证规则"""
        rules = {}
        
        if clarification_type == ClarificationType.INTENT_CLARIFICATION:
            rules['valid_selections'] = list(range(1, len(context.parsed_intents) + 1))
        elif clarification_type == ClarificationType.SLOT_CLARIFICATION:
            if context.incomplete_slots:
                slot_name = context.incomplete_slots[0]
                rules['slot_type'] = self._get_slot_type(slot_name)
        
        return rules
    
    def _extract_context_hints(self, context: ClarificationContext) -> Dict[str, Any]:
        """提取上下文提示"""
        hints = {}
        
        if context.conversation_history:
            hints['has_history'] = True
            hints['turn_count'] = len(context.conversation_history)
        
        if context.user_preferences:
            hints['has_preferences'] = True
            hints['preference_count'] = len(context.user_preferences)
        
        if context.ambiguity_analysis:
            hints['ambiguity_score'] = context.ambiguity_analysis.ambiguity_score
        
        return hints
    
    def _get_slot_type(self, slot_name: str) -> str:
        """获取槽位类型"""
        slot_types = {
            "departure_city": "TEXT",
            "arrival_city": "TEXT",
            "departure_date": "DATE",
            "passenger_count": "NUMBER",
            "phone_number": "PHONE",
            "card_number": "CARD"
        }
        return slot_types.get(slot_name, "TEXT")
    
    def _get_slot_suggestions(self, slot_name: str, context: ClarificationContext) -> List[str]:
        """获取槽位建议"""
        suggestions = []
        
        # 从用户偏好获取
        if slot_name in context.user_preferences:
            suggestions.append(str(context.user_preferences[slot_name]))
        
        # 从历史对话获取
        for turn in context.conversation_history:
            if slot_name in turn:
                suggestions.append(str(turn[slot_name]))
        
        # 默认建议
        defaults = {
            "departure_city": ["北京", "上海", "广州"],
            "arrival_city": ["深圳", "杭州", "成都"],
            "passenger_count": ["1", "2", "3"]
        }
        
        suggestions.extend(defaults.get(slot_name, []))
        
        return list(set(suggestions))[:3]
    
    def _interpret_value(self, value: str, slot_name: str) -> str:
        """解释值的含义"""
        if slot_name == "departure_city":
            if "那边" in value or "那里" in value:
                return "您之前提到的城市"
        elif slot_name == "departure_date":
            if "明天" in value:
                return "明天"
            elif "后天" in value:
                return "后天"
        
        return value
    
    def _get_clarification_options(self, value: str, slot_name: str) -> str:
        """获取澄清选项"""
        if slot_name == "departure_city":
            return "北京、上海、广州"
        elif slot_name == "departure_date":
            return "明天、后天、具体日期"
        
        return "请提供更具体的信息"
    
    def _get_value_clarification_suggestions(self, value: str, slot_name: str) -> List[str]:
        """获取值澄清建议"""
        suggestions = []
        
        if slot_name == "departure_city":
            suggestions = ["北京", "上海", "广州", "深圳"]
        elif slot_name == "departure_date":
            suggestions = ["明天", "后天", "下周一", "2024-01-15"]
        
        return suggestions
    
    def _generate_conflict_resolution_options(self, conflicts: Dict[str, List[Any]]) -> str:
        """生成冲突解决选项"""
        options = []
        
        for slot_name, values in conflicts.items():
            display_name = self._get_slot_display_name(slot_name)
            value_options = [f"{display_name}: {v}" for v in values]
            options.extend(value_options)
        
        return "; ".join(options)
    
    def _add_complexity_elements(self, question: str, context: ClarificationContext) -> str:
        """为复杂问题添加元素"""
        # 添加上下文说明
        if context.conversation_history:
            question = f"结合我们之前的对话，{question}"
        
        # 添加详细说明
        question += "\n\n请提供详细信息以便我更好地帮助您。"
        
        return question
    
    def _simplify_question(self, question: str) -> str:
        """简化问题"""
        # 移除复杂的解释
        simplified = question.split("。")[0] + "。"
        
        # 移除括号内容
        simplified = re.sub(r'（[^）]*）', '', simplified)
        
        return simplified.strip()
    
    def get_generator_statistics(self) -> Dict[str, Any]:
        """获取生成器统计信息"""
        return {
            'generation_stats': self.generation_stats,
            'user_profiles_count': len(self.user_adaptation_profiles),
            'template_categories': len(self.clarification_templates),
            'context_analyzers': list(self.context_analyzers.keys()),
            'response_patterns': len(self.response_patterns)
        }