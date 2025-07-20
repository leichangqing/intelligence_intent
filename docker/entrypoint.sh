#!/bin/bash
# ============================================================================
# 生产环境启动脚本 - TASK-054
# 智能意图识别系统的Docker容器启动脚本
# ============================================================================

set -e

# ============================================================================
# 环境变量配置
# ============================================================================
export APP_ENV=${APP_ENV:-production}
export LOG_LEVEL=${LOG_LEVEL:-INFO}
export MAX_WORKERS=${MAX_WORKERS:-4}
export TIMEOUT=${TIMEOUT:-120}
export KEEP_ALIVE=${KEEP_ALIVE:-2}

# ============================================================================
# 颜色输出函数
# ============================================================================
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

log_debug() {
    if [[ "${LOG_LEVEL}" == "DEBUG" ]]; then
        echo -e "${BLUE}[DEBUG]${NC} $1"
    fi
}

# ============================================================================
# 健康检查函数
# ============================================================================
check_database_connection() {
    log_info "检查数据库连接..."
    
    local max_attempts=30
    local attempt=1
    
    while [ $attempt -le $max_attempts ]; do
        if python -c "
import sys
import os
sys.path.append('/app/src')
from config.database import test_connection
if test_connection():
    print('Database connection successful')
    sys.exit(0)
else:
    sys.exit(1)
" 2>/dev/null; then
            log_info "数据库连接成功"
            return 0
        fi
        
        log_warn "数据库连接失败 (尝试 $attempt/$max_attempts)"
        sleep 2
        ((attempt++))
    done
    
    log_error "数据库连接失败，已超过最大重试次数"
    return 1
}

check_redis_connection() {
    log_info "检查Redis连接..."
    
    if python -c "
import sys
import os
sys.path.append('/app/src')
from services.cache_service import CacheService
import asyncio

async def test_redis():
    cache = CacheService()
    try:
        await cache.initialize()
        await cache.set('health_check', 'ok', ttl=10)
        result = await cache.get('health_check')
        return result == 'ok'
    except Exception:
        return False

result = asyncio.run(test_redis())
sys.exit(0 if result else 1)
" 2>/dev/null; then
        log_info "Redis连接成功"
        return 0
    else
        log_error "Redis连接失败"
        return 1
    fi
}

# ============================================================================
# 数据库迁移
# ============================================================================
run_database_migrations() {
    log_info "运行数据库迁移..."
    
    # 检查是否需要运行迁移
    if [ "${SKIP_MIGRATIONS:-false}" = "true" ]; then
        log_info "跳过数据库迁移 (SKIP_MIGRATIONS=true)"
        return 0
    fi
    
    # 运行Alembic迁移
    if [ -f "alembic.ini" ]; then
        log_info "执行Alembic数据库迁移..."
        python -m alembic upgrade head
        if [ $? -eq 0 ]; then
            log_info "数据库迁移完成"
        else
            log_error "数据库迁移失败"
            return 1
        fi
    else
        log_warn "未找到alembic.ini，跳过数据库迁移"
    fi
}

# ============================================================================
# 初始化数据
# ============================================================================
initialize_data() {
    log_info "初始化系统数据..."
    
    if [ "${SKIP_INIT_DATA:-false}" = "true" ]; then
        log_info "跳过数据初始化 (SKIP_INIT_DATA=true)"
        return 0
    fi
    
    # 运行初始化脚本
    if [ -f "scripts/init_database.py" ]; then
        log_info "执行数据初始化脚本..."
        python scripts/init_database.py
        if [ $? -eq 0 ]; then
            log_info "数据初始化完成"
        else
            log_warn "数据初始化失败，可能数据已存在"
        fi
    fi
}

# ============================================================================
# 缓存预热
# ============================================================================
warm_up_cache() {
    log_info "预热缓存..."
    
    if [ "${SKIP_CACHE_WARMUP:-false}" = "true" ]; then
        log_info "跳过缓存预热 (SKIP_CACHE_WARMUP=true)"
        return 0
    fi
    
    # 运行缓存预热脚本
    if [ -f "scripts/warm_up_cache.py" ]; then
        log_info "执行缓存预热脚本..."
        python scripts/warm_up_cache.py
        if [ $? -eq 0 ]; then
            log_info "缓存预热完成"
        else
            log_warn "缓存预热失败"
        fi
    fi
}

# ============================================================================
# 系统优化
# ============================================================================
optimize_system() {
    log_info "应用系统优化配置..."
    
    # Python优化
    export PYTHONHASHSEED=0
    export PYTHONOPTIMIZE=1
    
    # 内存优化
    if [ -n "${MALLOC_TRIM_THRESHOLD}" ]; then
        export MALLOC_TRIM_THRESHOLD_=${MALLOC_TRIM_THRESHOLD}
    fi
    
    # 确保日志目录存在
    mkdir -p /app/logs /app/data /app/tmp
    
    log_info "系统优化配置完成"
}

# ============================================================================
# 信号处理
# ============================================================================
cleanup() {
    log_info "接收到停止信号，正在优雅关闭..."
    
    # 如果Uvicorn进程存在，发送SIGTERM信号
    if [ ! -z "$UVICORN_PID" ]; then
        kill -TERM "$UVICORN_PID" 2>/dev/null || true
        wait "$UVICORN_PID" 2>/dev/null || true
    fi
    
    log_info "应用已优雅关闭"
    exit 0
}

# 注册信号处理器
trap cleanup SIGTERM SIGINT

# ============================================================================
# 主启动流程
# ============================================================================
main() {
    log_info "启动智能意图识别系统 (环境: ${APP_ENV})"
    log_info "工作目录: $(pwd)"
    log_info "Python版本: $(python --version)"
    log_info "用户: $(whoami)"
    
    # 系统优化
    optimize_system
    
    # 健康检查
    if ! check_database_connection; then
        log_error "数据库连接检查失败，退出启动"
        exit 1
    fi
    
    if ! check_redis_connection; then
        log_error "Redis连接检查失败，退出启动"
        exit 1
    fi
    
    # 数据库迁移
    if ! run_database_migrations; then
        log_error "数据库迁移失败，退出启动"
        exit 1
    fi
    
    # 初始化数据
    initialize_data
    
    # 缓存预热
    warm_up_cache
    
    log_info "所有初始化步骤完成，启动应用服务器..."
    
    # 根据环境选择启动方式
    if [ "${APP_ENV}" = "development" ]; then
        log_info "启动开发模式服务器 (热重载已启用)"
        exec uvicorn src.main:app \
            --host 0.0.0.0 \
            --port 8000 \
            --reload \
            --log-level "${LOG_LEVEL,,}" \
            --access-log
    else
        log_info "启动生产模式服务器"
        log_info "工作进程数: ${MAX_WORKERS}"
        log_info "超时设置: ${TIMEOUT}秒"
        log_info "保持连接: ${KEEP_ALIVE}秒"
        
        exec gunicorn src.main:app \
            --worker-class uvicorn.workers.UvicornWorker \
            --workers "${MAX_WORKERS}" \
            --bind 0.0.0.0:8000 \
            --timeout "${TIMEOUT}" \
            --keep-alive "${KEEP_ALIVE}" \
            --max-requests 1000 \
            --max-requests-jitter 100 \
            --preload \
            --log-level "${LOG_LEVEL,,}" \
            --access-logfile - \
            --error-logfile - \
            --capture-output &
        
        UVICORN_PID=$!
        wait "$UVICORN_PID"
    fi
}

# ============================================================================
# 入口点
# ============================================================================
if [ "${1}" = "--help" ] || [ "${1}" = "-h" ]; then
    echo "智能意图识别系统 Docker 启动脚本"
    echo ""
    echo "环境变量:"
    echo "  APP_ENV              应用环境 (development/production)"
    echo "  LOG_LEVEL            日志级别 (DEBUG/INFO/WARNING/ERROR)"
    echo "  MAX_WORKERS          工作进程数"
    echo "  TIMEOUT              请求超时时间"
    echo "  KEEP_ALIVE           保持连接时间"
    echo "  SKIP_MIGRATIONS      跳过数据库迁移"
    echo "  SKIP_INIT_DATA       跳过数据初始化"
    echo "  SKIP_CACHE_WARMUP    跳过缓存预热"
    echo ""
    echo "用法:"
    echo "  ./entrypoint.sh                启动应用"
    echo "  ./entrypoint.sh --help         显示帮助信息"
    exit 0
fi

# 检查是否以root用户运行
if [ "$(id -u)" = "0" ]; then
    log_error "不应该以root用户运行此应用"
    exit 1
fi

# 执行主函数
main "$@"