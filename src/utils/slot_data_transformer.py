"""
槽位数据转换工具
统一不同数据层的槽位数据格式
"""
from typing import Dict, List, Any, Optional
from datetime import datetime
from pydantic import BaseModel

from src.schemas.chat import SlotInfo
from src.models.slot import SlotValue


class SlotDataTransformer:
    """槽位数据转换器"""
    
    @staticmethod
    def db_to_api_format(slot_values: List[SlotValue]) -> Dict[str, SlotInfo]:
        """
        将数据库槽位值转换为API响应格式
        
        Args:
            slot_values: 数据库SlotValue对象列表
            
        Returns:
            Dict[str, SlotInfo]: API格式的槽位字典
        """
        result = {}
        
        for slot_value in slot_values:
            slot_info = SlotInfo(
                value=slot_value.normalized_value or slot_value.extracted_value,
                confidence=float(slot_value.confidence) if slot_value.confidence else None,
                source=slot_value.extraction_method,
                original_text=slot_value.original_text,
                is_validated=slot_value.validation_status == 'valid',
                validation_error=slot_value.validation_error if slot_value.validation_status == 'invalid' else None
            )
            result[slot_value.slot_name] = slot_info
            
        return result
    
    @staticmethod
    def api_to_db_format(slots: Dict[str, SlotInfo], conversation_id: int, slot_id_mapping: Dict[str, int]) -> List[Dict[str, Any]]:
        """
        将API格式槽位转换为数据库插入格式
        
        Args:
            slots: API格式的槽位字典
            conversation_id: 对话ID
            slot_id_mapping: 槽位名到slot_id的映射
            
        Returns:
            List[Dict]: 用于数据库插入的字典列表
        """
        result = []
        
        for slot_name, slot_info in slots.items():
            if slot_name not in slot_id_mapping:
                continue  # 跳过未定义的槽位
                
            db_record = {
                'conversation_id': conversation_id,
                'slot_id': slot_id_mapping[slot_name],
                'slot_name': slot_name,
                'original_text': slot_info.original_text,
                'extracted_value': str(slot_info.value),
                'normalized_value': str(slot_info.value),  # 可以后续添加标准化逻辑
                'confidence': slot_info.confidence,
                'extraction_method': slot_info.source or 'api',
                'validation_status': 'valid' if slot_info.is_validated else 'pending',
                'validation_error': slot_info.validation_error,
                'is_confirmed': slot_info.is_validated or False
            }
            result.append(db_record)
            
        return result
    
    @staticmethod
    def cache_to_api_format(cached_slots: Dict[str, Any]) -> Dict[str, SlotInfo]:
        """
        将缓存格式槽位转换为API响应格式
        
        Args:
            cached_slots: 缓存中的槽位数据
            
        Returns:
            Dict[str, SlotInfo]: API格式的槽位字典
        """
        result = {}
        
        for slot_name, slot_data in cached_slots.items():
            if isinstance(slot_data, dict):
                # 缓存中存储的是完整SlotInfo格式
                slot_info = SlotInfo(
                    value=slot_data.get('value'),
                    confidence=slot_data.get('confidence'),
                    source=slot_data.get('source'),
                    original_text=slot_data.get('original_text'),
                    is_validated=slot_data.get('is_validated', True),
                    validation_error=slot_data.get('validation_error')
                )
            else:
                # 缓存中存储的是简单值
                slot_info = SlotInfo(
                    value=slot_data,
                    confidence=None,
                    source='cache',
                    is_validated=True
                )
            result[slot_name] = slot_info
            
        return result
    
    @staticmethod
    def api_to_cache_format(slots: Dict[str, SlotInfo]) -> Dict[str, Dict[str, Any]]:
        """
        将API格式槽位转换为缓存格式
        
        Args:
            slots: API格式的槽位字典
            
        Returns:
            Dict: 用于缓存存储的格式
        """
        result = {}
        
        for slot_name, slot_info in slots.items():
            result[slot_name] = {
                'value': slot_info.value,
                'confidence': slot_info.confidence,
                'source': slot_info.source,
                'original_text': slot_info.original_text,
                'is_validated': slot_info.is_validated,
                'validation_error': slot_info.validation_error,
                'updated_at': datetime.utcnow().isoformat()
            }
            
        return result
    
    @staticmethod
    def merge_slots(existing_slots: Dict[str, SlotInfo], new_slots: Dict[str, SlotInfo]) -> Dict[str, SlotInfo]:
        """
        合并槽位数据（新槽位优先）
        
        Args:
            existing_slots: 现有槽位
            new_slots: 新槽位
            
        Returns:
            Dict[str, SlotInfo]: 合并后的槽位
        """
        result = existing_slots.copy()
        result.update(new_slots)
        return result
    
    @staticmethod
    def validate_slots(slots: Dict[str, SlotInfo], slot_definitions: Dict[str, Dict[str, Any]]) -> Dict[str, str]:
        """
        验证槽位数据
        
        Args:
            slots: 要验证的槽位
            slot_definitions: 槽位定义（从配置获取）
            
        Returns:
            Dict[str, str]: 验证错误映射 {slot_name: error_message}
        """
        errors = {}
        
        for slot_name, slot_info in slots.items():
            if slot_name not in slot_definitions:
                errors[slot_name] = f"未定义的槽位: {slot_name}"
                continue
                
            slot_def = slot_definitions[slot_name]
            
            # 检查必填槽位
            if slot_def.get('is_required', False) and not slot_info.value:
                errors[slot_name] = f"必填槽位不能为空"
                continue
                
            # 检查数据类型
            slot_type = slot_def.get('slot_type', 'text')
            if not SlotDataTransformer._validate_slot_type(slot_info.value, slot_type):
                errors[slot_name] = f"槽位类型不匹配，期望: {slot_type}"
                continue
                
        return errors
    
    @staticmethod
    def _validate_slot_type(value: Any, slot_type: str) -> bool:
        """验证槽位值类型"""
        if value is None:
            return True
            
        try:
            if slot_type == 'number':
                float(value)
            elif slot_type == 'boolean':
                if str(value).lower() not in ['true', 'false', '1', '0', 'yes', 'no']:
                    return False
            elif slot_type == 'email':
                import re
                if not re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', str(value)):
                    return False
            # 其他类型暂时都当作text处理
            return True
        except (ValueError, TypeError):
            return False
    
    @staticmethod
    def extract_missing_slots(filled_slots: Dict[str, SlotInfo], required_slots: List[str]) -> List[str]:
        """
        提取缺失的必填槽位
        
        Args:
            filled_slots: 已填充的槽位
            required_slots: 必填槽位名称列表
            
        Returns:
            List[str]: 缺失的槽位名称列表
        """
        missing = []
        for slot_name in required_slots:
            if slot_name not in filled_slots or not filled_slots[slot_name].value:
                missing.append(slot_name)
        return missing
    
    @staticmethod
    def get_slot_completion_rate(filled_slots: Dict[str, SlotInfo], total_slots: List[str]) -> float:
        """
        计算槽位完成率
        
        Args:
            filled_slots: 已填充的槽位
            total_slots: 总槽位列表
            
        Returns:
            float: 完成率 (0.0-1.0)
        """
        if not total_slots:
            return 1.0
            
        filled_count = len([
            slot_name for slot_name in total_slots 
            if slot_name in filled_slots and filled_slots[slot_name].value
        ])
        
        return filled_count / len(total_slots)