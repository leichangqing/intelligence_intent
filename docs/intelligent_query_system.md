# 智能查询系统 (TASK-031)

## 概述

智能查询系统是一个高级的知识库查询处理框架，实现了语义分析、上下文感知、查询优化等功能。该系统能够理解用户意图，分析查询复杂度，并根据上下文提供最佳的查询策略。

## 核心组件

### 1. 查询规范化器 (QueryNormalizer)

负责清理和规范化用户输入的查询文本：

- **文本清理**：移除多余空格、特殊字符
- **实体识别**：识别电话号码、邮箱、银行卡号等实体
- **同义词替换**：统一同义词表达
- **停用词处理**：过滤无意义词汇，保留重要疑问词

```python
normalizer = QueryNormalizer()
normalized_query, entities = await normalizer.normalize_query("请问如何查询我的银行账户余额？")
```

### 2. 查询分析器 (QueryAnalyzer)

分析查询的语义特征和意图：

- **查询类型识别**：事实性、程序性、概念性、比较性等
- **复杂度分析**：简单、中等、复杂、极复杂
- **意图识别**：搜索、比较、解释、指导、推荐、故障排除
- **关键词提取**：使用jieba分词和词性标注
- **领域识别**：银行、旅游、购物、技术等

```python
analyzer = QueryAnalyzer()
analysis = await analyzer.analyze_query(normalized_query, entities)
print(f"查询类型: {analysis.query_type}")
print(f"查询意图: {analysis.query_intent}")
print(f"复杂度: {analysis.query_complexity}")
```

### 3. 上下文感知查询增强器 (ContextAwareQueryEnhancer)

基于会话上下文增强查询：

- **会话模式分析**：查询频率、复杂度趋势、领域切换
- **对话流程分析**：初始、继续、问题解决、比较
- **用户意图历史**：主导意图、意图多样性
- **时间模式分析**：会话时长、查询间隔、时间紧迫性
- **查询演化分析**：细化、扩展、转向、重复

```python
enhancer = ContextAwareQueryEnhancer(cache_service)
processed_query = await enhancer.enhance_query(query, analysis, context)
```

### 4. 智能查询处理器 (IntelligentQueryProcessor)

主控制器，协调各个组件：

```python
processor = IntelligentQueryProcessor(cache_service)
processed_query = await processor.process_query(query, context)
```

## 数据结构

### QueryType (查询类型)

```python
class QueryType(Enum):
    FACTUAL = "factual"           # 事实性查询
    PROCEDURAL = "procedural"     # 程序性查询
    CONCEPTUAL = "conceptual"     # 概念性查询
    COMPARATIVE = "comparative"   # 比较性查询
    CAUSAL = "causal"            # 因果关系查询
    TEMPORAL = "temporal"        # 时间相关查询
    SPATIAL = "spatial"          # 空间相关查询
    PERSONAL = "personal"        # 个人化查询
```

### QueryIntent (查询意图)

```python
class QueryIntent(Enum):
    SEARCH = "search"            # 搜索信息
    COMPARE = "compare"          # 比较对比
    EXPLAIN = "explain"          # 解释说明
    INSTRUCT = "instruct"        # 指导说明
    RECOMMEND = "recommend"      # 推荐建议
    TROUBLESHOOT = "troubleshoot"  # 故障排除
```

### QueryComplexity (查询复杂度)

```python
class QueryComplexity(Enum):
    SIMPLE = "simple"
    MODERATE = "moderate"
    COMPLEX = "complex"
    VERY_COMPLEX = "very_complex"
```

### ProcessedQuery (处理后的查询)

```python
@dataclass
class ProcessedQuery:
    original_query: str              # 原始查询
    enhanced_query: str              # 增强查询
    analysis: QueryAnalysis          # 查询分析结果
    search_strategies: List[str]     # 搜索策略
    filters: Dict[str, Any]          # 过滤条件
    boost_terms: List[str]           # 提升词
    context_terms: List[str]         # 上下文词
    expected_answer_type: str        # 期望答案类型
    routing_config: str              # 路由配置
    metadata: Dict[str, Any]         # 元数据
```

## RAGFLOW智能集成

### 智能查询方法

```python
async def query_knowledge_base_intelligent(
    self, 
    query: str, 
    session_context: Dict[str, Any],
    config_name: str = "default"
) -> RagflowResponse:
```

### 搜索策略

1. **基本搜索** (basic)：标准查询
2. **多步骤搜索** (multi_step)：复杂查询分解
3. **比较搜索** (comparative)：对比分析
4. **上下文感知搜索** (context_aware)：基于会话历史
5. **领域专用搜索** (domain_specific)：特定领域优化

### 多步骤查询处理

对于复杂查询，系统会：

1. **查询分解**：将复杂查询分解为多个子查询
2. **子查询执行**：分别执行每个子查询
3. **结果合并**：合并多个响应结果
4. **文档去重**：去除重复的源文档

```python
# 示例：程序性查询分解
原查询: "如何开通银行卡？"
子查询: 
- "什么是银行卡"
- "银行卡开通步骤"
- "银行卡开通注意事项"
```

### 比较查询处理

对于比较性查询：

1. **实体提取**：识别比较对象
2. **分别查询**：对每个实体单独查询
3. **结果对比**：生成对比分析
4. **总结建议**：提供选择建议

```python
# 示例：比较查询处理
原查询: "基金和股票有什么区别？"
处理: 
- 查询"基金的特点"
- 查询"股票的特点"
- 生成对比结果
```

### 上下文感知处理

基于会话历史和用户偏好：

1. **上下文分析**：分析会话模式和用户意图
2. **查询增强**：添加上下文信息
3. **结果优化**：基于上下文重新排序
4. **个性化推荐**：根据用户偏好调整

## 性能优化

### 缓存机制

1. **查询结果缓存**：缓存RAGFLOW响应
2. **分析结果缓存**：缓存查询分析结果
3. **配置缓存**：缓存RAGFLOW配置
4. **会话上下文缓存**：缓存会话信息

### 速率限制

- **滑动窗口算法**：控制请求频率
- **配置化限制**：可配置的速率限制参数
- **智能回退**：超限时使用备用配置

### 回退机制

1. **配置回退**：主配置失败时使用备用配置
2. **查询回退**：智能查询失败时回退到基本查询
3. **默认响应**：最后的回退响应

## 集成示例

### 对话服务集成

```python
class ConversationService:
    async def call_ragflow(self, user_input: str, session_context: Dict[str, Any], 
                          config_name: str = "default") -> Dict[str, Any]:
        # 构建查询上下文
        query_context = {
            'session_id': session_context.get('session_id'),
            'user_id': session_context.get('user_id'),
            'conversation_history': session_context.get('conversation_history', []),
            'current_intent': session_context.get('current_intent'),
            'current_slots': session_context.get('current_slots', {}),
            'timestamp': datetime.now().isoformat()
        }
        
        # 调用智能化RAGFLOW服务
        response = await self.ragflow_service.query_knowledge_base_intelligent(
            query=user_input,
            session_context=query_context,
            config_name=config_name
        )
        
        return {
            'answer': response.data,
            'source_documents': response.source_documents,
            'confidence': self._calculate_ragflow_confidence(response),
            'response_time': response.response_time
        }
```

### 查询分析数据

```python
async def get_query_analytics(self, session_id: str = None) -> Dict[str, Any]:
    return {
        'total_queries': 0,
        'query_types': {},              # 查询类型分布
        'query_intents': {},            # 查询意图分布
        'complexity_distribution': {},  # 复杂度分布
        'domain_distribution': {},      # 领域分布
        'success_rate': 0.0,
        'popular_keywords': {},
        'query_patterns': []
    }
```

## 配置和部署

### 环境要求

- Python 3.8+
- jieba 中文分词库
- aiohttp 异步HTTP客户端
- Redis 缓存服务

### 配置文件

```yaml
# RAGFLOW配置
ragflow:
  default:
    api_endpoint: "https://api.ragflow.example.com/v1"
    timeout_seconds: 30
    rate_limit:
      max_requests: 100
      window_seconds: 60
    fallback_config:
      enabled: true
      config_name: "backup"
      default_response: "抱歉，我暂时无法回答您的问题。"
```

### 数据库迁移

```bash
# 创建RAGFLOW配置表
python migrations/add_ragflow_config_table.py create

# 显示配置信息
python migrations/add_ragflow_config_table.py show
```

## 测试和监控

### 功能测试

```bash
# 运行智能查询测试
python test_intelligent_query.py
```

### 性能监控

- **响应时间监控**：跟踪查询处理时间
- **成功率监控**：统计查询成功率
- **缓存命中率**：监控缓存性能
- **错误率统计**：记录和分析错误

### 日志记录

```python
logger.info(f"智能查询完成: {query} -> {response.success}, 耗时: {response_time:.3f}s")
logger.error(f"查询处理失败: {str(e)}")
```

## 最佳实践

1. **查询优化**：
   - 使用缓存避免重复处理
   - 合理设置TTL时间
   - 优化查询分解策略

2. **错误处理**：
   - 实现多层回退机制
   - 记录详细错误日志
   - 提供友好的错误提示

3. **性能优化**：
   - 使用异步处理
   - 实现连接池管理
   - 合理设置超时时间

4. **安全考虑**：
   - API密钥安全存储
   - 输入验证和清理
   - 速率限制保护

## 扩展功能

### 未来增强

1. **机器学习集成**：
   - 查询意图预测模型
   - 个性化推荐算法
   - 查询质量评估

2. **多语言支持**：
   - 英文查询处理
   - 多语言实体识别
   - 跨语言查询翻译

3. **高级分析**：
   - 查询趋势分析
   - 用户行为分析
   - 知识图谱集成

4. **实时优化**：
   - 在线学习机制
   - 动态策略调整
   - 自适应参数优化

## 总结

智能查询系统通过语义分析、上下文感知和查询优化，显著提升了知识库查询的准确性和用户体验。系统支持多种查询类型和搜索策略，具有良好的扩展性和可维护性。

关键特性：
- ✅ 智能语义分析
- ✅ 上下文感知增强
- ✅ 多策略搜索
- ✅ 性能优化
- ✅ 错误处理和回退
- ✅ 全面的监控和分析

该系统为构建高质量的智能对话系统提供了坚实的基础。