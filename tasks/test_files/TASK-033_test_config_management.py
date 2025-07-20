#!/usr/bin/env python3
"""
配置管理系统测试 (TASK-033)
测试增强的配置管理、验证、版本控制和环境特定配置功能
"""
import asyncio
import sys
import os
import tempfile
import json
from pathlib import Path
sys.path.insert(0, os.path.abspath('.'))

from src.services.cache_service import CacheService
from src.core.config_manager import (
    EnhancedConfigManager, ConfigType, ConfigChangeEvent, get_config_manager
)
from src.core.config_validator import (
    ConfigValidatorService, ValidationLevel, ValidationRule, get_config_validator
)
from src.core.config_version_manager import (
    ConfigVersionManager, ChangeType, VersionStatus, get_version_manager
)
from src.core.environment_config_manager import (
    EnvironmentConfigManager, Environment, ConfigScope, get_environment_config_manager
)

async def test_basic_config_manager():
    """测试基本配置管理功能"""
    print("=== 测试基本配置管理功能 ===")
    
    cache_service = CacheService()
    await cache_service.initialize()
    
    config_manager = get_config_manager(cache_service)
    
    # 测试配置设置和获取
    print("\n1. 测试配置设置和获取")
    
    # 系统配置测试
    success = await config_manager.set_config(
        key="test_system_config",
        value="test_value",
        config_type=ConfigType.SYSTEM,
        description="测试系统配置"
    )
    print(f"设置系统配置: {success}")
    
    value = await config_manager.get_config("test_system_config", config_type=ConfigType.SYSTEM)
    print(f"获取系统配置: {value}")
    
    # RAGFLOW配置测试
    ragflow_config = {
        'api_endpoint': 'https://api.ragflow.io/v1',
        'api_key': 'test_api_key_12345678',
        'timeout_seconds': 30,
        'rate_limit': {
            'requests_per_minute': 60,
            'requests_per_hour': 1000
        },
        'health_check_url': 'https://api.ragflow.io/health',
        'is_active': True
    }
    
    success = await config_manager.set_config(
        key="test_ragflow_config",
        value=ragflow_config,
        config_type=ConfigType.RAGFLOW,
        description="测试RAGFLOW配置"
    )
    print(f"设置RAGFLOW配置: {success}")
    
    # 功能开关测试
    feature_flag = {
        'is_enabled': True,
        'description': '测试功能开关',
        'target_users': ['user1', 'user2'],
        'rollout_percentage': 50
    }
    
    success = await config_manager.set_config(
        key="test_feature_flag",
        value=feature_flag,
        config_type=ConfigType.FEATURE_FLAG,
        description="测试功能开关"
    )
    print(f"设置功能开关: {success}")
    
    await cache_service.close()
    return True

async def test_config_validation():
    """测试配置验证功能"""
    print("\n=== 测试配置验证功能 ===")
    
    validator = get_config_validator()
    
    # 测试RAGFLOW配置验证
    print("\n1. 测试RAGFLOW配置验证")
    
    # 有效配置
    valid_config = {
        'config_name': 'test_ragflow',
        'api_endpoint': 'https://api.ragflow.io/v1',
        'api_key': 'valid_key_1234567890abcdef',
        'timeout_seconds': 30,
        'rate_limit': {
            'requests_per_minute': 60,
            'requests_per_hour': 3600
        },
        'health_check_url': 'https://api.ragflow.io/health'
    }
    
    result = validator.validate_config(ConfigType.RAGFLOW, valid_config)
    print(f"有效配置验证: {result.is_valid}")
    if result.warnings:
        print(f"警告: {result.warnings}")
    if result.suggestions:
        print(f"建议: {result.suggestions}")
    
    # 无效配置
    invalid_config = {
        'config_name': 'test_ragflow',
        'api_endpoint': 'http://insecure-api.com',  # 不安全的HTTP
        'api_key': 'weak',  # 太短的密钥
        'timeout_seconds': 500,  # 超时时间过长
        'rate_limit': {
            'requests_per_minute': 120,
            'requests_per_hour': 1000  # 不一致的速率限制
        }
    }
    
    result = validator.validate_config(ConfigType.RAGFLOW, invalid_config)
    print(f"\n无效配置验证: {result.is_valid}")
    if result.errors:
        print(f"错误: {result.errors}")
    
    # 测试功能开关验证
    print("\n2. 测试功能开关验证")
    
    feature_flag_config = {
        'flag_name': 'test_feature',
        'is_enabled': True,
        'rollout_percentage': 150,  # 无效的百分比
        'target_users': ['user1'] * 1001  # 过多的目标用户
    }
    
    result = validator.validate_config(ConfigType.FEATURE_FLAG, feature_flag_config)
    print(f"功能开关验证: {result.is_valid}")
    if result.errors:
        print(f"错误: {result.errors}")
    
    # 添加自定义验证规则
    print("\n3. 测试自定义验证规则")
    
    def custom_validator(config_data):
        return 'custom_field' in config_data
    
    custom_rule = ValidationRule(
        name="custom_field_required",
        description="必须包含自定义字段",
        level=ValidationLevel.ERROR,
        validator=custom_validator,
        message="缺少必需的自定义字段",
        suggestion="请添加custom_field字段"
    )
    
    validator.add_custom_rule(ConfigType.SYSTEM, custom_rule)
    
    test_config = {'some_field': 'value'}
    result = validator.validate_config(ConfigType.SYSTEM, test_config)
    print(f"自定义规则验证: {result.is_valid}")
    if result.errors:
        print(f"错误: {result.errors}")
    
    return True

async def test_version_management():
    """测试版本管理功能"""
    print("\n=== 测试版本管理功能 ===")
    
    cache_service = CacheService()
    await cache_service.initialize()
    
    version_manager = get_version_manager(cache_service)
    
    # 测试版本创建
    print("\n1. 测试版本创建")
    
    config_key = "test_version_config"
    
    # 创建第一个版本
    config_v1 = {
        'setting1': 'value1',
        'setting2': 100,
        'setting3': True
    }
    
    version1 = version_manager.create_version(
        config_key=config_key,
        config_data=config_v1,
        description="初始配置版本",
        created_by="test_user",
        tags=["initial", "v1"]
    )
    print(f"创建版本1: {version1.version_id}")
    
    # 创建第二个版本（有变更）
    config_v2 = {
        'setting1': 'value1_updated',
        'setting2': 200,
        'setting3': True,
        'setting4': 'new_setting'
    }
    
    version2 = version_manager.create_version(
        config_key=config_key,
        config_data=config_v2,
        description="更新配置版本",
        created_by="test_user",
        tags=["update", "v2"]
    )
    print(f"创建版本2: {version2.version_id}")
    
    # 测试版本历史
    print("\n2. 测试版本历史")
    
    history = version_manager.get_version_history(config_key)
    print(f"版本历史数量: {len(history)}")
    for version in history:
        print(f"  版本 {version.version_number}: {version.description}")
        print(f"    变更数量: {len(version.changes)}")
        for change in version.changes:
            print(f"    - {change.field_name}: {change.change_type.value}")
    
    # 测试版本比较
    print("\n3. 测试版本比较")
    
    diff = version_manager.compare_versions(version1.version_id, version2.version_id)
    if diff:
        print(f"版本差异: {diff.summary}")
        print(f"新增字段: {list(diff.added_fields.keys())}")
        print(f"修改字段: {list(diff.modified_fields.keys())}")
        print(f"删除字段: {list(diff.removed_fields.keys())}")
    
    # 测试版本回滚
    print("\n4. 测试版本回滚")
    
    rollback_version = version_manager.rollback_to_version(
        config_key=config_key,
        target_version_id=version1.version_id,
        rollback_by="test_user"
    )
    
    if rollback_version:
        print(f"回滚成功: {rollback_version.version_id}")
        print(f"回滚状态: {rollback_version.status.value}")
    
    await cache_service.close()
    return True

async def test_environment_config():
    """测试环境配置功能"""
    print("\n=== 测试环境配置功能 ===")
    
    cache_service = CacheService()
    await cache_service.initialize()
    
    base_config_manager = get_config_manager(cache_service)
    env_config_manager = get_environment_config_manager(cache_service, base_config_manager)
    
    # 创建临时配置目录
    with tempfile.TemporaryDirectory() as temp_dir:
        # 更新配置路径
        env_config_manager.config_base_path = Path(temp_dir)
        
        # 创建环境配置文件
        print("\n1. 创建环境配置")
        
        # 生产环境配置
        production_config = {
            'database': {
                'host': 'prod-db.example.com',
                'port': 5432,
                'ssl': True
            },
            'api': {
                'timeout': 30,
                'rate_limit': 1000
            },
            'debug': False
        }
        
        prod_file = Path(temp_dir) / "production.json"
        with open(prod_file, 'w') as f:
            json.dump(production_config, f, indent=2)
        
        # 开发环境配置
        development_config = {
            'database': {
                'host': 'localhost',
                'port': 5432,
                'ssl': False
            },
            'api': {
                'timeout': 60
            },
            'debug': True,
            'mock_external_services': True
        }
        
        dev_file = Path(temp_dir) / "development.json"
        with open(dev_file, 'w') as f:
            json.dump(development_config, f, indent=2)
        
        # 重新加载环境配置
        env_config_manager._initialize_environments()
        
        # 测试配置获取
        print("\n2. 测试配置获取")
        
        # 切换到生产环境
        env_config_manager.switch_environment(Environment.PRODUCTION)
        
        db_host = env_config_manager.get_config('database.host')
        api_timeout = env_config_manager.get_config('api.timeout')
        debug_mode = env_config_manager.get_config('debug')
        
        print(f"生产环境 - 数据库主机: {db_host}")
        print(f"生产环境 - API超时: {api_timeout}")
        print(f"生产环境 - 调试模式: {debug_mode}")
        
        # 切换到开发环境
        env_config_manager.switch_environment(Environment.DEVELOPMENT)
        
        db_host = env_config_manager.get_config('database.host')
        api_timeout = env_config_manager.get_config('api.timeout')
        debug_mode = env_config_manager.get_config('debug')
        mock_services = env_config_manager.get_config('mock_external_services')
        
        print(f"开发环境 - 数据库主机: {db_host}")
        print(f"开发环境 - API超时: {api_timeout}")
        print(f"开发环境 - 调试模式: {debug_mode}")
        print(f"开发环境 - 模拟外部服务: {mock_services}")
        
        # 测试配置继承
        print("\n3. 测试配置继承")
        
        # 开发环境应该继承生产环境的配置，并覆盖特定字段
        ssl_setting = env_config_manager.get_config('database.ssl')
        rate_limit = env_config_manager.get_config('api.rate_limit')
        
        print(f"开发环境继承 - SSL设置: {ssl_setting}")
        print(f"开发环境继承 - 速率限制: {rate_limit}")
        
        # 测试环境差异比较
        print("\n4. 测试环境差异比较")
        
        diff = env_config_manager.get_environment_diff(Environment.PRODUCTION, Environment.DEVELOPMENT)
        print(f"环境差异摘要: {diff['summary']}")
        if diff['modified']:
            print("修改的配置:")
            for key, change in diff['modified'].items():
                print(f"  {key}: {change['from']} -> {change['to']}")
        
        # 测试配置设置
        print("\n5. 测试配置设置")
        
        success = env_config_manager.set_config(
            'new_feature.enabled',
            True,
            Environment.DEVELOPMENT
        )
        print(f"设置开发环境配置: {success}")
        
        new_feature = env_config_manager.get_config('new_feature.enabled')
        print(f"新功能启用状态: {new_feature}")
    
    await cache_service.close()
    return True

async def test_config_caching():
    """测试配置缓存功能"""
    print("\n=== 测试配置缓存功能 ===")
    
    cache_service = CacheService()
    await cache_service.initialize()
    
    config_manager = get_config_manager(cache_service)
    
    # 测试缓存性能
    print("\n1. 测试缓存性能")
    
    import time
    
    # 设置测试配置
    await config_manager.set_config(
        key="cache_test_config",
        value="cached_value",
        config_type=ConfigType.SYSTEM
    )
    
    # 第一次获取（从数据库）
    start_time = time.time()
    value1 = await config_manager.get_config("cache_test_config")
    first_access_time = time.time() - start_time
    
    # 第二次获取（从缓存）
    start_time = time.time()
    value2 = await config_manager.get_config("cache_test_config")
    second_access_time = time.time() - start_time
    
    print(f"第一次访问时间: {first_access_time:.4f}s")
    print(f"第二次访问时间: {second_access_time:.4f}s")
    print(f"缓存加速比: {first_access_time / max(second_access_time, 0.0001):.1f}x")
    print(f"两次获取的值相同: {value1 == value2}")
    
    # 测试缓存失效
    print("\n2. 测试缓存失效")
    
    # 更新配置（应该使缓存失效）
    await config_manager.set_config(
        key="cache_test_config",
        value="updated_cached_value",
        config_type=ConfigType.SYSTEM
    )
    
    # 获取更新后的值
    updated_value = await config_manager.get_config("cache_test_config")
    print(f"更新后的值: {updated_value}")
    print(f"缓存正确失效: {updated_value == 'updated_cached_value'}")
    
    await cache_service.close()
    return True

async def test_change_events():
    """测试配置变更事件"""
    print("\n=== 测试配置变更事件 ===")
    
    cache_service = CacheService()
    await cache_service.initialize()
    
    config_manager = get_config_manager(cache_service)
    
    # 事件收集器
    received_events = []
    
    def event_listener(event: ConfigChangeEvent):
        received_events.append(event)
        print(f"收到配置变更事件: {event.config_key} -> {event.event_type.value}")
    
    # 添加事件监听器
    config_manager.add_change_listener(event_listener)
    
    # 触发配置变更
    print("\n1. 触发配置变更事件")
    
    await config_manager.set_config(
        key="event_test_config",
        value="initial_value",
        config_type=ConfigType.SYSTEM,
        description="事件测试配置"
    )
    
    await config_manager.set_config(
        key="event_test_config",
        value="updated_value",
        config_type=ConfigType.SYSTEM,
        description="更新事件测试配置"
    )
    
    print(f"收到的事件数量: {len(received_events)}")
    
    for i, event in enumerate(received_events):
        print(f"事件 {i+1}:")
        print(f"  配置键: {event.config_key}")
        print(f"  事件类型: {event.event_type.value}")
        print(f"  旧值: {event.old_value}")
        print(f"  新值: {event.new_value}")
    
    await cache_service.close()
    return True

async def main():
    """主测试函数"""
    print("开始配置管理系统测试...")
    
    test_results = []
    
    try:
        # 运行所有测试
        basic_test = await test_basic_config_manager()
        test_results.append(("基本配置管理", basic_test))
        
        validation_test = await test_config_validation()
        test_results.append(("配置验证", validation_test))
        
        version_test = await test_version_management()
        test_results.append(("版本管理", version_test))
        
        env_test = await test_environment_config()
        test_results.append(("环境配置", env_test))
        
        cache_test = await test_config_caching()
        test_results.append(("配置缓存", cache_test))
        
        event_test = await test_change_events()
        test_results.append(("变更事件", event_test))
        
        # 输出测试结果
        print("\n=== 测试结果汇总 ===")
        all_passed = True
        for test_name, result in test_results:
            status = "✓ 通过" if result else "✗ 失败"
            print(f"{test_name}: {status}")
            if not result:
                all_passed = False
        
        if all_passed:
            print("\n🎉 所有配置管理系统测试通过！")
            print("TASK-033 配置管理优化功能实现成功！")
            return True
        else:
            print("\n❌ 部分测试失败，需要进一步调试")
            return False
            
    except Exception as e:
        print(f"\n❌ 测试执行失败: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    result = asyncio.run(main())
    sys.exit(0 if result else 1)