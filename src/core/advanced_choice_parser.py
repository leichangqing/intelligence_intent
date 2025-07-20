"""
高级用户选择解析器
实现自然语言选择解析和智能纠错
"""

from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
from enum import Enum
import re
import logging
from datetime import datetime
from difflib import SequenceMatcher
import jieba
import jieba.posseg as pseg

from ..utils.logger import get_logger

logger = get_logger(__name__)


class ChoiceType(Enum):
    """选择类型"""
    NUMERIC = "numeric"         # 数字选择
    TEXTUAL = "textual"         # 文本选择
    MIXED = "mixed"             # 混合选择
    DESCRIPTIVE = "descriptive"  # 描述性选择
    NEGATIVE = "negative"       # 否定选择
    UNCERTAIN = "uncertain"     # 不确定选择


class ConfidenceLevel(Enum):
    """置信度等级"""
    HIGH = "high"      # 高置信度
    MEDIUM = "medium"  # 中等置信度
    LOW = "low"        # 低置信度
    VERY_LOW = "very_low"  # 很低置信度


@dataclass
class ParseResult:
    """解析结果"""
    choice_type: ChoiceType
    selected_option: Optional[int]
    selected_text: Optional[str]
    confidence: float
    confidence_level: ConfidenceLevel
    alternative_matches: List[Tuple[int, str, float]]
    error_corrections: List[str]
    explanation: str
    raw_input: str
    processing_steps: List[str]


@dataclass
class CorrectionSuggestion:
    """纠错建议"""
    original_text: str
    corrected_text: str
    correction_type: str
    confidence: float
    explanation: str


class AdvancedChoiceParser:
    """高级用户选择解析器"""
    
    def __init__(self):
        # 数字匹配模式
        self.number_patterns = [
            r'^(\d+)$',                    # 纯数字
            r'^第?(\d+)个?',               # 第X个
            r'^选择?(\d+)',                # 选择X
            r'^(\d+)号?',                  # X号
            r'^([一二三四五六七八九十])$',    # 中文数字
            r'我选(\d+)',                  # 我选X
            r'就(\d+)',                    # 就X
            r'要(\d+)',                    # 要X
        ]
        
        # 中文数字映射
        self.chinese_numbers = {
            '一': 1, '二': 2, '三': 3, '四': 4, '五': 5,
            '六': 6, '七': 7, '八': 8, '九': 9, '十': 10
        }
        
        # 否定词汇
        self.negative_words = [
            '都不是', '不是', '没有', '不对', '错了', '不要', '不需要',
            '不符合', '不匹配', '不行', '不可以', '取消', '算了'
        ]
        
        # 不确定词汇
        self.uncertain_words = [
            '不知道', '不确定', '不清楚', '不太明白', '不太懂',
            '看不懂', '不明白', '搞不清', '不太理解', '模糊'
        ]
        
        # 选择指示词
        self.choice_indicators = [
            '选择', '选', '要', '需要', '想要', '是', '就是', '应该是',
            '我觉得是', '我认为是', '我想是', '我要的是', '我需要的是'
        ]
        
        # 常见错误模式
        self.error_patterns = {
            'typo': r'[0-9]+',  # 数字错误
            'space': r'\s+',    # 空格错误
            'punctuation': r'[,.!?；，。！？]',  # 标点错误
        }
        
        # 相似度阈值
        self.similarity_threshold = 0.6
        
        # 历史解析记录
        self.parsing_history: List[Dict] = []
        
        # 用户习惯模式
        self.user_patterns: Dict[str, Dict] = {}
        
        # 上下文感知模式
        self.context_patterns = {
            'sequence_choices': r'第([\u4e00\u4e8c\u4e09\u56db\u4e94\u516d\u4e03\u516b\u4e5d\u5341\d+])个',
            'ordinal_choices': r'([\u4e00\u4e8c\u4e09\u56db\u4e94\u516d\u4e03\u516b\u4e5d\u5341\d+])',
            'preference_indicators': ['喜欢', '偏好', '倾向于', '选择', '更想要'],
            'rejection_indicators': ['不喜欢', '不要', '不选', '除了', '不是']
        }
        
        # 增强的语义匹配模式
        self.semantic_patterns = {
            'booking_related': ['预订', '订', '预定', '安排', '预约'],
            'query_related': ['查询', '查看', '询问', '了解', '获取'],
            'modification_related': ['修改', '更改', '变更', '调整', '换'],
            'cancellation_related': ['取消', '撤销', '退订', '删除']
        }
        
        # 自适应阈值
        self.adaptive_thresholds = {
            'base_similarity': 0.6,
            'contextual_boost': 0.1,
            'user_pattern_boost': 0.05,
            'semantic_boost': 0.15
        }
    
    async def parse_user_choice(self, 
                              user_input: str,
                              candidates: List[Dict],
                              user_id: Optional[str] = None,
                              context: Optional[Dict] = None) -> ParseResult:
        """
        解析用户选择
        
        Args:
            user_input: 用户输入
            candidates: 候选选项
            user_id: 用户ID
            context: 上下文信息
            
        Returns:
            ParseResult: 解析结果
        """
        try:
            processing_steps = []
            user_input = user_input.strip()
            
            # 预处理用户输入
            cleaned_input = self._preprocess_input(user_input)
            processing_steps.append(f"预处理: '{user_input}' -> '{cleaned_input}'")
            
            # 检查是否为否定回答
            if self._is_negative_response(cleaned_input):
                processing_steps.append("检测到否定回答")
                return ParseResult(
                    choice_type=ChoiceType.NEGATIVE,
                    selected_option=None,
                    selected_text=None,
                    confidence=0.9,
                    confidence_level=ConfidenceLevel.HIGH,
                    alternative_matches=[],
                    error_corrections=[],
                    explanation="用户表示所有选项都不符合需求",
                    raw_input=user_input,
                    processing_steps=processing_steps
                )
            
            # 检查是否为不确定回答
            if self._is_uncertain_response(cleaned_input):
                processing_steps.append("检测到不确定回答")
                return ParseResult(
                    choice_type=ChoiceType.UNCERTAIN,
                    selected_option=None,
                    selected_text=None,
                    confidence=0.8,
                    confidence_level=ConfidenceLevel.HIGH,
                    alternative_matches=[],
                    error_corrections=[],
                    explanation="用户表示不确定或需要更多信息",
                    raw_input=user_input,
                    processing_steps=processing_steps
                )
            
            # 尝试数字选择解析
            numeric_result = await self._parse_numeric_choice(cleaned_input, candidates)
            if numeric_result:
                processing_steps.append(f"数字解析成功: 选项 {numeric_result[0]}")
                return ParseResult(
                    choice_type=ChoiceType.NUMERIC,
                    selected_option=numeric_result[0],
                    selected_text=numeric_result[1],
                    confidence=numeric_result[2],
                    confidence_level=self._get_confidence_level(numeric_result[2]),
                    alternative_matches=[],
                    error_corrections=[],
                    explanation=f"解析为数字选择: {numeric_result[0]}",
                    raw_input=user_input,
                    processing_steps=processing_steps
                )
            
            # 尝试文本匹配解析
            text_result = await self._parse_text_choice(cleaned_input, candidates)
            if text_result:
                processing_steps.append(f"文本匹配成功: {text_result[1]}")
                return ParseResult(
                    choice_type=ChoiceType.TEXTUAL,
                    selected_option=text_result[0],
                    selected_text=text_result[1],
                    confidence=text_result[2],
                    confidence_level=self._get_confidence_level(text_result[2]),
                    alternative_matches=text_result[3] if len(text_result) > 3 else [],
                    error_corrections=[],
                    explanation=f"文本匹配: {text_result[1]}",
                    raw_input=user_input,
                    processing_steps=processing_steps
                )
            
            # 尝试上下文感知解析
            context_result = await self._parse_with_context(cleaned_input, candidates, context)
            if context_result:
                processing_steps.append(f"上下文解析成功: {context_result[1]}")
                return ParseResult(
                    choice_type=ChoiceType.MIXED,
                    selected_option=context_result[0],
                    selected_text=context_result[1],
                    confidence=context_result[2],
                    confidence_level=self._get_confidence_level(context_result[2]),
                    alternative_matches=context_result[3] if len(context_result) > 3 else [],
                    error_corrections=[],
                    explanation=f"上下文感知匹配: {context_result[1]}",
                    raw_input=user_input,
                    processing_steps=processing_steps
                )
            
            # 尝试用户模式匹配
            pattern_result = await self._parse_with_user_patterns(cleaned_input, candidates, user_id)
            if pattern_result:
                processing_steps.append(f"用户模式匹配成功: {pattern_result[1]}")
                return ParseResult(
                    choice_type=ChoiceType.MIXED,
                    selected_option=pattern_result[0],
                    selected_text=pattern_result[1],
                    confidence=pattern_result[2],
                    confidence_level=self._get_confidence_level(pattern_result[2]),
                    alternative_matches=[],
                    error_corrections=[],
                    explanation=f"用户模式匹配: {pattern_result[1]}",
                    raw_input=user_input,
                    processing_steps=processing_steps
                )
            
            # 尝试智能纠错
            corrected_result = await self._parse_with_correction(cleaned_input, candidates)
            if corrected_result:
                processing_steps.append(f"智能纠错成功: {corrected_result[1]}")
                return ParseResult(
                    choice_type=ChoiceType.MIXED,
                    selected_option=corrected_result[0],
                    selected_text=corrected_result[1],
                    confidence=corrected_result[2],
                    confidence_level=self._get_confidence_level(corrected_result[2]),
                    alternative_matches=corrected_result[4] if len(corrected_result) > 4 else [],
                    error_corrections=corrected_result[3] if len(corrected_result) > 3 else [],
                    explanation=f"智能纠错匹配: {corrected_result[1]}",
                    raw_input=user_input,
                    processing_steps=processing_steps
                )
            
            # 尝试描述性解析
            descriptive_result = await self._parse_descriptive_choice(cleaned_input, candidates)
            if descriptive_result:
                processing_steps.append(f"描述性解析成功: {descriptive_result[1]}")
                return ParseResult(
                    choice_type=ChoiceType.DESCRIPTIVE,
                    selected_option=descriptive_result[0],
                    selected_text=descriptive_result[1],
                    confidence=descriptive_result[2],
                    confidence_level=self._get_confidence_level(descriptive_result[2]),
                    alternative_matches=descriptive_result[3] if len(descriptive_result) > 3 else [],
                    error_corrections=[],
                    explanation=f"描述性匹配: {descriptive_result[1]}",
                    raw_input=user_input,
                    processing_steps=processing_steps
                )
            
            # 解析失败，返回低置信度结果
            processing_steps.append("所有解析方法都失败")
            return ParseResult(
                choice_type=ChoiceType.UNCERTAIN,
                selected_option=None,
                selected_text=None,
                confidence=0.1,
                confidence_level=ConfidenceLevel.VERY_LOW,
                alternative_matches=[],
                error_corrections=self._generate_correction_suggestions(user_input, candidates),
                explanation="无法解析用户选择，建议用户重新输入",
                raw_input=user_input,
                processing_steps=processing_steps
            )
            
        except Exception as e:
            logger.error(f"用户选择解析失败: {str(e)}")
            return ParseResult(
                choice_type=ChoiceType.UNCERTAIN,
                selected_option=None,
                selected_text=None,
                confidence=0.0,
                confidence_level=ConfidenceLevel.VERY_LOW,
                alternative_matches=[],
                error_corrections=[],
                explanation=f"解析过程中发生错误: {str(e)}",
                raw_input=user_input,
                processing_steps=["解析过程中发生错误"]
            )
    
    def _preprocess_input(self, user_input: str) -> str:
        """预处理用户输入"""
        try:
            # 去除多余的空格
            cleaned = re.sub(r'\s+', ' ', user_input.strip())
            
            # 去除常见的无关词汇
            cleaned = re.sub(r'^(额|呃|嗯|那|这|就|我|要|选|的|是)+', '', cleaned)
            
            # 标准化标点符号
            cleaned = re.sub(r'[,.!?；，。！？]+', '', cleaned)
            
            # 转换为小写（对于英文）
            cleaned = cleaned.lower()
            
            return cleaned
            
        except Exception as e:
            logger.error(f"输入预处理失败: {str(e)}")
            return user_input
    
    def _is_negative_response(self, user_input: str) -> bool:
        """检查是否为否定回答"""
        for negative_word in self.negative_words:
            if negative_word in user_input:
                return True
        return False
    
    def _is_uncertain_response(self, user_input: str) -> bool:
        """检查是否为不确定回答"""
        for uncertain_word in self.uncertain_words:
            if uncertain_word in user_input:
                return True
        return False
    
    async def _parse_numeric_choice(self, user_input: str, candidates: List[Dict]) -> Optional[Tuple[int, str, float]]:
        """解析数字选择"""
        try:
            # 尝试各种数字模式
            for pattern in self.number_patterns:
                match = re.search(pattern, user_input)
                if match:
                    number_str = match.group(1)
                    
                    # 转换中文数字
                    if number_str in self.chinese_numbers:
                        number = self.chinese_numbers[number_str]
                    else:
                        try:
                            number = int(number_str)
                        except ValueError:
                            continue
                    
                    # 检查数字是否在有效范围内
                    if 1 <= number <= len(candidates):
                        selected_candidate = candidates[number - 1]
                        return (
                            number,
                            selected_candidate.get('display_name', selected_candidate['intent_name']),
                            0.9  # 高置信度
                        )
            
            return None
            
        except Exception as e:
            logger.error(f"数字选择解析失败: {str(e)}")
            return None
    
    async def _parse_text_choice(self, user_input: str, candidates: List[Dict]) -> Optional[Tuple[int, str, float, List[Tuple[int, str, float]]]]:
        """解析文本选择"""
        try:
            matches = []
            
            # 对每个候选进行匹配
            for i, candidate in enumerate(candidates):
                display_name = candidate.get('display_name', candidate['intent_name'])
                intent_name = candidate['intent_name']
                
                # 直接匹配
                if display_name.lower() in user_input or intent_name.lower() in user_input:
                    matches.append((i + 1, display_name, 0.9))
                    continue
                
                # 部分匹配
                for word in jieba.cut(user_input):
                    if len(word) > 1 and (word in display_name or word in intent_name):
                        similarity = self._calculate_similarity(word, display_name)
                        if similarity > self.similarity_threshold:
                            matches.append((i + 1, display_name, similarity))
                            break
                
                # 语义相似度匹配
                similarity = self._calculate_semantic_similarity(user_input, display_name)
                if similarity > self.similarity_threshold:
                    matches.append((i + 1, display_name, similarity))
            
            # 按置信度排序
            matches.sort(key=lambda x: x[2], reverse=True)
            
            if matches:
                best_match = matches[0]
                alternatives = matches[1:3]  # 最多3个备选
                return (best_match[0], best_match[1], best_match[2], alternatives)
            
            return None
            
        except Exception as e:
            logger.error(f"文本选择解析失败: {str(e)}")
            return None
    
    async def _parse_with_correction(self, user_input: str, candidates: List[Dict]) -> Optional[Tuple[int, str, float, List[str], List[Tuple[int, str, float]]]]:
        """带纠错的解析"""
        try:
            corrections = []
            
            # 尝试常见错误纠正
            corrected_input = self._correct_common_errors(user_input)
            if corrected_input != user_input:
                corrections.append(f"纠正: '{user_input}' -> '{corrected_input}'")
                
                # 用纠正后的输入重新解析
                numeric_result = await self._parse_numeric_choice(corrected_input, candidates)
                if numeric_result:
                    return (numeric_result[0], numeric_result[1], numeric_result[2] * 0.8, corrections, [])
                
                text_result = await self._parse_text_choice(corrected_input, candidates)
                if text_result:
                    return (text_result[0], text_result[1], text_result[2] * 0.8, corrections, text_result[3])
            
            # 尝试拼写纠错
            for i, candidate in enumerate(candidates):
                display_name = candidate.get('display_name', candidate['intent_name'])
                
                # 检查是否为拼写错误
                if self._is_likely_typo(user_input, display_name):
                    corrections.append(f"拼写纠正: '{user_input}' 可能是 '{display_name}'")
                    return (i + 1, display_name, 0.7, corrections, [])
            
            return None
            
        except Exception as e:
            logger.error(f"纠错解析失败: {str(e)}")
            return None
    
    async def _parse_descriptive_choice(self, user_input: str, candidates: List[Dict]) -> Optional[Tuple[int, str, float, List[Tuple[int, str, float]]]]:
        """描述性选择解析"""
        try:
            # 使用jieba进行分词和词性标注
            words = pseg.cut(user_input)
            key_words = [word for word, flag in words if flag.startswith('n') or flag.startswith('v')]
            
            if not key_words:
                return None
            
            matches = []
            
            # 对每个候选进行语义匹配
            for i, candidate in enumerate(candidates):
                display_name = candidate.get('display_name', candidate['intent_name'])
                intent_name = candidate['intent_name']
                
                # 计算关键词匹配度
                keyword_score = self._calculate_keyword_match(key_words, display_name + " " + intent_name)
                
                # 计算整体语义相似度
                semantic_score = self._calculate_semantic_similarity(user_input, display_name)
                
                # 综合得分
                combined_score = (keyword_score * 0.6 + semantic_score * 0.4)
                
                if combined_score > 0.4:  # 降低阈值以捕获更多可能性
                    matches.append((i + 1, display_name, combined_score))
            
            # 按得分排序
            matches.sort(key=lambda x: x[2], reverse=True)
            
            if matches:
                best_match = matches[0]
                alternatives = matches[1:3]
                return (best_match[0], best_match[1], best_match[2], alternatives)
            
            return None
            
        except Exception as e:
            logger.error(f"描述性选择解析失败: {str(e)}")
            return None
    
    def _correct_common_errors(self, user_input: str) -> str:
        """纠正常见错误"""
        try:
            corrected = user_input
            
            # 纠正数字拼写错误
            number_corrections = {
                'l': '1', 'I': '1', 'o': '0', 'O': '0',
                '２': '2', '３': '3', '４': '4', '５': '5'
            }
            
            for wrong, correct in number_corrections.items():
                corrected = corrected.replace(wrong, correct)
            
            # 去除多余的空格和标点
            corrected = re.sub(r'\s+', '', corrected)
            corrected = re.sub(r'[^\w\u4e00-\u9fff]', '', corrected)
            
            return corrected
            
        except Exception as e:
            logger.error(f"常见错误纠正失败: {str(e)}")
            return user_input
    
    def _is_likely_typo(self, user_input: str, reference: str) -> bool:
        """判断是否为拼写错误"""
        try:
            # 长度差异不能太大
            if abs(len(user_input) - len(reference)) > 3:
                return False
            
            # 计算相似度
            similarity = SequenceMatcher(None, user_input, reference).ratio()
            
            # 相似度阈值
            return similarity > 0.7
            
        except Exception as e:
            logger.error(f"拼写错误检查失败: {str(e)}")
            return False
    
    def _calculate_similarity(self, text1: str, text2: str) -> float:
        """计算文本相似度"""
        try:
            return SequenceMatcher(None, text1.lower(), text2.lower()).ratio()
        except Exception:
            return 0.0
    
    def _calculate_semantic_similarity(self, text1: str, text2: str) -> float:
        """计算语义相似度（增强版）"""
        try:
            # 分词
            words1 = set(jieba.cut(text1))
            words2 = set(jieba.cut(text2))
            
            if not words1 or not words2:
                return 0.0
            
            # 基础Jaccard相似度
            intersection = words1.intersection(words2)
            union = words1.union(words2)
            jaccard_similarity = len(intersection) / len(union) if union else 0.0
            
            # 语义模式匹配加成
            semantic_boost = 0.0
            for category, keywords in self.semantic_patterns.items():
                text1_has_semantic = any(keyword in text1 for keyword in keywords)
                text2_has_semantic = any(keyword in text2 for keyword in keywords)
                
                if text1_has_semantic and text2_has_semantic:
                    semantic_boost += self.adaptive_thresholds['semantic_boost']
                    break
            
            # 组合得分
            final_similarity = min(1.0, jaccard_similarity + semantic_boost)
            
            return final_similarity
            
        except Exception as e:
            logger.error(f"语义相似度计算失败: {str(e)}")
            return 0.0
    
    def _calculate_keyword_match(self, keywords: List[str], text: str) -> float:
        """计算关键词匹配度"""
        try:
            if not keywords:
                return 0.0
            
            matches = 0
            for keyword in keywords:
                if keyword in text:
                    matches += 1
            
            return matches / len(keywords)
            
        except Exception as e:
            logger.error(f"关键词匹配度计算失败: {str(e)}")
            return 0.0
    
    def _get_confidence_level(self, confidence: float) -> ConfidenceLevel:
        """获取置信度等级"""
        if confidence >= 0.8:
            return ConfidenceLevel.HIGH
        elif confidence >= 0.6:
            return ConfidenceLevel.MEDIUM
        elif confidence >= 0.4:
            return ConfidenceLevel.LOW
        else:
            return ConfidenceLevel.VERY_LOW
    
    def _generate_correction_suggestions(self, user_input: str, candidates: List[Dict]) -> List[str]:
        """生成纠错建议"""
        suggestions = []
        
        try:
            # 建议使用数字选择
            if len(candidates) <= 10:
                suggestions.append("请直接输入数字选择，如：1、2、3")
            
            # 建议使用关键词
            if len(user_input) < 2:
                suggestions.append("请输入更多关键词来描述您的需求")
            
            # 建议从候选中选择
            if len(candidates) > 0:
                candidate_names = [c.get('display_name', c['intent_name']) for c in candidates[:3]]
                suggestions.append(f"您可以选择：{', '.join(candidate_names)}")
            
            # 建议重新描述
            suggestions.append("请重新描述您的需求，我会帮您匹配最合适的选项")
            
        except Exception as e:
            logger.error(f"纠错建议生成失败: {str(e)}")
        
        return suggestions
    
    def update_user_pattern(self, user_id: str, parse_result: ParseResult, success: bool):
        """更新用户习惯模式"""
        try:
            if user_id not in self.user_patterns:
                self.user_patterns[user_id] = {
                    'preferred_choice_type': {},
                    'successful_patterns': [],
                    'failed_patterns': [],
                    'total_interactions': 0
                }
            
            pattern = self.user_patterns[user_id]
            pattern['total_interactions'] += 1
            
            # 更新选择类型偏好
            choice_type = parse_result.choice_type.value
            if choice_type not in pattern['preferred_choice_type']:
                pattern['preferred_choice_type'][choice_type] = 0
            
            if success:
                pattern['preferred_choice_type'][choice_type] += 1
                pattern['successful_patterns'].append({
                    'input': parse_result.raw_input,
                    'choice_type': choice_type,
                    'confidence': parse_result.confidence
                })
            else:
                pattern['failed_patterns'].append({
                    'input': parse_result.raw_input,
                    'choice_type': choice_type,
                    'confidence': parse_result.confidence
                })
            
            # 保持历史记录不过长
            if len(pattern['successful_patterns']) > 20:
                pattern['successful_patterns'] = pattern['successful_patterns'][-20:]
            if len(pattern['failed_patterns']) > 10:
                pattern['failed_patterns'] = pattern['failed_patterns'][-10:]
            
        except Exception as e:
            logger.error(f"用户模式更新失败: {str(e)}")
    
    def get_parser_statistics(self) -> Dict[str, Any]:
        """获取解析器统计信息"""
        try:
            return {
                'total_patterns': len(self.user_patterns),
                'number_patterns_count': len(self.number_patterns),
                'negative_words_count': len(self.negative_words),
                'uncertain_words_count': len(self.uncertain_words),
                'choice_indicators_count': len(self.choice_indicators),
                'parsing_history_count': len(self.parsing_history),
                'similarity_threshold': self.similarity_threshold,
                'user_patterns_summary': {
                    user_id: {
                        'total_interactions': pattern['total_interactions'],
                        'preferred_types': pattern['preferred_choice_type']
                    }
                    for user_id, pattern in self.user_patterns.items()
                }
            }
        except Exception as e:
            logger.error(f"获取解析器统计失败: {str(e)}")
            return {'error': str(e)}
    
    async def _parse_with_context(self, user_input: str, candidates: List[Dict], context: Optional[Dict] = None) -> Optional[Tuple[int, str, float, List[Tuple[int, str, float]]]]:
        """
        基于上下文的解析（TASK-024增强功能）
        
        Args:
            user_input: 用户输入
            candidates: 候选选项
            context: 上下文信息
            
        Returns:
            Optional[Tuple]: (选项索引, 选项文本, 置信度, 备选项)
        """
        try:
            if not context:
                return None
            
            matches = []
            
            # 序列选择模式匹配
            sequence_match = re.search(self.context_patterns['sequence_choices'], user_input)
            if sequence_match:
                number_str = sequence_match.group(1)
                if number_str in self.chinese_numbers:
                    number = self.chinese_numbers[number_str]
                else:
                    try:
                        number = int(number_str)
                    except ValueError:
                        number = None
                
                if number and 1 <= number <= len(candidates):
                    candidate = candidates[number - 1]
                    return (number, candidate.get('display_name', candidate['intent_name']), 0.9, [])
            
            # 基于对话历史的上下文匹配
            conversation_history = context.get('conversation_history', [])
            if conversation_history:
                recent_intents = [turn.get('intent') for turn in conversation_history[-3:] if turn.get('intent')]
                
                # 检查是否有相关的历史意图
                for i, candidate in enumerate(candidates):
                    intent_name = candidate['intent_name']
                    if intent_name in recent_intents:
                        matches.append((i + 1, candidate.get('display_name', intent_name), 0.7))
            
            # 基于用户偏好的匹配
            user_preferences = context.get('user_preferences', {})
            if user_preferences:
                for i, candidate in enumerate(candidates):
                    intent_name = candidate['intent_name']
                    # 检查用户偏好
                    if user_preferences.get(f"preferred_{intent_name}", False):
                        matches.append((i + 1, candidate.get('display_name', intent_name), 0.8))
            
            # 基于当前会话状态的匹配
            current_intent = context.get('current_intent')
            if current_intent:
                # 查找相关或延续的意图
                for i, candidate in enumerate(candidates):
                    intent_name = candidate['intent_name']
                    # 简单的意图关联逻辑
                    if self._are_intents_related(current_intent, intent_name):
                        matches.append((i + 1, candidate.get('display_name', intent_name), 0.6))
            
            # 按置信度排序并返回最佳匹配
            if matches:
                matches.sort(key=lambda x: x[2], reverse=True)
                best_match = matches[0]
                alternatives = matches[1:3]
                return (best_match[0], best_match[1], best_match[2], alternatives)
            
            return None
            
        except Exception as e:
            logger.error(f"上下文解析失败: {str(e)}")
            return None
    
    async def _parse_with_user_patterns(self, user_input: str, candidates: List[Dict], user_id: Optional[str] = None) -> Optional[Tuple[int, str, float]]:
        """
        基于用户习惯模式的解析（TASK-024增强功能）
        
        Args:
            user_input: 用户输入
            candidates: 候选选项
            user_id: 用户ID
            
        Returns:
            Optional[Tuple]: (选项索引, 选项文本, 置信度)
        """
        try:
            if not user_id or user_id not in self.user_patterns:
                return None
            
            user_pattern = self.user_patterns[user_id]
            
            # 检查用户历史成功模式
            successful_patterns = user_pattern.get('successful_patterns', [])
            for pattern in successful_patterns[-10:]:  # 检查最近10个成功模式
                pattern_input = pattern['input'].lower()
                current_input = user_input.lower()
                
                # 计算输入相似度
                similarity = self._calculate_similarity(pattern_input, current_input)
                if similarity > 0.7:  # 高相似度阈值
                    # 尝试找到对应的候选项
                    for i, candidate in enumerate(candidates):
                        intent_name = candidate['intent_name']
                        display_name = candidate.get('display_name', intent_name)
                        
                        # 如果历史模式成功选择了类似的选项
                        if intent_name in pattern_input or display_name.lower() in pattern_input:
                            confidence = similarity * 0.8  # 基于相似度的置信度
                            return (i + 1, display_name, confidence)
            
            # 检查用户偏好的选择类型
            preferred_types = user_pattern.get('preferred_choice_type', {})
            if preferred_types:
                # 根据用户偏好调整解析策略
                most_preferred = max(preferred_types.items(), key=lambda x: x[1])
                preferred_type = most_preferred[0]
                
                # 如果用户偏好数字选择，优先尝试数字解析
                if preferred_type == 'numeric':
                    numeric_result = await self._parse_numeric_choice(user_input, candidates)
                    if numeric_result:
                        return numeric_result
                
                # 如果用户偏好文本选择，优先尝试文本解析
                elif preferred_type == 'textual':
                    text_result = await self._parse_text_choice(user_input, candidates)
                    if text_result:
                        return (text_result[0], text_result[1], text_result[2])
            
            return None
            
        except Exception as e:
            logger.error(f"用户模式解析失败: {str(e)}")
            return None
    
    def _are_intents_related(self, intent1: str, intent2: str) -> bool:
        """
        检查两个意图是否相关（TASK-024增强功能）
        
        Args:
            intent1: 第一个意图
            intent2: 第二个意图
            
        Returns:
            bool: 是否相关
        """
        try:
            # 简单的意图关联逻辑
            related_groups = [
                {'book_flight', 'check_flight_status', 'cancel_flight'},
                {'check_balance', 'transfer_money', 'pay_bill'},
                {'book_hotel', 'check_hotel', 'cancel_hotel'}
            ]
            
            for group in related_groups:
                if intent1 in group and intent2 in group:
                    return True
            
            # 检查意图名称相似性
            similarity = self._calculate_similarity(intent1, intent2)
            return similarity > 0.4
            
        except Exception:
            return False
    
    async def parse_multi_choice(self, user_input: str, candidates: List[Dict], allow_multiple: bool = False) -> List[ParseResult]:
        """
        多选择解析（TASK-024新增功能）
        
        Args:
            user_input: 用户输入
            candidates: 候选选项
            allow_multiple: 是否允许多选
            
        Returns:
            List[ParseResult]: 解析结果列表
        """
        try:
            results = []
            
            if not allow_multiple:
                # 单选模式，返回单个结果
                result = await self.parse_user_choice(user_input, candidates)
                return [result]
            
            # 多选模式
            # 检查是否包含多选指示词
            multi_indicators = ['和', '还有', '以及', '也要', '都要', '全部']
            has_multi_indicator = any(indicator in user_input for indicator in multi_indicators)
            
            if not has_multi_indicator:
                # 没有多选指示词，按单选处理
                result = await self.parse_user_choice(user_input, candidates)
                return [result]
            
            # 解析多个选择
            # 分割用户输入
            separators = ['和', '还有', '以及', '、', ',', '，']
            parts = [user_input]
            
            for sep in separators:
                new_parts = []
                for part in parts:
                    new_parts.extend(part.split(sep))
                parts = new_parts
            
            # 清理并解析每个部分
            for part in parts:
                part = part.strip()
                if len(part) > 0:
                    result = await self.parse_user_choice(part, candidates)
                    if result.selected_option:
                        results.append(result)
            
            # 如果没有解析到多个结果，回退到单选
            if len(results) <= 1:
                result = await self.parse_user_choice(user_input, candidates)
                return [result]
            
            return results
            
        except Exception as e:
            logger.error(f"多选择解析失败: {str(e)}")
            # 返回单选结果作为后备
            result = await self.parse_user_choice(user_input, candidates)
            return [result]
    
    async def parse_with_feedback(self, user_input: str, candidates: List[Dict], 
                                previous_result: Optional[ParseResult] = None,
                                user_feedback: Optional[str] = None) -> ParseResult:
        """
        基于反馈的解析（TASK-024新增功能）
        
        Args:
            user_input: 用户输入
            candidates: 候选选项
            previous_result: 之前的解析结果
            user_feedback: 用户反馈
            
        Returns:
            ParseResult: 新的解析结果
        """
        try:
            # 如果有用户反馈，根据反馈调整
            if user_feedback and previous_result:
                feedback_lower = user_feedback.lower()
                
                # 正面反馈
                if any(word in feedback_lower for word in ['对', '是的', '正确', '对的', '没错']):
                    # 确认之前的选择是正确的，增加置信度
                    previous_result.confidence = min(0.95, previous_result.confidence + 0.1)
                    previous_result.confidence_level = self._get_confidence_level(previous_result.confidence)
                    previous_result.explanation += " (用户确认正确)"
                    return previous_result
                
                # 负面反馈
                elif any(word in feedback_lower for word in ['不对', '错了', '不是', '不对的']):
                    # 之前的选择错误，需要重新解析
                    # 排除之前选择的选项
                    filtered_candidates = []
                    for i, candidate in enumerate(candidates):
                        if i + 1 != previous_result.selected_option:
                            filtered_candidates.append(candidate)
                    
                    if filtered_candidates:
                        # 用排除后的候选项重新解析
                        result = await self.parse_user_choice(user_input, filtered_candidates)
                        result.explanation += " (基于用户反馈排除之前选项)"
                        return result
            
            # 正常解析
            return await self.parse_user_choice(user_input, candidates)
            
        except Exception as e:
            logger.error(f"反馈解析失败: {str(e)}")
            return await self.parse_user_choice(user_input, candidates)
    
    def get_parsing_analytics(self, user_id: Optional[str] = None) -> Dict[str, Any]:
        """
        获取解析分析报告（TASK-024新增功能）
        
        Args:
            user_id: 用户ID（可选）
            
        Returns:
            Dict[str, Any]: 分析报告
        """
        try:
            total_parses = len(self.parsing_history)
            if total_parses == 0:
                return {'total_parses': 0, 'message': '暂无解析历史'}
            
            # 过滤用户特定的历史记录
            history = self.parsing_history
            if user_id:
                history = [h for h in self.parsing_history if h.get('user_id') == user_id]
            
            if not history:
                return {'user_id': user_id, 'total_parses': 0, 'message': '该用户暂无解析历史'}
            
            # 统计分析
            success_count = sum(1 for h in history if h['result'].selected_option is not None)
            success_rate = success_count / len(history) if history else 0
            
            # 选择类型分布
            choice_types = {}
            confidence_levels = {}
            
            for h in history:
                result = h['result']
                choice_type = result.choice_type.value
                confidence_level = result.confidence_level.value
                
                choice_types[choice_type] = choice_types.get(choice_type, 0) + 1
                confidence_levels[confidence_level] = confidence_levels.get(confidence_level, 0) + 1
            
            # 平均置信度
            avg_confidence = sum(h['result'].confidence for h in history) / len(history)
            
            # 最近的解析趋势
            recent_history = history[-10:] if len(history) >= 10 else history
            recent_success_rate = sum(1 for h in recent_history if h['result'].selected_option is not None) / len(recent_history)
            
            analytics = {
                'user_id': user_id,
                'total_parses': len(history),
                'success_rate': round(success_rate, 3),
                'recent_success_rate': round(recent_success_rate, 3),
                'avg_confidence': round(avg_confidence, 3),
                'choice_type_distribution': choice_types,
                'confidence_level_distribution': confidence_levels,
                'trend': 'improving' if recent_success_rate > success_rate else 'declining' if recent_success_rate < success_rate else 'stable'
            }
            
            return analytics
            
        except Exception as e:
            logger.error(f"解析分析失败: {str(e)}")
            return {'error': str(e)}