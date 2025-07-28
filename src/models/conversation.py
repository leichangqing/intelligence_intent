"""
对话相关数据模型
"""
from peewee import *
from playhouse.mysql_ext import JSONField
from .base import CommonModel
from datetime import datetime, timedelta


class User(CommonModel):
    """用户表 - 与MySQL Schema对应"""
    user_id = CharField(max_length=100, unique=True, verbose_name="用户ID")
    user_type = CharField(max_length=20, default='individual', verbose_name="用户类型", 
                         constraints=[Check("user_type IN ('individual', 'enterprise', 'admin', 'system')")])
    username = CharField(max_length=100, null=True, verbose_name="用户名")
    email = CharField(max_length=255, null=True, verbose_name="邮箱")
    phone = CharField(max_length=20, null=True, verbose_name="电话")
    display_name = CharField(max_length=200, null=True, verbose_name="显示名称")
    avatar_url = CharField(max_length=500, null=True, verbose_name="头像URL")
    status = CharField(max_length=20, default='active', verbose_name="状态",
                      constraints=[Check("status IN ('active', 'inactive', 'suspended', 'deleted')")])
    preferences = JSONField(null=True, verbose_name="用户偏好设置")
    metadata = JSONField(null=True, verbose_name="用户元数据")
    last_login_at = DateTimeField(null=True, verbose_name="最后登录时间")
    
    class Meta:
        table_name = 'users'
        indexes = (
            (('username',), False),
            (('email',), False),
            (('user_type',), False),
            (('status',), False),
        )


class Session(CommonModel):
    """会话记录表 - 与MySQL Schema对应"""
    
    session_id = CharField(max_length=100, unique=True, verbose_name="会话ID")
    user_id = CharField(max_length=100, verbose_name="用户ID")  # 与数据库schema匹配
    current_intent = CharField(max_length=100, null=True, verbose_name="当前意图")  # 与数据库字段匹配
    session_state = CharField(max_length=20, default='active', verbose_name="会话状态")  # active, completed, expired, error
    context = JSONField(null=True, verbose_name="会话上下文")
    metadata = JSONField(null=True, verbose_name="元数据")
    expires_at = DateTimeField(null=True, verbose_name="过期时间")
    
    class Meta:
        table_name = 'sessions'
        indexes = (
            (('session_id',), False),
            (('user_id',), False),
            (('session_state',), False),
            (('expires_at',), False),
            (('current_intent',), False),
        )
    
    def get_context(self) -> dict:
        """获取会话上下文"""
        if self.context:
            return self.context if isinstance(self.context, dict) else {}
        return {}
    
    def set_context(self, context: dict):
        """设置会话上下文"""
        self.context = context
    
    def update_context(self, key: str, value: any):
        """更新上下文中的特定键值"""
        ctx = self.get_context()
        ctx[key] = value
        self.set_context(ctx)
    
    def get_metadata(self) -> dict:
        """获取元数据"""
        if self.metadata:
            return self.metadata if isinstance(self.metadata, dict) else {}
        return {}
    
    def set_metadata(self, metadata: dict):
        """设置元数据"""
        self.metadata = metadata
    
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
    """对话历史表 - 与MySQL Schema对应"""
    
    id = BigAutoField(primary_key=True)  # 显式定义BIGINT主键
    session_id = CharField(max_length=100, verbose_name="会话ID")  # 与数据库字段匹配
    user_id = CharField(max_length=100, verbose_name="用户ID")  # 与数据库字段匹配
    user_input = TextField(verbose_name="用户输入")
    intent_recognized = CharField(max_length=100, null=True, verbose_name="识别的意图")  # 与数据库字段匹配
    confidence_score = DecimalField(max_digits=5, decimal_places=4, null=True, verbose_name="置信度分数")
    system_response = TextField(null=True, verbose_name="系统响应")
    response_type = CharField(max_length=50, null=True, verbose_name="响应类型")
    status = CharField(max_length=50, null=True, verbose_name="处理状态")
    processing_time_ms = IntegerField(null=True, verbose_name="处理时间毫秒")
    error_message = TextField(null=True, verbose_name="错误信息")
    metadata = JSONField(null=True, verbose_name="元数据")
    
    class Meta:
        table_name = 'conversations'
        indexes = (
            (('session_id',), False),
            (('user_id',), False),
            (('intent_recognized',), False),
            (('status',), False),
            (('created_at',), False),
        )
    
    def get_slots_filled(self) -> dict:
        """
        v2.2改进: 从 slot_values 表动态获取已填充的槽位
        此方法现在需要查询相关的 slot_values 记录
        """
        try:
            from src.models.slot_value import SlotValue
            from src.models.slot import Slot
            
            # 直接使用数据库查询，避免异步调用
            slot_values = list(
                SlotValue.select(SlotValue, Slot)
                .join(Slot)
                .where(
                    (SlotValue.conversation == self.id) &
                    (SlotValue.validation_status.in_(['valid', 'pending']))
                )
            )
            
            result = {}
            for slot_value in slot_values:
                final_value = slot_value.normalized_value or slot_value.extracted_value
                if final_value:
                    result[slot_value.slot_name] = {
                        'value': final_value,
                        'confidence': float(slot_value.confidence) if slot_value.confidence else 0.0,
                        'extraction_method': slot_value.extraction_method or 'unknown',
                        'original_text': slot_value.original_text or ''
                    }
            
            return result
        except Exception:
            return {}
    
    def get_slots_missing(self) -> list:
        """
        v2.2改进: 从 slot_values 表动态获取缺失的槽位
        此方法现在需要基于意图定义和已填充槽位计算
        """
        from src.services.slot_value_service import get_slot_value_service
        from src.models.intent import Intent
        try:
            slot_value_service = get_slot_value_service()
            # 获取意图对象
            if self.intent_recognized:
                intent = Intent.get(Intent.intent_name == self.intent_recognized)
                import asyncio
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    # 获取槽位状态信息
                    status_info = loop.run_until_complete(
                        slot_value_service.get_conversation_slots_status(self, intent)
                    )
                    return status_info.get('missing_required_slots', [])
                finally:
                    loop.close()
        except Exception:
            return []
    
    def get_response_metadata(self) -> dict:
        """获取响应元数据"""
        if self.response_metadata:
            return self.response_metadata if isinstance(self.response_metadata, dict) else {}
        return {}
    
    def set_response_metadata(self, metadata: dict):
        """设置响应元数据"""
        self.response_metadata = metadata
    
    def get_context_snapshot(self) -> dict:
        """获取上下文快照 - 暂时未实现"""
        return {}
    
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
    
    @property
    def slots_filled(self) -> dict:
        """兼容性属性: 返回已填充的槽位"""
        return self.get_slots_filled()
    
    @property 
    def intent_name(self) -> str:
        """兼容性属性: 返回意图名称"""
        return self.intent_recognized
    
    @intent_name.setter
    def intent_name(self, value: str):
        """兼容性属性: 设置意图名称"""
        self.intent_recognized = value
    
    def __str__(self):
        return f"Conversation({self.session_id}: {self.user_input[:50]}...)"


class IntentAmbiguity(CommonModel):
    """意图歧义处理表 - 与MySQL Schema对应"""
    
    conversation = ForeignKeyField(Conversation, on_delete='CASCADE', verbose_name="对话记录")
    user_input = TextField(verbose_name="用户输入")
    candidate_intents = JSONField(verbose_name="候选意图列表")
    disambiguation_question = TextField(null=True, verbose_name="消歧问题")
    disambiguation_options = JSONField(null=True, verbose_name="消歧选项")
    user_choice = IntegerField(null=True, verbose_name="用户选择")
    resolution_method = CharField(max_length=20, null=True, verbose_name="解决方法")  # user_choice, auto_resolve, fallback, escalate
    resolved_intent_id = IntegerField(null=True, verbose_name="最终确定的意图ID")
    resolved_at = DateTimeField(null=True, verbose_name="解决时间")
    resolved = BooleanField(default=False, verbose_name="是否已解决")
    
    class Meta:
        table_name = 'intent_ambiguities'
        indexes = (
            (('conversation',), False),
            (('resolved', 'created_at'), False),
            (('resolution_method',), False),
        )
    
    def get_candidate_intents(self) -> list:
        """获取候选意图列表"""
        if self.candidate_intents:
            return self.candidate_intents if isinstance(self.candidate_intents, list) else []
        return []
    
    def set_candidate_intents(self, candidates: list):
        """设置候选意图列表"""
        self.candidate_intents = candidates
    
    def get_disambiguation_options(self) -> list:
        """获取歧义消除选项"""
        if self.disambiguation_options:
            return self.disambiguation_options if isinstance(self.disambiguation_options, list) else []
        return []
    
    def set_disambiguation_options(self, options: list):
        """设置歧义消除选项"""
        self.disambiguation_options = options
    
    def is_resolved(self) -> bool:
        """判断歧义是否已解决"""
        return self.resolved
    
    def resolve_with_choice(self, choice: str):
        """通过用户选择解决歧义"""
        self.user_choice = choice
        self.resolution_method = 'user_choice'
        self.resolved_at = datetime.now()
        self.resolved = True
    
    def resolve_automatically(self, choice: str):
        """自动解决歧义"""
        self.user_choice = choice
        self.resolution_method = 'auto_resolve'
        self.resolved_at = datetime.now()
        self.resolved = True
    
    def __str__(self):
        return f"Ambiguity({self.conversation.id}: {len(self.get_candidate_intents())} candidates)"


class IntentTransfer(CommonModel):
    """意图转移记录表 - 与MySQL Schema对应"""
    
    session = ForeignKeyField(Session, field='session_id', column_name='session_id', on_delete='CASCADE', verbose_name="会话ID")
    conversation = ForeignKeyField(Conversation, null=True, on_delete='SET NULL', verbose_name="对话ID")
    user_id = ForeignKeyField(User, field='user_id', on_delete='CASCADE', verbose_name="用户ID")
    from_intent_id = IntegerField(null=True, verbose_name="源意图ID")
    from_intent_name = CharField(max_length=100, null=True, verbose_name="源意图名称")
    to_intent_id = IntegerField(null=True, verbose_name="目标意图ID")
    to_intent_name = CharField(max_length=100, null=True, verbose_name="目标意图名称")
    transfer_type = CharField(max_length=20, verbose_name="转移类型")  # user_request, system_redirect, fallback, escalation, completion
    transfer_reason = TextField(null=True, verbose_name="转移原因")
    saved_context = JSONField(null=True, verbose_name="保存的上下文")
    transfer_confidence = DecimalField(max_digits=5, decimal_places=4, null=True, verbose_name="转移置信度")
    is_successful = BooleanField(default=True, verbose_name="是否成功")
    resumed_at = DateTimeField(null=True, verbose_name="恢复时间")
    
    class Meta:
        table_name = 'intent_transfers'
        indexes = (
            (('session', 'created_at'), False),
            (('user_id', 'transfer_type'), False),
            (('from_intent_id', 'to_intent_id'), False),
            (('transfer_type',), False),
        )
    
    def get_saved_context(self) -> dict:
        """获取保存的上下文"""
        if self.saved_context:
            return self.saved_context if isinstance(self.saved_context, dict) else {}
        return {}
    
    def set_saved_context(self, context: dict):
        """设置保存的上下文"""
        self.saved_context = context
    
    def is_interruption(self) -> bool:
        """判断是否为中断类型转移"""
        return self.transfer_type == 'user_request'
    
    def is_explicit_change(self) -> bool:
        """判断是否为明确的意图改变"""
        return self.transfer_type == 'system_redirect'
    
    def can_resume(self) -> bool:
        """判断是否可以恢复原意图"""
        return self.is_interruption() and self.resumed_at is None
    
    def resume(self):
        """恢复到原意图"""
        if self.can_resume():
            self.resumed_at = datetime.now()
    
    def __str__(self):
        return f"Transfer({self.from_intent_name} -> {self.to_intent_name})"


class UserContext(CommonModel):
    """用户上下文表 - 与MySQL Schema对应"""
    
    user_id = ForeignKeyField(User, field='user_id', on_delete='CASCADE', verbose_name="用户ID")
    context_type = CharField(max_length=20, verbose_name="上下文类型")  # preference, history, profile, session, temporary
    context_key = CharField(max_length=100, verbose_name="上下文键")
    context_value = JSONField(null=True, verbose_name="上下文值")
    scope = CharField(max_length=20, default='global', verbose_name="作用范围")  # global, session, conversation
    priority = IntegerField(default=1, verbose_name="优先级")
    expires_at = DateTimeField(null=True, verbose_name="过期时间")
    is_active = BooleanField(default=True, verbose_name="是否有效")
    
    class Meta:
        table_name = 'user_contexts'
        indexes = (
            (('user_id', 'context_type'), False),
            (('context_key',), False),
            (('expires_at',), False),
            (('scope', 'priority'), False),
            (('user_id', 'context_type', 'context_key'), True),  # 联合唯一索引
        )
    
    def get_context_value(self) -> any:
        """获取上下文值"""
        return self.context_value
    
    def set_context_value(self, value: any):
        """设置上下文值"""
        self.context_value = value
    
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