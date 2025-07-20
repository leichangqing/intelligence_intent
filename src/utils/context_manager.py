"""
上下文管理器 (TASK-034)
提供会话上下文的管理、持久化和优化功能
"""
from typing import Dict, Any, Optional, List
import json
import time
from datetime import datetime, timedelta
from collections import defaultdict

from src.utils.logger import get_logger

logger = get_logger(__name__)


class ContextManager:
    """上下文管理器"""
    
    def __init__(self):
        # 内存中的会话上下文
        self.session_contexts: Dict[str, Dict[str, Any]] = {}
        self.context_history: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        self.last_access_time: Dict[str, float] = {}
        
        # 配置
        self.max_context_history = 10
        self.context_ttl = 3600 * 24  # 24小时
        self.auto_save_interval = 300  # 5分钟
    
    async def initialize_session_context(self, session_id: str, user_id: str, 
                                       initial_context: Dict[str, Any]) -> Dict[str, Any]:
        """
        初始化会话上下文
        
        Args:
            session_id: 会话ID
            user_id: 用户ID
            initial_context: 初始上下文
            
        Returns:
            Dict: 初始化后的上下文
        """
        try:
            # 默认上下文结构
            default_context = {
                "session_id": session_id,
                "user_id": user_id,
                "created_at": datetime.now().isoformat(),
                "last_updated": datetime.now().isoformat(),
                "conversation_history": [],
                "current_intent": None,
                "current_slots": {},
                "intent_stack": [],
                "user_preferences": {},
                "device_info": {},
                "location": {},
                "session_state": "active",
                "turn_count": 0,
                "context_version": 1
            }
            
            # 合并初始上下文
            if initial_context:
                default_context.update(initial_context)
            
            # 保存到内存
            self.session_contexts[session_id] = default_context
            self.last_access_time[session_id] = time.time()
            
            # 记录到历史
            self._record_context_history(session_id, default_context, "initialize")
            
            logger.info(f"初始化会话上下文: {session_id}, 用户: {user_id}")
            return default_context
            
        except Exception as e:
            logger.error(f"初始化会话上下文失败: {session_id}, 错误: {str(e)}")
            raise
    
    async def get_context(self, session_id: str) -> Optional[Dict[str, Any]]:
        """
        获取会话上下文
        
        Args:
            session_id: 会话ID
            
        Returns:
            Optional[Dict]: 会话上下文
        """
        try:
            # 更新访问时间
            self.last_access_time[session_id] = time.time()
            
            # 从内存获取
            context = self.session_contexts.get(session_id)
            if context:
                return context.copy()
            
            # 如果内存中没有，尝试从持久化存储加载
            context = await self._load_context_from_storage(session_id)
            if context:
                self.session_contexts[session_id] = context
                return context.copy()
            
            return None
            
        except Exception as e:
            logger.error(f"获取会话上下文失败: {session_id}, 错误: {str(e)}")
            return None
    
    async def update_context(self, session_id: str, updates: Dict[str, Any],
                           merge_strategy: str = "merge") -> Dict[str, Any]:
        """
        更新会话上下文
        
        Args:
            session_id: 会话ID
            updates: 更新内容
            merge_strategy: 合并策略 (merge/replace/append)
            
        Returns:
            Dict: 更新后的上下文
        """
        try:
            current_context = await self.get_context(session_id)
            if not current_context:
                raise ValueError(f"会话上下文不存在: {session_id}")
            
            # 备份当前上下文
            old_context = current_context.copy()
            
            # 根据策略合并
            if merge_strategy == "replace":
                # 完全替换（保留基础字段）
                basic_fields = ["session_id", "user_id", "created_at"]
                new_context = {k: v for k, v in current_context.items() if k in basic_fields}
                new_context.update(updates)
            elif merge_strategy == "append":
                # 追加到列表字段
                new_context = current_context.copy()
                for key, value in updates.items():
                    if key in new_context and isinstance(new_context[key], list):
                        if isinstance(value, list):
                            new_context[key].extend(value)
                        else:
                            new_context[key].append(value)
                    else:
                        new_context[key] = value
            else:  # merge
                # 深度合并
                new_context = self._deep_merge(current_context, updates)
            
            # 更新元数据
            new_context["last_updated"] = datetime.now().isoformat()
            new_context["context_version"] = new_context.get("context_version", 1) + 1
            
            # 保存到内存
            self.session_contexts[session_id] = new_context
            self.last_access_time[session_id] = time.time()
            
            # 记录变更历史
            changes = self._calculate_changes(old_context, new_context)
            self._record_context_history(session_id, new_context, "update", changes)
            
            logger.info(f"更新会话上下文: {session_id}, 策略: {merge_strategy}, 变更: {len(changes)}")
            return new_context.copy()
            
        except Exception as e:
            logger.error(f"更新会话上下文失败: {session_id}, 错误: {str(e)}")
            raise
    
    def _deep_merge(self, target: Dict[str, Any], source: Dict[str, Any]) -> Dict[str, Any]:
        """深度合并字典"""
        result = target.copy()
        
        for key, value in source.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = self._deep_merge(result[key], value)
            else:
                result[key] = value
        
        return result
    
    def _calculate_changes(self, old_context: Dict[str, Any], 
                          new_context: Dict[str, Any]) -> List[Dict[str, Any]]:
        """计算上下文变更"""
        changes = []
        
        # 检查新增和修改的字段
        for key, new_value in new_context.items():
            if key not in old_context:
                changes.append({
                    "field": key,
                    "action": "added",
                    "old_value": None,
                    "new_value": new_value
                })
            elif old_context[key] != new_value:
                changes.append({
                    "field": key,
                    "action": "modified",
                    "old_value": old_context[key],
                    "new_value": new_value
                })
        
        # 检查删除的字段
        for key, old_value in old_context.items():
            if key not in new_context:
                changes.append({
                    "field": key,
                    "action": "removed",
                    "old_value": old_value,
                    "new_value": None
                })
        
        return changes
    
    def _record_context_history(self, session_id: str, context: Dict[str, Any],
                               action: str, changes: List[Dict[str, Any]] = None):
        """记录上下文历史"""
        try:
            history_record = {
                "timestamp": datetime.now().isoformat(),
                "action": action,
                "context_version": context.get("context_version", 1),
                "changes": changes or [],
                "context_size": len(json.dumps(context))
            }
            
            # 添加到历史记录
            self.context_history[session_id].append(history_record)
            
            # 限制历史记录数量
            if len(self.context_history[session_id]) > self.max_context_history:
                self.context_history[session_id] = self.context_history[session_id][-self.max_context_history:]
                
        except Exception as e:
            logger.error(f"记录上下文历史失败: {session_id}, 错误: {str(e)}")
    
    async def add_conversation_turn(self, session_id: str, user_input: str,
                                  intent: Optional[str], slots: Dict[str, Any],
                                  response: str) -> bool:
        """
        添加对话轮次到上下文
        
        Args:
            session_id: 会话ID
            user_input: 用户输入
            intent: 识别的意图
            slots: 提取的槽位
            response: 系统响应
            
        Returns:
            bool: 是否成功
        """
        try:
            context = await self.get_context(session_id)
            if not context:
                return False
            
            # 创建对话记录
            turn_record = {
                "turn_index": context.get("turn_count", 0) + 1,
                "timestamp": datetime.now().isoformat(),
                "user_input": user_input,
                "intent": intent,
                "slots": slots,
                "response": response
            }
            
            # 更新上下文
            updates = {
                "conversation_history": context.get("conversation_history", []) + [turn_record],
                "turn_count": context.get("turn_count", 0) + 1,
                "current_intent": intent,
                "current_slots": slots
            }
            
            # 限制历史记录长度
            if len(updates["conversation_history"]) > 20:
                updates["conversation_history"] = updates["conversation_history"][-20:]
            
            await self.update_context(session_id, updates)
            return True
            
        except Exception as e:
            logger.error(f"添加对话轮次失败: {session_id}, 错误: {str(e)}")
            return False
    
    async def push_intent_stack(self, session_id: str, intent: str, context: Dict[str, Any]) -> bool:
        """
        推入意图栈（用于意图打岔处理）
        
        Args:
            session_id: 会话ID
            intent: 要推入的意图
            context: 意图上下文
            
        Returns:
            bool: 是否成功
        """
        try:
            current_context = await self.get_context(session_id)
            if not current_context:
                return False
            
            intent_record = {
                "intent": intent,
                "context": context,
                "pushed_at": datetime.now().isoformat()
            }
            
            intent_stack = current_context.get("intent_stack", [])
            intent_stack.append(intent_record)
            
            # 限制栈深度
            if len(intent_stack) > 5:
                intent_stack = intent_stack[-5:]
            
            await self.update_context(session_id, {"intent_stack": intent_stack})
            return True
            
        except Exception as e:
            logger.error(f"推入意图栈失败: {session_id}, 错误: {str(e)}")
            return False
    
    async def pop_intent_stack(self, session_id: str) -> Optional[Dict[str, Any]]:
        """
        弹出意图栈
        
        Args:
            session_id: 会话ID
            
        Returns:
            Optional[Dict]: 弹出的意图记录
        """
        try:
            current_context = await self.get_context(session_id)
            if not current_context:
                return None
            
            intent_stack = current_context.get("intent_stack", [])
            if not intent_stack:
                return None
            
            popped_intent = intent_stack.pop()
            await self.update_context(session_id, {"intent_stack": intent_stack})
            
            return popped_intent
            
        except Exception as e:
            logger.error(f"弹出意图栈失败: {session_id}, 错误: {str(e)}")
            return None
    
    async def cleanup_expired_contexts(self) -> int:
        """清理过期的上下文"""
        try:
            current_time = time.time()
            expired_sessions = []
            
            for session_id, last_access in self.last_access_time.items():
                if current_time - last_access > self.context_ttl:
                    expired_sessions.append(session_id)
            
            # 清理过期会话
            for session_id in expired_sessions:
                if session_id in self.session_contexts:
                    del self.session_contexts[session_id]
                if session_id in self.last_access_time:
                    del self.last_access_time[session_id]
                if session_id in self.context_history:
                    del self.context_history[session_id]
            
            logger.info(f"清理过期上下文: {len(expired_sessions)} 个")
            return len(expired_sessions)
            
        except Exception as e:
            logger.error(f"清理过期上下文失败: {str(e)}")
            return 0
    
    async def get_context_history(self, session_id: str) -> List[Dict[str, Any]]:
        """获取上下文变更历史"""
        return self.context_history.get(session_id, []).copy()
    
    async def export_context(self, session_id: str) -> Optional[Dict[str, Any]]:
        """导出完整的会话上下文"""
        try:
            context = await self.get_context(session_id)
            if not context:
                return None
            
            return {
                "context": context,
                "history": await self.get_context_history(session_id),
                "exported_at": datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"导出上下文失败: {session_id}, 错误: {str(e)}")
            return None
    
    async def get_statistics(self) -> Dict[str, Any]:
        """获取上下文管理统计"""
        try:
            active_sessions = len(self.session_contexts)
            total_history_records = sum(len(history) for history in self.context_history.values())
            
            # 计算平均上下文大小
            total_size = 0
            for context in self.session_contexts.values():
                total_size += len(json.dumps(context))
            
            avg_context_size = total_size / active_sessions if active_sessions > 0 else 0
            
            return {
                "active_sessions": active_sessions,
                "total_history_records": total_history_records,
                "average_context_size_bytes": avg_context_size,
                "max_context_history": self.max_context_history,
                "context_ttl_seconds": self.context_ttl
            }
            
        except Exception as e:
            logger.error(f"获取上下文统计失败: {str(e)}")
            return {}
    
    async def _load_context_from_storage(self, session_id: str) -> Optional[Dict[str, Any]]:
        """从持久化存储加载上下文（这里暂时返回None，实际实现可以从数据库加载）"""
        # TODO: 实现从数据库或文件系统加载上下文
        return None
    
    async def _save_context_to_storage(self, session_id: str, context: Dict[str, Any]) -> bool:
        """保存上下文到持久化存储（这里暂时返回True，实际实现可以保存到数据库）"""
        # TODO: 实现保存上下文到数据库或文件系统
        return True