"""
智能槽位询问生成引擎
生成上下文感知、个性化的槽位询问问题
"""

from typing import Dict, List, Optional, Any, Set, Tuple
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
import json
import re

from ..models.slot import Slot
from ..models.intent import Intent
from ..models.conversation import Conversation
from ..utils.logger import get_logger

logger = get_logger(__name__)


class QuestionType(Enum):
    """问题类型"""
    DIRECT = "direct"                   # 直接询问
    CHOICE = "choice"                  # 选择题
    CONFIRMATION = "confirmation"       # 确认问题
    CLARIFICATION = "clarification"     # 澄清问题
    FOLLOW_UP = "follow_up"            # 追问
    SUGGESTION = "suggestion"          # 建议式询问
    CONDITIONAL = "conditional"        # 条件性询问


class QuestionStyle(Enum):
    """问题风格"""
    FORMAL = "formal"                  # 正式
    CASUAL = "casual"                  # 随意
    FRIENDLY = "friendly"              # 友好
    PROFESSIONAL = "professional"      # 专业
    CONCISE = "concise"               # 简洁
    DETAILED = "detailed"             # 详细
    DIRECT = "direct"                 # 直接


@dataclass
class QuestionTemplate:
    """问题模板"""
    template: str
    question_type: QuestionType
    style: QuestionStyle
    variables: List[str]
    conditions: Optional[Dict[str, Any]] = None
    priority: int = 0
    
    def format(self, context: Dict[str, Any]) -> str:
        """格式化模板"""
        try:
            formatted = self.template
            for var in self.variables:
                value = context.get(var, f"{{{var}}}")
                formatted = formatted.replace(f"{{{var}}}", str(value))
            return formatted
        except Exception as e:
            logger.warning(f"模板格式化失败: {e}")
            return self.template


@dataclass
class QuestionCandidate:
    """问题候选"""
    question: str
    question_type: QuestionType
    style: QuestionStyle
    confidence: float
    context_relevance: float
    personalization_score: float
    slot_names: List[str]
    metadata: Dict[str, Any]
    
    @property
    def total_score(self) -> float:
        """计算总分"""
        return (self.confidence * 0.4 + 
                self.context_relevance * 0.3 + 
                self.personalization_score * 0.3)


class IntelligentQuestionGenerator:
    """智能问题生成器"""
    
    def __init__(self):
        self.templates: Dict[str, List[QuestionTemplate]] = {}
        self.style_preferences: Dict[str, QuestionStyle] = {}
        self.question_history: Dict[str, List[str]] = {}
        self._setup_default_templates()
    
    def _setup_default_templates(self):
        """设置默认问题模板"""
        # 机票预订相关模板
        flight_templates = [
            QuestionTemplate(
                template="请问您要从哪个城市出发？",
                question_type=QuestionType.DIRECT,
                style=QuestionStyle.FRIENDLY,
                variables=[]
            ),
            QuestionTemplate(
                template="您的出发城市是{suggestion}吗？",
                question_type=QuestionType.CONFIRMATION,
                style=QuestionStyle.CASUAL,
                variables=["suggestion"]
            ),
            QuestionTemplate(
                template="请选择您的出发城市：\n1. {option1}\n2. {option2}\n3. {option3}\n或者您可以直接输入其他城市",
                question_type=QuestionType.CHOICE,
                style=QuestionStyle.DETAILED,
                variables=["option1", "option2", "option3"]
            ),
            QuestionTemplate(
                template="您计划什么时候出发？（如：明天、下周一、2024-01-15）",
                question_type=QuestionType.DIRECT,
                style=QuestionStyle.DETAILED,
                variables=[]
            ),
            QuestionTemplate(
                template="您需要预订几张机票？",
                question_type=QuestionType.DIRECT,
                style=QuestionStyle.CONCISE,
                variables=[]
            )
        ]
        
        # 余额查询相关模板
        balance_templates = [
            QuestionTemplate(
                template="请提供您的银行卡号进行余额查询：",
                question_type=QuestionType.DIRECT,
                style=QuestionStyle.PROFESSIONAL,
                variables=[]
            ),
            QuestionTemplate(
                template="为了查询余额，我需要您的银行卡号。请放心，这是安全的查询。",
                question_type=QuestionType.DIRECT,
                style=QuestionStyle.FRIENDLY,
                variables=[]
            ),
            QuestionTemplate(
                template="请输入您要查询的卡号（如：6222开头的储蓄卡）：",
                question_type=QuestionType.SUGGESTION,
                style=QuestionStyle.DETAILED,
                variables=[]
            )
        ]
        
        # 通用模板
        general_templates = [
            QuestionTemplate(
                template="请提供{slot_display_name}：",
                question_type=QuestionType.DIRECT,
                style=QuestionStyle.CONCISE,
                variables=["slot_display_name"]
            ),
            QuestionTemplate(
                template="为了{intent_purpose}，我需要知道{slot_display_name}。",
                question_type=QuestionType.DIRECT,
                style=QuestionStyle.PROFESSIONAL,
                variables=["intent_purpose", "slot_display_name"]
            ),
            QuestionTemplate(
                template="您能告诉我{slot_display_name}吗？{examples_hint}",
                question_type=QuestionType.DIRECT,
                style=QuestionStyle.FRIENDLY,
                variables=["slot_display_name", "examples_hint"]
            )
        ]
        
        self.templates.update({
            "book_flight": flight_templates,
            "check_balance": balance_templates,
            "general": general_templates
        })
    
    async def generate_question(self, 
                              intent: Intent,
                              missing_slots: List[Slot],
                              context: Dict[str, Any],
                              user_id: Optional[str] = None) -> QuestionCandidate:
        """
        生成智能问题
        
        Args:
            intent: 意图对象
            missing_slots: 缺失的槽位列表
            context: 对话上下文
            user_id: 用户ID
            
        Returns:
            QuestionCandidate: 最佳问题候选
        """
        try:
            # 获取用户偏好风格
            preferred_style = await self._get_user_style_preference(user_id) if user_id else QuestionStyle.FRIENDLY
            
            # 生成问题候选列表
            candidates = await self._generate_candidates(intent, missing_slots, context, preferred_style)
            
            # 对候选问题评分
            scored_candidates = await self._score_candidates(candidates, context, user_id)
            
            # 选择最佳候选
            best_candidate = max(scored_candidates, key=lambda c: c.total_score)
            
            # 记录问题历史
            if user_id:
                await self._record_question_history(user_id, best_candidate.question)
            
            logger.debug(f"生成问题: {best_candidate.question} (得分: {best_candidate.total_score:.3f})")
            
            return best_candidate
            
        except Exception as e:
            logger.error(f"问题生成失败: {e}")
            # 返回默认问题
            return self._create_fallback_question(missing_slots)
    
    async def _generate_candidates(self,
                                 intent: Intent,
                                 missing_slots: List[Slot],
                                 context: Dict[str, Any],
                                 preferred_style: QuestionStyle) -> List[QuestionCandidate]:
        """生成问题候选列表"""
        candidates = []
        
        # 获取意图相关模板
        intent_templates = self.templates.get(intent.intent_name, [])
        general_templates = self.templates.get("general", [])
        all_templates = intent_templates + general_templates
        
        for slot in missing_slots:
            slot_candidates = await self._generate_slot_candidates(
                slot, intent, context, all_templates, preferred_style
            )
            candidates.extend(slot_candidates)
        
        # 生成多槽位组合问题
        if len(missing_slots) > 1:
            combo_candidates = await self._generate_combination_candidates(
                missing_slots, intent, context, preferred_style
            )
            candidates.extend(combo_candidates)
        
        return candidates
    
    async def _generate_slot_candidates(self,
                                      slot: Slot,
                                      intent: Intent,
                                      context: Dict[str, Any],
                                      templates: List[QuestionTemplate],
                                      preferred_style: QuestionStyle) -> List[QuestionCandidate]:
        """为单个槽位生成候选问题"""
        candidates = []
        
        # 准备模板上下文
        template_context = {
            "slot_name": slot.slot_name,
            "slot_display_name": self._get_slot_display_name(slot),
            "intent_purpose": self._get_intent_purpose(intent),
            "examples_hint": self._get_examples_hint(slot)
        }
        
        # 添加用户建议值
        suggestions = await self._get_slot_suggestions(slot, context)
        if suggestions:
            template_context.update({
                "suggestion": suggestions[0],
                "option1": suggestions[0] if len(suggestions) > 0 else "",
                "option2": suggestions[1] if len(suggestions) > 1 else "",
                "option3": suggestions[2] if len(suggestions) > 2 else ""
            })
        
        # 使用自定义模板（如果存在）
        if slot.prompt_template:
            custom_question = slot.format_prompt(template_context)
            candidates.append(QuestionCandidate(
                question=custom_question,
                question_type=QuestionType.DIRECT,
                style=preferred_style,
                confidence=0.9,
                context_relevance=0.8,
                personalization_score=0.7,
                slot_names=[slot.slot_name],
                metadata={"source": "custom_template"}
            ))
        
        # 使用模板生成问题
        for template in templates:
            if self._template_matches_slot(template, slot, template_context):
                try:
                    question = template.format(template_context)
                    
                    # 计算基础分数
                    confidence = self._calculate_template_confidence(template, slot)
                    context_relevance = self._calculate_context_relevance(template, context)
                    personalization = self._calculate_personalization_score(template, preferred_style)
                    
                    candidates.append(QuestionCandidate(
                        question=question,
                        question_type=template.question_type,
                        style=template.style,
                        confidence=confidence,
                        context_relevance=context_relevance,
                        personalization_score=personalization,
                        slot_names=[slot.slot_name],
                        metadata={"source": "template", "template_id": id(template)}
                    ))
                    
                except Exception as e:
                    logger.warning(f"模板生成失败: {type(e).__name__}: {str(e)}")
        
        return candidates
    
    async def _generate_combination_candidates(self,
                                             slots: List[Slot],
                                             intent: Intent,
                                             context: Dict[str, Any],
                                             preferred_style: QuestionStyle) -> List[QuestionCandidate]:
        """生成多槽位组合问题"""
        candidates = []
        
        if len(slots) <= 1:
            return candidates
        
        # 生成组合问题模板
        slot_names = [slot.slot_name for slot in slots[:3]]  # 最多3个槽位
        slot_display_names = [self._get_slot_display_name(slot) for slot in slots[:3]]
        
        # 列表式问题
        list_question = "请提供以下信息：\n"
        for i, display_name in enumerate(slot_display_names, 1):
            list_question += f"{i}. {display_name}\n"
        
        candidates.append(QuestionCandidate(
            question=list_question.strip(),
            question_type=QuestionType.DIRECT,
            style=QuestionStyle.DETAILED,
            confidence=0.8,
            context_relevance=0.7,
            personalization_score=0.6,
            slot_names=slot_names,
            metadata={"source": "combination", "type": "list"}
        ))
        
        # 自然语言组合问题
        if len(slots) == 2:
            natural_question = f"请告诉我{slot_display_names[0]}和{slot_display_names[1]}。"
        else:
            natural_question = f"请提供{slot_display_names[0]}、{slot_display_names[1]}等信息。"
        
        candidates.append(QuestionCandidate(
            question=natural_question,
            question_type=QuestionType.DIRECT,
            style=QuestionStyle.CASUAL,
            confidence=0.7,
            context_relevance=0.8,
            personalization_score=0.7,
            slot_names=slot_names,
            metadata={"source": "combination", "type": "natural"}
        ))
        
        return candidates
    
    async def _score_candidates(self,
                              candidates: List[QuestionCandidate],
                              context: Dict[str, Any],
                              user_id: Optional[str]) -> List[QuestionCandidate]:
        """对候选问题进行评分"""
        for candidate in candidates:
            # 调整上下文相关性分数
            if self._has_context_clues(candidate, context):
                candidate.context_relevance += 0.2
            
            # 调整个性化分数
            if user_id:
                history_penalty = await self._get_repetition_penalty(user_id, candidate.question)
                candidate.personalization_score -= history_penalty
            
            # 调整置信度
            if candidate.question_type in [QuestionType.CONFIRMATION, QuestionType.SUGGESTION]:
                candidate.confidence += 0.1
        
        return candidates
    
    def _get_slot_display_name(self, slot: Slot) -> str:
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
        return display_names.get(slot.slot_name, slot.slot_name)
    
    def _get_intent_purpose(self, intent: Intent) -> str:
        """获取意图目的描述"""
        purposes = {
            "book_flight": "为您预订机票",
            "check_balance": "查询账户余额",
            "transfer_money": "进行转账操作",
            "pay_bill": "缴费服务"
        }
        return purposes.get(intent.intent_name, "完成您的请求")
    
    def _get_examples_hint(self, slot: Slot) -> str:
        """获取示例提示"""
        examples = slot.get_examples()
        if not examples:
            return ""
        
        if len(examples) == 1:
            return f"（例如：{examples[0]}）"
        elif len(examples) <= 3:
            return f"（例如：{', '.join(examples)}）"
        else:
            return f"（例如：{', '.join(examples[:2])}等）"
    
    async def _get_slot_suggestions(self, slot: Slot, context: Dict[str, Any]) -> List[str]:
        """获取槽位建议值"""
        suggestions = []
        
        # 从上下文获取建议
        if "user_profile" in context:
            profile = context["user_profile"]
            if slot.slot_name == "departure_city" and "preferred_departure_city" in profile:
                suggestions.append(profile["preferred_departure_city"])
        
        # 从历史对话获取建议
        if "conversation_context" in context:
            conv_context = context["conversation_context"]
            if slot.slot_name in conv_context:
                suggestions.append(conv_context[slot.slot_name])
        
        # 从槽位示例获取建议
        examples = slot.get_examples()
        suggestions.extend(examples[:3])
        
        # 去重并返回前3个
        unique_suggestions = []
        seen = set()
        for suggestion in suggestions:
            if suggestion not in seen:
                unique_suggestions.append(suggestion)
                seen.add(suggestion)
                if len(unique_suggestions) >= 3:
                    break
        
        return unique_suggestions
    
    def _template_matches_slot(self, template: QuestionTemplate, slot: Slot, context: Dict[str, Any]) -> bool:
        """检查模板是否适用于槽位"""
        # 检查模板条件
        if template.conditions:
            for condition, expected in template.conditions.items():
                if condition == "slot_type" and slot.slot_type != expected:
                    return False
                if condition == "is_required" and slot.is_required != expected:
                    return False
        
        # 检查模板变量是否可用
        for var in template.variables:
            if var not in context and f"{{{var}}}" in template.template:
                return False
        
        return True
    
    def _calculate_template_confidence(self, template: QuestionTemplate, slot: Slot) -> float:
        """计算模板置信度"""
        base_confidence = 0.7
        
        # 问题类型加成
        if template.question_type == QuestionType.DIRECT:
            base_confidence += 0.1
        elif template.question_type in [QuestionType.CHOICE, QuestionType.SUGGESTION]:
            base_confidence += 0.15
        
        # 槽位类型匹配加成
        if slot.slot_type == "ENUM" and template.question_type == QuestionType.CHOICE:
            base_confidence += 0.2
        
        return min(base_confidence, 1.0)
    
    def _calculate_context_relevance(self, template: QuestionTemplate, context: Dict[str, Any]) -> float:
        """计算上下文相关性"""
        relevance = 0.6
        
        # 有用户档案信息
        if "user_profile" in context:
            relevance += 0.1
        
        # 有对话历史
        if "conversation_context" in context:
            relevance += 0.1
        
        # 模板类型与上下文匹配
        if template.question_type == QuestionType.CONFIRMATION and "suggestions" in context:
            relevance += 0.2
        
        return min(relevance, 1.0)
    
    def _calculate_personalization_score(self, template: QuestionTemplate, preferred_style: QuestionStyle) -> float:
        """计算个性化分数"""
        if template.style == preferred_style:
            return 0.9
        
        # 风格兼容性矩阵
        style_compatibility = {
            QuestionStyle.FRIENDLY: {QuestionStyle.CASUAL: 0.8, QuestionStyle.DETAILED: 0.7},
            QuestionStyle.PROFESSIONAL: {QuestionStyle.FORMAL: 0.8, QuestionStyle.DETAILED: 0.7},
            QuestionStyle.CONCISE: {QuestionStyle.DIRECT: 0.8}
        }
        
        if preferred_style in style_compatibility:
            return style_compatibility[preferred_style].get(template.style, 0.5)
        
        return 0.6
    
    def _has_context_clues(self, candidate: QuestionCandidate, context: Dict[str, Any]) -> bool:
        """检查候选问题是否有上下文线索"""
        question_lower = candidate.question.lower()
        
        # 检查是否包含建议值
        if "suggestion" in context and str(context["suggestion"]).lower() in question_lower:
            return True
        
        # 检查是否包含用户偏好
        if "user_profile" in context:
            profile = context["user_profile"]
            for value in profile.values():
                if isinstance(value, str) and value.lower() in question_lower:
                    return True
        
        return False
    
    async def _get_repetition_penalty(self, user_id: str, question: str) -> float:
        """计算重复问题的惩罚分数"""
        if user_id not in self.question_history:
            return 0.0
        
        history = self.question_history[user_id]
        similar_count = sum(1 for q in history if self._questions_similar(q, question))
        
        return min(similar_count * 0.1, 0.3)
    
    def _questions_similar(self, q1: str, q2: str) -> bool:
        """检查两个问题是否相似"""
        # 简单的相似度检查
        words1 = set(q1.lower().split())
        words2 = set(q2.lower().split())
        
        if len(words1) == 0 or len(words2) == 0:
            return False
        
        intersection = words1.intersection(words2)
        similarity = len(intersection) / min(len(words1), len(words2))
        
        return similarity > 0.6
    
    async def _get_user_style_preference(self, user_id: str) -> QuestionStyle:
        """获取用户偏好风格"""
        # 从缓存或数据库获取用户偏好
        return self.style_preferences.get(user_id, QuestionStyle.FRIENDLY)
    
    async def _record_question_history(self, user_id: str, question: str):
        """记录问题历史"""
        if user_id not in self.question_history:
            self.question_history[user_id] = []
        
        history = self.question_history[user_id]
        history.append(question)
        
        # 保留最近20个问题
        if len(history) > 20:
            history.pop(0)
    
    def _create_fallback_question(self, missing_slots: List[Slot]) -> QuestionCandidate:
        """创建后备问题"""
        if len(missing_slots) == 1:
            slot = missing_slots[0]
            question = f"请提供{self._get_slot_display_name(slot)}："
        else:
            question = "请提供以下信息以完成您的请求。"
        
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


# 全局问题生成器实例
question_generator = IntelligentQuestionGenerator()