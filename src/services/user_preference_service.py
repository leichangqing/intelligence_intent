"""
用户偏好服务 (B2B架构)
管理系统配置的用户偏好，而不是从前端请求获取
"""
from typing import Dict, Any, Optional, List
from datetime import datetime

from src.models.conversation import UserContext
from src.services.cache_service import get_cache_service
from src.utils.logger import get_logger

logger = get_logger(__name__)


class UserPreferenceService:
    """用户偏好服务 - B2B系统后台管理"""
    
    def __init__(self):
        self.cache_service = None
        self.cache_namespace = "user_preferences"
        self.default_ttl = 7200  # 2小时缓存
        self._initialized = False
    
    async def _ensure_initialized(self):
        """确保服务已初始化"""
        if not self._initialized:
            self.cache_service = await get_cache_service()
            self._initialized = True
    
    async def get_user_preferences(self, user_id: str) -> Dict[str, Any]:
        """
        获取用户偏好配置（从数据库/缓存）
        
        Args:
            user_id: 用户ID
            
        Returns:
            Dict: 用户偏好配置
        """
        try:
            # 确保服务已初始化
            await self._ensure_initialized()
            
            # 1. 尝试从缓存获取
            cache_key = f"user_preferences:{user_id}"
            cached_prefs = await self.cache_service.get(cache_key, namespace=self.cache_namespace)
            
            if cached_prefs:
                logger.debug(f"从缓存获取用户偏好: {user_id}")
                return cached_prefs
            
            # 2. 从数据库查询偏好配置
            preferences = {}
            
            # 查询用户偏好类型的上下文
            pref_contexts = UserContext.select().where(
                (UserContext.user_id == user_id) &
                (UserContext.context_type == 'preference') &
                (UserContext.is_active == True)
            ).order_by(UserContext.priority.desc())
            
            for ctx in pref_contexts:
                preferences[ctx.context_key] = ctx.context_value
            
            # 3. 如果没有配置，使用系统默认值
            if not preferences:
                preferences = self._get_default_preferences(user_id)
                # 保存默认配置到数据库
                await self._save_default_preferences(user_id, preferences)
            
            # 4. 缓存结果
            await self.cache_service.set(
                cache_key, preferences, 
                ttl=self.default_ttl, 
                namespace=self.cache_namespace
            )
            
            logger.info(f"获取用户偏好成功: {user_id}, 项目数: {len(preferences)}")
            return preferences
            
        except Exception as e:
            logger.error(f"获取用户偏好失败: {user_id}, 错误: {str(e)}")
            return self._get_default_preferences(user_id)
    
    async def update_user_preference(
        self, 
        user_id: str, 
        preference_key: str, 
        preference_value: Any,
        operator_id: str = "system"
    ) -> bool:
        """
        更新用户偏好配置（B2B管理员操作）
        
        Args:
            user_id: 用户ID
            preference_key: 偏好键
            preference_value: 偏好值
            operator_id: 操作者ID
            
        Returns:
            bool: 更新是否成功
        """
        try:
            # 确保服务已初始化
            await self._ensure_initialized()
            
            # 1. 查找现有配置
            existing_ctx = UserContext.select().where(
                (UserContext.user_id == user_id) &
                (UserContext.context_type == 'preference') &
                (UserContext.context_key == preference_key)
            ).first()
            
            if existing_ctx:
                # 更新现有配置
                old_value = existing_ctx.context_value
                existing_ctx.context_value = preference_value
                existing_ctx.updated_at = datetime.now()
                existing_ctx.save()
                
                logger.info(f"更新用户偏好: {user_id}.{preference_key}: {old_value} -> {preference_value}")
            else:
                # 创建新配置
                UserContext.create(
                    user_id=user_id,
                    context_type='preference',
                    context_key=preference_key,
                    context_value=preference_value,
                    scope='global',
                    priority=1,
                    is_active=True
                )
                
                logger.info(f"创建用户偏好: {user_id}.{preference_key} = {preference_value}")
            
            # 2. 清除缓存
            cache_key = f"user_preferences:{user_id}"
            await self.cache_service.delete(cache_key, namespace=self.cache_namespace)
            
            return True
            
        except Exception as e:
            logger.error(f"更新用户偏好失败: {user_id}.{preference_key}, 错误: {str(e)}")
            return False
    
    async def bulk_update_preferences(
        self, 
        user_id: str, 
        preferences: Dict[str, Any],
        operator_id: str = "system"
    ) -> Dict[str, bool]:
        """
        批量更新用户偏好
        
        Args:
            user_id: 用户ID
            preferences: 偏好字典
            operator_id: 操作者ID
            
        Returns:
            Dict: 每个偏好的更新结果
        """
        results = {}
        
        for key, value in preferences.items():
            results[key] = await self.update_user_preference(
                user_id, key, value, operator_id
            )
        
        success_count = sum(results.values())
        logger.info(f"批量更新用户偏好完成: {user_id}, 成功: {success_count}/{len(preferences)}")
        
        return results
    
    async def get_all_users_preferences(self) -> Dict[str, Dict[str, Any]]:
        """
        获取所有用户的偏好配置（管理员功能）
        
        Returns:
            Dict: {user_id: {preference_key: value}}
        """
        try:
            all_preferences = {}
            
            # 查询所有偏好配置
            contexts = UserContext.select().where(
                (UserContext.context_type == 'preference') &
                (UserContext.is_active == True)
            ).order_by(UserContext.user_id, UserContext.priority.desc())
            
            for ctx in contexts:
                user_id = ctx.user_id
                if user_id not in all_preferences:
                    all_preferences[user_id] = {}
                all_preferences[user_id][ctx.context_key] = ctx.context_value
            
            logger.info(f"获取所有用户偏好: 用户数={len(all_preferences)}")
            return all_preferences
            
        except Exception as e:
            logger.error(f"获取所有用户偏好失败: {str(e)}")
            return {}
    
    def _get_default_preferences(self, user_id: str) -> Dict[str, Any]:
        """
        获取系统默认偏好配置
        
        Args:
            user_id: 用户ID
            
        Returns:
            Dict: 默认偏好配置
        """
        return {
            'language': 'zh-CN',
            'currency': 'CNY',
            'timezone': 'Asia/Shanghai',
            'notification_enabled': True,
            'theme': 'light',
            'date_format': 'YYYY-MM-DD',
            'time_format': '24h',
            'auto_logout_minutes': 120,
            # 业务相关默认配置
            'preferred_airline': None,
            'preferred_hotel_chain': None,
            'default_travel_class': 'economy',
            'price_alert_enabled': False
        }
    
    async def _save_default_preferences(self, user_id: str, preferences: Dict[str, Any]) -> None:
        """
        保存默认偏好配置到数据库
        
        Args:
            user_id: 用户ID
            preferences: 偏好配置
        """
        try:
            for key, value in preferences.items():
                UserContext.create(
                    user_id=user_id,
                    context_type='preference',
                    context_key=key,
                    context_value=value,
                    scope='global',
                    priority=1,
                    is_active=True
                )
            
            logger.info(f"保存默认用户偏好: {user_id}, 项目数: {len(preferences)}")
            
        except Exception as e:
            logger.error(f"保存默认用户偏好失败: {user_id}, 错误: {str(e)}")


# 全局服务实例
_user_preference_service = None


def get_user_preference_service() -> UserPreferenceService:
    """获取用户偏好服务实例（单例模式）"""
    global _user_preference_service
    if _user_preference_service is None:
        _user_preference_service = UserPreferenceService()
    return _user_preference_service