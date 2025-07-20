#!/usr/bin/env python3
"""
智能查询功能测试脚本 (TASK-031)
测试智能化知识库查询逻辑和优化算法
"""
import asyncio
import sys
import os
sys.path.insert(0, os.path.abspath('.'))

from src.services.cache_service import CacheService
from src.services.query_processor import (
    IntelligentQueryProcessor, QueryContext, QueryType, QueryComplexity, QueryIntent
)
from src.services.ragflow_service import RagflowService
from src.services.conversation_service import ConversationService
from src.utils.logger import get_logger

logger = get_logger(__name__)


async def test_query_normalization():
    """测试查询规范化"""
    print("=== 测试查询规范化 ===")
    
    cache_service = CacheService()
    await cache_service.initialize()
    
    processor = IntelligentQueryProcessor(cache_service)
    
    test_queries = [
        "请问如何查询我的银行账户余额？",
        "我想要预订明天从北京到上海的机票",
        "比较一下iPhone和华为手机的优缺点",
        "系统出现503错误，怎么解决？",
        "请帮我推荐一些理财产品",
        "修改密码的具体步骤是什么"
    ]
    
    for query in test_queries:
        print(f"\n原始查询: {query}")
        
        # 规范化查询
        normalized_query, entities = await processor.normalizer.normalize_query(query)
        print(f"规范化后: {normalized_query}")
        print(f"提取实体: {[e.text for e in entities]}")
        
        # 分析查询
        analysis = await processor.analyzer.analyze_query(normalized_query, entities)
        print(f"查询类型: {analysis.query_type.value}")
        print(f"查询意图: {analysis.query_intent.value}")
        print(f"复杂度: {analysis.query_complexity.value}")
        print(f"关键词: {analysis.keywords}")
        print(f"领域: {analysis.domain}")
        print(f"置信度: {analysis.confidence:.3f}")
        print("-" * 50)
    
    await cache_service.close()


async def test_context_aware_enhancement():
    """测试上下文感知增强"""
    print("\n=== 测试上下文感知增强 ===")
    
    cache_service = CacheService()
    await cache_service.initialize()
    
    processor = IntelligentQueryProcessor(cache_service)
    
    # 模拟会话上下文
    context = QueryContext(
        session_id="test_session_001",
        user_id="test_user",
        conversation_history=[
            {"role": "user", "content": "我想查询银行账户信息"},
            {"role": "assistant", "content": "我可以帮您查询账户信息，请问您需要查询什么具体信息？"},
            {"role": "user", "content": "余额查询"}
        ],
        current_intent="banking_inquiry",
        current_slots={"account_type": "checking"},
        user_preferences={"preferred_domains": ["banking", "finance"]},
        domain_context="banking",
        previous_queries=["查询账户", "余额查询"],
        query_pattern="banking_sequence"
    )
    
    test_queries = [
        "转账手续费是多少？",  # 银行领域继续
        "除了余额还能查看什么？",  # 扩展查询
        "如果忘记密码怎么办？",  # 问题解决
        "和其他银行比较有什么优势？"  # 比较查询
    ]
    
    for query in test_queries:
        print(f"\n当前查询: {query}")
        
        # 处理查询
        processed_query = await processor.process_query(query, context)
        
        print(f"增强查询: {processed_query.enhanced_query}")
        print(f"搜索策略: {processed_query.search_strategies}")
        print(f"过滤条件: {processed_query.filters}")
        print(f"提升词: {processed_query.boost_terms}")
        print(f"上下文词: {processed_query.context_terms}")
        print(f"期望答案类型: {processed_query.expected_answer_type}")
        print(f"路由配置: {processed_query.routing_config}")
        
        # 更新上下文
        context.previous_queries.append(query)
        context.conversation_history.append({"role": "user", "content": query})
        
        print("-" * 50)
    
    await cache_service.close()


async def test_intelligent_ragflow_integration():
    """测试智能RAGFLOW集成"""
    print("\n=== 测试智能RAGFLOW集成 ===")
    
    cache_service = CacheService()
    await cache_service.initialize()
    
    # 创建RAGFLOW服务
    ragflow_service = RagflowService(cache_service)
    
    # 模拟会话上下文
    session_context = {
        'session_id': 'test_session_002',
        'user_id': 'test_user',
        'conversation_history': [
            {"role": "user", "content": "我想了解投资理财"},
            {"role": "assistant", "content": "我可以为您介绍投资理财的相关信息"}
        ],
        'current_intent': 'financial_consultation',
        'current_slots': {'topic': 'investment'},
        'user_preferences': {'preferred_domains': ['finance', 'investment']},
        'domain_context': 'finance',
        'previous_queries': ['投资理财', '理财产品'],
        'query_pattern': 'financial_consultation'
    }
    
    test_queries = [
        "什么是基金投资？",  # 概念性查询
        "如何选择适合的基金？",  # 程序性查询
        "基金和股票有什么区别？",  # 比较性查询
        "最近市场行情如何？",  # 时间相关查询
        "我应该投资多少钱？"  # 个人化查询
    ]
    
    for query in test_queries:
        print(f"\n查询: {query}")
        
        try:
            # 调用智能查询
            response = await ragflow_service.query_knowledge_base_intelligent(
                query=query,
                session_context=session_context,
                config_name="default"
            )
            
            print(f"查询成功: {response.success}")
            if response.success:
                print(f"回答: {response.data}")
                print(f"源文档数量: {len(response.source_documents)}")
            else:
                print(f"错误: {response.error}")
            
            print(f"响应时间: {response.response_time:.3f}s")
            
        except Exception as e:
            print(f"查询失败: {str(e)}")
        
        print("-" * 50)
    
    await cache_service.close()


async def test_conversation_service_integration():
    """测试对话服务集成"""
    print("\n=== 测试对话服务集成 ===")
    
    cache_service = CacheService()
    await cache_service.initialize()
    
    # 创建RAGFLOW服务
    ragflow_service = RagflowService(cache_service)
    
    # 创建对话服务
    conversation_service = ConversationService(cache_service, ragflow_service)
    
    # 模拟会话上下文
    session_context = {
        'session_id': 'test_session_003',
        'user_id': 'test_user',
        'conversation_history': [
            {"role": "user", "content": "我想查询技术问题"},
            {"role": "assistant", "content": "我可以帮您解决技术问题"}
        ],
        'current_intent': 'technical_support',
        'current_slots': {'category': 'system_error'},
        'user_preferences': {'preferred_domains': ['technical', 'system']},
        'domain_context': 'technical',
        'previous_queries': ['技术问题', '系统错误'],
        'query_pattern': 'technical_support'
    }
    
    test_queries = [
        "数据库连接失败怎么处理？",
        "如何优化系统性能？",
        "服务器内存不足的解决方案",
        "API接口超时如何调试？"
    ]
    
    for query in test_queries:
        print(f"\n查询: {query}")
        
        try:
            # 调用对话服务的RAGFLOW方法
            response = await conversation_service.call_ragflow(
                user_input=query,
                session_context=session_context,
                config_name="technical"
            )
            
            print(f"回答: {response.get('answer', '无回答')}")
            print(f"置信度: {response.get('confidence', 0.0):.3f}")
            print(f"响应时间: {response.get('response_time', 0.0):.3f}s")
            print(f"使用配置: {response.get('config_used', 'unknown')}")
            
            if response.get('source_documents'):
                print(f"源文档数量: {len(response['source_documents'])}")
            
            if response.get('error'):
                print(f"错误: {response['error']}")
            
        except Exception as e:
            print(f"查询失败: {str(e)}")
        
        print("-" * 50)
    
    await cache_service.close()


async def test_query_analytics():
    """测试查询分析功能"""
    print("\n=== 测试查询分析功能 ===")
    
    cache_service = CacheService()
    await cache_service.initialize()
    
    ragflow_service = RagflowService(cache_service)
    
    # 模拟多个查询以生成分析数据
    session_context = {
        'session_id': 'test_session_004',
        'user_id': 'test_user',
        'conversation_history': [],
        'current_intent': None,
        'current_slots': {},
        'user_preferences': {},
        'domain_context': None,
        'previous_queries': [],
        'query_pattern': None
    }
    
    # 执行多个查询
    queries = [
        "如何开通银行卡？",
        "信用卡和借记卡的区别",
        "忘记密码怎么找回",
        "转账手续费多少",
        "理财产品推荐"
    ]
    
    for query in queries:
        try:
            await ragflow_service.query_knowledge_base_intelligent(
                query=query,
                session_context=session_context,
                config_name="default"
            )
            session_context['previous_queries'].append(query)
        except Exception as e:
            print(f"查询失败: {str(e)}")
    
    # 获取分析数据
    try:
        analytics = await ragflow_service.get_query_analytics(
            session_id=session_context['session_id']
        )
        
        print("查询分析结果:")
        print(f"总查询数: {analytics.get('total_queries', 0)}")
        print(f"查询类型分布: {analytics.get('query_types', {})}")
        print(f"查询意图分布: {analytics.get('query_intents', {})}")
        print(f"复杂度分布: {analytics.get('complexity_distribution', {})}")
        print(f"领域分布: {analytics.get('domain_distribution', {})}")
        
    except Exception as e:
        print(f"获取分析数据失败: {str(e)}")
    
    await cache_service.close()


async def test_error_handling():
    """测试错误处理"""
    print("\n=== 测试错误处理 ===")
    
    cache_service = CacheService()
    await cache_service.initialize()
    
    processor = IntelligentQueryProcessor(cache_service)
    
    # 测试异常情况
    test_cases = [
        "",  # 空查询
        "   ",  # 空白查询
        "a" * 1000,  # 超长查询
        "？？？！！！",  # 只有标点符号
        "123456789",  # 纯数字
        "abcdefghijk",  # 纯英文
    ]
    
    for query in test_cases:
        print(f"\n测试查询: '{query[:50]}{'...' if len(query) > 50 else ''}'")
        
        try:
            # 创建基本上下文
            context = QueryContext(
                session_id="error_test_session",
                user_id="error_test_user",
                conversation_history=[],
                previous_queries=[]
            )
            
            # 处理查询
            processed_query = await processor.process_query(query, context)
            
            print(f"处理结果: {processed_query.enhanced_query}")
            print(f"查询类型: {processed_query.analysis.query_type.value}")
            print(f"置信度: {processed_query.analysis.confidence:.3f}")
            
        except Exception as e:
            print(f"处理失败: {str(e)}")
        
        print("-" * 30)
    
    await cache_service.close()


async def main():
    """主测试函数"""
    print("开始智能查询功能测试...")
    
    try:
        # 运行所有测试
        await test_query_normalization()
        await test_context_aware_enhancement()
        await test_intelligent_ragflow_integration()
        await test_conversation_service_integration()
        await test_query_analytics()
        await test_error_handling()
        
        print("\n✅ 所有测试完成!")
        
    except Exception as e:
        print(f"\n❌ 测试失败: {str(e)}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())