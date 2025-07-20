"""
配置验证和导入导出API (TASK-038)
提供配置验证、批量导入导出、备份恢复等高级配置管理功能
"""
from fastapi import APIRouter, Depends, HTTPException, Query, Path, UploadFile, File
from typing import Dict, List, Any, Optional
from datetime import datetime
import json
import yaml
import io
import zipfile
import base64

from src.api.dependencies import require_admin_auth, get_cache_service_dependency
from src.schemas.common import StandardResponse
from src.models.audit import ConfigAuditLog
from src.models.intent import Intent
from src.models.slot import Slot
from src.models.template import Template
from src.models.function import Function
from src.security.dependencies import require_high_security, sanitize_json_body
from src.utils.logger import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/admin/config", tags=["配置验证与导入导出"])


@router.post("/validate", response_model=StandardResponse[Dict[str, Any]])
async def validate_configuration(
    current_user: Dict = Depends(require_admin_auth),
    security_check: Dict = Depends(require_high_security),
    config_data: Dict[str, Any] = Depends(sanitize_json_body(allow_html=False))
):
    """验证配置数据的完整性和正确性"""
    try:
        validation_results = {
            "is_valid": True,
            "errors": [],
            "warnings": [],
            "suggestions": [],
            "validated_sections": []
        }
        
        # 验证意图配置
        if "intents" in config_data:
            intent_validation = _validate_intents(config_data["intents"])
            validation_results["validated_sections"].append("intents")
            if not intent_validation["is_valid"]:
                validation_results["is_valid"] = False
                validation_results["errors"].extend(intent_validation["errors"])
            validation_results["warnings"].extend(intent_validation["warnings"])
            validation_results["suggestions"].extend(intent_validation["suggestions"])
        
        # 验证槽位配置
        if "slots" in config_data:
            slot_validation = _validate_slots(config_data["slots"])
            validation_results["validated_sections"].append("slots")
            if not slot_validation["is_valid"]:
                validation_results["is_valid"] = False
                validation_results["errors"].extend(slot_validation["errors"])
            validation_results["warnings"].extend(slot_validation["warnings"])
            validation_results["suggestions"].extend(slot_validation["suggestions"])
        
        # 验证模板配置
        if "templates" in config_data:
            template_validation = _validate_templates(config_data["templates"])
            validation_results["validated_sections"].append("templates")
            if not template_validation["is_valid"]:
                validation_results["is_valid"] = False
                validation_results["errors"].extend(template_validation["errors"])
            validation_results["warnings"].extend(template_validation["warnings"])
            validation_results["suggestions"].extend(template_validation["suggestions"])
        
        # 验证函数配置
        if "functions" in config_data:
            function_validation = _validate_functions(config_data["functions"])
            validation_results["validated_sections"].append("functions")
            if not function_validation["is_valid"]:
                validation_results["is_valid"] = False
                validation_results["errors"].extend(function_validation["errors"])
            validation_results["warnings"].extend(function_validation["warnings"])
            validation_results["suggestions"].extend(function_validation["suggestions"])
        
        # 验证系统配置
        if "system_config" in config_data:
            system_validation = _validate_system_config(config_data["system_config"])
            validation_results["validated_sections"].append("system_config")
            if not system_validation["is_valid"]:
                validation_results["is_valid"] = False
                validation_results["errors"].extend(system_validation["errors"])
            validation_results["warnings"].extend(system_validation["warnings"])
            validation_results["suggestions"].extend(system_validation["suggestions"])
        
        # 交叉验证
        cross_validation = _perform_cross_validation(config_data)
        if not cross_validation["is_valid"]:
            validation_results["is_valid"] = False
            validation_results["errors"].extend(cross_validation["errors"])
        validation_results["warnings"].extend(cross_validation["warnings"])
        
        # 记录验证操作
        ConfigAuditLog.create(
            table_name_field="config_validation",
            record_id="validation",
            action="VALIDATE",
            old_values={},
            new_values={
                "sections_validated": validation_results["validated_sections"],
                "is_valid": validation_results["is_valid"],
                "error_count": len(validation_results["errors"]),
                "warning_count": len(validation_results["warnings"])
            },
            operator_id=current_user.get("user_id", "unknown"),
            operator_name=current_user.get("username", "unknown"),
            ip_address=security_check["client_info"]["ip_address"]
        )
        
        logger.info(f"配置验证完成: 有效={validation_results['is_valid']}, 错误={len(validation_results['errors'])}, 警告={len(validation_results['warnings'])}")
        
        return StandardResponse(
            code=200,
            message="配置验证完成",
            data=validation_results
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"配置验证失败: {str(e)}")
        raise HTTPException(status_code=500, detail="配置验证失败")


@router.post("/import", response_model=StandardResponse[Dict[str, Any]])
async def import_configuration(
    file: UploadFile = File(..., description="配置文件 (JSON/YAML/ZIP)"),
    current_user: Dict = Depends(require_admin_auth),
    security_check: Dict = Depends(require_high_security),
    overwrite: bool = Query(False, description="是否覆盖已存在的配置"),
    validate_only: bool = Query(False, description="仅验证不导入")
):
    """导入配置文件"""
    try:
        # 检查文件大小
        if file.size > 10 * 1024 * 1024:  # 10MB限制
            raise HTTPException(status_code=400, detail="文件大小超过限制 (10MB)")
        
        # 读取文件内容
        content = await file.read()
        
        # 解析配置数据
        config_data = None
        if file.filename.endswith('.json'):
            config_data = json.loads(content.decode('utf-8'))
        elif file.filename.endswith(('.yml', '.yaml')):
            config_data = yaml.safe_load(content.decode('utf-8'))
        elif file.filename.endswith('.zip'):
            config_data = _extract_zip_config(content)
        else:
            raise HTTPException(status_code=400, detail="不支持的文件格式，支持 JSON、YAML、ZIP")
        
        # 验证配置
        validation_result = await validate_configuration.__wrapped__(
            current_user=current_user,
            security_check=security_check,
            config_data=config_data
        )
        
        if not validation_result.data["is_valid"]:
            return StandardResponse(
                code=400,
                message="配置验证失败，无法导入",
                data={
                    "validation_errors": validation_result.data["errors"],
                    "validation_warnings": validation_result.data["warnings"]
                }
            )
        
        # 如果只是验证，返回验证结果
        if validate_only:
            return StandardResponse(
                code=200,
                message="配置验证通过",
                data=validation_result.data
            )
        
        # 执行导入
        import_results = {
            "imported_sections": [],
            "skipped_items": [],
            "created_count": 0,
            "updated_count": 0,
            "skipped_count": 0
        }
        
        # 导入意图
        if "intents" in config_data:
            intent_result = _import_intents(config_data["intents"], overwrite)
            import_results["imported_sections"].append("intents")
            import_results["created_count"] += intent_result["created"]
            import_results["updated_count"] += intent_result["updated"]
            import_results["skipped_count"] += intent_result["skipped"]
            import_results["skipped_items"].extend(intent_result["skipped_items"])
        
        # 导入槽位
        if "slots" in config_data:
            slot_result = _import_slots(config_data["slots"], overwrite)
            import_results["imported_sections"].append("slots")
            import_results["created_count"] += slot_result["created"]
            import_results["updated_count"] += slot_result["updated"]
            import_results["skipped_count"] += slot_result["skipped"]
            import_results["skipped_items"].extend(slot_result["skipped_items"])
        
        # 导入模板
        if "templates" in config_data:
            template_result = _import_templates(config_data["templates"], overwrite)
            import_results["imported_sections"].append("templates")
            import_results["created_count"] += template_result["created"]
            import_results["updated_count"] += template_result["updated"]
            import_results["skipped_count"] += template_result["skipped"]
            import_results["skipped_items"].extend(template_result["skipped_items"])
        
        # 导入函数
        if "functions" in config_data:
            function_result = _import_functions(config_data["functions"], overwrite)
            import_results["imported_sections"].append("functions")
            import_results["created_count"] += function_result["created"]
            import_results["updated_count"] += function_result["updated"]
            import_results["skipped_count"] += function_result["skipped"]
            import_results["skipped_items"].extend(function_result["skipped_items"])
        
        # 记录导入操作
        ConfigAuditLog.create(
            table_name_field="config_import",
            record_id="import",
            action="IMPORT",
            old_values={},
            new_values={
                "file_name": file.filename,
                "file_size": file.size,
                "imported_sections": import_results["imported_sections"],
                "created_count": import_results["created_count"],
                "updated_count": import_results["updated_count"],
                "overwrite": overwrite
            },
            operator_id=current_user.get("user_id", "unknown"),
            operator_name=current_user.get("username", "unknown"),
            ip_address=security_check["client_info"]["ip_address"]
        )
        
        logger.info(f"配置导入完成: 创建={import_results['created_count']}, 更新={import_results['updated_count']}, 跳过={import_results['skipped_count']}")
        
        return StandardResponse(
            code=200,
            message="配置导入成功",
            data={
                **import_results,
                "import_time": datetime.now().isoformat()
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"配置导入失败: {str(e)}")
        raise HTTPException(status_code=500, detail="配置导入失败")


@router.get("/export", response_model=StandardResponse[Dict[str, Any]])
async def export_configuration(
    current_user: Dict = Depends(require_admin_auth),
    security_check: Dict = Depends(require_high_security),
    sections: List[str] = Query(["all"], description="导出的配置部分"),
    format: str = Query("json", description="导出格式 (json/yaml/zip)"),
    include_metadata: bool = Query(True, description="是否包含元数据"),
    filter_active_only: bool = Query(False, description="仅导出激活的配置")
):
    """导出系统配置"""
    try:
        if format not in ["json", "yaml", "zip"]:
            raise HTTPException(status_code=400, detail="不支持的导出格式")
        
        export_data = {}
        export_stats = {
            "exported_sections": [],
            "total_items": 0
        }
        
        # 导出意图
        if "all" in sections or "intents" in sections:
            intents_data = _export_intents(include_metadata, filter_active_only)
            export_data["intents"] = intents_data
            export_stats["exported_sections"].append("intents")
            export_stats["total_items"] += len(intents_data)
        
        # 导出槽位
        if "all" in sections or "slots" in sections:
            slots_data = _export_slots(include_metadata, filter_active_only)
            export_data["slots"] = slots_data
            export_stats["exported_sections"].append("slots")
            export_stats["total_items"] += len(slots_data)
        
        # 导出模板
        if "all" in sections or "templates" in sections:
            templates_data = _export_templates(include_metadata, filter_active_only)
            export_data["templates"] = templates_data
            export_stats["exported_sections"].append("templates")
            export_stats["total_items"] += len(templates_data)
        
        # 导出函数
        if "all" in sections or "functions" in sections:
            functions_data = _export_functions(include_metadata, filter_active_only)
            export_data["functions"] = functions_data
            export_stats["exported_sections"].append("functions")
            export_stats["total_items"] += len(functions_data)
        
        # 添加导出元数据
        if include_metadata:
            export_data["_metadata"] = {
                "export_time": datetime.now().isoformat(),
                "exported_by": current_user.get("username", "unknown"),
                "export_version": "1.0",
                "sections": export_stats["exported_sections"],
                "total_items": export_stats["total_items"]
            }
        
        # 根据格式生成导出内容
        if format == "json":
            export_content = json.dumps(export_data, ensure_ascii=False, indent=2)
            content_type = "application/json"
            filename = f"config_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        elif format == "yaml":
            export_content = yaml.dump(export_data, allow_unicode=True, default_flow_style=False)
            content_type = "application/x-yaml"
            filename = f"config_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.yaml"
        else:  # zip
            zip_content = _create_zip_export(export_data)
            export_content = base64.b64encode(zip_content).decode('utf-8')
            content_type = "application/zip"
            filename = f"config_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip"
        
        # 记录导出操作
        ConfigAuditLog.create(
            table_name_field="config_export",
            record_id="export",
            action="EXPORT",
            old_values={},
            new_values={
                "sections": export_stats["exported_sections"],
                "format": format,
                "total_items": export_stats["total_items"],
                "include_metadata": include_metadata
            },
            operator_id=current_user.get("user_id", "unknown"),
            operator_name=current_user.get("username", "unknown"),
            ip_address=security_check["client_info"]["ip_address"]
        )
        
        logger.info(f"配置导出完成: 格式={format}, 项目数={export_stats['total_items']}")
        
        return StandardResponse(
            code=200,
            message="配置导出成功",
            data={
                "filename": filename,
                "content_type": content_type,
                "content": export_content,
                "size_bytes": len(export_content.encode('utf-8')),
                "export_stats": export_stats,
                "export_time": datetime.now().isoformat()
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"配置导出失败: {str(e)}")
        raise HTTPException(status_code=500, detail="配置导出失败")


@router.post("/backup", response_model=StandardResponse[Dict[str, Any]])
async def create_configuration_backup(
    current_user: Dict = Depends(require_admin_auth),
    security_check: Dict = Depends(require_high_security),
    backup_data: Dict[str, Any] = Depends(sanitize_json_body(allow_html=False))
):
    """创建配置备份"""
    try:
        backup_name = backup_data.get("name", f"backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
        description = backup_data.get("description", "")
        include_sections = backup_data.get("sections", ["all"])
        
        # 生成备份ID
        import uuid
        backup_id = f"backup_{uuid.uuid4().hex[:8]}"
        
        # 创建完整的配置备份
        backup_content = {}
        backup_stats = {"total_items": 0, "sections": []}
        
        # 备份所有配置数据
        for section in ["intents", "slots", "templates", "functions"]:
            if "all" in include_sections or section in include_sections:
                if section == "intents":
                    data = _export_intents(include_metadata=True, filter_active_only=False)
                elif section == "slots":
                    data = _export_slots(include_metadata=True, filter_active_only=False)
                elif section == "templates":
                    data = _export_templates(include_metadata=True, filter_active_only=False)
                elif section == "functions":
                    data = _export_functions(include_metadata=True, filter_active_only=False)
                
                backup_content[section] = data
                backup_stats["sections"].append(section)
                backup_stats["total_items"] += len(data)
        
        # 添加备份元数据
        backup_metadata = {
            "backup_id": backup_id,
            "name": backup_name,
            "description": description,
            "created_by": current_user.get("username", "unknown"),
            "created_at": datetime.now().isoformat(),
            "sections": backup_stats["sections"],
            "total_items": backup_stats["total_items"],
            "version": "1.0"
        }
        
        backup_content["_backup_metadata"] = backup_metadata
        
        # 压缩备份内容
        compressed_backup = _create_zip_export(backup_content)
        backup_size = len(compressed_backup)
        
        # 这里应该将备份存储到文件系统或云存储
        # 为演示目的，我们记录备份信息
        backup_info = {
            "backup_id": backup_id,
            "name": backup_name,
            "description": description,
            "size_bytes": backup_size,
            "sections": backup_stats["sections"],
            "total_items": backup_stats["total_items"],
            "created_by": current_user.get("username", "unknown"),
            "created_at": datetime.now().isoformat(),
            "storage_path": f"/backups/{backup_id}.zip",
            "retention_days": backup_data.get("retention_days", 90)
        }
        
        # 记录备份操作
        ConfigAuditLog.create(
            table_name_field="config_backup",
            record_id=backup_id,
            action="BACKUP",
            old_values={},
            new_values={
                "backup_name": backup_name,
                "sections": backup_stats["sections"],
                "total_items": backup_stats["total_items"],
                "size_bytes": backup_size
            },
            operator_id=current_user.get("user_id", "unknown"),
            operator_name=current_user.get("username", "unknown"),
            ip_address=security_check["client_info"]["ip_address"]
        )
        
        logger.info(f"配置备份创建成功: {backup_id} ({backup_size} bytes)")
        
        return StandardResponse(
            code=201,
            message="配置备份创建成功",
            data=backup_info
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"创建配置备份失败: {str(e)}")
        raise HTTPException(status_code=500, detail="创建配置备份失败")


@router.get("/backups", response_model=StandardResponse[List[Dict[str, Any]]])
async def list_configuration_backups(
    current_user: Dict = Depends(require_admin_auth),
    security_check: Dict = Depends(require_high_security),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100)
):
    """获取配置备份列表"""
    try:
        # 模拟备份列表（实际应从存储系统获取）
        mock_backups = [
            {
                "backup_id": "backup_12345678",
                "name": "backup_20240101_120000",
                "description": "定期备份",
                "size_bytes": 1024000,
                "sections": ["intents", "slots", "templates", "functions"],
                "total_items": 150,
                "created_by": "admin",
                "created_at": "2024-01-01T12:00:00Z",
                "retention_days": 90,
                "status": "completed"
            },
            {
                "backup_id": "backup_87654321",
                "name": "pre_update_backup",
                "description": "更新前备份",
                "size_bytes": 956000,
                "sections": ["intents", "slots"],
                "total_items": 85,
                "created_by": "admin",
                "created_at": "2023-12-28T15:30:00Z",
                "retention_days": 90,
                "status": "completed"
            }
        ]
        
        # 分页处理
        total = len(mock_backups)
        start_idx = (page - 1) * page_size
        end_idx = start_idx + page_size
        backups = mock_backups[start_idx:end_idx]
        
        response_data = {
            "items": backups,
            "pagination": {
                "page": page,
                "page_size": page_size,
                "total": total,
                "pages": (total + page_size - 1) // page_size
            }
        }
        
        return StandardResponse(
            code=200,
            message="配置备份列表获取成功",
            data=response_data
        )
        
    except Exception as e:
        logger.error(f"获取配置备份列表失败: {str(e)}")
        raise HTTPException(status_code=500, detail="获取配置备份列表失败")


# 验证函数
def _validate_intents(intents_data: List[Dict]) -> Dict[str, Any]:
    """验证意图配置"""
    result = {"is_valid": True, "errors": [], "warnings": [], "suggestions": []}
    
    intent_names = set()
    for i, intent in enumerate(intents_data):
        # 检查必需字段
        if "intent_name" not in intent:
            result["errors"].append(f"意图 #{i+1}: 缺少 intent_name 字段")
            result["is_valid"] = False
        elif intent["intent_name"] in intent_names:
            result["errors"].append(f"意图名称重复: {intent['intent_name']}")
            result["is_valid"] = False
        else:
            intent_names.add(intent["intent_name"])
        
        if "patterns" not in intent or not intent["patterns"]:
            result["warnings"].append(f"意图 {intent.get('intent_name', f'#{i+1}')}: 没有定义训练样本")
        
        # 检查槽位引用
        if "slots" in intent:
            for slot in intent["slots"]:
                if "slot_name" not in slot:
                    result["errors"].append(f"意图 {intent.get('intent_name', f'#{i+1}')}: 槽位定义缺少 slot_name")
                    result["is_valid"] = False
    
    return result


def _validate_slots(slots_data: List[Dict]) -> Dict[str, Any]:
    """验证槽位配置"""
    result = {"is_valid": True, "errors": [], "warnings": [], "suggestions": []}
    
    slot_names = set()
    for i, slot in enumerate(slots_data):
        if "slot_name" not in slot:
            result["errors"].append(f"槽位 #{i+1}: 缺少 slot_name 字段")
            result["is_valid"] = False
        elif slot["slot_name"] in slot_names:
            result["errors"].append(f"槽位名称重复: {slot['slot_name']}")
            result["is_valid"] = False
        else:
            slot_names.add(slot["slot_name"])
        
        if "slot_type" not in slot:
            result["errors"].append(f"槽位 {slot.get('slot_name', f'#{i+1}')}: 缺少 slot_type 字段")
            result["is_valid"] = False
    
    return result


def _validate_templates(templates_data: List[Dict]) -> Dict[str, Any]:
    """验证模板配置"""
    result = {"is_valid": True, "errors": [], "warnings": [], "suggestions": []}
    
    template_names = set()
    for i, template in enumerate(templates_data):
        if "template_name" not in template:
            result["errors"].append(f"模板 #{i+1}: 缺少 template_name 字段")
            result["is_valid"] = False
        elif template["template_name"] in template_names:
            result["errors"].append(f"模板名称重复: {template['template_name']}")
            result["is_valid"] = False
        else:
            template_names.add(template["template_name"])
        
        if "content" not in template or not template["content"]:
            result["errors"].append(f"模板 {template.get('template_name', f'#{i+1}')}: 缺少 content 字段")
            result["is_valid"] = False
    
    return result


def _validate_functions(functions_data: List[Dict]) -> Dict[str, Any]:
    """验证函数配置"""
    result = {"is_valid": True, "errors": [], "warnings": [], "suggestions": []}
    
    function_names = set()
    for i, function in enumerate(functions_data):
        if "function_name" not in function:
            result["errors"].append(f"函数 #{i+1}: 缺少 function_name 字段")
            result["is_valid"] = False
        elif function["function_name"] in function_names:
            result["errors"].append(f"函数名称重复: {function['function_name']}")
            result["is_valid"] = False
        else:
            function_names.add(function["function_name"])
        
        if "implementation_code" not in function or not function["implementation_code"]:
            result["warnings"].append(f"函数 {function.get('function_name', f'#{i+1}')}: 没有实现代码")
    
    return result


def _validate_system_config(system_config: Dict) -> Dict[str, Any]:
    """验证系统配置"""
    result = {"is_valid": True, "errors": [], "warnings": [], "suggestions": []}
    
    # 验证必需的系统配置项
    required_configs = ["nlu_threshold", "max_conversation_turns"]
    for config_key in required_configs:
        if config_key not in system_config:
            result["warnings"].append(f"缺少系统配置项: {config_key}")
    
    return result


def _perform_cross_validation(config_data: Dict) -> Dict[str, Any]:
    """执行交叉验证"""
    result = {"is_valid": True, "errors": [], "warnings": []}
    
    # 检查意图和槽位的引用关系
    if "intents" in config_data and "slots" in config_data:
        slot_names = {slot["slot_name"] for slot in config_data["slots"] if "slot_name" in slot}
        
        for intent in config_data["intents"]:
            if "slots" in intent:
                for slot_ref in intent["slots"]:
                    if "slot_name" in slot_ref and slot_ref["slot_name"] not in slot_names:
                        result["errors"].append(f"意图 {intent.get('intent_name', 'unknown')} 引用了不存在的槽位: {slot_ref['slot_name']}")
                        result["is_valid"] = False
    
    return result


# 导入函数
def _import_intents(intents_data: List[Dict], overwrite: bool) -> Dict[str, int]:
    """导入意图配置"""
    result = {"created": 0, "updated": 0, "skipped": 0, "skipped_items": []}
    
    for intent_data in intents_data:
        intent_name = intent_data.get("intent_name")
        if not intent_name:
            continue
        
        try:
            existing_intent = Intent.get(Intent.intent_name == intent_name)
            if overwrite:
                # 更新现有意图
                for key, value in intent_data.items():
                    if hasattr(existing_intent, key):
                        setattr(existing_intent, key, value)
                existing_intent.save()
                result["updated"] += 1
            else:
                result["skipped"] += 1
                result["skipped_items"].append(f"intent:{intent_name}")
        except Intent.DoesNotExist:
            # 创建新意图
            Intent.create(**intent_data)
            result["created"] += 1
    
    return result


def _import_slots(slots_data: List[Dict], overwrite: bool) -> Dict[str, int]:
    """导入槽位配置"""
    result = {"created": 0, "updated": 0, "skipped": 0, "skipped_items": []}
    
    for slot_data in slots_data:
        slot_name = slot_data.get("slot_name")
        if not slot_name:
            continue
        
        try:
            existing_slot = Slot.get(Slot.slot_name == slot_name)
            if overwrite:
                for key, value in slot_data.items():
                    if hasattr(existing_slot, key):
                        setattr(existing_slot, key, value)
                existing_slot.save()
                result["updated"] += 1
            else:
                result["skipped"] += 1
                result["skipped_items"].append(f"slot:{slot_name}")
        except Slot.DoesNotExist:
            Slot.create(**slot_data)
            result["created"] += 1
    
    return result


def _import_templates(templates_data: List[Dict], overwrite: bool) -> Dict[str, int]:
    """导入模板配置"""
    result = {"created": 0, "updated": 0, "skipped": 0, "skipped_items": []}
    
    for template_data in templates_data:
        template_name = template_data.get("template_name")
        if not template_name:
            continue
        
        try:
            existing_template = Template.get(Template.template_name == template_name)
            if overwrite:
                for key, value in template_data.items():
                    if hasattr(existing_template, key):
                        setattr(existing_template, key, value)
                existing_template.save()
                result["updated"] += 1
            else:
                result["skipped"] += 1
                result["skipped_items"].append(f"template:{template_name}")
        except Template.DoesNotExist:
            Template.create(**template_data)
            result["created"] += 1
    
    return result


def _import_functions(functions_data: List[Dict], overwrite: bool) -> Dict[str, int]:
    """导入函数配置"""
    result = {"created": 0, "updated": 0, "skipped": 0, "skipped_items": []}
    
    for function_data in functions_data:
        function_name = function_data.get("function_name")
        if not function_name:
            continue
        
        try:
            existing_function = Function.get(Function.function_name == function_name)
            if overwrite:
                for key, value in function_data.items():
                    if hasattr(existing_function, key):
                        setattr(existing_function, key, value)
                existing_function.save()
                result["updated"] += 1
            else:
                result["skipped"] += 1
                result["skipped_items"].append(f"function:{function_name}")
        except Function.DoesNotExist:
            Function.create(**function_data)
            result["created"] += 1
    
    return result


# 导出函数
def _export_intents(include_metadata: bool, filter_active_only: bool) -> List[Dict]:
    """导出意图配置"""
    query = Intent.select()
    if filter_active_only:
        query = query.where(Intent.is_active == True)
    
    intents_data = []
    for intent in query:
        intent_data = {
            "intent_name": intent.intent_name,
            "display_name": intent.display_name,
            "description": intent.description,
            "patterns": intent.get_patterns(),
            "responses": intent.get_responses(),
            "slots": intent.get_slot_definitions(),
            "is_active": intent.is_active
        }
        
        if include_metadata:
            intent_data["_metadata"] = {
                "created_at": intent.created_at.isoformat(),
                "updated_at": intent.updated_at.isoformat()
            }
        
        intents_data.append(intent_data)
    
    return intents_data


def _export_slots(include_metadata: bool, filter_active_only: bool) -> List[Dict]:
    """导出槽位配置"""
    query = Slot.select()
    if filter_active_only:
        query = query.where(Slot.is_active == True)
    
    slots_data = []
    for slot in query:
        slot_data = {
            "slot_name": slot.slot_name,
            "slot_type": slot.slot_type,
            "description": slot.description,
            "values": slot.get_values(),
            "validation_rules": slot.get_validation_rules(),
            "is_required": slot.is_required,
            "is_active": slot.is_active
        }
        
        if include_metadata:
            slot_data["_metadata"] = {
                "created_at": slot.created_at.isoformat(),
                "updated_at": slot.updated_at.isoformat()
            }
        
        slots_data.append(slot_data)
    
    return slots_data


def _export_templates(include_metadata: bool, filter_active_only: bool) -> List[Dict]:
    """导出模板配置"""
    query = Template.select()
    if filter_active_only:
        query = query.where(Template.is_active == True)
    
    templates_data = []
    for template in query:
        template_data = {
            "template_name": template.template_name,
            "template_type": template.template_type,
            "content": template.content,
            "variables": template.get_variables(),
            "conditions": template.get_conditions(),
            "is_active": template.is_active
        }
        
        if include_metadata:
            template_data["_metadata"] = {
                "created_at": template.created_at.isoformat(),
                "updated_at": template.updated_at.isoformat()
            }
        
        templates_data.append(template_data)
    
    return templates_data


def _export_functions(include_metadata: bool, filter_active_only: bool) -> List[Dict]:
    """导出函数配置"""
    query = Function.select()
    if filter_active_only:
        query = query.where(Function.is_active == True)
    
    functions_data = []
    for function in query:
        function_data = {
            "function_name": function.function_name,
            "display_name": function.display_name,
            "description": function.description,
            "category": function.category,
            "implementation_code": function.implementation_code,
            "function_schema": function.get_function_schema(),
            "timeout_seconds": function.timeout_seconds,
            "max_retries": function.max_retries,
            "is_async": function.is_async,
            "is_active": function.is_active
        }
        
        if include_metadata:
            function_data["_metadata"] = {
                "created_at": function.created_at.isoformat(),
                "updated_at": function.updated_at.isoformat()
            }
        
        functions_data.append(function_data)
    
    return functions_data


def _extract_zip_config(zip_content: bytes) -> Dict:
    """从ZIP文件提取配置"""
    with zipfile.ZipFile(io.BytesIO(zip_content), 'r') as zip_file:
        config_data = {}
        
        for file_info in zip_file.infolist():
            if file_info.filename.endswith('.json'):
                content = zip_file.read(file_info.filename).decode('utf-8')
                data = json.loads(content)
                config_data.update(data)
            elif file_info.filename.endswith(('.yml', '.yaml')):
                content = zip_file.read(file_info.filename).decode('utf-8')
                data = yaml.safe_load(content)
                config_data.update(data)
        
        return config_data


def _create_zip_export(config_data: Dict) -> bytes:
    """创建ZIP格式导出"""
    zip_buffer = io.BytesIO()
    
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
        # 将每个配置部分写入单独的JSON文件
        for section_name, section_data in config_data.items():
            if not section_name.startswith('_'):
                json_content = json.dumps(section_data, ensure_ascii=False, indent=2)
                zip_file.writestr(f"{section_name}.json", json_content)
        
        # 添加元数据文件
        if '_metadata' in config_data or '_backup_metadata' in config_data:
            metadata = config_data.get('_metadata') or config_data.get('_backup_metadata')
            metadata_content = json.dumps(metadata, ensure_ascii=False, indent=2)
            zip_file.writestr("metadata.json", metadata_content)
    
    return zip_buffer.getvalue()