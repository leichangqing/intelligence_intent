"""
清理任务调度工作进程 (V2.2重构)
负责定时执行系统清理任务
"""
import asyncio
import signal
import sys
from typing import Optional
from datetime import datetime

from src.services.cleanup_service import get_cleanup_service
from src.utils.logger import get_logger

logger = get_logger(__name__)


class CleanupSchedulerWorker:
    """清理任务调度工作进程"""
    
    def __init__(self, interval_hours: int = 24):
        self.logger = logger
        self.cleanup_service = get_cleanup_service()
        self.interval_hours = interval_hours
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
            self.logger.info(f"清理调度工作进程启动，间隔: {self.interval_hours}小时")
            
            # 启动清理调度器
            await self.cleanup_service.start_scheduler(self.interval_hours)
            
            # 立即执行一次清理（可选）
            self.logger.info("执行初始清理任务...")
            initial_result = await self.cleanup_service.manual_cleanup()
            self.logger.info(f"初始清理完成: {initial_result}")
            
            # 等待关闭信号
            await self.shutdown_event.wait()
            
            # 停止清理调度器
            await self.cleanup_service.stop_scheduler()
            
            self.logger.info("清理调度工作进程停止")
            
        except Exception as e:
            self.logger.error(f"清理调度工作进程异常: {str(e)}")
            raise
    
    async def shutdown(self):
        """关闭工作进程"""
        if not self.is_running:
            return
        
        self.is_running = False
        self.shutdown_event.set()
        self.logger.info("清理调度工作进程正在关闭...")
    
    async def get_status(self) -> dict:
        """获取工作进程状态"""
        try:
            cleanup_stats = await self.cleanup_service.get_cleanup_statistics()
            
            return {
                'worker_type': 'cleanup_scheduler',
                'is_running': self.is_running,
                'interval_hours': self.interval_hours,
                'start_time': datetime.now().isoformat(),
                'cleanup_statistics': cleanup_stats
            }
        except Exception as e:
            self.logger.error(f"获取状态失败: {str(e)}")
            return {
                'worker_type': 'cleanup_scheduler',
                'is_running': self.is_running,
                'interval_hours': self.interval_hours,
                'error': str(e)
            }
    
    async def force_cleanup(self) -> dict:
        """强制执行清理"""
        try:
            self.logger.info("强制执行清理任务...")
            result = await self.cleanup_service.manual_cleanup()
            self.logger.info(f"强制清理完成: {result}")
            return result
        except Exception as e:
            self.logger.error(f"强制清理失败: {str(e)}")
            return {'error': str(e)}


async def main():
    """主函数"""
    # 从命令行参数或环境变量获取配置
    import os
    
    interval_hours = int(os.getenv('CLEANUP_INTERVAL_HOURS', '24'))
    
    worker = CleanupSchedulerWorker(interval_hours=interval_hours)
    
    try:
        await worker.start()
    except KeyboardInterrupt:
        logger.info("收到键盘中断，正在关闭...")
    except Exception as e:
        logger.error(f"工作进程异常退出: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())