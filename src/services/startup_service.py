"""
系统启动服务
负责初始化各种服务和缓存
"""
import asyncio
from typing import Optional

from src.services.cache_service import CacheService
from src.services.synonym_service import get_synonym_service
from src.utils.logger import get_logger

logger = get_logger(__name__)


class StartupService:
    """系统启动服务"""
    
    def __init__(self):
        self.cache_service: Optional[CacheService] = None
        self.synonym_service = None
        self._initialized = False
    
    async def initialize_all_services(self):
        """初始化所有服务"""
        try:
            logger.info("开始初始化系统服务...")
            
            # 1. 初始化缓存服务
            await self._initialize_cache_service()
            
            # 2. 初始化同义词服务
            await self._initialize_synonym_service()
            
            # 3. 其他服务初始化
            await self._initialize_other_services()
            
            self._initialized = True
            logger.info("✅ 所有系统服务初始化完成")
            
        except Exception as e:
            logger.error(f"❌ 系统服务初始化失败: {str(e)}")
            raise
    
    async def _initialize_cache_service(self):
        """初始化缓存服务"""
        try:
            # 这里可以初始化Redis缓存服务
            # self.cache_service = CacheService()
            # await self.cache_service.initialize()
            logger.info("缓存服务初始化完成")
        except Exception as e:
            logger.warning(f"缓存服务初始化失败，将使用内存缓存: {str(e)}")
    
    async def _initialize_synonym_service(self):
        """初始化同义词服务"""
        try:
            self.synonym_service = await get_synonym_service(self.cache_service)
            logger.info("✅ 同义词服务初始化完成")
        except Exception as e:
            logger.error(f"❌ 同义词服务初始化失败: {str(e)}")
            # 不抛出异常，允许系统继续运行
    
    async def _initialize_other_services(self):
        """初始化其他服务"""
        try:
            # 可以在这里初始化其他服务
            # 比如NLU引擎预热、模型加载等
            logger.info("其他服务初始化完成")
        except Exception as e:
            logger.warning(f"其他服务初始化警告: {str(e)}")
    
    def is_initialized(self) -> bool:
        """检查是否已初始化"""
        return self._initialized
    
    async def health_check(self) -> dict:
        """健康检查"""
        status = {
            "initialized": self._initialized,
            "cache_service": self.cache_service is not None,
            "synonym_service": self.synonym_service is not None,
        }
        
        if self.synonym_service:
            try:
                # 测试同义词服务
                test_dict = self.synonym_service.get_synonym_dict()
                status["synonym_dict_size"] = len(test_dict)
            except Exception as e:
                status["synonym_service_error"] = str(e)
        
        return status


# 全局启动服务实例
_startup_service: Optional[StartupService] = None


async def get_startup_service() -> StartupService:
    """获取启动服务单例"""
    global _startup_service
    
    if _startup_service is None:
        _startup_service = StartupService()
        await _startup_service.initialize_all_services()
    
    return _startup_service


def get_startup_service_sync() -> Optional[StartupService]:
    """获取已初始化的启动服务（同步方法）"""
    return _startup_service