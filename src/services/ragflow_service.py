"""
RAGFLOW服务集成
"""
from typing import Dict, List, Optional, Any
import json
import aiohttp
import asyncio
import hashlib
from datetime import datetime, timedelta

from src.models.config import RagflowConfig
from src.services.cache_service import CacheService
from src.services.query_processor import (
    IntelligentQueryProcessor, QueryContext, ProcessedQuery
)
from src.core.fallback_manager import (
    FallbackManager, FallbackType, FallbackContext, FallbackResult, get_fallback_manager
)
from src.core.intelligent_fallback_decision import (
    IntelligentFallbackDecisionEngine, DecisionContext, get_decision_engine
)
from src.utils.logger import get_logger

logger = get_logger(__name__)


class RagflowResponse:
    """RAGFLOW响应封装类"""
    
    def __init__(self, success: bool, data: Any = None, error: str = None,
                 response_time: float = 0.0, source_documents: List[Dict] = None):
        self.success = success
        self.data = data
        self.error = error
        self.response_time = response_time
        self.source_documents = source_documents or []
    
    def to_dict(self) -> Dict:
        """转换为字典格式"""
        return {
            'success': self.success,
            'data': self.data,
            'error': self.error,
            'response_time': self.response_time,
            'source_documents': self.source_documents
        }


class RagflowService:
    """RAGFLOW集成服务类"""
    
    def __init__(self, cache_service: CacheService):
        self.cache_service = cache_service
        self.cache_namespace = "ragflow"
        self._config_cache: Dict[str, RagflowConfig] = {}
        self._session: Optional[aiohttp.ClientSession] = None
        
        # TASK-031: 智能查询处理器
        self.query_processor = IntelligentQueryProcessor(cache_service)
        
        # TASK-032: 回退管理器和智能决策引擎
        self.fallback_manager = get_fallback_manager(cache_service)
        self.decision_engine = get_decision_engine(cache_service)
    
    async def initialize(self):
        """初始化服务"""
        try:
            # 创建HTTP会话
            connector = aiohttp.TCPConnector(
                limit=100,
                limit_per_host=30,
                keepalive_timeout=60
            )
            timeout = aiohttp.ClientTimeout(total=60)
            self._session = aiohttp.ClientSession(
                connector=connector,
                timeout=timeout
            )
            
            # 加载配置
            await self._load_configurations()
            
            logger.info("RAGFLOW服务初始化完成")
            
        except Exception as e:
            logger.error(f"RAGFLOW服务初始化失败: {str(e)}")
            raise
    
    async def cleanup(self):
        """清理资源"""
        if self._session:
            await self._session.close()
            self._session = None
    
    async def _load_configurations(self):
        """加载RAGFLOW配置"""
        try:
            # 从数据库加载所有活跃配置
            configs = RagflowConfig.select().where(RagflowConfig.is_active == True)
            
            for config in configs:
                self._config_cache[config.config_name] = config
                
                # 缓存配置
                cache_key = f"config:{config.config_name}"
                config_data = {
                    'api_endpoint': config.api_endpoint,
                    'headers': config.get_headers(),
                    'timeout_seconds': config.timeout_seconds,
                    'rate_limit': config.get_rate_limit(),
                    'fallback_config': config.get_fallback_config()
                }
                await self.cache_service.set(cache_key, config_data, 
                                           ttl=3600, namespace=self.cache_namespace)
            
            logger.info(f"加载了{len(self._config_cache)}个RAGFLOW配置")
            
        except Exception as e:
            logger.error(f"加载RAGFLOW配置失败: {str(e)}")
    
    async def query_knowledge_base_intelligent(self, query: str, session_context: Dict[str, Any],
                                             config_name: str = "default") -> RagflowResponse:
        """智能化知识库查询 (TASK-031)
        
        Args:
            query: 查询文本
            session_context: 会话上下文
            config_name: 配置名称
            
        Returns:
            RagflowResponse: 查询响应
        """
        start_time = datetime.now()
        
        try:
            # 1. 构建查询上下文
            query_context = QueryContext(
                session_id=session_context.get('session_id', ''),
                user_id=session_context.get('user_id', ''),
                conversation_history=session_context.get('conversation_history', []),
                current_intent=session_context.get('current_intent'),
                current_slots=session_context.get('current_slots', {}),
                user_preferences=session_context.get('user_preferences', {}),
                domain_context=session_context.get('domain_context'),
                previous_queries=session_context.get('previous_queries', []),
                query_pattern=session_context.get('query_pattern')
            )
            
            # 2. 智能查询处理
            processed_query = await self.query_processor.process_query(query, query_context)
            
            # 3. 根据处理结果选择配置
            selected_config = processed_query.routing_config or config_name
            
            # 4. 构建增强的查询数据
            enhanced_request_data = {
                'query': processed_query.enhanced_query,
                'original_query': processed_query.original_query,
                'context': {
                    'session_id': query_context.session_id,
                    'user_id': query_context.user_id,
                    'conversation_history': query_context.conversation_history[-5:],  # 最近5条
                    'query_analysis': {
                        'query_type': processed_query.analysis.query_type.value,
                        'query_intent': processed_query.analysis.query_intent.value,
                        'complexity': processed_query.analysis.query_complexity.value,
                        'domain': processed_query.analysis.domain,
                        'entities': [e.text for e in processed_query.analysis.entities],
                        'keywords': processed_query.analysis.keywords,
                        'semantic_keywords': processed_query.analysis.semantic_keywords
                    },
                    'search_strategies': processed_query.search_strategies,
                    'expected_answer_type': processed_query.expected_answer_type,
                    'timestamp': datetime.now().isoformat()
                },
                'filters': processed_query.filters,
                'boost_terms': processed_query.boost_terms,
                'context_terms': processed_query.context_terms
            }
            
            # 5. 执行查询
            response = await self._execute_intelligent_query(
                selected_config, enhanced_request_data, processed_query
            )
            
            # 6. 更新查询历史
            await self._update_query_history(query_context.session_id, query, processed_query)
            
            # 计算响应时间
            response_time = (datetime.now() - start_time).total_seconds()
            response.response_time = response_time
            
            logger.info(f"智能查询完成: {query} -> {response.success}, 耗时: {response_time:.3f}s")
            
            return response
            
        except Exception as e:
            response_time = (datetime.now() - start_time).total_seconds()
            error_message = str(e)
            
            logger.error(f"智能查询失败: {error_message}")
            
            # 使用高级回退系统处理智能查询失败
            fallback_response = await self._handle_advanced_fallback(
                query, config_name, session_context, {}, error_message, response_time
            )
            
            if fallback_response.success:
                return fallback_response
            
            # 最终回退到基本查询
            return await self.query_knowledge_base(query, config_name, session_context)
    
    async def query_knowledge_base(self, query: str, config_name: str = "default",
                                 context: Optional[Dict] = None,
                                 filters: Optional[Dict] = None) -> RagflowResponse:
        """查询知识库
        
        Args:
            query: 查询文本
            config_name: 配置名称
            context: 查询上下文
            filters: 查询过滤条件
            
        Returns:
            RagflowResponse: 查询响应
        """
        start_time = datetime.now()
        
        try:
            # 获取配置
            config = await self._get_config(config_name)
            if not config:
                return RagflowResponse(
                    False, 
                    error=f"RAGFLOW配置不存在: {config_name}"
                )
            
            # 检查速率限制
            if not await self._check_rate_limit(config_name):
                return RagflowResponse(
                    False, 
                    error="请求频率过高，请稍后重试"
                )
            
            # 构建请求数据
            request_data = {
                'query': query,
                'context': context or {},
                'filters': filters or {}
            }
            
            # 发送请求
            response_data = await self._send_request(
                config, 'query', request_data
            )
            
            # 计算响应时间
            response_time = (datetime.now() - start_time).total_seconds()
            
            # 处理响应
            if response_data:
                # 提取源文档信息
                source_documents = self._extract_source_documents(response_data)
                
                return RagflowResponse(
                    True,
                    data=response_data.get('answer', ''),
                    response_time=response_time,
                    source_documents=source_documents
                )
            else:
                return RagflowResponse(
                    False,
                    error="RAGFLOW返回空响应",
                    response_time=response_time
                )
                
        except Exception as e:
            response_time = (datetime.now() - start_time).total_seconds()
            error_message = str(e)
            
            logger.error(f"RAGFLOW查询失败: {error_message}")
            
            # 使用高级回退系统 (TASK-032)
            fallback_response = await self._handle_advanced_fallback(
                query, config_name, context, filters, error_message, response_time
            )
            
            if fallback_response.success:
                return fallback_response
            
            return RagflowResponse(
                False,
                error=error_message,
                response_time=response_time
            )
    
    async def _get_config(self, config_name: str) -> Optional[RagflowConfig]:
        """获取配置"""
        # 优先从缓存获取
        if config_name in self._config_cache:
            return self._config_cache[config_name]
        
        # 从数据库加载
        try:
            config = RagflowConfig.get(
                RagflowConfig.config_name == config_name,
                RagflowConfig.is_active == True
            )
            self._config_cache[config_name] = config
            return config
            
        except RagflowConfig.DoesNotExist:
            logger.warning(f"RAGFLOW配置不存在: {config_name}")
            return None
    
    async def _check_rate_limit(self, config_name: str) -> bool:
        """检查速率限制"""
        try:
            config = self._config_cache.get(config_name)
            if not config:
                return True
            
            rate_limit = config.get_rate_limit()
            if not rate_limit:
                return True
            
            # 从速率限制配置中获取参数
            max_requests = rate_limit.get('max_requests', 100)
            window_seconds = rate_limit.get('window_seconds', 60)
            
            # 使用滑动窗口算法检查速率限制
            cache_key = f"rate_limit:{config_name}"
            
            # 获取当前窗口的请求记录
            now = datetime.now().timestamp()
            window_start = now - window_seconds
            
            requests = await self.cache_service.get(cache_key, namespace=self.cache_namespace) or []
            if isinstance(requests, str):
                requests = json.loads(requests)
            
            # 清理过期的请求记录
            valid_requests = [req_time for req_time in requests if req_time > window_start]
            
            # 检查是否超出限制
            if len(valid_requests) >= max_requests:
                logger.warning(f"RAGFLOW配置 {config_name} 达到速率限制")
                return False
            
            # 添加当前请求
            valid_requests.append(now)
            
            # 更新缓存
            await self.cache_service.set(cache_key, valid_requests, 
                                       ttl=window_seconds, namespace=self.cache_namespace)
            
            return True
            
        except Exception as e:
            logger.error(f"检查速率限制失败: {str(e)}")
            return True  # 发生错误时允许请求
    
    async def _send_request(self, config: RagflowConfig, endpoint: str, 
                          data: Dict) -> Optional[Dict]:
        """发送HTTP请求"""
        if not self._session:
            await self.initialize()
        
        try:
            url = f"{config.api_endpoint.rstrip('/')}/{endpoint}"
            headers = config.get_headers()
            
            # 添加API密钥到请求头
            if config.api_key:
                headers['Authorization'] = f"Bearer {config.api_key}"
            
            # 设置内容类型
            headers['Content-Type'] = 'application/json'
            
            # 发送POST请求
            async with self._session.post(
                url,
                json=data,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=config.timeout_seconds)
            ) as response:
                
                if response.status == 200:
                    response_data = await response.json()
                    logger.debug(f"RAGFLOW请求成功: {url}")
                    return response_data
                else:
                    error_text = await response.text()
                    logger.error(f"RAGFLOW请求失败: {response.status}, {error_text}")
                    return None
                    
        except asyncio.TimeoutError:
            logger.error(f"RAGFLOW请求超时: {config.config_name}")
            return None
        except Exception as e:
            logger.error(f"RAGFLOW请求异常: {str(e)}")
            return None
    
    def _extract_source_documents(self, response_data: Dict) -> List[Dict]:
        """提取源文档信息"""
        source_documents = []
        
        try:
            # 根据RAGFLOW响应格式提取源文档
            documents = response_data.get('source_documents', [])
            
            for doc in documents:
                doc_info = {
                    'title': doc.get('title', ''),
                    'content': doc.get('content', ''),
                    'score': doc.get('score', 0.0),
                    'metadata': doc.get('metadata', {}),
                    'source': doc.get('source', ''),
                    'page_number': doc.get('page_number'),
                    'chunk_index': doc.get('chunk_index')
                }
                source_documents.append(doc_info)
            
        except Exception as e:
            logger.warning(f"提取源文档信息失败: {str(e)}")
        
        return source_documents
    
    async def _handle_advanced_fallback(self, query: str, config_name: str,
                                       context: Optional[Dict], 
                                       filters: Optional[Dict],
                                       error_message: str,
                                       initial_response_time: float) -> RagflowResponse:
        """处理高级回退逻辑 (TASK-032)"""
        try:
            # 构建回退上下文
            fallback_context = FallbackContext(
                error_type=FallbackType.RAGFLOW_QUERY,
                error_message=error_message,
                original_request={
                    'query': query,
                    'config_name': config_name,
                    'context': context,
                    'filters': filters
                },
                session_context=context or {},
                user_id=context.get('user_id', 'unknown') if context else 'unknown',
                session_id=context.get('session_id', 'unknown') if context else 'unknown',
                metadata={
                    'service': 'ragflow',
                    'initial_response_time': initial_response_time
                }
            )
            
            # 使用智能决策引擎选择最佳回退策略
            decision_context = DecisionContext(
                fallback_context=fallback_context,
                available_strategies=self.fallback_manager.fallback_rules[FallbackType.RAGFLOW_QUERY].strategies,
                historical_performance={},
                system_metrics={},
                user_profile={},
                business_rules={}
            )
            
            decision_result = await self.decision_engine.make_decision(decision_context)
            logger.info(f"智能决策选择策略: {decision_result.recommended_strategy.value}, 置信度: {decision_result.confidence:.3f}")
            
            # 执行回退
            fallback_result = await self.fallback_manager.handle_fallback(fallback_context)
            
            # 更新策略性能
            if decision_result.recommended_strategy:
                await self.decision_engine.update_strategy_performance(
                    decision_result.recommended_strategy, 
                    fallback_result
                )
            
            # 转换为RagflowResponse
            if fallback_result.success:
                return RagflowResponse(
                    True,
                    data=fallback_result.data,
                    response_time=fallback_result.response_time + initial_response_time,
                    source_documents=[]
                )
            else:
                return RagflowResponse(
                    False,
                    error=fallback_result.error,
                    response_time=fallback_result.response_time + initial_response_time
                )
                
        except Exception as e:
            logger.error(f"高级回退处理失败: {str(e)}")
            # 使用传统回退作为最后的保障
            return await self._try_legacy_fallback_query(query, config_name, context, filters)
    
    async def _try_legacy_fallback_query(self, query: str, config_name: str,
                                       context: Optional[Dict], 
                                       filters: Optional[Dict]) -> RagflowResponse:
        """传统回退查询（保留原有逻辑作为最后保障）"""
        try:
            config = self._config_cache.get(config_name)
            if not config:
                return RagflowResponse(False, error="无回退配置")
            
            fallback_config = config.get_fallback_config()
            if not fallback_config or not fallback_config.get('enabled', False):
                return RagflowResponse(False, error="回退查询未启用")
            
            # 使用回退配置名称
            fallback_config_name = fallback_config.get('config_name')
            if fallback_config_name and fallback_config_name != config_name:
                logger.info(f"使用回退配置进行查询: {fallback_config_name}")
                return await self.query_knowledge_base(
                    query, fallback_config_name, context, filters
                )
            
            # 使用默认回退响应
            default_response = fallback_config.get('default_response', '抱歉，我暂时无法回答这个问题。')
            return RagflowResponse(
                True,
                data=default_response,
                response_time=0.0
            )
            
        except Exception as e:
            logger.error(f"传统回退查询失败: {str(e)}")
            return RagflowResponse(False, error="回退查询失败")
    
    async def upload_document(self, file_path: str, config_name: str = "default",
                            metadata: Optional[Dict] = None) -> RagflowResponse:
        """上传文档到知识库
        
        Args:
            file_path: 文件路径
            config_name: 配置名称
            metadata: 文档元数据
            
        Returns:
            RagflowResponse: 上传响应
        """
        start_time = datetime.now()
        
        try:
            config = await self._get_config(config_name)
            if not config:
                return RagflowResponse(
                    False,
                    error=f"RAGFLOW配置不存在: {config_name}"
                )
            
            # 构建上传数据
            upload_data = {
                'file_path': file_path,
                'metadata': metadata or {}
            }
            
            # 发送上传请求
            response_data = await self._send_request(
                config, 'upload', upload_data
            )
            
            response_time = (datetime.now() - start_time).total_seconds()
            
            if response_data:
                return RagflowResponse(
                    True,
                    data=response_data,
                    response_time=response_time
                )
            else:
                return RagflowResponse(
                    False,
                    error="文档上传失败",
                    response_time=response_time
                )
                
        except Exception as e:
            response_time = (datetime.now() - start_time).total_seconds()
            logger.error(f"文档上传失败: {str(e)}")
            return RagflowResponse(
                False,
                error=str(e),
                response_time=response_time
            )
    
    async def delete_document(self, document_id: str, config_name: str = "default") -> RagflowResponse:
        """删除知识库文档
        
        Args:
            document_id: 文档ID
            config_name: 配置名称
            
        Returns:
            RagflowResponse: 删除响应
        """
        try:
            config = await self._get_config(config_name)
            if not config:
                return RagflowResponse(
                    False,
                    error=f"RAGFLOW配置不存在: {config_name}"
                )
            
            # 构建删除请求数据
            delete_data = {'document_id': document_id}
            
            # 发送删除请求
            response_data = await self._send_request(
                config, 'delete', delete_data
            )
            
            if response_data:
                return RagflowResponse(True, data=response_data)
            else:
                return RagflowResponse(False, error="文档删除失败")
                
        except Exception as e:
            logger.error(f"文档删除失败: {str(e)}")
            return RagflowResponse(False, error=str(e))
    
    async def check_health(self, config_name: str = "default") -> bool:
        """检查RAGFLOW服务健康状态
        
        Args:
            config_name: 配置名称
            
        Returns:
            bool: 健康状态
        """
        try:
            config = await self._get_config(config_name)
            if not config:
                return False
            
            # 如果有健康检查URL，使用专门的健康检查接口
            if config.health_check_url:
                try:
                    if not self._session:
                        await self.initialize()
                    
                    async with self._session.get(
                        config.health_check_url,
                        timeout=aiohttp.ClientTimeout(total=10)
                    ) as response:
                        return response.status == 200
                        
                except Exception:
                    return False
            
            # 否则发送简单的查询请求
            response = await self.query_knowledge_base(
                "health check", config_name
            )
            return response.success or response.error != "RAGFLOW返回空响应"
            
        except Exception as e:
            logger.error(f"RAGFLOW健康检查失败: {str(e)}")
            return False
    
    async def get_statistics(self, config_name: str = "default") -> Dict[str, Any]:
        """获取RAGFLOW使用统计
        
        Args:
            config_name: 配置名称
            
        Returns:
            Dict: 统计信息
        """
        try:
            # 从缓存获取统计信息
            cache_key = f"stats:{config_name}"
            cached_stats = await self.cache_service.get(cache_key, namespace=self.cache_namespace)
            
            if cached_stats:
                return cached_stats
            
            # 计算统计信息
            stats = {
                'config_name': config_name,
                'is_healthy': await self.check_health(config_name),
                'total_requests': 0,  # 实际应该从日志或数据库获取
                'successful_requests': 0,
                'failed_requests': 0,
                'average_response_time': 0.0,
                'last_check_time': datetime.now().isoformat()
            }
            
            # 缓存统计信息
            await self.cache_service.set(cache_key, stats, ttl=300, namespace=self.cache_namespace)
            
            return stats
            
        except Exception as e:
            logger.error(f"获取RAGFLOW统计失败: {str(e)}")
            return {}
    
    async def refresh_configuration(self, config_name: Optional[str] = None):
        """刷新配置
        
        Args:
            config_name: 配置名称，为None时刷新所有配置
        """
        try:
            if config_name:
                # 清除指定配置的缓存
                if config_name in self._config_cache:
                    del self._config_cache[config_name]
                
                cache_key = f"config:{config_name}"
                await self.cache_service.delete(cache_key, namespace=self.cache_namespace)
                
                # 重新加载配置
                await self._get_config(config_name)
            else:
                # 清除所有配置缓存
                self._config_cache.clear()
                await self.cache_service.clear_namespace(self.cache_namespace)
                
                # 重新加载所有配置
                await self._load_configurations()
            
            logger.info(f"RAGFLOW配置刷新完成: {config_name or 'all'}")
            
        except Exception as e:
            logger.error(f"RAGFLOW配置刷新失败: {str(e)}")
    
    def get_available_configs(self) -> List[str]:
        """获取可用的配置名称列表"""
        return list(self._config_cache.keys())
    
    # ========== TASK-031: 智能查询处理支持方法 ==========
    
    async def _execute_intelligent_query(self, config_name: str, enhanced_request_data: Dict[str, Any],
                                       processed_query: ProcessedQuery) -> RagflowResponse:
        """执行智能查询"""
        try:
            # 获取配置
            config = await self._get_config(config_name)
            if not config:
                return RagflowResponse(
                    False,
                    error=f"RAGFLOW配置不存在: {config_name}"
                )
            
            # 检查速率限制
            if not await self._check_rate_limit(config_name):
                return RagflowResponse(
                    False,
                    error="请求频率过高，请稍后重试"
                )
            
            # 根据搜索策略执行不同的查询方式
            search_strategies = processed_query.search_strategies
            
            if 'multi_step' in search_strategies:
                return await self._execute_multi_step_query(config, enhanced_request_data, processed_query)
            elif 'comparative' in search_strategies:
                return await self._execute_comparative_query(config, enhanced_request_data, processed_query)
            elif 'context_aware' in search_strategies:
                return await self._execute_context_aware_query(config, enhanced_request_data, processed_query)
            else:
                return await self._execute_enhanced_basic_query(config, enhanced_request_data, processed_query)
                
        except Exception as e:
            logger.error(f"智能查询执行失败: {str(e)}")
            return RagflowResponse(
                False,
                error=str(e)
            )
    
    async def _execute_multi_step_query(self, config: RagflowConfig, request_data: Dict[str, Any],
                                      processed_query: ProcessedQuery) -> RagflowResponse:
        """执行多步骤查询"""
        try:
            # 将复杂查询分解为多个子查询
            sub_queries = self._decompose_complex_query(processed_query)
            
            all_responses = []
            all_source_documents = []
            
            for sub_query in sub_queries:
                sub_request_data = request_data.copy()
                sub_request_data['query'] = sub_query
                
                # 执行子查询
                response_data = await self._send_request(config, 'query', sub_request_data)
                
                if response_data:
                    all_responses.append(response_data)
                    # 提取源文档
                    sub_documents = self._extract_source_documents(response_data)
                    all_source_documents.extend(sub_documents)
            
            if all_responses:
                # 合并多个响应
                merged_answer = self._merge_multi_step_responses(all_responses, processed_query)
                
                # 去重和排序源文档
                unique_documents = self._deduplicate_and_rank_documents(all_source_documents)
                
                return RagflowResponse(
                    True,
                    data=merged_answer,
                    source_documents=unique_documents
                )
            else:
                return RagflowResponse(
                    False,
                    error="多步骤查询未找到结果"
                )
                
        except Exception as e:
            logger.error(f"多步骤查询失败: {str(e)}")
            return RagflowResponse(False, error=str(e))
    
    async def _execute_comparative_query(self, config: RagflowConfig, request_data: Dict[str, Any],
                                       processed_query: ProcessedQuery) -> RagflowResponse:
        """执行比较查询"""
        try:
            # 提取比较实体
            comparison_entities = self._extract_comparison_entities(processed_query)
            
            if len(comparison_entities) >= 2:
                # 分别查询每个实体
                entity_responses = []
                
                for entity in comparison_entities:
                    entity_request_data = request_data.copy()
                    entity_request_data['query'] = f"{entity} {processed_query.analysis.normalized_query}"
                    
                    response_data = await self._send_request(config, 'query', entity_request_data)
                    if response_data:
                        entity_responses.append({
                            'entity': entity,
                            'response': response_data
                        })
                
                if entity_responses:
                    # 生成比较结果
                    comparison_result = self._generate_comparison_result(entity_responses, processed_query)
                    
                    # 合并源文档
                    all_source_documents = []
                    for entity_response in entity_responses:
                        documents = self._extract_source_documents(entity_response['response'])
                        all_source_documents.extend(documents)
                    
                    return RagflowResponse(
                        True,
                        data=comparison_result,
                        source_documents=all_source_documents
                    )
            
            # 回退到基本查询
            return await self._execute_enhanced_basic_query(config, request_data, processed_query)
            
        except Exception as e:
            logger.error(f"比较查询失败: {str(e)}")
            return RagflowResponse(False, error=str(e))
    
    async def _execute_context_aware_query(self, config: RagflowConfig, request_data: Dict[str, Any],
                                         processed_query: ProcessedQuery) -> RagflowResponse:
        """执行上下文感知查询"""
        try:
            # 构建上下文增强的查询
            context_enhanced_data = request_data.copy()
            
            # 添加上下文权重
            context_weight = self._calculate_context_weight(processed_query)
            context_enhanced_data['context_weight'] = context_weight
            
            # 添加上下文过滤
            context_filters = self._build_context_filters(processed_query)
            context_enhanced_data['context_filters'] = context_filters
            
            # 执行上下文感知查询
            response_data = await self._send_request(config, 'query', context_enhanced_data)
            
            if response_data:
                # 后处理：基于上下文重新排序结果
                processed_response = self._post_process_context_aware_response(
                    response_data, processed_query
                )
                
                # 提取和排序源文档
                source_documents = self._extract_source_documents(processed_response)
                ranked_documents = self._rank_documents_by_context(source_documents, processed_query)
                
                return RagflowResponse(
                    True,
                    data=processed_response.get('answer', ''),
                    source_documents=ranked_documents
                )
            else:
                return RagflowResponse(
                    False,
                    error="上下文感知查询未找到结果"
                )
                
        except Exception as e:
            logger.error(f"上下文感知查询失败: {str(e)}")
            return RagflowResponse(False, error=str(e))
    
    async def _execute_enhanced_basic_query(self, config: RagflowConfig, request_data: Dict[str, Any],
                                          processed_query: ProcessedQuery) -> RagflowResponse:
        """执行增强基本查询"""
        try:
            # 发送增强查询请求
            response_data = await self._send_request(config, 'query', request_data)
            
            if response_data:
                # 后处理：基于查询分析优化响应
                optimized_response = self._optimize_response_by_analysis(response_data, processed_query)
                
                # 提取和增强源文档
                source_documents = self._extract_source_documents(optimized_response)
                enhanced_documents = self._enhance_source_documents(source_documents, processed_query)
                
                return RagflowResponse(
                    True,
                    data=optimized_response.get('answer', ''),
                    source_documents=enhanced_documents
                )
            else:
                return RagflowResponse(
                    False,
                    error="增强查询未找到结果"
                )
                
        except Exception as e:
            logger.error(f"增强基本查询失败: {str(e)}")
            return RagflowResponse(False, error=str(e))
    
    def _decompose_complex_query(self, processed_query: ProcessedQuery) -> List[str]:
        """分解复杂查询"""
        query = processed_query.original_query
        analysis = processed_query.analysis
        
        sub_queries = []
        
        # 基于查询类型分解
        if analysis.query_type.value == 'procedural':
            # 程序性查询：分解为步骤
            if '如何' in query or '怎么' in query:
                sub_queries.append(f"什么是{analysis.keywords[0] if analysis.keywords else '目标'}")
                sub_queries.append(f"{analysis.keywords[0] if analysis.keywords else '目标'}的步骤")
                sub_queries.append(f"{analysis.keywords[0] if analysis.keywords else '目标'}的注意事项")
        
        elif analysis.query_type.value == 'comparative':
            # 比较查询：分解为各个对比项
            entities = [e.text for e in analysis.entities]
            if len(entities) >= 2:
                for entity in entities:
                    sub_queries.append(f"{entity}的特点")
                sub_queries.append(f"{entities[0]}和{entities[1]}的区别")
        
        elif analysis.query_complexity.value in ['complex', 'very_complex']:
            # 复杂查询：分解为关键词子查询
            for keyword in analysis.keywords[:3]:  # 最多3个关键词
                sub_queries.append(f"{keyword}是什么")
        
        # 如果没有分解出子查询，使用原查询
        if not sub_queries:
            sub_queries.append(query)
        
        return sub_queries
    
    def _extract_comparison_entities(self, processed_query: ProcessedQuery) -> List[str]:
        """提取比较实体"""
        entities = []
        
        # 从实体中提取
        for entity in processed_query.analysis.entities:
            if entity.entity_type in ['product', 'service', 'concept']:
                entities.append(entity.text)
        
        # 从关键词中提取
        comparison_keywords = ['和', '与', '或', '还是', '对比']
        query = processed_query.original_query
        
        for keyword in comparison_keywords:
            if keyword in query:
                parts = query.split(keyword)
                if len(parts) >= 2:
                    entities.extend([part.strip() for part in parts if part.strip()])
        
        return entities[:4]  # 限制数量
    
    def _merge_multi_step_responses(self, responses: List[Dict[str, Any]], 
                                  processed_query: ProcessedQuery) -> str:
        """合并多步骤响应"""
        merged_answer = []
        
        for i, response in enumerate(responses):
            answer = response.get('answer', '')
            if answer:
                if processed_query.analysis.query_type.value == 'procedural':
                    merged_answer.append(f"步骤{i+1}: {answer}")
                else:
                    merged_answer.append(answer)
        
        return '\n\n'.join(merged_answer)
    
    def _generate_comparison_result(self, entity_responses: List[Dict[str, Any]], 
                                  processed_query: ProcessedQuery) -> str:
        """生成比较结果"""
        comparison_result = []
        
        comparison_result.append("以下是比较结果：\n")
        
        for entity_response in entity_responses:
            entity = entity_response['entity']
            response = entity_response['response']
            answer = response.get('answer', '')
            
            if answer:
                comparison_result.append(f"关于{entity}：{answer}")
        
        # 添加总结
        if len(entity_responses) >= 2:
            comparison_result.append("\n总结：根据以上信息，您可以根据具体需求选择合适的选项。")
        
        return '\n\n'.join(comparison_result)
    
    def _calculate_context_weight(self, processed_query: ProcessedQuery) -> Dict[str, float]:
        """计算上下文权重"""
        weight = {}
        
        # 基于查询分析的权重
        if processed_query.analysis.domain:
            weight['domain'] = 0.3
        
        # 基于实体的权重
        if processed_query.analysis.entities:
            weight['entities'] = 0.2
        
        # 基于关键词的权重
        if processed_query.analysis.keywords:
            weight['keywords'] = 0.2
        
        # 基于上下文词的权重
        if processed_query.context_terms:
            weight['context'] = 0.3
        
        return weight
    
    def _build_context_filters(self, processed_query: ProcessedQuery) -> Dict[str, Any]:
        """构建上下文过滤器"""
        filters = {}
        
        # 基于领域过滤
        if processed_query.analysis.domain:
            filters['domain'] = processed_query.analysis.domain
        
        # 基于查询类型过滤
        filters['query_type'] = processed_query.analysis.query_type.value
        
        # 基于时间上下文过滤
        if processed_query.analysis.temporal_context:
            filters['temporal'] = processed_query.analysis.temporal_context
        
        # 基于空间上下文过滤
        if processed_query.analysis.spatial_context:
            filters['spatial'] = processed_query.analysis.spatial_context
        
        return filters
    
    def _post_process_context_aware_response(self, response_data: Dict[str, Any], 
                                           processed_query: ProcessedQuery) -> Dict[str, Any]:
        """后处理上下文感知响应"""
        # 基于查询分析调整响应
        answer = response_data.get('answer', '')
        
        # 根据期望的答案类型调整格式
        if processed_query.expected_answer_type == 'step_by_step':
            # 如果期望步骤性答案，尝试格式化为步骤
            if '步骤' not in answer and ('如何' in processed_query.original_query or '怎么' in processed_query.original_query):
                # 尝试将答案格式化为步骤
                sentences = answer.split('。')
                if len(sentences) > 1:
                    formatted_answer = []
                    for i, sentence in enumerate(sentences):
                        if sentence.strip():
                            formatted_answer.append(f"步骤{i+1}: {sentence.strip()}。")
                    answer = '\n'.join(formatted_answer)
        
        elif processed_query.expected_answer_type == 'comparative':
            # 如果期望比较性答案，强调对比
            if '比较' in processed_query.original_query or '区别' in processed_query.original_query:
                if '相比' not in answer and '区别' not in answer:
                    answer = f"从比较角度来看：{answer}"
        
        response_data['answer'] = answer
        return response_data
    
    def _rank_documents_by_context(self, documents: List[Dict], processed_query: ProcessedQuery) -> List[Dict]:
        """基于上下文对文档进行排序"""
        for doc in documents:
            # 计算上下文相关性得分
            context_score = 0.0
            
            # 基于关键词匹配
            content = doc.get('content', '').lower()
            for keyword in processed_query.analysis.keywords:
                if keyword.lower() in content:
                    context_score += 0.1
            
            # 基于实体匹配
            for entity in processed_query.analysis.entities:
                if entity.text.lower() in content:
                    context_score += 0.15
            
            # 基于领域匹配
            if processed_query.analysis.domain:
                domain_keywords = {
                    'banking': ['银行', '账户', '金融'],
                    'travel': ['旅行', '机票', '酒店'],
                    'technical': ['技术', '系统', '软件']
                }
                
                domain_words = domain_keywords.get(processed_query.analysis.domain, [])
                for word in domain_words:
                    if word in content:
                        context_score += 0.1
            
            # 更新文档得分
            original_score = doc.get('score', 0.0)
            doc['score'] = original_score + context_score
        
        # 按得分排序
        return sorted(documents, key=lambda x: x.get('score', 0.0), reverse=True)
    
    def _optimize_response_by_analysis(self, response_data: Dict[str, Any], 
                                     processed_query: ProcessedQuery) -> Dict[str, Any]:
        """基于查询分析优化响应"""
        answer = response_data.get('answer', '')
        
        # 基于查询意图优化
        if processed_query.analysis.query_intent.value == 'instruct':
            # 指导性查询：确保答案包含具体步骤
            if '步骤' not in answer and '方法' not in answer:
                answer = f"具体方法：{answer}"
        
        elif processed_query.analysis.query_intent.value == 'explain':
            # 解释性查询：确保答案包含详细说明
            if len(answer) < 50:  # 答案过短
                answer = f"详细说明：{answer}"
        
        elif processed_query.analysis.query_intent.value == 'recommend':
            # 推荐性查询：强调建议性
            if '建议' not in answer and '推荐' not in answer:
                answer = f"推荐方案：{answer}"
        
        response_data['answer'] = answer
        return response_data
    
    def _enhance_source_documents(self, documents: List[Dict], processed_query: ProcessedQuery) -> List[Dict]:
        """增强源文档"""
        enhanced_documents = []
        
        for doc in documents:
            enhanced_doc = doc.copy()
            
            # 添加相关性标签
            relevance_tags = []
            
            # 基于关键词匹配
            content = doc.get('content', '').lower()
            matched_keywords = []
            for keyword in processed_query.analysis.keywords:
                if keyword.lower() in content:
                    matched_keywords.append(keyword)
            
            if matched_keywords:
                relevance_tags.append(f"匹配关键词: {', '.join(matched_keywords)}")
            
            # 基于实体匹配
            matched_entities = []
            for entity in processed_query.analysis.entities:
                if entity.text.lower() in content:
                    matched_entities.append(entity.text)
            
            if matched_entities:
                relevance_tags.append(f"匹配实体: {', '.join(matched_entities)}")
            
            # 基于查询类型匹配
            if processed_query.analysis.query_type.value == 'procedural':
                if any(word in content for word in ['步骤', '方法', '流程', '操作']):
                    relevance_tags.append("包含操作步骤")
            
            elif processed_query.analysis.query_type.value == 'comparative':
                if any(word in content for word in ['比较', '对比', '区别', '差异']):
                    relevance_tags.append("包含比较信息")
            
            # 添加增强信息
            enhanced_doc['relevance_tags'] = relevance_tags
            enhanced_doc['query_type_match'] = processed_query.analysis.query_type.value
            enhanced_doc['analysis_confidence'] = processed_query.analysis.confidence
            
            enhanced_documents.append(enhanced_doc)
        
        return enhanced_documents
    
    def _deduplicate_and_rank_documents(self, documents: List[Dict]) -> List[Dict]:
        """去重和排序文档"""
        # 简单去重：基于内容哈希
        seen_content = set()
        unique_documents = []
        
        for doc in documents:
            content = doc.get('content', '')
            content_hash = hashlib.md5(content.encode()).hexdigest()
            
            if content_hash not in seen_content:
                seen_content.add(content_hash)
                unique_documents.append(doc)
        
        # 按得分排序
        return sorted(unique_documents, key=lambda x: x.get('score', 0.0), reverse=True)
    
    async def _update_query_history(self, session_id: str, query: str, processed_query: ProcessedQuery):
        """更新查询历史"""
        try:
            cache_key = f"query_history:{session_id}"
            
            # 获取现有历史
            history = await self.cache_service.get(cache_key, namespace=self.cache_namespace) or []
            
            # 添加新查询
            history_entry = {
                'query': query,
                'enhanced_query': processed_query.enhanced_query,
                'query_type': processed_query.analysis.query_type.value,
                'query_intent': processed_query.analysis.query_intent.value,
                'complexity': processed_query.analysis.query_complexity.value,
                'domain': processed_query.analysis.domain,
                'timestamp': datetime.now().isoformat()
            }
            
            history.append(history_entry)
            
            # 保持最近50条记录
            if len(history) > 50:
                history = history[-50:]
            
            # 更新缓存
            await self.cache_service.set(cache_key, history, ttl=7200, namespace=self.cache_namespace)
            
        except Exception as e:
            logger.warning(f"更新查询历史失败: {str(e)}")
    
    async def get_query_analytics(self, session_id: str = None, time_range: int = 24) -> Dict[str, Any]:
        """获取查询分析数据 (TASK-031)"""
        try:
            analytics = {
                'total_queries': 0,
                'query_types': {},
                'query_intents': {},
                'complexity_distribution': {},
                'domain_distribution': {},
                'average_processing_time': 0.0,
                'success_rate': 0.0,
                'popular_keywords': {},
                'query_patterns': []
            }
            
            # 如果指定了session_id，获取会话级分析
            if session_id:
                cache_key = f"query_history:{session_id}"
                history = await self.cache_service.get(cache_key, namespace=self.cache_namespace) or []
                
                # 分析历史数据
                analytics = self._analyze_query_history(history)
            
            return analytics
            
        except Exception as e:
            logger.error(f"获取查询分析失败: {str(e)}")
            return {}
    
    def _analyze_query_history(self, history: List[Dict]) -> Dict[str, Any]:
        """分析查询历史"""
        analytics = {
            'total_queries': len(history),
            'query_types': {},
            'query_intents': {},
            'complexity_distribution': {},
            'domain_distribution': {},
            'popular_keywords': {},
            'query_patterns': []
        }
        
        if not history:
            return analytics
        
        # 统计查询类型
        for entry in history:
            query_type = entry.get('query_type', 'unknown')
            analytics['query_types'][query_type] = analytics['query_types'].get(query_type, 0) + 1
            
            query_intent = entry.get('query_intent', 'unknown')
            analytics['query_intents'][query_intent] = analytics['query_intents'].get(query_intent, 0) + 1
            
            complexity = entry.get('complexity', 'unknown')
            analytics['complexity_distribution'][complexity] = analytics['complexity_distribution'].get(complexity, 0) + 1
            
            domain = entry.get('domain', 'general')
            analytics['domain_distribution'][domain] = analytics['domain_distribution'].get(domain, 0) + 1
        
        # 计算百分比
        total = analytics['total_queries']
        for category in ['query_types', 'query_intents', 'complexity_distribution', 'domain_distribution']:
            for key, count in analytics[category].items():
                analytics[category][key] = {
                    'count': count,
                    'percentage': (count / total) * 100
                }
        
        return analytics