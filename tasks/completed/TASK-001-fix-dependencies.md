# 修复依赖问题，更新requirements.txt

## 任务信息

- **任务ID**: TASK-001
- **任务名称**: 修复依赖问题，更新requirements.txt
- **创建时间**: 2024-12-01
- **最后更新**: 2024-12-01
- **状态**: completed
- **优先级**: P0
- **预估工时**: 2小时
- **实际工时**: 1.5小时
- **完成时间**: 2024-12-01

## 任务描述

### 背景
当前项目中存在多个依赖导入问题，主要是缺少必要的Python包，导致核心模块无法正常导入和运行。从流程图一致性验证结果可以看出，所有服务都因为依赖问题无法加载。

### 目标
- 解决所有依赖导入问题
- 更新requirements.txt文件，包含所有必要的包
- 确保所有核心模块可以正常导入
- 为后续开发提供稳定的依赖环境

### 范围
**包含**:
- 分析当前导入错误
- 识别缺失的依赖包
- 更新requirements.txt
- 验证依赖安装

**不包含**:
- 解决代码逻辑问题
- 功能实现
- 版本兼容性问题（独立任务处理）

## 技术要求

### 依赖项
- 无前置任务

### 涉及文件
- `requirements.txt` - 更新
- 可能需要创建 `requirements-dev.txt` - 新建

### 已识别的缺失依赖
基于错误信息分析：
1. `langchain` - NLU引擎需要
2. `aiohttp` - 异步HTTP客户端
3. `pydantic-settings` - Pydantic设置管理
4. `peewee` - ORM数据库操作
5. `redis` - Redis客户端
6. `asyncpg` - PostgreSQL异步驱动（如需要）
7. `aiomysql` - MySQL异步驱动
8. `fastapi` - Web框架
9. `uvicorn` - ASGI服务器
10. `python-multipart` - 文件上传支持
11. `python-jose` - JWT处理
12. `passlib` - 密码哈希
13. `bcrypt` - 密码加密
14. `python-dotenv` - 环境变量管理

## 实现计划

### 步骤分解
1. [ ] 分析当前导入错误，列出所有缺失的包
2. [ ] 研究每个包的作用和最新稳定版本
3. [ ] 创建完整的requirements.txt文件
4. [ ] 区分生产和开发依赖
5. [ ] 测试依赖安装
6. [ ] 验证核心模块可以导入
7. [ ] 运行基础导入测试

### 验收标准
- [ ] requirements.txt包含所有必要依赖
- [ ] `pip install -r requirements.txt`执行成功
- [ ] 所有核心模块可以正常导入
- [ ] 运行`python -c "from src.config.settings import settings; print('OK')"`成功
- [ ] 流程图一致性测试中的导入问题解决

## 依赖包分析

### Web框架相关
```
fastapi>=0.104.0
uvicorn[standard]>=0.24.0
python-multipart>=0.0.6
```

### 数据库相关  
```
peewee>=3.17.0
aiomysql>=0.2.0
asyncpg>=0.29.0  # 如果需要PostgreSQL
```

### 缓存相关
```
redis>=5.0.0
aioredis>=2.0.0
```

### AI/NLP相关
```
langchain>=0.0.350
openai>=1.3.0
httpx>=0.25.0
```

### 配置和工具
```
pydantic>=2.5.0
pydantic-settings>=2.1.0
python-dotenv>=1.0.0
python-jose[cryptography]>=3.3.0
passlib[bcrypt]>=1.7.4
```

### HTTP客户端
```
aiohttp>=3.9.0
httpx>=0.25.0
```

### 开发工具（requirements-dev.txt）
```
pytest>=7.4.0
pytest-asyncio>=0.21.0
pytest-cov>=4.1.0
black>=23.0.0
isort>=5.12.0
flake8>=6.0.0
mypy>=1.7.0
```

## 测试计划

### 导入测试
创建简单的导入测试脚本：
```python
# test_imports.py
def test_core_imports():
    try:
        from src.config.settings import settings
        from src.services.cache_service import CacheService
        from src.services.intent_service import IntentService
        from src.core.nlu_engine import NLUEngine
        print("✅ All core imports successful")
        return True
    except ImportError as e:
        print(f"❌ Import failed: {e}")
        return False

if __name__ == "__main__":
    test_core_imports()
```

### 依赖验证
```bash
# 验证关键包可用
python -c "import fastapi; print(f'FastAPI: {fastapi.__version__}')"
python -c "import langchain; print(f'LangChain: {langchain.__version__}')"  
python -c "import redis; print('Redis client OK')"
python -c "import peewee; print('Peewee ORM OK')"
```

## 参考资料

- [FastAPI依赖文档](https://fastapi.tiangolo.com/)
- [LangChain安装指南](https://python.langchain.com/docs/get_started/installation)
- [Pydantic V2迁移指南](https://docs.pydantic.dev/2.0/migration/)

## 风险评估

### 潜在问题
1. **版本冲突** - 不同包之间可能存在版本兼容性问题
2. **系统依赖** - 某些包可能需要系统级依赖
3. **网络问题** - 下载大型包可能遇到网络问题

### 缓解措施
1. 使用明确的版本号避免兼容性问题
2. 测试每个包的安装
3. 准备离线安装方案

---

**任务负责人**: Claude
**审核人**: 开发者

**注意**: 此任务是后续所有开发工作的基础，必须优先完成。