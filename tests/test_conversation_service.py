"""
对话服务单元测试
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timedelta
import json
import uuid

from src.services.conversation_service import ConversationService
from src.models.conversation import Session, Conversation, IntentAmbiguity, IntentTransfer
from src.services.cache_service import CacheService
from src.services.ragflow_service import RagflowService


class TestConversationService:
    """对话服务测试类"""
    
    @pytest.fixture
    def mock_cache_service(self):
        """模拟缓存服务"""
        return AsyncMock(spec=CacheService)
    
    @pytest.fixture
    def mock_ragflow_service(self):
        """模拟RAGFLOW服务"""
        return AsyncMock(spec=RagflowService)
    
    @pytest.fixture
    def conversation_service(self, mock_cache_service, mock_ragflow_service):
        """创建对话服务实例"""
        with patch('src.services.conversation_service.get_fallback_manager'), \
             patch('src.services.conversation_service.get_decision_engine'):
            service = ConversationService(mock_cache_service, mock_ragflow_service)
            return service
    
    @pytest.mark.asyncio
    async def test_get_existing_session_from_cache(self, conversation_service, mock_cache_service):
        """测试从缓存获取现有会话"""
        # 准备测试数据
        user_id = "user123"
        session_id = "sess_abc123"
        cached_session = {
            'id': 1,
            'session_id': session_id,
            'user_id': user_id,
            'context': {},
            'created_at': datetime.now().isoformat()
        }
        
        # 设置模拟行为
        mock_cache_service.get.return_value = cached_session
        
        # 创建模拟Session对象
        mock_session = MagicMock()
        mock_session.id = 1
        mock_session.session_id = session_id
        mock_session.user_id = user_id
        
        with patch('src.services.conversation_service.Session') as mock_session_model:
            mock_session_model.get_by_id.return_value = mock_session
            
            # 调用方法
            result = await conversation_service.get_or_create_session(user_id, session_id)
            
            # 验证结果
            assert result == mock_session
            mock_cache_service.get.assert_called_once_with(f"session:{session_id}", 
                                                         namespace="conversation")
    
    @pytest.mark.asyncio
    async def test_get_existing_session_from_database(self, conversation_service, mock_cache_service):
        """测试从数据库获取现有会话"""
        # 准备测试数据
        user_id = "user123"
        session_id = "sess_def456"
        
        # 设置模拟行为 - 缓存中没有数据
        mock_cache_service.get.return_value = None
        
        # 创建模拟Session对象
        mock_session = MagicMock()
        mock_session.id = 1
        mock_session.session_id = session_id
        mock_session.user_id = user_id
        mock_session.created_at = datetime.now()
        mock_session.get_context.return_value = {}
        
        with patch('src.services.conversation_service.Session') as mock_session_model:
            mock_session_model.get.return_value = mock_session
            
            # 调用方法
            result = await conversation_service.get_or_create_session(user_id, session_id)
            
            # 验证结果
            assert result == mock_session
            
            # 验证缓存被设置
            mock_cache_service.set.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_create_new_session(self, conversation_service, mock_cache_service):
        """测试创建新会话"""
        # 准备测试数据
        user_id = "user456"
        
        # 设置模拟行为
        mock_cache_service.get.return_value = None
        
        # 创建模拟Session对象
        mock_session = MagicMock()
        mock_session.id = 2
        mock_session.user_id = user_id
        mock_session.created_at = datetime.now()
        
        with patch('src.services.conversation_service.Session') as mock_session_model:
            # 数据库中不存在会话
            mock_session_model.get.side_effect = mock_session_model.DoesNotExist
            mock_session_model.create.return_value = mock_session
            
            # 调用方法
            result = await conversation_service.get_or_create_session(user_id)
            
            # 验证结果
            assert result == mock_session
            
            # 验证Session.create被调用
            mock_session_model.create.assert_called_once()
            
            # 验证缓存被设置
            mock_cache_service.set.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_create_new_session_with_specific_id(self, conversation_service, mock_cache_service):
        """测试使用指定ID创建新会话"""
        # 准备测试数据
        user_id = "user789"
        session_id = "sess_custom123"
        
        # 设置模拟行为
        mock_cache_service.get.return_value = None
        
        # 创建模拟Session对象
        mock_session = MagicMock()
        mock_session.id = 3
        mock_session.session_id = session_id
        mock_session.user_id = user_id
        mock_session.created_at = datetime.now()
        
        with patch('src.services.conversation_service.Session') as mock_session_model:
            # 数据库中不存在会话
            mock_session_model.get.side_effect = mock_session_model.DoesNotExist
            mock_session_model.create.return_value = mock_session
            
            # 调用方法
            result = await conversation_service.get_or_create_session(user_id, session_id)
            
            # 验证结果
            assert result == mock_session
            
            # 验证Session.create被调用时使用了指定的session_id
            call_args = mock_session_model.create.call_args
            assert call_args[1]['session_id'] == session_id
    
    @pytest.mark.asyncio
    async def test_save_conversation(self, conversation_service, mock_cache_service):
        """测试保存对话记录"""
        # 准备测试数据
        conversation_data = {
            'session_id': 'sess_123',
            'user_id': 'user123',
            'user_input': '我想订机票',
            'intent_name': 'book_flight',
            'confidence': 0.85,
            'entities': [{'entity': 'action', 'value': 'book'}],
            'response': '好的，我帮您预订机票'
        }
        
        # 创建模拟Conversation对象
        mock_conversation = MagicMock()
        mock_conversation.id = 1
        
        with patch('src.services.conversation_service.Conversation') as mock_conversation_model:
            mock_conversation_model.create.return_value = mock_conversation
            
            # 调用方法
            result = await conversation_service.save_conversation(conversation_data)
            
            # 验证结果
            assert result == mock_conversation
            
            # 验证Conversation.create被调用
            mock_conversation_model.create.assert_called_once()
            
            # 验证缓存被更新
            mock_cache_service.delete.assert_called()
    
    @pytest.mark.asyncio
    async def test_get_conversation_history(self, conversation_service, mock_cache_service):
        """测试获取对话历史"""
        # 准备测试数据
        session_id = "sess_456"
        limit = 10
        
        # 设置模拟行为 - 缓存中没有数据
        mock_cache_service.get.return_value = None
        
        # 创建模拟对话记录
        mock_conversation1 = MagicMock()
        mock_conversation1.id = 1
        mock_conversation1.user_input = "我想订机票"
        mock_conversation1.response = "好的，我帮您预订机票"
        mock_conversation1.created_at = datetime.now()
        
        mock_conversation2 = MagicMock()
        mock_conversation2.id = 2
        mock_conversation2.user_input = "到北京的"
        mock_conversation2.response = "请问您希望什么时候出发？"
        mock_conversation2.created_at = datetime.now()
        
        conversations = [mock_conversation1, mock_conversation2]
        
        with patch('src.services.conversation_service.Conversation') as mock_conversation_model:
            mock_query = MagicMock()
            mock_query.where.return_value.order_by.return_value.limit.return_value = conversations
            mock_conversation_model.select.return_value = mock_query
            
            # 调用方法
            result = await conversation_service.get_conversation_history(session_id, limit)
            
            # 验证结果
            assert len(result) == 2
            assert result[0] == mock_conversation1
            assert result[1] == mock_conversation2
            
            # 验证缓存被设置
            mock_cache_service.set.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_get_conversation_history_from_cache(self, conversation_service, mock_cache_service):
        """测试从缓存获取对话历史"""
        # 准备测试数据
        session_id = "sess_789"
        limit = 5
        cached_history = [
            {
                'id': 1,
                'user_input': '我想订机票',
                'response': '好的，我帮您预订机票',
                'created_at': datetime.now().isoformat()
            }
        ]
        
        # 设置模拟行为
        mock_cache_service.get.return_value = cached_history
        
        # 调用方法
        result = await conversation_service.get_conversation_history(session_id, limit)
        
        # 验证结果
        assert len(result) == 1
        assert result[0]['user_input'] == '我想订机票'
        
        # 验证缓存被调用
        expected_cache_key = f"conversation_history:{session_id}:{limit}"
        mock_cache_service.get.assert_called_once_with(expected_cache_key, 
                                                     namespace="conversation")
    
    @pytest.mark.asyncio
    async def test_update_session_context(self, conversation_service, mock_cache_service):
        """测试更新会话上下文"""
        # 准备测试数据
        session_id = "sess_update"
        context_updates = {
            'current_intent': 'book_flight',
            'entities': {'destination': '北京', 'date': '明天'}
        }
        
        # 创建模拟Session对象
        mock_session = MagicMock()
        mock_session.id = 1
        mock_session.session_id = session_id
        mock_session.get_context.return_value = {'previous_intent': 'greeting'}
        
        with patch('src.services.conversation_service.Session') as mock_session_model:
            mock_session_model.get.return_value = mock_session
            
            # 调用方法
            await conversation_service.update_session_context(session_id, context_updates)
            
            # 验证Session.save被调用
            mock_session.save.assert_called_once()
            
            # 验证缓存被删除（强制刷新）
            mock_cache_service.delete.assert_called()
    
    @pytest.mark.asyncio
    async def test_save_intent_ambiguity(self, conversation_service):
        """测试保存意图歧义记录"""
        # 准备测试数据
        ambiguity_data = {
            'session_id': 'sess_ambiguous',
            'user_input': '我想处理机票',
            'candidates': [
                {'intent': 'book_flight', 'confidence': 0.7},
                {'intent': 'check_flight', 'confidence': 0.65}
            ],
            'ambiguity_score': 0.05,
            'clarification_question': '您是要预订机票还是查询机票？'
        }
        
        # 创建模拟IntentAmbiguity对象
        mock_ambiguity = MagicMock()
        mock_ambiguity.id = 1
        
        with patch('src.services.conversation_service.IntentAmbiguity') as mock_ambiguity_model:
            mock_ambiguity_model.create.return_value = mock_ambiguity
            
            # 调用方法
            result = await conversation_service.save_intent_ambiguity(ambiguity_data)
            
            # 验证结果
            assert result == mock_ambiguity
            
            # 验证IntentAmbiguity.create被调用
            mock_ambiguity_model.create.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_save_intent_transfer(self, conversation_service):
        """测试保存意图转移记录"""
        # 准备测试数据
        transfer_data = {
            'session_id': 'sess_transfer',
            'from_intent': 'book_flight',
            'to_intent': 'check_balance',
            'transfer_reason': 'user_request',
            'context_preserved': True
        }
        
        # 创建模拟IntentTransfer对象
        mock_transfer = MagicMock()
        mock_transfer.id = 1
        
        with patch('src.services.conversation_service.IntentTransfer') as mock_transfer_model:
            mock_transfer_model.create.return_value = mock_transfer
            
            # 调用方法
            result = await conversation_service.save_intent_transfer(transfer_data)
            
            # 验证结果
            assert result == mock_transfer
            
            # 验证IntentTransfer.create被调用
            mock_transfer_model.create.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_get_session_context(self, conversation_service, mock_cache_service):
        """测试获取会话上下文"""
        # 准备测试数据
        session_id = "sess_context"
        expected_context = {
            'current_intent': 'book_flight',
            'entities': {'destination': '北京'},
            'conversation_state': 'collecting_slots'
        }
        
        # 创建模拟Session对象
        mock_session = MagicMock()
        mock_session.get_context.return_value = expected_context
        
        with patch('src.services.conversation_service.Session') as mock_session_model:
            mock_session_model.get.return_value = mock_session
            
            # 调用方法
            result = await conversation_service.get_session_context(session_id)
            
            # 验证结果
            assert result == expected_context
    
    @pytest.mark.asyncio
    async def test_clear_session_context(self, conversation_service, mock_cache_service):
        """测试清空会话上下文"""
        # 准备测试数据
        session_id = "sess_clear"
        
        # 创建模拟Session对象
        mock_session = MagicMock()
        
        with patch('src.services.conversation_service.Session') as mock_session_model:
            mock_session_model.get.return_value = mock_session
            
            # 调用方法
            await conversation_service.clear_session_context(session_id)
            
            # 验证Session.save被调用
            mock_session.save.assert_called_once()
            
            # 验证缓存被清理
            mock_cache_service.delete.assert_called()
    
    @pytest.mark.asyncio
    async def test_end_session(self, conversation_service, mock_cache_service):
        """测试结束会话"""
        # 准备测试数据
        session_id = "sess_end"
        
        # 创建模拟Session对象
        mock_session = MagicMock()
        mock_session.is_active = True
        
        with patch('src.services.conversation_service.Session') as mock_session_model:
            mock_session_model.get.return_value = mock_session
            
            # 调用方法
            await conversation_service.end_session(session_id)
            
            # 验证会话被标记为非活跃
            assert mock_session.is_active == False
            mock_session.save.assert_called_once()
            
            # 验证缓存被清理
            mock_cache_service.delete.assert_called()
    
    @pytest.mark.asyncio
    async def test_error_handling(self, conversation_service, mock_cache_service):
        """测试错误处理"""
        # 准备测试数据
        user_id = "user_error"
        session_id = "sess_error"
        
        # 设置模拟行为 - 缓存和数据库都抛出异常
        mock_cache_service.get.side_effect = Exception("Cache error")
        
        with patch('src.services.conversation_service.Session') as mock_session_model:
            mock_session_model.get.side_effect = Exception("Database error")
            mock_session_model.create.side_effect = Exception("Create error")
            
            # 调用方法 - 应该抛出异常
            with pytest.raises(Exception):
                await conversation_service.get_or_create_session(user_id, session_id)