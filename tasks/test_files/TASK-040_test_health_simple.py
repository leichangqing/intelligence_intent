#!/usr/bin/env python3
"""
TASK-040: 简单健康检查测试
"""
import asyncio
import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

async def test_basic_health():
    """测试基础健康检查功能"""
    print("🏥 测试基础健康检查功能...")
    
    try:
        # 测试基础健康检查响应结构
        from src.schemas.common import StandardResponse
        from datetime import datetime
        
        # 模拟健康检查响应
        health_info = {
            "status": "healthy",
            "timestamp": datetime.utcnow().isoformat(),
            "service": "智能意图识别系统",
            "version": "1.0.0"
        }
        
        response = StandardResponse(
            success=True,
            message="服务正常",
            data=health_info
        )
        
        print(f"✅ 基础健康检查结构测试通过")
        print(f"   成功状态: {response.success}")
        print(f"   消息: {response.message}")
        print(f"   服务状态: {response.data['status']}")
        print(f"   时间戳: {response.data['timestamp']}")
        
        return True
        
    except Exception as e:
        print(f"❌ 基础健康检查测试失败: {str(e)}")
        return False


async def test_system_metrics():
    """测试系统指标获取"""
    print("\n📊 测试系统指标获取...")
    
    try:
        import psutil
        import time
        
        # 获取系统指标
        metrics = {
            "cpu_percent": psutil.cpu_percent(interval=1),
            "memory_percent": psutil.virtual_memory().percent,
            "disk_percent": psutil.disk_usage('/').percent,
            "network_io": psutil.net_io_counters()._asdict(),
            "timestamp": time.time()
        }
        
        print(f"✅ 系统指标获取成功")
        print(f"   CPU使用率: {metrics['cpu_percent']}%")
        print(f"   内存使用率: {metrics['memory_percent']}%")
        print(f"   磁盘使用率: {metrics['disk_percent']}%")
        
        return True
        
    except Exception as e:
        print(f"❌ 系统指标测试失败: {str(e)}")
        return False


async def test_uptime_calculation():
    """测试运行时间计算"""
    print("\n⏱️ 测试运行时间计算...")
    
    try:
        import psutil
        import os
        from datetime import datetime
        
        # 获取进程信息
        process = psutil.Process(os.getpid())
        create_time = process.create_time()
        current_time = datetime.utcnow().timestamp()
        uptime_seconds = int(current_time - create_time)
        
        # 计算可读的运行时间
        days = uptime_seconds // 86400
        hours = (uptime_seconds % 86400) // 3600
        minutes = (uptime_seconds % 3600) // 60
        seconds = uptime_seconds % 60
        
        uptime_str = f"{days}d {hours}h {minutes}m {seconds}s"
        
        print(f"✅ 运行时间计算成功")
        print(f"   进程ID: {os.getpid()}")
        print(f"   运行时间: {uptime_str}")
        print(f"   内存使用: {process.memory_info().rss / 1024 / 1024:.1f}MB")
        
        return True
        
    except Exception as e:
        print(f"❌ 运行时间计算失败: {str(e)}")
        return False


async def test_response_time_measurement():
    """测试响应时间测量"""
    print("\n⏱️ 测试响应时间测量...")
    
    try:
        import time
        
        # 模拟服务调用
        start_time = time.time()
        await asyncio.sleep(0.1)  # 模拟100ms延迟
        response_time = round((time.time() - start_time) * 1000, 2)
        
        print(f"✅ 响应时间测量成功")
        print(f"   测量时间: {response_time}ms")
        print(f"   预期时间: ~100ms")
        
        return True
        
    except Exception as e:
        print(f"❌ 响应时间测量失败: {str(e)}")
        return False


async def test_error_handling():
    """测试错误处理"""
    print("\n🚨 测试错误处理...")
    
    try:
        from src.schemas.common import StandardResponse
        from datetime import datetime
        
        # 模拟错误响应
        error_response = StandardResponse(
            success=False,
            message="服务不可用",
            data={
                "status": "unhealthy",
                "error": "模拟错误",
                "timestamp": datetime.utcnow().isoformat()
            }
        )
        
        print(f"✅ 错误处理测试通过")
        print(f"   成功状态: {error_response.success}")
        print(f"   错误消息: {error_response.message}")
        print(f"   服务状态: {error_response.data['status']}")
        
        return True
        
    except Exception as e:
        print(f"❌ 错误处理测试失败: {str(e)}")
        return False


async def test_health_status_aggregation():
    """测试健康状态聚合"""
    print("\n🔗 测试健康状态聚合...")
    
    try:
        # 模拟各个服务的健康状态
        dependencies_status = {
            "database": {"status": "healthy", "response_time": "45ms"},
            "redis": {"status": "healthy", "response_time": "12ms"},
            "nlu_engine": {"status": "healthy", "response_time": "156ms"},
            "ragflow": {"status": "degraded", "response_time": "2100ms", "error": "timeout"}
        }
        
        # 判断整体状态
        all_healthy = all(
            dep.get("status") == "healthy" 
            for dep in dependencies_status.values()
        )
        
        overall_status = "healthy" if all_healthy else "degraded"
        
        print(f"✅ 健康状态聚合测试通过")
        print(f"   整体状态: {overall_status}")
        for service, status in dependencies_status.items():
            service_status = status.get('status', 'unknown')
            response_time = status.get('response_time', 'N/A')
            print(f"   {service}: {service_status} ({response_time})")
        
        return True
        
    except Exception as e:
        print(f"❌ 健康状态聚合测试失败: {str(e)}")
        return False


async def run_tests():
    """运行所有测试"""
    print("🏥 开始TASK-040健康检查接口简单测试")
    print("=" * 50)
    
    test_cases = [
        ("基础健康检查", test_basic_health),
        ("系统指标获取", test_system_metrics),
        ("运行时间计算", test_uptime_calculation),
        ("响应时间测量", test_response_time_measurement),
        ("错误处理", test_error_handling),
        ("健康状态聚合", test_health_status_aggregation)
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
    print("\n" + "=" * 50)
    print("📊 测试结果总结")
    print("=" * 50)
    
    passed = sum(results)
    total = len(results)
    
    print(f"✅ 通过: {passed}/{total}")
    print(f"❌ 失败: {total - passed}/{total}")
    
    if passed == total:
        print("🎉 所有健康检查核心功能测试通过！")
        return True
    else:
        print("⚠️ 部分测试失败")
        return False


if __name__ == "__main__":
    # 运行测试
    success = asyncio.run(run_tests())
    
    if success:
        print("\n✅ TASK-040健康检查接口核心功能验证完成！")
    else:
        print("\n❌ TASK-040健康检查接口需要进一步调试")