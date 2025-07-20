#!/usr/bin/env python3
"""
实体提取功能测试脚本
"""
import asyncio
import sys
import os
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from src.core.nlu_engine import NLUEngine
from src.utils.logger import get_logger

logger = get_logger(__name__)


async def test_entity_extraction():
    """测试实体提取功能"""
    try:
        print("🚀 开始测试实体提取功能...")
        
        # 初始化NLU引擎
        print("⚙️ 初始化NLU引擎...")
        nlu_engine = NLUEngine()
        await nlu_engine.initialize()
        
        # 测试用例
        test_cases = [
            {
                "text": "我要从北京到上海的机票，明天出发",
                "expected_types": ["CITY", "time"],
                "description": "城市和时间提取"
            },
            {
                "text": "帮我预订CA1234航班，联系电话是13912345678",
                "expected_types": ["FLIGHT", "phone-number"],
                "description": "航班号和电话号码"
            },
            {
                "text": "张三想要查询账户余额，金额是1000元",
                "expected_types": ["PERSON", "amount-of-money"],
                "description": "人名和金额"
            },
            {
                "text": "发送邮件到test@example.com，网址是https://www.example.com",
                "expected_types": ["email", "url"],
                "description": "邮箱和网址"
            },
            {
                "text": "今天下午3点到5点，温度是25度",
                "expected_types": ["time", "temperature"],
                "description": "时间和温度"
            },
            {
                "text": "我在中国银行工作，距离公司2公里",
                "expected_types": ["ORGANIZATION", "distance"],
                "description": "机构和距离"
            },
            {
                "text": "买了500毫升矿泉水",
                "expected_types": ["volume"],
                "description": "体积单位"
            },
            {
                "text": "简单的文本，没有特殊实体",
                "expected_types": [],
                "description": "无实体文本"
            }
        ]
        
        print("\n🧪 开始测试用例...")
        print("=" * 80)
        
        for i, test_case in enumerate(test_cases, 1):
            text = test_case["text"]
            expected_types = test_case["expected_types"]
            description = test_case["description"]
            
            print(f"\n测试 {i}: {description}")
            print(f"输入文本: '{text}'")
            print(f"预期实体类型: {expected_types}")
            print("-" * 60)
            
            try:
                # 执行实体提取
                entities = await nlu_engine.extract_entities(
                    text=text,
                    use_duckling=True,  # 测试Duckling
                    use_llm=False       # 暂时禁用LLM（避免连接错误）
                )
                
                print(f"📋 提取到 {len(entities)} 个实体:")
                
                if entities:
                    for j, entity in enumerate(entities, 1):
                        print(f"  {j}. 类型: {entity.get('entity', 'Unknown')}")
                        print(f"     值: {entity.get('value', 'N/A')}")
                        print(f"     文本: '{entity.get('text', '')}'")
                        print(f"     位置: {entity.get('start', 0)}-{entity.get('end', 0)}")
                        print(f"     置信度: {entity.get('confidence', 0):.3f}")
                        print(f"     来源: {entity.get('source', 'unknown')}")
                        
                        # 显示额外信息
                        if 'grain' in entity and entity['grain']:
                            print(f"     时间粒度: {entity['grain']}")
                        if 'unit' in entity and isinstance(entity.get('value'), dict):
                            print(f"     单位: {entity['value'].get('unit', 'N/A')}")
                        print()
                
                # 验证预期实体类型
                found_types = {entity.get('entity') for entity in entities}
                missing_types = set(expected_types) - found_types
                unexpected_types = found_types - set(expected_types) if expected_types else set()
                
                if missing_types:
                    print(f"⚠️  未找到预期实体类型: {missing_types}")
                if unexpected_types and expected_types:  # 只在有预期类型时显示意外类型
                    print(f"ℹ️  发现额外实体类型: {unexpected_types}")
                if not missing_types and (not unexpected_types or not expected_types):
                    print("✅ 实体提取结果符合预期")
                
            except Exception as e:
                print(f"❌ 测试失败: {str(e)}")
                import traceback
                traceback.print_exc()
        
        # 测试特定实体类型提取
        print("\n🎯 测试特定实体类型提取...")
        print("=" * 80)
        
        test_text = "张三从北京到上海，CA1234航班，明天下午3点，票价1000元"
        
        specific_tests = [
            (["CITY"], "城市"),
            (["FLIGHT"], "航班"),
            (["PERSON"], "人名"),
            (["time"], "时间"),
            (["amount-of-money"], "金额")
        ]
        
        for entity_types, type_name in specific_tests:
            print(f"\n🔍 提取 {type_name} 实体...")
            entities = await nlu_engine.extract_entities(
                text=test_text,
                entity_types=entity_types,
                use_duckling=True,
                use_llm=False
            )
            
            print(f"找到 {len(entities)} 个 {type_name} 实体:")
            for entity in entities:
                print(f"  - {entity.get('entity')}: {entity.get('value')} (置信度: {entity.get('confidence', 0):.3f})")
        
        # 测试实体合并
        print("\n🔗 测试实体合并功能...")
        print("=" * 80)
        
        # 创建测试用的重叠实体
        test_entities = [
            {
                'entity': 'CITY',
                'value': '北京',
                'text': '北京',
                'start': 0,
                'end': 2,
                'confidence': 0.9,
                'source': 'rule'
            },
            {
                'entity': 'LOCATION',
                'value': '北京',
                'text': '北京',
                'start': 0,
                'end': 2,
                'confidence': 0.8,
                'source': 'llm'
            },
            {
                'entity': 'FLIGHT',
                'value': 'CA1234',
                'text': 'CA1234',
                'start': 10,
                'end': 16,
                'confidence': 0.95,
                'source': 'rule'
            }
        ]
        
        print(f"合并前: {len(test_entities)} 个实体")
        merged_entities = nlu_engine._merge_entities(test_entities)
        print(f"合并后: {len(merged_entities)} 个实体")
        
        for entity in merged_entities:
            print(f"  - {entity.get('entity')}: {entity.get('value')} "
                  f"(来源: {entity.get('source')}, 置信度: {entity.get('confidence', 0):.3f})")
            if 'merged_from' in entity:
                print(f"    合并来源: {entity['merged_from']}")
        
        print("\n✅ 实体提取功能测试完成!")
        
    except Exception as e:
        print(f"❌ 测试过程中出现错误: {str(e)}")
        import traceback
        traceback.print_exc()
    
    finally:
        # 清理资源
        if 'nlu_engine' in locals():
            await nlu_engine.cleanup()


async def test_duckling_connection():
    """测试Duckling连接"""
    print("\n🔌 测试Duckling连接...")
    
    nlu_engine = NLUEngine()
    await nlu_engine.initialize()
    
    # 测试一个简单的时间提取
    test_text = "明天下午3点"
    entities = await nlu_engine._extract_duckling_entities(test_text, ["time"])
    
    if entities:
        print(f"✅ Duckling连接正常，提取到 {len(entities)} 个时间实体")
        for entity in entities:
            print(f"  - {entity.get('value')}")
    else:
        print("⚠️ Duckling未连接或无法提取实体（这是正常的，如果没有启动Duckling服务）")
    
    await nlu_engine.cleanup()


async def main():
    """主函数"""
    await test_entity_extraction()
    await test_duckling_connection()


if __name__ == "__main__":
    # 运行测试
    asyncio.run(main())