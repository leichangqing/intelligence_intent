# 智能意图识别系统

基于FastAPI的智能意图识别系统，支持无状态B2B设计、混合Prompt Template配置、RAGFLOW集成等高级功能。

## 技术栈

- **Web框架**: FastAPI
- **数据库**: MySQL
- **ORM**: Peewee
- **缓存**: Redis
- **AI/NLU**: LangChain + LLM
- **实体识别**: Duckling
- **监控**: Prometheus

## 项目结构

```
app711/
├── src/
│   ├── main.py                 # FastAPI应用入口
│   ├── config/                 # 配置管理
│   │   ├── __init__.py
│   │   ├── settings.py         # 系统配置
│   │   └── database.py         # 数据库配置
│   ├── models/                 # 数据模型层 (Peewee ORM)
│   │   ├── __init__.py
│   │   ├── base.py            # 基础模型
│   │   ├── intent.py          # 意图相关模型
│   │   ├── slot.py            # 槽位相关模型
│   │   ├── conversation.py     # 对话相关模型
│   │   ├── function_call.py   # 功能调用模型
│   │   ├── template.py        # 模板配置模型
│   │   └── audit.py           # 审计日志模型
│   ├── services/              # 业务逻辑层
│   │   ├── __init__.py
│   │   ├── intent_service.py  # 意图识别服务
│   │   ├── slot_service.py    # 槽位管理服务
│   │   ├── conversation_service.py  # 对话管理服务
│   │   ├── nlu_service.py     # NLU处理服务
│   │   ├── function_service.py # 功能调用服务
│   │   ├── ragflow_service.py # RAGFLOW集成服务
│   │   └── cache_service.py   # 缓存服务
│   ├── api/                   # API接口层
│   │   ├── __init__.py
│   │   ├── v1/                # API v1版本
│   │   │   ├── __init__.py
│   │   │   ├── chat.py        # 对话接口
│   │   │   ├── admin.py       # 管理接口
│   │   │   ├── analytics.py   # 分析接口
│   │   │   └── health.py      # 健康检查
│   │   ├── dependencies.py    # FastAPI依赖
│   │   ├── middleware.py      # 中间件
│   │   └── exceptions.py      # 异常处理
│   ├── schemas/               # Pydantic数据验证模型
│   │   ├── __init__.py
│   │   ├── chat.py           # 对话相关Schema
│   │   ├── admin.py          # 管理相关Schema
│   │   └── common.py         # 通用Schema
│   ├── utils/                # 工具类
│   │   ├── __init__.py
│   │   ├── logger.py         # 日志工具
│   │   ├── security.py       # 安全工具
│   │   ├── validation.py     # 验证工具
│   │   └── helpers.py        # 辅助函数
│   └── core/                 # 核心组件
│       ├── __init__.py
│       ├── nlu_engine.py     # NLU引擎
│       ├── template_engine.py # 模板引擎
│       ├── cache_manager.py  # 缓存管理器
│       └── event_bus.py      # 事件总线
├── tests/                    # 测试
│   ├── __init__.py
│   ├── test_api/            # API测试
│   ├── test_services/       # 服务测试
│   └── test_models/         # 模型测试
├── docs/                    # 文档
├── requirements.txt         # Python依赖
├── docker-compose.yml       # Docker编排
├── Dockerfile              # Docker镜像
└── .env.example            # 环境变量示例
```

## 快速开始

### 1. 环境准备

```bash
# 克隆项目
git clone <repository>
cd app711

# 创建虚拟环境
python -m venv venv
source venv/bin/activate  # Linux/Mac
# 或 venv\Scripts\activate  # Windows

# 安装依赖
pip install -r requirements.txt
```

### 2. 配置环境

```bash
# 复制环境配置
cp .env.example .env

# 编辑配置文件
vim .env
```

### 3. 启动服务

```bash
# 启动依赖服务（MySQL + Redis）
docker-compose up -d mysql redis

# 初始化数据库
python -m src.models.init_db

# 启动应用
uvicorn src.main:app --reload --host 0.0.0.0 --port 8000
```

### 4. 访问应用

- API文档: http://localhost:8000/docs
- 健康检查: http://localhost:8000/api/v1/health
- 管理接口: http://localhost:8000/api/v1/admin/

## 核心功能

### 智能意图识别
- 基于LangChain + LLM的高精度意图识别
- 支持意图歧义检测和澄清
- 混合Prompt Template配置策略

### 槽位管理
- 智能槽位提取和验证
- 支持跨意图槽位继承
- Duckling实体标准化

### 对话流程
- 无状态B2B设计
- 意图转移和打岔处理
- 上下文感知管理

### 外部集成
- 条件式API调用
- RAGFLOW无缝集成
- 异步任务处理

### 性能优化
- Redis多层缓存
- 响应时间<2s
- 支持水平扩展

## 开发指南

### 添加新意图
1. 在`models/intent.py`中定义数据模型
2. 在`services/intent_service.py`中添加业务逻辑
3. 在`api/v1/admin.py`中暴露管理接口
4. 更新数据库架构和缓存策略

### API开发
- 使用FastAPI路由装饰器
- 遵循RESTful设计原则
- 使用Pydantic进行数据验证
- 添加完整的错误处理

### 测试
```bash
# 运行所有测试
pytest

# 运行特定测试
pytest tests/test_api/

# 生成覆盖率报告
pytest --cov=src tests/
```