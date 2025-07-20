"""
异步任务管理API
"""
from fastapi import APIRouter, Depends, HTTPException, Query, Path
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
import uuid
import json

from src.api.dependencies import get_current_user, require_admin_auth, get_cache_service_dependency
from src.schemas.common import StandardResponse
from src.utils.logger import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/tasks", tags=["异步任务"])


# 模拟任务存储（实际应该使用数据库或消息队列）
class TaskStore:
    def __init__(self):
        self.tasks = {}
    
    def create_task(self, task_data: dict) -> str:
        task_id = f"task_{uuid.uuid4().hex[:12]}"
        task_data['task_id'] = task_id
        task_data['created_at'] = datetime.now()
        task_data['updated_at'] = datetime.now()
        self.tasks[task_id] = task_data
        return task_id
    
    def get_task(self, task_id: str) -> Optional[dict]:
        return self.tasks.get(task_id)
    
    def update_task(self, task_id: str, updates: dict):
        if task_id in self.tasks:
            self.tasks[task_id].update(updates)
            self.tasks[task_id]['updated_at'] = datetime.now()
    
    def delete_task(self, task_id: str):
        if task_id in self.tasks:
            del self.tasks[task_id]
    
    def list_tasks(self, user_id: Optional[str] = None, status: Optional[str] = None, 
                   task_type: Optional[str] = None) -> List[dict]:
        tasks = []
        for task in self.tasks.values():
            if user_id and task.get('user_id') != user_id:
                continue
            if status and task.get('status') != status:
                continue
            if task_type and task.get('task_type') != task_type:
                continue
            tasks.append(task)
        return sorted(tasks, key=lambda x: x['created_at'], reverse=True)


# 全局任务存储实例
task_store = TaskStore()


@router.post("/async", response_model=StandardResponse[Dict[str, Any]])
async def create_async_task(
    task_data: Dict[str, Any],
    current_user: Optional[Dict] = Depends(get_current_user)
):
    """创建新的异步任务
    
    Args:
        task_data: 任务数据，包含task_type, conversation_id, user_id, request_data等
        
    Returns:
        Dict: 创建的任务信息
    """
    try:
        # 验证必需字段
        required_fields = ['task_type', 'user_id', 'request_data']
        for field in required_fields:
            if field not in task_data:
                raise HTTPException(status_code=400, detail=f"缺少必需字段: {field}")
        
        # 设置任务默认值
        task_info = {
            'task_type': task_data['task_type'],
            'conversation_id': task_data.get('conversation_id'),
            'user_id': task_data['user_id'],
            'request_data': task_data['request_data'],
            'priority': task_data.get('priority', 'normal'),
            'estimated_duration_seconds': task_data.get('estimated_duration_seconds', 30),
            'status': 'pending',
            'progress': 0.0,
            'result_data': None,
            'error_message': None,
            'retry_count': 0,
            'max_retries': task_data.get('max_retries', 3)
        }
        
        # 计算预估完成时间
        estimated_completion = datetime.now() + timedelta(
            seconds=task_info['estimated_duration_seconds']
        )
        task_info['estimated_completion'] = estimated_completion
        
        # 创建任务
        task_id = task_store.create_task(task_info)
        
        # 异步执行任务（这里是模拟，实际应该使用Celery等任务队列）
        await _simulate_task_execution(task_id)
        
        logger.info(f"异步任务创建成功: {task_id}, 类型: {task_info['task_type']}")
        
        return StandardResponse(
            code=201,
            message="任务创建成功",
            data={
                "task_id": task_id,
                "status": task_info['status'],
                "estimated_completion": estimated_completion.isoformat(),
                "created_at": task_info['created_at'].isoformat()
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"创建异步任务失败: {str(e)}")
        raise HTTPException(status_code=500, detail="创建异步任务失败")


@router.get("/async/{task_id}", response_model=StandardResponse[Dict[str, Any]])
async def get_async_task(
    task_id: str = Path(..., description="任务ID"),
    current_user: Optional[Dict] = Depends(get_current_user)
):
    """查询指定异步任务的状态
    
    Args:
        task_id: 任务ID
        
    Returns:
        Dict: 任务详细信息
    """
    try:
        task = task_store.get_task(task_id)
        if not task:
            raise HTTPException(status_code=404, detail="任务不存在")
        
        # 权限检查（用户只能查看自己的任务，管理员可以查看所有任务）
        if current_user:
            is_admin = current_user.get('is_admin', False)
            is_owner = current_user.get('user_id') == task.get('user_id')
            
            if not (is_admin or is_owner):
                raise HTTPException(status_code=403, detail="权限不足")
        
        # 格式化响应数据
        response_data = {
            "task_id": task['task_id'],
            "task_type": task['task_type'],
            "conversation_id": task.get('conversation_id'),
            "user_id": task['user_id'],
            "status": task['status'],
            "progress": task['progress'],
            "priority": task['priority'],
            "estimated_completion": task['estimated_completion'].isoformat(),
            "created_at": task['created_at'].isoformat(),
            "updated_at": task['updated_at'].isoformat(),
            "result_data": task.get('result_data'),
            "error_message": task.get('error_message'),
            "retry_count": task.get('retry_count', 0),
            "max_retries": task.get('max_retries', 3)
        }
        
        return StandardResponse(
            code=200,
            message="任务信息获取成功",
            data=response_data
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取异步任务失败: {str(e)}")
        raise HTTPException(status_code=500, detail="获取异步任务失败")


@router.get("/async", response_model=StandardResponse[Dict[str, Any]])
async def list_async_tasks(
    user_id: Optional[str] = Query(None, description="用户ID"),
    status: Optional[str] = Query(None, description="任务状态"),
    task_type: Optional[str] = Query(None, description="任务类型"),
    page: int = Query(1, ge=1, description="页码"),
    size: int = Query(10, ge=1, le=100, description="每页大小"),
    current_user: Optional[Dict] = Depends(get_current_user)
):
    """获取异步任务列表
    
    Returns:
        Dict: 任务列表和分页信息
    """
    try:
        # 权限检查
        if current_user:
            is_admin = current_user.get('is_admin', False)
            if not is_admin:
                # 非管理员只能查看自己的任务
                user_id = current_user.get('user_id')
        
        # 获取任务列表
        tasks = task_store.list_tasks(user_id=user_id, status=status, task_type=task_type)
        
        # 分页处理
        total = len(tasks)
        start_idx = (page - 1) * size
        end_idx = start_idx + size
        page_tasks = tasks[start_idx:end_idx]
        
        # 格式化任务数据
        task_list = []
        for task in page_tasks:
            task_info = {
                "task_id": task['task_id'],
                "task_type": task['task_type'],
                "user_id": task['user_id'],
                "status": task['status'],
                "progress": task['progress'],
                "priority": task['priority'],
                "created_at": task['created_at'].isoformat(),
                "updated_at": task['updated_at'].isoformat(),
                "estimated_completion": task['estimated_completion'].isoformat(),
                "has_result": task.get('result_data') is not None,
                "has_error": task.get('error_message') is not None
            }
            task_list.append(task_info)
        
        response_data = {
            "tasks": task_list,
            "pagination": {
                "page": page,
                "size": size,
                "total": total,
                "pages": (total + size - 1) // size
            },
            "summary": {
                "total_tasks": total,
                "pending": len([t for t in tasks if t['status'] == 'pending']),
                "processing": len([t for t in tasks if t['status'] == 'processing']),
                "completed": len([t for t in tasks if t['status'] == 'completed']),
                "failed": len([t for t in tasks if t['status'] == 'failed']),
                "cancelled": len([t for t in tasks if t['status'] == 'cancelled'])
            }
        }
        
        return StandardResponse(
            code=200,
            message="任务列表获取成功",
            data=response_data
        )
        
    except Exception as e:
        logger.error(f"获取任务列表失败: {str(e)}")
        raise HTTPException(status_code=500, detail="获取任务列表失败")


@router.delete("/async/{task_id}", response_model=StandardResponse[Dict[str, Any]])
async def cancel_async_task(
    task_id: str = Path(..., description="任务ID"),
    current_user: Optional[Dict] = Depends(get_current_user)
):
    """取消指定的异步任务
    
    Args:
        task_id: 任务ID
        
    Returns:
        Dict: 取消结果
    """
    try:
        task = task_store.get_task(task_id)
        if not task:
            raise HTTPException(status_code=404, detail="任务不存在")
        
        # 权限检查
        if current_user:
            is_admin = current_user.get('is_admin', False)
            is_owner = current_user.get('user_id') == task.get('user_id')
            
            if not (is_admin or is_owner):
                raise HTTPException(status_code=403, detail="权限不足")
        
        # 检查任务状态
        if task['status'] in ['completed', 'failed', 'cancelled']:
            raise HTTPException(
                status_code=400,
                detail=f"任务已{task['status']}，无法取消"
            )
        
        # 取消任务
        task_store.update_task(task_id, {
            'status': 'cancelled',
            'error_message': '任务被用户取消',
            'completed_at': datetime.now()
        })
        
        logger.info(f"异步任务已取消: {task_id}")
        
        return StandardResponse(
            code=200,
            message="任务取消成功",
            data={
                "task_id": task_id,
                "status": "cancelled",
                "cancelled_at": datetime.now().isoformat()
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"取消异步任务失败: {str(e)}")
        raise HTTPException(status_code=500, detail="取消异步任务失败")


@router.post("/async/{task_id}/retry", response_model=StandardResponse[Dict[str, Any]])
async def retry_async_task(
    task_id: str = Path(..., description="任务ID"),
    current_user: Optional[Dict] = Depends(get_current_user)
):
    """重试失败的异步任务
    
    Args:
        task_id: 任务ID
        
    Returns:
        Dict: 重试结果
    """
    try:
        task = task_store.get_task(task_id)
        if not task:
            raise HTTPException(status_code=404, detail="任务不存在")
        
        # 权限检查
        if current_user:
            is_admin = current_user.get('is_admin', False)
            is_owner = current_user.get('user_id') == task.get('user_id')
            
            if not (is_admin or is_owner):
                raise HTTPException(status_code=403, detail="权限不足")
        
        # 检查任务状态
        if task['status'] != 'failed':
            raise HTTPException(
                status_code=400,
                detail="只能重试失败的任务"
            )
        
        # 检查重试次数
        retry_count = task.get('retry_count', 0)
        max_retries = task.get('max_retries', 3)
        
        if retry_count >= max_retries:
            raise HTTPException(
                status_code=400,
                detail=f"已达到最大重试次数({max_retries})"
            )
        
        # 重置任务状态
        updates = {
            'status': 'pending',
            'progress': 0.0,
            'error_message': None,
            'retry_count': retry_count + 1,
            'estimated_completion': datetime.now() + timedelta(
                seconds=task.get('estimated_duration_seconds', 30)
            )
        }
        
        task_store.update_task(task_id, updates)
        
        # 重新执行任务
        await _simulate_task_execution(task_id)
        
        logger.info(f"异步任务重试: {task_id}, 重试次数: {retry_count + 1}")
        
        return StandardResponse(
            code=200,
            message="任务重试成功",
            data={
                "task_id": task_id,
                "status": "pending",
                "retry_count": retry_count + 1,
                "max_retries": max_retries,
                "estimated_completion": updates['estimated_completion'].isoformat()
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"重试异步任务失败: {str(e)}")
        raise HTTPException(status_code=500, detail="重试异步任务失败")


@router.get("/async/stats", response_model=StandardResponse[Dict[str, Any]])
async def get_task_stats(
    current_user: Dict = Depends(require_admin_auth)
):
    """获取任务统计信息（管理员接口）
    
    Returns:
        Dict: 任务统计数据
    """
    try:
        all_tasks = task_store.list_tasks()
        
        # 基础统计
        total_tasks = len(all_tasks)
        status_stats = {
            'pending': 0,
            'processing': 0,
            'completed': 0,
            'failed': 0,
            'cancelled': 0
        }
        
        type_stats = {}
        user_stats = {}
        
        for task in all_tasks:
            # 状态统计
            status = task.get('status', 'unknown')
            if status in status_stats:
                status_stats[status] += 1
            
            # 类型统计
            task_type = task.get('task_type', 'unknown')
            if task_type not in type_stats:
                type_stats[task_type] = 0
            type_stats[task_type] += 1
            
            # 用户统计
            user_id = task.get('user_id', 'unknown')
            if user_id not in user_stats:
                user_stats[user_id] = 0
            user_stats[user_id] += 1
        
        # 计算成功率
        completed = status_stats['completed']
        failed = status_stats['failed']
        total_finished = completed + failed
        success_rate = (completed / total_finished) if total_finished > 0 else 0
        
        # 最近24小时统计
        now = datetime.now()
        day_ago = now - timedelta(hours=24)
        recent_tasks = [t for t in all_tasks if t['created_at'] >= day_ago]
        
        response_data = {
            "overview": {
                "total_tasks": total_tasks,
                "success_rate": round(success_rate, 4),
                "recent_24h": len(recent_tasks)
            },
            "status_distribution": status_stats,
            "type_distribution": dict(sorted(
                type_stats.items(),
                key=lambda x: x[1],
                reverse=True
            )),
            "top_users": dict(sorted(
                user_stats.items(),
                key=lambda x: x[1],
                reverse=True
            )[:10]),
            "recent_activity": {
                "last_hour": len([
                    t for t in all_tasks 
                    if t['created_at'] >= now - timedelta(hours=1)
                ]),
                "last_6_hours": len([
                    t for t in all_tasks 
                    if t['created_at'] >= now - timedelta(hours=6)
                ]),
                "last_24_hours": len(recent_tasks)
            }
        }
        
        return StandardResponse(
            code=200,
            message="任务统计获取成功",
            data=response_data
        )
        
    except Exception as e:
        logger.error(f"获取任务统计失败: {str(e)}")
        raise HTTPException(status_code=500, detail="获取任务统计失败")


async def _simulate_task_execution(task_id: str):
    """模拟任务执行（实际应该使用异步任务队列）"""
    import asyncio
    import random
    
    async def execute():
        try:
            # 更新状态为处理中
            task_store.update_task(task_id, {
                'status': 'processing',
                'progress': 10.0
            })
            
            # 模拟任务执行时间
            await asyncio.sleep(2)
            
            # 模拟进度更新
            for progress in [30.0, 50.0, 70.0, 90.0]:
                task_store.update_task(task_id, {'progress': progress})
                await asyncio.sleep(0.5)
            
            # 模拟成功/失败（90%成功率）
            if random.random() < 0.9:
                # 成功完成
                result_data = {
                    "message": "任务执行成功",
                    "result": f"模拟结果_{random.randint(1000, 9999)}",
                    "processed_at": datetime.now().isoformat()
                }
                
                task_store.update_task(task_id, {
                    'status': 'completed',
                    'progress': 100.0,
                    'result_data': result_data,
                    'completed_at': datetime.now()
                })
            else:
                # 执行失败
                task_store.update_task(task_id, {
                    'status': 'failed',
                    'error_message': '模拟任务执行失败',
                    'completed_at': datetime.now()
                })
            
        except Exception as e:
            # 异常处理
            task_store.update_task(task_id, {
                'status': 'failed',
                'error_message': f'任务执行异常: {str(e)}',
                'completed_at': datetime.now()
            })
    
    # 在后台执行任务
    asyncio.create_task(execute())