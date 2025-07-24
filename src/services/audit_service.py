"""
审计日志服务 (V2.2重构)
实现应用层的配置变更审计功能，替代原数据库触发器
"""
from typing import Dict, Any, Optional, List
import json
from datetime import datetime
from enum import Enum

from src.models.audit import ConfigAuditLog, SecurityAuditLog
from src.utils.logger import get_logger

logger = get_logger(__name__)


class AuditAction(Enum):
    """审计操作类型"""
    INSERT = "INSERT"
    UPDATE = "UPDATE"
    DELETE = "DELETE"


class AuditableTable(Enum):
    """可审计的表名"""
    INTENTS = "intents"
    SLOTS = "slots"
    FUNCTION_CALLS = "function_calls"
    PROMPT_TEMPLATES = "prompt_templates"
    SYSTEM_CONFIGS = "system_configs"
    RAGFLOW_CONFIGS = "ragflow_configs"
    USERS = "users"


class AuditService:
    """审计日志服务类"""
    
    def __init__(self):
        self.logger = logger
    
    async def log_config_change(
        self,
        table_name: str,
        record_id: int,
        action: AuditAction,
        old_values: Optional[Dict[str, Any]] = None,
        new_values: Optional[Dict[str, Any]] = None,
        operator_id: str = "system",
        operator_name: Optional[str] = None
    ) -> ConfigAuditLog:
        """
        记录配置变更审计日志
        
        Args:
            table_name: 表名
            record_id: 记录ID
            action: 操作类型
            old_values: 修改前的值
            new_values: 修改后的值
            operator_id: 操作者ID
            operator_name: 操作者姓名
            
        Returns:
            ConfigAuditLog: 审计日志记录
        """
        try:
            # 创建审计日志记录
            audit_log = ConfigAuditLog.create(
                table_name=table_name,
                record_id=record_id,
                action=action.value,
                old_values=old_values,  # JSONField可以直接存储dict
                new_values=new_values,  # JSONField可以直接存储dict
                operator_id=operator_id,
                operator_name=operator_name or self._get_operator_display_name(operator_id)
            )
            
            self.logger.info(
                f"记录审计日志成功: {table_name}.{record_id} {action.value} by {operator_id}"
            )
            
            return audit_log
            
        except Exception as e:
            self.logger.error(f"记录审计日志失败: {str(e)}")
            raise
    
    async def log_intent_change(
        self,
        intent_id: int,
        action: AuditAction,
        old_intent: Optional[Dict[str, Any]] = None,
        new_intent: Optional[Dict[str, Any]] = None,
        operator_id: str = "system"
    ) -> ConfigAuditLog:
        """记录意图变更审计日志"""
        return await self.log_config_change(
            table_name=AuditableTable.INTENTS.value,
            record_id=intent_id,
            action=action,
            old_values=self._extract_intent_audit_fields(old_intent) if old_intent else None,
            new_values=self._extract_intent_audit_fields(new_intent) if new_intent else None,
            operator_id=operator_id
        )
    
    async def log_slot_change(
        self,
        slot_id: int,
        action: AuditAction,
        old_slot: Optional[Dict[str, Any]] = None,
        new_slot: Optional[Dict[str, Any]] = None,
        operator_id: str = "system"
    ) -> ConfigAuditLog:
        """记录槽位变更审计日志"""
        return await self.log_config_change(
            table_name=AuditableTable.SLOTS.value,
            record_id=slot_id,
            action=action,
            old_values=self._extract_slot_audit_fields(old_slot) if old_slot else None,
            new_values=self._extract_slot_audit_fields(new_slot) if new_slot else None,
            operator_id=operator_id
        )
    
    async def log_system_config_change(
        self,
        config_id: int,
        action: AuditAction,
        old_config: Optional[Dict[str, Any]] = None,
        new_config: Optional[Dict[str, Any]] = None,
        operator_id: str = "system"
    ) -> ConfigAuditLog:
        """记录系统配置变更审计日志"""
        return await self.log_config_change(
            table_name=AuditableTable.SYSTEM_CONFIGS.value,
            record_id=config_id,
            action=action,
            old_values=self._extract_system_config_audit_fields(old_config) if old_config else None,
            new_values=self._extract_system_config_audit_fields(new_config) if new_config else None,
            operator_id=operator_id
        )
    
    async def get_audit_history(
        self,
        table_name: Optional[str] = None,
        record_id: Optional[int] = None,
        operator_id: Optional[str] = None,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """
        获取审计历史记录
        
        Args:
            table_name: 表名过滤
            record_id: 记录ID过滤
            operator_id: 操作者ID过滤
            limit: 返回记录数限制
            
        Returns:
            List[Dict]: 审计历史记录列表
        """
        try:
            query = ConfigAuditLog.select()
            
            # 应用过滤条件
            if table_name:
                query = query.where(ConfigAuditLog.table_name == table_name)
            if record_id:
                query = query.where(ConfigAuditLog.record_id == record_id)
            if operator_id:
                query = query.where(ConfigAuditLog.operator_id == operator_id)
            
            # 排序和限制
            audit_logs = (query
                         .order_by(ConfigAuditLog.created_at.desc())
                         .limit(limit))
            
            result = []
            for log in audit_logs:
                result.append({
                    'id': log.id,
                    'table_name': log.table_name,
                    'record_id': log.record_id,
                    'action': log.action,
                    'old_values': log.get_old_values(),
                    'new_values': log.get_new_values(),
                    'operator_id': log.operator_id,
                    'operator_name': log.operator_name,
                    'created_at': log.created_at.isoformat()
                })
            
            return result
            
        except Exception as e:
            self.logger.error(f"获取审计历史失败: {str(e)}")
            raise
    
    async def get_change_summary(
        self,
        days: int = 7
    ) -> Dict[str, Any]:
        """
        获取变更统计摘要
        
        Args:
            days: 统计天数
            
        Returns:
            Dict: 变更统计信息
        """
        try:
            from datetime import timedelta
            
            cutoff_time = datetime.now() - timedelta(days=days)
            
            query = ConfigAuditLog.select().where(ConfigAuditLog.created_at >= cutoff_time)
            
            # 按表名统计
            table_stats = {}
            action_stats = {}
            operator_stats = {}
            
            for log in query:
                # 表名统计
                if log.table_name not in table_stats:
                    table_stats[log.table_name] = 0
                table_stats[log.table_name] += 1
                
                # 操作类型统计
                if log.action not in action_stats:
                    action_stats[log.action] = 0
                action_stats[log.action] += 1
                
                # 操作者统计
                if log.operator_id not in operator_stats:
                    operator_stats[log.operator_id] = 0
                operator_stats[log.operator_id] += 1
            
            return {
                'period_days': days,
                'total_changes': sum(table_stats.values()),
                'table_stats': table_stats,
                'action_stats': action_stats,
                'operator_stats': operator_stats,
                'generated_at': datetime.now().isoformat()
            }
            
        except Exception as e:
            self.logger.error(f"获取变更统计失败: {str(e)}")
            raise
    
    def _extract_intent_audit_fields(self, intent_data: Dict[str, Any]) -> Dict[str, Any]:
        """提取意图审计关键字段"""
        if not intent_data:
            return {}
        
        return {
            'intent_name': intent_data.get('intent_name'),
            'display_name': intent_data.get('display_name'),
            'confidence_threshold': intent_data.get('confidence_threshold'),
            'priority': intent_data.get('priority'),
            'is_active': intent_data.get('is_active'),
            'category': intent_data.get('category')
        }
    
    def _extract_slot_audit_fields(self, slot_data: Dict[str, Any]) -> Dict[str, Any]:
        """提取槽位审计关键字段"""
        if not slot_data:
            return {}
        
        return {
            'intent_id': slot_data.get('intent_id'),
            'slot_name': slot_data.get('slot_name'),
            'display_name': slot_data.get('display_name'),
            'slot_type': slot_data.get('slot_type'),
            'is_required': slot_data.get('is_required'),
            'is_active': slot_data.get('is_active')
        }
    
    def _extract_system_config_audit_fields(self, config_data: Dict[str, Any]) -> Dict[str, Any]:
        """提取系统配置审计关键字段"""
        if not config_data:
            return {}
        
        return {
            'config_category': config_data.get('config_category'),
            'config_key': config_data.get('config_key'),
            'config_value': config_data.get('config_value'),
            'value_type': config_data.get('value_type'),
            'is_active': config_data.get('is_active')
        }
    
    def _get_operator_display_name(self, operator_id: str) -> str:
        """获取操作者显示名称"""
        # 这里可以集成用户服务获取真实姓名
        # 暂时使用简单映射
        name_mapping = {
            'system': '系统',
            'admin': '管理员',
            'api': 'API调用'
        }
        
        return name_mapping.get(operator_id, f"用户({operator_id})")


# 全局审计服务实例
_audit_service = None


def get_audit_service() -> AuditService:
    """获取审计服务实例（单例模式）"""
    global _audit_service
    if _audit_service is None:
        _audit_service = AuditService()
    return _audit_service