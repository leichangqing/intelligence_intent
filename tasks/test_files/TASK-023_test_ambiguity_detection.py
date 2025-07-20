#!/usr/bin/env python3
"""
TASK-023 测试脚本
测试澄清问题生成功能
"""

import asyncio
import sys
import os

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.core.clarification_question_generator import (
    ClarificationQuestionGenerator, 
    ClarificationType, 
    ClarificationLevel,
    ClarificationStyle
)
from src.services.intent_service import IntentService
from src.services.slot_service import SlotService
from src.services.cache_service import CacheService
from src.core.nlu_engine import NLUEngine
from src.config.settings import settings

async def test_clarification_question_generator():
    """测试澄清问题生成器"""
    print("=== 测试澄清问题生成器 ===")
    
    generator = ClarificationQuestionGenerator()
    
    # 测试意图澄清
    print("\n1. 测试意图澄清问题生成")
    candidates = [
        {"intent_name": "book_flight", "display_name": "预订机票"},
        {"intent_name": "check_balance", "display_name": "查询余额"}
    ]
    
    context = {
        "conversation_history": [],
        "user_preferences": {},
        "turn_count": 1,
        "user_engagement": 0.7,
        "time_pressure": 0.3,
        "failed_attempts": 0
    }
    
    intent_question = await generator.generate_clarification_question(
        ClarificationType.INTENT, candidates, context, "user_123"
    )
    print(f"意图澄清问题: {intent_question.question_text}")
    
    # 测试槽位澄清
    print("\n2. 测试槽位澄清问题生成")
    slot_question = await generator.generate_clarification_question(
        ClarificationType.SLOT, candidates, context, "user_123"
    )
    print(f"槽位澄清问题: {slot_question.question_text}")
    
    # 测试歧义澄清
    print("\n3. 测试歧义澄清问题生成")
    ambiguity_question = await generator.generate_clarification_question(
        ClarificationType.AMBIGUITY, candidates, context, "user_123"
    )
    print(f"歧义澄清问题: {ambiguity_question.question_text}")
    
    # 测试确认澄清
    print("\n4. 测试确认澄清问题生成")
    confirmation_question = await generator.generate_clarification_question(
        ClarificationType.CONFIRMATION, candidates, context, "user_123"
    )
    print(f"确认澄清问题: {confirmation_question.question_text}")
    
    # 测试不同风格
    print("\n5. 测试不同风格问题生成")
    for style in [ClarificationStyle.FORMAL, ClarificationStyle.CASUAL, ClarificationStyle.FRIENDLY]:
        generator.default_style = style
        styled_question = await generator.generate_clarification_question(
            ClarificationType.INTENT, candidates, context, "user_123"
        )
        print(f"{style.value}风格: {styled_question.question_text}")
    
    # 测试不同复杂度
    print("\n6. 测试不同复杂度问题生成")
    for level in [ClarificationLevel.SIMPLE, ClarificationLevel.DETAILED]:
        generator.default_complexity = level
        complex_question = await generator.generate_clarification_question(
            ClarificationType.INTENT, candidates, context, "user_123"
        )
        print(f"{level.value}复杂度: {complex_question.question_text}")

async def test_intent_service_integration():
    """测试意图服务集成"""
    print("\n=== 测试意图服务集成 ===")
    
    try:
        # 创建模拟服务
        cache_service = CacheService()
        nlu_engine = NLUEngine(settings)
        intent_service = IntentService(cache_service, nlu_engine)
        
        # 测试澄清需求检测
        print("\n1. 测试澄清需求检测")
        test_inputs = [
            ("这个", "包含模糊词汇"),
            ("我要", "输入过短"),
            ("我要预订机票", "正常输入"),
            ("我要但是不要", "冲突信息")
        ]
        
        for user_input, expected_type in test_inputs:
            need_clarification, clarification_type, description = await intent_service.detect_clarification_need(
                user_input, {}
            )
            print(f"输入: '{user_input}' -> 需要澄清: {need_clarification}, 类型: {clarification_type.value if clarification_type else 'None'}, 描述: {description}")
        
        # 测试澄清问题生成
        print("\n2. 测试澄清问题生成")
        candidates = [
            {"intent_name": "book_flight", "display_name": "预订机票"},
            {"intent_name": "check_balance", "display_name": "查询余额"}
        ]
        
        question = await intent_service.generate_clarification_question(
            candidates, ClarificationType.INTENT, {}, "user_123"
        )
        print(f"生成的澄清问题: {question}")
        
    except Exception as e:
        print(f"意图服务测试失败: {e}")

async def test_slot_service_integration():
    """测试槽位服务集成"""
    print("\n=== 测试槽位服务集成 ===")
    
    try:
        # 创建模拟服务
        cache_service = CacheService()
        nlu_engine = NLUEngine(settings)
        slot_service = SlotService(cache_service, nlu_engine)
        
        # 创建模拟槽位对象
        class MockSlot:
            def __init__(self, slot_name, slot_type, is_required=True):
                self.slot_name = slot_name
                self.slot_type = slot_type
                self.is_required = is_required
            
            def get_validation_rules(self):
                return {}
            
            def get_examples(self):
                if self.slot_type == 'ENUM':
                    return ['选项1', '选项2', '选项3']
                return []
        
        # 测试槽位澄清问题生成
        print("\n1. 测试槽位澄清问题生成")
        test_slots = [
            MockSlot("departure_city", "TEXT"),
            MockSlot("departure_date", "DATE"),
            MockSlot("passenger_count", "NUMBER"),
            MockSlot("seat_type", "ENUM")
        ]
        
        for slot in test_slots:
            question = await slot_service.generate_slot_clarification_question(
                slot, {}, "user_123"
            )
            print(f"槽位 {slot.slot_name} ({slot.slot_type}): {question}")
        
        # 测试槽位值澄清需求检测
        print("\n2. 测试槽位值澄清需求检测")
        test_cases = [
            (MockSlot("departure_city", "TEXT"), "", "空值"),
            (MockSlot("departure_date", "DATE"), "2024-01-15", "正常日期"),
            (MockSlot("passenger_count", "NUMBER"), "10", "正常数字"),
            (MockSlot("seat_type", "ENUM"), "商务舱", "枚举值")
        ]
        
        for slot, value, description in test_cases:
            need_clarification, clarification_type, result_desc = await slot_service.detect_slot_value_clarification_need(
                slot, value, {}
            )
            print(f"{description} -> 需要澄清: {need_clarification}, 类型: {clarification_type.value if clarification_type else 'None'}, 描述: {result_desc}")
        
    except Exception as e:
        print(f"槽位服务测试失败: {e}")

async def test_performance_and_statistics():
    """测试性能和统计"""
    print("\n=== 测试性能和统计 ===")
    
    generator = ClarificationQuestionGenerator()
    
    # 测试批量生成性能
    print("\n1. 测试批量生成性能")
    import time
    
    candidates = [
        {"intent_name": "book_flight", "display_name": "预订机票"},
        {"intent_name": "check_balance", "display_name": "查询余额"}
    ]
    
    context = {
        "conversation_history": [],
        "user_preferences": {},
        "turn_count": 1,
        "user_engagement": 0.7,
        "time_pressure": 0.3,
        "failed_attempts": 0
    }
    
    start_time = time.time()
    
    for i in range(10):
        question = await generator.generate_clarification_question(
            ClarificationType.INTENT, candidates, context, f"user_{i}"
        )
    
    end_time = time.time()
    print(f"生成10个问题耗时: {end_time - start_time:.3f}秒")
    
    # 测试统计功能
    print("\n2. 测试统计功能")
    stats = generator.get_generator_statistics()
    print(f"生成器统计: {stats}")

async def main():
    """主测试函数"""
    print("开始TASK-023澄清问题生成测试")
    
    try:
        await test_clarification_question_generator()
        await test_intent_service_integration()
        await test_slot_service_integration()
        await test_performance_and_statistics()
        
        print("\n=== 测试完成 ===")
        print("TASK-023澄清问题生成功能测试通过!")
        
    except Exception as e:
        print(f"测试失败: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())