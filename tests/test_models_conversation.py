"""
对话模型单元测试
"""
import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime
import json

from src.models.conversation import Session, Conversation, IntentAmbiguity, IntentTransfer


class TestSessionModel:
    """会话模型测试类"""
    
    def test_session_creation(self):
        """测试会话创建"""
        # 创建会话实例
        session = Session()
        session.session_id = "sess_123"
        session.user_id = "user_456"
        session.context = json.dumps({"current_intent": "greeting"})
        session.status = "active"
        
        # 验证会话属性
        assert session.session_id == "sess_123"
        assert session.user_id == "user_456"
        assert isinstance(session.context, str)
        assert session.status == "active"
    
    def test_session_get_context(self):
        """测试获取会话上下文"""
        # 创建会话实例
        session = Session()
        context_data = {
            "current_intent": "book_flight",
            "slots": {"origin": "北京", "destination": "上海"},
            "conversation_state": "collecting_slots"
        }
        session.context = json.dumps(context_data)
        
        # 获取上下文
        context = session.get_context()
        
        # 验证上下文
        assert isinstance(context, dict)
        assert context["current_intent"] == "book_flight"
        assert context["slots"]["origin"] == "北京"
        assert context["conversation_state"] == "collecting_slots"
    
    def test_session_set_context(self):
        """测试设置会话上下文"""
        # 创建会话实例
        session = Session()
        context_data = {
            "current_intent": "check_balance",
            "user_preferences": {"language": "zh"}
        }
        
        # 设置上下文
        session.set_context(context_data)
        
        # 验证上下文
        stored_context = session.get_context()
        assert stored_context == context_data
    
    def test_session_update_context(self):
        """测试更新会话上下文"""
        # 创建会话实例
        session = Session()
        initial_context = {
            "current_intent": "book_flight",
            "slots": {"origin": "北京"}
        }
        session.set_context(initial_context)
        
        # 更新上下文
        updates = {
            "slots": {"origin": "北京", "destination": "上海"},
            "conversation_state": "collecting_slots"
        }
        session.update_context(updates)
        
        # 验证更新
        context = session.get_context()
        assert context["current_intent"] == "book_flight"
        assert context["slots"]["destination"] == "上海"
        assert context["conversation_state"] == "collecting_slots"
    
    def test_session_clear_context(self):
        """测试清空会话上下文"""
        # 创建会话实例
        session = Session()
        session.context = json.dumps({"current_intent": "book_flight"})
        
        # 清空上下文
        session.clear_context()
        
        # 验证清空
        context = session.get_context()
        assert context == {}
    
    def test_session_is_active(self):
        """测试检查会话是否活跃"""
        # 创建活跃会话
        session = Session()
        session.status = "active"
        assert session.is_active() == True
        
        # 创建非活跃会话
        session.status = "inactive"
        assert session.is_active() == False
    
    def test_session_activate(self):
        """测试激活会话"""
        # 创建会话实例
        session = Session()
        session.status = "inactive"
        
        # 激活会话
        session.activate()
        
        # 验证激活
        assert session.status == "active"
        assert session.is_active() == True
    
    def test_session_deactivate(self):
        """测试停用会话"""
        # 创建会话实例
        session = Session()
        session.status = "active"
        
        # 停用会话
        session.deactivate()
        
        # 验证停用
        assert session.status == "inactive"
        assert session.is_active() == False
    
    def test_session_get_conversations(self):
        """测试获取会话对话"""
        # 创建会话实例
        session = Session()
        session.id = 1
        session.session_id = "sess_123"
        
        # 模拟对话数据
        mock_conversations = [
            MagicMock(user_input="你好", response="您好！"),
            MagicMock(user_input="我要订机票", response="好的，我帮您预订机票")
        ]
        
        with patch('src.models.conversation.Conversation') as mock_conv_model:
            mock_query = MagicMock()
            mock_query.where.return_value.order_by.return_value = mock_conversations
            mock_conv_model.select.return_value = mock_query
            
            # 获取对话
            conversations = session.get_conversations()
            
            # 验证对话
            assert len(conversations) == 2
            assert conversations[0].user_input == "你好"
            assert conversations[1].user_input == "我要订机票"
    
    def test_session_get_conversation_count(self):
        """测试获取对话数量"""
        # 创建会话实例
        session = Session()
        session.id = 1
        
        # 模拟对话数量
        with patch('src.models.conversation.Conversation') as mock_conv_model:
            mock_query = MagicMock()
            mock_query.where.return_value.count.return_value = 5
            mock_conv_model.select.return_value = mock_query
            
            # 获取对话数量
            count = session.get_conversation_count()
            
            # 验证数量
            assert count == 5
    
    def test_session_get_last_conversation(self):
        """测试获取最后一次对话"""
        # 创建会话实例
        session = Session()
        session.id = 1
        
        # 模拟最后一次对话
        mock_conversation = MagicMock(
            user_input="我要订机票",
            response="好的，我帮您预订机票",
            created_at=datetime.now()
        )
        
        with patch('src.models.conversation.Conversation') as mock_conv_model:
            mock_query = MagicMock()
            mock_query.where.return_value.order_by.return_value.first.return_value = mock_conversation
            mock_conv_model.select.return_value = mock_query
            
            # 获取最后一次对话
            last_conv = session.get_last_conversation()
            
            # 验证最后一次对话
            assert last_conv.user_input == "我要订机票"
            assert last_conv.response == "好的，我帮您预订机票"
    
    def test_session_to_dict(self):
        """测试会话转字典"""
        # 创建会话实例
        session = Session()
        session.id = 1
        session.session_id = "sess_123"
        session.user_id = "user_456"
        session.context = json.dumps({"current_intent": "greeting"})
        session.status = "active"
        session.created_at = datetime(2024, 1, 1, 10, 0, 0)
        
        # 转换为字典
        session_dict = session.to_dict()
        
        # 验证字典内容
        assert session_dict['id'] == 1
        assert session_dict['session_id'] == "sess_123"
        assert session_dict['user_id'] == "user_456"
        assert session_dict['context'] == {"current_intent": "greeting"}
        assert session_dict['status'] == "active"
        assert 'created_at' in session_dict


class TestConversationModel:
    """对话模型测试类"""
    
    def test_conversation_creation(self):
        """测试对话创建"""
        # 创建对话实例
        conversation = Conversation()
        conversation.session_id = "sess_123"
        conversation.user_id = "user_456"
        conversation.user_input = "我要订机票"
        conversation.intent_name = "book_flight"
        conversation.confidence = 0.9
        conversation.entities = json.dumps([{"entity": "action", "value": "book"}])
        conversation.response = "好的，我帮您预订机票"
        conversation.response_time = 0.15
        
        # 验证对话属性
        assert conversation.session_id == "sess_123"
        assert conversation.user_id == "user_456"
        assert conversation.user_input == "我要订机票"
        assert conversation.intent_name == "book_flight"
        assert conversation.confidence == 0.9
        assert isinstance(conversation.entities, str)
        assert conversation.response == "好的，我帮您预订机票"
        assert conversation.response_time == 0.15
    
    def test_conversation_get_entities(self):
        """测试获取对话实体"""
        # 创建对话实例
        conversation = Conversation()
        entities = [
            {"entity": "origin", "value": "北京", "confidence": 0.9},
            {"entity": "destination", "value": "上海", "confidence": 0.85}
        ]
        conversation.entities = json.dumps(entities)
        
        # 获取实体
        entities_list = conversation.get_entities()
        
        # 验证实体
        assert isinstance(entities_list, list)
        assert len(entities_list) == 2
        assert entities_list[0]["entity"] == "origin"
        assert entities_list[1]["entity"] == "destination"
    
    def test_conversation_set_entities(self):
        """测试设置对话实体"""
        # 创建对话实例
        conversation = Conversation()
        entities = [
            {"entity": "date", "value": "明天", "confidence": 0.8}
        ]
        
        # 设置实体
        conversation.set_entities(entities)
        
        # 验证实体
        stored_entities = conversation.get_entities()
        assert stored_entities == entities
    
    def test_conversation_add_entity(self):
        """测试添加对话实体"""
        # 创建对话实例
        conversation = Conversation()
        conversation.entities = json.dumps([{"entity": "origin", "value": "北京"}])
        
        # 添加实体
        conversation.add_entity("destination", "上海", 0.9)
        
        # 验证实体
        entities = conversation.get_entities()
        assert len(entities) == 2
        assert entities[1]["entity"] == "destination"
        assert entities[1]["value"] == "上海"
        assert entities[1]["confidence"] == 0.9
    
    def test_conversation_is_successful(self):
        """测试检查对话是否成功"""
        # 创建成功对话
        conversation = Conversation()
        conversation.success = True
        assert conversation.is_successful() == True
        
        # 创建失败对话
        conversation.success = False
        assert conversation.is_successful() == False
    
    def test_conversation_get_duration(self):
        """测试获取对话持续时间"""
        # 创建对话实例
        conversation = Conversation()
        conversation.response_time = 0.25
        
        # 获取持续时间
        duration = conversation.get_duration()
        
        # 验证持续时间
        assert duration == 0.25
    
    def test_conversation_is_fast_response(self):
        """测试检查是否快速响应"""
        # 创建快速响应对话
        conversation = Conversation()
        conversation.response_time = 0.1
        assert conversation.is_fast_response() == True
        
        # 创建慢速响应对话
        conversation.response_time = 2.0
        assert conversation.is_fast_response() == False
    
    def test_conversation_get_session(self):
        """测试获取对话会话"""
        # 创建对话实例
        conversation = Conversation()
        conversation.session_id = "sess_123"
        
        # 模拟会话数据
        mock_session = MagicMock(
            session_id="sess_123",
            user_id="user_456",
            status="active"
        )
        
        with patch('src.models.conversation.Session') as mock_session_model:
            mock_session_model.get.return_value = mock_session
            
            # 获取会话
            session = conversation.get_session()
            
            # 验证会话
            assert session.session_id == "sess_123"
            assert session.user_id == "user_456"
            assert session.status == "active"
    
    def test_conversation_to_dict(self):
        """测试对话转字典"""
        # 创建对话实例
        conversation = Conversation()
        conversation.id = 1
        conversation.session_id = "sess_123"
        conversation.user_input = "我要订机票"
        conversation.intent_name = "book_flight"
        conversation.confidence = 0.9
        conversation.entities = json.dumps([{"entity": "action", "value": "book"}])
        conversation.response = "好的，我帮您预订机票"
        conversation.response_time = 0.15
        conversation.success = True
        conversation.created_at = datetime(2024, 1, 1, 10, 0, 0)
        
        # 转换为字典
        conv_dict = conversation.to_dict()
        
        # 验证字典内容
        assert conv_dict['id'] == 1
        assert conv_dict['session_id'] == "sess_123"
        assert conv_dict['user_input'] == "我要订机票"
        assert conv_dict['intent_name'] == "book_flight"
        assert conv_dict['confidence'] == 0.9
        assert isinstance(conv_dict['entities'], list)
        assert conv_dict['response'] == "好的，我帮您预订机票"
        assert conv_dict['response_time'] == 0.15
        assert conv_dict['success'] == True


class TestIntentAmbiguityModel:
    """意图歧义模型测试类"""
    
    def test_intent_ambiguity_creation(self):
        """测试意图歧义创建"""
        # 创建意图歧义实例
        ambiguity = IntentAmbiguity()
        ambiguity.session_id = "sess_123"
        ambiguity.user_input = "我想处理机票"
        ambiguity.candidates = json.dumps([
            {"intent": "book_flight", "confidence": 0.7},
            {"intent": "check_flight", "confidence": 0.6}
        ])
        ambiguity.ambiguity_score = 0.1
        ambiguity.resolved_intent = "book_flight"
        ambiguity.resolution_method = "user_choice"
        ambiguity.clarification_question = "请问您是要预订机票还是查询机票？"
        
        # 验证意图歧义属性
        assert ambiguity.session_id == "sess_123"
        assert ambiguity.user_input == "我想处理机票"
        assert isinstance(ambiguity.candidates, str)
        assert ambiguity.ambiguity_score == 0.1
        assert ambiguity.resolved_intent == "book_flight"
        assert ambiguity.resolution_method == "user_choice"
        assert ambiguity.clarification_question == "请问您是要预订机票还是查询机票？"
    
    def test_intent_ambiguity_get_candidates(self):
        """测试获取歧义候选者"""
        # 创建意图歧义实例
        ambiguity = IntentAmbiguity()
        candidates = [
            {"intent": "book_flight", "confidence": 0.7, "description": "预订机票"},
            {"intent": "check_flight", "confidence": 0.6, "description": "查询机票"}
        ]
        ambiguity.candidates = json.dumps(candidates)
        
        # 获取候选者
        candidates_list = ambiguity.get_candidates()
        
        # 验证候选者
        assert isinstance(candidates_list, list)
        assert len(candidates_list) == 2
        assert candidates_list[0]["intent"] == "book_flight"
        assert candidates_list[1]["intent"] == "check_flight"
    
    def test_intent_ambiguity_set_candidates(self):
        """测试设置歧义候选者"""
        # 创建意图歧义实例
        ambiguity = IntentAmbiguity()
        candidates = [
            {"intent": "book_hotel", "confidence": 0.65},
            {"intent": "check_hotel", "confidence": 0.6}
        ]
        
        # 设置候选者
        ambiguity.set_candidates(candidates)
        
        # 验证候选者
        stored_candidates = ambiguity.get_candidates()
        assert stored_candidates == candidates
    
    def test_intent_ambiguity_is_resolved(self):
        """测试检查歧义是否已解决"""
        # 创建已解决的歧义
        ambiguity = IntentAmbiguity()
        ambiguity.resolved_intent = "book_flight"
        assert ambiguity.is_resolved() == True
        
        # 创建未解决的歧义
        ambiguity.resolved_intent = None
        assert ambiguity.is_resolved() == False
    
    def test_intent_ambiguity_resolve(self):
        """测试解决歧义"""
        # 创建意图歧义实例
        ambiguity = IntentAmbiguity()
        ambiguity.resolved_intent = None
        
        # 解决歧义
        ambiguity.resolve("book_flight", "user_choice", 0.9)
        
        # 验证解决
        assert ambiguity.resolved_intent == "book_flight"
        assert ambiguity.resolution_method == "user_choice"
        assert ambiguity.resolution_confidence == 0.9
        assert ambiguity.resolved_at is not None
    
    def test_intent_ambiguity_get_top_candidate(self):
        """测试获取最高候选者"""
        # 创建意图歧义实例
        ambiguity = IntentAmbiguity()
        candidates = [
            {"intent": "book_flight", "confidence": 0.7},
            {"intent": "check_flight", "confidence": 0.6},
            {"intent": "cancel_flight", "confidence": 0.5}
        ]
        ambiguity.candidates = json.dumps(candidates)
        
        # 获取最高候选者
        top_candidate = ambiguity.get_top_candidate()
        
        # 验证最高候选者
        assert top_candidate["intent"] == "book_flight"
        assert top_candidate["confidence"] == 0.7
    
    def test_intent_ambiguity_get_confidence_gap(self):
        """测试获取置信度差距"""
        # 创建意图歧义实例
        ambiguity = IntentAmbiguity()
        candidates = [
            {"intent": "book_flight", "confidence": 0.7},
            {"intent": "check_flight", "confidence": 0.6}
        ]
        ambiguity.candidates = json.dumps(candidates)
        
        # 获取置信度差距
        gap = ambiguity.get_confidence_gap()
        
        # 验证置信度差距
        assert gap == 0.1
    
    def test_intent_ambiguity_to_dict(self):
        """测试意图歧义转字典"""
        # 创建意图歧义实例
        ambiguity = IntentAmbiguity()
        ambiguity.id = 1
        ambiguity.session_id = "sess_123"
        ambiguity.user_input = "我想处理机票"
        ambiguity.candidates = json.dumps([
            {"intent": "book_flight", "confidence": 0.7}
        ])
        ambiguity.ambiguity_score = 0.1
        ambiguity.resolved_intent = "book_flight"
        ambiguity.resolution_method = "user_choice"
        ambiguity.created_at = datetime(2024, 1, 1, 10, 0, 0)
        
        # 转换为字典
        ambiguity_dict = ambiguity.to_dict()
        
        # 验证字典内容
        assert ambiguity_dict['id'] == 1
        assert ambiguity_dict['session_id'] == "sess_123"
        assert ambiguity_dict['user_input'] == "我想处理机票"
        assert isinstance(ambiguity_dict['candidates'], list)
        assert ambiguity_dict['ambiguity_score'] == 0.1
        assert ambiguity_dict['resolved_intent'] == "book_flight"
        assert ambiguity_dict['resolution_method'] == "user_choice"


class TestIntentTransferModel:
    """意图转移模型测试类"""
    
    def test_intent_transfer_creation(self):
        """测试意图转移创建"""
        # 创建意图转移实例
        transfer = IntentTransfer()
        transfer.session_id = "sess_123"
        transfer.from_intent = "book_flight"
        transfer.to_intent = "check_balance"
        transfer.transfer_reason = "user_request"
        transfer.context_preserved = True
        transfer.confidence = 0.9
        
        # 验证意图转移属性
        assert transfer.session_id == "sess_123"
        assert transfer.from_intent == "book_flight"
        assert transfer.to_intent == "check_balance"
        assert transfer.transfer_reason == "user_request"
        assert transfer.context_preserved == True
        assert transfer.confidence == 0.9
    
    def test_intent_transfer_is_successful(self):
        """测试检查意图转移是否成功"""
        # 创建成功转移
        transfer = IntentTransfer()
        transfer.success = True
        assert transfer.is_successful() == True
        
        # 创建失败转移
        transfer.success = False
        assert transfer.is_successful() == False
    
    def test_intent_transfer_get_transfer_type(self):
        """测试获取转移类型"""
        # 创建意图转移实例
        transfer = IntentTransfer()
        transfer.from_intent = "book_flight"
        transfer.to_intent = "check_balance"
        
        # 获取转移类型
        transfer_type = transfer.get_transfer_type()
        
        # 验证转移类型
        assert transfer_type == "cross_domain"  # 不同域的转移
    
    def test_intent_transfer_get_context_data(self):
        """测试获取上下文数据"""
        # 创建意图转移实例
        transfer = IntentTransfer()
        context_data = {
            "previous_slots": {"origin": "北京", "destination": "上海"},
            "user_preferences": {"language": "zh"}
        }
        transfer.context_data = json.dumps(context_data)
        
        # 获取上下文数据
        context = transfer.get_context_data()
        
        # 验证上下文数据
        assert isinstance(context, dict)
        assert context["previous_slots"]["origin"] == "北京"
        assert context["user_preferences"]["language"] == "zh"
    
    def test_intent_transfer_set_context_data(self):
        """测试设置上下文数据"""
        # 创建意图转移实例
        transfer = IntentTransfer()
        context_data = {
            "preserved_data": {"user_id": "123", "session_state": "active"}
        }
        
        # 设置上下文数据
        transfer.set_context_data(context_data)
        
        # 验证上下文数据
        stored_context = transfer.get_context_data()
        assert stored_context == context_data
    
    def test_intent_transfer_to_dict(self):
        """测试意图转移转字典"""
        # 创建意图转移实例
        transfer = IntentTransfer()
        transfer.id = 1
        transfer.session_id = "sess_123"
        transfer.from_intent = "book_flight"
        transfer.to_intent = "check_balance"
        transfer.transfer_reason = "user_request"
        transfer.context_preserved = True
        transfer.confidence = 0.9
        transfer.success = True
        transfer.created_at = datetime(2024, 1, 1, 10, 0, 0)
        
        # 转换为字典
        transfer_dict = transfer.to_dict()
        
        # 验证字典内容
        assert transfer_dict['id'] == 1
        assert transfer_dict['session_id'] == "sess_123"
        assert transfer_dict['from_intent'] == "book_flight"
        assert transfer_dict['to_intent'] == "check_balance"
        assert transfer_dict['transfer_reason'] == "user_request"
        assert transfer_dict['context_preserved'] == True
        assert transfer_dict['confidence'] == 0.9
        assert transfer_dict['success'] == True