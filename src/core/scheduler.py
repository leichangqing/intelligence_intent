"""
通用任务调度器 (V2.2重构)
支持Cron表达式和定时任务调度
"""
import asyncio
from typing import Dict, Any, List, Optional, Callable, Union
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from enum import Enum
import re

from src.utils.logger import get_logger

logger = get_logger(__name__)


class ScheduleType(Enum):
    """调度类型"""
    INTERVAL = "interval"  # 间隔调度
    CRON = "cron"         # Cron表达式调度
    ONCE = "once"         # 一次性调度


@dataclass
class ScheduledTask:
    """调度任务"""
    name: str
    func: Callable
    schedule_type: ScheduleType
    schedule_expr: str  # 调度表达式（间隔秒数、cron表达式等）
    enabled: bool = True
    max_retries: int = 3
    retry_delay: int = 60
    timeout: Optional[int] = None
    
    # 运行时状态
    last_run: Optional[datetime] = None
    next_run: Optional[datetime] = None
    run_count: int = 0
    error_count: int = 0
    last_error: Optional[str] = None
    is_running: bool = False


class CronParser:
    """简单的Cron表达式解析器"""
    
    def __init__(self, cron_expr: str):
        self.cron_expr = cron_expr.strip()
        self.parts = self.cron_expr.split()
        
        if len(self.parts) != 5:
            raise ValueError(f"无效的Cron表达式，需要5个字段: {cron_expr}")
        
        self.minute, self.hour, self.day, self.month, self.weekday = self.parts
    
    def next_run_time(self, from_time: datetime) -> datetime:
        """计算下次运行时间"""
        # 这是一个简化版本，只支持基本的Cron表达式
        current = from_time.replace(second=0, microsecond=0)
        
        # 简单实现：支持 * 和具体数字
        minute = self._parse_field(self.minute, 0, 59)
        hour = self._parse_field(self.hour, 0, 23)
        
        # 找到下一个匹配的时间
        next_time = current + timedelta(minutes=1)
        
        while True:
            if (self._matches_field(next_time.minute, minute) and 
                self._matches_field(next_time.hour, hour)):
                return next_time
            
            next_time += timedelta(minutes=1)
            
            # 防止无限循环
            if next_time > current + timedelta(days=1):
                break
        
        return current + timedelta(days=1)
    
    def _parse_field(self, field: str, min_val: int, max_val: int) -> List[int]:
        """解析Cron字段"""
        if field == '*':
            return list(range(min_val, max_val + 1))
        
        if ',' in field:
            return [int(x) for x in field.split(',')]
        
        if '-' in field:
            start, end = field.split('-')
            return list(range(int(start), int(end) + 1))
        
        return [int(field)]
    
    def _matches_field(self, value: int, allowed_values: List[int]) -> bool:
        """检查值是否匹配字段"""
        return value in allowed_values


class TaskScheduler:
    """任务调度器"""
    
    def __init__(self):
        self.logger = logger
        self.tasks: Dict[str, ScheduledTask] = {}
        self.is_running = False
        self.scheduler_task: Optional[asyncio.Task] = None
    
    def add_task(
        self,
        name: str,
        func: Callable,
        schedule_type: ScheduleType,
        schedule_expr: str,
        **kwargs
    ) -> ScheduledTask:
        """添加调度任务"""
        task = ScheduledTask(
            name=name,
            func=func,
            schedule_type=schedule_type,
            schedule_expr=schedule_expr,
            **kwargs
        )
        
        # 计算初始的下次运行时间
        task.next_run = self._calculate_next_run(task, datetime.now())
        
        self.tasks[name] = task
        self.logger.info(f"添加调度任务: {name}, 类型: {schedule_type.value}, 表达式: {schedule_expr}")
        
        return task
    
    def remove_task(self, name: str) -> bool:
        """移除调度任务"""
        if name in self.tasks:
            del self.tasks[name]
            self.logger.info(f"移除调度任务: {name}")
            return True
        return False
    
    def enable_task(self, name: str) -> bool:
        """启用任务"""
        if name in self.tasks:
            self.tasks[name].enabled = True
            return True
        return False
    
    def disable_task(self, name: str) -> bool:
        """禁用任务"""
        if name in self.tasks:
            self.tasks[name].enabled = False
            return True
        return False
    
    async def start(self):
        """启动调度器"""
        if self.is_running:
            return
        
        self.is_running = True
        self.scheduler_task = asyncio.create_task(self._scheduler_loop())
        self.logger.info("任务调度器启动")
    
    async def stop(self):
        """停止调度器"""
        if not self.is_running:
            return
        
        self.is_running = False
        
        # 等待所有正在运行的任务完成
        running_tasks = [task for task in self.tasks.values() if task.is_running]
        if running_tasks:
            self.logger.info(f"等待 {len(running_tasks)} 个任务完成...")
            # 给正在运行的任务一些时间完成
            await asyncio.sleep(5)
        
        if self.scheduler_task:
            self.scheduler_task.cancel()
            try:
                await self.scheduler_task
            except asyncio.CancelledError:
                pass
        
        self.logger.info("任务调度器停止")
    
    async def _scheduler_loop(self):
        """调度器主循环"""
        while self.is_running:
            try:
                current_time = datetime.now()
                
                for task in list(self.tasks.values()):
                    if not self.is_running:
                        break
                    
                    if self._should_run_task(task, current_time):
                        # 异步执行任务，不等待完成
                        asyncio.create_task(self._execute_task(task))
                
                await asyncio.sleep(1)  # 每秒检查一次
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"调度器循环异常: {str(e)}")
                await asyncio.sleep(1)
    
    def _should_run_task(self, task: ScheduledTask, current_time: datetime) -> bool:
        """判断任务是否应该运行"""
        if not task.enabled or task.is_running:
            return False
        
        if task.error_count >= task.max_retries:
            return False
        
        if task.next_run and current_time >= task.next_run:
            return True
        
        return False
    
    async def _execute_task(self, task: ScheduledTask):
        """执行任务"""
        if task.is_running:
            return
        
        task.is_running = True
        start_time = datetime.now()
        
        try:
            self.logger.debug(f"开始执行任务: {task.name}")
            
            # 执行任务
            if asyncio.iscoroutinefunction(task.func):
                if task.timeout:
                    await asyncio.wait_for(task.func(), timeout=task.timeout)
                else:
                    await task.func()
            else:
                # 同步函数在线程池中执行
                loop = asyncio.get_event_loop()
                if task.timeout:
                    await asyncio.wait_for(
                        loop.run_in_executor(None, task.func),
                        timeout=task.timeout
                    )
                else:
                    await loop.run_in_executor(None, task.func)
            
            # 任务成功
            task.last_run = start_time
            task.run_count += 1
            task.error_count = 0
            task.last_error = None
            
            # 计算下次运行时间
            task.next_run = self._calculate_next_run(task, start_time)
            
            execution_time = (datetime.now() - start_time).total_seconds()
            self.logger.info(f"任务执行成功: {task.name}, 耗时: {execution_time:.2f}秒")
            
        except asyncio.TimeoutError:
            task.error_count += 1
            task.last_error = f"任务超时 (>{task.timeout}s)"
            self.logger.error(f"任务执行超时: {task.name}")
        except Exception as e:
            task.error_count += 1
            task.last_error = str(e)
            self.logger.error(f"任务执行失败: {task.name}, 错误: {str(e)}")
            
            # 如果还有重试次数，设置重试时间
            if task.error_count < task.max_retries:
                task.next_run = datetime.now() + timedelta(seconds=task.retry_delay)
        
        finally:
            task.is_running = False
    
    def _calculate_next_run(self, task: ScheduledTask, from_time: datetime) -> Optional[datetime]:
        """计算下次运行时间"""
        if task.schedule_type == ScheduleType.ONCE:
            return None  # 一次性任务不再运行
        
        elif task.schedule_type == ScheduleType.INTERVAL:
            interval = int(task.schedule_expr)
            return from_time + timedelta(seconds=interval)
        
        elif task.schedule_type == ScheduleType.CRON:
            try:
                cron_parser = CronParser(task.schedule_expr)
                return cron_parser.next_run_time(from_time)
            except Exception as e:
                self.logger.error(f"解析Cron表达式失败: {task.schedule_expr}, 错误: {str(e)}")
                # 回退到默认间隔（1小时）
                return from_time + timedelta(hours=1)
        
        return None
    
    def get_task_status(self) -> Dict[str, Any]:
        """获取任务状态"""
        status = {
            'scheduler_running': self.is_running,
            'total_tasks': len(self.tasks),
            'enabled_tasks': len([t for t in self.tasks.values() if t.enabled]),
            'running_tasks': len([t for t in self.tasks.values() if t.is_running]),
            'failed_tasks': len([t for t in self.tasks.values() if t.error_count >= t.max_retries]),
            'tasks': []
        }
        
        for task in self.tasks.values():
            task_info = {
                'name': task.name,
                'schedule_type': task.schedule_type.value,
                'schedule_expr': task.schedule_expr,
                'enabled': task.enabled,
                'is_running': task.is_running,
                'last_run': task.last_run.isoformat() if task.last_run else None,
                'next_run': task.next_run.isoformat() if task.next_run else None,
                'run_count': task.run_count,
                'error_count': task.error_count,
                'last_error': task.last_error,
                'status': self._get_task_status_text(task)
            }
            status['tasks'].append(task_info)
        
        return status
    
    def _get_task_status_text(self, task: ScheduledTask) -> str:
        """获取任务状态文本"""
        if not task.enabled:
            return 'disabled'
        elif task.is_running:
            return 'running'
        elif task.error_count >= task.max_retries:
            return 'failed'
        elif task.error_count > 0:
            return 'error'
        else:
            return 'active'
    
    async def run_task_now(self, name: str) -> bool:
        """立即运行指定任务"""
        if name not in self.tasks:
            return False
        
        task = self.tasks[name]
        if task.is_running:
            return False
        
        await self._execute_task(task)
        return True


# 全局调度器实例
_scheduler = None


def get_scheduler() -> TaskScheduler:
    """获取任务调度器实例（单例模式）"""
    global _scheduler
    if _scheduler is None:
        _scheduler = TaskScheduler()
    return _scheduler