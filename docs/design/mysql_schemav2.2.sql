-- 智能意图识别系统数据库表结构 v2.2
-- 支持B2B无状态设计、混合Prompt Template配置、RAGFLOW集成、智能歧义处理等高级功能
-- v2.2 改进说明：
-- 1. 逻辑上移：将审计、缓存失效等业务逻辑从数据库层（触发器、存储过程）转移到应用层，以提升性能、可维护性和可测试性。
-- 2. 规范化关键JSON字段：移除了conversations表中的slots_filled和slots_missing字段，相关信息由slot_values表提供，数据更规范。
-- 3. 统一数据类型：修正了config_audit_logs表中record_id的数据类型，以保证引用一致性。
-- 4. 优化日志策略：在日志相关表注释中，增加了对大规模系统使用专用日志服务的建议。

-- 创建数据库
CREATE DATABASE IF NOT EXISTS intent_db DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE intent_db;

-- 禁用外键检查以便删除表
SET FOREIGN_KEY_CHECKS = 0;

-- 删除所有表（按依赖关系倒序）
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
    prompt_template TEXT COMMENT '提示模板',
    error_message TEXT COMMENT '错误提示',
    extraction_priority INT DEFAULT 1 COMMENT '提取优先级',
    is_active BOOLEAN DEFAULT TRUE COMMENT '是否激活',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    FOREIGN KEY (intent_id) REFERENCES intents(id) ON DELETE CASCADE,
    INDEX idx_slot_type (slot_type),
    INDEX idx_required (is_required),
    INDEX idx_active (is_active),
    UNIQUE KEY uk_intent_slot (intent_id, slot_name)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='槽位配置表';

-- 4. 会话记录表
CREATE TABLE IF NOT EXISTS sessions (
    id INT PRIMARY KEY AUTO_INCREMENT,
    session_id VARCHAR(100) UNIQUE NOT NULL COMMENT '会话ID',
    user_id VARCHAR(100) NOT NULL COMMENT '用户ID',
    current_intent_id INT COMMENT '当前意图ID',
    current_intent_name VARCHAR(100) COMMENT '当前意图名称',
    session_state ENUM('active', 'paused', 'completed', 'expired', 'error') DEFAULT 'active' COMMENT '会话状态',
    context JSON COMMENT '会话上下文',
    metadata JSON COMMENT '元数据',
    channel VARCHAR(50) COMMENT '渠道来源',
    expires_at TIMESTAMP COMMENT '过期时间',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE,
    FOREIGN KEY (current_intent_id) REFERENCES intents(id) ON DELETE SET NULL,
    INDEX idx_session_id (session_id),
    INDEX idx_user_session (user_id, session_state),
    INDEX idx_expires (expires_at),
    INDEX idx_channel (channel),
    INDEX idx_state_time (session_state, updated_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='会话记录表';

-- 5. 对话历史表
CREATE TABLE IF NOT EXISTS conversations (
    id INT PRIMARY KEY AUTO_INCREMENT,
    session_id VARCHAR(100) NOT NULL COMMENT '会话ID',
    user_id VARCHAR(100) NOT NULL COMMENT '用户ID',
    conversation_turn INT NOT NULL COMMENT '对话轮次',
    user_input TEXT NOT NULL COMMENT '用户输入',
    user_input_type ENUM('text', 'voice', 'image', 'file') DEFAULT 'text' COMMENT '输入类型',
    intent_id INT COMMENT '识别的意图ID',
    intent_name VARCHAR(100) COMMENT '识别的意图名称',
    confidence_score DECIMAL(5,4) COMMENT '置信度分数',
    -- v2.2 改进: 移除了slots_filled和slots_missing字段。这些信息应通过查询slot_values表动态获取，以实现数据规范化。
    system_response TEXT COMMENT '系统响应',
    response_type VARCHAR(50) COMMENT '响应类型',
    response_metadata JSON COMMENT '响应元数据',
    status VARCHAR(50) COMMENT '对话状态码, 关联conversation_statuses.status_code',
    processing_time_ms INT COMMENT '处理时间(毫秒)',
    error_message TEXT COMMENT '错误信息',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    FOREIGN KEY (session_id) REFERENCES sessions(session_id) ON DELETE CASCADE,
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE,
    FOREIGN KEY (intent_id) REFERENCES intents(id) ON DELETE SET NULL,
    INDEX idx_session_turn (session_id, conversation_turn),
    INDEX idx_user_time (user_id, created_at),
    INDEX idx_intent_confidence (intent_id, confidence_score),
    INDEX idx_status_time (status, created_at),
    INDEX idx_response_type (response_type),
    UNIQUE KEY uk_session_turn (session_id, conversation_turn)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='对话历史表';

-- 槽位提取规则表
CREATE TABLE IF NOT EXISTS slot_extraction_rules (
    id INT PRIMARY KEY AUTO_INCREMENT,
    slot_id INT NOT NULL COMMENT '槽位ID',
    rule_type ENUM('regex', 'entity', 'keyword', 'ml_model', 'api_call') NOT NULL COMMENT '规则类型',
    rule_pattern TEXT NOT NULL COMMENT '规则模式',
    rule_config JSON COMMENT '规则配置',
    priority INT DEFAULT 1 COMMENT '优先级',
    confidence_boost DECIMAL(5,4) DEFAULT 0.0000 COMMENT '置信度加成',
    is_active BOOLEAN DEFAULT TRUE COMMENT '是否激活',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    FOREIGN KEY (slot_id) REFERENCES slots(id) ON DELETE CASCADE,
    INDEX idx_slot_priority (slot_id, priority),
    INDEX idx_rule_type (rule_type),
    INDEX idx_active (is_active)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='槽位提取规则表';

-- 2.1 槽位值存储表
CREATE TABLE IF NOT EXISTS slot_values (
    id INT PRIMARY KEY AUTO_INCREMENT,
    conversation_id INT NOT NULL COMMENT '对话ID',
    slot_id INT NOT NULL COMMENT '槽位ID',
    slot_name VARCHAR(100) NOT NULL COMMENT '槽位名称',
    original_text TEXT COMMENT '原始文本',
    extracted_value TEXT COMMENT '提取的值',
    normalized_value TEXT COMMENT '标准化后的值',
    confidence DECIMAL(5,4) COMMENT '提取置信度',
    extraction_method VARCHAR(50) COMMENT '提取方法',
    validation_status ENUM('valid', 'invalid', 'pending', 'corrected') DEFAULT 'pending' COMMENT '验证状态',
    validation_error TEXT COMMENT '验证错误信息',
    is_confirmed BOOLEAN DEFAULT FALSE COMMENT '是否已确认',
    source_turn INT COMMENT '来源对话轮次（槽位首次被识别的轮次）',
    last_updated_turn INT COMMENT '最后更新轮次',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    FOREIGN KEY (conversation_id) REFERENCES conversations(id) ON DELETE CASCADE,
    FOREIGN KEY (slot_id) REFERENCES slots(id) ON DELETE CASCADE,
    INDEX idx_conversation_slot (conversation_id, slot_id),
    INDEX idx_slot_value (slot_name, normalized_value(100)),
    INDEX idx_confidence (confidence),
    INDEX idx_validation_status (validation_status),
    INDEX idx_source_turn (source_turn),
    INDEX idx_last_updated_turn (last_updated_turn),
    UNIQUE KEY uk_conversation_slot (conversation_id, slot_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='槽位值存储表';

-- 2.2 槽位依赖关系表
CREATE TABLE IF NOT EXISTS slot_dependencies (
    id INT PRIMARY KEY AUTO_INCREMENT,
    dependent_slot_id INT NOT NULL COMMENT '依赖方槽位ID',
    required_slot_id INT NOT NULL COMMENT '被依赖槽位ID',
    dependency_type ENUM('required', 'conditional', 'exclusive', 'related') DEFAULT 'required' COMMENT '依赖类型',
    dependency_condition JSON COMMENT '依赖条件',
    dependency_level INT DEFAULT 1 COMMENT '依赖层级',
    is_active BOOLEAN DEFAULT TRUE COMMENT '是否激活',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    FOREIGN KEY (dependent_slot_id) REFERENCES slots(id) ON DELETE CASCADE,
    FOREIGN KEY (required_slot_id) REFERENCES slots(id) ON DELETE CASCADE,
    INDEX idx_dependent_slot (dependent_slot_id),
    INDEX idx_required_slot (required_slot_id),
    INDEX idx_dependency_level (dependency_level),
    UNIQUE KEY uk_slot_dependency (dependent_slot_id, required_slot_id),
    CONSTRAINT chk_no_self_dependency CHECK (dependent_slot_id != required_slot_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='槽位依赖关系表';

-- 3. 功能调用配置表
CREATE TABLE IF NOT EXISTS function_calls (
    id INT PRIMARY KEY AUTO_INCREMENT,
    intent_id INT NOT NULL COMMENT '关联意图ID',
    function_name VARCHAR(100) NOT NULL COMMENT '函数名称',
    function_type ENUM('api', 'internal', 'webhook', 'rpc') DEFAULT 'api' COMMENT '函数类型',
    api_endpoint VARCHAR(500) COMMENT 'API端点',
    http_method ENUM('GET', 'POST', 'PUT', 'DELETE', 'PATCH') DEFAULT 'POST' COMMENT 'HTTP方法',
    headers JSON COMMENT '请求头',
    param_mapping JSON COMMENT '参数映射',
    timeout_seconds INT DEFAULT 30 COMMENT '超时秒数',
    retry_count INT DEFAULT 3 COMMENT '重试次数',
    success_template TEXT COMMENT '成功响应模板',
    error_template TEXT COMMENT '错误响应模板',
    is_async BOOLEAN DEFAULT FALSE COMMENT '是否异步执行',
    priority INT DEFAULT 1 COMMENT '执行优先级',
    is_active BOOLEAN DEFAULT TRUE COMMENT '是否激活',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    FOREIGN KEY (intent_id) REFERENCES intents(id) ON DELETE CASCADE,
    INDEX idx_intent_function (intent_id, function_name),
    INDEX idx_function_type (function_type),
    INDEX idx_priority (priority),
    INDEX idx_active (is_active)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='功能调用配置表';

-- 6. 意图歧义处理表
CREATE TABLE IF NOT EXISTS intent_ambiguities (
    id INT PRIMARY KEY AUTO_INCREMENT,
    conversation_id INT NOT NULL COMMENT '对话ID',
    user_input TEXT NOT NULL COMMENT '用户输入',
    candidate_intents JSON NOT NULL COMMENT '候选意图列表',
    disambiguation_question TEXT COMMENT '消歧问题',
    disambiguation_options JSON COMMENT '消歧选项',
    user_choice INT COMMENT '用户选择',
    resolution_method ENUM('user_choice', 'auto_resolve', 'fallback', 'escalate') COMMENT '解决方法',
    resolved_intent_id INT COMMENT '最终确定的意图ID',
    resolved_at TIMESTAMP NULL COMMENT '解决时间',
    is_resolved BOOLEAN DEFAULT FALSE COMMENT '是否已解决',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    FOREIGN KEY (conversation_id) REFERENCES conversations(id) ON DELETE CASCADE,
    FOREIGN KEY (resolved_intent_id) REFERENCES intents(id) ON DELETE SET NULL,
    INDEX idx_conversation_ambiguity (conversation_id),
    INDEX idx_resolved_status (is_resolved, created_at),
    INDEX idx_resolution_method (resolution_method)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='意图歧义处理表';

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
) COMMENT='配置审计日志表 (v2.2注: 触发器已移除, 日志由应用层写入)';

-- 8. Prompt模板配置表
CREATE TABLE IF NOT EXISTS prompt_templates (
    id INT PRIMARY KEY AUTO_INCREMENT,
    template_name VARCHAR(100) UNIQUE NOT NULL COMMENT '模板名称',
    template_type ENUM('intent_recognition', 'slot_filling', 'response_generation', 'disambiguation', 'fallback') NOT NULL COMMENT '模板类型',
    intent_id INT COMMENT '关联意图ID(可选)',
    template_content TEXT NOT NULL COMMENT '模板内容',
    variables JSON COMMENT '模板变量',
    language VARCHAR(10) DEFAULT 'zh-CN' COMMENT '语言',
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
    INDEX idx_intent_template (intent_id, template_type),
    INDEX idx_priority (priority),
    INDEX idx_active (is_active),
    INDEX idx_language (language)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='Prompt模板配置表';

-- 9. 用户上下文表
CREATE TABLE IF NOT EXISTS user_contexts (
    id INT PRIMARY KEY AUTO_INCREMENT,
    user_id VARCHAR(100) NOT NULL COMMENT '用户ID',
    context_type ENUM('preference', 'history', 'profile', 'session', 'temporary') NOT NULL COMMENT '上下文类型',
    context_key VARCHAR(100) NOT NULL COMMENT '上下文键',
    context_value JSON COMMENT '上下文值',
    scope ENUM('global', 'session', 'conversation') DEFAULT 'global' COMMENT '作用范围',
    priority INT DEFAULT 1 COMMENT '优先级',
    expires_at TIMESTAMP NULL COMMENT '过期时间',
    is_active BOOLEAN DEFAULT TRUE COMMENT '是否有效',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE,
    INDEX idx_user_context (user_id, context_type),
    INDEX idx_context_key (context_key),
    INDEX idx_expires (expires_at),
    INDEX idx_scope_priority (scope, priority),
    UNIQUE KEY uk_user_context_key (user_id, context_type, context_key)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='用户上下文表';

-- 10. 意图转移记录表
CREATE TABLE IF NOT EXISTS intent_transfers (
    id INT PRIMARY KEY AUTO_INCREMENT,
    session_id VARCHAR(100) NOT NULL COMMENT '会话ID',
    conversation_id INT COMMENT '对话ID',
    user_id VARCHAR(100) NOT NULL COMMENT '用户ID',
    from_intent_id INT COMMENT '源意图ID',
    from_intent_name VARCHAR(100) COMMENT '源意图名称',
    to_intent_id INT COMMENT '目标意图ID',
    to_intent_name VARCHAR(100) COMMENT '目标意图名称',
    transfer_type ENUM('user_request', 'system_redirect', 'fallback', 'escalation', 'completion') NOT NULL COMMENT '转移类型',
    transfer_reason TEXT COMMENT '转移原因',
    saved_context JSON COMMENT '保存的上下文',
    transfer_confidence DECIMAL(5,4) COMMENT '转移置信度',
    is_successful BOOLEAN DEFAULT TRUE COMMENT '是否成功',
    resumed_at TIMESTAMP NULL COMMENT '恢复时间',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    FOREIGN KEY (session_id) REFERENCES sessions(session_id) ON DELETE CASCADE,
    FOREIGN KEY (conversation_id) REFERENCES conversations(id) ON DELETE SET NULL,
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE,
    FOREIGN KEY (from_intent_id) REFERENCES intents(id) ON DELETE SET NULL,
    FOREIGN KEY (to_intent_id) REFERENCES intents(id) ON DELETE SET NULL,
    INDEX idx_session_transfer (session_id, created_at),
    INDEX idx_user_transfer (user_id, transfer_type),
    INDEX idx_intent_from_to (from_intent_id, to_intent_id),
    INDEX idx_transfer_type (transfer_type)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='意图转移记录表';

-- 11. 系统配置表
CREATE TABLE IF NOT EXISTS system_configs (
    id INT PRIMARY KEY AUTO_INCREMENT,
    config_category VARCHAR(50) NOT NULL COMMENT '配置分类',
    config_key VARCHAR(100) NOT NULL COMMENT '配置键',
    config_value TEXT COMMENT '配置值',
    value_type ENUM('string', 'number', 'boolean', 'json', 'array') DEFAULT 'string' COMMENT '值类型',
    description TEXT COMMENT '配置描述',
    is_encrypted BOOLEAN DEFAULT FALSE COMMENT '是否加密',
    is_public BOOLEAN DEFAULT FALSE COMMENT '是否公开',
    validation_rule VARCHAR(500) COMMENT '验证规则',
    default_value TEXT COMMENT '默认值',
    is_active BOOLEAN DEFAULT TRUE COMMENT '是否有效',
    created_by VARCHAR(100) COMMENT '创建人',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    INDEX idx_category_key (config_category, config_key),
    INDEX idx_active (is_active),
    INDEX idx_public (is_public),
    UNIQUE KEY uk_category_key (config_category, config_key)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='系统配置表';


-- 12. API调用日志表
-- v2.2 注: 对于大规模系统，强烈建议将API调用日志、安全审计日志等高频写入数据存储在专用的日志系统（如ELK Stack, Loki）中，
-- 而非主业务数据库，以避免性能瓶颈。以下表结构可用于中小型系统或作为到专用系统的缓冲。
CREATE TABLE IF NOT EXISTS api_call_logs (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    request_id VARCHAR(100) UNIQUE NOT NULL COMMENT '请求ID',
    api_endpoint VARCHAR(500) NOT NULL COMMENT 'API端点',
    http_method VARCHAR(10) NOT NULL COMMENT 'HTTP方法',
    user_id VARCHAR(100) COMMENT '用户ID',
    api_key_hash VARCHAR(255) COMMENT 'API密钥哈希',
    request_headers JSON COMMENT '请求头',
    request_body LONGTEXT COMMENT '请求体',
    response_status INT COMMENT '响应状态码',
    response_headers JSON COMMENT '响应头',
    response_body LONGTEXT COMMENT '响应体',
    response_time_ms INT COMMENT '响应时间(毫秒)',
    request_size_bytes INT COMMENT '请求大小(字节)',
    response_size_bytes INT COMMENT '响应大小(字节)',
    client_ip VARCHAR(45) COMMENT '客户端IP',
    user_agent TEXT COMMENT '用户代理',
    referer VARCHAR(500) COMMENT '引用页',
    rate_limit_remaining INT COMMENT '剩余请求次数',
    error_message TEXT COMMENT '错误信息',
    processing_components JSON COMMENT '处理组件',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE SET NULL,
    INDEX idx_request_id (request_id),
    INDEX idx_api_endpoint (api_endpoint(100)),
    INDEX idx_user_time (user_id, created_at),
    INDEX idx_status_time (response_status, created_at),
    INDEX idx_response_time (response_time_ms),
    INDEX idx_client_ip (client_ip)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='API调用日志表';

-- 13. RAGFLOW集成配置表
CREATE TABLE IF NOT EXISTS ragflow_configs (
    id INT PRIMARY KEY AUTO_INCREMENT,
    config_name VARCHAR(100) UNIQUE NOT NULL COMMENT '配置名称',
    api_endpoint VARCHAR(500) NOT NULL COMMENT 'API端点',
    api_key_encrypted TEXT COMMENT '加密的API密钥',
    api_version VARCHAR(20) DEFAULT 'v1' COMMENT 'API版本',
    timeout_seconds INT DEFAULT 30 COMMENT '超时秒数',
    max_retries INT DEFAULT 3 COMMENT '最大重试次数',
    rate_limit_per_minute INT DEFAULT 60 COMMENT '每分钟限制',
    connection_pool_size INT DEFAULT 10 COMMENT '连接池大小',
    health_check_interval INT DEFAULT 300 COMMENT '健康检查间隔(秒)',
    last_health_check TIMESTAMP NULL COMMENT '最后健康检查时间',
    health_status ENUM('healthy', 'unhealthy', 'unknown') DEFAULT 'unknown' COMMENT '健康状态',
    config_metadata JSON COMMENT '配置元数据',
    is_active BOOLEAN DEFAULT TRUE COMMENT '是否激活',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    INDEX idx_config_name (config_name),
    INDEX idx_active (is_active),
    INDEX idx_health_status (health_status),
    INDEX idx_health_check (last_health_check)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='RAGFLOW集成配置表';

-- 14. 安全审计日志表
CREATE TABLE IF NOT EXISTS security_audit_logs (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    user_id VARCHAR(100) COMMENT '用户ID',
    ip_address VARCHAR(45) COMMENT 'IP地址',
    user_agent TEXT COMMENT '用户代理',
    action_type ENUM('login', 'logout', 'api_call', 'config_change', 'security_violation') COMMENT '操作类型',
    resource_type VARCHAR(50) COMMENT '资源类型',
    resource_id VARCHAR(100) COMMENT '资源ID',
    action_details JSON COMMENT '操作详情',
    risk_level ENUM('low', 'medium', 'high', 'critical') DEFAULT 'low' COMMENT '风险等级',
    status ENUM('success', 'failure', 'blocked') COMMENT '操作状态',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_user_id (user_id),
    INDEX idx_ip_address (ip_address),
    INDEX idx_action_type (action_type),
    INDEX idx_risk_level (risk_level),
    INDEX idx_created_at (created_at)
) COMMENT '安全审计日志表';

-- 15. 异步任务管理表
CREATE TABLE IF NOT EXISTS async_tasks (
    id INT AUTO_INCREMENT PRIMARY KEY,
    task_id VARCHAR(100) NOT NULL UNIQUE COMMENT '任务ID',
    task_type ENUM('api_call', 'batch_process', 'data_export', 'ragflow_call') NOT NULL COMMENT '任务类型',
    status ENUM('pending', 'processing', 'completed', 'failed', 'cancelled') DEFAULT 'pending' COMMENT '任务状态',
    conversation_id INT COMMENT '关联对话ID',
    user_id VARCHAR(100) NOT NULL COMMENT '用户ID',
    request_data JSON COMMENT '请求数据',
    result_data JSON COMMENT '结果数据',
    error_message TEXT COMMENT '错误信息',
    progress DECIMAL(5,2) DEFAULT 0.00 COMMENT '进度百分比',
    estimated_completion TIMESTAMP NULL COMMENT '预计完成时间',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    completed_at TIMESTAMP NULL COMMENT '实际完成时间',
    FOREIGN KEY (conversation_id) REFERENCES conversations(id) ON DELETE SET NULL,
    INDEX idx_task_id (task_id),
    INDEX idx_status (status),
    INDEX idx_user_id (user_id),
    INDEX idx_conversation_id (conversation_id),
    INDEX idx_created_at (created_at)
) ENGINE=InnoDB COMMENT '异步任务管理表';

-- 16. 缓存一致性管理表
CREATE TABLE IF NOT EXISTS cache_invalidation_logs (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    table_name VARCHAR(50) NOT NULL COMMENT '变更的表名',
    record_id VARCHAR(100) NOT NULL COMMENT '记录ID',
    operation_type ENUM('INSERT', 'UPDATE', 'DELETE') NOT NULL COMMENT '操作类型',
    cache_keys JSON NOT NULL COMMENT '需要失效的缓存键列表',
    invalidation_status ENUM('pending', 'processing', 'completed', 'failed') DEFAULT 'pending' COMMENT '失效状态',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    processed_at TIMESTAMP NULL COMMENT '处理时间',
    error_message TEXT COMMENT '错误信息',
    INDEX idx_table_record (table_name, record_id),
    INDEX idx_status (invalidation_status),
    INDEX idx_created_at (created_at)
) COMMENT '缓存失效日志表 (v2.2注: 由应用层写入, 供后台服务消费)';

-- 17. 异步日志队列表
CREATE TABLE IF NOT EXISTS async_log_queue (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    log_type ENUM('api_call', 'security_audit', 'performance', 'error') NOT NULL COMMENT '日志类型',
    log_data JSON NOT NULL COMMENT '日志数据',
    priority INT DEFAULT 1 COMMENT '优先级，数字越大优先级越高',
    status ENUM('pending', 'processing', 'completed', 'failed') DEFAULT 'pending' COMMENT '处理状态',
    retry_count INT DEFAULT 0 COMMENT '重试次数',
    max_retries INT DEFAULT 3 COMMENT '最大重试次数',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    processed_at TIMESTAMP NULL COMMENT '处理时间',
    error_message TEXT COMMENT '错误信息',
    INDEX idx_type_status (log_type, status),
    INDEX idx_priority (priority DESC),
    INDEX idx_created_at (created_at)
) COMMENT '异步日志队列表';

-- 18. 响应类型定义表
CREATE TABLE IF NOT EXISTS response_types (
    id INT PRIMARY KEY AUTO_INCREMENT,
    type_code VARCHAR(50) UNIQUE NOT NULL COMMENT '类型代码',
    type_name VARCHAR(100) NOT NULL COMMENT '类型名称',
    description TEXT COMMENT '类型描述',
    category VARCHAR(50) COMMENT '类型分类',
    template_format VARCHAR(100) COMMENT '模板格式',
    default_template TEXT COMMENT '默认模板',
    metadata JSON COMMENT '元数据',
    sort_order INT DEFAULT 1 COMMENT '排序',
    is_active BOOLEAN DEFAULT TRUE COMMENT '是否激活',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_type_code (type_code),
    INDEX idx_category (category),
    INDEX idx_active_sort (is_active, sort_order)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='响应类型定义表';

-- 19. 对话状态定义表
CREATE TABLE IF NOT EXISTS conversation_statuses (
    id INT PRIMARY KEY AUTO_INCREMENT,
    status_code VARCHAR(50) UNIQUE NOT NULL COMMENT '状态代码',
    status_name VARCHAR(100) NOT NULL COMMENT '状态名称',
    description TEXT COMMENT '状态描述',
    category VARCHAR(50) COMMENT '状态分类',
    is_final BOOLEAN DEFAULT FALSE COMMENT '是否为终态',
    next_allowed_statuses JSON COMMENT '允许的下一状态',
    auto_transition_rules JSON COMMENT '自动转换规则',
    notification_required BOOLEAN DEFAULT FALSE COMMENT '是否需要通知',
    sort_order INT DEFAULT 1 COMMENT '排序',
    is_active BOOLEAN DEFAULT TRUE COMMENT '是否激活',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_status_code (status_code),
    INDEX idx_category (category),
    INDEX idx_final_status (is_final),
    INDEX idx_active_sort (is_active, sort_order)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='对话状态定义表';

-- 20. 实体类型定义表
CREATE TABLE entity_types (
    id INT PRIMARY KEY AUTO_INCREMENT,
    entity_type_code VARCHAR(50) UNIQUE NOT NULL COMMENT '实体类型代码',
    entity_type_name VARCHAR(100) NOT NULL COMMENT '实体类型名称',
    description TEXT COMMENT '类型描述',
    category VARCHAR(50) COMMENT '实体分类',
    extraction_patterns JSON COMMENT '提取模式',
    validation_rules JSON COMMENT '验证规则',
    normalization_rules JSON COMMENT '标准化规则',
    synonyms JSON COMMENT '同义词',
    parent_type_id INT COMMENT '父类型ID',
    is_system_type BOOLEAN DEFAULT FALSE COMMENT '是否为系统类型',
    is_active BOOLEAN DEFAULT TRUE COMMENT '是否激活',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (parent_type_id) REFERENCES entity_types(id) ON DELETE SET NULL,
    INDEX idx_entity_type_code (entity_type_code),
    INDEX idx_category (category),
    INDEX idx_parent_type (parent_type_id),
    INDEX idx_system_type (is_system_type),
    INDEX idx_active (is_active)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='实体类型定义表';

-- 21. 实体词典表
CREATE TABLE entity_dictionary (
    id INT PRIMARY KEY AUTO_INCREMENT,
    entity_type_id INT NOT NULL COMMENT '实体类型ID',
    entity_value VARCHAR(200) NOT NULL COMMENT '实体值',
    canonical_form VARCHAR(200) COMMENT '标准形式',
    aliases JSON COMMENT '别名列表',
    confidence_weight DECIMAL(5,4) DEFAULT 1.0000 COMMENT '置信度权重',
    context_hints JSON COMMENT '上下文提示',
    metadata JSON COMMENT '元数据',
    frequency_count INT DEFAULT 0 COMMENT '使用频次',
    last_used_at TIMESTAMP NULL COMMENT '最后使用时间',
    is_active BOOLEAN DEFAULT TRUE COMMENT '是否激活',
    created_by VARCHAR(100) COMMENT '创建人',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (entity_type_id) REFERENCES entity_types(id) ON DELETE CASCADE,
    INDEX idx_entity_type_value (entity_type_id, entity_value),
    INDEX idx_canonical_form (canonical_form),
    INDEX idx_frequency (frequency_count DESC),
    INDEX idx_last_used (last_used_at),
    INDEX idx_active (is_active),
    FULLTEXT idx_entity_search (entity_value, canonical_form)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='实体词典表';

-- 初始化响应类型数据
INSERT INTO response_types (type_code, type_name, description, category) VALUES
('api_result', 'API调用结果', 'API调用成功返回的结果', 'success'),
('task_completion', '任务完成', '意图处理完成', 'success'),
('slot_prompt', '槽位询问', '需要用户提供更多槽位信息', 'interaction'),
('disambiguation', '歧义澄清', '需要用户澄清意图', 'interaction'),
('qa_response', '问答回复', '直接问答用户问题', 'information'),
('small_talk_with_context_return', '闲聊带上下文返回', '闲聊并引导回到主要任务', 'fallback'),
('intent_transfer_with_completion', '意图转移带完成', '意图转移并完成新意图', 'transfer'),
('cancellation_confirmation', '取消确认', '确认用户取消操作', 'control'),
('postponement_with_save', '延迟并保存', '保存当前进度并延迟决定', 'control'),
('rejection_acknowledgment', '拒绝确认', '确认用户拒绝建议', 'control'),
('validation_error_prompt', '验证错误提示', '槽位验证失败提示', 'error'),
('error_with_alternatives', '错误带替代方案', '出错时提供替代方案', 'error'),
('multi_intent_with_continuation', '多意图带继续', '多个意图并行处理', 'complex'),
('security_error', '安全错误', '安全验证失败', 'security');

-- 初始化对话状态数据
INSERT INTO conversation_statuses (status_code, status_name, description, category, is_final) VALUES
('completed', '已完成', '对话成功完成', 'success', TRUE),
('incomplete', '不完整', '槽位信息不完整', 'processing', FALSE),
('ambiguous', '歧义状态', '意图识别存在歧义', 'processing', FALSE),
('api_error', 'API错误', '外部API调用失败', 'error', TRUE),
('validation_error', '验证错误', '槽位验证失败', 'error', FALSE),
('ragflow_handled', 'RAGFLOW处理', '由RAGFLOW处理的非意图输入', 'fallback', TRUE),
('interruption_handled', '中断处理', '意图中断已处理', 'transfer', TRUE),
('multi_intent_processing', '多意图处理', '正在处理多个意图', 'complex', FALSE),
('intent_cancelled', '意图已取消', '用户取消意图', 'control', TRUE),
('intent_postponed', '意图已延迟', '用户延迟决定', 'control', FALSE),
('suggestion_rejected', '建议已拒绝', '用户拒绝系统建议', 'control', TRUE),
('intent_transfer', '意图转移', '意图已转移', 'transfer', TRUE),
('slot_filling', '槽位填充中', '正在进行槽位填充', 'processing', FALSE),
('context_maintained', '上下文维持', '保持对话上下文', 'processing', FALSE);

-- 插入示例用户数据
INSERT INTO users (user_id, user_type, username, email, display_name, status) VALUES
('system', 'system', 'system', 'system@intent.com', '系统用户', 'active'),
('admin', 'admin', 'admin', 'admin@intent.com', '管理员', 'active'),
('test_user_001', 'individual', 'testuser1', 'test1@example.com', '测试用户1', 'active'),
('test_user_002', 'individual', 'testuser2', 'test2@example.com', '测试用户2', 'active'),
('enterprise_001', 'enterprise', 'company1', 'contact@company1.com', '企业用户1', 'active');

-- 插入基础实体类型
INSERT INTO entity_types (entity_type_code, entity_type_name, description, category, is_system_type) VALUES
('person', '人名', '人员姓名实体', 'person', TRUE),
('organization', '机构名', '组织机构名称', 'organization', TRUE),
('location', '地点', '地理位置信息', 'location', TRUE),
('datetime', '日期时间', '时间相关实体', 'temporal', TRUE),
('number', '数字', '数值实体', 'numeric', TRUE),
('phone', '电话号码', '电话号码格式', 'contact', TRUE),
('email', '邮箱地址', '电子邮件地址', 'contact', TRUE),
('url', '网址', 'URL链接', 'web', TRUE),
('city', '城市', '城市名称', 'location', TRUE),
('airline', '航空公司', '航空公司名称', 'organization', TRUE),
('bank', '银行', '银行名称', 'organization', TRUE),
('card_type', '卡类型', '银行卡类型', 'financial', TRUE);

-- 插入实体词典数据
INSERT INTO entity_dictionary (entity_type_id, entity_value, canonical_form, aliases, confidence_weight, metadata, is_active, created_by) VALUES
-- 城市实体
((SELECT id FROM entity_types WHERE entity_type_code = 'city'), '北京', '北京市', '["北京", "京城", "首都", "BJ", "Beijing"]', 1.0, '{"province": "北京市", "code": "BJ"}', TRUE, 'system'),
((SELECT id FROM entity_types WHERE entity_type_code = 'city'), '上海', '上海市', '["上海", "魔都", "SH", "Shanghai"]', 1.0, '{"province": "上海市", "code": "SH"}', TRUE, 'system'),
((SELECT id FROM entity_types WHERE entity_type_code = 'city'), '广州', '广州市', '["广州", "花城", "GZ", "Guangzhou"]', 1.0, '{"province": "广东省", "code": "GZ"}', TRUE, 'system'),
((SELECT id FROM entity_types WHERE entity_type_code = 'city'), '深圳', '深圳市', '["深圳", "鹏城", "SZ", "Shenzhen"]', 1.0, '{"province": "广东省", "code": "SZ"}', TRUE, 'system'),
((SELECT id FROM entity_types WHERE entity_type_code = 'city'), '杭州', '杭州市', '["杭州", "HZ", "Hangzhou"]', 1.0, '{"province": "浙江省", "code": "HZ"}', TRUE, 'system'),
((SELECT id FROM entity_types WHERE entity_type_code = 'city'), '成都', '成都市', '["成都", "CD", "Chengdu"]', 1.0, '{"province": "四川省", "code": "CD"}', TRUE, 'system'),

-- 航空公司实体
((SELECT id FROM entity_types WHERE entity_type_code = 'airline'), '中国国际航空', '中国国际航空股份有限公司', '["国航", "Air China", "CA", "中国国航"]', 1.0, '{"code": "CA", "type": "国有"}', TRUE, 'system'),
((SELECT id FROM entity_types WHERE entity_type_code = 'airline'), '中国南方航空', '中国南方航空股份有限公司', '["南航", "China Southern", "CZ", "南方航空"]', 1.0, '{"code": "CZ", "type": "国有"}', TRUE, 'system'),
((SELECT id FROM entity_types WHERE entity_type_code = 'airline'), '中国东方航空', '中国东方航空股份有限公司', '["东航", "China Eastern", "MU", "东方航空"]', 1.0, '{"code": "MU", "type": "国有"}', TRUE, 'system'),
((SELECT id FROM entity_types WHERE entity_type_code = 'airline'), '海南航空', '海南航空股份有限公司', '["海航", "Hainan Airlines", "HU"]', 1.0, '{"code": "HU", "type": "民营"}', TRUE, 'system'),

-- 银行实体
((SELECT id FROM entity_types WHERE entity_type_code = 'bank'), '中国工商银行', '中国工商银行股份有限公司', '["工商银行", "工行", "ICBC"]', 1.0, '{"code": "ICBC", "type": "国有"}', TRUE, 'system'),
((SELECT id FROM entity_types WHERE entity_type_code = 'bank'), '中国建设银行', '中国建设银行股份有限公司', '["建设银行", "建行", "CCB"]', 1.0, '{"code": "CCB", "type": "国有"}', TRUE, 'system'),
((SELECT id FROM entity_types WHERE entity_type_code = 'bank'), '中国农业银行', '中国农业银行股份有限公司', '["农业银行", "农行", "ABC"]', 1.0, '{"code": "ABC", "type": "国有"}', TRUE, 'system'),
((SELECT id FROM entity_types WHERE entity_type_code = 'bank'), '中国银行', '中国银行股份有限公司', '["中行", "BOC"]', 1.0, '{"code": "BOC", "type": "国有"}', TRUE, 'system'),
((SELECT id FROM entity_types WHERE entity_type_code = 'bank'), '招商银行', '招商银行股份有限公司', '["招行", "CMB"]', 1.0, '{"code": "CMB", "type": "股份制"}', TRUE, 'system'),

-- 卡类型实体
((SELECT id FROM entity_types WHERE entity_type_code = 'card_type'), '储蓄卡', '储蓄卡', '["储蓄卡", "借记卡", "存款卡"]', 1.0, '{"type": "debit"}', TRUE, 'system'),
((SELECT id FROM entity_types WHERE entity_type_code = 'card_type'), '信用卡', '信用卡', '["信用卡", "贷记卡", "透支卡"]', 1.0, '{"type": "credit"}', TRUE, 'system');

-- 插入订机票意图
INSERT INTO intents (intent_name, display_name, description, confidence_threshold, priority, examples) VALUES
('book_flight', '订机票', '用户想要预订机票的意图', 0.8, 10,
'["我想订机票", "帮我订张机票", "我要买机票", "预订航班", "订从北京到上海的机票", "我想预订明天的航班", "帮我买张机票", "我想飞到上海"]');

-- 插入查银行卡余额意图
INSERT INTO intents (intent_name, display_name, description, confidence_threshold, priority, examples) VALUES
('check_balance', '查银行卡余额', '用户想要查询银行卡余额的意图', 0.75, 8,
'["查余额", "我的银行卡余额", "账户余额多少", "查询余额", "余额查询", "我的卡里还有多少钱", "查一下账户余额"]');

-- 插入新的意图类型
INSERT INTO intents (intent_name, display_name, description, confidence_threshold, priority, examples) VALUES
('cancel_intent', '取消意图', '用户取消当前意图的操作', 0.85, 15,
'["我不订了", "取消", "算了不要了", "不需要了", "取消操作"]'),
('postpone_intent', '延迟意图', '用户延迟决定的意图', 0.80, 12,
'["算了，我再想想", "稍后再说", "让我考虑一下", "等一下再决定"]'),
('reject_suggestion', '拒绝建议', '用户拒绝系统建议的意图', 0.82, 11,
'["不用了，我不需要这个服务", "不感兴趣", "不需要推荐", "没兴趣"]'),
('small_talk', '闲聊', '用户闲聊打岔的意图', 0.70, 5,
'["今天天气真好啊", "你好吗", "哈哈", "好的好的", "谢谢"]'),
('information_query', '信息查询', '用户查询相关信息的意图', 0.75, 7,
'["什么是经济舱", "机票价格怎么算", "怎么退票", "有什么优惠"]');

-- 插入订机票相关槽位
INSERT INTO slots (intent_id, slot_name, display_name, slot_type, is_required, validation_rules, prompt_template, error_message) VALUES
((SELECT id FROM intents WHERE intent_name = 'book_flight'), 'departure_city', '出发城市', 'text', TRUE,
'{"min_length": 2, "max_length": 20, "examples": ["北京", "上海", "广州", "深圳"]}', '请告诉我出发城市是哪里？', '请输入有效的城市名称'),

((SELECT id FROM intents WHERE intent_name = 'book_flight'), 'arrival_city', '到达城市', 'text', TRUE,
'{"min_length": 2, "max_length": 20, "examples": ["北京", "上海", "广州", "深圳"]}', '请告诉我到达城市是哪里？', '请输入有效的城市名称'),

((SELECT id FROM intents WHERE intent_name = 'book_flight'), 'departure_date', '出发日期', 'date', TRUE,
'{"format": "YYYY-MM-DD", "min_date": "today", "examples": ["2024-12-01", "明天", "下周一"]}', '请告诉我出发日期是哪天？', '请输入有效的日期格式'),

((SELECT id FROM intents WHERE intent_name = 'book_flight'), 'return_date', '返程日期', 'date', FALSE,
'{"format": "YYYY-MM-DD", "min_date": "departure_date", "examples": ["2024-12-05", "下周五", "不需要"]}', '请问是否需要返程票？如果需要，请告诉我返程日期。', '请输入有效的返程日期'),

((SELECT id FROM intents WHERE intent_name = 'book_flight'), 'passenger_count', '乘客人数', 'number', FALSE,
'{"min": 1, "max": 9, "default": 1, "examples": ["1", "2", "3人"]}', '请告诉我乘客人数，默认为1人。', '乘客人数必须在1-9之间'),

((SELECT id FROM intents WHERE intent_name = 'book_flight'), 'seat_class', '座位等级', 'text', FALSE,
'{"options": ["经济舱", "商务舱", "头等舱"], "default": "经济舱", "examples": ["经济舱", "商务舱", "头等舱"]}', '请选择座位等级：经济舱、商务舱或头等舱？', '请选择有效的座位等级');

-- 插入查银行卡余额相关槽位
INSERT INTO slots (intent_id, slot_name, display_name, slot_type, is_required, validation_rules, prompt_template, error_message) VALUES
((SELECT id FROM intents WHERE intent_name = 'check_balance'), 'card_number', '银行卡号', 'text', TRUE,
'{"pattern": "^\\\\d{16}$|^\\\\d{4}\\\\s\\\\d{4}\\\\s\\\\d{4}\\\\s\\\\d{4}$", "mask": true, "examples": ["6222080012345678", "6222 0800 1234 5678"]}', '请提供您的银行卡号（16位数字）', '请输入正确的16位银行卡号'),

((SELECT id FROM intents WHERE intent_name = 'check_balance'), 'verification_code', '验证码', 'text', FALSE,
'{"pattern": "^\\\\d{6}$", "expires": 300, "examples": ["123456", "验证码"]}', '请输入手机验证码（6位数字）', '请输入6位数字验证码');

-- 插入槽位依赖关系
INSERT INTO slot_dependencies (dependent_slot_id, required_slot_id, dependency_type, dependency_condition, dependency_level) VALUES
-- 返程日期依赖出发日期（条件依赖：只有在选择往返票时才需要）
((SELECT id FROM slots WHERE slot_name = 'return_date' AND intent_id = (SELECT id FROM intents WHERE intent_name = 'book_flight')),
 (SELECT id FROM slots WHERE slot_name = 'departure_date' AND intent_id = (SELECT id FROM intents WHERE intent_name = 'book_flight')),
 'conditional',
 '{"type": "has_value", "description": "需要返程票时", "slot": "departure_date"}', 1),

-- 座位等级依赖乘客人数（可选：人数确定后再选座位等级）
((SELECT id FROM slots WHERE slot_name = 'seat_class' AND intent_id = (SELECT id FROM intents WHERE intent_name = 'book_flight')),
 (SELECT id FROM slots WHERE slot_name = 'passenger_count' AND intent_id = (SELECT id FROM intents WHERE intent_name = 'book_flight')),
 'required',
 '{"type": "has_value", "description": "确定乘客人数后选择座位等级"}', 2),

-- 验证码依赖银行卡号（必需依赖：需要先输入卡号才能获取验证码）
((SELECT id FROM slots WHERE slot_name = 'verification_code' AND intent_id = (SELECT id FROM intents WHERE intent_name = 'check_balance')),
 (SELECT id FROM slots WHERE slot_name = 'card_number' AND intent_id = (SELECT id FROM intents WHERE intent_name = 'check_balance')),
 'required',
 '{"type": "has_value", "description": "输入银行卡号后获取验证码"}', 1);

-- 插入槽位提取规则
INSERT INTO slot_extraction_rules (slot_id, rule_type, rule_pattern, rule_config, priority, confidence_boost, is_active) VALUES
-- 城市提取规则
((SELECT id FROM slots WHERE slot_name = 'departure_city' AND intent_id = (SELECT id FROM intents WHERE intent_name = 'book_flight')),
'entity', '城市实体识别', '{"entity_type": "city", "min_confidence": 0.8}', 1, 0.2, TRUE),

((SELECT id FROM slots WHERE slot_name = 'arrival_city' AND intent_id = (SELECT id FROM intents WHERE intent_name = 'book_flight')),
'entity', '城市实体识别', '{"entity_type": "city", "min_confidence": 0.8}', 1, 0.2, TRUE),

-- 日期提取规则
((SELECT id FROM slots WHERE slot_name = 'departure_date' AND intent_id = (SELECT id FROM intents WHERE intent_name = 'book_flight')),
'regex', '\\d{4}-\\d{2}-\\d{2}|今天|明天|后天|下周[一二三四五六日]', '{"format": "YYYY-MM-DD"}', 1, 0.3, TRUE),

((SELECT id FROM slots WHERE slot_name = 'return_date' AND intent_id = (SELECT id FROM intents WHERE intent_name = 'book_flight')),
'regex', '\\d{4}-\\d{2}-\\d{2}|今天|明天|后天|下周[一二三四五六日]', '{"format": "YYYY-MM-DD"}', 1, 0.3, TRUE),

-- 人数提取规则
((SELECT id FROM slots WHERE slot_name = 'passenger_count' AND intent_id = (SELECT id FROM intents WHERE intent_name = 'book_flight')),
'regex', '[1-9]人?|[一二三四五六七八九]人?', '{"min": 1, "max": 9}', 1, 0.4, TRUE),

-- 座位等级提取规则
((SELECT id FROM slots WHERE slot_name = 'seat_class' AND intent_id = (SELECT id FROM intents WHERE intent_name = 'book_flight')),
'keyword', '经济舱|商务舱|头等舱', '{"exact_match": true}', 1, 0.5, TRUE),

-- 银行卡号提取规则
((SELECT id FROM slots WHERE slot_name = 'card_number' AND intent_id = (SELECT id FROM intents WHERE intent_name = 'check_balance')),
'regex', '\\d{16}|\\d{4}\\s\\d{4}\\s\\d{4}\\s\\d{4}', '{"mask_display": true, "validation": "luhn"}', 1, 0.6, TRUE),

-- 验证码提取规则
((SELECT id FROM slots WHERE slot_name = 'verification_code' AND intent_id = (SELECT id FROM intents WHERE intent_name = 'check_balance')),
'regex', '\\d{6}', '{"expires_in": 300}', 1, 0.7, TRUE);

-- 插入功能调用配置
INSERT INTO function_calls (intent_id, function_name, api_endpoint, http_method, headers, param_mapping, success_template, error_template) VALUES
((SELECT id FROM intents WHERE intent_name = 'book_flight'), 'book_flight_api', 'https://api.flight.com/v1/booking', 'POST',
'{"Content-Type": "application/json", "Authorization": "Bearer ${API_TOKEN}"}',
'{"departure_city": "departure_city", "arrival_city": "arrival_city", "departure_date": "departure_date", "return_date": "return_date", "passenger_count": "passenger_count", "seat_class": "seat_class"}',
'机票预订成功！订单号：${order_id}，出发时间：${departure_time}，请及时支付。',
'很抱歉，机票预订失败：${error_message}，请稍后重试或联系客服。');

INSERT INTO function_calls (intent_id, function_name, api_endpoint, http_method, headers, param_mapping, success_template, error_template) VALUES
((SELECT id FROM intents WHERE intent_name = 'check_balance'), 'check_balance_api', 'https://api.bank.com/v1/balance', 'POST',
'{"Content-Type": "application/json", "Authorization": "Bearer ${API_TOKEN}"}',
'{"card_number": "card_number", "verification_code": "verification_code"}',
'您的银行卡余额为：${balance}元，可用余额：${available_balance}元。',
'余额查询失败：${error_message}，请检查卡号或稍后重试。');

-- 插入Prompt模板配置
INSERT INTO prompt_templates (template_name, template_type, intent_id, template_content, variables, version, priority, is_active, created_by) VALUES
-- 意图识别模板
('book_flight_intent_recognition', 'intent_recognition',
(SELECT id FROM intents WHERE intent_name = 'book_flight'),
'根据用户输入识别是否为机票预订意图：\n用户输入: {user_input}\n上下文: {context}\n请判断意图并返回JSON格式结果: {"intent": "intent_name", "confidence": 0.95}',
'["user_input", "context"]', '1.0', 10, TRUE, 'system'),

-- 查余额意图识别模板
('check_balance_intent_recognition', 'intent_recognition',
(SELECT id FROM intents WHERE intent_name = 'check_balance'),
'根据用户输入识别是否为余额查询意图：\n用户输入: {user_input}\n上下文: {context}\n请判断意图并返回JSON格式结果: {"intent": "intent_name", "confidence": 0.95}',
'["user_input", "context"]', '1.0', 9, TRUE, 'system'),

-- 槽位提取模板
('flight_slot_extraction', 'slot_filling',
(SELECT id FROM intents WHERE intent_name = 'book_flight'),
'从用户输入中提取机票预订相关槽位：\n用户输入: {user_input}\n需要提取的槽位: {slot_definitions}\n请返回JSON格式结果: {"slots": {"departure_city": "北京", "arrival_city": "上海"}}',
'["user_input", "slot_definitions"]', '1.1', 8, TRUE, 'system'),

-- 银行卡槽位提取模板
('balance_slot_extraction', 'slot_filling',
(SELECT id FROM intents WHERE intent_name = 'check_balance'),
'从用户输入中提取银行卡余额查询相关槽位：\n用户输入: {user_input}\n需要提取的槽位: {slot_definitions}\n请返回JSON格式结果: {"slots": {"card_number": "6222****5678"}}',
'["user_input", "slot_definitions"]', '1.0', 7, TRUE, 'system'),

-- 歧义澄清模板
('global_disambiguation', 'disambiguation', NULL,
'用户输入存在歧义，请选择您的意图：\n{ambiguous_options}\n请回复数字选择或直接描述您的需求',
'["ambiguous_options"]', '1.0', 5, TRUE, 'system'),

-- 响应生成模板
('slot_filling_response', 'response_generation', NULL,
'基于缺失槽位生成友好的提示：\n缺失槽位: {missing_slots}\n用户历史: {user_history}\n生成个性化提示语',
'["missing_slots", "user_history"]', '1.0', 6, TRUE, 'system'),

-- 闲聊响应模板
('small_talk_response', 'response_generation',
(SELECT id FROM intents WHERE intent_name = 'small_talk'),
'友好回应用户的闲聊，并适当引导回到业务主题：\n用户输入: {user_input}\n当前上下文: {context}\n生成友好且有引导性的回复',
'["user_input", "context"]', '1.0', 3, TRUE, 'system'),

-- 取消意图响应模板
('cancel_intent_response', 'response_generation',
(SELECT id FROM intents WHERE intent_name = 'cancel_intent'),
'确认用户取消操作并提供后续选项：\n取消的意图: {cancelled_intent}\n已填充槽位: {filled_slots}\n生成确认取消的友好回复',
'["cancelled_intent", "filled_slots"]', '1.0', 4, TRUE, 'system'),

-- 兜底响应模板
('fallback_response', 'fallback', NULL,
'对无法理解的用户输入提供友好的兜底回复：\n用户输入: {user_input}\n提供帮助选项并引导用户重新表达需求',
'["user_input"]', '1.0', 1, TRUE, 'system');

-- 插入系统配置
INSERT INTO system_configs (config_category, config_key, config_value, value_type, description) VALUES
('thresholds', 'intent_confidence_threshold', '0.7', 'number', '意图识别置信度阈值'),
('thresholds', 'ambiguity_detection_threshold', '0.1', 'number', '歧义检测阈值'),
('thresholds', 'intent_transfer_threshold', '0.1', 'number', '意图转移检测阈值'),
('thresholds', 'slot_confidence_threshold', '0.6', 'number', '槽位置信度阈值'),
('session', 'session_timeout_seconds', '86400', 'number', '会话超时时间'),
('session', 'max_conversation_turns', '50', 'number', '最大对话轮数'),
('performance', 'nlu_cache_ttl', '1800', 'number', 'NLU结果缓存TTL'),
('performance', 'api_timeout_seconds', '30', 'number', 'API调用超时时间'),
('performance', 'max_retry_attempts', '3', 'number', '最大重试次数'),
('performance', 'async_task_timeout_seconds', '300', 'number', '异步任务超时时间'),
('performance', 'cache_performance_tracking', 'true', 'boolean', '是否启用缓存性能追踪'),
('security', 'jwt_expiry_hours', '24', 'number', 'JWT过期时间'),
('security', 'rate_limit_per_minute', '100', 'number', '每分钟请求限制'),
('security', 'enable_ip_whitelist', 'false', 'boolean', '是否启用IP白名单'),
('security', 'security_alert_threshold', '5', 'number', '安全告警阈值'),
('security', 'auto_block_enabled', 'true', 'boolean', '是否启用自动阻断'),
('ragflow', 'enable_ragflow', 'true', 'boolean', '是否启用RAGFLOW集成'),
('ragflow', 'health_check_interval', '300', 'number', 'RAGFLOW健康检查间隔(秒)'),
('ragflow', 'failure_threshold', '3', 'number', 'RAGFLOW失败阈值'),
('template', 'enable_ab_testing', 'true', 'boolean', '是否启用A/B测试'),
('async', 'enable_async_processing', 'true', 'boolean', '是否启用异步处理'),
('async', 'max_concurrent_tasks', '10', 'number', '最大并发任务数');

-- 插入RAGFLOW配置
INSERT INTO ragflow_configs (config_name, api_endpoint, api_key_encrypted, api_version, timeout_seconds, max_retries, rate_limit_per_minute, connection_pool_size, health_check_interval, config_metadata, is_active) VALUES
('default_ragflow', 'https://api.ragflow.com/v1/chat', 'encrypted_ragflow_api_key_here', 'v1', 30, 3, 100, 10, 300,
'{"headers": {"Content-Type": "application/json", "Authorization": "Bearer ${API_KEY}"}, "fallback_config": {"enable_fallback": true, "fallback_response": "抱歉，服务暂时不可用，请稍后重试。"}, "health_check_url": "https://api.ragflow.com/health"}',
TRUE),

('backup_ragflow', 'https://backup.ragflow.com/v1/chat', 'encrypted_backup_ragflow_key', 'v1', 45, 5, 60, 5, 600,
'{"headers": {"Content-Type": "application/json", "Authorization": "Bearer ${BACKUP_API_KEY}"}, "fallback_config": {"enable_fallback": true, "fallback_response": "备用服务暂时不可用。"}, "health_check_url": "https://backup.ragflow.com/health"}',
FALSE);

-- 插入示例会话数据
INSERT INTO sessions (session_id, user_id, current_intent_id, current_intent_name, session_state, context, metadata, channel, expires_at) VALUES
('session_test_001', 'test_user_001', (SELECT id FROM intents WHERE intent_name = 'book_flight'), 'book_flight', 'active',
'{"user_preference": {"language": "zh-CN", "notification": true}, "session_context": {"platform": "web", "device": "desktop"}}',
'{"source": "web_chat", "referrer": "homepage", "user_agent": "Mozilla/5.0"}', 'web',
DATE_ADD(NOW(), INTERVAL 1 DAY)),

('session_test_002', 'test_user_002', (SELECT id FROM intents WHERE intent_name = 'check_balance'), 'check_balance', 'active',
'{"user_preference": {"language": "zh-CN", "notification": false}, "session_context": {"platform": "mobile", "device": "iphone"}}',
'{"source": "mobile_app", "app_version": "1.2.3", "os": "iOS 14.0"}', 'mobile',
DATE_ADD(NOW(), INTERVAL 1 DAY)),

('session_test_003', 'enterprise_001', NULL, NULL, 'active',
'{"company_settings": {"auto_approve": true, "budget_limit": 50000}, "session_context": {"platform": "api", "integration": "erp"}}',
'{"source": "api", "client_id": "erp_system_001", "version": "2.1"}', 'api',
DATE_ADD(NOW(), INTERVAL 2 DAY));

-- 插入示例对话数据
INSERT INTO conversations (session_id, user_id, conversation_turn, user_input, user_input_type, intent_id, intent_name, confidence_score, slots_filled, slots_missing, system_response, response_type, status, processing_time_ms) VALUES
-- 订机票对话示例
('session_test_001', 'test_user_001', 1, '我想订机票', 'text',
(SELECT id FROM intents WHERE intent_name = 'book_flight'), 'book_flight', 0.95,
'{}', '["departure_city", "arrival_city", "departure_date"]',
'好的，我来帮您预订机票。请问您要从哪个城市出发呢？', 'slot_prompt', 'pending_user', 150),

('session_test_001', 'test_user_001', 2, '从北京出发', 'text',
(SELECT id FROM intents WHERE intent_name = 'book_flight'), 'book_flight', 0.92,
'{"departure_city": "北京"}', '["arrival_city", "departure_date"]',
'好的，从北京出发。请问您要到达哪个城市呢？', 'slot_prompt', 'pending_user', 120),

('session_test_001', 'test_user_001', 3, '到上海', 'text',
(SELECT id FROM intents WHERE intent_name = 'book_flight'), 'book_flight', 0.90,
'{"departure_city": "北京", "arrival_city": "上海"}', '["departure_date"]',
'明白了，从北京到上海。请问您计划什么时候出发呢？', 'slot_prompt', 'pending_user', 100),

-- 查余额对话示例
('session_test_002', 'test_user_002', 1, '查余额', 'text',
(SELECT id FROM intents WHERE intent_name = 'check_balance'), 'check_balance', 0.88,
'{}', '["card_number"]',
'好的，我来帮您查询银行卡余额。请提供您的银行卡号（16位数字）。', 'slot_prompt', 'pending_user', 80),

('session_test_002', 'test_user_002', 2, '我的卡号是6222080012345678', 'text',
(SELECT id FROM intents WHERE intent_name = 'check_balance'), 'check_balance', 0.85,
'{"card_number": "6222080012345678"}', '["verification_code"]',
'已收到您的银行卡信息。为了确保安全，请输入手机验证码（6位数字）。', 'slot_prompt', 'pending_user', 200);

-- 插入用户上下文数据
INSERT INTO user_contexts (user_id, context_type, context_key, context_value, scope, priority, expires_at, is_active) VALUES
-- 用户偏好设置
('test_user_001', 'preference', 'language', '"zh-CN"', 'global', 1, NULL, TRUE),
('test_user_001', 'preference', 'notification_enabled', 'true', 'global', 1, NULL, TRUE),
('test_user_001', 'preference', 'preferred_airlines', '["中国国际航空", "中国南方航空"]', 'global', 2, NULL, TRUE),
('test_user_001', 'preference', 'seat_preference', '"经济舱"', 'global', 3, NULL, TRUE),

('test_user_002', 'preference', 'language', '"zh-CN"', 'global', 1, NULL, TRUE),
('test_user_002', 'preference', 'notification_enabled', 'false', 'global', 1, NULL, TRUE),
('test_user_002', 'preference', 'default_bank', '"中国工商银行"', 'global', 2, NULL, TRUE),

-- 历史信息
('test_user_001', 'history', 'last_flight_booking', '{"departure_city": "北京", "arrival_city": "上海", "booking_date": "2024-11-15"}', 'global', 1, NULL, TRUE),
('test_user_002', 'history', 'last_balance_check', '{"card_number": "6222****5678", "check_date": "2024-11-10"}', 'global', 1, NULL, TRUE),

-- 会话临时数据
('test_user_001', 'temporary', 'current_booking_progress', '{"step": "date_selection", "completed_slots": ["departure_city", "arrival_city"]}', 'session', 1, DATE_ADD(NOW(), INTERVAL 2 HOUR), TRUE),
('test_user_002', 'temporary', 'verification_attempts', '1', 'session', 1, DATE_ADD(NOW(), INTERVAL 10 MINUTE), TRUE);

-- 创建索引优化查询性能
CREATE INDEX idx_conversations_session_created ON conversations(session_id, created_at);
CREATE INDEX idx_conversations_status_type ON conversations(status, response_type);
CREATE INDEX idx_slots_intent_required ON slots(intent_id, is_required);
CREATE INDEX idx_function_calls_intent_active ON function_calls(intent_id, is_active);
CREATE INDEX idx_prompt_templates_type_active ON prompt_templates(template_type, is_active);
CREATE INDEX idx_user_contexts_user_type ON user_contexts(user_id, context_type);
CREATE INDEX idx_intent_transfers_session_created ON intent_transfers(session_id, created_at);
CREATE INDEX idx_api_call_logs_endpoint_status ON api_call_logs(api_endpoint(100), response_status);
CREATE INDEX idx_security_audit_logs_risk_created ON security_audit_logs(risk_level, created_at);
CREATE INDEX idx_async_tasks_status_type ON async_tasks(status, task_type);
CREATE INDEX idx_async_tasks_user_created ON async_tasks(user_id, created_at);

-- 创建视图优化查询
CREATE VIEW v_active_intents AS
SELECT i.*,
       (SELECT COUNT(*) FROM slots s WHERE s.intent_id = i.id AND s.is_required = TRUE) as required_slot_count,
       (SELECT COUNT(*) FROM function_calls fc WHERE fc.intent_id = i.id AND fc.is_active = TRUE) as function_count
FROM intents i
WHERE i.is_active = TRUE;

CREATE VIEW v_conversation_summary AS
SELECT session_id,
       user_id,
       COUNT(*) as total_turns,
       COUNT(DISTINCT intent_name) as unique_intents,
       AVG(confidence_score) as avg_confidence,
       AVG(processing_time_ms) as avg_processing_time,
       MIN(created_at) as session_start,
       MAX(created_at) as session_end
FROM conversations
WHERE created_at >= DATE_SUB(NOW(), INTERVAL 30 DAY)
GROUP BY session_id, user_id;

-- v2.2 存储过程与触发器说明
-- 在v2.2版本中，我们遵循了将业务逻辑与数据存储分离的最佳实践，移除了原有的存储过程和触发器。
-- 这样做的好处是：
-- 1. 逻辑清晰：业务逻辑集中在应用层，便于理解、维护和迭代。
-- 2. 性能更优：避免了数据库触发器可能带来的同步阻塞和性能瓶颈。
-- 3. 可扩展性强：应用层逻辑更容易进行水平扩展和集成现代化的消息队列、缓存系统。
-- 4. 易于测试：应用层代码比数据库存储过程更容易进行单元测试和集成测试。
--
-- 以下是原功能的推荐实现方式：
--
-- 1. 审计日志 (原LogConfigChange存储过程和相关触发器):
--    应在应用层的服务方法（Service Layer）中实现。当一个配置（如Intent）被修改时，在同一个数据库事务中，
--    先执行UPDATE/INSERT/DELETE操作，然后向`config_audit_logs`表插入一条记录。操作者信息应作为参数显式传入。
--
-- 2. 缓存失效 (原InvalidateRelatedCache存储过程):
--    推荐使用发布/订阅模式。当配置变更事务成功提交后，应用层发布一个事件（如`IntentUpdatedEvent`）到
--    消息队列（如Redis Pub/Sub, RabbitMQ）。一个或多个后台消费者服务订阅这些事件，并执行具体的缓存清理操作。
--    同时，应用层也可以向`cache_invalidation_logs`表写入记录，由一个专职的后台服务轮询处理。
--
-- 3. 会话清理 (原CleanupExpiredSessions存储过程):
--    应由一个定期的后台任务（如Cron Job或Kubernetes CronJob）来执行。该任务会定期调用一个API接口或
--    执行一个脚本，来清理过期的`sessions`和`user_contexts`。
--
-- 4. 异步日志写入 (原WriteAsyncLog存储过程):
--    应用层直接向`async_log_queue`表写入数据即可。一个或多个后台工作进程（Worker）会从此队列中读取并处理日志。

-- 新增：上下文引用解析表 (支持多轮对话的代词引用解析)
CREATE TABLE IF NOT EXISTS context_references (
    id INT PRIMARY KEY AUTO_INCREMENT,
    session_id VARCHAR(100) NOT NULL COMMENT '会话ID',
    conversation_turn INT NOT NULL COMMENT '对话轮次',
    reference_text VARCHAR(500) NOT NULL COMMENT '引用文本（如"那里"、"它"、"上个"等）',
    resolved_slot_name VARCHAR(100) COMMENT '解析到的槽位名称',
    resolved_value TEXT COMMENT '解析后的值',
    reference_turn INT COMMENT '引用的对话轮次',
    reference_type ENUM('pronoun', 'temporal', 'spatial', 'entity', 'other') DEFAULT 'pronoun' COMMENT '引用类型',
    confidence DECIMAL(5,4) COMMENT '解析置信度',
    resolution_method VARCHAR(50) COMMENT '解析方法',
    is_validated BOOLEAN DEFAULT FALSE COMMENT '是否已验证',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    FOREIGN KEY (session_id) REFERENCES sessions(session_id) ON DELETE CASCADE,
    INDEX idx_session_turn (session_id, conversation_turn),
    INDEX idx_reference_type (reference_type),
    INDEX idx_confidence (confidence),
    INDEX idx_resolved_slot (resolved_slot_name)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='上下文引用解析表';

-- 新增：会话状态快照表 (用于快速查询会话当前状态)
CREATE TABLE IF NOT EXISTS session_state_snapshots (
    id INT PRIMARY KEY AUTO_INCREMENT,
    session_id VARCHAR(100) NOT NULL COMMENT '会话ID',
    current_turn INT NOT NULL COMMENT '当前轮次',
    current_intent_id INT COMMENT '当前意图ID',
    current_intent_name VARCHAR(100) COMMENT '当前意图名称',
    filled_slots JSON COMMENT '已填充的槽位快照',
    missing_slots JSON COMMENT '缺失的槽位快照',
    session_context JSON COMMENT '会话上下文快照',
    state_status ENUM('incomplete', 'completed', 'error', 'pending_confirmation') DEFAULT 'incomplete' COMMENT '状态',
    last_response_type VARCHAR(50) COMMENT '最后响应类型',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    FOREIGN KEY (session_id) REFERENCES sessions(session_id) ON DELETE CASCADE,
    FOREIGN KEY (current_intent_id) REFERENCES intents(id) ON DELETE SET NULL,
    INDEX idx_session_intent (session_id, current_intent_id),
    INDEX idx_state_status (state_status),
    INDEX idx_updated_time (updated_at),
    UNIQUE KEY uk_session_state (session_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='会话状态快照表';

