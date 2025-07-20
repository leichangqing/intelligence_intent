#!/usr/bin/env python3
"""
简化的回退系统测试 (TASK-032)
"""
import sys
import os
sys.path.insert(0, os.path.abspath('.'))

from src.core.fallback_manager import (
    FallbackManager, FallbackType, FallbackStrategy, FallbackContext, 
    FallbackResult, get_fallback_manager
)
from src.core.intelligent_fallback_decision import (
    IntelligentFallbackDecisionEngine, DecisionContext, get_decision_engine
)

def test_basic_imports():
    """测试基本导入"""
    print("=== 测试基本导入 ===")
    
    try:
        # 测试导入
        print("✓ 导入回退管理器成功")
        print("✓ 导入智能决策引擎成功")
        
        # 测试枚举
        print(f"✓ 回退类型数量: {len(FallbackType)}")
        print(f"✓ 回退策略数量: {len(FallbackStrategy)}")
        
        # 测试数据类
        context = FallbackContext(
            error_type=FallbackType.RAGFLOW_QUERY,
            error_message="测试错误",
            original_request={'user_input': '测试输入'},
            session_context={},
            user_id='test_user',
            session_id='test_session'
        )
        print("✓ 回退上下文创建成功")
        
        result = FallbackResult(
            success=True,
            data="测试结果",
            confidence=0.8
        )
        print("✓ 回退结果创建成功")
        
        return True
        
    except Exception as e:
        print(f"❌ 导入测试失败: {str(e)}")
        return False

def test_fallback_manager_creation():
    """测试回退管理器创建"""
    print("\n=== 测试回退管理器创建 ===")
    
    try:
        # 模拟缓存服务
        class MockCacheService:
            def __init__(self):
                self.data = {}
            
            async def get(self, key, namespace=None):
                return self.data.get(f"{namespace}:{key}")
            
            async def set(self, key, value, ttl=None, namespace=None):
                self.data[f"{namespace}:{key}"] = value
            
            async def delete(self, key, namespace=None):
                self.data.pop(f"{namespace}:{key}", None)
            
            async def get_keys_by_pattern(self, pattern, namespace=None):
                return []
        
        cache_service = MockCacheService()
        
        # 创建回退管理器
        fallback_manager = FallbackManager(cache_service)
        print("✓ 回退管理器创建成功")
        
        print(f"✓ 默认规则数量: {len(fallback_manager.fallback_rules)}")
        print(f"✓ 默认处理器数量: {len(fallback_manager.fallback_handlers)}")
        
        # 测试规则
        ragflow_rule = fallback_manager.fallback_rules[FallbackType.RAGFLOW_QUERY]
        print(f"✓ RAGFLOW查询规则策略: {[s.value for s in ragflow_rule.strategies]}")
        
        return True
        
    except Exception as e:
        print(f"❌ 回退管理器创建失败: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

def test_decision_engine_creation():
    """测试决策引擎创建"""
    print("\n=== 测试决策引擎创建 ===")
    
    try:
        # 模拟缓存服务
        class MockCacheService:
            def __init__(self):
                self.data = {}
            
            async def get(self, key, namespace=None):
                return self.data.get(f"{namespace}:{key}")
            
            async def set(self, key, value, ttl=None, namespace=None):
                self.data[f"{namespace}:{key}"] = value
        
        cache_service = MockCacheService()
        
        # 创建决策引擎
        decision_engine = IntelligentFallbackDecisionEngine(cache_service)
        print("✓ 决策引擎创建成功")
        
        print(f"✓ 决策权重数量: {len(decision_engine.decision_weights)}")
        print(f"✓ 策略性能数据: {len(decision_engine.strategy_performance)}")
        
        return True
        
    except Exception as e:
        print(f"❌ 决策引擎创建失败: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

def test_fallback_strategies():
    """测试回退策略"""
    print("\n=== 测试回退策略 ===")
    
    try:
        # 测试所有回退策略
        strategies = [
            FallbackStrategy.IMMEDIATE,
            FallbackStrategy.RETRY_THEN_FALLBACK,
            FallbackStrategy.CIRCUIT_BREAKER,
            FallbackStrategy.GRACEFUL_DEGRADATION,
            FallbackStrategy.CACHE_FALLBACK,
            FallbackStrategy.ALTERNATIVE_SERVICE,
            FallbackStrategy.DEFAULT_RESPONSE
        ]
        
        for strategy in strategies:
            print(f"✓ 策略: {strategy.value}")
        
        # 测试回退类型
        error_types = [
            FallbackType.RAGFLOW_QUERY,
            FallbackType.INTENT_RECOGNITION,
            FallbackType.SLOT_EXTRACTION,
            FallbackType.FUNCTION_CALL,
            FallbackType.NLU_ENGINE,
            FallbackType.EXTERNAL_SERVICE,
            FallbackType.NETWORK_ERROR,
            FallbackType.TIMEOUT_ERROR,
            FallbackType.RATE_LIMIT_ERROR
        ]
        
        for error_type in error_types:
            print(f"✓ 错误类型: {error_type.value}")
        
        return True
        
    except Exception as e:
        print(f"❌ 策略测试失败: {str(e)}")
        return False

def main():
    """主测试函数"""
    print("开始回退系统简化测试...")
    
    test_results = []
    
    try:
        # 测试基本导入
        import_test = test_basic_imports()
        test_results.append(("基本导入", import_test))
        
        # 测试回退管理器创建
        manager_test = test_fallback_manager_creation()
        test_results.append(("回退管理器创建", manager_test))
        
        # 测试决策引擎创建
        decision_test = test_decision_engine_creation()
        test_results.append(("决策引擎创建", decision_test))
        
        # 测试回退策略
        strategy_test = test_fallback_strategies()
        test_results.append(("回退策略", strategy_test))
        
        # 输出测试结果
        print("\n=== 测试结果汇总 ===")
        all_passed = True
        for test_name, result in test_results:
            status = "✓ 通过" if result else "✗ 失败"
            print(f"{test_name}: {status}")
            if not result:
                all_passed = False
        
        if all_passed:
            print("\n🎉 所有基础测试通过！回退系统核心组件正常！")
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
    result = main()
    sys.exit(0 if result else 1)