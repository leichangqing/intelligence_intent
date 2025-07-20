"""
对话相关数据模型
"""
from peewee import *
from .base import CommonModel
import json
from datetime import datetime, timedelta


class Session(CommonModel):
    """会话记录表"""
    
    session_id = CharField(max_length=100, unique=True, verbose_name="会话ID")
    user_id = CharField(max_length=100, verbose_name="用户ID")
    current_intent = CharField(max_length=100, null=True, verbose_name="当前意图")
    session_state = CharField(max_length=20, default='active', verbose_name="会话状态")  # active, completed, expired
    context = TextField(null=True, verbose_name="会话上下文JSON")
    expires_at = DateTimeField(null=True, verbose_name="过期时间")
    
    class Meta:
        table_name = 'sessions'
        indexes = (
            (('session_id',), False),
            (('user_id',), False),
            (('session_state',), False),
            (('expires_at',), False),
        )
    
    def get_context(self) -> dict:
        """获取会话上下文"""
        if self.context:
            try:
                return json.loads(self.context)
            except json.JSONDecodeError:
                return {}
        return {}
    
    def set_context(self, context: dict):
        """设置会话上下文"""
        self.context = json.dumps(context, ensure_ascii=False)
    
    def update_context(self, key: str, value: any):
        """更新上下文中的特定键值"""
        ctx = self.get_context()
        ctx[key] = value
        self.set_context(ctx)
    
    def is_expired(self) -> bool:
        """检查会话是否过期"""
        if self.expires_at:
            return datetime.now() > self.expires_at
        return False
    
    def extend_expiry(self, hours: int = 24):
        """延长会话过期时间"""
        self.expires_at = datetime.now() + timedelta(hours=hours)
    
    def is_active(self) -> bool:
        """检查会话是否活跃"""
        return self.session_state == 'active' and not self.is_expired()
    
    def complete(self):
        """完成会话"""
        self.session_state = 'completed'
    
    def expire(self):
        """使会话过期"""
        self.session_state = 'expired'
    
    def __str__(self):
        return f"Session({self.session_id}: {self.user_id})"


class Conversation(CommonModel):
    """对话历史表"""
    
    session_id = CharField(max_length=100, verbose_name="会话ID")
    user_id = CharField(max_length=100, verbose_name="用户ID")
    user_input = TextField(verbose_name="用户输入")
    intent_recognized = CharField(max_length=100, null=True, verbose_name="识别的意图")
    confidence_score = DecimalField(max_digits=5, decimal_places=4, null=True, verbose_name="置信度分数")
    slots_filled = TextField(null=True, verbose_name="已填充的槽位JSON")
    system_response = TextField(null=True, verbose_name="系统响应")
    response_type = CharField(max_length=50, null=True, verbose_name="响应类型")
    status = CharField(max_length=30, null=True, verbose_name="处理状态")
    processing_time_ms = IntegerField(null=True, verbose_name="处理时间毫秒")
    
    class Meta:
        table_name = 'conversations'
        indexes = (
            (('session_id', 'created_at'), False),
            (('user_id',), False),
            (('intent_recognized',), False),
            (('response_type',), False),
            (('status',), False),
        )
    
    def get_slots_filled(self) -> dict:
        """获取已填充的槽位"""
        if self.slots_filled:
            try:
                return json.loads(self.slots_filled)
            except json.JSONDecodeError:
                return {}
        return {}
    
    def set_slots_filled(self, slots: dict):
        """设置已填充的槽位"""
        self.slots_filled = json.dumps(slots, ensure_ascii=False)
    
    def get_context_snapshot(self) -> dict:
        """获取上下文快照"""
        if self.context_snapshot:
            try:
                return json.loads(self.context_snapshot)
            except json.JSONDecodeError:
                return {}
        return {}
    
    def set_context_snapshot(self, context: dict):
        """设置上下文快照"""
        self.context_snapshot = json.dumps(context, ensure_ascii=False)
    
    def is_successful(self) -> bool:
        """判断是否处理成功"""
        return self.status in ['completed', 'api_result']
    
    def is_incomplete(self) -> bool:
        """判断是否需要更多信息"""
        return self.status == 'incomplete'
    
    def is_ambiguous(self) -> bool:
        """判断是否存在歧义"""
        return self.status == 'ambiguous'
    
    def set_processing_time(self, start_time: datetime):
        """设置处理时间"""
        processing_time = (datetime.now() - start_time).total_seconds() * 1000
        self.processing_time_ms = int(processing_time)
    
    def is_fast_response(self, threshold_ms: int = 2000) -> bool:
        """判断是否为快速响应"""
        return self.processing_time_ms and self.processing_time_ms < threshold_ms
    
    def __str__(self):
        return f"Conversation({self.session_id}: {self.user_input[:50]}...)"


class IntentAmbiguity(CommonModel):
    """意图歧义处理表"""
    
    conversation = ForeignKeyField(Conversation, backref='ambiguities', on_delete='CASCADE', verbose_name="对话记录")
    candidate_intents = TextField(verbose_name="候选意图列表JSON")
    disambiguation_question = TextField(verbose_name="歧义消除问题")
    disambiguation_options = TextField(null=True, verbose_name="选择选项JSON")
    user_choice = CharField(max_length=100, null=True, verbose_name="用户选择的意图")
    resolution_method = CharField(max_length=50, null=True, verbose_name="解决方法")  # user_choice, system_auto, context_based
    resolved_at = DateTimeField(null=True, verbose_name="解决时间")
    
    class Meta:
        table_name = 'intent_ambiguities'
        indexes = (
            (('conversation',), False),
            (('resolved_at',), False),
            (('resolution_method',), False),
        )
    
    def get_candidate_intents(self) -> list:
        """获取候选意图列表"""
        if self.candidate_intents:
            try:
                return json.loads(self.candidate_intents)
            except json.JSONDecodeError:
                return []
        return []
    
    def set_candidate_intents(self, candidates: list):
        """设置候选意图列表"""
        self.candidate_intents = json.dumps(candidates, ensure_ascii=False)
    
    def get_disambiguation_options(self) -> list:
        """获取歧义消除选项"""
        if self.disambiguation_options:
            try:
                return json.loads(self.disambiguation_options)
            except json.JSONDecodeError:
                return []
        return []
    
    def set_disambiguation_options(self, options: list):
        """设置歧义消除选项"""
        self.disambiguation_options = json.dumps(options, ensure_ascii=False)
    
    def is_resolved(self) -> bool:
        """判断歧义是否已解决"""
        return self.resolved_at is not None
    
    def resolve_with_choice(self, choice: str):
        """通过用户选择解决歧义"""
        self.user_choice = choice
        self.resolution_method = 'user_choice'
        self.resolved_at = datetime.now()
    
    def resolve_automatically(self, choice: str):
        """自动解决歧义"""
        self.user_choice = choice
        self.resolution_method = 'system_auto'
        self.resolved_at = datetime.now()
    
    def __str__(self):
        return f"Ambiguity({self.conversation.id}: {len(self.get_candidate_intents())} candidates)"


class IntentTransfer(CommonModel):
    """意图转移记录表"""
    
    session_id = CharField(max_length=100, verbose_name="会话ID")
    user_id = CharField(max_length=100, verbose_name="用户ID")
    from_intent = CharField(max_length=100, null=True, verbose_name="源意图")
    to_intent = CharField(max_length=100, verbose_name="目标意图")
    transfer_type = CharField(max_length=50, verbose_name="转移类型")  # interruption, explicit_change, system_suggestion
    saved_context = TextField(null=True, verbose_name="保存的上下文JSON")
    transfer_reason = TextField(null=True, verbose_name="转移原因")
    confidence_score = DecimalField(max_digits=5, decimal_places=4, null=True, verbose_name="转移置信度")
    resumed_at = DateTimeField(null=True, verbose_name="恢复时间")
    
    class Meta:
        table_name = 'intent_transfers'
        indexes = (
            (('session_id', 'created_at'), False),
            (('user_id',), False),
            (('transfer_type',), False),
            (('from_intent', 'to_intent'), False),
        )
    
    def get_saved_context(self) -> dict:
        """获取保存的上下文"""
        if self.saved_context:
            try:
                return json.loads(self.saved_context)
            except json.JSONDecodeError:
                return {}
        return {}
    
    def set_saved_context(self, context: dict):
        """设置保存的上下文"""
        self.saved_context = json.dumps(context, ensure_ascii=False)
    
    def is_interruption(self) -> bool:
        """判断是否为中断类型转移"""
        return self.transfer_type == 'interruption'
    
    def is_explicit_change(self) -> bool:
        """判断是否为明确的意图改变"""
        return self.transfer_type == 'explicit_change'
    
    def can_resume(self) -> bool:
        """判断是否可以恢复原意图"""
        return self.is_interruption() and self.resumed_at is None
    
    def resume(self):
        """恢复到原意图"""
        if self.can_resume():
            self.resumed_at = datetime.now()
    
    def __str__(self):
        return f"Transfer({self.from_intent} -> {self.to_intent})"


class UserContext(CommonModel):
    """用户上下文表"""
    
    user_id = CharField(max_length=100, verbose_name="用户ID")
    context_type = CharField(max_length=50, verbose_name="上下文类型")  # preferences, history, temporary, session
    context_key = CharField(max_length=100, verbose_name="上下文键")
    context_value = TextField(verbose_name="上下文值JSON")
    expires_at = DateTimeField(null=True, verbose_name="过期时间")
    
    class Meta:
        table_name = 'user_contexts'
        indexes = (
            (('user_id', 'context_type', 'context_key'), True),  # 联合唯一索引
            (('user_id', 'context_type'), False),
            (('expires_at',), False),
        )
    
    def get_context_value(self) -> any:
        """获取上下文值"""
        if self.context_value:
            try:
                return json.loads(self.context_value)
            except json.JSONDecodeError:
                return self.context_value
        return None
    
    def set_context_value(self, value: any):
        """设置上下文值"""
        if isinstance(value, (dict, list)):
            self.context_value = json.dumps(value, ensure_ascii=False)
        else:
            self.context_value = str(value)
    
    def is_expired(self) -> bool:
        """检查是否过期"""
        if self.expires_at:
            return datetime.now() > self.expires_at
        return False
    
    def is_preference(self) -> bool:
        """判断是否为用户偏好"""
        return self.context_type == 'preferences'
    
    def is_temporary(self) -> bool:
        """判断是否为临时上下文"""
        return self.context_type == 'temporary'
    
    def __str__(self):
        return f"UserContext({self.user_id}.{self.context_key})"