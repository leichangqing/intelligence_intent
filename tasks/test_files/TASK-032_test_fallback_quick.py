#!/usr/bin/env python3
"""
快速回退系统测试 (TASK-032)
"""
import asyncio
import sys
import os
sys.path.insert(0, os.path.abspath('.'))

from src.services.cache_service import CacheService
from src.core.fallback_manager import (
    FallbackManager, FallbackType, FallbackStrategy, FallbackContext, 
    FallbackResult, get_fallback_manager
)

async def test_basic_fallback():
    """测试基本回退功能"""
    print("=== 测试基本回退功能 ===")
    
    cache_service = CacheService()
    await cache_service.initialize()
    
    fallback_manager = get_fallback_manager(cache_service)
    
    # 测试RAGFLOW查询失败回退
    fallback_context = FallbackContext(
        error_type=FallbackType.RAGFLOW_QUERY,
        error_message="RAGFLOW服务连接超时",
        original_request={'user_input': '请查询我的账户余额'},
        session_context={'user_id': 'test_user', 'session_id': 'test_session'},
        user_id='test_user',
        session_id='test_session'
    )
    
    result = await fallback_manager.handle_fallback(fallback_context)
    
    print(f"回退结果: {result.success}")
    print(f"回退策略: {result.strategy_used.value if result.strategy_used else 'None'}")
    print(f"回退链: {result.fallback_chain}")
    print(f"响应时间: {result.response_time:.3f}s")
    print(f"置信度: {result.confidence:.3f}")
    print(f"回退响应: {result.data}")
    
    await cache_service.close()
    return result.success

async def test_decision_engine():
    """测试决策引擎"""
    print("\n=== 测试智能决策引擎 ===")
    
    from src.core.intelligent_fallback_decision import get_decision_engine, DecisionContext
    
    cache_service = CacheService()
    await cache_service.initialize()
    
    decision_engine = get_decision_engine(cache_service)
    fallback_manager = get_fallback_manager(cache_service)
    
    # 构建决策上下文
    fallback_context = FallbackContext(
        error_type=FallbackType.RAGFLOW_QUERY,
        error_message="VIP用户RAGFLOW失败",
        original_request={'user_input': '测试查询'},
        session_context={'is_vip': True, 'user_tier': 'gold'},
        user_id='vip_user',
        session_id='vip_session'
    )
    
    decision_context = DecisionContext(
        fallback_context=fallback_context,
        available_strategies=fallback_manager.fallback_rules[FallbackType.RAGFLOW_QUERY].strategies,
        historical_performance={},
        system_metrics={'cpu_usage': 0.3, 'memory_usage': 0.4},
        user_profile={'is_vip': True, 'user_tier': 'gold'},
        business_rules={}
    )
    
    decision_result = await decision_engine.make_decision(decision_context)
    
    print(f"推荐策略: {decision_result.recommended_strategy.value}")
    print(f"决策置信度: {decision_result.confidence:.3f}")
    print(f"决策时间: {decision_result.decision_time:.3f}s")
    print(f"备选策略: {[s.value for s in decision_result.alternative_strategies]}")
    
    await cache_service.close()
    return decision_result.recommended_strategy is not None

async def test_conversation_integration():
    """测试对话服务集成"""
    print("\n=== 测试对话服务集成 ===")
    
    from src.services.conversation_service import ConversationService
    from src.services.ragflow_service import RagflowService
    
    cache_service = CacheService()
    await cache_service.initialize()
    
    # 创建服务实例
    ragflow_service = RagflowService(cache_service)
    conversation_service = ConversationService(cache_service, ragflow_service)
    
    # 测试正常情况
    session_context = {
        'session_id': 'test_session',
        'user_id': 'test_user',
        'conversation_history': [],
        'current_intent': 'query_balance',
        'current_slots': {}
    }
    
    try:
        result = await conversation_service.call_ragflow(
            user_input='查询账户余额',
            session_context=session_context,
            config_name='default'
        )
        
        print(f"对话服务调用成功: {result.get('answer') is not None}")
        print(f"使用回退: {result.get('fallback_used', False)}")
        print(f"回退策略: {result.get('fallback_strategy', 'None')}")
        print(f"置信度: {result.get('confidence', 0.0):.3f}")
        
        await cache_service.close()
        return True
        
    except Exception as e:
        print(f"对话服务调用失败: {str(e)}")
        await cache_service.close()
        return False

async def main():
    """主测试函数"""
    print("开始回退系统快速测试...")
    
    test_results = []
    
    try:
        # 测试基本回退功能
        basic_test = await test_basic_fallback()
        test_results.append(("基本回退功能", basic_test))
        
        # 测试智能决策引擎
        decision_test = await test_decision_engine()
        test_results.append(("智能决策引擎", decision_test))
        
        # 测试对话服务集成
        integration_test = await test_conversation_integration()
        test_results.append(("对话服务集成", integration_test))
        
        # 输出测试结果
        print("\n=== 测试结果汇总 ===")
        all_passed = True
        for test_name, result in test_results:
            status = "✓ 通过" if result else "✗ 失败"
            print(f"{test_name}: {status}")
            if not result:
                all_passed = False
        
        if all_passed:
            print("\n🎉 所有测试通过！回退系统实现成功！")
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