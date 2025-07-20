"""
管理员API
"""
from fastapi import APIRouter, Depends, HTTPException, Query, Path
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
import json

from src.api.dependencies import require_admin_auth, get_cache_service_dependency
from src.schemas.common import StandardResponse
from src.models.intent import Intent
from src.models.slot import Slot, SlotValue
from src.models.function import Function, FunctionCall, FunctionParameter
from src.models.config import SystemConfig, FeatureFlag, RagflowConfig
from src.models.template import PromptTemplate
from src.models.audit import ConfigAuditLog, SecurityAuditLog, PerformanceLog
from src.utils.logger import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/admin", tags=["管理员接口"])


@router.get("/stats/overview", response_model=StandardResponse[Dict[str, Any]])
async def get_system_overview(
    current_user: Dict = Depends(require_admin_auth)
):
    """获取系统概览统计
    
    Returns:
        Dict: 系统概览数据
    """
    try:
        # 统计意图数量
        total_intents = Intent.select().count()
        active_intents = Intent.select().where(Intent.is_active == True).count()
        
        # 统计槽位数量
        total_slots = Slot.select().count()
        active_slots = Slot.select().where(Slot.is_active == True).count()
        
        # 统计功能数量
        total_functions = Function.select().count()
        active_functions = Function.select().where(Function.is_active == True).count()
        
        # 统计最近7天的功能调用
        week_ago = datetime.now() - timedelta(days=7)
        recent_calls = FunctionCall.select().where(
            FunctionCall.created_at >= week_ago
        ).count()
        
        # 统计系统配置
        total_configs = SystemConfig.select().count()
        active_configs = SystemConfig.select().where(SystemConfig.is_active == True).count()
        
        overview_data = {
            "intents": {
                "total": total_intents,
                "active": active_intents,
                "inactive": total_intents - active_intents
            },
            "slots": {
                "total": total_slots,
                "active": active_slots,
                "inactive": total_slots - active_slots
            },
            "functions": {
                "total": total_functions,
                "active": active_functions,
                "inactive": total_functions - active_functions
            },
            "system": {
                "configs": total_configs,
                "active_configs": active_configs,
                "recent_function_calls": recent_calls,
                "last_updated": datetime.now().isoformat()
            }
        }
        
        return StandardResponse(
            code=200,
            message="系统概览获取成功",
            data=overview_data
        )
        
    except Exception as e:
        logger.error(f"获取系统概览失败: {str(e)}")
        raise HTTPException(status_code=500, detail="获取系统概览失败")


@router.get("/intents", response_model=StandardResponse[List[Dict[str, Any]]])
async def list_intents(
    current_user: Dict = Depends(require_admin_auth),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: Optional[str] = None,
    is_active: Optional[bool] = None
):
    """获取意图列表
    
    Args:
        page: 页码
        page_size: 每页大小
        search: 搜索关键词
        is_active: 是否激活状态过滤
        
    Returns:
        List[Dict]: 意图列表
    """
    try:
        # 构建查询条件
        query = Intent.select()
        
        if search:
            query = query.where(
                (Intent.intent_name.contains(search)) |
                (Intent.description.contains(search))
            )
        
        if is_active is not None:
            query = query.where(Intent.is_active == is_active)
        
        # 计算总数
        total = query.count()
        
        # 分页查询
        offset = (page - 1) * page_size
        intents = query.offset(offset).limit(page_size)
        
        # 构建响应数据
        intent_list = []
        for intent in intents:
            # 统计意图示例数量
            examples_count = intent.examples.count()
            
            # 统计槽位数量
            slots_count = intent.slots.count()
            
            intent_data = {
                "id": intent.id,
                "intent_name": intent.intent_name,
                "description": intent.description,
                "category": intent.category,
                "confidence_threshold": float(intent.confidence_threshold),
                "is_active": intent.is_active,
                "examples_count": examples_count,
                "slots_count": slots_count,
                "created_at": intent.created_at.isoformat(),
                "updated_at": intent.updated_at.isoformat()
            }
            intent_list.append(intent_data)
        
        response_data = {
            "items": intent_list,
            "pagination": {
                "page": page,
                "page_size": page_size,
                "total": total,
                "pages": (total + page_size - 1) // page_size
            }
        }
        
        return StandardResponse(
            code=200,
            message="意图列表获取成功",
            data=response_data
        )
        
    except Exception as e:
        logger.error(f"获取意图列表失败: {str(e)}")
        raise HTTPException(status_code=500, detail="获取意图列表失败")


@router.get("/functions", response_model=StandardResponse[List[Dict[str, Any]]])
async def list_functions(
    current_user: Dict = Depends(require_admin_auth),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    category: Optional[str] = None,
    is_active: Optional[bool] = None
):
    """获取功能列表
    
    Args:
        page: 页码
        page_size: 每页大小
        category: 功能分类过滤
        is_active: 是否激活状态过滤
        
    Returns:
        List[Dict]: 功能列表
    """
    try:
        # 构建查询条件
        query = Function.select()
        
        if category:
            query = query.where(Function.category == category)
        
        if is_active is not None:
            query = query.where(Function.is_active == is_active)
        
        # 计算总数
        total = query.count()
        
        # 分页查询
        offset = (page - 1) * page_size
        functions = query.offset(offset).limit(page_size)
        
        # 构建响应数据
        function_list = []
        for func in functions:
            # 统计最近调用次数
            week_ago = datetime.now() - timedelta(days=7)
            recent_calls = func.calls.where(
                FunctionCall.created_at >= week_ago
            ).count()
            
            # 统计成功率
            total_calls = func.calls.count()
            successful_calls = func.calls.where(
                FunctionCall.status == 'completed'
            ).count()
            success_rate = (successful_calls / total_calls * 100) if total_calls > 0 else 0
            
            function_data = {
                "id": func.id,
                "function_name": func.function_name,
                "description": func.description,
                "category": func.category,
                "is_active": func.is_active,
                "total_calls": total_calls,
                "recent_calls": recent_calls,
                "success_rate": round(success_rate, 2),
                "created_at": func.created_at.isoformat(),
                "updated_at": func.updated_at.isoformat()
            }
            function_list.append(function_data)
        
        response_data = {
            "items": function_list,
            "pagination": {
                "page": page,
                "page_size": page_size,
                "total": total,
                "pages": (total + page_size - 1) // page_size
            }
        }
        
        return StandardResponse(
            code=200,
            message="功能列表获取成功",
            data=response_data
        )
        
    except Exception as e:
        logger.error(f"获取功能列表失败: {str(e)}")
        raise HTTPException(status_code=500, detail="获取功能列表失败")


@router.get("/configs", response_model=StandardResponse[List[Dict[str, Any]]])
async def list_configs(
    current_user: Dict = Depends(require_admin_auth),
    category: Optional[str] = None,
    is_active: Optional[bool] = None
):
    """获取系统配置列表
    
    Args:
        category: 配置分类过滤
        is_active: 是否激活状态过滤
        
    Returns:
        List[Dict]: 配置列表
    """
    try:
        # 构建查询条件
        query = SystemConfig.select()
        
        if category:
            query = query.where(SystemConfig.config_category == category)
        
        if is_active is not None:
            query = query.where(SystemConfig.is_active == is_active)
        
        # 查询配置
        configs = query.order_by(SystemConfig.config_category, SystemConfig.config_key)
        
        # 构建响应数据
        config_list = []
        for config in configs:
            config_data = {
                "id": config.id,
                "config_category": config.config_category,
                "config_key": config.config_key,
                "config_value": config.config_value,
                "value_type": config.value_type,
                "description": config.description,
                "is_encrypted": config.is_encrypted,
                "is_active": config.is_active,
                "created_at": config.created_at.isoformat(),
                "updated_at": config.updated_at.isoformat()
            }
            config_list.append(config_data)
        
        return StandardResponse(
            code=200,
            message="配置列表获取成功",
            data=config_list
        )
        
    except Exception as e:
        logger.error(f"获取配置列表失败: {str(e)}")
        raise HTTPException(status_code=500, detail="获取配置列表失败")


@router.put("/configs/{config_id}", response_model=StandardResponse[Dict[str, Any]])
async def update_config(
    config_id: int,
    config_data: Dict[str, Any],
    current_user: Dict = Depends(require_admin_auth)
):
    """更新系统配置
    
    Args:
        config_id: 配置ID
        config_data: 配置数据
        
    Returns:
        Dict: 更新后的配置信息
    """
    try:
        # 获取配置
        config = SystemConfig.get_by_id(config_id)
        
        # 记录修改前的值（用于审计）
        old_values = {
            "config_value": config.config_value,
            "value_type": config.value_type,
            "description": config.description,
            "is_active": config.is_active
        }
        
        # 更新配置
        if "config_value" in config_data:
            config.config_value = config_data["config_value"]
        
        if "value_type" in config_data:
            config.value_type = config_data["value_type"]
        
        if "description" in config_data:
            config.description = config_data["description"]
        
        if "is_active" in config_data:
            config.is_active = config_data["is_active"]
        
        config.save()
        
        # 记录配置修改审计日志
        new_values = {
            "config_value": config.config_value,
            "value_type": config.value_type,
            "description": config.description,
            "is_active": config.is_active
        }
        
        ConfigAuditLog.create(
            table_name_field="system_configs",
            record_id=config.id,
            action="UPDATE",
            old_values=old_values,
            new_values=new_values,
            operator_id=current_user.get("user_id", "unknown"),
            operator_name=current_user.get("username", "unknown")
        )
        
        return StandardResponse(
            code=200,
            message="配置更新成功",
            data={
                "id": config.id,
                "config_category": config.config_category,
                "config_key": config.config_key,
                "config_value": config.config_value,
                "value_type": config.value_type,
                "description": config.description,
                "is_active": config.is_active,
                "updated_at": config.updated_at.isoformat()
            }
        )
        
    except SystemConfig.DoesNotExist:
        raise HTTPException(status_code=404, detail="配置不存在")
    except Exception as e:
        logger.error(f"更新配置失败: {str(e)}")
        raise HTTPException(status_code=500, detail="更新配置失败")


@router.get("/feature-flags", response_model=StandardResponse[List[Dict[str, Any]]])
async def list_feature_flags(
    current_user: Dict = Depends(require_admin_auth),
    environment: Optional[str] = None,
    is_enabled: Optional[bool] = None
):
    """获取功能开关列表
    
    Args:
        environment: 环境过滤
        is_enabled: 是否启用状态过滤
        
    Returns:
        List[Dict]: 功能开关列表
    """
    try:
        # 构建查询条件
        query = FeatureFlag.select()
        
        if environment:
            query = query.where(FeatureFlag.environment == environment)
        
        if is_enabled is not None:
            query = query.where(FeatureFlag.is_enabled == is_enabled)
        
        # 查询功能开关
        flags = query.order_by(FeatureFlag.flag_key)
        
        # 构建响应数据
        flag_list = []
        for flag in flags:
            flag_data = {
                "id": flag.id,
                "flag_name": flag.flag_name,
                "flag_key": flag.flag_key,
                "description": flag.description,
                "is_enabled": flag.is_enabled,
                "target_users": flag.get_target_users(),
                "rollout_percentage": flag.rollout_percentage,
                "environment": flag.environment,
                "expires_at": flag.expires_at.isoformat() if flag.expires_at else None,
                "is_expired": flag.is_expired(),
                "created_at": flag.created_at.isoformat(),
                "updated_at": flag.updated_at.isoformat()
            }
            flag_list.append(flag_data)
        
        return StandardResponse(
            code=200,
            message="功能开关列表获取成功",
            data=flag_list
        )
        
    except Exception as e:
        logger.error(f"获取功能开关列表失败: {str(e)}")
        raise HTTPException(status_code=500, detail="获取功能开关列表失败")


@router.put("/feature-flags/{flag_id}", response_model=StandardResponse[Dict[str, Any]])
async def update_feature_flag(
    flag_id: int,
    flag_data: Dict[str, Any],
    current_user: Dict = Depends(require_admin_auth)
):
    """更新功能开关
    
    Args:
        flag_id: 功能开关ID
        flag_data: 开关数据
        
    Returns:
        Dict: 更新后的开关信息
    """
    try:
        # 获取功能开关
        flag = FeatureFlag.get_by_id(flag_id)
        
        # 更新开关配置
        if "is_enabled" in flag_data:
            flag.is_enabled = flag_data["is_enabled"]
        
        if "description" in flag_data:
            flag.description = flag_data["description"]
        
        if "target_users" in flag_data:
            flag.set_target_users(flag_data["target_users"])
        
        if "rollout_percentage" in flag_data:
            flag.rollout_percentage = flag_data["rollout_percentage"]
        
        if "expires_at" in flag_data:
            if flag_data["expires_at"]:
                flag.expires_at = datetime.fromisoformat(flag_data["expires_at"])
            else:
                flag.expires_at = None
        
        flag.save()
        
        return StandardResponse(
            code=200,
            message="功能开关更新成功",
            data={
                "id": flag.id,
                "flag_name": flag.flag_name,
                "flag_key": flag.flag_key,
                "description": flag.description,
                "is_enabled": flag.is_enabled,
                "target_users": flag.get_target_users(),
                "rollout_percentage": flag.rollout_percentage,
                "environment": flag.environment,
                "expires_at": flag.expires_at.isoformat() if flag.expires_at else None,
                "updated_at": flag.updated_at.isoformat()
            }
        )
        
    except FeatureFlag.DoesNotExist:
        raise HTTPException(status_code=404, detail="功能开关不存在")
    except Exception as e:
        logger.error(f"更新功能开关失败: {str(e)}")
        raise HTTPException(status_code=500, detail="更新功能开关失败")


@router.get("/audit-logs", response_model=StandardResponse[List[Dict[str, Any]]])
async def list_audit_logs(
    current_user: Dict = Depends(require_admin_auth),
    log_type: str = Query("config", description="日志类型: config, security, performance"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    start_date: Optional[str] = None,
    end_date: Optional[str] = None
):
    """获取审计日志列表
    
    Args:
        log_type: 日志类型
        page: 页码
        page_size: 每页大小
        start_date: 开始日期
        end_date: 结束日期
        
    Returns:
        List[Dict]: 审计日志列表
    """
    try:
        # 根据日志类型选择对应的模型
        if log_type == "config":
            LogModel = ConfigAuditLog
        elif log_type == "security":
            LogModel = SecurityAuditLog
        elif log_type == "performance":
            LogModel = PerformanceLog
        else:
            raise HTTPException(status_code=400, detail="不支持的日志类型")
        
        # 构建查询条件
        query = LogModel.select()
        
        if start_date:
            start_dt = datetime.fromisoformat(start_date)
            query = query.where(LogModel.created_at >= start_dt)
        
        if end_date:
            end_dt = datetime.fromisoformat(end_date)
            query = query.where(LogModel.created_at <= end_dt)
        
        # 计算总数
        total = query.count()
        
        # 分页查询
        offset = (page - 1) * page_size
        logs = query.order_by(LogModel.created_at.desc()).offset(offset).limit(page_size)
        
        # 构建响应数据
        log_list = []
        for log in logs:
            if log_type == "config":
                log_data = {
                    "id": log.id,
                    "table_name": log.table_name_field,
                    "record_id": log.record_id,
                    "action": log.action,
                    "old_values": log.get_old_values(),
                    "new_values": log.get_new_values(),
                    "operator_id": log.operator_id,
                    "operator_name": log.operator_name,
                    "ip_address": log.ip_address,
                    "created_at": log.created_at.isoformat()
                }
            elif log_type == "security":
                log_data = {
                    "id": log.id,
                    "user_id": log.user_id,
                    "ip_address": log.ip_address,
                    "action_type": log.action_type,
                    "resource_type": log.resource_type,
                    "resource_id": log.resource_id,
                    "action_details": log.get_action_details(),
                    "risk_level": log.risk_level,
                    "status": log.status,
                    "error_message": log.error_message,
                    "created_at": log.created_at.isoformat()
                }
            elif log_type == "performance":
                log_data = {
                    "id": log.id,
                    "endpoint": log.endpoint,
                    "method": log.method,
                    "user_id": log.user_id,
                    "request_id": log.request_id,
                    "response_time_ms": log.response_time_ms,
                    "status_code": log.status_code,
                    "request_size_bytes": log.request_size_bytes,
                    "response_size_bytes": log.response_size_bytes,
                    "cpu_usage_percent": float(log.cpu_usage_percent) if log.cpu_usage_percent else None,
                    "memory_usage_mb": float(log.memory_usage_mb) if log.memory_usage_mb else None,
                    "cache_hit": log.cache_hit,
                    "database_queries": log.database_queries,
                    "external_api_calls": log.external_api_calls,
                    "created_at": log.created_at.isoformat()
                }
            
            log_list.append(log_data)
        
        response_data = {
            "items": log_list,
            "pagination": {
                "page": page,
                "page_size": page_size,
                "total": total,
                "pages": (total + page_size - 1) // page_size
            }
        }
        
        return StandardResponse(
            code=200,
            message=f"{log_type}审计日志获取成功",
            data=response_data
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取审计日志失败: {str(e)}")
        raise HTTPException(status_code=500, detail="获取审计日志失败")


@router.post("/cache/clear", response_model=StandardResponse[Dict[str, Any]])
async def clear_cache(
    cache_keys: Optional[List[str]] = None,
    namespace: Optional[str] = None,
    current_user: Dict = Depends(require_admin_auth),
    cache_service = Depends(get_cache_service_dependency)
):
    """清理缓存
    
    Args:
        cache_keys: 指定要清理的缓存键列表
        namespace: 指定要清理的命名空间
        
    Returns:
        Dict: 清理结果
    """
    try:
        cleared_count = 0
        
        if cache_keys:
            # 清理指定的缓存键
            for key in cache_keys:
                if namespace:
                    await cache_service.delete(key, namespace=namespace)
                else:
                    await cache_service.delete(key)
                cleared_count += 1
        
        elif namespace:
            # 清理指定命名空间的所有缓存
            await cache_service.clear_namespace(namespace)
            cleared_count = 1  # 简化计数
        
        else:
            # 清理所有缓存（危险操作，需要确认）
            await cache_service.redis_client.flushall()
            cleared_count = 1
        
        # 记录安全审计日志
        SecurityAuditLog.create(
            user_id=current_user.get("user_id", "unknown"),
            action_type="cache_clear",
            resource_type="cache",
            resource_id=namespace or "all",
            action_details={
                "cache_keys": cache_keys,
                "namespace": namespace,
                "cleared_count": cleared_count
            },
            risk_level="medium",
            status="success"
        )
        
        return StandardResponse(
            code=200,
            message="缓存清理成功",
            data={
                "cleared_count": cleared_count,
                "cache_keys": cache_keys,
                "namespace": namespace,
                "timestamp": datetime.now().isoformat()
            }
        )
        
    except Exception as e:
        logger.error(f"清理缓存失败: {str(e)}")
        
        # 记录失败的安全审计日志
        SecurityAuditLog.create(
            user_id=current_user.get("user_id", "unknown"),
            action_type="cache_clear",
            resource_type="cache",
            resource_id=namespace or "all",
            action_details={
                "cache_keys": cache_keys,
                "namespace": namespace,
                "error": str(e)
            },
            risk_level="medium",
            status="failed",
            error_message=str(e)
        )
        
        raise HTTPException(status_code=500, detail="清理缓存失败")


# ============ 意图配置CRUD接口 ============

@router.post("/intents", response_model=StandardResponse[Dict[str, Any]])
async def create_intent(
    intent_data: Dict[str, Any],
    current_user: Dict = Depends(require_admin_auth)
):
    """创建新的意图配置"""
    try:
        # 验证必需字段
        required_fields = ['intent_name', 'description']
        for field in required_fields:
            if field not in intent_data:
                raise HTTPException(status_code=400, detail=f"缺少必需字段: {field}")
        
        # 检查意图名是否已存在
        existing = Intent.select().where(Intent.intent_name == intent_data['intent_name']).first()
        if existing:
            raise HTTPException(status_code=400, detail="意图名称已存在")
        
        # 创建意图
        intent = Intent.create(
            intent_name=intent_data['intent_name'],
            description=intent_data['description'],
            category=intent_data.get('category', 'general'),
            confidence_threshold=intent_data.get('confidence_threshold', 0.7),
            priority=intent_data.get('priority', 5),
            is_active=intent_data.get('is_active', True)
        )
        
        # 添加示例
        examples = intent_data.get('examples', [])
        for example_text in examples:
            IntentExample.create(
                intent=intent,
                example_text=example_text,
                is_validated=True
            )
        
        logger.info(f"创建意图成功: {intent.intent_name}")
        
        return StandardResponse(
            code=201,
            message="意图创建成功",
            data={
                "id": intent.id,
                "intent_name": intent.intent_name,
                "description": intent.description,
                "category": intent.category,
                "examples_count": len(examples),
                "created_at": intent.created_at.isoformat()
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"创建意图失败: {str(e)}")
        raise HTTPException(status_code=500, detail="创建意图失败")


@router.put("/intents/{intent_id}", response_model=StandardResponse[Dict[str, Any]])
async def update_intent(
    intent_id: int = Path(..., description="意图ID"),
    intent_data: Dict[str, Any] = ...,
    current_user: Dict = Depends(require_admin_auth)
):
    """更新指定意图配置"""
    try:
        intent = Intent.get_by_id(intent_id)
        
        # 更新基本信息
        if 'description' in intent_data:
            intent.description = intent_data['description']
        if 'category' in intent_data:
            intent.category = intent_data['category']
        if 'confidence_threshold' in intent_data:
            intent.confidence_threshold = intent_data['confidence_threshold']
        if 'priority' in intent_data:
            intent.priority = intent_data['priority']
        if 'is_active' in intent_data:
            intent.is_active = intent_data['is_active']
        
        intent.save()
        
        # 更新示例
        if 'examples' in intent_data:
            # 删除现有示例
            IntentExample.delete().where(IntentExample.intent == intent).execute()
            
            # 添加新示例
            for example_text in intent_data['examples']:
                IntentExample.create(
                    intent=intent,
                    example_text=example_text,
                    is_validated=True
                )
        
        logger.info(f"更新意图成功: {intent.intent_name}")
        
        return StandardResponse(
            code=200,
            message="意图更新成功",
            data={
                "id": intent.id,
                "intent_name": intent.intent_name,
                "description": intent.description,
                "updated_at": intent.updated_at.isoformat()
            }
        )
        
    except Intent.DoesNotExist:
        raise HTTPException(status_code=404, detail="意图不存在")
    except Exception as e:
        logger.error(f"更新意图失败: {str(e)}")
        raise HTTPException(status_code=500, detail="更新意图失败")


@router.delete("/intents/{intent_id}", response_model=StandardResponse[Dict[str, Any]])
async def delete_intent(
    intent_id: int = Path(..., description="意图ID"),
    current_user: Dict = Depends(require_admin_auth)
):
    """删除指定意图配置"""
    try:
        intent = Intent.get_by_id(intent_id)
        intent_name = intent.intent_name
        
        # 软删除
        intent.is_active = False
        intent.save()
        
        logger.info(f"删除意图成功: {intent_name}")
        
        return StandardResponse(
            code=200,
            message="意图删除成功",
            data={
                "id": intent_id,
                "intent_name": intent_name,
                "deleted_at": datetime.now().isoformat()
            }
        )
        
    except Intent.DoesNotExist:
        raise HTTPException(status_code=404, detail="意图不存在")
    except Exception as e:
        logger.error(f"删除意图失败: {str(e)}")
        raise HTTPException(status_code=500, detail="删除意图失败")


# ============ 槽位配置接口 ============

@router.get("/intents/{intent_id}/slots", response_model=StandardResponse[List[Dict[str, Any]]])
async def get_intent_slots(
    intent_id: int = Path(..., description="意图ID"),
    current_user: Dict = Depends(require_admin_auth)
):
    """获取指定意图的槽位配置"""
    try:
        intent = Intent.get_by_id(intent_id)
        slots = list(intent.slots.order_by(Slot.sort_order))
        
        slot_list = []
        for slot in slots:
            slot_data = {
                "id": slot.id,
                "slot_name": slot.slot_name,
                "slot_type": slot.slot_type,
                "is_required": slot.is_required,
                "description": slot.description,
                "validation_rules": slot.get_validation_rules(),
                "prompt_template": slot.prompt_template,
                "default_value": slot.default_value,
                "sort_order": slot.sort_order,
                "is_active": slot.is_active,
                "created_at": slot.created_at.isoformat()
            }
            slot_list.append(slot_data)
        
        return StandardResponse(
            code=200,
            message="槽位列表获取成功",
            data=slot_list
        )
        
    except Intent.DoesNotExist:
        raise HTTPException(status_code=404, detail="意图不存在")
    except Exception as e:
        logger.error(f"获取槽位列表失败: {str(e)}")
        raise HTTPException(status_code=500, detail="获取槽位列表失败")


@router.post("/intents/{intent_id}/slots", response_model=StandardResponse[Dict[str, Any]])
async def create_intent_slot(
    intent_id: int = Path(..., description="意图ID"),
    slot_data: Dict[str, Any] = ...,
    current_user: Dict = Depends(require_admin_auth)
):
    """为指定意图创建新的槽位配置"""
    try:
        intent = Intent.get_by_id(intent_id)
        
        # 验证必需字段
        required_fields = ['slot_name', 'slot_type']
        for field in required_fields:
            if field not in slot_data:
                raise HTTPException(status_code=400, detail=f"缺少必需字段: {field}")
        
        # 检查槽位名是否已存在
        existing = Slot.select().where(
            Slot.intent_name == intent.intent_name,
            Slot.slot_name == slot_data['slot_name']
        ).first()
        if existing:
            raise HTTPException(status_code=400, detail="槽位名称已存在")
        
        # 创建槽位
        slot = Slot.create(
            intent_name=intent.intent_name,
            slot_name=slot_data['slot_name'],
            slot_type=slot_data['slot_type'],
            is_required=slot_data.get('is_required', False),
            description=slot_data.get('description', ''),
            validation_rules=json.dumps(slot_data.get('validation_rules', {})),
            prompt_template=slot_data.get('prompt_template', ''),
            default_value=slot_data.get('default_value'),
            sort_order=slot_data.get('sort_order', 0),
            is_active=slot_data.get('is_active', True)
        )
        
        # 添加槽位值示例
        examples = slot_data.get('examples', [])
        for example in examples:
            SlotValue.create(
                slot=slot,
                value=example,
                is_active=True
            )
        
        logger.info(f"创建槽位成功: {intent.intent_name}.{slot.slot_name}")
        
        return StandardResponse(
            code=201,
            message="槽位创建成功",
            data={
                "id": slot.id,
                "slot_name": slot.slot_name,
                "slot_type": slot.slot_type,
                "intent_name": intent.intent_name,
                "created_at": slot.created_at.isoformat()
            }
        )
        
    except Intent.DoesNotExist:
        raise HTTPException(status_code=404, detail="意图不存在")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"创建槽位失败: {str(e)}")
        raise HTTPException(status_code=500, detail="创建槽位失败")


# ============ 模板管理接口 ============

@router.get("/templates", response_model=StandardResponse[List[Dict[str, Any]]])
async def get_templates(
    template_type: Optional[str] = Query(None, description="模板类型"),
    intent_id: Optional[int] = Query(None, description="意图ID"),
    is_active: Optional[bool] = Query(None, description="是否激活"),
    current_user: Dict = Depends(require_admin_auth)
):
    """获取所有prompt template配置"""
    try:
        query = PromptTemplate.select()
        
        if template_type:
            query = query.where(PromptTemplate.template_type == template_type)
        if intent_id:
            query = query.where(PromptTemplate.intent_id == intent_id)
        if is_active is not None:
            query = query.where(PromptTemplate.is_active == is_active)
        
        templates = list(query.order_by(PromptTemplate.created_at.desc()))
        
        template_list = []
        for template in templates:
            template_data = {
                "id": template.id,
                "template_name": template.template_name,
                "template_type": template.template_type,
                "intent_id": template.intent_id,
                "template_content": template.template_content,
                "variables": template.get_variables(),
                "version": template.version,
                "is_active": template.is_active,
                "description": template.description,
                "created_at": template.created_at.isoformat(),
                "updated_at": template.updated_at.isoformat()
            }
            template_list.append(template_data)
        
        return StandardResponse(
            code=200,
            message="模板列表获取成功",
            data=template_list
        )
        
    except Exception as e:
        logger.error(f"获取模板列表失败: {str(e)}")
        raise HTTPException(status_code=500, detail="获取模板列表失败")


@router.post("/templates", response_model=StandardResponse[Dict[str, Any]])
async def create_template(
    template_data: Dict[str, Any],
    current_user: Dict = Depends(require_admin_auth)
):
    """创建新的prompt template配置"""
    try:
        # 验证必需字段
        required_fields = ['template_name', 'template_type', 'template_content']
        for field in required_fields:
            if field not in template_data:
                raise HTTPException(status_code=400, detail=f"缺少必需字段: {field}")
        
        # 创建模板
        template = PromptTemplate.create(
            template_name=template_data['template_name'],
            template_type=template_data['template_type'],
            intent_id=template_data.get('intent_id'),
            template_content=template_data['template_content'],
            variables=json.dumps(template_data.get('variables', [])),
            version=template_data.get('version', '1.0'),
            is_active=template_data.get('is_active', True),
            description=template_data.get('description', '')
        )
        
        logger.info(f"创建模板成功: {template.template_name}")
        
        return StandardResponse(
            code=201,
            message="模板创建成功",
            data={
                "id": template.id,
                "template_name": template.template_name,
                "template_type": template.template_type,
                "version": template.version,
                "created_at": template.created_at.isoformat()
            }
        )
        
    except Exception as e:
        logger.error(f"创建模板失败: {str(e)}")
        raise HTTPException(status_code=500, detail="创建模板失败")


@router.put("/templates/{template_id}", response_model=StandardResponse[Dict[str, Any]])
async def update_template(
    template_id: int = Path(..., description="模板ID"),
    template_data: Dict[str, Any] = ...,
    current_user: Dict = Depends(require_admin_auth)
):
    """更新指定prompt template配置"""
    try:
        template = PromptTemplate.get_by_id(template_id)
        
        # 更新字段
        if 'template_content' in template_data:
            template.template_content = template_data['template_content']
        if 'variables' in template_data:
            template.variables = json.dumps(template_data['variables'])
        if 'version' in template_data:
            template.version = template_data['version']
        if 'is_active' in template_data:
            template.is_active = template_data['is_active']
        if 'description' in template_data:
            template.description = template_data['description']
        
        template.save()
        
        logger.info(f"更新模板成功: {template.template_name}")
        
        return StandardResponse(
            code=200,
            message="模板更新成功",
            data={
                "id": template.id,
                "template_name": template.template_name,
                "version": template.version,
                "updated_at": template.updated_at.isoformat()
            }
        )
        
    except PromptTemplate.DoesNotExist:
        raise HTTPException(status_code=404, detail="模板不存在")
    except Exception as e:
        logger.error(f"更新模板失败: {str(e)}")
        raise HTTPException(status_code=500, detail="更新模板失败")


# ============ RAGFLOW配置管理 ============

@router.put("/ragflow/config", response_model=StandardResponse[Dict[str, Any]])
async def update_ragflow_config(
    config_data: Dict[str, Any],
    current_user: Dict = Depends(require_admin_auth)
):
    """更新RAGFLOW集成配置"""
    try:
        config_name = config_data.get('config_name', 'default')
        
        # 获取或创建配置
        try:
            config = RagflowConfig.get(RagflowConfig.config_name == config_name)
        except RagflowConfig.DoesNotExist:
            config = RagflowConfig.create(config_name=config_name)
        
        # 更新配置
        if 'api_endpoint' in config_data:
            config.api_endpoint = config_data['api_endpoint']
        if 'api_key' in config_data:
            config.api_key = config_data['api_key']
        if 'headers' in config_data:
            config.set_headers(config_data['headers'])
        if 'timeout_seconds' in config_data:
            config.timeout_seconds = config_data['timeout_seconds']
        if 'is_active' in config_data:
            config.is_active = config_data['is_active']
        
        config.save()
        
        logger.info(f"更新RAGFLOW配置成功: {config_name}")
        
        return StandardResponse(
            code=200,
            message="RAGFLOW配置更新成功",
            data={
                "config_name": config.config_name,
                "api_endpoint": config.api_endpoint,
                "is_active": config.is_active,
                "updated_at": config.updated_at.isoformat()
            }
        )
        
    except Exception as e:
        logger.error(f"更新RAGFLOW配置失败: {str(e)}")
        raise HTTPException(status_code=500, detail="更新RAGFLOW配置失败")


@router.get("/ragflow/health", response_model=StandardResponse[Dict[str, Any]])
async def get_ragflow_health(
    current_user: Dict = Depends(require_admin_auth)
):
    """检查RAGFLOW服务健康状态"""
    try:
        # 这里应该实际调用RAGFLOW健康检查
        # 目前返回模拟数据
        health_data = {
            "service_status": "healthy",
            "last_health_check": datetime.now().isoformat(),
            "response_time_ms": 150,
            "success_rate_24h": 0.98,
            "error_count_1h": 2,
            "consecutive_failures": 0,
            "endpoints": {
                "chat": {
                    "status": "healthy",
                    "response_time_ms": 145
                },
                "health": {
                    "status": "healthy",
                    "response_time_ms": 25
                }
            }
        }
        
        return StandardResponse(
            code=200,
            message="RAGFLOW健康状态获取成功",
            data=health_data
        )
        
    except Exception as e:
        logger.error(f"获取RAGFLOW健康状态失败: {str(e)}")
        raise HTTPException(status_code=500, detail="获取RAGFLOW健康状态失败")


@router.post("/ragflow/health-check", response_model=StandardResponse[Dict[str, Any]])
async def trigger_ragflow_health_check(
    current_user: Dict = Depends(require_admin_auth)
):
    """手动触发RAGFLOW健康检查"""
    try:
        # 这里应该实际触发健康检查
        # 目前返回模拟结果
        check_result = {
            "check_id": f"check_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            "status": "completed",
            "result": "healthy",
            "checked_at": datetime.now().isoformat(),
            "response_time_ms": 120
        }
        
        logger.info("触发RAGFLOW健康检查")
        
        return StandardResponse(
            code=200,
            message="RAGFLOW健康检查已触发",
            data=check_result
        )
        
    except Exception as e:
        logger.error(f"触发RAGFLOW健康检查失败: {str(e)}")
        raise HTTPException(status_code=500, detail="触发RAGFLOW健康检查失败")


# ============ 缓存刷新接口 ============

@router.post("/cache/refresh", response_model=StandardResponse[Dict[str, Any]])
async def refresh_cache(
    refresh_data: Dict[str, Any],
    current_user: Dict = Depends(require_admin_auth),
    cache_service = Depends(get_cache_service_dependency)
):
    """刷新系统缓存"""
    try:
        cache_types = refresh_data.get('cache_types', [])
        force_refresh = refresh_data.get('force_refresh', False)
        
        refresh_results = {}
        
        for cache_type in cache_types:
            try:
                if cache_type == 'intent_config':
                    # 清理意图配置缓存
                    await cache_service.clear_namespace('intent')
                    refresh_results[cache_type] = 'success'
                
                elif cache_type == 'slot_config':
                    # 清理槽位配置缓存
                    await cache_service.clear_namespace('slot')
                    refresh_results[cache_type] = 'success'
                
                elif cache_type == 'function_config':
                    # 清理功能配置缓存
                    await cache_service.clear_namespace('function')
                    refresh_results[cache_type] = 'success'
                
                else:
                    refresh_results[cache_type] = 'unknown_type'
                    
            except Exception as e:
                refresh_results[cache_type] = f'error: {str(e)}'
        
        logger.info(f"缓存刷新完成: {refresh_results}")
        
        return StandardResponse(
            code=200,
            message="缓存刷新完成",
            data={
                "refresh_results": refresh_results,
                "force_refresh": force_refresh,
                "refreshed_at": datetime.now().isoformat()
            }
        )
        
    except Exception as e:
        logger.error(f"缓存刷新失败: {str(e)}")
        raise HTTPException(status_code=500, detail="缓存刷新失败")