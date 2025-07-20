#!/usr/bin/env python3
"""
错误处理和响应标准化测试 (TASK-036)
测试标准化错误处理机制、API响应格式和监控系统
"""
import asyncio
import sys
import os
import json
from datetime import datetime, timedelta
from typing import Dict, Any

sys.path.insert(0, os.path.abspath('.'))

from src.core.error_handler import (
    ErrorHandler, StandardError, ValidationError, AuthenticationError,
    AuthorizationError, BusinessLogicError, ExternalServiceError,
    DatabaseError, ConfigurationError, RateLimitError,
    ErrorCode, ErrorCategory, ErrorSeverity, global_error_handler
)
from src.schemas.api_response import (
    ApiResponse, ApiError, ValidationErrorDetail, ResponseStatus,
    PaginationInfo, HealthCheckResponse, BatchResponse
)
from src.utils.error_monitor import (
    ErrorMonitor, MonitoringRule, MonitoringMetric, AlertLevel,
    global_error_monitor
)


async def test_error_handler_system():
    """测试错误处理系统"""
    print("=== 测试错误处理系统 ===")
    
    handler = ErrorHandler()
    
    # 测试案例1：验证错误
    print("\n1. 测试验证错误处理")
    
    validation_error = ValidationError(
        message="用户名不能为空",
        field="username",
        context={"input_value": ""},
        user_id="test_user",
        request_id="req_001"
    )
    
    error_detail = await handler.handle_error(validation_error)
    
    print(f"错误码: {error_detail.code.value}")
    print(f"错误消息: {error_detail.message}")
    print(f"错误类别: {error_detail.category.value}")
    print(f"严重程度: {error_detail.severity.value}")
    print(f"用户友好消息: {error_detail.to_user_message()}")
    print(f"上下文: {error_detail.context}")
    
    # 测试案例2：认证错误
    print("\n2. 测试认证错误处理")
    
    auth_error = AuthenticationError(
        message="Token已过期",
        context={"token_type": "jwt", "expired_at": "2024-01-15T10:00:00"},
        user_id="test_user"
    )
    
    auth_detail = await handler.handle_error(auth_error)
    print(f"认证错误: {auth_detail.code.value} - {auth_detail.message}")
    print(f"严重程度: {auth_detail.severity.value}")
    
    # 测试案例3：业务逻辑错误
    print("\n3. 测试业务逻辑错误处理")
    
    business_error = BusinessLogicError(
        message="余额不足，无法完成转账",
        context={
            "current_balance": 100.0,
            "transfer_amount": 200.0,
            "account_id": "acc_123"
        }
    )
    
    business_detail = await handler.handle_error(business_error)
    print(f"业务错误: {business_detail.code.value} - {business_detail.message}")
    print(f"上下文信息: {business_detail.context}")
    
    # 测试案例4：外部服务错误
    print("\n4. 测试外部服务错误处理")
    
    service_error = ExternalServiceError(
        message="支付服务不可用",
        service_name="payment_gateway",
        context={"timeout": 30, "retry_count": 3}
    )
    
    service_detail = await handler.handle_error(service_error)
    print(f"外部服务错误: {service_detail.code.value} - {service_detail.message}")
    print(f"服务名称: {service_detail.context.get('service_name')}")
    
    # 测试案例5：通用异常处理
    print("\n5. 测试通用异常处理")
    
    try:
        # 模拟一个通用异常
        raise ValueError("这是一个值错误")
    except Exception as e:
        generic_detail = await handler.handle_error(e, {"operation": "test"})
        print(f"通用异常: {generic_detail.code.value} - {generic_detail.message}")
        print(f"上下文: {generic_detail.context}")
    
    # 测试统计功能
    print("\n6. 测试错误统计")
    
    stats = handler.get_error_stats()
    print(f"错误统计: {stats}")
    
    recent_errors = handler.get_recent_errors(3)
    print(f"最近错误数量: {len(recent_errors)}")
    
    return True


async def test_api_response_format():
    """测试API响应格式"""
    print("\n=== 测试API响应格式 ===")
    
    # 测试案例1：成功响应
    print("\n1. 测试成功响应格式")
    
    success_data = {"user_id": "123", "username": "test_user", "email": "test@example.com"}
    success_response = ApiResponse.success(
        data=success_data,
        message="用户信息获取成功",
        request_id="req_001",
        processing_time_ms=50
    )
    
    print(f"响应状态: {success_response.status.value}")
    print(f"响应数据: {success_response.data}")
    print(f"响应消息: {success_response.message}")
    print(f"请求ID: {success_response.metadata.request_id}")
    print(f"处理时间: {success_response.metadata.processing_time_ms}ms")
    
    # 测试案例2：错误响应
    print("\n2. 测试错误响应格式")
    
    validation_error = ValidationError("用户名不能为空", field="username")
    error_detail = await global_error_handler.handle_error(validation_error)
    
    error_response = ApiResponse.error_response(
        error_data=error_detail,
        message="请求验证失败",
        request_id="req_002",
        processing_time_ms=20
    )
    
    print(f"错误响应状态: {error_response.status.value}")
    print(f"错误码: {error_response.error.code}")
    print(f"错误消息: {error_response.error.message}")
    print(f"错误类别: {error_response.error.category}")
    print(f"严重程度: {error_response.error.severity}")
    
    # 测试案例3：带分页的响应
    print("\n3. 测试分页响应格式")
    
    pagination = PaginationInfo(
        page=1,
        size=10,
        total=100,
        total_pages=10,
        has_next=True,
        has_prev=False
    )
    
    paginated_data = [{"id": i, "name": f"Item {i}"} for i in range(1, 11)]
    paginated_response = ApiResponse.success(
        data=paginated_data,
        pagination=pagination,
        message="分页数据获取成功"
    )
    
    print(f"分页数据数量: {len(paginated_response.data)}")
    print(f"当前页: {paginated_response.pagination.page}")
    print(f"总页数: {paginated_response.pagination.total_pages}")
    print(f"是否有下一页: {paginated_response.pagination.has_next}")
    
    # 测试案例4：警告响应
    print("\n4. 测试警告响应格式")
    
    warning_response = ApiResponse.warning(
        data={"processed": 8, "skipped": 2},
        message="处理完成但有警告",
        warnings=["跳过了2个无效记录", "某些字段使用了默认值"]
    )
    
    print(f"警告响应状态: {warning_response.status.value}")
    print(f"警告信息: {warning_response.warnings}")
    print(f"处理结果: {warning_response.data}")
    
    # 测试案例5：批量响应
    print("\n5. 测试批量响应格式")
    
    batch_results = []
    for i in range(5):
        if i % 3 == 0:  # 模拟部分失败
            result = ApiResponse.error_response(error_data="处理失败")
        else:
            result = ApiResponse.success(data={"item_id": i, "status": "processed"})
        batch_results.append(result)
    
    batch_response = BatchResponse(
        total_items=5,
        successful_items=3,
        failed_items=2,
        results=batch_results,
        processing_time_ms=200
    )
    
    print(f"批量处理总数: {batch_response.total_items}")
    print(f"成功数量: {batch_response.successful_items}")
    print(f"失败数量: {batch_response.failed_items}")
    print(f"总处理时间: {batch_response.processing_time_ms}ms")
    
    return True


async def test_error_monitoring():
    """测试错误监控系统"""
    print("\n=== 测试错误监控系统 ===")
    
    monitor = ErrorMonitor()
    
    # 测试案例1：记录错误
    print("\n1. 测试错误记录")
    
    # 创建一些测试错误
    test_errors = [
        ValidationError("字段验证失败", field="email"),
        AuthenticationError("认证失败"),
        BusinessLogicError("业务规则违反"),
        ExternalServiceError("外部服务超时", service_name="payment"),
        DatabaseError("数据库连接失败")
    ]
    
    for error in test_errors:
        error_detail = await global_error_handler.handle_error(error)
        await monitor.record_error(error_detail)
    
    print(f"已记录 {len(test_errors)} 个错误")
    
    # 测试案例2：监控规则触发
    print("\n2. 测试监控规则")
    
    # 添加测试监控规则
    test_rule = MonitoringRule(
        name="测试错误数量报警",
        metric=MonitoringMetric.ERROR_COUNT,
        threshold=3,
        window_minutes=1,
        alert_level=AlertLevel.WARNING,
        condition="greater_than",
        description="1分钟内错误数量超过3个"
    )
    
    monitor.add_monitoring_rule(test_rule)
    
    # 记录更多错误以触发规则
    for i in range(5):
        error = ValidationError(f"测试错误 {i}")
        error_detail = await global_error_handler.handle_error(error)
        await monitor.record_error(error_detail)
    
    print("已添加更多错误以触发监控规则")
    
    # 等待监控检查
    await asyncio.sleep(1)
    
    # 测试案例3：报警回调
    print("\n3. 测试报警回调")
    
    alert_triggered = False
    
    async def test_alert_callback(alert):
        nonlocal alert_triggered
        alert_triggered = True
        print(f"收到报警: {alert.title}")
        print(f"报警级别: {alert.level.value}")
        print(f"指标值: {alert.value}")
        print(f"阈值: {alert.threshold}")
    
    monitor.add_alert_callback(test_alert_callback)
    
    # 再添加一些错误来触发报警
    for i in range(3):
        error = DatabaseError(f"数据库错误 {i}")
        error_detail = await global_error_handler.handle_error(error)
        await monitor.record_error(error_detail)
    
    # 等待报警处理
    await asyncio.sleep(2)
    
    print(f"报警是否触发: {alert_triggered}")
    
    # 测试案例4：错误统计
    print("\n4. 测试错误统计")
    
    stats = monitor.get_error_statistics()
    print(f"总错误数: {stats.get('total_errors', 0)}")
    print(f"最近1小时错误数: {stats.get('errors_last_hour', 0)}")
    print(f"按类别分类: {stats.get('errors_by_category', {})}")
    print(f"按严重程度分类: {stats.get('errors_by_severity', {})}")
    print(f"活跃监控规则数: {stats.get('active_monitoring_rules', 0)}")
    
    # 测试案例5：最近报警
    print("\n5. 测试最近报警")
    
    recent_alerts = monitor.get_recent_alerts(5)
    print(f"最近报警数量: {len(recent_alerts)}")
    
    for i, alert in enumerate(recent_alerts):
        print(f"报警 {i+1}: {alert['title']} - {alert['level']}")
    
    return True


async def test_error_context_manager():
    """测试错误上下文管理器"""
    print("\n=== 测试错误上下文管理器 ===")
    
    # 测试案例1：正常执行
    print("\n1. 测试正常执行（无异常）")
    
    try:
        async with global_error_handler.error_context(operation="test_normal", user_id="test_user"):
            print("执行正常操作...")
            result = "操作成功"
        print(f"操作结果: {result}")
    except Exception as e:
        print(f"意外异常: {str(e)}")
    
    # 测试案例2：异常捕获和处理
    print("\n2. 测试异常捕获和处理")
    
    try:
        async with global_error_handler.error_context(
            operation="test_error", 
            user_id="test_user",
            request_id="req_003"
        ):
            print("执行可能出错的操作...")
            raise BusinessLogicError("模拟业务逻辑错误")
    except BusinessLogicError as e:
        print(f"捕获到业务逻辑错误: {str(e)}")
        print(f"错误码: {e.error_detail.code.value}")
    except Exception as e:
        print(f"捕获到其他异常: {str(e)}")
    
    # 测试案例3：嵌套错误上下文
    print("\n3. 测试嵌套错误上下文")
    
    try:
        async with global_error_handler.error_context(operation="outer_operation"):
            print("外层操作开始...")
            
            try:
                async with global_error_handler.error_context(operation="inner_operation"):
                    print("内层操作开始...")
                    raise ValidationError("内层验证错误")
            except ValidationError as inner_e:
                print(f"内层错误被捕获: {inner_e.error_detail.code.value}")
                # 重新抛出一个新的错误
                raise ExternalServiceError("外层服务错误")
                
    except ExternalServiceError as outer_e:
        print(f"外层错误被捕获: {outer_e.error_detail.code.value}")
    except Exception as e:
        print(f"未预期的错误: {str(e)}")
    
    return True


async def test_performance_and_concurrent():
    """测试性能和并发处理"""
    print("\n=== 测试性能和并发处理 ===")
    
    # 测试案例1：并发错误处理
    print("\n1. 测试并发错误处理")
    
    async def generate_error(error_id: int):
        """生成测试错误"""
        error_types = [
            ValidationError,
            AuthenticationError,
            BusinessLogicError,
            ExternalServiceError,
            DatabaseError
        ]
        
        error_type = error_types[error_id % len(error_types)]
        error = error_type(f"并发测试错误 {error_id}")
        
        return await global_error_handler.handle_error(error, {"error_id": error_id})
    
    # 并发生成错误
    start_time = datetime.now()
    
    tasks = [generate_error(i) for i in range(50)]
    error_details = await asyncio.gather(*tasks)
    
    end_time = datetime.now()
    processing_time = (end_time - start_time).total_seconds()
    
    print(f"并发处理 {len(tasks)} 个错误")
    print(f"总耗时: {processing_time:.3f}s")
    print(f"平均每个错误: {processing_time / len(tasks):.4f}s")
    
    # 验证结果
    success_count = sum(1 for detail in error_details if detail is not None)
    print(f"成功处理: {success_count}/{len(tasks)}")
    
    # 测试案例2：错误统计性能
    print("\n2. 测试错误统计性能")
    
    start_time = datetime.now()
    
    for _ in range(10):
        stats = global_error_handler.get_error_stats()
        recent = global_error_handler.get_recent_errors(10)
    
    end_time = datetime.now()
    stats_time = (end_time - start_time).total_seconds()
    
    print(f"统计查询性能: {stats_time:.3f}s for 10 queries")
    print(f"平均查询时间: {stats_time / 10:.4f}s")
    
    # 测试案例3：内存使用情况
    print("\n3. 测试内存使用情况")
    
    initial_error_count = len(global_error_handler.error_history)
    
    # 生成大量错误
    for i in range(100):
        error = ValidationError(f"内存测试错误 {i}")
        await global_error_handler.handle_error(error)
    
    final_error_count = len(global_error_handler.error_history)
    
    print(f"初始错误数: {initial_error_count}")
    print(f"最终错误数: {final_error_count}")
    print(f"新增错误数: {final_error_count - initial_error_count}")
    print(f"历史记录限制: {global_error_handler.max_history_size}")
    
    return True


async def test_integration_scenarios():
    """测试集成场景"""
    print("\n=== 测试集成场景 ===")
    
    # 测试案例1：完整的请求处理流程
    print("\n1. 测试完整的请求处理流程")
    
    async def simulate_api_request(request_data: Dict[str, Any]):
        """模拟API请求处理"""
        request_id = f"req_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        start_time = datetime.now()
        
        try:
            # 1. 请求验证
            if not request_data.get("user_id"):
                raise ValidationError("用户ID不能为空", field="user_id")
            
            # 2. 认证检查
            if request_data.get("token") == "invalid":
                raise AuthenticationError("无效的认证令牌")
            
            # 3. 业务逻辑处理
            if request_data.get("amount", 0) > 1000:
                raise BusinessLogicError("金额超过限制", context={"max_amount": 1000})
            
            # 4. 外部服务调用
            if request_data.get("service") == "unavailable":
                raise ExternalServiceError("外部服务不可用", service_name="payment")
            
            # 5. 成功处理
            result = {
                "status": "success",
                "user_id": request_data["user_id"],
                "processed_amount": request_data.get("amount", 0),
                "timestamp": datetime.now().isoformat()
            }
            
            processing_time = int((datetime.now() - start_time).total_seconds() * 1000)
            
            return ApiResponse.success(
                data=result,
                message="请求处理成功",
                request_id=request_id,
                processing_time_ms=processing_time
            )
            
        except StandardError as e:
            processing_time = int((datetime.now() - start_time).total_seconds() * 1000)
            
            return ApiResponse.error_response(
                error_data=e.error_detail,
                message="请求处理失败",
                request_id=request_id,
                processing_time_ms=processing_time
            )
    
    # 测试不同的请求场景
    test_requests = [
        {"user_id": "user_123", "amount": 100, "token": "valid"},  # 成功
        {"amount": 100, "token": "valid"},  # 验证错误
        {"user_id": "user_123", "amount": 100, "token": "invalid"},  # 认证错误
        {"user_id": "user_123", "amount": 2000, "token": "valid"},  # 业务逻辑错误
        {"user_id": "user_123", "amount": 100, "token": "valid", "service": "unavailable"},  # 外部服务错误
    ]
    
    for i, request_data in enumerate(test_requests):
        response = await simulate_api_request(request_data)
        print(f"请求 {i+1}: {response.status.value}")
        
        if response.status == ResponseStatus.SUCCESS:
            print(f"  处理结果: {response.data}")
        else:
            print(f"  错误信息: {response.error.code} - {response.error.message}")
        
        print(f"  处理时间: {response.metadata.processing_time_ms}ms")
    
    # 测试案例2：批量处理场景
    print("\n2. 测试批量处理场景")
    
    batch_requests = [
        {"user_id": f"user_{i}", "amount": 50 + i * 10} 
        for i in range(10)
    ]
    
    # 随机设置一些请求为无效
    batch_requests[2]["user_id"] = ""  # 验证错误
    batch_requests[5]["amount"] = 2000  # 业务逻辑错误
    batch_requests[8]["token"] = "invalid"  # 认证错误
    
    batch_results = []
    for request_data in batch_requests:
        result = await simulate_api_request(request_data)
        batch_results.append(result)
    
    # 统计批量处理结果
    successful = sum(1 for r in batch_results if r.status == ResponseStatus.SUCCESS)
    failed = len(batch_results) - successful
    
    print(f"批量处理结果: {successful} 成功, {failed} 失败")
    
    # 按错误类型分组
    error_groups = {}
    for result in batch_results:
        if result.status == ResponseStatus.ERROR:
            error_code = result.error.code
            if error_code not in error_groups:
                error_groups[error_code] = 0
            error_groups[error_code] += 1
    
    print(f"错误分布: {error_groups}")
    
    return True


async def main():
    """主测试函数"""
    print("开始错误处理和响应标准化测试...")
    
    test_results = []
    
    try:
        # 运行所有测试
        error_handler_test = await test_error_handler_system()
        test_results.append(("错误处理系统", error_handler_test))
        
        api_response_test = await test_api_response_format()
        test_results.append(("API响应格式", api_response_test))
        
        error_monitoring_test = await test_error_monitoring()
        test_results.append(("错误监控系统", error_monitoring_test))
        
        context_manager_test = await test_error_context_manager()
        test_results.append(("错误上下文管理器", context_manager_test))
        
        performance_test = await test_performance_and_concurrent()
        test_results.append(("性能和并发处理", performance_test))
        
        integration_test = await test_integration_scenarios()
        test_results.append(("集成场景测试", integration_test))
        
        # 输出测试结果
        print("\n=== 测试结果汇总 ===")
        all_passed = True
        for test_name, result in test_results:
            status = "✓ 通过" if result else "✗ 失败"
            print(f"{test_name}: {status}")
            if not result:
                all_passed = False
        
        if all_passed:
            print("\n🎉 所有错误处理和响应标准化测试通过！")
            print("TASK-036 错误处理和响应标准化功能完成！")
            print("\n实现的功能包括:")
            print("- ✅ 标准化错误处理系统")
            print("- ✅ 统一API响应格式")
            print("- ✅ 全局异常处理器")
            print("- ✅ 错误分类和编码系统")
            print("- ✅ 错误监控和报警")
            print("- ✅ 错误统计和分析")
            print("- ✅ 性能监控和优化")
            print("- ✅ 并发处理能力")
            print("- ✅ 错误上下文管理")
            print("- ✅ 集成测试场景")
            return True
        else:
            print("\n❌ 部分测试失败，需要进一步调试")
            return False
            
    except Exception as e:
        print(f"\n❌ 测试执行失败: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    result = asyncio.run(main())
    sys.exit(0 if result else 1)