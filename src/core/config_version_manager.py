"""
配置版本管理系统 (TASK-033)
提供配置的版本控制、变更追踪、回滚和审计功能
"""
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from enum import Enum
import json
import hashlib
import gzip
import base64
from datetime import datetime, timedelta
from pathlib import Path

from src.models.config import SystemConfig
from src.services.cache_service import CacheService
from src.utils.logger import get_logger

logger = get_logger(__name__)


class ChangeType(Enum):
    """变更类型"""
    CREATE = "create"
    UPDATE = "update"
    DELETE = "delete"
    ROLLBACK = "rollback"
    MIGRATE = "migrate"


class VersionStatus(Enum):
    """版本状态"""
    ACTIVE = "active"
    ARCHIVED = "archived"
    DEPRECATED = "deprecated"
    ROLLBACK = "rollback"


@dataclass
class ConfigChange:
    """配置变更记录"""
    field_name: str
    old_value: Any
    new_value: Any
    change_type: ChangeType
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class ConfigVersion:
    """配置版本"""
    version_id: str
    config_key: str
    config_data: Dict[str, Any]
    version_number: int
    hash_value: str
    created_at: datetime
    created_by: str
    description: str
    changes: List[ConfigChange] = field(default_factory=list)
    status: VersionStatus = VersionStatus.ACTIVE
    tags: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'version_id': self.version_id,
            'config_key': self.config_key,
            'config_data': self.config_data,
            'version_number': self.version_number,
            'hash_value': self.hash_value,
            'created_at': self.created_at.isoformat(),
            'created_by': self.created_by,
            'description': self.description,
            'changes': [
                {
                    'field_name': change.field_name,
                    'old_value': change.old_value,
                    'new_value': change.new_value,
                    'change_type': change.change_type.value,
                    'timestamp': change.timestamp.isoformat()
                }
                for change in self.changes
            ],
            'status': self.status.value,
            'tags': self.tags,
            'metadata': self.metadata
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ConfigVersion':
        """从字典创建"""
        changes = [
            ConfigChange(
                field_name=change['field_name'],
                old_value=change['old_value'],
                new_value=change['new_value'],
                change_type=ChangeType(change['change_type']),
                timestamp=datetime.fromisoformat(change['timestamp'])
            )
            for change in data.get('changes', [])
        ]
        
        return cls(
            version_id=data['version_id'],
            config_key=data['config_key'],
            config_data=data['config_data'],
            version_number=data['version_number'],
            hash_value=data['hash_value'],
            created_at=datetime.fromisoformat(data['created_at']),
            created_by=data['created_by'],
            description=data['description'],
            changes=changes,
            status=VersionStatus(data.get('status', 'active')),
            tags=data.get('tags', []),
            metadata=data.get('metadata', {})
        )


@dataclass
class VersionDiff:
    """版本差异"""
    from_version: str
    to_version: str
    added_fields: Dict[str, Any] = field(default_factory=dict)
    modified_fields: Dict[str, Tuple[Any, Any]] = field(default_factory=dict)
    removed_fields: Dict[str, Any] = field(default_factory=dict)
    summary: str = ""


class ConfigVersionManager:
    """配置版本管理器"""
    
    def __init__(self, cache_service: CacheService):
        self.cache_service = cache_service
        self.cache_namespace = "config_versions"
        
        # 版本存储
        self.versions: Dict[str, List[ConfigVersion]] = {}
        self.version_index: Dict[str, ConfigVersion] = {}
        
        # 配置
        self.max_versions_per_config = 20
        self.compression_enabled = True
        self.auto_cleanup_days = 90
        
        # 初始化存储
        self._initialize_storage()
    
    def _initialize_storage(self):
        """初始化存储"""
        try:
            # 从数据库加载版本历史
            self._load_versions_from_storage()
            logger.info("配置版本管理器初始化完成")
        except Exception as e:
            logger.error(f"初始化配置版本管理器失败: {str(e)}")
    
    def _load_versions_from_storage(self):
        """从存储加载版本历史"""
        try:
            # 从系统配置表加载版本数据
            version_configs = SystemConfig.select().where(
                SystemConfig.category == "config_version"
            )
            
            for config in version_configs:
                try:
                    version_data = json.loads(config.config_value)
                    version = ConfigVersion.from_dict(version_data)
                    
                    # 添加到版本存储
                    config_key = version.config_key
                    if config_key not in self.versions:
                        self.versions[config_key] = []
                    
                    self.versions[config_key].append(version)
                    self.version_index[version.version_id] = version
                    
                except Exception as e:
                    logger.error(f"加载版本数据失败: {config.config_key}, 错误: {str(e)}")
            
            # 按版本号排序
            for config_key in self.versions:
                self.versions[config_key].sort(key=lambda v: v.version_number)
            
            logger.info(f"已加载 {len(self.version_index)} 个配置版本")
            
        except Exception as e:
            logger.error(f"从存储加载版本失败: {str(e)}")
    
    def create_version(self, config_key: str, config_data: Dict[str, Any],
                      description: str, created_by: str = "system",
                      tags: List[str] = None) -> ConfigVersion:
        """创建新版本"""
        try:
            # 获取现有版本
            existing_versions = self.versions.get(config_key, [])
            
            # 计算版本号
            version_number = len(existing_versions) + 1
            
            # 生成版本ID和哈希
            version_id = f"{config_key}_v{version_number}_{int(datetime.now().timestamp())}"
            hash_value = self._calculate_hash(config_data)
            
            # 检查是否有实际变更
            if existing_versions:
                latest_version = existing_versions[-1]
                if latest_version.hash_value == hash_value:
                    logger.info(f"配置无变更，跳过版本创建: {config_key}")
                    return latest_version
            
            # 计算变更
            changes = self._calculate_changes(config_key, config_data)
            
            # 创建版本
            version = ConfigVersion(
                version_id=version_id,
                config_key=config_key,
                config_data=config_data.copy(),
                version_number=version_number,
                hash_value=hash_value,
                created_at=datetime.now(),
                created_by=created_by,
                description=description,
                changes=changes,
                tags=tags or []
            )
            
            # 保存版本
            self._save_version(version)
            
            # 添加到内存存储
            if config_key not in self.versions:
                self.versions[config_key] = []
            
            self.versions[config_key].append(version)
            self.version_index[version_id] = version
            
            # 清理旧版本
            self._cleanup_old_versions(config_key)
            
            logger.info(f"创建配置版本: {version_id}")
            return version
            
        except Exception as e:
            logger.error(f"创建配置版本失败: {config_key}, 错误: {str(e)}")
            raise
    
    def _calculate_hash(self, data: Dict[str, Any]) -> str:
        """计算数据哈希"""
        content = json.dumps(data, sort_keys=True, ensure_ascii=False)
        return hashlib.sha256(content.encode()).hexdigest()[:16]
    
    def _calculate_changes(self, config_key: str, new_data: Dict[str, Any]) -> List[ConfigChange]:
        """计算配置变更"""
        changes = []
        
        try:
            existing_versions = self.versions.get(config_key, [])
            if not existing_versions:
                # 首次创建
                for field, value in new_data.items():
                    changes.append(ConfigChange(
                        field_name=field,
                        old_value=None,
                        new_value=value,
                        change_type=ChangeType.CREATE
                    ))
            else:
                # 比较与最新版本的差异
                latest_version = existing_versions[-1]
                old_data = latest_version.config_data
                
                # 检查新增和修改的字段
                for field, new_value in new_data.items():
                    if field not in old_data:
                        changes.append(ConfigChange(
                            field_name=field,
                            old_value=None,
                            new_value=new_value,
                            change_type=ChangeType.CREATE
                        ))
                    elif old_data[field] != new_value:
                        changes.append(ConfigChange(
                            field_name=field,
                            old_value=old_data[field],
                            new_value=new_value,
                            change_type=ChangeType.UPDATE
                        ))
                
                # 检查删除的字段
                for field, old_value in old_data.items():
                    if field not in new_data:
                        changes.append(ConfigChange(
                            field_name=field,
                            old_value=old_value,
                            new_value=None,
                            change_type=ChangeType.DELETE
                        ))
            
        except Exception as e:
            logger.error(f"计算配置变更失败: {config_key}, 错误: {str(e)}")
        
        return changes
    
    def _save_version(self, version: ConfigVersion):
        """保存版本到存储"""
        try:
            # 压缩版本数据
            version_data = version.to_dict()
            
            if self.compression_enabled:
                compressed_data = self._compress_data(version_data)
                storage_data = {
                    'compressed': True,
                    'data': compressed_data
                }
            else:
                storage_data = {
                    'compressed': False,
                    'data': version_data
                }
            
            # 保存到系统配置表
            SystemConfig.set_config(
                key=f"version_{version.version_id}",
                value=storage_data,
                description=f"配置版本: {version.config_key} v{version.version_number}",
                category="config_version"
            )
            
        except Exception as e:
            logger.error(f"保存版本失败: {version.version_id}, 错误: {str(e)}")
            raise
    
    def _compress_data(self, data: Dict[str, Any]) -> str:
        """压缩数据"""
        try:
            json_data = json.dumps(data, ensure_ascii=False)
            compressed = gzip.compress(json_data.encode('utf-8'))
            return base64.b64encode(compressed).decode('ascii')
        except Exception as e:
            logger.error(f"数据压缩失败: {str(e)}")
            return json.dumps(data, ensure_ascii=False)
    
    def _decompress_data(self, compressed_data: str) -> Dict[str, Any]:
        """解压数据"""
        try:
            compressed = base64.b64decode(compressed_data.encode('ascii'))
            decompressed = gzip.decompress(compressed)
            return json.loads(decompressed.decode('utf-8'))
        except Exception as e:
            logger.error(f"数据解压失败: {str(e)}")
            return {}
    
    def get_version(self, version_id: str) -> Optional[ConfigVersion]:
        """获取指定版本"""
        return self.version_index.get(version_id)
    
    def get_latest_version(self, config_key: str) -> Optional[ConfigVersion]:
        """获取最新版本"""
        versions = self.versions.get(config_key, [])
        return versions[-1] if versions else None
    
    def get_version_history(self, config_key: str, limit: int = 10) -> List[ConfigVersion]:
        """获取版本历史"""
        versions = self.versions.get(config_key, [])
        return versions[-limit:] if limit > 0 else versions
    
    def get_version_by_number(self, config_key: str, version_number: int) -> Optional[ConfigVersion]:
        """根据版本号获取版本"""
        versions = self.versions.get(config_key, [])
        for version in versions:
            if version.version_number == version_number:
                return version
        return None
    
    def compare_versions(self, version_id1: str, version_id2: str) -> Optional[VersionDiff]:
        """比较两个版本的差异"""
        try:
            version1 = self.get_version(version_id1)
            version2 = self.get_version(version_id2)
            
            if not version1 or not version2:
                return None
            
            diff = VersionDiff(
                from_version=version_id1,
                to_version=version_id2
            )
            
            data1 = version1.config_data
            data2 = version2.config_data
            
            # 检查新增字段
            for key, value in data2.items():
                if key not in data1:
                    diff.added_fields[key] = value
            
            # 检查修改字段
            for key, value in data2.items():
                if key in data1 and data1[key] != value:
                    diff.modified_fields[key] = (data1[key], value)
            
            # 检查删除字段
            for key, value in data1.items():
                if key not in data2:
                    diff.removed_fields[key] = value
            
            # 生成摘要
            changes_count = len(diff.added_fields) + len(diff.modified_fields) + len(diff.removed_fields)
            diff.summary = f"共 {changes_count} 项变更: "
            diff.summary += f"{len(diff.added_fields)} 项新增, "
            diff.summary += f"{len(diff.modified_fields)} 项修改, "
            diff.summary += f"{len(diff.removed_fields)} 项删除"
            
            return diff
            
        except Exception as e:
            logger.error(f"比较版本失败: {version_id1} vs {version_id2}, 错误: {str(e)}")
            return None
    
    def rollback_to_version(self, config_key: str, target_version_id: str,
                           rollback_by: str = "system") -> Optional[ConfigVersion]:
        """回滚到指定版本"""
        try:
            target_version = self.get_version(target_version_id)
            if not target_version or target_version.config_key != config_key:
                logger.error(f"目标版本不存在或配置键不匹配: {target_version_id}")
                return None
            
            # 创建回滚版本
            rollback_description = f"回滚到版本 {target_version.version_number} ({target_version_id})"
            
            rollback_version = self.create_version(
                config_key=config_key,
                config_data=target_version.config_data.copy(),
                description=rollback_description,
                created_by=rollback_by,
                tags=["rollback"]
            )
            
            # 标记为回滚版本
            rollback_version.status = VersionStatus.ROLLBACK
            rollback_version.metadata['rollback_from'] = target_version_id
            
            logger.info(f"配置回滚完成: {config_key} -> {target_version_id}")
            return rollback_version
            
        except Exception as e:
            logger.error(f"配置回滚失败: {config_key} -> {target_version_id}, 错误: {str(e)}")
            return None
    
    def tag_version(self, version_id: str, tags: List[str]) -> bool:
        """为版本添加标签"""
        try:
            version = self.get_version(version_id)
            if not version:
                return False
            
            # 添加标签（去重）
            version.tags = list(set(version.tags + tags))
            
            # 更新存储
            self._save_version(version)
            
            logger.info(f"版本标签更新: {version_id} -> {tags}")
            return True
            
        except Exception as e:
            logger.error(f"更新版本标签失败: {version_id}, 错误: {str(e)}")
            return False
    
    def search_versions(self, config_key: Optional[str] = None,
                       tags: List[str] = None,
                       created_by: Optional[str] = None,
                       date_range: Tuple[datetime, datetime] = None) -> List[ConfigVersion]:
        """搜索版本"""
        try:
            results = []
            
            # 确定搜索范围
            if config_key:
                search_versions = self.versions.get(config_key, [])
            else:
                search_versions = []
                for versions in self.versions.values():
                    search_versions.extend(versions)
            
            # 应用过滤条件
            for version in search_versions:
                # 标签过滤
                if tags and not any(tag in version.tags for tag in tags):
                    continue
                
                # 创建者过滤
                if created_by and version.created_by != created_by:
                    continue
                
                # 日期范围过滤
                if date_range:
                    start_date, end_date = date_range
                    if not (start_date <= version.created_at <= end_date):
                        continue
                
                results.append(version)
            
            # 按创建时间倒序排列
            results.sort(key=lambda v: v.created_at, reverse=True)
            
            return results
            
        except Exception as e:
            logger.error(f"搜索版本失败: {str(e)}")
            return []
    
    def _cleanup_old_versions(self, config_key: str):
        """清理旧版本"""
        try:
            versions = self.versions.get(config_key, [])
            
            if len(versions) <= self.max_versions_per_config:
                return
            
            # 保留最新的版本
            versions_to_keep = versions[-self.max_versions_per_config:]
            versions_to_remove = versions[:-self.max_versions_per_config]
            
            # 删除旧版本
            for version in versions_to_remove:
                # 从索引移除
                if version.version_id in self.version_index:
                    del self.version_index[version.version_id]
                
                # 从存储删除
                try:
                    config_key_to_delete = f"version_{version.version_id}"
                    SystemConfig.delete().where(
                        SystemConfig.config_key == config_key_to_delete
                    ).execute()
                except Exception as e:
                    logger.error(f"删除存储版本失败: {version.version_id}, 错误: {str(e)}")
            
            # 更新版本列表
            self.versions[config_key] = versions_to_keep
            
            logger.info(f"清理旧版本: {config_key}, 删除 {len(versions_to_remove)} 个版本")
            
        except Exception as e:
            logger.error(f"清理旧版本失败: {config_key}, 错误: {str(e)}")
    
    def get_statistics(self) -> Dict[str, Any]:
        """获取版本统计信息"""
        try:
            total_versions = len(self.version_index)
            total_configs = len(self.versions)
            
            # 按状态统计
            status_stats = {}
            for status in VersionStatus:
                status_stats[status.value] = 0
            
            for version in self.version_index.values():
                status_stats[version.status.value] += 1
            
            # 按创建者统计
            creator_stats = {}
            for version in self.version_index.values():
                creator = version.created_by
                creator_stats[creator] = creator_stats.get(creator, 0) + 1
            
            # 最近活动
            recent_versions = sorted(
                self.version_index.values(),
                key=lambda v: v.created_at,
                reverse=True
            )[:5]
            
            return {
                'total_versions': total_versions,
                'total_configs': total_configs,
                'average_versions_per_config': total_versions / max(total_configs, 1),
                'status_distribution': status_stats,
                'creator_distribution': creator_stats,
                'recent_activity': [
                    {
                        'version_id': v.version_id,
                        'config_key': v.config_key,
                        'created_at': v.created_at.isoformat(),
                        'created_by': v.created_by,
                        'description': v.description
                    }
                    for v in recent_versions
                ]
            }
            
        except Exception as e:
            logger.error(f"获取版本统计失败: {str(e)}")
            return {}
    
    def export_versions(self, config_key: Optional[str] = None,
                       format: str = 'json') -> str:
        """导出版本数据"""
        try:
            if config_key:
                versions_to_export = self.versions.get(config_key, [])
            else:
                versions_to_export = list(self.version_index.values())
            
            export_data = {
                'export_time': datetime.now().isoformat(),
                'total_versions': len(versions_to_export),
                'versions': [version.to_dict() for version in versions_to_export]
            }
            
            if format == 'json':
                return json.dumps(export_data, indent=2, ensure_ascii=False)
            else:
                return str(export_data)
                
        except Exception as e:
            logger.error(f"导出版本数据失败: {str(e)}")
            return ""
    
    def cleanup(self):
        """清理资源"""
        try:
            # 清理过期版本
            cutoff_date = datetime.now() - timedelta(days=self.auto_cleanup_days)
            
            expired_versions = []
            for version in self.version_index.values():
                if (version.created_at < cutoff_date and 
                    version.status not in [VersionStatus.ACTIVE, VersionStatus.ROLLBACK]):
                    expired_versions.append(version)
            
            for version in expired_versions:
                # 从内存移除
                if version.version_id in self.version_index:
                    del self.version_index[version.version_id]
                
                # 从配置列表移除
                config_versions = self.versions.get(version.config_key, [])
                if version in config_versions:
                    config_versions.remove(version)
                
                # 从存储删除
                config_key_to_delete = f"version_{version.version_id}"
                SystemConfig.delete().where(
                    SystemConfig.config_key == config_key_to_delete
                ).execute()
            
            logger.info(f"清理过期版本: {len(expired_versions)} 个")
            
        except Exception as e:
            logger.error(f"清理版本管理器失败: {str(e)}")


# 全局版本管理器实例
_version_manager: Optional[ConfigVersionManager] = None


def get_version_manager(cache_service: CacheService) -> ConfigVersionManager:
    """获取全局版本管理器实例"""
    global _version_manager
    
    if _version_manager is None:
        _version_manager = ConfigVersionManager(cache_service)
    
    return _version_manager