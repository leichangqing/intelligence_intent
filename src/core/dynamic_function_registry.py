"""
动态函数注册系统核心组件
实现函数的动态注册、发现、加载和管理
"""

import asyncio
import inspect
import importlib
import pkgutil
import sys
import os
from typing import Dict, List, Optional, Any, Callable, Union, Type
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime
import json
import hashlib
from pathlib import Path

from src.models.function import Function, FunctionParameter, FunctionCall
from src.utils.logger import get_logger

logger = get_logger(__name__)


class FunctionType(Enum):
    """函数类型枚举"""
    PYTHON_CALLABLE = "python_callable"       # Python可调用对象
    PYTHON_CODE = "python_code"               # Python代码字符串
    API_WRAPPER = "api_wrapper"               # API包装器
    ASYNC_FUNCTION = "async_function"         # 异步函数
    CLASS_METHOD = "class_method"             # 类方法
    LAMBDA_FUNCTION = "lambda_function"       # Lambda函数
    PLUGIN_FUNCTION = "plugin_function"       # 插件函数


class RegistrationSource(Enum):
    """注册来源枚举"""
    MANUAL = "manual"                         # 手动注册
    DATABASE = "database"                     # 数据库加载
    FILE_DISCOVERY = "file_discovery"         # 文件发现
    PLUGIN_DISCOVERY = "plugin_discovery"     # 插件发现
    AUTO_DISCOVERY = "auto_discovery"         # 自动发现
    RUNTIME_GENERATION = "runtime_generation" # 运行时生成


@dataclass
class FunctionSignature:
    """函数签名信息"""
    name: str
    parameters: List[Dict[str, Any]]
    return_type: Optional[str] = None
    is_async: bool = False
    is_generator: bool = False
    docstring: Optional[str] = None
    annotations: Dict[str, Any] = field(default_factory=dict)


@dataclass
class FunctionMetadata:
    """函数元数据"""
    name: str
    display_name: Optional[str] = None
    description: Optional[str] = None
    category: Optional[str] = None
    version: str = "1.0.0"
    function_type: FunctionType = FunctionType.PYTHON_CALLABLE
    source: RegistrationSource = RegistrationSource.MANUAL
    signature: Optional[FunctionSignature] = None
    config: Dict[str, Any] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)
    dependencies: List[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    hash_value: Optional[str] = None


@dataclass
class RegistrationRequest:
    """函数注册请求"""
    name: str
    function: Optional[Callable] = None
    code: Optional[str] = None
    config: Optional[Dict[str, Any]] = None
    metadata: Optional[FunctionMetadata] = None
    override: bool = False
    validate: bool = True
    auto_generate_signature: bool = True


class FunctionValidator:
    """函数验证器"""
    
    @staticmethod
    def validate_function_name(name: str) -> bool:
        """验证函数名称"""
        import re
        pattern = r'^[a-zA-Z_][a-zA-Z0-9_]*$'
        return bool(re.match(pattern, name)) and len(name) <= 100
    
    @staticmethod
    def validate_python_code(code: str) -> bool:
        """验证Python代码"""
        try:
            compile(code, '<string>', 'exec')
            return True
        except SyntaxError:
            return False
    
    @staticmethod
    def validate_function_signature(func: Callable) -> bool:
        """验证函数签名"""
        try:
            signature = inspect.signature(func)
            # 检查参数类型
            for param in signature.parameters.values():
                if param.kind == inspect.Parameter.VAR_POSITIONAL:
                    continue  # *args 允许
                if param.kind == inspect.Parameter.VAR_KEYWORD:
                    continue  # **kwargs 允许
            return True
        except (TypeError, ValueError):
            return False
    
    @staticmethod
    def validate_api_config(config: Dict[str, Any]) -> bool:
        """验证API配置"""
        required_fields = ['url', 'method']
        return all(field in config for field in required_fields)


class SignatureExtractor:
    """签名提取器"""
    
    @staticmethod
    def extract_signature(func: Callable) -> FunctionSignature:
        """提取函数签名"""
        try:
            signature = inspect.signature(func)
            
            # 提取参数信息
            parameters = []
            for param_name, param in signature.parameters.items():
                if param_name == 'self':
                    continue
                
                param_info = {
                    'name': param_name,
                    'type': SignatureExtractor._get_type_name(param.annotation),
                    'required': param.default == inspect.Parameter.empty,
                    'default': param.default if param.default != inspect.Parameter.empty else None,
                    'kind': param.kind.name
                }
                parameters.append(param_info)
            
            # 提取返回类型
            return_type = SignatureExtractor._get_type_name(signature.return_annotation)
            
            return FunctionSignature(
                name=func.__name__,
                parameters=parameters,
                return_type=return_type,
                is_async=asyncio.iscoroutinefunction(func),
                is_generator=inspect.isgeneratorfunction(func),
                docstring=func.__doc__,
                annotations=getattr(func, '__annotations__', {})
            )
            
        except Exception as e:
            logger.error(f"提取函数签名失败: {func.__name__}, {str(e)}")
            return FunctionSignature(name=func.__name__, parameters=[])
    
    @staticmethod
    def _get_type_name(annotation) -> str:
        """获取类型名称"""
        if annotation == inspect.Parameter.empty:
            return 'Any'
        
        if hasattr(annotation, '__name__'):
            return annotation.__name__
        elif hasattr(annotation, '_name'):
            return annotation._name
        else:
            return str(annotation)


class FunctionDiscovery:
    """函数发现器"""
    
    def __init__(self):
        self.discovered_functions: Dict[str, Callable] = {}
    
    async def discover_from_module(self, module_path: str) -> List[Callable]:
        """从模块发现函数"""
        discovered = []
        
        try:
            module = importlib.import_module(module_path)
            
            for name in dir(module):
                if name.startswith('_'):
                    continue
                
                obj = getattr(module, name)
                if callable(obj) and hasattr(obj, '__code__'):
                    discovered.append(obj)
                    logger.debug(f"发现函数: {module_path}.{name}")
            
        except Exception as e:
            logger.error(f"从模块发现函数失败: {module_path}, {str(e)}")
        
        return discovered
    
    async def discover_from_directory(self, directory: str, pattern: str = "*.py") -> List[Callable]:
        """从目录发现函数"""
        discovered = []
        
        try:
            path = Path(directory)
            if not path.exists():
                logger.warning(f"目录不存在: {directory}")
                return discovered
            
            for file_path in path.rglob(pattern):
                if file_path.is_file():
                    try:
                        # 构建模块路径
                        relative_path = file_path.relative_to(path)
                        module_path = str(relative_path.with_suffix('')).replace('/', '.')
                        
                        functions = await self.discover_from_module(module_path)
                        discovered.extend(functions)
                        
                    except Exception as e:
                        logger.warning(f"处理文件失败: {file_path}, {str(e)}")
        
        except Exception as e:
            logger.error(f"从目录发现函数失败: {directory}, {str(e)}")
        
        return discovered
    
    async def discover_decorated_functions(self, decorator_name: str = "register_function") -> List[Callable]:
        """发现装饰器标记的函数"""
        discovered = []
        
        try:
            # 遍历所有已加载的模块
            for module_name, module in sys.modules.items():
                if module is None:
                    continue
                
                try:
                    for name in dir(module):
                        obj = getattr(module, name, None)
                        if callable(obj) and hasattr(obj, decorator_name):
                            discovered.append(obj)
                            logger.debug(f"发现装饰器函数: {module_name}.{name}")
                
                except Exception:
                    continue  # 忽略无法访问的模块
        
        except Exception as e:
            logger.error(f"发现装饰器函数失败: {str(e)}")
        
        return discovered


class DynamicFunctionRegistry:
    """动态函数注册器"""
    
    def __init__(self):
        # 注册的函数存储
        self.registered_functions: Dict[str, Callable] = {}
        self.function_metadata: Dict[str, FunctionMetadata] = {}
        
        # 组件
        self.validator = FunctionValidator()
        self.signature_extractor = SignatureExtractor()
        self.discovery = FunctionDiscovery()
        
        # 缓存和索引
        self.category_index: Dict[str, List[str]] = {}
        self.tag_index: Dict[str, List[str]] = {}
        self.dependency_graph: Dict[str, List[str]] = {}
        
        # 统计信息
        self.registration_stats = {
            'total_registered': 0,
            'by_type': {},
            'by_source': {},
            'last_registration': None
        }
    
    async def register_function(self, request: RegistrationRequest) -> bool:
        """注册函数"""
        try:
            # 1. 验证请求
            if not await self._validate_registration_request(request):
                return False
            
            # 2. 检查函数是否已存在
            if request.name in self.registered_functions and not request.override:
                logger.warning(f"函数已存在，跳过注册: {request.name}")
                return False
            
            # 3. 准备函数对象
            function = await self._prepare_function(request)
            if not function:
                return False
            
            # 4. 生成元数据
            metadata = await self._generate_metadata(request, function)
            
            # 5. 验证函数
            if request.validate and not await self._validate_function(function, metadata):
                return False
            
            # 6. 执行注册
            self.registered_functions[request.name] = function
            self.function_metadata[request.name] = metadata
            
            # 7. 更新索引
            await self._update_indexes(request.name, metadata)
            
            # 8. 持久化到数据库
            await self._persist_to_database(request.name, function, metadata)
            
            # 9. 更新统计信息
            self._update_stats(metadata)
            
            logger.info(f"函数注册成功: {request.name}")
            return True
            
        except Exception as e:
            logger.error(f"函数注册失败: {request.name}, {str(e)}")
            return False
    
    async def register_from_callable(self, name: str, func: Callable, 
                                   metadata: Optional[Dict[str, Any]] = None) -> bool:
        """从可调用对象注册函数"""
        request = RegistrationRequest(
            name=name,
            function=func,
            metadata=FunctionMetadata(
                name=name,
                function_type=FunctionType.PYTHON_CALLABLE,
                **(metadata or {})
            )
        )
        return await self.register_function(request)
    
    async def register_from_code(self, name: str, code: str, 
                               entry_point: Optional[str] = None,
                               metadata: Optional[Dict[str, Any]] = None) -> bool:
        """从代码字符串注册函数"""
        config = {
            'code': code,
            'entry_point': entry_point or name
        }
        
        request = RegistrationRequest(
            name=name,
            code=code,
            config=config,
            metadata=FunctionMetadata(
                name=name,
                function_type=FunctionType.PYTHON_CODE,
                config=config,
                **(metadata or {})
            )
        )
        return await self.register_function(request)
    
    async def register_api_wrapper(self, name: str, api_config: Dict[str, Any],
                                 metadata: Optional[Dict[str, Any]] = None) -> bool:
        """注册API包装器函数"""
        request = RegistrationRequest(
            name=name,
            config=api_config,
            metadata=FunctionMetadata(
                name=name,
                function_type=FunctionType.API_WRAPPER,
                config=api_config,
                **(metadata or {})
            )
        )
        return await self.register_function(request)
    
    async def batch_register_from_discovery(self, source: str, 
                                          filter_func: Optional[Callable] = None) -> int:
        """批量注册发现的函数"""
        registered_count = 0
        
        try:
            # 根据source类型选择发现方法
            if source.startswith('module:'):
                module_path = source[7:]
                functions = await self.discovery.discover_from_module(module_path)
            elif source.startswith('directory:'):
                directory = source[10:]
                functions = await self.discovery.discover_from_directory(directory)
            elif source == 'decorated':
                functions = await self.discovery.discover_decorated_functions()
            else:
                logger.error(f"不支持的发现源: {source}")
                return 0
            
            # 过滤函数
            if filter_func:
                functions = [f for f in functions if filter_func(f)]
            
            # 批量注册
            for func in functions:
                try:
                    success = await self.register_from_callable(
                        func.__name__, func, 
                        {'source': RegistrationSource.AUTO_DISCOVERY}
                    )
                    if success:
                        registered_count += 1
                
                except Exception as e:
                    logger.warning(f"批量注册函数失败: {func.__name__}, {str(e)}")
            
            logger.info(f"批量注册完成: {registered_count}/{len(functions)} 个函数")
            
        except Exception as e:
            logger.error(f"批量注册失败: {str(e)}")
        
        return registered_count
    
    async def unregister_function(self, name: str) -> bool:
        """注销函数"""
        try:
            if name not in self.registered_functions:
                logger.warning(f"函数不存在，无法注销: {name}")
                return False
            
            # 检查依赖关系
            dependents = self._get_dependents(name)
            if dependents:
                logger.warning(f"函数存在依赖关系，无法注销: {name}, 依赖: {dependents}")
                return False
            
            # 移除注册
            del self.registered_functions[name]
            metadata = self.function_metadata.pop(name, None)
            
            # 更新索引
            if metadata:
                await self._remove_from_indexes(name, metadata)
            
            # 从数据库删除
            await self._remove_from_database(name)
            
            logger.info(f"函数注销成功: {name}")
            return True
            
        except Exception as e:
            logger.error(f"函数注销失败: {name}, {str(e)}")
            return False
    
    def get_function(self, name: str) -> Optional[Callable]:
        """获取已注册的函数"""
        return self.registered_functions.get(name)
    
    def get_metadata(self, name: str) -> Optional[FunctionMetadata]:
        """获取函数元数据"""
        return self.function_metadata.get(name)
    
    def list_functions(self, category: Optional[str] = None, 
                      tags: Optional[List[str]] = None) -> List[str]:
        """列出函数"""
        if category:
            return self.category_index.get(category, [])
        
        if tags:
            result_sets = [set(self.tag_index.get(tag, [])) for tag in tags]
            if result_sets:
                return list(set.intersection(*result_sets))
        
        return list(self.registered_functions.keys())
    
    def get_statistics(self) -> Dict[str, Any]:
        """获取注册统计信息"""
        return {
            **self.registration_stats,
            'active_functions': len(self.registered_functions),
            'categories': len(self.category_index),
            'tags': len(self.tag_index)
        }
    
    async def reload_function(self, name: str) -> bool:
        """重新加载函数"""
        try:
            metadata = self.function_metadata.get(name)
            if not metadata:
                return False
            
            if metadata.source == RegistrationSource.DATABASE:
                # 从数据库重新加载
                return await self._reload_from_database(name)
            else:
                logger.warning(f"函数不支持重新加载: {name}, 来源: {metadata.source}")
                return False
        
        except Exception as e:
            logger.error(f"重新加载函数失败: {name}, {str(e)}")
            return False
    
    # 私有方法
    
    async def _validate_registration_request(self, request: RegistrationRequest) -> bool:
        """验证注册请求"""
        if not self.validator.validate_function_name(request.name):
            logger.error(f"无效的函数名称: {request.name}")
            return False
        
        if request.code and not self.validator.validate_python_code(request.code):
            logger.error(f"无效的Python代码: {request.name}")
            return False
        
        return True
    
    async def _prepare_function(self, request: RegistrationRequest) -> Optional[Callable]:
        """准备函数对象"""
        if request.function:
            return request.function
        
        if request.code:
            return await self._compile_code_to_function(request.code, request.config)
        
        if request.config and request.metadata and request.metadata.function_type == FunctionType.API_WRAPPER:
            return self._create_api_wrapper(request.config)
        
        logger.error(f"无法准备函数对象: {request.name}")
        return None
    
    async def _compile_code_to_function(self, code: str, config: Optional[Dict[str, Any]]) -> Optional[Callable]:
        """编译代码为函数"""
        try:
            namespace = {}
            exec(code, namespace)
            
            entry_point = config.get('entry_point') if config else None
            if entry_point and entry_point in namespace:
                return namespace[entry_point]
            
            # 查找第一个可调用对象
            for name, obj in namespace.items():
                if callable(obj) and not name.startswith('_'):
                    return obj
            
            logger.error("代码中未找到可调用的函数")
            return None
            
        except Exception as e:
            logger.error(f"编译代码失败: {str(e)}")
            return None
    
    def _create_api_wrapper(self, config: Dict[str, Any]) -> Callable:
        """创建API包装器"""
        async def api_wrapper(**kwargs):
            import aiohttp
            
            url = config.get('url')
            method = config.get('method', 'POST').upper()
            headers = config.get('headers', {})
            timeout = config.get('timeout', 30)
            
            try:
                async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=timeout)) as session:
                    if method == 'GET':
                        async with session.get(url, params=kwargs, headers=headers) as response:
                            return await response.json()
                    else:
                        async with session.request(method, url, json=kwargs, headers=headers) as response:
                            return await response.json()
            
            except Exception as e:
                logger.error(f"API调用失败: {str(e)}")
                raise
        
        api_wrapper.__doc__ = config.get('description', 'API调用函数')
        return api_wrapper
    
    async def _generate_metadata(self, request: RegistrationRequest, function: Callable) -> FunctionMetadata:
        """生成函数元数据"""
        if request.metadata:
            metadata = request.metadata
        else:
            metadata = FunctionMetadata(name=request.name)
        
        # 自动生成签名
        if request.auto_generate_signature:
            metadata.signature = self.signature_extractor.extract_signature(function)
        
        # 生成哈希值
        if request.code:
            metadata.hash_value = hashlib.md5(request.code.encode()).hexdigest()
        
        metadata.updated_at = datetime.now()
        return metadata
    
    async def _validate_function(self, function: Callable, metadata: FunctionMetadata) -> bool:
        """验证函数"""
        if not self.validator.validate_function_signature(function):
            logger.error(f"函数签名验证失败: {metadata.name}")
            return False
        
        return True
    
    async def _update_indexes(self, name: str, metadata: FunctionMetadata):
        """更新索引"""
        # 分类索引
        if metadata.category:
            if metadata.category not in self.category_index:
                self.category_index[metadata.category] = []
            self.category_index[metadata.category].append(name)
        
        # 标签索引
        for tag in metadata.tags:
            if tag not in self.tag_index:
                self.tag_index[tag] = []
            self.tag_index[tag].append(name)
        
        # 依赖图
        self.dependency_graph[name] = metadata.dependencies
    
    async def _remove_from_indexes(self, name: str, metadata: FunctionMetadata):
        """从索引中移除"""
        # 分类索引
        if metadata.category and metadata.category in self.category_index:
            if name in self.category_index[metadata.category]:
                self.category_index[metadata.category].remove(name)
        
        # 标签索引
        for tag in metadata.tags:
            if tag in self.tag_index and name in self.tag_index[tag]:
                self.tag_index[tag].remove(name)
        
        # 依赖图
        if name in self.dependency_graph:
            del self.dependency_graph[name]
    
    def _get_dependents(self, name: str) -> List[str]:
        """获取依赖于指定函数的函数列表"""
        dependents = []
        for func_name, dependencies in self.dependency_graph.items():
            if name in dependencies:
                dependents.append(func_name)
        return dependents
    
    async def _persist_to_database(self, name: str, function: Callable, metadata: FunctionMetadata):
        """持久化到数据库"""
        try:
            # 创建或更新Function记录
            function_record, created = Function.get_or_create(
                function_name=name,
                defaults={
                    'display_name': metadata.display_name,
                    'description': metadata.description,
                    'category': metadata.category,
                    'version': metadata.version,
                    'is_active': True
                }
            )
            
            if not created:
                # 更新现有记录
                function_record.display_name = metadata.display_name
                function_record.description = metadata.description
                function_record.category = metadata.category
                function_record.version = metadata.version
                function_record.updated_at = datetime.now()
                function_record.save()
            
            # 设置实现配置
            implementation_config = {
                'type': metadata.function_type.value,
                'config': metadata.config,
                'hash_value': metadata.hash_value
            }
            function_record.set_implementation(implementation_config)
            function_record.save()
            
            # 保存参数定义
            if metadata.signature:
                # 删除旧的参数定义
                FunctionParameter.delete().where(FunctionParameter.function == function_record).execute()
                
                # 创建新的参数定义
                for param_info in metadata.signature.parameters:
                    FunctionParameter.create(
                        function=function_record,
                        parameter_name=param_info['name'],
                        parameter_type=param_info['type'],
                        is_required=param_info['required'],
                        default_value=json.dumps(param_info['default']) if param_info['default'] is not None else None
                    )
            
        except Exception as e:
            logger.error(f"持久化函数到数据库失败: {name}, {str(e)}")
    
    async def _remove_from_database(self, name: str):
        """从数据库删除"""
        try:
            function_record = Function.get(Function.function_name == name)
            function_record.delete_instance(recursive=True)
        except Function.DoesNotExist:
            pass
        except Exception as e:
            logger.error(f"从数据库删除函数失败: {name}, {str(e)}")
    
    async def _reload_from_database(self, name: str) -> bool:
        """从数据库重新加载函数"""
        try:
            function_record = Function.get(Function.function_name == name, Function.is_active == True)
            
            # 创建注册请求
            implementation = function_record.get_implementation()
            
            if implementation.get('type') == 'python_code':
                request = RegistrationRequest(
                    name=name,
                    code=implementation.get('config', {}).get('code', ''),
                    config=implementation.get('config', {}),
                    override=True
                )
            elif implementation.get('type') == 'api_wrapper':
                request = RegistrationRequest(
                    name=name,
                    config=implementation.get('config', {}),
                    override=True
                )
            else:
                logger.error(f"不支持的函数类型: {implementation.get('type')}")
                return False
            
            return await self.register_function(request)
            
        except Function.DoesNotExist:
            logger.error(f"数据库中未找到函数: {name}")
            return False
        except Exception as e:
            logger.error(f"从数据库重新加载函数失败: {name}, {str(e)}")
            return False
    
    def _update_stats(self, metadata: FunctionMetadata):
        """更新统计信息"""
        self.registration_stats['total_registered'] += 1
        self.registration_stats['last_registration'] = datetime.now().isoformat()
        
        # 按类型统计
        func_type = metadata.function_type.value
        if func_type not in self.registration_stats['by_type']:
            self.registration_stats['by_type'][func_type] = 0
        self.registration_stats['by_type'][func_type] += 1
        
        # 按来源统计
        source = metadata.source.value
        if source not in self.registration_stats['by_source']:
            self.registration_stats['by_source'][source] = 0
        self.registration_stats['by_source'][source] += 1


# 全局注册器实例
_global_registry: Optional[DynamicFunctionRegistry] = None


def get_function_registry() -> DynamicFunctionRegistry:
    """获取全局函数注册器实例"""
    global _global_registry
    if _global_registry is None:
        _global_registry = DynamicFunctionRegistry()
    return _global_registry


# 装饰器支持
def register_function(name: Optional[str] = None, 
                     category: Optional[str] = None,
                     description: Optional[str] = None,
                     tags: Optional[List[str]] = None):
    """函数注册装饰器"""
    def decorator(func: Callable) -> Callable:
        # 标记函数为可注册
        func.register_function = True
        func._registration_name = name or func.__name__
        func._registration_category = category
        func._registration_description = description or func.__doc__
        func._registration_tags = tags or []
        
        return func
    
    return decorator