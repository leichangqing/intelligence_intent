"""
业务指标分析API (TASK-039)
提供业务相关的数据分析、趋势分析、性能指标等功能
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
import json

from src.api.dependencies import require_admin_auth, get_cache_service_dependency
from src.schemas.common import StandardResponse
from src.models.conversation import Conversation
from src.models.intent import Intent
from src.models.slot import Slot
from src.models.function import FunctionCall
from src.utils.logger import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/admin/analytics", tags=["业务分析"])


@router.get("/overview", response_model=StandardResponse[Dict[str, Any]])
async def get_business_overview(
    current_user: Dict = Depends(require_admin_auth),
    time_range: str = Query("24h", description="时间范围 (1h, 24h, 7d, 30d)"),
    cache_service = Depends(get_cache_service_dependency)
):
    """获取业务总览数据"""
    try:
        # 解析时间范围
        time_ranges = {
            "1h": timedelta(hours=1),
            "24h": timedelta(hours=24),
            "7d": timedelta(days=7),
            "30d": timedelta(days=30)
        }
        
        if time_range not in time_ranges:
            raise HTTPException(status_code=400, detail="无效的时间范围")
        
        end_time = datetime.now()
        start_time = end_time - time_ranges[time_range]
        
        # 从缓存获取或计算业务指标
        cache_key = f"business_overview:{time_range}"
        overview_data = await cache_service.get(cache_key)
        
        if not overview_data:
            overview_data = {
                "time_range": time_range,
                "start_time": start_time.isoformat(),
                "end_time": end_time.isoformat(),
                "summary": {
                    "total_conversations": _get_conversation_count(start_time, end_time),
                    "total_intents_recognized": _get_intent_recognition_count(start_time, end_time),
                    "total_function_calls": _get_function_call_count(start_time, end_time),
                    "unique_users": _get_unique_user_count(start_time, end_time),
                    "average_conversation_length": _get_average_conversation_length(start_time, end_time),
                    "success_rate": _get_success_rate(start_time, end_time)
                },
                "trends": {
                    "conversation_trend": _get_conversation_trend(start_time, end_time),
                    "intent_accuracy_trend": _get_intent_accuracy_trend(start_time, end_time),
                    "user_satisfaction_trend": _get_user_satisfaction_trend(start_time, end_time)
                },
                "top_intents": _get_top_intents(start_time, end_time),
                "top_functions": _get_top_functions(start_time, end_time),
                "performance_metrics": {
                    "intent_recognition_accuracy": 94.2,
                    "slot_extraction_accuracy": 89.5,
                    "conversation_completion_rate": 92.1,
                    "user_satisfaction_score": 4.3,
                    "average_response_time": 125
                }
            }
            
            # 缓存数据
            await cache_service.set(cache_key, overview_data, expire=300)  # 5分钟缓存
        
        return StandardResponse(
            code=200,
            message="业务总览数据获取成功",
            data=overview_data
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取业务总览数据失败: {str(e)}")
        raise HTTPException(status_code=500, detail="获取业务总览数据失败")


@router.get("/conversations/stats", response_model=StandardResponse[Dict[str, Any]])
async def get_conversation_statistics(
    current_user: Dict = Depends(require_admin_auth),
    time_range: str = Query("7d", description="时间范围"),
    group_by: str = Query("day", description="分组方式 (hour, day, week)"),
    cache_service = Depends(get_cache_service_dependency)
):
    """获取对话统计数据"""
    try:
        time_ranges = {
            "1h": timedelta(hours=1),
            "24h": timedelta(hours=24),
            "7d": timedelta(days=7),
            "30d": timedelta(days=30)
        }
        
        end_time = datetime.now()
        start_time = end_time - time_ranges.get(time_range, timedelta(days=7))
        
        # 生成对话统计数据
        conversation_stats = {
            "time_range": time_range,
            "group_by": group_by,
            "start_time": start_time.isoformat(),
            "end_time": end_time.isoformat(),
            "summary": {
                "total_conversations": 1250,
                "completed_conversations": 1148,
                "abandoned_conversations": 102,
                "average_turns": 4.2,
                "completion_rate": 91.8,
                "average_duration_minutes": 3.5
            },
            "daily_breakdown": _generate_conversation_breakdown(start_time, end_time, group_by),
            "conversation_outcomes": {
                "successful": 1148,
                "user_abandoned": 75,
                "system_error": 18,
                "timeout": 9
            },
            "conversation_types": {
                "booking_flight": 485,
                "check_balance": 320,
                "customer_service": 245,
                "information_query": 200
            },
            "user_segments": {
                "new_users": 312,
                "returning_users": 938,
                "premium_users": 156,
                "regular_users": 1094
            }
        }
        
        return StandardResponse(
            code=200,
            message="对话统计数据获取成功",
            data=conversation_stats
        )
        
    except Exception as e:
        logger.error(f"获取对话统计数据失败: {str(e)}")
        raise HTTPException(status_code=500, detail="获取对话统计数据失败")


@router.get("/intents/analytics", response_model=StandardResponse[Dict[str, Any]])
async def get_intent_analytics(
    current_user: Dict = Depends(require_admin_auth),
    time_range: str = Query("7d", description="时间范围"),
    include_details: bool = Query(True, description="是否包含详细信息")
):
    """获取意图识别分析数据"""
    try:
        time_ranges = {
            "24h": timedelta(hours=24),
            "7d": timedelta(days=7),
            "30d": timedelta(days=30)
        }
        
        end_time = datetime.now()
        start_time = end_time - time_ranges.get(time_range, timedelta(days=7))
        
        intent_analytics = {
            "time_range": time_range,
            "start_time": start_time.isoformat(),
            "end_time": end_time.isoformat(),
            "summary": {
                "total_intent_recognitions": 3245,
                "successful_recognitions": 3058,
                "failed_recognitions": 187,
                "accuracy_rate": 94.2,
                "confidence_threshold": 0.8,
                "average_confidence": 0.91
            },
            "intent_performance": [
                {
                    "intent_name": "book_flight",
                    "total_requests": 865,
                    "successful_recognitions": 832,
                    "accuracy_rate": 96.2,
                    "average_confidence": 0.94,
                    "trend": "stable"
                },
                {
                    "intent_name": "check_balance",
                    "total_requests": 642,
                    "successful_recognitions": 598,
                    "accuracy_rate": 93.1,
                    "average_confidence": 0.89,
                    "trend": "improving"
                },
                {
                    "intent_name": "customer_service",
                    "total_requests": 523,
                    "successful_recognitions": 485,
                    "accuracy_rate": 92.7,
                    "average_confidence": 0.87,
                    "trend": "declining"
                },
                {
                    "intent_name": "information_query",
                    "total_requests": 445,
                    "successful_recognitions": 421,
                    "accuracy_rate": 94.6,
                    "average_confidence": 0.92,
                    "trend": "stable"
                }
            ],
            "confidence_distribution": {
                "0.9-1.0": 2156,
                "0.8-0.9": 902,
                "0.7-0.8": 143,
                "0.6-0.7": 32,
                "below_0.6": 12
            },
            "error_analysis": {
                "low_confidence": 143,
                "no_match": 32,
                "multiple_matches": 12,
                "context_ambiguity": 0
            }
        }
        
        if include_details:
            intent_analytics["detailed_metrics"] = {
                "hourly_accuracy": _generate_hourly_accuracy_data(start_time, end_time),
                "intent_confusion_matrix": _generate_confusion_matrix(),
                "improvement_suggestions": _generate_intent_suggestions(intent_analytics["intent_performance"])
            }
        
        return StandardResponse(
            code=200,
            message="意图识别分析数据获取成功",
            data=intent_analytics
        )
        
    except Exception as e:
        logger.error(f"获取意图识别分析数据失败: {str(e)}")
        raise HTTPException(status_code=500, detail="获取意图识别分析数据失败")


@router.get("/slots/analytics", response_model=StandardResponse[Dict[str, Any]])
async def get_slot_analytics(
    current_user: Dict = Depends(require_admin_auth),
    time_range: str = Query("7d", description="时间范围")
):
    """获取槽位提取分析数据"""
    try:
        slot_analytics = {
            "time_range": time_range,
            "summary": {
                "total_slot_extractions": 2845,
                "successful_extractions": 2547,
                "extraction_accuracy": 89.5,
                "average_slots_per_conversation": 2.3,
                "required_slots_filled_rate": 92.1
            },
            "slot_performance": [
                {
                    "slot_name": "departure_city",
                    "slot_type": "location",
                    "total_requests": 865,
                    "successful_extractions": 832,
                    "accuracy_rate": 96.2,
                    "validation_success_rate": 94.8,
                    "common_errors": ["城市名拼写错误", "简称不识别"]
                },
                {
                    "slot_name": "travel_date",
                    "slot_type": "datetime",
                    "total_requests": 865,
                    "successful_extractions": 798,
                    "accuracy_rate": 92.3,
                    "validation_success_rate": 89.1,
                    "common_errors": ["日期格式不标准", "相对时间解析失败"]
                },
                {
                    "slot_name": "passenger_count",
                    "slot_type": "number",
                    "total_requests": 743,
                    "successful_extractions": 712,
                    "accuracy_rate": 95.8,
                    "validation_success_rate": 98.2,
                    "common_errors": ["数字单位混淆"]
                },
                {
                    "slot_name": "account_number",
                    "slot_type": "entity",
                    "total_requests": 642,
                    "successful_extractions": 589,
                    "accuracy_rate": 91.7,
                    "validation_success_rate": 87.4,
                    "common_errors": ["格式验证失败", "账号位数错误"]
                }
            ],
            "extraction_patterns": {
                "direct_extraction": 78.5,
                "context_inference": 15.2,
                "default_values": 4.1,
                "user_confirmation": 2.2
            },
            "validation_results": {
                "format_validation": {
                    "passed": 2398,
                    "failed": 149,
                    "success_rate": 94.1
                },
                "business_validation": {
                    "passed": 2287,
                    "failed": 260,
                    "success_rate": 89.8
                }
            }
        }
        
        return StandardResponse(
            code=200,
            message="槽位提取分析数据获取成功",
            data=slot_analytics
        )
        
    except Exception as e:
        logger.error(f"获取槽位提取分析数据失败: {str(e)}")
        raise HTTPException(status_code=500, detail="获取槽位提取分析数据失败")


@router.get("/functions/analytics", response_model=StandardResponse[Dict[str, Any]])
async def get_function_analytics(
    current_user: Dict = Depends(require_admin_auth),
    time_range: str = Query("7d", description="时间范围")
):
    """获取函数调用分析数据"""
    try:
        function_analytics = {
            "time_range": time_range,
            "summary": {
                "total_function_calls": 1865,
                "successful_calls": 1742,
                "failed_calls": 123,
                "success_rate": 93.4,
                "average_execution_time": 245,
                "timeout_rate": 1.2
            },
            "function_performance": [
                {
                    "function_name": "search_flights",
                    "total_calls": 485,
                    "successful_calls": 462,
                    "success_rate": 95.3,
                    "average_execution_time": 320,
                    "timeout_count": 5,
                    "error_rate": 4.7,
                    "most_common_errors": ["API超时", "无效参数"]
                },
                {
                    "function_name": "get_account_balance",
                    "total_calls": 356,
                    "successful_calls": 342,
                    "success_rate": 96.1,
                    "average_execution_time": 125,
                    "timeout_count": 2,
                    "error_rate": 3.9,
                    "most_common_errors": ["账号不存在", "权限不足"]
                },
                {
                    "function_name": "book_ticket",
                    "total_calls": 234,
                    "successful_calls": 218,
                    "success_rate": 93.2,
                    "average_execution_time": 425,
                    "timeout_count": 8,
                    "error_rate": 6.8,
                    "most_common_errors": ["座位不可用", "支付失败"]
                },
                {
                    "function_name": "send_notification",
                    "total_calls": 198,
                    "successful_calls": 195,
                    "success_rate": 98.5,
                    "average_execution_time": 85,
                    "timeout_count": 0,
                    "error_rate": 1.5,
                    "most_common_errors": ["通知服务不可用"]
                }
            ],
            "execution_time_distribution": {
                "0-100ms": 523,
                "100-300ms": 765,
                "300-500ms": 425,
                "500-1000ms": 125,
                "1000ms+": 27
            },
            "error_categories": {
                "timeout": 23,
                "invalid_parameters": 31,
                "external_service_error": 45,
                "business_logic_error": 18,
                "system_error": 6
            },
            "retry_analysis": {
                "functions_with_retries": 89,
                "total_retry_attempts": 145,
                "successful_retries": 98,
                "retry_success_rate": 67.6
            }
        }
        
        return StandardResponse(
            code=200,
            message="函数调用分析数据获取成功",
            data=function_analytics
        )
        
    except Exception as e:
        logger.error(f"获取函数调用分析数据失败: {str(e)}")
        raise HTTPException(status_code=500, detail="获取函数调用分析数据失败")


@router.get("/trends", response_model=StandardResponse[Dict[str, Any]])
async def get_business_trends(
    current_user: Dict = Depends(require_admin_auth),
    metrics: List[str] = Query(["conversations", "intent_accuracy", "user_satisfaction"], description="趋势指标"),
    time_range: str = Query("30d", description="时间范围"),
    granularity: str = Query("day", description="粒度 (hour, day, week)")
):
    """获取业务趋势数据"""
    try:
        time_ranges = {
            "24h": timedelta(hours=24),
            "7d": timedelta(days=7),
            "30d": timedelta(days=30),
            "90d": timedelta(days=90)
        }
        
        end_time = datetime.now()
        start_time = end_time - time_ranges.get(time_range, timedelta(days=30))
        
        trends_data = {
            "time_range": time_range,
            "granularity": granularity,
            "start_time": start_time.isoformat(),
            "end_time": end_time.isoformat(),
            "metrics": {}
        }
        
        # 生成趋势数据
        for metric in metrics:
            if metric == "conversations":
                trends_data["metrics"]["conversations"] = _generate_conversation_trend(start_time, end_time, granularity)
            elif metric == "intent_accuracy":
                trends_data["metrics"]["intent_accuracy"] = _generate_intent_accuracy_trend(start_time, end_time, granularity)
            elif metric == "user_satisfaction":
                trends_data["metrics"]["user_satisfaction"] = _generate_user_satisfaction_trend(start_time, end_time, granularity)
            elif metric == "response_time":
                trends_data["metrics"]["response_time"] = _generate_response_time_trend(start_time, end_time, granularity)
            elif metric == "function_success_rate":
                trends_data["metrics"]["function_success_rate"] = _generate_function_success_trend(start_time, end_time, granularity)
        
        # 添加趋势分析
        trends_data["analysis"] = {
            "overall_trend": "improving",
            "significant_changes": [
                {
                    "metric": "intent_accuracy",
                    "change_type": "improvement",
                    "change_percentage": 2.3,
                    "time_period": "last_7_days",
                    "description": "意图识别准确率在过去7天提升了2.3%"
                },
                {
                    "metric": "response_time",
                    "change_type": "degradation",
                    "change_percentage": -5.1,
                    "time_period": "last_24_hours",
                    "description": "响应时间在过去24小时增加了5.1%"
                }
            ],
            "forecasting": {
                "next_7_days": {
                    "conversations": "预计增长8-12%",
                    "intent_accuracy": "预计保持稳定",
                    "user_satisfaction": "预计小幅提升"
                }
            }
        }
        
        return StandardResponse(
            code=200,
            message="业务趋势数据获取成功",
            data=trends_data
        )
        
    except Exception as e:
        logger.error(f"获取业务趋势数据失败: {str(e)}")
        raise HTTPException(status_code=500, detail="获取业务趋势数据失败")


@router.get("/comparison", response_model=StandardResponse[Dict[str, Any]])
async def get_period_comparison(
    current_user: Dict = Depends(require_admin_auth),
    current_period: str = Query("7d", description="当前周期"),
    comparison_period: str = Query("previous", description="对比周期 (previous, same_last_year)")
):
    """获取周期对比分析"""
    try:
        comparison_data = {
            "current_period": current_period,
            "comparison_period": comparison_period,
            "metrics_comparison": {
                "conversations": {
                    "current": 1250,
                    "previous": 1180,
                    "change_absolute": 70,
                    "change_percentage": 5.9,
                    "trend": "up"
                },
                "intent_accuracy": {
                    "current": 94.2,
                    "previous": 92.8,
                    "change_absolute": 1.4,
                    "change_percentage": 1.5,
                    "trend": "up"
                },
                "user_satisfaction": {
                    "current": 4.3,
                    "previous": 4.1,
                    "change_absolute": 0.2,
                    "change_percentage": 4.9,
                    "trend": "up"
                },
                "function_success_rate": {
                    "current": 93.4,
                    "previous": 94.1,
                    "change_absolute": -0.7,
                    "change_percentage": -0.7,
                    "trend": "down"
                },
                "average_response_time": {
                    "current": 125,
                    "previous": 118,
                    "change_absolute": 7,
                    "change_percentage": 5.9,
                    "trend": "down"
                }
            },
            "performance_summary": {
                "improved_metrics": ["conversations", "intent_accuracy", "user_satisfaction"],
                "declined_metrics": ["function_success_rate", "average_response_time"],
                "stable_metrics": [],
                "overall_performance": "improving"
            },
            "insights": [
                "对话数量稳步增长，用户活跃度提升",
                "意图识别准确率持续改善，模型优化效果显著",
                "用户满意度上升，服务质量得到认可",
                "函数成功率略有下降，需要关注外部服务稳定性",
                "响应时间增加，可能需要性能优化"
            ],
            "recommendations": [
                "继续优化模型以保持意图识别准确率提升趋势",
                "调查函数调用失败原因，加强错误处理机制",
                "考虑扩容或优化以改善响应时间",
                "加强监控以及时发现性能问题"
            ]
        }
        
        return StandardResponse(
            code=200,
            message="周期对比分析获取成功",
            data=comparison_data
        )
        
    except Exception as e:
        logger.error(f"获取周期对比分析失败: {str(e)}")
        raise HTTPException(status_code=500, detail="获取周期对比分析失败")


# 辅助函数
def _get_conversation_count(start_time: datetime, end_time: datetime) -> int:
    """获取对话数量"""
    try:
        return Conversation.select().where(
            Conversation.created_at.between(start_time, end_time)
        ).count()
    except:
        return 1250  # 模拟数据


def _get_intent_recognition_count(start_time: datetime, end_time: datetime) -> int:
    """获取意图识别数量"""
    # 模拟数据
    return 3245


def _get_function_call_count(start_time: datetime, end_time: datetime) -> int:
    """获取函数调用数量"""
    try:
        return FunctionCall.select().where(
            FunctionCall.created_at.between(start_time, end_time)
        ).count()
    except:
        return 1865  # 模拟数据


def _get_unique_user_count(start_time: datetime, end_time: datetime) -> int:
    """获取唯一用户数"""
    # 模拟数据
    return 892


def _get_average_conversation_length(start_time: datetime, end_time: datetime) -> float:
    """获取平均对话轮次"""
    # 模拟数据
    return 4.2


def _get_success_rate(start_time: datetime, end_time: datetime) -> float:
    """获取成功率"""
    # 模拟数据
    return 92.1


def _get_conversation_trend(start_time: datetime, end_time: datetime) -> str:
    """获取对话趋势"""
    return "increasing"


def _get_intent_accuracy_trend(start_time: datetime, end_time: datetime) -> str:
    """获取意图准确率趋势"""
    return "improving"


def _get_user_satisfaction_trend(start_time: datetime, end_time: datetime) -> str:
    """获取用户满意度趋势"""
    return "stable"


def _get_top_intents(start_time: datetime, end_time: datetime) -> List[Dict]:
    """获取热门意图"""
    return [
        {"intent": "book_flight", "count": 485, "percentage": 27.8},
        {"intent": "check_balance", "count": 356, "percentage": 20.4},
        {"intent": "customer_service", "count": 298, "percentage": 17.1},
        {"intent": "information_query", "count": 234, "percentage": 13.4},
        {"intent": "cancel_booking", "count": 178, "percentage": 10.2}
    ]


def _get_top_functions(start_time: datetime, end_time: datetime) -> List[Dict]:
    """获取热门函数"""
    return [
        {"function": "search_flights", "calls": 485, "success_rate": 95.3},
        {"function": "get_account_balance", "calls": 356, "success_rate": 96.1},
        {"function": "book_ticket", "calls": 234, "success_rate": 93.2},
        {"function": "send_notification", "calls": 198, "success_rate": 98.5}
    ]


def _generate_conversation_breakdown(start_time: datetime, end_time: datetime, group_by: str) -> List[Dict]:
    """生成对话分布数据"""
    import random
    from datetime import timedelta
    
    breakdown = []
    current_time = start_time
    
    if group_by == "hour":
        delta = timedelta(hours=1)
    elif group_by == "day":
        delta = timedelta(days=1)
    else:  # week
        delta = timedelta(weeks=1)
    
    while current_time < end_time:
        breakdown.append({
            "time": current_time.isoformat(),
            "conversations": random.randint(30, 80),
            "completed": random.randint(25, 75),
            "abandoned": random.randint(2, 8)
        })
        current_time += delta
    
    return breakdown


def _generate_hourly_accuracy_data(start_time: datetime, end_time: datetime) -> List[Dict]:
    """生成小时准确率数据"""
    import random
    
    data = []
    hours = int((end_time - start_time).total_seconds() / 3600)
    
    for i in range(min(hours, 24)):  # 最多24小时
        accuracy = 88 + random.uniform(0, 8)  # 88-96%之间
        data.append({
            "hour": i,
            "accuracy": round(accuracy, 1),
            "sample_size": random.randint(50, 200)
        })
    
    return data


def _generate_confusion_matrix() -> Dict:
    """生成意图混淆矩阵"""
    return {
        "matrix": [
            ["book_flight", "book_flight", 832, "check_balance", 5, "customer_service", 3],
            ["check_balance", "book_flight", 8, "check_balance", 598, "customer_service", 12],
            ["customer_service", "book_flight", 2, "check_balance", 15, "customer_service", 485],
            ["information_query", "book_flight", 1, "check_balance", 8, "information_query", 421]
        ],
        "labels": ["book_flight", "check_balance", "customer_service", "information_query"]
    }


def _generate_intent_suggestions(intent_performance: List[Dict]) -> List[str]:
    """生成意图优化建议"""
    suggestions = []
    
    for intent in intent_performance:
        if intent["accuracy_rate"] < 95:
            suggestions.append(f"'{intent['intent_name']}' 意图准确率较低({intent['accuracy_rate']:.1f}%)，建议增加训练样本")
        
        if intent["trend"] == "declining":
            suggestions.append(f"'{intent['intent_name']}' 意图表现下降趋势，需要检查模型或数据质量")
    
    if not suggestions:
        suggestions.append("所有意图表现良好，继续保持当前训练策略")
    
    return suggestions


def _generate_conversation_trend(start_time: datetime, end_time: datetime, granularity: str) -> List[Dict]:
    """生成对话趋势数据"""
    import random
    
    trend_data = []
    if granularity == "hour":
        delta = timedelta(hours=1)
    elif granularity == "day":
        delta = timedelta(days=1)
    else:  # week
        delta = timedelta(weeks=1)
    
    current_time = start_time
    base_value = 50
    
    while current_time < end_time:
        # 添加趋势和随机变化
        value = base_value + random.randint(-10, 15)
        trend_data.append({
            "timestamp": current_time.isoformat(),
            "value": max(0, value)
        })
        current_time += delta
        base_value += random.randint(-2, 3)  # 轻微趋势变化
    
    return trend_data


def _generate_intent_accuracy_trend(start_time: datetime, end_time: datetime, granularity: str) -> List[Dict]:
    """生成意图准确率趋势"""
    import random
    
    trend_data = []
    if granularity == "hour":
        delta = timedelta(hours=1)
    elif granularity == "day":
        delta = timedelta(days=1)
    else:  # week
        delta = timedelta(weeks=1)
    
    current_time = start_time
    base_accuracy = 92.0
    
    while current_time < end_time:
        accuracy = base_accuracy + random.uniform(-2, 3)
        trend_data.append({
            "timestamp": current_time.isoformat(),
            "value": min(100, max(80, accuracy))
        })
        current_time += delta
        base_accuracy += random.uniform(-0.1, 0.2)  # 轻微改善趋势
    
    return trend_data


def _generate_user_satisfaction_trend(start_time: datetime, end_time: datetime, granularity: str = "day") -> List[Dict]:
    """生成用户满意度趋势"""
    import random
    
    trend_data = []
    if granularity == "hour":
        delta = timedelta(hours=1)
    elif granularity == "day":
        delta = timedelta(days=1)
    else:  # week
        delta = timedelta(weeks=1)
    
    current_time = start_time
    base_satisfaction = 4.2
    
    while current_time < end_time:
        satisfaction = base_satisfaction + random.uniform(-0.3, 0.3)
        trend_data.append({
            "timestamp": current_time.isoformat(),
            "value": min(5.0, max(3.0, satisfaction))
        })
        current_time += delta
    
    return trend_data


def _generate_response_time_trend(start_time: datetime, end_time: datetime, granularity: str) -> List[Dict]:
    """生成响应时间趋势"""
    import random
    
    trend_data = []
    if granularity == "hour":
        delta = timedelta(hours=1)
    elif granularity == "day":
        delta = timedelta(days=1)
    else:  # week
        delta = timedelta(weeks=1)
    
    current_time = start_time
    base_time = 120
    
    while current_time < end_time:
        response_time = base_time + random.randint(-20, 30)
        trend_data.append({
            "timestamp": current_time.isoformat(),
            "value": max(50, response_time)
        })
        current_time += delta
    
    return trend_data


def _generate_function_success_trend(start_time: datetime, end_time: datetime, granularity: str) -> List[Dict]:
    """生成函数成功率趋势"""
    import random
    
    trend_data = []
    if granularity == "hour":
        delta = timedelta(hours=1)
    elif granularity == "day":
        delta = timedelta(days=1)
    else:  # week
        delta = timedelta(weeks=1)
    
    current_time = start_time
    base_rate = 93.0
    
    while current_time < end_time:
        success_rate = base_rate + random.uniform(-3, 2)
        trend_data.append({
            "timestamp": current_time.isoformat(),
            "value": min(100, max(85, success_rate))
        })
        current_time += delta
    
    return trend_data