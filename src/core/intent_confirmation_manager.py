"""
意图确认管理器
实现智能意图确认机制，确保用户意图的准确理解和执行
"""

from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime, timedelta
import json
import asyncio
from collections import defaultdict

from ..utils.logger import get_logger

logger = get_logger(__name__)


class ConfirmationTrigger(Enum):
    """确认触发条件"""
    LOW_CONFIDENCE = "low_confidence"           # 低置信度
    HIGH_RISK = "high_risk"                     # 高风险操作
    USER_REQUEST = "user_request"               # 用户要求
    POLICY_REQUIRED = "policy_required"         # 策略要求
    AMBIGUOUS_CONTEXT = "ambiguous_context"     # 上下文模糊
    FIRST_TIME_USER = "first_time_user"         # 首次用户
    CRITICAL_ACTION = "critical_action"         # 关键操作
    DATA_SENSITIVE = "data_sensitive"           # 敏感数据


class ConfirmationStrategy(Enum):
    """确认策略"""
    IMPLICIT = "implicit"                       # 隐式确认
    EXPLICIT = "explicit"                       # 显式确认
    PROGRESSIVE = "progressive"                 # 渐进式确认
    DETAILED = "detailed"                       # 详细确认
    QUICK = "quick"                            # 快速确认
    INTERACTIVE = "interactive"                 # 交互式确认


class ConfirmationResponse(Enum):
    """确认响应类型"""
    CONFIRMED = "confirmed"                     # 已确认
    REJECTED = "rejected"                       # 已拒绝
    MODIFIED = "modified"                       # 已修改
    UNCLEAR = "unclear"                         # 不清楚
    TIMEOUT = "timeout"                         # 超时
    SKIPPED = "skipped"                         # 跳过


class RiskLevel(Enum):
    """风险等级"""
    LOW = "low"                                # 低风险
    MEDIUM = "medium"                          # 中等风险
    HIGH = "high"                              # 高风险
    CRITICAL = "critical"                      # 严重风险


@dataclass
class ConfirmationContext:
    """确认上下文"""
    user_id: str
    conversation_id: int
    session_id: str
    intent_name: str
    confidence: float
    risk_level: RiskLevel
    triggers: List[ConfirmationTrigger]
    extracted_slots: Dict[str, Any]
    conversation_history: List[Dict[str, Any]]
    user_preferences: Dict[str, Any]
    system_policies: Dict[str, Any]
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ConfirmationRequest:
    """确认请求"""
    request_id: str
    context: ConfirmationContext
    strategy: ConfirmationStrategy
    confirmation_text: str
    expected_responses: List[str]
    timeout_seconds: int
    retry_count: int
    created_at: datetime
    expires_at: datetime
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ConfirmationResult:
    """确认结果"""
    request_id: str
    response_type: ConfirmationResponse
    user_response: Optional[str]
    confirmed_intent: Optional[str]
    confirmed_slots: Dict[str, Any]
    modifications: Dict[str, Any]
    confidence_adjustment: float
    processing_time: float
    retry_used: int
    explanation: str
    timestamp: datetime
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ConfirmationPolicy:
    """确认策略"""
    intent_patterns: List[str]
    risk_levels: List[RiskLevel]
    triggers: List[ConfirmationTrigger]
    strategy: ConfirmationStrategy
    min_confidence_threshold: float
    max_confirmation_attempts: int
    timeout_seconds: int
    enabled: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)


class IntentConfirmationManager:
    """意图确认管理器"""
    
    def __init__(self, settings):
        self.settings = settings
        
        # 确认请求管理
        self.active_requests: Dict[str, ConfirmationRequest] = {}
        self.completed_requests: List[ConfirmationResult] = []
        
        # 确认策略配置
        self.confirmation_policies: List[ConfirmationPolicy] = []
        self._initialize_default_policies()
        
        # 风险评估配置
        self.risk_patterns = {
            RiskLevel.CRITICAL: [
                'transfer_money', 'delete_account', 'cancel_subscription',
                'pay_bill', 'make_payment', 'authorize_transaction'
            ],
            RiskLevel.HIGH: [
                'book_flight', 'book_hotel', 'modify_booking', 
                'change_password', 'update_profile'
            ],
            RiskLevel.MEDIUM: [
                'check_balance', 'view_statement', 'get_info'
            ],
            RiskLevel.LOW: [
                'get_help', 'show_menu', 'greet'
            ]
        }
        
        # 确认模板
        self.confirmation_templates = {
            ConfirmationStrategy.EXPLICIT: {
                'simple': '您确定要{intent_action}吗？',
                'detailed': '请确认：您想要{intent_action}，具体信息为：{slot_details}',
                'risky': '这是一个重要操作：{intent_action}。请确认您要继续吗？'
            },
            ConfirmationStrategy.IMPLICIT: {
                'simple': '我理解您想要{intent_action}，对吗？',
                'detailed': '让我确认一下：{intent_action}，信息包括{slot_details}，这样对吗？'
            },
            ConfirmationStrategy.PROGRESSIVE: {
                'step1': '您是想要{intent_action}吗？',
                'step2': '好的，那么{slot_details}这些信息正确吗？',
                'step3': '最后确认一下，您要执行{intent_action}，对吗？'
            }
        }
        
        # 用户确认历史
        self.user_confirmation_history: Dict[str, List[Dict]] = defaultdict(list)
        
        # 统计信息
        self.confirmation_stats = {
            'total_requests': 0,
            'confirmed_count': 0,
            'rejected_count': 0,
            'timeout_count': 0,
            'avg_response_time': 0.0,
            'policy_triggers': defaultdict(int)
        }
    
    def _initialize_default_policies(self):
        """初始化默认确认策略"""
        default_policies = [
            # 高风险操作策略
            ConfirmationPolicy(
                intent_patterns=['transfer_*', 'pay_*', 'delete_*'],
                risk_levels=[RiskLevel.CRITICAL, RiskLevel.HIGH],
                triggers=[ConfirmationTrigger.HIGH_RISK, ConfirmationTrigger.CRITICAL_ACTION],
                strategy=ConfirmationStrategy.DETAILED,
                min_confidence_threshold=0.95,
                max_confirmation_attempts=2,
                timeout_seconds=60
            ),
            
            # 低置信度策略
            ConfirmationPolicy(
                intent_patterns=['*'],
                risk_levels=[RiskLevel.LOW, RiskLevel.MEDIUM, RiskLevel.HIGH],
                triggers=[ConfirmationTrigger.LOW_CONFIDENCE],
                strategy=ConfirmationStrategy.IMPLICIT,
                min_confidence_threshold=0.7,
                max_confirmation_attempts=1,
                timeout_seconds=30
            ),
            
            # 首次用户策略
            ConfirmationPolicy(
                intent_patterns=['book_*', 'transfer_*'],
                risk_levels=[RiskLevel.MEDIUM, RiskLevel.HIGH],
                triggers=[ConfirmationTrigger.FIRST_TIME_USER],
                strategy=ConfirmationStrategy.PROGRESSIVE,
                min_confidence_threshold=0.8,
                max_confirmation_attempts=2,
                timeout_seconds=45
            ),
            
            # 敏感数据策略
            ConfirmationPolicy(
                intent_patterns=['*'],
                risk_levels=[RiskLevel.HIGH, RiskLevel.CRITICAL],
                triggers=[ConfirmationTrigger.DATA_SENSITIVE],
                strategy=ConfirmationStrategy.EXPLICIT,
                min_confidence_threshold=0.85,
                max_confirmation_attempts=1,
                timeout_seconds=40
            )
        ]
        
        self.confirmation_policies.extend(default_policies)
    
    async def should_confirm_intent(self, context: ConfirmationContext) -> Tuple[bool, List[ConfirmationTrigger], ConfirmationStrategy]:
        """
        判断是否需要确认意图
        
        Args:
            context: 确认上下文
            
        Returns:
            Tuple[bool, List[ConfirmationTrigger], ConfirmationStrategy]: (是否需要确认, 触发条件, 建议策略)
        """
        try:
            triggers = []
            suggested_strategy = ConfirmationStrategy.IMPLICIT
            
            # 1. 检查置信度
            if context.confidence < 0.7:
                triggers.append(ConfirmationTrigger.LOW_CONFIDENCE)
            
            # 2. 检查风险等级
            risk_level = await self._assess_intent_risk(context.intent_name, context.extracted_slots)
            context.risk_level = risk_level
            
            if risk_level in [RiskLevel.HIGH, RiskLevel.CRITICAL]:
                triggers.append(ConfirmationTrigger.HIGH_RISK)
                suggested_strategy = ConfirmationStrategy.EXPLICIT
            
            # 3. 检查关键操作
            if await self._is_critical_action(context.intent_name, context.extracted_slots):
                triggers.append(ConfirmationTrigger.CRITICAL_ACTION)
                suggested_strategy = ConfirmationStrategy.DETAILED
            
            # 4. 检查敏感数据
            if await self._contains_sensitive_data(context.extracted_slots):
                triggers.append(ConfirmationTrigger.DATA_SENSITIVE)
            
            # 5. 检查首次用户
            if await self._is_first_time_user(context.user_id, context.intent_name):
                triggers.append(ConfirmationTrigger.FIRST_TIME_USER)
                suggested_strategy = ConfirmationStrategy.PROGRESSIVE
            
            # 6. 检查上下文模糊性
            if await self._is_context_ambiguous(context):
                triggers.append(ConfirmationTrigger.AMBIGUOUS_CONTEXT)
            
            # 7. 检查策略要求
            policy_required = await self._check_policy_requirements(context)
            if policy_required:
                triggers.append(ConfirmationTrigger.POLICY_REQUIRED)
            
            # 8. 应用确认策略
            applicable_policies = await self._get_applicable_policies(context, triggers)
            if applicable_policies:
                # 使用最严格的策略
                most_strict_policy = max(applicable_policies, key=lambda p: len(p.triggers))
                suggested_strategy = most_strict_policy.strategy
            
            # 决定是否需要确认
            should_confirm = len(triggers) > 0
            
            logger.info(f"意图确认评估: {context.intent_name}, 触发条件: {[t.value for t in triggers]}, "
                       f"需要确认: {should_confirm}, 建议策略: {suggested_strategy.value}")
            
            return should_confirm, triggers, suggested_strategy
            
        except Exception as e:
            logger.error(f"意图确认评估失败: {str(e)}")
            # 默认进行确认以确保安全
            return True, [ConfirmationTrigger.LOW_CONFIDENCE], ConfirmationStrategy.IMPLICIT
    
    async def create_confirmation_request(self, context: ConfirmationContext, 
                                        strategy: ConfirmationStrategy,
                                        triggers: List[ConfirmationTrigger]) -> ConfirmationRequest:
        """
        创建确认请求
        
        Args:
            context: 确认上下文
            strategy: 确认策略
            triggers: 触发条件
            
        Returns:
            ConfirmationRequest: 确认请求
        """
        try:
            request_id = f"conf_{context.user_id}_{context.conversation_id}_{datetime.now().timestamp()}"
            
            # 生成确认文本
            confirmation_text = await self._generate_confirmation_text(context, strategy)
            
            # 确定期望的响应
            expected_responses = self._get_expected_responses(strategy)
            
            # 确定超时时间
            timeout_seconds = await self._calculate_timeout(context, strategy)
            
            # 创建确认请求
            request = ConfirmationRequest(
                request_id=request_id,
                context=context,
                strategy=strategy,
                confirmation_text=confirmation_text,
                expected_responses=expected_responses,
                timeout_seconds=timeout_seconds,
                retry_count=0,
                created_at=datetime.now(),
                expires_at=datetime.now() + timedelta(seconds=timeout_seconds),
                metadata={
                    'triggers': [t.value for t in triggers],
                    'risk_level': context.risk_level.value,
                    'confidence': context.confidence
                }
            )
            
            # 保存活跃请求
            self.active_requests[request_id] = request
            
            # 更新统计
            self.confirmation_stats['total_requests'] += 1
            for trigger in triggers:
                self.confirmation_stats['policy_triggers'][trigger.value] += 1
            
            logger.info(f"创建确认请求: {request_id}, 策略: {strategy.value}, 超时: {timeout_seconds}秒")
            
            return request
            
        except Exception as e:
            logger.error(f"创建确认请求失败: {str(e)}")
            raise
    
    async def process_confirmation_response(self, request_id: str, 
                                          user_response: str,
                                          response_time: float = 0.0) -> ConfirmationResult:
        """
        处理确认响应
        
        Args:
            request_id: 请求ID
            user_response: 用户响应
            response_time: 响应时间
            
        Returns:
            ConfirmationResult: 确认结果
        """
        try:
            if request_id not in self.active_requests:
                raise ValueError(f"确认请求不存在: {request_id}")
            
            request = self.active_requests[request_id]
            
            # 检查是否超时
            if datetime.now() > request.expires_at:
                return await self._handle_timeout(request)
            
            # 解析用户响应
            response_type, confirmed_intent, confirmed_slots, modifications = await self._parse_confirmation_response(
                user_response, request
            )
            
            # 计算置信度调整
            confidence_adjustment = self._calculate_confidence_adjustment(
                response_type, request.context.confidence
            )
            
            # 创建确认结果
            result = ConfirmationResult(
                request_id=request_id,
                response_type=response_type,
                user_response=user_response,
                confirmed_intent=confirmed_intent,
                confirmed_slots=confirmed_slots,
                modifications=modifications,
                confidence_adjustment=confidence_adjustment,
                processing_time=response_time,
                retry_used=request.retry_count,
                explanation=self._generate_result_explanation(response_type, modifications),
                timestamp=datetime.now(),
                metadata={
                    'original_intent': request.context.intent_name,
                    'original_confidence': request.context.confidence,
                    'strategy_used': request.strategy.value
                }
            )
            
            # 更新用户确认历史
            await self._update_user_confirmation_history(request.context.user_id, result)
            
            # 更新统计
            await self._update_confirmation_statistics(result)
            
            # 移除活跃请求
            del self.active_requests[request_id]
            
            # 保存完成的请求
            self.completed_requests.append(result)
            
            # 保持历史记录不过长
            if len(self.completed_requests) > 1000:
                self.completed_requests = self.completed_requests[-1000:]
            
            logger.info(f"处理确认响应: {request_id}, 结果: {response_type.value}")
            
            return result
            
        except Exception as e:
            logger.error(f"处理确认响应失败: {str(e)}")
            # 返回错误结果
            return ConfirmationResult(
                request_id=request_id,
                response_type=ConfirmationResponse.UNCLEAR,
                user_response=user_response,
                confirmed_intent=None,
                confirmed_slots={},
                modifications={},
                confidence_adjustment=-0.2,
                processing_time=response_time,
                retry_used=0,
                explanation=f"处理失败: {str(e)}",
                timestamp=datetime.now()
            )
    
    async def _assess_intent_risk(self, intent_name: str, slots: Dict[str, Any]) -> RiskLevel:
        """评估意图风险等级"""
        try:
            # 基于意图名称的风险评估
            for risk_level, patterns in self.risk_patterns.items():
                for pattern in patterns:
                    if pattern.replace('*', '') in intent_name:
                        return risk_level
            
            # 基于槽位内容的风险评估
            risk_indicators = {
                'amount': ['金额', '数量', 'money', 'amount'],
                'account': ['账户', '卡号', 'account', 'card'],
                'personal': ['姓名', '身份证', 'name', 'id'],
                'time_sensitive': ['立即', '马上', 'urgent', 'asap']
            }
            
            for slot_name, slot_value in slots.items():
                slot_str = str(slot_value).lower()
                
                # 检查金额相关风险
                if any(indicator in slot_str for indicator in risk_indicators['amount']):
                    try:
                        # 尝试解析金额
                        import re
                        amount_match = re.search(r'(\d+(?:\.\d+)?)', slot_str)
                        if amount_match:
                            amount = float(amount_match.group(1))
                            if amount > 10000:
                                return RiskLevel.CRITICAL
                            elif amount > 1000:
                                return RiskLevel.HIGH
                            elif amount > 100:
                                return RiskLevel.MEDIUM
                    except:
                        pass
                
                # 检查其他风险指标
                if any(indicator in slot_str for indicator in risk_indicators['time_sensitive']):
                    return RiskLevel.HIGH
            
            return RiskLevel.LOW
            
        except Exception as e:
            logger.error(f"风险评估失败: {str(e)}")
            return RiskLevel.MEDIUM
    
    async def _is_critical_action(self, intent_name: str, slots: Dict[str, Any]) -> bool:
        """检查是否为关键操作"""
        critical_patterns = [
            'delete', 'remove', 'cancel', 'transfer', 'pay', 'authorize',
            'confirm', 'approve', 'execute', 'submit'
        ]
        
        return any(pattern in intent_name.lower() for pattern in critical_patterns)
    
    async def _contains_sensitive_data(self, slots: Dict[str, Any]) -> bool:
        """检查是否包含敏感数据"""
        sensitive_patterns = [
            r'\d{4}\s*\d{4}\s*\d{4}\s*\d{4}',  # 信用卡号
            r'\d{11}',                          # 手机号
            r'\d{15,18}',                       # 身份证号
            r'password', r'密码', r'pwd'          # 密码相关
        ]
        
        import re
        for slot_value in slots.values():
            slot_str = str(slot_value)
            for pattern in sensitive_patterns:
                if re.search(pattern, slot_str, re.IGNORECASE):
                    return True
        
        return False
    
    async def _is_first_time_user(self, user_id: str, intent_name: str) -> bool:
        """检查是否为首次使用该意图的用户"""
        try:
            user_history = self.user_confirmation_history.get(user_id, [])
            
            # 检查用户是否之前使用过该意图
            for history_item in user_history:
                if history_item.get('intent_name') == intent_name:
                    return False
            
            return len(user_history) < 3  # 少于3次交互认为是新用户
            
        except Exception:
            return True  # 出错时保守处理
    
    async def _is_context_ambiguous(self, context: ConfirmationContext) -> bool:
        """检查上下文是否模糊"""
        try:
            # 检查槽位完整性
            required_slots_count = len(context.extracted_slots)
            if required_slots_count < 2:  # 槽位信息不足
                return True
            
            # 检查对话历史的一致性
            recent_intents = []
            for turn in context.conversation_history[-3:]:  # 检查最近3轮
                if 'intent' in turn:
                    recent_intents.append(turn['intent'])
            
            # 如果最近的意图都不同，可能存在上下文跳跃
            if len(set(recent_intents)) > 2:
                return True
            
            return False
            
        except Exception:
            return True  # 出错时保守处理
    
    async def _check_policy_requirements(self, context: ConfirmationContext) -> bool:
        """检查策略要求"""
        # 这里可以实现具体的业务策略检查
        # 例如：特定时间段、特定金额范围、特定用户群体等
        return False
    
    async def _get_applicable_policies(self, context: ConfirmationContext, 
                                     triggers: List[ConfirmationTrigger]) -> List[ConfirmationPolicy]:
        """获取适用的确认策略"""
        applicable_policies = []
        
        for policy in self.confirmation_policies:
            if not policy.enabled:
                continue
            
            # 检查意图模式匹配
            intent_match = False
            for pattern in policy.intent_patterns:
                if pattern == '*' or pattern.replace('*', '') in context.intent_name:
                    intent_match = True
                    break
            
            if not intent_match:
                continue
            
            # 检查风险等级匹配
            if context.risk_level not in policy.risk_levels:
                continue
            
            # 检查触发条件匹配
            if not any(trigger in policy.triggers for trigger in triggers):
                continue
            
            # 检查置信度阈值
            if context.confidence >= policy.min_confidence_threshold:
                continue
            
            applicable_policies.append(policy)
        
        return applicable_policies
    
    async def _generate_confirmation_text(self, context: ConfirmationContext, 
                                        strategy: ConfirmationStrategy) -> str:
        """生成确认文本"""
        try:
            # 获取意图显示名称
            intent_display = self._get_intent_display_name(context.intent_name)
            
            # 生成槽位详情
            slot_details = self._format_slot_details(context.extracted_slots)
            
            # 根据策略选择模板
            templates = self.confirmation_templates.get(strategy, {})
            
            # 根据风险等级选择具体模板
            if context.risk_level in [RiskLevel.HIGH, RiskLevel.CRITICAL]:
                template_key = 'risky'
            elif slot_details:
                template_key = 'detailed'
            else:
                template_key = 'simple'
            
            template = templates.get(template_key, templates.get('simple', '请确认您的操作'))
            
            # 格式化模板
            confirmation_text = template.format(
                intent_action=intent_display,
                slot_details=slot_details
            )
            
            return confirmation_text
            
        except Exception as e:
            logger.error(f"生成确认文本失败: {str(e)}")
            return f"请确认您要{context.intent_name}吗？"
    
    def _get_intent_display_name(self, intent_name: str) -> str:
        """获取意图显示名称"""
        display_names = {
            'book_flight': '预订机票',
            'check_balance': '查询余额',
            'transfer_money': '转账',
            'pay_bill': '缴费',
            'cancel_booking': '取消预订'
        }
        return display_names.get(intent_name, intent_name)
    
    def _format_slot_details(self, slots: Dict[str, Any]) -> str:
        """格式化槽位详情"""
        if not slots:
            return ""
        
        slot_display_names = {
            'departure_city': '出发城市',
            'arrival_city': '到达城市',
            'departure_date': '出发日期',
            'amount': '金额',
            'account_number': '账户号码'
        }
        
        details = []
        for slot_name, slot_value in slots.items():
            display_name = slot_display_names.get(slot_name, slot_name)
            details.append(f"{display_name}: {slot_value}")
        
        return "、".join(details)
    
    def _get_expected_responses(self, strategy: ConfirmationStrategy) -> List[str]:
        """获取期望的响应"""
        base_responses = ['是', '对', '确认', '好', '不是', '不对', '取消', '修改']
        
        if strategy == ConfirmationStrategy.DETAILED:
            base_responses.extend(['需要修改', '信息有误', '重新输入'])
        elif strategy == ConfirmationStrategy.QUICK:
            base_responses = ['是', '不是', 'y', 'n']
        
        return base_responses
    
    async def _calculate_timeout(self, context: ConfirmationContext, 
                               strategy: ConfirmationStrategy) -> int:
        """计算超时时间"""
        base_timeout = 30  # 基础30秒
        
        # 根据策略调整
        strategy_modifiers = {
            ConfirmationStrategy.QUICK: 0.5,
            ConfirmationStrategy.DETAILED: 1.5,
            ConfirmationStrategy.PROGRESSIVE: 2.0
        }
        
        modifier = strategy_modifiers.get(strategy, 1.0)
        timeout = int(base_timeout * modifier)
        
        # 根据风险等级调整
        if context.risk_level == RiskLevel.CRITICAL:
            timeout += 30  # 关键操作给更多思考时间
        
        return min(timeout, 120)  # 最长2分钟
    
    async def _parse_confirmation_response(self, user_response: str, 
                                         request: ConfirmationRequest) -> Tuple[ConfirmationResponse, Optional[str], Dict[str, Any], Dict[str, Any]]:
        """解析确认响应"""
        try:
            user_response = user_response.strip().lower()
            
            # 确认响应
            positive_patterns = ['是', '对', '确认', '好的', '可以', 'yes', 'y', '没错', '正确']
            if any(pattern in user_response for pattern in positive_patterns):
                return (ConfirmationResponse.CONFIRMED, 
                       request.context.intent_name,
                       request.context.extracted_slots,
                       {})
            
            # 拒绝响应
            negative_patterns = ['不是', '不对', '取消', '不要', 'no', 'n', '错了', '不同意']
            if any(pattern in user_response for pattern in negative_patterns):
                return (ConfirmationResponse.REJECTED, None, {}, {})
            
            # 修改响应
            modify_patterns = ['修改', '更改', '改成', '不是这个', '换成']
            if any(pattern in user_response for pattern in modify_patterns):
                # 尝试解析修改内容
                modifications = await self._extract_modifications(user_response, request.context)
                return (ConfirmationResponse.MODIFIED, 
                       request.context.intent_name,
                       request.context.extracted_slots,
                       modifications)
            
            # 不清楚的响应
            return (ConfirmationResponse.UNCLEAR, None, {}, {})
            
        except Exception as e:
            logger.error(f"解析确认响应失败: {str(e)}")
            return (ConfirmationResponse.UNCLEAR, None, {}, {})
    
    async def _extract_modifications(self, user_response: str, 
                                   context: ConfirmationContext) -> Dict[str, Any]:
        """提取修改内容"""
        modifications = {}
        
        try:
            # 简单的修改解析逻辑
            # 这里可以集成更复杂的NLP解析
            
            # 查找日期修改
            import re
            date_pattern = r'(\d{4}-\d{2}-\d{2}|\d{1,2}月\d{1,2}日|明天|后天)'
            date_matches = re.findall(date_pattern, user_response)
            if date_matches:
                modifications['departure_date'] = date_matches[0]
            
            # 查找城市修改
            city_keywords = ['到', '去', '从', '出发']
            for keyword in city_keywords:
                if keyword in user_response:
                    # 简单的城市提取逻辑
                    pass
            
            return modifications
            
        except Exception as e:
            logger.error(f"提取修改内容失败: {str(e)}")
            return {}
    
    def _calculate_confidence_adjustment(self, response_type: ConfirmationResponse, 
                                       original_confidence: float) -> float:
        """计算置信度调整"""
        adjustments = {
            ConfirmationResponse.CONFIRMED: 0.2,
            ConfirmationResponse.REJECTED: -0.5,
            ConfirmationResponse.MODIFIED: 0.0,
            ConfirmationResponse.UNCLEAR: -0.1,
            ConfirmationResponse.TIMEOUT: -0.3
        }
        
        return adjustments.get(response_type, 0.0)
    
    def _generate_result_explanation(self, response_type: ConfirmationResponse, 
                                   modifications: Dict[str, Any]) -> str:
        """生成结果解释"""
        explanations = {
            ConfirmationResponse.CONFIRMED: "用户确认了意图和参数",
            ConfirmationResponse.REJECTED: "用户拒绝了操作",
            ConfirmationResponse.MODIFIED: f"用户要求修改: {modifications}",
            ConfirmationResponse.UNCLEAR: "用户响应不明确",
            ConfirmationResponse.TIMEOUT: "用户响应超时"
        }
        
        return explanations.get(response_type, "未知响应类型")
    
    async def _handle_timeout(self, request: ConfirmationRequest) -> ConfirmationResult:
        """处理超时"""
        result = ConfirmationResult(
            request_id=request.request_id,
            response_type=ConfirmationResponse.TIMEOUT,
            user_response=None,
            confirmed_intent=None,
            confirmed_slots={},
            modifications={},
            confidence_adjustment=-0.3,
            processing_time=request.timeout_seconds,
            retry_used=request.retry_count,
            explanation="用户响应超时",
            timestamp=datetime.now()
        )
        
        # 移除活跃请求
        if request.request_id in self.active_requests:
            del self.active_requests[request.request_id]
        
        return result
    
    async def _update_user_confirmation_history(self, user_id: str, result: ConfirmationResult):
        """更新用户确认历史"""
        try:
            history_item = {
                'intent_name': result.confirmed_intent,
                'response_type': result.response_type.value,
                'timestamp': result.timestamp.isoformat(),
                'confidence_adjustment': result.confidence_adjustment
            }
            
            self.user_confirmation_history[user_id].append(history_item)
            
            # 保持历史记录不过长
            if len(self.user_confirmation_history[user_id]) > 50:
                self.user_confirmation_history[user_id] = self.user_confirmation_history[user_id][-50:]
                
        except Exception as e:
            logger.error(f"更新用户确认历史失败: {str(e)}")
    
    async def _update_confirmation_statistics(self, result: ConfirmationResult):
        """更新确认统计"""
        try:
            if result.response_type == ConfirmationResponse.CONFIRMED:
                self.confirmation_stats['confirmed_count'] += 1
            elif result.response_type == ConfirmationResponse.REJECTED:
                self.confirmation_stats['rejected_count'] += 1
            elif result.response_type == ConfirmationResponse.TIMEOUT:
                self.confirmation_stats['timeout_count'] += 1
            
            # 更新平均响应时间
            total_responses = (self.confirmation_stats['confirmed_count'] + 
                             self.confirmation_stats['rejected_count'])
            if total_responses > 0:
                current_avg = self.confirmation_stats['avg_response_time']
                new_avg = ((current_avg * (total_responses - 1)) + result.processing_time) / total_responses
                self.confirmation_stats['avg_response_time'] = new_avg
                
        except Exception as e:
            logger.error(f"更新确认统计失败: {str(e)}")
    
    def get_confirmation_statistics(self) -> Dict[str, Any]:
        """获取确认统计信息"""
        try:
            total_requests = self.confirmation_stats['total_requests']
            if total_requests == 0:
                return {'total_requests': 0, 'message': '暂无确认数据'}
            
            stats = dict(self.confirmation_stats)
            
            # 计算成功率
            stats['confirmation_rate'] = (stats['confirmed_count'] / total_requests) if total_requests > 0 else 0
            stats['rejection_rate'] = (stats['rejected_count'] / total_requests) if total_requests > 0 else 0
            stats['timeout_rate'] = (stats['timeout_count'] / total_requests) if total_requests > 0 else 0
            
            # 添加活跃请求信息
            stats['active_requests_count'] = len(self.active_requests)
            stats['completed_requests_count'] = len(self.completed_requests)
            
            return stats
            
        except Exception as e:
            logger.error(f"获取确认统计失败: {str(e)}")
            return {'error': str(e)}
    
    def get_user_confirmation_profile(self, user_id: str) -> Dict[str, Any]:
        """获取用户确认画像"""
        try:
            history = self.user_confirmation_history.get(user_id, [])
            if not history:
                return {'user_id': user_id, 'profile': 'new_user', 'recommendations': []}
            
            # 分析用户确认模式
            confirmed_count = sum(1 for item in history if item['response_type'] == 'confirmed')
            rejected_count = sum(1 for item in history if item['response_type'] == 'rejected')
            total_count = len(history)
            
            confirmation_rate = confirmed_count / total_count if total_count > 0 else 0
            
            # 用户画像分类
            if confirmation_rate > 0.8:
                profile = 'trusting_user'
                recommendations = ['可以使用隐式确认', '减少确认步骤']
            elif confirmation_rate > 0.5:
                profile = 'normal_user'
                recommendations = ['保持当前确认策略']
            else:
                profile = 'cautious_user'
                recommendations = ['使用详细确认', '提供更多信息']
            
            return {
                'user_id': user_id,
                'total_confirmations': total_count,
                'confirmation_rate': round(confirmation_rate, 3),
                'profile': profile,
                'recommendations': recommendations,
                'recent_activity': history[-10:] if len(history) >= 10 else history
            }
            
        except Exception as e:
            logger.error(f"获取用户确认画像失败: {str(e)}")
            return {'error': str(e)}


# 全局确认管理器实例
confirmation_manager: Optional[IntentConfirmationManager] = None


def get_confirmation_manager(settings) -> IntentConfirmationManager:
    """获取确认管理器实例"""
    global confirmation_manager
    if confirmation_manager is None:
        confirmation_manager = IntentConfirmationManager(settings)
    return confirmation_manager