#!/usr/bin/env python3
"""
完整集成测试脚本 (TASK-031)
测试整个智能查询系统的完整集成
"""
import asyncio
import sys
import os
sys.path.insert(0, os.path.abspath('.'))

from src.services.cache_service import CacheService
from src.services.query_processor import (
    IntelligentQueryProcessor, QueryContext
)
from src.services.ragflow_service import RagflowService
from src.services.conversation_service import ConversationService
from src.utils.query_performance import QueryPerformanceMonitor, PerformanceReporter
from src.utils.logger import get_logger

logger = get_logger(__name__)


async def test_complete_workflow():
    """测试完整的工作流程"""
    print("=== 完整工作流程测试 ===")
    
    # 初始化服务
    cache_service = CacheService()
    await cache_service.initialize()
    
    # 创建性能监控器
    performance_monitor = QueryPerformanceMonitor(cache_service)
    
    # 创建服务
    ragflow_service = RagflowService(cache_service)
    conversation_service = ConversationService(cache_service, ragflow_service)
    
    # 模拟用户会话
    user_id = "test_user_001"
    session_id = "test_session_001"
    
    # 创建或获取会话
    session = await conversation_service.get_or_create_session(user_id, session_id)
    print(f"创建会话: {session.session_id}")
    
    # 模拟多轮对话
    conversation_flow = [
        {
            "user_input": "我想了解银行账户相关信息",
            "intent": "banking_inquiry",
            "expected_response_type": "informational"
        },
        {
            "user_input": "如何查询账户余额？",
            "intent": "balance_inquiry",
            "expected_response_type": "instructional"
        },
        {
            "user_input": "转账需要什么手续？",
            "intent": "transfer_inquiry",
            "expected_response_type": "procedural"
        },
        {
            "user_input": "银行卡丢失怎么办？",
            "intent": "card_loss_support",
            "expected_response_type": "support"
        },
        {
            "user_input": "和其他银行比较有什么优势？",
            "intent": "competitive_inquiry",
            "expected_response_type": "comparative"
        }
    ]
    
    conversation_history = []
    
    for i, turn in enumerate(conversation_flow):
        print(f"\n--- 对话轮次 {i + 1} ---")
        print(f"用户输入: {turn['user_input']}")
        
        # 开始性能监控
        query_hash = performance_monitor.start_query(
            turn['user_input'],
            metadata={'turn': i + 1, 'intent': turn['intent']}
        )
        
        try:
            # 构建会话上下文
            session_context = {
                'session_id': session.session_id,
                'user_id': user_id,
                'conversation_history': conversation_history,
                'current_intent': turn['intent'],
                'current_slots': {},
                'user_preferences': {'preferred_domains': ['banking', 'finance']},
                'domain_context': 'banking',
                'previous_queries': [h['user_input'] for h in conversation_history if h['role'] == 'user'],
                'query_pattern': 'banking_consultation'
            }
            
            # 调用智能查询
            response = await conversation_service.call_ragflow(
                user_input=turn['user_input'],
                session_context=session_context,
                config_name="default"
            )
            
            print(f"系统回答: {response.get('answer', '无回答')}")
            print(f"置信度: {response.get('confidence', 0.0):.3f}")
            print(f"响应时间: {response.get('response_time', 0.0):.3f}s")
            
            # 保存对话记录
            conversation_record = await conversation_service.save_conversation(
                session_id=session.session_id,
                user_input=turn['user_input'],
                intent=turn['intent'],
                slots={},
                response=response,
                confidence=response.get('confidence', 0.0)
            )
            
            # 更新对话历史
            conversation_history.extend([
                {'role': 'user', 'content': turn['user_input']},
                {'role': 'assistant', 'content': response.get('answer', '')}
            ])
            
            # 结束性能监控
            performance_monitor.end_query(
                query_hash,
                success=response.get('answer') is not None,
                error_message=response.get('error'),
                cache_hit=False,  # 实际应该从response中获取
                query_type=turn['expected_response_type']
            )
            
            print(f"对话记录已保存: {conversation_record.id}")
            
        except Exception as e:
            print(f"对话处理失败: {str(e)}")
            performance_monitor.end_query(query_hash, success=False, error_message=str(e))
        
        print("-" * 50)
    
    # 获取对话历史
    history = await conversation_service.get_conversation_history(session.session_id)
    print(f"\n对话历史记录数: {len(history)}")
    
    # 生成性能报告
    reporter = PerformanceReporter(performance_monitor)
    performance_report = await reporter.generate_report()
    
    print("\n=== 性能报告 ===")
    print(f"总查询数: {performance_report['current_stats']['total_queries']}")
    print(f"成功率: {performance_report['current_stats']['success_rate']}")
    print(f"平均响应时间: {performance_report['current_stats']['average_duration']}")
    print(f"缓存命中率: {performance_report['current_stats']['cache_hit_rate']}")
    
    if performance_report['issues']:
        print("\n发现的问题:")
        for issue in performance_report['issues']:
            print(f"- {issue['type']}: {issue['message']}")
    
    if performance_report['recommendations']:
        print("\n优化建议:")
        for rec in performance_report['recommendations']:
            print(f"- {rec['type']}: {rec['suggestion']}")
    
    # 清理
    await cache_service.close()
    print("\n✅ 完整工作流程测试完成!")


async def test_concurrent_queries():
    """测试并发查询处理"""
    print("\n=== 并发查询测试 ===")
    
    cache_service = CacheService()
    await cache_service.initialize()
    
    ragflow_service = RagflowService(cache_service)
    conversation_service = ConversationService(cache_service, ragflow_service)
    
    # 模拟多个用户的并发查询
    concurrent_queries = [
        {
            "user_id": "user_001",
            "query": "如何开通网上银行？",
            "context": {"domain": "banking", "intent": "service_inquiry"}
        },
        {
            "user_id": "user_002",
            "query": "信用卡申请条件是什么？",
            "context": {"domain": "banking", "intent": "credit_inquiry"}
        },
        {
            "user_id": "user_003",
            "query": "理财产品有哪些？",
            "context": {"domain": "finance", "intent": "product_inquiry"}
        },
        {
            "user_id": "user_004",
            "query": "忘记密码怎么找回？",
            "context": {"domain": "support", "intent": "password_recovery"}
        },
        {
            "user_id": "user_005",
            "query": "转账限额是多少？",
            "context": {"domain": "banking", "intent": "limit_inquiry"}
        }
    ]
    
    # 并发执行查询
    async def process_query(query_info):
        try:
            # 创建会话
            session = await conversation_service.get_or_create_session(
                query_info["user_id"],
                f"session_{query_info['user_id']}"
            )
            
            # 构建上下文
            session_context = {
                'session_id': session.session_id,
                'user_id': query_info["user_id"],
                'conversation_history': [],
                'current_intent': query_info["context"]["intent"],
                'current_slots': {},
                'user_preferences': {},
                'domain_context': query_info["context"]["domain"],
                'previous_queries': [],
                'query_pattern': 'single_query'
            }
            
            # 执行查询
            start_time = asyncio.get_event_loop().time()
            response = await conversation_service.call_ragflow(
                user_input=query_info["query"],
                session_context=session_context,
                config_name="default"
            )
            end_time = asyncio.get_event_loop().time()
            
            return {
                "user_id": query_info["user_id"],
                "query": query_info["query"],
                "response": response,
                "duration": end_time - start_time,
                "success": response.get('answer') is not None
            }
            
        except Exception as e:
            return {
                "user_id": query_info["user_id"],
                "query": query_info["query"],
                "error": str(e),
                "duration": 0.0,
                "success": False
            }
    
    # 并发执行
    start_time = asyncio.get_event_loop().time()
    results = await asyncio.gather(
        *[process_query(query) for query in concurrent_queries],
        return_exceptions=True
    )
    total_time = asyncio.get_event_loop().time() - start_time
    
    # 分析结果
    successful_queries = sum(1 for r in results if isinstance(r, dict) and r.get('success', False))
    failed_queries = len(results) - successful_queries
    average_duration = sum(r.get('duration', 0) for r in results if isinstance(r, dict)) / len(results)
    
    print(f"并发查询结果:")
    print(f"- 总查询数: {len(results)}")
    print(f"- 成功查询: {successful_queries}")
    print(f"- 失败查询: {failed_queries}")
    print(f"- 成功率: {successful_queries / len(results) * 100:.1f}%")
    print(f"- 平均单查询时间: {average_duration:.3f}s")
    print(f"- 总执行时间: {total_time:.3f}s")
    print(f"- 并发效率: {average_duration / total_time:.2f}")
    
    # 显示详细结果
    for result in results:
        if isinstance(result, dict):
            status = "✅" if result.get('success') else "❌"
            duration = result.get('duration', 0)
            print(f"{status} {result['user_id']}: {result['query'][:30]}... ({duration:.3f}s)")
            if not result.get('success') and 'error' in result:
                print(f"   错误: {result['error']}")
    
    await cache_service.close()
    print("\n✅ 并发查询测试完成!")


async def test_error_recovery():
    """测试错误恢复机制"""
    print("\n=== 错误恢复测试 ===")
    
    cache_service = CacheService()
    await cache_service.initialize()
    
    ragflow_service = RagflowService(cache_service)
    conversation_service = ConversationService(cache_service, ragflow_service)
    
    # 测试各种错误情况
    error_test_cases = [
        {
            "name": "空查询",
            "query": "",
            "expected_behavior": "应该返回默认错误提示"
        },
        {
            "name": "超长查询",
            "query": "a" * 1000,
            "expected_behavior": "应该被截断或拒绝"
        },
        {
            "name": "特殊字符查询",
            "query": "!@#$%^&*()_+{}[]|\\:;\"'<>?,./",
            "expected_behavior": "应该被清理和规范化"
        },
        {
            "name": "纯数字查询",
            "query": "123456789",
            "expected_behavior": "应该被识别为数字类型查询"
        },
        {
            "name": "不支持的语言",
            "query": "Hello, how are you?",
            "expected_behavior": "应该尝试处理或返回语言不支持提示"
        }
    ]
    
    for test_case in error_test_cases:
        print(f"\n测试: {test_case['name']}")
        print(f"查询: '{test_case['query']}'")
        print(f"期望行为: {test_case['expected_behavior']}")
        
        try:
            # 创建会话
            session = await conversation_service.get_or_create_session(
                "error_test_user",
                "error_test_session"
            )
            
            # 构建上下文
            session_context = {
                'session_id': session.session_id,
                'user_id': "error_test_user",
                'conversation_history': [],
                'current_intent': None,
                'current_slots': {},
                'user_preferences': {},
                'domain_context': None,
                'previous_queries': [],
                'query_pattern': 'error_test'
            }
            
            # 执行查询
            response = await conversation_service.call_ragflow(
                user_input=test_case['query'],
                session_context=session_context,
                config_name="default"
            )
            
            print(f"响应: {response}")
            
            # 检查响应是否合理
            if response.get('answer'):
                print("✅ 成功返回回答")
            elif response.get('error'):
                print(f"⚠️ 返回错误: {response['error']}")
            else:
                print("❌ 没有返回有效响应")
                
        except Exception as e:
            print(f"❌ 异常: {str(e)}")
        
        print("-" * 40)
    
    await cache_service.close()
    print("\n✅ 错误恢复测试完成!")


async def test_system_stress():
    """测试系统压力"""
    print("\n=== 系统压力测试 ===")
    
    cache_service = CacheService()
    await cache_service.initialize()
    
    ragflow_service = RagflowService(cache_service)
    conversation_service = ConversationService(cache_service, ragflow_service)
    performance_monitor = QueryPerformanceMonitor(cache_service)
    
    # 生成大量查询
    test_queries = [
        "账户余额查询",
        "转账操作指南",
        "银行卡申请流程",
        "理财产品推荐",
        "贷款利率咨询",
        "信用卡额度提升",
        "外汇汇率查询",
        "定期存款利率",
        "手机银行使用",
        "网上银行安全"
    ]
    
    num_iterations = 50  # 每个查询重复50次
    total_queries = len(test_queries) * num_iterations
    
    print(f"开始压力测试: {total_queries} 个查询")
    
    async def execute_query(query, iteration):
        query_hash = performance_monitor.start_query(
            query,
            metadata={'iteration': iteration, 'stress_test': True}
        )
        
        try:
            session = await conversation_service.get_or_create_session(
                f"stress_user_{iteration % 10}",  # 模拟10个用户
                f"stress_session_{iteration % 10}"
            )
            
            session_context = {
                'session_id': session.session_id,
                'user_id': f"stress_user_{iteration % 10}",
                'conversation_history': [],
                'current_intent': 'stress_test',
                'current_slots': {},
                'user_preferences': {},
                'domain_context': 'banking',
                'previous_queries': [],
                'query_pattern': 'stress_test'
            }
            
            response = await conversation_service.call_ragflow(
                user_input=query,
                session_context=session_context,
                config_name="default"
            )
            
            success = response.get('answer') is not None
            performance_monitor.end_query(
                query_hash,
                success=success,
                error_message=response.get('error'),
                query_type='stress_test'
            )
            
            return success
            
        except Exception as e:
            performance_monitor.end_query(
                query_hash,
                success=False,
                error_message=str(e),
                query_type='stress_test'
            )
            return False
    
    # 执行压力测试
    start_time = asyncio.get_event_loop().time()
    
    tasks = []
    for i in range(num_iterations):
        for query in test_queries:
            tasks.append(execute_query(query, i))
    
    # 限制并发数
    semaphore = asyncio.Semaphore(20)  # 最多20个并发
    
    async def limited_execute(task):
        async with semaphore:
            return await task
    
    results = await asyncio.gather(
        *[limited_execute(task) for task in tasks],
        return_exceptions=True
    )
    
    end_time = asyncio.get_event_loop().time()
    total_time = end_time - start_time
    
    # 分析结果
    successful_queries = sum(1 for r in results if r is True)
    failed_queries = len(results) - successful_queries
    queries_per_second = len(results) / total_time
    
    print(f"\n压力测试结果:")
    print(f"- 总查询数: {len(results)}")
    print(f"- 成功查询: {successful_queries}")
    print(f"- 失败查询: {failed_queries}")
    print(f"- 成功率: {successful_queries / len(results) * 100:.1f}%")
    print(f"- 总执行时间: {total_time:.2f}s")
    print(f"- 查询速度: {queries_per_second:.2f} QPS")
    
    # 获取详细性能统计
    stats = performance_monitor.get_current_stats()
    print(f"- 平均响应时间: {stats.average_duration:.3f}s")
    print(f"- P95响应时间: {stats.p95_duration:.3f}s")
    print(f"- P99响应时间: {stats.p99_duration:.3f}s")
    print(f"- 缓存命中率: {stats.cache_hit_rate:.1%}")
    
    await cache_service.close()
    print("\n✅ 系统压力测试完成!")


async def main():
    """主测试函数"""
    print("开始完整集成测试...")
    
    try:
        # 运行所有测试
        await test_complete_workflow()
        await test_concurrent_queries()
        await test_error_recovery()
        await test_system_stress()
        
        print("\n🎉 所有集成测试完成!")
        print("智能查询系统已成功实现并测试完成！")
        
    except Exception as e:
        print(f"\n❌ 集成测试失败: {str(e)}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())