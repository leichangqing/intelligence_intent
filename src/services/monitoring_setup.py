"""
监控系统设置 (V2.2重构)
初始化和配置健康检查、监控服务和稳定性验证
"""
from typing import Optional, Dict, Any
import asyncio
import json
from datetime import datetime

from src.services.cache_service import CacheService
from src.services.health_check_service import get_health_check_service, SystemHealthCheck
from src.services.monitoring_service import get_monitoring_service, MonitoringService, Alert, AlertLevel
from src.services.system_stability_validator import get_stability_validator, SystemStabilityValidator
from src.services.service_factory import initialize_service_factory, get_service_factory
from src.core.nlu_engine import NLUEngine
from src.utils.logger import get_logger

logger = get_logger(__name__)


class MonitoringSystem:
    """监控系统管理器"""
    
    def __init__(self, cache_service: CacheService, nlu_engine: NLUEngine):
        self.cache_service = cache_service
        self.nlu_engine = nlu_engine
        
        # 初始化服务工厂
        initialize_service_factory(cache_service, nlu_engine)
        
        # 初始化监控组件
        self.health_check_service: Optional[SystemHealthCheck] = None
        self.monitoring_service: Optional[MonitoringService] = None
        self.stability_validator: Optional[SystemStabilityValidator] = None
        
        self.is_initialized = False
        self.is_running = False
    
    async def initialize(self, config: Optional[Dict[str, Any]] = None) -> bool:
        """
        初始化监控系统
        
        Args:
            config: 监控配置，可包含：
                - health_check_interval: 健康检查间隔（秒）
                - metrics_collection_interval: 指标收集间隔（秒）
                - alert_rules: 告警规则配置
                
        Returns:
            bool: 初始化是否成功
        """
        try:
            logger.info("初始化监控系统...")
            
            # 设置默认配置
            config = config or {}
            health_check_interval = config.get('health_check_interval', 300)
            metrics_collection_interval = config.get('metrics_collection_interval', 60)
            
            # 初始化健康检查服务
            self.health_check_service = get_health_check_service(self.cache_service)
            logger.info("健康检查服务初始化完成")
            
            # 初始化监控服务
            self.monitoring_service = get_monitoring_service(self.health_check_service)
            self.monitoring_service.health_check_interval = health_check_interval
            self.monitoring_service.metrics_collection_interval = metrics_collection_interval
            
            # 应用自定义告警规则
            if 'alert_rules' in config:
                await self.monitoring_service.update_alert_rules(config['alert_rules'])
            
            logger.info("监控服务初始化完成")
            
            # 初始化稳定性验证器
            self.stability_validator = get_stability_validator(
                self.cache_service, 
                self.health_check_service, 
                self.monitoring_service
            )
            logger.info("稳定性验证器初始化完成")
            
            # 添加自定义告警处理器
            self.monitoring_service.add_alert_handler(self._log_alert_handler)
            self.monitoring_service.add_alert_handler(self._system_alert_handler)
            
            self.is_initialized = True
            logger.info("监控系统初始化成功")
            
            return True
            
        except Exception as e:
            logger.error(f"监控系统初始化失败: {str(e)}")
            return False
    
    async def start(self) -> bool:
        """
        启动监控系统
        
        Returns:
            bool: 启动是否成功
        """
        try:
            if not self.is_initialized:
                logger.error("监控系统未初始化，无法启动")
                return False
            
            logger.info("启动监控系统...")
            
            # 启动监控服务
            await self.monitoring_service.start_monitoring()
            
            self.is_running = True
            logger.info("监控系统启动成功")
            
            # 执行初始健康检查
            await self.run_initial_health_check()
            
            return True
            
        except Exception as e:
            logger.error(f"监控系统启动失败: {str(e)}")
            return False
    
    async def stop(self) -> bool:
        """
        停止监控系统
        
        Returns:
            bool: 停止是否成功
        """
        try:
            if not self.is_running:
                return True
            
            logger.info("停止监控系统...")
            
            # 停止监控服务
            if self.monitoring_service:
                await self.monitoring_service.stop_monitoring()
            
            self.is_running = False
            logger.info("监控系统已停止")
            
            return True
            
        except Exception as e:
            logger.error(f"监控系统停止失败: {str(e)}")
            return False
    
    async def run_initial_health_check(self):
        """运行初始健康检查"""
        try:
            logger.info("执行初始健康检查...")
            
            health_report = await self.health_check_service.check_overall_health()
            overall_status = health_report.get('overall_status')
            
            if overall_status == 'healthy':
                logger.info("系统健康状态良好")
            elif overall_status == 'warning':
                logger.warning("系统存在警告状态的组件")
            else:
                logger.error("系统存在严重健康问题")
            
            # 记录健康检查结果
            logger.info(f"健康检查摘要: {json.dumps(health_report['summary'], ensure_ascii=False)}")
            
        except Exception as e:
            logger.error(f"初始健康检查失败: {str(e)}")
    
    async def run_stability_validation(self, save_report: bool = True) -> Dict[str, Any]:
        """
        运行系统稳定性验证
        
        Args:
            save_report: 是否保存验证报告
            
        Returns:
            Dict[str, Any]: 验证报告
        """
        try:
            if not self.stability_validator:
                raise Exception("稳定性验证器未初始化")
            
            logger.info("开始系统稳定性验证...")
            
            report = await self.stability_validator.run_full_stability_validation()
            
            # 保存报告
            if save_report:
                await self._save_stability_report(report)
            
            return report
            
        except Exception as e:
            logger.error(f"系统稳定性验证失败: {str(e)}")
            return {
                'overall_status': 'error',
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            }
    
    async def get_monitoring_dashboard(self) -> Dict[str, Any]:
        """
        获取监控面板数据
        
        Returns:
            Dict[str, Any]: 监控面板数据
        """
        try:
            dashboard = {
                'timestamp': datetime.now().isoformat(),
                'system_status': 'unknown',
                'monitoring_enabled': self.is_running
            }
            
            if self.health_check_service:
                # 获取最新健康状态
                health_report = await self.health_check_service.check_overall_health()
                dashboard['health_status'] = health_report
                dashboard['system_status'] = health_report.get('overall_status', 'unknown')
                
                # 获取系统指标
                metrics = await self.health_check_service.get_system_metrics()
                dashboard['system_metrics'] = metrics
            
            if self.monitoring_service:
                # 获取监控服务状态
                monitoring_status = self.monitoring_service.get_monitoring_status()
                dashboard['monitoring_status'] = monitoring_status
                
                # 获取最近告警
                recent_alerts = self.monitoring_service.get_recent_alerts(hours=24)
                dashboard['recent_alerts'] = recent_alerts
                
                # 获取关键指标
                key_metrics = {}
                for metric_name in ['system_health_status', 'conversations_daily', 'config_changes_daily']:
                    metric_data = self.monitoring_service.get_metrics(metric_name, hours=24)
                    if metric_data:
                        key_metrics[metric_name] = metric_data[-10:]  # 最近10个数据点
                
                dashboard['key_metrics'] = key_metrics
            
            return dashboard
            
        except Exception as e:
            logger.error(f"获取监控面板数据失败: {str(e)}")
            return {
                'timestamp': datetime.now().isoformat(),
                'error': str(e),
                'system_status': 'error',
                'monitoring_enabled': False
            }
    
    async def _save_stability_report(self, report: Dict[str, Any]):
        """保存稳定性验证报告"""
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"/tmp/stability_report_{timestamp}.json"
            
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(report, f, ensure_ascii=False, indent=2)
            
            logger.info(f"稳定性验证报告已保存: {filename}")
            
        except Exception as e:
            logger.warning(f"保存稳定性验证报告失败: {str(e)}")
    
    def _log_alert_handler(self, alert: Alert):
        """日志告警处理器"""
        logger_method = {
            AlertLevel.INFO: logger.info,
            AlertLevel.WARNING: logger.warning,
            AlertLevel.CRITICAL: logger.error
        }.get(alert.level, logger.info)
        
        logger_method(
            f"MONITORING ALERT [{alert.level.value.upper()}] "
            f"{alert.title}: {alert.message} (Source: {alert.source})"
        )
    
    def _system_alert_handler(self, alert: Alert):
        """系统告警处理器 - 可以扩展为发送邮件、短信等"""
        # 这里可以实现发送告警通知的逻辑
        # 例如：发送邮件、调用webhook、写入外部系统等
        
        if alert.level == AlertLevel.CRITICAL:
            # 对于严重告警，可以执行特殊处理
            logger.critical(f"CRITICAL SYSTEM ALERT: {alert.title}")
            # 可以在这里实现紧急通知逻辑
    
    def get_status(self) -> Dict[str, Any]:
        """获取监控系统状态"""
        return {
            'initialized': self.is_initialized,
            'running': self.is_running,
            'components': {
                'health_check_service': self.health_check_service is not None,
                'monitoring_service': self.monitoring_service is not None,
                'stability_validator': self.stability_validator is not None
            }
        }


# 全局监控系统实例
_monitoring_system: Optional[MonitoringSystem] = None


async def initialize_monitoring_system(cache_service: CacheService, 
                                     nlu_engine: NLUEngine,
                                     config: Optional[Dict[str, Any]] = None) -> MonitoringSystem:
    """
    初始化全局监控系统
    
    Args:
        cache_service: 缓存服务实例
        nlu_engine: NLU引擎实例
        config: 监控配置
        
    Returns:
        MonitoringSystem: 监控系统实例
    """
    global _monitoring_system
    
    if _monitoring_system is None:
        _monitoring_system = MonitoringSystem(cache_service, nlu_engine)
    
    success = await _monitoring_system.initialize(config)
    if not success:
        raise Exception("监控系统初始化失败")
    
    return _monitoring_system


async def start_monitoring_system() -> bool:
    """
    启动全局监控系统
    
    Returns:
        bool: 启动是否成功
    """
    global _monitoring_system
    
    if _monitoring_system is None:
        logger.error("监控系统未初始化")
        return False
    
    return await _monitoring_system.start()


async def stop_monitoring_system() -> bool:
    """
    停止全局监控系统
    
    Returns:
        bool: 停止是否成功
    """
    global _monitoring_system
    
    if _monitoring_system is None:
        return True
    
    return await _monitoring_system.stop()


def get_monitoring_system() -> Optional[MonitoringSystem]:
    """获取全局监控系统实例"""
    return _monitoring_system


# 便捷函数
async def quick_health_check() -> Dict[str, Any]:
    """快速健康检查"""
    global _monitoring_system
    
    if _monitoring_system and _monitoring_system.health_check_service:
        return await _monitoring_system.health_check_service.check_overall_health()
    
    return {'error': '监控系统未初始化'}


async def quick_stability_validation() -> Dict[str, Any]:
    """快速稳定性验证"""
    global _monitoring_system
    
    if _monitoring_system:
        return await _monitoring_system.run_stability_validation(save_report=False)
    
    return {'error': '监控系统未初始化'}


async def get_monitoring_dashboard() -> Dict[str, Any]:
    """获取监控面板"""
    global _monitoring_system
    
    if _monitoring_system:
        return await _monitoring_system.get_monitoring_dashboard()
    
    return {'error': '监控系统未初始化'}