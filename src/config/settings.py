"""
系统配置管理
"""
import os
from typing import Optional
from pydantic import Field, ConfigDict
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """系统设置类"""
    
    # 应用基础配置
    APP_NAME: str = "智能意图识别系统"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = Field(default=False, env="DEBUG")
    LOG_LEVEL: str = Field(default="INFO", env="LOG_LEVEL")
    
    # API配置
    API_PREFIX: str = "/api"
    API_V1_PREFIX: str = "/api/v1"
    
    # 数据库配置
    DATABASE_HOST: str = Field(default="localhost", env="DATABASE_HOST")
    DATABASE_PORT: int = Field(default=3306, env="DATABASE_PORT")
    DATABASE_USER: str = Field(default="root", env="DATABASE_USER")
    DATABASE_PASSWORD: str = Field(default="", env="DATABASE_PASSWORD")
    DATABASE_NAME: str = Field(default="intent_db", env="DATABASE_NAME")
    
    # Redis配置
    REDIS_HOST: str = Field(default="localhost", env="REDIS_HOST")
    REDIS_PORT: int = Field(default=6379, env="REDIS_PORT")
    REDIS_DB: int = Field(default=0, env="REDIS_DB")
    REDIS_PASSWORD: Optional[str] = Field(default=None, env="REDIS_PASSWORD")
    
    # 缓存配置
    CACHE_TTL_CONFIG: int = Field(default=3600, env="CACHE_TTL_CONFIG")  # 配置缓存1小时
    CACHE_TTL_NLU: int = Field(default=1800, env="CACHE_TTL_NLU")       # NLU结果缓存30分钟
    CACHE_TTL_SESSION: int = Field(default=86400, env="CACHE_TTL_SESSION")  # 会话缓存24小时
    
    # NLU配置
    LLM_MODEL: str = Field(default="gpt-3.5-turbo", env="LLM_MODEL")
    LLM_API_KEY: str = Field(default="", env="LLM_API_KEY")
    LLM_API_BASE: Optional[str] = Field(default=None, env="LLM_API_BASE")
    LLM_API_URL: Optional[str] = Field(default=None, env="LLM_API_BASE")  # xinference兼容性映射
    LLM_TEMPERATURE: float = Field(default=0.1, env="LLM_TEMPERATURE")
    LLM_MAX_TOKENS: int = Field(default=1000, env="LLM_MAX_TOKENS")
    
    # Duckling配置
    DUCKLING_URL: str = Field(default="http://localhost:8000", env="DUCKLING_URL")
    DUCKLING_TIMEOUT: int = Field(default=5, env="DUCKLING_TIMEOUT")
    
    # RAGFLOW配置
    RAGFLOW_API_URL: str = Field(default="", env="RAGFLOW_API_URL")
    RAGFLOW_CHAT_ID: str = Field(default="", env="RAGFLOW_CHAT_ID")
    RAGFLOW_API_KEY: str = Field(default="", env="RAGFLOW_API_KEY")
    RAGFLOW_TIMEOUT: int = Field(default=30, env="RAGFLOW_TIMEOUT")
    RAGFLOW_ENABLED: bool = Field(default=True, env="RAGFLOW_ENABLED")
    
    # 安全配置
    SECRET_KEY: str = Field(default="your-secret-key-here", env="SECRET_KEY")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(default=60 * 24, env="ACCESS_TOKEN_EXPIRE_MINUTES")
    ALGORITHM: str = "HS256"
    
    # 性能配置
    MAX_CONCURRENT_REQUESTS: int = Field(default=100, env="MAX_CONCURRENT_REQUESTS")
    REQUEST_TIMEOUT: int = Field(default=30, env="REQUEST_TIMEOUT")
    API_CALL_TIMEOUT: int = Field(default=30, env="API_CALL_TIMEOUT")
    MAX_RETRY_ATTEMPTS: int = Field(default=3, env="MAX_RETRY_ATTEMPTS")
    
    # 意图识别配置
    INTENT_CONFIDENCE_THRESHOLD: float = Field(default=0.7, env="INTENT_CONFIDENCE_THRESHOLD")
    AMBIGUITY_DETECTION_THRESHOLD: float = Field(default=0.1, env="AMBIGUITY_DETECTION_THRESHOLD")
    SLOT_CONFIDENCE_THRESHOLD: float = Field(default=0.6, env="SLOT_CONFIDENCE_THRESHOLD")
    
    # 增强的置信度阈值配置
    CONFIDENCE_THRESHOLD_HIGH: float = Field(default=0.8, env="CONFIDENCE_THRESHOLD_HIGH")
    CONFIDENCE_THRESHOLD_MEDIUM: float = Field(default=0.6, env="CONFIDENCE_THRESHOLD_MEDIUM")
    CONFIDENCE_THRESHOLD_LOW: float = Field(default=0.4, env="CONFIDENCE_THRESHOLD_LOW")
    CONFIDENCE_THRESHOLD_REJECT: float = Field(default=0.3, env="CONFIDENCE_THRESHOLD_REJECT")
    
    # 置信度计算权重配置
    CONFIDENCE_WEIGHT_LLM: float = Field(default=0.7, env="CONFIDENCE_WEIGHT_LLM")
    CONFIDENCE_WEIGHT_RULE: float = Field(default=0.3, env="CONFIDENCE_WEIGHT_RULE")
    CONFIDENCE_WEIGHT_CONTEXT: float = Field(default=0.1, env="CONFIDENCE_WEIGHT_CONTEXT")
    
    # 自适应阈值配置
    ENABLE_ADAPTIVE_THRESHOLDS: bool = Field(default=True, env="ENABLE_ADAPTIVE_THRESHOLDS")
    THRESHOLD_ADAPTATION_RATE: float = Field(default=0.05, env="THRESHOLD_ADAPTATION_RATE")
    MIN_SAMPLES_FOR_ADAPTATION: int = Field(default=10, env="MIN_SAMPLES_FOR_ADAPTATION")
    
    # 会话配置
    SESSION_TIMEOUT_SECONDS: int = Field(default=86400, env="SESSION_TIMEOUT_SECONDS")
    MAX_CONVERSATION_TURNS: int = Field(default=50, env="MAX_CONVERSATION_TURNS")
    
    # 监控配置
    ENABLE_METRICS: bool = Field(default=True, env="ENABLE_METRICS")
    METRICS_PORT: int = Field(default=9090, env="METRICS_PORT")
    
    # 日志配置
    LOG_FORMAT: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    LOG_FILE: Optional[str] = Field(default=None, env="LOG_FILE")
    
    model_config = ConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True
    )


# 创建全局设置实例
settings = Settings()


def get_settings() -> Settings:
    """获取设置实例的工厂函数"""
    return settings