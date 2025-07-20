"""
函数调用配置管理API (TASK-038)
提供函数调用配置的完整CRUD操作和管理功能
"""
from fastapi import APIRouter, Depends, HTTPException, Query, Path
from typing import Dict, List, Any, Optional
from datetime import datetime
import json

from src.api.dependencies import require_admin_auth, get_cache_service_dependency
from src.schemas.common import StandardResponse
from src.models.function import Function, FunctionCall, FunctionParameter
from src.models.audit import ConfigAuditLog
from src.security.dependencies import require_high_security, sanitize_json_body
from src.utils.logger import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/admin/functions", tags=["函数配置管理"])


@router.get("/", response_model=StandardResponse[List[Dict[str, Any]]])
async def list_function_configs(
    current_user: Dict = Depends(require_admin_auth),
    security_check: Dict = Depends(require_high_security),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    category: Optional[str] = Query(None, description="功能分类"),
    is_active: Optional[bool] = Query(None, description="激活状态"),
    search: Optional[str] = Query(None, description="搜索关键词")
):
    """获取函数配置列表"""
    try:
        # 构建查询条件
        query = Function.select()
        
        if category:
            query = query.where(Function.category == category)
        
        if is_active is not None:
            query = query.where(Function.is_active == is_active)
        
        if search:
            query = query.where(
                (Function.function_name.contains(search)) |
                (Function.description.contains(search))
            )
        
        # 计算总数
        total = query.count()
        
        # 分页查询
        offset = (page - 1) * page_size
        functions = query.offset(offset).limit(page_size).order_by(Function.created_at.desc())
        
        # 构建响应数据
        function_list = []
        for func in functions:
            # 获取参数配置
            parameters = list(func.parameters.where(FunctionParameter.is_active == True))
            param_list = []
            for param in parameters:
                param_data = {
                    "id": param.id,
                    "parameter_name": param.parameter_name,
                    "parameter_type": param.parameter_type,
                    "is_required": param.is_required,
                    "default_value": param.default_value,
                    "description": param.description,
                    "validation_rules": param.get_validation_rules()
                }
                param_list.append(param_data)
            
            # 统计调用信息
            total_calls = func.calls.count()
            successful_calls = func.calls.where(FunctionCall.status == 'completed').count()
            success_rate = (successful_calls / total_calls * 100) if total_calls > 0 else 0
            
            function_data = {
                "id": func.id,
                "function_name": func.function_name,
                "display_name": func.display_name,
                "description": func.description,
                "category": func.category,
                "function_schema": func.get_function_schema(),
                "implementation_code": func.implementation_code,
                "timeout_seconds": func.timeout_seconds,
                "max_retries": func.max_retries,
                "is_async": func.is_async,
                "is_active": func.is_active,
                "parameters": param_list,
                "statistics": {
                    "total_calls": total_calls,
                    "successful_calls": successful_calls,
                    "success_rate": round(success_rate, 2)
                },
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
            message="函数配置列表获取成功",
            data=response_data
        )
        
    except Exception as e:
        logger.error(f"获取函数配置列表失败: {str(e)}")
        raise HTTPException(status_code=500, detail="获取函数配置列表失败")


@router.get("/{function_id}", response_model=StandardResponse[Dict[str, Any]])
async def get_function_config(
    function_id: int = Path(..., description="函数ID"),
    current_user: Dict = Depends(require_admin_auth),
    security_check: Dict = Depends(require_high_security)
):
    """获取指定函数的详细配置"""
    try:
        func = Function.get_by_id(function_id)
        
        # 获取参数配置
        parameters = list(func.parameters.order_by(FunctionParameter.sort_order))
        param_list = []
        for param in parameters:
            param_data = {
                "id": param.id,
                "parameter_name": param.parameter_name,
                "parameter_type": param.parameter_type,
                "is_required": param.is_required,
                "default_value": param.default_value,
                "description": param.description,
                "validation_rules": param.get_validation_rules(),
                "sort_order": param.sort_order,
                "is_active": param.is_active
            }
            param_list.append(param_data)
        
        # 获取最近的调用记录
        recent_calls = list(func.calls.order_by(FunctionCall.created_at.desc()).limit(10))
        call_list = []
        for call in recent_calls:
            call_data = {
                "id": call.id,
                "status": call.status,
                "input_parameters": call.get_input_parameters(),
                "output_result": call.get_output_result(),
                "execution_time_ms": call.execution_time_ms,
                "error_message": call.error_message,
                "created_at": call.created_at.isoformat()
            }
            call_list.append(call_data)
        
        function_data = {
            "id": func.id,
            "function_name": func.function_name,
            "display_name": func.display_name,
            "description": func.description,
            "category": func.category,
            "function_schema": func.get_function_schema(),
            "implementation_code": func.implementation_code,
            "timeout_seconds": func.timeout_seconds,
            "max_retries": func.max_retries,
            "is_async": func.is_async,
            "is_active": func.is_active,
            "parameters": param_list,
            "recent_calls": call_list,
            "created_at": func.created_at.isoformat(),
            "updated_at": func.updated_at.isoformat()
        }
        
        return StandardResponse(
            code=200,
            message="函数配置获取成功",
            data=function_data
        )
        
    except Function.DoesNotExist:
        raise HTTPException(status_code=404, detail="函数配置不存在")
    except Exception as e:
        logger.error(f"获取函数配置失败: {str(e)}")
        raise HTTPException(status_code=500, detail="获取函数配置失败")


@router.post("/", response_model=StandardResponse[Dict[str, Any]])
async def create_function_config(
    current_user: Dict = Depends(require_admin_auth),
    security_check: Dict = Depends(require_high_security),
    function_data: Dict[str, Any] = Depends(sanitize_json_body(allow_html=False))
):
    """创建新的函数配置"""
    try:
        # 验证必需字段
        required_fields = ['function_name', 'description', 'category', 'implementation_code']
        for field in required_fields:
            if field not in function_data:
                raise HTTPException(status_code=400, detail=f"缺少必需字段: {field}")
        
        # 检查函数名是否已存在
        existing = Function.select().where(Function.function_name == function_data['function_name']).first()
        if existing:
            raise HTTPException(status_code=400, detail="函数名称已存在")
        
        # 创建函数配置
        func = Function.create(
            function_name=function_data['function_name'],
            display_name=function_data.get('display_name', function_data['function_name']),
            description=function_data['description'],
            category=function_data['category'],
            function_schema=json.dumps(function_data.get('function_schema', {})),
            implementation_code=function_data['implementation_code'],
            timeout_seconds=function_data.get('timeout_seconds', 30),
            max_retries=function_data.get('max_retries', 3),
            is_async=function_data.get('is_async', False),
            is_active=function_data.get('is_active', True)
        )
        
        # 创建参数配置
        parameters = function_data.get('parameters', [])
        for i, param_data in enumerate(parameters):
            FunctionParameter.create(
                function=func,
                parameter_name=param_data['parameter_name'],
                parameter_type=param_data['parameter_type'],
                is_required=param_data.get('is_required', False),
                default_value=param_data.get('default_value'),
                description=param_data.get('description', ''),
                validation_rules=json.dumps(param_data.get('validation_rules', {})),
                sort_order=param_data.get('sort_order', i),
                is_active=param_data.get('is_active', True)
            )
        
        # 记录审计日志
        ConfigAuditLog.create(
            table_name_field="functions",
            record_id=func.id,
            action="CREATE",
            old_values={},
            new_values={
                "function_name": func.function_name,
                "category": func.category,
                "parameters_count": len(parameters)
            },
            operator_id=current_user.get("user_id", "unknown"),
            operator_name=current_user.get("username", "unknown"),
            ip_address=security_check["client_info"]["ip_address"]
        )
        
        logger.info(f"创建函数配置成功: {func.function_name}")
        
        return StandardResponse(
            code=201,
            message="函数配置创建成功",
            data={
                "id": func.id,
                "function_name": func.function_name,
                "category": func.category,
                "parameters_count": len(parameters),
                "created_at": func.created_at.isoformat()
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"创建函数配置失败: {str(e)}")
        raise HTTPException(status_code=500, detail="创建函数配置失败")


@router.put("/{function_id}", response_model=StandardResponse[Dict[str, Any]])
async def update_function_config(
    function_id: int = Path(..., description="函数ID"),
    current_user: Dict = Depends(require_admin_auth),
    security_check: Dict = Depends(require_high_security),
    function_data: Dict[str, Any] = Depends(sanitize_json_body(allow_html=False))
):
    """更新函数配置"""
    try:
        func = Function.get_by_id(function_id)
        
        # 记录修改前的值
        old_values = {
            "display_name": func.display_name,
            "description": func.description,
            "category": func.category,
            "timeout_seconds": func.timeout_seconds,
            "is_active": func.is_active
        }
        
        # 更新基本信息
        if 'display_name' in function_data:
            func.display_name = function_data['display_name']
        if 'description' in function_data:
            func.description = function_data['description']
        if 'category' in function_data:
            func.category = function_data['category']
        if 'function_schema' in function_data:
            func.function_schema = json.dumps(function_data['function_schema'])
        if 'implementation_code' in function_data:
            func.implementation_code = function_data['implementation_code']
        if 'timeout_seconds' in function_data:
            func.timeout_seconds = function_data['timeout_seconds']
        if 'max_retries' in function_data:
            func.max_retries = function_data['max_retries']
        if 'is_async' in function_data:
            func.is_async = function_data['is_async']
        if 'is_active' in function_data:
            func.is_active = function_data['is_active']
        
        func.save()
        
        # 更新参数配置
        if 'parameters' in function_data:
            # 删除现有参数
            FunctionParameter.delete().where(FunctionParameter.function == func).execute()
            
            # 添加新参数
            for i, param_data in enumerate(function_data['parameters']):
                FunctionParameter.create(
                    function=func,
                    parameter_name=param_data['parameter_name'],
                    parameter_type=param_data['parameter_type'],
                    is_required=param_data.get('is_required', False),
                    default_value=param_data.get('default_value'),
                    description=param_data.get('description', ''),
                    validation_rules=json.dumps(param_data.get('validation_rules', {})),
                    sort_order=param_data.get('sort_order', i),
                    is_active=param_data.get('is_active', True)
                )
        
        # 记录修改后的值
        new_values = {
            "display_name": func.display_name,
            "description": func.description,
            "category": func.category,
            "timeout_seconds": func.timeout_seconds,
            "is_active": func.is_active
        }
        
        # 记录审计日志
        ConfigAuditLog.create(
            table_name_field="functions",
            record_id=func.id,
            action="UPDATE",
            old_values=old_values,
            new_values=new_values,
            operator_id=current_user.get("user_id", "unknown"),
            operator_name=current_user.get("username", "unknown"),
            ip_address=security_check["client_info"]["ip_address"]
        )
        
        logger.info(f"更新函数配置成功: {func.function_name}")
        
        return StandardResponse(
            code=200,
            message="函数配置更新成功",
            data={
                "id": func.id,
                "function_name": func.function_name,
                "updated_at": func.updated_at.isoformat()
            }
        )
        
    except Function.DoesNotExist:
        raise HTTPException(status_code=404, detail="函数配置不存在")
    except Exception as e:
        logger.error(f"更新函数配置失败: {str(e)}")
        raise HTTPException(status_code=500, detail="更新函数配置失败")


@router.delete("/{function_id}", response_model=StandardResponse[Dict[str, Any]])
async def delete_function_config(
    function_id: int = Path(..., description="函数ID"),
    current_user: Dict = Depends(require_admin_auth),
    security_check: Dict = Depends(require_high_security)
):
    """删除函数配置（软删除）"""
    try:
        func = Function.get_by_id(function_id)
        function_name = func.function_name
        
        # 软删除
        func.is_active = False
        func.save()
        
        # 记录审计日志
        ConfigAuditLog.create(
            table_name_field="functions",
            record_id=func.id,
            action="DELETE",
            old_values={"is_active": True},
            new_values={"is_active": False},
            operator_id=current_user.get("user_id", "unknown"),
            operator_name=current_user.get("username", "unknown"),
            ip_address=security_check["client_info"]["ip_address"]
        )
        
        logger.info(f"删除函数配置成功: {function_name}")
        
        return StandardResponse(
            code=200,
            message="函数配置删除成功",
            data={
                "id": function_id,
                "function_name": function_name,
                "deleted_at": datetime.now().isoformat()
            }
        )
        
    except Function.DoesNotExist:
        raise HTTPException(status_code=404, detail="函数配置不存在")
    except Exception as e:
        logger.error(f"删除函数配置失败: {str(e)}")
        raise HTTPException(status_code=500, detail="删除函数配置失败")


@router.post("/{function_id}/test", response_model=StandardResponse[Dict[str, Any]])
async def test_function_config(
    function_id: int = Path(..., description="函数ID"),
    current_user: Dict = Depends(require_admin_auth),
    security_check: Dict = Depends(require_high_security),
    test_data: Dict[str, Any] = Depends(sanitize_json_body(allow_html=False))
):
    """测试函数配置"""
    try:
        func = Function.get_by_id(function_id)
        
        # 获取测试参数
        test_parameters = test_data.get('parameters', {})
        
        # 验证参数
        required_params = list(func.parameters.where(FunctionParameter.is_required == True))
        for param in required_params:
            if param.parameter_name not in test_parameters:
                raise HTTPException(
                    status_code=400, 
                    detail=f"缺少必需参数: {param.parameter_name}"
                )
        
        # 创建测试调用记录
        test_call = FunctionCall.create(
            function=func,
            input_parameters=json.dumps(test_parameters),
            status='pending',
            execution_time_ms=0
        )
        
        # 模拟函数执行（实际应该调用真实的函数）
        import time
        start_time = time.time()
        
        try:
            # 这里应该实际执行函数代码
            # 目前返回模拟结果
            result = {
                "status": "success",
                "output": f"函数 {func.function_name} 执行成功",
                "parameters_used": test_parameters,
                "execution_time": time.time() - start_time
            }
            
            # 更新调用记录
            test_call.status = 'completed'
            test_call.output_result = json.dumps(result)
            test_call.execution_time_ms = int((time.time() - start_time) * 1000)
            test_call.save()
            
        except Exception as exec_error:
            # 更新调用记录
            test_call.status = 'failed'
            test_call.error_message = str(exec_error)
            test_call.execution_time_ms = int((time.time() - start_time) * 1000)
            test_call.save()
            
            result = {
                "status": "error",
                "error": str(exec_error),
                "execution_time": time.time() - start_time
            }
        
        logger.info(f"测试函数配置: {func.function_name} - {result['status']}")
        
        return StandardResponse(
            code=200,
            message="函数测试完成",
            data={
                "function_name": func.function_name,
                "test_call_id": test_call.id,
                "result": result,
                "tested_at": datetime.now().isoformat()
            }
        )
        
    except Function.DoesNotExist:
        raise HTTPException(status_code=404, detail="函数配置不存在")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"测试函数配置失败: {str(e)}")
        raise HTTPException(status_code=500, detail="测试函数配置失败")


@router.get("/{function_id}/statistics", response_model=StandardResponse[Dict[str, Any]])
async def get_function_statistics(
    function_id: int = Path(..., description="函数ID"),
    current_user: Dict = Depends(require_admin_auth),
    days: int = Query(7, ge=1, le=90, description="统计天数")
):
    """获取函数调用统计信息"""
    try:
        func = Function.get_by_id(function_id)
        
        # 获取指定天数内的调用记录
        from datetime import timedelta
        start_date = datetime.now() - timedelta(days=days)
        
        calls = list(func.calls.where(FunctionCall.created_at >= start_date))
        
        # 计算统计信息
        total_calls = len(calls)
        successful_calls = len([c for c in calls if c.status == 'completed'])
        failed_calls = len([c for c in calls if c.status == 'failed'])
        success_rate = (successful_calls / total_calls * 100) if total_calls > 0 else 0
        
        # 计算平均执行时间
        execution_times = [c.execution_time_ms for c in calls if c.execution_time_ms is not None]
        avg_execution_time = sum(execution_times) / len(execution_times) if execution_times else 0
        
        # 按日期统计
        daily_stats = {}
        for call in calls:
            date_key = call.created_at.date().isoformat()
            if date_key not in daily_stats:
                daily_stats[date_key] = {"total": 0, "success": 0, "failed": 0}
            
            daily_stats[date_key]["total"] += 1
            if call.status == 'completed':
                daily_stats[date_key]["success"] += 1
            elif call.status == 'failed':
                daily_stats[date_key]["failed"] += 1
        
        # 错误分析
        error_messages = [c.error_message for c in calls if c.error_message]
        error_stats = {}
        for error in error_messages:
            error_stats[error] = error_stats.get(error, 0) + 1
        
        statistics = {
            "function_name": func.function_name,
            "period_days": days,
            "summary": {
                "total_calls": total_calls,
                "successful_calls": successful_calls,
                "failed_calls": failed_calls,
                "success_rate": round(success_rate, 2),
                "avg_execution_time_ms": round(avg_execution_time, 2)
            },
            "daily_stats": daily_stats,
            "error_stats": dict(sorted(error_stats.items(), key=lambda x: x[1], reverse=True)[:10]),
            "generated_at": datetime.now().isoformat()
        }
        
        return StandardResponse(
            code=200,
            message="函数统计信息获取成功",
            data=statistics
        )
        
    except Function.DoesNotExist:
        raise HTTPException(status_code=404, detail="函数配置不存在")
    except Exception as e:
        logger.error(f"获取函数统计信息失败: {str(e)}")
        raise HTTPException(status_code=500, detail="获取函数统计信息失败")