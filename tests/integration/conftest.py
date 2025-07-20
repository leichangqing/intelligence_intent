"""
集成测试配置和公共fixtures
"""
import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timedelta
import json
import os
import sys

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from src.services.intent_service import IntentService
from src.services.conversation_service import ConversationService
from src.services.slot_service import SlotService
from src.services.function_service import FunctionService
from src.services.cache_service import CacheService
from src.services.query_processor import IntelligentQueryProcessor
from src.models.conversation import Session, Conversation
from src.models.intent import Intent
from src.models.slot import Slot, SlotValue
from src.models.function import Function


@pytest.fixture(scope="session")
def event_loop():
    """创建事件循环"""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def mock_database():
    """模拟数据库连接"""
    db_mock = MagicMock()
    db_mock.connect.return_value = True
    db_mock.close.return_value = True
    db_mock.is_closed.return_value = False
    return db_mock


@pytest.fixture
def mock_redis():
    """模拟Redis连接"""
    redis_mock = AsyncMock()
    redis_mock.ping.return_value = True
    redis_mock.get.return_value = None
    redis_mock.set.return_value = True
    redis_mock.delete.return_value = 1
    redis_mock.exists.return_value = False
    redis_mock.expire.return_value = True
    redis_mock.ttl.return_value = 3600
    redis_mock.keys.return_value = []
    redis_mock.flushdb.return_value = True
    return redis_mock


@pytest.fixture
def mock_intent_service():
    """模拟意图服务"""
    service = MagicMock(spec=IntentService)
    
    # 设置异步方法
    service.recognize_intent = AsyncMock()
    service.resolve_ambiguity = AsyncMock()
    service.resolve_with_context = AsyncMock()
    service.get_confidence_threshold = AsyncMock()
    service.cache_intent_result = AsyncMock()
    service.get_cached_intent = AsyncMock()
    service.update_intent_statistics = AsyncMock()
    
    return service


@pytest.fixture
def mock_conversation_service():
    """模拟对话服务"""
    service = MagicMock(spec=ConversationService)
    
    # 设置异步方法
    service.get_or_create_session = AsyncMock()
    service.save_conversation = AsyncMock()
    service.update_session_context = AsyncMock()
    service.get_session_history = AsyncMock()
    service.save_ambiguity = AsyncMock()
    service.resolve_ambiguity = AsyncMock()
    service.get_ambiguity = AsyncMock()
    service.handle_intent_interruption = AsyncMock()
    service.resume_interrupted_intent = AsyncMock()
    service.save_error = AsyncMock()
    service.recover_from_error = AsyncMock()
    service.is_session_expired = AsyncMock()
    service.reset_session = AsyncMock()
    service.should_reset_context = AsyncMock()
    service.get_conversation_statistics = AsyncMock()
    
    return service


@pytest.fixture
def mock_slot_service():
    """模拟槽位服务"""
    service = MagicMock(spec=SlotService)
    
    # 设置异步方法
    service.extract_slots = AsyncMock()
    service.validate_slot_value = AsyncMock()
    service.get_required_slots = AsyncMock()
    service.get_missing_slots = AsyncMock()
    service.are_all_required_slots_filled = AsyncMock()
    service.generate_slot_question = AsyncMock()
    service.merge_slots = AsyncMock()
    service.inherit_slots = AsyncMock()
    service.detect_slot_correction = AsyncMock()
    service.save_slot_value = AsyncMock()
    service.get_slot_statistics = AsyncMock()
    
    return service


@pytest.fixture
def mock_function_service():
    """模拟功能服务"""
    service = MagicMock(spec=FunctionService)
    
    # 设置异步方法
    service.get_function_for_intent = AsyncMock()
    service.call_function = AsyncMock()
    service.validate_parameters = AsyncMock()
    service.register_function = AsyncMock()
    service.get_function_info = AsyncMock()
    service.get_function_history = AsyncMock()
    service.retry_function_call = AsyncMock()
    service.get_function_statistics = AsyncMock()
    
    return service


@pytest.fixture
def mock_cache_service():
    """模拟缓存服务"""
    service = MagicMock(spec=CacheService)
    
    # 设置异步方法
    service.get = AsyncMock()
    service.set = AsyncMock()
    service.delete = AsyncMock()
    service.exists = AsyncMock()
    service.expire = AsyncMock()
    service.ttl = AsyncMock()
    service.keys = AsyncMock()
    service.clear = AsyncMock()
    service.get_stats = AsyncMock()
    service.ping = AsyncMock()
    service.close = AsyncMock()
    
    return service


@pytest.fixture
def mock_query_processor():
    """模拟查询处理器"""
    service = MagicMock(spec=IntelligentQueryProcessor)
    
    # 设置异步方法
    service.process_query = AsyncMock()
    service.enhance_query = AsyncMock()
    service.analyze_query = AsyncMock()
    service.get_search_strategy = AsyncMock()
    service.execute_search = AsyncMock()
    service.format_results = AsyncMock()
    service.cache_results = AsyncMock()
    service.get_cached_results = AsyncMock()
    
    return service


@pytest.fixture
def mock_all_services(mock_intent_service, mock_conversation_service, mock_slot_service, 
                      mock_function_service, mock_cache_service, mock_query_processor):
    """所有模拟服务的集合"""
    return {
        'intent_service': mock_intent_service,
        'conversation_service': mock_conversation_service,
        'slot_service': mock_slot_service,
        'function_service': mock_function_service,
        'cache_service': mock_cache_service,
        'query_processor': mock_query_processor
    }


@pytest.fixture
def mock_session():
    """模拟会话对象"""
    session = MagicMock(spec=Session)
    session.id = 1
    session.session_id = "test_session_001"
    session.user_id = "test_user_001"
    session.status = "active"
    session.context = json.dumps({"current_intent": None, "slots": {}})
    session.created_at = datetime.now()
    session.updated_at = datetime.now()
    
    # 设置方法
    session.get_context.return_value = {"current_intent": None, "slots": {}}
    session.set_context = MagicMock()
    session.update_context = MagicMock()
    session.clear_context = MagicMock()
    session.is_active.return_value = True
    session.activate = MagicMock()
    session.deactivate = MagicMock()
    session.save = MagicMock()
    session.to_dict.return_value = {
        "id": 1,
        "session_id": "test_session_001",
        "user_id": "test_user_001",
        "status": "active",
        "context": {"current_intent": None, "slots": {}},
        "created_at": session.created_at.isoformat(),
        "updated_at": session.updated_at.isoformat()
    }
    
    return session


@pytest.fixture
def mock_intent():
    """模拟意图对象"""
    intent = MagicMock(spec=Intent)
    intent.id = 1
    intent.intent_name = "book_flight"
    intent.description = "预订机票"
    intent.confidence = 0.9
    intent.examples = json.dumps(["我要订机票", "帮我预订航班"])
    intent.is_active = True
    intent.created_at = datetime.now()
    intent.updated_at = datetime.now()
    
    # 设置方法
    intent.get_examples.return_value = ["我要订机票", "帮我预订航班"]
    intent.set_examples = MagicMock()
    intent.add_example = MagicMock()
    intent.remove_example = MagicMock()
    intent.update_statistics = MagicMock()
    intent.get_statistics.return_value = {
        "total_requests": 100,
        "successful_requests": 95,
        "success_rate": 0.95
    }
    intent.to_dict.return_value = {
        "id": 1,
        "intent_name": "book_flight",
        "description": "预订机票",
        "confidence": 0.9,
        "examples": ["我要订机票", "帮我预订航班"],
        "is_active": True,
        "created_at": intent.created_at.isoformat(),
        "updated_at": intent.updated_at.isoformat()
    }
    
    return intent


@pytest.fixture
def mock_slot():
    """模拟槽位对象"""
    slot = MagicMock(spec=Slot)
    slot.id = 1
    slot.intent_id = 1
    slot.slot_name = "origin"
    slot.slot_type = "text"
    slot.is_required = True
    slot.description = "出发地"
    slot.validation_rules = json.dumps({"min_length": 2, "max_length": 50})
    slot.default_value = None
    slot.question_template = "请问您从哪里出发？"
    slot.created_at = datetime.now()
    slot.updated_at = datetime.now()
    
    # 设置方法
    slot.get_validation_rules.return_value = {"min_length": 2, "max_length": 50}
    slot.set_validation_rules = MagicMock()
    slot.validate_value.return_value = True
    slot.has_default_value.return_value = False
    slot.get_default_value.return_value = None
    slot.to_dict.return_value = {
        "id": 1,
        "intent_id": 1,
        "slot_name": "origin",
        "slot_type": "text",
        "is_required": True,
        "description": "出发地",
        "validation_rules": {"min_length": 2, "max_length": 50},
        "default_value": None,
        "question_template": "请问您从哪里出发？",
        "created_at": slot.created_at.isoformat(),
        "updated_at": slot.updated_at.isoformat()
    }
    
    return slot


@pytest.fixture
def mock_function():
    """模拟功能对象"""
    function = MagicMock(spec=Function)
    function.id = 1
    function.function_name = "book_flight_api"
    function.function_type = "api"
    function.description = "预订机票API"
    function.parameters = json.dumps([
        {"name": "origin", "type": "string", "required": True},
        {"name": "destination", "type": "string", "required": True},
        {"name": "date", "type": "string", "required": True}
    ])
    function.implementation = "https://api.airline.com/book"
    function.timeout = 30
    function.retry_count = 3
    function.is_active = True
    function.created_at = datetime.now()
    function.updated_at = datetime.now()
    
    # 设置方法
    function.get_parameters.return_value = [
        {"name": "origin", "type": "string", "required": True},
        {"name": "destination", "type": "string", "required": True},
        {"name": "date", "type": "string", "required": True}
    ]
    function.set_parameters = MagicMock()
    function.get_required_parameters.return_value = [
        {"name": "origin", "type": "string", "required": True},
        {"name": "destination", "type": "string", "required": True},
        {"name": "date", "type": "string", "required": True}
    ]
    function.validate_parameters.return_value = True
    function.is_api_function.return_value = True
    function.is_python_function.return_value = False
    function.to_dict.return_value = {
        "id": 1,
        "function_name": "book_flight_api",
        "function_type": "api",
        "description": "预订机票API",
        "parameters": [
            {"name": "origin", "type": "string", "required": True},
            {"name": "destination", "type": "string", "required": True},
            {"name": "date", "type": "string", "required": True}
        ],
        "implementation": "https://api.airline.com/book",
        "timeout": 30,
        "retry_count": 3,
        "is_active": True,
        "created_at": function.created_at.isoformat(),
        "updated_at": function.updated_at.isoformat()
    }
    
    return function


@pytest.fixture
def sample_conversation_data():
    """示例对话数据"""
    return {
        "booking_conversation": [
            {
                "user_input": "我要订机票",
                "intent": "book_flight",
                "slots": {},
                "response": "请问您要从哪里到哪里？"
            },
            {
                "user_input": "从北京到上海",
                "intent": "book_flight",
                "slots": {"origin": "北京", "destination": "上海"},
                "response": "请问您希望什么时候出发？"
            },
            {
                "user_input": "明天上午",
                "intent": "book_flight",
                "slots": {"origin": "北京", "destination": "上海", "date": "2024-01-02", "time": "morning"},
                "response": "机票预订成功！"
            }
        ],
        "balance_inquiry": {
            "user_input": "查询余额",
            "intent": "check_balance",
            "slots": {},
            "response": "您的余额是5000元"
        },
        "ambiguous_intent": {
            "user_input": "我要处理机票",
            "candidates": [
                {"intent": "book_flight", "confidence": 0.7},
                {"intent": "check_flight", "confidence": 0.65},
                {"intent": "cancel_flight", "confidence": 0.6}
            ],
            "clarification": "请问您是要预订机票、查询机票还是取消机票？"
        }
    }


@pytest.fixture
def sample_function_results():
    """示例功能调用结果"""
    return {
        "book_flight": {
            "success": True,
            "booking_id": "BK123456",
            "flight_info": {
                "origin": "北京",
                "destination": "上海",
                "date": "2024-01-02",
                "time": "morning",
                "class": "economy",
                "price": 1200.50
            }
        },
        "check_balance": {
            "success": True,
            "balance": 5000.00,
            "account_info": {
                "account_number": "123456789",
                "currency": "CNY"
            }
        },
        "cancel_booking": {
            "success": True,
            "cancelled_booking_id": "BK123456",
            "refund_amount": 1200.50
        }
    }


@pytest.fixture
def performance_test_data():
    """性能测试数据"""
    return {
        "concurrent_users": 50,
        "requests_per_user": 10,
        "max_response_time": 2.0,
        "success_rate_threshold": 0.95,
        "test_scenarios": [
            "book_flight",
            "check_balance",
            "cancel_booking",
            "ambiguous_intent"
        ]
    }


@pytest.fixture(autouse=True)
def setup_test_environment():
    """设置测试环境"""
    # 设置测试环境变量
    os.environ['TESTING'] = 'true'
    os.environ['LOG_LEVEL'] = 'DEBUG'
    
    # 模拟缓存连接
    with patch('src.services.cache_service.redis') as mock_redis:
        mock_redis.Redis.from_url.return_value = MagicMock()
        
        yield
    
    # 清理测试环境
    if 'TESTING' in os.environ:
        del os.environ['TESTING']
    if 'LOG_LEVEL' in os.environ:
        del os.environ['LOG_LEVEL']


@pytest.fixture
def integration_test_config():
    """集成测试配置"""
    return {
        "database": {
            "test_db": "test_intent_db",
            "connection_timeout": 5,
            "max_connections": 10
        },
        "cache": {
            "test_redis": "redis://localhost:6379/15",
            "connection_timeout": 3,
            "max_connections": 20
        },
        "services": {
            "intent_service": {
                "confidence_threshold": 0.7,
                "max_ambiguity_candidates": 3
            },
            "conversation_service": {
                "session_timeout": 1800,
                "max_sessions": 1000
            },
            "slot_service": {
                "max_slot_retries": 3,
                "slot_timeout": 30
            },
            "function_service": {
                "default_timeout": 30,
                "max_retries": 3
            }
        },
        "api": {
            "max_request_size": 1024 * 1024,
            "rate_limit": 100,
            "timeout": 30
        }
    }


# 辅助函数
def create_test_session(session_id: str = "test_session", user_id: str = "test_user") -> MagicMock:
    """创建测试会话"""
    session = MagicMock(spec=Session)
    session.session_id = session_id
    session.user_id = user_id
    session.status = "active"
    session.context = json.dumps({"current_intent": None, "slots": {}})
    session.created_at = datetime.now()
    session.updated_at = datetime.now()
    
    session.get_context.return_value = {"current_intent": None, "slots": {}}
    session.set_context = MagicMock()
    session.update_context = MagicMock()
    session.clear_context = MagicMock()
    session.is_active.return_value = True
    session.save = MagicMock()
    
    return session


def create_test_intent(intent_name: str = "test_intent", confidence: float = 0.9) -> MagicMock:
    """创建测试意图"""
    intent = MagicMock(spec=Intent)
    intent.id = 1
    intent.intent_name = intent_name
    intent.confidence = confidence
    intent.description = f"测试意图 {intent_name}"
    intent.is_active = True
    intent.created_at = datetime.now()
    
    return intent


def create_test_slots(slot_data: dict) -> dict:
    """创建测试槽位"""
    slots = {}
    for slot_name, slot_value in slot_data.items():
        slots[slot_name] = {
            "value": slot_value,
            "confidence": 0.9,
            "source": "user_input"
        }
    return slots


def create_test_function_result(success: bool = True, **kwargs) -> dict:
    """创建测试功能结果"""
    result = {
        "success": success,
        "timestamp": datetime.now().isoformat()
    }
    result.update(kwargs)
    return result


# 测试标记
pytest.mark.integration = pytest.mark.integration
pytest.mark.slow = pytest.mark.slow
pytest.mark.concurrent = pytest.mark.concurrent