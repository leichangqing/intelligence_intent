"""
审计日志管理API (TASK-038)
提供审计日志的查询、分析、配置和管理功能
"""
from fastapi import APIRouter, Depends, HTTPException, Query, Path
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
import json

from src.api.dependencies import require_admin_auth, get_cache_service_dependency
from src.schemas.common import StandardResponse
from src.models.audit import ConfigAuditLog, SecurityAuditLog
from src.security.dependencies import require_high_security, sanitize_json_body
from src.utils.logger import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/admin/audit", tags=["审计日志管理"])


@router.get("/config-logs", response_model=StandardResponse[List[Dict[str, Any]]])
async def list_config_audit_logs(
    current_user: Dict = Depends(require_admin_auth),
    security_check: Dict = Depends(require_high_security),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    table_name: Optional[str] = Query(None, description="表名过滤"),
    action: Optional[str] = Query(None, description="操作类型过滤"),
    operator_name: Optional[str] = Query(None, description="操作者过滤"),
    start_time: Optional[str] = Query(None, description="开始时间 (ISO格式)"),
    end_time: Optional[str] = Query(None, description="结束时间 (ISO格式)")
):
    """获取配置审计日志列表"""
    try:
        # 构建查询条件
        query = ConfigAuditLog.select()
        
        if table_name:
            query = query.where(ConfigAuditLog.table_name_field == table_name)
        
        if action:
            query = query.where(ConfigAuditLog.action == action)
        
        if operator_name:
            query = query.where(ConfigAuditLog.operator_name.contains(operator_name))
        
        if start_time:
            try:
                start_dt = datetime.fromisoformat(start_time.replace('Z', '+00:00'))
                query = query.where(ConfigAuditLog.created_at >= start_dt)
            except ValueError:
                raise HTTPException(status_code=400, detail="无效的开始时间格式")
        
        if end_time:
            try:
                end_dt = datetime.fromisoformat(end_time.replace('Z', '+00:00'))
                query = query.where(ConfigAuditLog.created_at <= end_dt)
            except ValueError:
                raise HTTPException(status_code=400, detail="无效的结束时间格式")
        
        # 计算总数
        total = query.count()
        
        # 分页查询
        offset = (page - 1) * page_size
        logs = query.offset(offset).limit(page_size).order_by(ConfigAuditLog.created_at.desc())
        
        # 构建响应数据
        log_list = []
        for log in logs:
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
            message="配置审计日志列表获取成功",
            data=response_data
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取配置审计日志失败: {str(e)}")
        raise HTTPException(status_code=500, detail="获取配置审计日志失败")


@router.get("/security-logs", response_model=StandardResponse[List[Dict[str, Any]]])
async def list_security_audit_logs(
    current_user: Dict = Depends(require_admin_auth),
    security_check: Dict = Depends(require_high_security),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    event_type: Optional[str] = Query(None, description="事件类型过滤"),
    severity: Optional[str] = Query(None, description="严重程度过滤"),
    username: Optional[str] = Query(None, description="用户名过滤"),
    ip_address: Optional[str] = Query(None, description="IP地址过滤"),
    start_time: Optional[str] = Query(None, description="开始时间 (ISO格式)"),
    end_time: Optional[str] = Query(None, description="结束时间 (ISO格式)")
):
    """获取安全审计日志列表"""
    try:
        # 构建查询条件
        query = SecurityAuditLog.select()
        
        if event_type:
            query = query.where(SecurityAuditLog.event_type == event_type)
        
        if severity:
            query = query.where(SecurityAuditLog.severity == severity)
        
        if username:
            query = query.where(SecurityAuditLog.username.contains(username))
        
        if ip_address:
            query = query.where(SecurityAuditLog.ip_address == ip_address)
        
        if start_time:
            try:
                start_dt = datetime.fromisoformat(start_time.replace('Z', '+00:00'))
                query = query.where(SecurityAuditLog.created_at >= start_dt)
            except ValueError:
                raise HTTPException(status_code=400, detail="无效的开始时间格式")
        
        if end_time:
            try:
                end_dt = datetime.fromisoformat(end_time.replace('Z', '+00:00'))
                query = query.where(SecurityAuditLog.created_at <= end_dt)
            except ValueError:
                raise HTTPException(status_code=400, detail="无效的结束时间格式")
        
        # 计算总数
        total = query.count()
        
        # 分页查询
        offset = (page - 1) * page_size
        logs = query.offset(offset).limit(page_size).order_by(SecurityAuditLog.created_at.desc())
        
        # 构建响应数据
        log_list = []
        for log in logs:
            log_data = {
                "id": log.id,
                "event_type": log.event_type,
                "severity": log.severity,
                "description": log.description,
                "user_id": log.user_id,
                "username": log.username,
                "ip_address": log.ip_address,
                "user_agent": log.user_agent,
                "request_data": log.get_request_data(),
                "response_data": log.get_response_data(),
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
            message="安全审计日志列表获取成功",
            data=response_data
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取安全审计日志失败: {str(e)}")
        raise HTTPException(status_code=500, detail="获取安全审计日志失败")


@router.get("/config", response_model=StandardResponse[Dict[str, Any]])
async def get_audit_config(
    current_user: Dict = Depends(require_admin_auth),
    security_check: Dict = Depends(require_high_security),
    cache_service = Depends(get_cache_service_dependency)
):
    """获取审计日志配置"""
    try:
        # 从缓存获取审计配置
        config = await cache_service.get("audit:config")
        
        if not config:
            # 默认审计配置
            config = {
                "enabled": True,
                "config_audit": {
                    "enabled": True,
                    "retention_days": 90,
                    "tracked_tables": [
                        "intents", "slots", "templates", "functions", 
                        "api_keys", "users", "system_config"
                    ],
                    "tracked_actions": ["CREATE", "UPDATE", "DELETE"],
                    "log_old_values": True,
                    "log_new_values": True
                },
                "security_audit": {
                    "enabled": True,
                    "retention_days": 180,
                    "tracked_events": [
                        "LOGIN_SUCCESS", "LOGIN_FAILED", "LOGOUT",
                        "API_KEY_CREATED", "API_KEY_REVOKED",
                        "THREAT_DETECTED", "ATTACK_BLOCKED",
                        "PERMISSION_DENIED", "UNAUTHORIZED_ACCESS"
                    ],
                    "severity_levels": ["INFO", "WARNING", "ERROR", "CRITICAL"],
                    "log_request_data": True,
                    "log_response_data": False,
                    "sensitive_fields": ["password", "secret_key", "token"]
                },
                "storage": {
                    "type": "database",
                    "backup_enabled": True,
                    "backup_interval_days": 7,
                    "compression_enabled": True,
                    "encryption_enabled": True
                },
                "export": {
                    "enabled": True,
                    "formats": ["json", "csv", "pdf"],
                    "max_records_per_export": 10000,
                    "require_approval": True
                },
                "alerting": {
                    "enabled": True,
                    "critical_events_alert": True,
                    "failed_logins_threshold": 5,
                    "suspicious_activity_alert": True,
                    "notification_channels": ["email", "webhook"]
                }
            }
            
            # 缓存默认配置
            await cache_service.set("audit:config", config, expire=3600)
        
        return StandardResponse(
            code=200,
            message="审计日志配置获取成功",
            data=config
        )
        
    except Exception as e:
        logger.error(f"获取审计日志配置失败: {str(e)}")
        raise HTTPException(status_code=500, detail="获取审计日志配置失败")


@router.put("/config", response_model=StandardResponse[Dict[str, Any]])
async def update_audit_config(
    current_user: Dict = Depends(require_admin_auth),
    security_check: Dict = Depends(require_high_security),
    config_data: Dict[str, Any] = Depends(sanitize_json_body(allow_html=False)),
    cache_service = Depends(get_cache_service_dependency)
):
    """更新审计日志配置"""
    try:
        # 获取当前配置
        current_config = await cache_service.get("audit:config") or {}
        
        # 验证配置数据
        validated_config = _validate_audit_config(config_data)
        
        # 更新配置
        current_config.update(validated_config)
        
        # 保存到缓存
        await cache_service.set("audit:config", current_config, expire=3600)
        
        # 记录配置变更
        ConfigAuditLog.create(
            table_name_field="audit_config",
            record_id="audit_config",
            action="UPDATE",
            old_values={"config_keys": list(validated_config.keys())},
            new_values=validated_config,
            operator_id=current_user.get("user_id", "unknown"),
            operator_name=current_user.get("username", "unknown"),
            ip_address=security_check["client_info"]["ip_address"]
        )
        
        logger.info("更新审计日志配置成功")
        
        return StandardResponse(
            code=200,
            message="审计日志配置更新成功",
            data={
                "updated_fields": list(validated_config.keys()),
                "updated_at": datetime.now().isoformat()
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"更新审计日志配置失败: {str(e)}")
        raise HTTPException(status_code=500, detail="更新审计日志配置失败")


@router.get("/statistics", response_model=StandardResponse[Dict[str, Any]])
async def get_audit_statistics(
    current_user: Dict = Depends(require_admin_auth),
    security_check: Dict = Depends(require_high_security),
    days: int = Query(30, ge=1, le=365, description="统计天数")
):
    """获取审计日志统计信息"""
    try:
        # 计算时间范围
        start_time = datetime.now() - timedelta(days=days)
        
        # 配置审计统计
        config_logs = ConfigAuditLog.select().where(ConfigAuditLog.created_at >= start_time)
        config_stats = {
            "total_changes": config_logs.count(),
            "create_operations": config_logs.where(ConfigAuditLog.action == "CREATE").count(),
            "update_operations": config_logs.where(ConfigAuditLog.action == "UPDATE").count(),
            "delete_operations": config_logs.where(ConfigAuditLog.action == "DELETE").count()
        }
        
        # 按表统计配置变更
        table_stats = {}
        for log in config_logs:
            table_name = log.table_name_field
            table_stats[table_name] = table_stats.get(table_name, 0) + 1
        
        # 按操作者统计
        operator_stats = {}
        for log in config_logs:
            operator = log.operator_name
            operator_stats[operator] = operator_stats.get(operator, 0) + 1
        
        # 安全审计统计
        security_logs = SecurityAuditLog.select().where(SecurityAuditLog.created_at >= start_time)
        security_stats = {
            "total_events": security_logs.count(),
            "info_events": security_logs.where(SecurityAuditLog.severity == "INFO").count(),
            "warning_events": security_logs.where(SecurityAuditLog.severity == "WARNING").count(),
            "error_events": security_logs.where(SecurityAuditLog.severity == "ERROR").count(),
            "critical_events": security_logs.where(SecurityAuditLog.severity == "CRITICAL").count()
        }
        
        # 按事件类型统计
        event_type_stats = {}
        for log in security_logs:
            event_type = log.event_type
            event_type_stats[event_type] = event_type_stats.get(event_type, 0) + 1
        
        # 按用户统计安全事件
        user_stats = {}
        for log in security_logs:
            username = log.username or "unknown"
            user_stats[username] = user_stats.get(username, 0) + 1
        
        # 按IP统计
        ip_stats = {}
        for log in security_logs:
            ip = log.ip_address or "unknown"
            ip_stats[ip] = ip_stats.get(ip, 0) + 1
        
        # 时间分布统计（按天）
        daily_stats = {}
        all_logs = list(config_logs) + list(security_logs)
        for log in all_logs:
            date_key = log.created_at.date().isoformat()
            daily_stats[date_key] = daily_stats.get(date_key, 0) + 1
        
        # 风险评估
        risk_score = 0
        if security_stats["critical_events"] > 0:
            risk_score += 50
        if security_stats["error_events"] > 10:
            risk_score += 30
        if security_stats["warning_events"] > 50:
            risk_score += 20
        
        risk_level = "低"
        if risk_score > 70:
            risk_level = "高"
        elif risk_score > 40:
            risk_level = "中"
        
        statistics = {
            "time_range_days": days,
            "config_audit": {
                **config_stats,
                "top_changed_tables": dict(sorted(table_stats.items(), key=lambda x: x[1], reverse=True)[:10]),
                "top_operators": dict(sorted(operator_stats.items(), key=lambda x: x[1], reverse=True)[:10])
            },
            "security_audit": {
                **security_stats,
                "top_event_types": dict(sorted(event_type_stats.items(), key=lambda x: x[1], reverse=True)[:10]),
                "top_users": dict(sorted(user_stats.items(), key=lambda x: x[1], reverse=True)[:10]),
                "top_ips": dict(sorted(ip_stats.items(), key=lambda x: x[1], reverse=True)[:10])
            },
            "daily_distribution": daily_stats,
            "risk_assessment": {
                "risk_score": min(100, risk_score),
                "risk_level": risk_level,
                "recommendations": _generate_audit_recommendations(security_stats, config_stats)
            },
            "generated_at": datetime.now().isoformat()
        }
        
        return StandardResponse(
            code=200,
            message="审计日志统计信息获取成功",
            data=statistics
        )
        
    except Exception as e:
        logger.error(f"获取审计日志统计失败: {str(e)}")
        raise HTTPException(status_code=500, detail="获取审计日志统计失败")


@router.post("/export", response_model=StandardResponse[Dict[str, Any]])
async def export_audit_logs(
    current_user: Dict = Depends(require_admin_auth),
    security_check: Dict = Depends(require_high_security),
    export_data: Dict[str, Any] = Depends(sanitize_json_body(allow_html=False))
):
    """导出审计日志"""
    try:
        # 验证导出参数
        log_type = export_data.get("log_type", "all")  # config, security, all
        format_type = export_data.get("format", "json")  # json, csv, pdf
        start_time = export_data.get("start_time")
        end_time = export_data.get("end_time")
        filters = export_data.get("filters", {})
        
        if format_type not in ["json", "csv", "pdf"]:
            raise HTTPException(status_code=400, detail="不支持的导出格式")
        
        # 解析时间范围
        start_dt = None
        end_dt = None
        
        if start_time:
            try:
                start_dt = datetime.fromisoformat(start_time.replace('Z', '+00:00'))
            except ValueError:
                raise HTTPException(status_code=400, detail="无效的开始时间格式")
        
        if end_time:
            try:
                end_dt = datetime.fromisoformat(end_time.replace('Z', '+00:00'))
            except ValueError:
                raise HTTPException(status_code=400, detail="无效的结束时间格式")
        
        # 生成导出任务ID
        import uuid
        export_id = f"export_{uuid.uuid4().hex[:8]}"
        
        # 模拟导出处理（实际应异步处理）
        exported_records = 0
        file_size = 0
        
        if log_type in ["config", "all"]:
            config_query = ConfigAuditLog.select()
            if start_dt:
                config_query = config_query.where(ConfigAuditLog.created_at >= start_dt)
            if end_dt:
                config_query = config_query.where(ConfigAuditLog.created_at <= end_dt)
            exported_records += config_query.count()
        
        if log_type in ["security", "all"]:
            security_query = SecurityAuditLog.select()
            if start_dt:
                security_query = security_query.where(SecurityAuditLog.created_at >= start_dt)
            if end_dt:
                security_query = security_query.where(SecurityAuditLog.created_at <= end_dt)
            exported_records += security_query.count()
        
        # 估算文件大小（每条记录约1KB）
        file_size = exported_records * 1024
        
        # 记录导出操作
        SecurityAuditLog.create(
            event_type="AUDIT_LOG_EXPORT",
            severity="INFO",
            description=f"导出审计日志: {log_type} 格式: {format_type} 记录数: {exported_records}",
            user_id=current_user.get("user_id", "unknown"),
            username=current_user.get("username", "unknown"),
            ip_address=security_check["client_info"]["ip_address"],
            user_agent=security_check["client_info"]["user_agent"],
            request_data=json.dumps(export_data)
        )
        
        # 实际环境中，这里应该创建一个异步任务来处理导出
        export_result = {
            "export_id": export_id,
            "status": "completed",  # pending, processing, completed, failed
            "log_type": log_type,
            "format": format_type,
            "exported_records": exported_records,
            "file_size_bytes": file_size,
            "download_url": f"/api/v1/admin/audit/downloads/{export_id}",
            "expires_at": (datetime.now() + timedelta(hours=24)).isoformat(),
            "created_at": datetime.now().isoformat()
        }
        
        logger.info(f"审计日志导出完成: {export_id} ({exported_records} 条记录)")
        
        return StandardResponse(
            code=200,
            message="审计日志导出成功",
            data=export_result
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"导出审计日志失败: {str(e)}")
        raise HTTPException(status_code=500, detail="导出审计日志失败")


@router.delete("/cleanup", response_model=StandardResponse[Dict[str, Any]])
async def cleanup_audit_logs(
    current_user: Dict = Depends(require_admin_auth),
    security_check: Dict = Depends(require_high_security),
    cleanup_data: Dict[str, Any] = Depends(sanitize_json_body(allow_html=False))
):
    """清理过期的审计日志"""
    try:
        log_type = cleanup_data.get("log_type", "all")  # config, security, all
        retention_days = cleanup_data.get("retention_days", 90)
        
        if retention_days < 30:
            raise HTTPException(status_code=400, detail="保留期不能少于30天")
        
        # 计算清理截止时间
        cutoff_time = datetime.now() - timedelta(days=retention_days)
        
        cleaned_records = 0
        
        # 清理配置审计日志
        if log_type in ["config", "all"]:
            config_count = ConfigAuditLog.delete().where(
                ConfigAuditLog.created_at < cutoff_time
            ).execute()
            cleaned_records += config_count
        
        # 清理安全审计日志
        if log_type in ["security", "all"]:
            security_count = SecurityAuditLog.delete().where(
                SecurityAuditLog.created_at < cutoff_time
            ).execute()
            cleaned_records += security_count
        
        # 记录清理操作
        SecurityAuditLog.create(
            event_type="AUDIT_LOG_CLEANUP",
            severity="INFO",
            description=f"清理审计日志: {log_type} 保留期: {retention_days}天 清理记录数: {cleaned_records}",
            user_id=current_user.get("user_id", "unknown"),
            username=current_user.get("username", "unknown"),
            ip_address=security_check["client_info"]["ip_address"],
            user_agent=security_check["client_info"]["user_agent"],
            request_data=json.dumps(cleanup_data)
        )
        
        logger.info(f"清理审计日志完成: {cleaned_records} 条记录")
        
        return StandardResponse(
            code=200,
            message="审计日志清理成功",
            data={
                "log_type": log_type,
                "retention_days": retention_days,
                "cleaned_records": cleaned_records,
                "cutoff_time": cutoff_time.isoformat(),
                "cleaned_at": datetime.now().isoformat()
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"清理审计日志失败: {str(e)}")
        raise HTTPException(status_code=500, detail="清理审计日志失败")


def _validate_audit_config(config_data: Dict[str, Any]) -> Dict[str, Any]:
    """验证审计配置数据"""
    validated = {}
    
    if "enabled" in config_data:
        validated["enabled"] = bool(config_data["enabled"])
    
    if "config_audit" in config_data:
        config_audit = config_data["config_audit"]
        if isinstance(config_audit, dict):
            validated["config_audit"] = config_audit
    
    if "security_audit" in config_data:
        security_audit = config_data["security_audit"]
        if isinstance(security_audit, dict):
            validated["security_audit"] = security_audit
    
    if "storage" in config_data:
        storage = config_data["storage"]
        if isinstance(storage, dict):
            validated["storage"] = storage
    
    if "export" in config_data:
        export_config = config_data["export"]
        if isinstance(export_config, dict):
            validated["export"] = export_config
    
    if "alerting" in config_data:
        alerting = config_data["alerting"]
        if isinstance(alerting, dict):
            validated["alerting"] = alerting
    
    return validated


def _generate_audit_recommendations(security_stats: Dict, config_stats: Dict) -> List[str]:
    """生成审计建议"""
    recommendations = []
    
    if security_stats.get("critical_events", 0) > 0:
        recommendations.append("检测到严重安全事件，建议立即调查并采取应对措施")
    
    if security_stats.get("error_events", 0) > 10:
        recommendations.append("错误事件较多，建议检查系统配置和用户权限设置")
    
    if config_stats.get("total_changes", 0) > 100:
        recommendations.append("配置变更频繁，建议建立变更审批流程")
    
    if security_stats.get("warning_events", 0) > 50:
        recommendations.append("警告事件较多，建议加强用户培训和访问控制")
    
    if len(recommendations) == 0:
        recommendations.append("审计日志状态正常，建议保持当前监控策略")
    
    return recommendations