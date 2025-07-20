# 环境变量配置文档

> TASK-056: 环境变量管理 - 完整配置指南

## 概述

本文档详细说明了智能意图识别系统的环境变量配置管理，包括变量定义、安全管理、多环境支持等。

## 快速开始

### 1. 配置文件位置

环境配置文件位于 `config/` 目录下：

```
config/
├── .env.development     # 开发环境配置
├── .env.testing        # 测试环境配置
├── .env.staging        # 预发布环境配置
├── .env.production     # 生产环境配置
└── .env.example        # 配置示例文件
```

### 2. 使用环境变量管理器

```python
from src.config.env_manager import EnvironmentVariableManager, EnvironmentType

# 初始化管理器
manager = EnvironmentVariableManager()

# 加载开发环境配置
config = manager.load_environment(EnvironmentType.DEVELOPMENT)

# 获取配置值
app_name = config.variables.get('APP_NAME')
database_host = config.variables.get('DATABASE_HOST')
```

### 3. 设置主加密密钥

```bash
# 设置环境变量（推荐）
export MASTER_ENCRYPTION_KEY="your-master-encryption-key-here"

# 或在配置文件中设置
echo "MASTER_ENCRYPTION_KEY=your-master-encryption-key-here" >> .env.local
```

## 环境变量分类

### 应用配置

| 变量名 | 类型 | 必需 | 默认值 | 描述 |
|--------|------|------|--------|------|
| `APP_NAME` | string | ✅ | "智能意图识别系统" | 应用程序名称 |
| `APP_ENV` | string | ✅ | "development" | 应用环境 (development/testing/staging/production) |
| `DEBUG` | boolean | ❌ | false | 调试模式开关 |
| `LOG_LEVEL` | string | ❌ | "INFO" | 日志级别 (DEBUG/INFO/WARNING/ERROR/CRITICAL) |

### 数据库配置

| 变量名 | 类型 | 必需 | 安全级别 | 描述 |
|--------|------|------|----------|------|
| `DATABASE_HOST` | string | ✅ | PUBLIC | 数据库主机地址 |
| `DATABASE_PORT` | integer | ✅ | PUBLIC | 数据库端口 (1-65535) |
| `DATABASE_NAME` | string | ✅ | PUBLIC | 数据库名称 |
| `DATABASE_USER` | string | ✅ | CONFIDENTIAL | 数据库用户名 |
| `DATABASE_PASSWORD` | secret | ✅ | SECRET | 数据库密码 (加密存储) |

### Redis配置

| 变量名 | 类型 | 必需 | 安全级别 | 描述 |
|--------|------|------|----------|------|
| `REDIS_HOST` | string | ✅ | PUBLIC | Redis主机地址 |
| `REDIS_PORT` | integer | ❌ | PUBLIC | Redis端口 |
| `REDIS_PASSWORD` | secret | ❌ | SECRET | Redis密码 (加密存储) |

### 安全配置

| 变量名 | 类型 | 必需 | 安全级别 | 描述 |
|--------|------|------|----------|------|
| `SECRET_KEY` | secret | ✅ | SECRET | 应用密钥 (加密存储) |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | integer | ❌ | PUBLIC | 访问令牌过期时间（分钟，1-43200） |

### API配置

| 变量名 | 类型 | 必需 | 安全级别 | 描述 |
|--------|------|------|----------|------|
| `LLM_API_KEY` | secret | ❌ | SECRET | LLM API密钥 (加密存储) |
| `LLM_API_BASE` | url | ❌ | PUBLIC | LLM API基础URL |
| `RAGFLOW_API_KEY` | secret | ❌ | SECRET | RAGFLOW API密钥 (加密存储) |

### 性能配置

| 变量名 | 类型 | 必需 | 范围 | 描述 |
|--------|------|------|------|------|
| `MAX_CONCURRENT_REQUESTS` | integer | ❌ | 1-10000 | 最大并发请求数 |
| `REQUEST_TIMEOUT` | integer | ❌ | 1-300 | 请求超时时间（秒） |

## 安全管理

### 加密存储

系统自动加密以下类型的敏感变量：

- **SECRET 级别**: 自动加密存储
- **TOP_SECRET 级别**: 自动加密存储
- **类型为 SECRET**: 自动加密存储

### 安全级别

| 级别 | 描述 | 示例 |
|------|------|------|
| `PUBLIC` | 公开信息 | 应用名称、端口号 |
| `INTERNAL` | 内部信息 | 服务器主机名 |
| `CONFIDENTIAL` | 机密信息 | 用户名、配置路径 |
| `SECRET` | 秘密信息 | 密码、API密钥 |
| `TOP_SECRET` | 绝密信息 | 主密钥、证书 |

### 密钥管理最佳实践

1. **生产环境**：
   - 使用强随机密钥
   - 定期轮换密钥
   - 使用专业密钥管理服务

2. **开发环境**：
   - 使用与生产不同的密钥
   - 可以使用相对简单的密钥

3. **密钥存储**：
   - 不要在代码中硬编码密钥
   - 使用环境变量或密钥管理服务
   - 定期备份密钥

## 多环境配置

### 环境类型

| 环境 | 用途 | 特点 |
|------|------|------|
| `development` | 开发环境 | 调试开启，详细日志，宽松限制 |
| `testing` | 测试环境 | 测试数据库，模拟服务 |
| `staging` | 预发布环境 | 生产近似配置，验证部署 |
| `production` | 生产环境 | 高安全性，性能优化 |

### 环境切换

```python
# 方式1：通过环境变量
os.environ['APP_ENV'] = 'production'
config = manager.load_environment(EnvironmentType.PRODUCTION)

# 方式2：直接指定
config = manager.load_environment(EnvironmentType.STAGING)

# 方式3：自动检测
current_env = os.getenv('APP_ENV', 'development')
env_type = EnvironmentType(current_env)
config = manager.load_environment(env_type)
```

## 验证和类型检查

### 自动验证

系统会自动验证以下内容：

1. **类型验证**: 确保值符合定义的类型
2. **范围验证**: 检查数值是否在允许范围内
3. **枚举验证**: 确保值在允许的选项列表中
4. **自定义验证**: 运行自定义验证函数

### 验证示例

```python
# 端口号验证 (1-65535)
manager.validate_value('DATABASE_PORT', '3306')  # True
manager.validate_value('DATABASE_PORT', '99999') # False

# 布尔值验证
manager.validate_value('DEBUG', 'true')   # True
manager.validate_value('DEBUG', 'false')  # True
manager.validate_value('DEBUG', 'maybe')  # False

# 枚举值验证
manager.validate_value('APP_ENV', 'development')  # True
manager.validate_value('APP_ENV', 'invalid_env')  # False
```

## 使用示例

### 基本使用

```python
from src.config.env_manager import EnvironmentVariableManager, EnvironmentType

# 初始化
manager = EnvironmentVariableManager()

# 加载配置
config = manager.load_environment(EnvironmentType.PRODUCTION)

# 使用配置
database_config = {
    'host': config.variables['DATABASE_HOST'],
    'port': int(config.variables['DATABASE_PORT']),
    'user': config.variables['DATABASE_USER'],
    'password': config.variables['DATABASE_PASSWORD'],
    'database': config.variables['DATABASE_NAME']
}
```

### 高级使用

```python
# 注册自定义变量
from src.config.env_manager import EnvironmentVariable, VariableType, SecurityLevel

custom_var = EnvironmentVariable(
    name="CUSTOM_API_ENDPOINT",
    type=VariableType.URL,
    description="自定义API端点",
    required=True,
    security_level=SecurityLevel.INTERNAL,
    validator_func=lambda x: x.startswith('https://')
)
manager.register_variable(custom_var)

# 创建新环境配置
new_config = {
    'APP_NAME': '我的应用',
    'DATABASE_HOST': 'localhost',
    'SECRET_KEY': 'my-secret-key'
}
manager.save_environment_config(
    EnvironmentType.DEVELOPMENT,
    new_config,
    encrypt_secrets=True
)
```

### 配置验证

```python
# 获取验证错误
config = manager.load_environment(EnvironmentType.DEVELOPMENT)
errors = manager.get_validation_errors()
if errors:
    for error in errors:
        print(f"配置错误: {error}")

# 获取配置状态
status = manager.get_config_status()
print(f"注册变量数: {status['registered_variables']}")
print(f"验证错误数: {status['validation_errors']}")
```

## 工具和脚本

### 生成配置文件

```bash
# 生成所有环境的配置文件
python src/config/generate_env_configs.py

# 输出示例：
# ✅ 开发环境配置文件生成成功: config/.env.development
# ✅ 测试环境配置文件生成成功: config/.env.testing
# ✅ 预发布环境配置文件生成成功: config/.env.staging
# ✅ 生产环境配置文件生成成功: config/.env.production
```

### 测试配置

```bash
# 测试环境变量管理器
python src/config/test_env_manager.py

# 测试内容：
# - 环境配置加载
# - 变量验证
# - 密钥管理
# - 配置状态
# - 文档生成
```

### 生成文档

```python
from src.config.env_manager import EnvironmentVariableManager

manager = EnvironmentVariableManager()
documentation = manager.generate_documentation()
print(documentation)
```

## 故障排除

### 常见问题

1. **解密失败**
   ```
   错误: 解密失败
   解决: 确保 MASTER_ENCRYPTION_KEY 环境变量正确设置
   ```

2. **验证失败**
   ```
   错误: 变量 DATABASE_PORT 验证失败
   解决: 检查值是否为有效的端口号 (1-65535)
   ```

3. **配置文件不存在**
   ```
   错误: 配置文件不存在
   解决: 运行 generate_env_configs.py 生成配置文件
   ```

### 调试模式

```python
import logging
logging.getLogger('src.config.env_manager').setLevel(logging.DEBUG)

# 这将输出详细的调试信息
config = manager.load_environment(EnvironmentType.DEVELOPMENT)
```

## 最佳实践

### 开发阶段

1. **本地开发**:
   - 使用 `.env.development` 配置
   - 设置 `DEBUG=true`
   - 使用本地数据库和服务

2. **配置管理**:
   - 不要提交包含真实密码的配置文件
   - 使用 `.env.example` 作为模板
   - 定期更新配置文档

### 部署阶段

1. **环境隔离**:
   - 每个环境使用独立的配置
   - 生产环境使用强密码和密钥
   - 限制配置文件访问权限

2. **安全考虑**:
   - 定期轮换密钥
   - 监控配置变更
   - 备份重要配置

3. **监控运维**:
   - 记录配置加载日志
   - 设置配置验证告警
   - 定期检查配置状态

## 扩展功能

### 添加新环境变量

```python
# 定义新变量
new_var = EnvironmentVariable(
    name="NEW_FEATURE_ENABLED",
    type=VariableType.BOOLEAN,
    description="新功能开关",
    default_value=False,
    environments=[EnvironmentType.DEVELOPMENT, EnvironmentType.TESTING]
)

# 注册变量
manager.register_variable(new_var)
```

### 自定义验证器

```python
def validate_email(value):
    import re
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, value) is not None

email_var = EnvironmentVariable(
    name="ADMIN_EMAIL",
    type=VariableType.EMAIL,
    description="管理员邮箱",
    validator_func=validate_email
)
```

### 集成外部密钥管理

```python
class CustomSecretManager:
    def __init__(self, external_service):
        self.service = external_service
    
    def encrypt(self, value):
        return self.service.encrypt(value)
    
    def decrypt(self, encrypted_value):
        return self.service.decrypt(encrypted_value)

# 替换默认密钥管理器
manager.secret_manager = CustomSecretManager(external_service)
```

## 参考资料

- [环境变量管理器源码](../src/config/env_manager.py)
- [配置生成脚本](../src/config/generate_env_configs.py)
- [测试脚本](../src/config/test_env_manager.py)
- [配置示例](../config/.env.example)

---

**注意**: 本文档随系统更新，请定期检查最新版本。如有问题请联系开发团队。