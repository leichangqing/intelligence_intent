#!/usr/bin/env python3
"""
API一致性验证脚本
验证API文档中的示例请求与实际代码结构的一致性
"""
import json
import sys
from typing import Dict, Any
from pathlib import Path

# 添加src路径以导入项目模块
sys.path.append(str(Path(__file__).parent.parent / "src"))

try:
    from schemas.chat import ChatRequest, ChatResponse, SessionManagementRequest, ContextUpdateRequest
    from pydantic import ValidationError
except ImportError as e:
    print(f"❌ 导入失败: {e}")
    print("请确保在项目根目录运行此脚本")
    sys.exit(1)

def validate_chat_interact_request():
    """验证对话交互请求结构"""
    print("🔍 验证 POST /api/v1/chat/interact 请求结构...")
    
    # 文档中的示例请求
    doc_example = {
        "user_id": "user123",
        "input": "我想订一张机票",
        "session_id": "sess_123",
        "context": {
            "device_info": {
                "platform": "web",
                "language": "zh-CN"
            },
            "client_system_id": "web_client_001"
        }
    }
    
    try:
        # 使用Pydantic模型验证
        chat_request = ChatRequest(**doc_example)
        print("✅ ChatRequest 验证通过")
        print(f"   - user_id: {chat_request.user_id}")
        print(f"   - input: {chat_request.input}")
        print(f"   - session_id: {chat_request.session_id}")
        print(f"   - context: {chat_request.context is not None}")
        return True
    except ValidationError as e:
        print(f"❌ ChatRequest 验证失败: {e}")
        return False

def validate_session_create_request():
    """验证会话创建请求结构"""
    print("\n🔍 验证 POST /api/v1/enhanced-chat/session/create 请求结构...")
    
    # 文档中的示例请求
    doc_example = {
        "user_id": "user123",
        "action": "create",
        "initial_context": {
            "device_info": {"platform": "web"},
            "business_context": {"department": "sales"}
        },
        "expiry_hours": 24
    }
    
    try:
        # 使用Pydantic模型验证
        session_request = SessionManagementRequest(**doc_example)
        print("✅ SessionManagementRequest 验证通过")
        print(f"   - user_id: {session_request.user_id}")
        print(f"   - action: {session_request.action}")
        print(f"   - initial_context: {session_request.initial_context is not None}")
        print(f"   - expiry_hours: {session_request.expiry_hours}")
        return True
    except ValidationError as e:
        print(f"❌ SessionManagementRequest 验证失败: {e}")
        return False

def validate_context_update_request():
    """验证上下文更新请求结构"""
    print("\n🔍 验证 POST /api/v1/enhanced-chat/session/update-context 请求结构...")
    
    # 文档中的示例请求
    doc_example = {
        "session_id": "sess_123",
        "context_updates": {
            "device_info": {"platform": "mobile"},
            "business_context": {"department": "sales"}
        },
        "merge_strategy": "merge",
        "preserve_history": True
    }
    
    try:
        # 使用Pydantic模型验证
        context_request = ContextUpdateRequest(**doc_example)
        print("✅ ContextUpdateRequest 验证通过")
        print(f"   - session_id: {context_request.session_id}")
        print(f"   - merge_strategy: {context_request.merge_strategy}")
        print(f"   - preserve_history: {context_request.preserve_history}")
        return True
    except ValidationError as e:
        print(f"❌ ContextUpdateRequest 验证失败: {e}")
        return False

def validate_response_structure():
    """验证响应结构完整性"""
    print("\n🔍 验证响应结构字段完整性...")
    
    # 检查ChatResponse模型的字段
    chat_response_fields = ChatResponse.__fields__.keys()
    required_fields = [
        'response', 'session_id', 'intent', 'confidence', 'slots', 
        'status', 'response_type', 'next_action', 'message_type'
    ]
    
    missing_fields = [field for field in required_fields if field not in chat_response_fields]
    
    if not missing_fields:
        print("✅ ChatResponse 字段完整性检查通过")
        print(f"   - 已定义字段: {list(chat_response_fields)}")
        return True
    else:
        print(f"❌ ChatResponse 缺少字段: {missing_fields}")
        return False

def main():
    """主验证函数"""
    print("=" * 50)
    print("🚀 开始API一致性验证...")
    print("=" * 50)
    
    results = []
    
    # 执行各项验证
    results.append(validate_chat_interact_request())
    results.append(validate_session_create_request()) 
    results.append(validate_context_update_request())
    results.append(validate_response_structure())
    
    # 汇总结果
    print("\n" + "=" * 50)
    print("📊 验证结果汇总:")
    print("=" * 50)
    
    passed = sum(results)
    total = len(results)
    
    if passed == total:
        print(f"🎉 全部验证通过! ({passed}/{total})")
        print("✅ API文档与代码结构完全一致")
        return 0
    else:
        print(f"⚠️  验证完成: {passed}/{total} 通过")
        print("❌ 发现不一致性问题，需要修复")
        return 1

if __name__ == "__main__":
    sys.exit(main())