"""
槽位数据迁移工具 (V2.2重构)
从conversations表的JSON字段迁移到slot_values表
"""
import json
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime

from src.models.conversation import Conversation, Session
from src.models.slot_value import SlotValue
from src.services.slot_value_service import get_slot_value_service
from src.utils.logger import get_logger

logger = get_logger(__name__)


class SlotMigrationResult:
    """槽位迁移结果"""
    def __init__(self):
        self.total_conversations = 0
        self.migrated_conversations = 0
        self.failed_conversations = 0
        self.total_slot_values = 0
        self.migrated_slot_values = 0
        self.failed_slot_values = 0
        self.errors: List[Dict[str, Any]] = []
        self.start_time = datetime.now()
        self.end_time: Optional[datetime] = None
    
    def add_error(self, conversation_id: int, error: str, details: Dict[str, Any] = None):
        """添加错误记录"""
        self.errors.append({
            'conversation_id': conversation_id,
            'error': error,
            'details': details or {},
            'timestamp': datetime.now().isoformat()
        })
    
    def complete(self):
        """完成迁移"""
        self.end_time = datetime.now()
    
    def get_summary(self) -> Dict[str, Any]:
        """获取迁移摘要"""
        execution_time = (self.end_time - self.start_time).total_seconds() if self.end_time else 0
        
        return {
            'total_conversations': self.total_conversations,
            'migrated_conversations': self.migrated_conversations,
            'failed_conversations': self.failed_conversations,
            'migration_success_rate': (
                self.migrated_conversations / self.total_conversations * 100 
                if self.total_conversations > 0 else 0
            ),
            'total_slot_values': self.total_slot_values,
            'migrated_slot_values': self.migrated_slot_values,
            'failed_slot_values': self.failed_slot_values,
            'slot_migration_success_rate': (
                self.migrated_slot_values / self.total_slot_values * 100 
                if self.total_slot_values > 0 else 0
            ),
            'execution_time_seconds': execution_time,
            'errors_count': len(self.errors),
            'start_time': self.start_time.isoformat(),
            'end_time': self.end_time.isoformat() if self.end_time else None
        }


class SlotMigrationTool:
    """槽位迁移工具"""
    
    def __init__(self):
        self.slot_value_service = get_slot_value_service()
        self.logger = logger
    
    async def migrate_all_conversations(
        self,
        batch_size: int = 100,
        dry_run: bool = False,
        continue_on_error: bool = True
    ) -> SlotMigrationResult:
        """
        迁移所有对话记录的槽位数据
        
        Args:
            batch_size: 批处理大小
            dry_run: 是否为试运行模式
            continue_on_error: 遇到错误时是否继续
            
        Returns:
            SlotMigrationResult: 迁移结果
        """
        result = SlotMigrationResult()
        
        try:
            # 统计总数
            total_conversations = (
                Conversation
                .select()
                .where(
                    (Conversation.slots_filled.is_null(False)) |
                    (Conversation.slots_missing.is_null(False))
                )
                .count()
            )
            
            result.total_conversations = total_conversations
            
            if total_conversations == 0:
                self.logger.info("没有需要迁移的对话记录")
                result.complete()
                return result
            
            self.logger.info(f"开始槽位迁移: 总计 {total_conversations} 条对话记录")
            
            # 分批处理
            offset = 0
            while offset < total_conversations:
                conversations = list(
                    Conversation
                    .select()
                    .where(
                        (Conversation.slots_filled.is_null(False)) |
                        (Conversation.slots_missing.is_null(False))
                    )
                    .offset(offset)
                    .limit(batch_size)
                )
                
                if not conversations:
                    break
                
                for conversation in conversations:
                    try:
                        await self._migrate_single_conversation(conversation, result, dry_run)
                    except Exception as e:
                        result.failed_conversations += 1
                        result.add_error(
                            conversation.id,
                            f"迁移对话失败: {str(e)}",
                            {'slots_filled': conversation.get_slots_filled()}
                        )
                        
                        if not continue_on_error:
                            raise
                        
                        self.logger.error(f"迁移对话 {conversation.id} 失败: {str(e)}")
                
                offset += batch_size
                
                # 进度报告
                progress = min(offset, total_conversations)
                self.logger.info(f"迁移进度: {progress}/{total_conversations} "
                               f"({progress/total_conversations*100:.1f}%)")
            
            result.complete()
            self.logger.info(f"槽位迁移完成: {result.get_summary()}")
            return result
            
        except Exception as e:
            result.complete()
            self.logger.error(f"槽位迁移失败: {str(e)}")
            raise
    
    async def _migrate_single_conversation(
        self,
        conversation: Conversation,
        result: SlotMigrationResult,
        dry_run: bool
    ):
        """
        迁移单个对话记录的槽位数据
        
        Args:
            conversation: 对话记录
            result: 迁移结果对象
            dry_run: 是否为试运行模式
        """
        try:
            # 提取槽位数据
            slots_filled = conversation.get_slots_filled()
            slots_missing = conversation.get_slots_missing()
            
            # 统计槽位数量
            slot_count = len(slots_filled) + len(slots_missing)
            result.total_slot_values += slot_count
            
            if not slots_filled and not slots_missing:
                result.migrated_conversations += 1
                return
            
            if not dry_run:
                # 迁移填充的槽位
                for slot_name, slot_value in slots_filled.items():
                    try:
                        await self._migrate_slot_value(
                            conversation, slot_name, slot_value, 'filled'
                        )
                        result.migrated_slot_values += 1
                    except Exception as e:
                        result.failed_slot_values += 1
                        result.add_error(
                            conversation.id,
                            f"迁移槽位值失败: {slot_name}",
                            {'slot_value': slot_value, 'error': str(e)}
                        )
                
                # 迁移缺失的槽位
                for slot_name in slots_missing:
                    try:
                        await self._migrate_slot_value(
                            conversation, slot_name, None, 'missing'
                        )
                        result.migrated_slot_values += 1
                    except Exception as e:
                        result.failed_slot_values += 1
                        result.add_error(
                            conversation.id,
                            f"迁移缺失槽位失败: {slot_name}",
                            {'error': str(e)}
                        )
            else:
                # 试运行模式，只统计
                result.migrated_slot_values += slot_count
            
            result.migrated_conversations += 1
            
        except Exception as e:
            self.logger.error(f"迁移对话 {conversation.id} 时发生错误: {str(e)}")
            raise
    
    async def _migrate_slot_value(
        self,
        conversation: Conversation,
        slot_name: str,
        slot_value: Any,
        status: str
    ):
        """
        迁移单个槽位值
        
        Args:
            conversation: 对话记录
            slot_name: 槽位名称
            slot_value: 槽位值
            status: 槽位状态 ('filled' 或 'missing')
        """
        try:
            # 获取会话信息
            session = conversation.session
            
            # 确定验证状态
            validation_status = 'valid' if status == 'filled' else 'missing'
            
            # 创建槽位值记录
            slot_value_record = SlotValue.create(
                session_id=session.session_id,
                conversation_id=conversation.id,
                intent_name=conversation.intent_name,
                slot_name=slot_name,
                slot_value=slot_value,
                validation_status=validation_status,
                extracted_from='migration',
                confidence_score=0.9 if status == 'filled' else 0.0
            )
            
            self.logger.debug(f"迁移槽位: {slot_name} -> {slot_value_record.id}")
            
        except Exception as e:
            self.logger.error(f"创建槽位值记录失败: {str(e)}")
            raise
    
    async def verify_migration(self) -> Dict[str, Any]:
        """
        验证迁移结果的完整性
        
        Returns:
            Dict: 验证报告
        """
        try:
            # 统计原始数据
            conversations_with_slots = (
                Conversation
                .select()
                .where(
                    (Conversation.slots_filled.is_null(False)) |
                    (Conversation.slots_missing.is_null(False))
                )
                .count()
            )
            
            # 统计迁移后数据
            slot_values_count = SlotValue.select().count()
            migrated_conversations = (
                SlotValue
                .select(SlotValue.conversation_id)
                .distinct()
                .count()
            )
            
            # 检查数据一致性
            inconsistent_conversations = []
            
            # 抽样检查
            sample_conversations = list(
                Conversation
                .select()
                .where(
                    (Conversation.slots_filled.is_null(False)) |
                    (Conversation.slots_missing.is_null(False))
                )
                .limit(100)
            )
            
            for conversation in sample_conversations:
                original_slots = len(conversation.get_slots_filled()) + len(conversation.get_slots_missing())
                migrated_slots = SlotValue.select().where(
                    SlotValue.conversation_id == conversation.id
                ).count()
                
                if original_slots != migrated_slots:
                    inconsistent_conversations.append({
                        'conversation_id': conversation.id,
                        'original_slots': original_slots,
                        'migrated_slots': migrated_slots
                    })
            
            return {
                'original_conversations_with_slots': conversations_with_slots,
                'migrated_conversations': migrated_conversations,
                'total_slot_values': slot_values_count,
                'inconsistent_conversations': len(inconsistent_conversations),
                'inconsistent_details': inconsistent_conversations,
                'migration_integrity': (
                    len(inconsistent_conversations) == 0 and 
                    conversations_with_slots == migrated_conversations
                ),
                'verification_time': datetime.now().isoformat()
            }
            
        except Exception as e:
            self.logger.error(f"迁移验证失败: {str(e)}")
            raise
    
    async def rollback_migration(self, before_time: datetime) -> Dict[str, Any]:
        """
        回滚迁移操作（删除指定时间后创建的槽位值记录）
        
        Args:
            before_time: 回滚时间点
            
        Returns:
            Dict: 回滚结果
        """
        try:
            # 查找需要删除的记录
            records_to_delete = list(
                SlotValue
                .select()
                .where(SlotValue.created_at >= before_time)
            )
            
            deleted_count = 0
            
            for record in records_to_delete:
                record.delete_instance()
                deleted_count += 1
            
            return {
                'deleted_records': deleted_count,
                'rollback_time': before_time.isoformat(),
                'executed_at': datetime.now().isoformat()
            }
            
        except Exception as e:
            self.logger.error(f"迁移回滚失败: {str(e)}")
            raise


# 全局迁移工具实例
_migration_tool = None


def get_migration_tool() -> SlotMigrationTool:
    """获取迁移工具实例（单例模式）"""
    global _migration_tool
    if _migration_tool is None:
        _migration_tool = SlotMigrationTool()
    return _migration_tool