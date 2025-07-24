"""
监控和健康检查 API (V2.2重构)
提供系统监控、健康检查和稳定性验证的RESTful接口
"""
from typing import Dict, Any, Optional
from fastapi import APIRouter, HTTPException, BackgroundTasks, Query
from pydantic import BaseModel
from datetime import datetime

from src.services.monitoring_setup import (
    get_monitoring_system, quick_health_check, 
    quick_stability_validation, get_monitoring_dashboard
)
from src.services.monitoring_service import AlertLevel
from src.utils.logger import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/monitoring", tags=["monitoring"])


class HealthCheckResponse(BaseModel):
    """健康检查响应模型"""
    overall_status: str
    execution_time_ms: float
    timestamp: str
    components: list
    summary: Dict[str, Any]


class StabilityValidationResponse(BaseModel):
    """稳定性验证响应模型"""
    overall_status: str
    execution_time_seconds: float
    timestamp: str
    summary: Dict[str, Any]
    test_results: list
    errors: list
    recommendations: list


class MonitoringDashboardResponse(BaseModel):
    """监控面板响应模型"""
    timestamp: str
    system_status: str
    monitoring_enabled: bool
    health_status: Optional[Dict[str, Any]] = None
    system_metrics: Optional[Dict[str, Any]] = None
    monitoring_status: Optional[Dict[str, Any]] = None
    recent_alerts: Optional[list] = None
    key_metrics: Optional[Dict[str, Any]] = None


@router.get("/health", response_model=HealthCheckResponse, summary="系统健康检查")
async def health_check():
    """
    执行系统健康检查
    
    检查数据库、缓存、审计系统、数据一致性等组件的健康状态。
    
    Returns:
        HealthCheckResponse: 健康检查结果
    """
    try:
        logger.info("API调用: 系统健康检查")
        
        health_data = await quick_health_check()
        
        if 'error' in health_data:
            raise HTTPException(
                status_code=503,
                detail=f"健康检查失败: {health_data['error']}"
            )
        
        return HealthCheckResponse(**health_data)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"健康检查API失败: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"健康检查失败: {str(e)}"
        )


@router.get("/stability", response_model=StabilityValidationResponse, summary="系统稳定性验证")
async def stability_validation(
    background_tasks: BackgroundTasks,
    save_report: bool = Query(False, description="是否保存验证报告")
):
    """
    执行系统稳定性验证
    
    运行全面的稳定性测试，包括数据库稳定性、缓存稳定性、服务集成、
    数据一致性、性能负载测试等。
    
    Args:
        save_report: 是否保存详细报告到文件
        
    Returns:
        StabilityValidationResponse: 稳定性验证结果
    """
    try:
        logger.info(f"API调用: 系统稳定性验证 (save_report={save_report})")
        
        # 如果需要保存报告，使用后台任务执行完整验证
        if save_report:
            monitoring_system = get_monitoring_system()
            if not monitoring_system:
                raise HTTPException(
                    status_code=503,
                    detail="监控系统未初始化"
                )
            
            # 在后台执行完整的稳定性验证
            background_tasks.add_task(
                monitoring_system.run_stability_validation, True
            )
            
            return StabilityValidationResponse(
                overall_status="running",
                execution_time_seconds=0,
                timestamp=datetime.now().isoformat(),
                summary={
                    "total_tests": 0,
                    "passed_tests": 0,
                    "failed_tests": 0,
                    "success_rate": 0,
                    "total_errors": 0
                },
                test_results=[],
                errors=[],
                recommendations=["稳定性验证正在后台运行，请稍后查看日志或报告文件"]
            )
        
        # 执行快速稳定性验证
        stability_data = await quick_stability_validation()
        
        if 'error' in stability_data:
            raise HTTPException(
                status_code=503,
                detail=f"稳定性验证失败: {stability_data['error']}"
            )
        
        return StabilityValidationResponse(**stability_data)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"稳定性验证API失败: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"稳定性验证失败: {str(e)}"
        )


@router.get("/dashboard", response_model=MonitoringDashboardResponse, summary="监控面板")
async def monitoring_dashboard():
    """
    获取监控面板数据
    
    提供系统监控的综合视图，包括健康状态、系统指标、
    最近告警、关键性能指标等。
    
    Returns:
        MonitoringDashboardResponse: 监控面板数据
    """
    try:
        logger.info("API调用: 监控面板")
        
        dashboard_data = await get_monitoring_dashboard()
        
        if 'error' in dashboard_data:
            raise HTTPException(
                status_code=503,
                detail=f"获取监控面板数据失败: {dashboard_data['error']}"
            )
        
        return MonitoringDashboardResponse(**dashboard_data)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"监控面板API失败: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"获取监控面板数据失败: {str(e)}"
        )


@router.get("/alerts", summary="获取系统告警")
async def get_alerts(
    hours: int = Query(24, ge=1, le=168, description="获取多少小时内的告警"),
    level: Optional[str] = Query(None, description="告警级别过滤 (info/warning/critical)")
):
    """
    获取系统告警列表
    
    Args:
        hours: 时间范围（小时），1-168小时
        level: 告警级别过滤
        
    Returns:
        Dict: 告警列表
    """
    try:
        logger.info(f"API调用: 获取告警 (hours={hours}, level={level})")
        
        monitoring_system = get_monitoring_system()
        if not monitoring_system or not monitoring_system.monitoring_service:
            raise HTTPException(
                status_code=503,
                detail="监控服务未启动"
            )
        
        # 转换告警级别
        alert_level = None
        if level:
            level_map = {
                'info': AlertLevel.INFO,
                'warning': AlertLevel.WARNING,
                'critical': AlertLevel.CRITICAL
            }
            alert_level = level_map.get(level.lower())
            if alert_level is None:
                raise HTTPException(
                    status_code=400,
                    detail="无效的告警级别，支持: info, warning, critical"
                )
        
        alerts = monitoring_system.monitoring_service.get_recent_alerts(
            hours=hours, level=alert_level
        )
        
        return {
            'alerts': alerts,
            'total_count': len(alerts),
            'time_range_hours': hours,
            'level_filter': level,
            'timestamp': datetime.now().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取告警API失败: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"获取告警失败: {str(e)}"
        )


@router.get("/metrics/{metric_name}", summary="获取系统指标")
async def get_metrics(
    metric_name: str,
    hours: int = Query(1, ge=1, le=72, description="获取多少小时内的指标")
):
    """
    获取特定指标的历史数据
    
    Args:
        metric_name: 指标名称
        hours: 时间范围（小时）
        
    Returns:
        Dict: 指标数据
    """
    try:
        logger.info(f"API调用: 获取指标 {metric_name} (hours={hours})")
        
        monitoring_system = get_monitoring_system()
        if not monitoring_system or not monitoring_system.monitoring_service:
            raise HTTPException(
                status_code=503,
                detail="监控服务未启动"
            )
        
        metrics = monitoring_system.monitoring_service.get_metrics(metric_name, hours)
        
        return {
            'metric_name': metric_name,
            'data': metrics,
            'data_points': len(metrics),
            'time_range_hours': hours,
            'timestamp': datetime.now().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取指标API失败: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"获取指标失败: {str(e)}"
        )


@router.get("/status", summary="监控系统状态")
async def monitoring_status():
    """
    获取监控系统自身的状态
    
    Returns:
        Dict: 监控系统状态信息
    """
    try:
        logger.info("API调用: 监控系统状态")
        
        monitoring_system = get_monitoring_system()
        if not monitoring_system:
            return {
                'monitoring_system': 'not_initialized',
                'timestamp': datetime.now().isoformat()
            }
        
        status = monitoring_system.get_status()
        
        if monitoring_system.monitoring_service:
            monitoring_service_status = monitoring_system.monitoring_service.get_monitoring_status()
            status.update(monitoring_service_status)
        
        status['timestamp'] = datetime.now().isoformat()
        
        return status
        
    except Exception as e:
        logger.error(f"获取监控状态API失败: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"获取监控状态失败: {str(e)}"
        )


@router.post("/alert-rules", summary="更新告警规则")
async def update_alert_rules(rules: Dict[str, Dict[str, Any]]):
    """
    更新系统告警规则
    
    Args:
        rules: 告警规则配置
        
    Returns:
        Dict: 更新结果
    """
    try:
        logger.info("API调用: 更新告警规则")
        
        monitoring_system = get_monitoring_system()
        if not monitoring_system or not monitoring_system.monitoring_service:
            raise HTTPException(
                status_code=503,
                detail="监控服务未启动"
            )
        
        await monitoring_system.monitoring_service.update_alert_rules(rules)
        
        return {
            'success': True,
            'message': '告警规则更新成功',
            'timestamp': datetime.now().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"更新告警规则API失败: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"更新告警规则失败: {str(e)}"
        )