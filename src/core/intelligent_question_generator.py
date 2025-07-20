"""
智能歧义问题生成器
实现上下文感知和个性化问题模板
"""

from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
from enum import Enum
import logging
from datetime import datetime
import random
import re

from .ambiguity_detector import AmbiguityAnalysis, AmbiguityType
from ..models.intent import Intent
from ..utils.logger import get_logger

logger = get_logger(__name__)


class QuestionStyle(Enum):
    """问题风格"""
    FORMAL = "formal"           # 正式
    CASUAL = "casual"           # 随意
    FRIENDLY = "friendly"       # 友好
    CONCISE = "concise"         # 简洁
    DETAILED = "detailed"       # 详细


class QuestionComplexity(Enum):
    """问题复杂度"""
    SIMPLE = "simple"           # 简单
    MODERATE = "moderate"       # 中等
    COMPLEX = "complex"         # 复杂


@dataclass
class UserProfile:
    """用户画像"""
    preferred_style: QuestionStyle
    complexity_tolerance: QuestionComplexity
    patience_level: float       # 0.0-1.0
    interaction_history: List[Dict]
    success_patterns: Dict[str, float]
    response_time_avg: float    # 平均响应时间（秒）
    language_preference: str    # 语言偏好


@dataclass
class QuestionContext:
    """问题上下文"""
    conversation_history: List[Dict]
    current_intent_confidence: float
    ambiguity_analysis: AmbiguityAnalysis
    user_engagement: float
    time_pressure: float
    turn_count: int


@dataclass
class GeneratedQuestion:
    """生成的问题"""
    question_text: str
    question_type: str
    style: QuestionStyle
    complexity: QuestionComplexity
    confidence: float
    explanation: str
    follow_up_hints: List[str]
    context_adaptations: List[str]


class IntelligentQuestionGenerator:
    """智能问题生成器"""
    
    def __init__(self):
        self.user_profiles: Dict[str, UserProfile] = {}
        self.question_templates = self._initialize_templates()
        self.context_adaptations = self._initialize_adaptations()
        self.style_modifiers = self._initialize_style_modifiers()
        self.success_patterns = self._initialize_success_patterns()
    
    def _initialize_templates(self) -> Dict[str, Dict[str, List[str]]]:
        """初始化问题模板"""
        return {
            AmbiguityType.SEMANTIC.value: {
                QuestionStyle.FORMAL.value: [
                    "请您从以下选项中选择最符合您需求的功能：\n{options}\n请回复对应的数字。",
                    "为了更准确地理解您的需求，请您明确选择：\n{options}\n请告诉我您的选择。",
                    "检测到多个可能的功能，请您确认：\n{options}\n请指出您需要的功能。"
                ],
                QuestionStyle.CASUAL.value: [
                    "看起来有几个选择呢：\n{options}\n你想要哪个？",
                    "我想到了几种可能：\n{options}\n你觉得是哪个？",
                    "有几个选项：\n{options}\n选哪个呢？"
                ],
                QuestionStyle.FRIENDLY.value: [
                    "我为您找到了几个相关的功能：\n{options}\n请选择您需要的那个。",
                    "这里有几个选择：\n{options}\n您觉得哪个更合适？",
                    "让我为您列出几个选项：\n{options}\n请告诉我您的偏好。"
                ],
                QuestionStyle.CONCISE.value: [
                    "选择：\n{options}",
                    "请选择：\n{options}",
                    "选项：\n{options}"
                ],
                QuestionStyle.DETAILED.value: [
                    "根据您的描述，我识别出以下几个可能的功能。为了确保为您提供最准确的服务，请您仔细查看并选择：\n{options}\n每个选项都有详细说明，请根据您的实际需求进行选择。",
                    "我分析了您的输入，发现可能对应以下几种不同的功能：\n{options}\n请仔细阅读各选项的描述，选择最符合您当前需求的功能。"
                ]
            },
            AmbiguityType.CONTEXTUAL.value: {
                QuestionStyle.FORMAL.value: [
                    "基于当前对话上下文，我需要确认您的意图：\n{options}\n请选择适合的选项。",
                    "考虑到我们之前的对话，请您明确选择：\n{options}"
                ],
                QuestionStyle.CASUAL.value: [
                    "结合刚才聊的，你是想：\n{options}\n哪个对？",
                    "根据咱们的对话，你的意思是：\n{options}\n对吧？"
                ],
                QuestionStyle.FRIENDLY.value: [
                    "结合我们刚才的对话，我想确认一下：\n{options}\n您指的是哪个？",
                    "根据前面的聊天内容，请您确认：\n{options}"
                ]
            },
            AmbiguityType.CONFIDENCE.value: {
                QuestionStyle.FORMAL.value: [
                    "系统检测到以下几个可能的选项，置信度相近：\n{options}\n请您明确选择。",
                    "以下选项的匹配度都较高：\n{options}\n请指定您的需求。"
                ],
                QuestionStyle.CASUAL.value: [
                    "这几个都挺像的：\n{options}\n你要哪个？",
                    "有几个差不多的选择：\n{options}\n选哪个？"
                ]
            }
        }
    
    def _initialize_adaptations(self) -> Dict[str, List[str]]:
        """初始化上下文适应"""
        return {
            'high_time_pressure': [
                "我知道您比较急，",
                "为了节省时间，",
                "快速确认一下，"
            ],
            'low_engagement': [
                "为了更好地帮助您，",
                "我想确保理解正确，",
                "请帮我确认一下，"
            ],
            'multiple_failures': [
                "让我们重新开始，",
                "为了避免误解，",
                "我们再仔细确认一下，"
            ],
            'expert_user': [
                "直接选择：",
                "请选择具体功能：",
                "确认选项："
            ],
            'novice_user': [
                "别担心，这很简单。",
                "我来帮您选择，",
                "让我详细解释一下，"
            ]
        }
    
    def _initialize_style_modifiers(self) -> Dict[str, Dict[str, str]]:
        """初始化风格修饰符"""
        return {
            QuestionStyle.FORMAL.value: {
                'prefix': '请您',
                'suffix': '。谢谢配合。',
                'connector': '，'
            },
            QuestionStyle.CASUAL.value: {
                'prefix': '',
                'suffix': '？',
                'connector': '，'
            },
            QuestionStyle.FRIENDLY.value: {
                'prefix': '',
                'suffix': '😊',
                'connector': '，'
            },
            QuestionStyle.CONCISE.value: {
                'prefix': '',
                'suffix': '',
                'connector': ':'
            },
            QuestionStyle.DETAILED.value: {
                'prefix': '为了确保准确理解您的需求，',
                'suffix': '。如有疑问，请随时询问。',
                'connector': '。此外，'
            }
        }
    
    def _initialize_success_patterns(self) -> Dict[str, float]:
        """初始化成功模式"""
        return {
            'numbered_options': 0.85,
            'descriptive_options': 0.75,
            'example_driven': 0.8,
            'context_aware': 0.9,
            'user_adapted': 0.88
        }
    
    async def generate_disambiguation_question(self,
                                             candidates: List[Dict],
                                             ambiguity_analysis: AmbiguityAnalysis,
                                             context: QuestionContext,
                                             user_id: str) -> GeneratedQuestion:
        """
        生成智能歧义澄清问题
        
        Args:
            candidates: 候选意图列表
            ambiguity_analysis: 歧义分析结果
            context: 问题上下文
            user_id: 用户ID
            
        Returns:
            GeneratedQuestion: 生成的问题
        """
        try:
            # 获取或创建用户画像
            user_profile = await self._get_or_create_user_profile(user_id, context)
            
            # 选择问题风格和复杂度
            style, complexity = self._determine_style_and_complexity(
                user_profile, context, ambiguity_analysis
            )
            
            # 生成候选选项
            formatted_options = await self._format_candidates(
                candidates, style, complexity, context, user_profile
            )
            
            # 选择合适的模板
            template = await self._select_template(
                ambiguity_analysis.primary_type, style, context, user_profile
            )
            
            # 应用上下文适应
            adapted_template = await self._apply_context_adaptations(
                template, context, user_profile
            )
            
            # 生成最终问题
            question_text = adapted_template.format(options=formatted_options)
            
            # 应用风格修饰
            final_question = self._apply_style_modifiers(question_text, style)
            
            # 生成后续提示
            follow_up_hints = self._generate_follow_up_hints(
                candidates, style, complexity
            )
            
            # 计算生成置信度
            generation_confidence = self._calculate_generation_confidence(
                ambiguity_analysis, context, user_profile, style
            )
            
            # 记录上下文适应
            context_adaptations = self._record_context_adaptations(
                context, user_profile, style
            )
            
            generated_question = GeneratedQuestion(
                question_text=final_question,
                question_type=f"disambiguation_{ambiguity_analysis.primary_type.value}",
                style=style,
                complexity=complexity,
                confidence=generation_confidence,
                explanation=f"基于{ambiguity_analysis.primary_type.value}歧义生成，适应用户{style.value}风格",
                follow_up_hints=follow_up_hints,
                context_adaptations=context_adaptations
            )
            
            # 更新用户画像
            await self._update_user_profile(user_id, generated_question, context)
            
            logger.info(f"生成智能问题: 风格={style.value}, 复杂度={complexity.value}, "
                       f"置信度={generation_confidence:.3f}")
            
            return generated_question
            
        except Exception as e:
            logger.error(f"智能问题生成失败: {str(e)}")
            return await self._generate_fallback_question(candidates)
    
    async def _get_or_create_user_profile(self, user_id: str, 
                                        context: QuestionContext) -> UserProfile:
        """获取或创建用户画像"""
        if user_id not in self.user_profiles:
            # 基于初始上下文推断用户特征
            self.user_profiles[user_id] = UserProfile(
                preferred_style=self._infer_initial_style(context),
                complexity_tolerance=self._infer_complexity_tolerance(context),
                patience_level=self._infer_patience_level(context),
                interaction_history=[],
                success_patterns={},
                response_time_avg=30.0,  # 默认30秒
                language_preference='zh'
            )
        
        return self.user_profiles[user_id]
    
    def _determine_style_and_complexity(self,
                                      user_profile: UserProfile,
                                      context: QuestionContext,
                                      ambiguity_analysis: AmbiguityAnalysis) -> Tuple[QuestionStyle, QuestionComplexity]:
        """确定问题风格和复杂度"""
        try:
            # 基础风格选择
            base_style = user_profile.preferred_style
            
            # 上下文调整
            if context.time_pressure > 0.7:
                # 时间压力大，倾向简洁
                style = QuestionStyle.CONCISE
            elif context.user_engagement < 0.3:
                # 用户参与度低，使用友好风格
                style = QuestionStyle.FRIENDLY
            elif context.turn_count > 5:
                # 对话轮次多，使用详细风格
                style = QuestionStyle.DETAILED
            else:
                style = base_style
            
            # 复杂度选择
            if ambiguity_analysis.ambiguity_score > 0.8:
                # 歧义度高，使用简单问题
                complexity = QuestionComplexity.SIMPLE
            elif user_profile.complexity_tolerance == QuestionComplexity.COMPLEX:
                # 用户能接受复杂问题
                complexity = QuestionComplexity.MODERATE
            else:
                complexity = QuestionComplexity.SIMPLE
            
            # 基于成功模式调整
            if user_profile.success_patterns:
                best_style = max(user_profile.success_patterns.items(), 
                               key=lambda x: x[1])[0]
                if best_style in [s.value for s in QuestionStyle]:
                    style = QuestionStyle(best_style)
            
            return style, complexity
            
        except Exception as e:
            logger.error(f"风格复杂度确定失败: {str(e)}")
            return QuestionStyle.FRIENDLY, QuestionComplexity.SIMPLE
    
    async def _format_candidates(self,
                               candidates: List[Dict],
                               style: QuestionStyle,
                               complexity: QuestionComplexity,
                               context: QuestionContext,
                               user_profile: UserProfile) -> str:
        """格式化候选选项"""
        try:
            formatted_options = []
            
            for i, candidate in enumerate(candidates, 1):
                option_text = f"{i}. "
                
                # 基础选项文本
                display_name = candidate.get('display_name', candidate['intent_name'])
                option_text += display_name
                
                # 根据复杂度添加详细信息
                if complexity in [QuestionComplexity.MODERATE, QuestionComplexity.COMPLEX]:
                    # 添加置信度信息
                    confidence = candidate.get('confidence', 0.0)
                    if style != QuestionStyle.CONCISE:
                        option_text += f" (匹配度: {confidence:.0%})"
                    
                    # 添加功能描述
                    if complexity == QuestionComplexity.COMPLEX:
                        description = self._get_intent_description(candidate['intent_name'])
                        if description:
                            option_text += f"\n   {description}"
                
                # 添加使用场景示例
                if style == QuestionStyle.DETAILED and complexity == QuestionComplexity.COMPLEX:
                    examples = self._get_intent_examples(candidate['intent_name'])
                    if examples:
                        option_text += f"\n   例如：{examples[0]}"
                
                formatted_options.append(option_text)
            
            return "\n".join(formatted_options)
            
        except Exception as e:
            logger.error(f"候选选项格式化失败: {str(e)}")
            return "\n".join([f"{i}. {c.get('display_name', c['intent_name'])}" 
                            for i, c in enumerate(candidates, 1)])
    
    async def _select_template(self,
                             ambiguity_type: AmbiguityType,
                             style: QuestionStyle,
                             context: QuestionContext,
                             user_profile: UserProfile) -> str:
        """选择合适的模板"""
        try:
            templates = self.question_templates.get(
                ambiguity_type.value, {}
            ).get(style.value, [])
            
            if not templates:
                # 回退到友好风格
                templates = self.question_templates.get(
                    ambiguity_type.value, {}
                ).get(QuestionStyle.FRIENDLY.value, [
                    "请从以下选项中选择：\n{options}"
                ])
            
            # 基于历史成功率选择模板
            if user_profile.interaction_history:
                # 简化：选择第一个模板
                return templates[0]
            else:
                # 随机选择以增加多样性
                return random.choice(templates)
                
        except Exception as e:
            logger.error(f"模板选择失败: {str(e)}")
            return "请选择：\n{options}"
    
    async def _apply_context_adaptations(self,
                                       template: str,
                                       context: QuestionContext,
                                       user_profile: UserProfile) -> str:
        """应用上下文适应"""
        try:
            adaptations = []
            
            # 时间压力适应
            if context.time_pressure > 0.7:
                adaptations.extend(self.context_adaptations['high_time_pressure'])
            
            # 用户参与度适应
            if context.user_engagement < 0.3:
                adaptations.extend(self.context_adaptations['low_engagement'])
            
            # 失败历史适应
            if context.turn_count > 3:
                adaptations.extend(self.context_adaptations['multiple_failures'])
            
            # 用户经验适应
            if user_profile.success_patterns and len(user_profile.interaction_history) > 10:
                adaptations.extend(self.context_adaptations['expert_user'])
            elif len(user_profile.interaction_history) < 3:
                adaptations.extend(self.context_adaptations['novice_user'])
            
            # 应用适应
            if adaptations:
                adaptation = random.choice(adaptations)
                return adaptation + template
            
            return template
            
        except Exception as e:
            logger.error(f"上下文适应失败: {str(e)}")
            return template
    
    def _apply_style_modifiers(self, question_text: str, style: QuestionStyle) -> str:
        """应用风格修饰符"""
        try:
            modifiers = self.style_modifiers.get(style.value, {})
            
            prefix = modifiers.get('prefix', '')
            suffix = modifiers.get('suffix', '')
            
            if prefix:
                question_text = prefix + question_text
            if suffix:
                question_text = question_text + suffix
            
            return question_text
            
        except Exception as e:
            logger.error(f"风格修饰失败: {str(e)}")
            return question_text
    
    def _generate_follow_up_hints(self,
                                candidates: List[Dict],
                                style: QuestionStyle,
                                complexity: QuestionComplexity) -> List[str]:
        """生成后续提示"""
        hints = []
        
        try:
            if style != QuestionStyle.CONCISE:
                hints.append("您可以直接回复数字，也可以描述具体需求")
            
            if complexity == QuestionComplexity.COMPLEX:
                hints.append("如需了解更多功能详情，请告诉我")
            
            if len(candidates) > 3:
                hints.append("也可以说'都不是'来描述其他需求")
            
            hints.append("如有疑问，请随时询问")
            
        except Exception as e:
            logger.error(f"后续提示生成失败: {str(e)}")
        
        return hints
    
    def _calculate_generation_confidence(self,
                                       ambiguity_analysis: AmbiguityAnalysis,
                                       context: QuestionContext,
                                       user_profile: UserProfile,
                                       style: QuestionStyle) -> float:
        """计算生成置信度"""
        try:
            base_confidence = 0.7
            
            # 基于歧义分析调整
            if ambiguity_analysis.ambiguity_score < 0.5:
                base_confidence += 0.1
            elif ambiguity_analysis.ambiguity_score > 0.8:
                base_confidence -= 0.1
            
            # 基于用户画像调整
            if len(user_profile.interaction_history) > 5:
                base_confidence += 0.1
            
            # 基于上下文调整
            if context.turn_count < 3:
                base_confidence += 0.05
            
            # 基于风格匹配调整
            if style == user_profile.preferred_style:
                base_confidence += 0.1
            
            return max(0.1, min(0.95, base_confidence))
            
        except Exception as e:
            logger.error(f"生成置信度计算失败: {str(e)}")
            return 0.7
    
    def _record_context_adaptations(self,
                                  context: QuestionContext,
                                  user_profile: UserProfile,
                                  style: QuestionStyle) -> List[str]:
        """记录上下文适应"""
        adaptations = []
        
        try:
            if context.time_pressure > 0.7:
                adaptations.append("时间压力适应")
            
            if context.user_engagement < 0.3:
                adaptations.append("参与度提升")
            
            if style != user_profile.preferred_style:
                adaptations.append(f"风格调整: {user_profile.preferred_style.value} -> {style.value}")
            
        except Exception as e:
            logger.error(f"上下文适应记录失败: {str(e)}")
        
        return adaptations
    
    async def _update_user_profile(self,
                                 user_id: str,
                                 generated_question: GeneratedQuestion,
                                 context: QuestionContext):
        """更新用户画像"""
        try:
            if user_id in self.user_profiles:
                profile = self.user_profiles[user_id]
                
                # 记录交互历史
                interaction = {
                    'timestamp': datetime.now(),
                    'question_style': generated_question.style.value,
                    'complexity': generated_question.complexity.value,
                    'confidence': generated_question.confidence,
                    'context': {
                        'turn_count': context.turn_count,
                        'time_pressure': context.time_pressure,
                        'user_engagement': context.user_engagement
                    }
                }
                
                profile.interaction_history.append(interaction)
                
                # 保留最近50次交互
                if len(profile.interaction_history) > 50:
                    profile.interaction_history = profile.interaction_history[-50:]
                
        except Exception as e:
            logger.error(f"用户画像更新失败: {str(e)}")
    
    def _infer_initial_style(self, context: QuestionContext) -> QuestionStyle:
        """推断初始风格"""
        if context.time_pressure > 0.7:
            return QuestionStyle.CONCISE
        elif context.user_engagement > 0.7:
            return QuestionStyle.FRIENDLY
        else:
            return QuestionStyle.CASUAL
    
    def _infer_complexity_tolerance(self, context: QuestionContext) -> QuestionComplexity:
        """推断复杂度容忍度"""
        if context.turn_count > 3:
            return QuestionComplexity.SIMPLE
        else:
            return QuestionComplexity.MODERATE
    
    def _infer_patience_level(self, context: QuestionContext) -> float:
        """推断耐心水平"""
        base_patience = 0.7
        
        if context.time_pressure > 0.5:
            base_patience -= 0.2
        
        if context.turn_count > 3:
            base_patience -= 0.1
        
        if context.user_engagement > 0.7:
            base_patience += 0.1
        
        return max(0.1, min(1.0, base_patience))
    
    def _get_intent_description(self, intent_name: str) -> Optional[str]:
        """获取意图描述"""
        descriptions = {
            'book_flight': '预订机票服务',
            'check_balance': '查询账户余额',
            'weather_query': '天气查询服务'
        }
        return descriptions.get(intent_name)
    
    def _get_intent_examples(self, intent_name: str) -> List[str]:
        """获取意图示例"""
        examples = {
            'book_flight': ['我要订票', '预订机票', '买飞机票'],
            'check_balance': ['查余额', '我的账户有多少钱', '余额查询'],
            'weather_query': ['今天天气如何', '明天会下雨吗', '查天气']
        }
        return examples.get(intent_name, [])
    
    async def _generate_fallback_question(self, candidates: List[Dict]) -> GeneratedQuestion:
        """生成后备问题"""
        options = "\n".join([f"{i}. {c.get('display_name', c['intent_name'])}" 
                           for i, c in enumerate(candidates, 1)])
        
        return GeneratedQuestion(
            question_text=f"请选择您需要的功能：\n{options}",
            question_type="fallback",
            style=QuestionStyle.FRIENDLY,
            complexity=QuestionComplexity.SIMPLE,
            confidence=0.5,
            explanation="后备问题生成",
            follow_up_hints=["请回复对应的数字"],
            context_adaptations=[]
        )
    
    def get_generator_statistics(self) -> Dict[str, Any]:
        """获取生成器统计信息"""
        try:
            return {
                'user_profiles_count': len(self.user_profiles),
                'template_categories': len(self.question_templates),
                'style_types': len(QuestionStyle),
                'complexity_levels': len(QuestionComplexity),
                'adaptation_strategies': len(self.context_adaptations),
                'success_patterns': self.success_patterns
            }
        except Exception as e:
            logger.error(f"获取生成器统计失败: {str(e)}")
            return {'error': str(e)}