# Redis 缓存数据示例 (混合架构 V2.2)

## v2.2 版本主要更新

**架构优化变化**:
- **混合架构设计**: 计算层无状态，存储层有状态，支持多轮对话的历史上下文推理
- **数据结构规范化**: conversations表移除slots_filled/slots_missing字段，槽位信息从slot_values表动态获取
- **新增模型支持**: 支持entity_types、entity_dictionary、response_types、conversation_status等新模型的缓存
- **应用层缓存管理**: 缓存失效逻辑从数据库触发器迁移到应用层事件驱动机制  
- **异步日志缓存**: 新增async_log_queue和cache_invalidation_logs的缓存策略

## 1. 统一缓存键命名规范

### 1.1 缓存键模板 v2.2 (CacheService优化)
基于 `src/services/cache_service.py` 的统一模板系统（已修复初始化和方法名问题）：

```python
CACHE_KEY_TEMPLATES = {
    # 基础模板
    'session': 'intent_system:session_context:{session_id}',
    'session_basic': 'intent_system:session:{session_id}',
    'intent_recognition': 'intent_system:nlu_result:{input_hash}:{user_id}',
    'intent_config': 'intent_system:intent_config:{intent_name}',
    'user_profile': 'intent_system:user_profile:{user_id}',
    'conversation_history': 'intent_system:history:{session_id}:{limit}',
    'slot_definitions': 'intent_system:slot_definitions:{intent_name}',
    'function_def': 'intent_system:function_def:{function_name}',
    'transfer_history': 'intent_system:transfer_history:{session_id}:{limit}',
    'stack': 'intent_system:stack:{session_id}',
    'stats_session': 'intent_system:stats:session:{user_id}',
    'rate_limit': 'intent_system:rate_limit:{config_name}',
    'ragflow_config': 'intent_system:config:{config_name}',
    'query_history': 'intent_system:query_history:{session_id}',
    'param_schemas': 'intent_system:param_schemas:{function_name}',
    'session_patterns': 'intent_system:session_patterns:{session_id}',
    'enhanced_query': 'intent_system:enhanced_query:{query_hash}',
    'slot_dependencies': 'intent_system:slot_dependencies:{intent_id}',
    
    # v2.2 新增模板
    'slot_values': 'intent_system:slot_values:{conversation_id}',
    'slot_value_record': 'intent_system:slot_value:{conversation_id}:{slot_id}',
    'entity_types': 'intent_system:entity_types:all',
    'entity_type': 'intent_system:entity_type:{type_code}',
    'entity_dictionary': 'intent_system:entity_dict:{type_code}',
    'response_types': 'intent_system:response_types:{category}',
    'response_type': 'intent_system:response_type:{type_code}',
    'conversation_status': 'intent_system:conv_status:all',
    'conversation_status': 'intent_system:conv_status:{status_code}',
    'system_configs': 'intent_system:system_config:{category}',
    'prompt_templates': 'intent_system:prompt_templates:{template_type}',
    'slot_extraction_rules': 'intent_system:slot_rules:{slot_id}',
    'async_log_status': 'intent_system:async_log_status:{log_type}',
    'cache_invalidation': 'intent_system:cache_invalidation:{table_name}:{record_id}'
}
```

### 1.2 TTL设置标准 v2.2
- **会话数据**: 3600秒 (1小时)
- **用户偏好**: 7200秒 (2小时) 
- **意图识别结果**: 1800秒 (30分钟)
- **配置数据**: 3600秒 (1小时)
- **业务API结果**: 600秒 (10分钟)
- **性能统计**: 300秒 (5分钟)
- **槽位值数据**: 3600秒 (1小时) *v2.2新增*
- **实体词典**: 7200秒 (2小时) *v2.2新增*
- **响应类型**: 3600秒 (1小时) *v2.2新增*
- **异步日志状态**: 300秒 (5分钟) *v2.2新增*
- **缓存失效记录**: 1800秒 (30分钟) *v2.2新增*

## 2. 混合架构会话缓存

### 2.1 基础会话缓存
**Key**: `intent_system:session:sess_a1b2c3d4e5f6`
**TTL**: 3600秒
**数据结构**: JSON (基于SessionDataStructure)

```json
{
  "id": 123,
  "session_id": "sess_a1b2c3d4e5f6",
  "user_id": "enterprise_user_001",
  "context": {
    "session_id": "sess_a1b2c3d4e5f6",
    "user_id": "enterprise_user_001",
    "created_at": "2024-01-20T10:30:00.123456",
    "current_intent": "booking_flight",
    "current_slots": {
      "departure_city": "北京",
      "arrival_city": "上海",
      "departure_date": "2024-01-21"
    },
    "conversation_history": [
      {
        "turn": 1,
        "user_input": "我想订一张明天去上海的机票",
        "intent": "booking_flight",
        "confidence": 0.95,
        "timestamp": "2024-01-20T10:30:00Z"
      }
    ],
    
    // 混合架构业务字段 - 从API请求映射
    "device_info": {
      "platform": "web",
      "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
      "ip_address": "192.168.1.100",
      "screen_resolution": "1920x1080",
      "language": "zh-CN"
    },
    "location": {
      "city": "北京",
      "latitude": 39.9042,
      "longitude": 116.4074,
      "timezone": "Asia/Shanghai"
    },
    "client_system_id": "enterprise_portal_v2.1",
    "request_trace_id": "req_trace_20240120_001",
    "business_context": {
      "department": "sales",
      "cost_center": "CC1001",
      "approval_required": true,
      "booking_policy": "economy_only"
    },
    "temp_preferences": {
      "currency": "USD"  // 临时覆盖系统配置
    },
    
    // 系统管理的用户偏好 - 从数据库加载
    "user_preferences": {
      "language": "zh-CN",
      "currency": "CNY",  // 被temp_preferences覆盖为USD
      "timezone": "Asia/Shanghai",
      "notification_enabled": true,
      "theme": "light",
      "preferred_airline": "国航",
      "default_travel_class": "economy",
      "price_alert_enabled": false
    }
  },
  "created_at": "2024-01-20T10:30:00.123456",
  
  // 快捷访问字段（从context提取）
  "current_intent": "booking_flight",
  "current_slots": {
    "departure_city": "北京",
    "arrival_city": "上海", 
    "departure_date": "2024-01-21"
  },
  "conversation_history": [...],
  "device_info": {...},
  "location": {...},
  "user_preferences": {...}
}
```

## 3. 意图识别结果缓存

### 3.1 NLU处理结果
**Key**: `intent_system:nlu_result:12345678:enterprise_user_001`
**TTL**: 1800秒
**数据结构**: JSON

```json
{
  "input_text": "我想订一张明天去上海的机票",
  "input_hash": 12345678,
  "user_id": "enterprise_user_001",
  "intent": {
    "intent_name": "booking_flight",
    "display_name": "机票预订",
    "confidence": 0.95,
    "id": 1
  },
  "slots": {
    "destination": {
      "value": "上海",
      "confidence": 0.9,
      "source": "llm",
      "original_text": "上海",
      "is_validated": true
    },
    "departure_date": {
      "value": "明天",
      "normalized_value": "2024-01-21",
      "confidence": 0.85,
      "source": "llm",
      "original_text": "明天"
    }
  },
  "confidence": 0.95,
  "processing_time_ms": 250,
  "cached_at": "2024-01-20T10:30:01.234567",
  "llm_model": "gpt-4",
  "context_used": {
    "user_preferences": true,
    "conversation_history": true,
    "business_context": true
  }
}
```

## 4. 用户偏好管理缓存 (混合架构)

### 4.1 系统配置的用户偏好
**Key**: `intent_system:user_profile:enterprise_user_001`
**TTL**: 7200秒
**数据结构**: JSON

```json
{
  "user_id": "enterprise_user_001",
  "loaded_at": "2024-01-20T10:30:00Z",
  "preferences": {
    // 基础偏好
    "language": "zh-CN",
    "currency": "CNY",
    "timezone": "Asia/Shanghai",
    "date_format": "YYYY-MM-DD",
    "time_format": "24h",
    "notification_enabled": true,
    "theme": "light",
    "auto_logout_minutes": 120,
    
    // 业务偏好 (系统管理员配置)
    "preferred_airline": "国航",
    "preferred_hotel_chain": "如家",
    "default_travel_class": "economy",
    "price_alert_enabled": false,
    "booking_approval_required": true,
    "cost_center": "CC1001",
    "expense_limit": 5000.00
  },
  "profile_data": {
    "department": "sales",
    "manager_id": "manager_001",
    "employee_level": "senior",
    "travel_policy_version": "v2.1"
  },
  "last_updated": "2024-01-15T09:00:00Z",
  "managed_by": "admin_001"
}
```

## 5. 意图配置缓存

### 5.1 单个意图配置
**Key**: `intent_system:intent_config:booking_flight`
**TTL**: 3600秒
**数据结构**: JSON

```json
{
  "id": 1,
  "intent_name": "booking_flight",
  "display_name": "机票预订",
  "description": "用户想要预订机票的意图",
  "confidence_threshold": 0.8,
  "priority": 10,
  "is_active": true,
  "examples": [
    "我想订机票",
    "帮我订张机票",
    "我要买机票",
    "预订航班",
    "订从北京到上海的机票"
  ],
  "slots": [
    {
      "slot_name": "departure_city",
      "slot_type": "TEXT",
      "is_required": true,
      "validation_rules": {
        "pattern": "^[\\u4e00-\\u9fa5]{2,10}$",
        "allowed_values": ["北京", "上海", "广州", "深圳"]
      },
      "prompt_template": "请告诉我出发城市是哪里？"
    },
    {
      "slot_name": "arrival_city", 
      "slot_type": "TEXT",
      "is_required": true,
      "validation_rules": {
        "pattern": "^[\\u4e00-\\u9fa5]{2,10}$",
        "allowed_values": ["北京", "上海", "广州", "深圳"]
      },
      "prompt_template": "请告诉我到达城市是哪里？"
    },
    {
      "slot_name": "departure_date",
      "slot_type": "DATE",
      "is_required": true,
      "validation_rules": {
        "date_format": "YYYY-MM-DD",
        "min_date": "today",
        "max_date": "+30d"
      },
      "prompt_template": "请告诉我出发日期是哪天？"
    }
  ],
  "function_call": {
    "function_name": "book_flight_api",
    "api_endpoint": "https://api.enterprise-travel.com/v1/booking",
    "http_method": "POST",
    "headers": {
      "Authorization": "Bearer ${API_TOKEN}",
      "Content-Type": "application/json"
    },
    "param_mapping": {
      "departure_city": "from",
      "arrival_city": "to", 
      "departure_date": "date",
      "user_id": "employee_id"
    },
    "timeout_seconds": 30,
    "retry_count": 3
  },
  "created_at": "2024-01-15T09:00:00Z",
  "updated_at": "2024-01-18T14:30:00Z"
}
```

## 6. 对话历史缓存

### 6.1 会话对话历史
**Key**: `intent_system:history:sess_a1b2c3d4e5f6:20`
**TTL**: 86400秒
**数据结构**: JSON Array

```json
[
  {
    "turn": 1,
    "timestamp": "2024-01-20T10:30:00Z",
    "user_input": "我想订一张明天去上海的机票",
    "intent_recognized": "booking_flight",
    "confidence": 0.95,
    "slots_extracted": {
      "arrival_city": "上海",
      "departure_date": "明天"
    },
    "slots_filled": {
      "arrival_city": "上海",
      "departure_date": "2024-01-21"
    },
    "system_response": "好的，我帮您预订明天去上海的机票。请告诉我出发城市是哪里？",
    "response_type": "slot_filling",
    "processing_time_ms": 180,
    "request_trace_id": "req_trace_20240120_001"
  },
  {
    "turn": 2,
    "timestamp": "2024-01-20T10:31:30Z",
    "user_input": "北京",
    "intent_recognized": "booking_flight",
    "confidence": 0.98,
    "slots_extracted": {
      "departure_city": "北京"
    },
    "slots_filled": {
      "departure_city": "北京",
      "arrival_city": "上海",
      "departure_date": "2024-01-21"
    },
    "system_response": "从北京到上海，明天出发。正在为您查询可用航班...",
    "response_type": "api_calling",
    "processing_time_ms": 120,
    "request_trace_id": "req_trace_20240120_002"
  },
  {
    "turn": 3,
    "timestamp": "2024-01-20T10:32:45Z",
    "user_input": "",
    "intent_recognized": "booking_flight",
    "api_call_result": {
      "success": true,
      "order_id": "FL202401210001",
      "flight_number": "CA1234",
      "departure_time": "2024-01-21T08:30:00",
      "arrival_time": "2024-01-21T10:45:00",
      "price": 580.00,
      "seat": "12A"
    },
    "system_response": "已为您成功预订机票！\\n航班号：CA1234\\n出发：2024-01-21 08:30 北京\\n到达：2024-01-21 10:45 上海\\n座位：12A\\n价格：580元\\n订单号：FL202401210001",
    "response_type": "function_result",
    "processing_time_ms": 2400,
    "request_trace_id": "req_trace_20240120_003"
  }
]
```

## 7. 业务API调用缓存

### 7.1 API调用结果缓存
**Key**: `intent_system:api_result:book_flight:hash_of_params`
**TTL**: 600秒
**数据结构**: JSON

```json
{
  "function_name": "book_flight_api",
  "api_endpoint": "https://api.enterprise-travel.com/v1/booking",
  "params": {
    "from": "北京",
    "to": "上海", 
    "date": "2024-01-21",
    "employee_id": "enterprise_user_001",
    "passenger_count": 1,
    "class": "economy"
  },
  "request_headers": {
    "Authorization": "Bearer ey...",
    "Content-Type": "application/json",
    "X-Trace-ID": "req_trace_20240120_003"
  },
  "result": {
    "success": true,
    "order_id": "FL202401210001",
    "flight_number": "CA1234",
    "airline": "中国国际航空",
    "departure_time": "2024-01-21T08:30:00",
    "arrival_time": "2024-01-21T10:45:00",
    "price": 580.00,
    "currency": "CNY",
    "seat": "12A",
    "booking_reference": "ABCD123",
    "status": "confirmed"
  },
  "response_time_ms": 2400,
  "cached_at": "2024-01-20T10:32:45Z",
  "expires_at": "2024-01-20T10:42:45Z",
  "business_context": {
    "department": "sales",
    "cost_center": "CC1001",
    "approval_status": "auto_approved"
  }
}
```

## 8. 系统配置缓存

### 8.1 系统阈值配置
**Key**: `intent_system:config:system_thresholds`
**TTL**: 3600秒
**数据结构**: JSON

```json
{
  "config_name": "system_thresholds",
  "intent_confidence_threshold": 0.7,
  "ambiguity_detection_threshold": 0.1,
  "intent_transfer_threshold": 0.1,
  "slot_confidence_threshold": 0.6,
  "session_timeout_seconds": 3600,
  "max_conversation_turns": 50,
  "max_ambiguity_candidates": 5,
  "nlu_cache_ttl": 1800,
  "api_timeout_seconds": 30,
  "max_retry_attempts": 3,
  "enterprise_specific": {
    "approval_amount_threshold": 1000.00,
    "max_booking_window_days": 30,
    "require_manager_approval": true,
    "cost_center_validation": true
  },
  "updated_at": "2024-01-20T09:00:00Z",
  "version": "v2.2"
}
```

## 9. 意图栈管理缓存

### 9.1 用户意图栈
**Key**: `intent_system:stack:sess_a1b2c3d4e5f6`
**TTL**: 3600秒
**数据结构**: JSON

```json
{
  "session_id": "sess_a1b2c3d4e5f6",
  "user_id": "enterprise_user_001",
  "intent_stack": [
    {
      "intent_name": "booking_flight",
      "intent_id": 1,
      "status": "active",
      "confidence": 0.95,
      "slots": {
        "departure_city": "北京",
        "arrival_city": "上海",
        "departure_date": "2024-01-21"
      },
      "pushed_at": "2024-01-20T10:30:00Z",
      "last_updated": "2024-01-20T10:32:45Z",
      "completion_status": "completed"
    }
  ],
  "stack_depth": 1,
  "max_stack_depth": 5,
  "last_operation": "intent_completed",
  "last_operation_at": "2024-01-20T10:32:45Z"
}
```

## 10. 性能监控缓存

### 10.1 实时系统性能
**Key**: `intent_system:stats:system:realtime`
**TTL**: 60秒
**数据结构**: JSON

```json
{
  "timestamp": "2024-01-20T10:33:00Z",
  "system_metrics": {
    "cpu_usage_percent": 65.4,
    "memory_usage_percent": 78.2,
    "active_sessions": 234,
    "requests_per_second": 45.6,
    "average_response_time_ms": 180.5,
    "cache_hit_rate": 0.89,
    "database_connections": 12,
    "error_rate_5min": 0.02
  },
  "intent_metrics": {
    "total_intent_recognitions": 1520,
    "successful_recognitions": 1444,
    "ambiguous_cases": 32,
    "fallback_cases": 44,
    "average_confidence": 0.87
  },
  "api_metrics": {
    "total_api_calls": 456,
    "successful_calls": 442,
    "failed_calls": 14,
    "average_api_response_time_ms": 850,
    "timeout_rate": 0.008
  },
  "enterprise_metrics": {
    "enterprise_users_active": 89,
    "approval_pending_count": 5,
    "cost_center_distribution": {
      "CC1001": 45,
      "CC1002": 28,
      "CC1003": 16
    }
  }
}
```

## 11. 缓存失效管理

### 11.1 配置更新通知
**Key**: `intent_system:cache_invalidation:notifications`
**TTL**: 300秒
**数据结构**: JSON Array

```json
[
  {
    "invalidation_id": "inv_20240120_001",
    "type": "intent_config",
    "action": "update",
    "target": "booking_flight",
    "affected_keys": [
      "intent_system:intent_config:booking_flight",
      "intent_system:slot_definitions:booking_flight"
    ],
    "timestamp": "2024-01-20T10:00:00Z",
    "operator_id": "admin_001",
    "reason": "更新置信度阈值"
  },
  {
    "invalidation_id": "inv_20240120_002", 
    "type": "user_preferences",
    "action": "bulk_update",
    "target": "enterprise_user_001",
    "affected_keys": [
      "intent_system:user_profile:enterprise_user_001"
    ],
    "timestamp": "2024-01-20T10:15:00Z",
    "operator_id": "manager_001",
    "reason": "更新差旅政策偏好"
  }
]
```

## 12. 企业级特有缓存

### 12.1 企业用户管理
**Key**: `intent_system:enterprise:users:active`
**TTL**: 1800秒
**数据结构**: JSON

```json
{
  "total_users": 156,
  "active_sessions": 89,
  "users_by_department": {
    "sales": 45,
    "marketing": 28,
    "finance": 16,
    "hr": 12,
    "it": 8
  },
  "users_by_level": {
    "junior": 67,
    "senior": 54,
    "manager": 25,
    "director": 10
  },
  "activity_summary": {
    "intent_distribution": {
      "booking_flight": 245,
      "booking_hotel": 123,
      "expense_report": 89,
      "check_balance": 67
    },
    "peak_hours": ["09:00-12:00", "14:00-17:00"],
    "average_session_duration_minutes": 12.5
  },
  "last_updated": "2024-01-20T10:30:00Z"
}
```

### 12.2 成本中心统计
**Key**: `intent_system:cost_center:CC1001:daily:20240120`
**TTL**: 86400秒
**数据结构**: JSON

```json
{
  "cost_center": "CC1001",
  "date": "2024-01-20",
  "department": "sales",
  "manager": "manager_001",
  "statistics": {
    "total_bookings": 15,
    "total_amount": 8750.00,
    "currency": "CNY",
    "booking_types": {
      "flight": 8,
      "hotel": 5,
      "train": 2
    },
    "approval_status": {
      "auto_approved": 10,
      "pending_approval": 3,
      "approved": 2,
      "rejected": 0
    },
    "average_booking_amount": 583.33
  },
  "top_users": [
    {
      "user_id": "enterprise_user_001",
      "bookings": 3,
      "amount": 1740.00
    },
    {
      "user_id": "enterprise_user_002", 
      "bookings": 2,
      "amount": 1160.00
    }
  ],
  "generated_at": "2024-01-20T23:59:59Z"
}
```

## 13. 缓存性能优化

### 13.1 缓存命中率统计
**Key**: `intent_system:cache:performance:hourly`
**TTL**: 3600秒
**数据结构**: JSON

```json
{
  "hour": "2024-01-20T10:00:00Z",
  "cache_statistics": {
    "total_requests": 15420,
    "cache_hits": 13724,
    "cache_misses": 1696,
    "hit_rate": 0.89,
    "avg_hit_response_time_ms": 2.3,
    "avg_miss_response_time_ms": 25.7
  },
  "key_type_performance": {
    "session": {
      "requests": 5680,
      "hits": 4912,
      "hit_rate": 0.86
    },
    "intent_recognition": {
      "requests": 3240,
      "hits": 2916,
      "hit_rate": 0.90
    },
    "user_profile": {
      "requests": 2150,
      "hits": 2021,
      "hit_rate": 0.94
    },
    "intent_config": {
      "requests": 1890,
      "hits": 1832,
      "hit_rate": 0.97
    }
  },
  "memory_usage": {
    "total_keys": 125680,
    "memory_usage_mb": 456.7,
    "expired_keys": 245,
    "evicted_keys": 12
  }
}
```

## 14. v2.2新增模型缓存

### 14.1 槽位值缓存 (基于slot_values表)
**Key**: `intent_system:slot_values:conv_123`
**TTL**: 3600秒
**数据结构**: JSON

```json
{
  "conversation_id": 123,
  "slot_values": [
    {
      "id": 456,
      "slot_id": 12,
      "slot_name": "departure_city",
      "original_text": "我想从北京出发",
      "extracted_value": "北京",
      "normalized_value": "北京市",
      "confidence": 0.95,
      "extraction_method": "entity_recognition",
      "validation_status": "valid",
      "is_confirmed": true,
      "created_at": "2024-01-20T10:30:00Z"
    }
  ],
  "filled_count": 3,
  "missing_count": 1
}
```

### 14.2 实体词典缓存 (基于entity_dictionary表)
**Key**: `intent_system:entity_dict:city`
**TTL**: 7200秒
**数据结构**: JSON

```json
{
  "entity_type_code": "city",
  "entities": {
    "北京": {
      "id": 101,
      "entity_value": "北京",
      "canonical_form": "北京市",
      "aliases": ["北京", "京城", "首都", "BJ"],
      "confidence_weight": 1.0,
      "metadata": {"province": "北京市", "code": "BJ"},
      "frequency_count": 1250
    },
    "shanghai": {
      "id": 102,
      "entity_value": "上海",
      "canonical_form": "上海市", 
      "aliases": ["上海", "魔都", "SH"],
      "confidence_weight": 1.0,
      "metadata": {"province": "上海市", "code": "SH"}
    }
  },
  "total_entities": 50,
  "last_updated": "2024-01-20T08:00:00Z"
}
```

### 14.3 响应类型定义缓存 (基于response_types表)
**Key**: `intent_system:response_types:success`
**TTL**: 3600秒
**数据结构**: JSON

```json
{
  "category": "success",
  "response_types": [
    {
      "id": 1,
      "type_code": "api_result",
      "type_name": "API调用结果",
      "description": "API调用成功返回的结果",
      "template_format": "json",
      "default_template": "操作成功完成：${result}",
      "metadata": {"auto_close": true, "success_tone": "professional"}
    },
    {
      "id": 2,
      "type_code": "task_completion",
      "type_name": "任务完成",
      "description": "意图处理完成",
      "template_format": "text",
      "default_template": "任务已完成，订单号：${order_id}"
    }
  ]
}
```

### 14.4 对话状态缓存 (基于conversation_status表)
**Key**: `intent_system:conv_status:all`
**TTL**: 3600秒
**数据结构**: JSON

```json
{
  "status": [
    {
      "id": 1,
      "status_code": "completed",
      "status_name": "已完成",
      "description": "对话成功完成",
      "category": "success",
      "is_final": true,
      "next_allowed_status": [],
      "notification_required": false
    },
    {
      "id": 2,
      "status_code": "slot_filling",
      "status_name": "槽位填充中",
      "description": "正在进行槽位填充",
      "category": "processing",
      "is_final": false,
      "next_allowed_status": ["completed", "validation_error", "cancelled"],
      "notification_required": false
    }
  ],
  "by_category": {
    "success": ["completed", "ragflow_handled"],
    "processing": ["slot_filling", "ambiguous"],
    "error": ["api_error", "validation_error"]
  }
}
```

## 15. v2.2缓存失效机制

### 15.1 应用层事件驱动失效
```python
# v2.2: 替代数据库触发器的应用层失效机制
def publish_cache_invalidation_event(table_name: str, record_id: int, operation: str, data: dict):
    """发布缓存失效事件"""
    event = {
        "event_type": "cache_invalidation",
        "table_name": table_name,
        "record_id": record_id,
        "operation": operation,  # INSERT, UPDATE, DELETE
        "data": data,
        "timestamp": datetime.utcnow().isoformat(),
        "invalidation_id": generate_uuid()
    }
    
    # 发布到消息队列或事件系统
    event_system.publish("cache.invalidation", event)
    
    # 记录到cache_invalidation_logs表
    record_invalidation_log(event)

# 消费者处理失效事件
def handle_invalidation_event(event):
    """处理缓存失效事件"""
    invalidation_service.process_event(event)

## 15.3 v2.2修复的缓存服务初始化问题

### CacheService初始化优化
```python
# 修复前的问题: Redis缓存服务未初始化警告
# 修复: 调整服务初始化顺序，确保缓存服务在其他服务之前初始化

# src/main.py 启动序列优化:
@app.on_event("startup")
async def startup_event():
    """应用启动事件 - v2.2优化版本"""
    logger.info("正在启动智能意图识别系统...")
    
    try:
        # 1. 首先初始化缓存服务
        from src.services.cache_service import CacheService
        cache_service = CacheService()
        await cache_service.initialize()
        logger.info("缓存服务初始化完成")
        
        # 2. 初始化数据库连接
        database.connect(reuse_if_open=True)
        logger.info("数据库连接建立成功")
        
        # 3. 初始化其他服务
        await initialize_system_services()
        
        # 4. 缓存预热（现在可以安全执行）
        await cache_service.warmup_cache()
        logger.info("缓存预热完成")
        
    except Exception as e:
        logger.error(f"系统启动失败: {e}")
        raise
```

### 修复的缓存方法名
```python
# 修复前: generate_key方法不存在
# 修复后: 统一使用get_cache_key方法

# 错误的调用方式:
# cache_key = cache_service.generate_key(template, params)

# 正确的调用方式:
cache_key = cache_service.get_cache_key(template, **params)

# 示例:
session_key = cache_service.get_cache_key('session', session_id=session_id)
user_key = cache_service.get_cache_key('user_profile', user_id=user_id)
```
```

### 15.2 异步日志缓存
**Key**: `intent_system:async_log_status:api_call`
**TTL**: 300秒
**数据结构**: JSON

```json
{
  "log_type": "api_call",
  "queue_status": {
    "pending_count": 25,
    "processing_count": 3,
    "completed_count": 1247,
    "failed_count": 2
  },
  "performance": {
    "avg_processing_time_ms": 45,
    "throughput_per_minute": 85
  },
  "last_processed_at": "2024-01-20T10:29:45Z"
}
```

这个v2.2更新文档展示了：

1. **v2.2架构优化** - 数据结构规范化、应用层逻辑分离
2. **新增模型支持** - 槽位值、实体词典、响应类型等新模型的缓存策略
3. **事件驱动失效** - 替代数据库触发器的应用层缓存失效机制
4. **异步处理缓存** - 支持async_log_queue和cache_invalidation_logs的缓存管理
5. **B2B企业特性** - 完整支持企业级数据结构和业务流程

所有示例都基于MySQL Schema v2.2的最新架构设计！