"""
增强的歧义检测引擎
实现多维度歧义检测：语义相似性、上下文感知、领域知识
"""

from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
from enum import Enum
import logging
import math
import re
from datetime import datetime, timedelta
from collections import defaultdict

from ..models.intent import Intent
from ..models.conversation import Conversation
from ..config.settings import Settings
from ..utils.logger import get_logger

logger = get_logger(__name__)


class AmbiguityType(Enum):
    """歧义类型"""
    SEMANTIC = "semantic"           # 语义歧义
    CONTEXTUAL = "contextual"       # 上下文歧义
    CONFIDENCE = "confidence"       # 置信度歧义
    DOMAIN = "domain"              # 领域歧义
    STRUCTURAL = "structural"       # 结构化歧义
    TEMPORAL = "temporal"          # 时间相关歧义


class AmbiguityLevel(Enum):
    """歧义严重程度"""
    LOW = "low"                    # 轻微歧义
    MEDIUM = "medium"              # 中等歧义
    HIGH = "high"                  # 严重歧义
    CRITICAL = "critical"          # 关键歧义


@dataclass
class AmbiguitySignal:
    """歧义信号"""
    type: AmbiguityType
    level: AmbiguityLevel
    score: float                   # 歧义得分 (0.0-1.0)
    evidence: Dict[str, Any]       # 证据信息
    explanation: str               # 解释说明
    confidence: float              # 信号置信度


@dataclass
class AmbiguityAnalysis:
    """歧义分析结果"""
    is_ambiguous: bool
    ambiguity_score: float         # 综合歧义得分
    primary_type: AmbiguityType    # 主要歧义类型
    signals: List[AmbiguitySignal] # 歧义信号列表
    candidates: List[Dict]         # 候选意图
    recommended_action: str        # 推荐行动
    analysis_metadata: Dict[str, Any]


class EnhancedAmbiguityDetector:
    """增强的歧义检测器"""
    
    def __init__(self, settings: Settings):
        self.settings = settings
        self.intent_similarities = {}  # 意图相似度缓存
        self.context_patterns = {}     # 上下文模式缓存
        self.domain_hierarchy = {}     # 领域层次结构
        self.user_preferences = {}     # 用户偏好缓存
        
        # 配置各种阈值
        self.thresholds = {
            'semantic_similarity': 0.8,    # 语义相似性阈值
            'confidence_gap': 0.15,        # 置信度差异阈值
            'context_relevance': 0.6,      # 上下文相关性阈值
            'domain_overlap': 0.7,         # 领域重叠阈值
            'temporal_window': 300,        # 时间窗口（秒）
        }
        
        # 权重配置
        self.weights = {
            AmbiguityType.SEMANTIC: 0.3,
            AmbiguityType.CONTEXTUAL: 0.25,
            AmbiguityType.CONFIDENCE: 0.2,
            AmbiguityType.DOMAIN: 0.15,
            AmbiguityType.STRUCTURAL: 0.1,
        }
    
    async def detect_ambiguity(self, 
                             candidates: List[Dict],
                             user_input: str,
                             conversation_context: Optional[Dict] = None) -> AmbiguityAnalysis:
        """
        综合歧义检测
        
        Args:
            candidates: 候选意图列表
            user_input: 用户输入
            conversation_context: 对话上下文
            
        Returns:
            AmbiguityAnalysis: 歧义分析结果
        """
        try:
            if not candidates or len(candidates) < 2:
                return AmbiguityAnalysis(
                    is_ambiguous=False,
                    ambiguity_score=0.0,
                    primary_type=AmbiguityType.CONFIDENCE,
                    signals=[],
                    candidates=candidates,
                    recommended_action="proceed",
                    analysis_metadata={"reason": "insufficient_candidates"}
                )
            
            # 收集所有歧义信号
            signals = []
            
            # 1. 语义相似性检测
            semantic_signals = await self._detect_semantic_ambiguity(candidates, user_input)
            signals.extend(semantic_signals)
            
            # 2. 置信度歧义检测
            confidence_signals = await self._detect_confidence_ambiguity(candidates)
            signals.extend(confidence_signals)
            
            # 3. 上下文歧义检测
            if conversation_context:
                context_signals = await self._detect_contextual_ambiguity(
                    candidates, user_input, conversation_context
                )
                signals.extend(context_signals)
            
            # 4. 领域歧义检测
            domain_signals = await self._detect_domain_ambiguity(candidates)
            signals.extend(domain_signals)
            
            # 5. 结构化歧义检测
            structural_signals = await self._detect_structural_ambiguity(candidates)
            signals.extend(structural_signals)
            
            # 6. 时间相关歧义检测
            temporal_signals = await self._detect_temporal_ambiguity(
                candidates, conversation_context
            )
            signals.extend(temporal_signals)
            
            # 综合分析
            analysis = await self._synthesize_analysis(signals, candidates, user_input)
            
            logger.info(f"歧义检测完成: 综合得分={analysis.ambiguity_score:.3f}, "
                       f"主要类型={analysis.primary_type.value}, 信号数={len(signals)}")
            
            return analysis
            
        except Exception as e:
            logger.error(f"歧义检测失败: {str(e)}")
            return AmbiguityAnalysis(
                is_ambiguous=False,
                ambiguity_score=0.0,
                primary_type=AmbiguityType.CONFIDENCE,
                signals=[],
                candidates=candidates,
                recommended_action="proceed",
                analysis_metadata={"error": str(e)}
            )
    
    async def _detect_semantic_ambiguity(self, candidates: List[Dict], user_input: str) -> List[AmbiguitySignal]:
        """检测语义歧义"""
        signals = []
        
        try:
            # 计算候选意图间的语义相似度
            for i, candidate1 in enumerate(candidates):
                for j, candidate2 in enumerate(candidates[i+1:], i+1):
                    similarity = await self._calculate_semantic_similarity(
                        candidate1, candidate2, user_input
                    )
                    
                    if similarity > self.thresholds['semantic_similarity']:
                        # 发现语义歧义
                        level = self._determine_ambiguity_level(similarity, 'semantic')
                        
                        signal = AmbiguitySignal(
                            type=AmbiguityType.SEMANTIC,
                            level=level,
                            score=similarity,
                            evidence={
                                'candidate1': candidate1['intent_name'],
                                'candidate2': candidate2['intent_name'],
                                'similarity_score': similarity,
                                'user_input': user_input[:100]
                            },
                            explanation=f"意图 {candidate1['intent_name']} 和 {candidate2['intent_name']} 在语义上高度相似 (相似度: {similarity:.3f})",
                            confidence=0.8
                        )
                        signals.append(signal)
            
            return signals
            
        except Exception as e:
            logger.error(f"语义歧义检测失败: {str(e)}")
            return []
    
    async def _detect_confidence_ambiguity(self, candidates: List[Dict]) -> List[AmbiguitySignal]:
        """检测置信度歧义"""
        signals = []
        
        try:
            # 按置信度排序
            sorted_candidates = sorted(candidates, key=lambda x: x['confidence'], reverse=True)
            
            # 检查前几个候选的置信度差异
            for i in range(min(3, len(sorted_candidates) - 1)):
                conf1 = sorted_candidates[i]['confidence']
                conf2 = sorted_candidates[i + 1]['confidence']
                gap = conf1 - conf2
                
                if gap < self.thresholds['confidence_gap']:
                    # 置信度差异过小，存在歧义
                    level = self._determine_ambiguity_level(1 - gap, 'confidence')
                    
                    signal = AmbiguitySignal(
                        type=AmbiguityType.CONFIDENCE,
                        level=level,
                        score=1 - gap,  # 差异越小，歧义得分越高
                        evidence={
                            'candidate1': sorted_candidates[i]['intent_name'],
                            'candidate2': sorted_candidates[i + 1]['intent_name'],
                            'confidence1': conf1,
                            'confidence2': conf2,
                            'gap': gap
                        },
                        explanation=f"置信度差异过小: {sorted_candidates[i]['intent_name']} ({conf1:.3f}) vs {sorted_candidates[i + 1]['intent_name']} ({conf2:.3f}), 差异={gap:.3f}",
                        confidence=0.9
                    )
                    signals.append(signal)
            
            return signals
            
        except Exception as e:
            logger.error(f"置信度歧义检测失败: {str(e)}")
            return []
    
    async def _detect_contextual_ambiguity(self, candidates: List[Dict], 
                                         user_input: str, 
                                         conversation_context: Dict) -> List[AmbiguitySignal]:
        """检测上下文歧义"""
        signals = []
        
        try:
            # 分析对话历史
            history = conversation_context.get('history', [])
            current_intent = conversation_context.get('current_intent')
            
            # 检查意图切换歧义
            if current_intent:
                for candidate in candidates:
                    if candidate['intent_name'] != current_intent:
                        # 检查是否存在意图切换的歧义
                        switch_probability = await self._calculate_intent_switch_probability(
                            current_intent, candidate['intent_name'], history
                        )
                        
                        if switch_probability > 0.3:  # 切换概率较高
                            level = self._determine_ambiguity_level(switch_probability, 'contextual')
                            
                            signal = AmbiguitySignal(
                                type=AmbiguityType.CONTEXTUAL,
                                level=level,
                                score=switch_probability,
                                evidence={
                                    'current_intent': current_intent,
                                    'candidate_intent': candidate['intent_name'],
                                    'switch_probability': switch_probability,
                                    'history_length': len(history)
                                },
                                explanation=f"在当前上下文中从 {current_intent} 切换到 {candidate['intent_name']} 存在歧义 (概率: {switch_probability:.3f})",
                                confidence=0.7
                            )
                            signals.append(signal)
            
            # 检查上下文相关性歧义
            for candidate in candidates:
                context_relevance = await self._calculate_context_relevance(
                    candidate, user_input, conversation_context
                )
                
                if context_relevance < self.thresholds['context_relevance']:
                    level = self._determine_ambiguity_level(1 - context_relevance, 'contextual')
                    
                    signal = AmbiguitySignal(
                        type=AmbiguityType.CONTEXTUAL,
                        level=level,
                        score=1 - context_relevance,
                        evidence={
                            'intent_name': candidate['intent_name'],
                            'context_relevance': context_relevance,
                            'user_input': user_input[:100]
                        },
                        explanation=f"意图 {candidate['intent_name']} 与当前上下文相关性较低 (相关性: {context_relevance:.3f})",
                        confidence=0.6
                    )
                    signals.append(signal)
            
            return signals
            
        except Exception as e:
            logger.error(f"上下文歧义检测失败: {str(e)}")
            return []
    
    async def _detect_domain_ambiguity(self, candidates: List[Dict]) -> List[AmbiguitySignal]:
        """检测领域歧义"""
        signals = []
        
        try:
            # 获取候选意图的领域信息
            domain_groups = defaultdict(list)
            
            for candidate in candidates:
                intent_name = candidate['intent_name']
                domain = await self._extract_intent_domain(intent_name)
                domain_groups[domain].append(candidate)
            
            # 如果有多个领域，检测领域歧义
            if len(domain_groups) > 1:
                domains = list(domain_groups.keys())
                
                for i, domain1 in enumerate(domains):
                    for domain2 in domains[i+1:]:
                        overlap = await self._calculate_domain_overlap(domain1, domain2)
                        
                        if overlap > self.thresholds['domain_overlap']:
                            level = self._determine_ambiguity_level(overlap, 'domain')
                            
                            signal = AmbiguitySignal(
                                type=AmbiguityType.DOMAIN,
                                level=level,
                                score=overlap,
                                evidence={
                                    'domain1': domain1,
                                    'domain2': domain2,
                                    'overlap_score': overlap,
                                    'candidates1': [c['intent_name'] for c in domain_groups[domain1]],
                                    'candidates2': [c['intent_name'] for c in domain_groups[domain2]]
                                },
                                explanation=f"领域 {domain1} 和 {domain2} 存在重叠歧义 (重叠度: {overlap:.3f})",
                                confidence=0.7
                            )
                            signals.append(signal)
            
            return signals
            
        except Exception as e:
            logger.error(f"领域歧义检测失败: {str(e)}")
            return []
    
    async def _detect_structural_ambiguity(self, candidates: List[Dict]) -> List[AmbiguitySignal]:
        """检测结构化歧义"""
        signals = []
        
        try:
            # 检测意图层次结构中的歧义
            for i, candidate1 in enumerate(candidates):
                for j, candidate2 in enumerate(candidates[i+1:], i+1):
                    relationship = await self._analyze_intent_relationship(
                        candidate1['intent_name'], candidate2['intent_name']
                    )
                    
                    if relationship in ['parent_child', 'sibling', 'cousin']:
                        # 存在结构化关系的歧义
                        level = self._determine_ambiguity_level(0.8, 'structural')
                        
                        signal = AmbiguitySignal(
                            type=AmbiguityType.STRUCTURAL,
                            level=level,
                            score=0.8,
                            evidence={
                                'candidate1': candidate1['intent_name'],
                                'candidate2': candidate2['intent_name'],
                                'relationship': relationship
                            },
                            explanation=f"意图 {candidate1['intent_name']} 和 {candidate2['intent_name']} 在结构上有 {relationship} 关系",
                            confidence=0.8
                        )
                        signals.append(signal)
            
            return signals
            
        except Exception as e:
            logger.error(f"结构化歧义检测失败: {str(e)}")
            return []
    
    async def _detect_temporal_ambiguity(self, candidates: List[Dict], 
                                       conversation_context: Optional[Dict]) -> List[AmbiguitySignal]:
        """检测时间相关歧义"""
        signals = []
        
        try:
            if not conversation_context:
                return signals
            
            current_time = datetime.now()
            
            # 检查时间敏感的意图
            for candidate in candidates:
                intent_name = candidate['intent_name']
                
                # 检查意图是否有时间依赖
                temporal_dependency = await self._check_temporal_dependency(intent_name, current_time)
                
                if temporal_dependency['has_dependency']:
                    level = self._determine_ambiguity_level(temporal_dependency['ambiguity_score'], 'temporal')
                    
                    signal = AmbiguitySignal(
                        type=AmbiguityType.TEMPORAL,
                        level=level,
                        score=temporal_dependency['ambiguity_score'],
                        evidence={
                            'intent_name': intent_name,
                            'dependency_type': temporal_dependency['type'],
                            'current_time': current_time.isoformat(),
                            'time_window': temporal_dependency['time_window']
                        },
                        explanation=f"意图 {intent_name} 具有时间依赖性歧义 ({temporal_dependency['type']})",
                        confidence=0.6
                    )
                    signals.append(signal)
            
            return signals
            
        except Exception as e:
            logger.error(f"时间歧义检测失败: {str(e)}")
            return []
    
    async def _synthesize_analysis(self, signals: List[AmbiguitySignal], 
                                 candidates: List[Dict], 
                                 user_input: str) -> AmbiguityAnalysis:
        """综合分析歧义信号"""
        try:
            if not signals:
                return AmbiguityAnalysis(
                    is_ambiguous=False,
                    ambiguity_score=0.0,
                    primary_type=AmbiguityType.CONFIDENCE,
                    signals=[],
                    candidates=candidates,
                    recommended_action="proceed",
                    analysis_metadata={"reason": "no_signals"}
                )
            
            # 按类型分组信号
            signal_groups = defaultdict(list)
            for signal in signals:
                signal_groups[signal.type].append(signal)
            
            # 计算加权综合得分
            weighted_score = 0.0
            total_weight = 0.0
            
            for signal_type, type_signals in signal_groups.items():
                if signal_type in self.weights:
                    type_score = max(s.score for s in type_signals)  # 取该类型的最高分
                    weight = self.weights[signal_type]
                    weighted_score += type_score * weight
                    total_weight += weight
            
            # 标准化得分
            if total_weight > 0:
                final_score = weighted_score / total_weight
            else:
                final_score = 0.0
            
            # 确定主要歧义类型
            primary_type = max(signal_groups.keys(), 
                             key=lambda t: max(s.score for s in signal_groups[t]))
            
            # 确定是否存在歧义
            is_ambiguous = final_score > 0.5
            
            # 推荐行动
            recommended_action = await self._recommend_action(final_score, primary_type, signals)
            
            # 分析元数据
            metadata = {
                'total_signals': len(signals),
                'signal_types': list(signal_groups.keys()),
                'weighted_calculation': {
                    'raw_score': weighted_score,
                    'total_weight': total_weight,
                    'final_score': final_score
                },
                'primary_signals': [s for s in signals if s.type == primary_type],
                'analysis_timestamp': datetime.now().isoformat()
            }
            
            return AmbiguityAnalysis(
                is_ambiguous=is_ambiguous,
                ambiguity_score=final_score,
                primary_type=primary_type,
                signals=signals,
                candidates=candidates,
                recommended_action=recommended_action,
                analysis_metadata=metadata
            )
            
        except Exception as e:
            logger.error(f"综合分析失败: {str(e)}")
            return AmbiguityAnalysis(
                is_ambiguous=False,
                ambiguity_score=0.0,
                primary_type=AmbiguityType.CONFIDENCE,
                signals=signals,
                candidates=candidates,
                recommended_action="proceed",
                analysis_metadata={"error": str(e)}
            )
    
    async def _calculate_semantic_similarity(self, candidate1: Dict, candidate2: Dict, user_input: str) -> float:
        """计算语义相似度"""
        try:
            # 这里应该使用向量化方法，暂时使用简单的文本相似度
            name1 = candidate1['intent_name']
            name2 = candidate2['intent_name']
            
            # 简单的字符串相似度计算
            words1 = set(name1.lower().split('_'))
            words2 = set(name2.lower().split('_'))
            
            if not words1 or not words2:
                return 0.0
            
            # Jaccard相似度
            intersection = words1.intersection(words2)
            union = words1.union(words2)
            
            jaccard = len(intersection) / len(union) if union else 0.0
            
            return jaccard
            
        except Exception as e:
            logger.error(f"语义相似度计算失败: {str(e)}")
            return 0.0
    
    async def _calculate_intent_switch_probability(self, current_intent: str, 
                                                 candidate_intent: str, 
                                                 history: List[Dict]) -> float:
        """计算意图切换概率"""
        try:
            # 统计历史中的意图切换模式
            switches = 0
            total_transitions = 0
            
            for i in range(len(history) - 1):
                if history[i].get('intent') == current_intent:
                    total_transitions += 1
                    if history[i + 1].get('intent') == candidate_intent:
                        switches += 1
            
            if total_transitions == 0:
                return 0.3  # 默认概率
            
            probability = switches / total_transitions
            return probability
            
        except Exception as e:
            logger.error(f"意图切换概率计算失败: {str(e)}")
            return 0.3
    
    async def _calculate_context_relevance(self, candidate: Dict, user_input: str, context: Dict) -> float:
        """计算上下文相关性"""
        try:
            relevance = 0.5  # 基础相关性
            
            # 检查与当前意图的相关性
            current_intent = context.get('current_intent')
            if current_intent:
                if candidate['intent_name'] == current_intent:
                    relevance += 0.3
                else:
                    # 检查意图间的相关性
                    intent_relatedness = await self._calculate_intent_relatedness(
                        candidate['intent_name'], current_intent
                    )
                    relevance += intent_relatedness * 0.2
            
            # 检查与历史的相关性
            history = context.get('history', [])
            if history:
                recent_intents = [h.get('intent') for h in history[-3:]]  # 最近3个意图
                if candidate['intent_name'] in recent_intents:
                    relevance += 0.2
            
            return min(1.0, relevance)
            
        except Exception as e:
            logger.error(f"上下文相关性计算失败: {str(e)}")
            return 0.5
    
    async def _extract_intent_domain(self, intent_name: str) -> str:
        """提取意图的领域"""
        try:
            # 基于意图名称推断领域
            if 'flight' in intent_name.lower() or 'book' in intent_name.lower():
                return 'travel'
            elif 'balance' in intent_name.lower() or 'account' in intent_name.lower():
                return 'financial'
            elif 'weather' in intent_name.lower():
                return 'weather'
            else:
                return 'general'
                
        except Exception as e:
            logger.error(f"领域提取失败: {str(e)}")
            return 'general'
    
    async def _calculate_domain_overlap(self, domain1: str, domain2: str) -> float:
        """计算领域重叠度"""
        try:
            # 定义领域相似度矩阵
            domain_similarity = {
                ('travel', 'financial'): 0.3,
                ('travel', 'weather'): 0.2,
                ('financial', 'weather'): 0.1,
                ('general', 'travel'): 0.4,
                ('general', 'financial'): 0.4,
                ('general', 'weather'): 0.3,
            }
            
            if domain1 == domain2:
                return 1.0
            
            key = tuple(sorted([domain1, domain2]))
            return domain_similarity.get(key, 0.1)
            
        except Exception as e:
            logger.error(f"领域重叠度计算失败: {str(e)}")
            return 0.1
    
    async def _analyze_intent_relationship(self, intent1: str, intent2: str) -> str:
        """分析意图间的关系"""
        try:
            # 简单的关系分析
            parts1 = intent1.split('_')
            parts2 = intent2.split('_')
            
            common_parts = set(parts1).intersection(set(parts2))
            
            if len(common_parts) >= 2:
                return 'sibling'
            elif len(common_parts) == 1:
                return 'cousin'
            else:
                return 'unrelated'
                
        except Exception as e:
            logger.error(f"意图关系分析失败: {str(e)}")
            return 'unrelated'
    
    async def _check_temporal_dependency(self, intent_name: str, current_time: datetime) -> Dict:
        """检查时间依赖性"""
        try:
            # 检查意图是否有时间依赖
            time_sensitive_intents = {
                'book_flight': 'future',
                'check_weather': 'current',
                'schedule_meeting': 'future'
            }
            
            if intent_name in time_sensitive_intents:
                dependency_type = time_sensitive_intents[intent_name]
                
                return {
                    'has_dependency': True,
                    'type': dependency_type,
                    'ambiguity_score': 0.6,
                    'time_window': '1h'
                }
            
            return {
                'has_dependency': False,
                'type': 'none',
                'ambiguity_score': 0.0,
                'time_window': 'none'
            }
            
        except Exception as e:
            logger.error(f"时间依赖检查失败: {str(e)}")
            return {
                'has_dependency': False,
                'type': 'none',
                'ambiguity_score': 0.0,
                'time_window': 'none'
            }
    
    async def _calculate_intent_relatedness(self, intent1: str, intent2: str) -> float:
        """计算意图相关性"""
        try:
            # 简单的相关性计算
            if intent1 == intent2:
                return 1.0
            
            # 检查是否有共同的词根
            words1 = set(intent1.lower().split('_'))
            words2 = set(intent2.lower().split('_'))
            
            if not words1 or not words2:
                return 0.0
            
            # Jaccard相似度
            intersection = words1.intersection(words2)
            union = words1.union(words2)
            
            return len(intersection) / len(union) if union else 0.0
            
        except Exception as e:
            logger.error(f"意图相关性计算失败: {str(e)}")
            return 0.0
    
    def _determine_ambiguity_level(self, score: float, signal_type: str) -> AmbiguityLevel:
        """确定歧义等级"""
        try:
            if score >= 0.8:
                return AmbiguityLevel.CRITICAL
            elif score >= 0.6:
                return AmbiguityLevel.HIGH
            elif score >= 0.4:
                return AmbiguityLevel.MEDIUM
            else:
                return AmbiguityLevel.LOW
                
        except Exception:
            return AmbiguityLevel.LOW
    
    async def _recommend_action(self, ambiguity_score: float, 
                              primary_type: AmbiguityType, 
                              signals: List[AmbiguitySignal]) -> str:
        """推荐行动"""
        try:
            if ambiguity_score < 0.3:
                return "proceed"
            elif ambiguity_score < 0.6:
                return "clarify"
            elif ambiguity_score < 0.8:
                return "disambiguate"
            else:
                return "escalate"
                
        except Exception:
            return "proceed"
    
    async def update_similarity_cache(self, intent1: str, intent2: str, similarity: float):
        """更新相似度缓存"""
        try:
            key = tuple(sorted([intent1, intent2]))
            self.intent_similarities[key] = similarity
            
        except Exception as e:
            logger.error(f"更新相似度缓存失败: {str(e)}")
    
    async def get_detection_statistics(self) -> Dict:
        """获取检测统计信息"""
        try:
            return {
                'cached_similarities': len(self.intent_similarities),
                'cached_patterns': len(self.context_patterns),
                'domain_hierarchy_size': len(self.domain_hierarchy),
                'user_preferences': len(self.user_preferences),
                'thresholds': self.thresholds,
                'weights': {k.value: v for k, v in self.weights.items()}
            }
            
        except Exception as e:
            logger.error(f"获取检测统计失败: {str(e)}")
            return {'error': str(e)}