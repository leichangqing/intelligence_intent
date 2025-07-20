# 智能意图识别系统 API 文档

## 概览

本文档提供了智能意图识别系统的完整API接口说明。系统基于FastAPI构建，提供了93个API端点，支持智能对话、意图识别、槽位填充、歧义解决等核心功能。

### 基本信息

- **基础URL**: `/api/v1`
- **认证方式**: JWT Token / API Key
- **文档格式**: OpenAPI 3.0
- **交互式文档**: 
  - Swagger UI: `/docs`
  - ReDoc: `/redoc`
  - OpenAPI Schema: `/openapi.json`

### 通用响应格式

```json
{
  "success": true,
  "message": "操作成功",
  "data": {},
  "error_code": null,
  "timestamp": "2024-01-01T12:00:00Z"
}
```

## 核心API接口

### 1. 智能对话接口

#### 1.1 基础对话处理

**POST** `/api/v1/chat/interact`

智能对话核心接口，处理用户输入并返回意图识别结果。

**请求参数:**
```json
{
  "session_id": "string",
  "user_id": "string", 
  "message": "我想订一张明天去北京的机票",
  "context": {},
  "metadata": {
    "channel": "web",
    "device": "desktop"
  }
}
```

**响应示例:**
```json
{
  "success": true,
  "data": {
    "intent": "book_flight",
    "confidence": 0.95,
    "slots": {
      "destination": "北京",
      "departure_date": "2024-01-02"
    },
    "response": "我来帮您订机票。请问您从哪里出发？",
    "need_clarification": false,
    "session_id": "sess_123456"
  }
}
```

#### 1.2 歧义解决

**POST** `/api/v1/chat/disambiguate`

处理意图歧义，提供用户选择选项。

**请求参数:**
```json
{
  "session_id": "string",
  "user_choice": 1,
  "context": {}
}
```

#### 1.3 流式对话

**POST** `/api/v1/chat/stream`

支持流式响应的对话接口，适用于长时间处理场景。

**请求参数:**
```json
{
  "message": "string",
  "session_id": "string",
  "stream": true
}
```

### 2. 会话管理接口

#### 2.1 创建会话

**POST** `/api/v1/chat/session/create`

创建新的对话会话。

**请求参数:**
```json
{
  "user_id": "string",
  "context": {},
  "metadata": {}
}
```

#### 2.2 更新会话上下文

**POST** `/api/v1/chat/session/update-context`

更新会话上下文信息。

**请求参数:**
```json
{
  "session_id": "string",
  "context": {},
  "operation": "merge" // merge | replace
}
```

#### 2.3 会话分析

**GET** `/api/v1/chat/session/{session_id}/analytics`

获取会话分析数据。

**响应示例:**
```json
{
  "success": true,
  "data": {
    "session_duration": 300,
    "intent_count": 5,
    "slot_fill_rate": 0.8,
    "user_satisfaction": 4.5
  }
}
```

### 3. 歧义解决接口

#### 3.1 歧义检测

**POST** `/api/v1/ambiguity/detect`

检测用户输入中的歧义。

**请求参数:**
```json
{
  "message": "string",
  "context": {},
  "threshold": 0.7
}
```

#### 3.2 生成澄清问题

**POST** `/api/v1/ambiguity/disambiguate`

生成澄清问题帮助解决歧义。

**请求参数:**
```json
{
  "candidates": [
    {
      "intent": "book_flight",
      "confidence": 0.6
    },
    {
      "intent": "check_flight",
      "confidence": 0.5
    }
  ],
  "context": {}
}
```

#### 3.3 智能建议

**GET** `/api/v1/ambiguity/suggestions/{session_id}`

获取智能建议选项。

### 4. 系统健康检查

#### 4.1 基础健康检查

**GET** `/api/v1/health/`

基础系统健康状态检查。

**响应示例:**
```json
{
  "success": true,
  "data": {
    "status": "healthy",
    "timestamp": "2024-01-01T12:00:00Z",
    "version": "1.0.0"
  }
}
```

#### 4.2 详细健康检查

**GET** `/api/v1/health/detailed`

获取详细的系统健康状态。

**响应示例:**
```json
{
  "success": true,
  "data": {
    "overall_status": "healthy",
    "components": {
      "database": "healthy",
      "redis": "healthy",
      "nlu_engine": "healthy",
      "ragflow": "healthy"
    },
    "metrics": {
      "response_time": 150,
      "memory_usage": 0.65,
      "cpu_usage": 0.45
    }
  }
}
```

#### 4.3 依赖服务检查

**GET** `/api/v1/health/dependencies`

检查所有依赖服务状态。

### 5. 分析统计接口

#### 5.1 对话统计

**GET** `/api/v1/analytics/conversations`

获取对话历史分析数据。

**查询参数:**
- `start_date`: 开始日期
- `end_date`: 结束日期
- `user_id`: 用户ID（可选）

#### 5.2 意图统计

**GET** `/api/v1/analytics/intent-stats`

获取意图识别统计数据。

**响应示例:**
```json
{
  "success": true,
  "data": {
    "total_intents": 1000,
    "intent_distribution": {
      "book_flight": 450,
      "check_balance": 300,
      "cancel_order": 250
    },
    "accuracy_rate": 0.92,
    "avg_confidence": 0.85
  }
}
```

#### 5.3 性能指标

**GET** `/api/v1/analytics/performance`

获取系统性能指标。

#### 5.4 用户行为分析

**GET** `/api/v1/analytics/user-behavior`

获取用户行为分析数据。

### 6. 管理后台接口

#### 6.1 系统概览

**GET** `/api/v1/admin/stats/overview`

获取系统概览统计信息。

**响应示例:**
```json
{
  "success": true,
  "data": {
    "total_sessions": 5000,
    "active_users": 150,
    "avg_response_time": 200,
    "success_rate": 0.95,
    "today_conversations": 500
  }
}
```

#### 6.2 意图配置管理

**GET** `/api/v1/admin/intents`

获取意图配置列表。

**POST** `/api/v1/admin/intents`

创建新的意图配置。

**请求参数:**
```json
{
  "name": "book_flight",
  "description": "预订机票意图",
  "examples": [
    "我想订机票",
    "帮我预订一张机票"
  ],
  "slots": [
    {
      "name": "destination",
      "type": "location",
      "required": true
    }
  ]
}
```

**PUT** `/api/v1/admin/intents/{intent_id}`

更新意图配置。

**DELETE** `/api/v1/admin/intents/{intent_id}`

删除意图配置。

#### 6.3 槽位配置管理

**GET** `/api/v1/admin/intents/{intent_id}/slots`

获取意图的槽位配置。

**POST** `/api/v1/admin/intents/{intent_id}/slots`

为意图创建新槽位。

#### 6.4 函数配置管理

**GET** `/api/v1/admin/functions`

获取函数配置列表。

#### 6.5 缓存管理

**POST** `/api/v1/admin/cache/clear`

清理系统缓存。

**POST** `/api/v1/admin/cache/refresh`

刷新系统缓存。

### 7. 异步任务接口

#### 7.1 创建异步任务

**POST** `/api/v1/tasks/async`

创建异步任务。

**请求参数:**
```json
{
  "task_type": "batch_process",
  "parameters": {},
  "priority": "high"
}
```

#### 7.2 查询任务状态

**GET** `/api/v1/tasks/async/{task_id}`

查询异步任务状态。

**响应示例:**
```json
{
  "success": true,
  "data": {
    "task_id": "task_123456",
    "status": "completed",
    "progress": 100,
    "result": {},
    "created_at": "2024-01-01T12:00:00Z",
    "completed_at": "2024-01-01T12:05:00Z"
  }
}
```

#### 7.3 任务列表

**GET** `/api/v1/tasks/async`

获取异步任务列表。

#### 7.4 取消任务

**DELETE** `/api/v1/tasks/async/{task_id}`

取消异步任务。

### 8. 函数配置接口

#### 8.1 函数列表

**GET** `/api/v1/functions/`

获取函数配置列表。

#### 8.2 函数详情

**GET** `/api/v1/functions/{function_id}`

获取函数详细信息。

#### 8.3 创建函数

**POST** `/api/v1/functions/`

创建新的函数配置。

#### 8.4 测试函数

**POST** `/api/v1/functions/{function_id}/test`

测试函数执行。

### 9. 配置验证接口

#### 9.1 配置验证

**POST** `/api/v1/config/validate`

验证配置文件有效性。

#### 9.2 配置导入导出

**POST** `/api/v1/config/import`

导入配置文件。

**GET** `/api/v1/config/export`

导出配置文件。

### 10. 安全配置接口

#### 10.1 API密钥管理

**GET** `/api/v1/security/api-keys`

获取API密钥列表。

**POST** `/api/v1/security/api-keys`

创建新的API密钥。

#### 10.2 威胁检测规则

**GET** `/api/v1/security/threat-detection/rules`

获取威胁检测规则。

#### 10.3 访问控制策略

**GET** `/api/v1/security/access-control/policies`

获取访问控制策略。

### 11. 监控接口

#### 11.1 实时指标

**GET** `/api/v1/monitor/metrics/realtime`

获取实时系统指标。

#### 11.2 历史指标

**GET** `/api/v1/monitor/metrics/history`

获取历史指标数据。

#### 11.3 活跃告警

**GET** `/api/v1/monitor/alerts/active`

获取活跃告警列表。

## 错误处理

### 错误响应格式

```json
{
  "success": false,
  "message": "错误描述",
  "error_code": "INTENT_NOT_FOUND",
  "details": {},
  "timestamp": "2024-01-01T12:00:00Z"
}
```

### 常见错误码

| 错误码 | HTTP状态码 | 描述 |
|--------|------------|------|
| INVALID_REQUEST | 400 | 请求参数无效 |
| UNAUTHORIZED | 401 | 未授权访问 |
| INTENT_NOT_FOUND | 404 | 意图未找到 |
| SLOT_VALIDATION_FAILED | 422 | 槽位验证失败 |
| INTERNAL_ERROR | 500 | 内部服务器错误 |
| SERVICE_UNAVAILABLE | 503 | 服务不可用 |

## 认证方式

### JWT Token认证

在请求头中包含JWT Token：

```http
Authorization: Bearer <jwt_token>
```

### API Key认证

在请求头中包含API Key：

```http
X-API-Key: <api_key>
```

## 限流策略

- **默认限制**: 每分钟100次请求
- **高级用户**: 每分钟500次请求
- **企业用户**: 每分钟1000次请求

## SDK示例

### Python SDK示例

```python
import requests

class IntentAPIClient:
    def __init__(self, base_url, api_key):
        self.base_url = base_url
        self.headers = {"X-API-Key": api_key}
    
    def chat_interact(self, message, session_id=None):
        url = f"{self.base_url}/api/v1/chat/interact"
        data = {
            "message": message,
            "session_id": session_id
        }
        response = requests.post(url, json=data, headers=self.headers)
        return response.json()

# 使用示例
client = IntentAPIClient("http://localhost:8000", "your_api_key")
result = client.chat_interact("我想订机票")
print(result)
```

### cURL示例

```bash
# 基础对话
curl -X POST "http://localhost:8000/api/v1/chat/interact" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your_api_key" \
  -d '{
    "message": "我想订一张机票",
    "session_id": "sess_123"
  }'

# 健康检查
curl -X GET "http://localhost:8000/api/v1/health/" \
  -H "X-API-Key: your_api_key"
```

## 部署说明

### 环境要求

- Python 3.11+
- MySQL 8.0+
- Redis 6.0+
- xinference服务
- RAGFLOW服务

### 配置文件

主要配置文件位于 `config/` 目录：

- `settings.py` - 主要系统配置
- `database.py` - 数据库配置
- `redis.py` - Redis配置
- `nlu.py` - NLU引擎配置

### Docker部署

```bash
# 构建镜像
docker build -t intent-api .

# 运行容器
docker run -p 8000:8000 intent-api
```

### 健康检查

系统提供多种健康检查端点：

- `/api/v1/health/` - 基础健康检查
- `/api/v1/health/readiness` - Kubernetes就绪探针
- `/api/v1/health/liveness` - Kubernetes存活探针

## 版本信息

- **当前版本**: v1.0.0
- **API版本**: v1
- **文档版本**: 2024-01-01

## 支持与反馈

如有疑问或建议，请联系技术支持团队。

---

*此文档会随着API的更新持续维护，请关注版本变更。*