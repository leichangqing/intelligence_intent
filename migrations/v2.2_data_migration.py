#!/usr/bin/env python3
"""
V2.2数据迁移脚本
从conversations表的JSON字段迁移到slot_values表的Python实现

用途：
1. 安全的槽位数据迁移
2. 数据一致性验证
3. 回滚支持
4. 详细的迁移报告
"""

import asyncio
import json
import logging
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple
import argparse
import sys
import os

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.config.database import get_database_connection
from src.models.conversation import Conversation, Session
from src.models.slot_value import SlotValue
from src.services.audit_service import get_audit_service
from src.utils.logger import get_logger

logger = get_logger(__name__)


class V22MigrationResult:
    """V2.2迁移结果"""
    def __init__(self):
        self.start_time = datetime.now()
        self.end_time: Optional[datetime] = None
        
        # 统计数据
        self.total_conversations = 0
        self.conversations_with_slots = 0
        self.migrated_conversations = 0
        self.failed_conversations = 0
        
        self.total_slot_values = 0
        self.migrated_slot_values = 0
        self.failed_slot_values = 0
        
        # 错误记录
        self.errors: List[Dict[str, Any]] = []
        self.warnings: List[Dict[str, Any]] = []
        
    def add_error(self, conversation_id: int, error: str, details: Dict[str, Any] = None):
        """添加错误记录"""
        self.errors.append({
            'conversation_id': conversation_id,
            'error': error,
            'details': details or {},
            'timestamp': datetime.now().isoformat()
        })
        
    def add_warning(self, conversation_id: int, warning: str, details: Dict[str, Any] = None):
        """添加警告记录"""
        self.warnings.append({
            'conversation_id': conversation_id,
            'warning': warning,
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
            'migration_info': {
                'version': 'v2.2',
                'start_time': self.start_time.isoformat(),
                'end_time': self.end_time.isoformat() if self.end_time else None,
                'execution_time_seconds': execution_time
            },
            'conversation_stats': {
                'total_conversations': self.total_conversations,
                'conversations_with_slots': self.conversations_with_slots,
                'migrated_conversations': self.migrated_conversations,
                'failed_conversations': self.failed_conversations,
                'migration_success_rate': (
                    self.migrated_conversations / max(self.conversations_with_slots, 1) * 100
                )
            },
            'slot_value_stats': {
                'total_slot_values': self.total_slot_values,
                'migrated_slot_values': self.migrated_slot_values,
                'failed_slot_values': self.failed_slot_values,
                'slot_migration_success_rate': (
                    self.migrated_slot_values / max(self.total_slot_values, 1) * 100
                )
            },
            'issues': {
                'errors_count': len(self.errors),
                'warnings_count': len(self.warnings),
                'errors': self.errors[-10:] if self.errors else [],  # 最近10个错误
                'warnings': self.warnings[-10:] if self.warnings else []  # 最近10个警告
            }
        }


class V22DataMigrator:
    """V2.2数据迁移器"""
    
    def __init__(self, dry_run: bool = False, batch_size: int = 100):
        self.dry_run = dry_run
        self.batch_size = batch_size
        self.audit_service = get_audit_service()
        
    async def migrate_all_data(self) -> V22MigrationResult:
        """
        迁移所有数据
        
        Returns:
            V22MigrationResult: 迁移结果
        """
        result = V22MigrationResult()
        
        try:
            logger.info(f"开始V2.2数据迁移 (dry_run={self.dry_run})")
            
            # 1. 预检查
            await self._pre_migration_check(result)
            
            # 2. 创建备份（如果不是试运行）
            if not self.dry_run:
                await self._create_backup_tables()
            
            # 3. 迁移槽位数据
            await self._migrate_slot_data(result)
            
            # 4. 验证迁移结果
            await self._verify_migration(result)
            
            # 5. 记录迁移完成
            if not self.dry_run:
                await self._record_migration_completion(result)
            
            result.complete()
            logger.info(f"V2.2数据迁移完成: {result.get_summary()}")
            return result
            
        except Exception as e:
            result.complete()
            logger.error(f"V2.2数据迁移失败: {str(e)}")
            result.add_error(0, f"Migration failed: {str(e)}", {'exception_type': type(e).__name__})
            raise
    
    async def _pre_migration_check(self, result: V22MigrationResult):
        """迁移前检查"""
        logger.info("执行迁移前检查...")
        
        # 统计需要迁移的数据
        conversations = list(
            Conversation.select().where(
                (Conversation.slots_filled.is_null(False)) |
                (Conversation.slots_missing.is_null(False))
            )
        )
        
        result.total_conversations = Conversation.select().count()
        result.conversations_with_slots = len(conversations)
        
        # 估算槽位值数量
        for conversation in conversations:
            try:
                slots_filled = conversation.get_slots_filled()
                slots_missing = conversation.get_slots_missing()
                result.total_slot_values += len(slots_filled) + len(slots_missing)
            except Exception as e:
                result.add_warning(
                    conversation.id, 
                    f"Failed to count slots: {str(e)}"
                )
        
        logger.info(f"迁移前检查完成: {result.conversations_with_slots} 个对话包含槽位数据")
        
        # 检查slot_values表是否存在
        try:
            SlotValue.select().limit(1).execute()
        except Exception:
            raise Exception("slot_values表不存在或不可访问，请先运行SQL升级脚本")
    
    async def _create_backup_tables(self):
        """创建备份表"""
        logger.info("创建备份表...")
        
        # 这里可以添加额外的备份逻辑
        # 主要的备份逻辑在SQL脚本中完成
        pass
    
    async def _migrate_slot_data(self, result: V22MigrationResult):
        """迁移槽位数据"""
        logger.info("开始迁移槽位数据...")
        
        # 分批获取需要迁移的对话
        offset = 0
        while True:
            conversations = list(
                Conversation.select().where(
                    (Conversation.slots_filled.is_null(False)) |
                    (Conversation.slots_missing.is_null(False))
                ).offset(offset).limit(self.batch_size)
            )
            
            if not conversations:
                break
                
            # 处理当前批次
            for conversation in conversations:
                try:
                    await self._migrate_single_conversation(conversation, result)
                except Exception as e:
                    result.failed_conversations += 1
                    result.add_error(
                        conversation.id,
                        f"Failed to migrate conversation: {str(e)}",
                        {
                            'session_id': conversation.session.session_id,
                            'intent_name': conversation.intent_name
                        }
                    )
                    logger.error(f"迁移对话 {conversation.id} 失败: {str(e)}")
            
            offset += self.batch_size
            
            # 进度报告
            logger.info(f"已处理 {min(offset, result.conversations_with_slots)} / {result.conversations_with_slots} 个对话")
    
    async def _migrate_single_conversation(self, conversation: Conversation, result: V22MigrationResult):
        """迁移单个对话的槽位数据"""
        try:
            slots_filled = conversation.get_slots_filled()
            slots_missing = conversation.get_slots_missing()
            
            migrated_count = 0
            
            # 迁移已填充的槽位
            for slot_name, slot_value in slots_filled.items():
                if not self.dry_run:
                    try:
                        slot_value_record, created = SlotValue.get_or_create(
                            session_id=conversation.session.session_id,
                            conversation_id=conversation.id,
                            slot_name=slot_name,
                            defaults={
                                'intent_name': conversation.intent_name,
                                'slot_value': json.dumps(slot_value) if isinstance(slot_value, (dict, list)) else str(slot_value),
                                'validation_status': 'valid',
                                'confidence_score': max(float(conversation.confidence_score or 0.8), 0.8),
                                'extracted_from': 'migration_v21'
                            }
                        )
                        
                        if not created:
                            # 更新已存在的记录
                            slot_value_record.slot_value = json.dumps(slot_value) if isinstance(slot_value, (dict, list)) else str(slot_value)
                            slot_value_record.validation_status = 'valid'
                            slot_value_record.updated_at = datetime.now()
                            slot_value_record.save()
                        
                        migrated_count += 1
                        result.migrated_slot_values += 1
                        
                    except Exception as e:
                        result.failed_slot_values += 1
                        result.add_error(
                            conversation.id,
                            f"Failed to migrate filled slot '{slot_name}': {str(e)}",
                            {'slot_name': slot_name, 'slot_value': str(slot_value)[:100]}
                        )
                else:
                    migrated_count += 1
                    result.migrated_slot_values += 1
            
            # 迁移缺失的槽位
            for slot_name in slots_missing:
                if not self.dry_run:
                    try:
                        slot_value_record, created = SlotValue.get_or_create(
                            session_id=conversation.session.session_id,
                            conversation_id=conversation.id,
                            slot_name=slot_name,
                            defaults={
                                'intent_name': conversation.intent_name,
                                'slot_value': None,
                                'validation_status': 'missing',
                                'confidence_score': 0.0,
                                'extracted_from': 'migration_v21'
                            }
                        )
                        
                        if not created:
                            # 更新已存在的记录
                            slot_value_record.validation_status = 'missing'
                            slot_value_record.updated_at = datetime.now()
                            slot_value_record.save()
                        
                        migrated_count += 1
                        result.migrated_slot_values += 1
                        
                    except Exception as e:
                        result.failed_slot_values += 1
                        result.add_error(
                            conversation.id,
                            f"Failed to migrate missing slot '{slot_name}': {str(e)}",
                            {'slot_name': slot_name}
                        )
                else:
                    migrated_count += 1
                    result.migrated_slot_values += 1
            
            if migrated_count > 0:
                result.migrated_conversations += 1
                
            logger.debug(f"迁移对话 {conversation.id}: {migrated_count} 个槽位")
            
        except Exception as e:
            logger.error(f"迁移对话 {conversation.id} 时发生错误: {str(e)}")
            raise
    
    async def _verify_migration(self, result: V22MigrationResult):
        """验证迁移结果"""
        logger.info("验证迁移结果...")
        
        # 验证槽位值数量
        actual_slot_values = SlotValue.select().where(
            SlotValue.extracted_from == 'migration_v21'
        ).count()
        
        if not self.dry_run and actual_slot_values != result.migrated_slot_values:
            result.add_warning(
                0,
                f"Slot value count mismatch: expected {result.migrated_slot_values}, got {actual_slot_values}"
            )
        
        # 验证数据完整性
        conversations_with_migrated_slots = SlotValue.select(
            SlotValue.conversation_id
        ).where(
            SlotValue.conversation_id.is_null(False),
            SlotValue.extracted_from == 'migration_v21'
        ).distinct().count()
        
        if not self.dry_run and conversations_with_migrated_slots < result.migrated_conversations:
            result.add_warning(
                0,
                f"Some conversations may not have been fully migrated: {conversations_with_migrated_slots} / {result.migrated_conversations}"
            )
        
        logger.info("迁移结果验证完成")
    
    async def _record_migration_completion(self, result: V22MigrationResult):
        """记录迁移完成"""
        try:
            await self.audit_service.log_config_change(
                table_name='system_migration',
                record_id=0,
                action=self.audit_service.AuditAction.UPDATE,
                old_values={'version': 'v2.1'},
                new_values={
                    'version': 'v2.2',
                    'migration_type': 'slot_data_migration',
                    'migrated_conversations': result.migrated_conversations,
                    'migrated_slot_values': result.migrated_slot_values,
                    'execution_time_seconds': (datetime.now() - result.start_time).total_seconds(),
                    'dry_run': self.dry_run
                },
                operator_id='migration_script'
            )
        except Exception as e:
            logger.warning(f"记录迁移完成信息失败: {str(e)}")
    
    async def rollback_migration(self, before_time: datetime) -> Dict[str, Any]:
        """
        回滚迁移（删除指定时间后创建的槽位值记录）
        
        Args:
            before_time: 回滚时间点
            
        Returns:
            Dict: 回滚结果
        """
        try:
            logger.info(f"开始回滚V2.2迁移数据（时间点：{before_time}）")
            
            # 查找需要删除的记录
            records_to_delete = list(
                SlotValue.select().where(
                    SlotValue.created_at >= before_time,
                    SlotValue.extracted_from.in_(['migration_v21', 'session_migration'])
                )
            )
            
            deleted_count = 0
            for record in records_to_delete:
                record.delete_instance()
                deleted_count += 1
            
            # 记录回滚操作
            await self.audit_service.log_config_change(
                table_name='system_migration',
                record_id=0,
                action=self.audit_service.AuditAction.DELETE,
                old_values={'version': 'v2.2', 'deleted_records': deleted_count},
                new_values={'version': 'v2.1_restored'},
                operator_id='rollback_script'
            )
            
            result = {
                'deleted_records': deleted_count,
                'rollback_time': before_time.isoformat(),
                'executed_at': datetime.now().isoformat()
            }
            
            logger.info(f"回滚完成: {result}")
            return result
            
        except Exception as e:
            logger.error(f"迁移回滚失败: {str(e)}")
            raise


async def main():
    """主函数"""
    parser = argparse.ArgumentParser(description='V2.2数据迁移脚本')
    parser.add_argument('--dry-run', action='store_true', help='试运行模式（不实际修改数据）')
    parser.add_argument('--batch-size', type=int, default=100, help='批处理大小')
    parser.add_argument('--rollback', help='回滚到指定时间（格式：YYYY-MM-DD HH:MM:SS）')
    parser.add_argument('--verbose', action='store_true', help='详细输出')
    
    args = parser.parse_args()
    
    # 设置日志级别
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    migrator = V22DataMigrator(dry_run=args.dry_run, batch_size=args.batch_size)
    
    try:
        if args.rollback:
            # 回滚操作
            rollback_time = datetime.strptime(args.rollback, '%Y-%m-%d %H:%M:%S')
            result = await migrator.rollback_migration(rollback_time)
            print(f"回滚完成: {json.dumps(result, indent=2, ensure_ascii=False)}")
        else:
            # 正常迁移
            result = await migrator.migrate_all_data()
            summary = result.get_summary()
            
            print("\n" + "="*80)
            print("V2.2 数据迁移完成")
            print("="*80)
            print(json.dumps(summary, indent=2, ensure_ascii=False))
            
            if result.errors:
                print(f"\n⚠️  发现 {len(result.errors)} 个错误，请检查日志")
                return 1
            elif result.warnings:
                print(f"\n⚠️  发现 {len(result.warnings)} 个警告，请检查日志") 
                return 0
            else:
                print("\n✅ 迁移成功完成，无错误")
                return 0
                
    except Exception as e:
        print(f"\n❌ 迁移失败: {str(e)}")
        logger.exception("Migration failed with exception")
        return 1


if __name__ == '__main__':
    import asyncio
    exit_code = asyncio.run(main())
    sys.exit(exit_code)