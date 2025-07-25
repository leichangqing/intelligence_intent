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
DROP TABLE IF EXISTS conversation_status;
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
    sort_order INT DEFAULT 1 COMMENT '排序顺序',
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
CREATE TABLE IF NOT EXISTS conversation_status (
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
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    INDEX idx_session_id (session_id),
    INDEX idx_user_id (user_id),
    INDEX idx_intent (intent_recognized),
    INDEX idx_status (status),
    INDEX idx_created_at (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='对话记录表';

-- ================================
-- 功能扩展表
-- ================================

-- 7.5. 函数定义表
CREATE TABLE IF NOT EXISTS functions (
    id INT PRIMARY KEY AUTO_INCREMENT,
    function_name VARCHAR(100) NOT NULL COMMENT '函数名称',
    intent_name VARCHAR(100) NOT NULL COMMENT '关联意图名称',
    description TEXT COMMENT '函数描述',
    function_type VARCHAR(50) DEFAULT 'api_call' COMMENT '函数类型',
    endpoint_url VARCHAR(500) COMMENT 'API端点',
    http_method VARCHAR(10) DEFAULT 'POST' COMMENT 'HTTP方法',
    headers JSON COMMENT '请求头',
    parameters JSON COMMENT '参数定义',
    timeout_seconds INT DEFAULT 30 COMMENT '超时时间',
    retry_count INT DEFAULT 3 COMMENT '重试次数',
    is_active BOOLEAN DEFAULT TRUE COMMENT '是否激活',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    INDEX idx_function_name (function_name),
    INDEX idx_intent_name (intent_name),
    INDEX idx_active (is_active)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='函数定义表';

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

-- 7. 配置审计日志表
CREATE TABLE IF NOT EXISTS config_audit_logs (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    table_name VARCHAR(50) NOT NULL COMMENT '表名',
    -- v2.2 改进: 将record_id类型改为BIGINT以匹配大多数主键类型，增强数据一致性。
    record_id BIGINT NOT NULL COMMENT '记录ID',
    action ENUM('INSERT', 'UPDATE', 'DELETE') NOT NULL COMMENT '操作类型',
    old_values JSON COMMENT '修改前的值',
    new_values JSON COMMENT '修改后的值',
    operator_id VARCHAR(100) NOT NULL COMMENT '操作者ID',
    operator_name VARCHAR(100) COMMENT '操作者姓名',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_table_record (table_name, record_id),
    INDEX idx_operator (operator_id),
    INDEX idx_created_at (created_at)
) COMMENT='配置审计日志表';

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

-- 13.5. Prompt模板配置表
CREATE TABLE IF NOT EXISTS prompt_templates (
    id INT PRIMARY KEY AUTO_INCREMENT,
    template_name VARCHAR(100) UNIQUE NOT NULL COMMENT '模板名称',
    template_type ENUM('intent_recognition', 'slot_filling', 'response_generation', 'disambiguation', 'fallback') NOT NULL COMMENT '模板类型',
    intent_id INT COMMENT '关联意图ID(可选)',
    template_content TEXT NOT NULL COMMENT '模板内容',
    variables JSON COMMENT '模板变量定义',
    language VARCHAR(10) DEFAULT 'zh' COMMENT '语言',
    version VARCHAR(20) DEFAULT '1.0' COMMENT '版本号',
    priority INT DEFAULT 1 COMMENT '优先级',
    usage_count INT DEFAULT 0 COMMENT '使用次数',
    success_rate DECIMAL(5,4) DEFAULT 0.0000 COMMENT '成功率',
    is_active BOOLEAN DEFAULT TRUE COMMENT '是否激活',
    created_by VARCHAR(100) COMMENT '创建人',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    FOREIGN KEY (intent_id) REFERENCES intents(id) ON DELETE SET NULL,
    INDEX idx_template_type (template_type),
    INDEX idx_intent_id (intent_id),
    INDEX idx_language (language),
    INDEX idx_priority (priority),
    INDEX idx_active (is_active)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='Prompt模板配置表';

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
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间'
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
('success', '成功响应', '操作成功时的响应', '[成功] {message}', TRUE),
('error', '错误响应', '操作失败时的响应', '[错误] {message}', TRUE),
('clarification', '澄清响应', '需要用户澄清时的响应', '[疑问] {message}', TRUE),
('slot_collection', '槽位收集', '收集槽位信息时的响应', '[询问] {message}', TRUE),
('confirmation', '确认响应', '需要用户确认时的响应', '[确认] {message}', TRUE),
('fallback', '兜底响应', '无法处理时的兜底响应', '[系统] {message}', TRUE);

-- 插入会话状态
INSERT INTO conversation_status (status_name, display_name, description, is_final) VALUES
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

-- 插入Prompt模板
INSERT INTO prompt_templates (template_name, template_type, intent_id, template_content, variables, language, version, priority, usage_count, success_rate, is_active, created_by, created_at, updated_at) VALUES
-- 订机票相关模板
('book_flight_recognition', 'intent_recognition', 1, 
 '根据用户输入判断是否为订机票意图：\n\n用户输入：{user_input}\n\n判断规则：\n1. 包含\"订\"、\"买\"、\"预订\"、\"购买\"等动作词\n2. 包含\"机票\"、\"航班\"、\"飞机票\"等关键词\n3. 可能包含出发地、目的地、时间等信息\n\n请分析并返回：\n- 意图识别结果：{intent_name}\n- 置信度：{confidence}\n- 匹配关键词：{matched_keywords}',
 '{"user_input": "用户原始输入", "intent_name": "意图名称", "confidence": "置信度分数", "matched_keywords": "匹配的关键词列表"}',
 'zh', '1.0', 1, 0, 0.0000, TRUE, 'system', NOW(), NOW()),

('book_flight_slot_filling', 'slot_filling', 1,
 '请从用户输入中提取订机票相关信息：\n\n用户输入：{user_input}\n当前已知信息：{current_slots}\n\n需要提取的槽位：\n- departure_city（出发城市）\n- arrival_city（到达城市）\n- departure_date（出发日期）\n- passenger_count（乘客数量，默认为1）\n\n提取规则：\n1. 城市名称：识别中国主要城市名\n2. 日期：支持\"明天\"、\"后天\"、\"下周一\"等相对时间\n3. 数量：识别\"一个人\"、\"两位\"、\"3人\"等表达\n\n请返回JSON格式的提取结果。',
 '{"user_input": "用户输入", "current_slots": "当前槽位状态"}',
 'zh', '1.0', 1, 0, 0.0000, TRUE, 'system', NOW(), NOW()),

('book_flight_response', 'response_generation', 1,
 '根据槽位填充情况生成订机票响应：\n\n已填充槽位：{filled_slots}\n缺失槽位：{missing_slots}\n意图：{intent}\n\n响应规则：\n1. 如果槽位完整：确认订票信息并询问是否继续\n2. 如果缺失必填槽位：友好询问缺失信息\n3. 如果信息有误：提示用户纠正\n\n生成自然、友好的中文响应。',
 '{"filled_slots": "已填充的槽位", "missing_slots": "缺失的槽位", "intent": "当前意图"}',
 'zh', '1.0', 1, 0, 0.0000, TRUE, 'system', NOW(), NOW()),

('book_flight_disambiguation', 'disambiguation', 1,
 '订机票意图存在歧义，需要用户澄清：\n\n候选选项：{candidates}\n用户输入：{user_input}\n\n请生成友好的澄清问题，帮助用户选择正确的选项。格式：\n\"我理解您想要订机票，请问您是想要：\n1. [选项1描述]\n2. [选项2描述]\n请选择对应的数字。\"',
 '{"candidates": "候选意图列表", "user_input": "用户原始输入"}',
 'zh', '1.0', 2, 0, 0.0000, TRUE, 'system', NOW(), NOW()),

-- 查账户余额相关模板
('check_balance_recognition', 'intent_recognition', 2,
 '根据用户输入判断是否为查询账户余额意图：\n\n用户输入：{user_input}\n\n判断规则：\n1. 包含\"查询\"、\"查看\"、\"查\"、\"看\"等动作词\n2. 包含\"余额\"、\"结余\"、\"剩余\"、\"账户\"、\"钱\"等关键词\n3. 可能包含账户类型（银行卡、信用卡、支付宝等）\n\n请分析并返回：\n- 意图识别结果：{intent_name}\n- 置信度：{confidence}\n- 匹配关键词：{matched_keywords}',
 '{"user_input": "用户原始输入", "intent_name": "意图名称", "confidence": "置信度分数", "matched_keywords": "匹配的关键词列表"}',
 'zh', '1.0', 1, 0, 0.0000, TRUE, 'system', NOW(), NOW()),

('check_balance_slot_filling', 'slot_filling', 2,
 '请从用户输入中提取查询余额相关信息：\n\n用户输入：{user_input}\n当前已知信息：{current_slots}\n\n需要提取的槽位：\n- account_type（账户类型）：银行卡、储蓄卡、信用卡、支付宝、微信等\n\n提取规则：\n1. 如果未明确指定账户类型，默认为\"银行卡\"\n2. 识别常见的账户类型表达\n3. 支持多种同义词表达\n\n请返回JSON格式的提取结果。',
 '{"user_input": "用户输入", "current_slots": "当前槽位状态"}',
 'zh', '1.0', 1, 0, 0.0000, TRUE, 'system', NOW(), NOW()),

('check_balance_response', 'response_generation', 2,
 '根据槽位填充情况生成查询余额响应：\n\n已填充槽位：{filled_slots}\n缺失槽位：{missing_slots}\n意图：{intent}\n\n响应规则：\n1. 如果槽位完整：确认查询的账户类型\n2. 如果缺失账户类型：询问具体要查询哪种账户\n3. 提供安全提示：不会显示完整账户信息\n\n生成专业、安全的中文响应。',
 '{"filled_slots": "已填充的槽位", "missing_slots": "缺失的槽位", "intent": "当前意图"}',
 'zh', '1.0', 1, 0, 0.0000, TRUE, 'system', NOW(), NOW()),

('check_balance_disambiguation', 'disambiguation', 2,
 '查询余额意图存在歧义，需要用户澄清：\n\n候选选项：{candidates}\n用户输入：{user_input}\n\n请生成友好的澄清问题，帮助用户选择正确的账户类型。格式：\n\"我理解您想要查询余额，请问您是想查询：\n1. [账户类型1]\n2. [账户类型2]\n请选择对应的数字。\"',
 '{"candidates": "候选选项列表", "user_input": "用户原始输入"}',
 'zh', '1.0', 2, 0, 0.0000, TRUE, 'system', NOW(), NOW()),

-- 通用模板
('general_intent_recognition', 'intent_recognition', NULL,
 '请分析用户输入并识别意图：\n\n用户输入：{user_input}\n可用意图：{available_intents}\n\n分析步骤：\n1. 识别关键动作词和名词\n2. 匹配已知意图模式\n3. 计算相似度得分\n4. 返回最匹配的意图和置信度\n\n输出格式：JSON',
 '{"user_input": "用户输入", "available_intents": "可用意图列表"}',
 'zh', '1.0', 0, 0, 0.0000, TRUE, 'system', NOW(), NOW()),

('general_slot_filling', 'slot_filling', NULL,
 '从用户输入中提取槽位信息：\n\n用户输入：{user_input}\n意图：{intent}\n槽位定义：{slot_definitions}\n当前槽位：{current_slots}\n\n提取规则：\n1. 根据槽位类型进行相应的实体识别\n2. 验证提取值的有效性\n3. 处理多值槽位\n4. 标注置信度\n\n返回提取结果的JSON格式。',
 '{"user_input": "用户输入", "intent": "意图名称", "slot_definitions": "槽位定义", "current_slots": "当前槽位状态"}',
 'zh', '1.0', 0, 0, 0.0000, TRUE, 'system', NOW(), NOW()),

('general_response_generation', 'response_generation', NULL,
 '生成自然语言响应：\n\n意图：{intent}\n槽位状态：{slot_status}\n系统状态：{system_status}\n\n生成规则：\n1. 使用友好、专业的语调\n2. 根据槽位完整性决定响应类型\n3. 提供清晰的下一步指引\n4. 避免技术术语\n\n请生成合适的中文响应。',
 '{"intent": "当前意图", "slot_status": "槽位状态", "system_status": "系统状态"}',
 'zh', '1.0', 0, 0, 0.0000, TRUE, 'system', NOW(), NOW()),

('general_disambiguation', 'disambiguation', NULL,
 '处理多意图歧义情况：\n\n用户输入：{user_input}\n候选意图：{candidate_intents}\n置信度分布：{confidence_scores}\n\n消歧策略：\n1. 分析各候选意图的特征\n2. 生成清晰的选择提示\n3. 提供具体的区分说明\n4. 引导用户明确表达意图\n\n生成友好的澄清问题。',
 '{"user_input": "用户输入", "candidate_intents": "候选意图", "confidence_scores": "置信度分数"}',
 'zh', '1.0', 1, 0, 0.0000, TRUE, 'system', NOW(), NOW()),

('fallback_response', 'fallback', NULL,
 '生成兜底响应：\n\n场景：{scenario}\n用户输入：{user_input}\n失败原因：{failure_reason}\n\n兜底策略：\n1. 向用户道歉并说明情况\n2. 提供可能的解决方案\n3. 引导用户重新表达需求\n4. 提供人工客服联系方式（如适用）\n\n保持礼貌和专业性。',
 '{"scenario": "失败场景", "user_input": "用户输入", "failure_reason": "失败原因"}',
 'zh', '1.0', 3, 0, 0.0000, TRUE, 'system', NOW(), NOW()),

('greeting_response', 'response_generation', 3,
 '生成问候响应：\n\n用户输入：{user_input}\n时间：{current_time}\n用户信息：{user_info}\n\n响应要素：\n1. 热情的问候\n2. 自我介绍（智能客服助手）\n3. 说明可提供的服务\n4. 询问如何帮助\n\n生成温暖、专业的问候语。',
 '{"user_input": "用户输入", "current_time": "当前时间", "user_info": "用户信息"}',
 'zh', '1.0', 1, 0, 0.0000, TRUE, 'system', NOW(), NOW()),

('goodbye_response', 'response_generation', 4, 
 '生成告别响应：\n\n用户输入：{user_input}\n服务总结：{service_summary}\n\n响应要素：\n1. 感谢用户的使用\n2. 简要总结提供的服务\n3. 表达继续服务的意愿\n4. 礼貌的告别\n\n生成温馨的告别语。',
 '{"user_input": "用户输入", "service_summary": "服务总结"}',
 'zh', '1.0', 1, 0, 0.0000, TRUE, 'system', NOW(), NOW());

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
-- B2B系统扩展表
-- ================================

-- RAGFLOW集成配置表
CREATE TABLE IF NOT EXISTS ragflow_configs (
    id INT PRIMARY KEY AUTO_INCREMENT,
    config_name VARCHAR(100) NOT NULL COMMENT '配置名称',
    api_endpoint VARCHAR(500) NOT NULL COMMENT 'API端点',
    api_key_encrypted TEXT COMMENT '加密的API密钥',
    api_version VARCHAR(20) DEFAULT 'v1' COMMENT 'API版本',
    timeout_seconds INT DEFAULT 30 COMMENT '超时秒数',
    max_retries INT DEFAULT 3 COMMENT '最大重试次数',
    rate_limit_per_minute INT DEFAULT 60 COMMENT '每分钟限制',
    connection_pool_size INT DEFAULT 10 COMMENT '连接池大小',
    health_check_interval INT DEFAULT 300 COMMENT '健康检查间隔(秒)',
    config_metadata JSON COMMENT '配置元数据',
    is_active BOOLEAN DEFAULT TRUE COMMENT '是否激活',
    created_by VARCHAR(100) COMMENT '创建人',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    UNIQUE KEY uk_ragflow_config_name (config_name),
    INDEX idx_ragflow_active (is_active),
    INDEX idx_ragflow_created_by (created_by)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='RAGFLOW集成配置表';

-- 异步任务管理表
CREATE TABLE IF NOT EXISTS async_tasks (
    id INT AUTO_INCREMENT PRIMARY KEY,
    task_id VARCHAR(100) NOT NULL COMMENT '任务ID',
    task_type ENUM('api_call', 'batch_process', 'data_export', 'ragflow_call') NOT NULL COMMENT '任务类型',
    status ENUM('pending', 'processing', 'completed', 'failed', 'cancelled') DEFAULT 'pending' COMMENT '任务状态',
    conversation_id BIGINT COMMENT '关联对话ID',
    user_id VARCHAR(100) NOT NULL COMMENT '用户ID',
    request_data JSON COMMENT '请求数据',
    result_data JSON COMMENT '结果数据',
    error_message TEXT COMMENT '错误信息',
    progress DECIMAL(5,2) DEFAULT 0.00 COMMENT '进度百分比',
    started_at TIMESTAMP NULL COMMENT '开始时间',
    completed_at TIMESTAMP NULL COMMENT '完成时间',
    retry_count INT DEFAULT 0 COMMENT '重试次数',
    priority INT DEFAULT 1 COMMENT '优先级',
    timeout_seconds INT DEFAULT 300 COMMENT '超时时间',
    metadata JSON COMMENT '任务元数据',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    UNIQUE KEY uk_async_task_id (task_id),
    INDEX idx_async_status_type (status, task_type),
    INDEX idx_async_user_created (user_id, created_at),
    INDEX idx_async_conversation (conversation_id),
    INDEX idx_async_priority (priority),
    FOREIGN KEY (conversation_id) REFERENCES conversations(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='异步任务管理表';

-- API调用日志表
CREATE TABLE IF NOT EXISTS api_call_logs (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    request_id VARCHAR(100) NOT NULL COMMENT '请求ID',
    api_endpoint VARCHAR(500) NOT NULL COMMENT 'API端点',
    http_method VARCHAR(10) NOT NULL COMMENT 'HTTP方法',
    user_id VARCHAR(100) COMMENT '用户ID',
    session_id VARCHAR(100) COMMENT '会话ID',
    request_headers JSON COMMENT '请求头',
    request_body TEXT COMMENT '请求体',
    response_status INT COMMENT '响应状态码',
    response_headers JSON COMMENT '响应头',
    response_body TEXT COMMENT '响应体',
    response_time_ms INT COMMENT '响应时间毫秒',
    error_message TEXT COMMENT '错误信息',
    client_ip VARCHAR(45) COMMENT '客户端IP',
    user_agent TEXT COMMENT '用户代理',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    UNIQUE KEY uk_api_request_id (request_id),
    INDEX idx_api_endpoint (api_endpoint(100)),
    INDEX idx_api_user_id (user_id),
    INDEX idx_api_session_id (session_id),
    INDEX idx_api_status (response_status),
    INDEX idx_api_created_at (created_at),
    INDEX idx_api_response_time (response_time_ms),
    INDEX idx_api_client_ip (client_ip)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='API调用日志表';

-- 安全审计日志表
CREATE TABLE IF NOT EXISTS security_audit_logs (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    event_type VARCHAR(50) NOT NULL COMMENT '事件类型',
    user_id VARCHAR(100) COMMENT '用户ID',
    session_id VARCHAR(100) COMMENT '会话ID',
    ip_address VARCHAR(45) COMMENT 'IP地址',
    user_agent TEXT COMMENT '用户代理',
    event_description TEXT COMMENT '事件描述',
    event_data JSON COMMENT '事件数据',
    risk_level ENUM('low', 'medium', 'high', 'critical') DEFAULT 'low' COMMENT '风险等级',
    status ENUM('pending', 'reviewed', 'resolved', 'ignored') DEFAULT 'pending' COMMENT '处理状态',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    INDEX idx_security_event_type (event_type),
    INDEX idx_security_user_id (user_id),
    INDEX idx_security_session_id (session_id),
    INDEX idx_security_ip (ip_address),
    INDEX idx_security_risk_level (risk_level),
    INDEX idx_security_created_at (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='安全审计日志表';

-- 缓存失效日志表
CREATE TABLE IF NOT EXISTS cache_invalidation_logs (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    cache_key VARCHAR(500) NOT NULL COMMENT '缓存键',
    cache_type VARCHAR(50) NOT NULL COMMENT '缓存类型',
    operation ENUM('invalidate', 'refresh', 'delete') NOT NULL COMMENT '操作类型',
    reason VARCHAR(200) COMMENT '失效原因',
    user_id VARCHAR(100) COMMENT '操作用户',
    affected_count INT DEFAULT 0 COMMENT '影响的记录数',
    execution_time_ms INT COMMENT '执行时间毫秒',
    success BOOLEAN DEFAULT TRUE COMMENT '是否成功',
    error_message TEXT COMMENT '错误信息',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    INDEX idx_cache_key (cache_key(100)),
    INDEX idx_cache_type (cache_type),
    INDEX idx_cache_operation (operation),
    INDEX idx_cache_user_id (user_id),
    INDEX idx_cache_created_at (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='缓存失效日志表';

-- 异步日志队列表
CREATE TABLE IF NOT EXISTS async_log_queue (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    log_type VARCHAR(50) NOT NULL COMMENT '日志类型',
    log_level ENUM('DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL') NOT NULL COMMENT '日志级别',
    log_data JSON NOT NULL COMMENT '日志数据',
    processing_status ENUM('pending', 'processing', 'completed', 'failed') DEFAULT 'pending' COMMENT '处理状态',
    retry_count INT DEFAULT 0 COMMENT '重试次数',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    processed_at TIMESTAMP NULL COMMENT '处理时间',
    INDEX idx_async_log_type (log_type),
    INDEX idx_async_log_level (log_level),
    INDEX idx_async_log_status (processing_status),
    INDEX idx_async_log_created (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='异步日志队列表';

-- 插入RAGFLOW默认配置
INSERT INTO ragflow_configs (config_name, api_endpoint, api_key_encrypted, api_version, timeout_seconds, max_retries, rate_limit_per_minute, connection_pool_size, health_check_interval, config_metadata, is_active, created_by) VALUES
('default_ragflow', 'https://api.ragflow.com/v1/chat', 'encrypted_ragflow_api_key_here', 'v1', 30, 3, 100, 10, 300,
'{"headers": {"Content-Type": "application/json", "Authorization": "Bearer ${API_KEY}"}, "fallback_config": {"enable_fallback": true, "fallback_response": "抱歉，服务暂时不可用，请稍后重试。"}, "health_check_url": "https://api.ragflow.com/health"}',
TRUE, 'system'),

('backup_ragflow', 'https://backup.ragflow.com/v1/chat', 'encrypted_backup_ragflow_key', 'v1', 45, 5, 60, 5, 600,
'{"headers": {"Content-Type": "application/json", "Authorization": "Bearer ${BACKUP_API_KEY}"}, "fallback_config": {"enable_fallback": true, "fallback_response": "备用服务暂时不可用。"}, "health_check_url": "https://backup.ragflow.com/health"}',
FALSE, 'system');

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