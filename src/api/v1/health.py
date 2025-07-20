"""
健康检查API
"""
from fastapi import APIRouter, Depends, HTTPException
from typing import Dict, Any, Optional
import asyncio
from datetime import datetime

from src.api.dependencies import (
    get_cache_service_dependency, 
    get_nlu_engine, 
    check_system_health,
    get_system_metrics
)
from src.schemas.common import StandardResponse
from src.utils.logger import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/health", tags=["健康检查"])


@router.get("/", response_model=StandardResponse[Dict[str, Any]])
async def health_check():
    """基础健康检查
    
    Returns:
        Dict: 健康状态信息
    """
    try:
        health_info = {
            "status": "healthy",
            "timestamp": datetime.utcnow().isoformat(),
            "service": "智能意图识别系统",
            "version": "1.0.0"
        }
        
        return StandardResponse(
            success=True,
            message="服务正常",
            data=health_info
        )
        
    except Exception as e:
        logger.error(f"健康检查失败: {str(e)}")
        raise HTTPException(status_code=500, detail="健康检查失败")


@router.get("/detailed", response_model=StandardResponse[Dict[str, Any]])
async def detailed_health_check(
    health_status: Dict = Depends(check_system_health)
):
    """详细健康检查
    
    Returns:
        Dict: 详细健康状态信息
    """
    try:
        return StandardResponse(
            success=health_status["status"] == "healthy",
            message="详细健康检查完成",
            data=health_status
        )
        
    except Exception as e:
        logger.error(f"详细健康检查失败: {str(e)}")
        raise HTTPException(status_code=500, detail="详细健康检查失败")


@router.get("/metrics", response_model=StandardResponse[Dict[str, Any]])
async def system_metrics(
    metrics: Dict = Depends(get_system_metrics)
):
    """获取系统指标
    
    Returns:
        Dict: 系统性能指标
    """
    try:
        return StandardResponse(
            success=True,
            message="系统指标获取成功",
            data=metrics
        )
        
    except Exception as e:
        logger.error(f"获取系统指标失败: {str(e)}")
        raise HTTPException(status_code=500, detail="获取系统指标失败")


@router.get("/database")
async def database_health():
    """数据库健康检查
    
    Returns:
        Dict: 数据库状态
    """
    try:
        from src.config.database import database
        
        # 执行简单查询测试数据库连接
        with database.atomic():
            # 执行一个简单的查询
            result = database.execute_sql("SELECT 1 as test")
            test_value = result.fetchone()[0]
        
        if test_value == 1:
            return StandardResponse(
                success=True,
                message="数据库连接正常",
                data={
                    "status": "healthy",
                    "database": "mysql",
                    "test_query": "successful",
                    "timestamp": datetime.utcnow().isoformat()
                }
            )
        else:
            raise Exception("数据库测试查询返回异常值")
            
    except Exception as e:
        logger.error(f"数据库健康检查失败: {str(e)}")
        return StandardResponse(
            success=False,
            message="数据库连接失败",
            data={
                "status": "unhealthy",
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }
        )


@router.get("/redis")
async def redis_health(
    cache_service = Depends(get_cache_service_dependency)
):
    """Redis健康检查
    
    Returns:
        Dict: Redis状态
    """
    try:
        # 测试Redis连接
        test_key = "health_check_test"
        test_value = f"test_{datetime.utcnow().timestamp()}"
        
        # 设置测试值
        await cache_service.set(test_key, test_value, ttl=10)
        
        # 获取测试值
        retrieved_value = await cache_service.get(test_key)
        
        # 删除测试值
        await cache_service.delete(test_key)
        
        if retrieved_value == test_value:
            return StandardResponse(
                success=True,
                message="Redis连接正常",
                data={
                    "status": "healthy",
                    "cache_service": "redis",
                    "test_operation": "successful",
                    "timestamp": datetime.utcnow().isoformat()
                }
            )
        else:
            raise Exception("Redis测试操作返回异常值")
            
    except Exception as e:
        logger.error(f"Redis健康检查失败: {str(e)}")
        return StandardResponse(
            success=False,
            message="Redis连接失败",
            data={
                "status": "unhealthy",
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }
        )


@router.get("/nlu")
async def nlu_health(
    nlu_engine = Depends(get_nlu_engine)
):
    """NLU引擎健康检查
    
    Returns:
        Dict: NLU引擎状态
    """
    try:
        # 测试NLU引擎基本功能
        test_text = "测试NLU引擎健康状态"
        
        # 执行意图识别测试
        intent_result = await nlu_engine.recognize_intent(test_text)
        
        # 执行实体提取测试
        entities_result = await nlu_engine.extract_entities(test_text)
        
        return StandardResponse(
            success=True,
            message="NLU引擎正常",
            data={
                "status": "healthy",
                "nlu_engine": "operational",
                "intent_recognition": "working",
                "entity_extraction": "working",
                "test_intent": intent_result.get('intent', 'unknown'),
                "test_confidence": intent_result.get('confidence', 0.0),
                "test_entities_count": len(entities_result) if entities_result else 0,
                "timestamp": datetime.utcnow().isoformat()
            }
        )
        
    except Exception as e:
        logger.error(f"NLU引擎健康检查失败: {str(e)}")
        return StandardResponse(
            success=False,
            message="NLU引擎异常",
            data={
                "status": "unhealthy",
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }
        )


@router.get("/dependencies")
async def dependencies_health():
    """依赖服务健康检查
    
    Returns:
        Dict: 所有依赖服务状态
    """
    try:
        # 并发检查所有依赖服务
        tasks = [
            _check_database_health(),
            _check_redis_health(),
            _check_nlu_health(),
            _check_ragflow_health()
        ]
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        dependencies_status = {
            "database": results[0] if not isinstance(results[0], Exception) else {"status": "error", "error": str(results[0])},
            "redis": results[1] if not isinstance(results[1], Exception) else {"status": "error", "error": str(results[1])},
            "nlu_engine": results[2] if not isinstance(results[2], Exception) else {"status": "error", "error": str(results[2])},
            "ragflow": results[3] if not isinstance(results[3], Exception) else {"status": "error", "error": str(results[3])}
        }
        
        # 判断整体状态
        all_healthy = all(
            dep.get("status") == "healthy" 
            for dep in dependencies_status.values()
        )
        
        overall_status = "healthy" if all_healthy else "degraded"
        
        return StandardResponse(
            success=all_healthy,
            message=f"依赖服务状态: {overall_status}",
            data={
                "overall_status": overall_status,
                "dependencies": dependencies_status,
                "timestamp": datetime.utcnow().isoformat()
            }
        )
        
    except Exception as e:
        logger.error(f"依赖服务健康检查失败: {str(e)}")
        return StandardResponse(
            success=False,
            message="依赖服务健康检查失败",
            data={
                "overall_status": "error",
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }
        )


async def _check_database_health() -> Dict[str, Any]:
    """检查数据库健康状态"""
    try:
        from src.config.database import database
        import time
        
        start_time = time.time()
        with database.atomic():
            result = database.execute_sql("SELECT 1")
            result.fetchone()
        response_time = round((time.time() - start_time) * 1000, 2)
        
        return {
            "status": "healthy",
            "response_time": f"{response_time}ms"
        }
        
    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e)
        }


async def _check_redis_health() -> Dict[str, Any]:
    """检查Redis健康状态"""
    try:
        from src.services.cache_service import CacheService
        import time
        
        start_time = time.time()
        cache_service = CacheService()
        await cache_service.initialize()
        
        # 执行ping操作
        await cache_service.redis_client.ping()
        response_time = round((time.time() - start_time) * 1000, 2)
        
        return {
            "status": "healthy",
            "response_time": f"{response_time}ms"
        }
        
    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e)
        }


async def _check_nlu_health() -> Dict[str, Any]:
    """检查NLU引擎健康状态"""
    try:
        from src.core.nlu_engine import NLUEngine
        import time
        
        start_time = time.time()
        nlu_engine = NLUEngine()
        if not nlu_engine._initialized:
            await nlu_engine.initialize()
        
        # 执行简单的意图识别测试
        result = await nlu_engine.recognize_intent("健康检查测试")
        response_time = round((time.time() - start_time) * 1000, 2)
        
        return {
            "status": "healthy",
            "response_time": f"{response_time}ms",
            "test_result": result.get('intent', 'unknown')
        }
        
    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e)
        }


async def _check_ragflow_health() -> Dict[str, Any]:
    """检查RAGFLOW服务健康状态"""
    try:
        from src.services.ragflow_service import RagflowService
        from src.services.cache_service import CacheService
        import time
        
        start_time = time.time()
        cache_service = CacheService()
        ragflow_service = RagflowService(cache_service)
        
        # 执行简单的健康检查查询
        health_check_query = "健康检查测试"
        try:
            # 尝试查询RAGFLOW服务
            response = await ragflow_service.query_knowledge_base(
                query=health_check_query,
                conversation_id="health_check",
                max_results=1
            )
            
            response_time = round((time.time() - start_time) * 1000, 2)
            
            if response.success:
                return {
                    "status": "healthy",
                    "response_time": f"{response_time}ms",
                    "service_available": True
                }
            else:
                return {
                    "status": "degraded",
                    "response_time": f"{response_time}ms",
                    "service_available": False,
                    "error": response.error
                }
                
        except Exception as query_error:
            # 如果查询失败，检查服务是否可达
            response_time = round((time.time() - start_time) * 1000, 2)
            return {
                "status": "degraded",
                "response_time": f"{response_time}ms",
                "service_available": False,
                "error": str(query_error)
            }
        
    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e)
        }


@router.get("/ragflow")
async def ragflow_health(
    cache_service = Depends(get_cache_service_dependency)
):
    """RAGFLOW服务健康检查
    
    Returns:
        Dict: RAGFLOW服务状态
    """
    try:
        from src.services.ragflow_service import RagflowService
        import time
        
        start_time = time.time()
        ragflow_service = RagflowService(cache_service)
        
        # 测试RAGFLOW服务连接
        test_query = "健康检查测试"
        response = await ragflow_service.query_knowledge_base(
            query=test_query,
            conversation_id="health_check_test",
            max_results=1
        )
        
        response_time = round((time.time() - start_time) * 1000, 2)
        
        if response.success:
            return StandardResponse(
                success=True,
                message="RAGFLOW服务正常",
                data={
                    "status": "healthy",
                    "service": "ragflow",
                    "response_time": f"{response_time}ms",
                    "test_query": "successful",
                    "data_available": bool(response.data),
                    "timestamp": datetime.utcnow().isoformat()
                }
            )
        else:
            return StandardResponse(
                success=False,
                message="RAGFLOW服务异常",
                data={
                    "status": "unhealthy",
                    "service": "ragflow",
                    "response_time": f"{response_time}ms",
                    "error": response.error,
                    "timestamp": datetime.utcnow().isoformat()
                }
            )
            
    except Exception as e:
        logger.error(f"RAGFLOW健康检查失败: {str(e)}")
        return StandardResponse(
            success=False,
            message="RAGFLOW服务连接失败",
            data={
                "status": "unhealthy",
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }
        )


@router.get("/readiness")
async def readiness_check():
    """就绪状态检查（用于K8s readiness probe）
    
    Returns:
        Dict: 服务就绪状态
    """
    try:
        # 检查关键依赖是否就绪
        from src.config.database import database
        from src.core.nlu_engine import NLUEngine
        
        # 检查数据库连接
        try:
            database.execute_sql("SELECT 1").fetchone()
        except Exception:
            raise HTTPException(status_code=503, detail="数据库未就绪")
        
        # 检查NLU引擎是否初始化
        nlu_engine = NLUEngine()
        if not hasattr(nlu_engine, '_initialized') or not nlu_engine._initialized:
            raise HTTPException(status_code=503, detail="NLU引擎未就绪")
        
        return StandardResponse(
            success=True,
            message="服务已就绪",
            data={
                "status": "ready",
                "timestamp": datetime.utcnow().isoformat()
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"就绪状态检查失败: {str(e)}")
        raise HTTPException(status_code=503, detail="服务未就绪")


@router.get("/liveness")
async def liveness_check():
    """存活状态检查（用于K8s liveness probe）
    
    Returns:
        Dict: 服务存活状态
    """
    try:
        import psutil
        import os
        
        # 获取进程信息
        process = psutil.Process(os.getpid())
        create_time = process.create_time()
        current_time = datetime.utcnow().timestamp()
        uptime_seconds = int(current_time - create_time)
        
        # 计算可读的运行时间
        days = uptime_seconds // 86400
        hours = (uptime_seconds % 86400) // 3600
        minutes = (uptime_seconds % 3600) // 60
        seconds = uptime_seconds % 60
        
        uptime_str = f"{days}d {hours}h {minutes}m {seconds}s"
        
        return StandardResponse(
            success=True,
            message="服务存活",
            data={
                "status": "alive",
                "timestamp": datetime.utcnow().isoformat(),
                "uptime": uptime_str,
                "uptime_seconds": uptime_seconds,
                "process_id": os.getpid(),
                "memory_usage": f"{process.memory_info().rss / 1024 / 1024:.1f}MB"
            }
        )
        
    except Exception as e:
        logger.error(f"存活状态检查失败: {str(e)}")
        raise HTTPException(status_code=503, detail="服务不可用")