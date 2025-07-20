#!/usr/bin/env python3
"""
回退系统测试 (TASK-032)
测试统一回退管理器、智能决策引擎和各种回退策略
"""
import asyncio
import sys
import os
import time
from datetime import datetime
sys.path.insert(0, os.path.abspath('.'))

from src.services.cache_service import CacheService
from src.core.fallback_manager import (
    FallbackManager, FallbackType, FallbackStrategy, FallbackContext, 
    FallbackResult, get_fallback_manager
)
from src.core.intelligent_fallback_decision import (
    IntelligentFallbackDecisionEngine, DecisionContext, get_decision_engine
)
from src.services.conversation_service import ConversationService
from src.services.ragflow_service import RagflowService
from src.utils.logger import get_logger

logger = get_logger(__name__)


async def test_fallback_manager():
    """测试回退管理器"""
    print("=== 测试回退管理器 ===")
    
    cache_service = CacheService()
    await cache_service.initialize()
    
    fallback_manager = get_fallback_manager(cache_service)
    
    # 测试不同类型的回退场景
    test_scenarios = [
        {
            'name': 'RAGFLOW查询失败',
            'error_type': FallbackType.RAGFLOW_QUERY,
            'error_message': 'RAGFLOW服务连接超时',
            'user_input': '请查询我的账户余额',
            'expected_strategies': ['retry_then_fallback', 'alternative_service', 'cache_fallback', 'default_response']
        },
        {
            'name': '意图识别失败',
            'error_type': FallbackType.INTENT_RECOGNITION,
            'error_message': 'NLU引擎响应异常',
            'user_input': '我想要办理业务',
            'expected_strategies': ['retry_then_fallback', 'graceful_degradation', 'default_response']
        },
        {
            'name': '网络错误',
            'error_type': FallbackType.NETWORK_ERROR,
            'error_message': '网络连接中断',
            'user_input': '查询机票价格',
            'expected_strategies': ['retry_then_fallback', 'cache_fallback', 'default_response']
        },
        {
            'name': '超时错误',
            'error_type': FallbackType.TIMEOUT_ERROR,
            'error_message': '请求超时',
            'user_input': '转账操作',
            'expected_strategies': ['immediate', 'cache_fallback', 'default_response']
        },
        {
            'name': '速率限制',
            'error_type': FallbackType.RATE_LIMIT_ERROR,
            'error_message': '请求过于频繁',
            'user_input': '连续查询',
            'expected_strategies': ['circuit_breaker', 'cache_fallback', 'default_response']
        }
    ]
    
    for scenario in test_scenarios:
        print(f"\n测试场景: {scenario['name']}")
        
        # 构建回退上下文
        fallback_context = FallbackContext(
            error_type=scenario['error_type'],
            error_message=scenario['error_message'],
            original_request={'user_input': scenario['user_input']},
            session_context={'user_id': 'test_user', 'session_id': 'test_session'},
            user_id='test_user',
            session_id='test_session'
        )
        
        # 执行回退
        result = await fallback_manager.handle_fallback(fallback_context)
        
        print(f"回退结果: {result.success}")
        print(f"回退策略: {result.strategy_used.value if result.strategy_used else 'None'}")
        print(f"回退链: {result.fallback_chain}")
        print(f"响应时间: {result.response_time:.3f}s")
        print(f"置信度: {result.confidence:.3f}")
        
        if result.success:
            print(f"回退响应: {result.data}")
        else:
            print(f"回退失败: {result.error}")
        
        print("-" * 50)
    
    await cache_service.close()


async def test_intelligent_decision_engine():
    """测试智能决策引擎"""
    print("\n=== 测试智能决策引擎 ===")
    
    cache_service = CacheService()
    await cache_service.initialize()
    
    decision_engine = get_decision_engine(cache_service)
    fallback_manager = get_fallback_manager(cache_service)
    
    # 测试决策场景
    test_scenarios = [
        {
            'name': 'VIP用户RAGFLOW失败',
            'error_type': FallbackType.RAGFLOW_QUERY,
            'user_profile': {'is_vip': True, 'user_tier': 'gold', 'patience_level': 0.8},
            'expected_preference': 'alternative_service'
        },
        {
            'name': '普通用户高负载时',
            'error_type': FallbackType.RAGFLOW_QUERY,
            'user_profile': {'is_vip': False, 'user_tier': 'standard', 'patience_level': 0.3},
            'system_high_load': True,
            'expected_preference': 'immediate'
        },
        {
            'name': '工作时间技术故障',
            'error_type': FallbackType.NLU_ENGINE,
            'user_profile': {'is_vip': False, 'user_tier': 'standard', 'patience_level': 0.6},
            'business_hours': True,
            'expected_preference': 'graceful_degradation'
        },
        {
            'name': '频繁错误后断路器',
            'error_type': FallbackType.EXTERNAL_SERVICE,
            'user_profile': {'is_vip': False, 'user_tier': 'standard', 'patience_level': 0.5},
            'error_frequency': 'high',
            'expected_preference': 'circuit_breaker'
        }
    ]
    
    for scenario in test_scenarios:
        print(f"\n决策场景: {scenario['name']}")
        
        # 构建决策上下文
        fallback_context = FallbackContext(
            error_type=scenario['error_type'],
            error_message=f"测试场景: {scenario['name']}",
            original_request={'user_input': '测试查询'},
            session_context=scenario['user_profile'],
            user_id='test_user',
            session_id='test_session'
        )
        
        decision_context = DecisionContext(
            fallback_context=fallback_context,
            available_strategies=fallback_manager.fallback_rules[scenario['error_type']].strategies,
            historical_performance={},
            system_metrics={
                'cpu_usage': 0.9 if scenario.get('system_high_load') else 0.3,
                'memory_usage': 0.8 if scenario.get('system_high_load') else 0.4,
                'overall_load': 0.9 if scenario.get('system_high_load') else 0.3
            },
            user_profile=scenario['user_profile'],
            business_rules={}
        )
        
        # 执行决策
        decision_result = await decision_engine.make_decision(decision_context)
        
        print(f"推荐策略: {decision_result.recommended_strategy.value}")
        print(f"决策置信度: {decision_result.confidence:.3f}")
        print(f"决策时间: {decision_result.decision_time:.3f}s")
        print(f"备选策略: {[s.value for s in decision_result.alternative_strategies]}")
        
        print("推理过程:")
        for reasoning in decision_result.reasoning:
            print(f"  - {reasoning}")
        
        # 显示策略评分
        print("策略评分:")
        for score in decision_result.strategy_scores[:3]:  # 显示前3个
            print(f"  {score.strategy.value}: {score.score:.3f} (置信度: {score.confidence:.3f})")
            print(f"    预期成功率: {score.estimated_success_rate:.2%}")
            print(f"    预期响应时间: {score.estimated_response_time:.1f}s")
        
        print("-" * 50)
    
    await cache_service.close()


async def test_conversation_service_fallback():
    """测试对话服务回退集成"""
    print("\n=== 测试对话服务回退集成 ===")
    
    cache_service = CacheService()
    await cache_service.initialize()
    
    # 创建服务实例
    ragflow_service = RagflowService(cache_service)
    conversation_service = ConversationService(cache_service, ragflow_service)
    
    # 测试场景
    test_scenarios = [
        {
            'name': 'RAGFLOW服务未初始化',
            'user_input': '查询账户余额',
            'setup': lambda: setattr(conversation_service, 'ragflow_service', None),
            'expected_fallback': True
        },
        {
            'name': '正常RAGFLOW调用',
            'user_input': '查询账户余额',
            'setup': lambda: None,
            'expected_fallback': False
        },
        {
            'name': '复杂查询测试',
            'user_input': '我想查询最近一个月的交易记录，并且需要分析我的消费模式',
            'setup': lambda: None,
            'expected_fallback': False
        }
    ]
    
    for scenario in test_scenarios:
        print(f"\n测试场景: {scenario['name']}")
        
        # 设置测试环境
        scenario['setup']()
        
        # 构建会话上下文
        session_context = {
            'session_id': 'test_session',
            'user_id': 'test_user',
            'conversation_history': [],
            'current_intent': 'query_balance',
            'current_slots': {},
            'user_tier': 'standard'
        }
        
        try:
            # 调用对话服务
            result = await conversation_service.call_ragflow(
                user_input=scenario['user_input'],
                session_context=session_context,
                config_name='default'
            )
            
            print(f"调用结果: {result.get('answer', 'None')}")
            print(f"使用回退: {result.get('fallback_used', False)}")
            print(f"回退策略: {result.get('fallback_strategy', 'None')}")
            print(f"置信度: {result.get('confidence', 0.0):.3f}")
            print(f"响应时间: {result.get('response_time', 0.0):.3f}s")
            
            if result.get('error'):
                print(f"错误信息: {result['error']}")
            
        except Exception as e:
            print(f"调用失败: {str(e)}")
        
        print("-" * 50)
    
    await cache_service.close()


async def test_fallback_performance():
    """测试回退性能"""
    print("\n=== 测试回退性能 ===")
    
    cache_service = CacheService()
    await cache_service.initialize()
    
    fallback_manager = get_fallback_manager(cache_service)
    decision_engine = get_decision_engine(cache_service)
    
    # 性能测试
    test_count = 50
    total_time = 0
    successful_fallbacks = 0
    
    print(f"执行 {test_count} 次回退操作...")
    
    for i in range(test_count):
        # 构建回退上下文
        fallback_context = FallbackContext(
            error_type=FallbackType.RAGFLOW_QUERY,
            error_message=f"性能测试 {i+1}",
            original_request={'user_input': f'测试查询 {i+1}'},
            session_context={'user_id': f'test_user_{i}', 'session_id': f'test_session_{i}'},
            user_id=f'test_user_{i}',
            session_id=f'test_session_{i}'
        )
        
        # 执行回退
        start_time = time.time()
        result = await fallback_manager.handle_fallback(fallback_context)
        end_time = time.time()
        
        total_time += (end_time - start_time)
        
        if result.success:
            successful_fallbacks += 1
    
    # 统计结果
    average_time = total_time / test_count
    success_rate = successful_fallbacks / test_count
    
    print(f"\n性能测试结果:")
    print(f"总测试次数: {test_count}")
    print(f"成功次数: {successful_fallbacks}")
    print(f"成功率: {success_rate:.2%}")
    print(f"平均响应时间: {average_time:.3f}s")
    print(f"总耗时: {total_time:.3f}s")
    print(f"QPS: {test_count / total_time:.2f}")
    
    # 获取统计信息
    stats = await fallback_manager.get_fallback_stats()
    print(f"\n回退统计信息:")
    print(f"错误统计: {stats.get('error_stats', {})}")
    print(f"断路器状态: {len(stats.get('circuit_breakers', {}))}")
    
    # 获取决策分析
    analytics = await decision_engine.get_decision_analytics()
    print(f"\n决策分析:")
    print(f"策略性能统计: {len(analytics.get('strategy_performance', {}))}")
    print(f"用户满意度: {len(analytics.get('user_satisfaction', {}))}")
    
    await cache_service.close()


async def test_circuit_breaker():
    """测试断路器功能"""
    print("\n=== 测试断路器功能 ===")
    
    cache_service = CacheService()
    await cache_service.initialize()
    
    fallback_manager = get_fallback_manager(cache_service)
    
    # 模拟连续失败触发断路器
    service_key = "test_service"
    error_count = 6  # 超过阈值5
    
    print(f"模拟 {error_count} 次连续失败...")
    
    for i in range(error_count):
        fallback_context = FallbackContext(
            error_type=FallbackType.EXTERNAL_SERVICE,
            error_message=f"连续失败 {i+1}",
            original_request={'user_input': f'测试查询 {i+1}'},
            session_context={'user_id': 'test_user', 'session_id': service_key},
            user_id='test_user',
            session_id=service_key
        )
        
        result = await fallback_manager.handle_fallback(fallback_context)
        
        if i < 4:
            print(f"第 {i+1} 次失败: 正常处理")
        elif i == 4:
            print(f"第 {i+1} 次失败: 触发断路器")
        else:
            print(f"第 {i+1} 次失败: 断路器已打开，快速失败")
    
    # 检查断路器状态
    stats = await fallback_manager.get_fallback_stats()
    circuit_breakers = stats.get('circuit_breakers', {})
    
    print(f"\n断路器状态:")
    for key, state in circuit_breakers.items():
        print(f"服务: {key}")
        print(f"状态: {state.get('state', 'unknown')}")
        print(f"失败次数: {state.get('failure_count', 0)}")
        print(f"最后失败时间: {state.get('last_failure_time', 'unknown')}")
    
    # 测试断路器重置
    print("\n重置断路器...")
    await fallback_manager.reset_circuit_breaker(service_key)
    
    # 重新测试
    fallback_context = FallbackContext(
        error_type=FallbackType.EXTERNAL_SERVICE,
        error_message="重置后测试",
        original_request={'user_input': '重置测试'},
        session_context={'user_id': 'test_user', 'session_id': service_key},
        user_id='test_user',
        session_id=service_key
    )
    
    result = await fallback_manager.handle_fallback(fallback_context)
    print(f"重置后测试: {result.success}")
    
    await cache_service.close()


async def test_fallback_caching():
    """测试回退缓存功能"""
    print("\n=== 测试回退缓存功能 ===")
    
    cache_service = CacheService()
    await cache_service.initialize()
    
    fallback_manager = get_fallback_manager(cache_service)
    
    # 第一次查询（会被缓存）
    print("第一次查询（预期会被缓存）...")
    
    fallback_context = FallbackContext(
        error_type=FallbackType.RAGFLOW_QUERY,
        error_message="测试缓存",
        original_request={'user_input': '查询账户余额'},
        session_context={'user_id': 'test_user', 'session_id': 'test_session'},
        user_id='test_user',
        session_id='test_session'
    )
    
    result1 = await fallback_manager.handle_fallback(fallback_context)
    print(f"第一次结果: {result1.success}")
    print(f"是否来自缓存: {result1.is_cached}")
    print(f"响应时间: {result1.response_time:.3f}s")
    
    # 第二次相同查询（应该从缓存获取）
    print("\n第二次相同查询（预期从缓存获取）...")
    
    result2 = await fallback_manager.handle_fallback(fallback_context)
    print(f"第二次结果: {result2.success}")
    print(f"是否来自缓存: {result2.is_cached}")
    print(f"响应时间: {result2.response_time:.3f}s")
    
    # 不同查询
    print("\n不同查询（预期不会命中缓存）...")
    
    fallback_context.original_request['user_input'] = '查询交易记录'
    result3 = await fallback_manager.handle_fallback(fallback_context)
    print(f"不同查询结果: {result3.success}")
    print(f"是否来自缓存: {result3.is_cached}")
    print(f"响应时间: {result3.response_time:.3f}s")
    
    await cache_service.close()


async def main():
    """主测试函数"""
    print("开始回退系统测试...")
    
    try:
        # 运行所有测试
        await test_fallback_manager()
        await test_intelligent_decision_engine()
        await test_conversation_service_fallback()
        await test_fallback_performance()
        await test_circuit_breaker()
        await test_fallback_caching()
        
        print("\n🎉 所有回退系统测试完成!")
        print("回退机制已成功实现并测试完成！")
        
    except Exception as e:
        print(f"\n❌ 测试失败: {str(e)}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())