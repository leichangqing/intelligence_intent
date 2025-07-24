"""
定时清理服务 (V2.2重构)
替代原存储过程的会话清理功能
"""
import asyncio
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from enum import Enum

from src.models.conversation import Session, Conversation, UserContext
from src.models.audit import ConfigAuditLog, CacheInvalidationLog, AsyncLogQueue
from src.models.slot_value import SlotValue
from src.utils.logger import get_logger

logger = get_logger(__name__)


class CleanupType(Enum):
    """清理类型枚举"""
    EXPIRED_SESSIONS = "expired_sessions"
    OLD_CONVERSATIONS = "old_conversations"  
    EXPIRED_USER_CONTEXTS = "expired_user_contexts"
    OLD_AUDIT_LOGS = "old_audit_logs"
    OLD_CACHE_LOGS = "old_cache_logs"
    OLD_ASYNC_LOGS = "old_async_logs"
    INVALID_SLOT_VALUES = "invalid_slot_values"


class CleanupTask:
    """清理任务"""
    
    def __init__(
        self,
        cleanup_type: CleanupType,
        retention_days: int,
        batch_size: int = 1000,
        enabled: bool = True
    ):
        self.cleanup_type = cleanup_type
        self.retention_days = retention_days
        self.batch_size = batch_size
        self.enabled = enabled
        self.logger = logger.getChild(f"CleanupTask.{cleanup_type.value}")
    
    async def execute(self) -> Dict[str, Any]:
        """执行清理任务"""
        if not self.enabled:
            return {'status': 'skipped', 'reason': 'task disabled'}
        
        start_time = datetime.now()
        cutoff_date = start_time - timedelta(days=self.retention_days)
        
        try:
            if self.cleanup_type == CleanupType.EXPIRED_SESSIONS:
                result = await self._cleanup_expired_sessions(cutoff_date)
            elif self.cleanup_type == CleanupType.OLD_CONVERSATIONS:
                result = await self._cleanup_old_conversations(cutoff_date)
            elif self.cleanup_type == CleanupType.EXPIRED_USER_CONTEXTS:
                result = await self._cleanup_expired_user_contexts()
            elif self.cleanup_type == CleanupType.OLD_AUDIT_LOGS:
                result = await self._cleanup_old_audit_logs(cutoff_date)
            elif self.cleanup_type == CleanupType.OLD_CACHE_LOGS:
                result = await self._cleanup_old_cache_logs(cutoff_date)
            elif self.cleanup_type == CleanupType.OLD_ASYNC_LOGS:
                result = await self._cleanup_old_async_logs(cutoff_date)
            elif self.cleanup_type == CleanupType.INVALID_SLOT_VALUES:
                result = await self._cleanup_invalid_slot_values(cutoff_date)
            else:
                return {'status': 'error', 'message': f'未知清理类型: {self.cleanup_type}'}
            
            execution_time = (datetime.now() - start_time).total_seconds()
            
            result.update({
                'status': 'completed',
                'cleanup_type': self.cleanup_type.value,
                'cutoff_date': cutoff_date.isoformat(),
                'execution_time_seconds': execution_time,
                'completed_at': datetime.now().isoformat()
            })
            
            self.logger.info(f"清理任务完成: {result}")
            return result
            
        except Exception as e:
            execution_time = (datetime.now() - start_time).total_seconds()
            error_result = {
                'status': 'error',
                'cleanup_type': self.cleanup_type.value,
                'error': str(e),
                'execution_time_seconds': execution_time,
                'failed_at': datetime.now().isoformat()
            }
            
            self.logger.error(f"清理任务失败: {error_result}")
            return error_result
    
    async def _cleanup_expired_sessions(self, cutoff_date: datetime) -> Dict[str, Any]:
        """清理过期会话"""
        # 标记过期的活跃会话
        expired_count = (
            Session
            .update(session_state='expired')
            .where(
                (Session.session_state == 'active') &
                ((Session.expires_at < datetime.now()) | (Session.updated_at < cutoff_date))
            )
            .execute()
        )
        
        # 删除非常老的会话记录
        very_old_cutoff = datetime.now() - timedelta(days=self.retention_days * 2)
        deleted_count = (
            Session
            .delete()
            .where(
                (Session.session_state.in_(['expired', 'completed'])) &
                (Session.updated_at < very_old_cutoff)
            )
            .execute()
        )
        
        return {
            'expired_count': expired_count,
            'deleted_count': deleted_count,
            'total_processed': expired_count + deleted_count
        }
    
    async def _cleanup_old_conversations(self, cutoff_date: datetime) -> Dict[str, Any]:
        """清理旧对话记录"""
        # 删除旧的对话记录，但保留最近的记录用于分析
        deleted_count = (
            Conversation
            .delete()
            .where(
                (Conversation.created_at < cutoff_date) &
                (Conversation.status.in_(['completed', 'failed', 'api_error']))
            )
            .execute()
        )
        
        return {
            'deleted_count': deleted_count,
            'total_processed': deleted_count
        }
    
    async def _cleanup_expired_user_contexts(self) -> Dict[str, Any]:
        """清理过期的用户上下文"""
        current_time = datetime.now()
        
        # 删除已过期的用户上下文
        deleted_count = (
            UserContext
            .delete()
            .where(
                (UserContext.expires_at.is_null(False)) &
                (UserContext.expires_at < current_time)
            )
            .execute()
        )
        
        return {
            'deleted_count': deleted_count,
            'total_processed': deleted_count
        }
    
    async def _cleanup_old_audit_logs(self, cutoff_date: datetime) -> Dict[str, Any]:
        """清理旧审计日志"""
        # 分批删除以避免长时间锁表
        total_deleted = 0
        batch_deleted = self.batch_size
        
        while batch_deleted == self.batch_size:
            old_logs = list(
                ConfigAuditLog
                .select()
                .where(ConfigAuditLog.created_at < cutoff_date)
                .limit(self.batch_size)
            )
            
            if not old_logs:
                break
            
            log_ids = [log.id for log in old_logs]
            batch_deleted = (
                ConfigAuditLog
                .delete()
                .where(ConfigAuditLog.id.in_(log_ids))
                .execute()
            )
            
            total_deleted += batch_deleted
            
            # 短暂休眠避免过度占用资源
            await asyncio.sleep(0.1)
        
        return {
            'deleted_count': total_deleted,
            'total_processed': total_deleted
        }
    
    async def _cleanup_old_cache_logs(self, cutoff_date: datetime) -> Dict[str, Any]:
        """清理旧缓存失效日志"""
        deleted_count = (
            CacheInvalidationLog
            .delete()
            .where(
                (CacheInvalidationLog.invalidation_status == 'completed') &
                (CacheInvalidationLog.processed_at < cutoff_date)
            )
            .execute()
        )
        
        return {
            'deleted_count': deleted_count,
            'total_processed': deleted_count
        }
    
    async def _cleanup_old_async_logs(self, cutoff_date: datetime) -> Dict[str, Any]:
        """清理旧异步日志"""
        deleted_count = (
            AsyncLogQueue
            .delete()
            .where(
                (AsyncLogQueue.status == 'completed') &
                (AsyncLogQueue.processed_at < cutoff_date)
            )
            .execute()
        )
        
        return {
            'deleted_count': deleted_count,
            'total_processed': deleted_count
        }
    
    async def _cleanup_invalid_slot_values(self, cutoff_date: datetime) -> Dict[str, Any]:
        """清理无效槽位值"""
        deleted_count = (
            SlotValue
            .delete()
            .where(
                (SlotValue.validation_status == 'invalid') &
                (SlotValue.created_at < cutoff_date)
            )
            .execute()
        )
        
        return {
            'deleted_count': deleted_count,
            'total_processed': deleted_count
        }


class CleanupScheduler:
    """清理任务调度器"""
    
    def __init__(self):
        self.logger = logger.getChild(self.__class__.__name__)
        self.tasks: List[CleanupTask] = []
        self.is_running = False
        self.scheduler_task: Optional[asyncio.Task] = None
        
        # 默认清理任务配置
        self._initialize_default_tasks()
    
    def _initialize_default_tasks(self):
        """初始化默认清理任务"""
        default_tasks = [
            CleanupTask(CleanupType.EXPIRED_SESSIONS, retention_days=1),
            CleanupTask(CleanupType.EXPIRED_USER_CONTEXTS, retention_days=0),  # 立即清理过期的
            CleanupTask(CleanupType.OLD_CONVERSATIONS, retention_days=90),
            CleanupTask(CleanupType.OLD_AUDIT_LOGS, retention_days=180),
            CleanupTask(CleanupType.OLD_CACHE_LOGS, retention_days=30),
            CleanupTask(CleanupType.OLD_ASYNC_LOGS, retention_days=30),
            CleanupTask(CleanupType.INVALID_SLOT_VALUES, retention_days=30),
        ]
        
        self.tasks.extend(default_tasks)
    
    def add_task(self, task: CleanupTask):
        """添加清理任务"""
        self.tasks.append(task)
        self.logger.info(f"添加清理任务: {task.cleanup_type.value}")
    
    def remove_task(self, cleanup_type: CleanupType):
        """移除清理任务"""
        self.tasks = [task for task in self.tasks if task.cleanup_type != cleanup_type]
        self.logger.info(f"移除清理任务: {cleanup_type.value}")
    
    async def run_all_tasks(self) -> Dict[str, Any]:
        """运行所有清理任务"""
        start_time = datetime.now()
        results = []
        
        for task in self.tasks:
            try:
                result = await task.execute()
                results.append(result)
            except Exception as e:
                error_result = {
                    'status': 'error',
                    'cleanup_type': task.cleanup_type.value,
                    'error': str(e)
                }
                results.append(error_result)
                self.logger.error(f"执行清理任务失败: {task.cleanup_type.value}, 错误: {str(e)}")
        
        execution_time = (datetime.now() - start_time).total_seconds()
        
        # 统计结果
        completed_count = len([r for r in results if r.get('status') == 'completed'])
        error_count = len([r for r in results if r.get('status') == 'error'])
        skipped_count = len([r for r in results if r.get('status') == 'skipped'])
        
        summary = {
            'started_at': start_time.isoformat(),
            'completed_at': datetime.now().isoformat(),
            'execution_time_seconds': execution_time,
            'total_tasks': len(self.tasks),
            'completed_tasks': completed_count,
            'error_tasks': error_count,
            'skipped_tasks': skipped_count,
            'task_results': results
        }
        
        self.logger.info(f"清理任务批次完成: 总数={len(self.tasks)}, 成功={completed_count}, 失败={error_count}")
        return summary
    
    async def run_single_task(self, cleanup_type: CleanupType) -> Dict[str, Any]:
        """运行单个清理任务"""
        task = next((t for t in self.tasks if t.cleanup_type == cleanup_type), None)
        
        if not task:
            return {
                'status': 'error',
                'message': f'未找到清理任务: {cleanup_type.value}'
            }
        
        return await task.execute()
    
    async def start_scheduler(self, interval_hours: int = 24):
        """启动定时调度器"""
        if self.is_running:
            self.logger.warning("清理调度器已在运行中")
            return
        
        self.is_running = True
        self.scheduler_task = asyncio.create_task(
            self._scheduler_loop(interval_hours)
        )
        
        self.logger.info(f"清理调度器启动，间隔: {interval_hours}小时")
    
    async def stop_scheduler(self):
        """停止定时调度器"""
        if not self.is_running:
            return
        
        self.is_running = False
        
        if self.scheduler_task:
            self.scheduler_task.cancel()
            try:
                await self.scheduler_task
            except asyncio.CancelledError:
                pass
        
        self.logger.info("清理调度器已停止")
    
    async def _scheduler_loop(self, interval_hours: int):
        """调度器循环"""
        interval_seconds = interval_hours * 3600
        
        while self.is_running:
            try:
                await self.run_all_tasks()
                await asyncio.sleep(interval_seconds)
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"调度器循环异常: {str(e)}")
                await asyncio.sleep(60)  # 出错时短暂休眠
    
    def get_task_status(self) -> Dict[str, Any]:
        """获取任务状态"""
        return {
            'total_tasks': len(self.tasks),
            'enabled_tasks': len([t for t in self.tasks if t.enabled]),
            'is_running': self.is_running,
            'tasks': [
                {
                    'type': task.cleanup_type.value,
                    'retention_days': task.retention_days,
                    'enabled': task.enabled,
                    'batch_size': task.batch_size
                }
                for task in self.tasks
            ]
        }


class CleanupService:
    """清理服务"""
    
    def __init__(self):
        self.logger = logger
        self.scheduler = CleanupScheduler()
    
    async def manual_cleanup(
        self,
        cleanup_types: Optional[List[CleanupType]] = None
    ) -> Dict[str, Any]:
        """手动执行清理"""
        if cleanup_types:
            results = []
            for cleanup_type in cleanup_types:
                result = await self.scheduler.run_single_task(cleanup_type)
                results.append(result)
            
            return {
                'type': 'manual_selective',
                'results': results
            }
        else:
            return {
                'type': 'manual_all',
                'result': await self.scheduler.run_all_tasks()
            }
    
    async def get_cleanup_statistics(self) -> Dict[str, Any]:
        """获取清理统计信息"""
        try:
            stats = {}
            
            # 会话统计
            active_sessions = Session.select().where(Session.session_state == 'active').count()
            expired_sessions = Session.select().where(Session.session_state == 'expired').count()
            
            # 对话统计  
            total_conversations = Conversation.select().count()
            recent_conversations = Conversation.select().where(
                Conversation.created_at >= datetime.now() - timedelta(days=30)
            ).count()
            
            # 审计日志统计
            total_audit_logs = ConfigAuditLog.select().count()
            recent_audit_logs = ConfigAuditLog.select().where(
                ConfigAuditLog.created_at >= datetime.now() - timedelta(days=7)
            ).count()
            
            stats = {
                'sessions': {
                    'active': active_sessions,
                    'expired': expired_sessions,
                    'total': active_sessions + expired_sessions
                },
                'conversations': {
                    'total': total_conversations,
                    'recent_30_days': recent_conversations
                },
                'audit_logs': {
                    'total': total_audit_logs,
                    'recent_7_days': recent_audit_logs
                },
                'scheduler_status': self.scheduler.get_task_status(),
                'generated_at': datetime.now().isoformat()
            }
            
            return stats
            
        except Exception as e:
            self.logger.error(f"获取清理统计失败: {str(e)}")
            raise
    
    async def start_scheduler(self, interval_hours: int = 24):
        """启动定时调度器"""
        await self.scheduler.start_scheduler(interval_hours)
    
    async def stop_scheduler(self):
        """停止定时调度器"""
        await self.scheduler.stop_scheduler()


# 全局清理服务实例
_cleanup_service = None


def get_cleanup_service() -> CleanupService:
    """获取清理服务实例（单例模式）"""
    global _cleanup_service
    if _cleanup_service is None:
        _cleanup_service = CleanupService()
    return _cleanup_service