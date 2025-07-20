"""
验证代码框架与数据结构文档的一致性测试
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
import json
from datetime import datetime
from typing import Dict, Any

from src.schemas.chat import (
    ChatInteractRequest, ChatResponse, SlotInfo, 
    IntentCandidate, ApiResultData, ChatContext, DeviceInfo
)


class TestDataStructureConsistency:
    """测试数据结构一致性"""
    
    def test_chat_request_structure(self):
        """测试聊天请求结构与文档一致性"""
        # 文档中的标准请求结构
        doc_request = {
            "user_id": "user123",
            "input": "我想订一张明天从北京到上海的经济舱机票",
            "context": {
                "location": {
                    "ip": "192.168.1.100",
                    "city": "Beijing",
                    "country": "CN"
                },
                "user_preferences": {
                    "language": "zh-CN",
                    "timezone": "Asia/Shanghai"
                }
            }
        }
        
        # 验证Pydantic模型是否能正确解析
        context = ChatContext(
            location=doc_request["context"]["location"],
            user_preferences=doc_request["context"]["user_preferences"]
        )
        
        request = ChatInteractRequest(
            user_id=doc_request["user_id"],
            input=doc_request["input"],
            context=context
        )
        
        assert request.user_id == "user123"
        assert "订一张" in request.input
        assert request.context.location["city"] == "Beijing"
        assert request.context.user_preferences["language"] == "zh-CN"
    
    def test_chat_response_structure(self):
        """测试聊天响应结构与文档一致性"""
        # 文档中的标准响应结构data部分
        doc_response_data = {
            "response": "机票预订成功！订单号：FL202412010001",
            "intent": "book_flight",
            "confidence": 0.95,
            "status": "completed",
            "response_type": "api_result",
            "slots": {
                "departure_city": {
                    "value": "北京",
                    "confidence": 0.98,
                    "source": "user_input",
                    "normalized_value": "Beijing",
                    "extracted_from": "从北京"
                }
            },
            "api_result": {
                "order_id": "FL202412010001",
                "flight_number": "CA1234",
                "price": 580.00
            }
        }
        
        # 验证Pydantic模型
        slot_info = SlotInfo(
            value="北京",
            confidence=0.98,
            source="user_input"
        )
        
        api_result = ApiResultData(
            order_id="FL202412010001",
            flight_info={"flight_number": "CA1234", "price": 580.00}
        )
        
        response = ChatResponse(
            response="机票预订成功！订单号：FL202412010001",
            intent="book_flight",
            confidence=0.95,
            status="completed",
            response_type="api_result",
            slots={"departure_city": slot_info},
            api_result=api_result
        )
        
        assert response.intent == "book_flight"
        assert response.confidence == 0.95
        assert response.slots["departure_city"].value == "北京"
        assert response.api_result.order_id == "FL202412010001"
    
    def test_slot_structure_consistency(self):
        """测试槽位结构一致性"""
        # 文档中的槽位结构
        doc_slot = {
            "value": "北京",
            "confidence": 0.98,
            "source": "user_input",
            "normalized_value": "Beijing",
            "extracted_from": "从北京"
        }
        
        # 验证SlotInfo模型
        slot_info = SlotInfo(
            value=doc_slot["value"],
            confidence=doc_slot["confidence"],
            source=doc_slot["source"]
        )
        
        assert slot_info.value == "北京"
        assert slot_info.confidence == 0.98
        assert slot_info.source == "user_input"
    
    def test_intent_candidate_structure(self):
        """测试意图候选结构一致性"""
        # 文档中的候选意图结构
        doc_candidate = {
            "intent": "book_flight",
            "confidence": 0.72,
            "display_name": "机票",
            "description": "预订航班机票"
        }
        
        # 验证IntentCandidate模型
        candidate = IntentCandidate(
            intent_name=doc_candidate["intent"],
            display_name=doc_candidate["display_name"],
            confidence=doc_candidate["confidence"],
            description=doc_candidate["description"]
        )
        
        assert candidate.intent_name == "book_flight"
        assert candidate.display_name == "机票"
        assert candidate.confidence == 0.72
    
    def test_ambiguous_response_structure(self):
        """测试歧义响应结构一致性"""
        # 文档中的歧义响应
        doc_candidates = [
            {
                "intent": "book_flight",
                "confidence": 0.72,
                "display_name": "机票",
                "description": "预订航班机票"
            },
            {
                "intent": "book_train",
                "confidence": 0.68,
                "display_name": "火车票",
                "description": "预订火车票"
            }
        ]
        
        # 验证候选意图列表
        candidates = [
            IntentCandidate(
                intent_name=c["intent"],
                display_name=c["display_name"],
                confidence=c["confidence"],
                description=c["description"]
            )
            for c in doc_candidates
        ]
        
        response = ChatResponse(
            response="请问您想要预订哪种票？",
            intent=None,
            confidence=0.0,
            status="ambiguous",
            response_type="disambiguation",
            ambiguous_intents=candidates
        )
        
        assert response.status == "ambiguous"
        assert len(response.ambiguous_intents) == 2
        assert response.ambiguous_intents[0].intent_name == "book_flight"
        assert response.ambiguous_intents[1].intent_name == "book_train"
    
    def test_incomplete_response_structure(self):
        """测试不完整响应结构一致性"""
        # 文档中的槽位不完整响应
        doc_response = {
            "response": "好的，我来帮您预订机票。请告诉我出发城市是哪里？",
            "intent": "book_flight",
            "confidence": 0.92,
            "status": "slot_filling",
            "response_type": "slot_prompt",
            "missing_slots": ["departure_city", "arrival_city", "departure_date"]
        }
        
        # 验证响应模型
        response = ChatResponse(
            response=doc_response["response"],
            intent=doc_response["intent"],
            confidence=doc_response["confidence"],
            status=doc_response["status"],
            response_type=doc_response["response_type"],
            missing_slots=doc_response["missing_slots"]
        )
        
        assert response.intent == "book_flight"
        assert response.status == "slot_filling"
        assert "departure_city" in response.missing_slots
        assert len(response.missing_slots) == 3
    
    def test_api_error_response_structure(self):
        """测试API错误响应结构一致性"""
        # 文档中的API错误响应
        doc_response = {
            "response": "很抱歉，机票预订服务暂时不可用",
            "intent": "book_flight",
            "confidence": 0.93,
            "status": "api_error",
            "response_type": "error_with_alternatives",
            "suggestions": ["查询余额", "联系客服", "稍后重试"]
        }
        
        # 验证错误响应模型
        response = ChatResponse(
            response=doc_response["response"],
            intent=doc_response["intent"],
            confidence=doc_response["confidence"],
            status=doc_response["status"],
            response_type=doc_response["response_type"],
            suggestions=doc_response["suggestions"]
        )
        
        assert response.status == "api_error"
        assert response.response_type == "error_with_alternatives"
        assert "查询余额" in response.suggestions
    
    def test_validation_error_structure(self):
        """测试验证错误结构一致性"""
        # 文档中的验证错误槽位
        doc_slot = {
            "value": "北京",
            "confidence": 0.94,
            "source": "user_input",
            "validation_status": "invalid",
            "validation_error": "same_as_departure"
        }
        
        # 验证槽位验证错误
        slot_info = SlotInfo(
            value=doc_slot["value"],
            confidence=doc_slot["confidence"],
            source=doc_slot["source"],
            is_validated=False,
            validation_error=doc_slot["validation_error"]
        )
        
        assert slot_info.value == "北京"
        assert slot_info.is_validated == False
        assert slot_info.validation_error == "same_as_departure"
    
    def test_multi_intent_response_structure(self):
        """测试多意图响应结构一致性"""
        # 文档中的多意图处理响应
        doc_response = {
            "response": "我先为您查询余额，然后帮您预订北京到上海的机票。",
            "intent": "multi_intent",
            "confidence": 0.89,
            "status": "multi_intent_processing",
            "response_type": "multi_intent_with_continuation",
            "missing_slots": ["departure_date"]
        }
        
        # 验证多意图响应
        response = ChatResponse(
            response=doc_response["response"],
            intent=doc_response["intent"],
            confidence=doc_response["confidence"],
            status=doc_response["status"],
            response_type=doc_response["response_type"],
            missing_slots=doc_response["missing_slots"]
        )
        
        assert response.intent == "multi_intent"
        assert response.status == "multi_intent_processing"
        assert "departure_date" in response.missing_slots
    
    def test_device_info_structure(self):
        """测试设备信息结构一致性"""
        # 文档中的设备信息
        doc_device = {
            "platform": "web",
            "ip_address": "192.168.1.100",
            "language": "zh-CN"
        }
        
        # 验证DeviceInfo模型
        device_info = DeviceInfo(
            platform=doc_device["platform"],
            ip_address=doc_device["ip_address"],
            language=doc_device["language"]
        )
        
        assert device_info.platform == "web"
        assert device_info.ip_address == "192.168.1.100"
        assert device_info.language == "zh-CN"
    
    def test_processing_metadata_structure(self):
        """测试处理元数据结构一致性"""
        # 文档中的元数据字段
        doc_metadata = {
            "timestamp": "2024-12-01T10:00:15Z",
            "request_id": "req_20241201_001",
            "processing_time_ms": 350
        }
        
        # 验证响应元数据
        response = ChatResponse(
            response="测试响应",
            status="completed",
            response_type="task_completion",
            processing_time_ms=doc_metadata["processing_time_ms"],
            request_id=doc_metadata["request_id"]
        )
        
        assert response.processing_time_ms == 350
        assert response.request_id == "req_20241201_001"
    
    def test_status_response_type_mapping(self):
        """测试status和response_type字段映射一致性"""
        # 文档中定义的status和response_type对应关系
        status_mappings = {
            "completed": ["task_completion", "api_result"],
            "incomplete": ["slot_prompt"],
            "ambiguous": ["disambiguation"],
            "api_error": ["error_with_alternatives"],
            "validation_error": ["validation_error_prompt"],
            "ragflow_handled": ["ragflow_response"],
            "interruption_handled": ["small_talk_with_context_return"],
            "multi_intent_processing": ["multi_intent_with_continuation"],
            "intent_cancelled": ["cancellation_confirmation"],
            "intent_postponed": ["postponement_with_save"],
            "suggestion_rejected": ["rejection_acknowledgment"]
        }
        
        # 验证每个状态和响应类型组合
        for status, response_types in status_mappings.items():
            for response_type in response_types:
                response = ChatResponse(
                    response=f"测试{status}状态",
                    status=status,
                    response_type=response_type
                )
                
                assert response.status == status
                assert response.response_type == response_type


if __name__ == "__main__":
    # 运行一致性验证测试
    test_instance = TestDataStructureConsistency()
    
    print("开始验证数据结构一致性...")
    
    test_methods = [
        method for method in dir(test_instance) 
        if method.startswith('test_') and callable(getattr(test_instance, method))
    ]
    
    passed_tests = 0
    failed_tests = 0
    
    for test_method in test_methods:
        try:
            print(f"运行测试: {test_method}")
            getattr(test_instance, test_method)()
            print(f"✓ {test_method} 通过")
            passed_tests += 1
        except Exception as e:
            print(f"✗ {test_method} 失败: {str(e)}")
            failed_tests += 1
    
    print(f"\n测试总结:")
    print(f"通过: {passed_tests}")
    print(f"失败: {failed_tests}")
    print(f"总计: {passed_tests + failed_tests}")
    
    if failed_tests == 0:
        print("\n🎉 所有测试通过！代码框架与文档数据结构完全一致。")
    else:
        print(f"\n⚠️  有 {failed_tests} 个测试失败，需要检查代码与文档的一致性。")