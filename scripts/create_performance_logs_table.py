#!/usr/bin/env python3
"""
创建缺失的performance_logs表
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import asyncio
from src.config.settings import settings
import mysql.connector
from mysql.connector import Error

async def create_performance_logs_table():
    """创建performance_logs表"""
    try:
        # 连接数据库
        connection = mysql.connector.connect(
            host=settings.DATABASE_HOST,
            port=settings.DATABASE_PORT,
            user=settings.DATABASE_USER,
            password=settings.DATABASE_PASSWORD,
            database=settings.DATABASE_NAME,
            charset='utf8mb4'
        )
        
        cursor = connection.cursor()
        
        # 创建performance_logs表
        create_table_sql = """
        CREATE TABLE IF NOT EXISTS performance_logs (
            id BIGINT AUTO_INCREMENT PRIMARY KEY,
            endpoint VARCHAR(200) NOT NULL COMMENT 'API端点',
            method VARCHAR(10) NOT NULL COMMENT 'HTTP方法',
            user_id VARCHAR(100) COMMENT '用户ID',
            request_id VARCHAR(100) COMMENT '请求ID',
            response_time_ms INT NOT NULL COMMENT '响应时间毫秒',
            status_code INT NOT NULL COMMENT 'HTTP状态码',
            request_size_bytes INT COMMENT '请求大小字节',
            response_size_bytes INT COMMENT '响应大小字节',
            cpu_usage_percent DECIMAL(5,2) COMMENT 'CPU使用率',
            memory_usage_mb DECIMAL(10,2) COMMENT '内存使用MB',
            cache_hit BOOLEAN COMMENT '是否缓存命中',
            database_queries INT DEFAULT 0 COMMENT '数据库查询次数',
            external_api_calls INT DEFAULT 0 COMMENT '外部API调用次数',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
            
            INDEX idx_endpoint_method (endpoint(100), method),
            INDEX idx_response_time (response_time_ms),
            INDEX idx_status_code (status_code),
            INDEX idx_created_at (created_at),
            INDEX idx_user_id (user_id)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci 
        COMMENT='性能监控日志表 - 记录API请求的性能指标'
        """
        
        cursor.execute(create_table_sql)
        connection.commit()
        
        print("✅ performance_logs表创建成功")
        
        # 验证表是否存在
        cursor.execute("SHOW TABLES LIKE 'performance_logs'")
        result = cursor.fetchone()
        
        if result:
            print("✅ 表验证成功，performance_logs表已存在")
            
            # 显示表结构
            cursor.execute("DESCRIBE performance_logs")
            columns = cursor.fetchall()
            
            print("\n📋 表结构:")
            for column in columns:
                print(f"  {column[0]:20} {column[1]:30} {column[2]:10} {column[3]:10}")
        else:
            print("❌ 表验证失败，performance_logs表不存在")
        
        cursor.close()
        connection.close()
        
        return True
        
    except Error as e:
        print(f"❌ 数据库操作失败: {e}")
        return False
    except Exception as e:
        print(f"❌ 创建表失败: {e}")
        return False

async def main():
    """主函数"""
    print("🚀 开始创建performance_logs表...")
    success = await create_performance_logs_table()
    
    if success:
        print("🎉 表创建任务完成")
        return 0
    else:
        print("💥 表创建任务失败")
        return 1

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)