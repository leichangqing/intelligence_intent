"""
追问和个性化问题生成引擎
处理用户回应不完整、模糊或错误时的智能追问逻辑
"""

from typing import Dict, List, Optional, Any, Set, Tuple
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
import re

from .question_generator import QuestionCandidate, QuestionType, QuestionStyle
from .context_aware_questioning import ConversationContext, DialogueState
from ..models.slot import Slot
from ..models.intent import Intent
from ..utils.logger import get_logger

logger = get_logger(__name__)


class FollowUpType(Enum):
    """追问类型"""
    CLARIFICATION = "clarification"     # 澄清追问
    COMPLETION = "completion"           # 补全追问
    CORRECTION = "correction"           # 纠错追问
    VALIDATION = "validation"           # 验证追问
    DISAMBIGUATION = "disambiguation"   # 消歧追问
    SPECIFICATION = "specification"     # 具体化追问
    CONFIRMATION = "confirmation"       # 确认追问


class UserResponseType(Enum):
    """用户回应类型"""
    INCOMPLETE = "incomplete"           # 不完整
    AMBIGUOUS = "ambiguous"            # 模糊
    INVALID = "invalid"                # 无效
    PARTIAL = "partial"                # 部分正确
    CONFLICTING = "conflicting"        # 冲突
    UNCLEAR = "unclear"                # 不清楚
    OFF_TOPIC = "off_topic"            # 偏题


@dataclass
class UserResponse:
    """用户回应分析结果"""
    original_text: str
    response_type: UserResponseType
    extracted_values: Dict[str, Any]
    confidence_scores: Dict[str, float]
    issues: List[str]
    suggestions: List[str]
    context_clues: Dict[str, Any]


@dataclass
class FollowUpQuestion:
    """追问问题"""
    question: str
    followup_type: FollowUpType
    target_slots: List[str]
    context_hints: Dict[str, Any]
    urgency: float  # 0.0-1.0
    patience_level: float  # 0.0-1.0，适应用户耐心程度


class FollowUpQuestionEngine:
    """追问问题生成引擎"""
    
    def __init__(self):
        self.response_patterns = self._setup_response_patterns()
        self.followup_templates = self._setup_followup_templates()
        self.personalization_profiles: Dict[str, Dict] = {}
        self.error_recovery_strategies = self._setup_error_recovery_strategies()
    
    def _setup_response_patterns(self) -> Dict[str, List[str]]:
        """设置用户回应模式"""
        return {
            "incomplete_indicators": [
                r"不知道", r"不清楚", r"不太明白", r"不确定",
                r"可能", r"大概", r"应该", r"好像",
                r"忘了", r"想不起来", r"不记得"
            ],
            "ambiguous_indicators": [
                r"那个", r"这个", r"那里", r"这里",
                r"附近", r"差不多", r"类似", r"相似"
            ],
            "invalid_indicators": [
                r"随便", r"无所谓", r"都行", r"没关系",
                r"跳过", r"算了", r"不要了"
            ],
            "partial_indicators": [
                r"但是", r"不过", r"除了", r"还有",
                r"或者", r"要么", r"也许"
            ],
            "conflicting_indicators": [
                r"不对", r"错了", r"改成", r"修改",
                r"其实", r"应该是", r"不是"
            ]
        }
    
    def _setup_followup_templates(self) -> Dict[FollowUpType, List[str]]:
        """设置追问模板"""
        return {
            FollowUpType.CLARIFICATION: [
                "您是指{clarification_target}吗？",
                "能再详细说明一下{clarification_target}吗？",
                "关于{clarification_target}，您的意思是？"
            ],
            FollowUpType.COMPLETION: [
                "您还需要提供{missing_info}。",
                "请补充{missing_info}的信息。",
                "关于{missing_info}，您还没有告诉我。"
            ],
            FollowUpType.CORRECTION: [
                "刚才的{field_name}信息好像有问题，请重新输入。",
                "让我们重新确认{field_name}。",
                "{field_name}的格式不正确，请重新输入。"
            ],
            FollowUpType.VALIDATION: [
                "您确认{field_name}是{value}吗？",
                "让我确认一下，{field_name}是{value}，对吗？",
                "请确认：{field_name} = {value}"
            ],
            FollowUpType.DISAMBIGUATION: [
                "您是说{option1}还是{option2}？",
                "有多个选择：{options}，请选择一个。",
                "请从以下选项中选择：{options}"
            ],
            FollowUpType.SPECIFICATION: [
                "能具体说明一下{field_name}吗？",
                "请提供更具体的{field_name}信息。",
                "关于{field_name}，能给出更详细的描述吗？"
            ]
        }
    
    def _setup_error_recovery_strategies(self) -> Dict[str, Dict]:
        """设置错误恢复策略"""
        return {
            "max_attempts": {
                "default": 3,
                "phone_number": 2,
                "card_number": 2,
                "date": 3,
                "city": 4
            },
            "escalation_steps": {
                1: "提供示例",
                2: "简化问题",
                3: "提供选择",
                4: "人工协助"
            },
            "patience_thresholds": {
                "high": 0.8,    # 用户很有耐心
                "medium": 0.5,  # 用户中等耐心
                "low": 0.2      # 用户没耐心
            }
        }
    
    async def analyze_user_response(self,
                                  user_input: str,
                                  expected_slots: List[Slot],
                                  context: ConversationContext) -> UserResponse:
        """
        分析用户回应
        
        Args:
            user_input: 用户输入
            expected_slots: 期望的槽位
            context: 对话上下文
            
        Returns:
            UserResponse: 回应分析结果
        """
        try:
            # 基础信息提取
            extracted_values = {}
            confidence_scores = {}
            issues = []
            suggestions = []
            
            # 判断回应类型
            response_type = self._classify_response_type(user_input)
            
            # 尝试提取槽位值
            for slot in expected_slots:
                value, confidence = await self._extract_slot_value(user_input, slot, context)
                if value is not None:
                    extracted_values[slot.slot_name] = value
                    confidence_scores[slot.slot_name] = confidence
            
            # 分析问题和建议
            issues = self._identify_response_issues(user_input, expected_slots, response_type)
            suggestions = self._generate_response_suggestions(user_input, expected_slots, response_type)
            
            # 获取上下文线索
            context_clues = self._extract_context_clues(user_input, context)
            
            return UserResponse(
                original_text=user_input,
                response_type=response_type,
                extracted_values=extracted_values,
                confidence_scores=confidence_scores,
                issues=issues,
                suggestions=suggestions,
                context_clues=context_clues
            )
            
        except Exception as e:
            logger.error(f"用户回应分析失败: {e}")
            return UserResponse(
                original_text=user_input,
                response_type=UserResponseType.UNCLEAR,
                extracted_values={},
                confidence_scores={},
                issues=["分析失败"],
                suggestions=["请重新描述"],
                context_clues={}
            )
    
    async def generate_followup_question(self,
                                       user_response: UserResponse,
                                       target_slots: List[Slot],
                                       context: ConversationContext) -> FollowUpQuestion:
        """
        生成追问问题
        
        Args:
            user_response: 用户回应分析结果
            target_slots: 目标槽位
            context: 对话上下文
            
        Returns:
            FollowUpQuestion: 追问问题
        """
        try:
            # 确定追问类型
            followup_type = self._determine_followup_type(user_response, target_slots, context)
            
            # 获取用户个性化设置
            user_profile = self._get_user_personalization_profile(context.user_id)
            
            # 生成追问问题
            question = await self._generate_typed_followup(
                followup_type, user_response, target_slots, context, user_profile
            )
            
            # 计算紧急度和耐心适应
            urgency = self._calculate_question_urgency(context, target_slots)
            patience_level = self._assess_user_patience(context, user_profile)
            
            # 适应用户耐心程度
            question = self._adapt_to_patience_level(question, patience_level)
            
            followup_question = FollowUpQuestion(
                question=question,
                followup_type=followup_type,
                target_slots=[slot.slot_name for slot in target_slots],
                context_hints=user_response.context_clues,
                urgency=urgency,
                patience_level=patience_level
            )
            
            # 更新用户个性化档案
            await self._update_personalization_profile(context.user_id, followup_question, user_response)
            
            logger.debug(f"生成追问: 类型={followup_type.value}, 问题={question[:50]}...")
            
            return followup_question
            
        except Exception as e:
            logger.error(f"追问生成失败: {e}")
            return self._create_fallback_followup(target_slots)
    
    def _classify_response_type(self, user_input: str) -> UserResponseType:
        """分类用户回应类型"""
        text = user_input.lower().strip()
        
        # 检查各种模式
        for response_type, patterns in self.response_patterns.items():
            for pattern in patterns:
                if re.search(pattern, text):
                    if response_type == "incomplete_indicators":
                        return UserResponseType.INCOMPLETE
                    elif response_type == "ambiguous_indicators":
                        return UserResponseType.AMBIGUOUS
                    elif response_type == "invalid_indicators":
                        return UserResponseType.INVALID
                    elif response_type == "partial_indicators":
                        return UserResponseType.PARTIAL
                    elif response_type == "conflicting_indicators":
                        return UserResponseType.CONFLICTING
        
        # 基于长度和内容判断
        if len(text) < 3:
            return UserResponseType.INCOMPLETE
        elif len(text.split()) > 20:
            return UserResponseType.OFF_TOPIC
        else:
            return UserResponseType.UNCLEAR
    
    async def _extract_slot_value(self,
                                user_input: str,
                                slot: Slot,
                                context: ConversationContext) -> Tuple[Optional[Any], float]:
        """从用户输入中提取槽位值"""
        text = user_input.strip()
        
        # 基于槽位类型的提取逻辑
        if slot.slot_type == "NUMBER":
            numbers = re.findall(r'\d+', text)
            if numbers:
                return int(numbers[0]), 0.8
        
        elif slot.slot_type == "DATE":
            # 简单的日期提取
            date_patterns = [
                r'(\d{4})-(\d{1,2})-(\d{1,2})',
                r'(\d{1,2})月(\d{1,2})日',
                r'(明天|后天|大后天)'
            ]
            for pattern in date_patterns:
                match = re.search(pattern, text)
                if match:
                    return match.group(), 0.7
        
        elif slot.slot_name == "phone_number":
            phone_pattern = r'1[3-9]\d{9}'
            match = re.search(phone_pattern, text)
            if match:
                return match.group(), 0.9
        
        elif slot.slot_name in ["departure_city", "arrival_city"]:
            # 城市名提取
            city_pattern = r'([北上广深杭成都重庆等]{1,10}[市]?)'
            match = re.search(city_pattern, text)
            if match:
                return match.group(1), 0.8
        
        # 兜底：返回原始文本
        if len(text) > 0 and len(text) < 100:
            return text, 0.3
        
        return None, 0.0
    
    def _identify_response_issues(self,
                                user_input: str,
                                expected_slots: List[Slot],
                                response_type: UserResponseType) -> List[str]:
        """识别回应中的问题"""
        issues = []
        
        if response_type == UserResponseType.INCOMPLETE:
            issues.append("信息不完整")
        elif response_type == UserResponseType.AMBIGUOUS:
            issues.append("信息模糊")
        elif response_type == UserResponseType.INVALID:
            issues.append("信息无效")
        elif response_type == UserResponseType.OFF_TOPIC:
            issues.append("回复偏题")
        
        # 检查格式问题
        for slot in expected_slots:
            if slot.slot_type == "NUMBER" and not re.search(r'\d+', user_input):
                issues.append(f"{slot.slot_name}需要数字")
            elif slot.slot_name == "phone_number" and not re.search(r'1[3-9]\d{9}', user_input):
                issues.append("手机号格式不正确")
        
        return issues
    
    def _generate_response_suggestions(self,
                                     user_input: str,
                                     expected_slots: List[Slot],
                                     response_type: UserResponseType) -> List[str]:
        """生成回应建议"""
        suggestions = []
        
        if response_type == UserResponseType.INCOMPLETE:
            suggestions.append("请提供更详细的信息")
        elif response_type == UserResponseType.AMBIGUOUS:
            suggestions.append("请更具体地描述")
        elif response_type == UserResponseType.INVALID:
            suggestions.append("请提供有效的信息")
        
        # 基于槽位类型的建议
        for slot in expected_slots:
            examples = slot.get_examples()
            if examples:
                suggestions.append(f"例如：{examples[0]}")
        
        return suggestions
    
    def _extract_context_clues(self, user_input: str, context: ConversationContext) -> Dict[str, Any]:
        """提取上下文线索"""
        clues = {}
        
        # 提取关键词
        keywords = re.findall(r'[一-龥]{2,}', user_input)
        if keywords:
            clues["keywords"] = keywords[:5]
        
        # 提取数字
        numbers = re.findall(r'\d+', user_input)
        if numbers:
            clues["numbers"] = numbers
        
        # 提取时间表达
        time_expressions = re.findall(r'(明天|后天|下周|月|日)', user_input)
        if time_expressions:
            clues["time_expressions"] = time_expressions
        
        return clues
    
    def _determine_followup_type(self,
                               user_response: UserResponse,
                               target_slots: List[Slot],
                               context: ConversationContext) -> FollowUpType:
        """确定追问类型"""
        response_type = user_response.response_type
        
        if response_type == UserResponseType.INCOMPLETE:
            return FollowUpType.COMPLETION
        elif response_type == UserResponseType.AMBIGUOUS:
            return FollowUpType.CLARIFICATION
        elif response_type == UserResponseType.INVALID:
            return FollowUpType.CORRECTION
        elif response_type == UserResponseType.PARTIAL:
            return FollowUpType.VALIDATION
        elif response_type == UserResponseType.CONFLICTING:
            return FollowUpType.DISAMBIGUATION
        elif response_type == UserResponseType.UNCLEAR:
            return FollowUpType.SPECIFICATION
        else:
            return FollowUpType.CLARIFICATION
    
    async def _generate_typed_followup(self,
                                     followup_type: FollowUpType,
                                     user_response: UserResponse,
                                     target_slots: List[Slot],
                                     context: ConversationContext,
                                     user_profile: Dict) -> str:
        """生成特定类型的追问"""
        templates = self.followup_templates.get(followup_type, [])
        
        if not templates:
            return "请再详细说明一下。"
        
        # 选择合适的模板
        template = templates[0]  # 暂时选择第一个
        
        # 准备模板参数
        template_vars = self._prepare_template_variables(
            followup_type, user_response, target_slots, context
        )
        
        # 格式化模板
        try:
            question = template.format(**template_vars)
        except KeyError as e:
            logger.warning(f"模板变量缺失: {e}")
            question = templates[-1] if len(templates) > 1 else "请提供更多信息。"
        
        return question
    
    def _prepare_template_variables(self,
                                  followup_type: FollowUpType,
                                  user_response: UserResponse,
                                  target_slots: List[Slot],
                                  context: ConversationContext) -> Dict[str, str]:
        """准备模板变量"""
        variables = {}
        
        if target_slots:
            slot = target_slots[0]
            variables["field_name"] = self._get_slot_display_name(slot)
            variables["clarification_target"] = self._get_slot_display_name(slot)
            variables["missing_info"] = self._get_slot_display_name(slot)
        
        # 添加提取的值
        if user_response.extracted_values:
            first_value = list(user_response.extracted_values.values())[0]
            variables["value"] = str(first_value)
        
        # 添加选项
        if len(target_slots) > 0:
            examples = target_slots[0].get_examples()
            if len(examples) >= 2:
                variables["option1"] = examples[0]
                variables["option2"] = examples[1]
                variables["options"] = ", ".join(examples[:3])
        
        return variables
    
    def _get_user_personalization_profile(self, user_id: str) -> Dict:
        """获取用户个性化档案"""
        if user_id not in self.personalization_profiles:
            self.personalization_profiles[user_id] = {
                "patience_level": 0.7,
                "preferred_style": "friendly",
                "error_tolerance": 0.5,
                "detail_preference": 0.6,
                "interaction_history": [],
                "success_patterns": {},
                "failure_patterns": {}
            }
        
        return self.personalization_profiles[user_id]
    
    def _calculate_question_urgency(self, context: ConversationContext, target_slots: List[Slot]) -> float:
        """计算问题紧急度"""
        urgency = 0.5  # 基础紧急度
        
        # 基于轮次数调整
        if context.turn_count > 5:
            urgency += 0.2
        
        # 基于失败次数调整
        total_failures = sum(context.failed_attempts.values())
        if total_failures > 2:
            urgency += 0.3
        
        # 基于必填槽位调整
        required_slots = [slot for slot in target_slots if slot.is_required]
        if required_slots:
            urgency += 0.2
        
        return min(urgency, 1.0)
    
    def _assess_user_patience(self, context: ConversationContext, user_profile: Dict) -> float:
        """评估用户耐心程度"""
        base_patience = user_profile.get("patience_level", 0.7)
        
        # 基于时间压力调整
        if context.time_pressure > 0.7:
            base_patience -= 0.2
        
        # 基于用户参与度调整
        if context.user_engagement < 0.3:
            base_patience -= 0.1
        
        # 基于失败历史调整
        total_failures = sum(context.failed_attempts.values())
        if total_failures > 1:
            base_patience -= total_failures * 0.1
        
        return max(base_patience, 0.1)
    
    def _adapt_to_patience_level(self, question: str, patience_level: float) -> str:
        """根据耐心程度调整问题"""
        if patience_level < 0.3:  # 用户没耐心
            # 简化问题，直接询问
            question = question.split("（")[0]  # 移除解释
            question = question.split("\n")[0]  # 只保留第一行
        elif patience_level > 0.7:  # 用户很有耐心
            # 可以添加更多解释和帮助
            if "？" in question and not question.endswith("。"):
                question += "如需帮助，请告诉我。"
        
        return question
    
    async def _update_personalization_profile(self,
                                            user_id: str,
                                            followup_question: FollowUpQuestion,
                                            user_response: UserResponse):
        """更新用户个性化档案"""
        if user_id not in self.personalization_profiles:
            return
        
        profile = self.personalization_profiles[user_id]
        
        # 记录交互历史
        interaction = {
            "timestamp": datetime.now(),
            "followup_type": followup_question.followup_type.value,
            "response_type": user_response.response_type.value,
            "urgency": followup_question.urgency,
            "patience_level": followup_question.patience_level
        }
        
        profile["interaction_history"].append(interaction)
        
        # 保留最近50次交互
        if len(profile["interaction_history"]) > 50:
            profile["interaction_history"] = profile["interaction_history"][-50:]
        
        # 更新耐心水平（基于历史表现）
        recent_interactions = profile["interaction_history"][-10:]
        if recent_interactions:
            avg_patience = sum(i["patience_level"] for i in recent_interactions) / len(recent_interactions)
            profile["patience_level"] = (profile["patience_level"] + avg_patience) / 2
    
    def _create_fallback_followup(self, target_slots: List[Slot]) -> FollowUpQuestion:
        """创建后备追问"""
        question = "能再详细说明一下吗？"
        
        if target_slots:
            slot_name = self._get_slot_display_name(target_slots[0])
            question = f"关于{slot_name}，能再详细说明一下吗？"
        
        return FollowUpQuestion(
            question=question,
            followup_type=FollowUpType.CLARIFICATION,
            target_slots=[slot.slot_name for slot in target_slots],
            context_hints={},
            urgency=0.5,
            patience_level=0.5
        )
    
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


# 全局追问引擎实例
followup_engine = FollowUpQuestionEngine()