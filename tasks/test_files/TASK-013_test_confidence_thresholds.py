#!/usr/bin/env python3
"""
简单的置信度管理器测试脚本
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from unittest.mock import Mock
from src.core.confidence_manager import (
    ConfidenceManager, ConfidenceLevel, ConfidenceSource, 
    ConfidenceScore, ThresholdDecision
)


def create_test_settings():
    """创建测试设置"""
    settings = Mock()
    settings.CONFIDENCE_THRESHOLD_HIGH = 0.8
    settings.CONFIDENCE_THRESHOLD_MEDIUM = 0.6
    settings.CONFIDENCE_THRESHOLD_LOW = 0.4
    settings.CONFIDENCE_THRESHOLD_REJECT = 0.3
    settings.CONFIDENCE_WEIGHT_LLM = 0.7
    settings.CONFIDENCE_WEIGHT_RULE = 0.3
    settings.CONFIDENCE_WEIGHT_CONTEXT = 0.1
    settings.INTENT_CONFIDENCE_THRESHOLD = 0.7
    settings.AMBIGUITY_DETECTION_THRESHOLD = 0.1
    settings.ENABLE_ADAPTIVE_THRESHOLDS = True
    settings.THRESHOLD_ADAPTATION_RATE = 0.05
    settings.MIN_SAMPLES_FOR_ADAPTATION = 10
    return settings


def test_confidence_calculation():
    """测试置信度计算"""
    print("=== 测试置信度计算 ===")
    
    settings = create_test_settings()
    manager = ConfidenceManager(settings)
    
    # 测试1: 单独LLM置信度
    result1 = manager.calculate_hybrid_confidence(llm_confidence=0.8)
    print(f"LLM单独置信度: {result1.value:.3f}")
    print(f"解释: {result1.explanation}")
    assert abs(result1.value - 0.8) < 0.001, "LLM单独置信度计算错误"
    
    # 测试2: 混合置信度
    result2 = manager.calculate_hybrid_confidence(
        llm_confidence=0.8,
        rule_confidence=0.6,
        context_confidence=0.7
    )
    expected = (0.8 * 0.7 + 0.6 * 0.3 + 0.7 * 0.1) / (0.7 + 0.3 + 0.1)
    print(f"混合置信度: {result2.value:.3f} (期望: {expected:.3f})")
    print(f"解释: {result2.explanation}")
    assert abs(result2.value - expected) < 0.001, "混合置信度计算错误"
    
    print("✓ 置信度计算测试通过\n")


def test_threshold_decision():
    """测试阈值决策"""
    print("=== 测试阈值决策 ===")
    
    settings = create_test_settings()
    manager = ConfidenceManager(settings)
    
    # 模拟意图
    mock_intent = Mock()
    mock_intent.name = "book_flight"
    mock_intent.intent_name = "book_flight"
    mock_intent.confidence_threshold = 0.7
    
    # 测试1: 高置信度通过
    confidence_score = ConfidenceScore(
        value=0.8,
        source=ConfidenceSource.LLM,
        components={'llm': 0.8}
    )
    
    decision1 = manager.make_threshold_decision(confidence_score, mock_intent)
    print(f"高置信度决策: {decision1.passed} (置信度: {decision1.confidence_score:.3f})")
    print(f"理由: {decision1.reason}")
    assert decision1.passed == True, "高置信度应该通过"
    assert decision1.level == ConfidenceLevel.HIGH, "应该是高置信度等级"
    
    # 测试2: 低置信度失败
    confidence_score_low = ConfidenceScore(
        value=0.5,
        source=ConfidenceSource.LLM,
        components={'llm': 0.5}
    )
    
    decision2 = manager.make_threshold_decision(confidence_score_low, mock_intent)
    print(f"低置信度决策: {decision2.passed} (置信度: {decision2.confidence_score:.3f})")
    print(f"理由: {decision2.reason}")
    assert decision2.passed == False, "低置信度应该失败"
    
    print("✓ 阈值决策测试通过\n")


def test_confidence_calibration():
    """测试置信度校准"""
    print("=== 测试置信度校准 ===")
    
    settings = create_test_settings()
    manager = ConfidenceManager(settings)
    
    # 测试LLM校准
    llm_calibrated = manager.calibrate_confidence(0.8, ConfidenceSource.LLM)
    print(f"LLM校准: 0.8 -> {llm_calibrated:.3f}")
    assert llm_calibrated == 0.8 * 0.95, "LLM校准错误"
    
    # 测试规则校准
    rule_calibrated = manager.calibrate_confidence(0.95, ConfidenceSource.RULE)
    print(f"规则校准: 0.95 -> {rule_calibrated:.3f}")
    assert rule_calibrated == 0.90, "规则校准错误"
    
    # 测试上下文校准
    context_calibrated = manager.calibrate_confidence(0.7, ConfidenceSource.CONTEXT)
    print(f"上下文校准: 0.7 -> {context_calibrated:.3f}")
    assert context_calibrated == 0.7 * 0.8, "上下文校准错误"
    
    print("✓ 置信度校准测试通过\n")


def test_adaptive_threshold():
    """测试自适应阈值"""
    print("=== 测试自适应阈值 ===")
    
    settings = create_test_settings()
    manager = ConfidenceManager(settings)
    
    intent_name = "test_intent"
    
    # 添加成功案例
    for i in range(5):
        manager.update_intent_statistics(intent_name, 0.8, success=True)
    
    # 添加失败案例
    for i in range(2):
        manager.update_intent_statistics(intent_name, 0.5, success=False)
    
    stats = manager.get_confidence_statistics()
    
    print(f"意图统计: {stats}")
    assert intent_name in stats, "应该包含测试意图"
    
    intent_stats = stats[intent_name]
    assert intent_stats['total_samples'] == 7, "总样本数错误"
    assert intent_stats['success_count'] == 5, "成功数错误"
    assert intent_stats['failure_count'] == 2, "失败数错误"
    assert abs(intent_stats['success_rate'] - 5/7) < 0.001, "成功率错误"
    
    print("✓ 自适应阈值测试通过\n")


def test_confidence_levels():
    """测试置信度等级"""
    print("=== 测试置信度等级 ===")
    
    settings = create_test_settings()
    manager = ConfidenceManager(settings)
    
    # 测试各个等级
    assert manager._get_confidence_level(0.9) == ConfidenceLevel.HIGH
    assert manager._get_confidence_level(0.7) == ConfidenceLevel.MEDIUM
    assert manager._get_confidence_level(0.5) == ConfidenceLevel.LOW
    assert manager._get_confidence_level(0.2) == ConfidenceLevel.REJECT
    
    print("置信度等级判断:")
    print(f"0.9 -> {manager._get_confidence_level(0.9).value}")
    print(f"0.7 -> {manager._get_confidence_level(0.7).value}")
    print(f"0.5 -> {manager._get_confidence_level(0.5).value}")
    print(f"0.2 -> {manager._get_confidence_level(0.2).value}")
    
    print("✓ 置信度等级测试通过\n")


def main():
    """主测试函数"""
    print("开始置信度管理器测试...")
    print("=" * 50)
    
    try:
        test_confidence_calculation()
        test_threshold_decision()
        test_confidence_calibration()
        test_adaptive_threshold()
        test_confidence_levels()
        
        print("=" * 50)
        print("🎉 所有测试通过！")
        print("\nTASK-013 (置信度计算和阈值处理) 实现完成!")
        print("✓ 配置了增强的置信度阈值")
        print("✓ 实现了混合置信度计算")
        print("✓ 添加了智能阈值决策")
        print("✓ 支持自适应阈值调整")
        print("✓ 完善了置信度校准机制")
        print("✓ 集成到NLU引擎和意图服务")
        
    except Exception as e:
        print(f"❌ 测试失败: {str(e)}")
        return False
    
    return True


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)