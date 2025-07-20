#!/usr/bin/env python3
"""
TASK-056: 生成环境特定配置文件的脚本
使用 EnvironmentVariableManager 生成开发、测试、预发布和生产环境的配置文件
"""
import os
import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from src.config.env_manager import EnvironmentVariableManager, EnvironmentType

def generate_development_config(manager: EnvironmentVariableManager):
    """生成开发环境配置"""
    config_variables = {
        # 应用配置
        "APP_NAME": "智能意图识别系统-开发环境",
        "APP_ENV": "development",
        "DEBUG": "true",
        "LOG_LEVEL": "DEBUG",
        
        # 数据库配置
        "DATABASE_HOST": "localhost",
        "DATABASE_PORT": "3306",
        "DATABASE_NAME": "intent_recognition_dev",
        "DATABASE_USER": "dev_user",
        "DATABASE_PASSWORD": "dev_password_123",
        
        # Redis配置
        "REDIS_HOST": "localhost",
        "REDIS_PORT": "6379",
        "REDIS_PASSWORD": "",
        
        # 安全配置
        "SECRET_KEY": "dev-secret-key-for-development-only",
        "ACCESS_TOKEN_EXPIRE_MINUTES": "60",
        
        # API配置
        "LLM_API_KEY": "EMPTY",
        "LLM_API_BASE": "http://localhost:9997/v1",
        "RAGFLOW_API_KEY": "dev_ragflow_key_here",
        
        # 性能配置
        "MAX_CONCURRENT_REQUESTS": "50",
        "REQUEST_TIMEOUT": "30"
    }
    
    return manager.save_environment_config(
        EnvironmentType.DEVELOPMENT, 
        config_variables, 
        encrypt_secrets=True
    )

def generate_testing_config(manager: EnvironmentVariableManager):
    """生成测试环境配置"""
    config_variables = {
        # 应用配置
        "APP_NAME": "智能意图识别系统-测试环境",
        "APP_ENV": "testing",
        "DEBUG": "false",
        "LOG_LEVEL": "INFO",
        
        # 数据库配置
        "DATABASE_HOST": "test-db.internal",
        "DATABASE_PORT": "3306",
        "DATABASE_NAME": "intent_recognition_test",
        "DATABASE_USER": "test_user",
        "DATABASE_PASSWORD": "test_secure_password_456",
        
        # Redis配置
        "REDIS_HOST": "test-redis.internal",
        "REDIS_PORT": "6379",
        "REDIS_PASSWORD": "test_redis_password",
        
        # 安全配置
        "SECRET_KEY": "test-secret-key-change-this-value",
        "ACCESS_TOKEN_EXPIRE_MINUTES": "120",
        
        # API配置
        "LLM_API_KEY": "test_llm_api_key",
        "LLM_API_BASE": "https://test-api.llm.com/v1",
        "RAGFLOW_API_KEY": "test_ragflow_key_here",
        
        # 性能配置
        "MAX_CONCURRENT_REQUESTS": "30",
        "REQUEST_TIMEOUT": "25"
    }
    
    return manager.save_environment_config(
        EnvironmentType.TESTING, 
        config_variables, 
        encrypt_secrets=True
    )

def generate_staging_config(manager: EnvironmentVariableManager):
    """生成预发布环境配置"""
    config_variables = {
        # 应用配置
        "APP_NAME": "智能意图识别系统-预发布环境",
        "APP_ENV": "staging",
        "DEBUG": "false",
        "LOG_LEVEL": "INFO",
        
        # 数据库配置
        "DATABASE_HOST": "staging-db.company.com",
        "DATABASE_PORT": "3306",
        "DATABASE_NAME": "intent_recognition_staging",
        "DATABASE_USER": "staging_user",
        "DATABASE_PASSWORD": "staging_secure_password_789",
        
        # Redis配置
        "REDIS_HOST": "staging-redis.company.com",
        "REDIS_PORT": "6379",
        "REDIS_PASSWORD": "staging_redis_secure_password",
        
        # 安全配置
        "SECRET_KEY": "staging-secret-key-very-secure-change-this",
        "ACCESS_TOKEN_EXPIRE_MINUTES": "480",
        
        # API配置
        "LLM_API_KEY": "staging_llm_api_key_secure",
        "LLM_API_BASE": "https://staging-api.llm.com/v1",
        "RAGFLOW_API_KEY": "staging_ragflow_key_secure",
        
        # 性能配置
        "MAX_CONCURRENT_REQUESTS": "80",
        "REQUEST_TIMEOUT": "30"
    }
    
    return manager.save_environment_config(
        EnvironmentType.STAGING, 
        config_variables, 
        encrypt_secrets=True
    )

def generate_production_config(manager: EnvironmentVariableManager):
    """生成生产环境配置"""
    config_variables = {
        # 应用配置
        "APP_NAME": "智能意图识别系统",
        "APP_ENV": "production",
        "DEBUG": "false",
        "LOG_LEVEL": "WARNING",
        
        # 数据库配置
        "DATABASE_HOST": "prod-db.company.com",
        "DATABASE_PORT": "3306",
        "DATABASE_NAME": "intent_recognition_prod",
        "DATABASE_USER": "prod_user",
        "DATABASE_PASSWORD": "PRODUCTION_SECURE_PASSWORD_REPLACE_ME",
        
        # Redis配置
        "REDIS_HOST": "prod-redis.company.com",
        "REDIS_PORT": "6379",
        "REDIS_PASSWORD": "PRODUCTION_REDIS_PASSWORD_REPLACE_ME",
        
        # 安全配置
        "SECRET_KEY": "PRODUCTION_SECRET_KEY_MUST_BE_CHANGED",
        "ACCESS_TOKEN_EXPIRE_MINUTES": "1440",
        
        # API配置
        "LLM_API_KEY": "PRODUCTION_LLM_API_KEY_REPLACE_ME",
        "LLM_API_BASE": "https://api.llm.com/v1",
        "RAGFLOW_API_KEY": "PRODUCTION_RAGFLOW_KEY_REPLACE_ME",
        
        # 性能配置
        "MAX_CONCURRENT_REQUESTS": "200",
        "REQUEST_TIMEOUT": "30"
    }
    
    return manager.save_environment_config(
        EnvironmentType.PRODUCTION, 
        config_variables, 
        encrypt_secrets=True
    )

def main():
    """主函数"""
    try:
        # 初始化环境变量管理器
        config_dir = project_root / "config"
        manager = EnvironmentVariableManager(config_dir)
        
        print("🔧 开始生成环境配置文件...")
        
        # 生成各环境配置文件
        environments = [
            ("开发环境", generate_development_config),
            ("测试环境", generate_testing_config),
            ("预发布环境", generate_staging_config),
            ("生产环境", generate_production_config)
        ]
        
        generated_files = []
        
        for env_name, generator_func in environments:
            try:
                config_file = generator_func(manager)
                generated_files.append(config_file)
                print(f"✅ {env_name}配置文件生成成功: {config_file}")
            except Exception as e:
                print(f"❌ {env_name}配置文件生成失败: {e}")
        
        print(f"\n🎉 配置文件生成完成！共生成 {len(generated_files)} 个配置文件:")
        for file_path in generated_files:
            print(f"   📄 {file_path}")
        
        print("\n📋 使用说明:")
        print("1. 请根据实际环境修改相应配置文件中的敏感信息")
        print("2. 生产环境密码和密钥必须更换为安全值")
        print("3. 配置文件中的敏感信息已自动加密存储")
        print("4. 使用 EnvironmentVariableManager.load_environment() 加载配置")
        
    except Exception as e:
        print(f"❌ 生成配置文件时发生错误: {e}")
        return 1
    
    return 0

if __name__ == "__main__":
    exit(main())