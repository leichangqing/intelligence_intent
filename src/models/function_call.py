"""
功能调用相关数据模型
"""
from peewee import *
from .base import CommonModel
from .intent import Intent
from .conversation import Conversation
import json
from datetime import datetime


class FunctionCall(CommonModel):
    """功能调用配置表"""
    
    intent = ForeignKeyField(Intent, backref='function_calls', on_delete='CASCADE', verbose_name="关联意图")
    function_name = CharField(max_length=100, verbose_name="函数名称")
    api_endpoint = CharField(max_length=500, verbose_name="API端点")
    http_method = CharField(max_length=10, default='POST', verbose_name="HTTP方法")
    headers = TextField(null=True, verbose_name="请求头JSON")
    param_mapping = TextField(null=True, verbose_name="参数映射配置JSON")
    retry_times = IntegerField(default=3, verbose_name="重试次数")
    timeout_seconds = IntegerField(default=30, verbose_name="超时时间")
    success_template = TextField(null=True, verbose_name="成功响应模板")
    error_template = TextField(null=True, verbose_name="错误响应模板")
    is_active = BooleanField(default=True, verbose_name="是否激活")
    
    class Meta:
        table_name = 'function_calls'
        indexes = (
            (('intent', 'function_name'), True),  # 联合唯一索引
            (('function_name',), False),
            (('is_active',), False),
        )
    
    def get_headers(self) -> dict:
        """获取请求头字典"""
        if self.headers:
            try:
                return json.loads(self.headers)
            except json.JSONDecodeError:
                return {}
        return {}
    
    def set_headers(self, headers: dict):
        """设置请求头"""
        self.headers = json.dumps(headers, ensure_ascii=False)
    
    def get_param_mapping(self) -> dict:
        """获取参数映射配置"""
        if self.param_mapping:
            try:
                return json.loads(self.param_mapping)
            except json.JSONDecodeError:
                return {}
        return {}
    
    def set_param_mapping(self, mapping: dict):
        """设置参数映射配置"""
        self.param_mapping = json.dumps(mapping, ensure_ascii=False)
    
    def map_slots_to_params(self, slots: dict) -> dict:
        """将槽位映射为API参数"""
        # 根据param_mapping配置将槽位值映射为API调用参数
        mapping = self.get_param_mapping()
        params = {}
        
        for slot_name, slot_value in slots.items():
            # 查找映射配置
            if slot_name in mapping:
                param_name = mapping[slot_name]
                if isinstance(param_name, str):
                    params[param_name] = slot_value
                elif isinstance(param_name, dict):
                    # 支持复杂映射，如类型转换、默认值等
                    target_param = param_name.get('param_name', slot_name)
                    transform = param_name.get('transform')
                    
                    if transform == 'int':
                        try:
                            params[target_param] = int(slot_value)
                        except (ValueError, TypeError):
                            params[target_param] = slot_value
                    elif transform == 'float':
                        try:
                            params[target_param] = float(slot_value)
                        except (ValueError, TypeError):
                            params[target_param] = slot_value
                    else:
                        params[target_param] = slot_value
            else:
                # 没有映射配置时直接使用槽位名作为参数名
                params[slot_name] = slot_value
        
        return params
    
    def is_post_method(self) -> bool:
        """判断是否为POST方法"""
        return self.http_method.upper() == 'POST'
    
    def is_get_method(self) -> bool:
        """判断是否为GET方法"""
        return self.http_method.upper() == 'GET'
    
    def __str__(self):
        return f"FunctionCall({self.intent.intent_name}.{self.function_name})"


class ApiCallLog(CommonModel):
    """API调用日志表"""
    
    id = BigAutoField(primary_key=True)  # 显式定义BIGINT主键
    conversation_id = BigIntegerField(verbose_name="对话记录ID")
    function_call = ForeignKeyField(FunctionCall, backref='call_logs', on_delete='SET NULL', null=True, verbose_name="功能调用配置")
    function_name = CharField(max_length=100, verbose_name="函数名称")
    api_endpoint = CharField(max_length=500, verbose_name="API端点")
    request_params = TextField(null=True, verbose_name="请求参数JSON")
    request_headers = TextField(null=True, verbose_name="请求头JSON")
    response_data = TextField(null=True, verbose_name="响应数据JSON")
    status_code = IntegerField(null=True, verbose_name="HTTP状态码")
    response_time_ms = IntegerField(null=True, verbose_name="响应时间毫秒")
    error_message = TextField(null=True, verbose_name="错误信息")
    retry_count = IntegerField(default=0, verbose_name="重试次数")
    success = BooleanField(null=True, verbose_name="是否成功")
    
    class Meta:
        table_name = 'api_call_logs'
        indexes = (
            (('conversation_id',), False),
            (('function_name',), False),
            (('success',), False),
            (('status_code',), False),
            (('created_at',), False),
        )
    
    def get_request_params(self) -> dict:
        """获取请求参数"""
        if self.request_params:
            try:
                return json.loads(self.request_params)
            except json.JSONDecodeError:
                return {}
        return {}
    
    def set_request_params(self, params: dict):
        """设置请求参数"""
        self.request_params = json.dumps(params, ensure_ascii=False)
    
    def get_request_headers(self) -> dict:
        """获取请求头"""
        if self.request_headers:
            try:
                return json.loads(self.request_headers)
            except json.JSONDecodeError:
                return {}
        return {}
    
    def set_request_headers(self, headers: dict):
        """设置请求头"""
        self.request_headers = json.dumps(headers, ensure_ascii=False)
    
    def get_response_data(self) -> dict:
        """获取响应数据"""
        if self.response_data:
            try:
                return json.loads(self.response_data)
            except json.JSONDecodeError:
                return {}
        return {}
    
    def set_response_data(self, data: dict):
        """设置响应数据"""
        self.response_data = json.dumps(data, ensure_ascii=False)
    
    def mark_success(self, status_code: int, response_data: dict, response_time_ms: int):
        """标记调用成功"""
        self.success = True
        self.status_code = status_code
        self.set_response_data(response_data)
        self.response_time_ms = response_time_ms
        self.error_message = None
    
    def mark_failure(self, error_message: str, status_code: int = None):
        """标记调用失败"""
        self.success = False
        self.error_message = error_message
        if status_code:
            self.status_code = status_code
    
    def increment_retry(self):
        """增加重试次数"""
        self.retry_count += 1
    
    def is_successful(self) -> bool:
        """判断是否调用成功"""
        return self.success is True
    
    def is_timeout(self) -> bool:
        """判断是否超时"""
        return "timeout" in (self.error_message or "").lower()
    
    def is_fast_response(self, threshold_ms: int = 1000) -> bool:
        """判断是否为快速响应"""
        return self.response_time_ms and self.response_time_ms < threshold_ms
    
    def __str__(self):
        return f"ApiCallLog({self.function_name}: {self.status_code})"


class AsyncTask(CommonModel):
    """异步任务管理表"""
    
    id = BigAutoField(primary_key=True)  # 显式定义BIGINT主键
    task_id = CharField(max_length=100, unique=True, verbose_name="任务ID")
    task_type = CharField(max_length=50, verbose_name="任务类型")  # api_call, batch_process, data_export
    status = CharField(max_length=20, default='pending', verbose_name="任务状态")  # pending, processing, completed, failed, cancelled
    conversation_id = BigIntegerField(null=True, verbose_name="关联对话ID")
    user_id = CharField(max_length=100, verbose_name="用户ID")
    request_data = TextField(null=True, verbose_name="请求数据JSON")
    result_data = TextField(null=True, verbose_name="结果数据JSON")
    error_message = TextField(null=True, verbose_name="错误信息")
    progress = DecimalField(max_digits=5, decimal_places=2, default=0.00, verbose_name="进度百分比")
    estimated_completion = DateTimeField(null=True, verbose_name="预计完成时间")
    completed_at = DateTimeField(null=True, verbose_name="实际完成时间")
    
    class Meta:
        table_name = 'async_tasks'
        indexes = (
            (('task_id',), False),
            (('status',), False),
            (('user_id',), False),
            (('conversation_id',), False),
            (('task_type',), False),
            (('created_at',), False),
        )
    
    def get_request_data(self) -> dict:
        """获取请求数据"""
        if self.request_data:
            try:
                return json.loads(self.request_data)
            except json.JSONDecodeError:
                return {}
        return {}
    
    def set_request_data(self, data: dict):
        """设置请求数据"""
        self.request_data = json.dumps(data, ensure_ascii=False)
    
    def get_result_data(self) -> dict:
        """获取结果数据"""
        if self.result_data:
            try:
                return json.loads(self.result_data)
            except json.JSONDecodeError:
                return {}
        return {}
    
    def set_result_data(self, data: dict):
        """设置结果数据"""
        self.result_data = json.dumps(data, ensure_ascii=False)
    
    def start_processing(self):
        """开始处理任务"""
        self.status = 'processing'
        self.progress = 0.0
    
    def update_progress(self, progress: float):
        """更新进度"""
        if 0.0 <= progress <= 100.0:
            self.progress = progress
    
    def complete_successfully(self, result_data: dict):
        """成功完成任务"""
        self.status = 'completed'
        self.progress = 100.0
        self.set_result_data(result_data)
        self.completed_at = datetime.now()
        self.error_message = None
    
    def fail_with_error(self, error_message: str):
        """任务失败"""
        self.status = 'failed'
        self.error_message = error_message
        self.completed_at = datetime.now()
    
    def cancel(self):
        """取消任务"""
        self.status = 'cancelled'
        self.completed_at = datetime.now()
    
    def is_pending(self) -> bool:
        """判断是否待处理"""
        return self.status == 'pending'
    
    def is_processing(self) -> bool:
        """判断是否处理中"""
        return self.status == 'processing'
    
    def is_completed(self) -> bool:
        """判断是否已完成"""
        return self.status in ['completed', 'failed', 'cancelled']
    
    def is_successful(self) -> bool:
        """判断是否成功完成"""
        return self.status == 'completed'
    
    def __str__(self):
        return f"AsyncTask({self.task_id}: {self.status})"