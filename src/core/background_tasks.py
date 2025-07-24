"""
后台任务管理器 (V2.2重构)
管理异步日志处理和定时清理任务
"""
import asyncio
from typing import Dict, Any, List, Optional, Callable
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass

from src.services.async_log_service import get_async_log_service
from src.utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class TaskInfo:
    """任务信息"""
    name: str
    func: Callable
    interval_seconds: float
    is_running: bool = False
    last_run: Optional[datetime] = None
    next_run: Optional[datetime] = None
    error_count: int = 0
    max_errors: int = 5


class BackgroundTaskManager:
    """后台任务管理器"""
    
    def __init__(self):
        self.logger = logger
        self.tasks: Dict[str, TaskInfo] = {}
        self.is_running = False
        self.main_loop_task: Optional[asyncio.Task] = None
        self.executor = ThreadPoolExecutor(max_workers=4)
        
        # 注册默认任务
        self._register_default_tasks()
    
    def _register_default_tasks(self):
        """注册默认后台任务"""
        # 异步日志处理任务
        self.register_task(
            name="async_log_processor",
            func=self._run_log_processor,
            interval_seconds=5.0
        )
        
        # 系统监控任务
        self.register_task(
            name="system_monitor",
            func=self._run_system_monitor,
            interval_seconds=60.0
        )
    
    def register_task(
        self,
        name: str,
        func: Callable,
        interval_seconds: float,
        max_errors: int = 5
    ):
        """注册后台任务"""
        task_info = TaskInfo(
            name=name,
            func=func,
            interval_seconds=interval_seconds,
            max_errors=max_errors
        )
        self.tasks[name] = task_info
        self.logger.info(f"注册后台任务: {name}, 间隔: {interval_seconds}秒")
    
    def unregister_task(self, name: str):
        """取消注册后台任务"""
        if name in self.tasks:
            task_info = self.tasks[name]
            task_info.is_running = False
            del self.tasks[name]
            self.logger.info(f"取消注册后台任务: {name}")
    
    async def start(self):
        """启动后台任务管理器"""
        if self.is_running:
            return
        
        self.is_running = True
        self.main_loop_task = asyncio.create_task(self._main_loop())
        self.logger.info("后台任务管理器启动")
    
    async def stop(self):
        """停止后台任务管理器"""
        if not self.is_running:
            return
        
        self.is_running = False
        
        # 停止所有任务
        for task_info in self.tasks.values():
            task_info.is_running = False
        
        # 等待主循环结束
        if self.main_loop_task:
            try:
                await asyncio.wait_for(self.main_loop_task, timeout=10.0)
            except asyncio.TimeoutError:
                self.main_loop_task.cancel()
        
        # 关闭线程池
        self.executor.shutdown(wait=True)
        
        self.logger.info("后台任务管理器停止")
    
    async def _main_loop(self):
        """主循环"""
        while self.is_running:
            try:
                current_time = datetime.now()
                
                for task_name, task_info in self.tasks.items():
                    if not self.is_running:
                        break
                    
                    # 检查任务是否需要执行
                    if self._should_run_task(task_info, current_time):
                        asyncio.create_task(self._execute_task(task_info))
                
                await asyncio.sleep(1.0)  # 主循环间隔
                
            except Exception as e:
                self.logger.error(f"后台任务主循环异常: {str(e)}")
                await asyncio.sleep(1.0)
    
    def _should_run_task(self, task_info: TaskInfo, current_time: datetime) -> bool:
        """判断任务是否应该执行"""
        if task_info.is_running:
            return False
        
        if task_info.error_count >= task_info.max_errors:
            return False
        
        if task_info.last_run is None:
            return True
        
        elapsed = (current_time - task_info.last_run).total_seconds()
        return elapsed >= task_info.interval_seconds
    
    async def _execute_task(self, task_info: TaskInfo):
        """执行单个任务"""
        if task_info.is_running:
            return
        
        task_info.is_running = True
        start_time = datetime.now()
        
        try:
            # 执行任务
            if asyncio.iscoroutinefunction(task_info.func):
                await task_info.func()
            else:
                # 在线程池中执行同步函数
                loop = asyncio.get_event_loop()
                await loop.run_in_executor(self.executor, task_info.func)
            
            # 任务成功，重置错误计数
            task_info.error_count = 0
            task_info.last_run = start_time
            
            execution_time = (datetime.now() - start_time).total_seconds()
            self.logger.debug(f"任务执行完成: {task_info.name}, 耗时: {execution_time:.2f}秒")
            
        except Exception as e:
            task_info.error_count += 1
            self.logger.error(f"任务执行失败: {task_info.name}, 错误: {str(e)}, "
                            f"错误次数: {task_info.error_count}/{task_info.max_errors}")
            
            if task_info.error_count >= task_info.max_errors:
                self.logger.error(f"任务达到最大错误次数，已停用: {task_info.name}")
        
        finally:
            task_info.is_running = False
    
    async def _run_log_processor(self):
        """运行异步日志处理器"""
        async_log_service = get_async_log_service()
        await async_log_service.processor._process_batch()
    
    async def _run_system_monitor(self):
        """运行系统监控"""
        try:
            # 获取队列状态
            async_log_service = get_async_log_service()
            queue_status = await async_log_service.get_queue_status()
            
            # 检查队列积压
            backlog = queue_status.get('backlog', 0)
            if backlog > 100:
                self.logger.warning(f"异步日志队列积压严重: {backlog} 条")
            
            # 记录系统监控信息
            self.logger.debug(f"系统监控: 日志队列积压={backlog}")
            
        except Exception as e:
            self.logger.error(f"系统监控执行失败: {str(e)}")
    
    def get_task_status(self) -> Dict[str, Any]:
        """获取所有任务状态"""
        status = {
            'manager_running': self.is_running,
            'total_tasks': len(self.tasks),
            'tasks': {}
        }
        
        for name, task_info in self.tasks.items():
            status['tasks'][name] = {
                'name': task_info.name,
                'interval_seconds': task_info.interval_seconds,
                'is_running': task_info.is_running,
                'last_run': task_info.last_run.isoformat() if task_info.last_run else None,
                'error_count': task_info.error_count,
                'max_errors': task_info.max_errors,
                'status': 'disabled' if task_info.error_count >= task_info.max_errors else 'active'
            }
        
        return status
    
    async def force_run_task(self, task_name: str) -> bool:
        """强制运行指定任务"""
        if task_name not in self.tasks:
            return False
        
        task_info = self.tasks[task_name]
        if task_info.is_running:
            return False
        
        await self._execute_task(task_info)
        return True
    
    def reset_task_errors(self, task_name: str) -> bool:
        """重置任务错误计数"""
        if task_name not in self.tasks:
            return False
        
        self.tasks[task_name].error_count = 0
        self.logger.info(f"重置任务错误计数: {task_name}")
        return True


# 全局后台任务管理器
_task_manager = None


def get_task_manager() -> BackgroundTaskManager:
    """获取后台任务管理器实例（单例模式）"""
    global _task_manager
    if _task_manager is None:
        _task_manager = BackgroundTaskManager()
    return _task_manager


async def start_background_tasks():
    """启动后台任务"""
    manager = get_task_manager()
    await manager.start()


async def stop_background_tasks():
    """停止后台任务"""
    manager = get_task_manager()
    await manager.stop()