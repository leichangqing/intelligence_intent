"""
日志处理工作进程 (V2.2重构)
负责异步处理日志队列中的记录
"""
import asyncio
import signal
import sys
from typing import Optional
from datetime import datetime

from src.services.async_log_service import get_async_log_service
from src.core.background_tasks import get_task_manager
from src.utils.logger import get_logger

logger = get_logger(__name__)


class LogProcessorWorker:
    """日志处理工作进程"""
    
    def __init__(self):
        self.logger = logger
        self.async_log_service = get_async_log_service()
        self.task_manager = get_task_manager()
        self.is_running = False
        self.shutdown_event = asyncio.Event()
        
        # 注册信号处理器
        self._setup_signal_handlers()
    
    def _setup_signal_handlers(self):
        """设置信号处理器"""
        def signal_handler(signum, frame):
            self.logger.info(f"收到信号 {signum}, 准备关闭...")
            asyncio.create_task(self.shutdown())
        
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
    
    async def start(self):
        """启动工作进程"""
        try:
            self.is_running = True
            self.logger.info("日志处理工作进程启动")
            
            # 启动后台任务管理器
            await self.task_manager.start()
            
            # 启动异步日志处理器
            processor_task = asyncio.create_task(
                self.async_log_service.start_processor()
            )
            
            # 等待关闭信号
            await self.shutdown_event.wait()
            
            # 停止处理器
            await self.async_log_service.stop_processor()
            processor_task.cancel()
            
            # 停止后台任务管理器
            await self.task_manager.stop()
            
            self.logger.info("日志处理工作进程停止")
            
        except Exception as e:
            self.logger.error(f"日志处理工作进程异常: {str(e)}")
            raise
    
    async def shutdown(self):
        """关闭工作进程"""
        if not self.is_running:
            return
        
        self.is_running = False
        self.shutdown_event.set()
        self.logger.info("日志处理工作进程正在关闭...")
    
    async def get_status(self) -> dict:
        """获取工作进程状态"""
        return {
            'worker_type': 'log_processor',
            'is_running': self.is_running,
            'start_time': datetime.now().isoformat(),
            'queue_status': await self.async_log_service.get_queue_status(),
            'task_manager_status': self.task_manager.get_task_status()
        }


async def main():
    """主函数"""
    worker = LogProcessorWorker()
    
    try:
        await worker.start()
    except KeyboardInterrupt:
        logger.info("收到键盘中断，正在关闭...")
    except Exception as e:
        logger.error(f"工作进程异常退出: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())