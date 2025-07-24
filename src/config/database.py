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
        User, Intent, Slot, SlotValue, SlotDependency, ResponseType,
        Session, Conversation, ConversationStatus, IntentAmbiguity, IntentTransfer, UserContext,
        SystemConfig, RagflowConfig, EntityType, EntityDictionary, SlotExtractionRule,
        PromptTemplate, SecurityAuditLog, CacheInvalidationLog, AsyncLogQueue,
        ApiCallLog, AsyncTask, SynonymGroup, SynonymTerm, StopWord, EntityPattern
    )
    from src.models.function_call import FunctionCall as LegacyFunctionCall
    
    # 按照依赖关系正确排序创建表
    tables = [
        # 1. 基础表（无外键依赖）
        User,             # 用户表，被其他表引用
        Intent,           # 意图表，被其他表引用
        ResponseType,     # 响应类型表，被其他表引用
        ConversationStatus,  # 会话状态表，被其他表引用
        SystemConfig,     # 系统配置表
        RagflowConfig,    # RAG流配置表
        EntityType,       # 实体类型表，被实体词典引用
        
        # 2. 依赖基础表的表
        Session,          # 依赖 User
        Slot,             # 依赖 Intent
        LegacyFunctionCall,   # 依赖 Intent
        UserContext,      # 依赖 User
        SecurityAuditLog, # 依赖 User
        EntityDictionary, # 依赖 EntityType
        PromptTemplate,   # 依赖 Intent
        
        # 3. 依赖前面表的表
        Conversation,     # 依赖 Session, User
        SlotDependency,   # 依赖 Slot
        SlotExtractionRule,  # 依赖 Slot
        
        # 4. 依赖多个表的表
        SlotValue,        # 依赖 Slot, Conversation
        IntentAmbiguity,  # 依赖 Conversation
        IntentTransfer,   # 依赖 Session, Conversation, User
        ApiCallLog,       # 依赖 Conversation, LegacyFunctionCall
        AsyncTask,        # 依赖 Conversation
        
        # 5. 独立表（无外键依赖）
        CacheInvalidationLog,  # 缓存失效日志
        AsyncLogQueue,    # 异步日志队列
        
        # 6. 同义词管理表
        SynonymGroup,     # 同义词组（无外键依赖）
        StopWord,         # 停用词（无外键依赖）  
        EntityPattern,    # 实体模式（无外键依赖）
        SynonymTerm,      # 同义词条（依赖SynonymGroup）
    ]
    
    # 逐个创建表以确保依赖关系
    for table in tables:
        try:
            database.create_tables([table], safe=True)
            print(f"✅ 创建表: {table._meta.table_name}")
        except Exception as e:
            print(f"❌ 创建表失败 {table._meta.table_name}: {e}")
            
    print("数据表创建完成")


async def get_database():
    """获取数据库连接的依赖函数"""
    if database.is_closed():
        database.connect()
    try:
        yield database
    finally:
        pass  # 连接池会自动管理连接