#!/usr/bin/env python3
"""
TASK-040: 健康检查接口测试脚本
"""

import asyncio
import json
import time
from typing import Dict, Any
from src.api.v1.health import (
    health_check,
    detailed_health_check,
    system_metrics,
    database_health,
    redis_health,
    nlu_health,
    ragflow_health,
    dependencies_health,
    readiness_check,
    liveness_check,
    _check_database_health,
    _check_redis_health,
    _check_nlu_health,
    _check_ragflow_health
)
from src.utils.logger import get_logger

logger = get_logger(__name__)


async def test_basic_health_check():
    """测试基础健康检查"""
    print("🏥 测试基础健康检查...")
    
    try:
        response = await health_check()
        print(f"✅ 基础健康检查: {response.message}")
        print(f"   状态码: {response.code}")
        print(f"   数据: {json.dumps(response.data, indent=2, ensure_ascii=False)}")
        return True
    except Exception as e:
        print(f"❌ 基础健康检查失败: {str(e)}")
        return False


async def test_detailed_health_check():
    """测试详细健康检查"""
    print("\n🔍 测试详细健康检查...")
    
    try:
        # 模拟依赖注入
        from src.api.dependencies import check_system_health
        health_status = await check_system_health()
        
        # 调用详细健康检查
        response = await detailed_health_check(health_status)
        print(f"✅ 详细健康检查: {response.message}")
        print(f"   状态码: {response.code}")
        print(f"   整体状态: {health_status['status']}")
        print(f"   服务状态: {json.dumps(health_status['services'], indent=2, ensure_ascii=False)}")
        return True
    except Exception as e:
        print(f"❌ 详细健康检查失败: {str(e)}")
        return False


async def test_system_metrics():
    """测试系统指标"""
    print("\n📊 测试系统指标...")
    
    try:
        from src.api.dependencies import get_system_metrics
        metrics = await get_system_metrics()
        
        response = await system_metrics(metrics)
        print(f"✅ 系统指标: {response.message}")
        print(f"   CPU使用率: {metrics['cpu_percent']}%")
        print(f"   内存使用率: {metrics['memory_percent']}%")
        print(f"   磁盘使用率: {metrics['disk_percent']}%")
        return True
    except Exception as e:
        print(f"❌ 系统指标测试失败: {str(e)}")
        return False


async def test_database_health():
    """测试数据库健康检查"""
    print("\n🗄️ 测试数据库健康检查...")
    
    try:
        response = await database_health()
        print(f"✅ 数据库健康检查: {response.message}")
        print(f"   状态码: {response.code}")
        print(f"   数据库状态: {response.data['status']}")
        return True
    except Exception as e:
        print(f"❌ 数据库健康检查失败: {str(e)}")
        return False


async def test_redis_health():
    """测试Redis健康检查"""
    print("\n🔴 测试Redis健康检查...")
    
    try:
        from src.api.dependencies import get_cache_service_dependency
        cache_service = await get_cache_service_dependency()
        
        response = await redis_health(cache_service)
        print(f"✅ Redis健康检查: {response.message}")
        print(f"   状态码: {response.code}")
        print(f"   Redis状态: {response.data['status']}")
        return True
    except Exception as e:
        print(f"❌ Redis健康检查失败: {str(e)}")
        return False


async def test_nlu_health():
    """测试NLU引擎健康检查"""
    print("\n🧠 测试NLU引擎健康检查...")
    
    try:
        from src.api.dependencies import get_nlu_engine
        nlu_engine = await get_nlu_engine()
        
        response = await nlu_health(nlu_engine)
        print(f"✅ NLU引擎健康检查: {response.message}")
        print(f"   状态码: {response.code}")
        print(f"   NLU状态: {response.data['status']}")
        print(f"   测试意图: {response.data['test_intent']}")
        print(f"   测试置信度: {response.data['test_confidence']}")
        return True
    except Exception as e:
        print(f"❌ NLU引擎健康检查失败: {str(e)}")
        return False


async def test_ragflow_health():
    """测试RAGFLOW健康检查"""
    print("\n🌊 测试RAGFLOW健康检查...")
    
    try:
        from src.api.dependencies import get_cache_service_dependency
        cache_service = await get_cache_service_dependency()
        
        response = await ragflow_health(cache_service)
        print(f"✅ RAGFLOW健康检查: {response.message}")
        print(f"   状态码: {response.code}")
        print(f"   RAGFLOW状态: {response.data['status']}")
        return True
    except Exception as e:
        print(f"❌ RAGFLOW健康检查失败: {str(e)}")
        return False


async def test_dependencies_health():
    """测试依赖服务健康检查"""
    print("\n🔗 测试依赖服务健康检查...")
    
    try:
        response = await dependencies_health()
        print(f"✅ 依赖服务健康检查: {response.message}")
        print(f"   状态码: {response.code}")
        print(f"   整体状态: {response.data['overall_status']}")
        
        dependencies = response.data['dependencies']
        for service, status in dependencies.items():
            service_status = status.get('status', 'unknown')
            response_time = status.get('response_time', 'N/A')
            print(f"   {service}: {service_status} ({response_time})")
        
        return True
    except Exception as e:
        print(f"❌ 依赖服务健康检查失败: {str(e)}")
        return False


async def test_readiness_check():
    """测试就绪状态检查"""
    print("\n🚀 测试就绪状态检查...")
    
    try:
        response = await readiness_check()
        print(f"✅ 就绪状态检查: {response.message}")
        print(f"   状态码: {response.code}")
        print(f"   就绪状态: {response.data['status']}")
        return True
    except Exception as e:
        print(f"❌ 就绪状态检查失败: {str(e)}")
        return False


async def test_liveness_check():
    """测试存活状态检查"""
    print("\n💓 测试存活状态检查...")
    
    try:
        response = await liveness_check()
        print(f"✅ 存活状态检查: {response.message}")
        print(f"   状态码: {response.code}")
        print(f"   存活状态: {response.data['status']}")
        print(f"   运行时间: {response.data['uptime']}")
        print(f"   进程ID: {response.data['process_id']}")
        print(f"   内存使用: {response.data['memory_usage']}")
        return True
    except Exception as e:
        print(f"❌ 存活状态检查失败: {str(e)}")
        return False


async def test_internal_health_functions():
    """测试内部健康检查函数"""
    print("\n🔧 测试内部健康检查函数...")
    
    test_functions = [
        ("数据库", _check_database_health),
        ("Redis", _check_redis_health),
        ("NLU引擎", _check_nlu_health),
        ("RAGFLOW", _check_ragflow_health)
    ]
    
    results = []
    for service_name, test_func in test_functions:
        try:
            result = await test_func()
            status = result.get('status', 'unknown')
            response_time = result.get('response_time', 'N/A')
            print(f"   {service_name}: {status} ({response_time})")
            results.append(True)
        except Exception as e:
            print(f"   {service_name}: 失败 - {str(e)}")
            results.append(False)
    
    return all(results)


async def run_all_tests():
    """运行所有健康检查测试"""
    print("🏥 开始TASK-040健康检查接口测试")
    print("=" * 50)
    
    start_time = time.time()
    
    # 测试用例列表
    test_cases = [
        ("基础健康检查", test_basic_health_check),
        ("详细健康检查", test_detailed_health_check),
        ("系统指标", test_system_metrics),
        ("数据库健康检查", test_database_health),
        ("Redis健康检查", test_redis_health),
        ("NLU引擎健康检查", test_nlu_health),
        ("RAGFLOW健康检查", test_ragflow_health),
        ("依赖服务健康检查", test_dependencies_health),
        ("就绪状态检查", test_readiness_check),
        ("存活状态检查", test_liveness_check),
        ("内部健康检查函数", test_internal_health_functions)
    ]
    
    results = []
    for test_name, test_func in test_cases:
        try:
            result = await test_func()
            results.append(result)
        except Exception as e:
            print(f"❌ {test_name}执行失败: {str(e)}")
            results.append(False)
    
    # 总结测试结果
    end_time = time.time()
    total_time = end_time - start_time
    
    print("\n" + "=" * 50)
    print("📊 测试结果总结")
    print("=" * 50)
    
    passed = sum(results)
    total = len(results)
    
    print(f"✅ 通过: {passed}/{total}")
    print(f"❌ 失败: {total - passed}/{total}")
    print(f"⏱️ 总耗时: {total_time:.2f}秒")
    
    if passed == total:
        print("🎉 所有健康检查测试通过！")
        return True
    else:
        print("⚠️ 部分健康检查测试失败")
        return False


if __name__ == "__main__":
    # 运行测试
    success = asyncio.run(run_all_tests())
    
    if success:
        print("\n✅ TASK-040健康检查接口实现完成！")
    else:
        print("\n❌ TASK-040健康检查接口需要进一步调试")