"""
配置验证服务 (TASK-033)
提供配置的业务逻辑验证、安全性检查和最佳实践建议
"""
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass
from enum import Enum
import re
import json
import ipaddress
from urllib.parse import urlparse
from datetime import datetime, timedelta

from src.core.config_manager import ConfigValidationResult, ConfigType
from src.utils.logger import get_logger

logger = get_logger(__name__)


class ValidationLevel(Enum):
    """验证级别"""
    CRITICAL = "critical"    # 严重错误，会导致系统无法运行
    ERROR = "error"         # 错误，会影响功能正常使用
    WARNING = "warning"     # 警告，可能存在风险
    INFO = "info"          # 信息提示，最佳实践建议


@dataclass
class ValidationRule:
    """验证规则"""
    name: str
    description: str
    level: ValidationLevel
    validator: Callable[[Any], bool]
    message: str
    suggestion: Optional[str] = None


class ValidationResult:
    """验证结果（临时定义）"""
    def __init__(self, is_valid: bool, errors: List[str] = None, 
                 warnings: List[str] = None, suggestions: List[str] = None):
        self.is_valid = is_valid
        self.errors = errors or []
        self.warnings = warnings or []
        self.suggestions = suggestions or []


class SecurityValidator:
    """安全性验证器"""
    
    @staticmethod
    def validate_api_key(api_key: str) -> ValidationResult:
        """验证API密钥安全性"""
        errors = []
        warnings = []
        suggestions = []
        
        if not api_key:
            return ValidationResult(True, [], [], [])
        
        # 长度检查
        if len(api_key) < 16:
            errors.append("API密钥长度不足16位，存在安全风险")
        elif len(api_key) < 32:
            warnings.append("建议API密钥长度不少于32位")
        
        # 复杂度检查
        if api_key.isalnum():
            warnings.append("API密钥建议包含特殊字符以提高安全性")
        
        # 常见弱密钥检查
        weak_patterns = [
            r'^[0-9]+$',           # 纯数字
            r'^[a-zA-Z]+$',        # 纯字母
            r'^(test|demo|dev)',   # 测试密钥
            r'(password|123456)',  # 常见弱密钥
        ]
        
        for pattern in weak_patterns:
            if re.search(pattern, api_key, re.IGNORECASE):
                errors.append("检测到弱API密钥模式，存在安全风险")
                suggestions.append("使用随机生成的强密钥")
                break
        
        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            suggestions=suggestions
        )
    
    @staticmethod
    def validate_url_security(url: str) -> ValidationResult:
        """验证URL安全性"""
        errors = []
        warnings = []
        suggestions = []
        
        try:
            parsed = urlparse(url)
            
            # HTTPS检查
            if parsed.scheme != 'https':
                if parsed.hostname in ['localhost', '127.0.0.1']:
                    warnings.append("本地开发环境建议使用HTTPS")
                else:
                    errors.append("生产环境必须使用HTTPS协议")
                    suggestions.append("将HTTP协议更改为HTTPS")
            
            # 端口检查
            if parsed.port:
                if parsed.port in [80, 443, 8080, 8443]:
                    # 标准端口，通常OK
                    pass
                elif parsed.port < 1024:
                    warnings.append("使用系统保留端口可能存在权限问题")
                elif parsed.port > 65535:
                    errors.append("端口号超出有效范围")
            
            # IP地址检查
            if parsed.hostname:
                try:
                    ip = ipaddress.ip_address(parsed.hostname)
                    if ip.is_private:
                        warnings.append("使用私有IP地址，确保网络可达性")
                    elif ip.is_loopback:
                        warnings.append("使用回环地址，仅限本地访问")
                except ValueError:
                    # 不是IP地址，是域名
                    pass
            
        except Exception as e:
            errors.append(f"URL格式无效: {str(e)}")
        
        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            suggestions=suggestions
        )


class PerformanceValidator:
    """性能验证器"""
    
    @staticmethod
    def validate_timeout_settings(timeout: int, context: str = "") -> ValidationResult:
        """验证超时设置"""
        errors = []
        warnings = []
        suggestions = []
        
        # 基本范围检查
        if timeout <= 0:
            errors.append("超时时间必须大于0")
        elif timeout > 300:  # 5分钟
            warnings.append("超时时间过长可能影响用户体验")
            suggestions.append("建议超时时间不超过300秒")
        
        # 根据上下文提供建议
        if context.lower() in ['api', 'http', 'web']:
            if timeout < 5:
                warnings.append("API调用超时时间过短可能导致频繁失败")
            elif timeout > 60:
                warnings.append("API调用超时时间过长影响响应性")
                suggestions.append("建议API超时时间在5-60秒之间")
        
        elif context.lower() in ['database', 'db']:
            if timeout < 1:
                warnings.append("数据库超时时间过短")
            elif timeout > 30:
                warnings.append("数据库超时时间过长")
                suggestions.append("建议数据库超时时间在1-30秒之间")
        
        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            suggestions=suggestions
        )
    
    @staticmethod
    def validate_rate_limit(rate_limit: Dict[str, int]) -> ValidationResult:
        """验证速率限制配置"""
        errors = []
        warnings = []
        suggestions = []
        
        required_keys = ['requests_per_minute', 'requests_per_hour']
        for key in required_keys:
            if key not in rate_limit:
                errors.append(f"缺少必需的速率限制配置: {key}")
        
        if errors:
            return ValidationResult(False, errors, warnings, suggestions)
        
        rpm = rate_limit.get('requests_per_minute', 0)
        rph = rate_limit.get('requests_per_hour', 0)
        
        # 逻辑一致性检查
        if rpm * 60 > rph:
            errors.append("每分钟请求数与每小时请求数配置不一致")
            suggestions.append("确保每分钟请求数 * 60 <= 每小时请求数")
        
        # 合理性检查
        if rpm > 1000:
            warnings.append("每分钟请求数过高，可能给服务器造成压力")
        elif rpm < 1:
            warnings.append("每分钟请求数过低，可能影响系统性能")
        
        if rph > 60000:
            warnings.append("每小时请求数过高")
        elif rph < 60:
            warnings.append("每小时请求数过低")
        
        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            suggestions=suggestions
        )


class BusinessLogicValidator:
    """业务逻辑验证器"""
    
    @staticmethod
    def validate_ragflow_config(config: Dict[str, Any]) -> ValidationResult:
        """验证RAGFLOW配置的业务逻辑"""
        errors = []
        warnings = []
        suggestions = []
        
        # API端点验证
        if 'api_endpoint' in config:
            url_result = SecurityValidator.validate_url_security(config['api_endpoint'])
            errors.extend(url_result.errors)
            warnings.extend(url_result.warnings)
            suggestions.extend(url_result.suggestions)
        
        # 超时配置验证
        if 'timeout_seconds' in config:
            timeout_result = PerformanceValidator.validate_timeout_settings(
                config['timeout_seconds'], 'api'
            )
            errors.extend(timeout_result.errors)
            warnings.extend(timeout_result.warnings)
            suggestions.extend(timeout_result.suggestions)
        
        # 速率限制验证
        if 'rate_limit' in config and config['rate_limit']:
            rate_result = PerformanceValidator.validate_rate_limit(config['rate_limit'])
            errors.extend(rate_result.errors)
            warnings.extend(rate_result.warnings)
            suggestions.extend(rate_result.suggestions)
        
        # API密钥验证
        if 'api_key' in config and config['api_key']:
            key_result = SecurityValidator.validate_api_key(config['api_key'])
            errors.extend(key_result.errors)
            warnings.extend(key_result.warnings)
            suggestions.extend(key_result.suggestions)
        
        # 健康检查URL验证
        if 'health_check_url' in config and config['health_check_url']:
            health_result = SecurityValidator.validate_url_security(config['health_check_url'])
            errors.extend(health_result.errors)
            warnings.extend(health_result.warnings)
            suggestions.extend(health_result.suggestions)
        else:
            suggestions.append("建议配置健康检查URL以监控服务状态")
        
        # 回退配置验证
        if 'fallback_config' in config and config['fallback_config']:
            fallback_config = config['fallback_config']
            if not isinstance(fallback_config, dict):
                errors.append("回退配置必须是字典格式")
            else:
                # 验证回退配置的完整性
                expected_keys = ['enabled', 'max_retries', 'retry_delay']
                missing_keys = [key for key in expected_keys if key not in fallback_config]
                if missing_keys:
                    warnings.append(f"回退配置缺少推荐字段: {missing_keys}")
        
        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            suggestions=suggestions
        )
    
    @staticmethod
    def validate_feature_flag(config: Dict[str, Any]) -> ValidationResult:
        """验证功能开关的业务逻辑"""
        errors = []
        warnings = []
        suggestions = []
        
        # 时间范围验证
        start_time = config.get('start_time')
        end_time = config.get('end_time')
        
        if start_time and end_time:
            if isinstance(start_time, str):
                start_time = datetime.fromisoformat(start_time.replace('Z', '+00:00'))
            if isinstance(end_time, str):
                end_time = datetime.fromisoformat(end_time.replace('Z', '+00:00'))
            
            if start_time >= end_time:
                errors.append("开始时间必须早于结束时间")
            
            # 时间范围合理性检查
            duration = end_time - start_time
            if duration < timedelta(hours=1):
                warnings.append("功能开关时间范围过短，可能影响测试效果")
            elif duration > timedelta(days=365):
                warnings.append("功能开关时间范围过长，建议定期评估")
        
        # 推出百分比验证
        rollout = config.get('rollout_percentage', 0)
        if rollout < 0 or rollout > 100:
            errors.append("推出百分比必须在0-100之间")
        elif rollout == 100:
            warnings.append("100%推出时建议确认功能稳定性")
            suggestions.append("考虑先进行小范围测试")
        
        # 目标用户验证
        target_users = config.get('target_users', [])
        if target_users and not isinstance(target_users, list):
            errors.append("目标用户必须是列表格式")
        elif isinstance(target_users, list) and len(target_users) > 1000:
            warnings.append("目标用户列表过长，可能影响性能")
            suggestions.append("考虑使用用户分组策略")
        
        # 功能开关命名验证
        flag_name = config.get('flag_name', '')
        if flag_name:
            if not re.match(r'^[a-zA-Z][a-zA-Z0-9_-]*$', flag_name):
                errors.append("功能开关名称必须以字母开头，只能包含字母、数字、下划线和连字符")
            elif len(flag_name) > 100:
                errors.append("功能开关名称过长")
            elif '_' not in flag_name and '-' not in flag_name:
                suggestions.append("建议使用下划线或连字符提高可读性")
        
        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            suggestions=suggestions
        )


class EnvironmentValidator:
    """环境相关验证器"""
    
    @staticmethod
    def validate_production_readiness(config: Dict[str, Any], config_type: ConfigType) -> ValidationResult:
        """验证生产环境就绪性"""
        errors = []
        warnings = []
        suggestions = []
        
        import os
        environment = os.getenv('APP_ENV', 'development')
        
        if environment != 'production':
            return ValidationResult(True, [], [], [])
        
        # 生产环境特定验证
        if config_type == ConfigType.RAGFLOW:
            # API密钥必须配置
            if not config.get('api_key'):
                errors.append("生产环境必须配置API密钥")
            
            # 必须使用HTTPS
            api_endpoint = config.get('api_endpoint', '')
            if api_endpoint and not api_endpoint.startswith('https://'):
                errors.append("生产环境必须使用HTTPS协议")
            
            # 必须配置健康检查
            if not config.get('health_check_url'):
                warnings.append("生产环境建议配置健康检查URL")
            
            # 超时配置检查
            timeout = config.get('timeout_seconds', 30)
            if timeout > 60:
                warnings.append("生产环境建议API超时时间不超过60秒")
        
        elif config_type == ConfigType.FEATURE_FLAG:
            # 功能开关推出策略
            rollout = config.get('rollout_percentage', 0)
            if rollout == 100 and not config.get('end_time'):
                warnings.append("生产环境100%推出的功能建议设置结束时间")
            
            # 目标用户策略
            target_users = config.get('target_users', [])
            if not target_users and rollout < 100:
                warnings.append("部分推出时建议明确指定目标用户")
        
        elif config_type == ConfigType.SYSTEM:
            # 系统配置安全性
            config_key = config.get('config_key', '')
            config_value = str(config.get('config_value', ''))
            
            # 敏感信息检查
            sensitive_patterns = [
                r'password', r'secret', r'key', r'token', r'credential'
            ]
            if any(re.search(pattern, config_key, re.IGNORECASE) for pattern in sensitive_patterns):
                if len(config_value) < 16:
                    errors.append("敏感配置值长度不足，存在安全风险")
                warnings.append("敏感配置建议使用环境变量管理")
        
        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            suggestions=suggestions
        )


class ConfigValidatorService:
    """配置验证服务"""
    
    def __init__(self):
        self.security_validator = SecurityValidator()
        self.performance_validator = PerformanceValidator()
        self.business_validator = BusinessLogicValidator()
        self.environment_validator = EnvironmentValidator()
        
        # 自定义验证规则
        self.custom_rules: Dict[ConfigType, List[ValidationRule]] = {
            ConfigType.SYSTEM: [],
            ConfigType.RAGFLOW: [],
            ConfigType.FEATURE_FLAG: []
        }
    
    def validate_config(self, config_type: ConfigType, config_data: Dict[str, Any]) -> ConfigValidationResult:
        """综合验证配置"""
        all_errors = []
        all_warnings = []
        all_suggestions = []
        
        try:
            # 业务逻辑验证
            if config_type == ConfigType.RAGFLOW:
                result = self.business_validator.validate_ragflow_config(config_data)
            elif config_type == ConfigType.FEATURE_FLAG:
                result = self.business_validator.validate_feature_flag(config_data)
            else:
                result = ValidationResult(True, [], [], [])
            
            all_errors.extend(result.errors)
            all_warnings.extend(result.warnings)
            all_suggestions.extend(result.suggestions)
            
            # 环境验证
            env_result = self.environment_validator.validate_production_readiness(
                config_data, config_type
            )
            all_errors.extend(env_result.errors)
            all_warnings.extend(env_result.warnings)
            all_suggestions.extend(env_result.suggestions)
            
            # 自定义规则验证
            custom_rules = self.custom_rules.get(config_type, [])
            for rule in custom_rules:
                try:
                    if not rule.validator(config_data):
                        if rule.level == ValidationLevel.CRITICAL or rule.level == ValidationLevel.ERROR:
                            all_errors.append(f"{rule.name}: {rule.message}")
                        elif rule.level == ValidationLevel.WARNING:
                            all_warnings.append(f"{rule.name}: {rule.message}")
                        
                        if rule.suggestion:
                            all_suggestions.append(rule.suggestion)
                except Exception as e:
                    logger.error(f"自定义验证规则执行失败: {rule.name}, 错误: {str(e)}")
            
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
                errors=[f"验证过程发生错误: {str(e)}"],
                warnings=all_warnings,
                suggestions=all_suggestions
            )
    
    def add_custom_rule(self, config_type: ConfigType, rule: ValidationRule):
        """添加自定义验证规则"""
        self.custom_rules[config_type].append(rule)
        logger.info(f"添加自定义验证规则: {config_type.value} - {rule.name}")
    
    def remove_custom_rule(self, config_type: ConfigType, rule_name: str) -> bool:
        """移除自定义验证规则"""
        rules = self.custom_rules.get(config_type, [])
        for i, rule in enumerate(rules):
            if rule.name == rule_name:
                del rules[i]
                logger.info(f"移除自定义验证规则: {config_type.value} - {rule_name}")
                return True
        return False
    
    def get_validation_report(self, config_type: ConfigType, config_data: Dict[str, Any]) -> Dict[str, Any]:
        """获取详细的验证报告"""
        result = self.validate_config(config_type, config_data)
        
        return {
            'config_type': config_type.value,
            'is_valid': result.is_valid,
            'validation_time': datetime.now().isoformat(),
            'summary': {
                'total_errors': len(result.errors),
                'total_warnings': len(result.warnings),
                'total_suggestions': len(result.suggestions)
            },
            'errors': result.errors,
            'warnings': result.warnings,
            'suggestions': result.suggestions,
            'recommendation': self._get_recommendation(result)
        }
    
    def _get_recommendation(self, result: ConfigValidationResult) -> str:
        """获取验证建议"""
        if not result.is_valid:
            return "配置存在错误，需要修复后才能使用"
        elif result.warnings:
            return "配置基本正确，但存在一些需要注意的问题"
        elif result.suggestions:
            return "配置正确，建议参考优化建议进一步改进"
        else:
            return "配置完全正确，符合最佳实践"


# 全局验证服务实例
_validator_service: Optional[ConfigValidatorService] = None


def get_config_validator() -> ConfigValidatorService:
    """获取配置验证服务实例"""
    global _validator_service
    
    if _validator_service is None:
        _validator_service = ConfigValidatorService()
    
    return _validator_service