"""
任务API接口单元测试
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient
from fastapi import FastAPI
import json
from datetime import datetime, timedelta

from src.api.v1.tasks import router as tasks_router


@pytest.fixture
def app():
    """创建测试FastAPI应用"""
    app = FastAPI()
    app.include_router(tasks_router, prefix="/api/v1")
    return app


@pytest.fixture
def client(app):
    """创建测试客户端"""
    return TestClient(app)


@pytest.fixture
def mock_dependencies():
    """模拟依赖"""
    with patch('src.api.v1.tasks.get_current_user') as mock_user, \
         patch('src.api.v1.tasks.require_admin_auth') as mock_admin, \
         patch('src.api.v1.tasks.get_cache_service_dependency') as mock_cache:
        
        mock_user.return_value = {"user_id": "test_user", "is_admin": False}
        mock_admin.return_value = {"user_id": "admin_user", "is_admin": True}
        mock_cache.return_value = AsyncMock()
        
        yield {
            "user": mock_user,
            "admin": mock_admin,
            "cache": mock_cache
        }


class TestTasksAPI:
    """任务API测试类"""
    
    def test_create_async_task(self, client, mock_dependencies):
        """测试创建异步任务"""
        # 准备测试数据
        task_data = {
            "task_type": "book_flight",
            "user_id": "test_user",
            "request_data": {
                "origin": "北京",
                "destination": "上海",
                "date": "2024-01-01"
            },
            "priority": "high",
            "estimated_duration_seconds": 60
        }
        
        # 模拟任务存储
        with patch('src.api.v1.tasks.task_store') as mock_store:
            mock_store.create_task.return_value = "task_abc123"
            
            # 发送请求
            response = client.post("/api/v1/tasks/async", json=task_data)
            
            # 验证响应
            assert response.status_code == 200
            data = response.json()
            assert data["code"] == 201
            assert "data" in data
            assert data["data"]["task_id"] == "task_abc123"
            assert data["data"]["status"] == "pending"
    
    def test_create_async_task_missing_fields(self, client, mock_dependencies):
        """测试创建异步任务缺少必需字段"""
        # 准备不完整的测试数据
        task_data = {
            "task_type": "book_flight",
            "user_id": "test_user"
            # 缺少 request_data
        }
        
        # 发送请求
        response = client.post("/api/v1/tasks/async", json=task_data)
        
        # 验证响应
        assert response.status_code == 400
        data = response.json()
        assert data["code"] == 400
        assert "缺少必需字段" in data["detail"]
    
    def test_get_async_task(self, client, mock_dependencies):
        """测试获取异步任务"""
        # 准备测试数据
        task_id = "task_abc123"
        
        # 模拟任务数据
        mock_task = {
            "task_id": task_id,
            "task_type": "book_flight",
            "user_id": "test_user",
            "status": "completed",
            "progress": 100.0,
            "priority": "normal",
            "estimated_completion": datetime.now() + timedelta(seconds=30),
            "created_at": datetime.now(),
            "updated_at": datetime.now(),
            "result_data": {
                "booking_id": "BK123456",
                "message": "预订成功"
            },
            "error_message": None,
            "retry_count": 0,
            "max_retries": 3
        }
        
        with patch('src.api.v1.tasks.task_store') as mock_store:
            mock_store.get_task.return_value = mock_task
            
            # 发送请求
            response = client.get(f"/api/v1/tasks/async/{task_id}")
            
            # 验证响应
            assert response.status_code == 200
            data = response.json()
            assert data["code"] == 200
            assert "data" in data
            assert data["data"]["task_id"] == task_id
            assert data["data"]["status"] == "completed"
            assert data["data"]["progress"] == 100.0
            assert data["data"]["result_data"]["booking_id"] == "BK123456"
    
    def test_get_async_task_not_found(self, client, mock_dependencies):
        """测试获取不存在的异步任务"""
        # 准备测试数据
        task_id = "task_nonexistent"
        
        # 模拟任务不存在
        with patch('src.api.v1.tasks.task_store') as mock_store:
            mock_store.get_task.return_value = None
            
            # 发送请求
            response = client.get(f"/api/v1/tasks/async/{task_id}")
            
            # 验证响应
            assert response.status_code == 404
            data = response.json()
            assert data["code"] == 404
            assert "任务不存在" in data["detail"]
    
    def test_get_async_task_permission_denied(self, client, mock_dependencies):
        """测试获取异步任务权限不足"""
        # 准备测试数据
        task_id = "task_abc123"
        
        # 模拟其他用户的任务
        mock_task = {
            "task_id": task_id,
            "task_type": "book_flight",
            "user_id": "other_user",  # 不同的用户
            "status": "pending"
        }
        
        with patch('src.api.v1.tasks.task_store') as mock_store:
            mock_store.get_task.return_value = mock_task
            
            # 发送请求
            response = client.get(f"/api/v1/tasks/async/{task_id}")
            
            # 验证响应
            assert response.status_code == 403
            data = response.json()
            assert data["code"] == 403
            assert "权限不足" in data["detail"]
    
    def test_list_async_tasks(self, client, mock_dependencies):
        """测试获取异步任务列表"""
        # 准备测试数据
        mock_tasks = [
            {
                "task_id": "task_001",
                "task_type": "book_flight",
                "user_id": "test_user",
                "status": "completed",
                "progress": 100.0,
                "priority": "normal",
                "created_at": datetime.now(),
                "updated_at": datetime.now(),
                "estimated_completion": datetime.now() + timedelta(seconds=30),
                "result_data": {"booking_id": "BK001"},
                "error_message": None
            },
            {
                "task_id": "task_002",
                "task_type": "check_balance",
                "user_id": "test_user",
                "status": "processing",
                "progress": 50.0,
                "priority": "high",
                "created_at": datetime.now(),
                "updated_at": datetime.now(),
                "estimated_completion": datetime.now() + timedelta(seconds=15),
                "result_data": None,
                "error_message": None
            }
        ]
        
        with patch('src.api.v1.tasks.task_store') as mock_store:
            mock_store.list_tasks.return_value = mock_tasks
            
            # 发送请求
            response = client.get("/api/v1/tasks/async")
            
            # 验证响应
            assert response.status_code == 200
            data = response.json()
            assert data["code"] == 200
            assert "data" in data
            assert len(data["data"]["tasks"]) == 2
            assert data["data"]["tasks"][0]["task_id"] == "task_001"
            assert data["data"]["tasks"][1]["task_id"] == "task_002"
            assert data["data"]["summary"]["total_tasks"] == 2
            assert data["data"]["summary"]["completed"] == 1
            assert data["data"]["summary"]["processing"] == 1
    
    def test_list_async_tasks_with_filters(self, client, mock_dependencies):
        """测试带过滤条件的任务列表"""
        # 准备测试数据
        params = {
            "status": "completed",
            "task_type": "book_flight",
            "page": 1,
            "size": 5
        }
        
        mock_tasks = [
            {
                "task_id": "task_001",
                "task_type": "book_flight",
                "user_id": "test_user",
                "status": "completed",
                "progress": 100.0,
                "priority": "normal",
                "created_at": datetime.now(),
                "updated_at": datetime.now(),
                "estimated_completion": datetime.now() + timedelta(seconds=30),
                "result_data": {"booking_id": "BK001"},
                "error_message": None
            }
        ]
        
        with patch('src.api.v1.tasks.task_store') as mock_store:
            mock_store.list_tasks.return_value = mock_tasks
            
            # 发送请求
            response = client.get("/api/v1/tasks/async", params=params)
            
            # 验证响应
            assert response.status_code == 200
            data = response.json()
            assert data["code"] == 200
            assert "data" in data
            assert len(data["data"]["tasks"]) == 1
            assert data["data"]["tasks"][0]["status"] == "completed"
            assert data["data"]["tasks"][0]["task_type"] == "book_flight"
    
    def test_cancel_async_task(self, client, mock_dependencies):
        """测试取消异步任务"""
        # 准备测试数据
        task_id = "task_abc123"
        
        # 模拟任务数据
        mock_task = {
            "task_id": task_id,
            "task_type": "book_flight",
            "user_id": "test_user",
            "status": "processing"
        }
        
        with patch('src.api.v1.tasks.task_store') as mock_store:
            mock_store.get_task.return_value = mock_task
            mock_store.update_task.return_value = None
            
            # 发送请求
            response = client.delete(f"/api/v1/tasks/async/{task_id}")
            
            # 验证响应
            assert response.status_code == 200
            data = response.json()
            assert data["code"] == 200
            assert "data" in data
            assert data["data"]["task_id"] == task_id
            assert data["data"]["status"] == "cancelled"
    
    def test_cancel_async_task_already_completed(self, client, mock_dependencies):
        """测试取消已完成的异步任务"""
        # 准备测试数据
        task_id = "task_abc123"
        
        # 模拟已完成的任务
        mock_task = {
            "task_id": task_id,
            "task_type": "book_flight",
            "user_id": "test_user",
            "status": "completed"
        }
        
        with patch('src.api.v1.tasks.task_store') as mock_store:
            mock_store.get_task.return_value = mock_task
            
            # 发送请求
            response = client.delete(f"/api/v1/tasks/async/{task_id}")
            
            # 验证响应
            assert response.status_code == 400
            data = response.json()
            assert data["code"] == 400
            assert "已completed" in data["detail"]
    
    def test_retry_async_task(self, client, mock_dependencies):
        """测试重试异步任务"""
        # 准备测试数据
        task_id = "task_abc123"
        
        # 模拟失败的任务
        mock_task = {
            "task_id": task_id,
            "task_type": "book_flight",
            "user_id": "test_user",
            "status": "failed",
            "retry_count": 1,
            "max_retries": 3
        }
        
        with patch('src.api.v1.tasks.task_store') as mock_store:
            mock_store.get_task.return_value = mock_task
            mock_store.update_task.return_value = None
            
            # 发送请求
            response = client.post(f"/api/v1/tasks/async/{task_id}/retry")
            
            # 验证响应
            assert response.status_code == 200
            data = response.json()
            assert data["code"] == 200
            assert "data" in data
            assert data["data"]["task_id"] == task_id
            assert data["data"]["status"] == "pending"
            assert data["data"]["retry_count"] == 2
    
    def test_retry_async_task_max_retries_reached(self, client, mock_dependencies):
        """测试重试次数已达上限的异步任务"""
        # 准备测试数据
        task_id = "task_abc123"
        
        # 模拟达到最大重试次数的任务
        mock_task = {
            "task_id": task_id,
            "task_type": "book_flight",
            "user_id": "test_user",
            "status": "failed",
            "retry_count": 3,
            "max_retries": 3
        }
        
        with patch('src.api.v1.tasks.task_store') as mock_store:
            mock_store.get_task.return_value = mock_task
            
            # 发送请求
            response = client.post(f"/api/v1/tasks/async/{task_id}/retry")
            
            # 验证响应
            assert response.status_code == 400
            data = response.json()
            assert data["code"] == 400
            assert "已达到最大重试次数" in data["detail"]
    
    def test_get_task_stats_admin(self, client, mock_dependencies):
        """测试获取任务统计（管理员）"""
        # 准备测试数据
        mock_tasks = [
            {
                "task_id": "task_001",
                "task_type": "book_flight",
                "user_id": "user_001",
                "status": "completed",
                "created_at": datetime.now()
            },
            {
                "task_id": "task_002",
                "task_type": "check_balance",
                "user_id": "user_002",
                "status": "failed",
                "created_at": datetime.now()
            },
            {
                "task_id": "task_003",
                "task_type": "book_flight",
                "user_id": "user_001",
                "status": "processing",
                "created_at": datetime.now()
            }
        ]
        
        with patch('src.api.v1.tasks.task_store') as mock_store:
            mock_store.list_tasks.return_value = mock_tasks
            
            # 发送请求
            response = client.get("/api/v1/tasks/async/stats")
            
            # 验证响应
            assert response.status_code == 200
            data = response.json()
            assert data["code"] == 200
            assert "data" in data
            assert data["data"]["overview"]["total_tasks"] == 3
            assert data["data"]["status_distribution"]["completed"] == 1
            assert data["data"]["status_distribution"]["failed"] == 1
            assert data["data"]["status_distribution"]["processing"] == 1
            assert data["data"]["type_distribution"]["book_flight"] == 2
            assert data["data"]["type_distribution"]["check_balance"] == 1
    
    def test_task_execution_simulation(self, client, mock_dependencies):
        """测试任务执行模拟"""
        # 准备测试数据
        task_data = {
            "task_type": "test_task",
            "user_id": "test_user",
            "request_data": {"test": "data"}
        }
        
        # 模拟任务执行
        with patch('src.api.v1.tasks.task_store') as mock_store, \
             patch('src.api.v1.tasks._simulate_task_execution') as mock_execute:
            
            mock_store.create_task.return_value = "task_test123"
            mock_execute.return_value = None
            
            # 发送请求
            response = client.post("/api/v1/tasks/async", json=task_data)
            
            # 验证响应
            assert response.status_code == 200
            data = response.json()
            assert data["code"] == 201
            assert "data" in data
            assert data["data"]["task_id"] == "task_test123"
            
            # 验证任务执行被调用
            mock_execute.assert_called_once_with("task_test123")
    
    def test_task_progress_tracking(self, client, mock_dependencies):
        """测试任务进度跟踪"""
        # 准备测试数据
        task_id = "task_progress123"
        
        # 模拟不同进度的任务
        progress_updates = [
            {"status": "processing", "progress": 25.0},
            {"status": "processing", "progress": 50.0},
            {"status": "processing", "progress": 75.0},
            {"status": "completed", "progress": 100.0}
        ]
        
        with patch('src.api.v1.tasks.task_store') as mock_store:
            for i, update in enumerate(progress_updates):
                mock_task = {
                    "task_id": task_id,
                    "task_type": "long_running_task",
                    "user_id": "test_user",
                    "status": update["status"],
                    "progress": update["progress"],
                    "priority": "normal",
                    "created_at": datetime.now(),
                    "updated_at": datetime.now(),
                    "estimated_completion": datetime.now() + timedelta(seconds=30)
                }
                mock_store.get_task.return_value = mock_task
                
                # 发送请求
                response = client.get(f"/api/v1/tasks/async/{task_id}")
                
                # 验证响应
                assert response.status_code == 200
                data = response.json()
                assert data["code"] == 200
                assert data["data"]["progress"] == update["progress"]
                assert data["data"]["status"] == update["status"]
    
    def test_task_error_handling(self, client, mock_dependencies):
        """测试任务错误处理"""
        # 准备测试数据
        task_data = {
            "task_type": "error_task",
            "user_id": "test_user",
            "request_data": {"cause_error": True}
        }
        
        # 模拟任务创建失败
        with patch('src.api.v1.tasks.task_store') as mock_store:
            mock_store.create_task.side_effect = Exception("Task creation failed")
            
            # 发送请求
            response = client.post("/api/v1/tasks/async", json=task_data)
            
            # 验证响应
            assert response.status_code == 500
            data = response.json()
            assert data["code"] == 500
            assert "创建异步任务失败" in data["detail"]
    
    def test_task_cleanup(self, client, mock_dependencies):
        """测试任务清理"""
        # 准备测试数据
        old_task_id = "task_old123"
        
        # 模拟已完成的旧任务
        mock_old_task = {
            "task_id": old_task_id,
            "task_type": "book_flight",
            "user_id": "test_user",
            "status": "completed",
            "created_at": datetime.now() - timedelta(days=7),  # 7天前
            "updated_at": datetime.now() - timedelta(days=7)
        }
        
        with patch('src.api.v1.tasks.task_store') as mock_store:
            mock_store.get_task.return_value = mock_old_task
            mock_store.delete_task.return_value = None
            
            # 发送清理请求
            response = client.delete(f"/api/v1/tasks/async/{old_task_id}")
            
            # 验证响应
            assert response.status_code == 200
            data = response.json()
            assert data["code"] == 200
            assert "取消" in data["message"]