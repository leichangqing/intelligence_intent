"""
安全配置管理API (TASK-038)
提供安全配置的完整CRUD操作和管理功能，包括API密钥、访问控制、威胁检测等
"""
from fastapi import APIRouter, Depends, HTTPException, Query, Path
from typing import Dict, List, Any, Optional, Union
from datetime import datetime, timedelta
import json
import ipaddress

from src.api.dependencies import require_admin_auth, get_cache_service_dependency
from src.schemas.common import StandardResponse
from src.models.audit import SecurityAuditLog, ConfigAuditLog
from src.security.dependencies import require_high_security, sanitize_json_body
from src.security.api_key_manager import ApiKeyManager, ApiKeyScope, ApiKeyStatus
from src.security.threat_detector import ThreatDetector, ThreatCategory, ThreatSeverity
from src.utils.logger import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/admin/security", tags=["安全配置管理"])


@router.get("/api-keys", response_model=StandardResponse[List[Dict[str, Any]]])
async def list_api_keys(
    current_user: Dict = Depends(require_admin_auth),
    security_check: Dict = Depends(require_high_security),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    client_id: Optional[str] = Query(None, description="客户端ID过滤"),
    status: Optional[str] = Query(None, description="状态过滤"),
    cache_service = Depends(get_cache_service_dependency)
):
    """获取API密钥列表"""
    try:
        api_key_manager = ApiKeyManager(cache_service)
        
        # 获取API密钥列表
        api_keys = await api_key_manager.list_api_keys(
            client_id=client_id,
            status=ApiKeyStatus(status) if status else None,
            limit=page_size,
            offset=(page - 1) * page_size
        )
        
        # 获取总数
        total_count = await api_key_manager.count_api_keys(
            client_id=client_id,
            status=ApiKeyStatus(status) if status else None
        )
        
        # 构建响应数据
        key_list = []
        for key_info in api_keys:
            # 获取使用统计
            usage_stats = await api_key_manager.get_key_usage_stats(key_info.key_id, days=30)
            
            key_data = {
                "key_id": key_info.key_id,
                "public_key": key_info.public_key,
                "name": key_info.name,
                "description": key_info.description,
                "client_id": key_info.client_id,
                "scopes": [scope.value for scope in key_info.scopes],
                "status": key_info.status.value,
                "rate_limit_per_hour": key_info.rate_limit_per_hour,
                "allowed_ips": key_info.allowed_ips,
                "usage_count": key_info.usage_count,
                "last_used_at": key_info.last_used_at.isoformat() if key_info.last_used_at else None,
                "expires_at": key_info.expires_at.isoformat() if key_info.expires_at else None,
                "created_at": key_info.created_at.isoformat(),
                "usage_stats": {
                    "monthly_requests": usage_stats.get("total_requests", 0),
                    "success_rate": usage_stats.get("success_rate", 0),
                    "avg_response_time": usage_stats.get("avg_response_time_ms", 0)
                },
                "metadata": key_info.metadata
            }
            key_list.append(key_data)
        
        response_data = {
            "items": key_list,
            "pagination": {
                "page": page,
                "page_size": page_size,
                "total": total_count,
                "pages": (total_count + page_size - 1) // page_size
            }
        }
        
        return StandardResponse(
            code=200,
            message="API密钥列表获取成功",
            data=response_data
        )
        
    except Exception as e:
        logger.error(f"获取API密钥列表失败: {str(e)}")
        raise HTTPException(status_code=500, detail="获取API密钥列表失败")


@router.post("/api-keys", response_model=StandardResponse[Dict[str, Any]])
async def create_api_key(
    current_user: Dict = Depends(require_admin_auth),
    security_check: Dict = Depends(require_high_security),
    key_data: Dict[str, Any] = Depends(sanitize_json_body(allow_html=False)),
    cache_service = Depends(get_cache_service_dependency)
):
    """创建新的API密钥"""
    try:
        # 验证必需字段
        required_fields = ['name', 'client_id', 'scopes']
        for field in required_fields:
            if field not in key_data:
                raise HTTPException(status_code=400, detail=f"缺少必需字段: {field}")
        
        # 验证权限范围
        try:
            scopes = [ApiKeyScope(scope) for scope in key_data['scopes']]
        except ValueError as e:
            raise HTTPException(status_code=400, detail=f"无效的权限范围: {str(e)}")
        
        # 验证IP地址列表
        allowed_ips = key_data.get('allowed_ips', [])
        if allowed_ips:
            try:
                for ip in allowed_ips:
                    ipaddress.ip_address(ip)
            except ValueError:
                raise HTTPException(status_code=400, detail="无效的IP地址格式")
        
        api_key_manager = ApiKeyManager(cache_service)
        
        # 生成API密钥
        public_key, secret_key = await api_key_manager.generate_api_key(
            name=key_data['name'],
            description=key_data.get('description', ''),
            scopes=scopes,
            client_id=key_data['client_id'],
            expires_in_days=key_data.get('expires_in_days', 365),
            rate_limit_per_hour=key_data.get('rate_limit_per_hour', 1000),
            allowed_ips=allowed_ips,
            metadata=key_data.get('metadata', {})
        )
        
        # 记录安全审计日志
        SecurityAuditLog.create(
            event_type="API_KEY_CREATED",
            severity="INFO",
            description=f"创建API密钥: {key_data['name']} (客户端: {key_data['client_id']})",
            user_id=current_user.get("user_id", "unknown"),
            username=current_user.get("username", "unknown"),
            ip_address=security_check["client_info"]["ip_address"],
            user_agent=security_check["client_info"]["user_agent"],
            request_data={
                "name": key_data['name'],
                "client_id": key_data['client_id'],
                "scopes": [scope.value for scope in scopes]
            }
        )
        
        logger.info(f"创建API密钥成功: {key_data['name']} (客户端: {key_data['client_id']})")
        
        return StandardResponse(
            code=201,
            message="API密钥创建成功",
            data={
                "public_key": public_key,
                "secret_key": secret_key,
                "name": key_data['name'],
                "client_id": key_data['client_id'],
                "scopes": [scope.value for scope in scopes],
                "created_at": datetime.now().isoformat()
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"创建API密钥失败: {str(e)}")
        raise HTTPException(status_code=500, detail="创建API密钥失败")


@router.put("/api-keys/{key_id}", response_model=StandardResponse[Dict[str, Any]])
async def update_api_key(
    key_id: str = Path(..., description="API密钥ID"),
    current_user: Dict = Depends(require_admin_auth),
    security_check: Dict = Depends(require_high_security),
    key_data: Dict[str, Any] = Depends(sanitize_json_body(allow_html=False)),
    cache_service = Depends(get_cache_service_dependency)
):
    """更新API密钥配置"""
    try:
        api_key_manager = ApiKeyManager(cache_service)
        
        # 获取现有密钥信息
        key_info = await api_key_manager.get_api_key_info(key_id)
        if not key_info:
            raise HTTPException(status_code=404, detail="API密钥不存在")
        
        # 记录修改前的值
        old_values = {
            "name": key_info.name,
            "description": key_info.description,
            "rate_limit_per_hour": key_info.rate_limit_per_hour,
            "allowed_ips": key_info.allowed_ips,
            "status": key_info.status.value
        }
        
        # 更新密钥信息
        update_data = {}
        if 'name' in key_data:
            update_data['name'] = key_data['name']
        if 'description' in key_data:
            update_data['description'] = key_data['description']
        if 'rate_limit_per_hour' in key_data:
            update_data['rate_limit_per_hour'] = key_data['rate_limit_per_hour']
        if 'allowed_ips' in key_data:
            # 验证IP地址
            try:
                for ip in key_data['allowed_ips']:
                    ipaddress.ip_address(ip)
                update_data['allowed_ips'] = key_data['allowed_ips']
            except ValueError:
                raise HTTPException(status_code=400, detail="无效的IP地址格式")
        if 'metadata' in key_data:
            update_data['metadata'] = key_data['metadata']
        
        success = await api_key_manager.update_api_key(key_id, **update_data)
        if not success:
            raise HTTPException(status_code=500, detail="更新API密钥失败")
        
        # 记录审计日志
        ConfigAuditLog.create(
            table_name_field="api_keys",
            record_id=key_id,
            action="UPDATE",
            old_values=old_values,
            new_values=update_data,
            operator_id=current_user.get("user_id", "unknown"),
            operator_name=current_user.get("username", "unknown"),
            ip_address=security_check["client_info"]["ip_address"]
        )
        
        logger.info(f"更新API密钥成功: {key_id}")
        
        return StandardResponse(
            code=200,
            message="API密钥更新成功",
            data={
                "key_id": key_id,
                "updated_fields": list(update_data.keys()),
                "updated_at": datetime.now().isoformat()
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"更新API密钥失败: {str(e)}")
        raise HTTPException(status_code=500, detail="更新API密钥失败")


@router.delete("/api-keys/{key_id}", response_model=StandardResponse[Dict[str, Any]])
async def revoke_api_key(
    key_id: str = Path(..., description="API密钥ID"),
    current_user: Dict = Depends(require_admin_auth),
    security_check: Dict = Depends(require_high_security),
    revoke_data: Dict[str, Any] = Depends(sanitize_json_body(allow_html=False)),
    cache_service = Depends(get_cache_service_dependency)
):
    """撤销API密钥"""
    try:
        api_key_manager = ApiKeyManager(cache_service)
        
        # 获取密钥信息
        key_info = await api_key_manager.get_api_key_info(key_id)
        if not key_info:
            raise HTTPException(status_code=404, detail="API密钥不存在")
        
        reason = revoke_data.get('reason', '管理员撤销')
        
        # 撤销密钥
        success = await api_key_manager.revoke_api_key(key_id, reason)
        if not success:
            raise HTTPException(status_code=500, detail="撤销API密钥失败")
        
        # 记录安全审计日志
        SecurityAuditLog.create(
            event_type="API_KEY_REVOKED",
            severity="WARNING",
            description=f"撤销API密钥: {key_info.name} (原因: {reason})",
            user_id=current_user.get("user_id", "unknown"),
            username=current_user.get("username", "unknown"),
            ip_address=security_check["client_info"]["ip_address"],
            user_agent=security_check["client_info"]["user_agent"],
            request_data={
                "key_id": key_id,
                "key_name": key_info.name,
                "reason": reason
            }
        )
        
        logger.warning(f"撤销API密钥: {key_id} (原因: {reason})")
        
        return StandardResponse(
            code=200,
            message="API密钥撤销成功",
            data={
                "key_id": key_id,
                "key_name": key_info.name,
                "reason": reason,
                "revoked_at": datetime.now().isoformat()
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"撤销API密钥失败: {str(e)}")
        raise HTTPException(status_code=500, detail="撤销API密钥失败")


@router.get("/threat-detection/rules", response_model=StandardResponse[List[Dict[str, Any]]])
async def list_threat_detection_rules(
    current_user: Dict = Depends(require_admin_auth),
    security_check: Dict = Depends(require_high_security),
    category: Optional[str] = Query(None, description="威胁类别过滤"),
    enabled: Optional[bool] = Query(None, description="启用状态过滤"),
    cache_service = Depends(get_cache_service_dependency)
):
    """获取威胁检测规则列表"""
    try:
        threat_detector = ThreatDetector(cache_service)
        await threat_detector.initialize()
        
        # 获取威胁检测规则
        rules = await threat_detector.get_detection_rules(
            category=ThreatCategory(category) if category else None,
            enabled=enabled
        )
        
        rule_list = []
        for rule in rules:
            rule_data = {
                "rule_id": rule.rule_id,
                "name": rule.name,
                "description": rule.description,
                "category": rule.category.value,
                "severity": rule.severity.value,
                "enabled": rule.enabled,
                "conditions": rule.conditions,
                "actions": rule.actions,
                "threshold": rule.threshold,
                "time_window_seconds": rule.time_window_seconds,
                "created_at": rule.created_at.isoformat(),
                "updated_at": rule.updated_at.isoformat(),
                "trigger_count": rule.trigger_count,
                "last_triggered": rule.last_triggered.isoformat() if rule.last_triggered else None
            }
            rule_list.append(rule_data)
        
        return StandardResponse(
            code=200,
            message="威胁检测规则列表获取成功",
            data=rule_list
        )
        
    except Exception as e:
        logger.error(f"获取威胁检测规则失败: {str(e)}")
        raise HTTPException(status_code=500, detail="获取威胁检测规则失败")


@router.post("/threat-detection/rules", response_model=StandardResponse[Dict[str, Any]])
async def create_threat_detection_rule(
    current_user: Dict = Depends(require_admin_auth),
    security_check: Dict = Depends(require_high_security),
    rule_data: Dict[str, Any] = Depends(sanitize_json_body(allow_html=False)),
    cache_service = Depends(get_cache_service_dependency)
):
    """创建威胁检测规则"""
    try:
        # 验证必需字段
        required_fields = ['name', 'category', 'severity', 'conditions']
        for field in required_fields:
            if field not in rule_data:
                raise HTTPException(status_code=400, detail=f"缺少必需字段: {field}")
        
        # 验证枚举值
        try:
            category = ThreatCategory(rule_data['category'])
            severity = ThreatSeverity(rule_data['severity'])
        except ValueError as e:
            raise HTTPException(status_code=400, detail=f"无效的枚举值: {str(e)}")
        
        threat_detector = ThreatDetector(cache_service)
        await threat_detector.initialize()
        
        # 创建威胁检测规则
        rule_id = await threat_detector.create_detection_rule(
            name=rule_data['name'],
            description=rule_data.get('description', ''),
            category=category,
            severity=severity,
            conditions=rule_data['conditions'],
            actions=rule_data.get('actions', ['log']),
            threshold=rule_data.get('threshold', 1),
            time_window_seconds=rule_data.get('time_window_seconds', 3600),
            enabled=rule_data.get('enabled', True)
        )
        
        # 记录安全审计日志
        SecurityAuditLog.create(
            event_type="THREAT_RULE_CREATED",
            severity="INFO",
            description=f"创建威胁检测规则: {rule_data['name']}",
            user_id=current_user.get("user_id", "unknown"),
            username=current_user.get("username", "unknown"),
            ip_address=security_check["client_info"]["ip_address"],
            user_agent=security_check["client_info"]["user_agent"],
            request_data={
                "rule_name": rule_data['name'],
                "category": category.value,
                "severity": severity.value
            }
        )
        
        logger.info(f"创建威胁检测规则成功: {rule_data['name']}")
        
        return StandardResponse(
            code=201,
            message="威胁检测规则创建成功",
            data={
                "rule_id": rule_id,
                "name": rule_data['name'],
                "category": category.value,
                "severity": severity.value,
                "created_at": datetime.now().isoformat()
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"创建威胁检测规则失败: {str(e)}")
        raise HTTPException(status_code=500, detail="创建威胁检测规则失败")


@router.get("/access-control/policies", response_model=StandardResponse[List[Dict[str, Any]]])
async def list_access_control_policies(
    current_user: Dict = Depends(require_admin_auth),
    security_check: Dict = Depends(require_high_security),
    policy_type: Optional[str] = Query(None, description="策略类型过滤"),
    enabled: Optional[bool] = Query(None, description="启用状态过滤")
):
    """获取访问控制策略列表"""
    try:
        # 这里应该从数据库或配置文件中获取访问控制策略
        # 为演示目的，返回模拟数据
        policies = [
            {
                "policy_id": "policy_001",
                "name": "IP白名单策略",
                "description": "允许特定IP地址访问",
                "policy_type": "ip_whitelist",
                "enabled": True,
                "conditions": {
                    "allowed_ips": ["192.168.1.0/24", "10.0.0.0/16"],
                    "endpoints": ["/api/v1/*"]
                },
                "actions": ["allow"],
                "priority": 100,
                "created_at": "2024-01-01T00:00:00Z",
                "updated_at": "2024-01-15T12:00:00Z"
            },
            {
                "policy_id": "policy_002",
                "name": "速率限制策略",
                "description": "限制API调用频率",
                "policy_type": "rate_limit",
                "enabled": True,
                "conditions": {
                    "requests_per_hour": 1000,
                    "requests_per_minute": 60,
                    "endpoints": ["/api/v1/chat"]
                },
                "actions": ["throttle", "log"],
                "priority": 200,
                "created_at": "2024-01-01T00:00:00Z",
                "updated_at": "2024-01-20T08:30:00Z"
            }
        ]
        
        # 应用过滤条件
        if policy_type:
            policies = [p for p in policies if p["policy_type"] == policy_type]
        if enabled is not None:
            policies = [p for p in policies if p["enabled"] == enabled]
        
        return StandardResponse(
            code=200,
            message="访问控制策略列表获取成功",
            data=policies
        )
        
    except Exception as e:
        logger.error(f"获取访问控制策略失败: {str(e)}")
        raise HTTPException(status_code=500, detail="获取访问控制策略失败")


@router.get("/audit/events", response_model=StandardResponse[List[Dict[str, Any]]])
async def list_security_audit_events(
    current_user: Dict = Depends(require_admin_auth),
    security_check: Dict = Depends(require_high_security),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    event_type: Optional[str] = Query(None, description="事件类型过滤"),
    severity: Optional[str] = Query(None, description="严重程度过滤"),
    start_time: Optional[str] = Query(None, description="开始时间 (ISO格式)"),
    end_time: Optional[str] = Query(None, description="结束时间 (ISO格式)")
):
    """获取安全审计事件列表"""
    try:
        # 构建查询条件
        query = SecurityAuditLog.select()
        
        if event_type:
            query = query.where(SecurityAuditLog.event_type == event_type)
        
        if severity:
            query = query.where(SecurityAuditLog.severity == severity)
        
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
        events = query.offset(offset).limit(page_size).order_by(SecurityAuditLog.created_at.desc())
        
        # 构建响应数据
        event_list = []
        for event in events:
            event_data = {
                "id": event.id,
                "event_type": event.event_type,
                "severity": event.severity,
                "description": event.description,
                "user_id": event.user_id,
                "username": event.username,
                "ip_address": event.ip_address,
                "user_agent": event.user_agent,
                "request_data": event.get_request_data(),
                "response_data": event.get_response_data(),
                "created_at": event.created_at.isoformat()
            }
            event_list.append(event_data)
        
        response_data = {
            "items": event_list,
            "pagination": {
                "page": page,
                "page_size": page_size,
                "total": total,
                "pages": (total + page_size - 1) // page_size
            }
        }
        
        return StandardResponse(
            code=200,
            message="安全审计事件列表获取成功",
            data=response_data
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取安全审计事件失败: {str(e)}")
        raise HTTPException(status_code=500, detail="获取安全审计事件失败")


@router.get("/summary", response_model=StandardResponse[Dict[str, Any]])
async def get_security_summary(
    current_user: Dict = Depends(require_admin_auth),
    security_check: Dict = Depends(require_high_security),
    hours: int = Query(24, ge=1, le=168, description="统计时间范围（小时）"),
    cache_service = Depends(get_cache_service_dependency)
):
    """获取安全状态摘要"""
    try:
        # 计算时间范围
        start_time = datetime.now() - timedelta(hours=hours)
        
        # API密钥统计
        api_key_manager = ApiKeyManager(cache_service)
        active_keys = await api_key_manager.count_api_keys(status=ApiKeyStatus.ACTIVE)
        
        # 威胁检测统计
        threat_detector = ThreatDetector(cache_service)
        await threat_detector.initialize()
        threat_summary = await threat_detector.get_threat_summary(hours=hours)
        
        # 安全事件统计
        security_events = SecurityAuditLog.select().where(
            SecurityAuditLog.created_at >= start_time
        )
        
        event_stats = {
            "total_events": security_events.count(),
            "critical_events": security_events.where(SecurityAuditLog.severity == "CRITICAL").count(),
            "warning_events": security_events.where(SecurityAuditLog.severity == "WARNING").count(),
            "info_events": security_events.where(SecurityAuditLog.severity == "INFO").count()
        }
        
        # 按事件类型统计
        event_types = {}
        for event in security_events:
            event_types[event.event_type] = event_types.get(event.event_type, 0) + 1
        
        # 安全状态评分
        security_score = 100
        if threat_summary.get('total_threats', 0) > 10:
            security_score -= 20
        if event_stats['critical_events'] > 0:
            security_score -= 30
        if event_stats['warning_events'] > 5:
            security_score -= 15
        
        security_level = "高"
        if security_score < 60:
            security_level = "低"
        elif security_score < 80:
            security_level = "中"
        
        summary = {
            "security_score": max(0, security_score),
            "security_level": security_level,
            "time_range_hours": hours,
            "api_keys": {
                "active_count": active_keys,
                "total_requests": threat_summary.get("total_requests", 0)
            },
            "threats": {
                "total_threats": threat_summary.get("total_threats", 0),
                "blocked_attacks": threat_summary.get("blocked_attacks", 0),
                "suspicious_ips": threat_summary.get("blocked_ips", 0),
                "threats_by_category": threat_summary.get("threats_by_category", {})
            },
            "security_events": event_stats,
            "event_types": dict(sorted(event_types.items(), key=lambda x: x[1], reverse=True)[:10]),
            "recommendations": self._generate_security_recommendations(
                security_score, threat_summary, event_stats
            ),
            "generated_at": datetime.now().isoformat()
        }
        
        return StandardResponse(
            code=200,
            message="安全状态摘要获取成功",
            data=summary
        )
        
    except Exception as e:
        logger.error(f"获取安全状态摘要失败: {str(e)}")
        raise HTTPException(status_code=500, detail="获取安全状态摘要失败")


def _generate_security_recommendations(security_score: int, threat_summary: Dict, event_stats: Dict) -> List[str]:
    """生成安全建议"""
    recommendations = []
    
    if security_score < 60:
        recommendations.append("安全风险较高，建议立即审查安全策略并加强防护措施")
    
    if threat_summary.get("total_threats", 0) > 20:
        recommendations.append("检测到大量威胁，建议启用更严格的访问控制规则")
    
    if event_stats.get("critical_events", 0) > 0:
        recommendations.append("存在严重安全事件，建议立即调查并采取应对措施")
    
    if threat_summary.get("blocked_ips", 0) > 10:
        recommendations.append("有多个可疑IP被阻止，建议审查IP黑名单策略")
    
    brute_force_threats = threat_summary.get("threats_by_category", {}).get("BRUTE_FORCE", 0)
    if brute_force_threats > 5:
        recommendations.append("检测到暴力破解攻击，建议启用账户锁定机制")
    
    if len(recommendations) == 0:
        recommendations.append("当前安全状态良好，建议保持现有安全策略")
    
    return recommendations