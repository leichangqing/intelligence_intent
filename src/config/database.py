"""
数据库配置和连接管理
"""
from peewee import MySQLDatabase, Model
from playhouse.pool import PooledMySQLDatabase
from .settings import settings

# 创建数据库连接池
database = PooledMySQLDatabase(
    settings.DATABASE_NAME,
    user=settings.DATABASE_USER,
    password=settings.DATABASE_PASSWORD,
    host=settings.DATABASE_HOST,
    port=settings.DATABASE_PORT,
    charset='utf8mb4',
    max_connections=20,
    stale_timeout=300
)


class BaseModel(Model):
    """基础模型类，所有模型都继承此类"""
    
    class Meta:
        database = database


def init_database():
    """初始化数据库连接"""
    # 连接数据库
    database.connect()
    print(f"已连接到数据库: {settings.DATABASE_NAME}")


def close_database():
    """关闭数据库连接"""
    if not database.is_closed():
        database.close()
        print("数据库连接已关闭")


def create_tables():
    """创建所有数据表"""
    from src.models import (
        Intent, Slot, SlotValue, SlotDependency, FunctionCall, Session, Conversation,
        IntentAmbiguity, ConfigAuditLog, PromptTemplate,
        UserContext, IntentTransfer, SystemConfig,
        ApiCallLog, RagflowConfig, SecurityAuditLog,
        AsyncTask, CacheInvalidationLog, AsyncLogQueue,
        ResponseType, ConversationStatus
    )
    
    # 创建所有表
    tables = [
        Intent, Slot, SlotValue, SlotDependency, FunctionCall, Session, Conversation,
        IntentAmbiguity, ConfigAuditLog, PromptTemplate,
        UserContext, IntentTransfer, SystemConfig,
        ApiCallLog, RagflowConfig, SecurityAuditLog,
        AsyncTask, CacheInvalidationLog, AsyncLogQueue,
        ResponseType, ConversationStatus
    ]
    
    database.create_tables(tables, safe=True)
    print("数据表创建完成")


async def get_database():
    """获取数据库连接的依赖函数"""
    if database.is_closed():
        database.connect()
    try:
        yield database
    finally:
        pass  # 连接池会自动管理连接