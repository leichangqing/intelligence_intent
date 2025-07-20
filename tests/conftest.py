"""
Pytest配置文件
"""
import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock
import sys
import os

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# 设置asyncio事件循环策略
@pytest.fixture(scope="session")
def event_loop():
    """创建事件循环"""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()

@pytest.fixture(scope="session")
def anyio_backend():
    """设置anyio后端"""
    return "asyncio"

@pytest.fixture
def mock_settings():
    """模拟设置"""
    settings = MagicMock()
    settings.DEBUG = True
    settings.REDIS_URL = "redis://localhost:6379/0"
    settings.MYSQL_HOST = "localhost"
    settings.MYSQL_PORT = 3306
    settings.MYSQL_DATABASE = "test_db"
    settings.MYSQL_USER = "test_user"
    settings.MYSQL_PASSWORD = "test_pass"
    settings.AMBIGUITY_DETECTION_THRESHOLD = 0.1
    settings.CONFIDENCE_THRESHOLD = 0.7
    settings.MIN_CONFIDENCE = 0.3
    settings.LOG_LEVEL = "INFO"
    settings.CACHE_TTL = 3600
    return settings

@pytest.fixture
def mock_database():
    """模拟数据库连接"""
    db = MagicMock()
    db.connect.return_value = True
    db.close.return_value = True
    db.is_closed.return_value = False
    return db

@pytest.fixture
def mock_redis():
    """模拟Redis连接"""
    redis = AsyncMock()
    redis.get.return_value = None
    redis.set.return_value = True
    redis.delete.return_value = True
    redis.exists.return_value = False
    redis.ping.return_value = True
    return redis

@pytest.fixture
def mock_logger():
    """模拟日志记录器"""
    logger = MagicMock()
    logger.info.return_value = None
    logger.warning.return_value = None
    logger.error.return_value = None
    logger.debug.return_value = None
    return logger

@pytest.fixture
def sample_user_data():
    """示例用户数据"""
    return {
        "user_id": "user_123",
        "session_id": "sess_456",
        "username": "test_user",
        "email": "test@example.com",
        "preferences": {
            "language": "zh",
            "timezone": "Asia/Shanghai"
        }
    }

@pytest.fixture
def sample_conversation_data():
    """示例对话数据"""
    return {
        "session_id": "sess_123",
        "user_id": "user_456",
        "user_input": "我要订机票",
        "intent_name": "book_flight",
        "confidence": 0.9,
        "entities": [
            {
                "entity": "action",
                "value": "book",
                "confidence": 0.8
            }
        ],
        "response": "好的，我帮您预订机票",
        "created_at": "2024-01-01T10:00:00Z"
    }

@pytest.fixture
def sample_intent_data():
    """示例意图数据"""
    return {
        "intent_name": "book_flight",
        "description": "预订机票",
        "examples": [
            "我要订机票",
            "帮我预订航班",
            "买机票"
        ],
        "slots": [
            {
                "slot_name": "origin",
                "slot_type": "text",
                "is_required": True,
                "description": "出发地"
            },
            {
                "slot_name": "destination",
                "slot_type": "text",
                "is_required": True,
                "description": "目的地"
            },
            {
                "slot_name": "date",
                "slot_type": "date",
                "is_required": True,
                "description": "出发日期"
            }
        ],
        "is_active": True
    }

@pytest.fixture
def sample_function_data():
    """示例功能数据"""
    return {
        "function_name": "book_flight",
        "function_type": "api",
        "description": "预订机票功能",
        "parameters": [
            {
                "name": "origin",
                "type": "string",
                "required": True,
                "description": "出发地"
            },
            {
                "name": "destination",
                "type": "string",
                "required": True,
                "description": "目的地"
            },
            {
                "name": "date",
                "type": "string",
                "required": True,
                "description": "出发日期"
            }
        ],
        "implementation": "https://api.airline.com/book",
        "is_active": True
    }

@pytest.fixture
def sample_query_data():
    """示例查询数据"""
    return {
        "query": "北京天气怎么样",
        "user_id": "user_123",
        "session_id": "sess_456",
        "context": {
            "conversation_history": [],
            "user_preferences": {
                "language": "zh"
            }
        }
    }

# 标记慢速测试
def pytest_configure(config):
    """配置pytest"""
    config.addinivalue_line(
        "markers", "slow: marks tests as slow (deselect with '-m \"not slow\"')"
    )
    config.addinivalue_line(
        "markers", "integration: marks tests as integration tests"
    )
    config.addinivalue_line(
        "markers", "unit: marks tests as unit tests"
    )

# 测试收集钩子
def pytest_collection_modifyitems(config, items):
    """修改测试项"""
    for item in items:
        # 为异步测试添加asyncio标记
        if asyncio.iscoroutinefunction(item.function):
            item.add_marker(pytest.mark.asyncio)
        
        # 为集成测试添加标记
        if "integration" in item.nodeid:
            item.add_marker(pytest.mark.integration)
        
        # 为单元测试添加标记
        if "test_" in item.name and "integration" not in item.nodeid:
            item.add_marker(pytest.mark.unit)

# 测试会话钩子
@pytest.fixture(scope="session", autouse=True)
def setup_test_environment():
    """设置测试环境"""
    # 设置环境变量
    os.environ["TESTING"] = "1"
    os.environ["LOG_LEVEL"] = "ERROR"
    
    yield
    
    # 清理环境变量
    os.environ.pop("TESTING", None)
    os.environ.pop("LOG_LEVEL", None)

# 函数级别的自动清理
@pytest.fixture(autouse=True)
def cleanup_test_data():
    """清理测试数据"""
    yield
    # 这里可以添加测试后清理逻辑
    pass