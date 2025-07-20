# Redis 缓存数据示例

## 1. 缓存键命名规范

### 1.1 键名前缀
- `intent_config:` - 意图配置缓存
- `slot_config:` - 槽位配置缓存
- `function_config:` - 功能调用配置缓存
- `template_config:` - Prompt模板配置缓存
- `user_context:` - 用户上下文缓存
- `nlu_result:` - NLU结果缓存
- `intent_match:` - 意图匹配结果缓存
- `api_call:` - API调用结果缓存
- `security_config:` - 安全配置缓存
- `audit_log:` - 审计日志缓存

### 1.2 TTL设置
- 配置数据: 3600秒 (1小时)
- 模板配置: 3600秒 (1小时)
- 用户上下文: 7200秒 (2小时)
- NLU结果: 1800秒 (30分钟)
- 意图匹配: 1800秒 (30分钟)
- API调用结果: 300秒 (5分钟)
- 安全配置: 7200秒 (2小时)
- 审计日志: 900秒 (15分钟)

## 2. 意图配置缓存

### 2.1 意图配置列表
**Key**: `intent_config:all`
**TTL**: 3600秒
**数据结构**: Hash
```json
{
  "book_flight": {
    "id": 1,
    "intent_name": "book_flight",
    "display_name": "订机票",
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
    ]
  },
  "check_balance": {
    "id": 2,
    "intent_name": "check_balance",
    "display_name": "查银行卡余额",
    "description": "用户想要查询银行卡余额的意图",
    "confidence_threshold": 0.75,
    "priority": 8,
    "is_active": true,
    "examples": [
      "查余额",
      "我的银行卡余额",
      "账户余额多少",
      "查询余额"
    ]
  }
}
```

### 2.2 单个意图配置
**Key**: `intent_config:book_flight`
**TTL**: 3600秒
**数据结构**: String (JSON)
```json
{
  "id": 1,
  "intent_name": "book_flight",
  "display_name": "订机票",
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
      "prompt_template": "请告诉我出发城市是哪里？"
    },
    {
      "slot_name": "arrival_city",
      "slot_type": "TEXT",
      "is_required": true,
      "prompt_template": "请告诉我到达城市是哪里？"
    },
    {
      "slot_name": "departure_date",
      "slot_type": "DATE",
      "is_required": true,
      "prompt_template": "请告诉我出发日期是哪天？"
    }
  ],
  "function_call": {
    "function_name": "book_flight_api",
    "api_endpoint": "https://api.flight.com/v1/booking",
    "http_method": "POST",
    "param_mapping": {
      "departure_city": "departure_city",
      "arrival_city": "arrival_city",
      "departure_date": "departure_date"
    }
  }
}
```

## 3. 用户上下文缓存

### 3.1 用户上下文信息
**Key**: `user_context:user123`
**TTL**: 7200秒
**数据结构**: Hash
```json
{
  "user_id": "user123",
  "last_active": "2024-12-01T10:05:00Z",
  "preferences": {
    "preferred_class": "经济舱",
    "frequent_routes": ["北京-上海", "上海-深圳"],
    "preferred_airlines": ["CA", "MU"],
    "language": "zh-CN"
  },
  "recent_intents": [
    {"intent": "book_flight", "timestamp": "2024-12-01T10:00:00Z", "frequency": 5},
    {"intent": "check_flight", "timestamp": "2024-12-01T09:30:00Z", "frequency": 2}
  ]
}
```

### 3.2 意图匹配结果缓存
**Key**: `intent_match:{hash_of_input}`
**TTL**: 1800秒
**数据结构**: Hash
```json
{
  "input": "我想订一张明天从北京到上海的机票",
  "input_hash": "abc123def456",
  "intent": "book_flight",
  "confidence": 0.95,
  "slots": {
    "departure_city": {
      "value": "北京",
      "confidence": 0.98,
      "source": "user_input"
    },
    "arrival_city": {
      "value": "上海",
      "confidence": 0.97,
      "source": "user_input"
    },
    "departure_date": {
      "value": "2024-12-02",
      "confidence": 0.90,
      "source": "user_input"
    }
  },
  "cached_at": "2024-12-01T10:00:00Z"
}
```

## 4. 用户上下文缓存

### 4.1 用户历史偏好
**Key**: `user_context:user123:preferences`
**TTL**: 604800秒 (7天)
**数据结构**: Hash
```json
{
  "frequent_intents": {
    "book_flight": 15,
    "check_balance": 8,
    "book_hotel": 3
  },
  "slot_preferences": {
    "seat_class": "商务舱",
    "departure_city": "北京",
    "bank_card": "6222****5678"
  },
  "interaction_patterns": {
    "avg_response_time": 3.5,
    "preferred_time_slots": ["09:00-12:00", "14:00-18:00"],
    "communication_style": "direct"
  },
  "last_successful_intents": {
    "book_flight": {
      "completed_at": "2024-11-28T15:30:00Z",
      "slots": {
        "departure_city": "北京",
        "arrival_city": "上海",
        "departure_date": "2024-11-29"
      }
    }
  }
}
```

### 4.2 用户当前会话上下文
**Key**: `user_context:user123:current`
**TTL**: 86400秒
**数据结构**: Hash
```json
{
  "active_sessions": ["sess_20241201_001"],
  "current_session": "sess_20241201_001",
  "conversation_turn": 3,
  "last_interaction": "2024-12-01T10:05:00Z",
  "device_info": {
    "platform": "web",
    "user_agent": "Mozilla/5.0...",
    "ip_address": "192.168.1.100"
  },
  "temporary_context": {
    "mentioned_entities": ["北京", "上海", "明天"],
    "conversation_topic": "travel",
    "emotional_state": "neutral"
  }
}
```

## 5. NLU结果缓存

### 5.1 意图识别结果
**Key**: `nlu_result:hash_of_input_text`
**TTL**: 1800秒
**数据结构**: String (JSON)
```json
{
  "input_text": "我想订一张明天从北京到上海的机票",
  "intent_results": [
    {
      "intent": "book_flight",
      "confidence": 0.95,
      "reasoning": "用户明确表达订机票意图"
    },
    {
      "intent": "travel_inquiry",
      "confidence": 0.25,
      "reasoning": "包含旅行相关信息"
    }
  ],
  "entities": [
    {
      "entity": "departure_city",
      "value": "北京",
      "confidence": 0.98,
      "start": 7,
      "end": 9
    },
    {
      "entity": "arrival_city",
      "value": "上海",
      "confidence": 0.97,
      "start": 11,
      "end": 13
    },
    {
      "entity": "departure_date",
      "value": "明天",
      "normalized_value": "2024-12-02",
      "confidence": 0.90,
      "start": 4,
      "end": 6
    }
  ],
  "processed_at": "2024-12-01T10:01:00Z",
  "processing_time_ms": 250
}
```

## 6. 歧义处理缓存

### 6.1 意图歧义状态
**Key**: `ambiguity:user123:sess_20241201_001`
**TTL**: 300秒
**数据结构**: Hash
```json
{
  "conversation_id": 12345,
  "original_input": "我想订票",
  "candidate_intents": [
    {
      "intent": "book_flight",
      "confidence": 0.72,
      "display_name": "机票"
    },
    {
      "intent": "book_train",
      "confidence": 0.68,
      "display_name": "火车票"
    },
    {
      "intent": "book_movie",
      "confidence": 0.65,
      "display_name": "电影票"
    }
  ],
  "disambiguation_question": "请问您想要预订哪种票？\n1. 机票\n2. 火车票\n3. 电影票",
  "created_at": "2024-12-01T10:00:00Z",
  "awaiting_response": true,
  "context": {
    "previous_intents": ["check_balance"],
    "user_history": ["book_flight", "book_flight", "book_train"]
  }
}
```

## 7. 对话历史缓存

### 7.1 会话对话历史
**Key**: `conversation:user123:sess_20241201_001`
**TTL**: 86400秒
**数据结构**: List
```json
[
  {
    "turn": 1,
    "timestamp": "2024-12-01T10:00:00Z",
    "user_input": "我想订机票",
    "intent_recognized": "book_flight",
    "confidence": 0.92,
    "slots_filled": {},
    "system_response": "好的，请告诉我出发城市是哪里？",
    "response_type": "slot_filling",
    "processing_time_ms": 180
  },
  {
    "turn": 2,
    "timestamp": "2024-12-01T10:02:00Z",
    "user_input": "北京",
    "intent_recognized": "book_flight",
    "confidence": 0.95,
    "slots_filled": {
      "departure_city": "北京"
    },
    "system_response": "好的，从北京出发。请告诉我到达城市是哪里？",
    "response_type": "slot_filling",
    "processing_time_ms": 120
  },
  {
    "turn": 3,
    "timestamp": "2024-12-01T10:03:00Z",
    "user_input": "上海",
    "intent_recognized": "book_flight",
    "confidence": 0.93,
    "slots_filled": {
      "departure_city": "北京",
      "arrival_city": "上海"
    },
    "system_response": "北京到上海，请告诉我出发日期是哪天？",
    "response_type": "slot_filling",
    "processing_time_ms": 110
  }
]
```

## 8. 功能调用缓存

### 8.1 API调用结果缓存
**Key**: `api_result:book_flight:hash_of_params`
**TTL**: 600秒 (10分钟)
**数据结构**: String (JSON)
```json
{
  "function_name": "book_flight_api",
  "params": {
    "departure_city": "北京",
    "arrival_city": "上海",
    "departure_date": "2024-12-02",
    "passenger_count": 1,
    "seat_class": "经济舱"
  },
  "result": {
    "success": true,
    "order_id": "FL202412010001",
    "flight_number": "CA1234",
    "departure_time": "2024-12-02T08:30:00",
    "arrival_time": "2024-12-02T10:45:00",
    "price": 580.00,
    "seat": "12A"
  },
  "cached_at": "2024-12-01T10:05:00Z",
  "expires_at": "2024-12-01T10:15:00Z"
}
```

## 9. 系统配置缓存

### 9.1 RAGFLOW配置
**Key**: `ragflow_config:default`
**TTL**: 3600秒
**数据结构**: Hash
```json
{
  "config_name": "default_ragflow",
  "api_endpoint": "https://api.ragflow.com/v1/chat",
  "api_key": "ragflow_api_key_here",
  "headers": {
    "Content-Type": "application/json",
    "Authorization": "Bearer ${API_KEY}"
  },
  "timeout_seconds": 30,
  "is_active": true,
  "rate_limit": {
    "requests_per_minute": 100,
    "requests_per_hour": 1000
  }
}
```

### 9.2 系统阈值配置
**Key**: `system_config:thresholds`
**TTL**: 3600秒
**数据结构**: Hash
```json
{
  "intent_confidence_threshold": 0.7,
  "ambiguity_detection_threshold": 0.1,
  "intent_transfer_threshold": 0.1,
  "slot_confidence_threshold": 0.6,
  "session_timeout_seconds": 86400,
  "max_conversation_turns": 50,
  "max_ambiguity_candidates": 5,
  "nlu_cache_ttl": 1800,
  "api_timeout_seconds": 30,
  "max_retry_attempts": 3
}
```

## 10. 缓存更新策略

### 10.1 配置更新通知
**Key**: `config_update:notifications`
**TTL**: 300秒
**数据结构**: List
```json
[
  {
    "type": "intent_config",
    "action": "update",
    "target": "book_flight",
    "timestamp": "2024-12-01T10:00:00Z",
    "version": 2
  },
  {
    "type": "slot_config",
    "action": "create",
    "target": "book_flight.passenger_type",
    "timestamp": "2024-12-01T10:05:00Z",
    "version": 1
  }
]
```

### 10.2 缓存失效标记
**Key**: `cache_invalidation:intent_config`
**TTL**: 60秒
**数据结构**: Set
```
{
  "book_flight",
  "check_balance"
}
```

## 11. 性能监控缓存

### 11.1 API性能统计
**Key**: `performance:api:book_flight_api`
**TTL**: 3600秒
**数据结构**: Hash
```json
{
  "total_calls": 156,
  "success_calls": 152,
  "failed_calls": 4,
  "avg_response_time": 450.5,
  "max_response_time": 1200,
  "min_response_time": 180,
  "last_call_at": "2024-12-01T10:05:00Z",
  "error_rate": 0.026
}
```

### 11.2 用户行为统计
**Key**: `stats:user_behavior:daily:20241201`
**TTL**: 86400秒
**数据结构**: Hash
```json
{
  "total_sessions": 1250,
  "total_conversations": 3800,
  "intent_distribution": {
    "book_flight": 850,
    "check_balance": 600,
    "book_hotel": 350
  },
  "avg_conversation_length": 3.2,
  "completion_rate": 0.85,
  "ambiguity_rate": 0.12,
  "fallback_rate": 0.08
}
```

## 12. Prompt模板配置缓存

### 12.1 意图识别模板
**Key**: `template_config:intent_recognition:1`
**TTL**: 3600秒
**数据结构**: Hash
```json
{
  "template_id": 1,
  "template_name": "book_flight_intent_recognition",
  "template_type": "intent_recognition",
  "intent_id": 1,
  "template_content": "根据用户输入识别是否为机票预订意图:\n用户输入: {user_input}\n上下文: {context}\n请判断意图并返回JSON格式结果: {\"intent\": \"intent_name\", \"confidence\": 0.95}",
  "variables": ["user_input", "context"],
  "version": "1.0",
  "is_active": true,
  "created_at": "2024-12-01T10:00:00Z",
  "updated_at": "2024-12-01T10:00:00Z"
}
```

### 12.2 槽位提取模板
**Key**: `template_config:slot_extraction:1`
**TTL**: 3600秒
**数据结构**: Hash
```json
{
  "template_id": 2,
  "template_name": "flight_slot_extraction",
  "template_type": "slot_extraction",
  "intent_id": 1,
  "template_content": "从用户输入中提取机票预订相关槽位:\n用户输入: {user_input}\n需要提取的槽位: {slot_definitions}\n请返回JSON格式结果: {\"slots\": {\"departure_city\": \"北京\", \"arrival_city\": \"上海\"}}",
  "variables": ["user_input", "slot_definitions"],
  "version": "1.1",
  "is_active": true,
  "created_at": "2024-12-01T10:00:00Z",
  "updated_at": "2024-12-01T12:00:00Z"
}
```

### 12.3 歧义澄清模板
**Key**: `template_config:disambiguation:global`
**TTL**: 3600秒
**数据结构**: Hash
```json
{
  "template_id": 3,
  "template_name": "global_disambiguation",
  "template_type": "disambiguation",
  "intent_id": null,
  "template_content": "用户输入存在歧义，请选择您的意图:\n{ambiguous_options}\n请回复数字选择或直接描述您的需求",
  "variables": ["ambiguous_options"],
  "version": "1.0",
  "is_active": true,
  "created_at": "2024-12-01T10:00:00Z",
  "updated_at": "2024-12-01T10:00:00Z"
}
```

## 13. 安全配置缓存

### 13.1 系统安全配置
**Key**: `security_config:system`
**TTL**: 7200秒
**数据结构**: Hash
```json
{
  "jwt_expiry_hours": 24,
  "max_retry_times": 3,
  "rate_limit_per_minute": 100,
  "session_timeout_minutes": 30,
  "enable_ip_whitelist": true,
  "allowed_ips": ["192.168.1.0/24", "10.0.0.0/8"],
  "encryption_key": "encrypted_key_hash",
  "audit_log_enabled": true,
  "security_level": "high",
  "updated_at": "2024-12-01T10:00:00Z"
}
```

### 13.2 用户权限缓存
**Key**: `security_config:user_permissions:admin123`
**TTL**: 3600秒
**数据结构**: Hash
```json
{
  "user_id": "admin123",
  "role": "admin",
  "permissions": [
    "intent.create",
    "intent.read",
    "intent.update",
    "intent.delete",
    "template.create",
    "template.read",
    "template.update",
    "template.delete",
    "system.monitor",
    "audit.read"
  ],
  "ip_restrictions": ["192.168.1.0/24"],
  "session_limit": 5,
  "expires_at": "2024-12-02T10:00:00Z"
}
```

## 14. 审计日志缓存

### 14.1 最近操作日志
**Key**: `audit_log:recent:admin123`
**TTL**: 900秒
**数据结构**: List
```json
[
  {
    "log_id": "log_20241201_001",
    "user_id": "admin123",
    "operation": "update",
    "resource_type": "intent",
    "resource_id": "1",
    "old_value": {"confidence_threshold": 0.8},
    "new_value": {"confidence_threshold": 0.85},
    "timestamp": "2024-12-01T10:00:00Z",
    "ip_address": "192.168.1.100",
    "user_agent": "Mozilla/5.0...",
    "status": "success"
  },
  {
    "log_id": "log_20241201_002",
    "user_id": "admin123",
    "operation": "create",
    "resource_type": "template",
    "resource_id": "3",
    "old_value": null,
    "new_value": {"template_name": "new_disambiguation"},
    "timestamp": "2024-12-01T10:05:00Z",
    "ip_address": "192.168.1.100",
    "user_agent": "Mozilla/5.0...",
    "status": "success"
  }
]
```

## 15. RAGFLOW状态缓存

### 15.1 RAGFLOW健康状态
**Key**: `ragflow_status:health`
**TTL**: 300秒
**数据结构**: Hash
```json
{
  "service_status": "active",
  "last_health_check": "2024-12-01T10:05:00Z",
  "response_time_ms": 150,
  "success_rate_24h": 0.98,
  "error_count_1h": 2,
  "consecutive_failures": 0,
  "next_check_at": "2024-12-01T10:10:00Z",
  "endpoints": {
    "chat": {
      "status": "healthy",
      "last_check": "2024-12-01T10:05:00Z",
      "response_time_ms": 145
    },
    "health": {
      "status": "healthy",
      "last_check": "2024-12-01T10:05:00Z",
      "response_time_ms": 25
    }
  }
}
```

### 15.2 RAGFLOW调用结果缓存
**Key**: `ragflow_result:hash_of_input`
**TTL**: 600秒
**数据结构**: Hash
```json
{
  "input_text": "今天天气真好啊",
  "input_hash": "xyz789abc123",
  "ragflow_response": "是的，今天确实是个好天气！不过我们还是回到刚才的话题吧，您需要什么帮助？",
  "response_type": "small_talk_with_context_return",
  "processing_time_ms": 180,
  "confidence": 0.92,
  "cached_at": "2024-12-01T10:05:00Z",
  "context_maintained": true,
  "fallback_used": false
}
```

### 15.3 RAGFLOW频率限制状态
**Key**: `ragflow_rate_limit:user123`
**TTL**: 60秒
**数据结构**: Hash
```json
{
  "requests_this_minute": 12,
  "requests_this_hour": 145,
  "last_request_at": "2024-12-01T10:05:00Z",
  "rate_limit_hit": false,
  "reset_time_minute": "2024-12-01T10:06:00Z",
  "reset_time_hour": "2024-12-01T11:00:00Z"
}
```

## 16. 异步任务缓存

### 16.1 异步任务状态
**Key**: `async_task:task_20241201_001`
**TTL**: 3600秒
**数据结构**: Hash
```json
{
  "task_id": "task_20241201_001",
  "task_type": "api_call",
  "status": "processing",
  "conversation_id": 12345,
  "user_id": "user123",
  "request_data": {
    "function_name": "book_flight_api",
    "params": {
      "departure_city": "北京",
      "arrival_city": "上海",
      "departure_date": "2024-12-02"
    }
  },
  "progress": 65.5,
  "estimated_completion": "2024-12-01T10:08:00Z",
  "created_at": "2024-12-01T10:05:00Z",
  "updated_at": "2024-12-01T10:06:30Z",
  "retry_count": 0,
  "max_retries": 3
}
```

### 16.2 用户异步任务队列
**Key**: `async_tasks:user123`
**TTL**: 86400秒
**数据结构**: List
```json
[
  {
    "task_id": "task_20241201_001",
    "task_type": "api_call",
    "status": "processing",
    "created_at": "2024-12-01T10:05:00Z",
    "priority": "normal"
  },
  {
    "task_id": "task_20241201_002",
    "task_type": "ragflow_call",
    "status": "pending",
    "created_at": "2024-12-01T10:06:00Z",
    "priority": "low"
  }
]
```

### 16.3 异步任务结果
**Key**: `async_result:task_20241201_001`
**TTL**: 1800秒
**数据结构**: Hash
```json
{
  "task_id": "task_20241201_001",
  "status": "completed",
  "result_data": {
    "success": true,
    "order_id": "FL202412010001",
    "flight_number": "CA1234",
    "price": 580.00,
    "message": "机票预订成功！"
  },
  "processing_time_ms": 2400,
  "completed_at": "2024-12-01T10:07:24Z",
  "notification_sent": true
}
```

## 17. 性能优化缓存

### 17.1 系统性能指标
**Key**: `performance:system:realtime`
**TTL**: 60秒
**数据结构**: Hash
```json
{
  "cpu_usage": 65.4,
  "memory_usage": 78.2,
  "active_connections": 234,
  "requests_per_second": 45.6,
  "average_response_time": 180.5,
  "cache_hit_rate": 0.89,
  "database_connections": 12,
  "ragflow_availability": 0.98,
  "async_queue_size": 8,
  "error_rate_5min": 0.02,
  "last_updated": "2024-12-01T10:06:00Z"
}
```

### 17.2 缓存性能统计
**Key**: `performance:cache:stats`
**TTL**: 300秒
**数据结构**: Hash
```json
{
  "total_requests": 15420,
  "cache_hits": 13724,
  "cache_misses": 1696,
  "hit_rate": 0.89,
  "avg_hit_time_ms": 2.3,
  "avg_miss_time_ms": 25.7,
  "expired_keys": 245,
  "evicted_keys": 12,
  "memory_usage_mb": 256.7,
  "last_reset": "2024-12-01T09:00:00Z"
}
```