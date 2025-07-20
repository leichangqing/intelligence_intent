#!/usr/bin/env python3
"""
意图识别功能测试脚本
"""
import asyncio
import sys
import os
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from src.config.settings import settings
from src.config.database import init_database, close_database
from src.services.intent_service import IntentService
from src.services.cache_service import CacheService
from src.core.nlu_engine import NLUEngine
from src.models.intent import Intent


async def test_intent_recognition():
    """测试意图识别功能"""
    try:
        print("🚀 开始测试意图识别功能...")
        
        # 1. 初始化数据库连接
        print("📦 初始化数据库连接...")
        init_database()
        
        # 2. 初始化服务
        print("⚙️ 初始化服务...")
        cache_service = CacheService()
        await cache_service.initialize()
        
        nlu_engine = NLUEngine()
        await nlu_engine.initialize()
        
        intent_service = IntentService(cache_service, nlu_engine)
        
        # 3. 检查数据库中的意图
        print("📋 检查可用意图...")
        intents = list(Intent.select().where(Intent.is_active == True))
        print(f"找到 {len(intents)} 个活跃意图:")
        for intent in intents:
            print(f"  - {intent.intent_name}: {intent.display_name}")
        
        if not intents:
            print("❌ 没有找到活跃意图，请先运行数据库初始化脚本")
            return
        
        # 4. 测试用例
        test_cases = [
            "我要订机票",
            "帮我买张票",
            "预订航班", 
            "查询余额",
            "我的余额",
            "账户余额",
            "你好",
            "今天天气怎么样",
            "从北京到上海的机票"
        ]
        
        print("\n🧪 开始测试用例...")
        print("=" * 60)
        
        for i, test_input in enumerate(test_cases, 1):
            print(f"\n测试 {i}: '{test_input}'")
            print("-" * 40)
            
            try:
                # 执行意图识别
                result = await intent_service.recognize_intent(
                    user_input=test_input,
                    user_id="test_user",
                    context={"session_id": "test_session"}
                )
                
                # 显示结果
                print(f"🎯 识别结果:")
                print(f"   意图: {result.intent.intent_name if result.intent else 'None'}")
                print(f"   显示名: {result.intent.display_name if result.intent else 'None'}")
                print(f"   置信度: {result.confidence:.3f}")
                print(f"   识别类型: {result.recognition_type}")
                
                if result.is_ambiguous and result.alternatives:
                    print(f"   歧义候选:")
                    for alt in result.alternatives:
                        print(f"     - {alt['intent_name']}: {alt['confidence']:.3f}")
                
                # 测试歧义澄清生成
                if result.is_ambiguous:
                    question = await intent_service.generate_disambiguation_question(result.alternatives)
                    print(f"   澄清问题: {question[:100]}...")
                
            except Exception as e:
                print(f"❌ 测试失败: {str(e)}")
        
        # 5. 测试置信度计算
        print("\n🔍 测试置信度计算...")
        print("=" * 60)
        
        if intents:
            test_intent = intents[0]
            test_inputs = ["我要订机票", "随便说点什么", "查询余额"]
            
            for test_input in test_inputs:
                confidence = await intent_service.calculate_confidence(
                    test_input, test_intent, {"session_id": "test"}
                )
                print(f"'{test_input}' -> {test_intent.intent_name}: {confidence:.3f}")
        
        # 6. 测试歧义检测
        print("\n🔀 测试歧义检测...")
        print("=" * 60)
        
        test_candidates = [
            {"intent_name": "book_flight", "confidence": 0.85},
            {"intent_name": "check_balance", "confidence": 0.82},
            {"intent_name": "cancel_booking", "confidence": 0.45}
        ]
        
        is_ambiguous, ambiguous_candidates = await intent_service.detect_ambiguity(test_candidates)
        print(f"歧义检测结果: {is_ambiguous}")
        if is_ambiguous:
            print(f"歧义候选数量: {len(ambiguous_candidates)}")
            for candidate in ambiguous_candidates:
                print(f"  - {candidate['intent_name']}: {candidate['confidence']:.3f}")
        
        print("\n✅ 测试完成!")
        
    except Exception as e:
        print(f"❌ 测试过程中出现错误: {str(e)}")
        import traceback
        traceback.print_exc()
    
    finally:
        # 清理资源
        if 'nlu_engine' in locals():
            await nlu_engine.cleanup()
        if 'cache_service' in locals() and hasattr(cache_service, 'cleanup'):
            await cache_service.cleanup()
        
        try:
            close_database()
        except:
            pass


async def main():
    """主函数"""
    await test_intent_recognition()


if __name__ == "__main__":
    # 运行测试
    asyncio.run(main())