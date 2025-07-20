"""
性能监控配置API (TASK-038)
提供性能监控配置的管理功能，包括指标收集、阈值设置、告警配置等
"""
from fastapi import APIRouter, Depends, HTTPException, Query, Path
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
import json

from src.api.dependencies import require_admin_auth, get_cache_service_dependency
from src.schemas.common import StandardResponse
from src.models.audit import ConfigAuditLog
from src.security.dependencies import require_high_security, sanitize_json_body
from src.utils.logger import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/admin/performance", tags=["性能监控配置"])


@router.get("/metrics/config", response_model=StandardResponse[Dict[str, Any]])
async def get_metrics_config(
    current_user: Dict = Depends(require_admin_auth),
    security_check: Dict = Depends(require_high_security),
    cache_service = Depends(get_cache_service_dependency)
):
    """获取指标收集配置"""
    try:
        # 从缓存或配置文件获取指标配置
        config = await cache_service.get("performance:metrics:config")
        
        if not config:
            # 默认配置
            config = {
                "enabled": True,
                "collection_interval_seconds": 60,
                "retention_days": 30,
                "metrics": {
                    "system": {
                        "cpu_usage": {"enabled": True, "threshold_warning": 80, "threshold_critical": 95},
                        "memory_usage": {"enabled": True, "threshold_warning": 85, "threshold_critical": 95},
                        "disk_usage": {"enabled": True, "threshold_warning": 85, "threshold_critical": 95},
                        "network_io": {"enabled": True, "threshold_warning": 100000000, "threshold_critical": 500000000}
                    },
                    "application": {
                        "response_time": {"enabled": True, "threshold_warning": 2000, "threshold_critical": 5000},
                        "request_rate": {"enabled": True, "threshold_warning": 1000, "threshold_critical": 2000},
                        "error_rate": {"enabled": True, "threshold_warning": 5, "threshold_critical": 10},
                        "active_connections": {"enabled": True, "threshold_warning": 500, "threshold_critical": 1000}
                    },
                    "business": {
                        "intent_recognition_accuracy": {"enabled": True, "threshold_warning": 85, "threshold_critical": 75},
                        "slot_extraction_accuracy": {"enabled": True, "threshold_warning": 80, "threshold_critical": 70},
                        "conversation_completion_rate": {"enabled": True, "threshold_warning": 90, "threshold_critical": 80},
                        "user_satisfaction_score": {"enabled": True, "threshold_warning": 4.0, "threshold_critical": 3.0}
                    }
                },
                "alerting": {
                    "enabled": True,
                    "channels": ["email", "webhook"],
                    "email_recipients": ["admin@example.com"],
                    "webhook_url": "https://hooks.slack.com/services/YOUR/WEBHOOK/URL",
                    "cooldown_minutes": 30
                },
                "dashboards": {
                    "enabled": True,
                    "auto_refresh_seconds": 30,
                    "default_time_range": "1h"
                }
            }
            
            # 缓存默认配置
            await cache_service.set("performance:metrics:config", config, expire=3600)
        
        return StandardResponse(
            code=200,
            message="指标收集配置获取成功",
            data=config
        )
        
    except Exception as e:
        logger.error(f"获取指标收集配置失败: {str(e)}")
        raise HTTPException(status_code=500, detail="获取指标收集配置失败")


@router.put("/metrics/config", response_model=StandardResponse[Dict[str, Any]])
async def update_metrics_config(
    current_user: Dict = Depends(require_admin_auth),
    security_check: Dict = Depends(require_high_security),
    config_data: Dict[str, Any] = Depends(sanitize_json_body(allow_html=False)),
    cache_service = Depends(get_cache_service_dependency)
):
    """更新指标收集配置"""
    try:
        # 获取当前配置
        current_config = await cache_service.get("performance:metrics:config") or {}
        
        # 验证配置数据
        validated_config = _validate_metrics_config(config_data)
        
        # 更新配置
        current_config.update(validated_config)
        
        # 保存到缓存
        await cache_service.set("performance:metrics:config", current_config, expire=3600)
        
        # 记录审计日志
        ConfigAuditLog.create(
            table_name_field="performance_metrics_config",
            record_id="metrics_config",
            action="UPDATE",
            old_values={"config_keys": list(validated_config.keys())},
            new_values=validated_config,
            operator_id=current_user.get("user_id", "unknown"),
            operator_name=current_user.get("username", "unknown"),
            ip_address=security_check["client_info"]["ip_address"]
        )
        
        logger.info("更新指标收集配置成功")
        
        return StandardResponse(
            code=200,
            message="指标收集配置更新成功",
            data={
                "updated_fields": list(validated_config.keys()),
                "updated_at": datetime.now().isoformat()
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"更新指标收集配置失败: {str(e)}")
        raise HTTPException(status_code=500, detail="更新指标收集配置失败")


@router.get("/alerts/rules", response_model=StandardResponse[List[Dict[str, Any]]])
async def list_alert_rules(
    current_user: Dict = Depends(require_admin_auth),
    security_check: Dict = Depends(require_high_security),
    enabled: Optional[bool] = Query(None, description="启用状态过滤"),
    severity: Optional[str] = Query(None, description="严重程度过滤"),
    cache_service = Depends(get_cache_service_dependency)
):
    """获取告警规则列表"""
    try:
        # 从缓存获取告警规则
        rules = await cache_service.get("performance:alert:rules") or []
        
        if not rules:
            # 默认告警规则
            rules = [
                {
                    "rule_id": "rule_001",
                    "name": "高CPU使用率告警",
                    "description": "当CPU使用率超过阈值时触发告警",
                    "metric": "system.cpu_usage",
                    "condition": "greater_than",
                    "threshold": 90,
                    "duration_minutes": 5,
                    "severity": "warning",
                    "enabled": True,
                    "actions": ["email", "webhook"],
                    "created_at": "2024-01-01T00:00:00Z",
                    "updated_at": "2024-01-15T12:00:00Z"
                },
                {
                    "rule_id": "rule_002",
                    "name": "高错误率告警", 
                    "description": "当API错误率超过阈值时触发告警",
                    "metric": "application.error_rate",
                    "condition": "greater_than",
                    "threshold": 10,
                    "duration_minutes": 3,
                    "severity": "critical",
                    "enabled": True,
                    "actions": ["email", "webhook", "sms"],
                    "created_at": "2024-01-01T00:00:00Z",
                    "updated_at": "2024-01-20T08:30:00Z"
                },
                {
                    "rule_id": "rule_003",
                    "name": "意图识别准确率下降告警",
                    "description": "当意图识别准确率低于阈值时触发告警",
                    "metric": "business.intent_recognition_accuracy",
                    "condition": "less_than",
                    "threshold": 80,
                    "duration_minutes": 10,
                    "severity": "warning",
                    "enabled": True,
                    "actions": ["email"],
                    "created_at": "2024-01-01T00:00:00Z",
                    "updated_at": "2024-01-25T15:45:00Z"
                }
            ]
            
            # 缓存默认规则
            await cache_service.set("performance:alert:rules", rules, expire=3600)
        
        # 应用过滤条件
        if enabled is not None:
            rules = [rule for rule in rules if rule["enabled"] == enabled]
        if severity:
            rules = [rule for rule in rules if rule["severity"] == severity]
        
        return StandardResponse(
            code=200,
            message="告警规则列表获取成功",
            data=rules
        )
        
    except Exception as e:
        logger.error(f"获取告警规则失败: {str(e)}")
        raise HTTPException(status_code=500, detail="获取告警规则失败")


@router.post("/alerts/rules", response_model=StandardResponse[Dict[str, Any]])
async def create_alert_rule(
    current_user: Dict = Depends(require_admin_auth),
    security_check: Dict = Depends(require_high_security),
    rule_data: Dict[str, Any] = Depends(sanitize_json_body(allow_html=False)),
    cache_service = Depends(get_cache_service_dependency)
):
    """创建告警规则"""
    try:
        # 验证必需字段
        required_fields = ['name', 'metric', 'condition', 'threshold', 'severity']
        for field in required_fields:
            if field not in rule_data:
                raise HTTPException(status_code=400, detail=f"缺少必需字段: {field}")
        
        # 验证告警规则数据
        validated_rule = _validate_alert_rule(rule_data)
        
        # 生成规则ID
        import uuid
        rule_id = f"rule_{uuid.uuid4().hex[:8]}"
        validated_rule["rule_id"] = rule_id
        validated_rule["created_at"] = datetime.now().isoformat()
        validated_rule["updated_at"] = datetime.now().isoformat()
        
        # 获取现有规则
        rules = await cache_service.get("performance:alert:rules") or []
        rules.append(validated_rule)
        
        # 保存到缓存
        await cache_service.set("performance:alert:rules", rules, expire=3600)
        
        # 记录审计日志
        ConfigAuditLog.create(
            table_name_field="performance_alert_rules",
            record_id=rule_id,
            action="CREATE",
            old_values={},
            new_values={
                "name": validated_rule["name"],
                "metric": validated_rule["metric"],
                "severity": validated_rule["severity"]
            },
            operator_id=current_user.get("user_id", "unknown"),
            operator_name=current_user.get("username", "unknown"),
            ip_address=security_check["client_info"]["ip_address"]
        )
        
        logger.info(f"创建告警规则成功: {validated_rule['name']}")
        
        return StandardResponse(
            code=201,
            message="告警规则创建成功",
            data={
                "rule_id": rule_id,
                "name": validated_rule["name"],
                "metric": validated_rule["metric"],
                "severity": validated_rule["severity"],
                "created_at": validated_rule["created_at"]
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"创建告警规则失败: {str(e)}")
        raise HTTPException(status_code=500, detail="创建告警规则失败")


@router.put("/alerts/rules/{rule_id}", response_model=StandardResponse[Dict[str, Any]])
async def update_alert_rule(
    rule_id: str = Path(..., description="告警规则ID"),
    current_user: Dict = Depends(require_admin_auth),
    security_check: Dict = Depends(require_high_security),
    rule_data: Dict[str, Any] = Depends(sanitize_json_body(allow_html=False)),
    cache_service = Depends(get_cache_service_dependency)
):
    """更新告警规则"""
    try:
        # 获取现有规则
        rules = await cache_service.get("performance:alert:rules") or []
        
        # 查找要更新的规则
        rule_index = None
        old_rule = None
        for i, rule in enumerate(rules):
            if rule["rule_id"] == rule_id:
                rule_index = i
                old_rule = rule.copy()
                break
        
        if rule_index is None:
            raise HTTPException(status_code=404, detail="告警规则不存在")
        
        # 验证更新数据
        validated_updates = _validate_alert_rule(rule_data, partial=True)
        
        # 更新规则
        rules[rule_index].update(validated_updates)
        rules[rule_index]["updated_at"] = datetime.now().isoformat()
        
        # 保存到缓存
        await cache_service.set("performance:alert:rules", rules, expire=3600)
        
        # 记录审计日志
        ConfigAuditLog.create(
            table_name_field="performance_alert_rules",
            record_id=rule_id,
            action="UPDATE",
            old_values=old_rule,
            new_values=validated_updates,
            operator_id=current_user.get("user_id", "unknown"),
            operator_name=current_user.get("username", "unknown"),
            ip_address=security_check["client_info"]["ip_address"]
        )
        
        logger.info(f"更新告警规则成功: {rule_id}")
        
        return StandardResponse(
            code=200,
            message="告警规则更新成功",
            data={
                "rule_id": rule_id,
                "updated_fields": list(validated_updates.keys()),
                "updated_at": rules[rule_index]["updated_at"]
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"更新告警规则失败: {str(e)}")
        raise HTTPException(status_code=500, detail="更新告警规则失败")


@router.delete("/alerts/rules/{rule_id}", response_model=StandardResponse[Dict[str, Any]])
async def delete_alert_rule(
    rule_id: str = Path(..., description="告警规则ID"),
    current_user: Dict = Depends(require_admin_auth),
    security_check: Dict = Depends(require_high_security),
    cache_service = Depends(get_cache_service_dependency)
):
    """删除告警规则"""
    try:
        # 获取现有规则
        rules = await cache_service.get("performance:alert:rules") or []
        
        # 查找要删除的规则
        rule_to_delete = None
        rules_updated = []
        for rule in rules:
            if rule["rule_id"] == rule_id:
                rule_to_delete = rule
            else:
                rules_updated.append(rule)
        
        if rule_to_delete is None:
            raise HTTPException(status_code=404, detail="告警规则不存在")
        
        # 保存更新后的规则列表
        await cache_service.set("performance:alert:rules", rules_updated, expire=3600)
        
        # 记录审计日志
        ConfigAuditLog.create(
            table_name_field="performance_alert_rules",
            record_id=rule_id,
            action="DELETE",
            old_values=rule_to_delete,
            new_values={},
            operator_id=current_user.get("user_id", "unknown"),
            operator_name=current_user.get("username", "unknown"),
            ip_address=security_check["client_info"]["ip_address"]
        )
        
        logger.info(f"删除告警规则成功: {rule_id}")
        
        return StandardResponse(
            code=200,
            message="告警规则删除成功",
            data={
                "rule_id": rule_id,
                "rule_name": rule_to_delete["name"],
                "deleted_at": datetime.now().isoformat()
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"删除告警规则失败: {str(e)}")
        raise HTTPException(status_code=500, detail="删除告警规则失败")


@router.get("/dashboard/config", response_model=StandardResponse[Dict[str, Any]])
async def get_dashboard_config(
    current_user: Dict = Depends(require_admin_auth),
    security_check: Dict = Depends(require_high_security),
    cache_service = Depends(get_cache_service_dependency)
):
    """获取仪表盘配置"""
    try:
        # 从缓存获取仪表盘配置
        config = await cache_service.get("performance:dashboard:config")
        
        if not config:
            # 默认仪表盘配置
            config = {
                "layout": {
                    "grid_columns": 12,
                    "grid_rows": 8,
                    "refresh_interval_seconds": 30,
                    "auto_refresh": True
                },
                "widgets": [
                    {
                        "widget_id": "cpu_usage",
                        "title": "CPU使用率",
                        "type": "gauge",
                        "position": {"x": 0, "y": 0, "w": 3, "h": 2},
                        "data_source": "system.cpu_usage",
                        "thresholds": {"warning": 80, "critical": 95},
                        "unit": "%"
                    },
                    {
                        "widget_id": "memory_usage",
                        "title": "内存使用率",
                        "type": "gauge",
                        "position": {"x": 3, "y": 0, "w": 3, "h": 2},
                        "data_source": "system.memory_usage",
                        "thresholds": {"warning": 85, "critical": 95},
                        "unit": "%"
                    },
                    {
                        "widget_id": "response_time",
                        "title": "平均响应时间",
                        "type": "line_chart",
                        "position": {"x": 6, "y": 0, "w": 6, "h": 3},
                        "data_source": "application.response_time",
                        "time_range": "1h",
                        "unit": "ms"
                    },
                    {
                        "widget_id": "request_rate",
                        "title": "请求速率",
                        "type": "area_chart",
                        "position": {"x": 0, "y": 3, "w": 6, "h": 3},
                        "data_source": "application.request_rate",
                        "time_range": "1h",
                        "unit": "req/s"
                    },
                    {
                        "widget_id": "error_rate",
                        "title": "错误率",
                        "type": "line_chart",
                        "position": {"x": 6, "y": 3, "w": 6, "h": 3},
                        "data_source": "application.error_rate",
                        "time_range": "1h",
                        "unit": "%"
                    },
                    {
                        "widget_id": "intent_accuracy",
                        "title": "意图识别准确率",
                        "type": "stat",
                        "position": {"x": 0, "y": 6, "w": 4, "h": 2},
                        "data_source": "business.intent_recognition_accuracy",
                        "unit": "%"
                    },
                    {
                        "widget_id": "active_conversations",
                        "title": "活跃对话数",
                        "type": "stat",
                        "position": {"x": 4, "y": 6, "w": 4, "h": 2},
                        "data_source": "business.active_conversations",
                        "unit": ""
                    },
                    {
                        "widget_id": "system_health",
                        "title": "系统健康状态",
                        "type": "status",
                        "position": {"x": 8, "y": 6, "w": 4, "h": 2},
                        "data_source": "system.health_status"
                    }
                ],
                "themes": {
                    "default": "light",
                    "available": ["light", "dark", "auto"]
                },
                "export": {
                    "enabled": True,
                    "formats": ["png", "pdf", "csv"]
                }
            }
            
            # 缓存默认配置
            await cache_service.set("performance:dashboard:config", config, expire=3600)
        
        return StandardResponse(
            code=200,
            message="仪表盘配置获取成功",
            data=config
        )
        
    except Exception as e:
        logger.error(f"获取仪表盘配置失败: {str(e)}")
        raise HTTPException(status_code=500, detail="获取仪表盘配置失败")


@router.get("/stats/summary", response_model=StandardResponse[Dict[str, Any]])
async def get_performance_summary(
    current_user: Dict = Depends(require_admin_auth),
    security_check: Dict = Depends(require_high_security),
    time_range: str = Query("1h", description="时间范围 (1h, 6h, 24h, 7d, 30d)"),
    cache_service = Depends(get_cache_service_dependency)
):
    """获取性能监控摘要"""
    try:
        # 模拟性能数据（实际应从监控系统获取）
        summary = {
            "time_range": time_range,
            "system_metrics": {
                "cpu_usage": {
                    "current": 45.2,
                    "average": 42.8,
                    "peak": 78.9,
                    "trend": "stable"
                },
                "memory_usage": {
                    "current": 68.5,
                    "average": 65.2,
                    "peak": 82.1,
                    "trend": "increasing"
                },
                "disk_usage": {
                    "current": 45.8,
                    "average": 45.6,
                    "peak": 46.2,
                    "trend": "stable"
                }
            },
            "application_metrics": {
                "response_time": {
                    "current": 1250,
                    "average": 1180,
                    "p95": 2100,
                    "trend": "improving"
                },
                "request_rate": {
                    "current": 125,
                    "average": 118,
                    "peak": 245,
                    "trend": "stable"
                },
                "error_rate": {
                    "current": 2.1,
                    "average": 2.3,
                    "peak": 5.8,
                    "trend": "improving"
                },
                "active_connections": {
                    "current": 85,
                    "average": 78,
                    "peak": 156,
                    "trend": "stable"
                }
            },
            "business_metrics": {
                "intent_recognition_accuracy": {
                    "current": 92.5,
                    "average": 91.8,
                    "minimum": 88.2,
                    "trend": "improving"
                },
                "slot_extraction_accuracy": {
                    "current": 89.3,
                    "average": 88.7,
                    "minimum": 85.1,
                    "trend": "stable"
                },
                "conversation_completion_rate": {
                    "current": 94.2,
                    "average": 93.8,
                    "minimum": 91.5,
                    "trend": "stable"
                }
            },
            "alerts": {
                "active_count": 2,
                "resolved_count": 8,
                "warning_count": 1,
                "critical_count": 1
            },
            "health_status": {
                "overall": "healthy",
                "services": {
                    "api_server": "healthy",
                    "nlu_engine": "healthy", 
                    "database": "warning",
                    "cache": "healthy",
                    "ragflow": "healthy"
                }
            },
            "generated_at": datetime.now().isoformat()
        }
        
        return StandardResponse(
            code=200,
            message="性能监控摘要获取成功",
            data=summary
        )
        
    except Exception as e:
        logger.error(f"获取性能监控摘要失败: {str(e)}")
        raise HTTPException(status_code=500, detail="获取性能监控摘要失败")


def _validate_metrics_config(config_data: Dict[str, Any]) -> Dict[str, Any]:
    """验证指标配置数据"""
    validated = {}
    
    if "enabled" in config_data:
        validated["enabled"] = bool(config_data["enabled"])
    
    if "collection_interval_seconds" in config_data:
        interval = config_data["collection_interval_seconds"]
        if not isinstance(interval, int) or interval < 10:
            raise HTTPException(status_code=400, detail="收集间隔必须至少为10秒")
        validated["collection_interval_seconds"] = interval
    
    if "retention_days" in config_data:
        retention = config_data["retention_days"]
        if not isinstance(retention, int) or retention < 1:
            raise HTTPException(status_code=400, detail="保留天数必须至少为1天")
        validated["retention_days"] = retention
    
    if "metrics" in config_data:
        validated["metrics"] = config_data["metrics"]
    
    if "alerting" in config_data:
        validated["alerting"] = config_data["alerting"]
    
    return validated


def _validate_alert_rule(rule_data: Dict[str, Any], partial: bool = False) -> Dict[str, Any]:
    """验证告警规则数据"""
    validated = {}
    
    # 验证必需字段（仅在创建时）
    if not partial:
        required_fields = ['name', 'metric', 'condition', 'threshold', 'severity']
        for field in required_fields:
            if field not in rule_data:
                raise HTTPException(status_code=400, detail=f"缺少必需字段: {field}")
    
    if "name" in rule_data:
        if not rule_data["name"].strip():
            raise HTTPException(status_code=400, detail="规则名称不能为空")
        validated["name"] = rule_data["name"].strip()
    
    if "description" in rule_data:
        validated["description"] = rule_data["description"]
    
    if "metric" in rule_data:
        validated["metric"] = rule_data["metric"]
    
    if "condition" in rule_data:
        valid_conditions = ["greater_than", "less_than", "equal_to", "not_equal_to"]
        if rule_data["condition"] not in valid_conditions:
            raise HTTPException(status_code=400, detail=f"无效的条件: {rule_data['condition']}")
        validated["condition"] = rule_data["condition"]
    
    if "threshold" in rule_data:
        validated["threshold"] = rule_data["threshold"]
    
    if "duration_minutes" in rule_data:
        duration = rule_data["duration_minutes"]
        if not isinstance(duration, int) or duration < 1:
            raise HTTPException(status_code=400, detail="持续时间必须至少为1分钟")
        validated["duration_minutes"] = duration
    
    if "severity" in rule_data:
        valid_severities = ["info", "warning", "critical"]
        if rule_data["severity"] not in valid_severities:
            raise HTTPException(status_code=400, detail=f"无效的严重程度: {rule_data['severity']}")
        validated["severity"] = rule_data["severity"]
    
    if "enabled" in rule_data:
        validated["enabled"] = bool(rule_data["enabled"])
    
    if "actions" in rule_data:
        if not isinstance(rule_data["actions"], list):
            raise HTTPException(status_code=400, detail="动作必须是数组")
        validated["actions"] = rule_data["actions"]
    
    return validated