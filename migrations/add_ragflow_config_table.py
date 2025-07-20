#!/usr/bin/env python3
"""
数据库迁移脚本：创建RAGFLOW配置表
TASK-030: RAGFLOW服务完整实现
"""
import sys
import os
sys.path.insert(0, os.path.abspath('.'))

from src.models.config import RagflowConfig, FeatureFlag
from src.models.base import db
from src.utils.logger import get_logger

logger = get_logger(__name__)


def create_ragflow_tables():
    """创建RAGFLOW相关表"""
    try:
        # 创建表
        db.create_tables([RagflowConfig, FeatureFlag])
        logger.info("RAGFLOW配置表创建成功")
        
        # 创建默认配置
        default_config = RagflowConfig.create(
            config_name="default",
            api_endpoint="https://api.ragflow.example.com/v1",
            api_key="your_api_key_here",
            timeout_seconds=30,
            is_active=True
        )
        
        # 设置默认头部
        default_config.set_headers({
            "Content-Type": "application/json",
            "User-Agent": "IntelligentAgent/1.0"
        })
        
        # 设置默认速率限制
        default_config.set_rate_limit({
            "max_requests": 100,
            "window_seconds": 60
        })
        
        # 设置默认回退配置
        default_config.set_fallback_config({
            "enabled": True,
            "default_response": "抱歉，我暂时无法回答您的问题。请尝试重新表述或联系客服。"
        })
        
        default_config.save()
        
        logger.info("默认RAGFLOW配置创建成功")
        
        # 创建备份配置
        backup_config = RagflowConfig.create(
            config_name="backup",
            api_endpoint="https://backup.ragflow.example.com/v1",
            api_key="your_backup_api_key_here",
            timeout_seconds=45,
            is_active=True
        )
        
        backup_config.set_headers({
            "Content-Type": "application/json",
            "User-Agent": "IntelligentAgent/1.0"
        })
        
        backup_config.set_rate_limit({
            "max_requests": 50,
            "window_seconds": 60
        })
        
        backup_config.save()
        
        logger.info("备份RAGFLOW配置创建成功")
        
        # 创建技术专用配置
        tech_config = RagflowConfig.create(
            config_name="technical",
            api_endpoint="https://tech.ragflow.example.com/v1",
            api_key="your_tech_api_key_here",
            timeout_seconds=60,
            is_active=True
        )
        
        tech_config.set_headers({
            "Content-Type": "application/json",
            "User-Agent": "IntelligentAgent/1.0",
            "X-Domain": "technical"
        })
        
        tech_config.set_rate_limit({
            "max_requests": 200,
            "window_seconds": 60
        })
        
        tech_config.set_fallback_config({
            "enabled": True,
            "config_name": "default",
            "default_response": "抱歉，技术问题暂时无法回答。请联系技术支持。"
        })
        
        tech_config.save()
        
        logger.info("技术专用RAGFLOW配置创建成功")
        
        # 创建功能开关
        ragflow_feature = FeatureFlag.create(
            flag_name="ragflow_enabled",
            is_enabled=True,
            description="RAGFLOW服务总开关",
            rollout_percentage=100
        )
        
        logger.info("RAGFLOW功能开关创建成功")
        
        # 创建高级功能开关
        advanced_features = [
            {
                "flag_name": "ragflow_cache_enabled",
                "is_enabled": True,
                "description": "RAGFLOW缓存功能开关",
                "rollout_percentage": 100
            },
            {
                "flag_name": "ragflow_rate_limit_enabled",
                "is_enabled": True,
                "description": "RAGFLOW速率限制功能开关",
                "rollout_percentage": 100
            },
            {
                "flag_name": "ragflow_fallback_enabled",
                "is_enabled": True,
                "description": "RAGFLOW回退机制功能开关",
                "rollout_percentage": 100
            },
            {
                "flag_name": "ragflow_health_check_enabled",
                "is_enabled": True,
                "description": "RAGFLOW健康检查功能开关",
                "rollout_percentage": 80
            },
            {
                "flag_name": "ragflow_document_upload_enabled",
                "is_enabled": False,
                "description": "RAGFLOW文档上传功能开关",
                "rollout_percentage": 0
            }
        ]
        
        for feature in advanced_features:
            FeatureFlag.create(**feature)
        
        logger.info("高级功能开关创建成功")
        
        print("✅ RAGFLOW数据库迁移完成")
        print("✅ 默认配置已创建")
        print("✅ 备份配置已创建")
        print("✅ 技术专用配置已创建")
        print("✅ 功能开关已创建")
        
    except Exception as e:
        logger.error(f"RAGFLOW表创建失败: {str(e)}")
        raise


def drop_ragflow_tables():
    """删除RAGFLOW相关表"""
    try:
        db.drop_tables([RagflowConfig, FeatureFlag])
        logger.info("RAGFLOW配置表删除成功")
        print("✅ RAGFLOW表删除完成")
        
    except Exception as e:
        logger.error(f"RAGFLOW表删除失败: {str(e)}")
        raise


def update_ragflow_config():
    """更新RAGFLOW配置"""
    try:
        # 更新默认配置
        default_config = RagflowConfig.get(RagflowConfig.config_name == "default")
        
        # 更新健康检查URL
        default_config.health_check_url = "https://api.ragflow.example.com/health"
        
        # 更新回退配置
        fallback_config = {
            "enabled": True,
            "config_name": "backup",
            "default_response": "抱歉，我暂时无法回答您的问题。请稍后再试或联系客服。",
            "max_retries": 3,
            "retry_delay": 1.0
        }
        default_config.set_fallback_config(fallback_config)
        
        default_config.save()
        
        logger.info("RAGFLOW配置更新成功")
        print("✅ RAGFLOW配置更新完成")
        
    except Exception as e:
        logger.error(f"RAGFLOW配置更新失败: {str(e)}")
        raise


def show_ragflow_config():
    """显示RAGFLOW配置"""
    try:
        configs = RagflowConfig.select().where(RagflowConfig.is_active == True)
        
        print("\n=== RAGFLOW配置列表 ===")
        for config in configs:
            print(f"\n配置名称: {config.config_name}")
            print(f"API端点: {config.api_endpoint}")
            print(f"超时时间: {config.timeout_seconds}秒")
            print(f"是否激活: {config.is_active}")
            print(f"HTTP头部: {config.get_headers()}")
            print(f"速率限制: {config.get_rate_limit()}")
            print(f"回退配置: {config.get_fallback_config()}")
            print(f"健康检查URL: {config.health_check_url}")
            print("-" * 40)
        
        # 显示功能开关
        print("\n=== 功能开关列表 ===")
        flags = FeatureFlag.select().where(FeatureFlag.is_enabled == True)
        for flag in flags:
            print(f"功能名称: {flag.flag_name}")
            print(f"是否启用: {flag.is_enabled}")
            print(f"推出百分比: {flag.rollout_percentage}%")
            print(f"描述: {flag.description}")
            print("-" * 40)
        
    except Exception as e:
        logger.error(f"显示RAGFLOW配置失败: {str(e)}")
        raise


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="RAGFLOW数据库迁移脚本")
    parser.add_argument("action", choices=["create", "drop", "update", "show"], 
                       help="操作类型")
    
    args = parser.parse_args()
    
    if args.action == "create":
        create_ragflow_tables()
    elif args.action == "drop":
        drop_ragflow_tables()
    elif args.action == "update":
        update_ragflow_config()
    elif args.action == "show":
        show_ragflow_config()
    else:
        print("无效的操作类型")
        sys.exit(1)