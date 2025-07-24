-- 智能意图识别系统数据库表结构 v2.3 完整版
-- 支持B2B无状态设计、混合Prompt Template配置、RAGFLOW集成、智能歧义处理、同义词管理等高级功能
-- v2.3 新增功能：
-- 1. 同义词管理：同义词组、同义词条、停用词、实体识别模式的数据库化管理
-- 2. 完整初始数据：包含订机票、查余额等基础意图和相关槽位配置
-- 3. 数据一致性：修复字段名称不一致问题，统一数据结构
-- 4. 性能优化：添加必要的索引和约束，优化查询性能

-- 创建数据库
CREATE DATABASE IF NOT EXISTS intent_db DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE intent_db;

-- 禁用外键检查以便删除表
SET FOREIGN_KEY_CHECKS = 0;

-- 删除所有表（按依赖关系倒序）
DROP TABLE IF EXISTS synonym_terms;
DROP TABLE IF EXISTS synonym_groups;
DROP TABLE IF EXISTS stop_words;
DROP TABLE IF EXISTS entity_patterns;
DROP TABLE IF EXISTS async_log_queue;
DROP TABLE IF EXISTS cache_invalidation_logs;
DROP TABLE IF EXISTS async_tasks;
DROP TABLE IF EXISTS security_audit_logs;
DROP TABLE IF EXISTS api_call_logs;
DROP TABLE IF EXISTS ragflow_configs;
DROP TABLE IF EXISTS system_configs;
DROP TABLE IF EXISTS intent_transfers;
DROP TABLE IF EXISTS user_contexts;
DROP TABLE IF EXISTS prompt_templates;
DROP TABLE IF EXISTS config_audit_logs;
DROP TABLE IF EXISTS intent_ambiguities;
DROP TABLE IF EXISTS conversations;
DROP TABLE IF EXISTS sessions;
DROP TABLE IF EXISTS function_calls;
DROP TABLE IF EXISTS slot_values;
DROP TABLE IF EXISTS slot_extraction_rules;
DROP TABLE IF EXISTS slot_dependencies;
DROP TABLE IF EXISTS slots;
DROP TABLE IF EXISTS response_types;
DROP TABLE IF EXISTS conversation_statuses;
DROP TABLE IF EXISTS intents;
DROP TABLE IF EXISTS entity_dictionary;
DROP TABLE IF EXISTS entity_types;
DROP TABLE IF EXISTS users;
DROP VIEW IF EXISTS v_active_intents;
DROP VIEW IF EXISTS v_conversation_summary;

-- 重新启用外键检查
SET FOREIGN_KEY_CHECKS = 1;

-- ================================
-- 核心业务表
-- ================================

-- 0. 用户信息表
CREATE TABLE IF NOT EXISTS users (
    id INT PRIMARY KEY AUTO_INCREMENT,
    user_id VARCHAR(100) UNIQUE NOT NULL COMMENT '用户唯一标识',
    user_type ENUM('individual', 'enterprise', 'admin', 'system') DEFAULT 'individual' COMMENT '用户类型',
    username VARCHAR(100) COMMENT '用户名',
    email VARCHAR(255) COMMENT '邮箱地址',
    phone VARCHAR(20) COMMENT '手机号码',
    display_name VARCHAR(200) COMMENT '显示名称',
    avatar_url VARCHAR(500) COMMENT '头像URL',
    status ENUM('active', 'inactive', 'suspended', 'deleted') DEFAULT 'active' COMMENT '用户状态',
    preferences JSON COMMENT '用户偏好设置',
    metadata JSON COMMENT '用户元数据',
    last_login_at TIMESTAMP NULL COMMENT '最后登录时间',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    INDEX idx_user_id (user_id),
    INDEX idx_user_type (user_type),
    INDEX idx_status (status),
    INDEX idx_email (email),
    INDEX idx_phone (phone),
    INDEX idx_last_login (last_login_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='用户信息表';

-- 1. 意图配置表
CREATE TABLE IF NOT EXISTS intents (
    id INT PRIMARY KEY AUTO_INCREMENT,
    intent_name VARCHAR(100) UNIQUE NOT NULL COMMENT '意图名称',
    display_name VARCHAR(200) NOT NULL COMMENT '显示名称',
    description TEXT COMMENT '意图描述',
    confidence_threshold DECIMAL(5,4) DEFAULT 0.7000 COMMENT '置信度阈值',
    priority INT DEFAULT 1 COMMENT '优先级',
    category VARCHAR(50) COMMENT '意图分类',
    is_active BOOLEAN DEFAULT TRUE COMMENT '是否激活',
    examples JSON COMMENT '示例语句',
    fallback_response TEXT COMMENT '兜底回复',
    created_by VARCHAR(100) COMMENT '创建人',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    INDEX idx_intent_name (intent_name),
    INDEX idx_active_priority (is_active, priority),
    INDEX idx_category (category),
    INDEX idx_created_by (created_by)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='意图配置表';

-- 2. 槽位配置表
CREATE TABLE IF NOT EXISTS slots (
    id INT PRIMARY KEY AUTO_INCREMENT,
    intent_id INT NOT NULL COMMENT '关联意图ID',
    slot_name VARCHAR(100) NOT NULL COMMENT '槽位名称',
    display_name VARCHAR(200) COMMENT '显示名称',
    slot_type ENUM('text', 'number', 'date', 'time', 'email', 'phone', 'entity', 'boolean') NOT NULL COMMENT '槽位类型',
    is_required BOOLEAN DEFAULT FALSE COMMENT '是否必填',
    is_list BOOLEAN DEFAULT FALSE COMMENT '是否为列表类型',
    validation_rules JSON COMMENT '验证规则',
    default_value TEXT COMMENT '默认值',
    prompt_template TEXT COMMENT '询问模板',
    error_message TEXT COMMENT '错误提示',
    extraction_priority INT DEFAULT 1 COMMENT '提取优先级',
    is_active BOOLEAN DEFAULT TRUE COMMENT '是否激活',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    FOREIGN KEY (intent_id) REFERENCES intents(id) ON DELETE CASCADE,
    UNIQUE KEY unique_intent_slot (intent_id, slot_name),
    INDEX idx_intent_required (intent_id, is_required),
    INDEX idx_slot_type (slot_type)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='槽位配置表';

-- 3. 槽位值存储表 (v2.2新增)
CREATE TABLE IF NOT EXISTS slot_values (
    id INT PRIMARY KEY AUTO_INCREMENT,
    conversation_id BIGINT NOT NULL COMMENT '对话ID',
    slot_id INT NOT NULL COMMENT '槽位ID',
    slot_name VARCHAR(100) NOT NULL COMMENT '槽位名称',
    original_text TEXT COMMENT '原始文本',
    extracted_value TEXT COMMENT '提取的值',
    normalized_value TEXT COMMENT '标准化后的值',
    confidence DECIMAL(5,4) COMMENT '提取置信度',
    extraction_method VARCHAR(50) COMMENT '提取方法',
    validation_status VARCHAR(20) DEFAULT 'pending' COMMENT '验证状态',
    validation_error TEXT COMMENT '验证错误信息',
    is_confirmed BOOLEAN DEFAULT FALSE COMMENT '是否已确认',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    UNIQUE KEY unique_conversation_slot (conversation_id, slot_id),
    INDEX idx_slot_name_value (slot_name, normalized_value(100)),
    INDEX idx_confidence (confidence),
    INDEX idx_validation_status (validation_status),
    CONSTRAINT chk_validation_status CHECK (validation_status IN ('valid', 'invalid', 'pending', 'corrected'))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='槽位值存储表';

-- 4. 响应类型配置表
CREATE TABLE IF NOT EXISTS response_types (
    id INT PRIMARY KEY AUTO_INCREMENT,
    type_name VARCHAR(50) UNIQUE NOT NULL COMMENT '响应类型名称',
    display_name VARCHAR(100) NOT NULL COMMENT '显示名称',
    description TEXT COMMENT '描述',
    template TEXT COMMENT '模板',
    is_active BOOLEAN DEFAULT TRUE COMMENT '是否激活',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    INDEX idx_type_name (type_name),
    INDEX idx_active (is_active)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='响应类型配置表';

-- 5. 会话状态表
CREATE TABLE IF NOT EXISTS conversation_statuses (
    id INT PRIMARY KEY AUTO_INCREMENT,
    status_name VARCHAR(50) UNIQUE NOT NULL COMMENT '状态名称',
    display_name VARCHAR(100) NOT NULL COMMENT '显示名称',
    description TEXT COMMENT '描述',
    is_final BOOLEAN DEFAULT FALSE COMMENT '是否为最终状态',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    INDEX idx_status_name (status_name),
    INDEX idx_is_final (is_final)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='会话状态表';

-- 6. 会话表
CREATE TABLE IF NOT EXISTS sessions (
    id INT PRIMARY KEY AUTO_INCREMENT,
    session_id VARCHAR(100) UNIQUE NOT NULL COMMENT '会话ID',
    user_id VARCHAR(100) NOT NULL COMMENT '用户ID',
    current_intent VARCHAR(100) COMMENT '当前意图',
    session_state ENUM('active', 'completed', 'expired', 'error') DEFAULT 'active' COMMENT '会话状态',
    context JSON COMMENT '会话上下文',
    metadata JSON COMMENT '会话元数据',
    expires_at TIMESTAMP NULL COMMENT '过期时间',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    INDEX idx_session_id (session_id),
    INDEX idx_user_id (user_id),
    INDEX idx_state (session_state),
    INDEX idx_expires_at (expires_at),
    INDEX idx_current_intent (current_intent)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='会话表';

-- 7. 对话记录表
CREATE TABLE IF NOT EXISTS conversations (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    session_id VARCHAR(100) NOT NULL COMMENT '会话ID',
    user_id VARCHAR(100) NOT NULL COMMENT '用户ID',
    user_input TEXT NOT NULL COMMENT '用户输入',
    intent_recognized VARCHAR(100) COMMENT '识别的意图',
    confidence_score DECIMAL(5,4) COMMENT '置信度分数',
    system_response TEXT COMMENT '系统响应',
    response_type VARCHAR(50) COMMENT '响应类型',
    status VARCHAR(50) COMMENT '处理状态',
    processing_time_ms INT COMMENT '处理时间毫秒',
    error_message TEXT COMMENT '错误信息',
    metadata JSON COMMENT '元数据',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    INDEX idx_session_id (session_id),
    INDEX idx_user_id (user_id),
    INDEX idx_intent (intent_recognized),
    INDEX idx_status (status),
    INDEX idx_created_at (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='对话记录表';

-- ================================
-- 功能扩展表
-- ================================

-- 8. 函数调用配置表
CREATE TABLE IF NOT EXISTS function_calls (
    id INT PRIMARY KEY AUTO_INCREMENT,
    intent_id INT NOT NULL COMMENT '关联意图ID',
    function_name VARCHAR(100) NOT NULL COMMENT '函数名称',
    description TEXT COMMENT '函数描述',
    api_endpoint VARCHAR(500) NOT NULL COMMENT 'API端点',
    http_method VARCHAR(10) DEFAULT 'POST' COMMENT 'HTTP方法',
    headers JSON COMMENT '请求头',
    parameter_mapping JSON COMMENT '参数映射配置',
    timeout_seconds INT DEFAULT 30 COMMENT '超时时间',
    retry_attempts INT DEFAULT 3 COMMENT '重试次数',
    success_template TEXT COMMENT '成功响应模板',
    error_template TEXT COMMENT '错误响应模板',
    is_active BOOLEAN DEFAULT TRUE COMMENT '是否激活',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    FOREIGN KEY (intent_id) REFERENCES intents(id) ON DELETE CASCADE,
    INDEX idx_intent_id (intent_id),
    INDEX idx_function_name (function_name),
    INDEX idx_active (is_active)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='函数调用配置表';

-- 9. 系统配置表
CREATE TABLE IF NOT EXISTS system_configs (
    id INT PRIMARY KEY AUTO_INCREMENT,
    config_category VARCHAR(50) NOT NULL COMMENT '配置分类',
    config_key VARCHAR(100) NOT NULL COMMENT '配置键',
    config_value TEXT COMMENT '配置值',
    value_type ENUM('string', 'number', 'boolean', 'json', 'array') NOT NULL COMMENT '值类型',
    description TEXT COMMENT '配置描述',
    is_encrypted BOOLEAN DEFAULT FALSE COMMENT '是否加密',
    is_public BOOLEAN DEFAULT TRUE COMMENT '是否公开',
    validation_rule VARCHAR(500) COMMENT '验证规则',
    default_value TEXT COMMENT '默认值',
    is_active BOOLEAN DEFAULT TRUE COMMENT '是否激活',
    created_by VARCHAR(100) COMMENT '创建人',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    UNIQUE KEY systemconfig_config_category_config_key (config_category, config_key),
    INDEX systemconfig_is_active (is_active),
    INDEX systemconfig_is_public (is_public)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='系统配置表';

-- ================================
-- 同义词管理表 (v2.3新增)
-- ================================

-- 10. 同义词组表
CREATE TABLE IF NOT EXISTS synonym_groups (
    id INT PRIMARY KEY AUTO_INCREMENT,
    group_name VARCHAR(100) UNIQUE NOT NULL COMMENT '同义词组名称',
    standard_term VARCHAR(100) NOT NULL COMMENT '标准词汇',
    description TEXT COMMENT '描述',
    category VARCHAR(50) COMMENT '分类',
    is_active BOOLEAN DEFAULT TRUE COMMENT '是否激活',
    priority INT DEFAULT 1 COMMENT '优先级',
    created_by VARCHAR(100) COMMENT '创建人',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    INDEX idx_standard_term (standard_term),
    INDEX idx_category (category),
    INDEX idx_active (is_active),
    INDEX idx_priority (priority)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='同义词组表';

-- 11. 同义词条表
CREATE TABLE IF NOT EXISTS synonym_terms (
    id INT PRIMARY KEY AUTO_INCREMENT,
    group_id INT NOT NULL COMMENT '同义词组ID',
    term VARCHAR(100) NOT NULL COMMENT '同义词',
    confidence DECIMAL(5,4) DEFAULT 1.0000 COMMENT '相似度',
    context_tags JSON COMMENT '上下文标签',
    usage_count BIGINT DEFAULT 0 COMMENT '使用次数',
    is_active BOOLEAN DEFAULT TRUE COMMENT '是否激活',
    created_by VARCHAR(100) COMMENT '创建人',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    FOREIGN KEY (group_id) REFERENCES synonym_groups(id) ON DELETE CASCADE,
    UNIQUE KEY unique_group_term (group_id, term),
    INDEX idx_term (term),
    INDEX idx_confidence (confidence),
    INDEX idx_usage_count (usage_count),
    INDEX idx_active (is_active)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='同义词条表';

-- 12. 停用词表
CREATE TABLE IF NOT EXISTS stop_words (
    id INT PRIMARY KEY AUTO_INCREMENT,
    word VARCHAR(50) UNIQUE NOT NULL COMMENT '停用词',
    category VARCHAR(30) COMMENT '分类',
    language VARCHAR(10) DEFAULT 'zh' COMMENT '语言',
    is_active BOOLEAN DEFAULT TRUE COMMENT '是否激活',
    created_by VARCHAR(100) COMMENT '创建人',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    INDEX idx_word (word),
    INDEX idx_category (category),
    INDEX idx_language (language),
    INDEX idx_active (is_active)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='停用词表';

-- 13. 实体识别模式表
CREATE TABLE IF NOT EXISTS entity_patterns (
    id INT PRIMARY KEY AUTO_INCREMENT,
    pattern_name VARCHAR(50) UNIQUE NOT NULL COMMENT '模式名称',
    pattern_regex TEXT NOT NULL COMMENT '正则表达式',
    entity_type VARCHAR(50) NOT NULL COMMENT '实体类型',
    description TEXT COMMENT '描述',
    examples JSON COMMENT '示例',
    confidence DECIMAL(5,4) DEFAULT 0.9000 COMMENT '置信度',
    is_active BOOLEAN DEFAULT TRUE COMMENT '是否激活',
    priority INT DEFAULT 1 COMMENT '优先级',
    created_by VARCHAR(100) COMMENT '创建人',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    INDEX idx_pattern_name (pattern_name),
    INDEX idx_entity_type (entity_type),
    INDEX idx_active (is_active),
    INDEX idx_priority (priority)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='实体识别模式表';

-- ================================
-- 扩展表和日志表
-- ================================

-- 14. 实体类型表
CREATE TABLE IF NOT EXISTS entity_types (
    id INT PRIMARY KEY AUTO_INCREMENT,
    type_name VARCHAR(50) UNIQUE NOT NULL COMMENT '实体类型名称',
    display_name VARCHAR(100) NOT NULL COMMENT '显示名称',
    description TEXT COMMENT '描述',
    validation_pattern VARCHAR(500) COMMENT '验证模式',
    examples JSON COMMENT '示例',
    is_active BOOLEAN DEFAULT TRUE COMMENT '是否激活',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='实体类型表';

-- 15. 其他支持表（简化版）
CREATE TABLE IF NOT EXISTS slot_dependencies (
    id INT PRIMARY KEY AUTO_INCREMENT,
    parent_slot_id INT NOT NULL,
    child_slot_id INT NOT NULL,
    dependency_type VARCHAR(50) DEFAULT 'required_if',
    conditions JSON,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='槽位依赖表';

CREATE TABLE IF NOT EXISTS intent_ambiguities (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    conversation_id BIGINT NOT NULL,
    candidate_intents JSON NOT NULL,
    resolution_strategy VARCHAR(50),
    resolved_intent VARCHAR(100),
    user_choice VARCHAR(100),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='意图歧义处理表';

-- ================================
-- 初始化数据
-- ================================

-- 插入响应类型
INSERT INTO response_types (type_name, display_name, description, template, is_active) VALUES
('success', '成功响应', '操作成功时的响应', '✅ {message}', TRUE),
('error', '错误响应', '操作失败时的响应', '❌ {message}', TRUE),
('clarification', '澄清响应', '需要用户澄清时的响应', '🤔 {message}', TRUE),
('slot_collection', '槽位收集', '收集槽位信息时的响应', '📝 {message}', TRUE),
('confirmation', '确认响应', '需要用户确认时的响应', '✋ {message}', TRUE),
('fallback', '兜底响应', '无法处理时的兜底响应', '🤖 {message}', TRUE);

-- 插入会话状态
INSERT INTO conversation_statuses (status_name, display_name, description, is_final) VALUES
('active', '进行中', '对话正在进行', FALSE),
('completed', '已完成', '对话已成功完成', TRUE),
('failed', '失败', '对话处理失败', TRUE),
('timeout', '超时', '对话超时', TRUE),
('cancelled', '已取消', '对话被取消', TRUE);

-- 插入基础意图
INSERT INTO intents (intent_name, display_name, description, confidence_threshold, priority, category, is_active, examples, fallback_response, created_by, created_at, updated_at) VALUES
-- 订机票意图
('book_flight', '订机票', '帮助用户预订航班机票', 0.7000, 1, 'travel', TRUE, 
'["我想订一张明天去上海的机票", "帮我预订机票", "我要买机票", "订一张机票", "我想订机票", "预订航班", "购买机票", "我要去北京，帮我订机票", "明天的航班有吗", "我需要订一张机票", "帮我查一下机票", "想要预订明天的航班", "我要订一张去广州的机票", "机票预订", "航班预订", "买机票", "订机票", "book a flight", "book flight ticket", "I want to book a flight"]',
'抱歉，我无法为您预订机票。请提供出发城市、到达城市和出发日期等信息。', 'system', NOW(), NOW()),

-- 查询账户余额意图
('check_balance', '查询账户余额', '查询用户银行账户或电子钱包余额', 0.7000, 1, 'banking', TRUE,
'["查询余额", "我的余额", "账户余额", "余额查询", "帮我查下余额", "我想知道我的余额", "账户里还有多少钱", "查一下我的余额", "银行卡余额", "我的账户余额是多少", "余额是多少", "查询银行卡余额", "我要查余额", "check balance", "account balance", "my balance"]',
'抱歉，我无法查询您的账户余额。请提供有效的账户信息。', 'system', NOW(), NOW()),

-- 问候意图
('greeting', '问候', '用户问候和打招呼', 0.8000, 0, 'general', TRUE,
'["你好", "您好", "早上好", "下午好", "晚上好", "hello", "hi", "嗨", "在吗", "在不在"]',
'您好！我是智能客服助手，很高兴为您服务。我可以帮您订机票、查询账户余额等。请问有什么可以帮助您的吗？', 'system', NOW(), NOW()),

-- 再见意图
('goodbye', '再见', '用户告别和结束对话', 0.8000, 0, 'general', TRUE,
'["再见", "拜拜", "谢谢", "没事了", "结束", "退出", "bye", "goodbye", "不用了", "好的，谢谢"]',
'感谢您的使用，再见！如果还有其他需要，随时可以联系我。', 'system', NOW(), NOW());

-- 插入槽位配置
INSERT INTO slots (intent_id, slot_name, display_name, slot_type, is_required, is_list, validation_rules, default_value, prompt_template, error_message, extraction_priority, is_active, created_at, updated_at) VALUES
-- 订机票相关槽位
((SELECT id FROM intents WHERE intent_name = 'book_flight'), 'departure_city', '出发城市', 'entity', TRUE, FALSE,
'{"entity_type": "CITY", "examples": ["北京", "上海", "广州", "深圳", "杭州"], "validation_pattern": "^[\\\\u4e00-\\\\u9fa5]{2,10}$"}',
NULL, '请问您从哪个城市出发？', '请提供有效的出发城市名称', 1, TRUE, NOW(), NOW()),

((SELECT id FROM intents WHERE intent_name = 'book_flight'), 'arrival_city', '到达城市', 'entity', TRUE, FALSE,
'{"entity_type": "CITY", "examples": ["北京", "上海", "广州", "深圳", "杭州"], "validation_pattern": "^[\\\\u4e00-\\\\u9fa5]{2,10}$"}',
NULL, '请问您要到哪个城市？', '请提供有效的到达城市名称', 2, TRUE, NOW(), NOW()),

((SELECT id FROM intents WHERE intent_name = 'book_flight'), 'departure_date', '出发日期', 'date', TRUE, FALSE,
'{"format": "YYYY-MM-DD", "examples": ["明天", "后天", "下周一", "2024-12-15"]}',
NULL, '请问您希望什么时候出发？', '请提供有效的出发日期', 3, TRUE, NOW(), NOW()),

((SELECT id FROM intents WHERE intent_name = 'book_flight'), 'passenger_count', '乘客数量', 'number', FALSE, FALSE,
'{"min_value": 1, "max_value": 9, "examples": ["1", "2", "3", "一个人", "两个人"]}',
'1', '请问您需要预订几位乘客的机票？', '乘客数量必须在1-9之间', 4, TRUE, NOW(), NOW()),

-- 查询余额相关槽位
((SELECT id FROM intents WHERE intent_name = 'check_balance'), 'account_type', '账户类型', 'text', FALSE, FALSE,
'{"allowed_values": ["银行卡", "储蓄卡", "信用卡", "支付宝", "微信"], "examples": ["银行卡", "储蓄卡", "信用卡"]}',
'银行卡', '请问您要查询哪种账户的余额？', '请选择有效的账户类型', 1, TRUE, NOW(), NOW());

-- 插入系统配置
INSERT INTO system_configs (config_category, config_key, config_value, value_type, description, is_encrypted, is_public, validation_rule, default_value, is_active, created_by, created_at, updated_at) VALUES
('nlu', 'intent_confidence_threshold', '0.7', 'number', '意图识别置信度阈值', FALSE, TRUE, '{"min": 0.1, "max": 1.0}', '0.7', TRUE, 'system', NOW(), NOW()),
('session', 'session_timeout_seconds', '86400', 'number', '会话超时时间（秒）', FALSE, TRUE, '{"min": 300, "max": 604800}', '86400', TRUE, 'system', NOW(), NOW()),
('api', 'api_call_timeout', '30', 'number', 'API调用超时时间（秒）', FALSE, TRUE, '{"min": 5, "max": 120}', '30', TRUE, 'system', NOW(), NOW()),
('api', 'max_retry_attempts', '3', 'number', '最大重试次数', FALSE, TRUE, '{"min": 0, "max": 10}', '3', TRUE, 'system', NOW(), NOW()),
('business', 'enable_intent_confirmation', 'true', 'boolean', '是否启用意图确认', FALSE, TRUE, NULL, 'true', TRUE, 'system', NOW(), NOW()),
('system', 'system_version', '2.3.0', 'string', '系统版本号', FALSE, TRUE, NULL, '2.3.0', TRUE, 'system', NOW(), NOW());

-- 插入同义词组
INSERT INTO synonym_groups (group_name, standard_term, category, description, created_by, created_at, updated_at) VALUES
('如何询问', '如何', 'question', '询问方式的同义词', 'system', NOW(), NOW()),
('查询操作', '查询', 'action', '查询相关的动作词', 'system', NOW(), NOW()),
('购买操作', '购买', 'action', '购买、采购相关的动作词', 'system', NOW(), NOW()),
('账户相关', '账户', 'entity', '账户、账号相关词汇', 'system', NOW(), NOW()),
('余额概念', '余额', 'entity', '余额、结余相关词汇', 'system', NOW(), NOW()),
('银行卡类型', '银行卡', 'entity', '各种银行卡类型', 'system', NOW(), NOW()),
('机票概念', '机票', 'entity', '机票、航班相关词汇', 'system', NOW(), NOW()),
('预订操作', '预订', 'action', '预订、预约相关动作', 'system', NOW(), NOW()),
('取消操作', '取消', 'action', '取消、撤销相关动作', 'system', NOW(), NOW()),
('修改操作', '修改', 'action', '修改、更改相关动作', 'system', NOW(), NOW()),
('问题概念', '问题', 'entity', '问题、故障相关词汇', 'system', NOW(), NOW()),
('帮助概念', '帮助', 'action', '帮助、协助相关词汇', 'system', NOW(), NOW());

-- 插入同义词条
INSERT INTO synonym_terms (group_id, term, confidence, created_by, created_at, updated_at) VALUES
-- 如何询问
((SELECT id FROM synonym_groups WHERE group_name = '如何询问'), '怎样', 0.9500, 'system', NOW(), NOW()),
((SELECT id FROM synonym_groups WHERE group_name = '如何询问'), '怎么', 0.9500, 'system', NOW(), NOW()),
((SELECT id FROM synonym_groups WHERE group_name = '如何询问'), '如何才能', 0.9000, 'system', NOW(), NOW()),
((SELECT id FROM synonym_groups WHERE group_name = '如何询问'), '怎么样', 0.8500, 'system', NOW(), NOW()),

-- 查询操作
((SELECT id FROM synonym_groups WHERE group_name = '查询操作'), '查看', 0.9000, 'system', NOW(), NOW()),
((SELECT id FROM synonym_groups WHERE group_name = '查询操作'), '搜索', 0.9000, 'system', NOW(), NOW()),
((SELECT id FROM synonym_groups WHERE group_name = '查询操作'), '寻找', 0.8500, 'system', NOW(), NOW()),
((SELECT id FROM synonym_groups WHERE group_name = '查询操作'), '找到', 0.8500, 'system', NOW(), NOW()),
((SELECT id FROM synonym_groups WHERE group_name = '查询操作'), '获取', 0.8000, 'system', NOW(), NOW()),

-- 购买操作
((SELECT id FROM synonym_groups WHERE group_name = '购买操作'), '买', 0.9500, 'system', NOW(), NOW()),
((SELECT id FROM synonym_groups WHERE group_name = '购买操作'), '购入', 0.8500, 'system', NOW(), NOW()),
((SELECT id FROM synonym_groups WHERE group_name = '购买操作'), '采购', 0.8000, 'system', NOW(), NOW()),
((SELECT id FROM synonym_groups WHERE group_name = '购买操作'), '订购', 0.9000, 'system', NOW(), NOW()),

-- 账户相关
((SELECT id FROM synonym_groups WHERE group_name = '账户相关'), '账号', 0.9500, 'system', NOW(), NOW()),
((SELECT id FROM synonym_groups WHERE group_name = '账户相关'), '帐户', 0.9500, 'system', NOW(), NOW()),
((SELECT id FROM synonym_groups WHERE group_name = '账户相关'), '用户', 0.8000, 'system', NOW(), NOW()),
((SELECT id FROM synonym_groups WHERE group_name = '账户相关'), '个人', 0.7500, 'system', NOW(), NOW()),

-- 余额概念
((SELECT id FROM synonym_groups WHERE group_name = '余额概念'), '结余', 0.9000, 'system', NOW(), NOW()),
((SELECT id FROM synonym_groups WHERE group_name = '余额概念'), '剩余', 0.8500, 'system', NOW(), NOW()),
((SELECT id FROM synonym_groups WHERE group_name = '余额概念'), '可用金额', 0.8000, 'system', NOW(), NOW()),

-- 银行卡类型
((SELECT id FROM synonym_groups WHERE group_name = '银行卡类型'), '储蓄卡', 0.9500, 'system', NOW(), NOW()),
((SELECT id FROM synonym_groups WHERE group_name = '银行卡类型'), '借记卡', 0.9500, 'system', NOW(), NOW()),
((SELECT id FROM synonym_groups WHERE group_name = '银行卡类型'), '信用卡', 0.9000, 'system', NOW(), NOW()),
((SELECT id FROM synonym_groups WHERE group_name = '银行卡类型'), '卡片', 0.7500, 'system', NOW(), NOW()),

-- 机票概念
((SELECT id FROM synonym_groups WHERE group_name = '机票概念'), '飞机票', 0.9500, 'system', NOW(), NOW()),
((SELECT id FROM synonym_groups WHERE group_name = '机票概念'), '航班', 0.9000, 'system', NOW(), NOW()),
((SELECT id FROM synonym_groups WHERE group_name = '机票概念'), '班机', 0.8500, 'system', NOW(), NOW()),
((SELECT id FROM synonym_groups WHERE group_name = '机票概念'), '机位', 0.8000, 'system', NOW(), NOW()),

-- 预订操作
((SELECT id FROM synonym_groups WHERE group_name = '预订操作'), '预约', 0.9000, 'system', NOW(), NOW()),
((SELECT id FROM synonym_groups WHERE group_name = '预订操作'), '订购', 0.8500, 'system', NOW(), NOW()),
((SELECT id FROM synonym_groups WHERE group_name = '预订操作'), '预定', 0.9500, 'system', NOW(), NOW()),
((SELECT id FROM synonym_groups WHERE group_name = '预订操作'), '订票', 0.9000, 'system', NOW(), NOW()),

-- 取消操作
((SELECT id FROM synonym_groups WHERE group_name = '取消操作'), '撤销', 0.9000, 'system', NOW(), NOW()),
((SELECT id FROM synonym_groups WHERE group_name = '取消操作'), '退订', 0.9500, 'system', NOW(), NOW()),
((SELECT id FROM synonym_groups WHERE group_name = '取消操作'), '作废', 0.8500, 'system', NOW(), NOW()),
((SELECT id FROM synonym_groups WHERE group_name = '取消操作'), '终止', 0.8000, 'system', NOW(), NOW()),

-- 修改操作
((SELECT id FROM synonym_groups WHERE group_name = '修改操作'), '更改', 0.9500, 'system', NOW(), NOW()),
((SELECT id FROM synonym_groups WHERE group_name = '修改操作'), '变更', 0.9000, 'system', NOW(), NOW()),
((SELECT id FROM synonym_groups WHERE group_name = '修改操作'), '调整', 0.8500, 'system', NOW(), NOW()),
((SELECT id FROM synonym_groups WHERE group_name = '修改操作'), '编辑', 0.8000, 'system', NOW(), NOW()),

-- 问题概念
((SELECT id FROM synonym_groups WHERE group_name = '问题概念'), '故障', 0.9000, 'system', NOW(), NOW()),
((SELECT id FROM synonym_groups WHERE group_name = '问题概念'), '错误', 0.9000, 'system', NOW(), NOW()),
((SELECT id FROM synonym_groups WHERE group_name = '问题概念'), '异常', 0.8500, 'system', NOW(), NOW()),
((SELECT id FROM synonym_groups WHERE group_name = '问题概念'), '困难', 0.8000, 'system', NOW(), NOW()),

-- 帮助概念
((SELECT id FROM synonym_groups WHERE group_name = '帮助概念'), '协助', 0.9000, 'system', NOW(), NOW()),
((SELECT id FROM synonym_groups WHERE group_name = '帮助概念'), '支持', 0.8500, 'system', NOW(), NOW()),
((SELECT id FROM synonym_groups WHERE group_name = '帮助概念'), '指导', 0.8500, 'system', NOW(), NOW()),
((SELECT id FROM synonym_groups WHERE group_name = '帮助概念'), '援助', 0.8000, 'system', NOW(), NOW());

-- 插入停用词
INSERT INTO stop_words (word, category, language, created_by, created_at, updated_at) VALUES
-- 助词
('的', 'particle', 'zh', 'system', NOW(), NOW()),
('了', 'particle', 'zh', 'system', NOW(), NOW()),
('在', 'preposition', 'zh', 'system', NOW(), NOW()),
('是', 'verb', 'zh', 'system', NOW(), NOW()),
('有', 'verb', 'zh', 'system', NOW(), NOW()),
('和', 'conjunction', 'zh', 'system', NOW(), NOW()),
('就', 'adverb', 'zh', 'system', NOW(), NOW()),
('不', 'adverb', 'zh', 'system', NOW(), NOW()),
('人', 'noun', 'zh', 'system', NOW(), NOW()),
('都', 'adverb', 'zh', 'system', NOW(), NOW()),
('一', 'number', 'zh', 'system', NOW(), NOW()),
('个', 'classifier', 'zh', 'system', NOW(), NOW()),
('上', 'preposition', 'zh', 'system', NOW(), NOW()),
('也', 'adverb', 'zh', 'system', NOW(), NOW()),
('很', 'adverb', 'zh', 'system', NOW(), NOW()),
('到', 'verb', 'zh', 'system', NOW(), NOW()),
('说', 'verb', 'zh', 'system', NOW(), NOW()),
('要', 'verb', 'zh', 'system', NOW(), NOW()),
('去', 'verb', 'zh', 'system', NOW(), NOW()),
('你', 'pronoun', 'zh', 'system', NOW(), NOW()),
('会', 'verb', 'zh', 'system', NOW(), NOW()),
('着', 'particle', 'zh', 'system', NOW(), NOW()),
('没有', 'verb', 'zh', 'system', NOW(), NOW()),
('看', 'verb', 'zh', 'system', NOW(), NOW()),
('好', 'adjective', 'zh', 'system', NOW(), NOW()),
('自己', 'pronoun', 'zh', 'system', NOW(), NOW()),
('这', 'pronoun', 'zh', 'system', NOW(), NOW()),
('那', 'pronoun', 'zh', 'system', NOW(), NOW()),
('些', 'classifier', 'zh', 'system', NOW(), NOW()),
-- 疑问词
('什么', 'question', 'zh', 'system', NOW(), NOW()),
('怎么', 'question', 'zh', 'system', NOW(), NOW()),
('为什么', 'question', 'zh', 'system', NOW(), NOW()),
('吗', 'particle', 'zh', 'system', NOW(), NOW()),
('呢', 'particle', 'zh', 'system', NOW(), NOW()),
('吧', 'particle', 'zh', 'system', NOW(), NOW()),
('啊', 'particle', 'zh', 'system', NOW(), NOW()),
('哦', 'particle', 'zh', 'system', NOW(), NOW()),
('哪', 'question', 'zh', 'system', NOW(), NOW()),
('那么', 'adverb', 'zh', 'system', NOW(), NOW()),
('这么', 'adverb', 'zh', 'system', NOW(), NOW()),
-- 常用动词
('可以', 'verb', 'zh', 'system', NOW(), NOW()),
('能够', 'verb', 'zh', 'system', NOW(), NOW()),
('应该', 'verb', 'zh', 'system', NOW(), NOW()),
('需要', 'verb', 'zh', 'system', NOW(), NOW()),
('想要', 'verb', 'zh', 'system', NOW(), NOW()),
('希望', 'verb', 'zh', 'system', NOW(), NOW()),
('帮助', 'verb', 'zh', 'system', NOW(), NOW()),
('告诉', 'verb', 'zh', 'system', NOW(), NOW()),
('知道', 'verb', 'zh', 'system', NOW(), NOW()),
('了解', 'verb', 'zh', 'system', NOW(), NOW()),
('明白', 'verb', 'zh', 'system', NOW(), NOW()),
('清楚', 'adjective', 'zh', 'system', NOW(), NOW());

-- 插入实体识别模式
INSERT INTO entity_patterns (pattern_name, pattern_regex, entity_type, description, examples, confidence, created_by, created_at, updated_at) VALUES
('手机号码', '1[3-9]\\d{9}', 'PHONE', '中国大陆手机号码', '["13800138000", "18912345678"]', 0.9500, 'system', NOW(), NOW()),
('邮箱地址', '[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\\.[a-zA-Z]{2,}', 'EMAIL', '电子邮箱地址', '["example@email.com", "user@domain.com"]', 0.9000, 'system', NOW(), NOW()),
('身份证号', '\\d{15}|\\d{18}', 'ID_CARD', '身份证号码', '["110101199001011234", "11010119900101123X"]', 0.9500, 'system', NOW(), NOW()),
('银行卡号', '\\d{16,19}', 'BANK_CARD', '银行卡号', '["6222080012345678", "62220800123456789"]', 0.9000, 'system', NOW(), NOW()),
('金额', '[0-9,]+(?:\\.[0-9]+)?(?:元|块|万|千|百)?', 'AMOUNT', '金额表达', '["100元", "1000块", "1.5万"]', 0.8500, 'system', NOW(), NOW()),
('日期', '\\d{4}[-/年]\\d{1,2}[-/月]\\d{1,2}[日号]?', 'DATE', '日期表达', '["2024-01-01", "2024年1月1日"]', 0.8500, 'system', NOW(), NOW()),
('时间', '\\d{1,2}[:|：]\\d{1,2}', 'TIME', '时间表达', '["14:30", "上午9点"]', 0.8000, 'system', NOW(), NOW()),
('航班号', '[A-Z]{2}\\d{3,4}', 'FLIGHT', '航班号', '["CA1234", "MU5678"]', 0.9500, 'system', NOW(), NOW()),
('机场代码', '[A-Z]{3}', 'AIRPORT', '三字机场代码', '["PEK", "SHA", "CAN"]', 0.9000, 'system', NOW(), NOW()),
('中国城市', '[北京|上海|广州|深圳|杭州|南京|武汉|成都|西安|重庆|天津|青岛|大连|厦门|苏州|无锡|宁波|长沙|郑州|济南|哈尔滨|沈阳|长春|石家庄|太原|呼和浩特|兰州|西宁|银川|乌鲁木齐|拉萨|昆明|贵阳|南宁|海口|三亚|福州|南昌|合肥]+', 'CITY', '中国主要城市', '["北京", "上海", "广州"]', 0.8500, 'system', NOW(), NOW());

-- 插入实体类型
INSERT INTO entity_types (type_name, display_name, description, validation_pattern, examples, is_active) VALUES
('CITY', '城市', '中国城市名称', '^[\\u4e00-\\u9fa5]{2,10}$', 
'["北京", "上海", "广州", "深圳", "杭州"]', TRUE),
('DATE', '日期', '日期信息', NULL,
'["明天", "后天", "下周一", "2024-12-15"]', TRUE),
('NUMBER', '数字', '数字信息', '^[0-9]+$',
'["1", "2", "3", "10"]', TRUE),
('PHONE', '电话号码', '手机号码', '^1[3-9]\\d{9}$',
'["13800138000", "18912345678"]', TRUE),
('EMAIL', '邮箱地址', '电子邮箱', '^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\\.[a-zA-Z]{2,}$',
'["example@email.com", "user@domain.com"]', TRUE);

-- ================================
-- 显示初始化结果
-- ================================

SELECT '=== 数据库初始化完成 v2.3 ===' AS status;
SELECT COUNT(*) AS intents_count, '个意图' AS description FROM intents;
SELECT COUNT(*) AS slots_count, '个槽位' AS description FROM slots;
SELECT COUNT(*) AS response_types_count, '个响应类型' AS description FROM response_types;
SELECT COUNT(*) AS system_configs_count, '个系统配置' AS description FROM system_configs;
SELECT COUNT(*) AS synonym_groups_count, '个同义词组' AS description FROM synonym_groups;
SELECT COUNT(*) AS synonym_terms_count, '个同义词条' AS description FROM synonym_terms;
SELECT COUNT(*) AS stop_words_count, '个停用词' AS description FROM stop_words;
SELECT COUNT(*) AS entity_patterns_count, '个实体模式' AS description FROM entity_patterns;

-- 显示意图列表
SELECT 
    intent_name AS '意图名称',
    display_name AS '显示名称', 
    category AS '分类',
    JSON_LENGTH(examples) AS '示例数量',
    is_active AS '状态'
FROM intents 
ORDER BY priority DESC, intent_name;

-- 显示同义词组统计
SELECT 
    category AS '分类',
    COUNT(*) AS '词组数量'
FROM synonym_groups 
WHERE is_active = TRUE
GROUP BY category
ORDER BY COUNT(*) DESC;