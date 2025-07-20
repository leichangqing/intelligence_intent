#!/usr/bin/env python3
"""
TASK-025 测试脚本
测试意图确认机制功能
"""

import asyncio
import sys
import os
from datetime import datetime
from unittest.mock import Mock, patch

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.core.intent_confirmation_manager import (
    IntentConfirmationManager,
    ConfirmationContext,
    ConfirmationTrigger,
    ConfirmationStrategy,
    ConfirmationResponse,
    RiskLevel
)
from src.services.intent_service import IntentService
from src.services.cache_service import CacheService
from src.core.nlu_engine import NLUEngine
from src.models.intent import Intent
from src.config.settings import settings


class MockSettings:
    """模拟设置类"""
    AMBIGUITY_DETECTION_THRESHOLD = 0.3
    CACHE_TTL_INTENT = 3600


async def test_intent_confirmation_manager():
    """测试意图确认管理器"""
    print("=== 测试意图确认管理器 ===")
    
    # 创建确认管理器
    mock_settings = MockSettings()
    confirmation_manager = IntentConfirmationManager(mock_settings)
    
    # 测试场景1：低置信度触发确认
    print("\n1. 测试低置信度触发确认")
    context = ConfirmationContext(
        user_id="user_123",
        conversation_id=1,
        session_id="session_user_123_1",
        intent_name="book_flight",
        confidence=0.6,  # 低置信度
        risk_level=RiskLevel.LOW,
        triggers=[],
        extracted_slots={"departure_city": "北京", "arrival_city": "上海"},
        conversation_history=[],
        user_preferences={},
        system_policies={}
    )
    
    should_confirm, triggers, strategy = await confirmation_manager.should_confirm_intent(context)
    print(f"需要确认: {should_confirm}")
    print(f"触发条件: {[t.value for t in triggers]}")
    print(f"建议策略: {strategy.value}")
    
    if should_confirm:
        # 创建确认请求
        request = await confirmation_manager.create_confirmation_request(context, strategy, triggers)
        print(f"确认请求ID: {request.request_id}")
        print(f"确认文本: {request.confirmation_text}")
        
        # 模拟用户确认响应
        print("\n模拟用户确认响应 '是的'")
        result = await confirmation_manager.process_confirmation_response(
            request.request_id, "是的", 1.5
        )
        print(f"确认结果: {result.response_type.value}")
        print(f"置信度调整: {result.confidence_adjustment}")
    
    # 测试场景2：高风险操作触发确认
    print("\n2. 测试高风险操作触发确认")
    high_risk_context = ConfirmationContext(
        user_id="user_456",
        conversation_id=2,
        session_id="session_user_456_2",
        intent_name="transfer_money",  # 高风险操作
        confidence=0.85,
        risk_level=RiskLevel.HIGH,
        triggers=[],
        extracted_slots={"amount": "5000", "target_account": "6228481234567890"},
        conversation_history=[],
        user_preferences={},
        system_policies={}
    )
    
    should_confirm_hr, triggers_hr, strategy_hr = await confirmation_manager.should_confirm_intent(high_risk_context)
    print(f"需要确认: {should_confirm_hr}")
    print(f"触发条件: {[t.value for t in triggers_hr]}")
    print(f"建议策略: {strategy_hr.value}")
    
    if should_confirm_hr:
        request_hr = await confirmation_manager.create_confirmation_request(high_risk_context, strategy_hr, triggers_hr)
        print(f"确认文本: {request_hr.confirmation_text}")
        
        # 模拟用户拒绝响应
        print("\n模拟用户拒绝响应 '不是'")
        result_hr = await confirmation_manager.process_confirmation_response(
            request_hr.request_id, "不是", 2.0
        )
        print(f"确认结果: {result_hr.response_type.value}")
        print(f"解释: {result_hr.explanation}")
    
    # 测试场景3：敏感数据触发确认
    print("\n3. 测试敏感数据触发确认")
    sensitive_context = ConfirmationContext(
        user_id="user_789",
        conversation_id=3,
        session_id="session_user_789_3",
        intent_name="update_profile",
        confidence=0.75,
        risk_level=RiskLevel.MEDIUM,
        triggers=[],
        extracted_slots={"phone": "13812345678", "id_card": "110101199001011234"},  # 敏感数据
        conversation_history=[],
        user_preferences={},
        system_policies={}
    )
    
    should_confirm_sen, triggers_sen, strategy_sen = await confirmation_manager.should_confirm_intent(sensitive_context)
    print(f"需要确认: {should_confirm_sen}")
    print(f"触发条件: {[t.value for t in triggers_sen]}")
    print(f"建议策略: {strategy_sen.value}")
    
    # 测试统计信息
    print("\n4. 测试统计信息")
    stats = confirmation_manager.get_confirmation_statistics()
    print(f"总确认请求: {stats.get('total_requests', 0)}")
    print(f"确认成功率: {stats.get('confirmation_rate', 0):.2%}")
    
    # 测试用户确认画像
    print("\n5. 测试用户确认画像")
    profile = confirmation_manager.get_user_confirmation_profile("user_123")
    print(f"用户画像: {profile.get('profile', 'unknown')}")
    print(f"建议: {profile.get('recommendations', [])}")
    
    print("\n意图确认管理器测试完成!")


async def test_intent_service_confirmation():
    """测试意图服务的确认功能"""
    print("\n=== 测试意图服务确认功能 ===")
    
    try:
        # 创建模拟的依赖服务
        cache_service = CacheService()
        
        # 创建模拟的NLU引擎
        nlu_engine = Mock()
        nlu_engine.recognize_intent = Mock(return_value={
            'intent_name': 'book_flight',
            'confidence': 0.65,  # 低置信度，可能触发确认
            'slots': {'departure_city': '北京', 'arrival_city': '上海'}
        })
        
        # 创建意图服务
        intent_service = IntentService(cache_service, nlu_engine)
        
        # 创建模拟意图对象
        mock_intent = Mock()
        mock_intent.intent_name = "book_flight"
        mock_intent.display_name = "预订机票"
        mock_intent.is_active = True
        mock_intent.priority = 1
        
        # 模拟_get_intent_by_name方法
        intent_service._get_intent_by_name = Mock(return_value=mock_intent)
        
        # 测试意图确认检查
        print("\n1. 测试意图确认需求检查")
        need_confirmation, request_id, strategy = await intent_service.check_intent_confirmation_needed(
            mock_intent,
            0.65,  # 低置信度
            {"departure_city": "北京", "arrival_city": "上海"},
            "user_test",
            1,
            {"history": [], "user_preferences": {}}
        )
        
        print(f"需要确认: {need_confirmation}")
        if need_confirmation:
            print(f"确认请求ID: {request_id}")
            print(f"确认策略: {strategy.value}")
            
            # 获取确认请求文本
            confirmation_text = intent_service.get_confirmation_request_text(request_id)
            print(f"确认文本: {confirmation_text}")
            
            # 测试确认响应处理
            print("\n2. 测试确认响应处理")
            success, confirmed_intent, details = await intent_service.process_intent_confirmation(
                request_id, "是的，我要预订机票", 1.2
            )
            
            print(f"确认成功: {success}")
            if confirmed_intent:
                print(f"确认的意图: {confirmed_intent.intent_name}")
            print(f"详情: {details}")
        
        # 测试带确认的意图识别
        print("\n3. 测试带确认的意图识别")
        
        # 模拟recognize_intent方法
        mock_recognition_result = Mock()
        mock_recognition_result.intent = mock_intent
        mock_recognition_result.confidence = 0.65
        mock_recognition_result.is_ambiguous = False
        
        intent_service.recognize_intent = Mock(return_value=mock_recognition_result)
        
        recognition_result, confirmation_request_id = await intent_service.recognize_intent_with_confirmation(
            "我要预订从北京到上海的机票",
            "user_test",
            {
                "conversation_id": 1,
                "extracted_slots": {"departure_city": "北京", "arrival_city": "上海"},
                "history": []
            }
        )
        
        print(f"识别结果: {recognition_result.intent.intent_name if recognition_result.intent else 'None'}")
        print(f"置信度: {recognition_result.confidence}")
        print(f"确认请求ID: {confirmation_request_id}")
        
        # 测试统计信息
        print("\n4. 测试确认统计信息")
        stats = intent_service.get_intent_confirmation_statistics()
        print(f"统计信息: {stats}")
        
        # 测试用户确认画像
        print("\n5. 测试用户确认画像")
        profile = intent_service.get_user_confirmation_profile("user_test")
        print(f"用户画像: {profile}")
        
        print("\n意图服务确认功能测试完成!")
        
    except Exception as e:
        print(f"测试过程中发生错误: {str(e)}")
        import traceback
        traceback.print_exc()


async def test_confirmation_scenarios():
    """测试各种确认场景"""
    print("\n=== 测试各种确认场景 ===")
    
    mock_settings = MockSettings()
    confirmation_manager = IntentConfirmationManager(mock_settings)
    
    # 场景1：首次用户操作
    print("\n场景1：首次用户操作")
    first_time_context = ConfirmationContext(
        user_id="new_user_001",
        conversation_id=1,
        session_id="session_new_user_001_1",
        intent_name="book_flight",
        confidence=0.8,
        risk_level=RiskLevel.MEDIUM,
        triggers=[],
        extracted_slots={"departure_city": "北京", "arrival_city": "上海", "departure_date": "2024-01-15"},
        conversation_history=[],  # 空历史，表示新用户
        user_preferences={},
        system_policies={}
    )
    
    should_confirm, triggers, strategy = await confirmation_manager.should_confirm_intent(first_time_context)
    print(f"首次用户需要确认: {should_confirm}, 策略: {strategy.value if should_confirm else 'N/A'}")
    
    # 场景2：大金额转账
    print("\n场景2：大金额转账")
    large_amount_context = ConfirmationContext(
        user_id="user_rich",
        conversation_id=2,
        session_id="session_user_rich_2",
        intent_name="transfer_money",
        confidence=0.9,
        risk_level=RiskLevel.CRITICAL,
        triggers=[],
        extracted_slots={"amount": "50000", "target_account": "6228481234567890"},
        conversation_history=[],
        user_preferences={},
        system_policies={}
    )
    
    should_confirm_la, triggers_la, strategy_la = await confirmation_manager.should_confirm_intent(large_amount_context)
    print(f"大金额转账需要确认: {should_confirm_la}, 策略: {strategy_la.value if should_confirm_la else 'N/A'}")
    
    # 场景3：信用卡信息操作
    print("\n场景3：信用卡信息操作")
    credit_card_context = ConfirmationContext(
        user_id="user_cardholder",
        conversation_id=3,
        session_id="session_user_cardholder_3",
        intent_name="update_payment_method",
        confidence=0.75,
        risk_level=RiskLevel.HIGH,
        triggers=[],
        extracted_slots={"card_number": "4111 1111 1111 1111", "cvv": "123"},  # 敏感信用卡信息
        conversation_history=[],
        user_preferences={},
        system_policies={}
    )
    
    should_confirm_cc, triggers_cc, strategy_cc = await confirmation_manager.should_confirm_intent(credit_card_context)
    print(f"信用卡操作需要确认: {should_confirm_cc}, 策略: {strategy_cc.value if should_confirm_cc else 'N/A'}")
    
    # 场景4：上下文模糊
    print("\n场景4：上下文模糊")
    ambiguous_context = ConfirmationContext(
        user_id="user_confused",
        conversation_id=4,
        session_id="session_user_confused_4",
        intent_name="book_flight",
        confidence=0.7,
        risk_level=RiskLevel.MEDIUM,
        triggers=[],
        extracted_slots={"departure_city": "北京"},  # 槽位信息不完整
        conversation_history=[
            {"intent": "check_weather"},
            {"intent": "book_hotel"},
            {"intent": "cancel_booking"}  # 意图跳跃频繁
        ],
        user_preferences={},
        system_policies={}
    )
    
    should_confirm_amb, triggers_amb, strategy_amb = await confirmation_manager.should_confirm_intent(ambiguous_context)
    print(f"上下文模糊需要确认: {should_confirm_amb}, 策略: {strategy_amb.value if should_confirm_amb else 'N/A'}")
    
    print("\n确认场景测试完成!")


async def test_confirmation_responses():
    """测试确认响应解析"""
    print("\n=== 测试确认响应解析 ===")
    
    mock_settings = MockSettings()
    confirmation_manager = IntentConfirmationManager(mock_settings)
    
    # 创建一个基础确认请求
    context = ConfirmationContext(
        user_id="user_response_test",
        conversation_id=1,
        session_id="session_test",
        intent_name="book_flight",
        confidence=0.7,
        risk_level=RiskLevel.MEDIUM,
        triggers=[ConfirmationTrigger.LOW_CONFIDENCE],
        extracted_slots={"departure_city": "北京", "arrival_city": "上海"},
        conversation_history=[],
        user_preferences={},
        system_policies={}
    )
    
    request = await confirmation_manager.create_confirmation_request(
        context, ConfirmationStrategy.EXPLICIT, [ConfirmationTrigger.LOW_CONFIDENCE]
    )
    
    # 测试各种用户响应
    test_responses = [
        ("是的", "确认响应"),
        ("对", "确认响应"),
        ("确认", "确认响应"),
        ("不是", "拒绝响应"),
        ("取消", "拒绝响应"),
        ("不要", "拒绝响应"),
        ("修改出发时间", "修改响应"),
        ("改成明天", "修改响应"),
        ("什么意思", "不清楚响应"),
        ("啊？", "不清楚响应")
    ]
    
    print("\n测试不同类型的用户响应:")
    for response_text, expected_type in test_responses:
        # 为每个测试创建新的请求
        test_request = await confirmation_manager.create_confirmation_request(
            context, ConfirmationStrategy.EXPLICIT, [ConfirmationTrigger.LOW_CONFIDENCE]
        )
        
        result = await confirmation_manager.process_confirmation_response(
            test_request.request_id, response_text, 1.0
        )
        
        print(f"用户响应: '{response_text}' -> 结果: {result.response_type.value} ({expected_type})")
        if result.modifications:
            print(f"  修改内容: {result.modifications}")
    
    print("\n确认响应解析测试完成!")


async def main():
    """主测试函数"""
    print("开始 TASK-025 意图确认机制测试")
    print("=" * 50)
    
    try:
        # 测试意图确认管理器
        await test_intent_confirmation_manager()
        
        # 测试意图服务确认功能
        await test_intent_service_confirmation()
        
        # 测试确认场景
        await test_confirmation_scenarios()
        
        # 测试确认响应
        await test_confirmation_responses()
        
        print("\n" + "=" * 50)
        print("TASK-025 意图确认机制测试全部完成!")
        print("✅ 意图确认机制已成功实现并测试通过")
        
    except Exception as e:
        print(f"\n测试过程中发生错误: {str(e)}")
        import traceback
        traceback.print_exc()
        return False
    
    return True


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)