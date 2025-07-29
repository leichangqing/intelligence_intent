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
    
    async def get_conversation_slots(
        self,
        conversation_id: int,
        include_invalid: bool = False
    ) -> Dict[str, Any]:
        """
        获取对话的槽位信息
        
        Args:
            conversation_id: 对话ID
            include_invalid: 是否包含无效槽位
            
        Returns:
            Dict: 槽位信息字典
        """
        try:
            from src.models.conversation import Conversation
            conversation = Conversation.get_by_id(conversation_id)
            slot_values = SlotValue.get_conversation_slots(conversation, include_invalid)
            
            slots = {}
            for slot_value in slot_values:
                slots[slot_value.slot_name] = {
                    'value': slot_value.get_final_value(),
                    'confidence': slot_value.confidence,
                    'status': slot_value.validation_status,
                    'created_at': slot_value.created_at
                }
            return slots
        except Exception as e:
            self.logger.error(f"获取对话槽位失败: conversation_id={conversation_id}, error={str(e)}")
            return {}
    
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
            
            # 先进行标准化处理
            slot_value.normalize_value()
            
            # 获取槽位的验证规则
            validation_rules = slot.get_validation_rules()
            if additional_rules:
                validation_rules.update(additional_rules)
            
            # 基础类型验证 - 使用标准化后的值
            if slot.slot_type == 'number':
                try:
                    # 使用标准化后的值进行验证
                    value_to_validate = slot_value.normalized_value or extracted_value
                    normalized_value = float(value_to_validate)
                    
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
            
            elif slot.slot_type == 'date':
                # 日期类型验证和标准化
                try:
                    normalized_date = await self._normalize_date_value(extracted_value)
                    slot_value.set_valid(normalized_date)
                except Exception as e:
                    slot_value.set_invalid(f"日期格式不正确: {str(e)}")
                    return {'is_valid': False, 'error': '日期格式错误'}
            
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
    
    async def _normalize_date_value(self, value: str) -> str:
        """
        标准化日期值，将相对日期转换为具体日期
        
        Args:
            value: 原始日期值
            
        Returns:
            str: 标准化后的日期字符串 (YYYY-MM-DD格式)
        """
        try:
            from datetime import timedelta
            
            if isinstance(value, str):
                value_clean = value.strip()
                
                # 处理相对日期
                if '今天' in value_clean or '今日' in value_clean:
                    return datetime.now().strftime('%Y-%m-%d')
                elif '明天' in value_clean or '明日' in value_clean:
                    return (datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d')
                elif '后天' in value_clean:
                    return (datetime.now() + timedelta(days=2)).strftime('%Y-%m-%d')
                elif '昨天' in value_clean or '昨日' in value_clean:
                    return (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
                elif '前天' in value_clean:
                    return (datetime.now() - timedelta(days=2)).strftime('%Y-%m-%d')
                
                # 尝试解析其他日期格式
                # 这里可以添加更多的日期格式解析逻辑
                # 如: 2024-01-15, 01/15/2024, 15-01-2024 等
                
                # 简单的YYYY-MM-DD格式检查
                import re
                if re.match(r'^\d{4}-\d{2}-\d{2}$', value_clean):
                    # 验证日期是否有效
                    try:
                        datetime.strptime(value_clean, '%Y-%m-%d')
                        return value_clean
                    except ValueError:
                        pass
                
                # 如果无法解析，返回原值
                return value_clean
            
            return str(value)
            
        except Exception as e:
            self.logger.warning(f"日期标准化失败: {value}, 错误: {str(e)}")
            return str(value)
    
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
                .where(Conversation.session_id == session.session_id)
                .order_by(Conversation.created_at.desc())
            )
            
            if not conversations:
                return {}
            
            # 获取会话中所有对话的槽位值
            slot_values = {}
            
            # 查询该会话所有对话的有效槽位值
            conversation_ids = [conv.id for conv in conversations]
            values = list(
                SlotValue.select()
                .join(Slot)
                .where(SlotValue.conversation.in_(conversation_ids))
                .where(SlotValue.validation_status.in_(['valid', 'pending', 'corrected']))
                .order_by(SlotValue.created_at.desc())
            )
            
            # 只保留每个槽位的最新值，避免重复，返回字典格式（兼容JSON序列化）
            processed_slots = set()
            for slot_value in values:
                slot_name = slot_value.slot.slot_name
                if slot_name not in processed_slots:
                    # 返回字典格式，避免SlotInfo对象的JSON序列化问题
                    slot_info_dict = {
                        'name': slot_name,
                        'original_text': slot_value.original_text or '',
                        'extracted_value': slot_value.extracted_value,
                        'normalized_value': slot_value.normalized_value,
                        'confidence': float(slot_value.confidence) if slot_value.confidence else 0.0,
                        'extraction_method': slot_value.extraction_method or 'unknown',
                        'validation': None,
                        'is_confirmed': True,
                        'value': slot_value.get_final_value(),
                        'source': slot_value.extraction_method or 'unknown',
                        'is_validated': slot_value.validation_status in ['valid', 'pending'],
                        'validation_error': slot_value.validation_error
                    }
                    slot_values[slot_name] = slot_info_dict
                    processed_slots.add(slot_name)
            
            return slot_values
            
        except Exception as e:
            self.logger.error(f"获取会话槽位值失败: {str(e)}")
            return {}
    
    async def update_session_slots(self, session_id: str, intent_name: str, slots: Dict[str, Any]) -> bool:
        """
        更新会话槽位值
        
        Args:
            session_id: 会话ID
            intent_name: 意图名称
            slots: 槽位数据
            
        Returns:
            bool: 是否更新成功
        """
        try:
            # 这是一个占位方法，实际更新逻辑在其他方法中处理
            self.logger.debug(f"更新会话槽位: {session_id}, 意图: {intent_name}, 槽位数: {len(slots)}")
            return True
        except Exception as e:
            self.logger.error(f"更新会话槽位失败: {str(e)}")
            return False
    
    async def save_conversation_slots(self, session_id: str, conversation_id: int, intent: str, slots: Dict[str, Any]) -> bool:
        """
        保存对话槽位值
        
        Args:
            session_id: 会话ID
            conversation_id: 对话ID
            intent: 意图名称
            slots: 槽位数据
            
        Returns:
            bool: 是否保存成功
        """
        try:
            if not slots:
                return True
            
            from src.models.intent import Intent
            from src.models.slot import Slot
            from src.models.conversation import Conversation
            
            # 获取意图和对话对象
            try:
                intent_obj = Intent.get(Intent.intent_name == intent)
                conversation_obj = Conversation.get(Conversation.id == conversation_id)
            except Exception as e:
                self.logger.error(f"获取意图或对话对象失败: {str(e)}")
                return False
            
            saved_count = 0
            
            self.logger.info(f"准备保存槽位值: {slots}")
            
            # 保存每个槽位值
            for slot_name, slot_data in slots.items():
                try:
                    # 获取槽位定义
                    slot_def = Slot.get(
                        (Slot.intent == intent_obj) & 
                        (Slot.slot_name == slot_name)
                    )
                    
                    # 提取槽位值数据 - 处理SlotInfo对象
                    if hasattr(slot_data, 'value'):  # SlotInfo对象
                        extracted_value = slot_data.value or slot_data.extracted_value
                        original_text = slot_data.original_text or ''
                        confidence = slot_data.confidence or 0.0
                        extraction_method = slot_data.source or slot_data.extraction_method or 'llm'
                    else:  # 字典格式
                        extracted_value = slot_data.get('value') or slot_data.get('extracted_value')
                        original_text = slot_data.get('original_text', '')
                        confidence = slot_data.get('confidence', 0.0)
                        extraction_method = slot_data.get('source', 'llm')
                    
                    if extracted_value is not None:
                        # 更新或创建槽位值
                        slot_value = SlotValue.update_or_create_slot_value(
                            conversation=conversation_obj,
                            slot=slot_def,
                            extracted_value=str(extracted_value),
                            original_text=original_text,
                            confidence=confidence,
                            extraction_method=extraction_method
                        )
                        
                        # 调用标准化方法
                        slot_value.normalize_value()
                        slot_value.save()
                        
                        saved_count += 1
                        self.logger.debug(f"保存槽位值成功: {slot_name} = {extracted_value}")
                        
                except Slot.DoesNotExist:
                    self.logger.warning(f"槽位定义不存在: {slot_name}")
                    continue
                except Exception as e:
                    self.logger.error(f"保存槽位值失败: {slot_name}, 错误: {str(e)}")
                    continue
            
            self.logger.info(f"保存对话槽位完成: conversation_id={conversation_id}, 成功={saved_count}/{len(slots)}")
            return saved_count > 0
            
        except Exception as e:
            self.logger.error(f"保存对话槽位失败: {str(e)}")
            return False
    
    async def initialize_session_slots(self, session_id: str, initial_slots: Dict[str, Any]) -> bool:
        """
        初始化会话槽位
        
        Args:
            session_id: 会话ID
            initial_slots: 初始槽位数据
            
        Returns:
            bool: 是否初始化成功
        """
        try:
            self.logger.debug(f"初始化会话槽位: {session_id}, 槽位数: {len(initial_slots)}")
            return True
        except Exception as e:
            self.logger.error(f"初始化会话槽位失败: {str(e)}")
            return False


# 全局槽位值服务实例
_slot_value_service = None


def get_slot_value_service() -> SlotValueService:
    """获取槽位值服务实例（单例模式）"""
    global _slot_value_service
    if _slot_value_service is None:
        _slot_value_service = SlotValueService()
    return _slot_value_service