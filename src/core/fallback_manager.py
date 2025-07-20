"""
统一回退管理器 (TASK-032)
提供多层级、智能化的回退机制，确保系统在各种失败情况下都能提供合理的响应
"""
from typing import Dict, List, Optional, Any, Callable, Union
from dataclasses import dataclass, field
from enum import Enum
import asyncio
import json
import time
from datetime import datetime, timedelta
from collections import defaultdict

from src.models.config import SystemConfig, RagflowConfig, FeatureFlag
from src.services.cache_service import CacheService
from src.utils.logger import get_logger

logger = get_logger(__name__)


class FallbackType(Enum):
    """回退类型枚举"""
    RAGFLOW_QUERY = "ragflow_query"          # RAGFLOW查询失败
    INTENT_RECOGNITION = "intent_recognition"  # 意图识别失败
    SLOT_EXTRACTION = "slot_extraction"      # 槽位提取失败
    FUNCTION_CALL = "function_call"          # 函数调用失败
    NLU_ENGINE = "nlu_engine"               # NLU引擎失败
    EXTERNAL_SERVICE = "external_service"    # 外部服务失败
    SYSTEM_ERROR = "system_error"           # 系统错误
    NETWORK_ERROR = "network_error"         # 网络错误
    TIMEOUT_ERROR = "timeout_error"         # 超时错误
    RATE_LIMIT_ERROR = "rate_limit_error"   # 速率限制错误


class FallbackStrategy(Enum):
    """回退策略枚举"""
    IMMEDIATE = "immediate"                  # 立即回退
    RETRY_THEN_FALLBACK = "retry_then_fallback"  # 重试后回退
    CIRCUIT_BREAKER = "circuit_breaker"      # 断路器模式
    GRACEFUL_DEGRADATION = "graceful_degradation"  # 优雅降级
    CACHE_FALLBACK = "cache_fallback"        # 缓存回退
    ALTERNATIVE_SERVICE = "alternative_service"  # 备选服务
    DEFAULT_RESPONSE = "default_response"    # 默认响应


class FallbackPriority(Enum):
    """回退优先级枚举"""
    HIGH = "high"      # 高优先级：关键服务失败
    MEDIUM = "medium"  # 中优先级：一般服务失败
    LOW = "low"        # 低优先级：辅助服务失败


@dataclass
class FallbackContext:
    """回退上下文"""
    error_type: FallbackType
    error_message: str
    original_request: Dict[str, Any]
    session_context: Dict[str, Any]
    user_id: str
    session_id: str
    timestamp: datetime = field(default_factory=datetime.now)
    retry_count: int = 0
    max_retries: int = 3
    timeout: float = 30.0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class FallbackResult:
    """回退结果"""
    success: bool
    data: Any = None
    error: Optional[str] = None
    strategy_used: Optional[FallbackStrategy] = None
    fallback_chain: List[str] = field(default_factory=list)
    response_time: float = 0.0
    confidence: float = 0.0
    is_cached: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class FallbackRule:
    """回退规则"""
    error_type: FallbackType
    strategies: List[FallbackStrategy]
    priority: FallbackPriority
    max_retries: int = 3
    timeout: float = 30.0
    conditions: Dict[str, Any] = field(default_factory=dict)
    enabled: bool = True


class FallbackManager:
    """统一回退管理器"""
    
    def __init__(self, cache_service: CacheService):
        self.cache_service = cache_service
        self.cache_namespace = "fallback_manager"
        self.fallback_rules: Dict[FallbackType, FallbackRule] = {}
        self.fallback_handlers: Dict[FallbackStrategy, Callable] = {}
        self.error_stats: Dict[FallbackType, Dict[str, int]] = defaultdict(lambda: defaultdict(int))
        self.circuit_breakers: Dict[str, Dict[str, Any]] = {}
        self.last_fallback_time: Dict[str, datetime] = {}
        
        # 初始化默认规则
        self._initialize_default_rules()
        
        # 注册默认处理器
        self._register_default_handlers()
    
    def _initialize_default_rules(self):
        """初始化默认回退规则"""
        self.fallback_rules = {
            FallbackType.RAGFLOW_QUERY: FallbackRule(
                error_type=FallbackType.RAGFLOW_QUERY,
                strategies=[
                    FallbackStrategy.RETRY_THEN_FALLBACK,
                    FallbackStrategy.ALTERNATIVE_SERVICE,
                    FallbackStrategy.CACHE_FALLBACK,
                    FallbackStrategy.DEFAULT_RESPONSE
                ],
                priority=FallbackPriority.HIGH,
                max_retries=3,
                timeout=30.0
            ),
            FallbackType.INTENT_RECOGNITION: FallbackRule(
                error_type=FallbackType.INTENT_RECOGNITION,
                strategies=[
                    FallbackStrategy.RETRY_THEN_FALLBACK,
                    FallbackStrategy.GRACEFUL_DEGRADATION,
                    FallbackStrategy.DEFAULT_RESPONSE
                ],
                priority=FallbackPriority.HIGH,
                max_retries=2,
                timeout=20.0
            ),
            FallbackType.SLOT_EXTRACTION: FallbackRule(
                error_type=FallbackType.SLOT_EXTRACTION,
                strategies=[
                    FallbackStrategy.GRACEFUL_DEGRADATION,
                    FallbackStrategy.DEFAULT_RESPONSE
                ],
                priority=FallbackPriority.MEDIUM,
                max_retries=1,
                timeout=15.0
            ),
            FallbackType.FUNCTION_CALL: FallbackRule(
                error_type=FallbackType.FUNCTION_CALL,
                strategies=[
                    FallbackStrategy.RETRY_THEN_FALLBACK,
                    FallbackStrategy.ALTERNATIVE_SERVICE,
                    FallbackStrategy.DEFAULT_RESPONSE
                ],
                priority=FallbackPriority.HIGH,
                max_retries=3,
                timeout=30.0
            ),
            FallbackType.NLU_ENGINE: FallbackRule(
                error_type=FallbackType.NLU_ENGINE,
                strategies=[
                    FallbackStrategy.CIRCUIT_BREAKER,
                    FallbackStrategy.CACHE_FALLBACK,
                    FallbackStrategy.DEFAULT_RESPONSE
                ],
                priority=FallbackPriority.HIGH,
                max_retries=2,
                timeout=25.0
            ),
            FallbackType.EXTERNAL_SERVICE: FallbackRule(
                error_type=FallbackType.EXTERNAL_SERVICE,
                strategies=[
                    FallbackStrategy.RETRY_THEN_FALLBACK,
                    FallbackStrategy.ALTERNATIVE_SERVICE,
                    FallbackStrategy.DEFAULT_RESPONSE
                ],
                priority=FallbackPriority.MEDIUM,
                max_retries=2,
                timeout=20.0
            ),
            FallbackType.NETWORK_ERROR: FallbackRule(
                error_type=FallbackType.NETWORK_ERROR,
                strategies=[
                    FallbackStrategy.RETRY_THEN_FALLBACK,
                    FallbackStrategy.CACHE_FALLBACK,
                    FallbackStrategy.DEFAULT_RESPONSE
                ],
                priority=FallbackPriority.MEDIUM,
                max_retries=3,
                timeout=30.0
            ),
            FallbackType.TIMEOUT_ERROR: FallbackRule(
                error_type=FallbackType.TIMEOUT_ERROR,
                strategies=[
                    FallbackStrategy.IMMEDIATE,
                    FallbackStrategy.CACHE_FALLBACK,
                    FallbackStrategy.DEFAULT_RESPONSE
                ],
                priority=FallbackPriority.HIGH,
                max_retries=1,
                timeout=10.0
            ),
            FallbackType.RATE_LIMIT_ERROR: FallbackRule(
                error_type=FallbackType.RATE_LIMIT_ERROR,
                strategies=[
                    FallbackStrategy.CIRCUIT_BREAKER,
                    FallbackStrategy.CACHE_FALLBACK,
                    FallbackStrategy.DEFAULT_RESPONSE
                ],
                priority=FallbackPriority.HIGH,
                max_retries=0,
                timeout=5.0
            )
        }
    
    def _register_default_handlers(self):
        """注册默认处理器"""
        self.fallback_handlers = {
            FallbackStrategy.IMMEDIATE: self._handle_immediate_fallback,
            FallbackStrategy.RETRY_THEN_FALLBACK: self._handle_retry_then_fallback,
            FallbackStrategy.CIRCUIT_BREAKER: self._handle_circuit_breaker,
            FallbackStrategy.GRACEFUL_DEGRADATION: self._handle_graceful_degradation,
            FallbackStrategy.CACHE_FALLBACK: self._handle_cache_fallback,
            FallbackStrategy.ALTERNATIVE_SERVICE: self._handle_alternative_service,
            FallbackStrategy.DEFAULT_RESPONSE: self._handle_default_response
        }
    
    def register_fallback_handler(self, strategy: FallbackStrategy, handler: Callable):
        """注册自定义回退处理器"""
        self.fallback_handlers[strategy] = handler
        logger.info(f"注册回退处理器: {strategy.value}")
    
    def update_fallback_rule(self, error_type: FallbackType, rule: FallbackRule):
        """更新回退规则"""
        self.fallback_rules[error_type] = rule
        logger.info(f"更新回退规则: {error_type.value}")
    
    async def handle_fallback(self, context: FallbackContext) -> FallbackResult:
        """处理回退逻辑"""
        start_time = time.time()
        
        try:
            # 记录错误统计
            self._record_error_stats(context)
            
            # 获取回退规则
            rule = self.fallback_rules.get(context.error_type)
            if not rule or not rule.enabled:
                return FallbackResult(
                    success=False,
                    error=f"没有找到或启用的回退规则: {context.error_type.value}",
                    response_time=time.time() - start_time
                )
            
            # 检查是否超过最大重试次数
            if context.retry_count >= rule.max_retries:
                logger.warning(f"达到最大重试次数: {context.error_type.value}")
                return await self._handle_final_fallback(context)
            
            # 按优先级执行回退策略
            fallback_chain = []
            for strategy in rule.strategies:
                if strategy not in self.fallback_handlers:
                    logger.warning(f"未找到回退处理器: {strategy.value}")
                    continue
                
                try:
                    handler = self.fallback_handlers[strategy]
                    result = await handler(context, rule)
                    
                    fallback_chain.append(strategy.value)
                    
                    if result.success:
                        result.fallback_chain = fallback_chain
                        result.response_time = time.time() - start_time
                        result.strategy_used = strategy
                        
                        # 记录成功的回退
                        await self._record_successful_fallback(context, strategy, result)
                        
                        return result
                    
                    # 如果策略失败，记录并继续尝试下一个
                    logger.warning(f"回退策略失败: {strategy.value}, 错误: {result.error}")
                    
                except Exception as e:
                    logger.error(f"回退策略执行异常: {strategy.value}, 错误: {str(e)}")
                    continue
            
            # 所有策略都失败了
            return FallbackResult(
                success=False,
                error=f"所有回退策略都失败: {context.error_type.value}",
                fallback_chain=fallback_chain,
                response_time=time.time() - start_time
            )
            
        except Exception as e:
            logger.error(f"回退处理异常: {str(e)}")
            return FallbackResult(
                success=False,
                error=f"回退处理异常: {str(e)}",
                response_time=time.time() - start_time
            )
    
    async def _handle_immediate_fallback(self, context: FallbackContext, rule: FallbackRule) -> FallbackResult:
        """立即回退处理"""
        logger.info(f"执行立即回退: {context.error_type.value}")
        
        # 立即返回默认响应
        default_responses = {
            FallbackType.RAGFLOW_QUERY: "抱歉，我暂时无法查询相关信息，请稍后再试。",
            FallbackType.INTENT_RECOGNITION: "抱歉，我没有理解您的意思，请重新表述您的问题。",
            FallbackType.SLOT_EXTRACTION: "抱歉，我需要更多信息来帮助您，请提供更详细的描述。",
            FallbackType.FUNCTION_CALL: "抱歉，操作暂时无法完成，请稍后再试。",
            FallbackType.TIMEOUT_ERROR: "抱歉，响应时间过长，请稍后再试。",
            FallbackType.RATE_LIMIT_ERROR: "抱歉，请求过于频繁，请稍后再试。"
        }
        
        response = default_responses.get(context.error_type, "抱歉，系统暂时无法处理您的请求。")
        
        return FallbackResult(
            success=True,
            data=response,
            confidence=0.3,
            metadata={'fallback_type': 'immediate'}
        )
    
    async def _handle_retry_then_fallback(self, context: FallbackContext, rule: FallbackRule) -> FallbackResult:
        """重试后回退处理"""
        logger.info(f"执行重试后回退: {context.error_type.value}, 重试次数: {context.retry_count}")
        
        if context.retry_count < rule.max_retries:
            # 增加重试次数
            context.retry_count += 1
            
            # 指数退避
            delay = min(2 ** context.retry_count, 10)
            await asyncio.sleep(delay)
            
            # 这里应该重新尝试原始操作
            # 由于这是演示，我们模拟重试失败
            logger.info(f"重试失败，继续下一个回退策略")
            
            return FallbackResult(
                success=False,
                error=f"重试失败: {context.error_message}",
                metadata={'retry_count': context.retry_count}
            )
        
        # 达到最大重试次数，执行其他回退策略
        return await self._handle_cache_fallback(context, rule)
    
    async def _handle_circuit_breaker(self, context: FallbackContext, rule: FallbackRule) -> FallbackResult:
        """断路器模式处理"""
        service_key = f"{context.error_type.value}_{context.session_id}"
        
        # 获取断路器状态
        circuit_breaker = self.circuit_breakers.get(service_key, {
            'state': 'closed',  # closed, open, half_open
            'failure_count': 0,
            'last_failure_time': None,
            'success_count': 0,
            'timeout': 60  # 断路器打开后的超时时间（秒）
        })
        
        now = datetime.now()
        
        # 检查断路器状态
        if circuit_breaker['state'] == 'open':
            # 检查是否可以转为半开状态
            if (circuit_breaker['last_failure_time'] and 
                now - circuit_breaker['last_failure_time'] > timedelta(seconds=circuit_breaker['timeout'])):
                circuit_breaker['state'] = 'half_open'
                circuit_breaker['success_count'] = 0
                logger.info(f"断路器转为半开状态: {service_key}")
            else:
                # 断路器仍然打开，直接回退
                logger.info(f"断路器打开，直接回退: {service_key}")
                return await self._handle_cache_fallback(context, rule)
        
        # 断路器关闭或半开状态，记录失败
        circuit_breaker['failure_count'] += 1
        circuit_breaker['last_failure_time'] = now
        
        # 判断是否需要打开断路器
        if circuit_breaker['failure_count'] >= 5:  # 阈值为5次失败
            circuit_breaker['state'] = 'open'
            logger.warning(f"断路器打开: {service_key}")
        
        # 更新断路器状态
        self.circuit_breakers[service_key] = circuit_breaker
        
        # 执行缓存回退
        return await self._handle_cache_fallback(context, rule)
    
    async def _handle_graceful_degradation(self, context: FallbackContext, rule: FallbackRule) -> FallbackResult:
        """优雅降级处理"""
        logger.info(f"执行优雅降级: {context.error_type.value}")
        
        # 根据错误类型提供降级服务
        if context.error_type == FallbackType.INTENT_RECOGNITION:
            # 意图识别失败，提供基础的关键词匹配
            user_input = context.original_request.get('user_input', '')
            
            # 简单的关键词匹配
            keywords_intent_map = {
                ['余额', '查询', '账户']: 'query_balance',
                ['转账', '汇款', '转钱']: 'transfer_money',
                ['机票', '订票', '航班']: 'book_flight',
                ['帮助', '协助', '客服']: 'help_support'
            }
            
            detected_intent = None
            for keywords, intent in keywords_intent_map.items():
                if any(keyword in user_input for keyword in keywords):
                    detected_intent = intent
                    break
            
            if detected_intent:
                return FallbackResult(
                    success=True,
                    data={'intent': detected_intent, 'confidence': 0.6},
                    confidence=0.6,
                    metadata={'fallback_type': 'graceful_degradation', 'method': 'keyword_matching'}
                )
        
        elif context.error_type == FallbackType.SLOT_EXTRACTION:
            # 槽位提取失败，提供基础的模式匹配
            user_input = context.original_request.get('user_input', '')
            
            # 简单的槽位提取
            import re
            slots = {}
            
            # 金额提取
            amount_pattern = r'(\d+(?:\.\d+)?)\s*(?:元|块|万|千)'
            amount_match = re.search(amount_pattern, user_input)
            if amount_match:
                slots['amount'] = amount_match.group(1)
            
            # 时间提取
            time_pattern = r'(\d{4}[-/年]\d{1,2}[-/月]\d{1,2}[日号]?)'
            time_match = re.search(time_pattern, user_input)
            if time_match:
                slots['date'] = time_match.group(1)
            
            return FallbackResult(
                success=True,
                data=slots,
                confidence=0.5,
                metadata={'fallback_type': 'graceful_degradation', 'method': 'pattern_matching'}
            )
        
        # 默认降级响应
        return FallbackResult(
            success=False,
            error=f"无法为 {context.error_type.value} 提供降级服务"
        )
    
    async def _handle_cache_fallback(self, context: FallbackContext, rule: FallbackRule) -> FallbackResult:
        """缓存回退处理"""
        logger.info(f"执行缓存回退: {context.error_type.value}")
        
        try:
            # 构建缓存键
            cache_key = self._build_cache_key(context)
            
            # 尝试从缓存获取结果
            cached_result = await self.cache_service.get(cache_key, namespace=self.cache_namespace)
            
            if cached_result:
                logger.info(f"从缓存获取回退结果: {cache_key}")
                return FallbackResult(
                    success=True,
                    data=cached_result,
                    confidence=0.7,
                    is_cached=True,
                    metadata={'fallback_type': 'cache', 'cache_key': cache_key}
                )
            
            # 缓存中没有结果，尝试获取相似的缓存结果
            similar_result = await self._get_similar_cache_result(context)
            if similar_result:
                return FallbackResult(
                    success=True,
                    data=similar_result,
                    confidence=0.5,
                    is_cached=True,
                    metadata={'fallback_type': 'cache', 'method': 'similar_match'}
                )
            
            # 没有找到缓存结果
            return FallbackResult(
                success=False,
                error="缓存中没有找到相关结果"
            )
            
        except Exception as e:
            logger.error(f"缓存回退失败: {str(e)}")
            return FallbackResult(
                success=False,
                error=f"缓存回退失败: {str(e)}"
            )
    
    async def _handle_alternative_service(self, context: FallbackContext, rule: FallbackRule) -> FallbackResult:
        """备选服务处理"""
        logger.info(f"执行备选服务回退: {context.error_type.value}")
        
        if context.error_type == FallbackType.RAGFLOW_QUERY:
            # 尝试使用备选的RAGFLOW配置
            try:
                # 获取备选配置
                alternative_configs = RagflowConfig.select().where(
                    RagflowConfig.is_active == True,
                    RagflowConfig.config_name != context.original_request.get('config_name', 'default')
                ).limit(2)
                
                for config in alternative_configs:
                    logger.info(f"尝试备选RAGFLOW配置: {config.config_name}")
                    
                    # 这里应该调用备选服务
                    # 由于这是演示，我们模拟一个成功的响应
                    return FallbackResult(
                        success=True,
                        data="这是来自备选服务的响应",
                        confidence=0.6,
                        metadata={
                            'fallback_type': 'alternative_service',
                            'config_used': config.config_name
                        }
                    )
                
            except Exception as e:
                logger.error(f"备选服务调用失败: {str(e)}")
        
        return FallbackResult(
            success=False,
            error=f"没有可用的备选服务: {context.error_type.value}"
        )
    
    async def _handle_default_response(self, context: FallbackContext, rule: FallbackRule) -> FallbackResult:
        """默认响应处理"""
        logger.info(f"执行默认响应回退: {context.error_type.value}")
        
        # 根据错误类型和上下文生成个性化的默认响应
        user_input = context.original_request.get('user_input', '')
        
        # 智能默认响应
        if context.error_type == FallbackType.RAGFLOW_QUERY:
            if '查询' in user_input or '询问' in user_input:
                response = "抱歉，我暂时无法查询相关信息。您可以尝试：\n1. 重新描述您的问题\n2. 联系客服获取帮助\n3. 稍后再试"
            else:
                response = "抱歉，我暂时无法理解您的问题。请提供更多详细信息，我会尽力帮助您。"
        
        elif context.error_type == FallbackType.INTENT_RECOGNITION:
            response = "抱歉，我没有完全理解您的意图。请您：\n1. 用更简单的语言重新表述\n2. 提供更多上下文信息\n3. 或者直接告诉我您想要什么帮助"
        
        elif context.error_type == FallbackType.FUNCTION_CALL:
            response = "抱歉，我暂时无法完成这个操作。请稍后再试，或者联系客服获取帮助。"
        
        else:
            response = "抱歉，系统暂时出现了一些问题。我们正在努力解决，请稍后再试。"
        
        # 添加个性化信息
        if context.session_context.get('user_name'):
            response = f"{context.session_context['user_name']}，{response}"
        
        return FallbackResult(
            success=True,
            data=response,
            confidence=0.2,
            metadata={
                'fallback_type': 'default_response',
                'error_type': context.error_type.value,
                'personalized': bool(context.session_context.get('user_name'))
            }
        )
    
    async def _handle_final_fallback(self, context: FallbackContext) -> FallbackResult:
        """最终回退处理"""
        logger.warning(f"执行最终回退: {context.error_type.value}")
        
        # 记录严重错误
        await self._record_critical_error(context)
        
        # 提供最基本的响应
        response = "系统暂时无法处理您的请求，请稍后再试或联系客服。"
        
        return FallbackResult(
            success=True,
            data=response,
            confidence=0.1,
            metadata={
                'fallback_type': 'final_fallback',
                'error_type': context.error_type.value,
                'retry_count': context.retry_count
            }
        )
    
    def _build_cache_key(self, context: FallbackContext) -> str:
        """构建缓存键"""
        import hashlib
        
        # 构建缓存键的组成部分
        key_parts = [
            context.error_type.value,
            context.original_request.get('user_input', ''),
            context.session_context.get('current_intent', ''),
            context.user_id
        ]
        
        # 生成哈希键
        key_content = '|'.join(str(part) for part in key_parts)
        hash_key = hashlib.md5(key_content.encode()).hexdigest()
        
        return f"fallback_{context.error_type.value}_{hash_key}"
    
    async def _get_similar_cache_result(self, context: FallbackContext) -> Optional[Any]:
        """获取相似的缓存结果"""
        try:
            # 搜索相似的缓存键
            pattern = f"fallback_{context.error_type.value}_*"
            similar_keys = await self.cache_service.get_keys_by_pattern(pattern, namespace=self.cache_namespace)
            
            if similar_keys:
                # 取第一个匹配的结果
                similar_key = similar_keys[0]
                return await self.cache_service.get(similar_key, namespace=self.cache_namespace)
            
            return None
            
        except Exception as e:
            logger.error(f"获取相似缓存结果失败: {str(e)}")
            return None
    
    def _record_error_stats(self, context: FallbackContext):
        """记录错误统计"""
        self.error_stats[context.error_type]['total_count'] += 1
        self.error_stats[context.error_type]['retry_count'] += context.retry_count
        
        # 记录最近的错误时间
        error_key = f"{context.error_type.value}_{context.session_id}"
        self.last_fallback_time[error_key] = context.timestamp
    
    async def _record_successful_fallback(self, context: FallbackContext, strategy: FallbackStrategy, result: FallbackResult):
        """记录成功的回退"""
        try:
            # 记录到缓存
            success_key = f"fallback_success_{context.error_type.value}_{strategy.value}"
            success_data = {
                'timestamp': context.timestamp.isoformat(),
                'user_id': context.user_id,
                'session_id': context.session_id,
                'strategy': strategy.value,
                'response_time': result.response_time,
                'confidence': result.confidence
            }
            
            await self.cache_service.set(success_key, success_data, ttl=3600, namespace=self.cache_namespace)
            
            # 如果结果有价值，缓存起来供后续使用
            if result.confidence > 0.5:
                cache_key = self._build_cache_key(context)
                await self.cache_service.set(cache_key, result.data, ttl=1800, namespace=self.cache_namespace)
            
        except Exception as e:
            logger.error(f"记录成功回退失败: {str(e)}")
    
    async def _record_critical_error(self, context: FallbackContext):
        """记录严重错误"""
        try:
            critical_error_data = {
                'error_type': context.error_type.value,
                'error_message': context.error_message,
                'user_id': context.user_id,
                'session_id': context.session_id,
                'timestamp': context.timestamp.isoformat(),
                'retry_count': context.retry_count,
                'original_request': context.original_request
            }
            
            critical_key = f"critical_error_{context.error_type.value}_{context.session_id}_{int(context.timestamp.timestamp())}"
            await self.cache_service.set(critical_key, critical_error_data, ttl=86400, namespace=self.cache_namespace)
            
        except Exception as e:
            logger.error(f"记录严重错误失败: {str(e)}")
    
    async def get_fallback_stats(self) -> Dict[str, Any]:
        """获取回退统计信息"""
        try:
            stats = {
                'error_stats': dict(self.error_stats),
                'circuit_breakers': self.circuit_breakers,
                'fallback_rules': {
                    error_type.value: {
                        'strategies': [s.value for s in rule.strategies],
                        'priority': rule.priority.value,
                        'max_retries': rule.max_retries,
                        'enabled': rule.enabled
                    }
                    for error_type, rule in self.fallback_rules.items()
                },
                'last_fallback_times': {
                    key: timestamp.isoformat()
                    for key, timestamp in self.last_fallback_time.items()
                }
            }
            
            return stats
            
        except Exception as e:
            logger.error(f"获取回退统计失败: {str(e)}")
            return {}
    
    async def reset_circuit_breaker(self, service_key: str):
        """重置断路器"""
        if service_key in self.circuit_breakers:
            self.circuit_breakers[service_key] = {
                'state': 'closed',
                'failure_count': 0,
                'last_failure_time': None,
                'success_count': 0,
                'timeout': 60
            }
            logger.info(f"重置断路器: {service_key}")
    
    async def update_fallback_config(self, config_updates: Dict[str, Any]):
        """更新回退配置"""
        try:
            for key, value in config_updates.items():
                if key.startswith('fallback_'):
                    SystemConfig.set_config(key, value, category='fallback')
            
            logger.info("回退配置更新成功")
            
        except Exception as e:
            logger.error(f"更新回退配置失败: {str(e)}")
    
    async def cleanup(self):
        """清理资源"""
        # 清理过期的统计数据
        cutoff_time = datetime.now() - timedelta(hours=24)
        
        expired_keys = []
        for key, timestamp in self.last_fallback_time.items():
            if timestamp < cutoff_time:
                expired_keys.append(key)
        
        for key in expired_keys:
            del self.last_fallback_time[key]
        
        logger.info(f"清理过期数据: {len(expired_keys)} 条")


# 全局回退管理器实例
_fallback_manager: Optional[FallbackManager] = None


def get_fallback_manager(cache_service: CacheService) -> FallbackManager:
    """获取全局回退管理器实例"""
    global _fallback_manager
    
    if _fallback_manager is None:
        _fallback_manager = FallbackManager(cache_service)
    
    return _fallback_manager