"""
意图识别服务
"""
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime

from src.models.intent import Intent
from src.models.conversation import Conversation, IntentAmbiguity
from src.services.cache_service import CacheService
from src.services.audit_service import AuditService, AuditAction
from src.services.cache_invalidation_service import CacheInvalidationService, CacheInvalidationType
from src.services.config_management_service import get_config_management_service
from src.core.event_system import get_event_system, EventType
from src.core.nlu_engine import NLUEngine
from src.core.confidence_manager import ConfidenceManager, ThresholdDecision
from src.core.ambiguity_detector import EnhancedAmbiguityDetector, AmbiguityAnalysis
from src.core.intelligent_question_generator import IntelligentQuestionGenerator, QuestionContext
from src.core.advanced_choice_parser import AdvancedChoiceParser, ParseResult
from src.core.multi_strategy_resolver import MultiStrategyResolver, ResolutionContext, ResolutionAttempt
from src.core.clarification_question_generator import ClarificationQuestionGenerator, ClarificationType
from src.core.intent_confirmation_manager import (
    IntentConfirmationManager, ConfirmationContext, ConfirmationTrigger,
    ConfirmationStrategy, ConfirmationResponse, RiskLevel, get_confirmation_manager
)
from src.schemas.intent_recognition import IntentRecognitionResult
from src.utils.logger import get_logger
from src.config.settings import settings

logger = get_logger(__name__)


class IntentService:
    """意图识别服务类"""
    
    def __init__(self, cache_service: CacheService, nlu_engine: NLUEngine,
                 audit_service: Optional[AuditService] = None,
                 cache_invalidation_service: Optional[CacheInvalidationService] = None):
        self.cache_service = cache_service
        self.nlu_engine = nlu_engine
        self.audit_service = audit_service or AuditService()
        self.cache_invalidation_service = cache_invalidation_service or CacheInvalidationService(cache_service)
        # V2.2重构: 集成配置管理服务和事件系统
        self.config_management_service = get_config_management_service()
        self.event_system = get_event_system()
        self.confidence_manager = ConfidenceManager(settings)
        self.ambiguity_threshold = settings.AMBIGUITY_DETECTION_THRESHOLD
        self.enhanced_ambiguity_detector = EnhancedAmbiguityDetector(settings)
        self.intelligent_question_generator = IntelligentQuestionGenerator()
        self.advanced_choice_parser = AdvancedChoiceParser()
        self.multi_strategy_resolver = MultiStrategyResolver()
        self.clarification_generator = ClarificationQuestionGenerator()
        self.confirmation_manager = get_confirmation_manager(settings)
    
    async def recognize_intent(self, user_input: str, user_id: str, 
                             context: Dict = None) -> IntentRecognitionResult:
        """
        识别用户输入的意图
        
        Args:
            user_input: 用户输入文本
            user_id: 用户ID
            context: 对话上下文
            
        Returns:
            IntentRecognitionResult: 意图识别结果
        """
        try:
            # 1. 检查缓存中是否有相同输入的识别结果
            input_hash = abs(hash(user_input))
            cache_key = self.cache_service.get_cache_key('intent_recognition', input_hash=input_hash, user_id=user_id)
            cached_result = await self.cache_service.get(cache_key)
            if cached_result:
                logger.info(f"从缓存获取意图识别结果: {user_input[:50]}")
                return self._deserialize_result(cached_result)
            
            # 2. 获取所有活跃的意图配置
            active_intents = await self._get_active_intents()
            if not active_intents:
                logger.warning("没有找到活跃的意图配置")
                return IntentRecognitionResult.from_intent_service_result(
                    intent=None, 
                    confidence=0.0,
                    user_input=user_input,
                    context=context
                )
            
            # 3. 使用NLU引擎进行意图识别
            nlu_result = await self.nlu_engine.recognize_intent(
                user_input, active_intents=None, context=context
            )
            
            # 将NLU结果转换为标准格式
            recognition_results = await self._convert_nlu_result(nlu_result, active_intents)
            
            # 4. 分析识别结果
            result = await self._analyze_recognition_results(
                recognition_results, user_input, context
            )
            
            # 5. 缓存识别结果
            await self.cache_service.set(
                cache_key, self._serialize_result(result), ttl=1800
            )
            
            # 6. 记录识别日志
            logger.info(f"意图识别完成: {user_input[:50]} -> {result.intent.intent_name if result.intent else 'None'}")
            
            return result
            
        except Exception as e:
            logger.error(f"意图识别失败: {str(e)}")
            return IntentRecognitionResult.from_intent_service_result(
                intent=None, 
                confidence=0.0,
                user_input=user_input,
                context=context
            )
    
    async def recognize_intent_with_history(
        self, 
        user_input: str, 
        user_id: str, 
        session_context: Dict[str, Any],
        conversation_history: List[Dict[str, Any]]
    ) -> IntentRecognitionResult:
        """
        基于历史对话的意图识别（混合架构设计）
        
        Args:
            user_input: 用户输入文本
            user_id: 用户ID
            session_context: 会话上下文
            conversation_history: 对话历史
            
        Returns:
            IntentRecognitionResult: 意图识别结果
        """
        try:
            # 构建增强的上下文信息
            enhanced_context = {
                **(session_context or {}),
                'conversation_history': conversation_history,
                'current_turn': session_context.get('current_turn', 1),
                'current_slots': session_context.get('current_slots', {}),
                'user_id': user_id
            }
            
            # 检查是否存在上下文相关的缓存
            context_hash = abs(hash(str(enhanced_context)))
            input_hash = abs(hash(user_input))
            cache_key = self.cache_service.get_cache_key(
                'intent_recognition_with_history', 
                input_hash=input_hash, 
                user_id=user_id,
                context_hash=context_hash
            )
            
            cached_result = await self.cache_service.get(cache_key)
            if cached_result:
                logger.info(f"从缓存获取历史增强的意图识别结果: {user_input[:50]}")
                return self._deserialize_result(cached_result)
            
            # 分析对话历史，提取上下文线索
            historical_context = self._analyze_conversation_history(conversation_history)
            
            # 合并历史分析结果到上下文
            enhanced_context.update({
                'historical_intents': historical_context.get('recent_intents', []),
                'historical_entities': historical_context.get('entities', {}),
                'conversation_topic': historical_context.get('topic', None),
                'interaction_pattern': historical_context.get('pattern', 'linear')
            })
            
            # 使用增强上下文进行意图识别
            result = await self.recognize_intent(user_input, user_id, enhanced_context)
            
            # 基于历史调整置信度
            if result.intent and conversation_history:
                adjusted_confidence = self._adjust_confidence_with_history(
                    result, conversation_history, enhanced_context
                )
                result.confidence = adjusted_confidence
                
                # 重新判断是否需要歧义处理
                if adjusted_confidence < 0.6 and len(result.alternatives) > 1:
                    result.is_ambiguous = True
            
            # 缓存增强识别结果
            await self.cache_service.set(
                cache_key, self._serialize_result(result), ttl=1800
            )
            
            logger.info(
                f"历史增强意图识别完成: {user_input[:50]} -> "
                f"{result.intent.intent_name if result.intent else 'None'} "
                f"(置信度: {result.confidence:.3f})"
            )
            
            return result
            
        except Exception as e:
            logger.error(f"历史增强意图识别失败: {str(e)}")
            # 回退到基础意图识别
            return await self.recognize_intent(user_input, user_id, session_context)
    
    def _analyze_conversation_history(self, conversation_history: List[Dict[str, Any]]) -> Dict[str, Any]:
        """分析对话历史，提取上下文线索"""
        if not conversation_history:
            return {}
        
        try:
            recent_intents = []
            entities = {}
            topics = []
            
            # 分析最近几轮对话
            for turn in conversation_history[-5:]:  # 最近5轮
                if turn.get('intent_recognized'):
                    recent_intents.append(turn['intent_recognized'])
                
                if turn.get('slots_extracted'):
                    entities.update(turn['slots_extracted'])
                
                if turn.get('system_response'):
                    # 简单的主题提取（可以后续增强）
                    response = turn['system_response']
                    if '机票' in response or '航班' in response:
                        topics.append('flight_booking')
                    elif '银行' in response or '余额' in response:
                        topics.append('banking')
            
            # 确定主要话题
            main_topic = max(set(topics), key=topics.count) if topics else None
            
            # 确定交互模式
            pattern = 'multi_turn' if len(conversation_history) > 3 else 'linear'
            
            return {
                'recent_intents': recent_intents[-3:],  # 最近3个意图
                'entities': entities,
                'topic': main_topic,
                'pattern': pattern,
                'turn_count': len(conversation_history)
            }
            
        except Exception as e:
            logger.warning(f"分析对话历史失败: {str(e)}")
            return {}
    
    def _adjust_confidence_with_history(
        self, 
        result: IntentRecognitionResult, 
        conversation_history: List[Dict[str, Any]],
        enhanced_context: Dict[str, Any]
    ) -> float:
        """基于历史对话调整置信度"""
        try:
            base_confidence = result.confidence
            adjustment = 0.0
            user_input = result.user_input or ""
            
            # 检查是否为不完整输入（可能是槽位补充）
            is_incomplete_input = len(user_input.split()) <= 3 and base_confidence < 0.5
            
            # 意图连续性检查
            recent_intents = enhanced_context.get('historical_intents', [])
            if result.intent and recent_intents:
                if result.intent.intent_name in recent_intents:
                    adjustment += 0.1  # 同一意图连续出现，增加置信度
            
            # 增强的槽位延续性检查 - 特别处理不完整输入
            if is_incomplete_input and conversation_history:
                # 对于不完整输入，查找最近的意图上下文
                last_intent = None
                for turn in reversed(conversation_history[-3:]):  # 最近3轮
                    if turn.get('intent_recognized'):
                        last_intent = turn['intent_recognized']
                        break
                
                if last_intent:
                    # 检查输入是否像是在提供槽位信息
                    potential_slots = self._detect_potential_slot_values(user_input, last_intent)
                    if potential_slots:
                        # 如果输入看起来像是在提供槽位值，倾向于继承之前的意图
                        for alt in result.alternatives:
                            if alt.intent_name == last_intent:
                                # 将匹配历史意图的候选提升置信度
                                alt.confidence = min(1.0, alt.confidence + 0.3)
                                logger.debug(f"基于上下文提升意图 {last_intent} 置信度: {alt.confidence}")
                                
                        # 重新排序alternatives
                        result.alternatives.sort(key=lambda x: x.confidence, reverse=True)
                        
                        # 更新主要意图为最高置信度的候选
                        if result.alternatives and result.alternatives[0].confidence > base_confidence:
                            # 直接更新主要意图
                            best_alt = result.alternatives[0]
                            try:
                                from src.models.intent import Intent
                                result.intent = Intent.get(Intent.intent_name == best_alt.intent_name)
                                result.intent_name = best_alt.intent_name
                                result.confidence = best_alt.confidence
                                result.is_ambiguous = False  # 基于上下文解决了歧义
                                
                                logger.info(f"基于上下文延续，意图从 {result.intent_name or 'None'} 调整为 {best_alt.intent_name}")
                                
                                # 添加推理说明
                                context_reason = f"基于历史意图 {last_intent} 和槽位信息 {list(potential_slots.keys())} 调整"
                                if result.reasoning:
                                    result.reasoning += f" | {context_reason}"
                                else:
                                    result.reasoning = context_reason
                                    
                            except Exception as e:
                                logger.warning(f"更新意图对象失败: {e}")
                                adjustment += 0.3  # 如果无法更新意图对象，至少提升置信度
            
            # 原有的槽位延续性检查
            current_slots = enhanced_context.get('current_slots', {})
            if current_slots and result.intent:
                # 如果当前输入可能在延续之前的槽位填充
                slot_names = [slot.slot_name for slot in result.intent.slots]
                overlapping_slots = set(current_slots.keys()) & set(slot_names)
                if overlapping_slots:
                    adjustment += 0.05  # 槽位延续，小幅增加置信度
            
            # 对话长度调整
            turn_count = len(conversation_history)
            if turn_count > 1:
                # 多轮对话中，适当提高置信度
                adjustment += min(0.1, turn_count * 0.02)
            
            # 应用调整但确保在合理范围内
            adjusted_confidence = min(1.0, max(0.0, base_confidence + adjustment))
            
            return adjusted_confidence
            
        except Exception as e:
            logger.warning(f"调整置信度失败: {str(e)}")
            return result.confidence
    
    def _detect_potential_slot_values(self, user_input: str, intent_name: str) -> Dict[str, Any]:
        """检测用户输入中可能的槽位值"""
        potential_slots = {}
        user_input_lower = user_input.lower()
        
        # 常见的城市名（简化版）
        cities = ['北京', '上海', '广州', '深圳', '杭州', '南京', '武汉', '成都', '重庆', '西安']
        for city in cities:
            if city in user_input:
                if intent_name in ['book_flight', 'book_train']:
                    # 根据语言模式判断是出发地还是目的地
                    if '去' in user_input or '到' in user_input:
                        potential_slots['arrival_city'] = city
                    elif '从' in user_input:
                        potential_slots['departure_city'] = city
                    else:
                        # 默认认为是目的地
                        potential_slots['arrival_city'] = city
        
        # 检测时间表达
        time_patterns = ['明天', '后天', '下周', '今天', '周一', '周二', '周三', '周四', '周五', '周六', '周日']
        for pattern in time_patterns:
            if pattern in user_input:
                potential_slots['departure_date'] = pattern
        
        # 检测数量
        import re
        numbers = re.findall(r'[一二三四五六七八九十\d]+(?=人|位|张|个)', user_input)
        if numbers:
            potential_slots['passenger_count'] = numbers[0]
            
        return potential_slots
    
    async def _get_active_intents(self) -> List[Intent]:
        """获取所有活跃的意图配置"""
        # 首先尝试从缓存获取
        cached_intents = await self.cache_service.get("active_intents")
        if cached_intents:
            return cached_intents
        
        # 从数据库查询活跃意图
        intents = list(Intent.select().where(Intent.is_active == True).order_by(Intent.priority.desc()))
        
        # 缓存结果
        await self.cache_service.set("active_intents", intents, ttl=3600)
        
        # 记录审计日志 - 系统查询活跃意图
        try:
            await self.audit_service.log_config_change(
                table_name="intents",
                record_id=0,
                action=AuditAction.INSERT,  # 使用INSERT表示查询操作
                old_values=None,
                new_values={"action": "query_active_intents", "count": len(intents)},
                operator_id="intent_service"
            )
        except Exception as e:
            logger.warning(f"记录意图查询审计日志失败: {str(e)}")
        
        return intents
    
    async def _analyze_recognition_results(self, results: List[Dict], 
                                         user_input: str, context: Dict = None) -> IntentRecognitionResult:
        """
        分析意图识别结果
        
        Args:
            results: NLU引擎返回的识别结果列表
            user_input: 用户输入
            context: 对话上下文
            
        Returns:
            IntentRecognitionResult: 分析后的结果
        """
        if not results:
            return IntentRecognitionResult.from_intent_service_result(
                intent=None, 
                confidence=0.0,
                user_input=user_input,
                context=context
            )
        
        # 按置信度排序
        results.sort(key=lambda x: x['confidence'], reverse=True)
        
        top_result = results[0]
        top_intent = await self._get_intent_by_name(top_result['intent_name'])
        top_confidence = top_result['confidence']
        
        # 使用置信度管理器进行阈值决策
        from src.core.confidence_manager import ConfidenceScore, ConfidenceSource
        
        # 创建置信度分数对象
        confidence_score = ConfidenceScore(
            value=top_confidence,
            source=ConfidenceSource.HYBRID,
            components={'recognition': top_confidence},
            explanation=f"识别置信度: {top_confidence:.3f}"
        )
        
        # 准备候选意图列表
        alternatives = []
        if len(results) > 1:
            for result in results[:3]:  # 最多3个候选
                intent = await self._get_intent_by_name(result['intent_name'])
                if intent:
                    alternatives.append((intent.intent_name, result['confidence']))
        
        # 进行阈值决策（传递上下文和用户ID）
        threshold_decision = self.confidence_manager.make_threshold_decision(
            confidence_score, top_intent, alternatives, context, 
            context.get('user_id') if context else None
        )
        
        logger.info(f"阈值决策: {threshold_decision.reason}")
        
        # 根据决策结果返回 - 修改：低置信度也尝试歧义检测
        if not threshold_decision.passed:
            # 检查是否是潜在的歧义情况
            # 如果用户输入包含通用词汇，尝试歧义检测
            ambiguous_keywords = ['订票', '买票', '预订', '想要', '帮我', '我要']
            contains_ambiguous_keyword = any(keyword in user_input for keyword in ambiguous_keywords)
            
            if contains_ambiguous_keyword:
                # 尝试基于关键词的歧义检测
                potential_candidates = await self._find_potential_candidates_by_keywords(user_input)
                if len(potential_candidates) > 1:
                    # 进行歧义检测
                    is_ambiguous, ambiguous_candidates, ambiguity_analysis = await self.detect_ambiguity(
                        potential_candidates, user_input, context
                    )
                    if is_ambiguous:
                        logger.info(f"基于关键词检测到歧义: {len(ambiguous_candidates)}个候选")
                        return IntentRecognitionResult.from_ambiguous_result(
                            candidates=ambiguous_candidates,
                            analysis=ambiguity_analysis,
                            user_input=user_input,
                            context=context
                        )
            
            # 更新意图统计（失败案例）
            if top_intent:
                self.confidence_manager.update_intent_statistics(
                    top_intent.intent_name, top_confidence, success=False
                )
            return IntentRecognitionResult.from_intent_service_result(
                intent=None, 
                confidence=top_confidence,
                user_input=user_input,
                context=context
            )
        
        # 使用增强的歧义检测
        if len(results) > 1:
            # 准备候选意图列表
            candidates_for_detection = []
            for result in results[:5]:  # 最多检查5个候选
                intent = await self._get_intent_by_name(result['intent_name'])
                if intent:
                    candidates_for_detection.append({
                        'intent_name': intent.intent_name,
                        'display_name': intent.display_name,
                        'confidence': result['confidence']
                    })
            
            # 进行增强歧义检测
            is_ambiguous, ambiguous_candidates, ambiguity_analysis = await self.detect_ambiguity(
                candidates_for_detection, user_input, context
            )
            
            if is_ambiguous and len(ambiguous_candidates) > 1:
                # 对歧义候选进行阈值验证
                valid_alternatives = []
                for candidate in ambiguous_candidates:
                    intent = await self._get_intent_by_name(candidate['intent_name'])
                    if intent:
                        # 对每个候选进行阈值检查
                        alt_confidence_score = ConfidenceScore(
                            value=candidate['confidence'],
                            source=ConfidenceSource.HYBRID,
                            components={'recognition': candidate['confidence']}
                        )
                        alt_decision = self.confidence_manager.make_threshold_decision(
                            alt_confidence_score, intent
                        )
                        
                        if alt_decision.passed:
                            enhanced_candidate = {
                                'intent_name': intent.intent_name,
                                'display_name': intent.display_name,
                                'confidence': candidate['confidence'],
                                'threshold_decision': alt_decision,
                                'ambiguity_analysis': ambiguity_analysis
                            }
                            valid_alternatives.append(enhanced_candidate)
                
                if len(valid_alternatives) > 1:
                    logger.info(f"增强歧义检测确认: {len(valid_alternatives)}个候选意图, "
                               f"歧义得分={ambiguity_analysis.ambiguity_score:.3f}, "
                               f"主要类型={ambiguity_analysis.primary_type.value if ambiguity_analysis.primary_type else 'None'}")
                    
                    # 尝试自动解决歧义
                    auto_resolved_intent = await self._attempt_auto_resolution(
                        valid_alternatives, ambiguity_analysis, context, user_input
                    )
                    
                    if auto_resolved_intent:
                        logger.info(f"自动解决歧义成功: {auto_resolved_intent.intent_name}")
                        return IntentRecognitionResult.from_intent_service_result(
                            intent=auto_resolved_intent, 
                            confidence=top_confidence,
                            user_input=user_input,
                            context=context
                        )
                    
                    # 自动解决失败，返回歧义结果
                    return IntentRecognitionResult.from_intent_service_result(
                        intent=None, 
                        confidence=top_confidence, 
                        alternatives=[{
                            'intent_name': alt['intent_name'],
                            'confidence': alt['confidence']
                        } for alt in valid_alternatives],
                        is_ambiguous=True,
                        user_input=user_input,
                        context=context
                    )
        
        # 单一明确的意图 - 更新成功统计
        self.confidence_manager.update_intent_statistics(
            top_intent.intent_name, top_confidence, success=True
        )
        
        return IntentRecognitionResult.from_intent_service_result(
            intent=top_intent, 
            confidence=top_confidence,
            user_input=user_input,
            context=context
        )
    
    async def _get_intent_by_name(self, intent_name: str) -> Optional[Intent]:
        """根据名称获取意图对象"""
        try:
            return Intent.get(Intent.intent_name == intent_name, Intent.is_active == True)
        except Intent.DoesNotExist:
            return None
    
    async def resolve_ambiguity(self, conversation_id: int, candidates: List[Dict], 
                              user_choice: str, user_id: Optional[str] = None,
                              context: Optional[Dict] = None) -> Tuple[Optional[Intent], ParseResult]:
        """
        解决意图歧义（增强版）
        
        Args:
            conversation_id: 对话ID
            candidates: 候选意图列表
            user_choice: 用户选择（可以是数字或意图名称）
            user_id: 用户ID
            context: 对话上下文
            
        Returns:
            Tuple[Optional[Intent], ParseResult]: (解决后的意图, 解析结果)
        """
        try:
            # 查找对应的歧义记录
            ambiguity = IntentAmbiguity.get(
                IntentAmbiguity.conversation == conversation_id,
                IntentAmbiguity.resolved_at.is_null(True)
            )
            
            # 使用高级选择解析器
            parse_result = await self.advanced_choice_parser.parse_user_choice(
                user_choice, candidates, user_id, context
            )
            
            logger.info(f"高级解析结果: 类型={parse_result.choice_type.value}, "
                       f"置信度={parse_result.confidence:.3f}, "
                       f"选择={parse_result.selected_option}")
            
            selected_intent = None
            
            # 根据解析结果处理
            if parse_result.choice_type.value == 'negative':
                # 用户表示都不符合
                ambiguity.resolve_with_choice("none_of_above")
                ambiguity.save()
                logger.info(f"用户表示都不符合: {conversation_id}")
                return None, parse_result
            
            elif parse_result.choice_type.value == 'uncertain':
                # 用户不确定，需要更多信息
                logger.info(f"用户不确定选择: {conversation_id}")
                return None, parse_result
            
            elif parse_result.selected_option:
                # 有明确选择
                selected_intent = await self._get_intent_from_parse_result(parse_result, candidates)
                
                if selected_intent:
                    # 更新歧义记录
                    ambiguity.resolve_with_choice(selected_intent.intent_name)
                    ambiguity.save()
                    
                    # 更新用户模式
                    self.advanced_choice_parser.update_user_pattern(
                        user_id, parse_result, success=True
                    )
                    
                    logger.info(f"歧义已解决: {conversation_id} -> {selected_intent.intent_name}")
                    return selected_intent, parse_result
            
            # 解析失败
            if user_id:
                self.advanced_choice_parser.update_user_pattern(
                    user_id, parse_result, success=False
                )
            
            return None, parse_result
            
        except IntentAmbiguity.DoesNotExist:
            logger.warning(f"未找到歧义记录: {conversation_id}")
            # 创建一个默认的解析结果
            from src.core.advanced_choice_parser import ChoiceType, ConfidenceLevel
            default_result = ParseResult(
                choice_type=ChoiceType.UNCERTAIN,
                selected_option=None,
                selected_text=None,
                confidence=0.0,
                confidence_level=ConfidenceLevel.VERY_LOW,
                alternative_matches=[],
                error_corrections=[],
                explanation="未找到歧义记录",
                raw_input=user_choice,
                processing_steps=["未找到歧义记录"]
            )
            return None, default_result
        except Exception as e:
            logger.error(f"解决歧义失败: {str(e)}")
            # 创建一个错误的解析结果
            from src.core.advanced_choice_parser import ChoiceType, ConfidenceLevel
            error_result = ParseResult(
                choice_type=ChoiceType.UNCERTAIN,
                selected_option=None,
                selected_text=None,
                confidence=0.0,
                confidence_level=ConfidenceLevel.VERY_LOW,
                alternative_matches=[],
                error_corrections=[],
                explanation=f"解析错误: {str(e)}",
                raw_input=user_choice,
                processing_steps=[f"解析错误: {str(e)}"]
            )
            return None, error_result
    
    async def _get_intent_from_parse_result(self, parse_result: ParseResult, candidates: List[Dict]) -> Optional[Intent]:
        """根据解析结果获取意图对象"""
        try:
            if parse_result.selected_option and 1 <= parse_result.selected_option <= len(candidates):
                candidate = candidates[parse_result.selected_option - 1]
                return await self._get_intent_by_name(candidate['intent_name'])
            return None
        except Exception as e:
            logger.error(f"从解析结果获取意图失败: {str(e)}")
            return None
    
    async def _parse_user_choice(self, user_choice: str, candidates: List[Dict]) -> Optional[Intent]:
        """
        解析用户的歧义选择
        
        Args:
            user_choice: 用户选择（数字或意图名称）
            candidates: 候选意图列表
            
        Returns:
            Intent: 选择的意图对象
        """
        user_choice = user_choice.strip()
        
        # 尝试解析为数字选择
        try:
            choice_index = int(user_choice) - 1  # 用户输入从1开始
            if 0 <= choice_index < len(candidates):
                intent_name = candidates[choice_index]['intent_name']
                return await self._get_intent_by_name(intent_name)
        except ValueError:
            pass
        
        # 尝试直接匹配意图名称
        for candidate in candidates:
            if user_choice.lower() in [
                candidate['intent_name'].lower(),
                candidate.get('display_name', '').lower()
            ]:
                return await self._get_intent_by_name(candidate['intent_name'])
        
        # 模糊匹配
        for candidate in candidates:
            if user_choice.lower() in candidate.get('display_name', '').lower():
                return await self._get_intent_by_name(candidate['intent_name'])
        
        return None
    
    async def generate_disambiguation_question(self, 
                                             candidates: List[Dict],
                                             ambiguity_analysis: Optional[AmbiguityAnalysis] = None,
                                             context: Optional[Dict] = None,
                                             user_id: Optional[str] = None) -> str:
        """
        生成智能歧义澄清问题
        
        Args:
            candidates: 候选意图列表
            ambiguity_analysis: 歧义分析结果
            context: 对话上下文
            user_id: 用户ID
            
        Returns:
            str: 歧义澄清问题
        """
        try:
            if len(candidates) <= 1:
                return "请明确您的需求。"
            
            # 如果有歧义分析和上下文，使用智能生成器
            if ambiguity_analysis and context and user_id:
                # 构建问题上下文
                question_context = QuestionContext(
                    conversation_history=context.get('history', []),
                    current_intent_confidence=context.get('confidence', 0.5),
                    ambiguity_analysis=ambiguity_analysis,
                    user_engagement=context.get('user_engagement', 0.7),
                    time_pressure=context.get('time_pressure', 0.3),
                    turn_count=context.get('turn_count', 1)
                )
                
                # 使用智能生成器
                generated_question = await self.intelligent_question_generator.generate_disambiguation_question(
                    candidates, ambiguity_analysis, question_context, user_id
                )
                
                logger.info(f"使用智能生成器: 风格={generated_question.style.value}, "
                           f"复杂度={generated_question.complexity.value}, "
                           f"置信度={generated_question.confidence:.3f}")
                
                return generated_question.question_text
            
            # 回退到基本生成
            return await self._generate_basic_disambiguation_question(candidates)
            
        except Exception as e:
            logger.error(f"智能歧义问题生成失败: {str(e)}")
            return await self._generate_basic_disambiguation_question(candidates)
    
    async def _generate_basic_disambiguation_question(self, candidates: List[Dict]) -> str:
        """生成基本歧义澄清问题"""
        try:
            # 构建选择选项
            options = []
            for i, candidate in enumerate(candidates[:5], 1):  # 最多显示5个选项
                display_name = candidate.get('display_name', candidate['intent_name'])
                options.append(f"{i}. {display_name}")
            
            question = "我理解您的需求可能是以下几种，请选择：\n" + "\n".join(options)
            question += "\n\n请回复对应的数字或直接描述您的具体需求。"
            
            return question
            
        except Exception as e:
            logger.error(f"基本歧义问题生成失败: {str(e)}")
            return "请明确您的需求。"
    
    async def detect_intent_transfer(self, current_intent: str, user_input: str, 
                                   context: Dict = None) -> Tuple[bool, Optional[Intent], float]:
        """
        检测意图转移
        
        Args:
            current_intent: 当前意图名称
            user_input: 用户输入
            context: 对话上下文
            
        Returns:
            Tuple[bool, Optional[Intent], float]: (是否转移, 新意图, 置信度)
        """
        try:
            # 重新识别意图
            result = await self.recognize_intent(user_input, context.get('user_id', ''), context)
            
            if result.intent and result.intent.intent_name != current_intent:
                # 检查转移置信度是否足够高
                transfer_threshold = 0.1  # 转移阈值
                if result.confidence > 0.7:  # 新意图置信度阈值
                    logger.info(f"检测到意图转移: {current_intent} -> {result.intent.intent_name}")
                    return True, result.intent, result.confidence
            
            return False, None, 0.0
            
        except Exception as e:
            logger.error(f"意图转移检测失败: {str(e)}")
            return False, None, 0.0
    
    async def _convert_nlu_result(self, nlu_result, active_intents: List[Intent]) -> List[Dict]:
        """
        将NLU引擎结果转换为标准格式
        
        Args:
            nlu_result: NLU引擎返回的结果
            active_intents: 活跃意图列表
            
        Returns:
            List[Dict]: 标准格式的识别结果列表
        """
        try:
            if not nlu_result or nlu_result.intent_name == 'unknown':
                return []
            
            # 主要结果
            results = [{
                'intent_name': nlu_result.intent_name,
                'confidence': nlu_result.confidence
            }]
            
            # 添加备选结果
            if hasattr(nlu_result, 'alternatives') and nlu_result.alternatives:
                for alt in nlu_result.alternatives:
                    if hasattr(alt, 'intent_name') and hasattr(alt, 'confidence'):
                        results.append({
                            'intent_name': alt.intent_name,
                            'confidence': alt.confidence
                        })
            
            # 过滤掉不在活跃意图列表中的结果
            active_intent_names = set()
            if active_intents:
                for intent in active_intents:
                    if hasattr(intent, 'intent_name'):
                        active_intent_names.add(intent.intent_name)
            filtered_results = []
            
            for result in results:
                if not active_intent_names or result['intent_name'] in active_intent_names:
                    filtered_results.append(result)
            
            return filtered_results
            
        except Exception as e:
            logger.error(f"转换NLU结果失败: {str(e)}")
            return []
    
    async def calculate_confidence(self, user_input: str, intent: Intent, 
                                 context: Dict = None) -> float:
        """
        计算意图识别的置信度
        
        Args:
            user_input: 用户输入
            intent: 候选意图
            context: 对话上下文
            
        Returns:
            float: 置信度值 (0.0 - 1.0)
        """
        try:
            # 基础置信度计算
            base_confidence = 0.0
            
            # 1. 关键词匹配得分
            keyword_score = await self._calculate_keyword_score(user_input, intent)
            base_confidence += keyword_score * 0.4
            
            # 2. 示例相似度得分
            example_score = await self._calculate_example_similarity(user_input, intent)
            base_confidence += example_score * 0.4
            
            # 3. 上下文相关性得分
            context_score = await self._calculate_context_score(user_input, intent, context)
            base_confidence += context_score * 0.2
            
            # 确保在合理范围内
            confidence = max(0.0, min(1.0, base_confidence))
            
            logger.debug(f"置信度计算: {intent.intent_name} -> {confidence:.3f} "
                        f"(关键词:{keyword_score:.3f}, 示例:{example_score:.3f}, 上下文:{context_score:.3f})")
            
            return confidence
            
        except Exception as e:
            logger.error(f"置信度计算失败: {str(e)}")
            return 0.0
    
    async def _calculate_keyword_score(self, user_input: str, intent: Intent) -> float:
        """计算关键词匹配得分"""
        try:
            user_words = set(user_input.lower().split())
            intent_words = set()
            
            # 从意图名称提取关键词
            intent_words.update(intent.intent_name.lower().split('_'))
            
            # 从描述提取关键词
            if intent.description:
                intent_words.update(intent.description.lower().split())
            
            # 从显示名称提取关键词
            if intent.display_name:
                intent_words.update(intent.display_name.lower().split())
            
            # 计算交集得分
            if not intent_words:
                return 0.0
            
            matched_words = user_words.intersection(intent_words)
            score = len(matched_words) / len(intent_words)
            
            return min(1.0, score)
            
        except Exception as e:
            logger.error(f"关键词得分计算失败: {str(e)}")
            return 0.0
    
    async def _calculate_example_similarity(self, user_input: str, intent: Intent) -> float:
        """计算与示例的相似度得分"""
        try:
            examples = intent.get_examples()
            if not examples:
                return 0.0
            
            user_input_lower = user_input.lower()
            max_similarity = 0.0
            
            for example in examples[:10]:  # 限制检查数量
                example_lower = example.lower()
                
                # 简单的字符级相似度计算
                similarity = self._calculate_string_similarity(user_input_lower, example_lower)
                max_similarity = max(max_similarity, similarity)
            
            return max_similarity
            
        except Exception as e:
            logger.error(f"示例相似度计算失败: {str(e)}")
            return 0.0
    
    def _calculate_string_similarity(self, str1: str, str2: str) -> float:
        """计算两个字符串的相似度（简单版本）"""
        try:
            if not str1 or not str2:
                return 0.0
            
            # 计算公共子串
            words1 = set(str1.split())
            words2 = set(str2.split())
            
            if not words1 or not words2:
                return 0.0
            
            # Jaccard相似度
            intersection = words1.intersection(words2)
            union = words1.union(words2)
            
            return len(intersection) / len(union) if union else 0.0
            
        except Exception:
            return 0.0
    
    async def _calculate_context_score(self, user_input: str, intent: Intent, 
                                     context: Dict = None) -> float:
        """计算上下文相关性得分"""
        try:
            if not context:
                return 0.5  # 无上下文时给中性分数
            
            score = 0.5
            
            # 如果有当前意图，检查是否延续
            current_intent = context.get('current_intent')
            if current_intent == intent.intent_name:
                score += 0.3
            
            # 检查历史意图倾向
            intent_history = context.get('intent_history', [])
            if intent.intent_name in intent_history:
                score += 0.2
            
            return min(1.0, score)
            
        except Exception as e:
            logger.error(f"上下文得分计算失败: {str(e)}")
            return 0.5
    
    async def detect_ambiguity(self, candidates: List[Dict], 
                             user_input: str = "",
                             conversation_context: Dict = None,
                             threshold: float = None) -> Tuple[bool, List[Dict], AmbiguityAnalysis]:
        """
        检测意图识别歧义（增强版）
        
        Args:
            candidates: 候选意图列表
            user_input: 用户输入
            conversation_context: 对话上下文
            threshold: 歧义检测阈值
            
        Returns:
            Tuple[bool, List[Dict], AmbiguityAnalysis]: (是否有歧义, 歧义候选列表, 歧义分析结果)
        """
        try:
            if not candidates or len(candidates) < 2:
                return False, [], AmbiguityAnalysis(
                    is_ambiguous=False,
                    ambiguity_score=0.0,
                    primary_type=None,
                    signals=[],
                    candidates=candidates,
                    recommended_action="proceed",
                    analysis_metadata={"reason": "insufficient_candidates"}
                )
            
            # 使用增强的歧义检测器
            analysis = await self.enhanced_ambiguity_detector.detect_ambiguity(
                candidates, user_input, conversation_context
            )
            
            # 如果检测到歧义，筛选有效候选
            if analysis.is_ambiguous:
                # 使用原有的基本过滤逻辑作为后备
                if threshold is None:
                    threshold = self.ambiguity_threshold
                
                min_confidence = 0.5
                sorted_candidates = sorted(candidates, key=lambda x: x['confidence'], reverse=True)
                
                ambiguous_candidates = []
                first_confidence = sorted_candidates[0]['confidence']
                
                for candidate in sorted_candidates:
                    if (candidate['confidence'] >= min_confidence and 
                        first_confidence - candidate['confidence'] <= threshold):
                        ambiguous_candidates.append(candidate)
                
                logger.info(f"增强歧义检测: 歧义得分={analysis.ambiguity_score:.3f}, "
                           f"主要类型={analysis.primary_type.value if analysis.primary_type else 'None'}, "
                           f"候选数={len(ambiguous_candidates)}")
                
                return True, ambiguous_candidates[:5], analysis
            
            return False, [], analysis
            
        except Exception as e:
            logger.error(f"歧义检测失败: {str(e)}")
            # 回退到基本检测
            return await self._basic_ambiguity_detection(candidates, threshold)
    
    async def _basic_ambiguity_detection(self, candidates: List[Dict], 
                                       threshold: float = None) -> Tuple[bool, List[Dict], AmbiguityAnalysis]:
        """基本歧义检测（回退方法）"""
        try:
            if not candidates or len(candidates) < 2:
                return False, [], AmbiguityAnalysis(
                    is_ambiguous=False,
                    ambiguity_score=0.0,
                    primary_type=None,
                    signals=[],
                    candidates=candidates,
                    recommended_action="proceed",
                    analysis_metadata={"method": "basic_fallback"}
                )
            
            # 使用默认阈值
            if threshold is None:
                threshold = self.ambiguity_threshold
            
            # 按置信度排序
            sorted_candidates = sorted(candidates, key=lambda x: x['confidence'], reverse=True)
            
            # 检查前两个候选的置信度差异
            first_confidence = sorted_candidates[0]['confidence']
            second_confidence = sorted_candidates[1]['confidence']
            confidence_diff = first_confidence - second_confidence
            
            # 如果差异小于阈值且都超过最低置信度，认为有歧义
            min_confidence = 0.5
            is_ambiguous = (confidence_diff < threshold and 
                          first_confidence >= min_confidence and 
                          second_confidence >= min_confidence)
            
            if is_ambiguous:
                # 收集所有满足条件的候选
                ambiguous_candidates = []
                for candidate in sorted_candidates:
                    if (candidate['confidence'] >= min_confidence and 
                        first_confidence - candidate['confidence'] <= threshold):
                        ambiguous_candidates.append(candidate)
                
                logger.info(f"基本歧义检测: {len(ambiguous_candidates)}个候选, "
                           f"置信度差异: {confidence_diff:.3f}")
                
                # 创建基本的歧义分析结果
                from src.core.ambiguity_detector import AmbiguityType
                basic_analysis = AmbiguityAnalysis(
                    is_ambiguous=True,
                    ambiguity_score=1 - confidence_diff,
                    primary_type=AmbiguityType.CONFIDENCE,
                    signals=[],
                    candidates=ambiguous_candidates[:5],
                    recommended_action="disambiguate",
                    analysis_metadata={"method": "basic", "confidence_diff": confidence_diff}
                )
                
                return True, ambiguous_candidates[:5], basic_analysis
            
            # 无歧义情况
            basic_analysis = AmbiguityAnalysis(
                is_ambiguous=False,
                ambiguity_score=confidence_diff,
                primary_type=AmbiguityType.CONFIDENCE,
                signals=[],
                candidates=candidates,
                recommended_action="proceed",
                analysis_metadata={"method": "basic", "confidence_diff": confidence_diff}
            )
            
            return False, [], basic_analysis
            
        except Exception as e:
            logger.error(f"基本歧义检测失败: {str(e)}")
            return False, [], AmbiguityAnalysis(
                is_ambiguous=False,
                ambiguity_score=0.0,
                primary_type=None,
                signals=[],
                candidates=candidates,
                recommended_action="proceed",
                analysis_metadata={"error": str(e)}
            )
    
    async def _attempt_auto_resolution(self, 
                                     candidates: List[Dict],
                                     ambiguity_analysis: AmbiguityAnalysis,
                                     context: Optional[Dict],
                                     user_input: str) -> Optional[Intent]:
        """
        尝试自动解决歧义
        
        Args:
            candidates: 候选意图列表
            ambiguity_analysis: 歧义分析结果
            context: 对话上下文
            user_input: 用户输入
            
        Returns:
            Optional[Intent]: 自动解决的意图，如果无法自动解决则返回None
        """
        try:
            if not context:
                return None
            
            # 构建解决上下文
            resolution_context = ResolutionContext(
                user_id=context.get('user_id', ''),
                conversation_id=context.get('conversation_id', 0),
                ambiguity_analysis=ambiguity_analysis,
                candidates=candidates,
                conversation_history=context.get('history', []),
                user_preferences=context.get('user_preferences', {}),
                time_constraints=context.get('time_constraints', {}),
                current_session_data=context
            )
            
            # 使用多策略解决器
            resolved_intent, resolution_attempt = await self.multi_strategy_resolver.resolve_ambiguity(
                resolution_context
            )
            
            # 记录解决尝试
            logger.info(f"自动解决尝试: 策略={resolution_attempt.strategy.value}, "
                       f"结果={resolution_attempt.result.value}, "
                       f"置信度={resolution_attempt.confidence:.3f}")
            
            return resolved_intent
            
        except Exception as e:
            logger.error(f"自动解决歧义失败: {str(e)}")
            return None
    
    def _serialize_result(self, result: IntentRecognitionResult) -> Dict:
        """序列化识别结果用于缓存"""
        return result.to_legacy_intent_service_format()
    
    def _deserialize_result(self, data: Dict) -> IntentRecognitionResult:
        """从缓存数据反序列化识别结果"""
        intent = None
        if data.get('intent_name') or data.get('intent'):
            intent_name = data.get('intent_name') or data.get('intent')
            try:
                intent = Intent.get(Intent.intent_name == intent_name)
            except:
                pass
        
        return IntentRecognitionResult.from_intent_service_result(
            intent=intent,
            confidence=data.get('confidence', 0.0),
            alternatives=data.get('alternatives', []),
            is_ambiguous=data.get('is_ambiguous', False)
        )
    
    async def get_confidence_statistics(self) -> Dict:
        """获取置信度统计信息"""
        try:
            stats = self.confidence_manager.get_confidence_statistics()
            
            # 添加系统级统计
            system_stats = {
                'total_intents_tracked': len(stats),
                'active_adaptive_thresholds': len([
                    intent for intent, data in stats.items()
                    if data.get('adaptive_threshold') is not None
                ]),
                'average_success_rate': sum([
                    data['success_rate'] for data in stats.values()
                ]) / len(stats) if stats else 0,
                'threshold_configuration': {
                    'global_intent_threshold': settings.INTENT_CONFIDENCE_THRESHOLD,
                    'ambiguity_threshold': settings.AMBIGUITY_DETECTION_THRESHOLD,
                    'confidence_levels': {
                        'high': settings.CONFIDENCE_THRESHOLD_HIGH,
                        'medium': settings.CONFIDENCE_THRESHOLD_MEDIUM,
                        'low': settings.CONFIDENCE_THRESHOLD_LOW,
                        'reject': settings.CONFIDENCE_THRESHOLD_REJECT
                    }
                }
            }
            
            return {
                'system_stats': system_stats,
                'intent_stats': stats,
                'timestamp': str(datetime.now())
            }
            
        except Exception as e:
            logger.error(f"获取置信度统计失败: {str(e)}")
            return {'error': str(e)}
    
    async def update_intent_feedback(self, intent_name: str, confidence: float, 
                                   user_confirmed: bool, user_id: str = "anonymous") -> bool:
        """
        更新意图反馈用于自适应阈值调整
        
        Args:
            intent_name: 意图名称
            confidence: 置信度
            user_confirmed: 用户是否确认了意图
            user_id: 用户ID
            
        Returns:
            bool: 更新是否成功
        """
        try:
            self.confidence_manager.update_intent_statistics(
                intent_name, confidence, user_confirmed
            )
            
            # 记录意图反馈审计日志
            try:
                intent = await self._get_intent_by_name(intent_name)
                await self.audit_service.log_config_change(
                    table_name="intent_feedback",
                    record_id=intent.id if intent else 0,
                    action=AuditAction.UPDATE,
                    old_values={"intent_name": intent_name, "previous_confidence": confidence},
                    new_values={
                        "intent_name": intent_name,
                        "confidence": confidence,
                        "user_confirmed": user_confirmed,
                        "updated_at": datetime.now().isoformat()
                    },
                    operator_id=user_id
                )
            except Exception as audit_error:
                logger.warning(f"记录意图反馈审计日志失败: {str(audit_error)}")
            
            logger.info(f"更新意图反馈: {intent_name} (置信度: {confidence:.3f}, 确认: {user_confirmed})")
            return True
        except Exception as e:
            logger.error(f"更新意图反馈失败: {str(e)}")
            return False
    
    async def generate_clarification_question(self,
                                           candidates: List[Dict],
                                           clarification_type: ClarificationType,
                                           context: Optional[Dict] = None,
                                           user_id: Optional[str] = None) -> str:
        """
        生成澄清问题（TASK-023实现）
        
        Args:
            candidates: 候选意图列表
            clarification_type: 澄清类型
            context: 对话上下文
            user_id: 用户ID
            
        Returns:
            str: 澄清问题文本
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
                'failed_attempts': context.get('failed_attempts', 0) if context else 0
            }
            
            # 使用澄清问题生成器
            clarification_question = await self.clarification_generator.generate_clarification_question(
                clarification_type, candidates, clarification_context, user_id
            )
            
            logger.info(f"生成澄清问题: 类型={clarification_type.value}, "
                       f"风格={clarification_question.style.value}, "
                       f"复杂度={clarification_question.complexity.value}")
            
            return clarification_question.question_text
            
        except Exception as e:
            logger.error(f"澄清问题生成失败: {str(e)}")
            return await self._generate_fallback_clarification_question(candidates, clarification_type)
    
    async def _generate_fallback_clarification_question(self,
                                                       candidates: List[Dict],
                                                       clarification_type: ClarificationType) -> str:
        """
        生成回退澄清问题
        
        Args:
            candidates: 候选意图列表
            clarification_type: 澄清类型
            
        Returns:
            str: 回退澄清问题
        """
        try:
            if clarification_type == ClarificationType.INTENT:
                if len(candidates) > 1:
                    return "请明确您想要做什么：" + "、".join([c.get('display_name', c['intent_name']) for c in candidates[:3]])
                else:
                    return "请明确您的具体需求。"
            
            elif clarification_type == ClarificationType.SLOT:
                return "请提供更多详细信息。"
            
            elif clarification_type == ClarificationType.VALUE:
                return "请确认您输入的信息是否正确。"
            
            elif clarification_type == ClarificationType.AMBIGUITY:
                return "您的请求可能有多种理解，请澄清您的具体意图。"
            
            elif clarification_type == ClarificationType.CONTEXT:
                return "请提供更多上下文信息以便更好地理解您的需求。"
            
            elif clarification_type == ClarificationType.CONFIRMATION:
                return "请确认这是您想要的操作吗？"
            
            elif clarification_type == ClarificationType.INCOMPLETE_INFO:
                return "您的信息不完整，请补充必要的详细信息。"
            
            elif clarification_type == ClarificationType.CONFLICTING_INFO:
                return "您的信息存在冲突，请重新确认。"
            
            else:
                return "请澄清您的需求。"
            
        except Exception as e:
            logger.error(f"回退澄清问题生成失败: {str(e)}")
            return "请明确您的需求。"
    
    async def detect_clarification_need(self,
                                      user_input: str,
                                      context: Optional[Dict] = None) -> Tuple[bool, Optional[ClarificationType], str]:
        """
        检测是否需要澄清
        
        Args:
            user_input: 用户输入
            context: 对话上下文
            
        Returns:
            Tuple[bool, Optional[ClarificationType], str]: (是否需要澄清, 澄清类型, 描述)
        """
        try:
            # 检查用户输入长度
            if len(user_input.strip()) < 3:
                return True, ClarificationType.INCOMPLETE_INFO, "用户输入过短"
            
            # 检查是否包含模糊词汇
            ambiguous_words = ['这个', '那个', '它', '他', '她', '某个', '什么', '哪个', '怎么']
            user_input_lower = user_input.lower()
            if any(word in user_input_lower for word in ambiguous_words):
                return True, ClarificationType.AMBIGUITY, "包含模糊词汇"
            
            # 检查是否包含冲突信息
            conflicting_patterns = [
                ('是', '不是'), ('要', '不要'), ('可以', '不可以'),
                ('需要', '不需要'), ('想要', '不想要')
            ]
            for pos, neg in conflicting_patterns:
                if pos in user_input_lower and neg in user_input_lower:
                    return True, ClarificationType.CONFLICTING_INFO, "包含冲突信息"
            
            # 检查上下文一致性
            if context:
                current_intent = context.get('current_intent')
                if current_intent:
                    # 简单的上下文一致性检查
                    intent_keywords = {
                        'book_flight': ['机票', '飞机', '航班', '预订'],
                        'check_balance': ['余额', '查询', '账户', '银行']
                    }
                    
                    if current_intent in intent_keywords:
                        keywords = intent_keywords[current_intent]
                        if not any(keyword in user_input_lower for keyword in keywords):
                            return True, ClarificationType.CONTEXT, "上下文不一致"
            
            return False, None, "无需澄清"
            
        except Exception as e:
            logger.error(f"澄清需求检测失败: {str(e)}")
            return False, None, f"检测失败: {str(e)}"
    
    async def resolve_ambiguity_with_feedback(self, conversation_id: int, candidates: List[Dict], 
                                            user_choice: str, user_feedback: Optional[str] = None,
                                            user_id: Optional[str] = None,
                                            context: Optional[Dict] = None) -> Tuple[Optional[Intent], ParseResult]:
        """
        基于反馈的歧义解决（TASK-024增强功能）
        
        Args:
            conversation_id: 对话ID
            candidates: 候选意图列表
            user_choice: 用户选择
            user_feedback: 用户反馈
            user_id: 用户ID
            context: 对话上下文
            
        Returns:
            Tuple[Optional[Intent], ParseResult]: (解决后的意图, 解析结果)
        """
        try:
            # 获取之前的解析结果（如果有）
            previous_result = context.get('previous_parse_result') if context else None
            
            # 使用反馈增强的解析
            parse_result = await self.advanced_choice_parser.parse_with_feedback(
                user_choice, candidates, previous_result, user_feedback
            )
            
            # 更新用户模式
            if user_id:
                success = parse_result.selected_option is not None
                self.advanced_choice_parser.update_user_pattern(user_id, parse_result, success)
            
            logger.info(f"反馈增强解析结果: 类型={parse_result.choice_type.value}, "
                       f"置信度={parse_result.confidence:.3f}")
            
            # 处理解析结果
            if parse_result.selected_option:
                selected_intent = await self._get_intent_from_parse_result(parse_result, candidates)
                if selected_intent:
                    # 更新歧义记录
                    try:
                        ambiguity = IntentAmbiguity.get(
                            IntentAmbiguity.conversation == conversation_id,
                            IntentAmbiguity.resolved_at.is_null(True)
                        )
                        ambiguity.resolve_with_choice(selected_intent.intent_name)
                        ambiguity.save()
                    except IntentAmbiguity.DoesNotExist:
                        pass
                    
                    return selected_intent, parse_result
            
            return None, parse_result
            
        except Exception as e:
            logger.error(f"反馈增强歧义解决失败: {str(e)}")
            # 回退到标准解析
            return await self.resolve_ambiguity(conversation_id, candidates, user_choice, user_id, context)
    
    async def parse_multi_intent_choice(self, conversation_id: int, candidates: List[Dict],
                                      user_choice: str, user_id: Optional[str] = None,
                                      context: Optional[Dict] = None) -> Tuple[List[Intent], List[ParseResult]]:
        """
        多意图选择解析（TASK-024新增功能）
        
        Args:
            conversation_id: 对话ID
            candidates: 候选意图列表
            user_choice: 用户选择
            user_id: 用户ID
            context: 对话上下文
            
        Returns:
            Tuple[List[Intent], List[ParseResult]]: (解决的意图列表, 解析结果列表)
        """
        try:
            # 使用多选解析
            parse_results = await self.advanced_choice_parser.parse_multi_choice(
                user_choice, candidates, allow_multiple=True
            )
            
            selected_intents = []
            
            for parse_result in parse_results:
                if parse_result.selected_option:
                    intent = await self._get_intent_from_parse_result(parse_result, candidates)
                    if intent:
                        selected_intents.append(intent)
                        
                        # 更新用户模式
                        if user_id:
                            self.advanced_choice_parser.update_user_pattern(
                                user_id, parse_result, True
                            )
            
            logger.info(f"多意图解析结果: 解析到{len(selected_intents)}个意图")
            
            return selected_intents, parse_results
            
        except Exception as e:
            logger.error(f"多意图选择解析失败: {str(e)}")
            return [], []
    
    async def _find_potential_candidates_by_keywords(self, user_input: str) -> List[Dict]:
        """
        基于关键词找到潜在的候选意图
        
        Args:
            user_input: 用户输入
            
        Returns:
            List[Dict]: 潜在候选意图列表
        """
        candidates = []
        
        # 订票相关关键词映射
        keyword_mappings = {
            '订票': ['book_flight', 'book_train', 'book_movie'],
            '买票': ['book_flight', 'book_train', 'book_movie'],
            '预订': ['book_flight', 'book_train', 'book_movie'],
            '机票': ['book_flight'],
            '火车票': ['book_train'],
            '电影票': ['book_movie'],
            '航班': ['book_flight'],
            '火车': ['book_train'],
            '电影': ['book_movie'],
            '飞机': ['book_flight'],
            '余额': ['check_balance'],
            '查询': ['check_balance']
        }
        
        # 查找匹配的意图
        matched_intents = set()
        for keyword, intent_names in keyword_mappings.items():
            if keyword in user_input:
                matched_intents.update(intent_names)
        
        # 获取意图详情
        for intent_name in matched_intents:
            intent = await self._get_intent_by_name(intent_name)
            if intent and intent.is_active:
                candidates.append({
                    'intent_name': intent.intent_name,
                    'display_name': intent.display_name,
                    'confidence': 0.6  # 给一个中等置信度
                })
        
        return candidates

    def get_user_choice_analytics(self, user_id: str) -> Dict[str, Any]:
        """
        获取用户选择解析分析（TASK-024新增功能）
        
        Args:
            user_id: 用户ID
            
        Returns:
            Dict[str, Any]: 用户选择分析报告
        """
        try:
            # 获取解析分析
            analytics = self.advanced_choice_parser.get_parsing_analytics(user_id)
            
            # 获取用户模式统计
            parser_stats = self.advanced_choice_parser.get_parser_statistics()
            user_patterns = parser_stats.get('user_patterns_summary', {}).get(user_id, {})
            
            # 组合分析报告
            report = {
                'user_id': user_id,
                'parsing_analytics': analytics,
                'user_patterns': user_patterns,
                'recommendations': self._generate_user_choice_recommendations(analytics, user_patterns)
            }
            
            return report
            
        except Exception as e:
            logger.error(f"获取用户选择分析失败: {str(e)}")
            return {'error': str(e)}
    
    def _generate_user_choice_recommendations(self, analytics: Dict, patterns: Dict) -> List[str]:
        """
        生成用户选择建议（TASK-024新增功能）
        
        Args:
            analytics: 解析分析数据
            patterns: 用户模式数据
            
        Returns:
            List[str]: 建议列表
        """
        recommendations = []
        
        try:
            # 基于成功率的建议
            success_rate = analytics.get('success_rate', 0)
            if success_rate < 0.7:
                recommendations.append("建议使用数字选择（如：1、2、3）以提高解析成功率")
            
            # 基于选择类型偏好的建议
            choice_types = analytics.get('choice_type_distribution', {})
            if choice_types:
                most_used = max(choice_types.items(), key=lambda x: x[1])
                if most_used[0] == 'uncertain':
                    recommendations.append("建议提供更明确的选择描述")
                elif most_used[0] == 'textual':
                    recommendations.append("您习惯使用文本描述，系统将优化文本匹配")
            
            # 基于置信度的建议
            avg_confidence = analytics.get('avg_confidence', 0)
            if avg_confidence < 0.6:
                recommendations.append("建议使用更具体的关键词描述您的需求")
            
            # 基于趋势的建议
            trend = analytics.get('trend', 'stable')
            if trend == 'declining':
                recommendations.append("最近的选择解析效果有所下降，建议回顾之前成功的选择模式")
            elif trend == 'improving':
                recommendations.append("您的选择模式正在改善，请继续保持")
            
        except Exception as e:
            logger.error(f"生成用户选择建议失败: {str(e)}")
        
        return recommendations
    
    async def check_intent_confirmation_needed(self, intent: Intent, confidence: float,
                                             extracted_slots: Dict[str, Any],
                                             user_id: str, conversation_id: int,
                                             context: Optional[Dict] = None) -> Tuple[bool, str, ConfirmationStrategy]:
        """
        检查是否需要意图确认（TASK-025实现）
        
        Args:
            intent: 识别的意图
            confidence: 置信度
            extracted_slots: 提取的槽位
            user_id: 用户ID
            conversation_id: 对话ID
            context: 对话上下文
            
        Returns:
            Tuple[bool, str, ConfirmationStrategy]: (是否需要确认, 确认请求ID, 确认策略)
        """
        try:
            # 构建确认上下文
            confirmation_context = ConfirmationContext(
                user_id=user_id,
                conversation_id=conversation_id,
                session_id=f"session_{user_id}_{conversation_id}",
                intent_name=intent.intent_name,
                confidence=confidence,
                risk_level=RiskLevel.LOW,  # 将在should_confirm_intent中评估
                triggers=[],
                extracted_slots=extracted_slots,
                conversation_history=context.get('history', []) if context else [],
                user_preferences=context.get('user_preferences', {}) if context else {},
                system_policies=context.get('system_policies', {}) if context else {},
                metadata={
                    'intent_display_name': intent.display_name,
                    'recognition_time': datetime.now().isoformat()
                }
            )
            
            # 评估是否需要确认
            should_confirm, triggers, strategy = await self.confirmation_manager.should_confirm_intent(
                confirmation_context
            )
            
            if should_confirm:
                # 创建确认请求
                confirmation_request = await self.confirmation_manager.create_confirmation_request(
                    confirmation_context, strategy, triggers
                )
                
                logger.info(f"意图确认已触发: {intent.intent_name}, 请求ID: {confirmation_request.request_id}")
                
                return True, confirmation_request.request_id, strategy
            
            return False, "", ConfirmationStrategy.IMPLICIT
            
        except Exception as e:
            logger.error(f"检查意图确认失败: {str(e)}")
            # 保守处理，对高置信度不确认，低置信度确认
            if confidence < 0.7:
                return True, "", ConfirmationStrategy.IMPLICIT
            return False, "", ConfirmationStrategy.IMPLICIT
    
    async def process_intent_confirmation(self, request_id: str, user_response: str,
                                        response_time: float = 0.0) -> Tuple[bool, Optional[Intent], Dict[str, Any]]:
        """
        处理意图确认响应（TASK-025实现）
        
        Args:
            request_id: 确认请求ID
            user_response: 用户响应
            response_time: 响应时间
            
        Returns:
            Tuple[bool, Optional[Intent], Dict[str, Any]]: (是否确认成功, 确认的意图, 结果详情)
        """
        try:
            # 处理确认响应
            confirmation_result = await self.confirmation_manager.process_confirmation_response(
                request_id, user_response, response_time
            )
            
            # 根据确认结果处理
            if confirmation_result.response_type == ConfirmationResponse.CONFIRMED:
                # 用户确认了意图
                if confirmation_result.confirmed_intent:
                    intent = await self._get_intent_by_name(confirmation_result.confirmed_intent)
                    if intent:
                        # 更新意图反馈
                        original_confidence = confirmation_result.metadata.get('original_confidence', 0.5)
                        new_confidence = min(0.95, original_confidence + confirmation_result.confidence_adjustment)
                        await self.update_intent_feedback(intent.intent_name, new_confidence, True)
                        
                        logger.info(f"意图确认成功: {intent.intent_name}")
                        
                        return True, intent, {
                            'confirmed_slots': confirmation_result.confirmed_slots,
                            'confidence_adjustment': confirmation_result.confidence_adjustment,
                            'explanation': confirmation_result.explanation
                        }
            
            elif confirmation_result.response_type == ConfirmationResponse.MODIFIED:
                # 用户要求修改
                if confirmation_result.confirmed_intent:
                    intent = await self._get_intent_by_name(confirmation_result.confirmed_intent)
                    if intent:
                        logger.info(f"意图确认并修改: {intent.intent_name}, 修改: {confirmation_result.modifications}")
                        
                        return True, intent, {
                            'confirmed_slots': confirmation_result.confirmed_slots,
                            'modifications': confirmation_result.modifications,
                            'confidence_adjustment': confirmation_result.confidence_adjustment,
                            'explanation': confirmation_result.explanation
                        }
            
            elif confirmation_result.response_type == ConfirmationResponse.REJECTED:
                # 用户拒绝了意图
                logger.info(f"意图确认被拒绝: {request_id}")
                
                return False, None, {
                    'rejection_reason': confirmation_result.explanation,
                    'confidence_adjustment': confirmation_result.confidence_adjustment
                }
            
            # 其他情况（不清楚、超时等）
            logger.warning(f"意图确认结果不明确: {confirmation_result.response_type.value}")
            
            return False, None, {
                'unclear_reason': confirmation_result.explanation,
                'response_type': confirmation_result.response_type.value,
                'retry_used': confirmation_result.retry_used
            }
            
        except Exception as e:
            logger.error(f"处理意图确认失败: {str(e)}")
            return False, None, {'error': str(e)}
    
    def get_confirmation_request_text(self, request_id: str) -> Optional[str]:
        """
        获取确认请求文本（TASK-025实现）
        
        Args:
            request_id: 确认请求ID
            
        Returns:
            Optional[str]: 确认请求文本
        """
        try:
            active_requests = self.confirmation_manager.active_requests
            if request_id in active_requests:
                return active_requests[request_id].confirmation_text
            return None
            
        except Exception as e:
            logger.error(f"获取确认请求文本失败: {str(e)}")
            return None
    
    async def cancel_confirmation_request(self, request_id: str) -> bool:
        """
        取消确认请求（TASK-025实现）
        
        Args:
            request_id: 确认请求ID
            
        Returns:
            bool: 取消是否成功
        """
        try:
            if request_id in self.confirmation_manager.active_requests:
                # 移除活跃请求
                del self.confirmation_manager.active_requests[request_id]
                
                logger.info(f"确认请求已取消: {request_id}")
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"取消确认请求失败: {str(e)}")
            return False
    
    def get_intent_confirmation_statistics(self) -> Dict[str, Any]:
        """
        获取意图确认统计信息（TASK-025实现）
        
        Returns:
            Dict[str, Any]: 确认统计信息
        """
        try:
            return self.confirmation_manager.get_confirmation_statistics()
            
        except Exception as e:
            logger.error(f"获取确认统计失败: {str(e)}")
            return {'error': str(e)}
    
    def get_user_confirmation_profile(self, user_id: str) -> Dict[str, Any]:
        """
        获取用户确认画像（TASK-025实现）
        
        Args:
            user_id: 用户ID
            
        Returns:
            Dict[str, Any]: 用户确认画像
        """
        try:
            return self.confirmation_manager.get_user_confirmation_profile(user_id)
            
        except Exception as e:
            logger.error(f"获取用户确认画像失败: {str(e)}")
            return {'error': str(e)}
    
    async def create_intent(self, intent_data: Dict[str, Any], operator_id: str = "system") -> Optional[Intent]:
        """
        创建意图并记录审计日志
        
        Args:
            intent_data: 意图数据
            operator_id: 操作者ID
            
        Returns:
            Optional[Intent]: 创建的意图对象
        """
        try:
            # 创建意图
            intent = Intent.create(**intent_data)
            
            # 记录审计日志
            await self.audit_service.log_config_change(
                table_name="intents",
                record_id=intent.id,
                action=AuditAction.INSERT,
                old_values=None,
                new_values=intent_data,
                operator_id=operator_id
            )
            
            # 失效相关缓存
            await self.cache_invalidation_service.invalidate_intent_caches(
                intent.id, intent.intent_name, CacheInvalidationType.CONFIG_CHANGE
            )
            
            logger.info(f"意图创建成功: {intent.intent_name} by {operator_id}")
            return intent
            
        except Exception as e:
            logger.error(f"创建意图失败: {str(e)}")
            return None
    
    async def update_intent(self, intent_id: int, updates: Dict[str, Any], 
                          operator_id: str = "system") -> bool:
        """
        更新意图并记录审计日志
        
        Args:
            intent_id: 意图ID
            updates: 更新数据
            operator_id: 操作者ID
            
        Returns:
            bool: 更新是否成功
        """
        try:
            # 获取原始数据
            intent = Intent.get_by_id(intent_id)
            old_values = {
                'intent_name': intent.intent_name,
                'display_name': intent.display_name,
                'description': intent.description,
                'is_active': intent.is_active,
                'priority': intent.priority,
                'confidence_threshold': float(intent.confidence_threshold),
                'updated_at': intent.updated_at.isoformat() if intent.updated_at else None
            }
            
            # 执行更新
            query = Intent.update(**updates).where(Intent.id == intent_id)
            query.execute()
            
            # 获取更新后的数据
            updated_intent = Intent.get_by_id(intent_id)
            new_values = {
                'intent_name': updated_intent.intent_name,
                'display_name': updated_intent.display_name,
                'description': updated_intent.description,
                'is_active': updated_intent.is_active,
                'priority': updated_intent.priority,
                'confidence_threshold': float(updated_intent.confidence_threshold),
                'updated_at': updated_intent.updated_at.isoformat() if updated_intent.updated_at else None
            }
            
            # 记录审计日志
            await self.audit_service.log_config_change(
                table_name="intents",
                record_id=intent_id,
                action=AuditAction.UPDATE,
                old_values=old_values,
                new_values=new_values,
                operator_id=operator_id
            )
            
            # 失效相关缓存
            await self.cache_invalidation_service.invalidate_intent_caches(
                intent_id, updated_intent.intent_name, CacheInvalidationType.CONFIG_CHANGE
            )
            
            logger.info(f"意图更新成功: {intent_id} by {operator_id}")
            return True
            
        except Exception as e:
            logger.error(f"更新意图失败: {str(e)}")
            return False
    
    async def delete_intent(self, intent_id: int, operator_id: str = "system") -> bool:
        """
        删除意图并记录审计日志
        
        Args:
            intent_id: 意图ID
            operator_id: 操作者ID
            
        Returns:
            bool: 删除是否成功
        """
        try:
            # 获取要删除的意图信息
            intent = Intent.get_by_id(intent_id)
            old_values = {
                'intent_name': intent.intent_name,
                'display_name': intent.display_name,
                'description': intent.description,
                'is_active': intent.is_active,
                'priority': intent.priority,
                'confidence_threshold': float(intent.confidence_threshold),
                'deleted_at': datetime.now().isoformat()
            }
            
            # 执行软删除或硬删除
            intent.delete_instance()
            
            # 记录审计日志
            await self.audit_service.log_config_change(
                table_name="intents",
                record_id=intent_id,
                action=AuditAction.DELETE,
                old_values=old_values,
                new_values=None,
                operator_id=operator_id
            )
            
            # 失效相关缓存
            await self.cache_invalidation_service.invalidate_intent_caches(
                intent_id, intent.intent_name, CacheInvalidationType.CONFIG_CHANGE
            )
            
            logger.info(f"意图删除成功: {intent_id} by {operator_id}")
            return True
            
        except Exception as e:
            logger.error(f"删除意图失败: {str(e)}")
            return False
    
    async def bulk_update_intents(self, updates: List[Dict[str, Any]], 
                                operator_id: str = "system") -> Dict[str, Any]:
        """
        批量更新意图
        
        Args:
            updates: 更新列表，每个元素包含 {'id': int, 'data': dict}
            operator_id: 操作者ID
            
        Returns:
            Dict[str, Any]: 批量更新结果
        """
        try:
            successful = 0
            failed = 0
            errors = []
            
            for update in updates:
                intent_id = update.get('id')
                update_data = update.get('data', {})
                
                if await self.update_intent(intent_id, update_data, operator_id):
                    successful += 1
                else:
                    failed += 1
                    errors.append(f"Intent {intent_id} update failed")
            
            result = {
                'successful': successful,
                'failed': failed,
                'total': len(updates),
                'errors': errors,
                'timestamp': datetime.now().isoformat()
            }
            
            # 记录批量操作审计日志
            await self.audit_service.log_config_change(
                table_name="intents",
                record_id=0,
                action=AuditAction.UPDATE,
                old_values=None,
                new_values=result,
                operator_id=operator_id
            )
            
            logger.info(f"批量更新意图完成: {successful}/{len(updates)} 成功")
            return result
            
        except Exception as e:
            logger.error(f"批量更新意图失败: {str(e)}")
            return {
                'successful': 0,
                'failed': len(updates),
                'total': len(updates),
                'errors': [str(e)],
                'timestamp': datetime.now().isoformat()
            }
    
    async def recognize_intent_with_confirmation(self, user_input: str, user_id: str,
                                               context: Dict = None) -> Tuple[IntentRecognitionResult, Optional[str]]:
        """
        带确认机制的意图识别（TASK-025实现）
        
        Args:
            user_input: 用户输入文本
            user_id: 用户ID
            context: 对话上下文
            
        Returns:
            Tuple[IntentRecognitionResult, Optional[str]]: (识别结果, 确认请求ID)
        """
        try:
            # 首先进行正常的意图识别
            recognition_result = await self.recognize_intent(user_input, user_id, context)
            
            if recognition_result.intent and not recognition_result.is_ambiguous:
                # 检查是否需要确认
                conversation_id = context.get('conversation_id', 0) if context else 0
                extracted_slots = context.get('extracted_slots', {}) if context else {}
                
                need_confirmation, request_id, strategy = await self.check_intent_confirmation_needed(
                    recognition_result.intent,
                    recognition_result.confidence,
                    extracted_slots,
                    user_id,
                    conversation_id,
                    context
                )
                
                if need_confirmation:
                    # 需要确认，返回识别结果和确认请求ID
                    logger.info(f"意图识别完成，需要用户确认: {recognition_result.intent.intent_name}")
                    return recognition_result, request_id
            
            # 不需要确认，直接返回识别结果
            return recognition_result, None
            
        except Exception as e:
            logger.error(f"带确认的意图识别失败: {str(e)}")
            # 返回错误的识别结果
            error_result = IntentRecognitionResult(None, 0.0)
            return error_result, None
    
    # V2.2重构: 新增配置管理方法，集成事件驱动架构
    async def create_intent_config(
        self,
        intent_data: Dict[str, Any],
        operator_id: str = 'system'
    ) -> Dict[str, Any]:
        """
        创建意图配置（使用统一的配置管理服务）
        
        Args:
            intent_data: 意图数据
            operator_id: 操作者ID
            
        Returns:
            Dict: 操作结果
        """
        result = await self.config_management_service.create_intent(intent_data, operator_id)
        return result.to_dict()
    
    async def update_intent_config(
        self,
        intent_id: int,
        updates: Dict[str, Any],
        operator_id: str = 'system'
    ) -> Dict[str, Any]:
        """
        更新意图配置（使用统一的配置管理服务）
        
        Args:
            intent_id: 意图ID
            updates: 更新数据
            operator_id: 操作者ID
            
        Returns:
            Dict: 操作结果
        """
        result = await self.config_management_service.update_intent(intent_id, updates, operator_id)
        return result.to_dict()
    
    async def delete_intent_config(
        self,
        intent_id: int,
        operator_id: str = 'system'
    ) -> Dict[str, Any]:
        """
        删除意图配置（使用统一的配置管理服务）
        
        Args:
            intent_id: 意图ID
            operator_id: 操作者ID
            
        Returns:
            Dict: 操作结果
        """
        result = await self.config_management_service.delete_intent(intent_id, operator_id)
        return result.to_dict()
    
    async def get_intent_change_history(
        self,
        intent_id: Optional[int] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        获取意图配置变更历史
        
        Args:
            intent_id: 意图ID，为None时获取所有意图的变更历史
            limit: 返回记录数限制
            
        Returns:
            List[Dict]: 变更历史列表
        """
        return await self.config_management_service.get_config_change_history(
            entity_type='intent',
            entity_id=intent_id,
            limit=limit
        )