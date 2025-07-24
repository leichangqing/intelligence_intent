"""
服务工厂 (V2.2重构)
用于创建集成了审计日志和缓存失效的服务实例
"""
from typing import Optional

from src.services.cache_service import CacheService
from src.services.audit_service import AuditService
from src.services.cache_invalidation_service import CacheInvalidationService
from src.services.intent_service import IntentService
from src.services.slot_service import SlotService
from src.core.nlu_engine import NLUEngine
from src.utils.logger import get_logger

logger = get_logger(__name__)


class ServiceFactory:
    """服务工厂类"""
    
    def __init__(self, cache_service: CacheService, nlu_engine: NLUEngine):
        self.cache_service = cache_service
        self.nlu_engine = nlu_engine
        
        # 创建共享的审计和缓存失效服务
        self.audit_service = AuditService()
        self.cache_invalidation_service = CacheInvalidationService(cache_service)
    
    def create_intent_service(self) -> IntentService:
        """
        创建增强的意图服务
        
        Returns:
            IntentService: 集成了审计日志和缓存失效的意图服务
        """
        try:
            service = IntentService(
                cache_service=self.cache_service,
                nlu_engine=self.nlu_engine,
                audit_service=self.audit_service,
                cache_invalidation_service=self.cache_invalidation_service
            )
            
            logger.info("创建增强的意图服务成功")
            return service
            
        except Exception as e:
            logger.error(f"创建意图服务失败: {str(e)}")
            raise
    
    def create_slot_service(self) -> SlotService:
        """
        创建增强的槽位服务
        
        Returns:
            SlotService: 集成了审计日志和缓存失效的槽位服务
        """
        try:
            service = SlotService(
                cache_service=self.cache_service,
                nlu_engine=self.nlu_engine,
                audit_service=self.audit_service,
                cache_invalidation_service=self.cache_invalidation_service
            )
            
            logger.info("创建增强的槽位服务成功")
            return service
            
        except Exception as e:
            logger.error(f"创建槽位服务失败: {str(e)}")
            raise
    
    def get_audit_service(self) -> AuditService:
        """获取审计服务实例"""
        return self.audit_service
    
    def get_cache_invalidation_service(self) -> CacheInvalidationService:
        """获取缓存失效服务实例"""
        return self.cache_invalidation_service


# 全局服务工厂实例
_service_factory: Optional[ServiceFactory] = None


def initialize_service_factory(cache_service: CacheService, nlu_engine: NLUEngine) -> ServiceFactory:
    """
    初始化全局服务工厂
    
    Args:
        cache_service: 缓存服务实例
        nlu_engine: NLU引擎实例
        
    Returns:
        ServiceFactory: 服务工厂实例
    """
    global _service_factory
    _service_factory = ServiceFactory(cache_service, nlu_engine)
    logger.info("服务工厂初始化完成")
    return _service_factory


def get_service_factory() -> ServiceFactory:
    """
    获取全局服务工厂实例
    
    Returns:
        ServiceFactory: 服务工厂实例
        
    Raises:
        RuntimeError: 如果服务工厂未初始化
    """
    if _service_factory is None:
        raise RuntimeError("服务工厂未初始化，请先调用 initialize_service_factory()")
    
    return _service_factory


def get_enhanced_intent_service() -> IntentService:
    """
    获取增强的意图服务实例
    
    Returns:
        IntentService: 集成了审计日志和缓存失效的意图服务
    """
    factory = get_service_factory()
    return factory.create_intent_service()


def get_enhanced_slot_service() -> SlotService:
    """
    获取增强的槽位服务实例
    
    Returns:
        SlotService: 集成了审计日志和缓存失效的槽位服务
    """
    factory = get_service_factory()
    return factory.create_slot_service()


def get_audit_service() -> AuditService:
    """
    获取审计服务实例
    
    Returns:
        AuditService: 审计服务实例
    """
    factory = get_service_factory()
    return factory.get_audit_service()


def get_cache_invalidation_service() -> CacheInvalidationService:
    """
    获取缓存失效服务实例
    
    Returns:
        CacheInvalidationService: 缓存失效服务实例
    """
    factory = get_service_factory()
    return factory.get_cache_invalidation_service()


# 兼容性函数，保持向后兼容
def create_intent_service(cache_service: CacheService, nlu_engine: NLUEngine) -> IntentService:
    """
    创建意图服务（兼容性函数）
    
    Args:
        cache_service: 缓存服务
        nlu_engine: NLU引擎
        
    Returns:
        IntentService: 意图服务实例
    """
    logger.warning("使用兼容性函数创建意图服务，建议使用 get_enhanced_intent_service()")
    return IntentService(cache_service, nlu_engine)


def create_slot_service(cache_service: CacheService, nlu_engine: NLUEngine) -> SlotService:
    """
    创建槽位服务（兼容性函数）
    
    Args:
        cache_service: 缓存服务
        nlu_engine: NLU引擎
        
    Returns:
        SlotService: 槽位服务实例
    """
    logger.warning("使用兼容性函数创建槽位服务，建议使用 get_enhanced_slot_service()")
    return SlotService(cache_service, nlu_engine)