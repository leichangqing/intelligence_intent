#!/usr/bin/env python3
"""
TASK-024 测试脚本
测试用户选择解析功能
"""

import asyncio
import sys
import os

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.core.advanced_choice_parser import (
    AdvancedChoiceParser, 
    ChoiceType, 
    ConfidenceLevel,
    ParseResult
)

async def test_basic_choice_parsing():
    """测试基本选择解析"""
    print("=== 测试基本选择解析 ===")
    
    parser = AdvancedChoiceParser()
    
    # 测试候选选项
    candidates = [
        {"intent_name": "book_flight", "display_name": "预订机票"},
        {"intent_name": "check_balance", "display_name": "查询余额"},
        {"intent_name": "transfer_money", "display_name": "转账"}
    ]
    
    # 测试各种输入类型
    test_cases = [
        ("1", "数字选择"),
        ("第二个", "中文序号"),
        ("查询余额", "直接文本匹配"),
        ("我要预订机票", "自然语言描述"),
        ("转账", "简化文本"),
        ("都不是", "否定回答"),
        ("不知道", "不确定回答"),
        ("abc123", "无效输入")
    ]
    
    for user_input, description in test_cases:
        result = await parser.parse_user_choice(user_input, candidates)
        print(f"输入: '{user_input}' ({description})")
        print(f"  -> 选择类型: {result.choice_type.value}")
        print(f"  -> 选择项: {result.selected_option}")
        print(f"  -> 选择文本: {result.selected_text}")
        print(f"  -> 置信度: {result.confidence:.3f} ({result.confidence_level.value})")
        print(f"  -> 解释: {result.explanation}")
        print()

async def test_context_aware_parsing():
    """测试上下文感知解析"""
    print("=== 测试上下文感知解析 ===")
    
    parser = AdvancedChoiceParser()
    
    candidates = [
        {"intent_name": "book_flight", "display_name": "预订机票"},
        {"intent_name": "check_balance", "display_name": "查询余额"},
        {"intent_name": "transfer_money", "display_name": "转账"}
    ]
    
    # 测试上下文信息
    context = {
        "conversation_history": [
            {"intent": "book_flight", "timestamp": "2024-01-01"},
            {"intent": "check_balance", "timestamp": "2024-01-02"}
        ],
        "user_preferences": {
            "preferred_book_flight": True
        },
        "current_intent": "check_balance"
    }
    
    test_cases = [
        ("第一个", "序列选择"),
        ("还是查询", "基于当前意图"),
        ("像上次一样", "基于历史"),
        ("我的偏好", "基于用户偏好")
    ]
    
    for user_input, description in test_cases:
        result = await parser.parse_user_choice(user_input, candidates, context=context)
        print(f"输入: '{user_input}' ({description})")
        print(f"  -> 选择类型: {result.choice_type.value}")
        print(f"  -> 选择项: {result.selected_option}")
        print(f"  -> 置信度: {result.confidence:.3f}")
        print(f"  -> 处理步骤: {result.processing_steps}")
        print()

async def test_user_pattern_learning():
    """测试用户模式学习"""
    print("=== 测试用户模式学习 ===")
    
    parser = AdvancedChoiceParser()
    
    candidates = [
        {"intent_name": "book_flight", "display_name": "预订机票"},
        {"intent_name": "check_balance", "display_name": "查询余额"}
    ]
    
    user_id = "test_user_123"
    
    # 模拟用户交互历史
    interaction_history = [
        ("1", True),  # 成功
        ("第一个", True),  # 成功
        ("查询", False),  # 失败
        ("2", True),  # 成功
        ("余额", True)  # 成功
    ]
    
    # 建立用户模式
    print("建立用户模式...")
    for user_input, success in interaction_history:
        result = await parser.parse_user_choice(user_input, candidates, user_id=user_id)
        parser.update_user_pattern(user_id, result, success)
        print(f"学习: '{user_input}' -> {result.choice_type.value} ({'成功' if success else '失败'})")
    
    print("\n基于学习的模式进行解析...")
    # 测试基于学习模式的解析
    test_inputs = ["数字1", "第二个", "check"]
    for test_input in test_inputs:
        result = await parser.parse_user_choice(test_input, candidates, user_id=user_id)
        print(f"输入: '{test_input}' -> {result.choice_type.value}, 置信度: {result.confidence:.3f}")

async def test_multi_choice_parsing():
    """测试多选择解析"""
    print("=== 测试多选择解析 ===")
    
    parser = AdvancedChoiceParser()
    
    candidates = [
        {"intent_name": "book_flight", "display_name": "预订机票"},
        {"intent_name": "check_balance", "display_name": "查询余额"},
        {"intent_name": "transfer_money", "display_name": "转账"},
        {"intent_name": "pay_bill", "display_name": "缴费"}
    ]
    
    # 测试多选输入
    multi_choice_inputs = [
        ("1和2", "数字多选"),
        ("预订机票和查询余额", "文本多选"),
        ("第一个还有第三个", "序号多选"),
        ("转账、缴费", "逗号分隔"),
        ("都要", "全选指示")
    ]
    
    for user_input, description in multi_choice_inputs:
        results = await parser.parse_multi_choice(user_input, candidates, allow_multiple=True)
        print(f"输入: '{user_input}' ({description})")
        print(f"  -> 解析到 {len(results)} 个选择:")
        for i, result in enumerate(results):
            print(f"    {i+1}. {result.selected_text} (置信度: {result.confidence:.3f})")
        print()

async def test_feedback_based_parsing():
    """测试基于反馈的解析"""
    print("=== 测试基于反馈的解析 ===")
    
    parser = AdvancedChoiceParser()
    
    candidates = [
        {"intent_name": "book_flight", "display_name": "预订机票"},
        {"intent_name": "check_balance", "display_name": "查询余额"},
        {"intent_name": "transfer_money", "display_name": "转账"}
    ]
    
    # 第一次解析
    initial_result = await parser.parse_user_choice("机票", candidates)
    print(f"初始解析: '{initial_result.selected_text}' (置信度: {initial_result.confidence:.3f})")
    
    # 测试正面反馈
    positive_feedback_result = await parser.parse_with_feedback(
        "机票", candidates, initial_result, "对的"
    )
    print(f"正面反馈后: '{positive_feedback_result.selected_text}' (置信度: {positive_feedback_result.confidence:.3f})")
    
    # 测试负面反馈
    negative_feedback_result = await parser.parse_with_feedback(
        "机票", candidates, initial_result, "不对"
    )
    print(f"负面反馈后: '{negative_feedback_result.selected_text}' (置信度: {negative_feedback_result.confidence:.3f})")
    print(f"解释: {negative_feedback_result.explanation}")

async def test_parsing_analytics():
    """测试解析分析功能"""
    print("=== 测试解析分析功能 ===")
    
    parser = AdvancedChoiceParser()
    
    candidates = [
        {"intent_name": "book_flight", "display_name": "预订机票"},
        {"intent_name": "check_balance", "display_name": "查询余额"}
    ]
    
    # 模拟一些解析历史
    user_id = "analytics_user"
    test_inputs = ["1", "查询", "第二个", "abc", "余额", "2", "invalid", "预订"]
    
    for user_input in test_inputs:
        await parser.parse_user_choice(user_input, candidates, user_id=user_id)
    
    # 获取分析报告
    analytics = parser.get_parsing_analytics(user_id)
    print(f"用户 {user_id} 的解析分析:")
    print(f"  总解析次数: {analytics['total_parses']}")
    print(f"  成功率: {analytics['success_rate']:.1%}")
    print(f"  最近成功率: {analytics['recent_success_rate']:.1%}")
    print(f"  平均置信度: {analytics['avg_confidence']:.3f}")
    print(f"  趋势: {analytics['trend']}")
    print(f"  选择类型分布: {analytics['choice_type_distribution']}")
    print(f"  置信度等级分布: {analytics['confidence_level_distribution']}")
    
    # 全局分析
    global_analytics = parser.get_parsing_analytics()
    print(f"\n全局解析分析:")
    print(f"  总解析次数: {global_analytics['total_parses']}")
    print(f"  成功率: {global_analytics['success_rate']:.1%}")

async def test_error_handling_and_correction():
    """测试错误处理和纠正"""
    print("=== 测试错误处理和纠正 ===")
    
    parser = AdvancedChoiceParser()
    
    candidates = [
        {"intent_name": "book_flight", "display_name": "预订机票"},
        {"intent_name": "check_balance", "display_name": "查询余额"}
    ]
    
    # 测试各种错误情况
    error_cases = [
        ("", "空输入"),
        ("999", "超出范围的数字"),
        ("l", "数字拼写错误"),
        ("O", "数字拼写错误"),
        ("机漂", "拼写错误"),
        ("余额查询", "词序不同"),
        ("我想要第100个", "超出范围"),
        ("???", "无效字符")
    ]
    
    for user_input, description in error_cases:
        result = await parser.parse_user_choice(user_input, candidates)
        print(f"输入: '{user_input}' ({description})")
        print(f"  -> 选择类型: {result.choice_type.value}")
        print(f"  -> 置信度: {result.confidence:.3f}")
        print(f"  -> 纠错建议: {result.error_corrections}")
        print(f"  -> 解释: {result.explanation}")
        print()

async def test_performance_benchmarks():
    """测试性能基准"""
    print("=== 测试性能基准 ===")
    
    parser = AdvancedChoiceParser()
    
    candidates = [
        {"intent_name": "book_flight", "display_name": "预订机票"},
        {"intent_name": "check_balance", "display_name": "查询余额"},
        {"intent_name": "transfer_money", "display_name": "转账"}
    ]
    
    # 测试批量解析性能
    import time
    
    test_inputs = ["1", "预订", "第二个", "查询余额", "转账"] * 20  # 100个输入
    
    start_time = time.time()
    
    for user_input in test_inputs:
        await parser.parse_user_choice(user_input, candidates)
    
    end_time = time.time()
    
    total_time = end_time - start_time
    avg_time = total_time / len(test_inputs)
    
    print(f"批量解析性能测试:")
    print(f"  总输入数: {len(test_inputs)}")
    print(f"  总耗时: {total_time:.3f}秒")
    print(f"  平均每次解析: {avg_time:.3f}秒")
    print(f"  每秒处理能力: {len(test_inputs)/total_time:.1f} 次/秒")
    
    # 内存使用情况
    import psutil
    import os
    
    process = psutil.Process(os.getpid())
    memory_info = process.memory_info()
    print(f"  内存使用: {memory_info.rss / 1024 / 1024:.1f} MB")
    
    # 解析器统计
    stats = parser.get_parser_statistics()
    print(f"  解析器统计: {stats}")

async def main():
    """主测试函数"""
    print("开始TASK-024用户选择解析测试")
    
    try:
        await test_basic_choice_parsing()
        await test_context_aware_parsing()
        await test_user_pattern_learning()
        await test_multi_choice_parsing()
        await test_feedback_based_parsing()
        await test_parsing_analytics()
        await test_error_handling_and_correction()
        await test_performance_benchmarks()
        
        print("\n=== 测试完成 ===")
        print("TASK-024用户选择解析功能测试通过!")
        
    except Exception as e:
        print(f"测试失败: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())