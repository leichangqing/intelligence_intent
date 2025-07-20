# 智能意图识别系统部署指南

## 概览

本指南提供了智能意图识别系统的完整部署方案，支持从开发环境到生产环境的多种部署方式。系统基于FastAPI构建，使用Docker容器化部署，支持多环境配置和自动化运维。

### 系统架构

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│      Nginx      │    │   Prometheus    │    │    Grafana      │
│  (反向代理/SSL)  │    │    (监控)       │    │   (可视化)      │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │                       │                       │
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   FastAPI App   │    │     MySQL       │    │     Redis       │
│   (主应用服务)   │    │    (数据库)     │    │    (缓存)       │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │
┌─────────────────┐    ┌─────────────────┐
│   Xinference    │    │    RAGFLOW      │
│   (LLM服务)     │    │   (知识库)      │
└─────────────────┘    └─────────────────┘
```

## 部署方式选择

### 1. 开发环境部署
- **适用场景**: 本地开发调试
- **复杂度**: 低
- **部署时间**: 5-10分钟

### 2. 测试环境部署
- **适用场景**: 集成测试、功能验证
- **复杂度**: 中
- **部署时间**: 15-20分钟

### 3. 生产环境部署
- **适用场景**: 正式生产服务
- **复杂度**: 高
- **部署时间**: 30-45分钟

## 前置要求

### 系统要求

| 组件 | 最低配置 | 推荐配置 | 生产配置 |
|------|----------|----------|----------|
| CPU | 2核 | 4核 | 8核+ |
| 内存 | 4GB | 8GB | 16GB+ |
| 存储 | 20GB | 50GB | 100GB+ |
| 网络 | 10Mbps | 100Mbps | 1Gbps |

### 软件依赖

- **Docker**: >= 20.10
- **Docker Compose**: >= 2.0
- **Git**: >= 2.20
- **Python**: 3.11+ (本地开发)
- **Make**: GNU Make (可选，用于自动化)

### 外部服务

- **Xinference服务**: LLM模型推理
- **RAGFLOW服务**: 知识库查询
- **Duckling服务**: 实体提取（可选）

## 环境配置

### 环境变量文件

系统支持多环境配置，每个环境都有对应的配置文件：

```
config/
├── .env.development    # 开发环境
├── .env.testing       # 测试环境
├── .env.staging       # 预发布环境
└── .env.production    # 生产环境
```

### 核心环境变量

```bash
# 应用配置
APP_NAME=智能意图识别系统
APP_VERSION=1.0.0
DEBUG=false
LOG_LEVEL=INFO

# 数据库配置
DB_HOST=mysql
DB_PORT=3306
DB_USER=intent_user
DB_PASSWORD=your_secure_password
DB_NAME=intent_recognition

# Redis配置
REDIS_HOST=redis
REDIS_PORT=6379
REDIS_PASSWORD=your_redis_password
REDIS_DB=0

# NLU服务配置
XINFERENCE_BASE_URL=http://xinference:9997
XINFERENCE_MODEL=qwen2-instruct
XINFERENCE_API_KEY=your_xinference_key

# RAGFLOW配置
RAGFLOW_BASE_URL=http://ragflow:9380
RAGFLOW_API_KEY=your_ragflow_key

# 安全配置
SECRET_KEY=your_super_secret_key_here
JWT_SECRET_KEY=your_jwt_secret_key
JWT_ALGORITHM=HS256
JWT_EXPIRE_MINUTES=1440

# API配置
API_V1_PREFIX=/api/v1
CORS_ORIGINS=["http://localhost:3000"]
```

详细的环境变量说明请参考 [环境变量文档](ENVIRONMENT_VARIABLES.md)。

## 部署步骤

### 方式一：快速开发部署

适用于本地开发和快速验证。

#### 1. 克隆代码

```bash
git clone <repository_url>
cd intelligent-intent-recognition
```

#### 2. 环境配置

```bash
# 复制环境变量模板
cp .env.example .env

# 编辑环境变量
vim .env
```

#### 3. 启动服务

```bash
# 使用基础Docker Compose
docker-compose up -d

# 或使用Make命令
make dev-up
```

#### 4. 初始化数据库

```bash
# 等待数据库启动
sleep 30

# 初始化数据库
docker-compose exec app python scripts/init_database.py

# 或使用Make命令
make db-init
```

#### 5. 验证部署

```bash
# 检查服务状态
curl http://localhost:8000/api/v1/health/

# 访问API文档
open http://localhost:8000/docs
```

### 方式二：优化生产部署

适用于生产环境，包含完整的监控和日志系统。

#### 1. 准备生产环境

```bash
# 创建部署目录
mkdir -p /opt/intent-recognition
cd /opt/intent-recognition

# 克隆代码
git clone <repository_url> .
```

#### 2. 配置生产环境

```bash
# 使用生产环境配置
cp config/.env.production .env

# 编辑配置文件
vim .env

# 设置安全的密码和密钥
./scripts/generate_secrets.sh
```

#### 3. 部署服务

```bash
# 使用优化的Docker Compose
docker-compose -f docker-compose.optimized.yml up -d

# 或使用Make命令
make prod-deploy
```

#### 4. 配置SSL证书（生产环境）

```bash
# 使用Let's Encrypt
docker-compose exec nginx certbot --nginx -d your-domain.com

# 或手动配置SSL证书
cp your-cert.pem docker/nginx/ssl/
cp your-key.pem docker/nginx/ssl/
```

#### 5. 初始化和验证

```bash
# 初始化数据库
make db-init

# 运行健康检查
make health-check

# 检查所有服务状态
docker-compose -f docker-compose.optimized.yml ps
```

### 方式三：本地Python部署

适用于开发调试，不使用Docker。

#### 1. 安装依赖

```bash
# 创建虚拟环境
python3.11 -m venv venv
source venv/bin/activate

# 安装依赖
pip install -r requirements.txt
```

#### 2. 配置外部服务

```bash
# 启动MySQL和Redis
docker-compose up -d mysql redis

# 配置环境变量
export DB_HOST=localhost
export REDIS_HOST=localhost
```

#### 3. 启动应用

```bash
# 开发模式
python -m uvicorn src.main:app --reload --host 0.0.0.0 --port 8000

# 或使用Make命令
make dev-local
```

## Docker配置详解

### 基础Dockerfile

```dockerfile
FROM python:3.11-slim

# 设置工作目录
WORKDIR /app

# 安装系统依赖
RUN apt-get update && apt-get install -y \
    gcc \
    curl \
    && rm -rf /var/lib/apt/lists/*

# 安装Python依赖
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制应用代码
COPY . .

# 健康检查
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8000/api/v1/health/ || exit 1

# 启动应用
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### 优化Dockerfile

支持多阶段构建，包含开发、测试、生产三个目标：

```dockerfile
# 开发阶段
FROM python:3.11-slim as development
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
CMD ["uvicorn", "src.main:app", "--reload", "--host", "0.0.0.0"]

# 测试阶段
FROM development as testing
RUN pip install pytest pytest-cov
CMD ["pytest", "--cov=src", "--cov-report=html"]

# 生产阶段
FROM python:3.11-slim as production
RUN useradd --create-home --shell /bin/bash app
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
RUN chown -R app:app /app
USER app
CMD ["gunicorn", "src.main:app", "-w", "4", "-k", "uvicorn.workers.UvicornWorker"]
```

## 数据库配置

### MySQL配置优化

位置：`docker/mysql/my.cnf`

```ini
[mysqld]
# 基础配置
default-storage-engine=InnoDB
sql_mode=STRICT_TRANS_TABLES,NO_ZERO_DATE,NO_ZERO_IN_DATE,ERROR_FOR_DIVISION_BY_ZERO

# 性能优化
innodb_buffer_pool_size=1G
innodb_log_file_size=256M
innodb_log_buffer_size=32M
innodb_flush_log_at_trx_commit=2

# 连接配置
max_connections=200
max_connect_errors=10000
wait_timeout=28800

# 字符集配置
character-set-server=utf8mb4
collation-server=utf8mb4_unicode_ci
```

### 数据库初始化

```bash
# 手动初始化
docker-compose exec mysql mysql -u root -p intent_recognition < docs/design/mysql_schema.sql

# 或使用初始化脚本
python scripts/init_database.py
```

## Redis配置

### Redis优化配置

位置：`docker/redis/redis.conf`

```conf
# 内存配置
maxmemory 512mb
maxmemory-policy allkeys-lru

# 持久化配置
save 900 1
save 300 10
save 60 10000

# 网络配置
tcp-keepalive 300
timeout 0

# 日志配置
loglevel notice
logfile /var/log/redis/redis-server.log
```

## 监控配置

### Prometheus配置

位置：`docker/prometheus/prometheus.yml`

```yaml
global:
  scrape_interval: 15s
  evaluation_interval: 15s

scrape_configs:
  - job_name: 'fastapi-app'
    static_configs:
      - targets: ['app:8000']
    metrics_path: '/metrics'
    scrape_interval: 5s

  - job_name: 'mysql'
    static_configs:
      - targets: ['mysql-exporter:9104']

  - job_name: 'redis'
    static_configs:
      - targets: ['redis-exporter:9121']
```

### Grafana仪表盘

预配置的仪表盘包括：

1. **应用性能监控**
   - 请求响应时间
   - QPS和错误率
   - 内存和CPU使用率

2. **数据库监控**
   - 连接数和查询性能
   - 慢查询统计
   - 存储使用情况

3. **Redis监控**
   - 内存使用率
   - 命令执行统计
   - 连接数监控

## 网络配置

### Nginx反向代理

位置：`docker/nginx/nginx.conf`

```nginx
upstream app_backend {
    server app:8000;
}

server {
    listen 80;
    server_name your-domain.com;

    # 重定向到HTTPS
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name your-domain.com;

    # SSL配置
    ssl_certificate /etc/nginx/ssl/cert.pem;
    ssl_certificate_key /etc/nginx/ssl/key.pem;

    # 安全配置
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers ECDHE-RSA-AES256-GCM-SHA512:DHE-RSA-AES256-GCM-SHA512;
    ssl_prefer_server_ciphers off;

    # API代理
    location /api/ {
        proxy_pass http://app_backend;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # 静态文件
    location /docs {
        proxy_pass http://app_backend;
    }

    location /redoc {
        proxy_pass http://app_backend;
    }
}
```

## 自动化运维

### Make命令

系统提供了完整的Make命令用于自动化运维：

```bash
# 开发环境
make dev-up          # 启动开发环境
make dev-down        # 停止开发环境
make dev-logs        # 查看开发环境日志

# 生产环境
make prod-deploy     # 部署生产环境
make prod-update     # 更新生产环境
make prod-rollback   # 回滚生产环境

# 数据库管理
make db-init         # 初始化数据库
make db-backup       # 备份数据库
make db-restore      # 恢复数据库

# 监控和维护
make health-check    # 健康检查
make logs           # 查看日志
make clean          # 清理资源
```

### 部署脚本

#### 启动脚本：`docker/entrypoint.sh`

```bash
#!/bin/bash
set -e

# 等待数据库就绪
echo "等待数据库连接..."
while ! mysqladmin ping -h"$DB_HOST" -P"$DB_PORT" -u"$DB_USER" -p"$DB_PASSWORD" --silent; do
    sleep 1
done

# 等待Redis就绪
echo "等待Redis连接..."
while ! redis-cli -h "$REDIS_HOST" -p "$REDIS_PORT" ping; do
    sleep 1
done

# 运行数据库迁移
echo "运行数据库迁移..."
python scripts/init_database.py

# 启动应用
echo "启动应用..."
exec "$@"
```

#### 健康检查脚本

```bash
#!/bin/bash

# 检查应用健康状态
check_app_health() {
    response=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/api/v1/health/)
    if [ "$response" = "200" ]; then
        echo "✅ 应用服务正常"
        return 0
    else
        echo "❌ 应用服务异常 (HTTP: $response)"
        return 1
    fi
}

# 检查数据库连接
check_database() {
    if docker-compose exec -T mysql mysqladmin ping -h localhost -u "$DB_USER" -p"$DB_PASSWORD" --silent; then
        echo "✅ 数据库连接正常"
        return 0
    else
        echo "❌ 数据库连接异常"
        return 1
    fi
}

# 检查Redis连接
check_redis() {
    if docker-compose exec -T redis redis-cli ping | grep -q PONG; then
        echo "✅ Redis连接正常"
        return 0
    else
        echo "❌ Redis连接异常"
        return 1
    fi
}

# 执行所有检查
main() {
    echo "开始健康检查..."
    
    errors=0
    check_app_health || ((errors++))
    check_database || ((errors++))
    check_redis || ((errors++))
    
    if [ $errors -eq 0 ]; then
        echo "🎉 所有服务运行正常"
        exit 0
    else
        echo "⚠️  发现 $errors 个问题"
        exit 1
    fi
}

main "$@"
```

## 安全配置

### 容器安全

1. **非root用户运行**
   ```dockerfile
   RUN useradd --create-home --shell /bin/bash app
   USER app
   ```

2. **只读文件系统**
   ```yaml
   security_opt:
     - no-new-privileges:true
   read_only: true
   tmpfs:
     - /tmp:noexec,nosuid,size=100m
   ```

3. **资源限制**
   ```yaml
   deploy:
     resources:
       limits:
         cpus: '2'
         memory: 2G
       reservations:
         memory: 512M
   ```

### 网络安全

1. **网络隔离**
   ```yaml
   networks:
     app_network:
       driver: bridge
       internal: true
     monitoring_network:
       driver: bridge
   ```

2. **防火墙配置**
   ```bash
   # 只开放必要端口
   ufw allow 80/tcp
   ufw allow 443/tcp
   ufw deny 3306/tcp  # 数据库不对外开放
   ```

### 数据安全

1. **数据库加密**
   ```sql
   -- 配置加密连接
   ALTER USER 'intent_user'@'%' REQUIRE SSL;
   ```

2. **Redis密码保护**
   ```conf
   requirepass your_secure_redis_password
   ```

3. **环境变量加密**
   ```bash
   # 使用Docker secrets
   echo "your_secret" | docker secret create db_password -
   ```

## 备份策略

### 数据库备份

```bash
# 每日自动备份
#!/bin/bash
BACKUP_DIR="/backups/mysql"
DATE=$(date +%Y%m%d_%H%M%S)

# 创建备份
docker-compose exec -T mysql mysqldump \
    -u "$DB_USER" -p"$DB_PASSWORD" \
    --single-transaction \
    --routines \
    --triggers \
    "$DB_NAME" > "$BACKUP_DIR/backup_$DATE.sql"

# 压缩备份
gzip "$BACKUP_DIR/backup_$DATE.sql"

# 删除7天前的备份
find "$BACKUP_DIR" -name "backup_*.sql.gz" -mtime +7 -delete
```

### Redis备份

```bash
# Redis数据备份
#!/bin/bash
BACKUP_DIR="/backups/redis"
DATE=$(date +%Y%m%d_%H%M%S)

# 保存快照
docker-compose exec redis redis-cli BGSAVE

# 等待快照完成
while [ $(docker-compose exec redis redis-cli LASTSAVE) -eq $last_save ]; do
    sleep 1
done

# 复制备份文件
docker cp $(docker-compose ps -q redis):/data/dump.rdb "$BACKUP_DIR/dump_$DATE.rdb"
```

### 配置备份

```bash
# 配置文件备份
#!/bin/bash
BACKUP_DIR="/backups/config"
DATE=$(date +%Y%m%d_%H%M%S)

# 备份配置文件
tar -czf "$BACKUP_DIR/config_$DATE.tar.gz" \
    .env \
    config/ \
    docker/ \
    docker-compose*.yml
```

## 性能优化

### 应用层优化

1. **Gunicorn配置**
   ```python
   # gunicorn.conf.py
   bind = "0.0.0.0:8000"
   workers = multiprocessing.cpu_count() * 2 + 1
   worker_class = "uvicorn.workers.UvicornWorker"
   worker_connections = 1000
   max_requests = 1000
   max_requests_jitter = 100
   keepalive = 2
   ```

2. **缓存策略**
   ```python
   # Redis缓存配置
   CACHE_CONFIG = {
       "intent_cache_ttl": 3600,
       "slot_cache_ttl": 1800,
       "session_cache_ttl": 7200
   }
   ```

### 数据库优化

1. **索引优化**
   ```sql
   -- 为常用查询添加索引
   CREATE INDEX idx_conversations_user_id ON conversations(user_id);
   CREATE INDEX idx_conversations_created_at ON conversations(created_at);
   CREATE INDEX idx_intents_name ON intents(name);
   ```

2. **连接池配置**
   ```python
   DATABASE_CONFIG = {
       "pool_size": 20,
       "max_overflow": 30,
       "pool_pre_ping": True,
       "pool_recycle": 3600
   }
   ```

## 故障排除

### 常见问题

#### 1. 容器启动失败

```bash
# 检查日志
docker-compose logs app

# 检查端口占用
netstat -tulpn | grep :8000

# 重建容器
docker-compose down
docker-compose up --build -d
```

#### 2. 数据库连接失败

```bash
# 检查数据库状态
docker-compose exec mysql mysql -u root -p -e "SHOW PROCESSLIST;"

# 检查网络连接
docker-compose exec app ping mysql

# 重置数据库密码
docker-compose exec mysql mysql -u root -p -e "ALTER USER 'intent_user'@'%' IDENTIFIED BY 'new_password';"
```

#### 3. Redis连接问题

```bash
# 检查Redis状态
docker-compose exec redis redis-cli ping

# 查看Redis配置
docker-compose exec redis redis-cli CONFIG GET "*"

# 清理Redis缓存
docker-compose exec redis redis-cli FLUSHALL
```

#### 4. 内存不足

```bash
# 检查容器资源使用
docker stats

# 增加交换空间
sudo swapon --show
sudo fallocate -l 2G /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile
```

### 日志分析

#### 应用日志

```bash
# 实时查看应用日志
docker-compose logs -f app

# 查看错误日志
docker-compose logs app | grep ERROR

# 导出日志文件
docker-compose logs app > app.log
```

#### 系统监控

```bash
# 检查系统资源
htop
iotop
nethogs

# 检查磁盘空间
df -h
du -sh /*

# 检查网络连接
ss -tulpn
```

## 升级维护

### 应用更新

```bash
#!/bin/bash
# update.sh

echo "开始应用更新..."

# 1. 备份当前版本
docker-compose exec mysql mysqldump -u "$DB_USER" -p"$DB_PASSWORD" "$DB_NAME" > backup_$(date +%Y%m%d).sql

# 2. 拉取最新代码
git pull origin main

# 3. 构建新镜像
docker-compose build --no-cache app

# 4. 滚动更新
docker-compose up -d --no-deps app

# 5. 健康检查
sleep 30
if curl -f http://localhost:8000/api/v1/health/; then
    echo "✅ 更新成功"
else
    echo "❌ 更新失败，开始回滚"
    git checkout HEAD~1
    docker-compose build --no-cache app
    docker-compose up -d --no-deps app
fi
```

### 数据库迁移

```bash
# 数据库结构更新
python scripts/migrate_database.py

# 或使用Alembic
alembic upgrade head
```

### 配置热更新

```bash
# 重新加载配置（不重启服务）
docker-compose exec app kill -HUP 1

# 或重启特定服务
docker-compose restart app
```

## 监控告警

### Prometheus告警规则

```yaml
# alerts.yml
groups:
  - name: application
    rules:
      - alert: HighErrorRate
        expr: rate(http_requests_total{status=~"5.."}[5m]) > 0.1
        for: 5m
        labels:
          severity: critical
        annotations:
          summary: "高错误率告警"

      - alert: HighResponseTime
        expr: histogram_quantile(0.95, rate(http_request_duration_seconds_bucket[5m])) > 2
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "响应时间过长"
```

### 告警通知

```yaml
# alertmanager.yml
route:
  group_by: ['alertname']
  group_wait: 10s
  group_interval: 10s
  repeat_interval: 1h
  receiver: 'web.hook'

receivers:
  - name: 'web.hook'
    webhook_configs:
      - url: 'http://webhook:5000/alerts'
```

## 最佳实践

### 1. 版本管理
- 使用语义化版本号
- 标记发布版本
- 维护变更日志

### 2. 配置管理
- 环境变量集中管理
- 敏感信息加密存储
- 配置变更审计

### 3. 监控运维
- 建立完善的监控体系
- 设置合理的告警阈值
- 定期进行故障演练

### 4. 安全防护
- 定期更新依赖包
- 开启安全审计
- 实施访问控制

### 5. 性能优化
- 定期性能分析
- 数据库查询优化
- 缓存策略调整

## 联系支持

如在部署过程中遇到问题，请联系技术支持团队或查阅相关文档：

- [API文档](api_documentation.md)
- [环境变量文档](ENVIRONMENT_VARIABLES.md)
- [快速开始指南](../QUICK_START.md)

---

*本部署指南会随着系统版本更新持续维护，请关注最新版本。*