"""
槽位值管理服务 (V2.2重构)
替代conversations表中的slots_filled和slots_missing字段处理逻辑
"""
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime

from src.models.conversation import Conversation
from src.models.slot import Slot
from src.models.slot_value import SlotValue
from src.models.intent import Intent
from src.utils.logger import get_logger

logger = get_logger(__name__)


class SlotValueService:
    """槽位值管理服务类"""
    
    def __init__(self):
        self.logger = logger
    
    async def extract_and_store_slots(
        self,
        conversation: Conversation,
        intent: Intent,
        user_input: str,
        extraction_results: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        提取并存储槽位值
        
        Args:
            conversation: 对话对象
            intent: 意图对象
            user_input: 用户输入
            extraction_results: 槽位提取结果
            
        Returns:
            Dict: 处理结果统计
        """
        try:
            stored_count = 0
            updated_count = 0
            error_count = 0
            
            # 获取意图的所有槽位
            intent_slots = list(
                Slot.select()
                .where(
                    (Slot.intent_id == intent.id) &
                    (Slot.is_active == True)
                )
            )
            
            slot_dict = {slot.slot_name: slot for slot in intent_slots}
            
            # 处理提取到的槽位值
            for slot_name, slot_data in extraction_results.items():
                if slot_name not in slot_dict:
                    self.logger.warning(f"未知槽位: {slot_name}")
                    continue
                
                slot = slot_dict[slot_name]
                
                try:
                    # 提取槽位数据
                    extracted_value = slot_data.get('value')
                    confidence = slot_data.get('confidence')
                    extraction_method = slot_data.get('method', 'ml_model')
                    
                    if extracted_value:
                        # 更新或创建槽位值
                        slot_value = SlotValue.update_or_create_slot_value(
                            conversation=conversation,
                            slot=slot,
                            extracted_value=str(extracted_value),
                            original_text=user_input,
                            confidence=confidence,
                            extraction_method=extraction_method
                        )
                        
                        # 验证槽位值
                        await self._validate_slot_value(slot_value, slot)
                        
                        if hasattr(slot_value, '_created') and slot_value._created:
                            stored_count += 1
                        else:
                            updated_count += 1
                        
                        self.logger.debug(
                            f"处理槽位成功: {slot_name}={extracted_value}, "
                            f"置信度={confidence}"
                        )
                
                except Exception as e:
                    error_count += 1
                    self.logger.error(f"处理槽位失败: {slot_name}, 错误: {str(e)}")
            
            result = {
                'stored_count': stored_count,
                'updated_count': updated_count,
                'error_count': error_count,
                'total_processed': len(extraction_results)
            }
            
            self.logger.info(f"槽位提取存储完成: {result}")
            return result
            
        except Exception as e:
            self.logger.error(f"槽位提取存储失败: {str(e)}")
            raise
    
    async def get_conversation_slots_status(
        self,
        conversation: Conversation,
        intent: Intent
    ) -> Dict[str, Any]:
        """
        获取对话的槽位状态
        
        Args:
            conversation: 对话对象
            intent: 意图对象
            
        Returns:
            Dict: 槽位状态信息
        """
        try:
            # 获取已填充的槽位
            filled_slots = SlotValue.get_filled_slots_dict(conversation, only_valid=True)
            
            # 获取缺失的必填槽位
            missing_required_slots = SlotValue.get_missing_required_slots(
                conversation, intent.id
            )
            
            # 获取所有槽位值记录
            all_slot_values = SlotValue.get_conversation_slots(conversation)
            
            # 统计槽位状态
            status_stats = {
                'valid': 0,
                'invalid': 0,
                'pending': 0,
                'corrected': 0
            }
            
            for slot_value in all_slot_values:
                status_stats[slot_value.validation_status] += 1
            
            # 检查是否完整
            is_complete = len(missing_required_slots) == 0
            
            return {
                'filled_slots': filled_slots,
                'missing_required_slots': missing_required_slots,
                'is_complete': is_complete,
                'total_slots': len(all_slot_values),
                'status_statistics': status_stats,
                'slot_details': [sv.to_dict() for sv in all_slot_values]
            }
            
        except Exception as e:
            self.logger.error(f"获取槽位状态失败: {str(e)}")
            raise
    
    async def validate_slot_value(
        self,
        slot_value_id: int,
        validation_rules: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        验证槽位值
        
        Args:
            slot_value_id: 槽位值ID
            validation_rules: 额外的验证规则
            
        Returns:
            Dict: 验证结果
        """
        try:
            slot_value = SlotValue.get_by_id(slot_value_id)
            slot = slot_value.slot
            
            # 执行验证
            validation_result = await self._validate_slot_value(
                slot_value, slot, validation_rules
            )
            
            return {
                'slot_value_id': slot_value_id,
                'slot_name': slot_value.slot_name,
                'is_valid': validation_result['is_valid'],
                'validation_status': slot_value.validation_status,
                'validation_error': slot_value.validation_error,
                'normalized_value': slot_value.normalized_value
            }
            
        except Exception as e:
            self.logger.error(f"验证槽位值失败: {str(e)}")
            raise
    
    async def correct_slot_value(
        self,
        slot_value_id: int,
        corrected_value: str,
        operator: str = "system"
    ) -> SlotValue:
        """
        修正槽位值
        
        Args:
            slot_value_id: 槽位值ID
            corrected_value: 修正后的值
            operator: 操作者
            
        Returns:
            SlotValue: 修正后的槽位值
        """
        try:
            slot_value = SlotValue.get_by_id(slot_value_id)
            
            # 记录修正前的值
            old_value = slot_value.get_final_value()
            
            # 设置修正值
            slot_value.set_corrected(corrected_value)
            
            self.logger.info(
                f"槽位值修正成功: {slot_value.slot_name} "
                f"{old_value} -> {corrected_value} by {operator}"
            )
            
            return slot_value
            
        except Exception as e:
            self.logger.error(f"修正槽位值失败: {str(e)}")
            raise
    
    async def confirm_slot_values(
        self,
        conversation: Conversation,
        slot_names: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        确认槽位值
        
        Args:
            conversation: 对话对象
            slot_names: 要确认的槽位名称列表，None表示确认所有
            
        Returns:
            Dict: 确认结果统计
        """
        try:
            query = SlotValue.select().where(SlotValue.conversation == conversation)
            
            if slot_names:
                query = query.where(SlotValue.slot_name.in_(slot_names))
            
            slot_values = list(query)
            confirmed_count = 0
            
            for slot_value in slot_values:
                if not slot_value.is_confirmed:
                    slot_value.confirm()
                    confirmed_count += 1
            
            result = {
                'total_slots': len(slot_values),
                'confirmed_count': confirmed_count,
                'already_confirmed': len(slot_values) - confirmed_count
            }
            
            self.logger.info(f"槽位值确认完成: {result}")
            return result
            
        except Exception as e:
            self.logger.error(f"确认槽位值失败: {str(e)}")
            raise
    
    async def get_slot_value_history(
        self,
        slot_name: str,
        limit: int = 50,
        user_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        获取槽位值历史记录
        
        Args:
            slot_name: 槽位名称
            limit: 返回记录数限制
            user_id: 用户ID过滤
            
        Returns:
            List[Dict]: 历史记录列表
        """
        try:
            query = (
                SlotValue
                .select(SlotValue, Conversation)
                .join(Conversation)
                .where(SlotValue.slot_name == slot_name)
            )
            
            if user_id:
                query = query.where(Conversation.user_id == user_id)
            
            slot_values = list(
                query
                .order_by(SlotValue.created_at.desc())
                .limit(limit)
            )
            
            result = []
            for slot_value in slot_values:
                data = slot_value.to_dict()
                data['conversation_id'] = slot_value.conversation.id
                data['user_id'] = slot_value.conversation.user_id
                result.append(data)
            
            return result
            
        except Exception as e:
            self.logger.error(f"获取槽位值历史失败: {str(e)}")
            raise
    
    async def cleanup_invalid_slot_values(
        self,
        days_old: int = 30
    ) -> Dict[str, Any]:
        """
        清理过期的无效槽位值
        
        Args:
            days_old: 清理多少天前的记录
            
        Returns:
            Dict: 清理结果统计
        """
        try:
            from datetime import timedelta
            
            cutoff_date = datetime.now() - timedelta(days=days_old)
            
            # 查找过期的无效槽位值
            invalid_slot_values = list(
                SlotValue
                .select()
                .where(
                    (SlotValue.validation_status == 'invalid') &
                    (SlotValue.created_at < cutoff_date)
                )
            )
            
            # 删除过期的无效槽位值
            deleted_count = 0
            for slot_value in invalid_slot_values:
                slot_value.delete_instance()
                deleted_count += 1
            
            result = {
                'cutoff_date': cutoff_date.isoformat(),
                'deleted_count': deleted_count,
                'total_found': len(invalid_slot_values)
            }
            
            self.logger.info(f"清理无效槽位值完成: {result}")
            return result
            
        except Exception as e:
            self.logger.error(f"清理无效槽位值失败: {str(e)}")
            raise
    
    async def _validate_slot_value(
        self,
        slot_value: SlotValue,
        slot: Slot,
        additional_rules: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        内部槽位值验证方法
        
        Args:
            slot_value: 槽位值对象
            slot: 槽位定义对象
            additional_rules: 额外的验证规则
            
        Returns:
            Dict: 验证结果
        """
        try:
            extracted_value = slot_value.extracted_value
            
            if not extracted_value:
                slot_value.set_invalid("槽位值为空")
                return {'is_valid': False, 'error': '槽位值为空'}
            
            # 获取槽位的验证规则
            validation_rules = slot.get_validation_rules()
            if additional_rules:
                validation_rules.update(additional_rules)
            
            # 基础类型验证
            if slot.slot_type == 'number':
                try:
                    normalized_value = float(extracted_value)
                    
                    # 数值范围验证
                    if 'min' in validation_rules and normalized_value < validation_rules['min']:
                        slot_value.set_invalid(f"数值小于最小值 {validation_rules['min']}")
                        return {'is_valid': False, 'error': '数值范围错误'}
                    
                    if 'max' in validation_rules and normalized_value > validation_rules['max']:
                        slot_value.set_invalid(f"数值大于最大值 {validation_rules['max']}")
                        return {'is_valid': False, 'error': '数值范围错误'}
                    
                    slot_value.set_valid(str(normalized_value))
                    
                except ValueError:
                    slot_value.set_invalid("无法转换为数字")
                    return {'is_valid': False, 'error': '类型转换错误'}
            
            elif slot.slot_type == 'email':
                import re
                email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
                if re.match(email_pattern, extracted_value):
                    slot_value.set_valid(extracted_value.lower())
                else:
                    slot_value.set_invalid("邮箱格式不正确")
                    return {'is_valid': False, 'error': '格式错误'}
            
            elif slot.slot_type == 'phone':
                # 电话号码验证（简化版）
                import re
                phone_pattern = r'^[1][3-9][0-9]{9}$'
                clean_phone = re.sub(r'[^\d]', '', extracted_value)
                if re.match(phone_pattern, clean_phone):
                    slot_value.set_valid(clean_phone)
                else:
                    slot_value.set_invalid("手机号码格式不正确")
                    return {'is_valid': False, 'error': '格式错误'}
            
            elif slot.slot_type == 'text':
                # 文本长度验证
                text_length = len(extracted_value)
                min_length = validation_rules.get('min_length', 0)
                max_length = validation_rules.get('max_length', 1000)
                
                if text_length < min_length:
                    slot_value.set_invalid(f"文本长度不足 {min_length} 个字符")
                    return {'is_valid': False, 'error': '长度不足'}
                
                if text_length > max_length:
                    slot_value.set_invalid(f"文本长度超过 {max_length} 个字符")
                    return {'is_valid': False, 'error': '长度超限'}
                
                slot_value.set_valid(extracted_value.strip())
            
            else:
                # 默认验证：直接设置为有效
                slot_value.set_valid(extracted_value)
            
            return {'is_valid': True, 'normalized_value': slot_value.normalized_value}
            
        except Exception as e:
            error_msg = f"验证过程异常: {str(e)}"
            slot_value.set_invalid(error_msg)
            self.logger.error(f"槽位值验证异常: {error_msg}")
            return {'is_valid': False, 'error': error_msg}
    
    async def get_session_slot_values(self, session_id: str) -> Dict[str, Any]:
        """
        获取会话的所有槽位值
        
        Args:
            session_id: 会话ID
            
        Returns:
            Dict: 槽位值字典
        """
        try:
            from src.models.conversation import Session
            
            # 获取会话
            session = Session.get(Session.session_id == session_id)
            
            # 获取会话下的所有对话
            conversations = list(
                Conversation.select()
                .where(Conversation.session == session)
                .order_by(Conversation.created_at.desc())
            )
            
            if not conversations:
                return {}
            
            # 获取最新对话的槽位值
            latest_conversation = conversations[0]
            slot_values = {}
            
            # 查询该对话的所有已确认槽位值
            values = list(
                SlotValue.select()
                .join(Slot)
                .where(SlotValue.conversation == latest_conversation)
                .where(SlotValue.is_confirmed == True)
            )
            
            for slot_value in values:
                slot_values[slot_value.slot.slot_name] = {
                    'value': slot_value.get_final_value(),
                    'confidence': slot_value.confidence or 0.0,
                    'is_confirmed': slot_value.is_confirmed,
                    'validation_status': slot_value.validation_status,
                    'source_turn': getattr(slot_value, 'source_turn', 1)
                }
            
            return slot_values
            
        except Exception as e:
            self.logger.error(f"获取会话槽位值失败: {str(e)}")
            return {}


# 全局槽位值服务实例
_slot_value_service = None


def get_slot_value_service() -> SlotValueService:
    """获取槽位值服务实例（单例模式）"""
    global _slot_value_service
    if _slot_value_service is None:
        _slot_value_service = SlotValueService()
    return _slot_value_service