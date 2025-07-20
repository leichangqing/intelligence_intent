# 快速开始指南

## 项目概述

智能意图识别系统是基于FastAPI + MySQL + Peewee + Redis + LangChain + Duckling技术栈构建的B2B意图识别服务，支持：

- 🎯 高精度意图识别和歧义处理
- 🔧 智能槽位提取和验证
- 🔄 意图转移和打岔处理
- 🚀 RAGFLOW无缝集成
- ⚡ Redis多层缓存优化
- 📊 完整的监控和日志系统

## 环境要求

- Python 3.11+
- MySQL 8.0+
- Redis 7.0+
- Docker & Docker Compose（可选）

## 快速启动

### 1. 克隆项目
```bash
git clone <repository>
cd app711
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

### 3. 测试对话接口
```bash
curl -X POST "http://localhost:8000/api/v1/chat/interact" \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "test_user",
    "input": "我想订机票",
    "context": {
      "device_info": {
        "platform": "web"
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

### 内置意图
1. **book_flight** (订机票)
   - 槽位：出发城市、到达城市、出发日期、返程日期、乘客数量、座位等级

2. **check_balance** (查银行卡余额)
   - 槽位：银行卡号、验证码

### 测试对话示例

```bash
# 完整信息订机票
curl -X POST "http://localhost:8000/api/v1/chat/interact" \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "user123",
    "input": "我想订一张明天从北京到上海的机票"
  }'

# 信息不完整
curl -X POST "http://localhost:8000/api/v1/chat/interact" \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "user123", 
    "input": "我想订机票"
  }'

# 意图歧义
curl -X POST "http://localhost:8000/api/v1/chat/interact" \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "user123",
    "input": "我想订票"
  }'

# 非意图输入（RAGFLOW处理）
curl -X POST "http://localhost:8000/api/v1/chat/interact" \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "user123",
    "input": "今天天气怎么样？"
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

### 添加新意图

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

3. **功能调用**：配置外部API调用

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

1. **数据库连接失败**
   - 检查MySQL服务是否启动
   - 验证数据库配置信息
   - 确认数据库和表是否创建

2. **Redis连接失败**
   - 检查Redis服务是否启动
   - 验证Redis配置信息

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

1. **缓存策略**：合理设置缓存TTL
2. **数据库优化**：添加适当索引
3. **连接池**：调整数据库和Redis连接池大小
4. **异步处理**：使用后台任务处理耗时操作

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