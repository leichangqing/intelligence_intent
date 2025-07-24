"""
智能化知识库查询处理器 (TASK-031)
实现高级查询处理逻辑，包括语义分析、上下文感知、查询优化等功能
"""
from typing import Dict, List, Optional, Any, Tuple, Union
import re
import asyncio
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime, timedelta
import jieba
import jieba.posseg as pseg
from collections import defaultdict
import hashlib
import json

from src.services.cache_service import CacheService
from src.services.synonym_service import get_synonym_service_sync
from src.utils.logger import get_logger

logger = get_logger(__name__)


class QueryType(Enum):
    """查询类型枚举"""
    FACTUAL = "factual"           # 事实性查询
    PROCEDURAL = "procedural"     # 程序性查询
    CONCEPTUAL = "conceptual"     # 概念性查询
    COMPARATIVE = "comparative"   # 比较性查询
    CAUSAL = "causal"            # 因果关系查询
    TEMPORAL = "temporal"        # 时间相关查询
    SPATIAL = "spatial"          # 空间相关查询
    PERSONAL = "personal"        # 个人化查询


class QueryComplexity(Enum):
    """查询复杂度枚举"""
    SIMPLE = "simple"
    MODERATE = "moderate"
    COMPLEX = "complex"
    VERY_COMPLEX = "very_complex"


class QueryIntent(Enum):
    """查询意图枚举"""
    SEARCH = "search"            # 搜索信息
    COMPARE = "compare"          # 比较对比
    EXPLAIN = "explain"          # 解释说明
    INSTRUCT = "instruct"        # 指导说明
    RECOMMEND = "recommend"      # 推荐建议
    TROUBLESHOOT = "troubleshoot"  # 故障排除


@dataclass
class QueryEntity:
    """查询实体"""
    text: str
    entity_type: str
    confidence: float
    start_pos: int
    end_pos: int
    synonyms: List[str] = field(default_factory=list)
    related_terms: List[str] = field(default_factory=list)


@dataclass
class QueryAnalysis:
    """查询分析结果"""
    original_query: str
    normalized_query: str
    query_type: QueryType
    query_complexity: QueryComplexity
    query_intent: QueryIntent
    entities: List[QueryEntity]
    keywords: List[str]
    semantic_keywords: List[str]
    confidence: float
    language: str = "zh"
    domain: Optional[str] = None
    temporal_context: Optional[Dict] = None
    spatial_context: Optional[Dict] = None


@dataclass
class ProcessedQuery:
    """处理后的查询"""
    original_query: str
    enhanced_query: str
    analysis: QueryAnalysis
    search_strategies: List[str]
    filters: Dict[str, Any]
    boost_terms: List[str]
    context_terms: List[str]
    expected_answer_type: str
    routing_config: str
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class QueryContext:
    """查询上下文"""
    session_id: str
    user_id: str
    conversation_history: List[Dict[str, Any]]
    current_intent: Optional[str] = None
    current_slots: Dict[str, Any] = field(default_factory=dict)
    user_preferences: Dict[str, Any] = field(default_factory=dict)
    domain_context: Optional[str] = None
    temporal_context: Optional[Dict] = None
    previous_queries: List[str] = field(default_factory=list)
    query_pattern: Optional[str] = None


class QueryNormalizer:
    """查询规范化器"""
    
    def __init__(self):
        # 尝试从同义词服务获取数据，如果失败则使用默认数据
        self.synonym_service = get_synonym_service_sync()
        if self.synonym_service:
            self.stop_words = self.synonym_service.get_stop_words()
            self.synonym_dict = self.synonym_service.get_reverse_synonym_dict()
            self.entity_patterns = self.synonym_service.get_entity_patterns()
        else:
            # 如果同义词服务未初始化，使用默认数据
            logger.warning("同义词服务未初始化，使用默认数据")
            self.stop_words = self._load_stop_words()
            self.synonym_dict = self._load_synonym_dict()
            self.entity_patterns = self._load_entity_patterns()
    
    def _load_stop_words(self) -> set:
        """加载停用词"""
        # 基础停用词集合
        return {
            "的", "了", "在", "是", "有", "和", "就", "不", "人", "都", "一", "个", "上", "也", "很", "到", "说", "要", "去", "你", "会", "着", "没有", "看", "好", "自己", "这", "那", "些", "什么", "怎么", "为什么", "吗", "呢", "吧", "啊", "哦", "哪", "那么", "这么", "可以", "能够", "应该", "需要", "想要", "希望", "帮助", "告诉", "知道", "了解", "明白", "清楚"
        }
    
    def _load_synonym_dict(self) -> Dict[str, List[str]]:
        """加载同义词词典"""
        return {
            "如何": ["怎样", "怎么", "如何才能", "怎么样"],
            "查询": ["查看", "搜索", "寻找", "找到", "获取"],
            "购买": ["买", "购入", "采购", "订购"],
            "账户": ["账号", "帐户", "用户", "个人"],
            "余额": ["余额", "结余", "剩余", "可用金额"],
            "银行卡": ["储蓄卡", "借记卡", "信用卡", "卡片"],
            "机票": ["飞机票", "航班", "班机", "机位"],
            "预订": ["预约", "订购", "预定", "订票"],
            "取消": ["撤销", "退订", "作废", "终止"],
            "修改": ["更改", "变更", "调整", "编辑"],
            "问题": ["故障", "错误", "异常", "困难"],
            "帮助": ["协助", "支持", "指导", "援助"]
        }
    
    def _load_entity_patterns(self) -> Dict[str, str]:
        """加载实体识别模式"""
        return {
            "phone": r"1[3-9]\d{9}",
            "email": r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}",
            "id_card": r"\d{15}|\d{18}",
            "bank_card": r"\d{16,19}",
            "amount": r"[0-9,]+(?:\.[0-9]+)?(?:元|块|万|千|百)?",
            "date": r"\d{4}[-/年]\d{1,2}[-/月]\d{1,2}[日号]?",
            "time": r"\d{1,2}[:|：]\d{1,2}",
            "flight": r"[A-Z]{2}\d{3,4}",
            "airport": r"[A-Z]{3}",
            "city": r"[北京|上海|广州|深圳|杭州|南京|武汉|成都|西安|重庆|天津|青岛|大连|厦门|苏州|无锡|宁波|长沙|郑州|济南|哈尔滨|沈阳|长春|石家庄|太原|呼和浩特|兰州|西宁|银川|乌鲁木齐|拉萨|昆明|贵阳|南宁|海口|三亚|福州|南昌|合肥]+"
        }
    
    async def normalize_query(self, query: str) -> Tuple[str, List[QueryEntity]]:
        """规范化查询"""
        try:
            # 1. 基本清理
            cleaned_query = self._clean_query(query)
            
            # 2. 实体识别
            entities = self._extract_entities(cleaned_query)
            
            # 3. 同义词替换
            normalized_query = self._replace_synonyms(cleaned_query)
            
            # 4. 停用词处理（保留在原始查询中，但标记）
            normalized_query = self._process_stop_words(normalized_query)
            
            # 5. 语言规范化
            normalized_query = self._normalize_language(normalized_query)
            
            logger.debug(f"查询规范化: {query} -> {normalized_query}")
            
            return normalized_query, entities
            
        except Exception as e:
            logger.error(f"查询规范化失败: {str(e)}")
            return query, []
    
    def _clean_query(self, query: str) -> str:
        """清理查询"""
        # 移除多余空格
        query = re.sub(r'\s+', ' ', query.strip())
        
        # 移除特殊字符但保留标点
        query = re.sub(r'[^\w\s\u4e00-\u9fff.,!?;:()《》""''【】]', '', query)
        
        # 统一标点符号
        query = query.replace('？', '?').replace('！', '!').replace('，', ',').replace('。', '.')
        
        return query
    
    def _extract_entities(self, query: str) -> List[QueryEntity]:
        """提取实体"""
        entities = []
        
        for entity_type, pattern in self.entity_patterns.items():
            matches = re.finditer(pattern, query)
            for match in matches:
                entity = QueryEntity(
                    text=match.group(),
                    entity_type=entity_type,
                    confidence=0.8,
                    start_pos=match.start(),
                    end_pos=match.end()
                )
                entities.append(entity)
        
        return entities
    
    def _replace_synonyms(self, query: str) -> str:
        """同义词替换"""
        if self.synonym_service:
            # 使用同义词服务进行替换
            return self.synonym_service.replace_synonyms(query)
        else:
            # fallback到传统方式
            for standard_term, synonyms in self.synonym_dict.items():
                for synonym in synonyms:
                    query = query.replace(synonym, standard_term)
            return query
    
    def _process_stop_words(self, query: str) -> str:
        """处理停用词"""
        # 分词
        words = list(jieba.cut(query))
        
        # 过滤停用词，但保留重要的疑问词
        important_words = {"什么", "怎么", "如何", "为什么", "哪里", "什么时候", "多少", "哪个", "谁"}
        
        filtered_words = []
        for word in words:
            if word not in self.stop_words or word in important_words:
                filtered_words.append(word)
        
        return ' '.join(filtered_words)
    
    def _normalize_language(self, query: str) -> str:
        """语言规范化"""
        # 统一大小写
        query = query.lower()
        
        # 处理重复字符
        query = re.sub(r'(.)\1{2,}', r'\1\1', query)
        
        return query


class QueryAnalyzer:
    """查询分析器"""
    
    def __init__(self):
        self.query_type_patterns = self._load_query_type_patterns()
        self.complexity_indicators = self._load_complexity_indicators()
        self.intent_patterns = self._load_intent_patterns()
        self.domain_keywords = self._load_domain_keywords()
    
    def _load_query_type_patterns(self) -> Dict[QueryType, List[str]]:
        """加载查询类型模式"""
        return {
            QueryType.FACTUAL: ["什么是", "谁是", "哪里", "什么时候", "多少", "几个"],
            QueryType.PROCEDURAL: ["如何", "怎样", "怎么", "步骤", "方法", "流程"],
            QueryType.CONCEPTUAL: ["原理", "概念", "定义", "含义", "意思", "理解"],
            QueryType.COMPARATIVE: ["比较", "对比", "区别", "差异", "优缺点", "哪个好"],
            QueryType.CAUSAL: ["为什么", "原因", "导致", "因为", "结果", "影响"],
            QueryType.TEMPORAL: ["什么时候", "时间", "日期", "期限", "截止", "开始"],
            QueryType.SPATIAL: ["哪里", "位置", "地址", "方向", "距离", "附近"],
            QueryType.PERSONAL: ["我的", "个人", "账户", "信息", "资料", "设置"]
        }
    
    def _load_complexity_indicators(self) -> Dict[str, int]:
        """加载复杂度指标"""
        return {
            "连词": 2,  # 并且、或者、但是
            "条件": 3,  # 如果、假如、当
            "比较": 2,  # 比较、对比
            "时间": 2,  # 时间相关
            "数量": 1,  # 数量词
            "疑问": 1,  # 疑问词
            "否定": 1,  # 否定词
            "多个实体": 2,  # 多个实体
            "嵌套": 3   # 嵌套结构
        }
    
    def _load_intent_patterns(self) -> Dict[QueryIntent, List[str]]:
        """加载意图模式"""
        return {
            QueryIntent.SEARCH: ["查询", "搜索", "寻找", "找到", "获取", "查看"],
            QueryIntent.COMPARE: ["比较", "对比", "哪个好", "区别", "差异"],
            QueryIntent.EXPLAIN: ["解释", "说明", "介绍", "什么是", "原理"],
            QueryIntent.INSTRUCT: ["如何", "怎样", "步骤", "方法", "教程"],
            QueryIntent.RECOMMEND: ["推荐", "建议", "选择", "哪个", "最好"],
            QueryIntent.TROUBLESHOOT: ["故障", "错误", "问题", "异常", "修复"]
        }
    
    def _load_domain_keywords(self) -> Dict[str, List[str]]:
        """加载领域关键词"""
        return {
            "banking": ["银行", "账户", "余额", "转账", "存款", "取款", "信用卡", "借记卡"],
            "travel": ["机票", "酒店", "预订", "航班", "旅游", "出行", "签证"],
            "shopping": ["购买", "商品", "订单", "支付", "退款", "物流", "配送"],
            "technical": ["技术", "系统", "软件", "硬件", "网络", "服务器", "数据库"],
            "customer_service": ["客服", "投诉", "建议", "反馈", "咨询", "帮助"],
            "finance": ["理财", "投资", "基金", "股票", "保险", "贷款", "财务"]
        }
    
    async def analyze_query(self, normalized_query: str, entities: List[QueryEntity]) -> QueryAnalysis:
        """分析查询"""
        try:
            # 1. 查询类型识别
            query_type = self._identify_query_type(normalized_query)
            
            # 2. 复杂度分析
            complexity = self._analyze_complexity(normalized_query, entities)
            
            # 3. 意图识别
            intent = self._identify_intent(normalized_query)
            
            # 4. 关键词提取
            keywords = self._extract_keywords(normalized_query)
            
            # 5. 语义关键词扩展
            semantic_keywords = self._expand_semantic_keywords(keywords)
            
            # 6. 领域识别
            domain = self._identify_domain(normalized_query, keywords)
            
            # 7. 时空上下文分析
            temporal_context = self._analyze_temporal_context(normalized_query, entities)
            spatial_context = self._analyze_spatial_context(normalized_query, entities)
            
            # 8. 置信度计算
            confidence = self._calculate_analysis_confidence(
                query_type, complexity, intent, len(keywords), len(entities)
            )
            
            analysis = QueryAnalysis(
                original_query=normalized_query,
                normalized_query=normalized_query,
                query_type=query_type,
                query_complexity=complexity,
                query_intent=intent,
                entities=entities,
                keywords=keywords,
                semantic_keywords=semantic_keywords,
                confidence=confidence,
                domain=domain,
                temporal_context=temporal_context,
                spatial_context=spatial_context
            )
            
            logger.debug(f"查询分析完成: {analysis.query_type}, {analysis.query_intent}, 置信度: {confidence:.3f}")
            
            return analysis
            
        except Exception as e:
            logger.error(f"查询分析失败: {str(e)}")
            # 返回默认分析结果
            return QueryAnalysis(
                original_query=normalized_query,
                normalized_query=normalized_query,
                query_type=QueryType.FACTUAL,
                query_complexity=QueryComplexity.SIMPLE,
                query_intent=QueryIntent.SEARCH,
                entities=entities,
                keywords=[],
                semantic_keywords=[],
                confidence=0.5
            )
    
    def _identify_query_type(self, query: str) -> QueryType:
        """识别查询类型"""
        scores = {}
        
        for query_type, patterns in self.query_type_patterns.items():
            score = 0
            for pattern in patterns:
                if pattern in query:
                    score += 1
            scores[query_type] = score
        
        # 返回得分最高的类型
        if scores:
            return max(scores, key=scores.get)
        
        return QueryType.FACTUAL
    
    def _analyze_complexity(self, query: str, entities: List[QueryEntity]) -> QueryComplexity:
        """分析查询复杂度"""
        complexity_score = 0
        
        # 基于长度
        if len(query) > 50:
            complexity_score += 2
        elif len(query) > 20:
            complexity_score += 1
        
        # 基于实体数量
        complexity_score += len(entities)
        
        # 基于复杂度指标
        for indicator, score in self.complexity_indicators.items():
            if indicator in query:
                complexity_score += score
        
        # 基于分词数量
        words = list(jieba.cut(query))
        if len(words) > 10:
            complexity_score += 2
        elif len(words) > 5:
            complexity_score += 1
        
        # 映射到复杂度等级
        if complexity_score >= 8:
            return QueryComplexity.VERY_COMPLEX
        elif complexity_score >= 5:
            return QueryComplexity.COMPLEX
        elif complexity_score >= 2:
            return QueryComplexity.MODERATE
        else:
            return QueryComplexity.SIMPLE
    
    def _identify_intent(self, query: str) -> QueryIntent:
        """识别查询意图"""
        scores = {}
        
        for intent, patterns in self.intent_patterns.items():
            score = 0
            for pattern in patterns:
                if pattern in query:
                    score += 1
            scores[intent] = score
        
        if scores:
            return max(scores, key=scores.get)
        
        return QueryIntent.SEARCH
    
    def _extract_keywords(self, query: str) -> List[str]:
        """提取关键词"""
        # 使用jieba进行分词和词性标注
        words = pseg.cut(query)
        
        keywords = []
        for word, flag in words:
            # 只保留名词、动词、形容词等实义词
            if flag in ['n', 'v', 'a', 'nr', 'ns', 'nt', 'nz', 'vn', 'an']:
                if len(word) > 1:  # 过滤单字词
                    keywords.append(word)
        
        return keywords
    
    def _expand_semantic_keywords(self, keywords: List[str]) -> List[str]:
        """扩展语义关键词"""
        expanded = set(keywords)
        
        # 简单的语义扩展（实际应用中可以使用词向量模型）
        semantic_rules = {
            "银行": ["金融", "银行卡", "账户", "存款"],
            "机票": ["航班", "飞机", "预订", "旅行"],
            "购买": ["下单", "支付", "订购", "采购"],
            "查询": ["搜索", "寻找", "获取", "检索"],
            "问题": ["故障", "错误", "困难", "异常"],
            "帮助": ["支持", "协助", "指导", "服务"]
        }
        
        for keyword in keywords:
            if keyword in semantic_rules:
                expanded.update(semantic_rules[keyword])
        
        return list(expanded)
    
    def _identify_domain(self, query: str, keywords: List[str]) -> Optional[str]:
        """识别领域"""
        domain_scores = {}
        
        for domain, domain_keywords in self.domain_keywords.items():
            score = 0
            for keyword in domain_keywords:
                if keyword in query:
                    score += 1
            
            # 也检查提取的关键词
            for keyword in keywords:
                if keyword in domain_keywords:
                    score += 1
            
            domain_scores[domain] = score
        
        if domain_scores:
            max_score = max(domain_scores.values())
            if max_score > 0:
                return max(domain_scores, key=domain_scores.get)
        
        return None
    
    def _analyze_temporal_context(self, query: str, entities: List[QueryEntity]) -> Optional[Dict]:
        """分析时间上下文"""
        temporal_entities = [e for e in entities if e.entity_type in ['date', 'time']]
        
        if temporal_entities:
            return {
                'has_temporal': True,
                'temporal_entities': [e.text for e in temporal_entities],
                'temporal_type': 'explicit'
            }
        
        # 检查隐式时间表达
        temporal_keywords = ["今天", "明天", "昨天", "现在", "最近", "以前", "将来", "当前"]
        found_temporal = [kw for kw in temporal_keywords if kw in query]
        
        if found_temporal:
            return {
                'has_temporal': True,
                'temporal_keywords': found_temporal,
                'temporal_type': 'implicit'
            }
        
        return None
    
    def _analyze_spatial_context(self, query: str, entities: List[QueryEntity]) -> Optional[Dict]:
        """分析空间上下文"""
        spatial_entities = [e for e in entities if e.entity_type in ['city', 'airport']]
        
        if spatial_entities:
            return {
                'has_spatial': True,
                'spatial_entities': [e.text for e in spatial_entities],
                'spatial_type': 'explicit'
            }
        
        # 检查隐式空间表达
        spatial_keywords = ["这里", "那里", "附近", "周围", "本地", "远程", "当地"]
        found_spatial = [kw for kw in spatial_keywords if kw in query]
        
        if found_spatial:
            return {
                'has_spatial': True,
                'spatial_keywords': found_spatial,
                'spatial_type': 'implicit'
            }
        
        return None
    
    def _calculate_analysis_confidence(self, query_type: QueryType, complexity: QueryComplexity,
                                     intent: QueryIntent, keyword_count: int, entity_count: int) -> float:
        """计算分析置信度"""
        confidence = 0.5  # 基础置信度
        
        # 基于关键词数量
        if keyword_count > 0:
            confidence += min(0.2, keyword_count * 0.05)
        
        # 基于实体数量
        if entity_count > 0:
            confidence += min(0.15, entity_count * 0.05)
        
        # 基于复杂度（适中复杂度置信度更高）
        if complexity == QueryComplexity.MODERATE:
            confidence += 0.1
        elif complexity == QueryComplexity.SIMPLE:
            confidence += 0.05
        
        # 基于查询类型的确定性
        type_confidence = {
            QueryType.FACTUAL: 0.05,
            QueryType.PROCEDURAL: 0.1,
            QueryType.CONCEPTUAL: 0.08,
            QueryType.COMPARATIVE: 0.12,
            QueryType.CAUSAL: 0.1,
            QueryType.TEMPORAL: 0.08,
            QueryType.SPATIAL: 0.08,
            QueryType.PERSONAL: 0.15
        }
        confidence += type_confidence.get(query_type, 0.05)
        
        return min(1.0, confidence)


class ContextAwareQueryEnhancer:
    """上下文感知查询增强器"""
    
    def __init__(self, cache_service: CacheService):
        self.cache_service = cache_service
        self.cache_namespace = "query_context"
    
    async def enhance_query(self, query: str, analysis: QueryAnalysis, 
                          context: QueryContext) -> ProcessedQuery:
        """增强查询"""
        try:
            # 1. 上下文分析
            context_analysis = await self._analyze_context(context)
            
            # 2. 查询增强
            enhanced_query = await self._enhance_with_context(query, analysis, context_analysis)
            
            # 3. 搜索策略选择
            search_strategies = self._select_search_strategies(analysis, context_analysis)
            
            # 4. 过滤器生成
            filters = self._generate_filters(analysis, context_analysis)
            
            # 5. 提升词生成
            boost_terms = self._generate_boost_terms(analysis, context_analysis)
            
            # 6. 上下文词提取
            context_terms = self._extract_context_terms(context_analysis)
            
            # 7. 答案类型预测
            expected_answer_type = self._predict_answer_type(analysis)
            
            # 8. 配置路由
            routing_config = self._select_routing_config(analysis, context_analysis)
            
            processed_query = ProcessedQuery(
                original_query=query,
                enhanced_query=enhanced_query,
                analysis=analysis,
                search_strategies=search_strategies,
                filters=filters,
                boost_terms=boost_terms,
                context_terms=context_terms,
                expected_answer_type=expected_answer_type,
                routing_config=routing_config,
                metadata={
                    'context_analysis': context_analysis,
                    'enhancement_timestamp': datetime.now().isoformat()
                }
            )
            
            # 缓存增强结果
            await self._cache_enhancement_result(processed_query)
            
            logger.info(f"查询增强完成: {query} -> {enhanced_query}")
            
            return processed_query
            
        except Exception as e:
            logger.error(f"查询增强失败: {str(e)}")
            # 返回最小增强结果
            return ProcessedQuery(
                original_query=query,
                enhanced_query=query,
                analysis=analysis,
                search_strategies=["basic"],
                filters={},
                boost_terms=[],
                context_terms=[],
                expected_answer_type="text",
                routing_config="default"
            )
    
    async def _analyze_context(self, context: QueryContext) -> Dict[str, Any]:
        """分析上下文"""
        analysis = {
            'session_patterns': await self._analyze_session_patterns(context),
            'conversation_flow': self._analyze_conversation_flow(context),
            'user_intent_history': self._analyze_user_intent_history(context),
            'temporal_patterns': self._analyze_temporal_patterns(context),
            'domain_preference': self._analyze_domain_preference(context),
            'query_evolution': self._analyze_query_evolution(context)
        }
        
        return analysis
    
    async def _analyze_session_patterns(self, context: QueryContext) -> Dict[str, Any]:
        """分析会话模式"""
        cache_key = f"session_patterns:{context.session_id}"
        
        # 尝试从缓存获取
        cached_patterns = await self.cache_service.get(cache_key, namespace=self.cache_namespace)
        if cached_patterns:
            return cached_patterns
        
        # 分析会话模式
        patterns = {
            'query_count': len(context.previous_queries),
            'avg_query_length': sum(len(q) for q in context.previous_queries) / max(1, len(context.previous_queries)),
            'query_frequency': len(context.previous_queries) / max(1, len(context.conversation_history)),
            'domain_switches': self._count_domain_switches(context),
            'complexity_trend': self._analyze_complexity_trend(context)
        }
        
        # 缓存结果
        await self.cache_service.set(cache_key, patterns, ttl=3600, namespace=self.cache_namespace)
        
        return patterns
    
    def _analyze_conversation_flow(self, context: QueryContext) -> Dict[str, Any]:
        """分析对话流程"""
        if not context.conversation_history:
            return {'flow_type': 'initial', 'context_relevance': 0.0}
        
        # 分析最近的对话
        recent_messages = context.conversation_history[-5:]
        
        # 判断对话类型
        flow_type = 'continuation'
        if len(recent_messages) == 1:
            flow_type = 'initial'
        elif any('问题' in msg.get('content', '') for msg in recent_messages):
            flow_type = 'problem_solving'
        elif any('比较' in msg.get('content', '') for msg in recent_messages):
            flow_type = 'comparison'
        
        # 计算上下文相关性
        context_relevance = self._calculate_context_relevance(context)
        
        return {
            'flow_type': flow_type,
            'context_relevance': context_relevance,
            'message_count': len(recent_messages),
            'last_message_type': recent_messages[-1].get('role', 'unknown') if recent_messages else 'none'
        }
    
    def _analyze_user_intent_history(self, context: QueryContext) -> Dict[str, Any]:
        """分析用户意图历史"""
        intent_history = []
        
        # 从对话历史中提取意图
        for message in context.conversation_history:
            if message.get('role') == 'user':
                content = message.get('content', '')
                # 简单的意图识别
                if '查询' in content or '查看' in content:
                    intent_history.append('search')
                elif '比较' in content:
                    intent_history.append('compare')
                elif '如何' in content or '怎么' in content:
                    intent_history.append('instruct')
                elif '推荐' in content:
                    intent_history.append('recommend')
                else:
                    intent_history.append('general')
        
        return {
            'intent_sequence': intent_history,
            'dominant_intent': max(set(intent_history), key=intent_history.count) if intent_history else 'general',
            'intent_diversity': len(set(intent_history)) / max(1, len(intent_history)),
            'recent_intent': intent_history[-1] if intent_history else 'general'
        }
    
    def _analyze_temporal_patterns(self, context: QueryContext) -> Dict[str, Any]:
        """分析时间模式"""
        now = datetime.now()
        
        # 分析查询时间模式
        patterns = {
            'session_duration': self._calculate_session_duration(context),
            'query_interval': self._calculate_query_interval(context),
            'time_of_day': now.hour,
            'is_business_hours': 9 <= now.hour <= 17,
            'temporal_urgency': self._assess_temporal_urgency(context)
        }
        
        return patterns
    
    def _analyze_domain_preference(self, context: QueryContext) -> Dict[str, Any]:
        """分析领域偏好"""
        domain_mentions = defaultdict(int)
        
        # 分析历史查询中的领域
        for query in context.previous_queries:
            if '银行' in query or '账户' in query:
                domain_mentions['banking'] += 1
            elif '机票' in query or '航班' in query:
                domain_mentions['travel'] += 1
            elif '购买' in query or '商品' in query:
                domain_mentions['shopping'] += 1
            elif '技术' in query or '系统' in query:
                domain_mentions['technical'] += 1
        
        # 从用户偏好中获取
        user_preferences = context.user_preferences
        preferred_domains = user_preferences.get('preferred_domains', [])
        
        return {
            'historical_domains': dict(domain_mentions),
            'preferred_domains': preferred_domains,
            'current_domain': context.domain_context,
            'domain_stability': self._calculate_domain_stability(context)
        }
    
    def _analyze_query_evolution(self, context: QueryContext) -> Dict[str, Any]:
        """分析查询演化"""
        if len(context.previous_queries) < 2:
            return {'evolution_type': 'initial', 'refinement_level': 0}
        
        # 分析查询演化模式
        evolution_patterns = {
            'refinement': self._detect_query_refinement(context),
            'expansion': self._detect_query_expansion(context),
            'pivot': self._detect_query_pivot(context),
            'repetition': self._detect_query_repetition(context)
        }
        
        # 确定主要演化类型
        main_evolution = max(evolution_patterns, key=evolution_patterns.get)
        
        return {
            'evolution_type': main_evolution,
            'refinement_level': evolution_patterns['refinement'],
            'expansion_level': evolution_patterns['expansion'],
            'patterns': evolution_patterns
        }
    
    async def _enhance_with_context(self, query: str, analysis: QueryAnalysis, 
                                  context_analysis: Dict[str, Any]) -> str:
        """使用上下文增强查询"""
        enhanced_query = query
        
        # 1. 基于会话历史的增强
        if context_analysis['conversation_flow']['context_relevance'] > 0.7:
            enhanced_query = self._add_context_continuity(enhanced_query, context_analysis)
        
        # 2. 基于领域偏好的增强
        domain_preference = context_analysis['domain_preference']
        if domain_preference['current_domain']:
            enhanced_query = self._add_domain_context(enhanced_query, domain_preference['current_domain'])
        
        # 3. 基于时间模式的增强
        temporal_patterns = context_analysis['temporal_patterns']
        if temporal_patterns['temporal_urgency'] > 0.7:
            enhanced_query = self._add_urgency_context(enhanced_query)
        
        # 4. 基于查询演化的增强
        query_evolution = context_analysis['query_evolution']
        if query_evolution['evolution_type'] == 'refinement':
            enhanced_query = self._add_refinement_context(enhanced_query, query_evolution)
        
        return enhanced_query
    
    def _select_search_strategies(self, analysis: QueryAnalysis, context_analysis: Dict[str, Any]) -> List[str]:
        """选择搜索策略"""
        strategies = ['basic']
        
        # 基于查询复杂度
        if analysis.query_complexity in [QueryComplexity.COMPLEX, QueryComplexity.VERY_COMPLEX]:
            strategies.append('multi_step')
        
        # 基于查询类型
        if analysis.query_type == QueryType.COMPARATIVE:
            strategies.append('comparative')
        elif analysis.query_type == QueryType.PROCEDURAL:
            strategies.append('step_by_step')
        
        # 基于上下文
        if context_analysis['conversation_flow']['context_relevance'] > 0.8:
            strategies.append('context_aware')
        
        # 基于领域
        if analysis.domain:
            strategies.append('domain_specific')
        
        return strategies
    
    def _generate_filters(self, analysis: QueryAnalysis, context_analysis: Dict[str, Any]) -> Dict[str, Any]:
        """生成过滤器"""
        filters = {}
        
        # 基于领域
        if analysis.domain:
            filters['domain'] = analysis.domain
        
        # 基于时间上下文
        if analysis.temporal_context:
            filters['temporal'] = analysis.temporal_context
        
        # 基于空间上下文
        if analysis.spatial_context:
            filters['spatial'] = analysis.spatial_context
        
        # 基于查询类型
        filters['query_type'] = analysis.query_type.value
        
        # 基于用户偏好
        domain_preference = context_analysis['domain_preference']
        if domain_preference['preferred_domains']:
            filters['preferred_domains'] = domain_preference['preferred_domains']
        
        return filters
    
    def _generate_boost_terms(self, analysis: QueryAnalysis, context_analysis: Dict[str, Any]) -> List[str]:
        """生成提升词"""
        boost_terms = []
        
        # 基于关键词
        boost_terms.extend(analysis.keywords)
        
        # 基于语义关键词
        boost_terms.extend(analysis.semantic_keywords[:5])  # 限制数量
        
        # 基于实体
        entity_texts = [e.text for e in analysis.entities]
        boost_terms.extend(entity_texts)
        
        # 基于领域偏好
        domain_preference = context_analysis['domain_preference']
        if domain_preference['current_domain']:
            boost_terms.append(domain_preference['current_domain'])
        
        return list(set(boost_terms))  # 去重
    
    def _extract_context_terms(self, context_analysis: Dict[str, Any]) -> List[str]:
        """提取上下文词"""
        context_terms = []
        
        # 从对话流程中提取
        flow_info = context_analysis['conversation_flow']
        if flow_info['flow_type'] != 'initial':
            context_terms.append(flow_info['flow_type'])
        
        # 从意图历史中提取
        intent_history = context_analysis['user_intent_history']
        if intent_history['dominant_intent'] != 'general':
            context_terms.append(intent_history['dominant_intent'])
        
        # 从领域偏好中提取
        domain_preference = context_analysis['domain_preference']
        context_terms.extend(domain_preference['preferred_domains'])
        
        return context_terms
    
    def _predict_answer_type(self, analysis: QueryAnalysis) -> str:
        """预测答案类型"""
        # 基于查询类型预测
        type_mapping = {
            QueryType.FACTUAL: "factual",
            QueryType.PROCEDURAL: "step_by_step",
            QueryType.CONCEPTUAL: "explanatory",
            QueryType.COMPARATIVE: "comparative",
            QueryType.CAUSAL: "causal",
            QueryType.TEMPORAL: "temporal",
            QueryType.SPATIAL: "spatial",
            QueryType.PERSONAL: "personal"
        }
        
        return type_mapping.get(analysis.query_type, "text")
    
    def _select_routing_config(self, analysis: QueryAnalysis, context_analysis: Dict[str, Any]) -> str:
        """选择路由配置"""
        # 基于领域选择配置
        if analysis.domain:
            domain_config_mapping = {
                'banking': 'financial',
                'travel': 'default',
                'shopping': 'default',
                'technical': 'technical',
                'customer_service': 'customer_service',
                'finance': 'financial'
            }
            return domain_config_mapping.get(analysis.domain, 'default')
        
        # 基于查询复杂度
        if analysis.query_complexity == QueryComplexity.VERY_COMPLEX:
            return 'technical'
        
        # 基于用户偏好
        domain_preference = context_analysis['domain_preference']
        if domain_preference['preferred_domains']:
            first_domain = domain_preference['preferred_domains'][0]
            if first_domain in ['banking', 'finance']:
                return 'financial'
            elif first_domain == 'technical':
                return 'technical'
        
        return 'default'
    
    # 辅助方法
    def _count_domain_switches(self, context: QueryContext) -> int:
        """计算领域切换次数"""
        domains = []
        for query in context.previous_queries:
            if '银行' in query:
                domains.append('banking')
            elif '机票' in query:
                domains.append('travel')
            elif '购买' in query:
                domains.append('shopping')
            else:
                domains.append('general')
        
        switches = 0
        for i in range(1, len(domains)):
            if domains[i] != domains[i-1]:
                switches += 1
        
        return switches
    
    def _analyze_complexity_trend(self, context: QueryContext) -> str:
        """分析复杂度趋势"""
        if len(context.previous_queries) < 2:
            return 'stable'
        
        # 简单的复杂度评估
        complexities = [len(q.split()) for q in context.previous_queries]
        
        if complexities[-1] > complexities[-2]:
            return 'increasing'
        elif complexities[-1] < complexities[-2]:
            return 'decreasing'
        else:
            return 'stable'
    
    def _calculate_context_relevance(self, context: QueryContext) -> float:
        """计算上下文相关性"""
        if not context.conversation_history:
            return 0.0
        
        # 简单的相关性计算
        recent_messages = context.conversation_history[-3:]
        if len(recent_messages) < 2:
            return 0.5
        
        # 检查消息之间的相关性
        relevance_score = 0.0
        for i in range(1, len(recent_messages)):
            current_content = recent_messages[i].get('content', '')
            previous_content = recent_messages[i-1].get('content', '')
            
            # 简单的关键词重叠检查
            current_words = set(current_content.split())
            previous_words = set(previous_content.split())
            
            if current_words & previous_words:
                relevance_score += 0.3
        
        return min(1.0, relevance_score)
    
    def _calculate_session_duration(self, context: QueryContext) -> float:
        """计算会话持续时间"""
        if not context.conversation_history:
            return 0.0
        
        # 假设有时间戳字段
        try:
            first_message = context.conversation_history[0]
            last_message = context.conversation_history[-1]
            
            # 这里应该使用实际的时间戳
            return len(context.conversation_history) * 2.0  # 简化计算
        except:
            return 0.0
    
    def _calculate_query_interval(self, context: QueryContext) -> float:
        """计算查询间隔"""
        if len(context.previous_queries) < 2:
            return 0.0
        
        # 简化计算
        return 60.0  # 假设平均间隔60秒
    
    def _assess_temporal_urgency(self, context: QueryContext) -> float:
        """评估时间紧迫性"""
        urgency_keywords = ["紧急", "立即", "马上", "现在", "急需", "赶紧"]
        
        urgency_score = 0.0
        for query in context.previous_queries:
            for keyword in urgency_keywords:
                if keyword in query:
                    urgency_score += 0.2
        
        return min(1.0, urgency_score)
    
    def _calculate_domain_stability(self, context: QueryContext) -> float:
        """计算领域稳定性"""
        if not context.previous_queries:
            return 1.0
        
        domain_switches = self._count_domain_switches(context)
        query_count = len(context.previous_queries)
        
        if query_count <= 1:
            return 1.0
        
        stability = 1.0 - (domain_switches / (query_count - 1))
        return max(0.0, stability)
    
    def _detect_query_refinement(self, context: QueryContext) -> float:
        """检测查询细化"""
        if len(context.previous_queries) < 2:
            return 0.0
        
        # 简单的细化检测
        recent_queries = context.previous_queries[-2:]
        current_words = set(recent_queries[-1].split())
        previous_words = set(recent_queries[-2].split())
        
        # 如果当前查询包含之前查询的词汇并且更长
        if (current_words & previous_words and 
            len(recent_queries[-1]) > len(recent_queries[-2])):
            return 0.8
        
        return 0.0
    
    def _detect_query_expansion(self, context: QueryContext) -> float:
        """检测查询扩展"""
        if len(context.previous_queries) < 2:
            return 0.0
        
        # 检测查询是否在扩展范围
        expansion_keywords = ["还有", "另外", "除了", "以及", "同时"]
        
        for query in context.previous_queries[-2:]:
            for keyword in expansion_keywords:
                if keyword in query:
                    return 0.7
        
        return 0.0
    
    def _detect_query_pivot(self, context: QueryContext) -> float:
        """检测查询转向"""
        if len(context.previous_queries) < 2:
            return 0.0
        
        # 检测主题转换
        pivot_keywords = ["不过", "但是", "另一方面", "换个问题", "其实"]
        
        for query in context.previous_queries[-2:]:
            for keyword in pivot_keywords:
                if keyword in query:
                    return 0.6
        
        return 0.0
    
    def _detect_query_repetition(self, context: QueryContext) -> float:
        """检测查询重复"""
        if len(context.previous_queries) < 2:
            return 0.0
        
        # 检测相似或重复的查询
        recent_queries = context.previous_queries[-2:]
        similarity = self._calculate_query_similarity(recent_queries[0], recent_queries[1])
        
        if similarity > 0.8:
            return 0.9
        
        return 0.0
    
    def _calculate_query_similarity(self, query1: str, query2: str) -> float:
        """计算查询相似性"""
        words1 = set(query1.split())
        words2 = set(query2.split())
        
        if not words1 or not words2:
            return 0.0
        
        intersection = words1 & words2
        union = words1 | words2
        
        return len(intersection) / len(union)
    
    def _add_context_continuity(self, query: str, context_analysis: Dict[str, Any]) -> str:
        """添加上下文连续性"""
        flow_type = context_analysis['conversation_flow']['flow_type']
        
        if flow_type == 'continuation':
            return f"继续之前的话题：{query}"
        elif flow_type == 'problem_solving':
            return f"关于之前的问题：{query}"
        
        return query
    
    def _add_domain_context(self, query: str, domain: str) -> str:
        """添加领域上下文"""
        domain_prefixes = {
            'banking': '关于银行业务：',
            'travel': '关于旅行服务：',
            'shopping': '关于购物：',
            'technical': '关于技术问题：',
            'customer_service': '关于客户服务：',
            'finance': '关于金融服务：'
        }
        
        prefix = domain_prefixes.get(domain, '')
        return f"{prefix}{query}" if prefix else query
    
    def _add_urgency_context(self, query: str) -> str:
        """添加紧急性上下文"""
        return f"紧急查询：{query}"
    
    def _add_refinement_context(self, query: str, evolution: Dict[str, Any]) -> str:
        """添加细化上下文"""
        if evolution['refinement_level'] > 0.5:
            return f"进一步了解：{query}"
        
        return query
    
    async def _cache_enhancement_result(self, processed_query: ProcessedQuery):
        """缓存增强结果"""
        try:
            cache_key = f"enhanced_query:{hashlib.md5(processed_query.original_query.encode()).hexdigest()}"
            
            cache_data = {
                'enhanced_query': processed_query.enhanced_query,
                'search_strategies': processed_query.search_strategies,
                'filters': processed_query.filters,
                'boost_terms': processed_query.boost_terms,
                'timestamp': datetime.now().isoformat()
            }
            
            await self.cache_service.set(cache_key, cache_data, ttl=1800, namespace=self.cache_namespace)
            
        except Exception as e:
            logger.warning(f"缓存增强结果失败: {str(e)}")


class IntelligentQueryProcessor:
    """智能查询处理器 - 主控制器"""
    
    def __init__(self, cache_service: CacheService):
        self.cache_service = cache_service
        self.normalizer = QueryNormalizer()
        self.analyzer = QueryAnalyzer()
        self.enhancer = ContextAwareQueryEnhancer(cache_service)
        
    async def process_query(self, query: str, context: QueryContext) -> ProcessedQuery:
        """处理查询 - 主入口方法"""
        try:
            logger.info(f"开始处理查询: {query}")
            
            # 1. 查询规范化
            normalized_query, entities = await self.normalizer.normalize_query(query)
            
            # 2. 查询分析
            analysis = await self.analyzer.analyze_query(normalized_query, entities)
            
            # 3. 上下文增强
            processed_query = await self.enhancer.enhance_query(query, analysis, context)
            
            logger.info(f"查询处理完成: {query} -> {processed_query.enhanced_query}")
            
            return processed_query
            
        except Exception as e:
            logger.error(f"查询处理失败: {str(e)}")
            # 返回基本处理结果
            return ProcessedQuery(
                original_query=query,
                enhanced_query=query,
                analysis=QueryAnalysis(
                    original_query=query,
                    normalized_query=query,
                    query_type=QueryType.FACTUAL,
                    query_complexity=QueryComplexity.SIMPLE,
                    query_intent=QueryIntent.SEARCH,
                    entities=[],
                    keywords=[],
                    semantic_keywords=[],
                    confidence=0.5
                ),
                search_strategies=["basic"],
                filters={},
                boost_terms=[],
                context_terms=[],
                expected_answer_type="text",
                routing_config="default"
            )