"""
增强的槽位服务 - 整合数据转换功能
统一处理不同数据层的槽位格式
"""
from typing import Dict, List, Any, Optional
from datetime import datetime

from src.services.slot_service import SlotService, SlotExtractionResult
from src.services.cache_service import CacheService
from src.services.slot_value_service import SlotValueService, get_slot_value_service
from src.utils.slot_data_transformer import SlotDataTransformer
from src.schemas.chat import SlotInfo
from src.models.intent import Intent
from src.models.slot_value import SlotValue
from src.utils.logger import get_logger

logger = get_logger(__name__)


class EnhancedSlotExtractionResult:
    """增强的槽位提取结果"""
    
    def __init__(self, slots: Dict[str, SlotInfo], missing_slots: List[str],
                 validation_errors: Dict[str, str] = None, is_complete: bool = False):
        self.slots = slots
        self.missing_slots = missing_slots
        self.validation_errors = validation_errors or {}
        self.is_complete = is_complete
        self.has_errors = bool(validation_errors)


class EnhancedSlotService:
    """增强的槽位管理服务 - 统一数据格式处理"""
    
    def __init__(self, slot_service: SlotService, cache_service: CacheService):
        self.slot_service = slot_service
        self.cache_service = cache_service
        self.slot_value_service = get_slot_value_service()
        self.transformer = SlotDataTransformer()
    
    async def extract_slots(self, intent: Intent, user_input: str,
                          existing_slots: Dict[str, Any] = None,
                          context: Dict[str, Any] = None) -> EnhancedSlotExtractionResult:
        """
        增强的槽位提取，返回统一格式
        
        Args:
            intent: 意图对象
            user_input: 用户输入
            existing_slots: 已存在的槽位值
            context: 对话上下文
            
        Returns:
            EnhancedSlotExtractionResult: 增强的槽位提取结果
        """
        try:
            # 1. 调用原始槽位服务进行提取
            raw_result = await self.slot_service.extract_slots(
                intent, user_input, existing_slots, context
            )
            
            # 2. 转换为统一的SlotInfo格式
            unified_slots = await self._convert_to_slot_info_format(
                raw_result.slots, intent.intent_name
            )
            
            # 2.5. 应用槽位值标准化
            unified_slots = await self._normalize_slot_values(unified_slots, intent)
            
            # 3. 获取槽位定义进行验证
            slot_definitions = await self._get_slot_definitions(intent)
            
            # 4. 验证槽位数据
            validation_errors = self.transformer.validate_slots(
                unified_slots, slot_definitions
            )
            
            # 5. 检查完整性
            required_slots = [
                slot_name for slot_name, slot_def in slot_definitions.items()
                if slot_def.get('is_required', False)
            ]
            
            missing_slots = self.transformer.extract_missing_slots(
                unified_slots, required_slots
            )
            
            is_complete = len(missing_slots) == 0 and len(validation_errors) == 0
            
            return EnhancedSlotExtractionResult(
                slots=unified_slots,
                missing_slots=missing_slots,
                validation_errors=validation_errors,
                is_complete=is_complete
            )
            
        except Exception as e:
            logger.error(f"槽位提取失败: {str(e)}")
            return EnhancedSlotExtractionResult({}, [], {"system": str(e)})
    
    async def load_session_slots(self, session_id: str) -> Dict[str, SlotInfo]:
        """
        从数据库加载会话槽位数据
        
        Args:
            session_id: 会话ID
            
        Returns:
            Dict[str, SlotInfo]: 统一格式的槽位数据
        """
        try:
            # 1. 先尝试从缓存获取
            cache_key = self.cache_service.get_cache_key('slot_values', session_id=session_id)
            cached_slots = await self.cache_service.get(cache_key)
            
            if cached_slots:
                return self.transformer.cache_to_api_format(cached_slots)
            
            # 2. 从数据库获取
            slot_values = await self.slot_value_service.get_session_slot_values(session_id)
            if not slot_values:
                return {}
            
            # 3. 转换为API格式
            unified_slots = self.transformer.db_to_api_format(slot_values)
            
            # 4. 缓存结果
            cache_data = self.transformer.api_to_cache_format(unified_slots)
            await self.cache_service.set(cache_key, cache_data, ttl=3600)
            
            return unified_slots
            
        except Exception as e:
            logger.error(f"加载会话槽位失败: {session_id}, 错误: {str(e)}")
            return {}
    
    async def save_session_slots(self, session_id: str, conversation_id: int,
                               intent_name: str, slots: Dict[str, SlotInfo]) -> bool:
        """
        保存会话槽位数据到数据库
        
        Args:
            session_id: 会话ID
            conversation_id: 对话ID
            intent_name: 意图名称
            slots: 槽位数据
            
        Returns:
            bool: 保存是否成功
        """
        try:
            # 1. 获取槽位ID映射
            slot_id_mapping = await self._get_slot_id_mapping(intent_name)
            if not slot_id_mapping:
                logger.warning(f"未找到意图 {intent_name} 的槽位定义")
                return False
            
            # 2. 转换为数据库格式
            db_records = self.transformer.api_to_db_format(
                slots, conversation_id, slot_id_mapping
            )
            
            # 3. 保存到数据库
            success = await self.slot_value_service.save_conversation_slots(
                session_id, conversation_id, intent_name, slots
            )
            
            if success:
                # 4. 更新缓存
                await self._update_slot_cache(session_id, slots)
                
                # 5. 发布槽位更新事件
                await self._publish_slot_update_event(session_id, intent_name, slots)
            
            return success
            
        except Exception as e:
            logger.error(f"保存会话槽位失败: {session_id}, 错误: {str(e)}")
            return False
    
    async def merge_slots(self, session_id: str, new_slots: Dict[str, SlotInfo]) -> Dict[str, SlotInfo]:
        """
        合并新旧槽位数据
        
        Args:
            session_id: 会话ID
            new_slots: 新的槽位数据
            
        Returns:
            Dict[str, SlotInfo]: 合并后的槽位数据
        """
        try:
            existing_slots = await self.load_session_slots(session_id)
            merged_slots = self.transformer.merge_slots(existing_slots, new_slots)
            
            # 更新缓存
            await self._update_slot_cache(session_id, merged_slots)
            
            return merged_slots
            
        except Exception as e:
            logger.error(f"合并槽位失败: {session_id}, 错误: {str(e)}")
            return new_slots
    
    async def generate_slot_prompt(self, intent: Intent, missing_slots: List[str],
                                 context: Dict[str, Any] = None) -> str:
        """
        生成槽位询问提示
        
        Args:
            intent: 意图对象
            missing_slots: 缺失的槽位列表
            context: 对话上下文
            
        Returns:
            str: 槽位询问提示
        """
        try:
            # 调用原有服务的提示生成方法
            return await self.slot_service.generate_slot_prompt(
                intent, missing_slots, context
            )
        except Exception as e:
            logger.error(f"生成槽位提示失败: {str(e)}")
            return f"请提供以下信息: {', '.join(missing_slots)}"
    
    async def get_slot_completion_rate(self, session_id: str, intent_name: str) -> float:
        """
        计算槽位完成率
        
        Args:
            session_id: 会话ID
            intent_name: 意图名称
            
        Returns:
            float: 完成率 (0.0-1.0)
        """
        try:
            # 获取当前槽位
            current_slots = await self.load_session_slots(session_id)
            
            # 获取所有必需槽位
            slot_definitions = await self._get_slot_definitions_by_name(intent_name)
            total_slots = list(slot_definitions.keys())
            
            return self.transformer.get_slot_completion_rate(current_slots, total_slots)
            
        except Exception as e:
            logger.error(f"计算槽位完成率失败: {session_id}, {intent_name}, 错误: {str(e)}")
            return 0.0
    
    # 私有方法
    
    async def _convert_to_slot_info_format(self, raw_slots: Dict[str, Any], intent_name: str) -> Dict[str, SlotInfo]:
        """转换原始槽位数据为SlotInfo格式"""
        result = {}
        
        for slot_name, slot_value in raw_slots.items():
            if isinstance(slot_value, dict):
                # 如果已经是字典格式
                extracted_value = slot_value.get('value')
                original_text = slot_value.get('original_text')
                
                # 修复：如果value为空但original_text有值，使用original_text作为extracted_value
                # 处理空字符串和None的情况
                if (not extracted_value or extracted_value == '') and (original_text and original_text != ''):
                    extracted_value = original_text
                # 如果两者都为空，跳过这个槽位
                elif (not extracted_value or extracted_value == '') and (not original_text or original_text == ''):
                    continue
                
                # 使用LLM提取结果中的标准化值
                final_value = slot_value.get('value', extracted_value)  # 优先使用LLM标准化的值
                
                slot_info = SlotInfo(
                    name=slot_name,
                    extracted_value=extracted_value,
                    normalized_value=final_value,  # 使用LLM标准化后的值
                    confidence=slot_value.get('confidence'),
                    extraction_method=slot_value.get('source', 'nlu'),
                    original_text=original_text,
                    is_confirmed=slot_value.get('is_validated', True),
                    validation=None,  # 确保validation字段为None
                    # 向后兼容字段
                    value=final_value,  # 使用标准化后的值
                    source=slot_value.get('source', 'nlu'),
                    is_validated=slot_value.get('is_validated', True),
                    validation_error=None  # 确保validation_error为None
                )
                
                # 后备标准化处理：如果LLM没有正确标准化，手动处理
                # slot_info = self._apply_fallback_normalization(slot_info, slot_definitions)  # 暂时禁用，避免未定义错误
            else:
                # 简单值格式
                slot_info = SlotInfo(
                    name=slot_name,
                    extracted_value=slot_value,
                    normalized_value=slot_value,
                    confidence=None,
                    extraction_method='nlu',
                    is_confirmed=True,
                    validation=None,  # 确保validation字段为None
                    # 向后兼容字段
                    value=slot_value,
                    source='nlu',
                    is_validated=True,
                    validation_error=None  # 确保validation_error为None
                )
            
            result[slot_name] = slot_info
        
        return result
    
    async def _normalize_slot_values(self, slots: Dict[str, SlotInfo], intent: Intent) -> Dict[str, SlotInfo]:
        """
        对槽位值进行标准化处理
        
        Args:
            slots: 槽位字典
            intent: 意图对象
            
        Returns:
            Dict[str, SlotInfo]: 标准化后的槽位字典
        """
        try:
            # 获取槽位定义以了解槽位类型
            slot_definitions = await self._get_slot_definitions(intent)
            
            # 分离依赖槽位和非依赖槽位，先处理非依赖槽位
            dependent_slots = ['return_date']  # 依赖其他槽位的槽位列表
            independent_slots = {k: v for k, v in slots.items() if k not in dependent_slots}
            dependent_slot_items = {k: v for k, v in slots.items() if k in dependent_slots}
            
            # 先处理非依赖槽位
            for slot_name, slot_info in independent_slots.items():
                # 跳过没有有效提取值的槽位
                if not slot_info.extracted_value or slot_info.extracted_value == '':
                    continue
                    
                # 获取槽位类型
                slot_def = slot_definitions.get(slot_name, {})
                slot_type = slot_def.get('slot_type', 'text')
                
                # 应用类型特定的标准化
                if slot_type == 'date':
                    normalized_value = await self._normalize_date_value(slot_info.extracted_value)
                    # 更新SlotInfo对象的normalized_value和value字段
                    slot_info.normalized_value = normalized_value
                    slot_info.value = normalized_value
                elif slot_type == 'number':
                    # 数字标准化，包括中文数字转换
                    normalized_value = self._normalize_number_value(slot_info.extracted_value)
                    slot_info.normalized_value = normalized_value
                    slot_info.value = normalized_value
                elif slot_type == 'text' and slot_name == 'trip_type':
                    # trip_type特殊处理
                    if '往返' in slot_info.extracted_value or '来回' in slot_info.extracted_value:
                        normalized_value = 'round_trip'
                    else:
                        normalized_value = 'single'
                    slot_info.normalized_value = normalized_value
                    slot_info.value = normalized_value
                else:
                    # 其他类型的基本标准化（去除首尾空格）
                    normalized_value = str(slot_info.extracted_value).strip()
                    slot_info.normalized_value = normalized_value
                    slot_info.value = normalized_value
            
            # 再处理依赖槽位（此时非依赖槽位已经标准化）
            for slot_name, slot_info in dependent_slot_items.items():
                # 跳过没有有效提取值的槽位
                if not slot_info.extracted_value or slot_info.extracted_value == '':
                    continue
                    
                # 获取槽位类型
                slot_def = slot_definitions.get(slot_name, {})
                slot_type = slot_def.get('slot_type', 'text')
                
                # 应用类型特定的标准化，传入已更新的slots
                if slot_type == 'date':
                    normalized_value = await self._normalize_date_value(slot_info.extracted_value, slots)
                    # 更新SlotInfo对象的normalized_value和value字段
                    slot_info.normalized_value = normalized_value
                    slot_info.value = normalized_value
                else:
                    # 其他类型的基本标准化（去除首尾空格）
                    normalized_value = str(slot_info.extracted_value).strip()
                    slot_info.normalized_value = normalized_value
                    slot_info.value = normalized_value
            
            # 移除仍然为空的槽位
            filtered_slots = {}
            for slot_name, slot_info in slots.items():
                if slot_info.extracted_value and slot_info.extracted_value != '':
                    filtered_slots[slot_name] = slot_info
                    
            return filtered_slots
            
        except Exception as e:
            logger.error(f"槽位值标准化失败: {str(e)}")
            return slots
    
    async def _normalize_date_value(self, value: str, existing_slots: Dict[str, SlotInfo] = None) -> str:
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
                
                # 处理复合表达（如"三天后回来"）
                if '回来' in value_clean or '返程' in value_clean or '回程' in value_clean:
                    # 提取数字和时间单位
                    import re
                    match = re.search(r'(\d+|一|二|三|四|五|六|七|八|九|十)+(天|日)', value_clean)
                    if match:
                        # 获取参考日期（出发日期）
                        reference_date = datetime.now()
                        if existing_slots and 'departure_date' in existing_slots:
                            dep_date = existing_slots['departure_date'].value
                            try:
                                # 尝试解析已有的出发日期
                                if isinstance(dep_date, str) and dep_date != '三天后回来':
                                    # 首先尝试标准日期格式
                                    try:
                                        reference_date = datetime.strptime(dep_date, '%Y-%m-%d')
                                    except ValueError:
                                        # 如果不是标准格式，手动处理常见格式
                                        if '下周' in dep_date:
                                            weekdays = {'一': 0, '二': 1, '三': 2, '四': 3, '五': 4, '六': 5, '日': 6, '天': 6}
                                            for day_name, day_num in weekdays.items():
                                                if day_name in dep_date:
                                                    today = datetime.now()
                                                    current_weekday = today.weekday()
                                                    days_until_next_week = 7 - current_weekday + day_num
                                                    reference_date = today + timedelta(days=days_until_next_week)
                                                    break
                            except Exception as e:
                                logger.warning(f"解析departure_date失败: {dep_date}, 错误: {str(e)}")
                                pass
                        
                        # 提取天数
                        num_text = match.group(1)
                        chinese_nums = {'一': 1, '二': 2, '三': 3, '四': 4, '五': 5, '六': 6, '七': 7, '八': 8, '九': 9, '十': 10}
                        days = chinese_nums.get(num_text, int(num_text) if num_text.isdigit() else 3)
                        
                        return (reference_date + timedelta(days=days)).strftime('%Y-%m-%d')
                
                # 处理普通相对日期
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
                
                # 处理"下周X"格式
                elif '下周' in value_clean:
                    weekdays = {'一': 0, '二': 1, '三': 2, '四': 3, '五': 4, '六': 5, '日': 6, '天': 6}
                    for day_name, day_num in weekdays.items():
                        if day_name in value_clean:
                            today = datetime.now()
                            current_weekday = today.weekday()  # 0=Monday, 6=Sunday
                            days_until_next_week = 7 - current_weekday + day_num
                            target_date = today + timedelta(days=days_until_next_week)
                            return target_date.strftime('%Y-%m-%d')
                
                # 尝试解析其他日期格式
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
            logger.warning(f"日期标准化失败: {value}, 错误: {str(e)}")
            return str(value)
    
    def _normalize_number_value(self, value: str) -> str:
        """
        标准化数字值，将中文数字转换为阿拉伯数字
        
        Args:
            value: 原始数字值
            
        Returns:
            str: 标准化后的数字字符串
        """
        try:
            if not value or value == '':
                return '0'
                
            value_clean = str(value).strip()
            
            # 中文数字映射
            chinese_numbers = {
                '零': '0', '一': '1', '二': '2', '三': '3', '四': '4',
                '五': '5', '六': '6', '七': '7', '八': '8', '九': '9',
                '十': '10', '两': '2', '俩': '2'
            }
            
            # 首先尝试提取阿拉伯数字
            import re
            arabic_numbers = re.findall(r'\d+', value_clean)
            if arabic_numbers:
                return arabic_numbers[0]  # 返回第一个找到的数字
            
            # 处理包含量词的情况（如"一张"、"两位"、"三个"等）
            # 提取字符串中的中文数字部分
            for chinese_num in ['一', '二', '三', '四', '五', '六', '七', '八', '九', '十', '两', '俩', '零']:
                if chinese_num in value_clean:
                    # 如果找到中文数字，返回对应的阿拉伯数字
                    if chinese_num in chinese_numbers:
                        return chinese_numbers[chinese_num]
            
            # 如果是纯中文数字，进行转换
            if value_clean in chinese_numbers:
                return chinese_numbers[value_clean]
            
            # 处理复合中文数字（如"十二"、"二十"等）
            if '十' in value_clean:
                if value_clean == '十':
                    return '10'
                elif value_clean.startswith('十'):
                    # 十X -> 1X
                    suffix = value_clean[1:]
                    if suffix in chinese_numbers:
                        return '1' + chinese_numbers[suffix]
                elif value_clean.endswith('十'):
                    # X十 -> X0
                    prefix = value_clean[:-1]
                    if prefix in chinese_numbers:
                        return chinese_numbers[prefix] + '0'
                else:
                    # X十Y -> XY
                    parts = value_clean.split('十')
                    if len(parts) == 2 and parts[0] in chinese_numbers and parts[1] in chinese_numbers:
                        return chinese_numbers[parts[0]] + chinese_numbers[parts[1]]
            
            # 尝试直接转换为数字验证
            try:
                num = float(value_clean)
                # 如果是整数，返回整数格式
                if num.is_integer():
                    return str(int(num))
                else:
                    return str(num)
            except ValueError:
                pass
            
            # 如果无法转换，返回原值
            return value_clean
            
        except Exception as e:
            logger.warning(f"数字标准化失败: {value}, 错误: {str(e)}")
            return str(value)
    
    async def _get_slot_definitions(self, intent: Intent) -> Dict[str, Dict[str, Any]]:
        """获取槽位定义"""
        try:
            # 从缓存或数据库获取槽位定义
            cache_key = self.cache_service.get_cache_key('slot_definitions', intent_name=intent.intent_name)
            definitions = await self.cache_service.get(cache_key)
            
            if not definitions:
                # 从数据库查询
                from src.models.slot import Slot
                slots = Slot.select().where(Slot.intent_id == intent.id, Slot.is_active == True)
                
                definitions = {}
                for slot in slots:
                    definitions[slot.slot_name] = {
                        'slot_type': slot.slot_type,
                        'is_required': slot.is_required,
                        'validation_rules': slot.validation_rules,
                        'prompt_template': slot.prompt_template
                    }
                
                # 缓存结果
                await self.cache_service.set(cache_key, definitions, ttl=3600)
            
            return definitions
            
        except Exception as e:
            logger.error(f"获取槽位定义失败: {intent.intent_name}, 错误: {str(e)}")
            return {}
    
    async def _get_slot_definitions_by_name(self, intent_name: str) -> Dict[str, Dict[str, Any]]:
        """根据意图名称获取槽位定义"""
        try:
            from src.models.intent import Intent
            from src.models.slot import Slot
            
            intent = Intent.get(Intent.intent_name == intent_name)
            return await self._get_slot_definitions(intent)
        except Exception as e:
            logger.error(f"根据意图名获取槽位定义失败: {intent_name}, 错误: {str(e)}")
            return {}
    
    async def _get_slot_id_mapping(self, intent_name: str) -> Dict[str, int]:
        """获取槽位名到ID的映射"""
        try:
            from src.models.intent import Intent
            from src.models.slot import Slot
            
            intent = Intent.get(Intent.intent_name == intent_name)
            slots = Slot.select().where(Slot.intent_id == intent.id, Slot.is_active == True)
            
            return {slot.slot_name: slot.id for slot in slots}
        except Exception as e:
            logger.error(f"获取槽位ID映射失败: {intent_name}, 错误: {str(e)}")
            return {}
    
    async def _update_slot_cache(self, session_id: str, slots: Dict[str, SlotInfo]):
        """更新槽位缓存"""
        try:
            cache_key = self.cache_service.get_cache_key('slot_values', session_id=session_id)
            cache_data = self.transformer.api_to_cache_format(slots)
            await self.cache_service.set(cache_key, cache_data, ttl=3600)
        except Exception as e:
            logger.error(f"更新槽位缓存失败: {session_id}, 错误: {str(e)}")
    
    async def _publish_slot_update_event(self, session_id: str, intent_name: str, slots: Dict[str, SlotInfo]):
        """发布槽位更新事件"""
        try:
            event_data = {
                'session_id': session_id,
                'intent_name': intent_name,
                'slot_count': len(slots),
                'updated_at': datetime.utcnow().isoformat()
            }
            # 如果有事件系统，在这里发布事件
            logger.info(f"槽位更新事件: {event_data}")
        except Exception as e:
            logger.error(f"发布槽位更新事件失败: {str(e)}")
    
    def _apply_fallback_normalization(self, slot_info: SlotInfo, slot_definitions: List[Dict]) -> SlotInfo:
        """应用后备标准化处理"""
        try:
            # 找到对应的槽位定义
            slot_def = None
            for definition in slot_definitions:
                if definition.get('slot_name') == slot_info.name:
                    slot_def = definition
                    break
            
            if not slot_def:
                return slot_info
            
            slot_type = slot_def.get('slot_type', '').lower()
            slot_name = slot_info.name
            
            # 检查是否需要标准化
            if slot_info.normalized_value == slot_info.extracted_value and slot_info.extracted_value:
                # 只有当标准化值等于提取值时才进行后备标准化
                original_value = slot_info.extracted_value
                normalized_value = original_value
                
                # 数字类型特殊处理
                if slot_type == 'number' and slot_name == 'passenger_count':
                    normalized_value = self._normalize_passenger_count(original_value)
                elif slot_type == 'number':
                    normalized_value = self._normalize_number(original_value)
                elif slot_type == 'date':
                    normalized_value = self._normalize_date(original_value)
                
                # 如果标准化后的值不同，更新SlotInfo
                if normalized_value != original_value:
                    logger.info(f"后备标准化: {slot_name} '{original_value}' -> '{normalized_value}'")
                    slot_info.normalized_value = normalized_value
                    slot_info.value = normalized_value
            
            return slot_info
            
        except Exception as e:
            logger.error(f"后备标准化失败: {slot_info.name}, 错误: {str(e)}")
            return slot_info
    
    def _normalize_passenger_count(self, value: str) -> str:
        """标准化乘客数量"""
        try:
            if isinstance(value, (int, float)):
                return str(int(value))
            
            value_str = str(value).strip()
            
            # 移除常见后缀
            for suffix in ['个人', '人', '位', '名', '个']:
                if value_str.endswith(suffix):
                    value_str = value_str[:-len(suffix)]
                    break
            
            # 中文数字转换
            chinese_numbers = {
                '一': 1, '二': 2, '三': 3, '四': 4, '五': 5,
                '六': 6, '七': 7, '八': 8, '九': 9, '十': 10
            }
            
            if value_str in chinese_numbers:
                return str(chinese_numbers[value_str])
            
            # 尝试直接转换为数字
            try:
                return str(int(float(value_str)))
            except (ValueError, TypeError):
                return '1'  # 默认返回1
                
        except Exception:
            return '1'  # 默认返回1
    
    def _normalize_number(self, value: str) -> str:
        """标准化通用数字"""
        try:
            import re
            # 提取数字
            numbers = re.findall(r'\d+', str(value))
            if numbers:
                return numbers[0]
            return str(value)
        except:
            return str(value)
    
    def _normalize_date(self, value: str) -> str:
        """标准化日期"""
        try:
            from datetime import datetime, timedelta
            
            value_str = str(value).strip()
            today = datetime.now()
            
            # 处理相对日期
            if value_str in ['今天', '今日']:
                return today.strftime('%Y-%m-%d')
            elif value_str in ['明天', '明日']:
                return (today + timedelta(days=1)).strftime('%Y-%m-%d')
            elif value_str in ['后天']:
                return (today + timedelta(days=2)).strftime('%Y-%m-%d')
            elif value_str in ['昨天', '昨日']:
                return (today - timedelta(days=1)).strftime('%Y-%m-%d')
            elif value_str in ['前天']:
                return (today - timedelta(days=2)).strftime('%Y-%m-%d')
            
            return value_str
        except:
            return str(value)


# 服务实例获取函数
async def get_enhanced_slot_service() -> EnhancedSlotService:
    """获取增强槽位服务实例"""
    from src.services.cache_service import get_cache_service
    from src.services.slot_service import SlotService
    from src.core.nlu_engine import NLUEngine
    
    # 使用异步方式获取已初始化的缓存服务
    cache_service = await get_cache_service()
    from src.api.dependencies import get_nlu_engine
    nlu_engine = await get_nlu_engine()
    slot_service = SlotService(cache_service, nlu_engine)
    
    return EnhancedSlotService(slot_service, cache_service)