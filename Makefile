# 智能意图识别系统 - Makefile

.PHONY: help install dev test build run docker-up docker-down clean lint format

# 默认目标
help:
	@echo "智能意图识别系统 - 可用命令:"
	@echo ""
	@echo "开发相关:"
	@echo "  install     - 安装项目依赖"
	@echo "  dev         - 启动开发服务器"
	@echo "  test        - 运行测试"
	@echo "  lint        - 代码检查"
	@echo "  format      - 代码格式化"
	@echo ""
	@echo "构建和部署:"
	@echo "  build       - 构建Docker镜像"
	@echo "  run         - 运行应用"
	@echo "  docker-up   - 启动Docker服务"
	@echo "  docker-down - 停止Docker服务"
	@echo ""
	@echo "其他:"
	@echo "  clean       - 清理临时文件"
	@echo "  db-init     - 初始化数据库"

# 安装依赖
install:
	@echo "安装项目依赖..."
	pip install -r requirements.txt

# 启动开发服务器
dev:
	@echo "启动开发服务器..."
	uvicorn src.main:app --reload --host 0.0.0.0 --port 8000

# 运行测试
test:
	@echo "运行测试..."
	pytest tests/ -v --cov=src --cov-report=html

# 代码检查
lint:
	@echo "运行代码检查..."
	flake8 src/
	mypy src/

# 代码格式化
format:
	@echo "格式化代码..."
	black src/
	isort src/

# 构建Docker镜像
build:
	@echo "构建Docker镜像..."
	docker build -t intent-recognition-system .

# 运行应用
run:
	@echo "运行应用..."
	python -m src.main

# 启动Docker服务
docker-up:
	@echo "启动Docker服务..."
	docker-compose up -d

# 停止Docker服务
docker-down:
	@echo "停止Docker服务..."
	docker-compose down

# 初始化数据库
db-init:
	@echo "初始化数据库..."
	python -c "from src.config.database import create_tables; create_tables()"

# 清理临时文件
clean:
	@echo "清理临时文件..."
	find . -type f -name "*.pyc" -delete
	find . -type d -name "__pycache__" -delete
	find . -type d -name "*.egg-info" -exec rm -rf {} +
	rm -rf .pytest_cache
	rm -rf htmlcov
	rm -rf dist
	rm -rf build

# 生产环境部署
deploy-prod:
	@echo "部署到生产环境..."
	docker-compose --profile production up -d

# 查看日志
logs:
	@echo "查看应用日志..."
	docker-compose logs -f app

# 进入应用容器
shell:
	@echo "进入应用容器..."
	docker-compose exec app bash

# 备份数据库
backup-db:
	@echo "备份数据库..."
	docker-compose exec mysql mysqldump -u root -p intent_recognition_system > backup_$(shell date +%Y%m%d_%H%M%S).sql

# 检查服务状态
status:
	@echo "检查服务状态..."
	docker-compose ps
	@echo ""
	@echo "健康检查:"
	curl -f http://localhost:8000/api/v1/health || echo "应用服务异常"

# 重启服务
restart:
	@echo "重启服务..."
	docker-compose restart app

# 更新依赖
update-deps:
	@echo "更新依赖..."
	pip list --outdated
	pip install --upgrade -r requirements.txt

# 安全检查
security-check:
	@echo "运行安全检查..."
	pip-audit
	bandit -r src/