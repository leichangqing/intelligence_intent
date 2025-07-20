-- 基础MySQL数据库表结构
-- 简化版本，用于快速初始化

CREATE DATABASE IF NOT EXISTS intent_db DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE intent_db;

-- 禁用外键检查
SET FOREIGN_KEY_CHECKS = 0;

-- 删除所有表
DROP TABLE IF EXISTS intents;
DROP TABLE IF EXISTS slots;
DROP TABLE IF EXISTS function_calls;
DROP TABLE IF EXISTS sessions;
DROP TABLE IF EXISTS conversations;
DROP TABLE IF EXISTS system_configs;

-- 重新启用外键检查
SET FOREIGN_KEY_CHECKS = 1;

-- 1. 意图配置表
CREATE TABLE intents (
    id INT AUTO_INCREMENT PRIMARY KEY,
    intent_name VARCHAR(100) NOT NULL UNIQUE COMMENT '意图名称',
    display_name VARCHAR(200) NOT NULL COMMENT '显示名称',
    description TEXT COMMENT '意图描述',
    confidence_threshold DECIMAL(3,2) DEFAULT 0.7 COMMENT '置信度阈值',
    priority INT DEFAULT 1 COMMENT '意图优先级',
    is_active BOOLEAN DEFAULT TRUE COMMENT '是否激活',
    examples JSON COMMENT '示例语句',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_intent_name (intent_name),
    INDEX idx_active (is_active)
) COMMENT '意图配置表';

-- 2. 槽位配置表
CREATE TABLE slots (
    id INT AUTO_INCREMENT PRIMARY KEY,
    intent_id INT NOT NULL,
    slot_name VARCHAR(100) NOT NULL COMMENT '槽位名称',
    slot_type VARCHAR(50) NOT NULL COMMENT '槽位类型',
    is_required BOOLEAN DEFAULT FALSE COMMENT '是否必填',
    validation_rules JSON COMMENT '验证规则',
    prompt_template TEXT COMMENT '询问模板',
    examples JSON COMMENT '示例值',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (intent_id) REFERENCES intents(id) ON DELETE CASCADE,
    UNIQUE KEY unique_intent_slot (intent_id, slot_name),
    INDEX idx_intent_id (intent_id)
) COMMENT '槽位配置表';

-- 3. 功能调用配置表
CREATE TABLE function_calls (
    id INT AUTO_INCREMENT PRIMARY KEY,
    intent_id INT NOT NULL,
    function_name VARCHAR(100) NOT NULL COMMENT '函数名称',
    api_endpoint VARCHAR(500) NOT NULL COMMENT 'API端点',
    http_method VARCHAR(10) DEFAULT 'POST' COMMENT 'HTTP方法',
    headers JSON COMMENT '请求头',
    param_mapping JSON COMMENT '参数映射配置',
    retry_times INT DEFAULT 3 COMMENT '重试次数',
    timeout_seconds INT DEFAULT 30 COMMENT '超时时间',
    success_template TEXT COMMENT '成功响应模板',
    error_template TEXT COMMENT '错误响应模板',
    is_active BOOLEAN DEFAULT TRUE COMMENT '是否激活',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (intent_id) REFERENCES intents(id) ON DELETE CASCADE,
    INDEX idx_intent_id (intent_id),
    INDEX idx_function_name (function_name)
) COMMENT '功能调用配置表';

-- 4. 会话记录表
CREATE TABLE sessions (
    id INT AUTO_INCREMENT PRIMARY KEY,
    session_id VARCHAR(100) NOT NULL UNIQUE COMMENT '会话ID',
    user_id VARCHAR(100) NOT NULL COMMENT '用户ID',
    current_intent VARCHAR(100) COMMENT '当前意图',
    session_state ENUM('active', 'completed', 'expired') DEFAULT 'active' COMMENT '会话状态',
    context JSON COMMENT '会话上下文',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    expires_at TIMESTAMP NULL COMMENT '过期时间',
    INDEX idx_session_id (session_id),
    INDEX idx_user_id (user_id),
    INDEX idx_state (session_state)
) COMMENT '会话记录表';

-- 5. 对话历史表
CREATE TABLE conversations (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    session_id VARCHAR(100) NOT NULL COMMENT '会话ID',
    user_id VARCHAR(100) NOT NULL COMMENT '用户ID',
    user_input TEXT NOT NULL COMMENT '用户输入',
    intent_recognized VARCHAR(100) COMMENT '识别的意图',
    confidence_score DECIMAL(5,4) COMMENT '置信度分数',
    slots_filled JSON COMMENT '已填充的槽位',
    system_response TEXT COMMENT '系统响应',
    response_type VARCHAR(50) COMMENT '响应类型',
    status VARCHAR(50) COMMENT '处理状态',
    processing_time_ms INT COMMENT '处理时间毫秒',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_session_id (session_id),
    INDEX idx_user_id (user_id),
    INDEX idx_intent (intent_recognized),
    INDEX idx_created_at (created_at)
) COMMENT '对话历史表';

-- 6. 系统配置表
CREATE TABLE system_configs (
    id INT AUTO_INCREMENT PRIMARY KEY,
    config_key VARCHAR(100) NOT NULL UNIQUE COMMENT '配置键',
    config_value TEXT NOT NULL COMMENT '配置值',
    description TEXT COMMENT '配置描述',
    category VARCHAR(50) COMMENT '配置分类',
    is_readonly BOOLEAN DEFAULT FALSE COMMENT '是否只读',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_category (category),
    INDEX idx_readonly (is_readonly)
) COMMENT '系统配置表';

-- 插入初始数据

-- 插入意图
INSERT INTO intents (intent_name, display_name, description, confidence_threshold, priority, is_active, examples) VALUES
('book_flight', '预订机票', '帮助用户预订机票', 0.7, 1, TRUE, '["我要订机票", "帮我买张票", "预订航班", "订票"]'),
('check_balance', '查询余额', '查询用户账户余额', 0.7, 1, TRUE, '["查询余额", "我的余额", "账户余额", "余额查询"]');

-- 插入槽位
INSERT INTO slots (intent_id, slot_name, slot_type, is_required, validation_rules, prompt_template, examples) VALUES
((SELECT id FROM intents WHERE intent_name = 'book_flight'), 'departure_city', 'TEXT', TRUE, 
'{"min_length": 2, "max_length": 20}', '请问您从哪个城市出发？', '["北京", "上海", "广州", "深圳"]'),

((SELECT id FROM intents WHERE intent_name = 'book_flight'), 'arrival_city', 'TEXT', TRUE, 
'{"min_length": 2, "max_length": 20}', '请问您要到哪个城市？', '["北京", "上海", "广州", "深圳"]'),

((SELECT id FROM intents WHERE intent_name = 'book_flight'), 'departure_date', 'DATE', TRUE, 
'{"format": "YYYY-MM-DD", "min_date": "today"}', '请问您希望什么时候出发？', '["2024-12-15", "明天", "下周一"]'),

((SELECT id FROM intents WHERE intent_name = 'check_balance'), 'card_number', 'TEXT', TRUE, 
'{"pattern": "^[0-9]{16}$", "mask": true}', '请提供您的银行卡号（16位数字）', '["6222080012345678"]');

-- 插入功能调用配置
INSERT INTO function_calls (intent_id, function_name, api_endpoint, http_method, headers, param_mapping, success_template, error_template) VALUES
((SELECT id FROM intents WHERE intent_name = 'book_flight'), 'book_flight_api', 'https://api.flight.com/v1/booking', 'POST', 
'{"Content-Type": "application/json", "Authorization": "Bearer {api_key}"}', 
'{"from": "departure_city", "to": "arrival_city", "date": "departure_date"}',
'您的机票预订成功！航班号：{flight_number}，订单号：{order_id}',
'抱歉，预订失败：{error_message}'),

((SELECT id FROM intents WHERE intent_name = 'check_balance'), 'check_balance_api', 'https://api.bank.com/v1/balance', 'GET',
'{"Content-Type": "application/json", "Authorization": "Bearer {api_key}"}',
'{"card_number": "card_number"}',
'您的账户余额为：{balance}元',
'查询失败：{error_message}');

-- 插入系统配置
INSERT INTO system_configs (config_key, config_value, description, category, is_readonly) VALUES
('intent_confidence_threshold', '0.7', '意图识别置信度阈值', 'nlu', FALSE),
('ambiguity_detection_threshold', '0.1', '歧义检测阈值', 'nlu', FALSE),
('slot_confidence_threshold', '0.6', '槽位识别置信度阈值', 'nlu', FALSE),
('session_timeout_seconds', '86400', '会话超时时间（秒）', 'session', FALSE),
('max_conversation_turns', '50', '最大对话轮数', 'session', FALSE),
('api_call_timeout', '30', 'API调用超时时间（秒）', 'api', FALSE),
('max_retry_attempts', '3', '最大重试次数', 'api', FALSE);

-- 显示创建结果
SELECT 'Database initialization completed' AS status;
SELECT COUNT(*) AS intents_count FROM intents;
SELECT COUNT(*) AS slots_count FROM slots;
SELECT COUNT(*) AS function_calls_count FROM function_calls;
SELECT COUNT(*) AS system_configs_count FROM system_configs;