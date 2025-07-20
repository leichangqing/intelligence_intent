"""
查询处理器单元测试
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from typing import Dict, List, Optional, Any
import json
from datetime import datetime, timedelta

from src.services.query_processor import (
    QueryProcessor, QueryType, QueryComplexity, QueryIntent,
    QueryEntity, QueryAnalysis, ProcessedQuery, QueryContext
)
from src.services.cache_service import CacheService


class TestQueryEntity:
    """查询实体测试类"""
    
    def test_init_default_values(self):
        """测试默认值初始化"""
        entity = QueryEntity(
            text="北京",
            entity_type="location",
            confidence=0.9,
            start_pos=0,
            end_pos=2
        )
        
        assert entity.text == "北京"
        assert entity.entity_type == "location"
        assert entity.confidence == 0.9
        assert entity.start_pos == 0
        assert entity.end_pos == 2
        assert entity.synonyms == []
        assert entity.related_terms == []
    
    def test_init_with_optional_fields(self):
        """测试带可选字段的初始化"""
        entity = QueryEntity(
            text="上海",
            entity_type="location",
            confidence=0.85,
            start_pos=5,
            end_pos=7,
            synonyms=["魔都", "申城"],
            related_terms=["浦东", "外滩"]
        )
        
        assert entity.text == "上海"
        assert entity.synonyms == ["魔都", "申城"]
        assert entity.related_terms == ["浦东", "外滩"]


class TestQueryAnalysis:
    """查询分析测试类"""
    
    def test_init_complete(self):
        """测试完整初始化"""
        entities = [
            QueryEntity("北京", "location", 0.9, 0, 2),
            QueryEntity("天气", "concept", 0.8, 3, 5)
        ]
        
        analysis = QueryAnalysis(
            original_query="北京天气怎么样",
            normalized_query="北京 天气 怎么样",
            query_type=QueryType.FACTUAL,
            query_complexity=QueryComplexity.SIMPLE,
            query_intent=QueryIntent.SEARCH,
            entities=entities,
            keywords=["北京", "天气"],
            semantic_keywords=["天气预报", "气象"],
            confidence=0.85,
            language="zh",
            domain="weather"
        )
        
        assert analysis.original_query == "北京天气怎么样"
        assert analysis.normalized_query == "北京 天气 怎么样"
        assert analysis.query_type == QueryType.FACTUAL
        assert analysis.query_complexity == QueryComplexity.SIMPLE
        assert analysis.query_intent == QueryIntent.SEARCH
        assert len(analysis.entities) == 2
        assert analysis.keywords == ["北京", "天气"]
        assert analysis.semantic_keywords == ["天气预报", "气象"]
        assert analysis.confidence == 0.85
        assert analysis.language == "zh"
        assert analysis.domain == "weather"


class TestProcessedQuery:
    """处理后查询测试类"""
    
    def test_init_complete(self):
        """测试完整初始化"""
        analysis = QueryAnalysis(
            original_query="北京天气",
            normalized_query="北京 天气",
            query_type=QueryType.FACTUAL,
            query_complexity=QueryComplexity.SIMPLE,
            query_intent=QueryIntent.SEARCH,
            entities=[],
            keywords=["北京", "天气"],
            semantic_keywords=["天气预报"],
            confidence=0.9
        )
        
        processed_query = ProcessedQuery(
            original_query="北京天气",
            enhanced_query="北京 天气 预报 气象",
            analysis=analysis,
            search_strategies=["semantic_search", "keyword_search"],
            filters={"location": "北京", "type": "weather"},
            boost_terms=["天气", "气象"],
            context_terms=["预报", "温度"],
            expected_answer_type="weather_info",
            routing_config="weather_kb"
        )
        
        assert processed_query.original_query == "北京天气"
        assert processed_query.enhanced_query == "北京 天气 预报 气象"
        assert processed_query.analysis == analysis
        assert processed_query.search_strategies == ["semantic_search", "keyword_search"]
        assert processed_query.filters == {"location": "北京", "type": "weather"}
        assert processed_query.boost_terms == ["天气", "气象"]
        assert processed_query.context_terms == ["预报", "温度"]
        assert processed_query.expected_answer_type == "weather_info"
        assert processed_query.routing_config == "weather_kb"
        assert processed_query.metadata == {}


class TestQueryProcessor:
    """查询处理器测试类"""
    
    @pytest.fixture
    def mock_cache_service(self):
        """模拟缓存服务"""
        return AsyncMock(spec=CacheService)
    
    @pytest.fixture
    def query_processor(self, mock_cache_service):
        """创建查询处理器实例"""
        processor = QueryProcessor(mock_cache_service)
        return processor
    
    @pytest.mark.asyncio
    async def test_process_query_simple(self, query_processor, mock_cache_service):
        """测试简单查询处理"""
        # 准备测试数据
        query = "北京天气怎么样"
        context = QueryContext(
            session_id="sess_123",
            user_id="user_456",
            conversation_history=[],
            user_preferences={}
        )
        
        # 设置模拟行为
        mock_cache_service.get.return_value = None
        
        # 模拟查询分析
        mock_analysis = QueryAnalysis(
            original_query=query,
            normalized_query="北京 天气 怎么样",
            query_type=QueryType.FACTUAL,
            query_complexity=QueryComplexity.SIMPLE,
            query_intent=QueryIntent.SEARCH,
            entities=[QueryEntity("北京", "location", 0.9, 0, 2)],
            keywords=["北京", "天气"],
            semantic_keywords=["天气预报", "气象"],
            confidence=0.85
        )
        
        with patch.object(query_processor, '_analyze_query', return_value=mock_analysis), \
             patch.object(query_processor, '_enhance_query', return_value="北京 天气 预报"), \
             patch.object(query_processor, '_determine_search_strategies', return_value=["semantic_search"]), \
             patch.object(query_processor, '_extract_filters', return_value={"location": "北京"}), \
             patch.object(query_processor, '_identify_boost_terms', return_value=["天气"]), \
             patch.object(query_processor, '_get_context_terms', return_value=["预报"]), \
             patch.object(query_processor, '_determine_answer_type', return_value="weather_info"), \
             patch.object(query_processor, '_determine_routing', return_value="weather_kb"):
            
            # 调用方法
            result = await query_processor.process_query(query, context)
            
            # 验证结果
            assert isinstance(result, ProcessedQuery)
            assert result.original_query == query
            assert result.enhanced_query == "北京 天气 预报"
            assert result.analysis == mock_analysis
            assert result.search_strategies == ["semantic_search"]
            assert result.filters == {"location": "北京"}
            assert result.boost_terms == ["天气"]
            assert result.context_terms == ["预报"]
            assert result.expected_answer_type == "weather_info"
            assert result.routing_config == "weather_kb"
    
    @pytest.mark.asyncio
    async def test_process_query_from_cache(self, query_processor, mock_cache_service):
        """测试从缓存获取查询处理结果"""
        # 准备测试数据
        query = "上海天气预报"
        context = QueryContext(
            session_id="sess_789",
            user_id="user_123",
            conversation_history=[],
            user_preferences={}
        )
        
        # 模拟缓存结果
        cached_result = {
            "original_query": query,
            "enhanced_query": "上海 天气 预报",
            "analysis": {
                "original_query": query,
                "normalized_query": "上海 天气 预报",
                "query_type": "factual",
                "query_complexity": "simple",
                "query_intent": "search",
                "entities": [],
                "keywords": ["上海", "天气"],
                "semantic_keywords": ["天气预报"],
                "confidence": 0.9
            },
            "search_strategies": ["semantic_search"],
            "filters": {"location": "上海"},
            "boost_terms": ["天气"],
            "context_terms": ["预报"],
            "expected_answer_type": "weather_info",
            "routing_config": "weather_kb",
            "metadata": {}
        }
        
        # 设置模拟行为
        mock_cache_service.get.return_value = cached_result
        
        # 调用方法
        result = await query_processor.process_query(query, context)
        
        # 验证结果
        assert isinstance(result, ProcessedQuery)
        assert result.original_query == query
        assert result.enhanced_query == "上海 天气 预报"
        
        # 验证缓存被调用
        query_hash = query_processor._generate_cache_key(query, context)
        mock_cache_service.get.assert_called_once_with(f"processed_query:{query_hash}")
    
    @pytest.mark.asyncio
    async def test_analyze_query_factual(self, query_processor):
        """测试事实性查询分析"""
        # 准备测试数据
        query = "北京的人口是多少"
        context = QueryContext(
            session_id="sess_123",
            user_id="user_456",
            conversation_history=[],
            user_preferences={}
        )
        
        # 模拟实体提取
        entities = [QueryEntity("北京", "location", 0.9, 0, 2)]
        
        with patch.object(query_processor, '_extract_entities', return_value=entities), \
             patch.object(query_processor, '_extract_keywords', return_value=["北京", "人口"]), \
             patch.object(query_processor, '_generate_semantic_keywords', return_value=["人口数量", "人口统计"]), \
             patch.object(query_processor, '_classify_query_type', return_value=QueryType.FACTUAL), \
             patch.object(query_processor, '_assess_complexity', return_value=QueryComplexity.SIMPLE), \
             patch.object(query_processor, '_identify_intent', return_value=QueryIntent.SEARCH), \
             patch.object(query_processor, '_normalize_query', return_value="北京 人口 多少"):
            
            # 调用方法
            result = await query_processor._analyze_query(query, context)
            
            # 验证结果
            assert isinstance(result, QueryAnalysis)
            assert result.original_query == query
            assert result.normalized_query == "北京 人口 多少"
            assert result.query_type == QueryType.FACTUAL
            assert result.query_complexity == QueryComplexity.SIMPLE
            assert result.query_intent == QueryIntent.SEARCH
            assert len(result.entities) == 1
            assert result.entities[0].text == "北京"
            assert result.keywords == ["北京", "人口"]
            assert result.semantic_keywords == ["人口数量", "人口统计"]
    
    @pytest.mark.asyncio
    async def test_analyze_query_complex(self, query_processor):
        """测试复杂查询分析"""
        # 准备测试数据
        query = "比较北京和上海的GDP增长率，并分析其影响因素"
        context = QueryContext(
            session_id="sess_456",
            user_id="user_789",
            conversation_history=[],
            user_preferences={}
        )
        
        # 模拟实体提取
        entities = [
            QueryEntity("北京", "location", 0.9, 2, 4),
            QueryEntity("上海", "location", 0.9, 5, 7),
            QueryEntity("GDP", "concept", 0.8, 9, 12)
        ]
        
        with patch.object(query_processor, '_extract_entities', return_value=entities), \
             patch.object(query_processor, '_extract_keywords', return_value=["北京", "上海", "GDP", "增长率"]), \
             patch.object(query_processor, '_generate_semantic_keywords', return_value=["经济增长", "GDP对比"]), \
             patch.object(query_processor, '_classify_query_type', return_value=QueryType.COMPARATIVE), \
             patch.object(query_processor, '_assess_complexity', return_value=QueryComplexity.COMPLEX), \
             patch.object(query_processor, '_identify_intent', return_value=QueryIntent.COMPARE), \
             patch.object(query_processor, '_normalize_query', return_value="比较 北京 上海 GDP 增长率 分析 影响因素"):
            
            # 调用方法
            result = await query_processor._analyze_query(query, context)
            
            # 验证结果
            assert isinstance(result, QueryAnalysis)
            assert result.query_type == QueryType.COMPARATIVE
            assert result.query_complexity == QueryComplexity.COMPLEX
            assert result.query_intent == QueryIntent.COMPARE
            assert len(result.entities) == 3
            assert result.keywords == ["北京", "上海", "GDP", "增长率"]
            assert result.semantic_keywords == ["经济增长", "GDP对比"]
    
    @pytest.mark.asyncio
    async def test_enhance_query(self, query_processor):
        """测试查询增强"""
        # 准备测试数据
        analysis = QueryAnalysis(
            original_query="北京天气",
            normalized_query="北京 天气",
            query_type=QueryType.FACTUAL,
            query_complexity=QueryComplexity.SIMPLE,
            query_intent=QueryIntent.SEARCH,
            entities=[QueryEntity("北京", "location", 0.9, 0, 2)],
            keywords=["北京", "天气"],
            semantic_keywords=["天气预报", "气象"],
            confidence=0.85
        )
        
        context = QueryContext(
            session_id="sess_123",
            user_id="user_456",
            conversation_history=[],
            user_preferences={}
        )
        
        # 调用方法
        result = await query_processor._enhance_query(analysis, context)
        
        # 验证结果
        assert isinstance(result, str)
        assert "北京" in result
        assert "天气" in result
        # 应该包含语义关键词
        assert any(keyword in result for keyword in ["天气预报", "气象"])
    
    @pytest.mark.asyncio
    async def test_determine_search_strategies(self, query_processor):
        """测试搜索策略确定"""
        # 准备测试数据
        analysis = QueryAnalysis(
            original_query="如何解决网络连接问题",
            normalized_query="如何 解决 网络 连接 问题",
            query_type=QueryType.PROCEDURAL,
            query_complexity=QueryComplexity.MODERATE,
            query_intent=QueryIntent.TROUBLESHOOT,
            entities=[],
            keywords=["网络", "连接", "问题"],
            semantic_keywords=["网络故障", "连接问题"],
            confidence=0.8
        )
        
        context = QueryContext(
            session_id="sess_123",
            user_id="user_456",
            conversation_history=[],
            user_preferences={}
        )
        
        # 调用方法
        result = await query_processor._determine_search_strategies(analysis, context)
        
        # 验证结果
        assert isinstance(result, list)
        assert len(result) > 0
        # 程序性查询应该包含特定的搜索策略
        assert any("procedural" in strategy or "step" in strategy for strategy in result)
    
    @pytest.mark.asyncio
    async def test_extract_filters(self, query_processor):
        """测试过滤器提取"""
        # 准备测试数据
        analysis = QueryAnalysis(
            original_query="2023年北京的GDP数据",
            normalized_query="2023年 北京 GDP 数据",
            query_type=QueryType.FACTUAL,
            query_complexity=QueryComplexity.SIMPLE,
            query_intent=QueryIntent.SEARCH,
            entities=[
                QueryEntity("北京", "location", 0.9, 4, 6),
                QueryEntity("2023年", "time", 0.8, 0, 4)
            ],
            keywords=["2023年", "北京", "GDP"],
            semantic_keywords=["经济数据"],
            confidence=0.9
        )
        
        context = QueryContext(
            session_id="sess_123",
            user_id="user_456",
            conversation_history=[],
            user_preferences={}
        )
        
        # 调用方法
        result = await query_processor._extract_filters(analysis, context)
        
        # 验证结果
        assert isinstance(result, dict)
        # 应该包含地理位置过滤器
        assert "location" in result or "地点" in result
        # 应该包含时间过滤器
        assert "time" in result or "时间" in result or "year" in result
    
    @pytest.mark.asyncio
    async def test_identify_boost_terms(self, query_processor):
        """测试增强词识别"""
        # 准备测试数据
        analysis = QueryAnalysis(
            original_query="机器学习算法比较",
            normalized_query="机器学习 算法 比较",
            query_type=QueryType.COMPARATIVE,
            query_complexity=QueryComplexity.MODERATE,
            query_intent=QueryIntent.COMPARE,
            entities=[],
            keywords=["机器学习", "算法", "比较"],
            semantic_keywords=["人工智能", "算法对比"],
            confidence=0.85
        )
        
        context = QueryContext(
            session_id="sess_123",
            user_id="user_456",
            conversation_history=[],
            user_preferences={}
        )
        
        # 调用方法
        result = await query_processor._identify_boost_terms(analysis, context)
        
        # 验证结果
        assert isinstance(result, list)
        assert len(result) > 0
        # 应该包含关键词
        assert any(term in result for term in ["机器学习", "算法", "比较"])
    
    @pytest.mark.asyncio
    async def test_get_context_terms(self, query_processor):
        """测试上下文词获取"""
        # 准备测试数据
        analysis = QueryAnalysis(
            original_query="Python编程入门",
            normalized_query="Python 编程 入门",
            query_type=QueryType.PROCEDURAL,
            query_complexity=QueryComplexity.SIMPLE,
            query_intent=QueryIntent.INSTRUCT,
            entities=[],
            keywords=["Python", "编程", "入门"],
            semantic_keywords=["编程语言", "程序设计"],
            confidence=0.9
        )
        
        context = QueryContext(
            session_id="sess_123",
            user_id="user_456",
            conversation_history=[
                {"user_input": "我想学习编程", "response": "建议从Python开始"}
            ],
            user_preferences={"skill_level": "beginner"}
        )
        
        # 调用方法
        result = await query_processor._get_context_terms(analysis, context)
        
        # 验证结果
        assert isinstance(result, list)
        # 应该包含上下文相关的词
        assert any("编程" in term or "Python" in term for term in result)
    
    @pytest.mark.asyncio
    async def test_determine_answer_type(self, query_processor):
        """测试答案类型确定"""
        # 准备测试数据
        analysis = QueryAnalysis(
            original_query="北京天气预报",
            normalized_query="北京 天气 预报",
            query_type=QueryType.FACTUAL,
            query_complexity=QueryComplexity.SIMPLE,
            query_intent=QueryIntent.SEARCH,
            entities=[QueryEntity("北京", "location", 0.9, 0, 2)],
            keywords=["北京", "天气", "预报"],
            semantic_keywords=["气象信息"],
            confidence=0.9
        )
        
        context = QueryContext(
            session_id="sess_123",
            user_id="user_456",
            conversation_history=[],
            user_preferences={}
        )
        
        # 调用方法
        result = await query_processor._determine_answer_type(analysis, context)
        
        # 验证结果
        assert isinstance(result, str)
        assert "weather" in result.lower() or "天气" in result
    
    @pytest.mark.asyncio
    async def test_determine_routing(self, query_processor):
        """测试路由确定"""
        # 准备测试数据
        analysis = QueryAnalysis(
            original_query="公司财务报表分析",
            normalized_query="公司 财务 报表 分析",
            query_type=QueryType.PROCEDURAL,
            query_complexity=QueryComplexity.MODERATE,
            query_intent=QueryIntent.EXPLAIN,
            entities=[],
            keywords=["公司", "财务", "报表", "分析"],
            semantic_keywords=["财务分析", "会计报表"],
            confidence=0.8
        )
        
        context = QueryContext(
            session_id="sess_123",
            user_id="user_456",
            conversation_history=[],
            user_preferences={}
        )
        
        # 调用方法
        result = await query_processor._determine_routing(analysis, context)
        
        # 验证结果
        assert isinstance(result, str)
        assert "finance" in result.lower() or "财务" in result or "business" in result.lower()
    
    @pytest.mark.asyncio
    async def test_error_handling(self, query_processor, mock_cache_service):
        """测试错误处理"""
        # 准备测试数据
        query = "测试查询"
        context = QueryContext(
            session_id="sess_123",
            user_id="user_456",
            conversation_history=[],
            user_preferences={}
        )
        
        # 设置模拟行为 - 分析查询时抛出异常
        with patch.object(query_processor, '_analyze_query', side_effect=Exception("Analysis error")):
            
            # 调用方法 - 应该处理异常并返回基本结果
            result = await query_processor.process_query(query, context)
            
            # 验证结果
            assert isinstance(result, ProcessedQuery)
            assert result.original_query == query
            # 错误情况下应该有基本的处理结果
            assert result.enhanced_query is not None
            assert result.search_strategies is not None
    
    @pytest.mark.asyncio
    async def test_generate_cache_key(self, query_processor):
        """测试缓存键生成"""
        # 准备测试数据
        query = "北京天气怎么样"
        context = QueryContext(
            session_id="sess_123",
            user_id="user_456",
            conversation_history=[],
            user_preferences={}
        )
        
        # 调用方法
        result = query_processor._generate_cache_key(query, context)
        
        # 验证结果
        assert isinstance(result, str)
        assert len(result) > 0
        # 相同输入应该产生相同的缓存键
        result2 = query_processor._generate_cache_key(query, context)
        assert result == result2
    
    @pytest.mark.asyncio
    async def test_serialize_and_deserialize(self, query_processor):
        """测试序列化和反序列化"""
        # 准备测试数据
        analysis = QueryAnalysis(
            original_query="测试查询",
            normalized_query="测试 查询",
            query_type=QueryType.FACTUAL,
            query_complexity=QueryComplexity.SIMPLE,
            query_intent=QueryIntent.SEARCH,
            entities=[],
            keywords=["测试", "查询"],
            semantic_keywords=["测试关键词"],
            confidence=0.8
        )
        
        processed_query = ProcessedQuery(
            original_query="测试查询",
            enhanced_query="测试 查询 关键词",
            analysis=analysis,
            search_strategies=["semantic_search"],
            filters={"type": "test"},
            boost_terms=["测试"],
            context_terms=["查询"],
            expected_answer_type="test_result",
            routing_config="test_kb"
        )
        
        # 序列化
        serialized = query_processor._serialize_processed_query(processed_query)
        
        # 验证序列化结果
        assert isinstance(serialized, dict)
        assert serialized["original_query"] == "测试查询"
        
        # 反序列化
        deserialized = query_processor._deserialize_processed_query(serialized)
        
        # 验证反序列化结果
        assert isinstance(deserialized, ProcessedQuery)
        assert deserialized.original_query == "测试查询"
        assert deserialized.enhanced_query == "测试 查询 关键词"
        assert deserialized.search_strategies == ["semantic_search"]