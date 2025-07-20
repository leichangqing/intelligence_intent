"""
API包装器管理器
管理和协调多个API包装器实例，提供统一的API调用接口
"""

import asyncio
import json
from typing import Dict, List, Optional, Any, Callable
from datetime import datetime, timedelta
from dataclasses import asdict

from src.core.api_wrapper import (
    ApiWrapper, ApiWrapperConfig, ApiWrapperFactory, ApiRequest, ApiResponse,
    HttpMethod, AuthType, AuthConfig, RetryConfig, RateLimitConfig, CacheConfig,
    ContentType, RetryStrategy, create_simple_wrapper
)
from src.models.function_call import FunctionCall as FunctionCallConfig, ApiCallLog
from src.services.cache_service import CacheService
from src.utils.logger import get_logger

logger = get_logger(__name__)


class ApiWrapperManager:
    """API包装器管理器"""
    
    def __init__(self, cache_service: CacheService):
        self.cache_service = cache_service
        self.wrappers: Dict[str, ApiWrapper] = {}
        self.configurations: Dict[str, ApiWrapperConfig] = {}
        self.templates: Dict[str, Dict[str, Any]] = {}
        self._load_default_templates()
    
    def _load_default_templates(self):
        """加载默认模板"""
        self.templates = {
            "rest_api": {
                "content_type": "json",
                "default_method": "POST",
                "retry": {
                    "strategy": "exponential",
                    "max_attempts": 3,
                    "base_delay": 1.0
                },
                "rate_limit": {
                    "enabled": True,
                    "requests_per_second": 10.0
                }
            },
            "webhooks": {
                "content_type": "json",
                "default_method": "POST",
                "retry": {
                    "strategy": "fixed",
                    "max_attempts": 2,
                    "base_delay": 2.0
                },
                "timeout": 10.0
            },
            "file_upload": {
                "content_type": "multipart",
                "default_method": "POST",
                "timeout": 120.0,
                "retry": {
                    "strategy": "none"
                }
            },
            "graphql": {
                "content_type": "json",
                "default_method": "POST",
                "default_headers": {
                    "Content-Type": "application/json"
                },
                "retry": {
                    "strategy": "exponential",
                    "max_attempts": 2
                }
            }
        }
    
    async def create_wrapper_from_config(self, config_data: Dict[str, Any]) -> ApiWrapper:
        """从配置数据创建API包装器"""
        try:
            # 解析基础配置
            name = config_data.get('name', 'default')
            base_url = config_data['base_url']
            template = config_data.get('template', 'rest_api')
            
            # 应用模板
            wrapper_config = self._apply_template(config_data, template)
            
            # 创建配置对象
            api_config = self._build_api_config(wrapper_config)
            
            # 创建包装器
            wrapper = await ApiWrapperFactory.create_wrapper(api_config)
            
            # 存储配置和实例
            self.configurations[name] = api_config
            self.wrappers[name] = wrapper
            
            logger.info(f"创建API包装器: {name} -> {base_url}")
            return wrapper
            
        except Exception as e:
            logger.error(f"创建API包装器失败: {str(e)}")
            raise
    
    async def create_wrapper_from_function_call(self, function_call: FunctionCallConfig) -> ApiWrapper:
        """从函数调用配置创建API包装器"""
        try:
            # 构建配置数据
            config_data = {
                'name': f"func_{function_call.intent.intent_name}_{function_call.function_name}",
                'base_url': function_call.api_endpoint,
                'method': function_call.http_method,
                'timeout': function_call.timeout_seconds,
                'retry': {
                    'max_attempts': function_call.retry_times,
                    'strategy': 'exponential'
                },
                'headers': function_call.get_headers(),
                'parameter_mapping': function_call.get_param_mapping()
            }
            
            return await self.create_wrapper_from_config(config_data)
            
        except Exception as e:
            logger.error(f"从函数调用配置创建包装器失败: {str(e)}")
            raise
    
    def _apply_template(self, config_data: Dict[str, Any], template_name: str) -> Dict[str, Any]:
        """应用配置模板"""
        template = self.templates.get(template_name, {})
        
        # 深度合并配置
        merged_config = {}
        merged_config.update(template)
        merged_config.update(config_data)
        
        # 处理嵌套配置
        for key in ['auth', 'retry', 'rate_limit', 'cache']:
            if key in template and key in config_data:
                merged_config[key] = {**template[key], **config_data[key]}
        
        return merged_config
    
    def _build_api_config(self, config_data: Dict[str, Any]) -> ApiWrapperConfig:
        """构建API配置对象"""
        # 基础配置
        base_url = config_data['base_url']
        name = config_data.get('name', 'default')
        description = config_data.get('description')
        
        # HTTP配置
        default_method = HttpMethod(config_data.get('default_method', 'POST'))
        default_headers = config_data.get('default_headers', {})
        default_params = config_data.get('default_params', {})
        
        # 处理content_type，支持字符串映射
        content_type_str = config_data.get('content_type', 'application/json')
        content_type_mapping = {
            'json': ContentType.JSON,
            'form': ContentType.FORM_DATA,
            'multipart': ContentType.MULTIPART,
            'xml': ContentType.XML,
            'text': ContentType.TEXT,
            'binary': ContentType.BINARY,
            'application/json': ContentType.JSON,
            'application/x-www-form-urlencoded': ContentType.FORM_DATA,
            'multipart/form-data': ContentType.MULTIPART,
            'application/xml': ContentType.XML,
            'text/plain': ContentType.TEXT,
            'application/octet-stream': ContentType.BINARY
        }
        content_type = content_type_mapping.get(content_type_str, ContentType.JSON)
        
        timeout = config_data.get('timeout', 30.0)
        
        # 认证配置
        auth_data = config_data.get('auth', {})
        auth_type_str = auth_data.get('auth_type', 'none')
        auth_type_mapping = {
            'none': AuthType.NONE,
            'api_key': AuthType.API_KEY,
            'bearer_token': AuthType.BEARER_TOKEN,
            'basic_auth': AuthType.BASIC_AUTH,
            'oauth2': AuthType.OAUTH2,
            'custom_header': AuthType.CUSTOM_HEADER,
            'digest_auth': AuthType.DIGEST_AUTH,
            'jwt': AuthType.JWT
        }
        auth_type = auth_type_mapping.get(auth_type_str, AuthType.NONE)
        
        auth_config = AuthConfig(
            auth_type=auth_type,
            api_key=auth_data.get('api_key'),
            api_key_header=auth_data.get('api_key_header', 'X-API-Key'),
            token=auth_data.get('token'),
            username=auth_data.get('username'),
            password=auth_data.get('password'),
            custom_headers=auth_data.get('custom_headers', {})
        )
        
        # 重试配置
        retry_data = config_data.get('retry', {})
        retry_strategy_str = retry_data.get('strategy', 'exponential')
        retry_strategy_mapping = {
            'none': RetryStrategy.NONE,
            'fixed': RetryStrategy.FIXED,
            'exponential': RetryStrategy.EXPONENTIAL,
            'linear': RetryStrategy.LINEAR,
            'custom': RetryStrategy.CUSTOM
        }
        retry_strategy = retry_strategy_mapping.get(retry_strategy_str, RetryStrategy.EXPONENTIAL)
        
        retry_config = RetryConfig(
            strategy=retry_strategy,
            max_attempts=retry_data.get('max_attempts', 3),
            base_delay=retry_data.get('base_delay', 1.0),
            max_delay=retry_data.get('max_delay', 60.0),
            backoff_factor=retry_data.get('backoff_factor', 2.0)
        )
        
        # 限流配置
        rate_limit_data = config_data.get('rate_limit', {})
        rate_limit_config = RateLimitConfig(
            enabled=rate_limit_data.get('enabled', False),
            requests_per_second=rate_limit_data.get('requests_per_second', 10.0),
            requests_per_minute=rate_limit_data.get('requests_per_minute'),
            requests_per_hour=rate_limit_data.get('requests_per_hour')
        )
        
        # 缓存配置
        cache_data = config_data.get('cache', {})
        cache_config = CacheConfig(
            enabled=cache_data.get('enabled', False),
            ttl_seconds=cache_data.get('ttl_seconds', 300),
            max_size=cache_data.get('max_size', 1000)
        )
        
        # 参数映射
        parameter_mapping = config_data.get('parameter_mapping', {})
        response_mapping = config_data.get('response_mapping', {})
        
        return ApiWrapperConfig(
            base_url=base_url,
            name=name,
            description=description,
            default_method=default_method,
            default_headers=default_headers,
            default_params=default_params,
            content_type=content_type,
            timeout=timeout,
            auth=auth_config,
            retry=retry_config,
            rate_limit=rate_limit_config,
            cache=cache_config,
            parameter_mapping=parameter_mapping,
            response_mapping=response_mapping,
            debug=config_data.get('debug', False),
            log_requests=config_data.get('log_requests', True),
            log_responses=config_data.get('log_responses', False),
            metrics_enabled=config_data.get('metrics_enabled', True)
        )
    
    async def get_wrapper(self, name: str) -> Optional[ApiWrapper]:
        """获取API包装器"""
        return self.wrappers.get(name)
    
    async def call_api(self, wrapper_name: str, endpoint: str, 
                      method: str = "POST", params: Dict[str, Any] = None,
                      data: Any = None, **kwargs) -> ApiResponse:
        """调用API"""
        wrapper = await self.get_wrapper(wrapper_name)
        if not wrapper:
            raise ValueError(f"API包装器不存在: {wrapper_name}")
        
        request = ApiRequest(
            endpoint=endpoint,
            method=HttpMethod(method.upper()),
            params=params or {},
            data=data,
            **kwargs
        )
        
        return await wrapper.call(request)
    
    async def call_api_by_function_config(self, function_call: FunctionCallConfig,
                                        slots: Dict[str, Any],
                                        user_id: str = None,
                                        conversation_id: int = None) -> ApiResponse:
        """根据函数调用配置执行API调用"""
        try:
            # 获取或创建包装器
            wrapper_name = f"func_{function_call.intent.intent_name}_{function_call.function_name}"
            wrapper = await self.get_wrapper(wrapper_name)
            
            if not wrapper:
                wrapper = await self.create_wrapper_from_function_call(function_call)
            
            # 映射参数
            api_params = function_call.map_slots_to_params(slots)
            
            # 创建API调用日志
            api_log = await self._create_api_call_log(
                function_call, api_params, user_id, conversation_id
            )
            
            # 执行API调用
            start_time = datetime.now()
            
            try:
                response = await wrapper.call(ApiRequest(
                    endpoint="",  # 使用base_url作为完整端点
                    method=HttpMethod(function_call.http_method.upper()),
                    params=api_params if function_call.is_get_method() else {},
                    data=api_params if function_call.is_post_method() else None
                ))
                
                # 更新调用日志
                await self._update_api_call_log_success(
                    api_log, response, start_time
                )
                
                return response
                
            except Exception as e:
                # 更新调用日志
                await self._update_api_call_log_error(
                    api_log, str(e), start_time
                )
                raise
                
        except Exception as e:
            logger.error(f"API调用失败: {function_call.function_name}, {str(e)}")
            raise
    
    async def _create_api_call_log(self, function_call: FunctionCallConfig,
                                 params: Dict[str, Any], user_id: str,
                                 conversation_id: int) -> ApiCallLog:
        """创建API调用日志"""
        try:
            # 这里需要获取Conversation对象，暂时使用None
            api_log = ApiCallLog.create(
                conversation=None,  # 需要根据conversation_id查询
                function_call=function_call,
                function_name=function_call.function_name,
                api_endpoint=function_call.api_endpoint,
                request_params=json.dumps(params, ensure_ascii=False),
                request_headers=function_call.headers
            )
            return api_log
        except Exception as e:
            logger.error(f"创建API调用日志失败: {str(e)}")
            return None
    
    async def _update_api_call_log_success(self, api_log: Optional[ApiCallLog],
                                         response: ApiResponse, start_time: datetime):
        """更新API调用日志(成功)"""
        if not api_log:
            return
        
        try:
            response_time_ms = int((response.response_time - response.request_time) * 1000)
            
            api_log.mark_success(
                status_code=response.status_code,
                response_data=response.data if isinstance(response.data, dict) else {"data": response.data},
                response_time_ms=response_time_ms
            )
            api_log.save()
        except Exception as e:
            logger.error(f"更新API调用日志失败: {str(e)}")
    
    async def _update_api_call_log_error(self, api_log: Optional[ApiCallLog],
                                       error_message: str, start_time: datetime):
        """更新API调用日志(错误)"""
        if not api_log:
            return
        
        try:
            api_log.mark_failure(error_message=error_message)
            api_log.save()
        except Exception as e:
            logger.error(f"更新API调用日志失败: {str(e)}")
    
    async def get_wrapper_metrics(self, wrapper_name: str) -> Optional[Dict[str, Any]]:
        """获取包装器指标"""
        wrapper = await self.get_wrapper(wrapper_name)
        return wrapper.get_metrics() if wrapper else None
    
    async def get_all_metrics(self) -> Dict[str, Dict[str, Any]]:
        """获取所有包装器指标"""
        metrics = {}
        for name, wrapper in self.wrappers.items():
            wrapper_metrics = wrapper.get_metrics()
            if wrapper_metrics:
                metrics[name] = wrapper_metrics
        return metrics
    
    async def reload_wrapper(self, name: str, config_data: Dict[str, Any]) -> bool:
        """重新加载包装器"""
        try:
            # 关闭现有包装器
            if name in self.wrappers:
                await self.wrappers[name].close()
                del self.wrappers[name]
            
            if name in self.configurations:
                del self.configurations[name]
            
            # 创建新包装器
            await self.create_wrapper_from_config(config_data)
            
            logger.info(f"重新加载API包装器: {name}")
            return True
            
        except Exception as e:
            logger.error(f"重新加载API包装器失败: {name}, {str(e)}")
            return False
    
    async def remove_wrapper(self, name: str) -> bool:
        """移除包装器"""
        try:
            if name in self.wrappers:
                await self.wrappers[name].close()
                del self.wrappers[name]
            
            if name in self.configurations:
                del self.configurations[name]
            
            logger.info(f"移除API包装器: {name}")
            return True
            
        except Exception as e:
            logger.error(f"移除API包装器失败: {name}, {str(e)}")
            return False
    
    def list_wrappers(self) -> List[Dict[str, Any]]:
        """列出所有包装器"""
        wrappers_info = []
        
        for name, config in self.configurations.items():
            wrapper_info = {
                'name': name,
                'base_url': config.base_url,
                'description': config.description,
                'auth_type': config.auth.auth_type.value,
                'timeout': config.timeout,
                'retry_attempts': config.retry.max_attempts,
                'rate_limit_enabled': config.rate_limit.enabled,
                'cache_enabled': config.cache.enabled,
                'metrics_enabled': config.metrics_enabled,
                'active': name in self.wrappers
            }
            wrappers_info.append(wrapper_info)
        
        return wrappers_info
    
    async def test_wrapper_connection(self, name: str, test_endpoint: str = "") -> Dict[str, Any]:
        """测试包装器连接"""
        try:
            wrapper = await self.get_wrapper(name)
            if not wrapper:
                return {'success': False, 'error': '包装器不存在'}
            
            # 执行健康检查请求
            start_time = datetime.now()
            
            try:
                response = await wrapper.get(test_endpoint)
                end_time = datetime.now()
                
                return {
                    'success': True,
                    'status_code': response.status_code,
                    'response_time_ms': int((end_time - start_time).total_seconds() * 1000),
                    'url': response.url
                }
                
            except Exception as e:
                end_time = datetime.now()
                return {
                    'success': False,
                    'error': str(e),
                    'response_time_ms': int((end_time - start_time).total_seconds() * 1000)
                }
                
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    async def close_all(self):
        """关闭所有包装器"""
        for wrapper in self.wrappers.values():
            await wrapper.close()
        
        self.wrappers.clear()
        self.configurations.clear()
        
        await ApiWrapperFactory.close_all()
        
        logger.info("关闭所有API包装器")
    
    def export_configurations(self) -> List[Dict[str, Any]]:
        """导出配置"""
        configurations = []
        
        for name, config in self.configurations.items():
            config_dict = asdict(config)
            # 移除敏感信息
            if 'auth' in config_dict and config_dict['auth']:
                auth = config_dict['auth']
                for sensitive_field in ['api_key', 'token', 'password', 'jwt_secret']:
                    if sensitive_field in auth:
                        auth[sensitive_field] = '***MASKED***'
            
            configurations.append(config_dict)
        
        return configurations
    
    async def import_configurations(self, configurations: List[Dict[str, Any]]) -> Dict[str, bool]:
        """导入配置"""
        results = {}
        
        for config_data in configurations:
            try:
                name = config_data.get('name', 'unknown')
                await self.create_wrapper_from_config(config_data)
                results[name] = True
            except Exception as e:
                logger.error(f"导入配置失败: {config_data.get('name', 'unknown')}, {str(e)}")
                results[config_data.get('name', 'unknown')] = False
        
        return results


# 全局管理器实例
_api_wrapper_manager: Optional[ApiWrapperManager] = None


def get_api_wrapper_manager(cache_service: CacheService = None) -> ApiWrapperManager:
    """获取API包装器管理器实例"""
    global _api_wrapper_manager
    if _api_wrapper_manager is None:
        if cache_service is None:
            from src.services.cache_service import CacheService
            cache_service = CacheService()
        _api_wrapper_manager = ApiWrapperManager(cache_service)
    return _api_wrapper_manager