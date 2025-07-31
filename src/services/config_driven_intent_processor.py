"""
配置驱动的意图处理器
通过数据库配置实现意图执行，无需硬编码
"""
from typing import Dict, List, Any, Optional
from abc import ABC, abstractmethod
import json
import asyncio
import httpx
from datetime import datetime
import random
import time

from src.schemas.chat import ChatResponse, SessionMetadata
from src.models.intent import Intent
from src.utils.logger import get_logger

logger = get_logger(__name__)


class HandlerResult:
    """处理器执行结果"""
    
    def __init__(self, success: bool, data: Any = None, error: str = None):
        self.success = success
        self.data = data or {}
        self.error = error
    
    @classmethod
    def success_result(cls, data: Any = None) -> 'HandlerResult':
        return cls(True, data)
    
    @classmethod
    def failure_result(cls, error: str) -> 'HandlerResult':
        return cls(False, None, error)


class BaseIntentHandler(ABC):
    """意图处理器基类"""
    
    @abstractmethod
    async def execute(self, config: Dict, intent: Intent, slots: Dict, context: Dict) -> HandlerResult:
        """执行意图处理"""
        pass
    
    @abstractmethod
    def validate_config(self, config: Dict) -> bool:
        """验证配置有效性"""
        pass


class MockServiceHandler(BaseIntentHandler):
    """Mock服务处理器 - 模拟真实服务调用"""
    
    async def execute(self, config: Dict, intent: Intent, slots: Dict, context: Dict) -> HandlerResult:
        """执行Mock服务"""
        try:
            # 模拟延迟
            mock_delay = config.get('mock_delay', 1)
            await asyncio.sleep(mock_delay)
            
            # 模拟成功率
            success_rate = config.get('success_rate', 0.95)
            if random.random() > success_rate:
                return HandlerResult.failure_result("服务暂时不可用，请稍后重试")
            
            # 根据意图类型生成模拟数据
            service_name = config.get('service_name', 'unknown_service')
            
            if service_name == 'book_flight_service':
                return await self._mock_book_flight(slots, context)
            elif service_name == 'check_balance_service':
                return await self._mock_check_balance(slots, context)
            elif service_name == 'book_train_service':
                return await self._mock_book_train(slots, context)
            elif service_name == 'book_movie_service':
                return await self._mock_book_movie(slots, context)
            else:
                return HandlerResult.success_result({"message": f"Mock service {service_name} executed successfully"})
                
        except Exception as e:
            logger.error(f"Mock服务执行失败: {str(e)}")
            return HandlerResult.failure_result(f"处理失败: {str(e)}")
    
    async def _mock_book_flight(self, slots: Dict, context: Dict) -> HandlerResult:
        """模拟机票预订服务"""
        order_id = f"FL{int(time.time())}{random.randint(1000, 9999)}"
        
        result_data = {
            "order_id": order_id,
            "status": "confirmed",
            "departure_city": self._get_slot_value(slots, 'departure_city'),
            "arrival_city": self._get_slot_value(slots, 'arrival_city'),
            "departure_date": self._get_slot_value(slots, 'departure_date'),
            "passenger_count": self._get_slot_value(slots, 'passenger_count', '1'),
            "booking_time": datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
        
        # 如果是往返机票，添加返程信息
        if slots.get('return_date'):
            result_data["return_date"] = self._get_slot_value(slots, 'return_date')
        
        # 如果有trip_type信息，添加到结果中
        if slots.get('trip_type'):
            result_data["trip_type"] = self._get_slot_value(slots, 'trip_type')
        
        return HandlerResult.success_result(result_data)
    
    async def _mock_book_train(self, slots: Dict, context: Dict) -> HandlerResult:
        """模拟火车票预订服务"""
        order_id = f"TR{int(time.time())}{random.randint(1000, 9999)}"
        
        # 模拟火车车次
        train_numbers = ['G123', 'D456', 'K789', 'T321', 'Z654']
        train_number = random.choice(train_numbers)
        
        result_data = {
            "order_id": order_id,
            "train_number": train_number,
            "status": "confirmed",
            "departure_city": self._get_slot_value(slots, 'departure_city'),
            "arrival_city": self._get_slot_value(slots, 'arrival_city'),
            "departure_date": self._get_slot_value(slots, 'departure_date'),
            "passenger_count": self._get_slot_value(slots, 'passenger_count', '1'),
            "seat_type": self._get_slot_value(slots, 'seat_type', '硬座'),
            "booking_time": datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
        
        return HandlerResult.success_result(result_data)
    
    async def _mock_book_movie(self, slots: Dict, context: Dict) -> HandlerResult:
        """模拟电影票预订服务"""
        order_id = f"MV{int(time.time())}{random.randint(1000, 9999)}"
        
        # 模拟座位信息
        seat_rows = ['A', 'B', 'C', 'D', 'E', 'F']
        seat_numbers = list(range(1, 21))
        ticket_count = int(self._get_slot_value(slots, 'ticket_count', '1'))
        
        seat_info = []
        for i in range(ticket_count):
            row = random.choice(seat_rows)
            number = random.choice(seat_numbers)
            seat_info.append(f"{row}{number:02d}")
        
        result_data = {
            "order_id": order_id,
            "status": "confirmed",
            "movie_name": self._get_slot_value(slots, 'movie_name'),
            "cinema_name": self._get_slot_value(slots, 'cinema_name'),
            "show_time": self._get_slot_value(slots, 'show_time'),
            "ticket_count": self._get_slot_value(slots, 'ticket_count', '1'),
            "seat_preference": self._get_slot_value(slots, 'seat_preference', '无偏好'),
            "seat_info": ', '.join(seat_info),
            "booking_time": datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
        
        return HandlerResult.success_result(result_data)
    
    async def _mock_check_balance(self, slots: Dict, context: Dict) -> HandlerResult:
        """模拟余额查询服务"""
        account_type = self._get_slot_value(slots, 'account_type', '银行卡')
        
        # 模拟不同账户类型的余额
        balance_ranges = {
            '银行卡': (1000, 50000),
            '储蓄卡': (500, 30000), 
            '信用卡': (0, 20000),
            '支付宝': (100, 10000),
            '微信': (50, 5000)
        }
        
        balance_range = balance_ranges.get(account_type, (100, 10000))
        balance = random.randint(*balance_range)
        
        result_data = {
            "account_type": account_type,
            "balance": f"{balance:,.2f}",
            "currency": "CNY",
            "query_time": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            "account_status": "normal"
        }
        
        return HandlerResult.success_result(result_data)
    
    def _get_slot_value(self, slots: Dict, slot_name: str, default: str = '未知') -> str:
        """从槽位字典中获取值"""
        slot_data = slots.get(slot_name)
        if slot_data is None:
            return default
        if hasattr(slot_data, 'value'):
            return slot_data.value or default
        elif isinstance(slot_data, dict):
            return slot_data.get('value', default)
        else:
            return str(slot_data)
    
    def validate_config(self, config: Dict) -> bool:
        """验证Mock服务配置"""
        required_fields = ['service_name']
        return all(field in config for field in required_fields)


class APICallHandler(BaseIntentHandler):
    """API调用处理器"""
    
    async def execute(self, config: Dict, intent: Intent, slots: Dict, context: Dict) -> HandlerResult:
        """执行API调用"""
        try:
            endpoint = config['endpoint']
            method = config.get('method', 'POST')
            timeout = config.get('timeout', 30)
            headers = config.get('headers', {})
            
            # 渲染模板变量
            body = self._render_template(config.get('body_template', {}), slots, context)
            headers = self._render_template(headers, slots, context)
            
            async with httpx.AsyncClient() as client:
                response = await client.request(
                    method=method,
                    url=endpoint,
                    headers=headers,
                    json=body,
                    timeout=timeout
                )
                
                if response.status_code == 200:
                    return HandlerResult.success_result(response.json())
                else:
                    return HandlerResult.failure_result(f"API调用失败: HTTP {response.status_code}")
                    
        except Exception as e:
            logger.error(f"API调用失败: {str(e)}")
            return HandlerResult.failure_result(f"API调用异常: {str(e)}")
    
    def _render_template(self, template: Dict, slots: Dict, context: Dict) -> Dict:
        """渲染模板变量"""
        if not isinstance(template, dict):
            return template
            
        result = {}
        for key, value in template.items():
            if isinstance(value, str) and value.startswith('{') and value.endswith('}'):
                # 简单变量替换
                var_name = value[1:-1]
                if var_name in slots:
                    result[key] = self._get_slot_value(slots, var_name)
                elif var_name in context:
                    result[key] = context[var_name]
                else:
                    result[key] = value
            else:
                result[key] = value
        return result
    
    def _get_slot_value(self, slots: Dict, slot_name: str) -> str:
        """从槽位字典中获取值"""
        slot_data = slots.get(slot_name)
        if hasattr(slot_data, 'value'):
            return slot_data.value
        elif isinstance(slot_data, dict):
            return slot_data.get('value', '')
        else:
            return str(slot_data) if slot_data else ''
    
    def validate_config(self, config: Dict) -> bool:
        """验证API调用配置"""
        required_fields = ['endpoint']
        return all(field in config for field in required_fields)


class DatabaseHandler(BaseIntentHandler):
    """数据库操作处理器"""
    
    async def execute(self, config: Dict, intent: Intent, slots: Dict, context: Dict) -> HandlerResult:
        """执行数据库操作"""
        try:
            # 这里实现数据库操作逻辑
            # 暂时返回成功结果
            return HandlerResult.success_result({"message": "数据库操作完成"})
        except Exception as e:
            return HandlerResult.failure_result(f"数据库操作失败: {str(e)}")
    
    def validate_config(self, config: Dict) -> bool:
        return True


class ConfigDrivenIntentProcessor:
    """配置驱动的意图处理器"""
    
    def __init__(self):
        self.handlers = {
            'mock_service': MockServiceHandler(),
            'api_call': APICallHandler(), 
            'database': DatabaseHandler()
        }
    
    async def execute_intent(self, intent: Intent, slots: Dict, context: Dict) -> ChatResponse:
        """执行意图处理"""
        try:
            # 1. 获取处理器配置
            handler_config = await self._get_handler_config(intent.id)
            if not handler_config:
                return self._create_error_response(
                    "未找到意图处理器配置", intent, slots, context
                )
            
            # 2. 获取处理器
            handler = self.handlers.get(handler_config['handler_type'])
            if not handler:
                return self._create_error_response(
                    f"未知的处理器类型: {handler_config['handler_type']}", intent, slots, context
                )
            
            # 3. 执行处理器
            result = await handler.execute(
                handler_config['handler_config'],
                intent, slots, context
            )
            
            # 4. 根据结果生成响应
            if result.success:
                return await self._create_success_response(intent, slots, context, result.data)
            else:
                return await self._create_failure_response(intent, slots, context, result.error)
                
        except Exception as e:
            logger.error(f"意图执行失败: {str(e)}")
            return self._create_error_response(f"系统错误: {str(e)}", intent, slots, context)
    
    async def _get_handler_config(self, intent_id: int) -> Optional[Dict]:
        """获取处理器配置"""
        try:
            from src.models.intent import Intent
            
            # 直接使用SQL查询intent_handlers表
            from peewee import SQL
            query = """
                SELECT handler_type, handler_config 
                FROM intent_handlers 
                WHERE intent_id = %s AND is_active = 1
            """
            
            # 使用Intent模型的数据库连接
            cursor = Intent._meta.database.execute_sql(query, (intent_id,))
            result = cursor.fetchone()
            
            if result:
                handler_type, handler_config_json = result
                import json
                handler_config = json.loads(handler_config_json) if handler_config_json else {}
                
                return {
                    'handler_type': handler_type,
                    'handler_config': handler_config
                }
            else:
                # 如果没有找到配置，返回默认的mock配置
                logger.warning(f"未找到意图{intent_id}的处理器配置，使用默认mock配置")
                return {
                    'handler_type': 'mock_service',
                    'handler_config': {
                        'service_name': 'book_flight_service',  # 默认使用机票预订服务
                        'mock_delay': 1,
                        'success_rate': 0.95
                    }
                }
        except Exception as e:
            logger.error(f"获取处理器配置失败: {str(e)}")
            return None
    
    async def _create_success_response(self, intent: Intent, slots: Dict, context: Dict, data: Dict) -> ChatResponse:
        """创建成功响应"""
        # 获取成功响应模板
        template = await self._get_response_template(intent.id, 'success')
        
        # 合并槽位数据和API结果数据用于模板渲染
        template_vars = {**slots, **data}
        response_text = self._render_response_template(template, template_vars)
        
        # 如果模板渲染结果仍然是默认模板，使用更好的格式化输出
        if response_text == '操作成功完成！' and data:
            if intent.intent_name == 'book_flight':
                response_text = self._format_flight_booking_response(data)
            elif intent.intent_name == 'check_balance':
                response_text = self._format_balance_check_response(data)
            elif intent.intent_name == 'book_train':
                response_text = self._format_train_booking_response(data)
            elif intent.intent_name == 'book_movie':
                response_text = self._format_movie_booking_response(data)
        
        return ChatResponse(
            response=response_text,
            session_id=context.get('session_id', ''),
            intent=intent.intent_name,
            confidence=0.95,
            slots=slots,
            status="completed",
            response_type="api_result",
            next_action="none",
            api_result=data,
            session_metadata=SessionMetadata(
                total_turns=context.get('current_turn', 1),
                session_duration_seconds=0
            )
        )
    
    def _format_flight_booking_response(self, data: Dict) -> str:
        """格式化机票预订成功响应"""
        response = f"✅ 机票预订成功！\n\n"
        response += f"订单号：{data.get('order_id', '未知')}\n"
        response += f"航程：{data.get('departure_city', '未知')} → {data.get('arrival_city', '未知')}\n"
        response += f"日期：{data.get('departure_date', '未知')}\n"
        if data.get('return_date'):
            response += f"返程：{data.get('return_date')}\n"
        response += f"乘客数：{data.get('passenger_count', '1')}人\n\n"
        response += "请保存好订单号，稍后将发送确认短信。"
        return response
    
    def _format_balance_check_response(self, data: Dict) -> str:
        """格式化余额查询成功响应"""
        response = f"💳 {data.get('account_type', '银行卡')}余额查询成功！\n\n"
        if 'card_number' in data:
            response += f"卡号：{data['card_number']}\n"
        response += f"余额：¥{data.get('balance', '0.00')}\n"
        response += f"查询时间：{data.get('query_time', data.get('booking_time', ''))}\n\n"
        response += "如需其他服务，请继续咨询。"
        return response
    
    def _format_train_booking_response(self, data: Dict) -> str:
        """格式化火车票预订成功响应"""
        response = f"🚄 火车票预订成功！\n\n"
        response += f"订单号：{data.get('order_id', '未知')}\n"
        response += f"车次：{data.get('train_number', '未知')}\n"
        response += f"出发：{data.get('departure_city', '未知')} → {data.get('arrival_city', '未知')}\n"
        response += f"日期：{data.get('departure_date', '未知')}\n"
        response += f"座位：{data.get('seat_type', '未知')}\n"
        response += f"乘客：{data.get('passenger_count', '1')}人\n\n"
        response += "请保存好订单号，出行前请提前到达车站。"
        return response
    
    def _format_movie_booking_response(self, data: Dict) -> str:
        """格式化电影票预订成功响应"""
        response = f"🎬 电影票预订成功！\n\n"
        response += f"订单号：{data.get('order_id', '未知')}\n"
        response += f"电影：{data.get('movie_name', '未知')}\n"
        response += f"影院：{data.get('cinema_name', '未知')}\n"
        response += f"时间：{data.get('show_time', '未知')}\n"
        response += f"座位：{data.get('seat_info', '未知')}\n"
        response += f"票数：{data.get('ticket_count', '1')}张\n\n"
        response += "请保存好订单号，观影前请提前30分钟到达影院取票。"
        return response
    
    async def _create_failure_response(self, intent: Intent, slots: Dict, context: Dict, error: str) -> ChatResponse:
        """创建失败响应"""
        # 获取失败响应模板
        template = await self._get_response_template(intent.id, 'failure')
        response_text = self._render_response_template(template, {**slots, 'error_message': error})
        
        # 如果使用的是默认失败模板，提供更友好的错误信息
        if response_text == f"操作失败：{error}":
            response_text = f"很抱歉，{intent.display_name}服务暂时不可用：{error}。请稍后重试或联系客服。"
        
        return ChatResponse(
            response=response_text,
            session_id=context.get('session_id', ''),
            intent=intent.intent_name,
            confidence=0.95,
            slots=slots,
            status="api_error",
            response_type="error_with_alternatives",
            next_action="retry",
            session_metadata=SessionMetadata(
                total_turns=context.get('current_turn', 1),
                session_duration_seconds=0
            )
        )
    
    def _create_error_response(self, error: str, intent: Intent, slots: Dict, context: Dict) -> ChatResponse:
        """创建错误响应"""
        return ChatResponse(
            response=f"处理请求时出现错误：{error}",
            session_id=context.get('session_id', ''),
            intent=intent.intent_name if intent else 'unknown',
            confidence=0.0,
            slots=slots,
            status="error",
            response_type="error",
            next_action="none",
            session_metadata=SessionMetadata(
                total_turns=context.get('current_turn', 1),
                session_duration_seconds=0
            )
        )
    
    async def _get_response_template(self, intent_id: int, template_type: str) -> str:
        """获取响应模板"""
        try:
            from src.models.intent import Intent
            
            # 查询response_templates表
            query = """
                SELECT template_content 
                FROM response_templates 
                WHERE intent_id = %s AND template_type = %s AND is_active = 1
            """
            
            # 使用Intent模型的数据库连接
            cursor = Intent._meta.database.execute_sql(query, (intent_id, template_type))
            result = cursor.fetchone()
            
            if result:
                return result[0]
            else:
                # 如果没有找到模板，返回默认模板
                default_templates = {
                    'success': '操作成功完成！',
                    'failure': '操作失败：{error_message}',
                    'confirmation': '请确认您的信息是否正确？'  # 返回默认模板以触发硬编码逻辑
                }
                template = default_templates.get(template_type, '操作完成')
                logger.warning(f"未找到意图{intent_id}的{template_type}模板，使用默认模板: {template}")
                return template
        except Exception as e:
            logger.error(f"获取响应模板失败: {str(e)}")
            return "操作完成"
    
    def _render_response_template(self, template: str, variables: Dict) -> str:
        """渲染响应模板"""
        try:
            # 简单的变量替换
            result = template
            for key, value in variables.items():
                placeholder = f"{{{key}}}"
                if placeholder in result:
                    # 获取实际值
                    actual_value = value
                    if hasattr(value, 'value'):
                        actual_value = value.value
                    elif isinstance(value, dict):
                        actual_value = value.get('value', str(value))
                    
                    result = result.replace(placeholder, str(actual_value))
            return result
        except Exception as e:
            logger.error(f"模板渲染失败: {str(e)}")
            return template


# 全局实例
_config_driven_processor = None

async def get_config_driven_processor() -> ConfigDrivenIntentProcessor:
    """获取配置驱动处理器实例"""
    global _config_driven_processor
    if _config_driven_processor is None:
        _config_driven_processor = ConfigDrivenIntentProcessor()
    return _config_driven_processor