"""
日志工具
"""
import logging
import sys
from typing import Optional
from pathlib import Path
from logging.handlers import RotatingFileHandler
from src.config.settings import settings


class ColoredFormatter(logging.Formatter):
    """彩色日志格式化器"""
    
    COLORS = {
        'DEBUG': '\033[36m',    # 青色
        'INFO': '\033[32m',     # 绿色
        'WARNING': '\033[33m',  # 黄色
        'ERROR': '\033[31m',    # 红色
        'CRITICAL': '\033[35m', # 紫色
    }
    RESET = '\033[0m'
    
    def format(self, record):
        # 添加颜色
        if record.levelname in self.COLORS:
            record.levelname = f"{self.COLORS[record.levelname]}{record.levelname}{self.RESET}"
        
        return super().format(record)


def setup_logging():
    """设置全局日志配置"""
    
    # 创建日志目录
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)
    
    # 根日志器配置
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, settings.LOG_LEVEL.upper()))
    
    # 清除已有的处理器
    root_logger.handlers.clear()
    
    # 控制台处理器
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.DEBUG)
    
    if settings.DEBUG:
        # 开发环境使用彩色格式
        console_formatter = ColoredFormatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
    else:
        # 生产环境使用普通格式
        console_formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
    
    console_handler.setFormatter(console_formatter)
    root_logger.addHandler(console_handler)
    
    # 文件处理器
    if settings.LOG_FILE:
        file_handler = RotatingFileHandler(
            settings.LOG_FILE,
            maxBytes=10*1024*1024,  # 10MB
            backupCount=5,
            encoding='utf-8'
        )
        file_handler.setLevel(logging.INFO)
        
        file_formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s'
        )
        file_handler.setFormatter(file_formatter)
        root_logger.addHandler(file_handler)
    
    # 错误日志文件处理器
    error_handler = RotatingFileHandler(
        log_dir / "error.log",
        maxBytes=10*1024*1024,  # 10MB
        backupCount=5,
        encoding='utf-8'
    )
    error_handler.setLevel(logging.ERROR)
    
    error_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(filename)s:%(lineno)d - %(funcName)s - %(message)s'
    )
    error_handler.setFormatter(error_formatter)
    root_logger.addHandler(error_handler)
    
    # 禁用第三方库的调试日志
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("requests").setLevel(logging.WARNING)
    logging.getLogger("aiohttp").setLevel(logging.WARNING)
    logging.getLogger("redis").setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    """
    获取日志器
    
    Args:
        name: 日志器名称，通常使用 __name__
        
    Returns:
        logging.Logger: 配置好的日志器
    """
    return logging.getLogger(name)


class RequestLogger:
    """请求日志记录器"""
    
    def __init__(self, logger_name: str = "request"):
        self.logger = get_logger(logger_name)
    
    def log_request(self, method: str, url: str, user_id: Optional[str] = None, 
                   request_id: Optional[str] = None):
        """记录请求日志"""
        extra_info = []
        if user_id:
            extra_info.append(f"user={user_id}")
        if request_id:
            extra_info.append(f"req_id={request_id}")
        
        extra_str = f" [{', '.join(extra_info)}]" if extra_info else ""
        self.logger.info(f"REQUEST {method} {url}{extra_str}")
    
    def log_response(self, status_code: int, response_time_ms: int, 
                    request_id: Optional[str] = None):
        """记录响应日志"""
        extra_str = f" [req_id={request_id}]" if request_id else ""
        self.logger.info(f"RESPONSE {status_code} {response_time_ms}ms{extra_str}")
    
    def log_error(self, error: Exception, request_id: Optional[str] = None):
        """记录错误日志"""
        extra_str = f" [req_id={request_id}]" if request_id else ""
        self.logger.error(f"ERROR {type(error).__name__}: {str(error)}{extra_str}", exc_info=True)


class PerformanceLogger:
    """性能日志记录器"""
    
    def __init__(self, logger_name: str = "performance"):
        self.logger = get_logger(logger_name)
    
    def log_slow_query(self, query: str, duration_ms: int, threshold_ms: int = 1000):
        """记录慢查询"""
        if duration_ms > threshold_ms:
            self.logger.warning(f"SLOW_QUERY {duration_ms}ms: {query[:200]}")
    
    def log_cache_miss(self, cache_key: str, operation: str):
        """记录缓存未命中"""
        self.logger.debug(f"CACHE_MISS {operation}: {cache_key}")
    
    def log_cache_hit(self, cache_key: str, operation: str):
        """记录缓存命中"""
        self.logger.debug(f"CACHE_HIT {operation}: {cache_key}")
    
    def log_api_call(self, api_name: str, duration_ms: int, success: bool):
        """记录API调用"""
        status = "SUCCESS" if success else "FAILURE"
        self.logger.info(f"API_CALL {api_name} {status} {duration_ms}ms")


class SecurityLogger:
    """安全日志记录器"""
    
    def __init__(self, logger_name: str = "security"):
        self.logger = get_logger(logger_name)
    
    def log_login_attempt(self, user_id: str, ip_address: str, success: bool):
        """记录登录尝试"""
        status = "SUCCESS" if success else "FAILURE"
        self.logger.info(f"LOGIN_ATTEMPT {status} user={user_id} ip={ip_address}")
    
    def log_security_violation(self, violation_type: str, details: str, 
                             ip_address: Optional[str] = None, 
                             user_id: Optional[str] = None):
        """记录安全违规"""
        extra_info = []
        if ip_address:
            extra_info.append(f"ip={ip_address}")
        if user_id:
            extra_info.append(f"user={user_id}")
        
        extra_str = f" [{', '.join(extra_info)}]" if extra_info else ""
        self.logger.warning(f"SECURITY_VIOLATION {violation_type}: {details}{extra_str}")
    
    def log_permission_denied(self, resource: str, action: str, user_id: str):
        """记录权限拒绝"""
        self.logger.warning(f"PERMISSION_DENIED user={user_id} action={action} resource={resource}")


class BusinessLogger:
    """业务日志记录器"""
    
    def __init__(self, logger_name: str = "business"):
        self.logger = get_logger(logger_name)
    
    def log_intent_recognition(self, user_input: str, intent: Optional[str], 
                             confidence: float, user_id: str):
        """记录意图识别"""
        intent_str = intent or "UNKNOWN"
        self.logger.info(f"INTENT_RECOGNITION user={user_id} intent={intent_str} "
                        f"confidence={confidence:.3f} input='{user_input[:50]}'")
    
    def log_slot_extraction(self, intent: str, slots: dict, user_id: str):
        """记录槽位提取"""
        slots_str = ", ".join([f"{k}={v}" for k, v in slots.items()])
        self.logger.info(f"SLOT_EXTRACTION user={user_id} intent={intent} slots=[{slots_str}]")
    
    def log_api_function_call(self, function_name: str, success: bool, 
                            duration_ms: int, user_id: str):
        """记录函数调用"""
        status = "SUCCESS" if success else "FAILURE"
        self.logger.info(f"FUNCTION_CALL {status} user={user_id} function={function_name} "
                        f"duration={duration_ms}ms")
    
    def log_conversation_complete(self, session_id: str, user_id: str, 
                                turns: int, duration_seconds: int):
        """记录对话完成"""
        self.logger.info(f"CONVERSATION_COMPLETE user={user_id} session={session_id} "
                        f"turns={turns} duration={duration_seconds}s")


# 创建全局日志器实例
request_logger = RequestLogger()
performance_logger = PerformanceLogger()
security_logger = SecurityLogger()
business_logger = BusinessLogger()