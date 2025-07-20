"""
FastAPI应用主入口
"""
from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
import time
import asyncio
from contextlib import asynccontextmanager

from src.config.settings import settings
from src.config.database import init_database, close_database, create_tables
from src.api.v1 import chat, admin, analytics, health, tasks
from src.api.middleware import RateLimitMiddleware, SecurityMiddleware, LoggingMiddleware
from src.api.exceptions import setup_exception_handlers
from src.services.cache_service import CacheService
from src.utils.logger import setup_logging, get_logger

# 设置日志
setup_logging()
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    
    # 启动时执行
    logger.info("正在启动智能意图识别系统...")
    
    try:
        # 1. 初始化数据库连接
        init_database()
        logger.info("数据库连接初始化完成")
        
        # 2. 创建数据表（如果不存在）
        create_tables()
        logger.info("数据表检查完成")
        
        # 3. 初始化Redis缓存
        cache_service = CacheService()
        await cache_service.initialize()
        logger.info("Redis缓存初始化完成")
        
        # 4. 预热缓存
        await _warm_up_cache()
        logger.info("缓存预热完成")
        
        # 5. 初始化NLU引擎
        from src.core.nlu_engine import NLUEngine
        nlu_engine = NLUEngine()
        await nlu_engine.initialize()
        logger.info("NLU引擎初始化完成")
        
        logger.info(f"🚀 系统启动完成！监听端口: http://localhost:8000")
        logger.info(f"📚 API文档: http://localhost:8000/docs")
        
    except Exception as e:
        logger.error(f"系统启动失败: {str(e)}")
        raise
    
    yield
    
    # 关闭时执行
    logger.info("正在关闭系统...")
    
    try:
        # 关闭数据库连接
        close_database()
        
        # 关闭Redis连接
        cache_service = CacheService()
        await cache_service.close()
        
        logger.info("系统关闭完成")
        
    except Exception as e:
        logger.error(f"系统关闭异常: {str(e)}")


# 创建FastAPI应用实例
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="基于FastAPI的智能意图识别系统，支持无状态B2B设计、混合Prompt Template配置、RAGFLOW集成等高级功能",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan
)


def setup_middleware():
    """设置中间件"""
    
    # CORS中间件 - 处理跨域请求
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"] if settings.DEBUG else ["https://yourdomain.com"],
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE"],
        allow_headers=["*"],
    )
    
    # 可信主机中间件 - 防止Host头攻击
    if not settings.DEBUG:
        app.add_middleware(
            TrustedHostMiddleware,
            allowed_hosts=["yourdomain.com", "*.yourdomain.com"]
        )
    
    # 自定义中间件
    app.add_middleware(LoggingMiddleware)    # 请求日志中间件
    app.add_middleware(SecurityMiddleware)   # 安全中间件
    app.add_middleware(RateLimitMiddleware)  # 速率限制中间件


def setup_routes():
    """设置路由"""
    
    # API v1 路由
    app.include_router(
        chat.router,
        prefix=settings.API_V1_PREFIX,
        tags=["对话接口"]
    )
    
    app.include_router(
        admin.router,
        prefix=settings.API_V1_PREFIX,
        tags=["管理接口"]
    )
    
    app.include_router(
        analytics.router,
        prefix=settings.API_V1_PREFIX,
        tags=["分析接口"]
    )
    
    app.include_router(
        health.router,
        prefix=settings.API_V1_PREFIX,
        tags=["健康检查"]
    )
    
    app.include_router(
        tasks.router,
        prefix=settings.API_V1_PREFIX,
        tags=["异步任务"]
    )


def setup_global_handlers():
    """设置全局处理器"""
    
    # 异常处理器
    setup_exception_handlers(app)
    
    @app.middleware("http")
    async def add_process_time_header(request: Request, call_next):
        """添加处理时间头"""
        start_time = time.time()
        response = await call_next(request)
        process_time = time.time() - start_time
        response.headers["X-Process-Time"] = str(process_time)
        return response
    
    @app.get("/")
    async def root():
        """根路径"""
        return {
            "message": "智能意图识别系统",
            "version": settings.APP_VERSION,
            "status": "running",
            "docs": "/docs"
        }


async def _warm_up_cache():
    """缓存预热"""
    try:
        from src.services.intent_service import IntentService
        from src.services.cache_service import CacheService
        from src.core.nlu_engine import NLUEngine
        
        cache_service = CacheService()
        nlu_engine = NLUEngine()
        intent_service = IntentService(cache_service, nlu_engine)
        
        # 预热活跃意图配置
        active_intents = await intent_service._get_active_intents()
        logger.info(f"预热了 {len(active_intents)} 个活跃意图配置")
        
        # 预热系统配置
        from src.models.config import SystemConfig
        system_configs = list(SystemConfig.select().where(SystemConfig.is_active == True))
        config_dict = {config.config_key: config.config_value for config in system_configs}
        await cache_service.set("system_configs", config_dict, ttl=3600)
        logger.info(f"预热了 {len(system_configs)} 个系统配置")
        
    except Exception as e:
        logger.warning(f"缓存预热部分失败: {str(e)}")


# 设置应用
setup_middleware()
setup_routes()
setup_global_handlers()


if __name__ == "__main__":
    import uvicorn
    
    # 开发环境启动配置
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.DEBUG,
        log_level=settings.LOG_LEVEL.lower(),
        access_log=True
    )