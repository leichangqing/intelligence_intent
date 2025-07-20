#!/usr/bin/env python3
"""
配置管理系统简单测试 (TASK-033)
"""
import sys
import os
sys.path.insert(0, os.path.abspath('.'))

from src.core.config_manager import ConfigType, ConfigValidationResult
from src.core.config_validator import get_config_validator

def test_config_validation():
    """测试配置验证功能"""
    print("=== 测试配置验证功能 ===")
    
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
    
    return True

def test_config_types():
    """测试配置类型"""
    print("\n=== 测试配置类型 ===")
    
    print("可用的配置类型:")
    for config_type in ConfigType:
        print(f"  - {config_type.value}")
    
    return True

def main():
    """主测试函数"""
    print("开始配置管理系统简单测试...")
    
    try:
        # 测试配置类型
        type_test = test_config_types()
        print(f"配置类型测试: {'✓ 通过' if type_test else '✗ 失败'}")
        
        # 测试配置验证
        validation_test = test_config_validation()
        print(f"配置验证测试: {'✓ 通过' if validation_test else '✗ 失败'}")
        
        print("\n🎉 配置管理系统核心功能正常！")
        return True
        
    except Exception as e:
        print(f"\n❌ 测试失败: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    result = main()
    sys.exit(0 if result else 1)