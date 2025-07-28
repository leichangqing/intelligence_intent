"""
NLU自然语言理解引擎
集成xinference + Duckling + 自定义模型
"""
from typing import Dict, List, Optional, Any, Tuple
import json
import asyncio
import aiohttp
from datetime import datetime
from decimal import Decimal

from src.config.settings import settings
from src.models.intent import Intent
from src.models.slot import Slot
from src.utils.logger import get_logger
from src.schemas.intent_recognition import IntentRecognitionResult
from src.core.confidence_manager import ConfidenceManager, ConfidenceSource, ConfidenceScore

logger = get_logger(__name__)


class DecimalEncoder(json.JSONEncoder):
    """自定义JSON编码器，处理Decimal和datetime类型"""
    def default(self, obj):
        if isinstance(obj, Decimal):
            return float(obj)
        elif isinstance(obj, datetime):
            return obj.isoformat()
        return super().default(obj)


def safe_json_dumps(obj, **kwargs) -> str:
    """安全的JSON序列化，处理Decimal类型"""
    return json.dumps(obj, cls=DecimalEncoder, **kwargs)


class CustomLLM:
    """自定义LLM包装器，用于xinference集成"""
    
    def __init__(self, api_url: str, api_key: str):
        self.api_url = api_url
        self.api_key = api_key
        self.session = None
    
    async def _ainit_session(self):
        """异步初始化HTTP会话"""
        if not self.session:
            connector = aiohttp.TCPConnector(limit=100)
            timeout = aiohttp.ClientTimeout(total=30)
            self.session = aiohttp.ClientSession(connector=connector, timeout=timeout)
    
    async def acall(self, prompt: str, **kwargs: Any) -> str:
        """异步调用xinference LLM"""
        try:
            await self._ainit_session()
            
            headers = {
                'Authorization': f'Bearer {self.api_key}',
                'Content-Type': 'application/json'
            }
            
            data = {
                'model': kwargs.get('model', settings.LLM_MODEL),
                'messages': [{'role': 'user', 'content': prompt}],
                'temperature': kwargs.get('temperature', settings.LLM_TEMPERATURE),
                'max_tokens': kwargs.get('max_tokens', settings.LLM_MAX_TOKENS),
                'stream': False  # xinference支持，明确指定非流式
            }
            
            async with self.session.post(self.api_url, headers=headers, json=data) as response:
                if response.status == 200:
                    result = await response.json()
                    content = result['choices'][0]['message']['content']
                    logger.debug(f"LLM调用成功: {len(content)} 字符")
                    return content
                else:
                    error_text = await response.text()
                    logger.error(f"LLM调用失败: {response.status}, {error_text}")
                    return "Error: LLM调用失败"
        
        except Exception as e:
            logger.error(f"LLM异步调用异常: {str(e)}")
            return f"Error: {str(e)}"
    
    # 兼容性别名
    async def _acall(self, prompt: str, **kwargs: Any) -> str:
        return await self.acall(prompt, **kwargs)
    
    async def cleanup(self):
        """清理资源"""
        if self.session:
            await self.session.close()
            self.session = None


class NLUEngine:
    """NLU引擎主类"""
    
    def __init__(self):
        self.llm: Optional[CustomLLM] = None
        self.duckling_url = settings.DUCKLING_URL if hasattr(settings, 'DUCKLING_URL') else None
        self._initialized = False
        self._intent_cache: Dict[str, Intent] = {}
        self._session: Optional[aiohttp.ClientSession] = None
        self.confidence_manager = ConfidenceManager(settings)
    
    async def initialize(self):
        """初始化NLU引擎"""
        try:
            # 初始化LLM - 优先使用LLM_API_BASE (xinference)
            api_url = settings.LLM_API_BASE or settings.LLM_API_URL
            if api_url and settings.LLM_API_KEY is not None:
                # 构建完整的xinference API端点
                if not api_url.endswith('/chat/completions'):
                    api_url = api_url.rstrip('/') + '/chat/completions'
                
                self.llm = CustomLLM(api_url, settings.LLM_API_KEY or "EMPTY")
                logger.info(f"LLM初始化完成 - 连接到: {api_url}")
                
                # 测试连接
                await self._test_llm_connection()
            else:
                logger.warning("LLM配置缺失，使用模拟模式")
            
            # 初始化HTTP会话
            connector = aiohttp.TCPConnector(limit=100)
            timeout = aiohttp.ClientTimeout(total=30)
            self._session = aiohttp.ClientSession(connector=connector, timeout=timeout)
            
            # 加载意图缓存
            await self._load_intent_cache()
            
            self._initialized = True
            logger.info("NLU引擎初始化完成")
            
        except Exception as e:
            logger.error(f"NLU引擎初始化失败: {str(e)}")
            raise
    
    async def cleanup(self):
        """清理资源"""
        if self.llm:
            await self.llm.cleanup()
        
        if self._session:
            await self._session.close()
            self._session = None
    
    async def _load_intent_cache(self):
        """加载意图缓存"""
        try:
            intents = Intent.select().where(Intent.is_active == True)
            self._intent_cache.clear()
            
            for intent in intents:
                self._intent_cache[intent.intent_name] = intent
            
            logger.info(f"加载了{len(self._intent_cache)}个意图到缓存")
            
        except Exception as e:
            logger.error(f"加载意图缓存失败: {str(e)}")
    
    async def _test_llm_connection(self):
        """测试LLM连接"""
        try:
            if not self.llm:
                return False
            
            # 发送简单测试请求
            test_prompt = "请回复'连接正常'"
            response = await self.llm._acall(test_prompt)
            
            if "Error:" not in response:
                logger.info("✅ LLM连接测试成功")
                return True
            else:
                logger.warning(f"⚠️ LLM连接测试失败: {response}")
                return False
                
        except Exception as e:
            logger.warning(f"⚠️ LLM连接测试异常: {str(e)}")
            return False
    
    async def recognize_intent(self, user_input: str, active_intents: List = None, 
                             context: Optional[Dict] = None) -> IntentRecognitionResult:
        """识别用户意图
        
        Args:
            user_input: 用户输入文本
            active_intents: 活跃意图列表
            context: 对话上下文
            
        Returns:
            IntentRecognitionResult: 意图识别结果
        """
        try:
            if not self._initialized:
                await self.initialize()
            
            # 构建意图识别提示
            prompt = await self._build_intent_prompt(user_input, active_intents, context)
            
            # 获取多种置信度计算
            llm_confidence = None
            rule_confidence = None
            
            # 调用LLM进行意图识别
            if self.llm:
                llm_response = await self.llm._acall(
                    prompt, 
                    model=settings.LLM_MODEL,
                    temperature=settings.LLM_TEMPERATURE,
                    max_tokens=settings.LLM_MAX_TOKENS
                )
                result = await self._parse_llm_response(llm_response, user_input)
                
                # 如果LLM调用失败，回退到规则匹配
                if (result.intent == 'unknown' and result.confidence == 0.0 and 
                    ('Error:' in str(result.reasoning) or 'LLM响应格式错误' in str(result.reasoning))):
                    logger.info("LLM调用失败，回退到规则匹配模式")
                    rule_result = await self._rule_based_intent_recognition(user_input, active_intents)
                    result = rule_result
                    rule_confidence = rule_result.confidence
                else:
                    # 校准LLM置信度
                    llm_confidence = self.confidence_manager.calibrate_confidence(
                        result.confidence, ConfidenceSource.LLM
                    )
                    # 同时获取规则置信度作为参考
                    rule_result = await self._rule_based_intent_recognition(user_input, active_intents)
                    if rule_result.intent == result.intent:
                        rule_confidence = self.confidence_manager.calibrate_confidence(
                            rule_result.confidence, ConfidenceSource.RULE
                        )
            else:
                # 模拟模式：使用简单规则匹配
                rule_result = await self._rule_based_intent_recognition(user_input, active_intents)
                result = rule_result
                rule_confidence = self.confidence_manager.calibrate_confidence(
                    rule_result.confidence, ConfidenceSource.RULE
                )
            
            # 计算上下文置信度（如果有上下文信息）
            context_confidence = None
            if context and result.intent != 'unknown':
                context_confidence = self._calculate_context_confidence(result.intent, context)
            
            # 使用置信度管理器计算混合置信度
            if llm_confidence is not None or rule_confidence is not None:
                confidence_score = self.confidence_manager.calculate_hybrid_confidence(
                    llm_confidence=llm_confidence,
                    rule_confidence=rule_confidence,
                    context_confidence=context_confidence,
                    intent_name=result.intent if result.intent != 'unknown' else None
                )
                
                # 更新结果的置信度
                result.confidence = confidence_score.value
                
                # 添加置信度解释到推理中
                if hasattr(result, 'reasoning') and result.reasoning:
                    result.reasoning += f" | {confidence_score.explanation}"
                else:
                    result.reasoning = confidence_score.explanation
            
            logger.info(f"意图识别完成: {user_input[:50]} -> {result.intent} ({result.confidence:.3f})")
            return result
            
        except Exception as e:
            logger.error(f"意图识别失败: {str(e)}")
            return IntentRecognitionResult.from_nlu_result(
                intent_name="unknown", 
                confidence=0.0, 
                reasoning=f"识别失败: {str(e)}",
                user_input=user_input
            )
    
    async def _build_intent_prompt(self, user_input: str, active_intents: List = None, 
                                  context: Optional[Dict] = None) -> str:
        """构建意图识别提示"""
        # 获取意图描述 - 优先使用传入的活跃意图列表
        intent_descriptions = []
        intents_to_use = {}
        
        if active_intents:
            # 使用传入的活跃意图列表
            for intent in active_intents:
                intents_to_use[intent.intent_name] = intent
        else:
            # 使用缓存的意图
            intents_to_use = self._intent_cache
        
        for intent_name, intent in intents_to_use.items():
            description = f"- {intent_name}: {intent.description}"
            
            # 添加示例
            examples = intent.get_examples()
            if examples:
                examples_text = ", ".join([f'"{ex}"' for ex in examples[:3]])  # 只取前3个
                description += f" (示例: {examples_text})"
            
            intent_descriptions.append(description)
        
        intents_text = "\n".join(intent_descriptions)
        
        # 构建上下文信息
        context_text = ""
        if context:
            context_text = f"对话上下文：{safe_json_dumps(context, ensure_ascii=False)}\n"
        
        prompt = f"""你是一个智能意图识别助手。请分析用户输入的文本，识别其真实意图。

        可用的意图类别：
        {intents_text}

        {context_text}
        用户输入："{user_input}"

        请分析用户的真实意图，并返回JSON格式的结果：
        {{
            "intent": "意图名称",
            "confidence": 0.95,
            "reasoning": "识别理由",
            "alternatives": [
                {{"intent": "备选意图1", "confidence": 0.8}},
                {{"intent": "备选意图2", "confidence": 0.6}}
            ]
        }}

        要求：
        1. confidence值应该在0-1之间，表示识别的置信度
        2. 如果无法确定意图，返回"unknown"
        3. reasoning要简要说明识别理由
        4. alternatives最多返回3个备选意图，按置信度降序排列
        5. 只返回JSON，不要其他文字
        """
        
        return prompt
    
    async def _parse_llm_response(self, llm_response: str, user_input: str) -> IntentRecognitionResult:
        """解析LLM响应"""
        try:
            # 清理响应文本
            response_text = llm_response.strip()
            if response_text.startswith("```json"):
                response_text = response_text[7:]
            if response_text.endswith("```"):
                response_text = response_text[:-3]
            
            # 解析JSON
            result_data = json.loads(response_text)
            
            intent = result_data.get('intent', 'unknown')
            confidence = float(result_data.get('confidence', 0.0))
            reasoning = result_data.get('reasoning', '')
            alternatives = result_data.get('alternatives', [])
            
            # 验证意图是否存在（检查缓存中的所有意图）
            if intent != 'unknown' and intent not in self._intent_cache:
                logger.warning(f"LLM返回了未知意图: {intent}")
                intent = 'unknown'
                confidence = 0.0
                reasoning += " (意图不在预定义列表中)"
            
            return IntentRecognitionResult.from_nlu_result(
                intent_name=intent,
                confidence=confidence,
                alternatives=alternatives,
                reasoning=reasoning,
                user_input=user_input
            )
            
        except json.JSONDecodeError as e:
            logger.error(f"LLM响应JSON解析失败: {e}, 响应: {llm_response}")
            return IntentRecognitionResult.from_nlu_result(
                intent_name="unknown", 
                confidence=0.0, 
                reasoning="LLM响应格式错误",
                user_input=user_input
            )
        except Exception as e:
            logger.error(f"解析LLM响应失败: {str(e)}")
            return IntentRecognitionResult.from_nlu_result(
                intent_name="unknown", 
                confidence=0.0, 
                reasoning=f"解析失败: {str(e)}",
                user_input=user_input
            )
    
    def _calculate_context_confidence(self, intent_name: str, context: Dict) -> float:
        """
        计算基于上下文的置信度
        
        Args:
            intent_name: 意图名称
            context: 对话上下文
            
        Returns:
            float: 上下文置信度 (0.0-1.0)
        """
        if not context:
            return 0.5  # 无上下文，返回中性置信度
        
        confidence = 0.5  # 基础置信度
        
        # 检查上一个意图的相关性
        if 'last_intent' in context:
            last_intent = context['last_intent']
            # 如果是相关意图，提升置信度
            if self._are_intents_related(intent_name, last_intent):
                confidence += 0.2
        
        # 检查会话历史中的意图频率
        if 'intent_history' in context:
            intent_history = context['intent_history']
            intent_count = intent_history.count(intent_name)
            total_count = len(intent_history)
            if total_count > 0:
                frequency_boost = (intent_count / total_count) * 0.2
                confidence += frequency_boost
        
        # 检查槽位上下文
        if 'slots' in context and context['slots']:
            # 如果上下文中有槽位信息，可能支持当前意图
            confidence += 0.1
        
        # 检查时间相关性
        if 'timestamp' in context:
            # 可以基于时间进行意图相关性判断
            # 这里简化处理
            confidence += 0.05
        
        return max(0.0, min(1.0, confidence))
    
    def _are_intents_related(self, intent1: str, intent2: str) -> bool:
        """检查两个意图是否相关"""
        # 定义相关意图组
        related_groups = [
            ['book_flight', 'check_flight_status', 'cancel_flight'],
            ['check_balance', 'transfer_money', 'transaction_history'],
            ['weather_query', 'travel_planning'],
        ]
        
        for group in related_groups:
            if intent1 in group and intent2 in group:
                return True
        
        return False
    
    async def _rule_based_intent_recognition(self, user_input: str, 
                                           active_intents: List = None) -> IntentRecognitionResult:
        """基于规则的意图识别（模拟模式）"""
        try:
            user_input_lower = user_input.lower()
            best_match = None
            best_score = 0.0
            
            # 确定要匹配的意图范围
            intents_to_match = {}
            if active_intents:
                for intent in active_intents:
                    intents_to_match[intent.intent_name] = intent
            else:
                intents_to_match = self._intent_cache
            
            # 简单关键词匹配
            for intent_name, intent in intents_to_match.items():
                score = 0.0
                
                # 检查意图名称匹配
                if intent_name.lower() in user_input_lower:
                    score += 0.8
                
                # 检查描述关键词匹配
                if intent.description:
                    desc_words = intent.description.lower().split()
                    for word in desc_words:
                        if len(word) > 2 and word in user_input_lower:
                            score += 0.2
                
                # 检查示例匹配
                examples = intent.get_examples()
                for example_text in examples[:10]:  # 限制处理数量
                    example_words = example_text.lower().split()
                    for word in example_words:
                        if len(word) > 2 and word in user_input_lower:
                            score += 0.1
                
                if score > best_score:
                    best_score = score
                    best_match = intent_name
            
            # 设置阈值
            if best_score < 0.3:
                return IntentRecognitionResult.from_nlu_result(
                    intent_name="unknown", 
                    confidence=best_score, 
                    reasoning="未找到匹配的意图",
                    user_input=user_input
                )
            
            return IntentRecognitionResult.from_nlu_result(
                intent_name=best_match, 
                confidence=min(best_score, 0.95),  # 规则匹配最高置信度限制为0.95
                reasoning=f"基于关键词匹配，得分: {best_score:.3f}",
                user_input=user_input
            )
            
        except Exception as e:
            logger.error(f"规则匹配失败: {str(e)}")
            return IntentRecognitionResult.from_nlu_result(
                intent_name="unknown", 
                confidence=0.0, 
                reasoning=f"规则匹配失败: {str(e)}",
                user_input=user_input
            )
    
    async def extract_entities(self, text: str, entity_types: List[str] = None,
                             use_duckling: bool = True, use_llm: bool = True) -> List[Dict[str, Any]]:
        """提取文本中的实体
        
        Args:
            text: 输入文本
            entity_types: 要提取的实体类型列表
            use_duckling: 是否使用Duckling
            use_llm: 是否使用LLM
            
        Returns:
            List[Dict]: 实体列表
        """
        try:
            if not text or not text.strip():
                return []
            
            entities = []
            
            # 使用Duckling提取结构化实体
            if use_duckling and self.duckling_url:
                try:
                    duckling_dims = self._get_duckling_dims_for_types(entity_types)
                    duckling_entities = await self._extract_duckling_entities(text, duckling_dims)
                    entities.extend(duckling_entities)
                    logger.debug(f"Duckling提取了 {len(duckling_entities)} 个实体")
                except Exception as e:
                    logger.warning(f"Duckling实体提取异常: {str(e)}")
            
            # 使用LLM提取命名实体
            if use_llm and self.llm:
                try:
                    llm_types = self._get_llm_types_for_extraction(entity_types)
                    llm_entities = await self._extract_llm_entities(text, llm_types)
                    entities.extend(llm_entities)
                    logger.debug(f"LLM提取了 {len(llm_entities)} 个实体")
                except Exception as e:
                    logger.warning(f"LLM实体提取异常: {str(e)}")
            
            # 规则匹配（针对特定业务实体）
            try:
                rule_entities = await self._extract_rule_based_entities(text, entity_types)
                entities.extend(rule_entities)
                logger.debug(f"规则匹配了 {len(rule_entities)} 个实体")
            except Exception as e:
                logger.warning(f"规则实体提取异常: {str(e)}")
            
            # 合并和去重
            if entities:
                entities = self._merge_entities(entities)
                
                # 过滤低质量实体
                entities = self._filter_low_quality_entities(entities)
            
            logger.info(f"实体提取完成: '{text[:50]}...' -> {len(entities)} 个实体")
            return entities
            
        except Exception as e:
            logger.error(f"实体提取失败: {str(e)}")
            return []
    
    def _get_duckling_dims_for_types(self, entity_types: List[str] = None) -> List[str]:
        """根据实体类型获取Duckling维度"""
        if not entity_types:
            return ["time", "number", "amount-of-money", "phone-number", "email", "url"]
        
        type_to_dims = {
            'DATE': ['time'],
            'TIME': ['time'],
            'NUMBER': ['number'],
            'MONEY': ['amount-of-money'],
            'PHONE': ['phone-number'],
            'EMAIL': ['email'],
            'URL': ['url'],
            'DISTANCE': ['distance'],
            'VOLUME': ['volume'],
            'TEMPERATURE': ['temperature']
        }
        
        dims = set()
        for entity_type in entity_types:
            dims.update(type_to_dims.get(entity_type.upper(), []))
        
        # 默认包含常用的结构化实体
        if not dims:
            dims = {"time", "number", "amount-of-money"}
        
        return list(dims)
    
    def _get_llm_types_for_extraction(self, entity_types: List[str] = None) -> List[str]:
        """根据需求获取LLM提取的实体类型"""
        if entity_types:
            # 过滤出LLM适合提取的类型
            llm_suitable_types = {
                'PERSON', 'LOCATION', 'ORGANIZATION', 'PRODUCT',
                'FLIGHT', 'CITY', 'ACCOUNT', 'CUSTOM'
            }
            return [t for t in entity_types if t.upper() in llm_suitable_types]
        
        # 默认的LLM提取类型
        return ["PERSON", "LOCATION", "ORGANIZATION", "CITY", "FLIGHT", "CUSTOM"]
    
    async def _extract_rule_based_entities(self, text: str, entity_types: List[str] = None) -> List[Dict[str, Any]]:
        """基于规则的实体提取"""
        try:
            import re
            entities = []
            text_lower = text.lower()
            
            # 航班号匹配
            if not entity_types or 'FLIGHT' in entity_types:
                flight_pattern = r'[A-Z]{2}\d{3,4}|[A-Z]{3}\d{3,4}'
                for match in re.finditer(flight_pattern, text, re.IGNORECASE):
                    entities.append({
                        'entity': 'FLIGHT',
                        'value': match.group().upper(),
                        'text': match.group(),
                        'start': match.start(),
                        'end': match.end(),
                        'confidence': 0.85,
                        'source': 'rule'
                    })
            
            # 中国城市名称匹配
            if not entity_types or 'CITY' in entity_types:
                major_cities = [
                    '北京', '上海', '广州', '深圳', '杭州', '南京', '苏州', '天津',
                    '成都', '重庆', '武汉', '西安', '青岛', '大连', '厦门', '福州',
                    '长沙', '昆明', '南宁', '哈尔滨', '沈阳', '石家庄', '郑州', '济南',
                    '太原', '呼和浩特', '长春', '贵阳', '兰州', '银川', '西宁', '乌鲁木齐'
                ]
                
                for city in major_cities:
                    start = text.find(city)
                    if start != -1:
                        entities.append({
                            'entity': 'CITY',
                            'value': city,
                            'text': city,
                            'start': start,
                            'end': start + len(city),
                            'confidence': 0.9,
                            'source': 'rule'
                        })
            
            # 手机号码匹配
            if not entity_types or 'phone-number' in entity_types:
                phone_pattern = r'1[3-9]\d{9}'
                for match in re.finditer(phone_pattern, text):
                    entities.append({
                        'entity': 'phone-number',
                        'value': match.group(),
                        'text': match.group(),
                        'start': match.start(),
                        'end': match.end(),
                        'confidence': 0.95,
                        'source': 'rule'
                    })
            
            # 邮箱地址匹配
            if not entity_types or 'email' in entity_types:
                email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
                for match in re.finditer(email_pattern, text):
                    entities.append({
                        'entity': 'email',
                        'value': match.group(),
                        'text': match.group(),
                        'start': match.start(),
                        'end': match.end(),
                        'confidence': 0.9,
                        'source': 'rule'
                    })
            
            # URL匹配
            if not entity_types or 'url' in entity_types:
                url_pattern = r'https?://[^\s<>"{}|\\^`\[\]]+'
                for match in re.finditer(url_pattern, text):
                    entities.append({
                        'entity': 'url',
                        'value': match.group(),
                        'text': match.group(),
                        'start': match.start(),
                        'end': match.end(),
                        'confidence': 0.9,
                        'source': 'rule'
                    })
            
            # 数字匹配
            if not entity_types or 'number' in entity_types:
                number_pattern = r'\b\d+(\.\d+)?\b'
                for match in re.finditer(number_pattern, text):
                    try:
                        value = float(match.group()) if '.' in match.group() else int(match.group())
                        entities.append({
                            'entity': 'number',
                            'value': value,
                            'text': match.group(),
                            'start': match.start(),
                            'end': match.end(),
                            'confidence': 0.8,
                            'source': 'rule'
                        })
                    except ValueError:
                        continue
            
            # 金额匹配（带单位）
            if not entity_types or 'amount-of-money' in entity_types:
                money_pattern = r'\b(\d+(?:\.\d+)?)\s*(?:元|块|钱|美元|USD|人民币|RMB)\b'
                for match in re.finditer(money_pattern, text):
                    try:
                        amount = float(match.group(1))
                        currency = 'CNY'  # 默认人民币
                        if '美元' in match.group() or 'USD' in match.group():
                            currency = 'USD'
                        
                        entities.append({
                            'entity': 'amount-of-money',
                            'value': {
                                'value': amount,
                                'unit': currency
                            },
                            'text': match.group(),
                            'start': match.start(),
                            'end': match.end(),
                            'confidence': 0.9,
                            'source': 'rule'
                        })
                    except ValueError:
                        continue
            
            # 常见人名匹配（简化版）
            if not entity_types or 'PERSON' in entity_types:
                common_surnames = [
                    '张', '王', '李', '赵', '陈', '刘', '杨', '黄', '周', '吴',
                    '徐', '孙', '马', '朱', '胡', '郭', '何', '高', '林', '罗'
                ]
                
                for surname in common_surnames:
                    # 匹配"姓+1-2个字"的模式
                    name_pattern = f'{surname}[\\u4e00-\\u9fa5]{{1,2}}(?![\\u4e00-\\u9fa5])'
                    for match in re.finditer(name_pattern, text):
                        # 简单验证：不是常见词汇的一部分
                        if not self._is_common_word_part(match.group(), text, match.start()):
                            entities.append({
                                'entity': 'PERSON',
                                'value': match.group(),
                                'text': match.group(),
                                'start': match.start(),
                                'end': match.end(),
                                'confidence': 0.7,  # 人名识别置信度相对较低
                                'source': 'rule'
                            })
            
            # 组织机构匹配
            if not entity_types or 'ORGANIZATION' in entity_types:
                org_keywords = ['银行', '公司', '集团', '有限公司', '股份有限公司', '科技', '学校', '大学', '医院']
                for keyword in org_keywords:
                    # 查找包含关键词的组织名
                    pattern = f'[\\u4e00-\\u9fa5]{{2,8}}{keyword}'
                    for match in re.finditer(pattern, text):
                        entities.append({
                            'entity': 'ORGANIZATION',
                            'value': match.group(),
                            'text': match.group(),
                            'start': match.start(),
                            'end': match.end(),
                            'confidence': 0.8,
                            'source': 'rule'
                        })
            
            return entities
            
        except Exception as e:
            logger.error(f"规则实体提取失败: {str(e)}")
            return []
    
    def _is_common_word_part(self, name: str, full_text: str, start_pos: int) -> bool:
        """检查是否是常见词汇的一部分（用于人名验证）"""
        try:
            # 检查前后是否有其他汉字（可能是词汇的一部分）
            if start_pos > 0 and full_text[start_pos - 1].isalpha():
                return True
            
            end_pos = start_pos + len(name)
            if end_pos < len(full_text) and full_text[end_pos].isalpha():
                return True
            
            # 常见的非人名词汇
            common_words = [
                '张三', '李四', '王五',  # 示例名字
                '张开', '王国', '李子',  # 常见词汇
            ]
            
            return name in common_words
            
        except Exception:
            return False
    
    def _filter_low_quality_entities(self, entities: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """过滤低质量实体"""
        try:
            filtered = []
            
            for entity in entities:
                # 基本质量检查
                if not entity.get('value') or not entity.get('text'):
                    continue
                
                # 置信度过低
                if entity.get('confidence', 0) < 0.3:
                    continue
                
                # 文本太短且不是数字/时间类型
                if (len(entity.get('text', '')) < 2 and 
                    entity.get('entity') not in ['time', 'number']):
                    continue
                
                # 单字符且置信度不够高
                if (len(entity.get('text', '')) == 1 and 
                    entity.get('confidence', 0) < 0.8):
                    continue
                
                filtered.append(entity)
            
            return filtered
            
        except Exception as e:
            logger.warning(f"实体质量过滤失败: {str(e)}")
            return entities
    
    async def _extract_duckling_entities(self, text: str, dims: List[str] = None) -> List[Dict[str, Any]]:
        """使用Duckling提取实体
        
        Args:
            text: 输入文本
            dims: 要提取的实体维度列表
            
        Returns:
            List[Dict]: 提取的实体列表
        """
        try:
            if not self.duckling_url or not self._session:
                logger.debug("Duckling URL或会话未配置，跳过Duckling实体提取")
                return []
            
            # 默认的实体维度
            if dims is None:
                dims = [
                    "time", "number", "amount-of-money", "phone-number", 
                    "email", "url", "distance", "volume", "temperature"
                ]
            
            data = {
                'locale': 'zh_CN',
                'text': text,
                'dims': safe_json_dumps(dims)
            }
            
            async with self._session.post(
                f"{self.duckling_url}/parse",
                data=data,
                timeout=aiohttp.ClientTimeout(total=10)
            ) as response:
                if response.status == 200:
                    duckling_result = await response.json()
                    
                    entities = []
                    for item in duckling_result:
                        # 处理不同类型的value结构
                        entity_value = self._extract_duckling_value(item)
                        
                        entity = {
                            'entity': item['dim'],
                            'value': entity_value,
                            'start': item['start'],
                            'end': item['end'],
                            'text': text[item['start']:item['end']],
                            'confidence': 0.95,  # Duckling结果置信度很高
                            'source': 'duckling',
                            'raw_value': item.get('value', {}),  # 保留原始值信息
                            'grain': item.get('value', {}).get('grain'),  # 时间粒度
                            'latent': item.get('latent', False)  # 是否为潜在匹配
                        }
                        entities.append(entity)
                    
                    logger.debug(f"Duckling提取到 {len(entities)} 个实体")
                    return entities
                else:
                    error_text = await response.text()
                    logger.warning(f"Duckling请求失败: {response.status}, {error_text}")
                    return []
                    
        except asyncio.TimeoutError:
            logger.warning("Duckling请求超时")
            return []
        except Exception as e:
            logger.error(f"Duckling实体提取失败: {str(e)}")
            return []
    
    def _extract_duckling_value(self, duckling_item: Dict) -> Any:
        """提取Duckling实体的值"""
        try:
            value_data = duckling_item.get('value', {})
            dim = duckling_item.get('dim')
            
            if dim == 'time':
                # 时间实体：返回ISO格式或相对时间信息
                if 'value' in value_data:
                    return value_data['value']
                elif 'from' in value_data and 'to' in value_data:
                    return {
                        'from': value_data['from']['value'],
                        'to': value_data['to']['value'],
                        'type': 'interval'
                    }
                else:
                    return value_data
            
            elif dim == 'number':
                # 数字实体：返回数值
                return value_data.get('value', 0)
            
            elif dim == 'amount-of-money':
                # 金额实体：返回金额和货币信息
                return {
                    'value': value_data.get('value', 0),
                    'unit': value_data.get('unit', 'CNY')
                }
            
            elif dim in ['distance', 'volume', 'temperature']:
                # 测量实体：返回数值和单位
                return {
                    'value': value_data.get('value', 0),
                    'unit': value_data.get('unit', '')
                }
            
            else:
                # 其他实体：返回原始值
                return value_data.get('value', value_data)
                
        except Exception as e:
            logger.warning(f"解析Duckling值失败: {str(e)}")
            return duckling_item.get('value', {})
    
    async def _extract_llm_entities(self, text: str, entity_types: List[str] = None) -> List[Dict[str, Any]]:
        """使用LLM提取实体
        
        Args:
            text: 输入文本
            entity_types: 要提取的实体类型列表
            
        Returns:
            List[Dict]: 提取的实体列表
        """
        try:
            if not self.llm:
                logger.debug("LLM未配置，跳过LLM实体提取")
                return []
            
            # 默认的实体类型
            if entity_types is None:
                entity_types = [
                    "PERSON", "LOCATION", "ORGANIZATION", "PRODUCT", 
                    "FLIGHT", "CITY", "DATE", "ACCOUNT", "CUSTOM"
                ]
            
            # 构建实体类型描述
            entity_descriptions = {
                "PERSON": "人名、姓名",
                "LOCATION": "地点、地址、位置信息",
                "ORGANIZATION": "机构、公司名、组织名称",
                "PRODUCT": "产品名称、服务名称",
                "FLIGHT": "航班号、航空公司",
                "CITY": "城市名称、出发地、目的地",
                "DATE": "日期、时间相关信息（如果Duckling未识别）",
                "ACCOUNT": "账户相关信息",
                "CUSTOM": "其他重要的业务实体"
            }
            
            entity_type_text = "\n".join([
                f"- {etype}: {entity_descriptions.get(etype, '相关信息')}"
                for etype in entity_types
            ])
            
            prompt = f"""请从以下中文文本中提取相关实体信息：

文本："{text}"

请识别以下类型的实体：
{entity_type_text}

提取规则：
1. 只提取明确出现在文本中的实体
2. 计算准确的文本位置（start和end）
3. 为每个实体分配合理的置信度（0.7-0.95）
4. 如果一个词可以是多种类型，选择最合适的类型

返回JSON格式：
[
    {{
        "entity": "实体类型",
        "value": "标准化的实体值",
        "text": "原文中的文本片段",
        "start": 起始字符位置,
        "end": 结束字符位置,
        "confidence": 0.85
    }}
]

如果没有找到任何实体，返回空数组 []。
只返回JSON，不要其他文字。
"""
            
            llm_response = await self.llm._acall(prompt)
            
            # 解析LLM响应
            response_text = llm_response.strip()
            if response_text.startswith("```json"):
                response_text = response_text[7:-3]
            elif response_text.startswith("```"):
                response_text = response_text[3:-3]
            
            # 处理可能的格式问题
            response_text = response_text.strip()
            
            entities_data = json.loads(response_text)
            
            # 验证和清理实体数据
            cleaned_entities = []
            for entity in entities_data:
                if self._validate_llm_entity(entity, text):
                    entity['source'] = 'llm'
                    # 确保置信度在合理范围内
                    entity['confidence'] = max(0.5, min(0.95, float(entity.get('confidence', 0.8))))
                    cleaned_entities.append(entity)
            
            logger.debug(f"LLM提取到 {len(cleaned_entities)} 个有效实体")
            return cleaned_entities
            
        except json.JSONDecodeError as e:
            logger.warning(f"LLM实体响应JSON解析失败: {e}, 响应: {llm_response[:200] if 'llm_response' in locals() else 'N/A'}")
            return []
        except Exception as e:
            logger.error(f"LLM实体提取失败: {str(e)}")
            return []
    
    def _validate_llm_entity(self, entity: Dict, original_text: str) -> bool:
        """验证LLM提取的实体是否有效"""
        try:
            # 检查必需字段
            required_fields = ['entity', 'value', 'text', 'start', 'end']
            if not all(field in entity for field in required_fields):
                logger.debug(f"实体缺少必需字段: {entity}")
                return False
            
            # 检查位置信息
            start = int(entity['start'])
            end = int(entity['end'])
            
            if start < 0 or end > len(original_text) or start >= end:
                logger.debug(f"实体位置无效: start={start}, end={end}, text_len={len(original_text)}")
                return False
            
            # 检查文本是否匹配
            expected_text = original_text[start:end]
            actual_text = entity['text']
            
            if expected_text != actual_text:
                logger.debug(f"实体文本不匹配: expected='{expected_text}', actual='{actual_text}'")
                return False
            
            # 检查实体值是否为空
            if not entity['value'] or not entity['value'].strip():
                logger.debug(f"实体值为空: {entity}")
                return False
            
            return True
            
        except (ValueError, TypeError) as e:
            logger.debug(f"实体验证失败: {e}")
            return False
    
    def _merge_entities(self, entities: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """合并和去重实体
        
        优先级规则：
        1. Duckling > LLM（结构化实体优先）
        2. 置信度高的优先
        3. 具体类型 > 通用类型
        4. 长度长的 > 长度短的（更具体）
        """
        try:
            if not entities:
                return []
            
            merged = []
            
            # 按优先级排序
            def priority_key(entity):
                source_priority = {'duckling': 3, 'llm': 2, 'rule': 1}
                type_priority = {
                    'time': 10, 'number': 9, 'amount-of-money': 9,
                    'phone-number': 8, 'email': 8, 'url': 8,
                    'PERSON': 7, 'LOCATION': 7, 'CITY': 8,
                    'ORGANIZATION': 6, 'FLIGHT': 7,
                    'CUSTOM': 3
                }
                
                confidence = entity.get('confidence', 0.0)
                source_score = source_priority.get(entity.get('source', 'rule'), 1)
                type_score = type_priority.get(entity.get('entity', ''), 5)
                length_score = entity.get('end', 0) - entity.get('start', 0)
                
                return (source_score, confidence, type_score, length_score)
            
            entities.sort(key=priority_key, reverse=True)
            
            # 检测重叠和合并
            for entity in entities:
                start = entity.get('start', 0)
                end = entity.get('end', 0)
                
                # 检查是否与已添加的实体重叠
                overlap_entity = None
                max_overlap = 0
                
                for existing in merged:
                    existing_start = existing.get('start', 0)
                    existing_end = existing.get('end', 0)
                    
                    # 计算重叠区域
                    overlap_start = max(start, existing_start)
                    overlap_end = min(end, existing_end)
                    
                    if overlap_start < overlap_end:
                        overlap_size = overlap_end - overlap_start
                        entity_size = end - start
                        existing_size = existing_end - existing_start
                        
                        # 计算重叠比例
                        overlap_ratio = overlap_size / min(entity_size, existing_size)
                        
                        if overlap_ratio > 0.5:  # 重叠超过50%
                            if overlap_size > max_overlap:
                                max_overlap = overlap_size
                                overlap_entity = existing
                
                if overlap_entity:
                    # 决定是否替换或合并
                    if self._should_replace_entity(entity, overlap_entity):
                        merged.remove(overlap_entity)
                        merged.append(entity)
                    elif self._should_merge_entities(entity, overlap_entity):
                        # 合并实体信息
                        merged_entity = self._merge_entity_pair(entity, overlap_entity)
                        merged.remove(overlap_entity)
                        merged.append(merged_entity)
                    # 否则跳过当前实体
                else:
                    # 没有重叠，直接添加
                    merged.append(entity)
            
            # 按位置排序返回
            merged.sort(key=lambda x: x.get('start', 0))
            
            logger.debug(f"实体合并完成: {len(entities)} -> {len(merged)}")
            return merged
            
        except Exception as e:
            logger.error(f"实体合并失败: {str(e)}")
            return entities
    
    def _should_replace_entity(self, new_entity: Dict, existing_entity: Dict) -> bool:
        """判断是否应该用新实体替换现有实体"""
        try:
            # 来源优先级
            source_priority = {'duckling': 3, 'llm': 2, 'rule': 1}
            new_source_score = source_priority.get(new_entity.get('source', 'rule'), 1)
            existing_source_score = source_priority.get(existing_entity.get('source', 'rule'), 1)
            
            if new_source_score > existing_source_score:
                return True
            elif new_source_score < existing_source_score:
                return False
            
            # 相同来源时，比较置信度
            new_confidence = new_entity.get('confidence', 0.0)
            existing_confidence = existing_entity.get('confidence', 0.0)
            
            if new_confidence > existing_confidence + 0.1:  # 显著更高的置信度
                return True
            
            return False
            
        except Exception:
            return False
    
    def _should_merge_entities(self, entity1: Dict, entity2: Dict) -> bool:
        """判断是否应该合并两个实体"""
        try:
            # 如果是相同类型且来源不同，可以合并
            if (entity1.get('entity') == entity2.get('entity') and 
                entity1.get('source') != entity2.get('source')):
                return True
            
            # 如果是互补的实体类型，可以合并
            complementary_types = [
                ('time', 'DATE'),
                ('number', 'CUSTOM'),
                ('LOCATION', 'CITY')
            ]
            
            type1 = entity1.get('entity')
            type2 = entity2.get('entity')
            
            for t1, t2 in complementary_types:
                if (type1 == t1 and type2 == t2) or (type1 == t2 and type2 == t1):
                    return True
            
            return False
            
        except Exception:
            return False
    
    def _merge_entity_pair(self, entity1: Dict, entity2: Dict) -> Dict:
        """合并两个实体"""
        try:
            # 选择更高质量的实体作为基础
            if self._should_replace_entity(entity1, entity2):
                base_entity = entity1.copy()
                other_entity = entity2
            else:
                base_entity = entity2.copy()
                other_entity = entity1
            
            # 合并位置信息（取覆盖范围）
            start1, end1 = entity1.get('start', 0), entity1.get('end', 0)
            start2, end2 = entity2.get('start', 0), entity2.get('end', 0)
            
            base_entity['start'] = min(start1, start2)
            base_entity['end'] = max(end1, end2)
            
            # 合并来源信息
            sources = set()
            if entity1.get('source'):
                sources.add(entity1['source'])
            if entity2.get('source'):
                sources.add(entity2['source'])
            base_entity['merged_from'] = list(sources)
            
            # 如果有互补信息，添加到额外字段
            if other_entity.get('value') != base_entity.get('value'):
                base_entity['alternative_value'] = other_entity.get('value')
            
            return base_entity
            
        except Exception as e:
            logger.warning(f"合并实体对失败: {str(e)}")
            return entity1
    
    async def extract_slots(self, text: str, slot_definitions: List[Dict], 
                          context: Optional[Dict] = None) -> Dict[str, Any]:
        """提取槽位信息
        
        Args:
            text: 输入文本
            slot_definitions: 槽位定义列表
            context: 对话上下文
            
        Returns:
            Dict: 槽位提取结果
        """
        try:
            if not slot_definitions:
                return {}
            
            # 首先提取所有实体
            entities = await self.extract_entities(text)
            
            # 构建槽位提取提示
            slots_prompt = await self._build_slots_prompt(text, slot_definitions, entities, context)
            
            # 使用LLM提取槽位
            if self.llm:
                llm_response = await self.llm._acall(slots_prompt)
                slots_result = await self._parse_slots_response(llm_response)
                logger.info(f"LLM槽位提取结果: {slots_result}")
            else:
                # 简单的实体映射到槽位
                slots_result = self._map_entities_to_slots(entities, slot_definitions)
                logger.info(f"实体映射结果: {slots_result}")
            
            return slots_result
            
        except Exception as e:
            logger.error(f"槽位提取失败: {str(e)}")
            return {}
    
    async def _build_slots_prompt(self, text: str, slot_definitions: List[Dict],
                                entities: List[Dict], context: Optional[Dict] = None) -> str:
        """构建槽位提取提示"""
        # 构建槽位定义描述
        slots_desc = []
        for slot_def in slot_definitions:
            desc = f"- {slot_def['slot_name']} ({slot_def['slot_type']}): {slot_def.get('description', '')}"
            if slot_def.get('is_required'):
                desc += " [必需]"
            slots_desc.append(desc)
        
        slots_text = "\n".join(slots_desc)
        
        # 构建已识别实体信息
        entities_text = ""
        if entities:
            entities_desc = [f"- {e['entity']}: {e['value']} ({e['text']})" for e in entities]
            entities_text = f"已识别的实体：\n" + "\n".join(entities_desc) + "\n"
        
        # 构建上下文信息
        context_text = ""
        if context:
            context_text = f"对话上下文：{safe_json_dumps(context, ensure_ascii=False)}\n"
        
        prompt = f"""请从用户输入中提取指定的槽位信息。

需要提取的槽位：
{slots_text}

{entities_text}
{context_text}
用户输入："{text}"

请分析用户输入，提取相应的槽位值，返回JSON格式：
{{
    "槽位名称": {{
        "value": "提取的值",
        "confidence": 0.95,
        "source": "提取来源",
        "original_text": "原文中的文本"
    }}
}}

要求：
1. 只提取有明确值的槽位
2. confidence表示提取置信度(0-1)
3. source可以是"text", "entity", "context"
4. 如果没有找到任何槽位值，返回空对象 {{}}
5. 只返回JSON，不要其他文字
"""
        
        return prompt
    
    async def _parse_slots_response(self, llm_response: str) -> Dict[str, Any]:
        """解析槽位提取响应"""
        try:
            response_text = llm_response.strip()
            if response_text.startswith("```json"):
                response_text = response_text[7:-3]
            
            slots_data = json.loads(response_text)
            return slots_data
            
        except json.JSONDecodeError as e:
            logger.error(f"槽位响应JSON解析失败: {e}, 响应: {llm_response}")
            return {}
        except Exception as e:
            logger.error(f"解析槽位响应失败: {str(e)}")
            return {}
    
    def _map_entities_to_slots(self, entities: List[Dict], 
                             slot_definitions: List[Dict]) -> Dict[str, Any]:
        """将实体映射到槽位（简单版本）"""
        try:
            slots_result = {}
            
            for slot_def in slot_definitions:
                slot_name = slot_def['slot_name']
                slot_type = slot_def['slot_type']
                
                # 简单的类型映射
                for entity in entities:
                    entity_type = entity['entity']
                    entity_value = entity.get('value')
                    entity_text = entity.get('text', '')
                    
                    # 调试日志
                    logger.info(f"尝试映射: slot={slot_name}({slot_type}) <- entity={entity_text}({entity_type})")
                    
                    # 基于类型匹配
                    if ((slot_type.upper() == 'NUMBER' and entity_type == 'number') or
                        (slot_type.upper() == 'TIME' and entity_type == 'time') or
                        (slot_type.upper() == 'DATE' and entity_type == 'time') or
                        (slot_type.upper() == 'PHONE' and entity_type == 'phone-number') or
                        (slot_type.upper() == 'EMAIL' and entity_type == 'email') or
                        (slot_type.upper() == 'LOCATION' and entity_type == 'location') or
                        (slot_type.upper() == 'CITY' and entity_type == 'location') or
                        (slot_type.upper() == 'TEXT' and entity_type in ['location', 'person', 'organization', 'misc'])):
                        
                        # 使用entity的text作为value，如果entity没有value字段
                        final_value = entity_value if entity_value is not None else entity_text
                        
                        # 对于日期类型，优先使用original_text进行标准化
                        if slot_type.upper() == 'DATE' and entity_text:
                            # 使用原始文本而不是解析后的值，让后续的标准化处理
                            final_value = entity_text
                            logger.info(f"日期槽位使用原始文本: {entity_text}")
                        
                        logger.info(f"映射成功: {slot_name} = {final_value} (从实体: {entity_text})")
                        
                        slots_result[slot_name] = {
                            'value': final_value,
                            'confidence': entity.get('confidence', 0.8),
                            'source': 'entity',
                            'original_text': entity_text
                        }
                        break
            
            return slots_result
            
        except Exception as e:
            logger.error(f"实体到槽位映射失败: {str(e)}")
            return {}
    
    async def parse_time_entities(self, text: str) -> List[Dict[str, Any]]:
        """专门解析时间实体（使用Duckling）
        
        Args:
            text: 输入文本
            
        Returns:
            List[Dict]: 时间实体列表
        """
        try:
            if not self.duckling_url or not self._session:
                return []
            
            data = {
                'locale': 'zh_CN',
                'text': text,
                'dims': '["time"]'
            }
            
            async with self._session.post(
                f"{self.duckling_url}/parse",
                data=data
            ) as response:
                if response.status == 200:
                    return await response.json()
                else:
                    logger.warning(f"Duckling时间解析失败: {response.status}")
                    return []
                    
        except Exception as e:
            logger.error(f"时间实体解析失败: {str(e)}")
            return []
    
    async def refresh_intent_cache(self):
        """刷新意图缓存"""
        await self._load_intent_cache()
        logger.info("意图缓存已刷新")
    
    def get_cached_intents(self) -> List[str]:
        """获取缓存的意图列表"""
        return list(self._intent_cache.keys())
    
    async def validate_intent_examples(self, intent_name: str) -> Dict[str, Any]:
        """验证意图示例的质量
        
        Args:
            intent_name: 意图名称
            
        Returns:
            Dict: 验证结果
        """
        try:
            if intent_name not in self._intent_cache:
                return {'error': '意图不存在'}
            
            intent = self._intent_cache[intent_name]
            examples = intent.get_examples()
            
            if not examples:
                return {'error': '意图没有示例'}
            
            # 测试每个示例的识别准确性
            correct_count = 0
            total_count = len(examples)
            failed_examples = []
            
            for example_text in examples[:10]:  # 限制测试数量
                result = await self.recognize_intent(example_text)
                if result.intent == intent_name and result.confidence > 0.7:
                    correct_count += 1
                else:
                    failed_examples.append({
                        'text': example_text,
                        'expected': intent_name,
                        'actual': result.intent,
                        'confidence': result.confidence
                    })
            
            accuracy = correct_count / min(total_count, 10)
            
            return {
                'intent_name': intent_name,
                'total_examples': total_count,
                'tested_examples': min(total_count, 10),
                'correct_predictions': correct_count,
                'accuracy': accuracy,
                'failed_examples': failed_examples,
                'status': 'good' if accuracy >= 0.8 else 'needs_improvement'
            }
            
        except Exception as e:
            logger.error(f"验证意图示例失败: {str(e)}")
            return {'error': f'验证失败: {str(e)}'}