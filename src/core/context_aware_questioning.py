"""
上下文感知询问策略
根据对话上下文、用户行为和意图状态智能调整询问策略
"""

from typing import Dict, List, Optional, Any, Set, Tuple
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum

from .question_generator import QuestionCandidate, QuestionType, QuestionStyle, IntelligentQuestionGenerator
from ..models.slot import Slot
from ..models.intent import Intent
from ..models.conversation import Conversation
from ..utils.logger import get_logger

logger = get_logger(__name__)


class ContextStrategy(Enum):
    """上下文策略"""
    PROGRESSIVE = "progressive"          # 渐进式询问
    FOCUSED = "focused"                 # 专注式询问
    EXPLORATORY = "exploratory"         # 探索式询问
    CONFIRMATORY = "confirmatory"       # 确认式询问
    RECOVERY = "recovery"               # 恢复式询问
    EFFICIENT = "efficient"             # 高效式询问


class DialogueState(Enum):
    """对话状态"""
    INITIAL = "initial"                 # 初始状态
    COLLECTING = "collecting"           # 收集信息中
    CLARIFYING = "clarifying"           # 澄清中
    CONFIRMING = "confirming"           # 确认中
    COMPLETING = "completing"           # 完成中
    ERROR_RECOVERY = "error_recovery"   # 错误恢复


@dataclass
class ConversationContext:
    """对话上下文"""
    user_id: str
    conversation_id: str
    turn_count: int
    dialogue_state: DialogueState
    failed_attempts: Dict[str, int]
    collected_slots: Dict[str, Any]
    partial_slots: Dict[str, Any]
    user_preferences: Dict[str, Any]
    conversation_history: List[Dict[str, Any]]
    time_pressure: float  # 0.0-1.0，用户时间压力指标
    user_engagement: float  # 0.0-1.0，用户参与度指标
    
    @property
    def completion_rate(self) -> float:
        """计算完成率"""
        if not hasattr(self, '_required_slots_count'):
            return 0.0
        return len(self.collected_slots) / self._required_slots_count if self._required_slots_count > 0 else 1.0


class ContextAwareQuestioningEngine:
    """上下文感知询问引擎"""
    
    def __init__(self, question_generator: IntelligentQuestionGenerator):
        self.question_generator = question_generator
        self.strategy_cache: Dict[str, ContextStrategy] = {}
        self.adaptive_weights = {
            "context_importance": 0.3,
            "user_patience": 0.2,
            "completion_urgency": 0.25,
            "error_recovery": 0.25
        }
    
    async def generate_contextual_question(self,
                                         intent: Intent,
                                         missing_slots: List[Slot],
                                         context: ConversationContext) -> QuestionCandidate:
        """
        生成上下文感知的问题
        
        Args:
            intent: 意图对象
            missing_slots: 缺失槽位列表
            context: 对话上下文
            
        Returns:
            QuestionCandidate: 上下文优化的问题候选
        """
        try:
            # 选择询问策略
            strategy = await self._select_questioning_strategy(context, missing_slots)
            
            # 根据策略调整问题生成
            question_context = await self._build_question_context(context, strategy)
            
            # 生成基础问题候选
            base_candidate = await self.question_generator.generate_question(
                intent, missing_slots, question_context, context.user_id
            )
            
            # 应用上下文策略优化
            optimized_candidate = await self._apply_context_strategy(
                base_candidate, strategy, context, missing_slots
            )
            
            # 记录策略使用
            self.strategy_cache[f"{context.user_id}_{context.conversation_id}"] = strategy
            
            logger.info(f"生成上下文问题: 策略={strategy.value}, 问题={optimized_candidate.question[:50]}...")
            
            return optimized_candidate
            
        except Exception as e:
            logger.error(f"上下文问题生成失败: {e}")
            # 降级到基础问题生成
            return await self.question_generator.generate_question(
                intent, missing_slots, {}, context.user_id
            )
    
    async def _select_questioning_strategy(self,
                                         context: ConversationContext,
                                         missing_slots: List[Slot]) -> ContextStrategy:
        """选择询问策略"""
        # 基于对话状态选择策略
        if context.dialogue_state == DialogueState.INITIAL:
            return ContextStrategy.PROGRESSIVE
        
        elif context.dialogue_state == DialogueState.ERROR_RECOVERY:
            return ContextStrategy.RECOVERY
        
        elif context.dialogue_state == DialogueState.CLARIFYING:
            return ContextStrategy.CONFIRMATORY
        
        # 基于用户行为模式选择
        if context.time_pressure > 0.7:
            return ContextStrategy.EFFICIENT
        
        elif context.user_engagement < 0.3:
            return ContextStrategy.FOCUSED
        
        elif len(missing_slots) > 3:
            return ContextStrategy.PROGRESSIVE
        
        elif context.completion_rate > 0.7:
            return ContextStrategy.CONFIRMATORY
        
        else:
            return ContextStrategy.FOCUSED
    
    async def _build_question_context(self,
                                    context: ConversationContext,
                                    strategy: ContextStrategy) -> Dict[str, Any]:
        """构建问题生成上下文"""
        question_context = {
            "user_id": context.user_id,
            "conversation_id": context.conversation_id,
            "strategy": strategy.value,
            "dialogue_state": context.dialogue_state.value,
            "turn_count": context.turn_count,
            "completion_rate": context.completion_rate,
            "collected_slots": context.collected_slots,
            "partial_slots": context.partial_slots,
            "user_preferences": context.user_preferences,
            "time_pressure": context.time_pressure,
            "user_engagement": context.user_engagement
        }
        
        # 添加策略特定的上下文
        if strategy == ContextStrategy.CONFIRMATORY:
            question_context["confirmation_mode"] = True
            question_context["suggestions"] = self._get_confirmation_suggestions(context)
        
        elif strategy == ContextStrategy.RECOVERY:
            question_context["recovery_mode"] = True
            question_context["failed_slots"] = context.failed_attempts
        
        elif strategy == ContextStrategy.EFFICIENT:
            question_context["efficient_mode"] = True
            question_context["prioritize_required"] = True
        
        return question_context
    
    async def _apply_context_strategy(self,
                                    base_candidate: QuestionCandidate,
                                    strategy: ContextStrategy,
                                    context: ConversationContext,
                                    missing_slots: List[Slot]) -> QuestionCandidate:
        """应用上下文策略优化问题"""
        optimized_candidate = base_candidate
        
        if strategy == ContextStrategy.PROGRESSIVE:
            optimized_candidate = await self._apply_progressive_strategy(
                base_candidate, context, missing_slots
            )
        
        elif strategy == ContextStrategy.FOCUSED:
            optimized_candidate = await self._apply_focused_strategy(
                base_candidate, context, missing_slots
            )
        
        elif strategy == ContextStrategy.CONFIRMATORY:
            optimized_candidate = await self._apply_confirmatory_strategy(
                base_candidate, context, missing_slots
            )
        
        elif strategy == ContextStrategy.RECOVERY:
            optimized_candidate = await self._apply_recovery_strategy(
                base_candidate, context, missing_slots
            )
        
        elif strategy == ContextStrategy.EFFICIENT:
            optimized_candidate = await self._apply_efficient_strategy(
                base_candidate, context, missing_slots
            )
        
        # 应用通用上下文优化
        optimized_candidate = await self._apply_general_optimizations(
            optimized_candidate, context
        )
        
        return optimized_candidate
    
    async def _apply_progressive_strategy(self,
                                        candidate: QuestionCandidate,
                                        context: ConversationContext,
                                        missing_slots: List[Slot]) -> QuestionCandidate:
        """应用渐进式策略"""
        # 渐进式询问：一次只问一个最重要的槽位
        if len(missing_slots) > 1:
            # 选择最重要的槽位
            priority_slot = self._get_highest_priority_slot(missing_slots, context)
            
            # 重新生成单槽位问题
            single_slot_question = await self._generate_single_slot_question(
                priority_slot, context
            )
            
            candidate.question = single_slot_question
            candidate.slot_names = [priority_slot.slot_name]
            candidate.question_type = QuestionType.DIRECT
            candidate.context_relevance += 0.1
        
        # 添加进度提示
        progress_hint = self._generate_progress_hint(context)
        if progress_hint:
            candidate.question += f"\n\n{progress_hint}"
        
        return candidate
    
    async def _apply_focused_strategy(self,
                                    candidate: QuestionCandidate,
                                    context: ConversationContext,
                                    missing_slots: List[Slot]) -> QuestionCandidate:
        """应用专注式策略"""
        # 专注式询问：集中询问相关槽位，减少干扰
        related_slots = self._group_related_slots(missing_slots)
        
        if len(related_slots) > 1:
            # 生成组合问题，但保持简洁
            focused_question = await self._generate_focused_combination_question(
                related_slots, context
            )
            candidate.question = focused_question
            candidate.question_type = QuestionType.DIRECT
            candidate.style = QuestionStyle.CONCISE
        
        # 移除可能的干扰信息
        candidate = self._remove_distracting_elements(candidate)
        
        return candidate
    
    async def _apply_confirmatory_strategy(self,
                                         candidate: QuestionCandidate,
                                         context: ConversationContext,
                                         missing_slots: List[Slot]) -> QuestionCandidate:
        """应用确认式策略"""
        # 确认式询问：基于已有信息进行确认
        confirmations = self._get_confirmation_suggestions(context)
        
        if confirmations:
            # 转换为确认问题
            slot_name = missing_slots[0].slot_name if missing_slots else ""
            suggestion = confirmations.get(slot_name)
            
            if suggestion:
                candidate.question = f"您是说{suggestion}吗？"
                candidate.question_type = QuestionType.CONFIRMATION
                candidate.confidence += 0.2
        
        return candidate
    
    async def _apply_recovery_strategy(self,
                                     candidate: QuestionCandidate,
                                     context: ConversationContext,
                                     missing_slots: List[Slot]) -> QuestionCandidate:
        """应用恢复式策略"""
        # 恢复式询问：针对之前失败的槽位提供更详细的指导
        failed_slots = context.failed_attempts
        
        for slot in missing_slots:
            if slot.slot_name in failed_slots and failed_slots[slot.slot_name] > 0:
                # 生成恢复式问题
                recovery_question = await self._generate_recovery_question(slot, context)
                candidate.question = recovery_question
                candidate.question_type = QuestionType.CLARIFICATION
                candidate.style = QuestionStyle.DETAILED
                break
        
        return candidate
    
    async def _apply_efficient_strategy(self,
                                      candidate: QuestionCandidate,
                                      context: ConversationContext,
                                      missing_slots: List[Slot]) -> QuestionCandidate:
        """应用高效式策略"""
        # 高效式询问：快速收集信息，减少轮次
        if len(missing_slots) > 1:
            # 生成紧凑的多槽位问题
            efficient_question = await self._generate_efficient_combination_question(
                missing_slots[:3], context  # 最多3个槽位
            )
            candidate.question = efficient_question
            candidate.style = QuestionStyle.CONCISE
            candidate.question_type = QuestionType.DIRECT
        
        # 移除不必要的礼貌用语
        candidate.question = self._make_question_more_direct(candidate.question)
        
        return candidate
    
    async def _apply_general_optimizations(self,
                                         candidate: QuestionCandidate,
                                         context: ConversationContext) -> QuestionCandidate:
        """应用通用上下文优化"""
        # 基于用户参与度调整语气
        if context.user_engagement < 0.4:
            candidate = self._make_question_more_engaging(candidate)
        
        # 基于时间压力调整详细程度
        if context.time_pressure > 0.6:
            candidate.question = self._simplify_question(candidate.question)
        
        # 基于失败次数调整帮助信息
        total_failures = sum(context.failed_attempts.values())
        if total_failures > 2:
            candidate.question += self._add_help_hint(context)
        
        return candidate
    
    def _get_highest_priority_slot(self, slots: List[Slot], context: ConversationContext) -> Slot:
        """获取最高优先级槽位"""
        # 优先级计算：必填 > 用户偏好 > 依赖关系 > 字典序
        def priority_score(slot: Slot) -> tuple:
            required_score = 1 if slot.is_required else 0
            preference_score = 1 if slot.slot_name in context.user_preferences else 0
            failure_penalty = context.failed_attempts.get(slot.slot_name, 0)
            
            return (required_score, preference_score, -failure_penalty, slot.slot_name)
        
        return max(slots, key=priority_score)
    
    def _generate_progress_hint(self, context: ConversationContext) -> str:
        """生成进度提示"""
        if hasattr(context, '_required_slots_count') and context._required_slots_count > 0:
            completed = len(context.collected_slots)
            total = context._required_slots_count
            remaining = total - completed
            
            if remaining > 1:
                return f"（还需要{remaining}项信息）"
            elif remaining == 1:
                return f"（最后一项信息）"
        
        return ""
    
    def _group_related_slots(self, slots: List[Slot]) -> List[Slot]:
        """分组相关槽位"""
        # 简单的槽位关联逻辑
        travel_related = {"departure_city", "arrival_city", "departure_date", "return_date"}
        contact_related = {"phone_number", "passenger_name", "email"}
        payment_related = {"card_number", "card_type", "payment_method"}
        
        for slot in slots:
            if slot.slot_name in travel_related:
                return [s for s in slots if s.slot_name in travel_related]
            elif slot.slot_name in contact_related:
                return [s for s in slots if s.slot_name in contact_related]
            elif slot.slot_name in payment_related:
                return [s for s in slots if s.slot_name in payment_related]
        
        return slots[:2]  # 默认返回前两个
    
    async def _generate_single_slot_question(self, slot: Slot, context: ConversationContext) -> str:
        """生成单槽位问题"""
        display_name = self._get_slot_display_name(slot)
        
        # 根据槽位类型生成适当的问题
        if slot.slot_type == "DATE":
            return f"请问您的{display_name}是什么时候？"
        elif slot.slot_type == "NUMBER":
            return f"请输入{display_name}："
        elif slot.slot_type == "ENUM":
            examples = slot.get_examples()
            if examples:
                return f"请选择{display_name}（{', '.join(examples[:3])}）："
        
        return f"请提供{display_name}："
    
    async def _generate_focused_combination_question(self, slots: List[Slot], context: ConversationContext) -> str:
        """生成专注的组合问题"""
        if len(slots) == 2:
            names = [self._get_slot_display_name(slot) for slot in slots]
            return f"请告诉我{names[0]}和{names[1]}。"
        else:
            return "请提供以下信息：" + "、".join([self._get_slot_display_name(slot) for slot in slots[:3]])
    
    async def _generate_recovery_question(self, slot: Slot, context: ConversationContext) -> str:
        """生成恢复式问题"""
        display_name = self._get_slot_display_name(slot)
        examples = slot.get_examples()
        
        question = f"让我帮您重新填写{display_name}。"
        
        if examples:
            question += f"您可以输入类似 {examples[0]} 这样的格式。"
        
        # 添加具体的格式说明
        if slot.slot_type == "DATE":
            question += "日期格式可以是：明天、下周一、或 2024-01-15。"
        elif slot.slot_type == "NUMBER":
            question += "请输入数字。"
        elif slot.slot_name == "phone_number":
            question += "请输入11位手机号码。"
        
        return question
    
    async def _generate_efficient_combination_question(self, slots: List[Slot], context: ConversationContext) -> str:
        """生成高效的组合问题"""
        names = [self._get_slot_display_name(slot) for slot in slots]
        return f"请提供：{', '.join(names)}"
    
    def _get_confirmation_suggestions(self, context: ConversationContext) -> Dict[str, str]:
        """获取确认建议"""
        suggestions = {}
        
        # 从部分槽位中获取建议
        for slot_name, value in context.partial_slots.items():
            if isinstance(value, str) and len(value.strip()) > 0:
                suggestions[slot_name] = value.strip()
        
        # 从用户偏好中获取建议
        for slot_name, value in context.user_preferences.items():
            if slot_name not in suggestions:
                suggestions[slot_name] = str(value)
        
        return suggestions
    
    def _remove_distracting_elements(self, candidate: QuestionCandidate) -> QuestionCandidate:
        """移除干扰元素"""
        # 简化问题，移除过多的例子和解释
        question = candidate.question
        
        # 移除过长的示例
        if "（例如：" in question and len(question) > 100:
            question = re.sub(r"（例如：[^）]*）", "", question)
        
        candidate.question = question.strip()
        return candidate
    
    def _make_question_more_direct(self, question: str) -> str:
        """使问题更直接"""
        # 移除礼貌用语
        direct_question = question
        direct_question = direct_question.replace("请问", "")
        direct_question = direct_question.replace("麻烦", "")
        direct_question = direct_question.replace("可以告诉我", "")
        
        return direct_question.strip()
    
    def _make_question_more_engaging(self, candidate: QuestionCandidate) -> QuestionCandidate:
        """使问题更吸引人"""
        if candidate.style != QuestionStyle.FRIENDLY:
            candidate.style = QuestionStyle.FRIENDLY
            
            # 添加友好的开头
            if not candidate.question.startswith(("好的", "明白", "很好")):
                candidate.question = "好的，" + candidate.question
        
        return candidate
    
    def _simplify_question(self, question: str) -> str:
        """简化问题"""
        # 移除详细的解释和例子
        simplified = question.split("（")[0]  # 移除括号内容
        simplified = simplified.split("\n")[0]  # 只保留第一行
        
        return simplified.strip()
    
    def _add_help_hint(self, context: ConversationContext) -> str:
        """添加帮助提示"""
        return "\n\n如需帮助，请说\"不明白\"或\"跳过\"。"
    
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


# 全局上下文感知询问引擎实例
context_aware_engine: Optional[ContextAwareQuestioningEngine] = None


def get_context_aware_engine(question_generator: IntelligentQuestionGenerator) -> ContextAwareQuestioningEngine:
    """获取上下文感知询问引擎实例"""
    global context_aware_engine
    if context_aware_engine is None:
        context_aware_engine = ContextAwareQuestioningEngine(question_generator)
    return context_aware_engine