"""
健康检查API接口单元测试
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient
from fastapi import FastAPI
import json
from datetime import datetime

from src.api.v1.health import router as health_router


@pytest.fixture
def app():
    """创建测试FastAPI应用"""
    app = FastAPI()
    app.include_router(health_router, prefix="/api/v1")
    return app


@pytest.fixture
def client(app):
    """创建测试客户端"""
    return TestClient(app)


@pytest.fixture
def mock_dependencies():
    """模拟依赖"""
    with patch('src.api.v1.health.get_cache_service_dependency') as mock_cache:
        mock_cache.return_value = AsyncMock()
        yield {"cache": mock_cache}


class TestHealthAPI:
    """健康检查API测试类"""
    
    def test_basic_health_check(self, client, mock_dependencies):
        """测试基本健康检查"""
        # 发送请求
        response = client.get("/api/v1/health")
        
        # 验证响应
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 200
        assert "data" in data
        assert data["data"]["status"] == "healthy"
        assert "timestamp" in data["data"]
        assert "uptime" in data["data"]
    
    def test_detailed_health_check(self, client, mock_dependencies):
        """测试详细健康检查"""
        # 模拟数据库连接检查
        with patch('src.api.v1.health.check_database_connection', return_value=True), \
             patch('src.api.v1.health.check_redis_connection', return_value=True), \
             patch('src.api.v1.health.check_nlu_engine_status', return_value=True), \
             patch('src.api.v1.health.get_system_resources', return_value={
                 "cpu_usage": 15.5,
                 "memory_usage": 512,
                 "disk_usage": 75.2
             }):
            
            # 发送请求
            response = client.get("/api/v1/health/detailed")
            
            # 验证响应
            assert response.status_code == 200
            data = response.json()
            assert data["code"] == 200
            assert "data" in data
            assert data["data"]["status"] == "healthy"
            assert data["data"]["database"]["status"] == "connected"
            assert data["data"]["cache"]["status"] == "connected"
            assert data["data"]["nlu_engine"]["status"] == "ready"
            assert data["data"]["resources"]["cpu_usage"] == 15.5
            assert data["data"]["resources"]["memory_usage"] == 512
    
    def test_database_health_check(self, client, mock_dependencies):
        """测试数据库健康检查"""
        # 模拟数据库连接正常
        with patch('src.api.v1.health.check_database_connection', return_value=True), \
             patch('src.api.v1.health.get_database_stats', return_value={
                 "total_connections": 10,
                 "active_connections": 5,
                 "table_count": 15,
                 "last_backup": "2024-01-15T10:00:00Z"
             }):
            
            # 发送请求
            response = client.get("/api/v1/health/database")
            
            # 验证响应
            assert response.status_code == 200
            data = response.json()
            assert data["code"] == 200
            assert "data" in data
            assert data["data"]["status"] == "connected"
            assert data["data"]["total_connections"] == 10
            assert data["data"]["active_connections"] == 5
            assert data["data"]["table_count"] == 15
    
    def test_database_health_check_failed(self, client, mock_dependencies):
        """测试数据库健康检查失败"""
        # 模拟数据库连接失败
        with patch('src.api.v1.health.check_database_connection', return_value=False):
            
            # 发送请求
            response = client.get("/api/v1/health/database")
            
            # 验证响应
            assert response.status_code == 503
            data = response.json()
            assert data["code"] == 503
            assert "data" in data
            assert data["data"]["status"] == "disconnected"
    
    def test_cache_health_check(self, client, mock_dependencies):
        """测试缓存健康检查"""
        # 模拟缓存连接正常
        mock_cache_stats = {
            "status": "connected",
            "total_keys": 150,
            "hit_rate": 0.85,
            "memory_usage": "50MB",
            "connected_clients": 5
        }
        
        mock_dependencies["cache"].return_value.ping.return_value = True
        mock_dependencies["cache"].return_value.get_stats.return_value = mock_cache_stats
        
        # 发送请求
        response = client.get("/api/v1/health/cache")
        
        # 验证响应
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 200
        assert "data" in data
        assert data["data"]["status"] == "connected"
        assert data["data"]["total_keys"] == 150
        assert data["data"]["hit_rate"] == 0.85
    
    def test_cache_health_check_failed(self, client, mock_dependencies):
        """测试缓存健康检查失败"""
        # 模拟缓存连接失败
        mock_dependencies["cache"].return_value.ping.side_effect = Exception("连接失败")
        
        # 发送请求
        response = client.get("/api/v1/health/cache")
        
        # 验证响应
        assert response.status_code == 503
        data = response.json()
        assert data["code"] == 503
        assert "data" in data
        assert data["data"]["status"] == "disconnected"
    
    def test_nlu_engine_health_check(self, client, mock_dependencies):
        """测试NLU引擎健康检查"""
        # 模拟NLU引擎正常
        with patch('src.api.v1.health.check_nlu_engine_status', return_value=True), \
             patch('src.api.v1.health.get_nlu_engine_stats', return_value={
                 "status": "ready",
                 "model_loaded": True,
                 "model_version": "v1.0",
                 "inference_time": 0.15,
                 "total_requests": 1000
             }):
            
            # 发送请求
            response = client.get("/api/v1/health/nlu")
            
            # 验证响应
            assert response.status_code == 200
            data = response.json()
            assert data["code"] == 200
            assert "data" in data
            assert data["data"]["status"] == "ready"
            assert data["data"]["model_loaded"] == True
            assert data["data"]["model_version"] == "v1.0"
            assert data["data"]["inference_time"] == 0.15
    
    def test_nlu_engine_health_check_failed(self, client, mock_dependencies):
        """测试NLU引擎健康检查失败"""
        # 模拟NLU引擎不可用
        with patch('src.api.v1.health.check_nlu_engine_status', return_value=False):
            
            # 发送请求
            response = client.get("/api/v1/health/nlu")
            
            # 验证响应
            assert response.status_code == 503
            data = response.json()
            assert data["code"] == 503
            assert "data" in data
            assert data["data"]["status"] == "unavailable"
    
    def test_system_resources_check(self, client, mock_dependencies):
        """测试系统资源检查"""
        # 模拟系统资源信息
        mock_resources = {
            "cpu_usage": 25.5,
            "memory_usage": 768,
            "memory_total": 2048,
            "disk_usage": 45.2,
            "disk_total": 100,
            "network_io": {
                "bytes_sent": 1024000,
                "bytes_recv": 2048000
            }
        }
        
        with patch('src.api.v1.health.get_system_resources', return_value=mock_resources):
            
            # 发送请求
            response = client.get("/api/v1/health/resources")
            
            # 验证响应
            assert response.status_code == 200
            data = response.json()
            assert data["code"] == 200
            assert "data" in data
            assert data["data"]["cpu_usage"] == 25.5
            assert data["data"]["memory_usage"] == 768
            assert data["data"]["memory_total"] == 2048
            assert data["data"]["disk_usage"] == 45.2
    
    def test_system_resources_high_usage(self, client, mock_dependencies):
        """测试系统资源高使用率"""
        # 模拟高资源使用率
        mock_resources = {
            "cpu_usage": 95.0,
            "memory_usage": 1900,
            "memory_total": 2048,
            "disk_usage": 85.0,
            "disk_total": 100
        }
        
        with patch('src.api.v1.health.get_system_resources', return_value=mock_resources):
            
            # 发送请求
            response = client.get("/api/v1/health/resources")
            
            # 验证响应
            assert response.status_code == 200
            data = response.json()
            assert data["code"] == 200
            assert "data" in data
            assert data["data"]["cpu_usage"] == 95.0
            assert data["data"]["memory_usage"] == 1900
            assert data["data"]["disk_usage"] == 85.0
            # 应该有警告信息
            assert "warnings" in data["data"]
            assert len(data["data"]["warnings"]) > 0
    
    def test_readiness_check(self, client, mock_dependencies):
        """测试就绪检查"""
        # 模拟所有服务就绪
        with patch('src.api.v1.health.check_database_connection', return_value=True), \
             patch('src.api.v1.health.check_redis_connection', return_value=True), \
             patch('src.api.v1.health.check_nlu_engine_status', return_value=True):
            
            # 发送请求
            response = client.get("/api/v1/health/ready")
            
            # 验证响应
            assert response.status_code == 200
            data = response.json()
            assert data["code"] == 200
            assert "data" in data
            assert data["data"]["ready"] == True
            assert data["data"]["database"] == True
            assert data["data"]["cache"] == True
            assert data["data"]["nlu_engine"] == True
    
    def test_readiness_check_not_ready(self, client, mock_dependencies):
        """测试就绪检查未就绪"""
        # 模拟部分服务未就绪
        with patch('src.api.v1.health.check_database_connection', return_value=True), \
             patch('src.api.v1.health.check_redis_connection', return_value=False), \
             patch('src.api.v1.health.check_nlu_engine_status', return_value=True):
            
            # 发送请求
            response = client.get("/api/v1/health/ready")
            
            # 验证响应
            assert response.status_code == 503
            data = response.json()
            assert data["code"] == 503
            assert "data" in data
            assert data["data"]["ready"] == False
            assert data["data"]["database"] == True
            assert data["data"]["cache"] == False
            assert data["data"]["nlu_engine"] == True
    
    def test_liveness_check(self, client, mock_dependencies):
        """测试存活检查"""
        # 发送请求
        response = client.get("/api/v1/health/live")
        
        # 验证响应
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 200
        assert "data" in data
        assert data["data"]["alive"] == True
        assert "timestamp" in data["data"]
    
    def test_dependency_health_check(self, client, mock_dependencies):
        """测试依赖服务健康检查"""
        # 模拟依赖服务状态
        mock_dependencies_status = {
            "xinference": {
                "status": "connected",
                "url": "http://localhost:9997",
                "response_time": 0.05
            },
            "ragflow": {
                "status": "connected",
                "url": "http://localhost:8080",
                "response_time": 0.12
            },
            "duckling": {
                "status": "unavailable",
                "url": "http://localhost:8000",
                "error": "Connection timeout"
            }
        }
        
        with patch('src.api.v1.health.check_external_dependencies', return_value=mock_dependencies_status):
            
            # 发送请求
            response = client.get("/api/v1/health/dependencies")
            
            # 验证响应
            assert response.status_code == 200
            data = response.json()
            assert data["code"] == 200
            assert "data" in data
            assert data["data"]["xinference"]["status"] == "connected"
            assert data["data"]["ragflow"]["status"] == "connected"
            assert data["data"]["duckling"]["status"] == "unavailable"
            assert data["data"]["duckling"]["error"] == "Connection timeout"
    
    def test_performance_metrics(self, client, mock_dependencies):
        """测试性能指标"""
        # 模拟性能指标
        mock_metrics = {
            "request_count": 1000,
            "avg_response_time": 0.25,
            "error_rate": 0.02,
            "throughput": 50.0,
            "active_connections": 15,
            "queue_size": 3
        }
        
        with patch('src.api.v1.health.get_performance_metrics', return_value=mock_metrics):
            
            # 发送请求
            response = client.get("/api/v1/health/metrics")
            
            # 验证响应
            assert response.status_code == 200
            data = response.json()
            assert data["code"] == 200
            assert "data" in data
            assert data["data"]["request_count"] == 1000
            assert data["data"]["avg_response_time"] == 0.25
            assert data["data"]["error_rate"] == 0.02
            assert data["data"]["throughput"] == 50.0
    
    def test_health_check_with_custom_timeout(self, client, mock_dependencies):
        """测试自定义超时的健康检查"""
        # 发送带超时参数的请求
        response = client.get("/api/v1/health/detailed?timeout=5")
        
        # 验证响应
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 200
        assert "data" in data
        assert "timeout" in data["data"]
        assert data["data"]["timeout"] == 5
    
    def test_health_check_error_handling(self, client, mock_dependencies):
        """测试健康检查错误处理"""
        # 模拟检查过程中出现异常
        with patch('src.api.v1.health.check_database_connection', side_effect=Exception("Database error")):
            
            # 发送请求
            response = client.get("/api/v1/health/database")
            
            # 验证响应
            assert response.status_code == 503
            data = response.json()
            assert data["code"] == 503
            assert "data" in data
            assert data["data"]["status"] == "error"
            assert "Database error" in data["data"]["error"]
    
    def test_health_check_version_info(self, client, mock_dependencies):
        """测试版本信息健康检查"""
        # 模拟版本信息
        mock_version_info = {
            "app_version": "1.0.0",
            "python_version": "3.11.0",
            "fastapi_version": "0.104.1",
            "build_date": "2024-01-15",
            "git_commit": "abc123"
        }
        
        with patch('src.api.v1.health.get_version_info', return_value=mock_version_info):
            
            # 发送请求
            response = client.get("/api/v1/health/version")
            
            # 验证响应
            assert response.status_code == 200
            data = response.json()
            assert data["code"] == 200
            assert "data" in data
            assert data["data"]["app_version"] == "1.0.0"
            assert data["data"]["python_version"] == "3.11.0"
            assert data["data"]["build_date"] == "2024-01-15"