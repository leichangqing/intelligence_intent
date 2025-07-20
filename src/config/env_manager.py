"""
TASK-056: 环境变量管理
Enhanced Environment Variable Management System
"""
import os
import json
import base64
import hashlib
from typing import Dict, Any, Optional, List, Union, Type, Callable
from datetime import datetime, timedelta
from pathlib import Path
from dataclasses import dataclass, field
from enum import Enum
import logging
from cryptography.fernet import Fernet
from pydantic import BaseModel, Field, ValidationError, validator
import yaml

logger = logging.getLogger(__name__)


class EnvironmentType(Enum):
    """环境类型枚举"""
    DEVELOPMENT = "development"
    TESTING = "testing"
    STAGING = "staging"
    PRODUCTION = "production"
    LOCAL = "local"


class VariableType(Enum):
    """变量类型枚举"""
    STRING = "string"
    INTEGER = "integer"
    FLOAT = "float"
    BOOLEAN = "boolean"
    JSON = "json"
    LIST = "list"
    URL = "url"
    EMAIL = "email"
    SECRET = "secret"


class SecurityLevel(Enum):
    """安全级别枚举"""
    PUBLIC = "public"
    INTERNAL = "internal"
    CONFIDENTIAL = "confidential"
    SECRET = "secret"
    TOP_SECRET = "top_secret"


@dataclass
class EnvironmentVariable:
    """环境变量定义"""
    name: str
    type: VariableType
    description: str
    default_value: Optional[Any] = None
    required: bool = False
    security_level: SecurityLevel = SecurityLevel.PUBLIC
    environments: List[EnvironmentType] = field(default_factory=lambda: list(EnvironmentType))
    validator_func: Optional[Callable] = None
    encrypted: bool = False
    deprecated: bool = False
    deprecation_message: Optional[str] = None
    min_value: Optional[Union[int, float]] = None
    max_value: Optional[Union[int, float]] = None
    allowed_values: Optional[List[Any]] = None
    pattern: Optional[str] = None
    examples: List[str] = field(default_factory=list)


class EnvironmentConfig(BaseModel):
    """环境配置模型"""
    environment: EnvironmentType
    variables: Dict[str, Any] = Field(default_factory=dict)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    version: str = "1.0.0"
    checksum: Optional[str] = None


class SecretManager:
    """密钥管理器"""
    
    def __init__(self, master_key: Optional[str] = None):
        """初始化密钥管理器"""
        if master_key:
            self.cipher = Fernet(master_key.encode())
        else:
            # 从环境变量或生成新密钥
            key = os.getenv('MASTER_ENCRYPTION_KEY')
            if not key:
                key = Fernet.generate_key()
                logger.warning("生成新的主加密密钥，请保存: %s", key.decode())
            self.cipher = Fernet(key)
    
    def encrypt(self, value: str) -> str:
        """加密值"""
        try:
            encrypted = self.cipher.encrypt(value.encode())
            return base64.b64encode(encrypted).decode()
        except Exception as e:
            logger.error("加密失败: %s", e)
            raise
    
    def decrypt(self, encrypted_value: str) -> str:
        """解密值"""
        try:
            encrypted_bytes = base64.b64decode(encrypted_value.encode())
            decrypted = self.cipher.decrypt(encrypted_bytes)
            return decrypted.decode()
        except Exception as e:
            logger.error("解密失败: %s", e)
            raise


class EnvironmentVariableManager:
    """环境变量管理器"""
    
    def __init__(self, config_dir: Optional[Path] = None):
        """初始化环境变量管理器"""
        self.config_dir = config_dir or Path("config")
        self.config_dir.mkdir(exist_ok=True)
        
        self.secret_manager = SecretManager()
        self.variables_registry: Dict[str, EnvironmentVariable] = {}
        self.loaded_configs: Dict[EnvironmentType, EnvironmentConfig] = {}
        self.validation_errors: List[str] = []
        
        self._register_default_variables()
    
    def _register_default_variables(self):
        """注册默认环境变量"""
        default_variables = [
            # 应用配置
            EnvironmentVariable(
                name="APP_NAME",
                type=VariableType.STRING,
                description="应用程序名称",
                default_value="智能意图识别系统",
                required=True,
                examples=["Intent Recognition System", "智能意图识别系统"]
            ),
            EnvironmentVariable(
                name="APP_ENV",
                type=VariableType.STRING,
                description="应用环境",
                default_value="development",
                required=True,
                allowed_values=["development", "testing", "staging", "production"],
                examples=["development", "production"]
            ),
            EnvironmentVariable(
                name="DEBUG",
                type=VariableType.BOOLEAN,
                description="调试模式开关",
                default_value=False,
                environments=[EnvironmentType.DEVELOPMENT, EnvironmentType.TESTING]
            ),
            EnvironmentVariable(
                name="LOG_LEVEL",
                type=VariableType.STRING,
                description="日志级别",
                default_value="INFO",
                allowed_values=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
                examples=["INFO", "DEBUG"]
            ),
            
            # 数据库配置
            EnvironmentVariable(
                name="DATABASE_HOST",
                type=VariableType.STRING,
                description="数据库主机地址",
                default_value="localhost",
                required=True,
                examples=["localhost", "db.example.com", "127.0.0.1"]
            ),
            EnvironmentVariable(
                name="DATABASE_PORT",
                type=VariableType.INTEGER,
                description="数据库端口",
                default_value=3306,
                required=True,
                min_value=1,
                max_value=65535,
                examples=["3306", "5432"]
            ),
            EnvironmentVariable(
                name="DATABASE_NAME",
                type=VariableType.STRING,
                description="数据库名称",
                default_value="intent_recognition_system",
                required=True,
                examples=["intent_recognition_system", "app_db"]
            ),
            EnvironmentVariable(
                name="DATABASE_USER",
                type=VariableType.STRING,
                description="数据库用户名",
                required=True,
                security_level=SecurityLevel.CONFIDENTIAL,
                examples=["app_user", "db_user"]
            ),
            EnvironmentVariable(
                name="DATABASE_PASSWORD",
                type=VariableType.SECRET,
                description="数据库密码",
                required=True,
                security_level=SecurityLevel.SECRET,
                encrypted=True,
                examples=["your_secure_password"]
            ),
            
            # Redis配置
            EnvironmentVariable(
                name="REDIS_HOST",
                type=VariableType.STRING,
                description="Redis主机地址",
                default_value="localhost",
                required=True,
                examples=["localhost", "redis.example.com"]
            ),
            EnvironmentVariable(
                name="REDIS_PORT",
                type=VariableType.INTEGER,
                description="Redis端口",
                default_value=6379,
                min_value=1,
                max_value=65535,
                examples=["6379"]
            ),
            EnvironmentVariable(
                name="REDIS_PASSWORD",
                type=VariableType.SECRET,
                description="Redis密码",
                security_level=SecurityLevel.SECRET,
                encrypted=True,
                examples=["redis_password"]
            ),
            
            # 安全配置
            EnvironmentVariable(
                name="SECRET_KEY",
                type=VariableType.SECRET,
                description="应用密钥",
                required=True,
                security_level=SecurityLevel.SECRET,
                encrypted=True,
                examples=["your-secret-key-change-this-in-production"]
            ),
            EnvironmentVariable(
                name="ACCESS_TOKEN_EXPIRE_MINUTES",
                type=VariableType.INTEGER,
                description="访问令牌过期时间（分钟）",
                default_value=1440,
                min_value=1,
                max_value=43200,  # 30天
                examples=["1440", "60"]
            ),
            
            # API配置
            EnvironmentVariable(
                name="LLM_API_KEY",
                type=VariableType.SECRET,
                description="LLM API密钥",
                security_level=SecurityLevel.SECRET,
                encrypted=True,
                examples=["sk-xxx", "EMPTY"]
            ),
            EnvironmentVariable(
                name="LLM_API_BASE",
                type=VariableType.URL,
                description="LLM API基础URL",
                default_value="http://localhost:9997/v1",
                examples=["http://localhost:9997/v1", "https://api.openai.com/v1"]
            ),
            EnvironmentVariable(
                name="RAGFLOW_API_KEY",
                type=VariableType.SECRET,
                description="RAGFLOW API密钥",
                security_level=SecurityLevel.SECRET,
                encrypted=True,
                examples=["ragflow_api_key_here"]
            ),
            
            # 性能配置
            EnvironmentVariable(
                name="MAX_CONCURRENT_REQUESTS",
                type=VariableType.INTEGER,
                description="最大并发请求数",
                default_value=100,
                min_value=1,
                max_value=10000,
                examples=["100", "500"]
            ),
            EnvironmentVariable(
                name="REQUEST_TIMEOUT",
                type=VariableType.INTEGER,
                description="请求超时时间（秒）",
                default_value=30,
                min_value=1,
                max_value=300,
                examples=["30", "60"]
            ),
        ]
        
        for var in default_variables:
            self.register_variable(var)
    
    def register_variable(self, variable: EnvironmentVariable):
        """注册环境变量"""
        self.variables_registry[variable.name] = variable
        logger.debug("注册环境变量: %s", variable.name)
    
    def get_variable_definition(self, name: str) -> Optional[EnvironmentVariable]:
        """获取环境变量定义"""
        return self.variables_registry.get(name)
    
    def validate_value(self, name: str, value: Any) -> bool:
        """验证环境变量值"""
        var_def = self.get_variable_definition(name)
        if not var_def:
            logger.warning("未定义的环境变量: %s", name)
            return True
        
        try:
            # 类型验证
            validated_value = self._convert_type(value, var_def.type)
            
            # 范围验证
            if var_def.min_value is not None and validated_value < var_def.min_value:
                raise ValueError(f"值 {validated_value} 小于最小值 {var_def.min_value}")
            
            if var_def.max_value is not None and validated_value > var_def.max_value:
                raise ValueError(f"值 {validated_value} 大于最大值 {var_def.max_value}")
            
            # 允许值验证
            if var_def.allowed_values and validated_value not in var_def.allowed_values:
                raise ValueError(f"值 {validated_value} 不在允许列表中: {var_def.allowed_values}")
            
            # 自定义验证器
            if var_def.validator_func:
                if not var_def.validator_func(validated_value):
                    raise ValueError(f"自定义验证失败")
            
            return True
            
        except Exception as e:
            self.validation_errors.append(f"变量 {name} 验证失败: {e}")
            logger.error("变量 %s 验证失败: %s", name, e)
            return False
    
    def _convert_type(self, value: Any, var_type: VariableType) -> Any:
        """转换变量类型"""
        if value is None:
            return None
        
        if var_type == VariableType.STRING:
            return str(value)
        elif var_type == VariableType.INTEGER:
            return int(value)
        elif var_type == VariableType.FLOAT:
            return float(value)
        elif var_type == VariableType.BOOLEAN:
            if isinstance(value, bool):
                return value
            return str(value).lower() in ('true', '1', 'yes', 'on', 'enabled')
        elif var_type == VariableType.JSON:
            if isinstance(value, str):
                return json.loads(value)
            return value
        elif var_type == VariableType.LIST:
            if isinstance(value, str):
                return [item.strip() for item in value.split(',')]
            return list(value)
        elif var_type in (VariableType.URL, VariableType.EMAIL, VariableType.SECRET):
            return str(value)
        else:
            return value
    
    def load_environment(self, env_type: EnvironmentType, config_file: Optional[Path] = None) -> EnvironmentConfig:
        """加载环境配置"""
        if config_file is None:
            config_file = self.config_dir / f".env.{env_type.value}"
        
        # 从文件加载配置
        variables = {}
        if config_file.exists():
            variables.update(self._load_from_file(config_file))
        
        # 从环境变量加载
        env_variables = self._load_from_environment()
        variables.update(env_variables)
        
        # 解密敏感变量
        variables = self._decrypt_sensitive_variables(variables)
        
        # 验证配置
        self._validate_environment_config(variables, env_type)
        
        config = EnvironmentConfig(
            environment=env_type,
            variables=variables,
            metadata={
                "loaded_from": str(config_file),
                "loaded_at": datetime.now().isoformat(),
                "validation_errors": len(self.validation_errors)
            }
        )
        
        # 计算校验和
        config.checksum = self._calculate_checksum(config.variables)
        
        self.loaded_configs[env_type] = config
        return config
    
    def _load_from_file(self, file_path: Path) -> Dict[str, Any]:
        """从文件加载环境变量"""
        variables = {}
        
        try:
            if file_path.suffix.lower() in ['.yml', '.yaml']:
                # YAML格式
                with open(file_path, 'r', encoding='utf-8') as f:
                    data = yaml.safe_load(f) or {}
                    variables.update(data)
            elif file_path.suffix.lower() == '.json':
                # JSON格式
                with open(file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    variables.update(data)
            else:
                # .env格式
                with open(file_path, 'r', encoding='utf-8') as f:
                    for line_num, line in enumerate(f, 1):
                        line = line.strip()
                        if line and not line.startswith('#'):
                            try:
                                key, value = line.split('=', 1)
                                key = key.strip()
                                value = value.strip().strip('"\'')
                                variables[key] = value
                            except ValueError:
                                logger.warning("解析失败 %s:%d: %s", file_path, line_num, line)
            
            logger.info("从文件加载了 %d 个环境变量: %s", len(variables), file_path)
            
        except Exception as e:
            logger.error("加载配置文件失败 %s: %s", file_path, e)
        
        return variables
    
    def _load_from_environment(self) -> Dict[str, Any]:
        """从系统环境变量加载"""
        variables = {}
        
        # 只加载已注册的环境变量
        for var_name in self.variables_registry:
            env_value = os.getenv(var_name)
            if env_value is not None:
                variables[var_name] = env_value
        
        logger.info("从系统环境加载了 %d 个变量", len(variables))
        return variables
    
    def _decrypt_sensitive_variables(self, variables: Dict[str, Any]) -> Dict[str, Any]:
        """解密敏感变量"""
        decrypted = variables.copy()
        
        for var_name, value in variables.items():
            var_def = self.get_variable_definition(var_name)
            if var_def and var_def.encrypted and value:
                try:
                    # 检查是否为加密格式
                    if isinstance(value, str) and value.startswith('encrypted:'):
                        encrypted_value = value[10:]  # 移除 'encrypted:' 前缀
                        decrypted_value = self.secret_manager.decrypt(encrypted_value)
                        decrypted[var_name] = decrypted_value
                        logger.debug("解密变量: %s", var_name)
                except Exception as e:
                    logger.error("解密变量失败 %s: %s", var_name, e)
        
        return decrypted
    
    def _validate_environment_config(self, variables: Dict[str, Any], env_type: EnvironmentType):
        """验证环境配置"""
        self.validation_errors.clear()
        
        # 检查必需变量
        for var_name, var_def in self.variables_registry.items():
            if var_def.required and env_type in var_def.environments:
                if var_name not in variables:
                    self.validation_errors.append(f"缺少必需变量: {var_name}")
                    continue
            
            # 验证已存在的变量
            if var_name in variables:
                self.validate_value(var_name, variables[var_name])
        
        # 检查过时变量
        for var_name, var_def in self.variables_registry.items():
            if var_def.deprecated and var_name in variables:
                message = var_def.deprecation_message or f"变量 {var_name} 已过时"
                logger.warning(message)
        
        if self.validation_errors:
            logger.error("环境配置验证失败，共 %d 个错误", len(self.validation_errors))
            for error in self.validation_errors:
                logger.error("  - %s", error)
    
    def _calculate_checksum(self, variables: Dict[str, Any]) -> str:
        """计算配置校验和"""
        content = json.dumps(variables, sort_keys=True)
        return hashlib.sha256(content.encode()).hexdigest()
    
    def encrypt_value(self, value: str) -> str:
        """加密值"""
        encrypted = self.secret_manager.encrypt(value)
        return f"encrypted:{encrypted}"
    
    def save_environment_config(self, env_type: EnvironmentType, variables: Dict[str, Any], 
                              encrypt_secrets: bool = True) -> Path:
        """保存环境配置"""
        config_file = self.config_dir / f".env.{env_type.value}"
        
        # 加密敏感变量
        if encrypt_secrets:
            variables = self._encrypt_sensitive_variables(variables)
        
        # 保存为.env格式
        with open(config_file, 'w', encoding='utf-8') as f:
            f.write(f"# 环境配置文件 - {env_type.value.upper()}\n")
            f.write(f"# 生成时间: {datetime.now().isoformat()}\n")
            f.write(f"# 自动生成，请勿手动编辑敏感信息\n\n")
            
            # 按类别分组写入
            categories = self._group_variables_by_category(variables)
            
            for category, vars_in_category in categories.items():
                f.write(f"\n# {category}\n")
                for var_name in sorted(vars_in_category.keys()):
                    value = vars_in_category[var_name]
                    var_def = self.get_variable_definition(var_name)
                    
                    # 添加注释
                    if var_def:
                        f.write(f"# {var_def.description}\n")
                        if var_def.examples:
                            f.write(f"# 示例: {', '.join(var_def.examples)}\n")
                    
                    # 写入变量
                    if isinstance(value, str) and ' ' in value:
                        f.write(f'{var_name}="{value}"\n')
                    else:
                        f.write(f'{var_name}={value}\n')
                    f.write('\n')
        
        logger.info("保存环境配置到: %s", config_file)
        return config_file
    
    def _encrypt_sensitive_variables(self, variables: Dict[str, Any]) -> Dict[str, Any]:
        """加密敏感变量"""
        encrypted = variables.copy()
        
        for var_name, value in variables.items():
            var_def = self.get_variable_definition(var_name)
            if var_def and var_def.security_level in (SecurityLevel.SECRET, SecurityLevel.TOP_SECRET):
                if value and not str(value).startswith('encrypted:'):
                    encrypted[var_name] = self.encrypt_value(str(value))
                    logger.debug("加密变量: %s", var_name)
        
        return encrypted
    
    def _group_variables_by_category(self, variables: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
        """按类别分组变量"""
        categories = {
            "应用配置": {},
            "数据库配置": {},
            "Redis配置": {},
            "安全配置": {},
            "API配置": {},
            "性能配置": {},
            "监控配置": {},
            "其他配置": {}
        }
        
        for var_name, value in variables.items():
            if var_name.startswith('APP_') or var_name in ['DEBUG', 'LOG_LEVEL']:
                categories["应用配置"][var_name] = value
            elif var_name.startswith('DATABASE_'):
                categories["数据库配置"][var_name] = value
            elif var_name.startswith('REDIS_'):
                categories["Redis配置"][var_name] = value
            elif var_name in ['SECRET_KEY', 'ACCESS_TOKEN_EXPIRE_MINUTES']:
                categories["安全配置"][var_name] = value
            elif var_name.startswith(('LLM_', 'RAGFLOW_', 'DUCKLING_')):
                categories["API配置"][var_name] = value
            elif var_name.startswith(('MAX_', 'TIMEOUT', 'CACHE_')):
                categories["性能配置"][var_name] = value
            elif var_name.startswith(('METRICS_', 'ENABLE_')):
                categories["监控配置"][var_name] = value
            else:
                categories["其他配置"][var_name] = value
        
        # 移除空类别
        return {k: v for k, v in categories.items() if v}
    
    def generate_documentation(self) -> str:
        """生成环境变量文档"""
        doc = ["# 环境变量配置文档\n"]
        doc.append(f"生成时间: {datetime.now().isoformat()}\n")
        doc.append(f"注册变量数量: {len(self.variables_registry)}\n\n")
        
        # 按类别分组
        categories = self._group_variables_by_definition()
        
        for category, variables in categories.items():
            doc.append(f"## {category}\n\n")
            
            for var_name in sorted(variables.keys()):
                var_def = variables[var_name]
                doc.append(f"### {var_name}\n\n")
                doc.append(f"**描述**: {var_def.description}\n\n")
                doc.append(f"**类型**: {var_def.type.value}\n\n")
                doc.append(f"**必需**: {'是' if var_def.required else '否'}\n\n")
                doc.append(f"**安全级别**: {var_def.security_level.value}\n\n")
                
                if var_def.default_value is not None:
                    doc.append(f"**默认值**: `{var_def.default_value}`\n\n")
                
                if var_def.allowed_values:
                    doc.append(f"**允许值**: {', '.join(map(str, var_def.allowed_values))}\n\n")
                
                if var_def.min_value is not None or var_def.max_value is not None:
                    doc.append(f"**范围**: {var_def.min_value} - {var_def.max_value}\n\n")
                
                if var_def.examples:
                    doc.append(f"**示例**:\n")
                    for example in var_def.examples:
                        doc.append(f"- `{example}`\n")
                    doc.append("\n")
                
                if var_def.environments != list(EnvironmentType):
                    env_names = [env.value for env in var_def.environments]
                    doc.append(f"**适用环境**: {', '.join(env_names)}\n\n")
                
                if var_def.deprecated:
                    doc.append(f"**⚠️ 已过时**: {var_def.deprecation_message or '此变量已过时'}\n\n")
                
                doc.append("---\n\n")
        
        return ''.join(doc)
    
    def _group_variables_by_definition(self) -> Dict[str, Dict[str, EnvironmentVariable]]:
        """按定义分组变量"""
        categories = {
            "应用配置": {},
            "数据库配置": {},
            "缓存配置": {},
            "安全配置": {},
            "API配置": {},
            "性能配置": {},
            "监控配置": {},
            "其他配置": {}
        }
        
        for var_name, var_def in self.variables_registry.items():
            if var_name.startswith('APP_') or var_name in ['DEBUG', 'LOG_LEVEL']:
                categories["应用配置"][var_name] = var_def
            elif var_name.startswith('DATABASE_'):
                categories["数据库配置"][var_name] = var_def
            elif var_name.startswith('REDIS_') or var_name.startswith('CACHE_'):
                categories["缓存配置"][var_name] = var_def
            elif var_name in ['SECRET_KEY', 'ACCESS_TOKEN_EXPIRE_MINUTES']:
                categories["安全配置"][var_name] = var_def
            elif var_name.startswith(('LLM_', 'RAGFLOW_', 'DUCKLING_')):
                categories["API配置"][var_name] = var_def
            elif var_name.startswith(('MAX_', 'TIMEOUT')):
                categories["性能配置"][var_name] = var_def
            elif var_name.startswith(('METRICS_', 'ENABLE_')):
                categories["监控配置"][var_name] = var_def
            else:
                categories["其他配置"][var_name] = var_def
        
        # 移除空类别
        return {k: v for k, v in categories.items() if v}
    
    def get_validation_errors(self) -> List[str]:
        """获取验证错误"""
        return self.validation_errors.copy()
    
    def get_config_status(self) -> Dict[str, Any]:
        """获取配置状态"""
        return {
            "registered_variables": len(self.variables_registry),
            "loaded_environments": list(self.loaded_configs.keys()),
            "validation_errors": len(self.validation_errors),
            "last_validation": datetime.now().isoformat()
        }