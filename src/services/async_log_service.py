"""
异步日志处理服务 (V2.2重构)
处理async_log_queue表中的日志记录
"""
import asyncio
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from enum import Enum

from src.models.audit import AsyncLogQueue, ApiCallLog, SecurityAuditLog
from src.utils.logger import get_logger

logger = get_logger(__name__)


class LogType(Enum):
    """日志类型枚举"""
    API_CALL = "api_call"
    SECURITY_AUDIT = "security_audit"
    PERFORMANCE = "performance"
    ERROR = "error"


class AsyncLogProcessor:
    """异步日志处理器"""
    
    def __init__(self):
        self.logger = logger
        self.is_running = False
        self.batch_size = 50
        self.process_interval = 5  # 秒
        
    async def start(self):
        """启动日志处理器"""
        if self.is_running:
            return
            
        self.is_running = True
        self.logger.info("异步日志处理器启动")
        
        while self.is_running:
            try:
                await self._process_batch()
                await asyncio.sleep(self.process_interval)
            except Exception as e:
                self.logger.error(f"日志处理循环异常: {str(e)}")
                await asyncio.sleep(1)
    
    async def stop(self):
        """停止日志处理器"""
        self.is_running = False
        # 处理剩余日志
        await self._process_batch()
        self.logger.info("异步日志处理器停止")
    
    async def _process_batch(self):
        """批量处理日志"""
        try:
            # 获取待处理的日志
            pending_logs = list(
                AsyncLogQueue
                .select()
                .where(AsyncLogQueue.status == 'pending')
                .order_by(AsyncLogQueue.priority.desc(), AsyncLogQueue.created_at.asc())
                .limit(self.batch_size)
            )
            
            if not pending_logs:
                return
                
            processed_count = 0
            failed_count = 0
            
            for log_entry in pending_logs:
                try:
                    log_entry.start_processing()
                    
                    success = await self._process_single_log(log_entry)
                    
                    if success:
                        log_entry.mark_completed()
                        processed_count += 1
                    else:
                        log_entry.mark_failed("处理失败")
                        failed_count += 1
                        
                except Exception as e:
                    log_entry.mark_failed(str(e))
                    failed_count += 1
                    self.logger.error(f"处理日志失败: {log_entry.id}, 错误: {str(e)}")
            
            if processed_count > 0 or failed_count > 0:
                self.logger.info(f"批量处理完成: 成功={processed_count}, 失败={failed_count}")
                
        except Exception as e:
            self.logger.error(f"批量处理异常: {str(e)}")
    
    async def _process_single_log(self, log_entry: AsyncLogQueue) -> bool:
        """处理单条日志"""
        try:
            log_data = log_entry.get_log_data()
            log_type = log_entry.log_type
            
            if log_type == LogType.API_CALL.value:
                return await self._process_api_call_log(log_data)
            elif log_type == LogType.SECURITY_AUDIT.value:
                return await self._process_security_audit_log(log_data)
            elif log_type == LogType.PERFORMANCE.value:
                return await self._process_performance_log(log_data)
            elif log_type == LogType.ERROR.value:
                return await self._process_error_log(log_data)
            else:
                self.logger.warning(f"未知日志类型: {log_type}")
                return False
                
        except Exception as e:
            self.logger.error(f"处理单条日志异常: {str(e)}")
            return False
    
    async def _process_api_call_log(self, log_data: Dict[str, Any]) -> bool:
        """处理API调用日志"""
        try:
            ApiCallLog.create(
                request_id=log_data.get('request_id'),
                api_endpoint=log_data.get('api_endpoint'),
                http_method=log_data.get('http_method'),
                user_id=log_data.get('user_id'),
                api_key_hash=log_data.get('api_key_hash'),
                request_headers=log_data.get('request_headers'),
                request_body=log_data.get('request_body'),
                response_status=log_data.get('response_status'),
                response_headers=log_data.get('response_headers'),
                response_body=log_data.get('response_body'),
                response_time_ms=log_data.get('response_time_ms'),
                request_size_bytes=log_data.get('request_size_bytes'),
                response_size_bytes=log_data.get('response_size_bytes'),
                client_ip=log_data.get('client_ip'),
                user_agent=log_data.get('user_agent'),
                referer=log_data.get('referer'),
                rate_limit_remaining=log_data.get('rate_limit_remaining'),
                error_message=log_data.get('error_message'),
                processing_components=log_data.get('processing_components')
            )
            return True
        except Exception as e:
            self.logger.error(f"写入API调用日志失败: {str(e)}")
            return False
    
    async def _process_security_audit_log(self, log_data: Dict[str, Any]) -> bool:
        """处理安全审计日志"""
        try:
            SecurityAuditLog.create(
                user_id=log_data.get('user_id'),
                ip_address=log_data.get('ip_address'),
                user_agent=log_data.get('user_agent'),
                action_type=log_data.get('action_type'),
                resource_type=log_data.get('resource_type'),
                resource_id=log_data.get('resource_id'),
                action_details=log_data.get('action_details'),
                risk_level=log_data.get('risk_level', 'low'),
                status=log_data.get('status')
            )
            return True
        except Exception as e:
            self.logger.error(f"写入安全审计日志失败: {str(e)}")
            return False
    
    async def _process_performance_log(self, log_data: Dict[str, Any]) -> bool:
        """处理性能日志"""
        try:
            # 这里可以写入专门的性能监控表或发送到外部系统
            self.logger.info(f"性能日志: {log_data}")
            return True
        except Exception as e:
            self.logger.error(f"处理性能日志失败: {str(e)}")
            return False
    
    async def _process_error_log(self, log_data: Dict[str, Any]) -> bool:
        """处理错误日志"""
        try:
            # 这里可以发送告警或写入专门的错误日志表
            self.logger.error(f"系统错误: {log_data}")
            return True
        except Exception as e:
            self.logger.error(f"处理错误日志失败: {str(e)}")
            return False


class AsyncLogService:
    """异步日志服务"""
    
    def __init__(self):
        self.logger = logger
        self.processor = AsyncLogProcessor()
    
    async def queue_log(
        self,
        log_type: LogType,
        log_data: Dict[str, Any],
        priority: int = 1,
        max_retries: int = 3
    ) -> AsyncLogQueue:
        """添加日志到处理队列"""
        try:
            log_entry = AsyncLogQueue.create(
                log_type=log_type.value,
                log_data=log_data,
                priority=priority,
                max_retries=max_retries
            )
            
            self.logger.debug(f"日志已加入队列: {log_type.value}, ID: {log_entry.id}")
            return log_entry
            
        except Exception as e:
            self.logger.error(f"添加日志到队列失败: {str(e)}")
            raise
    
    async def queue_api_call_log(
        self,
        request_id: str,
        api_endpoint: str,
        http_method: str,
        response_status: int,
        response_time_ms: int,
        user_id: Optional[str] = None,
        client_ip: Optional[str] = None,
        **kwargs
    ):
        """添加API调用日志到队列"""
        log_data = {
            'request_id': request_id,
            'api_endpoint': api_endpoint,
            'http_method': http_method,
            'response_status': response_status,
            'response_time_ms': response_time_ms,
            'user_id': user_id,
            'client_ip': client_ip,
            **kwargs
        }
        
        return await self.queue_log(LogType.API_CALL, log_data)
    
    async def queue_security_audit_log(
        self,
        user_id: Optional[str],
        ip_address: str,
        action_type: str,
        status: str,
        risk_level: str = 'low',
        **kwargs
    ):
        """添加安全审计日志到队列"""
        log_data = {
            'user_id': user_id,
            'ip_address': ip_address,
            'action_type': action_type,
            'status': status,
            'risk_level': risk_level,
            **kwargs
        }
        
        priority = 3 if risk_level in ['high', 'critical'] else 1
        return await self.queue_log(LogType.SECURITY_AUDIT, log_data, priority)
    
    async def get_queue_status(self) -> Dict[str, Any]:
        """获取队列状态"""
        try:
            stats = {}
            
            # 按状态统计
            for status in ['pending', 'processing', 'completed', 'failed']:
                count = AsyncLogQueue.select().where(AsyncLogQueue.status == status).count()
                stats[f'{status}_count'] = count
            
            # 按日志类型统计
            type_stats = {}
            for log_type in LogType:
                count = AsyncLogQueue.select().where(AsyncLogQueue.log_type == log_type.value).count()
                type_stats[log_type.value] = count
            
            # 队列积压情况
            backlog = AsyncLogQueue.select().where(AsyncLogQueue.status == 'pending').count()
            
            return {
                'status_stats': stats,
                'type_stats': type_stats,
                'backlog': backlog,
                'processor_running': self.processor.is_running,
                'generated_at': datetime.now().isoformat()
            }
            
        except Exception as e:
            self.logger.error(f"获取队列状态失败: {str(e)}")
            raise
    
    async def cleanup_old_logs(self, days_old: int = 30) -> Dict[str, Any]:
        """清理旧日志"""
        try:
            cutoff_date = datetime.now() - timedelta(days=days_old)
            
            # 删除已完成的旧日志
            deleted_count = (
                AsyncLogQueue
                .delete()
                .where(
                    (AsyncLogQueue.status == 'completed') &
                    (AsyncLogQueue.processed_at < cutoff_date)
                )
                .execute()
            )
            
            result = {
                'cutoff_date': cutoff_date.isoformat(),
                'deleted_count': deleted_count
            }
            
            self.logger.info(f"清理旧日志完成: {result}")
            return result
            
        except Exception as e:
            self.logger.error(f"清理旧日志失败: {str(e)}")
            raise
    
    async def start_processor(self):
        """启动日志处理器"""
        await self.processor.start()
    
    async def stop_processor(self):
        """停止日志处理器"""
        await self.processor.stop()


# 全局异步日志服务实例
_async_log_service = None


def get_async_log_service() -> AsyncLogService:
    """获取异步日志服务实例（单例模式）"""
    global _async_log_service
    if _async_log_service is None:
        _async_log_service = AsyncLogService()
    return _async_log_service