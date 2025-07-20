# 测试文件组织说明

本目录包含了按照TASK编号重新组织的测试文件。这些文件原本分散在app711根目录下，现在按照项目路线图中的任务序号进行了重命名和归类。

## 文件映射说明

### 阶段2：核心功能层测试

#### NLU引擎实现
- `TASK-013_test_confidence_thresholds.py` - 置信度计算和阈值处理测试
- `TASK-014_test_slot_extraction_validation.py` - 槽位提取和验证逻辑测试
- `TASK-015_test_dependency_runner.py` - 槽位依赖关系处理测试
- `TASK-016_test_slot_inheritance.py` - 槽位继承机制测试
- `TASK-017_test_slot_questioning.py` - 槽位询问生成逻辑测试

#### 对话管理服务
- `TASK-018_test_session_context.py` - 会话上下文管理测试
- `TASK-019_test_intent_stack.py` - 意图栈管理测试
- `TASK-019_test_simple_intent_stack.py` - 简化意图栈测试
- `TASK-020_test_intent_transfer.py` - 意图转移逻辑测试

### 阶段3：业务功能层测试

#### 意图处理完善
- `TASK-023_test_ambiguity_detection.py` - 歧义检测和处理测试
- `TASK-024_test_user_choice_parsing.py` - 用户选择解析测试
- `TASK-025_test_intent_confirmation.py` - 意图确认机制测试

#### 函数调用服务
- `TASK-026_test_dynamic_function_registration.py` - 动态函数注册系统测试
- `TASK-027_test_api_wrapper.py` - API包装器实现测试
- `TASK-029_test_retry_error_handling.py` - 重试和错误处理测试

#### RAGFLOW集成
- `TASK-030_test_ragflow_service.py` - RAGFLOW服务完整实现测试
- `TASK-031_test_knowledge_base_query.py` - 知识库查询逻辑测试
- `TASK-032_test_fallback_mechanism.py` - 回退机制实现测试
- `TASK-032_test_fallback_quick.py` - 快速回退测试
- `TASK-032_test_fallback_simple.py` - 简化回退测试
- `TASK-033_test_config_management.py` - 配置管理优化测试
- `TASK-033_test_config_simple.py` - 简化配置管理测试

### 阶段4：API接口层测试

#### 核心API实现
- `TASK-034_test_chat_interface.py` - 聊天交互接口完善测试
- `TASK-035_test_ambiguity_resolution_interface.py` - 歧义解决接口实现测试
- `TASK-036_test_error_handling_standardization.py` - 错误处理和响应标准化测试
- `TASK-037_test_middleware_security.py` - 中间件和安全验证测试

#### 管理API实现
- `TASK-040_test_health_check_interface.py` - 健康检查接口测试
- `TASK-040_test_health_simple.py` - 简化健康检查测试

### 阶段5：测试与优化

#### 集成测试
- `TASK-046_test_complete_conversation_flow.py` - 完整对话流程测试

#### 示例验证
- `TASK-050_test_flight_booking_scenario.py` - 订机票场景端到端测试
- `TASK-051_test_balance_inquiry_scenario.py` - 查余额场景端到端测试
- `TASK-052_test_complex_interaction_scenario.py` - 复杂交互场景测试
- `TASK-053_test_stress_optimization.py` - 压力测试和优化

### 阶段6：部署准备

#### 容器化部署
- `TASK-054_test_docker_optimization.py` - Docker配置优化测试

## 文件命名规则

所有测试文件都遵循以下命名规则：
```
TASK-{编号}_test_{功能描述}.py
```

其中：
- `{编号}` - 对应项目路线图中的任务编号（001-061）
- `{功能描述}` - 简短的英文功能描述，使用下划线分隔

## 执行说明

这些测试文件可以独立执行，也可以按照任务顺序批量执行：

```bash
# 执行单个任务的测试
python -m pytest tasks/test_files/TASK-016_test_slot_inheritance.py

# 执行某个阶段的所有测试
python -m pytest tasks/test_files/TASK-01*_test_*.py

# 执行所有组织后的测试
python -m pytest tasks/test_files/
```

## 注意事项

1. **依赖关系**: 某些测试可能依赖其他组件，请确保相关服务已启动
2. **环境配置**: 执行前请确保测试环境配置正确
3. **数据准备**: 部分测试需要初始化测试数据
4. **顺序执行**: 建议按照任务编号顺序执行测试，以确保依赖关系正确

## 原始文件对照

| 原始文件名 | 新文件名 | 对应任务 |
|-----------|----------|----------|
| test_confidence_simple.py | TASK-013_test_confidence_thresholds.py | TASK-013 |
| test_slot_system.py | TASK-014_test_slot_extraction_validation.py | TASK-014 |
| test_dependency_runner.py | TASK-015_test_dependency_runner.py | TASK-015 |
| test_task016_inheritance.py | TASK-016_test_slot_inheritance.py | TASK-016 |
| test_task017_questioning.py | TASK-017_test_slot_questioning.py | TASK-017 |
| test_task018_conversation_context.py | TASK-018_test_session_context.py | TASK-018 |
| test_task019_intent_stack.py | TASK-019_test_intent_stack.py | TASK-019 |
| test_simple_intent_stack.py | TASK-019_test_simple_intent_stack.py | TASK-019 |
| test_task020_intent_transfer.py | TASK-020_test_intent_transfer.py | TASK-020 |
| test_task_023.py | TASK-023_test_ambiguity_detection.py | TASK-023 |
| test_task_024.py | TASK-024_test_user_choice_parsing.py | TASK-024 |
| test_task_025.py | TASK-025_test_intent_confirmation.py | TASK-025 |
| test_task_026.py | TASK-026_test_dynamic_function_registration.py | TASK-026 |
| test_task_027.py | TASK-027_test_api_wrapper.py | TASK-027 |
| test_retry_handling.py | TASK-029_test_retry_error_handling.py | TASK-029 |
| test_ragflow_service.py | TASK-030_test_ragflow_service.py | TASK-030 |
| test_intelligent_query.py | TASK-031_test_knowledge_base_query.py | TASK-031 |
| test_fallback_system.py | TASK-032_test_fallback_mechanism.py | TASK-032 |
| test_fallback_quick.py | TASK-032_test_fallback_quick.py | TASK-032 |
| test_fallback_simple.py | TASK-032_test_fallback_simple.py | TASK-032 |
| test_config_management_system.py | TASK-033_test_config_management.py | TASK-033 |
| test_config_simple.py | TASK-033_test_config_simple.py | TASK-033 |
| test_enhanced_chat.py | TASK-034_test_chat_interface.py | TASK-034 |
| test_ambiguity_resolution.py | TASK-035_test_ambiguity_resolution_interface.py | TASK-035 |
| test_error_handling.py | TASK-036_test_error_handling_standardization.py | TASK-036 |
| test_security_system.py | TASK-037_test_middleware_security.py | TASK-037 |
| test_health_check.py | TASK-040_test_health_check_interface.py | TASK-040 |
| test_health_simple.py | TASK-040_test_health_simple.py | TASK-040 |
| test_complete_integration.py | TASK-046_test_complete_conversation_flow.py | TASK-046 |
| test_flight_booking_task050.py | TASK-050_test_flight_booking_scenario.py | TASK-050 |
| test_balance_inquiry_task051.py | TASK-051_test_balance_inquiry_scenario.py | TASK-051 |
| test_complex_interaction_task052.py | TASK-052_test_complex_interaction_scenario.py | TASK-052 |
| test_stress_optimization_task053.py | TASK-053_test_stress_optimization.py | TASK-053 |
| test_docker_optimization_task054.py | TASK-054_test_docker_optimization.py | TASK-054 |

---

*文件组织完成时间: 2024-01-01*
*总计移动文件数: 35个*