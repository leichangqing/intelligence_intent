#!/usr/bin/env python3
"""
数据库初始化脚本 - MySQL版本
"""
import os
import sys
import time
import subprocess
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.config.settings import settings
from src.config.database import database, create_tables, init_database, close_database


def check_mysql_connection():
    """检查MySQL连接"""
    try:
        import mysql.connector
        connection = mysql.connector.connect(
            host=settings.DATABASE_HOST,
            port=settings.DATABASE_PORT,
            user=settings.DATABASE_USER,
            password=settings.DATABASE_PASSWORD,
            database=settings.DATABASE_NAME
        )
        connection.close()
        return True
    except Exception as e:
        print(f"MySQL连接失败: {e}")
        return False


def create_mysql_database():
    """创建MySQL数据库"""
    try:
        import mysql.connector
        # 连接到MySQL服务器（不指定数据库）
        connection = mysql.connector.connect(
            host=settings.DATABASE_HOST,
            port=settings.DATABASE_PORT,
            user=settings.DATABASE_USER,
            password=settings.DATABASE_PASSWORD
        )
        cursor = connection.cursor()
        
        # 创建数据库
        cursor.execute(f"""
        CREATE DATABASE IF NOT EXISTS {settings.DATABASE_NAME} 
        DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci
        """)
        print(f"MySQL数据库 {settings.DATABASE_NAME} 创建成功")
        
        cursor.close()
        connection.close()
        return True
    except Exception as e:
        print(f"创建MySQL数据库失败: {e}")
        return False


def execute_mysql_schema():
    """执行MySQL schema文件"""
    schema_file = project_root / "docs" / "design" / "mysql_schema.sql"
    if not schema_file.exists():
        print(f"Schema文件不存在: {schema_file}")
        return False
    
    try:
        # 使用mysql命令行工具执行schema
        cmd = [
            "mysql",
            f"-h{settings.DATABASE_HOST}",
            f"-P{settings.DATABASE_PORT}",
            f"-u{settings.DATABASE_USER}",
            f"-p{settings.DATABASE_PASSWORD}",
            settings.DATABASE_NAME
        ]
        
        with open(schema_file, 'r', encoding='utf-8') as f:
            result = subprocess.run(
                cmd,
                input=f.read(),
                text=True,
                capture_output=True,
                timeout=60
            )
        
        # 检查是否只是密码警告
        if result.returncode == 0:
            print("MySQL schema执行成功")
            return True
        else:
            # 过滤掉密码安全警告
            actual_errors = []
            for line in result.stderr.split('\n'):
                if ('Using a password on the command line interface can be insecure' not in line 
                    and line.strip()):
                    actual_errors.append(line)
            
            if actual_errors:
                print(f"MySQL schema执行失败: {chr(10).join(actual_errors)}")
                return False
            else:
                print("MySQL schema执行成功（忽略密码警告）")
                return True
            
    except Exception as e:
        print(f"执行MySQL schema时出错: {e}")
        return False




def seed_initial_data():
    """种子数据初始化"""
    try:
        from src.models.intent import Intent
        from src.models.slot import Slot
        from src.models.function_call import FunctionCall
        from src.models.template import PromptTemplate
        from src.models.config import SystemConfig
        
        # 创建示例意图 - 订票
        book_flight_intent = Intent.create(
            intent_name="book_flight",
            display_name="预订机票",
            description="帮助用户预订机票",
            confidence_threshold=0.7,
            priority=1,
            is_active=True,
            examples=["我要订机票", "帮我买张票", "预订航班"]
        )
        
        # 创建示例意图 - 查询余额
        check_balance_intent = Intent.create(
            intent_name="check_balance",
            display_name="查询余额",
            description="查询用户账户余额",
            confidence_threshold=0.7,
            priority=1,
            is_active=True,
            examples=["查询余额", "我的余额", "账户余额"]
        )
        
        # 为订票意图创建槽位
        Slot.create(
            intent=book_flight_intent,
            slot_name="departure_city",
            slot_type="TEXT",
            is_required=True,
            validation_rules={"min_length": 2},
            prompt_template="请问您从哪个城市出发？",
            examples=["北京", "上海", "广州"]
        )
        
        Slot.create(
            intent=book_flight_intent,
            slot_name="arrival_city",
            slot_type="TEXT",
            is_required=True,
            validation_rules={"min_length": 2},
            prompt_template="请问您要到哪个城市？",
            examples=["北京", "上海", "广州"]
        )
        
        Slot.create(
            intent=book_flight_intent,
            slot_name="departure_date",
            slot_type="DATE",
            is_required=True,
            validation_rules={"format": "YYYY-MM-DD"},
            prompt_template="请问您希望什么时候出发？",
            examples=["2024-12-15", "明天", "下周一"]
        )
        
        # 创建功能调用配置
        FunctionCall.create(
            intent=book_flight_intent,
            function_name="book_flight_api",
            api_endpoint="http://api.airline.com/book",
            http_method="POST",
            headers={"Content-Type": "application/json"},
            param_mapping={
                "from": "departure_city",
                "to": "arrival_city", 
                "date": "departure_date"
            },
            retry_times=3,
            timeout_seconds=30,
            success_template="您的机票预订成功！订单号：{order_id}",
            error_template="抱歉，预订失败：{error_message}",
            is_active=True
        )
        
        FunctionCall.create(
            intent=check_balance_intent,
            function_name="check_balance_api",
            api_endpoint="http://api.bank.com/balance",
            http_method="GET",
            headers={"Content-Type": "application/json"},
            param_mapping={},
            retry_times=3,
            timeout_seconds=10,
            success_template="您的账户余额为：{balance}元",
            error_template="查询失败：{error_message}",
            is_active=True
        )
        
        # 创建系统配置
        SystemConfig.create(
            config_key="intent_confidence_threshold",
            config_value="0.7",
            description="意图识别置信度阈值",
            category="nlu",
            is_readonly=False
        )
        
        SystemConfig.create(
            config_key="max_conversation_turns",
            config_value="50",
            description="最大对话轮数",
            category="session",
            is_readonly=False
        )
        
        print("初始数据种子创建成功")
        return True
        
    except Exception as e:
        print(f"创建种子数据失败: {e}")
        return False


def main():
    """主函数"""
    print("开始数据库初始化...")
    
    # 1. 尝试连接MySQL
    mysql_available = False
    try:
        mysql_available = check_mysql_connection()
        if not mysql_available:
            print("尝试创建MySQL数据库...")
            if create_mysql_database():
                mysql_available = check_mysql_connection()
    except Exception as e:
        print(f"MySQL操作失败: {e}")
    
    # 2. 如果MySQL不可用，退出
    if not mysql_available:
        print("MySQL不可用，请检查数据库配置")
        return False
    
    # 3. 初始化数据库连接
    try:
        init_database()
        print("数据库连接初始化成功")
    except Exception as e:
        print(f"数据库连接初始化失败: {e}")
        return False
    
    # 4. 创建表结构
    try:
        # MySQL: 执行完整schema
        if execute_mysql_schema():
            print("MySQL表结构创建成功")
        else:
            print("MySQL schema执行失败，尝试使用ORM创建...")
            create_tables()
        
    except Exception as e:
        print(f"创建表结构失败: {e}")
        return False
    
    # 5. 种子数据
    try:
        seed_initial_data()
    except Exception as e:
        print(f"种子数据创建失败: {e}")
        # 种子数据失败不影响整体初始化
    
    # 6. 关闭连接
    try:
        close_database()
        print("数据库初始化完成！")
        return True
    except Exception as e:
        print(f"关闭数据库连接时出错: {e}")
        return True  # 初始化仍然成功


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)