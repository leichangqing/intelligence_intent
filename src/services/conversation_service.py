"""
对话管理服务
"""
from typing import Dict, List, Optional, Any
import json
from datetime import datetime, timedelta

from src.models.conversation import Session, Conversation, IntentAmbiguity, IntentTransfer
from src.services.cache_service import CacheService
from src.services.ragflow_service import RagflowService
from src.core.fallback_manager import (
    FallbackManager, FallbackType, FallbackContext, FallbackResult, get_fallback_manager
)
from src.core.intelligent_fallback_decision import (
    IntelligentFallbackDecisionEngine, DecisionContext, get_decision_engine
)
from src.utils.logger import get_logger

logger = get_logger(__name__)


class ConversationService:
    """对话管理服务类"""
    
    def __init__(self, cache_service: CacheService, ragflow_service: RagflowService = None):
        self.cache_service = cache_service
        self.cache_namespace = "conversation"
        self.ragflow_service = ragflow_service
        
        # TASK-032: 回退管理器和智能决策引擎
        self.fallback_manager = get_fallback_manager(cache_service)
        self.decision_engine = get_decision_engine(cache_service)
    
    async def get_or_create_session(self, user_id: str, session_id: Optional[str] = None) -> Session:
        """获取或创建会话
        
        Args:
            user_id: 用户ID
            session_id: 会话ID，如果为None则创建新会话
            
        Returns:
            Session: 会话对象
        """
        if session_id:
            # 尝试从缓存获取会话
            cache_key = f"session:{session_id}"
            cached_session = await self.cache_service.get(cache_key, namespace=self.cache_namespace)
            
            if cached_session:
                logger.debug(f"从缓存获取会话: {session_id}")
                # 将缓存数据转换为Session对象
                try:
                    session = Session.get_by_id(cached_session['id'])
                    return session
                except Session.DoesNotExist:
                    pass
            
            # 从数据库获取会话
            try:
                session = Session.get(
                    Session.session_id == session_id,
                    Session.user_id == user_id,
                    Session.is_active == True
                )
                
                # 缓存会话信息
                session_data = {
                    'id': session.id,
                    'session_id': session.session_id,
                    'user_id': session.user_id,
                    'context': session.get_context(),
                    'created_at': session.created_at.isoformat()
                }
                await self.cache_service.set(cache_key, session_data, 
                                           ttl=3600, namespace=self.cache_namespace)
                
                return session
            except Session.DoesNotExist:
                pass
        
        # 创建新会话
        import uuid
        new_session_id = session_id or f"sess_{uuid.uuid4().hex[:12]}"
        
        session = Session.create(
            session_id=new_session_id,
            user_id=user_id,
            context=json.dumps({}),
            status='active'
        )
        
        # 缓存新会话
        cache_key = f"session:{new_session_id}"
        session_data = {
            'id': session.id,
            'session_id': session.session_id,
            'user_id': session.user_id,
            'context': {},
            'created_at': session.created_at.isoformat()
        }
        await self.cache_service.set(cache_key, session_data, 
                                   ttl=3600, namespace=self.cache_namespace)
        
        logger.info(f"创建新会话: {new_session_id} for user: {user_id}")
        return session
    
    async def save_conversation(self, session_id: str, user_input: str, intent: Optional[str],
                              slots: Dict[str, Any], response: Dict[str, Any],
                              confidence: float = 0.0) -> Conversation:
        """保存对话记录
        
        Args:
            session_id: 会话ID
            user_input: 用户输入
            intent: 识别的意图
            slots: 槽位信息
            response: 系统响应
            confidence: 置信度
            
        Returns:
            Conversation: 对话记录对象
        """
        # 获取会话
        try:
            session = Session.get(Session.session_id == session_id)
        except Session.DoesNotExist:
            logger.error(f"会话不存在: {session_id}")
            raise ValueError(f"会话不存在: {session_id}")
        
        # 创建对话记录
        conversation = Conversation.create(
            session=session,
            user_input=user_input,
            intent=intent,
            slots=json.dumps(slots, ensure_ascii=False),
            confidence=confidence,
            response=json.dumps(response, ensure_ascii=False),
            response_type=response.get('type', 'text')
        )
        
        # 更新会话的最后活动时间
        session.updated_at = datetime.now()
        session.save()
        
        # 更新缓存中的会话信息
        cache_key = f"session:{session_id}"
        await self.cache_service.delete(cache_key, namespace=self.cache_namespace)
        
        logger.info(f"保存对话记录: session={session_id}, intent={intent}")
        return conversation
    
    async def get_conversation_history(self, session_id: str, limit: int = 10) -> List[Dict[str, Any]]:
        """获取对话历史
        
        Args:
            session_id: 会话ID
            limit: 返回记录数限制
            
        Returns:
            List[Dict]: 对话历史列表
        """
        # 尝试从缓存获取
        cache_key = f"history:{session_id}:{limit}"
        cached_history = await self.cache_service.get(cache_key, namespace=self.cache_namespace)
        
        if cached_history:
            logger.debug(f"从缓存获取对话历史: {session_id}")
            return cached_history
        
        # 从数据库获取
        try:
            session = Session.get(Session.session_id == session_id)
            conversations = (Conversation
                           .select()
                           .where(Conversation.session == session)
                           .order_by(Conversation.created_at.desc())
                           .limit(limit))
            
            history = []
            for conv in conversations:
                history.append({
                    'id': conv.id,
                    'user_input': conv.user_input,
                    'intent': conv.intent,
                    'slots': conv.get_slots(),
                    'response': conv.get_response(),
                    'confidence': float(conv.confidence),
                    'created_at': conv.created_at.isoformat()
                })
            
            # 按时间正序排列
            history.reverse()
            
            # 缓存历史记录
            await self.cache_service.set(cache_key, history, 
                                       ttl=300, namespace=self.cache_namespace)
            
            return history
            
        except Session.DoesNotExist:
            logger.warning(f"会话不存在: {session_id}")
            return []
    
    async def update_session_context(self, session_id: str, context_updates: Dict[str, Any]) -> bool:
        """更新会话上下文
        
        Args:
            session_id: 会话ID
            context_updates: 上下文更新内容
            
        Returns:
            bool: 更新是否成功
        """
        try:
            session = Session.get(Session.session_id == session_id)
            current_context = session.get_context()
            
            # 合并上下文
            current_context.update(context_updates)
            session.set_context(current_context)
            session.save()
            
            # 更新缓存
            cache_key = f"session:{session_id}"
            await self.cache_service.delete(cache_key, namespace=self.cache_namespace)
            
            logger.info(f"更新会话上下文: {session_id}")
            return True
            
        except Session.DoesNotExist:
            logger.error(f"会话不存在: {session_id}")
            return False
    
    async def record_intent_ambiguity(self, session_id: str, user_input: str,
                                    candidates: List[Dict[str, Any]]) -> IntentAmbiguity:
        """记录意图歧义
        
        Args:
            session_id: 会话ID
            user_input: 用户输入
            candidates: 候选意图列表
            
        Returns:
            IntentAmbiguity: 歧义记录对象
        """
        try:
            session = Session.get(Session.session_id == session_id)
            
            ambiguity = IntentAmbiguity.create(
                session=session,
                user_input=user_input,
                candidate_intents=json.dumps(candidates, ensure_ascii=False),
                status='pending'
            )
            
            logger.info(f"记录意图歧义: session={session_id}, candidates_count={len(candidates)}")
            return ambiguity
            
        except Session.DoesNotExist:
            logger.error(f"会话不存在: {session_id}")
            raise ValueError(f"会话不存在: {session_id}")
    
    async def resolve_intent_ambiguity(self, ambiguity_id: int, selected_intent: str) -> bool:
        """解决意图歧义
        
        Args:
            ambiguity_id: 歧义记录ID
            selected_intent: 用户选择的意图
            
        Returns:
            bool: 解决是否成功
        """
        try:
            ambiguity = IntentAmbiguity.get_by_id(ambiguity_id)
            ambiguity.selected_intent = selected_intent
            ambiguity.status = 'resolved'
            ambiguity.resolved_at = datetime.now()
            ambiguity.save()
            
            logger.info(f"解决意图歧义: ambiguity_id={ambiguity_id}, selected={selected_intent}")
            return True
            
        except IntentAmbiguity.DoesNotExist:
            logger.error(f"歧义记录不存在: {ambiguity_id}")
            return False
    
    async def record_intent_transfer(self, session_id: str, from_intent: str,
                                   to_intent: str, transfer_reason: str) -> IntentTransfer:
        """记录意图转换
        
        Args:
            session_id: 会话ID
            from_intent: 源意图
            to_intent: 目标意图
            transfer_reason: 转换原因
            
        Returns:
            IntentTransfer: 转换记录对象
        """
        try:
            session = Session.get(Session.session_id == session_id)
            
            transfer = IntentTransfer.create(
                session=session,
                from_intent=from_intent,
                to_intent=to_intent,
                transfer_reason=transfer_reason
            )
            
            logger.info(f"记录意图转换: {from_intent} -> {to_intent}, reason={transfer_reason}")
            return transfer
            
        except Session.DoesNotExist:
            logger.error(f"会话不存在: {session_id}")
            raise ValueError(f"会话不存在: {session_id}")
    
    async def end_session(self, session_id: str) -> bool:
        """结束会话
        
        Args:
            session_id: 会话ID
            
        Returns:
            bool: 结束是否成功
        """
        try:
            session = Session.get(Session.session_id == session_id)
            session.is_active = False
            session.status = 'ended'
            session.ended_at = datetime.now()
            session.save()
            
            # 清除相关缓存
            cache_keys = [
                f"session:{session_id}",
                f"history:{session_id}:*"
            ]
            
            for key in cache_keys:
                if '*' in key:
                    # 清除匹配的所有键
                    await self.cache_service.delete_pattern(key, namespace=self.cache_namespace)
                else:
                    await self.cache_service.delete(key, namespace=self.cache_namespace)
            
            logger.info(f"结束会话: {session_id}")
            return True
            
        except Session.DoesNotExist:
            logger.error(f"会话不存在: {session_id}")
            return False
    
    async def cleanup_expired_sessions(self, expiry_hours: int = 24) -> int:
        """清理过期会话
        
        Args:
            expiry_hours: 过期时间（小时）
            
        Returns:
            int: 清理的会话数量
        """
        expiry_time = datetime.now() - timedelta(hours=expiry_hours)
        
        # 查找过期的活跃会话
        expired_sessions = (Session
                          .select()
                          .where(
                              Session.is_active == True,
                              Session.updated_at < expiry_time
                          ))
        
        count = 0
        for session in expired_sessions:
            session.is_active = False
            session.status = 'expired'
            session.ended_at = datetime.now()
            session.save()
            
            # 清除缓存
            await self.cache_service.delete(f"session:{session.session_id}", 
                                          namespace=self.cache_namespace)
            count += 1
        
        logger.info(f"清理过期会话: {count} 个")
        return count
    
    async def get_session_statistics(self, user_id: Optional[str] = None) -> Dict[str, Any]:
        """获取会话统计信息
        
        Args:
            user_id: 用户ID，为None时统计所有用户
            
        Returns:
            Dict: 统计信息
        """
        cache_key = f"stats:session:{user_id or 'all'}"
        cached_stats = await self.cache_service.get(cache_key, namespace=self.cache_namespace)
        
        if cached_stats:
            return cached_stats
        
        # 构建查询条件
        conditions = []
        if user_id:
            conditions.append(Session.user_id == user_id)
        
        # 统计会话数据
        query = Session.select()
        if conditions:
            query = query.where(*conditions)
        
        total_sessions = query.count()
        active_sessions = query.where(Session.is_active == True).count()
        
        # 统计最近24小时的会话
        recent_time = datetime.now() - timedelta(hours=24)
        recent_sessions = query.where(Session.created_at >= recent_time).count()
        
        # 统计对话轮次
        conversations_query = (Conversation
                             .select()
                             .join(Session))
        if conditions:
            conversations_query = conversations_query.where(*conditions)
        
        total_conversations = conversations_query.count()
        
        stats = {
            'total_sessions': total_sessions,
            'active_sessions': active_sessions,
            'recent_sessions': recent_sessions,
            'total_conversations': total_conversations,
            'avg_conversations_per_session': (
                total_conversations / total_sessions if total_sessions > 0 else 0
            ),
            'updated_at': datetime.now().isoformat()
        }
        
        # 缓存统计数据
        await self.cache_service.set(cache_key, stats, ttl=300, namespace=self.cache_namespace)
        
        return stats
    
    async def call_ragflow(self, user_input: str, session_context: Dict[str, Any], 
                          config_name: str = "default") -> Dict[str, Any]:
        """调用RAGFLOW服务进行知识库查询
        
        Args:
            user_input: 用户输入
            session_context: 会话上下文
            config_name: RAGFLOW配置名称
            
        Returns:
            Dict: RAGFLOW响应结果
        """
        try:
            if not self.ragflow_service:
                raise Exception("RAGFLOW服务未初始化")
            
            # 构建查询上下文
            query_context = {
                'session_id': session_context.get('session_id'),
                'user_id': session_context.get('user_id'),
                'conversation_history': session_context.get('conversation_history', []),
                'current_intent': session_context.get('current_intent'),
                'current_slots': session_context.get('current_slots', {}),
                'timestamp': datetime.now().isoformat()
            }
            
            # 调用智能化RAGFLOW服务 (TASK-031)
            response = await self.ragflow_service.query_knowledge_base_intelligent(
                query=user_input,
                session_context=query_context,
                config_name=config_name
            )
            
            if response.success:
                # 返回成功响应
                return {
                    'answer': response.data,
                    'source_documents': response.source_documents,
                    'response_time': response.response_time,
                    'confidence': self._calculate_ragflow_confidence(response),
                    'config_used': config_name
                }
            else:
                # 返回错误响应
                logger.error(f"RAGFLOW查询失败: {response.error}")
                return {
                    'answer': None,
                    'error': response.error,
                    'response_time': response.response_time,
                    'confidence': 0.0,
                    'config_used': config_name
                }
                
        except Exception as e:
            logger.error(f"RAGFLOW调用异常: {str(e)}")
            
            # 使用高级回退系统处理RAGFLOW调用异常 (TASK-032)
            try:
                fallback_result = await self._handle_ragflow_fallback(
                    user_input, session_context, config_name, str(e)
                )
                
                if fallback_result.get('answer'):
                    return fallback_result
                    
            except Exception as fallback_error:
                logger.error(f"RAGFLOW回退处理失败: {str(fallback_error)}")
            
            # 最终回退响应
            return {
                'answer': None,
                'error': str(e),
                'response_time': 0.0,
                'confidence': 0.0,
                'config_used': config_name
            }
    
    def _calculate_ragflow_confidence(self, response) -> float:
        """计算RAGFLOW响应的置信度
        
        Args:
            response: RAGFLOW响应对象
            
        Returns:
            float: 置信度分数 (0.0-1.0)
        """
        try:
            if not response.success or not response.data:
                return 0.0
            
            # 基础置信度
            base_confidence = 0.6
            
            # 根据响应时间调整置信度
            if response.response_time < 1.0:
                time_bonus = 0.1
            elif response.response_time < 3.0:
                time_bonus = 0.05
            else:
                time_bonus = 0.0
            
            # 根据源文档数量调整置信度
            source_count = len(response.source_documents)
            if source_count > 0:
                source_bonus = min(0.2, source_count * 0.1)
            else:
                source_bonus = 0.0
            
            # 根据答案长度调整置信度
            if response.data:
                answer_length = len(str(response.data))
                if answer_length > 50:
                    length_bonus = 0.1
                elif answer_length > 20:
                    length_bonus = 0.05
                else:
                    length_bonus = 0.0
            else:
                length_bonus = 0.0
            
            # 计算最终置信度
            final_confidence = base_confidence + time_bonus + source_bonus + length_bonus
            
            # 确保置信度在0.0-1.0范围内
            return min(1.0, max(0.0, final_confidence))
            
        except Exception as e:
            logger.warning(f"计算RAGFLOW置信度失败: {str(e)}")
            return 0.5  # 默认置信度
    
    async def _handle_ragflow_fallback(self, user_input: str, session_context: Dict[str, Any], 
                                     config_name: str, error_message: str) -> Dict[str, Any]:
        """处理RAGFLOW调用失败的回退逻辑 (TASK-032)"""
        try:
            # 构建回退上下文
            fallback_context = FallbackContext(
                error_type=FallbackType.RAGFLOW_QUERY,
                error_message=error_message,
                original_request={
                    'user_input': user_input,
                    'config_name': config_name,
                    'session_context': session_context
                },
                session_context=session_context,
                user_id=session_context.get('user_id', 'unknown'),
                session_id=session_context.get('session_id', 'unknown'),
                metadata={
                    'service': 'conversation',
                    'method': 'call_ragflow'
                }
            )
            
            # 使用智能决策引擎选择最佳回退策略
            decision_context = DecisionContext(
                fallback_context=fallback_context,
                available_strategies=self.fallback_manager.fallback_rules[FallbackType.RAGFLOW_QUERY].strategies,
                historical_performance={},
                system_metrics={},
                user_profile={'user_id': session_context.get('user_id', 'unknown')},
                business_rules={}
            )
            
            decision_result = await self.decision_engine.make_decision(decision_context)
            logger.info(f"对话服务RAGFLOW回退决策: {decision_result.recommended_strategy.value}")
            
            # 执行回退
            fallback_result = await self.fallback_manager.handle_fallback(fallback_context)
            
            # 更新策略性能
            if decision_result.recommended_strategy:
                await self.decision_engine.update_strategy_performance(
                    decision_result.recommended_strategy, 
                    fallback_result
                )
            
            # 转换为对话服务响应格式
            if fallback_result.success:
                return {
                    'answer': fallback_result.data,
                    'source_documents': [],
                    'response_time': fallback_result.response_time,
                    'confidence': fallback_result.confidence,
                    'config_used': config_name,
                    'fallback_used': True,
                    'fallback_strategy': decision_result.recommended_strategy.value
                }
            else:
                return {
                    'answer': None,
                    'error': fallback_result.error,
                    'response_time': fallback_result.response_time,
                    'confidence': 0.0,
                    'config_used': config_name,
                    'fallback_used': True,
                    'fallback_strategy': decision_result.recommended_strategy.value
                }
                
        except Exception as e:
            logger.error(f"RAGFLOW回退处理失败: {str(e)}")
            return {
                'answer': "抱歉，我暂时无法回答您的问题，请稍后再试。",
                'error': str(e),
                'response_time': 0.0,
                'confidence': 0.1,
                'config_used': config_name,
                'fallback_used': True,
                'fallback_strategy': 'emergency_fallback'
            }