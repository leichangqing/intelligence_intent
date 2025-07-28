"""
用户档案服务
处理用户偏好、历史行为和个性化信息
"""

from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
import json
import hashlib
from collections import defaultdict

from ..models.conversation import Conversation, Session
from ..models.slot_value import SlotValue
from ..services.cache_service import CacheService
from ..utils.logger import get_logger

logger = get_logger(__name__)


class UserProfileService:
    """用户档案服务"""
    
    def __init__(self, cache_service: CacheService):
        self.cache_service = cache_service
        self.profile_cache_ttl = 3600  # 1小时缓存
        self.behavior_analysis_window = 30  # 30天行为分析窗口
    
    async def get_user_profile(self, user_id: str) -> Dict[str, Any]:
        """
        获取用户档案信息
        
        Args:
            user_id: 用户ID
            
        Returns:
            Dict: 用户档案信息
        """
        cache_key = f"user_profile:{user_id}"
        
        # 尝试从缓存获取
        cached_profile = await self.cache_service.get(cache_key)
        if cached_profile:
            try:
                if isinstance(cached_profile, str):
                    return json.loads(cached_profile)
                elif isinstance(cached_profile, dict):
                    return cached_profile
                else:
                    logger.warning(f"用户档案缓存类型异常: {user_id}, type: {type(cached_profile)}")
            except (json.JSONDecodeError, TypeError) as e:
                logger.warning(f"用户档案缓存解析失败: {user_id}, 错误: {e}")
        
        # 构建用户档案
        profile = await self._build_user_profile(user_id)
        
        # 缓存结果
        await self.cache_service.set(
            cache_key, 
            profile, 
            ttl=self.profile_cache_ttl
        )
        
        return profile
    
    async def _build_user_profile(self, user_id: str) -> Dict[str, Any]:
        """构建用户档案"""
        profile = {
            "user_id": user_id,
            "preferences": await self._get_user_preferences(user_id),
            "frequent_values": await self._get_frequent_slot_values(user_id),
            "behavior_patterns": await self._analyze_behavior_patterns(user_id),
            "last_updated": datetime.now().isoformat()
        }
        
        logger.debug(f"构建用户档案完成: {user_id}")
        return profile
    
    async def _get_user_preferences(self, user_id: str) -> Dict[str, Any]:
        """获取用户偏好"""
        try:
            # 分析用户的常用值和偏好
            recent_conversations = list(
                Conversation.select()
                .where(Conversation.user_id == user_id)
                .where(Conversation.created_at >= datetime.now() - timedelta(days=self.behavior_analysis_window))
                .order_by(Conversation.created_at.desc())
                .limit(100)
            )
            
            preferences = {
                "preferred_departure_cities": [],
                "preferred_arrival_cities": [],
                "common_passenger_count": 1,
                "typical_interaction_time": "morning",  # morning, afternoon, evening
                "language_preference": "zh-CN",
                "contact_info": {}
            }
            
            # 统计城市偏好
            departure_cities = []
            arrival_cities = []
            passenger_counts = []
            interaction_hours = []
            
            for conv in recent_conversations:
                if conv.slots_filled:
                    try:
                        slots = json.loads(conv.slots_filled)
                        
                        if "departure_city" in slots:
                            departure_cities.append(slots["departure_city"])
                        if "arrival_city" in slots:
                            arrival_cities.append(slots["arrival_city"])
                        if "passenger_count" in slots:
                            try:
                                passenger_counts.append(int(slots["passenger_count"]))
                            except (ValueError, TypeError):
                                pass
                        
                        # 记录交互时间
                        hour = conv.created_at.hour
                        interaction_hours.append(hour)
                        
                    except json.JSONDecodeError:
                        continue
            
            # 计算最常用的值
            if departure_cities:
                city_counts = defaultdict(int)
                for city in departure_cities:
                    city_counts[city] += 1
                preferences["preferred_departure_cities"] = [
                    city for city, _ in sorted(city_counts.items(), key=lambda x: x[1], reverse=True)[:3]
                ]
            
            if arrival_cities:
                city_counts = defaultdict(int)
                for city in arrival_cities:
                    city_counts[city] += 1
                preferences["preferred_arrival_cities"] = [
                    city for city, _ in sorted(city_counts.items(), key=lambda x: x[1], reverse=True)[:3]
                ]
            
            if passenger_counts:
                count_freq = defaultdict(int)
                for count in passenger_counts:
                    count_freq[count] += 1
                preferences["common_passenger_count"] = max(count_freq.items(), key=lambda x: x[1])[0]
            
            # 分析交互时间偏好
            if interaction_hours:
                avg_hour = sum(interaction_hours) / len(interaction_hours)
                if avg_hour < 12:
                    preferences["typical_interaction_time"] = "morning"
                elif avg_hour < 18:
                    preferences["typical_interaction_time"] = "afternoon"
                else:
                    preferences["typical_interaction_time"] = "evening"
            
            return preferences
            
        except Exception as e:
            logger.error(f"获取用户偏好失败: {user_id}, 错误: {e}")
            return {}
    
    async def _get_frequent_slot_values(self, user_id: str) -> Dict[str, Any]:
        """获取用户的常用槽位值"""
        try:
            # 查询用户的槽位值历史
            recent_slot_values = list(
                SlotValue.select(SlotValue, SlotValue.slot)
                .join(Conversation, on=(SlotValue.conversation_id == Conversation.id))
                .where(Conversation.user_id == user_id)
                .where(SlotValue.created_at >= datetime.now() - timedelta(days=self.behavior_analysis_window))
                .where(SlotValue.validation_status == 'valid')
            )
            
            # 按槽位类型统计频率
            slot_frequencies = defaultdict(lambda: defaultdict(int))
            
            for slot_value in recent_slot_values:
                slot_name = slot_value.slot.slot_name
                value = slot_value.normalized_value or slot_value.extracted_value
                if value:  # 只统计有值的槽位
                    slot_frequencies[slot_name][value] += 1
            
            # 提取每个槽位的最常用值
            frequent_values = {}
            for slot_name, value_counts in slot_frequencies.items():
                if value_counts:
                    # 按频率排序，取前3个
                    sorted_values = sorted(value_counts.items(), key=lambda x: x[1], reverse=True)
                    frequent_values[slot_name] = {
                        "most_frequent": sorted_values[0][0],
                        "frequency": sorted_values[0][1],
                        "alternatives": [v for v, _ in sorted_values[1:4]]  # 前3个备选
                    }
            
            return frequent_values
            
        except Exception as e:
            logger.error(f"获取常用槽位值失败: {user_id}, 错误: {e}")
            return {}
    
    async def _analyze_behavior_patterns(self, user_id: str) -> Dict[str, Any]:
        """分析用户行为模式"""
        try:
            # 查询用户交互历史
            conversations = list(
                Conversation.select()
                .where(Conversation.user_id == user_id)
                .where(Conversation.created_at >= datetime.now() - timedelta(days=self.behavior_analysis_window))
                .order_by(Conversation.created_at.desc())
            )
            
            if not conversations:
                return {}
            
            patterns = {
                "interaction_frequency": 0,  # 每天平均交互次数
                "common_intents": [],
                "session_duration_avg": 0,  # 平均会话时长（分钟）
                "completion_rate": 0,  # 意图完成率
                "peak_hours": [],  # 高峰时段
                "retry_patterns": {}  # 重试模式
            }
            
            # 计算交互频率
            total_days = min(self.behavior_analysis_window, 
                           (datetime.now() - conversations[-1].created_at).days + 1)
            patterns["interaction_frequency"] = len(conversations) / max(total_days, 1)
            
            # 统计常用意图
            intent_counts = defaultdict(int)
            completed_intents = 0
            session_durations = []
            hourly_interactions = defaultdict(int)
            
            for conv in conversations:
                # 意图统计
                if conv.intent_name:
                    intent_counts[conv.intent_name] += 1
                
                # 完成率统计
                if conv.status == 'completed':
                    completed_intents += 1
                
                # 会话时长估算（使用 updated_at 作为结束时间的近似值）
                if conv.updated_at and conv.created_at:
                    duration = (conv.updated_at - conv.created_at).total_seconds() / 60
                    # 只有当时长大于0且小于合理值时才计入统计（避免异常数据）
                    if 0 < duration < 1440:  # 小于24小时
                        session_durations.append(duration)
                
                # 时段统计
                hourly_interactions[conv.created_at.hour] += 1
            
            # 常用意图（前5个）
            patterns["common_intents"] = [
                intent for intent, _ in sorted(intent_counts.items(), key=lambda x: x[1], reverse=True)[:5]
            ]
            
            # 完成率
            patterns["completion_rate"] = completed_intents / len(conversations) if conversations else 0
            
            # 平均会话时长
            patterns["session_duration_avg"] = sum(session_durations) / len(session_durations) if session_durations else 0
            
            # 高峰时段（交互次数最多的3个小时）
            patterns["peak_hours"] = [
                hour for hour, _ in sorted(hourly_interactions.items(), key=lambda x: x[1], reverse=True)[:3]
            ]
            
            return patterns
            
        except Exception as e:
            logger.error(f"分析用户行为模式失败: {user_id}, 错误: {e}")
            return {}
    
    async def update_user_preference(self, user_id: str, preference_key: str, preference_value: Any):
        """更新用户偏好"""
        try:
            profile = await self.get_user_profile(user_id)
            
            if "preferences" not in profile:
                profile["preferences"] = {}
            
            profile["preferences"][preference_key] = preference_value
            profile["last_updated"] = datetime.now().isoformat()
            
            # 更新缓存
            cache_key = f"user_profile:{user_id}"
            await self.cache_service.set(cache_key, profile, ttl=self.profile_cache_ttl)
            
            logger.info(f"更新用户偏好: {user_id}, {preference_key} = {preference_value}")
            
        except Exception as e:
            logger.error(f"更新用户偏好失败: {user_id}, {preference_key}, 错误: {e}")
    
    async def get_personalized_slot_suggestions(self, user_id: str, slot_name: str) -> List[str]:
        """
        获取个性化的槽位建议值
        
        Args:
            user_id: 用户ID
            slot_name: 槽位名称
            
        Returns:
            List[str]: 建议值列表
        """
        try:
            profile = await self.get_user_profile(user_id)
            suggestions = []
            
            # 从常用值获取建议
            frequent_values = profile.get("frequent_values", {})
            if slot_name in frequent_values:
                freq_data = frequent_values[slot_name]
                suggestions.append(freq_data["most_frequent"])
                suggestions.extend(freq_data.get("alternatives", []))
            
            # 从偏好获取建议
            preferences = profile.get("preferences", {})
            
            # 特定槽位的偏好映射
            preference_mapping = {
                "departure_city": preferences.get("preferred_departure_cities", []),
                "arrival_city": preferences.get("preferred_arrival_cities", []),
                "passenger_count": [str(preferences.get("common_passenger_count", 1))]
            }
            
            if slot_name in preference_mapping:
                suggestions.extend(preference_mapping[slot_name])
            
            # 去重并保持顺序
            unique_suggestions = []
            seen = set()
            for suggestion in suggestions:
                if suggestion not in seen:
                    unique_suggestions.append(suggestion)
                    seen.add(suggestion)
            
            return unique_suggestions[:5]  # 最多返回5个建议
            
        except Exception as e:
            logger.error(f"获取个性化槽位建议失败: {user_id}, {slot_name}, 错误: {e}")
            return []
    
    async def clear_user_profile_cache(self, user_id: str):
        """清除用户档案缓存"""
        cache_key = f"user_profile:{user_id}"
        await self.cache_service.delete(cache_key)
        logger.debug(f"清除用户档案缓存: {user_id}")


# 全局用户档案服务实例（需要在依赖注入中初始化）
user_profile_service: Optional[UserProfileService] = None


async def get_user_profile_service(cache_service: CacheService) -> UserProfileService:
    """获取用户档案服务实例"""
    global user_profile_service
    if user_profile_service is None:
        user_profile_service = UserProfileService(cache_service)
    return user_profile_service