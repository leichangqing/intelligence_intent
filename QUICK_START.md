# 快速开始指南

## 项目概述

智能意图识别系统v2.2是基于FastAPI + MySQL + Peewee + Redis + LangChain + Duckling技术栈构建的B2B混合架构意图识别服务，支持配置驱动的企业级对话处理。

## 🏗️ 混合架构设计核心理念

**计算层无状态 + 存储层有状态**，专为多轮对话业务场景优化：

- **计算无状态**: 每次API调用独立处理，支持水平扩展和负载均衡
- **存储有状态**: 持久化对话历史、槽位状态和会话上下文，支持智能推理
- **历史上下文**: 基于对话历史的意图识别和槽位继承
- **会话管理**: 完整的会话生命周期和状态跟踪

## 🚀 核心功能特性

- 🎯 高精度意图识别和歧义处理
- 🔧 智能槽位提取和验证 (基于slot_values表)
- 🔄 意图转移和打岔处理
- 🚀 RAGFLOW无缝集成
- ⚡ Redis多层缓存优化 (v2.2应用层事件驱动)
- 🏢 实体词典和响应类型管理
- 📊 完整的监控和日志系统
- 💬 多轮对话历史推理和上下文继承
- ⚙️ **配置驱动处理器** (intent_handlers表驱动的意图执行)
- 📝 **动态响应模板** (response_templates表管理的响应生成)
- 🏛️ **企业级业务规则** (intent_business_rules表支持的审批流程)

## 环境要求

- Python 3.11+
- MySQL 8.0+ (支持v2.2新增表结构)
- Redis 7.0+ (多层缓存架构)
- Docker & Docker Compose（可选）

## 快速启动

### 1. 克隆项目
```bash
git clone <repository>
cd intelligance_intent
```

### 2. 方式一：Docker启动（推荐）

```bash
# 复制环境配置
cp .env.example .env

# 编辑配置文件（必需）
vim .env

# 启动所有服务
make docker-up

# 或者
docker-compose up -d
```

### 3. 方式二：本地开发启动

```bash
# 创建虚拟环境
python -m venv venv
source venv/bin/activate  # Linux/Mac
# 或 venv\Scripts\activate  # Windows

# 安装依赖
make install
# 或 pip install -r requirements.txt

# 启动MySQL和Redis（如果没有Docker）
# 请确保MySQL和Redis服务正在运行
# v2.2注意：确保MySQL支持JSON字段和视图
# Redis需要支持pipeline和事务操作

# 复制配置文件
cp .env.example .env

# 编辑配置文件
vim .env

# 初始化数据库
make db-init

# 启动开发服务器
make dev
# 或 uvicorn src.main:app --reload --host 0.0.0.0 --port 8000
```

## 配置说明

### 必需配置项

在 `.env` 文件中配置以下必需项：

```bash
# 数据库配置
DATABASE_HOST=localhost
DATABASE_USER=root
DATABASE_PASSWORD=your_password
DATABASE_NAME=intent_recognition_system

# LLM配置（必需）
LLM_API_KEY=your_openai_api_key_here

# RAGFLOW配置（可选）
RAGFLOW_API_URL=https://api.ragflow.com/v1/chat
RAGFLOW_API_KEY=your_ragflow_api_key_here

# 安全配置
SECRET_KEY=your-secret-key-change-this-in-production
```

## 验证启动

### 1. 健康检查
```bash
curl http://localhost:8000/api/v1/health
```

### 2. 访问API文档
浏览器打开: http://localhost:8000/docs

### 3. 测试对话接口 (混合架构)

#### 基础对话测试
```bash
curl -X POST "http://localhost:8000/api/v1/chat/interact" \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "enterprise_user_001",
    "input": "我想订一张明天去上海的机票"
  }'
```

#补充
curl -X POST "http://localhost:8000/api/v1/chat/interact" \
  -H "Content-Type: application/json" \
  -d '{"session_id":"sess_b6d1d7b50028","user_id":"enterprise_user_001","input":"武汉"}'

#### 完整业务上下文测试
```bash
curl -X POST "http://localhost:8000/api/v1/chat/interact" \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "enterprise_user_001",
    "input": "我想订一张明天去上海的机票",
    "context": {
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
        "currency": "USD"
      }
    }
  }'
```

#### 移动端测试
```bash
curl -X POST "http://localhost:8000/api/v1/chat/interact" \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "mobile_user_002",
    "input": "查询我的账户余额",
    "context": {
      "device_info": {
        "platform": "mobile",
        "user_agent": "MobileApp/1.0 (iOS 16.4)",
        "ip_address": "10.0.0.50",
        "screen_resolution": "414x896",
        "language": "zh-CN"
      },
      "client_system_id": "mobile_app_ios",
      "request_trace_id": "mobile_req_001",
      "business_context": {
        "app_version": "1.2.3",
        "channel": "mobile"
      }
    }
  }'
```

## 系统监控

- **API文档**: http://localhost:8000/docs
- **健康检查**: http://localhost:8000/api/v1/health
- **Prometheus**: http://localhost:9090 (Docker环境)
- **Grafana**: http://localhost:3000 (Docker环境，admin/admin)

## 初始数据

系统启动后会自动创建示例数据：

### 内置意图 (配置驱动示例)
1. **book_flight** (订机票)
   - 槽位：出发城市、到达城市、出发日期、返程日期、乘客数量、座位等级
   - 处理器：mock_service (可配置为真实API)
   - 响应模板：confirmation, success, failure

2. **check_balance** (查银行卡余额)
   - 槽位：银行卡号、验证码
   - 处理器：mock_service (可配置为真实API)
   - 响应模板：confirmation, success, failure

3. **book_train** (火车票预订) - v2.2新增
   - 槽位：出发城市、到达城市、出发日期、座位类型、乘车人数
   - 处理器：配置驱动的服务调用
   - 响应模板：动态生成的确认和结果模板

4. **book_movie** (电影票预订) - v2.2新增
   - 槽位：电影名称、影院名称、观影时间、票数、座位偏好
   - 处理器：配置驱动的服务调用
   - 响应模板：动态生成的确认和结果模板

### 混合架构测试场景

#### 1. 完整信息预订 (企业用户 - 有状态对话)
```bash
curl -X POST "http://localhost:8000/api/v1/chat/interact" \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "enterprise_user_001",
    "input": "我想订一张明天从北京到上海的机票",
    "context": {
      "client_system_id": "enterprise_portal_v2.1",
      "business_context": {
        "department": "sales",
        "cost_center": "CC1001"
      }
    }
  }'
```

#### 2. 信息不完整 (槽位填充)
```bash
curl -X POST "http://localhost:8000/api/v1/chat/interact" \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "enterprise_user_002",
    "input": "我想订机票",
    "context": {
      "device_info": {
        "platform": "web"
      },
      "client_system_id": "hr_system_v1.0"
    }
  }'
```

#### 3. 意图歧义处理
```bash
curl -X POST "http://localhost:8000/api/v1/chat/interact" \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "enterprise_user_003",
    "input": "我想订票",
    "context": {
      "request_trace_id": "trace_001",
      "business_context": {
        "department": "finance"
      }
    }
  }'
```

#### 4. 移动端用户场景
```bash
curl -X POST "http://localhost:8000/api/v1/chat/interact" \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "mobile_user_001",
    "input": "查询我的银行卡余额",
    "context": {
      "device_info": {
        "platform": "mobile",
        "user_agent": "MobileApp/1.0"
      },
      "client_system_id": "mobile_banking_app"
    }
  }'
```

#### 5. 临时偏好覆盖
```bash
curl -X POST "http://localhost:8000/api/v1/chat/interact" \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "enterprise_user_004",
    "input": "帮我订个酒店",
    "context": {
      "temp_preferences": {
        "currency": "USD",
        "language": "en-US"
      },
      "business_context": {
        "cost_center": "CC2001",
        "approval_required": false
      }
    }
  }'
```

#### 6. 非意图输入 (RAGFLOW回退)
```bash
curl -X POST "http://localhost:8000/api/v1/chat/interact" \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "enterprise_user_005",
    "input": "今天天气怎么样？",
    "context": {
      "client_system_id": "customer_service_portal",
      "request_trace_id": "weather_query_001"
    }
  }'
```

#### 7. 配置驱动火车票预订 (v2.2新功能)
```bash
curl -X POST "http://localhost:8000/api/v1/chat/interact" \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "enterprise_user_006",
    "input": "我要订一张明天从北京到上海的火车票",
    "context": {
      "business_context": {
        "department": "marketing",
        "cost_center": "CC1002",
        "approval_required": false
      },
      "client_system_id": "enterprise_travel_system"
    }
  }'
```

#### 8. 配置驱动电影票预订 (v2.2新功能)
```bash
curl -X POST "http://localhost:8000/api/v1/chat/interact" \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "enterprise_user_007",
    "input": "我想订电影票看《流浪地球3》",
    "context": {
      "location": {
        "city": "北京",
        "timezone": "Asia/Shanghai"
      },
      "client_system_id": "entertainment_booking_system"
    }
  }'
```

#### 9. 测试动态响应模板
```bash
curl -X POST "http://localhost:8000/api/v1/chat/interact" \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "enterprise_user_008",
    "input": "确认",
    "session_id": "sess_existing_conversation",
    "context": {
      "client_system_id": "template_test_system"
    }
  }'
```

## 常用命令

```bash
# 查看服务状态
make status

# 查看日志
make logs

# 重启服务
make restart

# 进入应用容器
make shell

# 运行测试
make test

# 代码格式化
make format

# 备份数据库
make backup-db

# 清理临时文件
make clean
```

## 开发指南

### 添加新意图 (配置驱动模式)

1. **数据库配置**：在管理接口中添加新意图
```bash
curl -X POST "http://localhost:8000/api/v1/admin/intents" \
  -H "Content-Type: application/json" \
  -d '{
    "intent_name": "book_hotel",
    "display_name": "预订酒店",
    "description": "用户想要预订酒店",
    "confidence_threshold": 0.8,
    "examples": ["我想订酒店", "帮我预订酒店"]
  }'
```

2. **添加槽位**：为新意图添加槽位配置

3. **配置处理器** (v2.2新增)：在intent_handlers表中配置处理逻辑
```bash
# 示例：添加酒店预订处理器配置
INSERT INTO intent_handlers (intent_id, handler_type, handler_config, is_active) VALUES 
((SELECT id FROM intents WHERE intent_name = 'book_hotel'), 'api_service', 
'{"service_name": "hotel_booking_service", "api_endpoint": "https://api.hotel.com/v1/booking", "timeout_seconds": 30}', 
TRUE);
```

4. **配置响应模板** (v2.2新增)：在response_templates表中配置响应格式
```bash
# 示例：添加酒店预订确认模板
INSERT INTO response_templates (intent_id, template_type, template_content, is_active) VALUES
((SELECT id FROM intents WHERE intent_name = 'book_hotel'), 'confirmation',
'🏨 请确认您的酒店预订信息：\n\n📍 酒店名称：{hotel_name}\n📅 入住日期：{check_in_date}\n📅 退房日期：{check_out_date}\n\n以上信息是否正确？',
TRUE);
```

5. **功能调用**：配置外部API调用 (由intent_handlers表管理)

### 项目结构说明

```
src/
├── main.py                 # FastAPI应用入口
├── config/                 # 配置管理
├── models/                 # 数据模型 (Peewee)
├── services/              # 业务逻辑服务
├── api/                   # API接口路由
├── schemas/               # Pydantic验证模型
├── core/                  # 核心组件（NLU引擎等）
└── utils/                 # 工具类
```

## 故障排除

### 常见问题

0. **v2.2已修复的启动问题**
   - ✅ **Redis缓存服务未初始化警告**: 已优化服务启动顺序
   - ✅ **CacheService.generate_key方法不存在**: 已统一使用get_cache_key方法
   - ✅ **FunctionService.execute_function_call方法缺失**: 已实现功能调用执行方法
   - ✅ **ConfigDrivenIntentProcessor数据库导入错误**: 已修复配置驱动处理器的导入问题
   - ✅ **数据库初始化脚本执行顺序问题**: 已修复mysql_schemav2.3.sql的表创建顺序

1. **数据库连接失败**
   - 检查MySQL服务是否启动
   - 验证数据库配置信息
   - 确认数据库和表是否创建

2. **Redis连接失败**
   - 检查Redis服务是否启动
   - 验证Redis配置信息
   - v2.2：检查Redis是否支持pipeline和事务操作
   - **已修复**: Redis缓存服务未初始化警告（调整了启动顺序）

3. **LLM调用失败**
   - 检查API密钥是否正确
   - 验证网络连接
   - 查看API额度是否用完

4. **意图识别不准确**
   - 增加意图示例数据
   - 调整置信度阈值
   - 优化Prompt模板

### 日志查看

```bash
# Docker环境
docker-compose logs -f app

# 本地环境
tail -f logs/app.log
```

### 性能优化

1. **缓存策略v2.2**：
   - 槽位值缓存：3600秒 TTL
   - 实体词典缓存：7200秒 TTL
   - 响应类型缓存：3600秒 TTL
   - 异步日志状态：300秒 TTL
   - **意图处理器配置缓存**: 3600秒 TTL (配置驱动)
   - **响应模板缓存**: 3600秒 TTL (动态模板)
   - **业务规则缓存**: 3600秒 TTL (企业级规则)

2. **数据库优化v2.2**：
   - 使用v_active_intents和v_conversation_summary视图
   - 为新增表添加适当索引
   - 优化slot_values表查询性能

3. **连接池**：调整数据库和Redis连接池大小

4. **异步处理v2.2**：
   - 使用async_log_queue表进行日志队列管理
   - 实现事件驱动的缓存失效机制
   - 后台处理cache_invalidation_logs
   - **修复**: CacheService方法名统一使用get_cache_key

## v2.2混合架构亮点

### 1. B2B混合架构设计

**核心原则**: 计算无状态 + 存储有状态 + 配置驱动
- **API层无状态**: 每次请求独立处理，支持负载均衡和水平扩展
- **数据层有状态**: 持久化对话历史和会话状态，支持多轮推理
- **智能上下文**: 基于历史对话的意图识别和槽位继承
- **配置驱动**: intent_handlers和response_templates表驱动的业务逻辑
- **v2.2优化**: 修复了Redis缓存服务初始化顺序，消除启动警告

### 2. 配置驱动处理器架构

**重构硬编码为配置驱动**:
- **意图执行**: 从硬编码处理逻辑迁移到intent_handlers表配置
- **响应生成**: 从静态模板迁移到response_templates表动态管理
- **业务规则**: 通过intent_business_rules表支持企业级审批流程
- **槽位依赖**: slot_dependencies表管理复杂的槽位填充逻辑

### 3. 缓存优化改进

1. **数据规范化缓存**：
   - 槽位信息从conversations表迁移到slot_values表
   - 动态获取已填充/缺失槽位信息
   - 支持槽位验证状态和置信度缓存

2. **实体识别缓存**：
   - entity_types表缓存实体类型定义
   - entity_dictionary表缓存实体词典数据  
   - 支持别名和标准化形式的快速查找

3. **应用层缓存管理**：
   - 事件驱动的缓存失效机制
   - 异步日志队列处理
   - cache_invalidation_logs表跟踪失效状态

### 4. 多轮对话增强

- **会话状态管理**: 完整的会话生命周期跟踪
- **历史上下文推理**: 基于对话历史的智能决策
- **槽位继承**: 跨轮次的槽位值累积和验证

### 示例：配置驱动和缓存使用

```python
# v2.2: 获取对话的所有已填充槽位 (替代conversations.slots_filled字段)
filled_slots = await cache_service.get_conversation_filled_slots(conversation_id)
# 返回: {"departure_city": {"value": "北京", "confidence": 0.95, "is_confirmed": True}}

# 缓存实体识别结果
entity_result = await cache_service.lookup_entity("city", "北京")
# 返回: {"entity_value": "北京", "canonical_form": "北京市", "aliases": ["北京", "京城"]}

# 配置驱动处理器缓存
handler_config = await cache_service.get_intent_handlers(intent_id)
# 返回: {"handler_type": "mock_service", "handler_config": {...}, "fallback_config": {...}}

# 动态响应模板缓存
template = await cache_service.get_response_template(intent_id, "confirmation")
# 返回: {"template_content": "请确认您的预订信息...", "template_variables": [...]}

# v2.2修复：正确的缓存键生成方法
cache_key = cache_service.get_cache_key('session', session_id=session_id)
# 而不是: cache_service.generate_key()
```

## 生产部署

### Docker生产环境

```bash
# 使用生产配置启动
make deploy-prod

# 或者
docker-compose --profile production up -d
```

### 注意事项

1. **安全配置**：
   - 更换默认密钥
   - 启用HTTPS
   - 配置防火墙

2. **监控告警**：
   - 配置Prometheus告警规则
   - 设置Grafana监控面板
   - 启用日志聚合

3. **备份策略**：
   - 定期备份数据库
   - 备份配置文件
   - 建立灾备方案

## 技术支持

- 📖 详细文档：查看 `docs/` 目录
- 🐛 问题反馈：GitHub Issues
- 💬 技术交流：内部技术群