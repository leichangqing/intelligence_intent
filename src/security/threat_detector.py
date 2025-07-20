"""
高级威胁检测系统 (TASK-037)
提供实时威胁检测、行为分析和自动响应功能
"""
import time
import asyncio
from typing import Dict, List, Optional, Set, Tuple, Any
from datetime import datetime, timedelta
from enum import Enum
from dataclasses import dataclass, asdict
from collections import defaultdict, deque
import ipaddress
import hashlib
import json

from ..utils.logger import get_logger
from ..services.cache_service import CacheService

logger = get_logger(__name__)


class ThreatSeverity(str, Enum):
    """威胁严重程度"""
    INFO = "info"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ThreatCategory(str, Enum):
    """威胁类别"""
    BRUTE_FORCE = "brute_force"           # 暴力破解
    RATE_LIMIT_ABUSE = "rate_limit_abuse" # 速率限制滥用
    SUSPICIOUS_BEHAVIOR = "suspicious_behavior"  # 可疑行为
    MALICIOUS_PAYLOAD = "malicious_payload"      # 恶意载荷
    UNAUTHORIZED_ACCESS = "unauthorized_access"  # 未授权访问
    DATA_EXFILTRATION = "data_exfiltration"     # 数据泄露
    DENIAL_OF_SERVICE = "denial_of_service"     # 拒绝服务
    ACCOUNT_TAKEOVER = "account_takeover"       # 账户接管
    ANOMALOUS_TRAFFIC = "anomalous_traffic"     # 异常流量
    CREDENTIAL_STUFFING = "credential_stuffing" # 凭据填充


class ResponseAction(str, Enum):
    """响应动作"""
    LOG_ONLY = "log_only"               # 仅记录日志
    ALERT = "alert"                     # 发送警报
    RATE_LIMIT = "rate_limit"           # 速率限制
    TEMPORARY_BLOCK = "temporary_block" # 临时阻止
    PERMANENT_BLOCK = "permanent_block" # 永久阻止
    REQUIRE_CAPTCHA = "require_captcha" # 要求验证码
    ESCALATE = "escalate"               # 升级处理


@dataclass
class ThreatEvent:
    """威胁事件"""
    event_id: str
    timestamp: datetime
    source_ip: str
    user_agent: str
    user_id: Optional[str]
    category: ThreatCategory
    severity: ThreatSeverity
    description: str
    evidence: Dict[str, Any]
    confidence_score: float  # 0.0 - 1.0
    risk_score: int         # 0 - 100
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        result = asdict(self)
        result['timestamp'] = self.timestamp.isoformat()
        result['category'] = self.category.value
        result['severity'] = self.severity.value
        return result


@dataclass
class ThreatRule:
    """威胁检测规则"""
    rule_id: str
    name: str
    description: str
    category: ThreatCategory
    severity: ThreatSeverity
    conditions: Dict[str, Any]
    actions: List[ResponseAction]
    enabled: bool = True
    threshold: int = 1
    time_window_minutes: int = 60
    confidence_weight: float = 1.0


@dataclass
class ClientProfile:
    """客户端档案"""
    ip_address: str
    first_seen: datetime
    last_seen: datetime
    request_count: int
    failed_auth_count: int
    success_auth_count: int
    user_agents: Set[str]
    endpoints_accessed: Set[str]
    countries: Set[str]
    threat_score: float
    is_whitelisted: bool
    is_blacklisted: bool
    notes: str


class ThreatDetector:
    """威胁检测器"""
    
    def __init__(self, cache_service: Optional[CacheService] = None):
        self.cache_service = cache_service
        self.threat_rules: Dict[str, ThreatRule] = {}
        self.client_profiles: Dict[str, ClientProfile] = {}
        self.threat_events: deque = deque(maxlen=10000)
        self.blocked_ips: Set[str] = set()
        self.whitelisted_ips: Set[str] = set()
        
        # 检测配置
        self.max_requests_per_minute = 100
        self.max_failed_auth_attempts = 5
        self.max_endpoints_per_minute = 20
        self.suspicious_user_agents = [
            'sqlmap', 'nmap', 'nikto', 'dirb', 'gobuster', 'masscan',
            'burp', 'zap', 'w3af', 'acunetix', 'nessus'
        ]
        
        # 初始化默认规则
        self._setup_default_rules()
        
        # 异步任务
        self._monitoring_task = None
    
    async def initialize(self):
        """初始化威胁检测器"""
        try:
            # 加载历史数据
            await self._load_profiles()
            await self._load_threat_events()
            
            # 启动监控任务
            if not self._monitoring_task:
                self._monitoring_task = asyncio.create_task(self._monitoring_loop())
            
            logger.info("威胁检测器初始化完成")
            
        except Exception as e:
            logger.error(f"威胁检测器初始化失败: {str(e)}")
    
    async def analyze_request(
        self,
        ip_address: str,
        user_agent: str,
        endpoint: str,
        method: str,
        user_id: Optional[str] = None,
        payload: Optional[str] = None,
        auth_success: Optional[bool] = None
    ) -> List[ThreatEvent]:
        """分析请求并检测威胁"""
        threats = []
        
        try:
            # 更新客户端档案
            await self._update_client_profile(
                ip_address, user_agent, endpoint, user_id, auth_success
            )
            
            # 获取客户端档案
            profile = self.client_profiles.get(ip_address)
            
            # 应用检测规则
            for rule_id, rule in self.threat_rules.items():
                if not rule.enabled:
                    continue
                
                detected_threats = await self._apply_rule(
                    rule, ip_address, user_agent, endpoint, method,
                    user_id, payload, auth_success, profile
                )
                threats.extend(detected_threats)
            
            # 记录威胁事件
            for threat in threats:
                await self._record_threat_event(threat)
            
            return threats
            
        except Exception as e:
            logger.error(f"威胁分析失败: {str(e)}")
            return []
    
    async def check_ip_reputation(self, ip_address: str) -> Dict[str, Any]:
        """检查IP信誉"""
        try:
            # 检查黑名单
            if ip_address in self.blocked_ips:
                return {
                    'reputation': 'malicious',
                    'confidence': 1.0,
                    'reason': 'IP in blacklist'
                }
            
            # 检查白名单
            if ip_address in self.whitelisted_ips:
                return {
                    'reputation': 'trusted',
                    'confidence': 1.0,
                    'reason': 'IP in whitelist'
                }
            
            # 检查内网IP
            try:
                ip_obj = ipaddress.ip_address(ip_address)
                if ip_obj.is_private:
                    return {
                        'reputation': 'internal',
                        'confidence': 1.0,
                        'reason': 'Private IP address'
                    }
            except ValueError:
                pass
            
            # 基于历史行为分析
            profile = self.client_profiles.get(ip_address)
            if profile:
                if profile.threat_score > 0.8:
                    return {
                        'reputation': 'suspicious',
                        'confidence': profile.threat_score,
                        'reason': f'High threat score: {profile.threat_score:.2f}'
                    }
                elif profile.threat_score < 0.2:
                    return {
                        'reputation': 'good',
                        'confidence': 1.0 - profile.threat_score,
                        'reason': f'Low threat score: {profile.threat_score:.2f}'
                    }
            
            return {
                'reputation': 'unknown',
                'confidence': 0.5,
                'reason': 'No sufficient data'
            }
            
        except Exception as e:
            logger.error(f"IP信誉检查失败: {str(e)}")
            return {
                'reputation': 'unknown',
                'confidence': 0.0,
                'reason': f'Error: {str(e)}'
            }
    
    async def get_threat_summary(self, hours: int = 24) -> Dict[str, Any]:
        """获取威胁摘要"""
        try:
            cutoff_time = datetime.now() - timedelta(hours=hours)
            
            # 筛选时间范围内的威胁事件
            recent_threats = [
                threat for threat in self.threat_events
                if threat.timestamp >= cutoff_time
            ]
            
            # 统计信息
            total_threats = len(recent_threats)
            by_severity = defaultdict(int)
            by_category = defaultdict(int)
            by_ip = defaultdict(int)
            
            for threat in recent_threats:
                by_severity[threat.severity.value] += 1
                by_category[threat.category.value] += 1
                by_ip[threat.source_ip] += 1
            
            # 活跃客户端数
            active_clients = len(set(
                ip for ip, profile in self.client_profiles.items()
                if profile.last_seen >= cutoff_time
            ))
            
            # 被阻止的IP数
            blocked_ips_count = len(self.blocked_ips)
            
            return {
                'period_hours': hours,
                'total_threats': total_threats,
                'threats_by_severity': dict(by_severity),
                'threats_by_category': dict(by_category),
                'top_threat_ips': dict(sorted(by_ip.items(), key=lambda x: x[1], reverse=True)[:10]),
                'active_clients': active_clients,
                'blocked_ips': blocked_ips_count,
                'detection_rules': len([r for r in self.threat_rules.values() if r.enabled]),
                'monitored_profiles': len(self.client_profiles)
            }
            
        except Exception as e:
            logger.error(f"获取威胁摘要失败: {str(e)}")
            return {}
    
    async def block_ip(self, ip_address: str, reason: str, duration_hours: Optional[int] = None):
        """阻止IP地址"""
        try:
            self.blocked_ips.add(ip_address)
            
            # 更新客户端档案
            if ip_address in self.client_profiles:
                self.client_profiles[ip_address].is_blacklisted = True
                self.client_profiles[ip_address].notes += f" | Blocked: {reason}"
            
            # 缓存阻止信息
            if self.cache_service:
                block_info = {
                    'ip': ip_address,
                    'reason': reason,
                    'blocked_at': datetime.now().isoformat(),
                    'duration_hours': duration_hours
                }
                
                ttl = duration_hours * 3600 if duration_hours else None
                await self.cache_service.set(
                    f"blocked_ip:{ip_address}",
                    block_info,
                    ttl=ttl,
                    namespace="security"
                )
            
            logger.warning(f"IP已被阻止: {ip_address} - {reason}")
            
        except Exception as e:
            logger.error(f"阻止IP失败: {str(e)}")
    
    async def unblock_ip(self, ip_address: str):
        """解除IP阻止"""
        try:
            self.blocked_ips.discard(ip_address)
            
            # 更新客户端档案
            if ip_address in self.client_profiles:
                self.client_profiles[ip_address].is_blacklisted = False
            
            # 移除缓存
            if self.cache_service:
                await self.cache_service.delete(
                    f"blocked_ip:{ip_address}",
                    namespace="security"
                )
            
            logger.info(f"IP阻止已解除: {ip_address}")
            
        except Exception as e:
            logger.error(f"解除IP阻止失败: {str(e)}")
    
    def add_threat_rule(self, rule: ThreatRule):
        """添加威胁检测规则"""
        self.threat_rules[rule.rule_id] = rule
        logger.info(f"添加威胁检测规则: {rule.rule_id} - {rule.name}")
    
    def remove_threat_rule(self, rule_id: str) -> bool:
        """移除威胁检测规则"""
        if rule_id in self.threat_rules:
            del self.threat_rules[rule_id]
            logger.info(f"移除威胁检测规则: {rule_id}")
            return True
        return False
    
    def _setup_default_rules(self):
        """设置默认威胁检测规则"""
        # 暴力破解检测
        self.threat_rules["brute_force_auth"] = ThreatRule(
            rule_id="brute_force_auth",
            name="认证暴力破解检测",
            description="检测短时间内多次认证失败",
            category=ThreatCategory.BRUTE_FORCE,
            severity=ThreatSeverity.HIGH,
            conditions={
                'failed_auth_attempts': 5,
                'time_window_minutes': 10
            },
            actions=[ResponseAction.TEMPORARY_BLOCK, ResponseAction.ALERT],
            threshold=5,
            time_window_minutes=10
        )
        
        # 速率限制滥用
        self.threat_rules["rate_limit_abuse"] = ThreatRule(
            rule_id="rate_limit_abuse",
            name="速率限制滥用检测",
            description="检测异常高频请求",
            category=ThreatCategory.RATE_LIMIT_ABUSE,
            severity=ThreatSeverity.MEDIUM,
            conditions={
                'requests_per_minute': 200,
                'time_window_minutes': 1
            },
            actions=[ResponseAction.RATE_LIMIT, ResponseAction.LOG_ONLY],
            threshold=200,
            time_window_minutes=1
        )
        
        # 可疑User-Agent
        self.threat_rules["suspicious_user_agent"] = ThreatRule(
            rule_id="suspicious_user_agent",
            name="可疑User-Agent检测",
            description="检测已知的攻击工具User-Agent",
            category=ThreatCategory.SUSPICIOUS_BEHAVIOR,
            severity=ThreatSeverity.MEDIUM,
            conditions={
                'suspicious_user_agents': self.suspicious_user_agents
            },
            actions=[ResponseAction.ALERT, ResponseAction.LOG_ONLY],
            threshold=1,
            time_window_minutes=60
        )
        
        # 端点扫描检测
        self.threat_rules["endpoint_scanning"] = ThreatRule(
            rule_id="endpoint_scanning",
            name="端点扫描检测",
            description="检测短时间内访问大量不同端点",
            category=ThreatCategory.SUSPICIOUS_BEHAVIOR,
            severity=ThreatSeverity.MEDIUM,
            conditions={
                'unique_endpoints': 30,
                'time_window_minutes': 5
            },
            actions=[ResponseAction.TEMPORARY_BLOCK, ResponseAction.ALERT],
            threshold=30,
            time_window_minutes=5
        )
    
    async def _apply_rule(
        self,
        rule: ThreatRule,
        ip_address: str,
        user_agent: str,
        endpoint: str,
        method: str,
        user_id: Optional[str],
        payload: Optional[str],
        auth_success: Optional[bool],
        profile: Optional[ClientProfile]
    ) -> List[ThreatEvent]:
        """应用威胁检测规则"""
        threats = []
        
        try:
            if rule.rule_id == "brute_force_auth" and auth_success is False:
                if profile and profile.failed_auth_count >= rule.conditions['failed_auth_attempts']:
                    threat = ThreatEvent(
                        event_id=self._generate_event_id(),
                        timestamp=datetime.now(),
                        source_ip=ip_address,
                        user_agent=user_agent,
                        user_id=user_id,
                        category=rule.category,
                        severity=rule.severity,
                        description=f"检测到暴力破解攻击: {profile.failed_auth_count}次失败",
                        evidence={
                            'failed_attempts': profile.failed_auth_count,
                            'time_window': rule.time_window_minutes,
                            'endpoint': endpoint
                        },
                        confidence_score=0.9,
                        risk_score=85
                    )
                    threats.append(threat)
            
            elif rule.rule_id == "rate_limit_abuse":
                # 检查请求频率
                current_minute = datetime.now().replace(second=0, microsecond=0)
                minute_key = f"requests:{ip_address}:{current_minute.isoformat()}"
                
                if self.cache_service:
                    try:
                        count = await self.cache_service.get(minute_key, namespace="security")
                        count = int(count) if count else 0
                        
                        if count >= rule.conditions['requests_per_minute']:
                            threat = ThreatEvent(
                                event_id=self._generate_event_id(),
                                timestamp=datetime.now(),
                                source_ip=ip_address,
                                user_agent=user_agent,
                                user_id=user_id,
                                category=rule.category,
                                severity=rule.severity,
                                description=f"检测到速率限制滥用: {count}次请求/分钟",
                                evidence={
                                    'requests_per_minute': count,
                                    'threshold': rule.conditions['requests_per_minute'],
                                    'endpoint': endpoint
                                },
                                confidence_score=0.8,
                                risk_score=70
                            )
                            threats.append(threat)
                        
                        # 增加计数
                        await self.cache_service.incr(minute_key, namespace="security")
                        await self.cache_service.expire(minute_key, 60, namespace="security")
                        
                    except Exception:
                        pass
            
            elif rule.rule_id == "suspicious_user_agent":
                user_agent_lower = user_agent.lower()
                for suspicious_agent in rule.conditions['suspicious_user_agents']:
                    if suspicious_agent in user_agent_lower:
                        threat = ThreatEvent(
                            event_id=self._generate_event_id(),
                            timestamp=datetime.now(),
                            source_ip=ip_address,
                            user_agent=user_agent,
                            user_id=user_id,
                            category=rule.category,
                            severity=rule.severity,
                            description=f"检测到可疑User-Agent: {suspicious_agent}",
                            evidence={
                                'user_agent': user_agent,
                                'suspicious_pattern': suspicious_agent,
                                'endpoint': endpoint
                            },
                            confidence_score=0.95,
                            risk_score=60
                        )
                        threats.append(threat)
                        break
            
            elif rule.rule_id == "endpoint_scanning":
                if profile and len(profile.endpoints_accessed) >= rule.conditions['unique_endpoints']:
                    # 检查时间窗口
                    time_window = timedelta(minutes=rule.time_window_minutes)
                    if datetime.now() - profile.first_seen <= time_window:
                        threat = ThreatEvent(
                            event_id=self._generate_event_id(),
                            timestamp=datetime.now(),
                            source_ip=ip_address,
                            user_agent=user_agent,
                            user_id=user_id,
                            category=rule.category,
                            severity=rule.severity,
                            description=f"检测到端点扫描: 访问了{len(profile.endpoints_accessed)}个端点",
                            evidence={
                                'unique_endpoints': len(profile.endpoints_accessed),
                                'time_window_minutes': rule.time_window_minutes,
                                'endpoints': list(profile.endpoints_accessed)[:10]  # 只记录前10个
                            },
                            confidence_score=0.85,
                            risk_score=75
                        )
                        threats.append(threat)
            
            return threats
            
        except Exception as e:
            logger.error(f"应用威胁检测规则失败: {rule.rule_id} - {str(e)}")
            return []
    
    async def _update_client_profile(
        self,
        ip_address: str,
        user_agent: str,
        endpoint: str,
        user_id: Optional[str],
        auth_success: Optional[bool]
    ):
        """更新客户端档案"""
        try:
            now = datetime.now()
            
            if ip_address not in self.client_profiles:
                self.client_profiles[ip_address] = ClientProfile(
                    ip_address=ip_address,
                    first_seen=now,
                    last_seen=now,
                    request_count=0,
                    failed_auth_count=0,
                    success_auth_count=0,
                    user_agents=set(),
                    endpoints_accessed=set(),
                    countries=set(),
                    threat_score=0.0,
                    is_whitelisted=ip_address in self.whitelisted_ips,
                    is_blacklisted=ip_address in self.blocked_ips,
                    notes=""
                )
            
            profile = self.client_profiles[ip_address]
            profile.last_seen = now
            profile.request_count += 1
            profile.user_agents.add(user_agent)
            profile.endpoints_accessed.add(endpoint)
            
            # 更新认证统计
            if auth_success is not None:
                if auth_success:
                    profile.success_auth_count += 1
                    # 成功认证降低威胁分数
                    profile.threat_score = max(0.0, profile.threat_score - 0.1)
                else:
                    profile.failed_auth_count += 1
                    # 失败认证增加威胁分数
                    profile.threat_score = min(1.0, profile.threat_score + 0.2)
            
            # 基于行为更新威胁分数
            self._calculate_threat_score(profile)
            
        except Exception as e:
            logger.error(f"更新客户端档案失败: {str(e)}")
    
    def _calculate_threat_score(self, profile: ClientProfile):
        """计算威胁分数"""
        score = profile.threat_score
        
        # 基于失败认证比例
        if profile.success_auth_count + profile.failed_auth_count > 0:
            fail_ratio = profile.failed_auth_count / (profile.success_auth_count + profile.failed_auth_count)
            score += fail_ratio * 0.3
        
        # 基于User-Agent数量（频繁变化可能是攻击）
        if len(profile.user_agents) > 10:
            score += 0.2
        
        # 基于访问端点数量
        if len(profile.endpoints_accessed) > 50:
            score += 0.3
        
        # 基于请求频率
        time_diff = (profile.last_seen - profile.first_seen).total_seconds()
        if time_diff > 0:
            request_rate = profile.request_count / (time_diff / 60)  # 每分钟请求数
            if request_rate > 100:
                score += 0.4
        
        profile.threat_score = min(1.0, max(0.0, score))
    
    async def _record_threat_event(self, threat: ThreatEvent):
        """记录威胁事件"""
        self.threat_events.append(threat)
        
        # 执行响应动作
        await self._execute_response_actions(threat)
        
        # 缓存威胁事件
        if self.cache_service:
            try:
                await self.cache_service.lpush(
                    "threat_events",
                    json.dumps(threat.to_dict()),
                    namespace="security"
                )
            except Exception as e:
                logger.warning(f"缓存威胁事件失败: {str(e)}")
    
    async def _execute_response_actions(self, threat: ThreatEvent):
        """执行响应动作"""
        try:
            rule = self.threat_rules.get(threat.category.value)
            if not rule:
                return
            
            for action in rule.actions:
                if action == ResponseAction.TEMPORARY_BLOCK:
                    await self.block_ip(
                        threat.source_ip,
                        f"威胁检测: {threat.description}",
                        duration_hours=24
                    )
                elif action == ResponseAction.PERMANENT_BLOCK:
                    await self.block_ip(
                        threat.source_ip,
                        f"严重威胁: {threat.description}"
                    )
                elif action == ResponseAction.ALERT:
                    logger.warning(
                        f"威胁警报: {threat.category.value} - {threat.description} "
                        f"from {threat.source_ip}"
                    )
                elif action == ResponseAction.LOG_ONLY:
                    logger.info(
                        f"威胁记录: {threat.category.value} - {threat.description} "
                        f"from {threat.source_ip}"
                    )
                
        except Exception as e:
            logger.error(f"执行响应动作失败: {str(e)}")
    
    async def _load_profiles(self):
        """加载客户端档案"""
        if not self.cache_service:
            return
        
        try:
            # 从缓存加载档案数据
            profiles_data = await self.cache_service.get(
                "client_profiles",
                namespace="security"
            )
            
            if profiles_data:
                for ip, data in profiles_data.items():
                    profile = ClientProfile(**data)
                    profile.user_agents = set(profile.user_agents)
                    profile.endpoints_accessed = set(profile.endpoints_accessed)
                    profile.countries = set(profile.countries)
                    self.client_profiles[ip] = profile
                
                logger.info(f"加载了 {len(self.client_profiles)} 个客户端档案")
                
        except Exception as e:
            logger.warning(f"加载客户端档案失败: {str(e)}")
    
    async def _load_threat_events(self):
        """加载威胁事件"""
        if not self.cache_service:
            return
        
        try:
            # 从缓存加载最近的威胁事件
            events_data = await self.cache_service.lrange(
                "threat_events",
                0, 1000,
                namespace="security"
            )
            
            for event_json in events_data:
                try:
                    event_dict = json.loads(event_json)
                    event = ThreatEvent(
                        event_id=event_dict['event_id'],
                        timestamp=datetime.fromisoformat(event_dict['timestamp']),
                        source_ip=event_dict['source_ip'],
                        user_agent=event_dict['user_agent'],
                        user_id=event_dict.get('user_id'),
                        category=ThreatCategory(event_dict['category']),
                        severity=ThreatSeverity(event_dict['severity']),
                        description=event_dict['description'],
                        evidence=event_dict['evidence'],
                        confidence_score=event_dict['confidence_score'],
                        risk_score=event_dict['risk_score']
                    )
                    self.threat_events.append(event)
                except Exception:
                    continue
            
            logger.info(f"加载了 {len(self.threat_events)} 个威胁事件")
            
        except Exception as e:
            logger.warning(f"加载威胁事件失败: {str(e)}")
    
    async def _monitoring_loop(self):
        """监控循环"""
        while True:
            try:
                await asyncio.sleep(300)  # 每5分钟执行一次
                
                # 清理过期数据
                await self._cleanup_expired_data()
                
                # 保存档案数据
                await self._save_profiles()
                
                # 更新威胁统计
                await self._update_threat_statistics()
                
            except Exception as e:
                logger.error(f"监控循环异常: {str(e)}")
                await asyncio.sleep(60)
    
    async def _cleanup_expired_data(self):
        """清理过期数据"""
        try:
            cutoff_time = datetime.now() - timedelta(days=30)
            
            # 清理过期的客户端档案
            expired_ips = [
                ip for ip, profile in self.client_profiles.items()
                if profile.last_seen < cutoff_time and not profile.is_blacklisted
            ]
            
            for ip in expired_ips:
                del self.client_profiles[ip]
            
            if expired_ips:
                logger.info(f"清理了 {len(expired_ips)} 个过期客户端档案")
                
        except Exception as e:
            logger.error(f"清理过期数据失败: {str(e)}")
    
    async def _save_profiles(self):
        """保存客户端档案"""
        if not self.cache_service:
            return
        
        try:
            # 准备序列化数据
            profiles_data = {}
            for ip, profile in self.client_profiles.items():
                profile_dict = asdict(profile)
                profile_dict['user_agents'] = list(profile.user_agents)
                profile_dict['endpoints_accessed'] = list(profile.endpoints_accessed)
                profile_dict['countries'] = list(profile.countries)
                profile_dict['first_seen'] = profile.first_seen.isoformat()
                profile_dict['last_seen'] = profile.last_seen.isoformat()
                profiles_data[ip] = profile_dict
            
            # 保存到缓存
            await self.cache_service.set(
                "client_profiles",
                profiles_data,
                ttl=86400,  # 24小时
                namespace="security"
            )
            
        except Exception as e:
            logger.warning(f"保存客户端档案失败: {str(e)}")
    
    async def _update_threat_statistics(self):
        """更新威胁统计"""
        try:
            summary = await self.get_threat_summary(24)
            
            if self.cache_service:
                await self.cache_service.set(
                    "threat_summary_24h",
                    summary,
                    ttl=3600,  # 1小时
                    namespace="security"
                )
            
        except Exception as e:
            logger.error(f"更新威胁统计失败: {str(e)}")
    
    def _generate_event_id(self) -> str:
        """生成事件ID"""
        timestamp = str(time.time())
        return hashlib.md5(timestamp.encode()).hexdigest()[:16]


# 全局威胁检测器实例
_threat_detector: Optional[ThreatDetector] = None

async def get_threat_detector(cache_service: Optional[CacheService] = None) -> ThreatDetector:
    """获取威胁检测器实例"""
    global _threat_detector
    
    if _threat_detector is None:
        _threat_detector = ThreatDetector(cache_service)
        await _threat_detector.initialize()
    
    return _threat_detector