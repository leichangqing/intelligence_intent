# TASK-029: 重试和错误处理功能文档

## 概述

本文档描述了智能意图识别系统中函数调用服务的重试和错误处理功能。该功能为函数调用提供了强大的容错能力，包括智能重试、熔断器、错误统计和健康检查等特性。

## 主要特性

### 1. 智能重试机制
- **指数退避**: 支持指数退避算法，避免系统过载
- **随机抖动**: 添加随机延迟，防止惊群效应
- **自定义重试策略**: 支持基于异常类型和错误消息的重试决策
- **可配置重试次数**: 支持全局和函数级别的重试配置

### 2. 熔断器模式
- **故障检测**: 自动检测连续失败
- **服务降级**: 在故障达到阈值时自动熔断
- **自动恢复**: 支持半开状态和自动恢复机制
- **可配置参数**: 支持自定义故障阈值和恢复时间

### 3. 错误统计和监控
- **实时统计**: 记录成功率、错误率、平均响应时间
- **错误分类**: 按错误类型分类统计
- **历史记录**: 保存最近的错误信息和时间
- **健康检查**: 提供函数健康状态评估

### 4. 增强的错误处理
- **详细错误信息**: 包含错误类型、堆栈跟踪信息
- **错误上下文**: 保留执行上下文信息
- **重试计数**: 记录重试次数和执行时间

## 核心组件

### FunctionRetryConfig
重试配置类，定义重试行为：

```python
class FunctionRetryConfig:
    def __init__(self, 
                 max_attempts: int = 3,           # 最大重试次数
                 base_delay: float = 1.0,         # 基础延迟
                 max_delay: float = 60.0,         # 最大延迟
                 backoff_factor: float = 2.0,     # 退避因子
                 retry_exceptions: List[type] = None,  # 重试异常类型
                 retry_on_status: List[int] = None,    # 重试状态码
                 jitter: bool = True,             # 是否添加抖动
                 circuit_breaker: bool = False):  # 是否启用熔断器
```

### CircuitBreaker
熔断器实现：

```python
class CircuitBreaker:
    def __init__(self, 
                 failure_threshold: int = 5,      # 失败阈值
                 recovery_timeout: float = 60.0,  # 恢复超时
                 expected_exception: type = Exception):
```

### FunctionExecutionResult
增强的执行结果类：

```python
class FunctionExecutionResult:
    def __init__(self, 
                 success: bool,
                 result: Any = None,
                 error: str = None,
                 execution_time: float = 0.0,
                 metadata: Dict = None,
                 retry_count: int = 0,            # 重试次数
                 error_type: str = None,          # 错误类型
                 traceback_info: str = None):     # 堆栈跟踪
```

## 使用示例

### 1. 基本重试配置

```python
from src.services.function_service import FunctionService, FunctionRetryConfig

# 创建服务
function_service = FunctionService(cache_service)

# 配置重试策略
retry_config = FunctionRetryConfig(
    max_attempts=3,
    base_delay=1.0,
    backoff_factor=2.0,
    jitter=True
)

# 设置函数重试配置
function_service.set_function_retry_config("my_function", retry_config)

# 执行函数（自动重试）
result = await function_service.execute_function("my_function", {"param": "value"})
```

### 2. 启用熔断器

```python
# 启用熔断器
function_service.enable_circuit_breaker(
    "my_function", 
    failure_threshold=5,    # 5次失败后熔断
    recovery_timeout=60.0   # 60秒后尝试恢复
)

# 检查熔断器状态
status = function_service.get_circuit_breaker_status("my_function")
print(f"熔断器状态: {status}")
```

### 3. 错误统计和监控

```python
# 获取函数错误统计
stats = function_service.get_function_error_stats("my_function")
print(f"成功率: {stats['success_calls'] / stats['total_calls']:.2%}")

# 健康检查
health = await function_service.health_check_function("my_function")
print(f"健康状态: {health['status']}, 健康分数: {health['health_score']}")
```

### 4. 自定义重试策略

```python
# 自定义重试异常
retry_config = FunctionRetryConfig(
    max_attempts=5,
    retry_exceptions=[ConnectionError, TimeoutError, ValueError],
    retry_on_status=[500, 502, 503, 504, 429]
)

# 基于错误消息的重试
function_service.set_function_retry_config("api_call", retry_config)
```

## API 接口

### 配置管理

```python
# 设置函数重试配置
function_service.set_function_retry_config(function_name: str, config: FunctionRetryConfig)

# 设置全局重试配置
function_service.set_global_retry_config(config: FunctionRetryConfig)

# 获取函数重试配置
config = function_service.get_function_retry_config(function_name: str)
```

### 熔断器管理

```python
# 启用熔断器
function_service.enable_circuit_breaker(function_name: str, failure_threshold: int, recovery_timeout: float)

# 禁用熔断器
function_service.disable_circuit_breaker(function_name: str)

# 获取熔断器状态
status = function_service.get_circuit_breaker_status(function_name: str)

# 重置熔断器
function_service.reset_circuit_breaker(function_name: str)
```

### 统计和监控

```python
# 获取函数错误统计
stats = function_service.get_function_error_stats(function_name: str)

# 获取所有错误统计
all_stats = function_service.get_all_error_stats()

# 清除错误统计
function_service.clear_error_stats(function_name: str = None)

# 健康检查
health = await function_service.health_check_function(function_name: str)
```

## 重试策略

### 指数退避
默认使用指数退避算法：
```
delay = base_delay * (backoff_factor ^ attempt)
```

### 随机抖动
为避免惊群效应，添加随机抖动：
```
final_delay = delay + random(0, delay * 0.1)
```

### 重试判断
系统会根据以下条件判断是否重试：
1. 异常类型在重试列表中
2. 网络相关异常（ConnectionError, TimeoutError等）
3. 错误消息包含特定关键词（timeout, connection, unavailable等）

## 熔断器状态

### 状态转换
- **Closed**: 正常状态，允许请求通过
- **Open**: 熔断状态，拒绝所有请求
- **Half-Open**: 半开状态，允许少量请求测试服务恢复

### 状态机
```
Closed -> Open: 失败次数达到阈值
Open -> Half-Open: 超过恢复时间
Half-Open -> Closed: 请求成功
Half-Open -> Open: 请求失败
```

## 监控指标

### 函数级统计
- `total_calls`: 总调用次数
- `success_calls`: 成功调用次数
- `error_calls`: 错误调用次数
- `avg_execution_time`: 平均执行时间
- `error_types`: 错误类型统计
- `last_success_time`: 最后成功时间
- `last_error_time`: 最后错误时间

### 错误类型统计
- `count`: 错误次数
- `last_message`: 最后错误消息
- `last_time`: 最后错误时间

### 健康分数计算
```python
health_score = max(0, 100 - (error_rate * 100))
```

健康状态分级：
- `healthy`: 分数 > 70
- `degraded`: 分数 30-70
- `unhealthy`: 分数 < 30

## 配置最佳实践

### 1. 重试配置建议
- **API调用**: 3-5次重试，指数退避
- **数据库操作**: 2-3次重试，固定延迟
- **文件操作**: 1-2次重试，线性延迟

### 2. 熔断器配置建议
- **高可用服务**: 失败阈值3-5，恢复时间30-60秒
- **外部API**: 失败阈值5-10，恢复时间60-120秒
- **批处理任务**: 失败阈值10-20，恢复时间300-600秒

### 3. 监控配置建议
- 定期检查健康状态
- 设置告警阈值（如错误率>10%）
- 记录关键指标到监控系统

## 测试用例

系统提供了完整的测试用例，包括：

1. **基本重试测试**: 测试重试机制是否正常工作
2. **熔断器测试**: 测试熔断器状态转换
3. **异步超时测试**: 测试异步函数的超时重试
4. **健康检查测试**: 测试健康状态计算
5. **错误统计测试**: 测试统计数据的准确性

运行测试：
```bash
python test_retry_handling.py
```

## 注意事项

1. **资源管理**: 重试会增加系统负载，需要合理配置
2. **幂等性**: 确保重试的函数是幂等的
3. **超时设置**: 合理设置超时时间，避免长时间等待
4. **日志记录**: 重试过程会产生大量日志，注意日志级别
5. **统计数据**: 定期清理统计数据，避免内存泄漏

## 扩展功能

### 自定义重试策略
可以通过继承 `FunctionRetryConfig` 实现自定义重试策略：

```python
class CustomRetryConfig(FunctionRetryConfig):
    def should_retry(self, exception: Exception, attempt: int) -> bool:
        # 自定义重试逻辑
        return custom_logic(exception, attempt)
```

### 插件化错误处理
支持注册错误处理插件：

```python
def custom_error_handler(exception: Exception, context: dict) -> bool:
    # 自定义错误处理逻辑
    return should_retry

function_service.register_error_handler(custom_error_handler)
```

## 总结

重试和错误处理功能为函数调用服务提供了强大的容错能力，通过智能重试、熔断器、错误统计等机制，显著提高了系统的可靠性和可用性。合理的配置和监控可以确保系统在各种异常情况下都能稳定运行。