"""
分析和监控API
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta

from src.api.dependencies import require_admin_auth, get_cache_service_dependency
from src.schemas.common import StandardResponse
from src.models.conversation import Session, Conversation
from src.models.intent import Intent
from src.models.function import FunctionCall
from src.models.audit import PerformanceLog
from src.utils.logger import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/analytics", tags=["分析监控"])


@router.get("/conversations", response_model=StandardResponse[Dict[str, Any]])
async def get_conversations(
    user_id: Optional[str] = Query(None, description="用户ID"),
    request_id: Optional[str] = Query(None, description="请求ID"),
    intent: Optional[str] = Query(None, description="意图名称"),
    start_date: Optional[str] = Query(None, description="开始日期 YYYY-MM-DD"),
    end_date: Optional[str] = Query(None, description="结束日期 YYYY-MM-DD"),
    page: int = Query(1, ge=1, description="页码"),
    size: int = Query(10, ge=1, le=100, description="每页大小"),
    current_user: Dict = Depends(require_admin_auth)
):
    """查询对话历史记录
    
    Returns:
        Dict: 对话历史列表和分页信息
    """
    try:
        # 构建查询条件
        query = Conversation.select().join(Session)
        conditions = []
        
        if user_id:
            conditions.append(Session.user_id == user_id)
        
        if request_id:
            conditions.append(Conversation.request_id == request_id)
        
        if intent:
            conditions.append(Conversation.intent == intent)
        
        if start_date:
            start_dt = datetime.fromisoformat(start_date)
            conditions.append(Conversation.created_at >= start_dt)
        
        if end_date:
            end_dt = datetime.fromisoformat(end_date)
            conditions.append(Conversation.created_at <= end_dt)
        
        if conditions:
            query = query.where(*conditions)
        
        # 计算总数
        total = query.count()
        
        # 分页查询
        offset = (page - 1) * size
        conversations = (query
                        .order_by(Conversation.created_at.desc())
                        .offset(offset)
                        .limit(size))
        
        # 构建响应数据
        conversation_list = []
        for conv in conversations:
            conversation_data = {
                "id": conv.id,
                "session_id": conv.session.session_id,
                "user_id": conv.session.user_id,
                "request_id": conv.request_id,
                "user_input": conv.user_input,
                "intent": conv.intent,
                "confidence": float(conv.confidence) if conv.confidence else 0.0,
                "slots": conv.get_slots(),
                "response": conv.get_response(),
                "response_type": conv.response_type,
                "processing_time_ms": conv.processing_time_ms,
                "created_at": conv.created_at.isoformat(),
                "status": conv.status
            }
            conversation_list.append(conversation_data)
        
        response_data = {
            "conversations": conversation_list,
            "pagination": {
                "page": page,
                "size": size,
                "total": total,
                "pages": (total + size - 1) // size
            },
            "summary": {
                "total_conversations": total,
                "date_range": {
                    "start": start_date,
                    "end": end_date
                }
            }
        }
        
        return StandardResponse(
            code=200,
            message="对话历史查询成功",
            data=response_data
        )
        
    except Exception as e:
        logger.error(f"查询对话历史失败: {str(e)}")
        raise HTTPException(status_code=500, detail="查询对话历史失败")


@router.get("/intent-stats", response_model=StandardResponse[Dict[str, Any]])
async def get_intent_stats(
    date_range: str = Query("week", description="日期范围: today, week, month"),
    intent: Optional[str] = Query(None, description="特定意图名称"),
    group_by: str = Query("day", description="分组方式: day, hour, intent"),
    current_user: Dict = Depends(require_admin_auth)
):
    """获取意图识别统计数据
    
    Returns:
        Dict: 意图统计信息
    """
    try:
        # 计算时间范围
        now = datetime.now()
        if date_range == "today":
            start_date = now.replace(hour=0, minute=0, second=0, microsecond=0)
        elif date_range == "week":
            start_date = now - timedelta(days=7)
        elif date_range == "month":
            start_date = now - timedelta(days=30)
        else:
            start_date = now - timedelta(days=7)  # 默认一周
        
        # 构建基础查询
        query = Conversation.select().where(
            Conversation.created_at >= start_date
        )
        
        if intent:
            query = query.where(Conversation.intent == intent)
        
        # 执行统计查询
        conversations = list(query)
        
        # 基础统计
        total_requests = len(conversations)
        successful_recognitions = len([c for c in conversations if c.intent and c.intent != 'unknown'])
        failed_recognitions = total_requests - successful_recognitions
        
        # 意图分布统计
        intent_distribution = {}
        confidence_stats = []
        
        for conv in conversations:
            intent_name = conv.intent or 'unknown'
            if intent_name not in intent_distribution:
                intent_distribution[intent_name] = {
                    'count': 0,
                    'avg_confidence': 0.0,
                    'total_confidence': 0.0
                }
            
            intent_distribution[intent_name]['count'] += 1
            conf = float(conv.confidence) if conv.confidence else 0.0
            intent_distribution[intent_name]['total_confidence'] += conf
            confidence_stats.append(conf)
        
        # 计算平均置信度
        for intent_name, stats in intent_distribution.items():
            if stats['count'] > 0:
                stats['avg_confidence'] = stats['total_confidence'] / stats['count']
            del stats['total_confidence']  # 移除临时字段
        
        # 时间分组统计
        time_series = {}
        if group_by == "day":
            for conv in conversations:
                day_key = conv.created_at.strftime('%Y-%m-%d')
                if day_key not in time_series:
                    time_series[day_key] = {'total': 0, 'successful': 0}
                time_series[day_key]['total'] += 1
                if conv.intent and conv.intent != 'unknown':
                    time_series[day_key]['successful'] += 1
        
        elif group_by == "hour":
            for conv in conversations:
                hour_key = conv.created_at.strftime('%Y-%m-%d %H:00')
                if hour_key not in time_series:
                    time_series[hour_key] = {'total': 0, 'successful': 0}
                time_series[hour_key]['total'] += 1
                if conv.intent and conv.intent != 'unknown':
                    time_series[hour_key]['successful'] += 1
        
        # 计算平均置信度
        avg_confidence = sum(confidence_stats) / len(confidence_stats) if confidence_stats else 0.0
        
        # 成功率计算
        success_rate = (successful_recognitions / total_requests) if total_requests > 0 else 0.0
        
        response_data = {
            "summary": {
                "total_requests": total_requests,
                "successful_recognitions": successful_recognitions,
                "failed_recognitions": failed_recognitions,
                "success_rate": round(success_rate, 4),
                "avg_confidence": round(avg_confidence, 4),
                "date_range": date_range,
                "start_date": start_date.isoformat(),
                "end_date": now.isoformat()
            },
            "intent_distribution": intent_distribution,
            "time_series": time_series,
            "top_intents": sorted(
                intent_distribution.items(),
                key=lambda x: x[1]['count'],
                reverse=True
            )[:10]
        }
        
        return StandardResponse(
            code=200,
            message="意图统计获取成功",
            data=response_data
        )
        
    except Exception as e:
        logger.error(f"获取意图统计失败: {str(e)}")
        raise HTTPException(status_code=500, detail="获取意图统计失败")


@router.get("/performance", response_model=StandardResponse[Dict[str, Any]])
async def get_performance_stats(
    hours: int = Query(24, ge=1, le=168, description="统计小时数"),
    current_user: Dict = Depends(require_admin_auth)
):
    """获取系统性能指标
    
    Returns:
        Dict: 系统性能统计
    """
    try:
        # 计算时间范围
        end_time = datetime.now()
        start_time = end_time - timedelta(hours=hours)
        
        # 查询性能日志
        perf_logs = list(PerformanceLog.select().where(
            PerformanceLog.created_at >= start_time
        ))
        
        if not perf_logs:
            return StandardResponse(
                code=200,
                message="暂无性能数据",
                data={
                    "summary": {
                        "total_requests": 0,
                        "avg_response_time": 0,
                        "min_response_time": 0,
                        "max_response_time": 0,
                        "error_rate": 0,
                        "throughput": 0
                    },
                    "endpoint_stats": {},
                    "time_series": []
                }
            )
        
        # 基础统计
        total_requests = len(perf_logs)
        response_times = [log.response_time_ms for log in perf_logs]
        error_count = len([log for log in perf_logs if log.status_code >= 400])
        
        avg_response_time = sum(response_times) / len(response_times)
        min_response_time = min(response_times)
        max_response_time = max(response_times)
        error_rate = error_count / total_requests if total_requests > 0 else 0
        throughput = total_requests / hours  # 每小时请求数
        
        # 端点统计
        endpoint_stats = {}
        for log in perf_logs:
            endpoint = f"{log.method} {log.endpoint}"
            if endpoint not in endpoint_stats:
                endpoint_stats[endpoint] = {
                    'count': 0,
                    'avg_response_time': 0,
                    'min_response_time': float('inf'),
                    'max_response_time': 0,
                    'error_count': 0,
                    'total_response_time': 0
                }
            
            stats = endpoint_stats[endpoint]
            stats['count'] += 1
            stats['total_response_time'] += log.response_time_ms
            stats['min_response_time'] = min(stats['min_response_time'], log.response_time_ms)
            stats['max_response_time'] = max(stats['max_response_time'], log.response_time_ms)
            
            if log.status_code >= 400:
                stats['error_count'] += 1
        
        # 计算端点平均响应时间和错误率
        for endpoint, stats in endpoint_stats.items():
            stats['avg_response_time'] = stats['total_response_time'] / stats['count']
            stats['error_rate'] = stats['error_count'] / stats['count']
            del stats['total_response_time']  # 移除临时字段
        
        # 时间序列统计（每小时）
        time_series = {}
        for log in perf_logs:
            hour_key = log.created_at.strftime('%Y-%m-%d %H:00')
            if hour_key not in time_series:
                time_series[hour_key] = {
                    'requests': 0,
                    'errors': 0,
                    'total_response_time': 0,
                    'min_response_time': float('inf'),
                    'max_response_time': 0
                }
            
            series = time_series[hour_key]
            series['requests'] += 1
            series['total_response_time'] += log.response_time_ms
            series['min_response_time'] = min(series['min_response_time'], log.response_time_ms)
            series['max_response_time'] = max(series['max_response_time'], log.response_time_ms)
            
            if log.status_code >= 400:
                series['errors'] += 1
        
        # 计算时间序列平均值
        time_series_list = []
        for time_key in sorted(time_series.keys()):
            series = time_series[time_key]
            time_series_list.append({
                'timestamp': time_key,
                'requests': series['requests'],
                'errors': series['errors'],
                'avg_response_time': series['total_response_time'] / series['requests'],
                'min_response_time': series['min_response_time'],
                'max_response_time': series['max_response_time'],
                'error_rate': series['errors'] / series['requests']
            })
        
        # 慢请求统计
        slow_requests = [log for log in perf_logs if log.response_time_ms > 2000]
        
        response_data = {
            "summary": {
                "total_requests": total_requests,
                "avg_response_time": round(avg_response_time, 2),
                "min_response_time": min_response_time,
                "max_response_time": max_response_time,
                "error_rate": round(error_rate, 4),
                "error_count": error_count,
                "throughput": round(throughput, 2),
                "slow_requests": len(slow_requests),
                "time_range_hours": hours,
                "start_time": start_time.isoformat(),
                "end_time": end_time.isoformat()
            },
            "endpoint_stats": dict(sorted(
                endpoint_stats.items(),
                key=lambda x: x[1]['count'],
                reverse=True
            )),
            "time_series": time_series_list,
            "slow_requests": [
                {
                    "endpoint": f"{log.method} {log.endpoint}",
                    "response_time": log.response_time_ms,
                    "timestamp": log.created_at.isoformat(),
                    "user_id": log.user_id
                }
                for log in sorted(slow_requests, key=lambda x: x.response_time_ms, reverse=True)[:10]
            ]
        }
        
        return StandardResponse(
            code=200,
            message="性能统计获取成功",
            data=response_data
        )
        
    except Exception as e:
        logger.error(f"获取性能统计失败: {str(e)}")
        raise HTTPException(status_code=500, detail="获取性能统计失败")


@router.get("/user-behavior", response_model=StandardResponse[Dict[str, Any]])
async def get_user_behavior_stats(
    user_id: Optional[str] = Query(None, description="特定用户ID"),
    days: int = Query(7, ge=1, le=30, description="统计天数"),
    current_user: Dict = Depends(require_admin_auth)
):
    """获取用户行为统计
    
    Returns:
        Dict: 用户行为分析数据
    """
    try:
        # 计算时间范围
        end_time = datetime.now()
        start_time = end_time - timedelta(days=days)
        
        # 构建查询
        query = (Conversation
                .select()
                .join(Session)
                .where(Conversation.created_at >= start_time))
        
        if user_id:
            query = query.where(Session.user_id == user_id)
        
        conversations = list(query)
        
        # 用户统计
        user_stats = {}
        intent_preferences = {}
        session_stats = {}
        
        for conv in conversations:
            uid = conv.session.user_id
            session_id = conv.session.session_id
            
            # 用户统计
            if uid not in user_stats:
                user_stats[uid] = {
                    'total_interactions': 0,
                    'unique_sessions': set(),
                    'successful_intents': 0,
                    'failed_intents': 0,
                    'avg_confidence': 0,
                    'total_confidence': 0,
                    'first_interaction': conv.created_at,
                    'last_interaction': conv.created_at,
                    'preferred_intents': {}
                }
            
            stats = user_stats[uid]
            stats['total_interactions'] += 1
            stats['unique_sessions'].add(session_id)
            stats['last_interaction'] = max(stats['last_interaction'], conv.created_at)
            stats['first_interaction'] = min(stats['first_interaction'], conv.created_at)
            
            # 意图统计
            if conv.intent and conv.intent != 'unknown':
                stats['successful_intents'] += 1
                intent_name = conv.intent
                if intent_name not in stats['preferred_intents']:
                    stats['preferred_intents'][intent_name] = 0
                stats['preferred_intents'][intent_name] += 1
            else:
                stats['failed_intents'] += 1
            
            # 置信度统计
            conf = float(conv.confidence) if conv.confidence else 0.0
            stats['total_confidence'] += conf
            
            # 会话统计
            if session_id not in session_stats:
                session_stats[session_id] = {
                    'user_id': uid,
                    'interactions': 0,
                    'duration_minutes': 0,
                    'start_time': conv.created_at,
                    'end_time': conv.created_at
                }
            
            session_stats[session_id]['interactions'] += 1
            session_stats[session_id]['end_time'] = max(
                session_stats[session_id]['end_time'], 
                conv.created_at
            )
        
        # 计算平均值和会话时长
        for uid, stats in user_stats.items():
            if stats['total_interactions'] > 0:
                stats['avg_confidence'] = stats['total_confidence'] / stats['total_interactions']
            stats['unique_sessions'] = len(stats['unique_sessions'])
            del stats['total_confidence']  # 移除临时字段
            
            # 格式化日期
            stats['first_interaction'] = stats['first_interaction'].isoformat()
            stats['last_interaction'] = stats['last_interaction'].isoformat()
        
        # 计算会话时长
        for session_id, session in session_stats.items():
            duration = session['end_time'] - session['start_time']
            session['duration_minutes'] = duration.total_seconds() / 60
            session['start_time'] = session['start_time'].isoformat()
            session['end_time'] = session['end_time'].isoformat()
        
        # 全局意图偏好统计
        global_intent_preferences = {}
        for conv in conversations:
            if conv.intent and conv.intent != 'unknown':
                if conv.intent not in global_intent_preferences:
                    global_intent_preferences[conv.intent] = 0
                global_intent_preferences[conv.intent] += 1
        
        # 活跃用户统计
        active_users = len(user_stats)
        avg_interactions_per_user = (
            sum(stats['total_interactions'] for stats in user_stats.values()) / active_users
            if active_users > 0 else 0
        )
        
        response_data = {
            "summary": {
                "total_users": active_users,
                "total_interactions": len(conversations),
                "total_sessions": len(session_stats),
                "avg_interactions_per_user": round(avg_interactions_per_user, 2),
                "avg_session_duration_minutes": round(
                    sum(s['duration_minutes'] for s in session_stats.values()) / len(session_stats)
                    if session_stats else 0, 2
                ),
                "time_range_days": days,
                "start_date": start_time.isoformat(),
                "end_date": end_time.isoformat()
            },
            "user_stats": dict(sorted(
                user_stats.items(),
                key=lambda x: x[1]['total_interactions'],
                reverse=True
            )) if not user_id else user_stats,
            "global_intent_preferences": dict(sorted(
                global_intent_preferences.items(),
                key=lambda x: x[1],
                reverse=True
            )),
            "session_stats": dict(sorted(
                session_stats.items(),
                key=lambda x: x[1]['interactions'],
                reverse=True
            )[:20])  # 只返回前20个会话
        }
        
        return StandardResponse(
            code=200,
            message="用户行为统计获取成功",
            data=response_data
        )
        
    except Exception as e:
        logger.error(f"获取用户行为统计失败: {str(e)}")
        raise HTTPException(status_code=500, detail="获取用户行为统计失败")


@router.get("/function-calls", response_model=StandardResponse[Dict[str, Any]])
async def get_function_call_stats(
    function_name: Optional[str] = Query(None, description="功能名称"),
    days: int = Query(7, ge=1, le=30, description="统计天数"),
    current_user: Dict = Depends(require_admin_auth)
):
    """获取功能调用统计
    
    Returns:
        Dict: 功能调用分析数据
    """
    try:
        # 计算时间范围
        end_time = datetime.now()
        start_time = end_time - timedelta(days=days)
        
        # 构建查询
        query = (FunctionCall
                .select()
                .where(FunctionCall.created_at >= start_time))
        
        if function_name:
            query = query.where(FunctionCall.function.function_name == function_name)
        
        function_calls = list(query)
        
        # 功能调用统计
        function_stats = {}
        for call in function_calls:
            func_name = call.function.function_name
            
            if func_name not in function_stats:
                function_stats[func_name] = {
                    'total_calls': 0,
                    'successful_calls': 0,
                    'failed_calls': 0,
                    'avg_execution_time': 0,
                    'min_execution_time': float('inf'),
                    'max_execution_time': 0,
                    'total_execution_time': 0,
                    'error_types': {}
                }
            
            stats = function_stats[func_name]
            stats['total_calls'] += 1
            
            if call.status == 'completed':
                stats['successful_calls'] += 1
            else:
                stats['failed_calls'] += 1
                error_type = call.error_message[:50] if call.error_message else 'Unknown'
                if error_type not in stats['error_types']:
                    stats['error_types'][error_type] = 0
                stats['error_types'][error_type] += 1
            
            # 执行时间统计
            if call.execution_time:
                exec_time = call.execution_time
                stats['total_execution_time'] += exec_time
                stats['min_execution_time'] = min(stats['min_execution_time'], exec_time)
                stats['max_execution_time'] = max(stats['max_execution_time'], exec_time)
        
        # 计算平均执行时间
        for func_name, stats in function_stats.items():
            if stats['successful_calls'] > 0:
                stats['avg_execution_time'] = stats['total_execution_time'] / stats['successful_calls']
                stats['success_rate'] = stats['successful_calls'] / stats['total_calls']
            else:
                stats['avg_execution_time'] = 0
                stats['success_rate'] = 0
            
            if stats['min_execution_time'] == float('inf'):
                stats['min_execution_time'] = 0
            
            del stats['total_execution_time']  # 移除临时字段
        
        # 时间序列统计
        daily_stats = {}
        for call in function_calls:
            day_key = call.created_at.strftime('%Y-%m-%d')
            if day_key not in daily_stats:
                daily_stats[day_key] = {
                    'total_calls': 0,
                    'successful_calls': 0,
                    'failed_calls': 0
                }
            
            daily_stats[day_key]['total_calls'] += 1
            if call.status == 'completed':
                daily_stats[day_key]['successful_calls'] += 1
            else:
                daily_stats[day_key]['failed_calls'] += 1
        
        # 转换为列表格式
        time_series = []
        for day_key in sorted(daily_stats.keys()):
            stats = daily_stats[day_key]
            time_series.append({
                'date': day_key,
                'total_calls': stats['total_calls'],
                'successful_calls': stats['successful_calls'],
                'failed_calls': stats['failed_calls'],
                'success_rate': (
                    stats['successful_calls'] / stats['total_calls']
                    if stats['total_calls'] > 0 else 0
                )
            })
        
        # 总体统计
        total_calls = len(function_calls)
        successful_calls = len([c for c in function_calls if c.status == 'completed'])
        overall_success_rate = successful_calls / total_calls if total_calls > 0 else 0
        
        response_data = {
            "summary": {
                "total_calls": total_calls,
                "successful_calls": successful_calls,
                "failed_calls": total_calls - successful_calls,
                "overall_success_rate": round(overall_success_rate, 4),
                "unique_functions": len(function_stats),
                "time_range_days": days,
                "start_date": start_time.isoformat(),
                "end_date": end_time.isoformat()
            },
            "function_stats": dict(sorted(
                function_stats.items(),
                key=lambda x: x[1]['total_calls'],
                reverse=True
            )),
            "time_series": time_series,
            "top_errors": self._get_top_errors(function_calls)
        }
        
        return StandardResponse(
            code=200,
            message="功能调用统计获取成功",
            data=response_data
        )
        
    except Exception as e:
        logger.error(f"获取功能调用统计失败: {str(e)}")
        raise HTTPException(status_code=500, detail="获取功能调用统计失败")


def _get_top_errors(function_calls: List[FunctionCall]) -> List[Dict[str, Any]]:
    """获取错误排行榜"""
    error_counts = {}
    
    for call in function_calls:
        if call.status != 'completed' and call.error_message:
            error_msg = call.error_message[:100]  # 截取前100字符
            if error_msg not in error_counts:
                error_counts[error_msg] = {
                    'count': 0,
                    'functions': set(),
                    'last_occurrence': call.created_at
                }
            
            error_counts[error_msg]['count'] += 1
            error_counts[error_msg]['functions'].add(call.function.function_name)
            error_counts[error_msg]['last_occurrence'] = max(
                error_counts[error_msg]['last_occurrence'],
                call.created_at
            )
    
    # 转换为列表并排序
    top_errors = []
    for error_msg, data in sorted(error_counts.items(), key=lambda x: x[1]['count'], reverse=True)[:10]:
        top_errors.append({
            'error_message': error_msg,
            'count': data['count'],
            'affected_functions': list(data['functions']),
            'last_occurrence': data['last_occurrence'].isoformat()
        })
    
    return top_errors