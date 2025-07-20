# API接口规范

## 1. 基础信息

### 1.1 服务地址
- **开发环境**: http://localhost:8000
- **测试环境**: https://api-test.intent-system.com
- **生产环境**: https://api.intent-system.com

### 1.2 认证方式
- **JWT Token**: 用于用户身份认证
- **API Key**: 用于系统间调用认证

### 1.3 无状态设计说明
- **架构特点**: B2B架构下采用无状态设计，每次请求都是独立的业务处理
- **请求特点**: 前端系统发送完整的用户输入，无需多轮对话
- **意图处理**: 系统基于单次请求进行意图识别和业务处理
- **状态管理**: 前端系统负责业务状态管理，意图系统不维持用户状态

### 1.4 通用响应格式
```json
{
  "success": true,
  "code": 200,
  "message": "Success",
  "data": {},
  "timestamp": "2024-12-01T10:00:00Z",
  "request_id": "req_20241201_001"
}
```

### 1.5 安全性设计
- **输入校验**: 所有输入进行sanitization防注入攻击
- **JWT认证**: 使用JWT Token进行用户身份认证
- **数据加密**: 敏感数据传输和存储加密
- **权限控制**: 基于角色的访问控制(RBAC)
- **审计日志**: 记录所有配置变更和敏感操作

## 2. 核心对话接口

### 2.1 智能对话处理
**接口**: `POST /api/v1/chat/interact`
**描述**: 处理用户输入，执行意图识别、槽位填充和响应生成

**参数说明**:
- `user_id`: 用户标识符，用于用户上下文和个性化分析
- `input`: 用户输入的完整文本内容
- `context`: 请求上下文信息（设备信息、位置信息等）

**无状态意图识别**:
系统基于单次请求进行意图识别和处理：
- 分析用户输入的意图类型
- 从缓存中加载意图定义和配置
- 执行意图匹配和槽位提取
- 直接返回处理结果或调用外部API

#### 请求参数
```json
{
  "user_id": "user123",
  "input": "我想订一张明天从北京到上海的机票",
  "context": {
    "device_info": {
      "platform": "web",
      "user_agent": "Mozilla/5.0..."
    }
  }
}
```

#### 响应格式
```json
{
  "success": true,
  "code": 200,
  "message": "Success",
  "data": {
    "response": "好的，已为您查询到明天从北京到上海的机票，价格为1200元。是否需要预订？",
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
    "status": "completed",
    "response_type": "api_result",
    "next_action": "none",
    "api_result": {
      "flight_info": {
        "flight_number": "CA123",
        "price": 1200,
        "departure_time": "08:00",
        "arrival_time": "10:30"
      }
    },
    "processing_time_ms": 250,
    "message_type": "intent_request"
  },
  "timestamp": "2024-12-01T10:00:00Z",
  "request_id": "req_20241201_001"
}
```

#### cURL示例
```bash
curl -X POST "http://localhost:8000/api/v1/chat/interact" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..." \
  -d '{
    "user_id": "user123",
    "input": "我想订一张明天从北京到上海的机票",
    "context": {
      "device_info": {
        "platform": "web",
        "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
      }
    }
  }'
```

### 2.2 不同意图类型处理示例
**注意**: 所有意图请求均使用同一接口 `POST /api/v1/chat/interact`

**描述**: 系统自动分析用户输入并返回相应的意图识别结果

#### 2.2.1 意图歧义处理示例

**请求参数**
```json
{
  "user_id": "user123",
  "input": "我想订机票或者酒店",
  "context": {
    "device_info": {
      "platform": "web",
      "user_agent": "Mozilla/5.0..."
    }
  }
}
```

**响应示例**
```json
{
  "success": true,
  "code": 200,
  "message": "Success",
  "data": {
    "response": "请选择您需要的服务：\n1. 机票预订\n2. 酒店预订",
    "intent": null,
    "confidence": 0.0,
    "status": "ambiguous",
    "response_type": "disambiguation",
    "next_action": "user_choice",
    "ambiguous_intents": [
      {"intent": "book_flight", "confidence": 0.85},
      {"intent": "book_hotel", "confidence": 0.83}
    ],
    "message_type": "ambiguous_intent",
    "processing_time_ms": 180
  }
}
```

#### 2.2.2 槽位不完整的意图处理示例

**请求参数**
```json
{
  "user_id": "user123",
  "input": "我想订机票",
  "context": {
    "device_info": {
      "platform": "web",
      "user_agent": "Mozilla/5.0..."
    }
  }
}
```

**响应示例**
```json
{
  "success": true,
  "code": 200,
  "message": "Success",
  "data": {
    "response": "请提供以下信息以便为您查询机票：\n1. 出发城市\n2. 目的地城市\n3. 出发日期",
    "intent": "book_flight",
    "confidence": 0.95,
    "slots": {},
    "status": "incomplete",
    "response_type": "slot_prompt",
    "next_action": "collect_missing_slots",
    "missing_slots": ["departure_city", "arrival_city", "departure_date"],
    "message_type": "incomplete_intent",
    "processing_time_ms": 200
  }
}
```

#### cURL示例
```bash
curl -X POST "http://localhost:8000/api/v1/chat/interact" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..." \
  -d '{
    "user_id": "user123",
    "input": "1",
    "context": {
      "device_info": {
        "platform": "web",
        "user_agent": "Mozilla/5.0..."
      }
    }
  }'
```

## 3. 配置管理接口

### 3.1 意图配置管理

#### 3.1.1 获取意图列表
**接口**: `GET /api/v1/admin/intents`
**描述**: 获取所有意图配置

#### cURL示例
```bash
curl -X GET "http://localhost:8000/api/v1/admin/intents" \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
```

#### 3.1.2 创建意图配置
**接口**: `POST /api/v1/admin/intents`
**描述**: 创建新的意图配置

#### 请求参数
```json
{
  "intent_name": "book_hotel",
  "display_name": "预订酒店",
  "description": "用户想要预订酒店的意图",
  "confidence_threshold": 0.8,
  "priority": 5,
  "examples": [
    "我想订酒店",
    "帮我预订酒店",
    "找个酒店住"
  ]
}
```

#### cURL示例
```bash
curl -X POST "http://localhost:8000/api/v1/admin/intents" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..." \
  -d '{
    "intent_name": "book_hotel",
    "display_name": "预订酒店",
    "description": "用户想要预订酒店的意图",
    "confidence_threshold": 0.8,
    "priority": 5,
    "examples": [
      "我想订酒店",
      "帮我预订酒店",
      "找个酒店住"
    ]
  }'
```

#### 3.1.3 更新意图配置
**接口**: `PUT /api/v1/admin/intents/{intent_id}`
**描述**: 更新指定意图配置

#### cURL示例
```bash
curl -X PUT "http://localhost:8000/api/v1/admin/intents/1" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..." \
  -d '{
    "display_name": "机票预订",
    "confidence_threshold": 0.85,
    "examples": [
      "我想订机票",
      "帮我订张机票",
      "我要买机票",
      "预订航班"
    ]
  }'
```

#### 3.1.4 删除意图配置
**接口**: `DELETE /api/v1/admin/intents/{intent_id}`
**描述**: 删除指定意图配置

#### cURL示例
```bash
curl -X DELETE "http://localhost:8000/api/v1/admin/intents/1" \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
```

### 3.2 槽位配置管理

#### 3.2.1 获取槽位列表
**接口**: `GET /api/v1/admin/intents/{intent_id}/slots`
**描述**: 获取指定意图的槽位配置

#### cURL示例
```bash
curl -X GET "http://localhost:8000/api/v1/admin/intents/1/slots" \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
```

#### 3.2.2 创建槽位配置
**接口**: `POST /api/v1/admin/intents/{intent_id}/slots`
**描述**: 为指定意图创建新的槽位配置

#### 请求参数
```json
{
  "slot_name": "hotel_city",
  "slot_type": "TEXT",
  "is_required": true,
  "validation_rules": {
    "min_length": 2,
    "max_length": 20
  },
  "prompt_template": "请告诉我您要在哪个城市订酒店？",
  "examples": ["北京", "上海", "广州"]
}
```

#### cURL示例
```bash
curl -X POST "http://localhost:8000/api/v1/admin/intents/1/slots" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..." \
  -d '{
    "slot_name": "hotel_city",
    "slot_type": "TEXT",
    "is_required": true,
    "validation_rules": {
      "min_length": 2,
      "max_length": 20
    },
    "prompt_template": "请告诉我您要在哪个城市订酒店？",
    "examples": ["北京", "上海", "广州"]
  }'
```

### 3.3 功能调用配置管理

#### 3.3.1 获取功能调用配置
**接口**: `GET /api/v1/admin/intents/{intent_id}/function-calls`
**描述**: 获取指定意图的功能调用配置

#### cURL示例
```bash
curl -X GET "http://localhost:8000/api/v1/admin/intents/1/function-calls" \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
```

### 3.4 Prompt Template管理

#### 3.4.1 获取模板列表
**接口**: `GET /api/v1/admin/templates`
**描述**: 获取所有prompt template配置

#### 请求参数
- **查询参数**:
  - template_type (string): 模板类型 (intent_recognition, slot_extraction, disambiguation)
  - intent_id (integer): 特定意图ID
  - is_active (boolean): 是否激活

#### cURL示例
```bash
curl -X GET "http://localhost:8000/api/v1/admin/templates?template_type=intent_recognition&is_active=true" \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
```

#### 3.4.2 创建模板配置
**接口**: `POST /api/v1/admin/templates`
**描述**: 创建新的prompt template配置

#### 请求参数
```json
{
  "template_name": "book_flight_intent_recognition",
  "template_type": "intent_recognition",
  "intent_id": 1,
  "template_content": "根据用户输入识别是否为机票预订意图:\n用户输入: {user_input}\n请判断意图并返回JSON格式结果",
  "variables": ["user_input"],
  "version": "1.0",
  "is_active": true,
  "description": "机票预订意图识别专用模板"
}
```

#### cURL示例
```bash
curl -X POST "http://localhost:8000/api/v1/admin/templates" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..." \
  -d '{
    "template_name": "book_flight_intent_recognition",
    "template_type": "intent_recognition",
    "intent_id": 1,
    "template_content": "根据用户输入识别是否为机票预订意图:\n用户输入: {user_input}\n请判断意图并返回JSON格式结果",
    "variables": ["user_input"],
    "version": "1.0",
    "is_active": true,
    "description": "机票预订意图识别专用模板"
  }'
```

#### 3.4.3 更新模板配置
**接口**: `PUT /api/v1/admin/templates/{template_id}`
**描述**: 更新指定prompt template配置

#### 3.4.4 版本管理
**接口**: `GET /api/v1/admin/templates/{template_id}/versions`
**描述**: 获取模板的所有版本历史

#### 3.4.5 A/B测试配置
**接口**: `POST /api/v1/admin/templates/{template_id}/ab-test`
**描述**: 配置模板A/B测试

#### 请求参数
```json
{
  "test_name": "intent_recognition_optimization",
  "version_a": "1.0",
  "version_b": "1.1",
  "traffic_split": 0.5,
  "test_duration_days": 7
}
```

#### 3.3.2 创建功能调用配置
**接口**: `POST /api/v1/admin/intents/{intent_id}/function-calls`
**描述**: 为指定意图创建功能调用配置

#### 请求参数
```json
{
  "function_name": "book_hotel_api",
  "api_endpoint": "https://api.hotel.com/v1/booking",
  "http_method": "POST",
  "headers": {
    "Content-Type": "application/json",
    "Authorization": "Bearer ${API_TOKEN}"
  },
  "param_mapping": {
    "hotel_city": "city",
    "check_in_date": "checkin",
    "check_out_date": "checkout",
    "room_count": "rooms"
  },
  "retry_times": 3,
  "timeout_seconds": 30,
  "success_template": "酒店预订成功！订单号：${order_id}，酒店：${hotel_name}。",
  "error_template": "酒店预订失败：${error_message}，请稍后重试。"
}
```

#### cURL示例
```bash
curl -X POST "http://localhost:8000/api/v1/admin/intents/1/function-calls" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..." \
  -d '{
    "function_name": "book_hotel_api",
    "api_endpoint": "https://api.hotel.com/v1/booking",
    "http_method": "POST",
    "headers": {
      "Content-Type": "application/json",
      "Authorization": "Bearer ${API_TOKEN}"
    },
    "param_mapping": {
      "hotel_city": "city",
      "check_in_date": "checkin",
      "check_out_date": "checkout",
      "room_count": "rooms"
    },
    "retry_times": 3,
    "timeout_seconds": 30,
    "success_template": "酒店预订成功！订单号：${order_id}，酒店：${hotel_name}。",
    "error_template": "酒店预订失败：${error_message}，请稍后重试。"
  }'
```

## 4. 分析和监控接口

### 4.1 对话历史查询
**接口**: `GET /api/v1/analytics/conversations`
**描述**: 查询对话历史记录

#### 请求参数
- **查询参数**:
  - user_id (string): 用户ID
  - request_id (string): 请求标识符，用于查询特定请求的处理记录
  - intent (string): 意图名称
  - start_date (string): 开始日期
  - end_date (string): 结束日期
  - page (int): 页码
  - size (int): 每页大小

#### cURL示例
```bash
curl -X GET "http://localhost:8000/api/v1/analytics/conversations?user_id=user123&intent=book_flight&start_date=2024-12-01&end_date=2024-12-02&page=1&size=10" \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
```

### 4.2 意图识别统计
**接口**: `GET /api/v1/analytics/intent-stats`
**描述**: 获取意图识别统计数据

#### 请求参数
- **查询参数**:
  - date_range (string): 日期范围 (today, week, month)
  - intent (string): 特定意图名称
  - group_by (string): 分组方式 (day, hour, intent)

#### cURL示例
```bash
curl -X GET "http://localhost:8000/api/v1/analytics/intent-stats?date_range=week&group_by=day" \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
```

### 4.3 系统性能监控
**接口**: `GET /api/v1/analytics/performance`
**描述**: 获取系统性能指标

#### cURL示例
```bash
curl -X GET "http://localhost:8000/api/v1/analytics/performance" \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
```

## 5. 系统管理接口

### 5.1 缓存管理
**接口**: `POST /api/v1/admin/cache/refresh`
**描述**: 刷新系统缓存

#### 请求参数
```json
{
  "cache_types": ["intent_config", "slot_config", "function_config"],
  "force_refresh": true
}
```

#### cURL示例
```bash
curl -X POST "http://localhost:8000/api/v1/admin/cache/refresh" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..." \
  -d '{
    "cache_types": ["intent_config", "slot_config", "function_config"],
    "force_refresh": true
  }'
```

### 5.2 系统健康检查
**接口**: `GET /api/v1/health`
**描述**: 检查系统各组件健康状态

#### cURL示例
```bash
curl -X GET "http://localhost:8000/api/v1/health"
```

### 5.3 RAGFLOW配置管理
**接口**: `PUT /api/v1/admin/ragflow/config`
**描述**: 更新RAGFLOW集成配置

#### 请求参数
```json
{
  "config_name": "default_ragflow",
  "api_endpoint": "https://api.ragflow.com/v1/chat",
  "api_key": "new_api_key_here",
  "headers": {
    "Content-Type": "application/json",
    "Authorization": "Bearer ${API_KEY}"
  },
  "timeout_seconds": 30,
  "is_active": true
}
```

#### cURL示例
```bash
curl -X PUT "http://localhost:8000/api/v1/admin/ragflow/config" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..." \
  -d '{
    "config_name": "default_ragflow",
    "api_endpoint": "https://api.ragflow.com/v1/chat",
    "api_key": "new_api_key_here",
    "headers": {
      "Content-Type": "application/json",
      "Authorization": "Bearer ${API_KEY}"
    },
    "timeout_seconds": 30,
    "is_active": true
  }'
```

### 5.4 审计日志管理
**接口**: `GET /api/v1/admin/audit-logs`
**描述**: 获取系统审计日志

#### 请求参数
- **查询参数**:
  - user_id (string): 操作用户ID
  - operation_type (string): 操作类型 (create, update, delete)
  - resource_type (string): 资源类型 (intent, slot, template, function_call)
  - start_date (string): 开始时间
  - end_date (string): 结束时间
  - page (int): 页码
  - size (int): 每页大小

#### cURL示例
```bash
curl -X GET "http://localhost:8000/api/v1/admin/audit-logs?operation_type=update&resource_type=intent&page=1&size=20" \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
```

### 5.5 安全配置管理
**接口**: `PUT /api/v1/admin/security/config`
**描述**: 更新系统安全配置

#### 请求参数
```json
{
  "jwt_expiry_hours": 24,
  "max_retry_times": 3,
  "rate_limit_per_minute": 100,
  "session_timeout_minutes": 30,
  "enable_ip_whitelist": true,
  "allowed_ips": ["192.168.1.0/24", "10.0.0.0/8"]
}
```

#### cURL示例
```bash
curl -X PUT "http://localhost:8000/api/v1/admin/security/config" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..." \
  -d '{
    "jwt_expiry_hours": 24,
    "max_retry_times": 3,
    "rate_limit_per_minute": 100,
    "session_timeout_minutes": 30,
    "enable_ip_whitelist": true,
    "allowed_ips": ["192.168.1.0/24", "10.0.0.0/8"]
  }'
```

### 5.6 异步任务管理

#### 5.6.1 创建异步任务
**接口**: `POST /api/v1/tasks/async`
**描述**: 创建新的异步任务

#### 请求参数
```json
{
  "task_type": "api_call",
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
  "priority": "normal",
  "estimated_duration_seconds": 30
}
```

#### 响应示例
```json
{
  "success": true,
  "code": 201,
  "message": "Task created successfully",
  "data": {
    "task_id": "task_20241201_001",
    "status": "pending",
    "estimated_completion": "2024-12-01T10:08:00Z",
    "created_at": "2024-12-01T10:05:00Z"
  }
}
```

#### cURL示例
```bash
curl -X POST "http://localhost:8000/api/v1/tasks/async" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..." \
  -d '{
    "task_type": "api_call",
    "conversation_id": 12345,
    "user_id": "user123",
    "request_data": {
      "function_name": "book_flight_api",
      "params": {
        "departure_city": "北京",
        "arrival_city": "上海",
        "departure_date": "2024-12-02"
      }
    }
  }'
```

#### 5.6.2 查询异步任务状态
**接口**: `GET /api/v1/tasks/async/{task_id}`
**描述**: 查询指定异步任务的状态

#### 响应示例
```json
{
  "success": true,
  "code": 200,
  "message": "Success",
  "data": {
    "task_id": "task_20241201_001",
    "task_type": "api_call",
    "status": "processing",
    "progress": 65.5,
    "estimated_completion": "2024-12-01T10:08:00Z",
    "created_at": "2024-12-01T10:05:00Z",
    "updated_at": "2024-12-01T10:06:30Z",
    "result_data": null,
    "error_message": null
  }
}
```

#### cURL示例
```bash
curl -X GET "http://localhost:8000/api/v1/tasks/async/task_20241201_001" \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
```

#### 5.6.3 获取用户异步任务列表
**接口**: `GET /api/v1/tasks/async`
**描述**: 获取指定用户的异步任务列表

#### 请求参数
- **查询参数**:
  - user_id (string): 用户ID
  - status (string): 任务状态 (pending, processing, completed, failed, cancelled)
  - task_type (string): 任务类型
  - page (int): 页码
  - size (int): 每页大小

#### cURL示例
```bash
curl -X GET "http://localhost:8000/api/v1/tasks/async?user_id=user123&status=processing&page=1&size=10" \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
```

#### 5.6.4 取消异步任务
**接口**: `DELETE /api/v1/tasks/async/{task_id}`
**描述**: 取消指定的异步任务

#### cURL示例
```bash
curl -X DELETE "http://localhost:8000/api/v1/tasks/async/task_20241201_001" \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
```

### 5.7 RAGFLOW健康检查

#### 5.7.1 RAGFLOW服务状态
**接口**: `GET /api/v1/admin/ragflow/health`
**描述**: 检查RAGFLOW服务健康状态

#### 响应示例
```json
{
  "success": true,
  "code": 200,
  "message": "Success",
  "data": {
    "service_status": "healthy",
    "last_health_check": "2024-12-01T10:05:00Z",
    "response_time_ms": 150,
    "success_rate_24h": 0.98,
    "error_count_1h": 2,
    "consecutive_failures": 0,
    "endpoints": {
      "chat": {
        "status": "healthy",
        "response_time_ms": 145
      },
      "health": {
        "status": "healthy",
        "response_time_ms": 25
      }
    }
  }
}
```

#### cURL示例
```bash
curl -X GET "http://localhost:8000/api/v1/admin/ragflow/health" \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
```

#### 5.7.2 触发RAGFLOW健康检查
**接口**: `POST /api/v1/admin/ragflow/health-check`
**描述**: 手动触发RAGFLOW健康检查

#### cURL示例
```bash
curl -X POST "http://localhost:8000/api/v1/admin/ragflow/health-check" \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
```

### 5.8 安全审计管理

#### 5.8.1 获取安全审计日志
**接口**: `GET /api/v1/admin/security/audit-logs`
**描述**: 获取安全相关的审计日志

#### 请求参数
- **查询参数**:
  - user_id (string): 用户ID
  - ip_address (string): IP地址
  - action_type (string): 操作类型 (login, logout, api_call, config_change, security_violation)
  - risk_level (string): 风险等级 (low, medium, high, critical)
  - start_date (string): 开始时间
  - end_date (string): 结束时间
  - page (int): 页码
  - size (int): 每页大小

#### cURL示例
```bash
curl -X GET "http://localhost:8000/api/v1/admin/security/audit-logs?risk_level=high&action_type=security_violation&page=1&size=20" \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
```

#### 5.8.2 IP白名单管理
**接口**: `PUT /api/v1/admin/security/ip-whitelist`
**描述**: 更新IP白名单配置

#### 请求参数
```json
{
  "enable_whitelist": true,
  "allowed_ips": [
    "192.168.1.0/24",
    "10.0.0.0/8",
    "172.16.0.100"
  ],
  "block_unknown_ips": true
}
```

#### cURL示例
```bash
curl -X PUT "http://localhost:8000/api/v1/admin/security/ip-whitelist" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..." \
  -d '{
    "enable_whitelist": true,
    "allowed_ips": ["192.168.1.0/24", "10.0.0.0/8"]
  }'
```

#### 5.8.3 安全告警配置
**接口**: `PUT /api/v1/admin/security/alerts`
**描述**: 配置安全告警规则

#### 请求参数
```json
{
  "failed_login_threshold": 5,
  "suspicious_ip_threshold": 10,
  "rate_limit_violation_threshold": 3,
  "enable_auto_block": true,
  "block_duration_minutes": 60,
  "notification_emails": ["admin@company.com", "security@company.com"]
}
```

#### cURL示例
```bash
curl -X PUT "http://localhost:8000/api/v1/admin/security/alerts" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..." \
  -d '{
    "failed_login_threshold": 5,
    "enable_auto_block": true
  }'
```
```

### 5.9 性能监控接口

#### 5.9.1 系统性能指标
**接口**: `GET /api/v1/admin/performance/metrics`
**描述**: 获取系统实时性能指标

#### 响应示例
```json
{
  "success": true,
  "code": 200,
  "message": "Success",
  "data": {
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
}
```

#### cURL示例
```bash
curl -X GET "http://localhost:8000/api/v1/admin/performance/metrics" \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
```

#### 5.9.2 缓存性能统计
**接口**: `GET /api/v1/admin/performance/cache`
**描述**: 获取Redis缓存性能统计

#### 响应示例
```json
{
  "success": true,
  "code": 200,
  "message": "Success",
  "data": {
    "total_requests": 15420,
    "cache_hits": 13724,
    "cache_misses": 1696,
    "hit_rate": 0.89,
    "avg_hit_time_ms": 2.3,
    "avg_miss_time_ms": 25.7,
    "memory_usage_mb": 256.7,
    "expired_keys": 245,
    "evicted_keys": 12
  }
}
```

#### cURL示例
```bash
curl -X GET "http://localhost:8000/api/v1/admin/performance/cache" \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
```

## 6. 错误响应格式

### 6.1 通用错误响应
```json
{
  "success": false,
  "code": 400,
  "message": "Bad Request",
  "error": {
    "type": "ValidationError",
    "details": "Missing required field: user_id",
    "field": "user_id"
  },
  "timestamp": "2024-12-01T10:00:00Z",
  "request_id": "req_20241201_001"
}
```

### 6.2 常见错误码
- **400**: 请求参数错误
- **401**: 未授权访问
- **403**: 权限不足
- **404**: 资源不存在
- **429**: 请求频率限制
- **500**: 服务器内部错误
- **503**: 服务不可用

## 7. 请求限制和配额

### 7.1 频率限制
- **用户级别**: 每分钟100次请求
- **会话级别**: 每分钟20次请求
- **API Key级别**: 每分钟1000次请求

### 7.2 并发限制
- **单用户**: 最多5个并发请求
- **单会话**: 最多1个并发请求
- **系统级**: 最多1000个并发请求

### 7.3 数据大小限制
- **请求体**: 最大1MB
- **用户输入**: 最大1000字符
- **响应体**: 最大5MB

## 8. SDK和集成示例

### 8.1 JavaScript SDK示例
```javascript
import { IntentRecognitionClient } from '@intent-system/js-sdk';

const client = new IntentRecognitionClient({
  apiKey: 'your-api-key',
  baseUrl: 'https://api.intent-system.com'
});

// 发送用户输入
const response = await client.chat.interact({
  userId: 'user123',
  input: '我想订机票',
  context: {
    device_info: {
      platform: 'web'
    }
  }
});

console.log(response.data);
```

### 8.2 Python SDK示例
```python
from intent_system import IntentRecognitionClient

client = IntentRecognitionClient(
    api_key='your-api-key',
    base_url='https://api.intent-system.com'
)

# 发送用户输入
response = client.chat.interact(
    user_id='user123',
    input='我想订机票',
    context={
        'device_info': {
            'platform': 'web'
        }
    }
)

print(response.data)
```

## 9. Webhook集成

### 9.1 事件通知
**接口**: `POST /api/v1/webhooks/events`
**描述**: 接收系统事件通知

#### 事件类型
- **intent_recognized**: 意图识别成功
- **slot_filled**: 槽位填充完成
- **api_called**: API调用完成
- **request_completed**: 请求处理完成
- **error_occurred**: 错误发生

#### 请求格式
```json
{
  "event_type": "intent_recognized",
  "timestamp": "2024-12-01T10:00:00Z",
  "data": {
    "user_id": "user123",
    "request_id": "req_20241201_001",
    "intent": "book_flight",
    "confidence": 0.95,
    "slots": {}
  }
}
```