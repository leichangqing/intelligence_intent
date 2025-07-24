"""
同义词管理服务
负责加载和管理同义词词典、停用词和实体模式
"""
from typing import Dict, List, Set, Optional, Tuple
import asyncio
from collections import defaultdict

from src.models.synonym import SynonymGroup, SynonymTerm, StopWord, EntityPattern
from src.services.cache_service import CacheService
from src.utils.logger import get_logger

logger = get_logger(__name__)


class SynonymService:
    """同义词管理服务"""
    
    def __init__(self, cache_service: Optional[CacheService] = None):
        self.cache_service = cache_service
        self.cache_namespace = "synonym"
        self.cache_ttl = 3600  # 1小时
        
        # 内存缓存
        self._synonym_dict: Dict[str, str] = {}
        self._reverse_synonym_dict: Dict[str, List[str]] = defaultdict(list)
        self._stop_words: Set[str] = set()
        self._entity_patterns: Dict[str, str] = {}
        self._last_update = None
    
    async def initialize(self):
        """初始化服务，加载所有词典"""
        try:
            await self.reload_all_data()
            logger.info("同义词服务初始化完成")
        except Exception as e:
            logger.error(f"同义词服务初始化失败: {str(e)}")
            raise
    
    async def reload_all_data(self):
        """重新加载所有数据"""
        try:
            # 并发加载所有数据
            await asyncio.gather(
                self._load_synonyms(),
                self._load_stop_words(),
                self._load_entity_patterns()
            )
            
            self._last_update = asyncio.get_event_loop().time()
            logger.info("同义词数据重新加载完成")
            
        except Exception as e:
            logger.error(f"重新加载同义词数据失败: {str(e)}")
            raise
    
    async def _load_synonyms(self):
        """加载同义词词典"""
        try:
            # 尝试从缓存获取
            if self.cache_service:
                cached_data = await self.cache_service.get(
                    "synonym_dict", namespace=self.cache_namespace
                )
                if cached_data:
                    self._synonym_dict = cached_data['synonym_dict']
                    self._reverse_synonym_dict = defaultdict(list, cached_data['reverse_dict'])
                    logger.debug("从缓存加载同义词词典")
                    return
            
            # 从数据库加载
            synonym_dict = {}
            reverse_dict = defaultdict(list)
            
            # 获取所有激活的同义词组
            groups = list(
                SynonymGroup.select()
                .where(SynonymGroup.is_active == True)
                .order_by(SynonymGroup.priority.desc())
            )
            
            for group in groups:
                standard_term = group.standard_term
                
                # 获取该组的所有激活同义词
                terms = list(
                    SynonymTerm.select()
                    .where(
                        (SynonymTerm.group == group) &
                        (SynonymTerm.is_active == True)
                    )
                    .order_by(SynonymTerm.confidence.desc())
                )
                
                # 构建同义词映射
                for term in terms:
                    synonym_dict[term.term] = standard_term
                    reverse_dict[standard_term].append(term.term)
            
            self._synonym_dict = synonym_dict
            self._reverse_synonym_dict = reverse_dict
            
            # 缓存数据
            if self.cache_service:
                await self.cache_service.set(
                    "synonym_dict",
                    {
                        'synonym_dict': synonym_dict,
                        'reverse_dict': dict(reverse_dict)
                    },
                    ttl=self.cache_ttl,
                    namespace=self.cache_namespace
                )
            
            logger.info(f"加载同义词词典完成: {len(synonym_dict)}个同义词, {len(reverse_dict)}个词组")
            
        except Exception as e:
            logger.error(f"加载同义词词典失败: {str(e)}")
            # 使用默认词典作为fallback
            self._synonym_dict = self._get_default_synonyms()
            self._reverse_synonym_dict = self._build_reverse_dict(self._synonym_dict)
    
    async def _load_stop_words(self):
        """加载停用词"""
        try:
            # 尝试从缓存获取
            if self.cache_service:
                cached_words = await self.cache_service.get(
                    "stop_words", namespace=self.cache_namespace
                )
                if cached_words:
                    self._stop_words = set(cached_words)
                    logger.debug("从缓存加载停用词")
                    return
            
            # 从数据库加载
            stop_words = StopWord.get_active_words(language='zh')
            self._stop_words = stop_words
            
            # 如果数据库为空，使用默认停用词
            if not stop_words:
                self._stop_words = self._get_default_stop_words()
                logger.warning("数据库中无停用词，使用默认停用词")
            
            # 缓存数据
            if self.cache_service:
                await self.cache_service.set(
                    "stop_words",
                    list(self._stop_words),
                    ttl=self.cache_ttl,
                    namespace=self.cache_namespace
                )
            
            logger.info(f"加载停用词完成: {len(self._stop_words)}个")
            
        except Exception as e:
            logger.error(f"加载停用词失败: {str(e)}")
            # 使用默认停用词作为fallback
            self._stop_words = self._get_default_stop_words()
    
    async def _load_entity_patterns(self):
        """加载实体识别模式"""
        try:
            # 尝试从缓存获取
            if self.cache_service:
                cached_patterns = await self.cache_service.get(
                    "entity_patterns", namespace=self.cache_namespace
                )
                if cached_patterns:
                    self._entity_patterns = cached_patterns
                    logger.debug("从缓存加载实体模式")
                    return
            
            # 从数据库加载
            patterns = EntityPattern.get_active_patterns()
            self._entity_patterns = patterns
            
            # 如果数据库为空，使用默认模式
            if not patterns:
                self._entity_patterns = self._get_default_entity_patterns()
                logger.warning("数据库中无实体模式，使用默认模式")
            
            # 缓存数据
            if self.cache_service:
                await self.cache_service.set(
                    "entity_patterns",
                    self._entity_patterns,
                    ttl=self.cache_ttl,
                    namespace=self.cache_namespace
                )
            
            logger.info(f"加载实体模式完成: {len(self._entity_patterns)}个")
            
        except Exception as e:
            logger.error(f"加载实体模式失败: {str(e)}")
            # 使用默认模式作为fallback
            self._entity_patterns = self._get_default_entity_patterns()
    
    def get_synonym_dict(self) -> Dict[str, str]:
        """获取同义词字典 (同义词 -> 标准词)"""
        return self._synonym_dict.copy()
    
    def get_reverse_synonym_dict(self) -> Dict[str, List[str]]:
        """获取反向同义词字典 (标准词 -> 同义词列表)"""
        return dict(self._reverse_synonym_dict)
    
    def get_stop_words(self) -> Set[str]:
        """获取停用词集合"""
        return self._stop_words.copy()
    
    def get_entity_patterns(self) -> Dict[str, str]:
        """获取实体模式字典"""
        return self._entity_patterns.copy()
    
    def replace_synonyms(self, text: str) -> str:
        """替换文本中的同义词"""
        result = text
        for synonym, standard in self._synonym_dict.items():
            result = result.replace(synonym, standard)
        return result
    
    def get_standard_term(self, term: str) -> str:
        """获取词汇的标准形式"""
        return self._synonym_dict.get(term, term)
    
    def get_synonyms(self, standard_term: str) -> List[str]:
        """获取标准词的所有同义词"""
        return self._reverse_synonym_dict.get(standard_term, [])
    
    def is_stop_word(self, word: str) -> bool:
        """判断是否为停用词"""
        return word in self._stop_words
    
    async def add_synonym_group(
        self, 
        group_name: str, 
        standard_term: str, 
        synonyms: List[str],
        category: str = None,
        description: str = None
    ) -> bool:
        """添加同义词组"""
        try:
            # 创建同义词组
            group = SynonymGroup.create(
                group_name=group_name,
                standard_term=standard_term,
                category=category,
                description=description,
                created_by='system'
            )
            
            # 添加同义词条
            for synonym in synonyms:
                SynonymTerm.create(
                    group=group,
                    term=synonym,
                    created_by='system'
                )
            
            # 清除缓存
            if self.cache_service:
                await self.cache_service.delete("synonym_dict", namespace=self.cache_namespace)
            
            # 重新加载
            await self._load_synonyms()
            
            logger.info(f"添加同义词组成功: {group_name}")
            return True
            
        except Exception as e:
            logger.error(f"添加同义词组失败: {str(e)}")
            return False
    
    async def update_synonym_usage(self, synonym: str):
        """更新同义词使用统计"""
        try:
            term = SynonymTerm.get(SynonymTerm.term == synonym)
            term.increment_usage()
        except SynonymTerm.DoesNotExist:
            pass
        except Exception as e:
            logger.error(f"更新同义词使用统计失败: {str(e)}")
    
    def _get_default_synonyms(self) -> Dict[str, str]:
        """获取默认同义词词典（fallback）"""
        return {
            "怎样": "如何",
            "怎么": "如何", 
            "如何才能": "如何",
            "怎么样": "如何",
            "查看": "查询",
            "搜索": "查询",
            "寻找": "查询",
            "找到": "查询",
            "获取": "查询",
            "买": "购买",
            "购入": "购买",
            "采购": "购买",
            "订购": "购买",
            "账号": "账户",
            "帐户": "账户",
            "用户": "账户",
            "个人": "账户",
            "结余": "余额",
            "剩余": "余额",
            "可用金额": "余额",
            "储蓄卡": "银行卡",
            "借记卡": "银行卡",
            "信用卡": "银行卡",
            "卡片": "银行卡",
            "飞机票": "机票",
            "航班": "机票",
            "班机": "机票",
            "机位": "机票",
            "预约": "预订",
            "订购": "预订",
            "预定": "预订",
            "订票": "预订",
            "撤销": "取消",
            "退订": "取消",
            "作废": "取消",
            "终止": "取消",
            "更改": "修改",
            "变更": "修改",
            "调整": "修改",
            "编辑": "修改",
            "故障": "问题",
            "错误": "问题",
            "异常": "问题",
            "困难": "问题",
            "协助": "帮助",
            "支持": "帮助",
            "指导": "帮助",
            "援助": "帮助"
        }
    
    def _build_reverse_dict(self, synonym_dict: Dict[str, str]) -> Dict[str, List[str]]:
        """构建反向同义词字典"""
        reverse_dict = defaultdict(list)
        for synonym, standard in synonym_dict.items():
            reverse_dict[standard].append(synonym)
        return reverse_dict
    
    def _get_default_stop_words(self) -> Set[str]:
        """获取默认停用词集合（fallback）"""
        return {
            "的", "了", "在", "是", "有", "和", "就", "不", "人", "都", "一", "个", "上", "也", "很", "到", "说", "要", "去", "你", "会", "着", "没有", "看", "好", "自己", "这", "那", "些", "什么", "怎么", "为什么", "吗", "呢", "吧", "啊", "哦", "哪", "那么", "这么", "可以", "能够", "应该", "需要", "想要", "希望", "帮助", "告诉", "知道", "了解", "明白", "清楚"
        }
    
    def _get_default_entity_patterns(self) -> Dict[str, str]:
        """获取默认实体模式（fallback）"""
        return {
            "phone": r"1[3-9]\d{9}",
            "email": r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}",
            "id_card": r"\d{15}|\d{18}",
            "bank_card": r"\d{16,19}",
            "amount": r"[0-9,]+(?:\.[0-9]+)?(?:元|块|万|千|百)?",
            "date": r"\d{4}[-/年]\d{1,2}[-/月]\d{1,2}[日号]?",
            "time": r"\d{1,2}[:|：]\d{1,2}",
            "flight": r"[A-Z]{2}\d{3,4}",
            "airport": r"[A-Z]{3}",
            "city": r"[北京|上海|广州|深圳|杭州|南京|武汉|成都|西安|重庆|天津|青岛|大连|厦门|苏州|无锡|宁波|长沙|郑州|济南|哈尔滨|沈阳|长春|石家庄|太原|呼和浩特|兰州|西宁|银川|乌鲁木齐|拉萨|昆明|贵阳|南宁|海口|三亚|福州|南昌|合肥]+"
        }


# 全局单例服务
_synonym_service: Optional[SynonymService] = None


async def get_synonym_service(cache_service: Optional[CacheService] = None) -> SynonymService:
    """获取同义词服务单例"""
    global _synonym_service
    
    if _synonym_service is None:
        _synonym_service = SynonymService(cache_service)
        await _synonym_service.initialize()
    
    return _synonym_service


def get_synonym_service_sync() -> Optional[SynonymService]:
    """获取已初始化的同义词服务（同步方法）"""
    return _synonym_service