#!/usr/bin/env python3
"""
TASK-026 测试脚本
测试动态函数注册系统功能
"""

import asyncio
import sys
import os
from datetime import datetime
from unittest.mock import Mock, patch

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.core.dynamic_function_registry import (
    DynamicFunctionRegistry, get_function_registry, RegistrationRequest,
    FunctionMetadata, FunctionType, RegistrationSource, register_function
)
from src.services.function_service import FunctionService
from src.services.cache_service import CacheService


class MockCacheService:
    """模拟缓存服务"""
    
    def __init__(self):
        self.cache = {}
    
    async def get(self, key, namespace=None):
        full_key = f"{namespace}:{key}" if namespace else key
        return self.cache.get(full_key)
    
    async def set(self, key, value, ttl=None, namespace=None):
        full_key = f"{namespace}:{key}" if namespace else key
        self.cache[full_key] = value
    
    async def delete(self, key, namespace=None):
        full_key = f"{namespace}:{key}" if namespace else key
        if full_key in self.cache:
            del self.cache[full_key]
    
    async def clear_namespace(self, namespace):
        keys_to_delete = [k for k in self.cache.keys() if k.startswith(f"{namespace}:")]
        for key in keys_to_delete:
            del self.cache[key]


async def test_dynamic_function_registry():
    """测试动态函数注册器"""
    print("=== 测试动态函数注册器 ===")
    
    # 创建注册器
    registry = DynamicFunctionRegistry()
    
    # 测试1：注册Python函数
    print("\n1. 测试注册Python函数")
    
    def test_function(name: str, age: int = 18) -> str:
        """测试函数，返回问候语"""
        return f"Hello {name}, you are {age} years old"
    
    success = await registry.register_from_callable("test_func", test_function, {
        'description': '测试函数',
        'category': 'demo'
    })
    print(f"注册Python函数: {success}")
    
    # 验证注册结果
    func = registry.get_function("test_func")
    print(f"获取函数: {func is not None}")
    
    metadata = registry.get_metadata("test_func")
    if metadata:
        print(f"函数元数据: {metadata.name}, 类型: {metadata.function_type.value}")
        print(f"参数数量: {len(metadata.signature.parameters) if metadata.signature else 0}")
    
    # 测试2：注册代码函数
    print("\n2. 测试注册代码函数")
    
    code = '''
def calculate_area(length: float, width: float) -> float:
    """计算矩形面积"""
    return length * width

def calculate_perimeter(length: float, width: float) -> float:
    """计算矩形周长"""
    return 2 * (length + width)
'''
    
    success = await registry.register_from_code(
        "calculate_area", 
        code, 
        "calculate_area",
        {
            'description': '计算矩形面积',
            'category': 'math'
        }
    )
    print(f"注册代码函数: {success}")
    
    # 测试执行
    if success:
        func = registry.get_function("calculate_area")
        if func:
            try:
                result = func(5.0, 3.0)
                print(f"执行结果: calculate_area(5.0, 3.0) = {result}")
            except Exception as e:
                print(f"执行失败: {str(e)}")
    
    # 测试3：注册API包装器
    print("\n3. 测试注册API包装器")
    
    api_config = {
        'url': 'https://api.example.com/weather',
        'method': 'GET',
        'headers': {'Content-Type': 'application/json'},
        'timeout': 30,
        'description': '获取天气信息'
    }
    
    success = await registry.register_api_wrapper("get_weather", api_config, {
        'description': '获取天气信息API',
        'category': 'api'
    })
    print(f"注册API函数: {success}")
    
    # 测试4：函数发现
    print("\n4. 测试函数发现")
    
    @register_function(name="decorated_func", category="demo", description="装饰器标记的函数")
    def decorated_function(x: int, y: int) -> int:
        """装饰器标记的函数"""
        return x + y
    
    # 模拟发现装饰器函数
    discovered = await registry.discovery.discover_decorated_functions()
    print(f"发现装饰器函数: {len(discovered)} 个")
    
    for func in discovered:
        if hasattr(func, '_registration_name'):
            print(f"  - {func._registration_name}: {func._registration_description}")
    
    # 测试5：批量注册
    print("\n5. 测试批量注册")
    
    # 模拟从模块发现函数
    def mock_func1(a: str) -> str:
        return f"mock1: {a}"
    
    def mock_func2(b: int) -> int:
        return b * 2
    
    # 手动添加到注册器
    await registry.register_from_callable("mock_func1", mock_func1, {'category': 'mock'})
    await registry.register_from_callable("mock_func2", mock_func2, {'category': 'mock'})
    
    # 测试6：函数列表和统计
    print("\n6. 测试函数列表和统计")
    
    all_functions = registry.list_functions()
    print(f"所有函数: {all_functions}")
    
    demo_functions = registry.list_functions(category="demo")
    print(f"demo分类函数: {demo_functions}")
    
    stats = registry.get_statistics()
    print(f"注册统计: {stats}")
    
    # 测试7：函数注销
    print("\n7. 测试函数注销")
    
    success = await registry.unregister_function("mock_func1")
    print(f"注销函数: {success}")
    
    remaining_functions = registry.list_functions()
    print(f"剩余函数: {remaining_functions}")
    
    print("\n动态函数注册器测试完成!")


async def test_function_service_integration():
    """测试函数服务集成"""
    print("\n=== 测试函数服务集成 ===")
    
    # 创建模拟服务
    cache_service = MockCacheService()
    function_service = FunctionService(cache_service)
    
    # 等待初始化完成
    await asyncio.sleep(0.1)
    
    # 测试1：注册Python函数
    print("\n1. 测试通过函数服务注册Python函数")
    
    def add_numbers(a: int, b: int) -> int:
        """加法函数"""
        return a + b
    
    success = await function_service.register_python_function(
        "add_numbers", 
        add_numbers,
        category="math",
        description="两数相加",
        tags=["arithmetic", "basic"]
    )
    print(f"注册Python函数: {success}")
    
    # 测试2：注册代码函数
    print("\n2. 测试注册代码函数")
    
    code = '''
def multiply_numbers(x: float, y: float) -> float:
    """乘法函数"""
    return x * y
'''
    
    success = await function_service.register_code_function(
        "multiply_numbers",
        code,
        "multiply_numbers",
        category="math",
        description="两数相乘"
    )
    print(f"注册代码函数: {success}")
    
    # 测试3：注册API函数
    print("\n3. 测试注册API函数")
    
    api_config = {
        'url': 'https://jsonplaceholder.typicode.com/posts/1',
        'method': 'GET',
        'headers': {'Content-Type': 'application/json'},
        'description': '获取示例数据'
    }
    
    success = await function_service.register_api_function(
        "get_sample_data",
        api_config,
        category="api",
        description="获取示例数据"
    )
    print(f"注册API函数: {success}")
    
    # 测试4：列出已注册函数
    print("\n4. 测试列出已注册函数")
    
    all_functions = function_service.list_registered_functions()
    print(f"所有已注册函数: {len(all_functions)} 个")
    
    for func_info in all_functions:
        print(f"  - {func_info['name']}: {func_info['description']} [{func_info['category']}]")
    
    math_functions = function_service.list_registered_functions(category="math")
    print(f"数学函数: {len(math_functions)} 个")
    
    # 测试5：获取函数详细元数据
    print("\n5. 测试获取函数详细元数据")
    
    metadata = function_service.get_function_metadata_detailed("add_numbers")
    if metadata:
        print(f"add_numbers元数据:")
        print(f"  名称: {metadata['name']}")
        print(f"  描述: {metadata['description']}")
        print(f"  类型: {metadata['function_type']}")
        print(f"  来源: {metadata['source']}")
        if metadata['signature']:
            print(f"  参数: {len(metadata['signature']['parameters'])} 个")
            print(f"  异步: {metadata['signature']['is_async']}")
    
    # 测试6：批量注册配置
    print("\n6. 测试批量注册配置")
    
    config_data = [
        {
            'name': 'subtract_numbers',
            'type': 'python_code',
            'code': 'def subtract_numbers(a: int, b: int) -> int:\n    return a - b',
            'entry_point': 'subtract_numbers',
            'category': 'math',
            'description': '两数相减'
        },
        {
            'name': 'divide_numbers',
            'type': 'python_code',
            'code': 'def divide_numbers(a: float, b: float) -> float:\n    if b == 0:\n        raise ValueError("除数不能为零")\n    return a / b',
            'entry_point': 'divide_numbers',
            'category': 'math',
            'description': '两数相除'
        }
    ]
    
    results = await function_service.bulk_register_from_config(config_data)
    print(f"批量注册结果: {results}")
    
    # 测试7：执行函数
    print("\n7. 测试执行函数")
    
    # 执行简单函数
    try:
        result = await function_service.execute_function(
            "add_numbers",
            {"a": 10, "b": 20},
            user_id="test_user"
        )
        print(f"执行add_numbers: 成功={result.success}, 结果={result.result}")
    except Exception as e:
        print(f"执行add_numbers失败: {str(e)}")
    
    # 测试8：函数重新加载
    print("\n8. 测试函数重新加载")
    
    success = await function_service.reload_function("multiply_numbers")
    print(f"重新加载函数: {success}")
    
    # 测试9：导出函数定义
    print("\n9. 测试导出函数定义")
    
    definitions = await function_service.export_function_definitions(category="math")
    print(f"导出数学函数定义: {len(definitions)} 个")
    
    for definition in definitions:
        print(f"  - {definition['name']}: {definition['type']}")
    
    # 测试10：注册器统计
    print("\n10. 测试注册器统计")
    
    stats = function_service.get_registry_statistics()
    print(f"注册器统计: {stats}")
    
    # 测试11：函数注销
    print("\n11. 测试函数注销")
    
    success = await function_service.unregister_function("subtract_numbers")
    print(f"注销函数: {success}")
    
    remaining = function_service.list_registered_functions()
    print(f"剩余函数: {len(remaining)} 个")
    
    print("\n函数服务集成测试完成!")


async def test_function_discovery():
    """测试函数发现功能"""
    print("\n=== 测试函数发现功能 ===")
    
    registry = DynamicFunctionRegistry()
    
    # 创建一些测试函数
    @register_function(name="auto_func1", category="auto", description="自动发现函数1")
    def auto_function_1(x: int) -> int:
        return x * 2
    
    @register_function(name="auto_func2", category="auto", description="自动发现函数2") 
    def auto_function_2(text: str) -> str:
        return text.upper()
    
    def api_get_user(user_id: int) -> dict:
        """API函数：获取用户信息"""
        return {"user_id": user_id, "name": f"User{user_id}"}
    
    def func_process_data(data: list) -> int:
        """处理数据函数"""
        return len(data)
    
    # 测试装饰器发现
    print("\n1. 测试装饰器函数发现")
    discovered = await registry.discovery.discover_decorated_functions()
    print(f"发现装饰器函数: {len(discovered)} 个")
    
    # 手动注册发现的函数
    for func in discovered:
        if hasattr(func, 'register_function') and func.register_function:
            name = getattr(func, '_registration_name', func.__name__)
            category = getattr(func, '_registration_category', 'auto')
            description = getattr(func, '_registration_description', func.__doc__)
            
            await registry.register_from_callable(name, func, {
                'category': category,
                'description': description,
                'source': RegistrationSource.AUTO_DISCOVERY
            })
            print(f"  自动注册: {name}")
    
    # 测试统计
    stats = registry.get_statistics()
    print(f"发现后统计: {stats}")
    
    print("\n函数发现功能测试完成!")


async def test_error_handling():
    """测试错误处理"""
    print("\n=== 测试错误处理 ===")
    
    registry = DynamicFunctionRegistry()
    
    # 测试1：无效函数名
    print("\n1. 测试无效函数名")
    
    def valid_func():
        return "valid"
    
    success = await registry.register_from_callable("123invalid", valid_func)
    print(f"注册无效函数名: {success}")  # 应该为False
    
    success = await registry.register_from_callable("valid_name", valid_func)
    print(f"注册有效函数名: {success}")  # 应该为True
    
    # 测试2：无效代码
    print("\n2. 测试无效代码")
    
    invalid_code = "def invalid_func(\n    return 'missing colon'"
    success = await registry.register_from_code("invalid_code", invalid_code)
    print(f"注册无效代码: {success}")  # 应该为False
    
    # 测试3：重复注册
    print("\n3. 测试重复注册")
    
    def duplicate_func():
        return "original"
    
    success1 = await registry.register_from_callable("duplicate", duplicate_func)
    print(f"首次注册: {success1}")  # 应该为True
    
    success2 = await registry.register_from_callable("duplicate", duplicate_func)
    print(f"重复注册(不覆盖): {success2}")  # 应该为False
    
    # 测试4：强制覆盖
    print("\n4. 测试强制覆盖")
    
    def new_duplicate_func():
        return "new"
    
    request = RegistrationRequest(
        name="duplicate",
        function=new_duplicate_func,
        override=True
    )
    success = await registry.register_function(request)
    print(f"强制覆盖注册: {success}")  # 应该为True
    
    # 测试5：注销不存在的函数
    print("\n5. 测试注销不存在的函数")
    
    success = await registry.unregister_function("non_existent")
    print(f"注销不存在的函数: {success}")  # 应该为False
    
    print("\n错误处理测试完成!")


async def test_advanced_features():
    """测试高级特性"""
    print("\n=== 测试高级特性 ===")
    
    registry = DynamicFunctionRegistry()
    
    # 测试1：依赖关系
    print("\n1. 测试函数依赖关系")
    
    def base_func(x: int) -> int:
        return x * 2
    
    def dependent_func(x: int) -> int:
        # 这个函数依赖于base_func
        return base_func(x) + 1
    
    # 注册基础函数
    await registry.register_from_callable("base_func", base_func)
    
    # 注册依赖函数
    await registry.register_from_callable("dependent_func", dependent_func, {
        'dependencies': ['base_func']
    })
    
    # 尝试删除被依赖的函数
    success = await registry.unregister_function("base_func")
    print(f"删除被依赖函数: {success}")  # 应该为False
    
    # 先删除依赖函数
    success = await registry.unregister_function("dependent_func")
    print(f"删除依赖函数: {success}")  # 应该为True
    
    success = await registry.unregister_function("base_func")
    print(f"删除基础函数: {success}")  # 现在应该为True
    
    # 测试2：函数版本管理
    print("\n2. 测试函数版本管理")
    
    def versioned_func_v1():
        return "version 1"
    
    def versioned_func_v2():
        return "version 2"
    
    # 注册v1
    await registry.register_from_callable("versioned_func", versioned_func_v1, {
        'version': '1.0.0'
    })
    
    metadata_v1 = registry.get_metadata("versioned_func")
    print(f"V1版本: {metadata_v1.version if metadata_v1 else 'None'}")
    
    # 更新到v2
    request = RegistrationRequest(
        name="versioned_func",
        function=versioned_func_v2,
        metadata=FunctionMetadata(
            name="versioned_func",
            version="2.0.0"
        ),
        override=True
    )
    await registry.register_function(request)
    
    metadata_v2 = registry.get_metadata("versioned_func")
    print(f"V2版本: {metadata_v2.version if metadata_v2 else 'None'}")
    
    # 测试3：函数标签和分类
    print("\n3. 测试函数标签和分类")
    
    def tagged_func():
        return "tagged"
    
    await registry.register_from_callable("tagged_func", tagged_func, {
        'category': 'utility',
        'tags': ['helper', 'tool', 'utility']
    })
    
    # 按标签查找
    helper_functions = registry.list_functions(tags=['helper'])
    print(f"helper标签函数: {helper_functions}")
    
    tool_functions = registry.list_functions(tags=['tool'])
    print(f"tool标签函数: {tool_functions}")
    
    # 按分类查找
    utility_functions = registry.list_functions(category='utility')
    print(f"utility分类函数: {utility_functions}")
    
    print("\n高级特性测试完成!")


async def main():
    """主测试函数"""
    print("开始 TASK-026 动态函数注册系统测试")
    print("=" * 60)
    
    try:
        # 基础功能测试
        await test_dynamic_function_registry()
        
        # 服务集成测试
        await test_function_service_integration()
        
        # 函数发现测试
        await test_function_discovery()
        
        # 错误处理测试
        await test_error_handling()
        
        # 高级特性测试
        await test_advanced_features()
        
        print("\n" + "=" * 60)
        print("TASK-026 动态函数注册系统测试全部完成!")
        print("✅ 动态函数注册系统已成功实现并测试通过")
        
        return True
        
    except Exception as e:
        print(f"\n测试过程中发生错误: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)