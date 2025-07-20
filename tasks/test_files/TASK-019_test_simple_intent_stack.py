#!/usr/bin/env python3
"""
简单的意图栈测试
"""

import sys
import asyncio
from datetime import datetime

sys.path.insert(0, '.')

from src.services.intent_stack_service import IntentStackService, IntentStackFrame, IntentStackStatus


class MockCacheService:
    """Mock缓存服务"""
    def __init__(self):
        self.data = {}
    
    async def get(self, key: str, namespace: str = None) -> any:
        full_key = f"{namespace}:{key}" if namespace else key
        return self.data.get(full_key)
    
    async def set(self, key: str, value: any, ttl: int = None, namespace: str = None) -> bool:
        full_key = f"{namespace}:{key}" if namespace else key
        self.data[full_key] = value
        return True
    
    async def delete(self, key: str, namespace: str = None) -> bool:
        full_key = f"{namespace}:{key}" if namespace else key
        self.data.pop(full_key, None)
        return True


class MockIntent:
    """Mock意图对象"""
    def __init__(self, intent_name: str):
        self.id = 1
        self.intent_name = intent_name
        self.display_name = f"意图-{intent_name}"
        self.is_active = True
    
    def __bool__(self):
        return True
    
    def __str__(self):
        return f"MockIntent({self.intent_name})"
    
    def __repr__(self):
        return self.__str__()


# 修改服务的_get_intent_by_name方法
async def mock_get_intent_by_name(self, intent_name: str):
    """简单的mock意图获取"""
    return MockIntent(intent_name)


async def test_simple_stack_operations():
    """测试简单的栈操作"""
    print("=== 测试简单的栈操作 ===")
    
    # 初始化服务
    cache_service = MockCacheService()
    stack_service = IntentStackService(cache_service)
    
    # 替换_get_intent_by_name方法
    stack_service._get_intent_by_name = lambda intent_name: mock_get_intent_by_name(stack_service, intent_name)
    
    session_id = "sess_123"
    user_id = "user_123"
    
    # 测试推入意图
    try:
        frame1 = await stack_service.push_intent(
            session_id, user_id, "book_flight",
            context={"step": "start"}
        )
        print(f"✓ 推入意图成功: {frame1.intent_name}")
        
        # 测试栈顶查看
        top_frame = await stack_service.peek_intent(session_id)
        print(f"✓ 栈顶查看成功: {top_frame.intent_name}")
        
        # 测试推入第二个意图
        frame2 = await stack_service.push_intent(
            session_id, user_id, "check_balance",
            context={"step": "interrupt"}
        )
        print(f"✓ 推入第二个意图成功: {frame2.intent_name}")
        
        # 测试栈状态
        current_stack = await stack_service.get_intent_stack(session_id)
        print(f"✓ 栈长度: {len(current_stack)}")
        
        # 测试弹出
        popped = await stack_service.pop_intent(session_id)
        print(f"✓ 弹出成功: {popped.intent_name}")
        
        return True
        
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


async def main():
    """主测试函数"""
    print("开始简单意图栈测试...\n")
    
    success = await test_simple_stack_operations()
    
    if success:
        print("\n✅ 简单测试通过!")
    else:
        print("\n❌ 简单测试失败!")
    
    return success


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)