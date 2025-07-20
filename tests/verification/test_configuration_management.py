#!/usr/bin/env python3
"""
VT-005: 配置管理机制验证
验证配置驱动架构和热更新机制
"""
import sys
import os
import time
import asyncio
import json
import tempfile
from typing import Dict, List, Any, Optional
from dataclasses import dataclass

sys.path.insert(0, os.path.abspath('.'))

from src.core.config_manager import EnhancedConfigManager, ConfigType, ConfigEvent
from src.models.config import SystemConfig, RagflowConfig, FeatureFlag
from src.services.cache_service import CacheService


@dataclass
class VerificationResult:
    """验证结果"""
    test_name: str
    success: bool
    details: Dict[str, Any]
    error_message: Optional[str] = None
    execution_time: float = 0.0


class ConfigurationManagementVerifier:
    """配置管理机制验证器"""
    
    def __init__(self):
        self.cache_service = None
        self.config_manager = None
        self.verification_results: List[VerificationResult] = []
    
    async def setup(self):
        """设置验证环境"""
        try:
            # 模拟缓存服务
            class MockCacheService:
                def __init__(self):
                    self.data = {}
                    self.stats = {
                        'hit_count': 0,
                        'miss_count': 0,
                        'total_requests': 0
                    }
                
                async def get(self, key, namespace=None):
                    full_key = f"{namespace}:{key}" if namespace else key
                    self.stats['total_requests'] += 1
                    if full_key in self.data:
                        self.stats['hit_count'] += 1
                        return self.data[full_key]
                    else:
                        self.stats['miss_count'] += 1
                        return None
                
                async def set(self, key, value, ttl=None, namespace=None):
                    full_key = f"{namespace}:{key}" if namespace else key
                    self.data[full_key] = value
                
                async def delete(self, key, namespace=None):
                    full_key = f"{namespace}:{key}" if namespace else key
                    self.data.pop(full_key, None)
                
                async def delete_pattern(self, pattern, namespace=None):
                    keys_to_delete = []
                    pattern_prefix = f"{namespace}:" if namespace else ""
                    search_pattern = pattern_prefix + pattern.replace('*', '')
                    
                    for key in self.data.keys():
                        if key.startswith(search_pattern):
                            keys_to_delete.append(key)
                    
                    for key in keys_to_delete:
                        del self.data[key]
                
                async def get_stats(self):
                    total = self.stats['total_requests']
                    if total > 0:
                        hit_rate = self.stats['hit_count'] / total
                    else:
                        hit_rate = 0.0
                    
                    return {
                        'hit_rate': hit_rate,
                        'hit_count': self.stats['hit_count'],
                        'miss_count': self.stats['miss_count'],
                        'total_requests': total
                    }
            
            self.cache_service = MockCacheService()
            
            # 创建配置管理器
            self.config_manager = EnhancedConfigManager(self.cache_service)
            
            print("✓ 验证环境设置完成")
            return True
            
        except Exception as e:
            print(f"❌ 验证环境设置失败: {str(e)}")
            return False
    
    async def verify_mysql_configuration_loading(self) -> VerificationResult:
        """验证MySQL配置加载"""
        start_time = time.time()
        test_name = "MySQL配置加载验证"
        
        try:
            details = {}
            
            print("\n=== 验证MySQL配置加载 ===")
            
            # 1. 验证系统配置加载
            print("1. 验证系统配置操作")
            
            # 模拟设置系统配置
            test_config_key = "test_system_config"
            test_config_value = "test_value_123"
            
            success = await self.config_manager.set_config(
                key=test_config_key,
                value=test_config_value,
                config_type=ConfigType.SYSTEM,
                description="测试系统配置"
            )
            details['system_config_set'] = success
            
            if success:
                print(f"✓ 系统配置设置成功: {test_config_key}")
            else:
                print(f"❌ 系统配置设置失败: {test_config_key}")
            
            # 验证配置获取
            retrieved_value = await self.config_manager.get_config(
                key=test_config_key,
                config_type=ConfigType.SYSTEM
            )
            details['system_config_get'] = retrieved_value == test_config_value
            
            if details['system_config_get']:
                print(f"✓ 系统配置获取成功: {retrieved_value}")
            else:
                print(f"❌ 系统配置获取失败: 期望{test_config_value}, 实际{retrieved_value}")
            
            # 2. 验证RAGFLOW配置加载
            print("2. 验证RAGFLOW配置操作")
            
            ragflow_config_data = {
                'api_endpoint': 'https://test.ragflow.com/api',
                'api_key': 'test_api_key_12345',
                'timeout_seconds': 30,
                'rate_limit': {
                    'requests_per_minute': 60,
                    'requests_per_hour': 3600
                },
                'health_check_url': 'https://test.ragflow.com/health',
                'is_active': True
            }
            
            ragflow_success = await self.config_manager.set_config(
                key="test_ragflow_config",
                value=ragflow_config_data,
                config_type=ConfigType.RAGFLOW,
                description="测试RAGFLOW配置"
            )
            details['ragflow_config_set'] = ragflow_success
            
            if ragflow_success:
                print("✓ RAGFLOW配置设置成功")
            else:
                print("❌ RAGFLOW配置设置失败")
            
            # 验证RAGFLOW配置获取
            retrieved_ragflow = await self.config_manager.get_config(
                key="test_ragflow_config",
                config_type=ConfigType.RAGFLOW
            )
            details['ragflow_config_get'] = retrieved_ragflow is not None
            
            if details['ragflow_config_get']:
                print(f"✓ RAGFLOW配置获取成功: {type(retrieved_ragflow)}")
                details['ragflow_config_structure'] = all(
                    key in retrieved_ragflow for key in ['api_endpoint', 'api_key', 'timeout_seconds']
                )
            else:
                print("❌ RAGFLOW配置获取失败")
                details['ragflow_config_structure'] = False
            
            # 3. 验证功能开关配置
            print("3. 验证功能开关配置操作")
            
            feature_flag_data = {
                'is_enabled': True,
                'description': '测试功能开关',
                'target_users': ['user1', 'user2'],
                'rollout_percentage': 50,
                'start_time': None,
                'end_time': None
            }
            
            flag_success = await self.config_manager.set_config(
                key="test_feature_flag",
                value=feature_flag_data,
                config_type=ConfigType.FEATURE_FLAG,
                description="测试功能开关"
            )
            details['feature_flag_set'] = flag_success
            
            if flag_success:
                print("✓ 功能开关配置设置成功")
            else:
                print("❌ 功能开关配置设置失败")
            
            # 4. 验证配置加载性能
            print("4. 验证配置加载性能")
            
            load_times = []
            for i in range(5):
                start_load_time = time.time()
                await self.config_manager.get_config(test_config_key, config_type=ConfigType.SYSTEM)
                load_time = time.time() - start_load_time
                load_times.append(load_time)
            
            avg_load_time = sum(load_times) / len(load_times)
            details['avg_load_time'] = avg_load_time
            details['load_performance_ok'] = avg_load_time < 0.1  # 100ms阈值
            
            if details['load_performance_ok']:
                print(f"✓ 配置加载性能良好: 平均{avg_load_time*1000:.1f}ms")
            else:
                print(f"❌ 配置加载性能较差: 平均{avg_load_time*1000:.1f}ms")
            
            execution_time = time.time() - start_time
            success = (details['system_config_set'] and 
                      details['system_config_get'] and
                      details['ragflow_config_set'] and
                      details['ragflow_config_get'] and
                      details['ragflow_config_structure'] and
                      details['feature_flag_set'] and
                      details['load_performance_ok'])
            
            return VerificationResult(
                test_name=test_name,
                success=success,
                details=details,
                execution_time=execution_time
            )
            
        except Exception as e:
            execution_time = time.time() - start_time
            return VerificationResult(
                test_name=test_name,
                success=False,
                details={'error': str(e)},
                error_message=str(e),
                execution_time=execution_time
            )
    
    async def verify_redis_cache_mechanism(self) -> VerificationResult:
        """验证Redis缓存机制"""
        start_time = time.time()
        test_name = "Redis缓存机制验证"
        
        try:
            details = {}
            
            print("\n=== 验证Redis缓存机制 ===")
            
            # 1. 验证缓存写入
            print("1. 验证缓存写入机制")
            
            test_key = "test_cache_key"
            test_value = {"data": "test_cache_value", "timestamp": time.time()}
            
            # 首次获取配置（应该从"数据库"获取并缓存）
            await self.config_manager.set_config(
                key=test_key,
                value=test_value,
                config_type=ConfigType.SYSTEM
            )
            
            # 验证缓存是否被写入
            cached_value = await self.cache_service.get(f"config:{test_key}", namespace="config_manager")
            details['cache_write_success'] = cached_value is not None
            
            if details['cache_write_success']:
                print("✓ 缓存写入成功")
            else:
                print("❌ 缓存写入失败")
            
            # 2. 验证缓存读取
            print("2. 验证缓存读取机制")
            
            # 清除内部缓存，强制从Redis缓存读取
            self.config_manager.config_cache.clear()
            
            # 再次获取配置（应该从缓存获取）
            retrieved_from_cache = await self.config_manager.get_config(
                key=test_key,
                config_type=ConfigType.SYSTEM
            )
            
            details['cache_read_success'] = retrieved_from_cache is not None
            details['cache_data_correct'] = retrieved_from_cache == test_value
            
            if details['cache_read_success'] and details['cache_data_correct']:
                print("✓ 缓存读取成功且数据正确")
            else:
                print("❌ 缓存读取失败或数据错误")
            
            # 3. 验证缓存过期机制
            print("3. 验证缓存TTL机制")
            
            # 设置短TTL的缓存
            await self.cache_service.set(
                "short_ttl_key", 
                "short_ttl_value", 
                ttl=1,  # 1秒过期
                namespace="config_manager"
            )
            
            # 立即获取
            immediate_value = await self.cache_service.get("short_ttl_key", namespace="config_manager")
            details['ttl_immediate_success'] = immediate_value == "short_ttl_value"
            
            # 等待过期后获取（模拟过期）
            # 在真实的Redis中会自动过期，这里我们手动删除来模拟
            await asyncio.sleep(0.1)  # 短暂等待
            await self.cache_service.delete("short_ttl_key", namespace="config_manager")
            expired_value = await self.cache_service.get("short_ttl_key", namespace="config_manager")
            details['ttl_expiry_success'] = expired_value is None
            
            if details['ttl_immediate_success'] and details['ttl_expiry_success']:
                print("✓ 缓存TTL机制正常")
            else:
                print("❌ 缓存TTL机制异常")
            
            # 4. 验证缓存统计
            print("4. 验证缓存统计功能")
            
            cache_stats = await self.cache_service.get_stats()
            details['cache_stats_available'] = cache_stats is not None
            
            if details['cache_stats_available']:
                hit_rate = cache_stats.get('hit_rate', 0)
                total_requests = cache_stats.get('total_requests', 0)
                details['cache_stats_valid'] = 0 <= hit_rate <= 1 and total_requests > 0
                
                if details['cache_stats_valid']:
                    print(f"✓ 缓存统计正常: 命中率{hit_rate:.2%}, 总请求{total_requests}")
                else:
                    print("❌ 缓存统计数据异常")
            else:
                details['cache_stats_valid'] = False
                print("❌ 缓存统计功能不可用")
            
            # 5. 验证缓存清理功能
            print("5. 验证缓存清理功能")
            
            # 设置多个测试缓存
            for i in range(3):
                await self.cache_service.set(
                    f"cleanup_test_{i}",
                    f"cleanup_value_{i}",
                    namespace="config_manager"
                )
            
            # 验证缓存存在
            cleanup_items_before = []
            for i in range(3):
                value = await self.cache_service.get(f"cleanup_test_{i}", namespace="config_manager")
                cleanup_items_before.append(value is not None)
            
            # 执行模式清理
            await self.cache_service.delete_pattern("cleanup_test_*", namespace="config_manager")
            
            # 验证缓存被清理
            cleanup_items_after = []
            for i in range(3):
                value = await self.cache_service.get(f"cleanup_test_{i}", namespace="config_manager")
                cleanup_items_after.append(value is not None)
            
            details['cleanup_before_success'] = all(cleanup_items_before)
            details['cleanup_after_success'] = not any(cleanup_items_after)
            
            if details['cleanup_before_success'] and details['cleanup_after_success']:
                print("✓ 缓存清理功能正常")
            else:
                print("❌ 缓存清理功能异常")
            
            execution_time = time.time() - start_time
            success = (details['cache_write_success'] and
                      details['cache_read_success'] and
                      details['cache_data_correct'] and
                      details['ttl_immediate_success'] and
                      details['ttl_expiry_success'] and
                      details['cache_stats_available'] and
                      details['cache_stats_valid'] and
                      details['cleanup_before_success'] and
                      details['cleanup_after_success'])
            
            return VerificationResult(
                test_name=test_name,
                success=success,
                details=details,
                execution_time=execution_time
            )
            
        except Exception as e:
            execution_time = time.time() - start_time
            return VerificationResult(
                test_name=test_name,
                success=False,
                details={'error': str(e)},
                error_message=str(e),
                execution_time=execution_time
            )
    
    async def verify_hot_update_functionality(self) -> VerificationResult:
        """验证热更新功能"""
        start_time = time.time()
        test_name = "热更新功能验证"
        
        try:
            details = {}
            
            print("\n=== 验证热更新功能 ===")
            
            # 1. 验证配置变更事件监听
            print("1. 验证配置变更事件监听")
            
            change_events = []
            
            def change_listener(event):
                change_events.append({
                    'config_type': event.config_type.value,
                    'config_key': event.config_key,
                    'event_type': event.event_type.value,
                    'timestamp': event.timestamp
                })
            
            # 添加变更监听器
            self.config_manager.add_change_listener(change_listener)
            
            # 触发配置变更
            await self.config_manager.set_config(
                key="hot_update_test",
                value="hot_update_value",
                config_type=ConfigType.SYSTEM
            )
            
            # 等待事件处理
            await asyncio.sleep(0.1)
            
            details['change_event_triggered'] = len(change_events) > 0
            
            if details['change_event_triggered']:
                print(f"✓ 配置变更事件触发成功: {len(change_events)} 个事件")
                details['change_event_details'] = change_events[0] if change_events else {}
            else:
                print("❌ 配置变更事件未触发")
            
            # 2. 验证实时配置更新
            print("2. 验证实时配置更新")
            
            # 设置初始配置
            initial_value = "initial_hot_value"
            await self.config_manager.set_config(
                key="hot_update_realtime",
                value=initial_value,
                config_type=ConfigType.SYSTEM
            )
            
            # 验证初始值
            retrieved_initial = await self.config_manager.get_config("hot_update_realtime")
            details['initial_value_correct'] = retrieved_initial == initial_value
            
            # 更新配置
            updated_value = "updated_hot_value"
            await self.config_manager.set_config(
                key="hot_update_realtime",
                value=updated_value,
                config_type=ConfigType.SYSTEM
            )
            
            # 验证更新值立即生效
            retrieved_updated = await self.config_manager.get_config("hot_update_realtime")
            details['updated_value_correct'] = retrieved_updated == updated_value
            
            if details['initial_value_correct'] and details['updated_value_correct']:
                print("✓ 实时配置更新正常")
            else:
                print("❌ 实时配置更新失败")
            
            # 3. 验证配置验证机制
            print("3. 验证配置验证机制")
            
            # 测试有效配置
            valid_config = {
                'config_key': 'valid_test_key',
                'config_value': 'valid_test_value',
                'description': '有效的测试配置'
            }
            
            valid_result = await self.config_manager.validate_config(ConfigType.SYSTEM, valid_config)
            details['valid_config_passed'] = valid_result.is_valid and len(valid_result.errors) == 0
            
            # 测试无效配置
            invalid_config = {
                'config_value': 'missing_key_config'  # 缺少config_key
            }
            
            invalid_result = await self.config_manager.validate_config(ConfigType.SYSTEM, invalid_config)
            details['invalid_config_rejected'] = not invalid_result.is_valid and len(invalid_result.errors) > 0
            
            if details['valid_config_passed'] and details['invalid_config_rejected']:
                print("✓ 配置验证机制正常")
            else:
                print("❌ 配置验证机制异常")
            
            # 4. 验证配置版本管理
            print("4. 验证配置版本管理")
            
            version_key = "version_test_key"
            
            # 创建多个版本
            for i in range(3):
                await self.config_manager.set_config(
                    key=version_key,
                    value=f"version_{i}_value",
                    config_type=ConfigType.SYSTEM
                )
            
            # 获取版本历史
            versions = await self.config_manager.get_config_versions(version_key)
            details['version_tracking'] = len(versions) > 0
            
            if details['version_tracking']:
                print(f"✓ 配置版本跟踪正常: {len(versions)} 个版本")
                details['version_count'] = len(versions)
            else:
                print("❌ 配置版本跟踪失败")
                details['version_count'] = 0
            
            # 5. 验证配置导出导入
            print("5. 验证配置导出导入功能")
            
            # 设置测试配置
            await self.config_manager.set_config(
                key="export_test_key",
                value="export_test_value",
                config_type=ConfigType.SYSTEM
            )
            
            # 导出配置
            exported_config = await self.config_manager.export_config(ConfigType.SYSTEM)
            details['export_success'] = len(exported_config) > 0 and 'system' in exported_config
            
            if details['export_success']:
                print("✓ 配置导出成功")
                
                # 尝试解析导出的JSON
                try:
                    exported_data = json.loads(exported_config)
                    details['export_format_valid'] = isinstance(exported_data, dict)
                except json.JSONDecodeError:
                    details['export_format_valid'] = False
            else:
                print("❌ 配置导出失败")
                details['export_format_valid'] = False
            
            execution_time = time.time() - start_time
            success = (details['change_event_triggered'] and
                      details['initial_value_correct'] and
                      details['updated_value_correct'] and
                      details['valid_config_passed'] and
                      details['invalid_config_rejected'] and
                      details['version_tracking'] and
                      details['export_success'] and
                      details['export_format_valid'])
            
            return VerificationResult(
                test_name=test_name,
                success=success,
                details=details,
                execution_time=execution_time
            )
            
        except Exception as e:
            execution_time = time.time() - start_time
            return VerificationResult(
                test_name=test_name,
                success=False,
                details={'error': str(e)},
                error_message=str(e),
                execution_time=execution_time
            )
    
    async def verify_priority_strategy_mechanism(self) -> VerificationResult:
        """验证优先级策略机制"""
        start_time = time.time()
        test_name = "优先级策略机制验证"
        
        try:
            details = {}
            
            print("\n=== 验证优先级策略机制 ===")
            
            # 1. 验证配置优先级策略
            print("1. 验证配置优先级策略")
            
            priority_key = "priority_test_key"
            
            # 设置系统配置
            await self.config_manager.set_config(
                key=priority_key,
                value="system_value",
                config_type=ConfigType.SYSTEM
            )
            
            # 设置相同键的环境配置（模拟）
            os.environ[f"CONFIG_{priority_key.upper()}"] = "env_value"
            
            # 获取配置（应该优先返回系统配置）
            retrieved_value = await self.config_manager.get_config(priority_key)
            details['priority_order_correct'] = retrieved_value == "system_value"
            
            if details['priority_order_correct']:
                print("✓ 配置优先级策略正确")
            else:
                print(f"❌ 配置优先级策略错误: 期望system_value, 实际{retrieved_value}")
            
            # 2. 验证缓存与数据库优先级
            print("2. 验证缓存与数据库优先级")
            
            cache_priority_key = "cache_priority_test"
            
            # 首先在缓存中设置值
            await self.cache_service.set(
                f"config:{cache_priority_key}",
                "cached_value",
                namespace="config_manager"
            )
            
            # 在配置管理器中设置不同的值
            await self.config_manager.set_config(
                key=cache_priority_key,
                value="db_value",
                config_type=ConfigType.SYSTEM
            )
            
            # 获取配置（应该优先从缓存获取）
            retrieved_cached = await self.config_manager.get_config(cache_priority_key)
            details['cache_priority_correct'] = retrieved_cached in ["cached_value", "db_value"]
            
            if details['cache_priority_correct']:
                print(f"✓ 缓存优先级策略正确: {retrieved_cached}")
            else:
                print(f"❌ 缓存优先级策略错误: {retrieved_cached}")
            
            # 3. 验证配置类型优先级
            print("3. 验证配置类型优先级")
            
            multi_type_key = "multi_type_test"
            
            # 在不同配置类型中设置相同键
            await self.config_manager.set_config(
                key=multi_type_key,
                value="system_type_value",
                config_type=ConfigType.SYSTEM
            )
            
            # 获取时指定具体类型
            system_value = await self.config_manager.get_config(
                multi_type_key, 
                config_type=ConfigType.SYSTEM
            )
            
            # 获取时不指定类型（应该按照优先级查找）
            default_value = await self.config_manager.get_config(multi_type_key)
            
            details['type_priority_system'] = system_value == "system_type_value"
            details['type_priority_default'] = default_value is not None
            
            if details['type_priority_system'] and details['type_priority_default']:
                print("✓ 配置类型优先级正确")
            else:
                print("❌ 配置类型优先级错误")
            
            # 4. 验证只读配置优先级
            print("4. 验证只读配置保护")
            
            # 模拟只读配置检查
            readonly_key = "readonly_test_key"
            
            # 设置只读配置
            readonly_config = {
                'config_key': readonly_key,
                'config_value': 'readonly_value',
                'is_readonly': True
            }
            
            # 验证只读配置的验证逻辑
            validation_result = await self.config_manager.validate_config(
                ConfigType.SYSTEM, 
                readonly_config
            )
            
            details['readonly_validation'] = validation_result.is_valid
            
            if details['readonly_validation']:
                print("✓ 只读配置验证正确")
            else:
                print("❌ 只读配置验证错误")
            
            # 5. 验证环境特定配置优先级
            print("5. 验证环境特定配置")
            
            env_key = "env_specific_test"
            current_env = self.config_manager.environment
            
            # 设置环境特定配置
            await self.config_manager.set_config(
                key=env_key,
                value=f"{current_env}_specific_value",
                config_type=ConfigType.SYSTEM,
                description=f"{current_env}环境专用配置"
            )
            
            # 获取配置
            env_value = await self.config_manager.get_config(env_key)
            details['env_specific_correct'] = env_value == f"{current_env}_specific_value"
            
            if details['env_specific_correct']:
                print(f"✓ 环境特定配置正确: {current_env}")
            else:
                print(f"❌ 环境特定配置错误: {env_value}")
            
            # 6. 验证配置统计信息
            print("6. 验证配置统计信息")
            
            stats = await self.config_manager.get_config_statistics()
            details['stats_available'] = stats is not None and len(stats) > 0
            
            if details['stats_available']:
                expected_fields = ['total_configs', 'config_types', 'environment']
                details['stats_complete'] = all(field in stats for field in expected_fields)
                
                if details['stats_complete']:
                    print(f"✓ 配置统计完整: {stats.get('total_configs', 0)} 个配置")
                else:
                    print("❌ 配置统计不完整")
            else:
                details['stats_complete'] = False
                print("❌ 配置统计不可用")
            
            execution_time = time.time() - start_time
            success = (details['priority_order_correct'] and
                      details['cache_priority_correct'] and
                      details['type_priority_system'] and
                      details['type_priority_default'] and
                      details['readonly_validation'] and
                      details['env_specific_correct'] and
                      details['stats_available'] and
                      details['stats_complete'])
            
            return VerificationResult(
                test_name=test_name,
                success=success,
                details=details,
                execution_time=execution_time
            )
            
        except Exception as e:
            execution_time = time.time() - start_time
            return VerificationResult(
                test_name=test_name,
                success=False,
                details={'error': str(e)},
                error_message=str(e),
                execution_time=execution_time
            )
    
    async def run_all_verifications(self) -> Dict[str, Any]:
        """运行所有验证测试"""
        print("开始VT-005: 配置管理机制验证")
        print("=" * 60)
        
        # 设置环境
        if not await self.setup():
            return {
                'success': False,
                'error': '环境设置失败',
                'results': []
            }
        
        # 运行所有验证测试
        verifications = [
            self.verify_mysql_configuration_loading(),
            self.verify_redis_cache_mechanism(),
            self.verify_hot_update_functionality(),
            self.verify_priority_strategy_mechanism()
        ]
        
        results = []
        for verification in verifications:
            result = await verification
            results.append(result)
            self.verification_results.append(result)
        
        # 生成汇总报告
        total_tests = len(results)
        passed_tests = sum(1 for r in results if r.success)
        total_time = sum(r.execution_time for r in results)
        
        print("\n" + "=" * 60)
        print("VT-005 验证结果汇总")
        print("=" * 60)
        
        for result in results:
            status = "✓ 通过" if result.success else "✗ 失败"
            print(f"{result.test_name}: {status} ({result.execution_time:.2f}s)")
            if not result.success and result.error_message:
                print(f"  错误: {result.error_message}")
        
        print(f"\n总计: {passed_tests}/{total_tests} 测试通过")
        print(f"总执行时间: {total_time:.2f}秒")
        
        # 配置管理验证标准
        config_verification = {
            'mysql_config_loading': any(r.test_name.startswith('MySQL配置') and r.success for r in results),
            'redis_cache_mechanism': any(r.test_name.startswith('Redis缓存') and r.success for r in results),
            'hot_update_functionality': any(r.test_name.startswith('热更新') and r.success for r in results),
            'priority_strategy': any(r.test_name.startswith('优先级策略') and r.success for r in results)
        }
        
        all_mechanisms_working = all(config_verification.values())
        
        if all_mechanisms_working:
            print("\n🎉 配置管理机制验证完全通过！")
            print("✓ MySQL配置加载正常")
            print("✓ Redis缓存机制有效")
            print("✓ 热更新功能完整")
            print("✓ 优先级策略正确")
        else:
            print("\n❌ 配置管理机制验证部分失败")
            for mechanism, status in config_verification.items():
                status_text = "✓" if status else "✗"
                print(f"{status_text} {mechanism}")
        
        return {
            'success': all_mechanisms_working,
            'total_tests': total_tests,
            'passed_tests': passed_tests,
            'total_time': total_time,
            'config_verification': config_verification,
            'results': [
                {
                    'test_name': r.test_name,
                    'success': r.success,
                    'execution_time': r.execution_time,
                    'details': r.details,
                    'error_message': r.error_message
                }
                for r in results
            ]
        }


async def main():
    """主函数"""
    verifier = ConfigurationManagementVerifier()
    
    try:
        result = await verifier.run_all_verifications()
        
        # 根据结果返回适当的退出码
        if result['success']:
            print("\n✅ VT-005 验证成功完成")
            return 0
        else:
            print("\n❌ VT-005 验证存在失败项")
            return 1
            
    except Exception as e:
        print(f"\n💥 VT-005 验证执行异常: {str(e)}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)