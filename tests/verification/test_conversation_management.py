#!/usr/bin/env python3
"""
VT-006: 意图转移和槽位继承验证
验证复杂对话管理功能
"""
import sys
import os
import time
import asyncio
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from datetime import datetime

sys.path.insert(0, os.path.abspath('.'))

from src.services.intent_transfer_service import (
    IntentTransferService, TransferTrigger, TransferCondition, TransferRule, 
    TransferDecision, IntentTransferService
)
from src.services.intent_stack_service import (
    IntentStackService, IntentStackFrame, IntentStackStatus, IntentInterruptionType
)
from src.core.slot_inheritance import (
    SlotInheritanceEngine, ConversationInheritanceManager, InheritanceType, 
    InheritanceStrategy, InheritanceRule
)
from src.services.cache_service import CacheService


@dataclass
class VerificationResult:
    """验证结果"""
    test_name: str
    success: bool
    details: Dict[str, Any]
    error_message: Optional[str] = None
    execution_time: float = 0.0


class ConversationManagementVerifier:
    """对话管理验证器"""
    
    def __init__(self):
        self.cache_service = None
        self.intent_transfer_service = None
        self.intent_stack_service = None
        self.slot_inheritance_engine = None
        self.inheritance_manager = None
        self.verification_results: List[VerificationResult] = []
    
    async def setup(self):
        """设置验证环境"""
        try:
            # 模拟缓存服务
            class MockCacheService:
                def __init__(self):
                    self.data = {}
                
                async def get(self, key, namespace=None):
                    full_key = f"{namespace}:{key}" if namespace else key
                    return self.data.get(full_key)
                
                async def set(self, key, value, ttl=None, namespace=None):
                    full_key = f"{namespace}:{key}" if namespace else key
                    self.data[full_key] = value
                
                async def delete(self, key, namespace=None):
                    full_key = f"{namespace}:{key}" if namespace else key
                    self.data.pop(full_key, None)
            
            self.cache_service = MockCacheService()
            
            # 模拟意图服务
            class MockIntentService:
                async def recognize_intent(self, user_input, user_id, context=None):
                    # 模拟意图识别结果
                    class MockIntentResult:
                        def __init__(self, intent_name, confidence):
                            self.intent = type('Intent', (), {'intent_name': intent_name})()
                            self.confidence = confidence
                    
                    # 基于输入返回不同意图
                    if "余额" in user_input or "balance" in user_input:
                        return MockIntentResult("check_balance", 0.9)
                    elif "机票" in user_input or "flight" in user_input:
                        return MockIntentResult("book_flight", 0.85)
                    elif "取消" in user_input or "cancel" in user_input:
                        return MockIntentResult("cancel_request", 0.8)
                    else:
                        return MockIntentResult("unknown", 0.3)
            
            # 模拟Intent模型
            class MockIntent:
                def __init__(self, intent_name):
                    self.id = hash(intent_name) % 1000
                    self.intent_name = intent_name
                    self.is_active = True
                    self._current_intent = None
                
                @classmethod
                def set_current_intent(cls, intent_name):
                    cls._current_intent = intent_name
                
                @classmethod
                def get(cls, condition=None, **kwargs):
                    # 模拟查询
                    intent_name = getattr(cls, '_current_intent', 'default_intent')
                    return cls(intent_name)
                
                class DoesNotExist(Exception):
                    pass
            
            # 模拟IntentTransfer模型
            class MockIntentTransfer:
                _test_mode = True
                
                @classmethod
                def create(cls, **kwargs):
                    transfer = cls()
                    for key, value in kwargs.items():
                        setattr(transfer, key, value)
                    transfer.id = hash(str(kwargs)) % 10000
                    transfer.created_at = datetime.now()
                    transfer.updated_at = datetime.now()
                    return transfer
            
            # 设置测试模式
            from src.models import intent, conversation
            intent.Intent = MockIntent
            conversation.IntentTransfer = MockIntentTransfer
            conversation.IntentTransfer._test_mode = True
            
            # 初始化服务
            self.intent_stack_service = IntentStackService(self.cache_service)
            self.intent_transfer_service = IntentTransferService(
                self.cache_service, 
                MockIntentService(), 
                self.intent_stack_service
            )
            
            # 初始化槽位继承系统
            self.slot_inheritance_engine = SlotInheritanceEngine()
            self.inheritance_manager = ConversationInheritanceManager(self.slot_inheritance_engine)
            
            print("✓ 验证环境设置完成")
            return True
            
        except Exception as e:
            print(f"❌ 验证环境设置失败: {str(e)}")
            return False
    
    async def verify_intent_transfer_detection(self) -> VerificationResult:
        """验证意图转移检测"""
        start_time = time.time()
        test_name = "意图转移检测验证"
        
        try:
            details = {}
            
            print("\n=== 验证意图转移检测 ===")
            
            # 1. 验证明确意图转移检测
            print("1. 验证明确意图转移检测")
            
            session_id = "test_session_001"
            user_id = "test_user_001"
            current_intent = "book_flight"
            
            # 测试明确转移：从订机票转移到查余额
            user_input = "我想查余额"
            context = {'current_slots': {'departure_city': '北京'}}
            
            transfer_decision = await self.intent_transfer_service.evaluate_transfer(
                session_id, user_id, current_intent, user_input, context
            )
            
            details['explicit_transfer_detected'] = transfer_decision.should_transfer
            details['target_intent_correct'] = transfer_decision.target_intent == "check_balance"
            details['transfer_confidence'] = transfer_decision.confidence
            
            if details['explicit_transfer_detected'] and details['target_intent_correct']:
                print(f"✓ 明确意图转移检测成功: {current_intent} -> {transfer_decision.target_intent}")
            else:
                print("❌ 明确意图转移检测失败")
            
            # 2. 验证中断类型意图转移
            print("2. 验证中断类型意图转移")
            
            # 测试中断规则：余额查询中断
            interrupt_input = "余额多少"
            interrupt_decision = await self.intent_transfer_service.evaluate_transfer(
                session_id, user_id, "book_flight", interrupt_input, context
            )
            
            details['interrupt_transfer_detected'] = interrupt_decision.should_transfer
            details['interrupt_trigger_correct'] = (
                interrupt_decision.trigger == TransferTrigger.EXPLICIT_CHANGE or
                interrupt_decision.trigger == TransferTrigger.INTERRUPTION
            )
            
            if details['interrupt_transfer_detected']:
                print(f"✓ 中断类型转移检测成功: 触发器={interrupt_decision.trigger}")
            else:
                print("❌ 中断类型转移检测失败")
            
            # 3. 验证用户澄清转移
            print("3. 验证用户澄清转移")
            
            # 测试取消/返回意图
            cancel_input = "取消"
            cancel_decision = await self.intent_transfer_service.evaluate_transfer(
                session_id, user_id, current_intent, cancel_input, context
            )
            
            details['cancel_transfer_detected'] = cancel_decision.should_transfer
            details['cancel_target_correct'] = (
                cancel_decision.target_intent == "previous" or 
                cancel_decision.target_intent == "cancel_request"
            )
            
            if details['cancel_transfer_detected']:
                print(f"✓ 取消转移检测成功: 目标={cancel_decision.target_intent}")
            else:
                print("❌ 取消转移检测失败")
            
            # 4. 验证转移规则系统
            print("4. 验证转移规则系统")
            
            # 获取当前意图的转移规则
            transfer_rules = self.intent_transfer_service.get_transfer_rules(current_intent)
            details['rules_loaded'] = len(transfer_rules) > 0
            
            # 验证规则包含期望的类型
            rule_types = [rule.trigger for rule in transfer_rules]
            expected_triggers = [
                TransferTrigger.EXPLICIT_CHANGE,
                TransferTrigger.INTERRUPTION,
                TransferTrigger.USER_CLARIFICATION
            ]
            
            details['rule_types_complete'] = all(
                trigger in rule_types for trigger in expected_triggers
            )
            
            if details['rules_loaded'] and details['rule_types_complete']:
                print(f"✓ 转移规则系统正常: {len(transfer_rules)} 个规则")
            else:
                print("❌ 转移规则系统不完整")
            
            # 5. 验证转移决策质量
            print("5. 验证转移决策质量")
            
            # 测试不应该转移的情况
            no_transfer_input = "好的"
            no_transfer_decision = await self.intent_transfer_service.evaluate_transfer(
                session_id, user_id, current_intent, no_transfer_input, context
            )
            
            details['no_transfer_correct'] = not no_transfer_decision.should_transfer
            
            # 验证决策信息完整性
            decision_fields = ['should_transfer', 'target_intent', 'confidence', 'reason']
            details['decision_info_complete'] = all(
                hasattr(transfer_decision, field) for field in decision_fields
            )
            
            if details['no_transfer_correct'] and details['decision_info_complete']:
                print("✓ 转移决策质量正常")
            else:
                print("❌ 转移决策质量异常")
            
            execution_time = time.time() - start_time
            success = (details['explicit_transfer_detected'] and
                      details['target_intent_correct'] and
                      details['interrupt_transfer_detected'] and
                      details['cancel_transfer_detected'] and
                      details['rules_loaded'] and
                      details['rule_types_complete'] and
                      details['no_transfer_correct'] and
                      details['decision_info_complete'])
            
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
    
    async def verify_slot_inheritance_mechanism(self) -> VerificationResult:
        """验证槽位继承机制"""
        start_time = time.time()
        test_name = "槽位继承机制验证"
        
        try:
            details = {}
            
            print("\n=== 验证槽位继承机制 ===")
            
            # 1. 验证基础继承规则
            print("1. 验证基础继承规则")
            
            # 模拟槽位定义
            class MockSlot:
                def __init__(self, slot_name, intent_id=1):
                    self.slot_name = slot_name
                    self.intent_id = intent_id
            
            intent_slots = [
                MockSlot("departure_city"),
                MockSlot("arrival_city"),
                MockSlot("passenger_name"),
                MockSlot("phone_number")
            ]
            
            current_values = {}  # 当前没有值
            
            # 构建继承上下文
            context = {
                'session_context': {
                    'departure_city': '北京',
                    'arrival_city': '上海'
                },
                'user_profile': {
                    'passenger_name': '张三',
                    'phone_number': '138-0013-8000'
                },
                'conversation_context': {
                    'departure_city': '广州'  # 较新的值
                },
                'current_values': current_values,
                'source_timestamp': datetime.now()
            }
            
            # 执行继承
            inheritance_result = await self.slot_inheritance_engine.inherit_slot_values(
                intent_slots, current_values, context
            )
            
            details['inheritance_executed'] = inheritance_result is not None
            details['inherited_values_count'] = len(inheritance_result.inherited_values)
            details['applied_rules_count'] = len(inheritance_result.applied_rules)
            
            if details['inheritance_executed']:
                print(f"✓ 槽位继承执行成功: {details['inherited_values_count']} 个值")
            else:
                print("❌ 槽位继承执行失败")
            
            # 2. 验证继承优先级
            print("2. 验证继承优先级")
            
            # 检查是否正确选择了优先级更高的值
            inherited_departure = inheritance_result.inherited_values.get('departure_city')
            details['priority_correct'] = (inherited_departure == '北京')  # session优先级更高
            
            if details['priority_correct']:
                print(f"✓ 继承优先级正确: departure_city = {inherited_departure}")
            else:
                print(f"❌ 继承优先级错误: 期望北京, 实际{inherited_departure}")
            
            # 3. 验证继承策略
            print("3. 验证继承策略")
            
            # 测试补充策略
            current_values_with_existing = {'departure_city': '深圳'}
            supplement_result = await self.slot_inheritance_engine.inherit_slot_values(
                intent_slots, current_values_with_existing, context
            )
            
            # 补充策略不应该覆盖现有值
            final_departure = supplement_result.inherited_values.get('departure_city')
            details['supplement_strategy_correct'] = (final_departure == '深圳')
            
            if details['supplement_strategy_correct']:
                print("✓ 补充策略正确: 不覆盖现有值")
            else:
                print(f"❌ 补充策略错误: {final_departure}")
            
            # 4. 验证值转换器
            print("4. 验证值转换器")
            
            # 测试电话号码格式化
            raw_phone = "13800138000"
            formatted_phone = self.slot_inheritance_engine._format_phone_number(raw_phone)
            details['phone_formatting_correct'] = formatted_phone == "138-0013-8000"
            
            # 测试城市名提取
            city_with_suffix = "北京市"
            extracted_city = self.slot_inheritance_engine._extract_city_name(city_with_suffix)
            details['city_extraction_correct'] = extracted_city == "北京市"
            
            if details['phone_formatting_correct'] and details['city_extraction_correct']:
                print("✓ 值转换器正常工作")
            else:
                print("❌ 值转换器工作异常")
            
            # 5. 验证继承源追踪
            print("5. 验证继承源追踪")
            
            sources = inheritance_result.inheritance_sources
            details['source_tracking_available'] = len(sources) > 0
            
            # 验证源描述的合理性
            if sources:
                sample_source = list(sources.values())[0]
                details['source_description_valid'] = (
                    isinstance(sample_source, str) and len(sample_source) > 0
                )
            else:
                details['source_description_valid'] = False
            
            if details['source_tracking_available'] and details['source_description_valid']:
                print(f"✓ 继承源追踪正常: {len(sources)} 个源")
            else:
                print("❌ 继承源追踪异常")
            
            # 6. 验证对话历史继承
            print("6. 验证对话历史继承")
            
            try:
                # 这会尝试调用数据库，但我们有mock
                history_result = await self.inheritance_manager.inherit_from_conversation_history(
                    user_id="test_user",
                    intent_slots=intent_slots,
                    current_values={},
                    max_history=5,
                    use_cache=False  # 跳过缓存以测试核心逻辑
                )
                
                details['history_inheritance_works'] = history_result is not None
                
                if details['history_inheritance_works']:
                    print("✓ 对话历史继承正常")
                else:
                    print("❌ 对话历史继承失败")
                    
            except Exception as e:
                details['history_inheritance_works'] = False
                details['history_inheritance_error'] = str(e)
                print(f"❌ 对话历史继承异常: {str(e)}")
            
            execution_time = time.time() - start_time
            success = (details['inheritance_executed'] and
                      details['inherited_values_count'] > 0 and
                      details['applied_rules_count'] > 0 and
                      details['priority_correct'] and
                      details['supplement_strategy_correct'] and
                      details['phone_formatting_correct'] and
                      details['city_extraction_correct'] and
                      details['source_tracking_available'] and
                      details['source_description_valid'])
            
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
    
    async def verify_context_management(self) -> VerificationResult:
        """验证上下文管理"""
        start_time = time.time()
        test_name = "上下文管理验证"
        
        try:
            details = {}
            
            print("\n=== 验证上下文管理 ===")
            
            # 1. 验证意图转移执行
            print("1. 验证意图转移执行")
            
            session_id = "test_session_002"
            user_id = "test_user_002"
            
            # 创建转移决策
            transfer_decision = TransferDecision(
                should_transfer=True,
                target_intent="check_balance",
                confidence=0.9,
                trigger=TransferTrigger.INTERRUPTION,
                reason="用户要求查询余额",
                save_context=True
            )
            
            current_context = {
                'departure_city': '北京',
                'flight_date': '2024-12-25',
                'passenger_count': 2
            }
            
            # 执行转移
            transfer_success = await self.intent_transfer_service.execute_transfer(
                session_id, user_id, transfer_decision, current_context
            )
            
            details['transfer_execution_success'] = transfer_success
            
            if transfer_success:
                print("✓ 意图转移执行成功")
            else:
                print("❌ 意图转移执行失败")
            
            # 2. 验证上下文保存
            print("2. 验证上下文保存")
            
            # 获取转移历史
            transfer_history = await self.intent_transfer_service.get_transfer_history(session_id)
            details['transfer_history_available'] = len(transfer_history) > 0
            
            if details['transfer_history_available']:
                # 检查上下文是否被保存
                latest_transfer = transfer_history[0]
                details['context_saved'] = latest_transfer.get('saved_context') is not None
                print("✓ 转移历史记录正常")
            else:
                details['context_saved'] = False
                print("❌ 转移历史记录缺失")
            
            # 3. 验证转移统计
            print("3. 验证转移统计")
            
            transfer_stats = await self.intent_transfer_service.get_transfer_statistics(session_id)
            details['stats_available'] = transfer_stats is not None and 'total_transfers' in transfer_stats
            
            if details['stats_available']:
                total_transfers = transfer_stats.get('total_transfers', 0)
                details['stats_reasonable'] = total_transfers >= 0
                print(f"✓ 转移统计正常: {total_transfers} 次转移")
            else:
                details['stats_reasonable'] = False
                print("❌ 转移统计异常")
            
            # 4. 验证会话活动跟踪
            print("4. 验证会话活动跟踪")
            
            # 更新最后活动时间
            await self.intent_transfer_service.update_last_activity(session_id)
            
            # 检查活动时间是否被记录
            last_activity_key = f"last_activity:{session_id}"
            cached_activity = await self.cache_service.get(last_activity_key, namespace="intent_transfer")
            details['activity_tracking_works'] = cached_activity is not None
            
            if details['activity_tracking_works']:
                print("✓ 会话活动跟踪正常")
            else:
                print("❌ 会话活动跟踪失败")
            
            # 5. 验证特殊转移检测
            print("5. 验证特殊转移检测")
            
            # 测试退出意图检测
            exit_decision = await self.intent_transfer_service._check_special_transfers(
                session_id, "book_flight", "退出", {}
            )
            
            details['exit_detection_works'] = exit_decision.should_transfer
            details['exit_target_correct'] = exit_decision.target_intent == "session_end"
            
            if details['exit_detection_works'] and details['exit_target_correct']:
                print("✓ 特殊转移检测正常")
            else:
                print("❌ 特殊转移检测异常")
            
            # 6. 验证转移规则管理
            print("6. 验证转移规则管理")
            
            # 添加自定义规则
            custom_rule = TransferRule(
                rule_id="test_custom_rule",
                from_intent="test_intent",
                to_intent="test_target",
                trigger=TransferTrigger.USER_CLARIFICATION,
                conditions=[TransferCondition.PATTERN_MATCH],
                patterns=["测试模式"],
                description="测试自定义规则"
            )
            
            initial_rule_count = len(self.intent_transfer_service.transfer_rules.get("test_intent", []))
            self.intent_transfer_service.add_transfer_rule(custom_rule)
            final_rule_count = len(self.intent_transfer_service.transfer_rules.get("test_intent", []))
            
            details['rule_addition_works'] = final_rule_count > initial_rule_count
            
            # 测试规则移除
            removal_success = self.intent_transfer_service.remove_transfer_rule("test_custom_rule")
            details['rule_removal_works'] = removal_success
            
            if details['rule_addition_works'] and details['rule_removal_works']:
                print("✓ 转移规则管理正常")
            else:
                print("❌ 转移规则管理异常")
            
            execution_time = time.time() - start_time
            success = (details['transfer_execution_success'] and
                      details['transfer_history_available'] and
                      details['context_saved'] and
                      details['stats_available'] and
                      details['stats_reasonable'] and
                      details['activity_tracking_works'] and
                      details['exit_detection_works'] and
                      details['exit_target_correct'] and
                      details['rule_addition_works'] and
                      details['rule_removal_works'])
            
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
    
    async def verify_intent_stack_operations(self) -> VerificationResult:
        """验证意图栈操作"""
        start_time = time.time()
        test_name = "意图栈操作验证"
        
        try:
            details = {}
            
            print("\n=== 验证意图栈操作 ===")
            
            session_id = "test_session_003"
            user_id = "test_user_003"
            
            # 1. 验证栈的基本操作
            print("1. 验证栈的基本操作")
            
            # 推入第一个意图
            frame1 = await self.intent_stack_service.push_intent(
                session_id, user_id, "book_flight",
                context={'departure_city': '北京'},
                interruption_type=None,
                interruption_reason=None
            )
            
            details['push_success'] = frame1 is not None
            details['frame_id_generated'] = frame1.frame_id is not None if frame1 else False
            
            if details['push_success']:
                print(f"✓ 意图推入成功: {frame1.intent_name}")
            else:
                print("❌ 意图推入失败")
            
            # 2. 验证栈的查看操作
            print("2. 验证栈的查看操作")
            
            # 查看栈顶
            top_frame = await self.intent_stack_service.peek_intent(session_id)
            details['peek_success'] = top_frame is not None
            details['peek_correct'] = (top_frame.intent_name == "book_flight") if top_frame else False
            
            # 获取活跃意图
            active_frame = await self.intent_stack_service.get_active_intent(session_id)
            details['active_intent_correct'] = (active_frame.intent_name == "book_flight") if active_frame else False
            
            if details['peek_success'] and details['active_intent_correct']:
                print("✓ 栈查看操作正常")
            else:
                print("❌ 栈查看操作异常")
            
            # 3. 验证栈的中断和恢复
            print("3. 验证栈的中断和恢复")
            
            # 推入中断意图
            frame2 = await self.intent_stack_service.push_intent(
                session_id, user_id, "check_balance",
                context={'account_type': '储蓄账户'},
                interruption_type=IntentInterruptionType.USER_INITIATED,
                interruption_reason="用户要求查询余额"
            )
            
            details['interrupt_push_success'] = frame2 is not None
            
            # 验证栈深度
            current_stack = await self.intent_stack_service.get_intent_stack(session_id)
            details['stack_depth_correct'] = len(current_stack) == 2
            
            # 验证中断状态
            if len(current_stack) >= 2:
                interrupted_frame = current_stack[0]  # 第一个帧应该被中断
                details['interruption_status_correct'] = (
                    interrupted_frame.status == IntentStackStatus.INTERRUPTED
                )
            else:
                details['interruption_status_correct'] = False
            
            if details['interrupt_push_success'] and details['interruption_status_correct']:
                print("✓ 意图中断机制正常")
            else:
                print("❌ 意图中断机制异常")
            
            # 4. 验证栈的弹出操作
            print("4. 验证栈的弹出操作")
            
            # 弹出当前意图
            popped_frame = await self.intent_stack_service.pop_intent(session_id, "查询余额完成")
            details['pop_success'] = popped_frame is not None
            details['popped_intent_correct'] = (
                popped_frame.intent_name == "check_balance"
            ) if popped_frame else False
            
            # 验证父级意图是否恢复
            stack_after_pop = await self.intent_stack_service.get_intent_stack(session_id)
            if stack_after_pop:
                resumed_frame = stack_after_pop[-1]
                details['parent_resumed'] = resumed_frame.status == IntentStackStatus.ACTIVE
            else:
                details['parent_resumed'] = False
            
            if details['pop_success'] and details['parent_resumed']:
                print("✓ 意图弹出和恢复正常")
            else:
                print("❌ 意图弹出和恢复异常")
            
            # 5. 验证栈的上下文更新
            print("5. 验证栈的上下文更新")
            
            current_frame = await self.intent_stack_service.get_active_intent(session_id)
            if current_frame:
                # 更新上下文
                context_updates = {'arrival_city': '上海', 'flight_class': '经济舱'}
                update_success = await self.intent_stack_service.update_frame_context(
                    session_id, current_frame.frame_id, context_updates
                )
                
                details['context_update_success'] = update_success
                
                # 验证更新是否生效
                updated_frame = await self.intent_stack_service.get_active_intent(session_id)
                if updated_frame:
                    details['context_update_effective'] = (
                        updated_frame.saved_context.get('arrival_city') == '上海'
                    )
                else:
                    details['context_update_effective'] = False
            else:
                details['context_update_success'] = False
                details['context_update_effective'] = False
            
            if details['context_update_success'] and details['context_update_effective']:
                print("✓ 上下文更新正常")
            else:
                print("❌ 上下文更新异常")
            
            # 6. 验证栈的槽位更新
            print("6. 验证栈的槽位更新")
            
            if current_frame:
                # 更新槽位
                slot_updates = {'departure_city': '北京', 'passenger_name': '张三'}
                missing_slots = ['flight_date', 'passenger_count']
                
                slot_update_success = await self.intent_stack_service.update_frame_slots(
                    session_id, current_frame.frame_id, slot_updates, missing_slots
                )
                
                details['slot_update_success'] = slot_update_success
                
                # 验证槽位更新是否生效
                updated_frame = await self.intent_stack_service.get_active_intent(session_id)
                if updated_frame:
                    details['slot_values_correct'] = (
                        updated_frame.collected_slots.get('departure_city') == '北京'
                    )
                    details['missing_slots_correct'] = (
                        'flight_date' in updated_frame.missing_slots
                    )
                else:
                    details['slot_values_correct'] = False
                    details['missing_slots_correct'] = False
            else:
                details['slot_update_success'] = False
                details['slot_values_correct'] = False
                details['missing_slots_correct'] = False
            
            if (details['slot_update_success'] and 
                details['slot_values_correct'] and 
                details['missing_slots_correct']):
                print("✓ 槽位更新正常")
            else:
                print("❌ 槽位更新异常")
            
            # 7. 验证栈统计信息
            print("7. 验证栈统计信息")
            
            stack_stats = await self.intent_stack_service.get_stack_statistics(session_id)
            details['stats_available'] = stack_stats is not None and 'total_frames' in stack_stats
            
            if details['stats_available']:
                details['stats_reasonable'] = (
                    stack_stats.get('total_frames', 0) >= 0 and
                    stack_stats.get('current_depth', 0) >= 0
                )
                print(f"✓ 栈统计正常: {stack_stats.get('total_frames')} 帧")
            else:
                details['stats_reasonable'] = False
                print("❌ 栈统计异常")
            
            execution_time = time.time() - start_time
            success = (details['push_success'] and
                      details['frame_id_generated'] and
                      details['peek_success'] and
                      details['active_intent_correct'] and
                      details['interrupt_push_success'] and
                      details['stack_depth_correct'] and
                      details['interruption_status_correct'] and
                      details['pop_success'] and
                      details['parent_resumed'] and
                      details['context_update_success'] and
                      details['context_update_effective'] and
                      details['slot_update_success'] and
                      details['slot_values_correct'] and
                      details['missing_slots_correct'] and
                      details['stats_available'] and
                      details['stats_reasonable'])
            
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
        print("开始VT-006: 意图转移和槽位继承验证")
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
            self.verify_intent_transfer_detection(),
            self.verify_slot_inheritance_mechanism(),
            self.verify_context_management(),
            self.verify_intent_stack_operations()
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
        print("VT-006 验证结果汇总")
        print("=" * 60)
        
        for result in results:
            status = "✓ 通过" if result.success else "✗ 失败"
            print(f"{result.test_name}: {status} ({result.execution_time:.2f}s)")
            if not result.success and result.error_message:
                print(f"  错误: {result.error_message}")
        
        print(f"\n总计: {passed_tests}/{total_tests} 测试通过")
        print(f"总执行时间: {total_time:.2f}秒")
        
        # 对话管理验证标准
        conversation_verification = {
            'intent_transfer_detection': any(r.test_name.startswith('意图转移检测') and r.success for r in results),
            'slot_inheritance_mechanism': any(r.test_name.startswith('槽位继承机制') and r.success for r in results),
            'context_management': any(r.test_name.startswith('上下文管理') and r.success for r in results),
            'intent_stack_operations': any(r.test_name.startswith('意图栈操作') and r.success for r in results)
        }
        
        all_mechanisms_working = all(conversation_verification.values())
        
        if all_mechanisms_working:
            print("\n🎉 意图转移和槽位继承验证完全通过！")
            print("✓ 意图转移检测正确")
            print("✓ 槽位继承机制有效")
            print("✓ 上下文管理完整")
            print("✓ 意图栈操作正常")
        else:
            print("\n❌ 意图转移和槽位继承验证部分失败")
            for mechanism, status in conversation_verification.items():
                status_text = "✓" if status else "✗"
                print(f"{status_text} {mechanism}")
        
        return {
            'success': all_mechanisms_working,
            'total_tests': total_tests,
            'passed_tests': passed_tests,
            'total_time': total_time,
            'conversation_verification': conversation_verification,
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
    verifier = ConversationManagementVerifier()
    
    try:
        result = await verifier.run_all_verifications()
        
        # 根据结果返回适当的退出码
        if result['success']:
            print("\n✅ VT-006 验证成功完成")
            return 0
        else:
            print("\n❌ VT-006 验证存在失败项")
            return 1
            
    except Exception as e:
        print(f"\n💥 VT-006 验证执行异常: {str(e)}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)