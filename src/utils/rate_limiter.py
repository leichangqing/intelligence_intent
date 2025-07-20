"""
速率限制器 (TASK-034)
实现用户和IP级别的速率限制
"""
from typing import Dict, Optional
import time
import asyncio
from collections import defaultdict, deque
from datetime import datetime, timedelta

from src.utils.logger import get_logger

logger = get_logger(__name__)


class RateLimiter:
    """速率限制器"""
    
    def __init__(self, max_requests_per_minute: int = 60, max_requests_per_hour: int = 1000):
        self.max_requests_per_minute = max_requests_per_minute
        self.max_requests_per_hour = max_requests_per_hour
        
        # 用户请求记录
        self.user_minute_requests: Dict[str, deque] = defaultdict(lambda: deque(maxlen=max_requests_per_minute))
        self.user_hour_requests: Dict[str, deque] = defaultdict(lambda: deque(maxlen=max_requests_per_hour))
        
        # IP请求记录
        self.ip_minute_requests: Dict[str, deque] = defaultdict(lambda: deque(maxlen=max_requests_per_minute))
        self.ip_hour_requests: Dict[str, deque] = defaultdict(lambda: deque(maxlen=max_requests_per_hour))
        
        # 清理任务
        self._start_cleanup_task()
    
    async def check_rate_limit(self, user_id: str, ip_address: str) -> bool:
        """
        检查速率限制
        
        Args:
            user_id: 用户ID
            ip_address: IP地址
            
        Returns:
            bool: 是否允许请求
        """
        current_time = time.time()
        
        # 清理过期记录
        self._cleanup_expired_requests(current_time)
        
        # 检查用户级别限制
        if not self._check_user_limit(user_id, current_time):
            logger.warning(f"用户速率限制超限: {user_id}")
            return False
        
        # 检查IP级别限制
        if not self._check_ip_limit(ip_address, current_time):
            logger.warning(f"IP速率限制超限: {ip_address}")
            return False
        
        # 记录请求
        self._record_request(user_id, ip_address, current_time)
        
        return True
    
    def _check_user_limit(self, user_id: str, current_time: float) -> bool:
        """检查用户级别限制"""
        # 检查分钟级限制
        minute_requests = self.user_minute_requests[user_id]
        minute_cutoff = current_time - 60
        
        while minute_requests and minute_requests[0] < minute_cutoff:
            minute_requests.popleft()
        
        if len(minute_requests) >= self.max_requests_per_minute:
            return False
        
        # 检查小时级限制
        hour_requests = self.user_hour_requests[user_id]
        hour_cutoff = current_time - 3600
        
        while hour_requests and hour_requests[0] < hour_cutoff:
            hour_requests.popleft()
        
        if len(hour_requests) >= self.max_requests_per_hour:
            return False
        
        return True
    
    def _check_ip_limit(self, ip_address: str, current_time: float) -> bool:
        """检查IP级别限制"""
        # IP限制通常更严格
        ip_max_per_minute = min(self.max_requests_per_minute * 2, 120)
        ip_max_per_hour = min(self.max_requests_per_hour * 2, 2000)
        
        # 检查分钟级限制
        minute_requests = self.ip_minute_requests[ip_address]
        minute_cutoff = current_time - 60
        
        while minute_requests and minute_requests[0] < minute_cutoff:
            minute_requests.popleft()
        
        if len(minute_requests) >= ip_max_per_minute:
            return False
        
        # 检查小时级限制
        hour_requests = self.ip_hour_requests[ip_address]
        hour_cutoff = current_time - 3600
        
        while hour_requests and hour_requests[0] < hour_cutoff:
            hour_requests.popleft()
        
        if len(hour_requests) >= ip_max_per_hour:
            return False
        
        return True
    
    def _record_request(self, user_id: str, ip_address: str, current_time: float):
        """记录请求"""
        self.user_minute_requests[user_id].append(current_time)
        self.user_hour_requests[user_id].append(current_time)
        self.ip_minute_requests[ip_address].append(current_time)
        self.ip_hour_requests[ip_address].append(current_time)
    
    def _cleanup_expired_requests(self, current_time: float):
        """清理过期请求记录"""
        minute_cutoff = current_time - 60
        hour_cutoff = current_time - 3600
        
        # 清理用户记录
        for user_id in list(self.user_minute_requests.keys()):
            minute_requests = self.user_minute_requests[user_id]
            while minute_requests and minute_requests[0] < minute_cutoff:
                minute_requests.popleft()
            
            hour_requests = self.user_hour_requests[user_id]
            while hour_requests and hour_requests[0] < hour_cutoff:
                hour_requests.popleft()
            
            # 如果队列为空，删除记录
            if not minute_requests:
                del self.user_minute_requests[user_id]
            if not hour_requests:
                del self.user_hour_requests[user_id]
        
        # 清理IP记录
        for ip_address in list(self.ip_minute_requests.keys()):
            minute_requests = self.ip_minute_requests[ip_address]
            while minute_requests and minute_requests[0] < minute_cutoff:
                minute_requests.popleft()
            
            hour_requests = self.ip_hour_requests[ip_address]
            while hour_requests and hour_requests[0] < hour_cutoff:
                hour_requests.popleft()
            
            # 如果队列为空，删除记录
            if not minute_requests:
                del self.ip_minute_requests[ip_address]
            if not hour_requests:
                del self.ip_hour_requests[ip_address]
    
    def _start_cleanup_task(self):
        """启动清理任务"""
        async def cleanup_task():
            while True:
                try:
                    current_time = time.time()
                    self._cleanup_expired_requests(current_time)
                    await asyncio.sleep(60)  # 每分钟清理一次
                except Exception as e:
                    logger.error(f"速率限制器清理任务失败: {str(e)}")
                    await asyncio.sleep(60)
        
        # 启动后台清理任务
        asyncio.create_task(cleanup_task())
    
    def get_remaining_requests(self, user_id: str, ip_address: str) -> Dict[str, int]:
        """获取剩余请求数"""
        current_time = time.time()
        
        # 清理过期记录
        self._cleanup_expired_requests(current_time)
        
        # 计算用户剩余请求数
        user_minute_remaining = max(0, self.max_requests_per_minute - len(self.user_minute_requests[user_id]))
        user_hour_remaining = max(0, self.max_requests_per_hour - len(self.user_hour_requests[user_id]))
        
        # 计算IP剩余请求数
        ip_max_per_minute = min(self.max_requests_per_minute * 2, 120)
        ip_max_per_hour = min(self.max_requests_per_hour * 2, 2000)
        
        ip_minute_remaining = max(0, ip_max_per_minute - len(self.ip_minute_requests[ip_address]))
        ip_hour_remaining = max(0, ip_max_per_hour - len(self.ip_hour_requests[ip_address]))
        
        return {
            "user_minute_remaining": user_minute_remaining,
            "user_hour_remaining": user_hour_remaining,
            "ip_minute_remaining": ip_minute_remaining,
            "ip_hour_remaining": ip_hour_remaining,
            "minute_remaining": min(user_minute_remaining, ip_minute_remaining),
            "hour_remaining": min(user_hour_remaining, ip_hour_remaining)
        }
    
    def get_stats(self) -> Dict[str, int]:
        """获取速率限制统计"""
        return {
            "total_users_tracked": len(self.user_minute_requests),
            "total_ips_tracked": len(self.ip_minute_requests),
            "max_requests_per_minute": self.max_requests_per_minute,
            "max_requests_per_hour": self.max_requests_per_hour
        }