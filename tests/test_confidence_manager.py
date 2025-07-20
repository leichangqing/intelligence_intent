"""
测试置信度管理器
"""
import pytest
import asyncio
from unittest.mock import Mock, patch

from src.core.confidence_manager import (
    ConfidenceManager, ConfidenceLevel, ConfidenceSource, 
    ConfidenceScore, ThresholdDecision
)
from src.config.settings import Settings
from src.models.intent import Intent


@pytest.fixture
def test_settings():
    """测试用的设置"""
    settings = Mock(spec=Settings)
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


@pytest.fixture
def confidence_manager(test_settings):
    """置信度管理器实例"""
    return ConfidenceManager(test_settings)


@pytest.fixture
def mock_intent():
    """模拟意图对象"""
    intent = Mock(spec=Intent)
    intent.name = "book_flight"
    intent.intent_name = "book_flight"
    intent.confidence_threshold = 0.7
    return intent


class TestConfidenceManager:
    """置信度管理器测试"""
    
    def test_initialization(self, confidence_manager, test_settings):
        """测试初始化"""
        assert confidence_manager.settings == test_settings
        assert confidence_manager.thresholds[ConfidenceLevel.HIGH] == 0.8
        assert confidence_manager.thresholds[ConfidenceLevel.MEDIUM] == 0.6
        assert confidence_manager.weights[ConfidenceSource.LLM] == 0.7
    
    def test_calculate_hybrid_confidence_llm_only(self, confidence_manager):
        """测试仅LLM置信度计算"""
        result = confidence_manager.calculate_hybrid_confidence(
            llm_confidence=0.8
        )
        
        assert isinstance(result, ConfidenceScore)
        assert result.value == 0.8
        assert result.source == ConfidenceSource.HYBRID
        assert 'llm' in result.components
        assert result.components['llm'] == 0.8
    
    def test_calculate_hybrid_confidence_multiple_sources(self, confidence_manager):
        """测试多源置信度计算"""
        result = confidence_manager.calculate_hybrid_confidence(
            llm_confidence=0.8,
            rule_confidence=0.6,
            context_confidence=0.7
        )
        
        # 计算期望值: (0.8*0.7 + 0.6*0.3 + 0.7*0.1) / (0.7+0.3+0.1) = 0.75/1.1
        expected = (0.8 * 0.7 + 0.6 * 0.3 + 0.7 * 0.1) / (0.7 + 0.3 + 0.1)
        
        assert isinstance(result, ConfidenceScore)
        assert abs(result.value - expected) < 0.001
        assert result.source == ConfidenceSource.HYBRID
        assert len(result.components) == 3
    
    def test_calculate_hybrid_confidence_edge_cases(self, confidence_manager):
        """测试边界情况"""
        # 无输入
        result = confidence_manager.calculate_hybrid_confidence()
        assert result.value == 0.0
        
        # 超出范围的置信度
        result = confidence_manager.calculate_hybrid_confidence(
            llm_confidence=1.5  # 超过1.0
        )
        assert result.value <= 1.0
        
        result = confidence_manager.calculate_hybrid_confidence(
            llm_confidence=-0.1  # 小于0.0
        )
        assert result.value >= 0.0
    
    def test_get_confidence_level(self, confidence_manager):
        """测试置信度等级判断"""
        assert confidence_manager._get_confidence_level(0.9) == ConfidenceLevel.HIGH
        assert confidence_manager._get_confidence_level(0.7) == ConfidenceLevel.MEDIUM
        assert confidence_manager._get_confidence_level(0.5) == ConfidenceLevel.LOW
        assert confidence_manager._get_confidence_level(0.2) == ConfidenceLevel.REJECT
    
    def test_make_threshold_decision_pass(self, confidence_manager, mock_intent):
        """测试阈值决策通过"""
        confidence_score = ConfidenceScore(
            value=0.8,
            source=ConfidenceSource.LLM,
            components={'llm': 0.8}
        )
        
        decision = confidence_manager.make_threshold_decision(
            confidence_score, mock_intent
        )
        
        assert isinstance(decision, ThresholdDecision)
        assert decision.passed == True
        assert decision.level == ConfidenceLevel.HIGH
        assert decision.confidence_score == 0.8
    
    def test_make_threshold_decision_fail(self, confidence_manager, mock_intent):
        """测试阈值决策失败"""
        confidence_score = ConfidenceScore(
            value=0.5,
            source=ConfidenceSource.LLM,
            components={'llm': 0.5}
        )
        
        decision = confidence_manager.make_threshold_decision(
            confidence_score, mock_intent
        )
        
        assert decision.passed == False
        assert decision.level == ConfidenceLevel.LOW
        assert decision.confidence_score == 0.5
    
    def test_calibrate_confidence_by_source(self, confidence_manager):
        """测试按来源校准置信度"""
        # LLM置信度校准
        llm_calibrated = confidence_manager.calibrate_confidence(
            0.8, ConfidenceSource.LLM
        )
        assert llm_calibrated == 0.8 * 0.95
        
        # 规则置信度校准
        rule_calibrated = confidence_manager.calibrate_confidence(
            0.95, ConfidenceSource.RULE
        )
        assert rule_calibrated == 0.90  # 限制上限
        
        # 上下文置信度校准
        context_calibrated = confidence_manager.calibrate_confidence(
            0.7, ConfidenceSource.CONTEXT
        )
        assert context_calibrated == 0.7 * 0.8
    
    def test_update_intent_statistics(self, confidence_manager):
        """测试意图统计更新"""
        intent_name = "test_intent"
        
        # 添加成功案例
        for i in range(5):
            confidence_manager.update_intent_statistics(
                intent_name, 0.8, success=True
            )
        
        # 添加失败案例
        for i in range(2):
            confidence_manager.update_intent_statistics(
                intent_name, 0.5, success=False
            )
        
        stats = confidence_manager.get_confidence_statistics()
        
        assert intent_name in stats
        intent_stats = stats[intent_name]
        assert intent_stats['total_samples'] == 7
        assert intent_stats['success_count'] == 5
        assert intent_stats['failure_count'] == 2
        assert intent_stats['success_rate'] == 5/7
    
    def test_adaptive_threshold_update(self, confidence_manager):
        """测试自适应阈值更新"""
        intent_name = "adaptive_intent"
        
        # 添加足够的样本触发自适应更新
        for i in range(15):
            confidence_manager.update_intent_statistics(
                intent_name, 0.8, success=True
            )
        
        # 应该生成自适应阈值
        assert intent_name in confidence_manager._adaptive_thresholds
        adaptive_threshold = confidence_manager._adaptive_thresholds[intent_name]
        assert 0.3 <= adaptive_threshold <= 0.9
    
    def test_adaptive_adjustment(self, confidence_manager):
        """测试自适应调整"""
        intent_name = "adjust_intent"
        
        # 添加高成功率的历史数据
        for i in range(15):
            confidence_manager.update_intent_statistics(
                intent_name, 0.9, success=True
            )
        
        # 测试调整
        original_confidence = 0.7
        adjusted = confidence_manager._apply_adaptive_adjustment(
            original_confidence, intent_name
        )
        
        # 高成功率应该轻微提升置信度
        assert adjusted >= original_confidence
    
    def test_confidence_explanation_generation(self, confidence_manager):
        """测试置信度解释生成"""
        components = {
            'llm': 0.8,
            'rule': 0.6,
            'context': 0.7
        }
        
        explanation = confidence_manager._generate_confidence_explanation(
            components, 0.75
        )
        
        assert "综合置信度 0.750" in explanation
        assert "LLM: 0.800" in explanation
        assert "规则: 0.600" in explanation
        assert "上下文: 0.700" in explanation
    
    def test_decision_reason_generation(self, confidence_manager):
        """测试决策理由生成"""
        reason = confidence_manager._generate_decision_reason(
            0.8, 0.7, ConfidenceLevel.HIGH, "global", True
        )
        
        assert "置信度 0.800" in reason
        assert "通过" in reason
        assert "global阈值 0.700" in reason
        assert "等级: high" in reason


class TestConfidenceIntegration:
    """置信度系统集成测试"""
    
    def test_end_to_end_confidence_flow(self, confidence_manager, mock_intent):
        """测试端到端置信度流程"""
        # 1. 计算混合置信度
        confidence_score = confidence_manager.calculate_hybrid_confidence(
            llm_confidence=0.8,
            rule_confidence=0.7,
            intent_name=mock_intent.intent_name
        )
        
        # 2. 进行阈值决策
        decision = confidence_manager.make_threshold_decision(
            confidence_score, mock_intent
        )
        
        # 3. 更新统计
        confidence_manager.update_intent_statistics(
            mock_intent.intent_name, confidence_score.value, decision.passed
        )
        
        # 4. 获取统计信息
        stats = confidence_manager.get_confidence_statistics()
        
        assert isinstance(confidence_score, ConfidenceScore)
        assert isinstance(decision, ThresholdDecision)
        assert mock_intent.intent_name in stats
        
    def test_ambiguity_detection_integration(self, confidence_manager, mock_intent):
        """测试歧义检测集成"""
        alternatives = [
            ("intent1", 0.75),
            ("intent2", 0.74),  # 差值0.01 < 0.1阈值
            ("intent3", 0.6)
        ]
        
        confidence_score = ConfidenceScore(
            value=0.75,
            source=ConfidenceSource.HYBRID,
            components={'hybrid': 0.75}
        )
        
        decision = confidence_manager.make_threshold_decision(
            confidence_score, mock_intent, alternatives
        )
        
        # 应该检测到歧义
        assert "歧义" in decision.reason
        assert decision.alternatives == alternatives


if __name__ == "__main__":
    pytest.main([__file__, "-v"])