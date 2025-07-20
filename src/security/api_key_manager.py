"""
API密钥管理系统 (TASK-037)
提供API密钥生成、验证、管理和权限控制功能
"""
import secrets
import hashlib
import hmac
from typing import Dict, List, Optional, Set
from datetime import datetime, timedelta
from enum import Enum
from dataclasses import dataclass, asdict
import json

from ..utils.logger import get_logger
from ..services.cache_service import CacheService

logger = get_logger(__name__)


class ApiKeyStatus(str, Enum):
    """API密钥状态"""
    ACTIVE = "active"           # 活跃
    INACTIVE = "inactive"       # 非活跃
    EXPIRED = "expired"         # 已过期
    REVOKED = "revoked"         # 已撤销
    SUSPENDED = "suspended"     # 已暂停


class ApiKeyScope(str, Enum):
    """API密钥权限范围"""
    READ_ONLY = "read_only"           # 只读权限
    WRITE_ONLY = "write_only"         # 只写权限
    READ_WRITE = "read_write"         # 读写权限
    ADMIN = "admin"                   # 管理员权限
    ANALYTICS = "analytics"           # 分析权限
    INTENT_MANAGEMENT = "intent_mgmt" # 意图管理权限
    USER_MANAGEMENT = "user_mgmt"     # 用户管理权限


@dataclass
class ApiKeyInfo:
    """API密钥信息"""
    key_id: str
    key_hash: str
    name: str
    description: str
    scopes: List[ApiKeyScope]
    status: ApiKeyStatus
    created_at: datetime
    expires_at: Optional[datetime]
    last_used_at: Optional[datetime]
    usage_count: int
    rate_limit_per_hour: int
    allowed_ips: List[str]
    client_id: str
    metadata: Dict[str, str]
    
    def to_dict(self) -> Dict:
        """转换为字典格式"""
        result = asdict(self)
        result['created_at'] = self.created_at.isoformat()
        result['expires_at'] = self.expires_at.isoformat() if self.expires_at else None
        result['last_used_at'] = self.last_used_at.isoformat() if self.last_used_at else None
        result['scopes'] = [scope.value for scope in self.scopes]
        result['status'] = self.status.value
        return result
    
    @classmethod
    def from_dict(cls, data: Dict) -> "ApiKeyInfo":
        """从字典创建实例"""
        return cls(
            key_id=data['key_id'],
            key_hash=data['key_hash'],
            name=data['name'],
            description=data['description'],
            scopes=[ApiKeyScope(scope) for scope in data['scopes']],
            status=ApiKeyStatus(data['status']),
            created_at=datetime.fromisoformat(data['created_at']),
            expires_at=datetime.fromisoformat(data['expires_at']) if data['expires_at'] else None,
            last_used_at=datetime.fromisoformat(data['last_used_at']) if data['last_used_at'] else None,
            usage_count=data['usage_count'],
            rate_limit_per_hour=data['rate_limit_per_hour'],
            allowed_ips=data['allowed_ips'],
            client_id=data['client_id'],
            metadata=data['metadata']
        )


@dataclass
class ApiKeyUsageRecord:
    """API密钥使用记录"""
    key_id: str
    timestamp: datetime
    ip_address: str
    user_agent: str
    endpoint: str
    method: str
    success: bool
    response_code: int
    response_time_ms: int
    request_size: int
    response_size: int
    error_message: Optional[str] = None


class ApiKeyManager:
    """API密钥管理器"""
    
    def __init__(self, cache_service: Optional[CacheService] = None):
        self.cache_service = cache_service
        self.api_keys: Dict[str, ApiKeyInfo] = {}
        self.usage_records: List[ApiKeyUsageRecord] = []
        self.key_prefix = "ak_"  # API Key前缀
        self.secret_prefix = "sk_"  # Secret Key前缀
        
        # 安全配置
        self.min_key_length = 32
        self.max_usage_records = 10000
        self.default_rate_limit = 1000  # 每小时默认请求限制
        
    async def generate_api_key(
        self,
        name: str,
        description: str,
        scopes: List[ApiKeyScope],
        client_id: str,
        expires_in_days: Optional[int] = None,
        rate_limit_per_hour: Optional[int] = None,
        allowed_ips: Optional[List[str]] = None,
        metadata: Optional[Dict[str, str]] = None
    ) -> tuple[str, str]:
        """
        生成新的API密钥对
        
        Returns:
            tuple[str, str]: (public_key, secret_key)
        """
        try:
            # 生成密钥ID和密钥
            key_id = self._generate_key_id()
            secret_key = self._generate_secret_key()
            key_hash = self._hash_secret_key(secret_key)
            
            # 设置过期时间
            expires_at = None
            if expires_in_days:
                expires_at = datetime.now() + timedelta(days=expires_in_days)
            
            # 创建API密钥信息
            api_key_info = ApiKeyInfo(
                key_id=key_id,
                key_hash=key_hash,
                name=name,
                description=description,
                scopes=scopes,
                status=ApiKeyStatus.ACTIVE,
                created_at=datetime.now(),
                expires_at=expires_at,
                last_used_at=None,
                usage_count=0,
                rate_limit_per_hour=rate_limit_per_hour or self.default_rate_limit,
                allowed_ips=allowed_ips or [],
                client_id=client_id,
                metadata=metadata or {}
            )
            
            # 存储API密钥信息
            self.api_keys[key_id] = api_key_info
            
            # 缓存到Redis
            if self.cache_service:
                await self.cache_service.set(
                    f"api_key:{key_id}",
                    api_key_info.to_dict(),
                    ttl=86400,  # 24小时缓存
                    namespace="security"
                )
            
            logger.info(f"生成新API密钥: {key_id} for client: {client_id}")
            
            # 返回公钥和私钥
            public_key = f"{self.key_prefix}{key_id}"
            return public_key, secret_key
            
        except Exception as e:
            logger.error(f"生成API密钥失败: {str(e)}")
            raise
    
    async def verify_api_key(
        self,
        public_key: str,
        secret_key: str,
        ip_address: str,
        required_scopes: Optional[List[ApiKeyScope]] = None
    ) -> Optional[ApiKeyInfo]:
        """
        验证API密钥
        
        Args:
            public_key: 公钥
            secret_key: 私钥
            ip_address: 客户端IP地址
            required_scopes: 需要的权限范围
            
        Returns:
            ApiKeyInfo: 如果验证成功返回密钥信息，否则返回None
        """
        try:
            # 解析密钥ID
            if not public_key.startswith(self.key_prefix):
                logger.warning(f"无效的API密钥格式: {public_key[:20]}...")
                return None
            
            key_id = public_key[len(self.key_prefix):]
            
            # 获取密钥信息
            api_key_info = await self._get_api_key_info(key_id)
            if not api_key_info:
                logger.warning(f"API密钥不存在: {key_id}")
                return None
            
            # 验证密钥状态
            if not self._is_key_valid(api_key_info):
                logger.warning(f"API密钥状态无效: {key_id} - {api_key_info.status}")
                return None
            
            # 验证私钥
            if not self._verify_secret_key(secret_key, api_key_info.key_hash):
                logger.warning(f"API密钥私钥验证失败: {key_id}")
                return None
            
            # 验证IP地址限制
            if api_key_info.allowed_ips and ip_address not in api_key_info.allowed_ips:
                logger.warning(f"API密钥IP限制: {key_id} - {ip_address}")
                return None
            
            # 验证权限范围
            if required_scopes and not self._has_required_scopes(api_key_info.scopes, required_scopes):
                logger.warning(f"API密钥权限不足: {key_id} - required: {required_scopes}")
                return None
            
            # 检查速率限制
            if not await self._check_rate_limit(api_key_info):
                logger.warning(f"API密钥速率限制: {key_id}")
                return None
            
            # 更新使用记录
            await self._update_key_usage(api_key_info)
            
            logger.debug(f"API密钥验证成功: {key_id}")
            return api_key_info
            
        except Exception as e:
            logger.error(f"API密钥验证异常: {str(e)}")
            return None
    
    async def revoke_api_key(self, key_id: str, reason: str = "Manual revocation") -> bool:
        """撤销API密钥"""
        try:
            api_key_info = await self._get_api_key_info(key_id)
            if not api_key_info:
                return False
            
            # 更新状态
            api_key_info.status = ApiKeyStatus.REVOKED
            api_key_info.metadata['revoked_at'] = datetime.now().isoformat()
            api_key_info.metadata['revoke_reason'] = reason
            
            # 更新存储
            self.api_keys[key_id] = api_key_info
            
            if self.cache_service:
                await self.cache_service.set(
                    f"api_key:{key_id}",
                    api_key_info.to_dict(),
                    ttl=86400,
                    namespace="security"
                )
            
            logger.info(f"API密钥已撤销: {key_id} - {reason}")
            return True
            
        except Exception as e:
            logger.error(f"撤销API密钥失败: {str(e)}")
            return False
    
    async def list_api_keys(
        self,
        client_id: Optional[str] = None,
        status: Optional[ApiKeyStatus] = None,
        scope: Optional[ApiKeyScope] = None
    ) -> List[ApiKeyInfo]:
        """列出API密钥"""
        try:
            keys = list(self.api_keys.values())
            
            # 应用过滤条件
            if client_id:
                keys = [key for key in keys if key.client_id == client_id]
            
            if status:
                keys = [key for key in keys if key.status == status]
            
            if scope:
                keys = [key for key in keys if scope in key.scopes]
            
            return keys
            
        except Exception as e:
            logger.error(f"列出API密钥失败: {str(e)}")
            return []
    
    async def get_key_usage_stats(self, key_id: str, days: int = 7) -> Dict:
        """获取密钥使用统计"""
        try:
            cutoff_time = datetime.now() - timedelta(days=days)
            
            # 筛选指定时间范围的使用记录
            records = [
                record for record in self.usage_records
                if record.key_id == key_id and record.timestamp >= cutoff_time
            ]
            
            # 计算统计信息
            total_requests = len(records)
            successful_requests = len([r for r in records if r.success])
            failed_requests = total_requests - successful_requests
            
            avg_response_time = 0
            if records:
                avg_response_time = sum(r.response_time_ms for r in records) / len(records)
            
            # 按日期分组统计
            daily_stats = {}
            for record in records:
                date_key = record.timestamp.date().isoformat()
                if date_key not in daily_stats:
                    daily_stats[date_key] = {
                        'requests': 0,
                        'success': 0,
                        'failed': 0,
                        'avg_response_time': 0
                    }
                
                daily_stats[date_key]['requests'] += 1
                if record.success:
                    daily_stats[date_key]['success'] += 1
                else:
                    daily_stats[date_key]['failed'] += 1
            
            # 计算每日平均响应时间
            for date_key in daily_stats:
                day_records = [r for r in records if r.timestamp.date().isoformat() == date_key]
                if day_records:
                    daily_stats[date_key]['avg_response_time'] = sum(
                        r.response_time_ms for r in day_records
                    ) / len(day_records)
            
            return {
                'key_id': key_id,
                'period_days': days,
                'total_requests': total_requests,
                'successful_requests': successful_requests,
                'failed_requests': failed_requests,
                'success_rate': successful_requests / total_requests if total_requests > 0 else 0,
                'avg_response_time_ms': avg_response_time,
                'daily_stats': daily_stats
            }
            
        except Exception as e:
            logger.error(f"获取密钥使用统计失败: {str(e)}")
            return {}
    
    async def record_api_usage(
        self,
        key_id: str,
        ip_address: str,
        user_agent: str,
        endpoint: str,
        method: str,
        success: bool,
        response_code: int,
        response_time_ms: int,
        request_size: int,
        response_size: int,
        error_message: Optional[str] = None
    ):
        """记录API使用情况"""
        try:
            usage_record = ApiKeyUsageRecord(
                key_id=key_id,
                timestamp=datetime.now(),
                ip_address=ip_address,
                user_agent=user_agent,
                endpoint=endpoint,
                method=method,
                success=success,
                response_code=response_code,
                response_time_ms=response_time_ms,
                request_size=request_size,
                response_size=response_size,
                error_message=error_message
            )
            
            self.usage_records.append(usage_record)
            
            # 限制记录数量，防止内存泄漏
            if len(self.usage_records) > self.max_usage_records:
                self.usage_records = self.usage_records[-self.max_usage_records:]
            
            # 异步记录到缓存（可选）
            if self.cache_service:
                await self.cache_service.lpush(
                    f"api_usage:{key_id}",
                    json.dumps(asdict(usage_record), default=str),
                    namespace="security"
                )
            
        except Exception as e:
            logger.error(f"记录API使用情况失败: {str(e)}")
    
    def _generate_key_id(self) -> str:
        """生成密钥ID"""
        return secrets.token_hex(16)
    
    def _generate_secret_key(self) -> str:
        """生成私钥"""
        return f"{self.secret_prefix}{secrets.token_urlsafe(48)}"
    
    def _hash_secret_key(self, secret_key: str) -> str:
        """对私钥进行哈希"""
        return hashlib.sha256(secret_key.encode()).hexdigest()
    
    def _verify_secret_key(self, secret_key: str, key_hash: str) -> bool:
        """验证私钥"""
        return hmac.compare_digest(self._hash_secret_key(secret_key), key_hash)
    
    def _is_key_valid(self, api_key_info: ApiKeyInfo) -> bool:
        """检查密钥是否有效"""
        # 检查状态
        if api_key_info.status != ApiKeyStatus.ACTIVE:
            return False
        
        # 检查过期时间
        if api_key_info.expires_at and datetime.now() > api_key_info.expires_at:
            return False
        
        return True
    
    def _has_required_scopes(
        self,
        key_scopes: List[ApiKeyScope],
        required_scopes: List[ApiKeyScope]
    ) -> bool:
        """检查是否具有所需权限"""
        # 管理员权限可以访问所有内容
        if ApiKeyScope.ADMIN in key_scopes:
            return True
        
        # 检查是否包含所有必需的权限
        return all(scope in key_scopes for scope in required_scopes)
    
    async def _get_api_key_info(self, key_id: str) -> Optional[ApiKeyInfo]:
        """获取API密钥信息"""
        # 优先从内存获取
        if key_id in self.api_keys:
            return self.api_keys[key_id]
        
        # 从缓存获取
        if self.cache_service:
            try:
                cached_data = await self.cache_service.get(
                    f"api_key:{key_id}",
                    namespace="security"
                )
                if cached_data:
                    api_key_info = ApiKeyInfo.from_dict(cached_data)
                    self.api_keys[key_id] = api_key_info  # 缓存到内存
                    return api_key_info
            except Exception as e:
                logger.warning(f"从缓存获取API密钥失败: {str(e)}")
        
        return None
    
    async def _check_rate_limit(self, api_key_info: ApiKeyInfo) -> bool:
        """检查速率限制"""
        if not self.cache_service:
            return True  # 如果没有缓存服务，跳过限制检查
        
        try:
            current_hour = datetime.now().strftime("%Y%m%d%H")
            rate_limit_key = f"rate_limit:{api_key_info.key_id}:{current_hour}"
            
            # 获取当前小时的请求计数
            current_count = await self.cache_service.get(rate_limit_key, namespace="security")
            current_count = int(current_count) if current_count else 0
            
            # 检查是否超出限制
            if current_count >= api_key_info.rate_limit_per_hour:
                return False
            
            # 增加计数
            await self.cache_service.incr(rate_limit_key, namespace="security")
            await self.cache_service.expire(rate_limit_key, 3600, namespace="security")  # 1小时过期
            
            return True
            
        except Exception as e:
            logger.error(f"检查速率限制失败: {str(e)}")
            return True  # 出错时允许请求通过
    
    async def _update_key_usage(self, api_key_info: ApiKeyInfo):
        """更新密钥使用记录"""
        try:
            api_key_info.last_used_at = datetime.now()
            api_key_info.usage_count += 1
            
            # 更新内存和缓存
            self.api_keys[api_key_info.key_id] = api_key_info
            
            if self.cache_service:
                await self.cache_service.set(
                    f"api_key:{api_key_info.key_id}",
                    api_key_info.to_dict(),
                    ttl=86400,
                    namespace="security"
                )
                
        except Exception as e:
            logger.error(f"更新密钥使用记录失败: {str(e)}")


# 全局API密钥管理器实例
_api_key_manager: Optional[ApiKeyManager] = None

async def get_api_key_manager(cache_service: Optional[CacheService] = None) -> ApiKeyManager:
    """获取API密钥管理器实例"""
    global _api_key_manager
    
    if _api_key_manager is None:
        _api_key_manager = ApiKeyManager(cache_service)
    
    return _api_key_manager