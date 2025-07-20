"""
端到端测试配置文件 - TASK-050
提供航班预订端到端测试的通用配置和夹具
"""
import pytest
import asyncio
import os
import sys
from typing import Dict, Any
from unittest.mock import AsyncMock, MagicMock

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from src.services.intent_service import IntentService
from src.services.conversation_service import ConversationService
from src.services.slot_service import SlotService
from src.services.function_service import FunctionService
from src.services.cache_service import CacheService


@pytest.fixture(scope="session")
def event_loop():
    """创建事件循环"""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def e2e_test_config():
    """端到端测试配置"""
    return {
        'test_environment': 'e2e_testing',
        'mock_external_apis': True,
        'enable_performance_monitoring': True,
        'timeout_seconds': 30,
        'max_retries': 3,
        'log_level': 'INFO',
        'database_isolation': True,
        'cache_isolation': True
    }


@pytest.fixture
def flight_booking_test_users():
    """测试用户数据"""
    return {
        'business_user': {
            'user_id': 'biz_user_001',
            'user_type': 'business',
            'preferences': {
                'seat_class': '商务舱',
                'time_preference': '早班',
                'price_sensitivity': 'low'
            },
            'history': [
                {'route': '北京-上海', 'frequency': 'monthly'},
                {'route': '北京-深圳', 'frequency': 'quarterly'}
            ]
        },
        'family_user': {
            'user_id': 'family_user_001',
            'user_type': 'family',
            'preferences': {
                'seat_class': '经济舱',
                'group_size': 4,
                'price_sensitivity': 'high'
            },
            'history': [
                {'route': '北京-三亚', 'frequency': 'yearly'},
                {'route': '上海-成都', 'frequency': 'yearly'}
            ]
        },
        'student_user': {
            'user_id': 'student_user_001',
            'user_type': 'student',
            'preferences': {
                'seat_class': '经济舱',
                'price_sensitivity': 'very_high',
                'time_flexibility': 'high'
            },
            'history': [
                {'route': '北京-家乡', 'frequency': 'semester'}
            ]
        }
    }


@pytest.fixture
def mock_flight_data():
    """模拟航班数据"""
    return {
        'available_flights': [
            {
                'flight_number': 'CA1234',
                'airline': '中国国际航空',
                'departure_city': '北京',
                'arrival_city': '上海',
                'departure_time': '08:00',
                'arrival_time': '10:30',
                'duration': '2h30m',
                'aircraft_type': 'A320',
                'prices': {
                    '经济舱': 580,
                    '商务舱': 1200,
                    '头等舱': 2800
                },
                'available_seats': {
                    '经济舱': 120,
                    '商务舱': 20,
                    '头等舱': 8
                }
            },
            {
                'flight_number': 'MU5678',
                'airline': '中国东方航空',
                'departure_city': '北京',
                'arrival_city': '上海',
                'departure_time': '14:00',
                'arrival_time': '16:30',
                'duration': '2h30m',
                'aircraft_type': 'B737',
                'prices': {
                    '经济舱': 620,
                    '商务舱': 1350,
                    '头等舱': 3200
                },
                'available_seats': {
                    '经济舱': 100,
                    '商务舱': 24,
                    '头等舱': 12
                }
            },
            {
                'flight_number': 'CZ9999',
                'airline': '中国南方航空',
                'departure_city': '北京',
                'arrival_city': '上海',
                'departure_time': '20:00',
                'arrival_time': '22:30',
                'duration': '2h30m',
                'aircraft_type': 'A350',
                'prices': {
                    '经济舱': 550,
                    '商务舱': 1100,
                    '头等舱': 2600
                },
                'available_seats': {
                    '经济舱': 150,
                    '商务舱': 30,
                    '头等舱': 16
                }
            }
        ],
        'routes': {
            '北京-上海': ['CA1234', 'MU5678', 'CZ9999'],
            '北京-广州': ['CZ1111', 'CA5555'],
            '上海-深圳': ['MU2222', 'ZH8888'],
            '北京-成都': ['CA3333', '3U7777']
        },
        'airports': {
            '北京': {'code': 'PEK', 'name': '北京首都国际机场'},
            '上海': {'code': 'PVG', 'name': '上海浦东国际机场'},
            '广州': {'code': 'CAN', 'name': '广州白云国际机场'},
            '深圳': {'code': 'SZX', 'name': '深圳宝安国际机场'},
            '成都': {'code': 'CTU', 'name': '成都双流国际机场'}
        }
    }


@pytest.fixture
def mock_e2e_services():
    """端到端测试的模拟服务"""
    services = {
        'intent_service': MagicMock(spec=IntentService),
        'conversation_service': MagicMock(spec=ConversationService), 
        'slot_service': MagicMock(spec=SlotService),
        'function_service': MagicMock(spec=FunctionService),
        'cache_service': MagicMock(spec=CacheService)
    }
    
    # 配置意图识别服务
    async def mock_recognize_intent(text, user_id=None, context=None):
        """智能意图识别模拟"""
        # 机票相关关键词
        flight_keywords = ['机票', '航班', '飞机', '订票', '预订', '出差', '旅行']
        if any(keyword in text for keyword in flight_keywords):
            confidence = 0.95 if '机票' in text else 0.85
            return {
                'intent': 'book_flight',
                'confidence': confidence,
                'is_ambiguous': False,
                'slots': _extract_slots_from_text(text),
                'context_aware': bool(context)
            }
        elif '订票' in text:
            return {
                'intent': None,
                'confidence': 0.0,
                'is_ambiguous': True,
                'candidates': [
                    {'intent_name': 'book_flight', 'confidence': 0.72, 'display_name': '机票'},
                    {'intent_name': 'book_train', 'confidence': 0.68, 'display_name': '火车票'},
                    {'intent_name': 'book_movie', 'confidence': 0.65, 'display_name': '电影票'}
                ]
            }
        else:
            return {
                'intent': None,
                'confidence': 0.0,
                'is_ambiguous': False
            }
    
    services['intent_service'].recognize_intent = AsyncMock(side_effect=mock_recognize_intent)
    
    # 配置槽位服务
    async def mock_extract_slots(intent, text, context=None):
        """槽位提取模拟"""
        return _extract_slots_from_text(text)
    
    async def mock_validate_slots(slots):
        """槽位验证模拟"""
        errors = {}
        
        # 检查同城问题
        if ('departure_city' in slots and 'arrival_city' in slots and 
            slots['departure_city']['value'] == slots['arrival_city']['value']):
            errors['cities'] = '出发城市和到达城市不能相同'
        
        # 检查日期有效性
        if 'departure_date' in slots:
            date_value = slots['departure_date']['value']
            if '昨天' in date_value or '上周' in date_value:
                errors['departure_date'] = '不能预订过去的日期'
        
        return {
            'valid': len(errors) == 0,
            'errors': errors
        }
    
    services['slot_service'].extract_slots = AsyncMock(side_effect=mock_extract_slots)
    services['slot_service'].validate_slots = AsyncMock(side_effect=mock_validate_slots)
    
    # 配置对话服务
    async def mock_get_session_context(user_id, context=None):
        """会话上下文模拟"""
        return {
            'session_id': f'session_{user_id}_{int(asyncio.get_event_loop().time())}',
            'user_id': user_id,
            'current_intent': None,
            'slots': {},
            'conversation_history': [],
            'context_data': context or {},
            'created_at': asyncio.get_event_loop().time()
        }
    
    services['conversation_service'].get_or_create_session_context = AsyncMock(
        side_effect=mock_get_session_context
    )
    
    # 配置函数调用服务
    async def mock_call_function(function_name, params):
        """函数调用模拟"""
        if function_name == 'search_flights':
            return {
                'success': True,
                'data': {
                    'flights': [
                        {
                            'flight_number': 'CA1234',
                            'price': 580,
                            'departure_time': '08:00',
                            'available_seats': 50
                        }
                    ],
                    'total_count': 1
                }
            }
        elif function_name == 'book_flight_api':
            return {
                'success': True,
                'data': {
                    'order_id': f'FL{int(asyncio.get_event_loop().time())}',
                    'booking_id': f'BK{int(asyncio.get_event_loop().time())}',
                    'status': 'confirmed',
                    'flight_number': params.get('flight_number', 'CA1234')
                }
            }
        elif function_name == 'process_payment':
            return {
                'success': True,
                'data': {
                    'transaction_id': f'TXN{int(asyncio.get_event_loop().time())}',
                    'status': 'completed',
                    'amount': params.get('amount', 580)
                }
            }
        else:
            return {
                'success': False,
                'error': f'Unknown function: {function_name}'
            }
    
    services['function_service'].call_function = AsyncMock(side_effect=mock_call_function)
    
    # 配置缓存服务
    cache_store = {}
    
    async def mock_cache_get(key):
        return cache_store.get(key)
    
    async def mock_cache_set(key, value, ttl=None):
        cache_store[key] = value
        return True
    
    services['cache_service'].get = AsyncMock(side_effect=mock_cache_get)
    services['cache_service'].set = AsyncMock(side_effect=mock_cache_set)
    
    return services


def _extract_slots_from_text(text: str) -> Dict[str, Any]:
    """从文本中提取槽位信息的辅助函数"""
    slots = {}
    
    # 城市提取逻辑
    cities = ['北京', '上海', '广州', '深圳', '成都', '西安', '杭州', '南京', '武汉', '重庆']
    
    for city in cities:
        if f'从{city}' in text or f'{city}出发' in text:
            slots['departure_city'] = {
                'value': city,
                'confidence': 0.95,
                'source': 'text_pattern',
                'original_text': text
            }
        elif f'到{city}' in text or f'去{city}' in text or f'飞{city}' in text:
            slots['arrival_city'] = {
                'value': city,
                'confidence': 0.95,
                'source': 'text_pattern',
                'original_text': text
            }
    
    # 日期提取逻辑
    import datetime
    if '明天' in text:
        tomorrow = datetime.datetime.now() + datetime.timedelta(days=1)
        slots['departure_date'] = {
            'value': tomorrow.strftime('%Y-%m-%d'),
            'confidence': 0.90,
            'source': 'relative_date',
            'original_text': text
        }
    elif '后天' in text:
        day_after_tomorrow = datetime.datetime.now() + datetime.timedelta(days=2)
        slots['departure_date'] = {
            'value': day_after_tomorrow.strftime('%Y-%m-%d'),
            'confidence': 0.90,
            'source': 'relative_date',
            'original_text': text
        }
    elif '今天' in text:
        today = datetime.datetime.now()
        slots['departure_date'] = {
            'value': today.strftime('%Y-%m-%d'),
            'confidence': 0.85,
            'source': 'relative_date',
            'original_text': text
        }
    
    # 座位等级提取
    seat_classes = ['经济舱', '商务舱', '头等舱']
    for seat_class in seat_classes:
        if seat_class in text:
            slots['seat_class'] = {
                'value': seat_class,
                'confidence': 0.95,
                'source': 'direct_match',
                'original_text': text
            }
            break
    
    # 人数提取
    if '一张票' in text or '1张票' in text:
        slots['passenger_count'] = {
            'value': 1,
            'confidence': 0.90,
            'source': 'number_pattern'
        }
    elif '两张票' in text or '2张票' in text:
        slots['passenger_count'] = {
            'value': 2,
            'confidence': 0.90,
            'source': 'number_pattern'
        }
    elif '一家四口' in text or '4人' in text:
        slots['passenger_count'] = {
            'value': 4,
            'confidence': 0.95,
            'source': 'family_pattern'
        }
    
    return slots


@pytest.fixture
def e2e_test_metrics():
    """端到端测试指标收集器"""
    return {
        'performance_metrics': {
            'response_times': [],
            'success_rates': [],
            'error_counts': []
        },
        'business_metrics': {
            'booking_success_rate': 0,
            'user_satisfaction_score': 0,
            'conversion_rate': 0
        },
        'technical_metrics': {
            'api_call_counts': {},
            'cache_hit_rates': {},
            'error_distribution': {}
        }
    }


@pytest.fixture
def performance_monitor():
    """性能监控器"""
    class PerformanceMonitor:
        def __init__(self):
            self.start_time = None
            self.metrics = []
        
        def start_monitoring(self):
            self.start_time = asyncio.get_event_loop().time()
        
        def stop_monitoring(self):
            if self.start_time:
                duration = asyncio.get_event_loop().time() - self.start_time
                self.metrics.append({
                    'duration': duration,
                    'timestamp': asyncio.get_event_loop().time()
                })
                return duration
            return 0
        
        def get_average_response_time(self):
            if not self.metrics:
                return 0
            return sum(m['duration'] for m in self.metrics) / len(self.metrics)
        
        def reset(self):
            self.metrics = []
            self.start_time = None
    
    return PerformanceMonitor()


@pytest.fixture(autouse=True)
async def cleanup_test_data():
    """测试数据清理"""
    # 测试前的准备工作
    yield
    
    # 测试后的清理工作
    # 清理临时文件、缓存、数据库连接等
    pass