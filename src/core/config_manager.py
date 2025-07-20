"""
增强的配置管理系统 (TASK-033)
提供配置热更新、验证、版本管理、环境特定配置和缓存优化
"""
from typing import Dict, List, Optional, Any, Callable, Union
from dataclasses import dataclass, field
from enum import Enum
import asyncio
import json
import os
import hashlib
import time
from datetime import datetime, timedelta
from pathlib import Path
from collections import defaultdict
import threading
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import pydantic
from pydantic import BaseModel, Field, validator

from src.models.config import SystemConfig, RagflowConfig, FeatureFlag
from src.services.cache_service import CacheService
from src.config.settings import get_settings
from src.utils.logger import get_logger

logger = get_logger(__name__)


class ConfigType(Enum):
    """配置类型枚举"""
    SYSTEM = "system"
    RAGFLOW = "ragflow"
    FEATURE_FLAG = "feature_flag"
    ENVIRONMENT = "environment"
    RUNTIME = "runtime"


class ConfigEvent(Enum):
    """配置事件枚举"""
    CREATED = "created"
    UPDATED = "updated"
    DELETED = "deleted"
    VALIDATED = "validated"
    RELOADED = "reloaded"
    CACHED = "cached"


@dataclass
class ConfigVersion:
    """配置版本信息"""
    version: str
    timestamp: datetime
    hash: str
    author: str
    description: str
    changes: List[str] = field(default_factory=list)


@dataclass
class ConfigValidationResult:
    """配置验证结果"""
    is_valid: bool
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    suggestions: List[str] = field(default_factory=list)


@dataclass
class ConfigChangeEvent:
    """配置变更事件"""
    config_type: ConfigType
    config_key: str
    event_type: ConfigEvent
    old_value: Any = None
    new_value: Any = None
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)


class ConfigSchema(BaseModel):
    """配置Schema基类"""
    
    class Config:
        extra = "forbid"
        validate_assignment = True


class SystemConfigSchema(ConfigSchema):
    """系统配置Schema"""
    config_key: str = Field(..., min_length=1, max_length=100)
    config_value: Any = Field(...)
    description: Optional[str] = Field(None, max_length=1000)
    category: Optional[str] = Field(None, max_length=50)
    is_readonly: bool = Field(default=False)
    
    @validator('config_key')
    def validate_config_key(cls, v):
        if not v.replace('_', '').replace('-', '').isalnum():
            raise ValueError('配置键只能包含字母、数字、下划线和连字符')
        return v


class RagflowConfigSchema(ConfigSchema):
    """RAGFLOW配置Schema"""
    config_name: str = Field(..., min_length=1, max_length=100)
    api_endpoint: str = Field(..., pattern=r'^https?://.+')
    api_key: Optional[str] = Field(None, min_length=10)
    timeout_seconds: int = Field(default=30, ge=1, le=300)
    rate_limit: Optional[Dict[str, int]] = Field(None)
    fallback_config: Optional[Dict[str, Any]] = Field(None)
    health_check_url: Optional[str] = Field(None, pattern=r'^https?://.+')
    is_active: bool = Field(default=True)
    
    @validator('rate_limit')
    def validate_rate_limit(cls, v):
        if v is not None:
            required_keys = ['requests_per_minute', 'requests_per_hour']
            if not all(key in v for key in required_keys):
                raise ValueError(f'速率限制配置必须包含: {required_keys}')
        return v


class FeatureFlagSchema(ConfigSchema):
    """功能开关Schema"""
    flag_name: str = Field(..., min_length=1, max_length=100)
    is_enabled: bool = Field(default=False)
    description: Optional[str] = Field(None, max_length=1000)
    target_users: Optional[List[str]] = Field(None)
    rollout_percentage: int = Field(default=0, ge=0, le=100)
    start_time: Optional[datetime] = Field(None)
    end_time: Optional[datetime] = Field(None)
    
    @validator('end_time')
    def validate_end_time(cls, v, values):
        if v is not None and 'start_time' in values and values['start_time'] is not None:
            if v <= values['start_time']:
                raise ValueError('结束时间必须晚于开始时间')
        return v


class ConfigFileWatcher(FileSystemEventHandler):
    """配置文件监控器"""
    
    def __init__(self, config_manager):
        self.config_manager = config_manager
        self.last_modified = {}
        
    def on_modified(self, event):
        if event.is_directory:
            return
        
        # 防止重复触发
        now = time.time()
        if event.src_path in self.last_modified:
            if now - self.last_modified[event.src_path] < 1.0:
                return
        
        self.last_modified[event.src_path] = now
        
        # 异步处理文件变更
        asyncio.create_task(self.config_manager.handle_file_change(event.src_path))


class EnhancedConfigManager:
    """增强的配置管理器"""
    
    def __init__(self, cache_service: CacheService):
        self.cache_service = cache_service
        self.cache_namespace = "config_manager"
        self.settings = get_settings()
        
        # 配置存储
        self.config_cache: Dict[str, Any] = {}
        self.config_versions: Dict[str, List[ConfigVersion]] = defaultdict(list)
        self.config_schemas: Dict[ConfigType, type] = {
            ConfigType.SYSTEM: SystemConfigSchema,
            ConfigType.RAGFLOW: RagflowConfigSchema,
            ConfigType.FEATURE_FLAG: FeatureFlagSchema
        }
        
        # 事件处理
        self.event_handlers: Dict[ConfigEvent, List[Callable]] = defaultdict(list)
        self.change_listeners: List[Callable] = []
        
        # 文件监控
        self.file_observer = Observer()
        self.file_watcher = ConfigFileWatcher(self)
        self.watched_paths: List[str] = []
        
        # 环境配置
        self.environment = os.getenv('APP_ENV', 'development')
        self.config_paths = self._get_config_paths()
        
        # 验证器
        self.validators: Dict[ConfigType, List[Callable]] = defaultdict(list)
        
        # 缓存配置
        self.cache_ttl = 3600  # 1小时
        self.cache_enabled = True
        
        # 线程锁
        self.lock = threading.RLock()
        
        # 初始化
        self._initialize_default_validators()
        self._start_file_monitoring()
    
    def _get_config_paths(self) -> List[str]:
        """获取配置文件路径"""
        base_path = Path(__file__).parent.parent.parent
        return [
            str(base_path / "config"),
            str(base_path / f"config/{self.environment}"),
            str(base_path / "config/local"),
        ]
    
    def _initialize_default_validators(self):
        """初始化默认验证器"""
        
        # 系统配置验证器
        def validate_system_config(config_data: Dict[str, Any]) -> ConfigValidationResult:
            errors = []
            warnings = []
            suggestions = []
            
            # 必需字段检查
            if 'config_key' not in config_data:
                errors.append("缺少必需字段: config_key")
            
            if 'config_value' not in config_data:
                errors.append("缺少必需字段: config_value")
            
            # 业务逻辑验证
            if config_data.get('is_readonly', False) and 'SYSTEM' not in config_data.get('category', ''):
                warnings.append("只读配置建议归类为SYSTEM类别")
            
            return ConfigValidationResult(
                is_valid=len(errors) == 0,
                errors=errors,
                warnings=warnings,
                suggestions=suggestions
            )
        
        # RAGFLOW配置验证器
        def validate_ragflow_config(config_data: Dict[str, Any]) -> ConfigValidationResult:
            errors = []
            warnings = []
            suggestions = []
            
            # API端点验证
            if 'api_endpoint' in config_data:
                if not config_data['api_endpoint'].startswith(('http://', 'https://')):
                    errors.append("API端点必须以http://或https://开头")
            
            # 超时时间验证
            timeout = config_data.get('timeout_seconds', 30)
            if timeout < 1 or timeout > 300:
                errors.append("超时时间必须在1-300秒之间")
            
            # 健康检查建议
            if not config_data.get('health_check_url'):
                suggestions.append("建议配置健康检查URL以监控服务状态")
            
            return ConfigValidationResult(
                is_valid=len(errors) == 0,
                errors=errors,
                warnings=warnings,
                suggestions=suggestions
            )
        
        # 功能开关验证器
        def validate_feature_flag(config_data: Dict[str, Any]) -> ConfigValidationResult:
            errors = []
            warnings = []
            suggestions = []
            
            # 时间范围验证
            start_time = config_data.get('start_time')
            end_time = config_data.get('end_time')
            
            if start_time and end_time:
                if start_time >= end_time:
                    errors.append("开始时间必须早于结束时间")
            
            # 推出百分比验证
            rollout = config_data.get('rollout_percentage', 0)
            if rollout < 0 or rollout > 100:
                errors.append("推出百分比必须在0-100之间")
            
            # 生产环境建议
            if self.environment == 'production' and rollout == 100:
                warnings.append("生产环境中建议渐进式推出新功能")
            
            return ConfigValidationResult(
                is_valid=len(errors) == 0,
                errors=errors,
                warnings=warnings,
                suggestions=suggestions
            )
        
        # 注册验证器
        self.validators[ConfigType.SYSTEM].append(validate_system_config)
        self.validators[ConfigType.RAGFLOW].append(validate_ragflow_config)
        self.validators[ConfigType.FEATURE_FLAG].append(validate_feature_flag)
    
    def _start_file_monitoring(self):
        """启动文件监控"""
        try:
            for path in self.config_paths:
                if os.path.exists(path):
                    self.file_observer.schedule(self.file_watcher, path, recursive=True)
                    self.watched_paths.append(path)
            
            self.file_observer.start()
            logger.info(f"配置文件监控已启动，监控路径: {self.watched_paths}")
            
        except Exception as e:
            logger.error(f"启动文件监控失败: {str(e)}")
    
    async def handle_file_change(self, file_path: str):
        """处理文件变更事件"""
        try:
            if file_path.endswith('.json'):
                await self._reload_json_config(file_path)
            elif file_path.endswith('.env'):
                await self._reload_env_config(file_path)
            
            logger.info(f"配置文件已重新加载: {file_path}")
            
        except Exception as e:
            logger.error(f"处理文件变更失败: {file_path}, 错误: {str(e)}")
    
    async def _reload_json_config(self, file_path: str):
        """重新加载JSON配置"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                config_data = json.load(f)
            
            # 根据文件名确定配置类型
            file_name = os.path.basename(file_path)
            if 'ragflow' in file_name.lower():
                config_type = ConfigType.RAGFLOW
            elif 'feature' in file_name.lower():
                config_type = ConfigType.FEATURE_FLAG
            else:
                config_type = ConfigType.SYSTEM
            
            # 验证和应用配置
            await self._apply_config_changes(config_type, config_data)
            
        except Exception as e:
            logger.error(f"重新加载JSON配置失败: {file_path}, 错误: {str(e)}")
    
    async def _reload_env_config(self, file_path: str):
        """重新加载环境配置"""
        try:
            # 重新加载环境变量
            from dotenv import load_dotenv
            load_dotenv(file_path, override=True)
            
            # 重新创建设置实例
            from src.config.settings import Settings
            new_settings = Settings()
            
            # 更新全局设置
            self.settings = new_settings
            
            # 触发环境配置变更事件
            await self._trigger_event(ConfigEvent.RELOADED, 'environment', file_path)
            
        except Exception as e:
            logger.error(f"重新加载环境配置失败: {file_path}, 错误: {str(e)}")
    
    async def _apply_config_changes(self, config_type: ConfigType, config_data: Dict[str, Any]):
        """应用配置变更"""
        with self.lock:
            try:
                # 验证配置
                validation_result = await self.validate_config(config_type, config_data)
                if not validation_result.is_valid:
                    logger.error(f"配置验证失败: {validation_result.errors}")
                    return
                
                # 应用配置
                for key, value in config_data.items():
                    old_value = await self.get_config(key)
                    await self._set_config_internal(config_type, key, value)
                    
                    # 触发变更事件
                    await self._trigger_change_event(ConfigChangeEvent(
                        config_type=config_type,
                        config_key=key,
                        event_type=ConfigEvent.UPDATED,
                        old_value=old_value,
                        new_value=value
                    ))
                
                logger.info(f"配置变更已应用: {config_type.value}, {len(config_data)} 项")
                
            except Exception as e:
                logger.error(f"应用配置变更失败: {str(e)}")
    
    async def get_config(self, key: str, default: Any = None, 
                        config_type: Optional[ConfigType] = None) -> Any:
        """获取配置值"""
        try:
            # 优先从缓存获取
            if self.cache_enabled:
                cache_key = f"config:{key}"
                cached_value = await self.cache_service.get(cache_key, namespace=self.cache_namespace)
                if cached_value is not None:
                    return cached_value
            
            # 从数据库获取
            if config_type == ConfigType.SYSTEM or config_type is None:
                value = SystemConfig.get_config(key, default)
                if value is not None:
                    await self._cache_config(key, value)
                    return value
            
            if config_type == ConfigType.RAGFLOW or config_type is None:
                try:
                    config = RagflowConfig.get(RagflowConfig.config_name == key)
                    value = {
                        'api_endpoint': config.api_endpoint,
                        'api_key': config.api_key,
                        'timeout_seconds': config.timeout_seconds,
                        'rate_limit': config.get_rate_limit(),
                        'fallback_config': config.get_fallback_config(),
                        'health_check_url': config.health_check_url,
                        'is_active': config.is_active
                    }
                    await self._cache_config(key, value)
                    return value
                except RagflowConfig.DoesNotExist:
                    pass
            
            if config_type == ConfigType.FEATURE_FLAG or config_type is None:
                try:
                    flag = FeatureFlag.get(FeatureFlag.flag_name == key)
                    value = {
                        'is_enabled': flag.is_enabled,
                        'description': flag.description,
                        'target_users': flag.get_target_users(),
                        'rollout_percentage': flag.rollout_percentage,
                        'start_time': flag.start_time,
                        'end_time': flag.end_time
                    }
                    await self._cache_config(key, value)
                    return value
                except FeatureFlag.DoesNotExist:
                    pass
            
            # 返回默认值
            return default
            
        except Exception as e:
            logger.error(f"获取配置失败: {key}, 错误: {str(e)}")
            return default
    
    async def set_config(self, key: str, value: Any, config_type: ConfigType,
                        description: Optional[str] = None, 
                        validate: bool = True) -> bool:
        """设置配置值"""
        try:
            with self.lock:
                # 验证配置
                if validate:
                    config_data = {'config_key': key, 'config_value': value}
                    if description:
                        config_data['description'] = description
                    
                    validation_result = await self.validate_config(config_type, config_data)
                    if not validation_result.is_valid:
                        logger.error(f"配置验证失败: {validation_result.errors}")
                        return False
                
                # 获取旧值
                old_value = await self.get_config(key, config_type=config_type)
                
                # 设置配置
                success = await self._set_config_internal(config_type, key, value, description)
                
                if success:
                    # 更新缓存
                    await self._cache_config(key, value)
                    
                    # 创建版本记录
                    await self._create_config_version(key, value, f"更新配置: {key}")
                    
                    # 触发变更事件
                    await self._trigger_change_event(ConfigChangeEvent(
                        config_type=config_type,
                        config_key=key,
                        event_type=ConfigEvent.UPDATED,
                        old_value=old_value,
                        new_value=value
                    ))
                
                return success
                
        except Exception as e:
            logger.error(f"设置配置失败: {key}, 错误: {str(e)}")
            return False
    
    async def _set_config_internal(self, config_type: ConfigType, key: str, value: Any,
                                  description: Optional[str] = None) -> bool:
        """内部设置配置方法"""
        try:
            if config_type == ConfigType.SYSTEM:
                SystemConfig.set_config(key, value, description)
                return True
            
            elif config_type == ConfigType.RAGFLOW:
                if isinstance(value, dict):
                    config, created = RagflowConfig.get_or_create(
                        config_name=key,
                        defaults=value
                    )
                    if not created:
                        for field, field_value in value.items():
                            if hasattr(config, field):
                                setattr(config, field, field_value)
                        config.save()
                    return True
            
            elif config_type == ConfigType.FEATURE_FLAG:
                if isinstance(value, dict):
                    flag, created = FeatureFlag.get_or_create(
                        flag_name=key,
                        defaults=value
                    )
                    if not created:
                        for field, field_value in value.items():
                            if hasattr(flag, field):
                                setattr(flag, field, field_value)
                        flag.save()
                    return True
            
            return False
            
        except Exception as e:
            logger.error(f"内部设置配置失败: {key}, 错误: {str(e)}")
            return False
    
    async def validate_config(self, config_type: ConfigType, 
                            config_data: Dict[str, Any]) -> ConfigValidationResult:
        """验证配置"""
        try:
            # Schema验证
            schema_class = self.config_schemas.get(config_type)
            if schema_class:
                try:
                    schema_class(**config_data)
                except pydantic.ValidationError as e:
                    return ConfigValidationResult(
                        is_valid=False,
                        errors=[str(error) for error in e.errors()]
                    )
            
            # 自定义验证器
            validators = self.validators.get(config_type, [])
            all_errors = []
            all_warnings = []
            all_suggestions = []
            
            for validator in validators:
                result = validator(config_data)
                all_errors.extend(result.errors)
                all_warnings.extend(result.warnings)
                all_suggestions.extend(result.suggestions)
            
            return ConfigValidationResult(
                is_valid=len(all_errors) == 0,
                errors=all_errors,
                warnings=all_warnings,
                suggestions=all_suggestions
            )
            
        except Exception as e:
            logger.error(f"配置验证失败: {str(e)}")
            return ConfigValidationResult(
                is_valid=False,
                errors=[f"验证过程发生错误: {str(e)}"]
            )
    
    async def _cache_config(self, key: str, value: Any):
        """缓存配置"""
        if self.cache_enabled:
            cache_key = f"config:{key}"
            await self.cache_service.set(
                cache_key, value, 
                ttl=self.cache_ttl, 
                namespace=self.cache_namespace
            )
    
    async def _create_config_version(self, key: str, value: Any, description: str):
        """创建配置版本"""
        try:
            # 生成版本号
            version = f"v{len(self.config_versions[key]) + 1}"
            
            # 生成哈希
            content = json.dumps(value, sort_keys=True, ensure_ascii=False)
            hash_value = hashlib.sha256(content.encode()).hexdigest()[:8]
            
            # 创建版本记录
            config_version = ConfigVersion(
                version=version,
                timestamp=datetime.now(),
                hash=hash_value,
                author=os.getenv('USER', 'system'),
                description=description
            )
            
            self.config_versions[key].append(config_version)
            
            # 只保留最近10个版本
            if len(self.config_versions[key]) > 10:
                self.config_versions[key] = self.config_versions[key][-10:]
            
            logger.info(f"创建配置版本: {key} {version}")
            
        except Exception as e:
            logger.error(f"创建配置版本失败: {key}, 错误: {str(e)}")
    
    async def _trigger_change_event(self, event: ConfigChangeEvent):
        """触发配置变更事件"""
        try:
            # 调用所有变更监听器
            for listener in self.change_listeners:
                try:
                    if asyncio.iscoroutinefunction(listener):
                        await listener(event)
                    else:
                        listener(event)
                except Exception as e:
                    logger.error(f"配置变更监听器执行失败: {str(e)}")
            
            # 触发特定事件处理器
            handlers = self.event_handlers.get(event.event_type, [])
            for handler in handlers:
                try:
                    if asyncio.iscoroutinefunction(handler):
                        await handler(event)
                    else:
                        handler(event)
                except Exception as e:
                    logger.error(f"配置事件处理器执行失败: {str(e)}")
            
        except Exception as e:
            logger.error(f"触发配置变更事件失败: {str(e)}")
    
    async def _trigger_event(self, event_type: ConfigEvent, config_key: str, metadata: Any = None):
        """触发配置事件"""
        event = ConfigChangeEvent(
            config_type=ConfigType.SYSTEM,
            config_key=config_key,
            event_type=event_type,
            metadata={'data': metadata} if metadata else {}
        )
        await self._trigger_change_event(event)
    
    def add_change_listener(self, listener: Callable[[ConfigChangeEvent], None]):
        """添加配置变更监听器"""
        self.change_listeners.append(listener)
    
    def add_event_handler(self, event_type: ConfigEvent, handler: Callable):
        """添加事件处理器"""
        self.event_handlers[event_type].append(handler)
    
    def add_validator(self, config_type: ConfigType, validator: Callable):
        """添加自定义验证器"""
        self.validators[config_type].append(validator)
    
    async def get_config_versions(self, key: str) -> List[ConfigVersion]:
        """获取配置版本历史"""
        return self.config_versions.get(key, [])
    
    async def rollback_config(self, key: str, version: str) -> bool:
        """回滚配置到指定版本"""
        try:
            versions = self.config_versions.get(key, [])
            target_version = None
            
            for v in versions:
                if v.version == version:
                    target_version = v
                    break
            
            if not target_version:
                logger.error(f"配置版本不存在: {key} {version}")
                return False
            
            # 这里应该从版本记录中恢复配置值
            # 由于版本记录中没有保存实际值，这里只是示例
            logger.info(f"配置回滚: {key} -> {version}")
            return True
            
        except Exception as e:
            logger.error(f"配置回滚失败: {key}, 错误: {str(e)}")
            return False
    
    async def export_config(self, config_type: Optional[ConfigType] = None, 
                          format: str = 'json') -> str:
        """导出配置"""
        try:
            export_data = {}
            
            if config_type is None or config_type == ConfigType.SYSTEM:
                system_configs = SystemConfig.select()
                export_data['system'] = {
                    config.config_key: config.get_typed_value()
                    for config in system_configs
                }
            
            if config_type is None or config_type == ConfigType.RAGFLOW:
                ragflow_configs = RagflowConfig.select()
                export_data['ragflow'] = {
                    config.config_name: {
                        'api_endpoint': config.api_endpoint,
                        'api_key': config.api_key,
                        'timeout_seconds': config.timeout_seconds,
                        'rate_limit': config.get_rate_limit(),
                        'fallback_config': config.get_fallback_config(),
                        'health_check_url': config.health_check_url,
                        'is_active': config.is_active
                    }
                    for config in ragflow_configs
                }
            
            if config_type is None or config_type == ConfigType.FEATURE_FLAG:
                feature_flags = FeatureFlag.select()
                export_data['feature_flags'] = {
                    flag.flag_name: {
                        'is_enabled': flag.is_enabled,
                        'description': flag.description,
                        'target_users': flag.get_target_users(),
                        'rollout_percentage': flag.rollout_percentage,
                        'start_time': flag.start_time.isoformat() if flag.start_time else None,
                        'end_time': flag.end_time.isoformat() if flag.end_time else None
                    }
                    for flag in feature_flags
                }
            
            if format == 'json':
                return json.dumps(export_data, indent=2, ensure_ascii=False, default=str)
            else:
                return str(export_data)
                
        except Exception as e:
            logger.error(f"导出配置失败: {str(e)}")
            return ""
    
    async def import_config(self, config_data: str, format: str = 'json',
                          validate: bool = True) -> bool:
        """导入配置"""
        try:
            if format == 'json':
                data = json.loads(config_data)
            else:
                data = eval(config_data)
            
            # 导入系统配置
            if 'system' in data:
                for key, value in data['system'].items():
                    await self.set_config(key, value, ConfigType.SYSTEM, validate=validate)
            
            # 导入RAGFLOW配置
            if 'ragflow' in data:
                for key, value in data['ragflow'].items():
                    await self.set_config(key, value, ConfigType.RAGFLOW, validate=validate)
            
            # 导入功能开关
            if 'feature_flags' in data:
                for key, value in data['feature_flags'].items():
                    await self.set_config(key, value, ConfigType.FEATURE_FLAG, validate=validate)
            
            logger.info("配置导入完成")
            return True
            
        except Exception as e:
            logger.error(f"导入配置失败: {str(e)}")
            return False
    
    async def get_config_statistics(self) -> Dict[str, Any]:
        """获取配置统计信息"""
        try:
            stats = {
                'total_configs': 0,
                'config_types': {},
                'cache_hit_rate': 0.0,
                'last_update': None,
                'watched_paths': self.watched_paths,
                'environment': self.environment
            }
            
            # 统计系统配置
            system_count = SystemConfig.select().count()
            stats['config_types']['system'] = system_count
            stats['total_configs'] += system_count
            
            # 统计RAGFLOW配置
            ragflow_count = RagflowConfig.select().count()
            stats['config_types']['ragflow'] = ragflow_count
            stats['total_configs'] += ragflow_count
            
            # 统计功能开关
            feature_count = FeatureFlag.select().count()
            stats['config_types']['feature_flags'] = feature_count
            stats['total_configs'] += feature_count
            
            # 获取缓存统计
            cache_stats = await self.cache_service.get_stats()
            if cache_stats:
                stats['cache_hit_rate'] = cache_stats.get('hit_rate', 0.0)
            
            return stats
            
        except Exception as e:
            logger.error(f"获取配置统计失败: {str(e)}")
            return {}
    
    async def cleanup(self):
        """清理资源"""
        try:
            # 停止文件监控
            if self.file_observer.is_alive():
                self.file_observer.stop()
                self.file_observer.join()
            
            # 清理缓存
            await self.cache_service.delete_pattern(
                f"config:*", 
                namespace=self.cache_namespace
            )
            
            logger.info("配置管理器已清理")
            
        except Exception as e:
            logger.error(f"清理配置管理器失败: {str(e)}")


# 全局配置管理器实例
_config_manager: Optional[EnhancedConfigManager] = None


def get_config_manager(cache_service: CacheService) -> EnhancedConfigManager:
    """获取全局配置管理器实例"""
    global _config_manager
    
    if _config_manager is None:
        _config_manager = EnhancedConfigManager(cache_service)
    
    return _config_manager