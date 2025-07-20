"""
环境特定配置管理系统 (TASK-033)
提供多环境配置管理、配置继承、环境切换和配置隔离功能
"""
from typing import Dict, List, Optional, Any, Set
from dataclasses import dataclass, field
from enum import Enum
import os
import json
from pathlib import Path
from datetime import datetime

from src.core.config_manager import ConfigType, EnhancedConfigManager
from src.core.config_validator import get_config_validator
from src.services.cache_service import CacheService
from src.utils.logger import get_logger

logger = get_logger(__name__)


class Environment(Enum):
    """环境类型"""
    DEVELOPMENT = "development"
    TESTING = "testing"
    STAGING = "staging"
    PRODUCTION = "production"
    LOCAL = "local"


class ConfigScope(Enum):
    """配置作用域"""
    GLOBAL = "global"        # 全局配置，所有环境共享
    ENVIRONMENT = "environment"  # 环境特定配置
    LOCAL = "local"          # 本地覆盖配置
    RUNTIME = "runtime"      # 运行时配置


@dataclass
class EnvironmentConfig:
    """环境配置"""
    environment: Environment
    config_data: Dict[str, Any]
    parent_environment: Optional[Environment] = None
    inherit_from_parent: bool = True
    override_rules: Dict[str, Any] = field(default_factory=dict)
    validation_rules: Dict[str, Any] = field(default_factory=dict)
    
    def merge_with_parent(self, parent_config: 'EnvironmentConfig') -> Dict[str, Any]:
        """与父环境配置合并"""
        if not self.inherit_from_parent or not parent_config:
            return self.config_data.copy()
        
        merged_config = parent_config.config_data.copy()
        
        # 递归合并配置
        self._deep_merge(merged_config, self.config_data)
        
        # 应用覆盖规则
        self._apply_override_rules(merged_config)
        
        return merged_config
    
    def _deep_merge(self, target: Dict[str, Any], source: Dict[str, Any]):
        """深度合并字典"""
        for key, value in source.items():
            if key in target and isinstance(target[key], dict) and isinstance(value, dict):
                self._deep_merge(target[key], value)
            else:
                target[key] = value
    
    def _apply_override_rules(self, config: Dict[str, Any]):
        """应用覆盖规则"""
        for key, rule in self.override_rules.items():
            if key in config:
                if rule.get('force_override', False):
                    config[key] = rule['value']
                elif rule.get('append_list', False) and isinstance(config[key], list):
                    config[key].extend(rule['value'])


class EnvironmentConfigManager:
    """环境配置管理器"""
    
    def __init__(self, cache_service: CacheService, base_config_manager: EnhancedConfigManager):
        self.cache_service = cache_service
        self.base_config_manager = base_config_manager
        self.cache_namespace = "env_config"
        self.validator = get_config_validator()
        
        # 当前环境
        self.current_environment = Environment(os.getenv('APP_ENV', 'development'))
        
        # 环境配置存储
        self.environment_configs: Dict[Environment, EnvironmentConfig] = {}
        
        # 配置路径
        self.config_base_path = Path(__file__).parent.parent.parent / "config"
        
        # 环境继承关系
        self.environment_hierarchy = {
            Environment.PRODUCTION: None,
            Environment.STAGING: Environment.PRODUCTION,
            Environment.TESTING: Environment.STAGING,
            Environment.DEVELOPMENT: Environment.TESTING,
            Environment.LOCAL: Environment.DEVELOPMENT
        }
        
        # 配置缓存
        self.config_cache: Dict[str, Any] = {}
        self.cache_timestamps: Dict[str, datetime] = {}
        self.cache_ttl = 300  # 5分钟
        
        # 初始化
        self._initialize_environments()
    
    def _initialize_environments(self):
        """初始化环境配置"""
        try:
            # 加载所有环境配置
            for env in Environment:
                self._load_environment_config(env)
            
            logger.info(f"环境配置管理器初始化完成，当前环境: {self.current_environment.value}")
            
        except Exception as e:
            logger.error(f"初始化环境配置失败: {str(e)}")
    
    def _load_environment_config(self, environment: Environment):
        """加载环境配置"""
        try:
            config_file = self.config_base_path / f"{environment.value}.json"
            
            if config_file.exists():
                with open(config_file, 'r', encoding='utf-8') as f:
                    config_data = json.load(f)
            else:
                config_data = {}
            
            # 创建环境配置
            env_config = EnvironmentConfig(
                environment=environment,
                config_data=config_data,
                parent_environment=self.environment_hierarchy.get(environment)
            )
            
            self.environment_configs[environment] = env_config
            
            logger.info(f"加载环境配置: {environment.value}, {len(config_data)} 项配置")
            
        except Exception as e:
            logger.error(f"加载环境配置失败: {environment.value}, 错误: {str(e)}")
            # 创建空配置
            self.environment_configs[environment] = EnvironmentConfig(
                environment=environment,
                config_data={}
            )
    
    def get_config(self, key: str, default: Any = None, 
                  environment: Optional[Environment] = None,
                  use_cache: bool = True) -> Any:
        """获取环境配置"""
        try:
            target_env = environment or self.current_environment
            cache_key = f"{target_env.value}:{key}"
            
            # 检查缓存
            if use_cache and self._is_cache_valid(cache_key):
                return self.config_cache.get(cache_key, default)
            
            # 获取合并后的配置
            merged_config = self._get_merged_config(target_env)
            
            # 获取配置值
            value = self._get_nested_value(merged_config, key, default)
            
            # 更新缓存
            if use_cache:
                self.config_cache[cache_key] = value
                self.cache_timestamps[cache_key] = datetime.now()
            
            return value
            
        except Exception as e:
            logger.error(f"获取环境配置失败: {key}, 错误: {str(e)}")
            return default
    
    def set_config(self, key: str, value: Any, 
                  environment: Optional[Environment] = None,
                  scope: ConfigScope = ConfigScope.ENVIRONMENT,
                  validate: bool = True) -> bool:
        """设置环境配置"""
        try:
            target_env = environment or self.current_environment
            
            # 验证配置
            if validate:
                validation_result = self._validate_config(key, value, target_env)
                if not validation_result['is_valid']:
                    logger.error(f"配置验证失败: {validation_result['errors']}")
                    return False
            
            # 获取环境配置
            env_config = self.environment_configs.get(target_env)
            if not env_config:
                logger.error(f"环境配置不存在: {target_env.value}")
                return False
            
            # 设置配置值
            self._set_nested_value(env_config.config_data, key, value)
            
            # 保存到文件
            self._save_environment_config(target_env)
            
            # 清除相关缓存
            self._invalidate_cache(target_env, key)
            
            logger.info(f"设置环境配置: {target_env.value}:{key} = {value}")
            return True
            
        except Exception as e:
            logger.error(f"设置环境配置失败: {key}, 错误: {str(e)}")
            return False
    
    def _get_merged_config(self, environment: Environment) -> Dict[str, Any]:
        """获取合并后的环境配置"""
        env_config = self.environment_configs.get(environment)
        if not env_config:
            return {}
        
        # 如果有父环境，先获取父环境的合并配置
        parent_env = env_config.parent_environment
        if parent_env and env_config.inherit_from_parent:
            parent_config = self.environment_configs.get(parent_env)
            if parent_config:
                parent_merged = self._get_merged_config(parent_env)
                parent_config_with_merged = EnvironmentConfig(
                    environment=parent_env,
                    config_data=parent_merged
                )
                return env_config.merge_with_parent(parent_config_with_merged)
        
        return env_config.config_data.copy()
    
    def _get_nested_value(self, data: Dict[str, Any], key: str, default: Any = None) -> Any:
        """获取嵌套字典的值"""
        keys = key.split('.')
        current = data
        
        for k in keys:
            if isinstance(current, dict) and k in current:
                current = current[k]
            else:
                return default
        
        return current
    
    def _set_nested_value(self, data: Dict[str, Any], key: str, value: Any):
        """设置嵌套字典的值"""
        keys = key.split('.')
        current = data
        
        for k in keys[:-1]:
            if k not in current:
                current[k] = {}
            current = current[k]
        
        current[keys[-1]] = value
    
    def _save_environment_config(self, environment: Environment):
        """保存环境配置到文件"""
        try:
            env_config = self.environment_configs.get(environment)
            if not env_config:
                return
            
            config_file = self.config_base_path / f"{environment.value}.json"
            
            # 确保目录存在
            config_file.parent.mkdir(parents=True, exist_ok=True)
            
            # 保存配置
            with open(config_file, 'w', encoding='utf-8') as f:
                json.dump(env_config.config_data, f, indent=2, ensure_ascii=False)
            
            logger.info(f"保存环境配置: {environment.value}")
            
        except Exception as e:
            logger.error(f"保存环境配置失败: {environment.value}, 错误: {str(e)}")
    
    def _validate_config(self, key: str, value: Any, environment: Environment) -> Dict[str, Any]:
        """验证环境配置"""
        try:
            # 基本类型检查
            if not isinstance(key, str) or not key:
                return {
                    'is_valid': False,
                    'errors': ['配置键必须是非空字符串']
                }
            
            # 环境特定验证
            if environment == Environment.PRODUCTION:
                # 生产环境特殊验证
                if 'debug' in key.lower() and value is True:
                    return {
                        'is_valid': False,
                        'errors': ['生产环境不允许开启调试模式']
                    }
                
                if 'test' in key.lower():
                    return {
                        'is_valid': False,
                        'errors': ['生产环境不允许测试相关配置']
                    }
            
            # 敏感信息检查
            sensitive_keys = ['password', 'secret', 'key', 'token', 'credential']
            if any(sensitive_key in key.lower() for sensitive_key in sensitive_keys):
                if isinstance(value, str) and len(value) < 8:
                    return {
                        'is_valid': False,
                        'errors': ['敏感配置值长度不足']
                    }
            
            return {'is_valid': True, 'errors': []}
            
        except Exception as e:
            return {
                'is_valid': False,
                'errors': [f'验证过程发生错误: {str(e)}']
            }
    
    def _is_cache_valid(self, cache_key: str) -> bool:
        """检查缓存是否有效"""
        if cache_key not in self.cache_timestamps:
            return False
        
        cache_time = self.cache_timestamps[cache_key]
        return (datetime.now() - cache_time).total_seconds() < self.cache_ttl
    
    def _invalidate_cache(self, environment: Environment, key: str = None):
        """使缓存失效"""
        if key:
            # 清除特定键的缓存
            cache_key = f"{environment.value}:{key}"
            self.config_cache.pop(cache_key, None)
            self.cache_timestamps.pop(cache_key, None)
        else:
            # 清除环境相关的所有缓存
            keys_to_remove = [
                k for k in self.config_cache.keys() 
                if k.startswith(f"{environment.value}:")
            ]
            for k in keys_to_remove:
                self.config_cache.pop(k, None)
                self.cache_timestamps.pop(k, None)
    
    def switch_environment(self, environment: Environment) -> bool:
        """切换当前环境"""
        try:
            if environment not in self.environment_configs:
                logger.error(f"环境不存在: {environment.value}")
                return False
            
            old_env = self.current_environment
            self.current_environment = environment
            
            # 清除所有缓存
            self.config_cache.clear()
            self.cache_timestamps.clear()
            
            logger.info(f"环境切换: {old_env.value} -> {environment.value}")
            return True
            
        except Exception as e:
            logger.error(f"切换环境失败: {environment.value}, 错误: {str(e)}")
            return False
    
    def get_environment_diff(self, env1: Environment, env2: Environment) -> Dict[str, Any]:
        """比较两个环境的配置差异"""
        try:
            config1 = self._get_merged_config(env1)
            config2 = self._get_merged_config(env2)
            
            diff = {
                'added_in_env2': {},
                'removed_in_env2': {},
                'modified': {},
                'summary': {}
            }
            
            # 比较配置
            all_keys = set(config1.keys()) | set(config2.keys())
            
            for key in all_keys:
                if key not in config1:
                    diff['added_in_env2'][key] = config2[key]
                elif key not in config2:
                    diff['removed_in_env2'][key] = config1[key]
                elif config1[key] != config2[key]:
                    diff['modified'][key] = {
                        'from': config1[key],
                        'to': config2[key]
                    }
            
            # 生成摘要
            diff['summary'] = {
                'total_changes': len(diff['added_in_env2']) + len(diff['removed_in_env2']) + len(diff['modified']),
                'added_count': len(diff['added_in_env2']),
                'removed_count': len(diff['removed_in_env2']),
                'modified_count': len(diff['modified'])
            }
            
            return diff
            
        except Exception as e:
            logger.error(f"比较环境配置失败: {env1.value} vs {env2.value}, 错误: {str(e)}")
            return {}
    
    def export_environment_config(self, environment: Environment, 
                                 include_inherited: bool = True) -> Dict[str, Any]:
        """导出环境配置"""
        try:
            if include_inherited:
                config_data = self._get_merged_config(environment)
            else:
                env_config = self.environment_configs.get(environment)
                config_data = env_config.config_data if env_config else {}
            
            return {
                'environment': environment.value,
                'export_time': datetime.now().isoformat(),
                'include_inherited': include_inherited,
                'config': config_data
            }
            
        except Exception as e:
            logger.error(f"导出环境配置失败: {environment.value}, 错误: {str(e)}")
            return {}
    
    def import_environment_config(self, environment: Environment, 
                                 config_data: Dict[str, Any],
                                 merge_mode: str = 'replace') -> bool:
        """导入环境配置"""
        try:
            env_config = self.environment_configs.get(environment)
            if not env_config:
                logger.error(f"环境不存在: {environment.value}")
                return False
            
            if merge_mode == 'replace':
                env_config.config_data = config_data.copy()
            elif merge_mode == 'merge':
                env_config._deep_merge(env_config.config_data, config_data)
            elif merge_mode == 'update':
                env_config.config_data.update(config_data)
            
            # 保存配置
            self._save_environment_config(environment)
            
            # 清除缓存
            self._invalidate_cache(environment)
            
            logger.info(f"导入环境配置: {environment.value}, 模式: {merge_mode}")
            return True
            
        except Exception as e:
            logger.error(f"导入环境配置失败: {environment.value}, 错误: {str(e)}")
            return False
    
    def get_config_sources(self, key: str, environment: Optional[Environment] = None) -> List[Dict[str, Any]]:
        """获取配置的来源层次"""
        target_env = environment or self.current_environment
        sources = []
        
        # 从当前环境开始，向上追溯继承链
        current_env = target_env
        while current_env:
            env_config = self.environment_configs.get(current_env)
            if env_config:
                value = self._get_nested_value(env_config.config_data, key)
                if value is not None:
                    sources.append({
                        'environment': current_env.value,
                        'value': value,
                        'is_inherited': current_env != target_env
                    })
            
            # 移动到父环境
            current_env = self.environment_hierarchy.get(current_env)
        
        return sources
    
    def validate_all_environments(self) -> Dict[str, Any]:
        """验证所有环境配置"""
        results = {}
        
        for env in Environment:
            env_config = self.environment_configs.get(env)
            if env_config:
                merged_config = self._get_merged_config(env)
                
                # 验证每个配置项
                validation_errors = []
                for key, value in merged_config.items():
                    validation_result = self._validate_config(key, value, env)
                    if not validation_result['is_valid']:
                        validation_errors.extend([
                            f"{key}: {error}" for error in validation_result['errors']
                        ])
                
                results[env.value] = {
                    'is_valid': len(validation_errors) == 0,
                    'errors': validation_errors,
                    'config_count': len(merged_config)
                }
        
        return results
    
    def get_statistics(self) -> Dict[str, Any]:
        """获取环境配置统计信息"""
        try:
            stats = {
                'current_environment': self.current_environment.value,
                'total_environments': len(self.environment_configs),
                'cache_stats': {
                    'cached_configs': len(self.config_cache),
                    'cache_hit_rate': 0.0
                },
                'environment_stats': {}
            }
            
            # 统计每个环境的配置
            for env, env_config in self.environment_configs.items():
                merged_config = self._get_merged_config(env)
                stats['environment_stats'][env.value] = {
                    'direct_configs': len(env_config.config_data),
                    'merged_configs': len(merged_config),
                    'has_parent': env_config.parent_environment is not None,
                    'parent_environment': env_config.parent_environment.value if env_config.parent_environment else None
                }
            
            return stats
            
        except Exception as e:
            logger.error(f"获取环境配置统计失败: {str(e)}")
            return {}
    
    def cleanup(self):
        """清理资源"""
        try:
            # 清理缓存
            self.config_cache.clear()
            self.cache_timestamps.clear()
            
            logger.info("环境配置管理器已清理")
            
        except Exception as e:
            logger.error(f"清理环境配置管理器失败: {str(e)}")


# 全局环境配置管理器实例
_env_config_manager: Optional[EnvironmentConfigManager] = None


def get_environment_config_manager(cache_service: CacheService, 
                                 base_config_manager: EnhancedConfigManager) -> EnvironmentConfigManager:
    """获取全局环境配置管理器实例"""
    global _env_config_manager
    
    if _env_config_manager is None:
        _env_config_manager = EnvironmentConfigManager(cache_service, base_config_manager)
    
    return _env_config_manager