-- 智能意图识别系统数据库表结构 v2.1
-- 支持B2B无状态设计、混合Prompt Template配置、RAGFLOW集成、智能歧义处理等高级功能
-- v2.1 优化说明：根据专家评审意见优化数据类型一致性、可维护性和性能
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
DROP TABLE IF EXISTS slot_dependencies;
DROP TABLE IF EXISTS slots;
DROP TABLE IF EXISTS response_types;
DROP TABLE IF EXISTS conversation_statuses;
DROP TABLE IF EXISTS intents;

-- 重新启用外键检查
SET FOREIGN_KEY_CHECKS = 1;

-- 1. 意图配置表
CREATE TABLE IF NOT EXISTS intents (
    id INT AUTO_INCREMENT PRIMARY KEY,
    intent_name VARCHAR(100) NOT NULL UNIQUE COMMENT '意图名称',
    display_name VARCHAR(200) NOT NULL COMMENT '显示名称',
    description TEXT COMMENT '意图描述',
    confidence_threshold DECIMAL(3,2) DEFAULT 0.7 COMMENT '置信度阈值',
    priority INT DEFAULT 1 COMMENT '意图优先级，数字越大优先级越高',
    is_active BOOLEAN DEFAULT TRUE COMMENT '是否激活',
    examples JSON COMMENT '示例语句，JSON数组格式',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_intent_name (intent_name),
    INDEX idx_active (is_active)
) COMMENT '意图配置表';

-- 2. 槽位配置表
DROP TABLE IF EXISTS slots;
CREATE TABLE IF NOT EXISTS slots (
    id INT AUTO_INCREMENT PRIMARY KEY,
    intent_id INT NOT NULL,
    slot_name VARCHAR(100) NOT NULL COMMENT '槽位名称',
    slot_type VARCHAR(50) NOT NULL COMMENT '槽位类型：TEXT, DATE, NUMBER, ENUM等',
    is_required BOOLEAN DEFAULT FALSE COMMENT '是否必填',
    validation_rules JSON COMMENT '验证规则',
    prompt_template TEXT COMMENT '询问模板',
    examples JSON COMMENT '示例值，JSON数组格式',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (intent_id) REFERENCES intents(id) ON DELETE CASCADE,
    UNIQUE KEY unique_intent_slot (intent_id, slot_name),
    INDEX idx_intent_id (intent_id)
) COMMENT '槽位配置表';

-- 2.1 槽位值存储表
DROP TABLE IF EXISTS slot_values;
CREATE TABLE IF NOT EXISTS slot_values (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    conversation_id BIGINT NOT NULL COMMENT '会话ID',
    slot_id INT NOT NULL COMMENT '关联槽位',
    value TEXT NOT NULL COMMENT '槽位值',
    original_text TEXT COMMENT '原始文本',
    confidence DECIMAL(5,4) DEFAULT 1.0 COMMENT '置信度',
    extraction_method VARCHAR(50) DEFAULT 'llm' COMMENT '提取方法：llm, rule, duckling, manual',
    normalized_value TEXT COMMENT '标准化值',
    is_validated BOOLEAN DEFAULT TRUE COMMENT '是否已验证',
    validation_error TEXT COMMENT '验证错误信息',
    source_turn INT COMMENT '来源轮次',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (conversation_id) REFERENCES conversations(id) ON DELETE CASCADE,
    FOREIGN KEY (slot_id) REFERENCES slots(id) ON DELETE CASCADE,
    INDEX idx_conversation_slot (conversation_id, slot_id),
    INDEX idx_conversation_turn (conversation_id, source_turn),
    INDEX idx_extraction_method (extraction_method),
    INDEX idx_validated (is_validated)
) COMMENT '槽位值存储表';

-- 2.2 槽位依赖关系表
DROP TABLE IF EXISTS slot_dependencies;
CREATE TABLE IF NOT EXISTS slot_dependencies (
    id INT AUTO_INCREMENT PRIMARY KEY,
    dependent_slot_id INT NOT NULL COMMENT '依赖槽位',
    required_slot_id INT NOT NULL COMMENT '被依赖槽位',
    dependency_type VARCHAR(50) DEFAULT 'required' COMMENT '依赖类型：required, conditional, mutex',
    dependency_condition JSON COMMENT '依赖条件',
    priority INT DEFAULT 0 COMMENT '优先级',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (dependent_slot_id) REFERENCES slots(id) ON DELETE CASCADE,
    FOREIGN KEY (required_slot_id) REFERENCES slots(id) ON DELETE CASCADE,
    UNIQUE KEY unique_dependency (dependent_slot_id, required_slot_id),
    INDEX idx_dependency_type (dependency_type),
    INDEX idx_priority (priority)
) COMMENT '槽位依赖关系表';

-- 3. 功能调用配置表
DROP TABLE IF EXISTS function_calls;
CREATE TABLE IF NOT EXISTS function_calls (
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
DROP TABLE IF EXISTS sessions;
CREATE TABLE IF NOT EXISTS sessions (
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
DROP TABLE IF EXISTS conversations;
CREATE TABLE IF NOT EXISTS conversations (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    session_id VARCHAR(100) NOT NULL COMMENT '会话ID',
    user_id VARCHAR(100) NOT NULL COMMENT '用户ID',
    user_input TEXT NOT NULL COMMENT '用户输入',
    intent_recognized VARCHAR(100) COMMENT '识别的意图',
    confidence_score DECIMAL(5,4) COMMENT '置信度分数',
    slots_filled JSON COMMENT '已填充的槽位',
    system_response TEXT COMMENT '系统响应',
    response_type ENUM('api_result', 'task_completion', 'slot_prompt', 'disambiguation', 'qa_response', 'small_talk_with_context_return', 'intent_transfer_with_completion', 'cancellation_confirmation', 'postponement_with_save', 'rejection_acknowledgment', 'validation_error_prompt', 'error_with_alternatives', 'multi_intent_with_continuation', 'security_error') COMMENT '响应类型',
    status ENUM('completed', 'incomplete', 'ambiguous', 'api_error', 'validation_error', 'ragflow_handled', 'interruption_handled', 'multi_intent_processing', 'intent_cancelled', 'intent_postponed', 'suggestion_rejected', 'intent_transfer', 'slot_filling', 'context_maintained') COMMENT '处理状态',
    processing_time_ms INT COMMENT '处理时间毫秒',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_session_id (session_id),
    INDEX idx_user_id (user_id),
    INDEX idx_intent (intent_recognized),
    INDEX idx_created_at (created_at)
) COMMENT '对话历史表';

-- 6. 意图歧义处理表
DROP TABLE IF EXISTS intent_ambiguities;
CREATE TABLE IF NOT EXISTS intent_ambiguities (
    id INT AUTO_INCREMENT PRIMARY KEY,
    conversation_id BIGINT NOT NULL COMMENT '对话ID',
    candidate_intents JSON NOT NULL COMMENT '候选意图列表',
    disambiguation_question TEXT NOT NULL COMMENT '歧义消除问题',
    user_choice VARCHAR(100) COMMENT '用户选择的意图',
    resolved_at TIMESTAMP NULL COMMENT '解决时间',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (conversation_id) REFERENCES conversations(id) ON DELETE CASCADE,
    INDEX idx_conversation_id (conversation_id),
    INDEX idx_resolved (resolved_at)
) COMMENT '意图歧义处理表';

-- 7. 配置审计日志表
DROP TABLE IF EXISTS config_audit_logs;
CREATE TABLE IF NOT EXISTS config_audit_logs (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    table_name VARCHAR(50) NOT NULL COMMENT '表名',
    record_id INT NOT NULL COMMENT '记录ID',
    action ENUM('INSERT', 'UPDATE', 'DELETE') NOT NULL COMMENT '操作类型',
    old_values JSON COMMENT '修改前的值',
    new_values JSON COMMENT '修改后的值',
    operator_id VARCHAR(100) NOT NULL COMMENT '操作者ID',
    operator_name VARCHAR(100) COMMENT '操作者姓名',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_table_record (table_name, record_id),
    INDEX idx_operator (operator_id),
    INDEX idx_created_at (created_at)
) COMMENT '配置审计日志表';

-- 8. Prompt模板配置表
DROP TABLE IF EXISTS prompt_templates;
CREATE TABLE IF NOT EXISTS prompt_templates (
    id INT AUTO_INCREMENT PRIMARY KEY,
    template_name VARCHAR(100) NOT NULL COMMENT '模板名称',
    template_type ENUM('intent_recognition', 'slot_extraction', 'disambiguation', 'response_generation') NOT NULL COMMENT '模板类型',
    intent_id INT NULL COMMENT '关联意图ID，NULL表示通用模板',
    template_content TEXT NOT NULL COMMENT '模板内容',
    variables JSON COMMENT '模板变量列表',
    version VARCHAR(20) DEFAULT '1.0' COMMENT '模板版本',
    priority INT DEFAULT 0 COMMENT '模板优先级，数字越大优先级越高，用于多个通用模板选择',
    is_active BOOLEAN DEFAULT TRUE COMMENT '是否激活',
    is_default BOOLEAN DEFAULT FALSE COMMENT '是否为默认模板',
    ab_test_config JSON COMMENT 'A/B测试配置',
    performance_metrics JSON COMMENT '性能指标',
    description TEXT COMMENT '模板描述',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (intent_id) REFERENCES intents(id) ON DELETE CASCADE,
    UNIQUE KEY unique_template_intent_type (template_name, intent_id, template_type),
    INDEX idx_template_type (template_type),
    INDEX idx_intent_id (intent_id),
    INDEX idx_active (is_active),
    INDEX idx_priority (priority)
) COMMENT 'Prompt模板配置表（增加优先级支持）';

-- 9. 用户上下文表
DROP TABLE IF EXISTS user_contexts;
CREATE TABLE IF NOT EXISTS user_contexts (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    user_id VARCHAR(100) NOT NULL COMMENT '用户ID',
    context_type ENUM('preferences', 'history', 'temporary', 'session') COMMENT '上下文类型',
    context_key VARCHAR(100) NOT NULL COMMENT '上下文键',
    context_value JSON NOT NULL COMMENT '上下文值',
    expires_at TIMESTAMP NULL COMMENT '过期时间',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY unique_user_context (user_id, context_type, context_key),
    INDEX idx_user_id (user_id),
    INDEX idx_context_type (context_type),
    INDEX idx_expires_at (expires_at)
) COMMENT '用户上下文表';

-- 10. 意图转移记录表
DROP TABLE IF EXISTS intent_transfers;
CREATE TABLE IF NOT EXISTS intent_transfers (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    session_id VARCHAR(100) NOT NULL COMMENT '会话ID',
    user_id VARCHAR(100) NOT NULL COMMENT '用户ID',
    from_intent VARCHAR(100) COMMENT '源意图',
    to_intent VARCHAR(100) NOT NULL COMMENT '目标意图',
    transfer_type ENUM('interruption', 'explicit_change', 'system_suggestion', 'disambiguation') COMMENT '转移类型',
    saved_context JSON COMMENT '保存的上下文',
    transfer_reason TEXT COMMENT '转移原因',
    confidence_score DECIMAL(5,4) COMMENT '转移置信度',
    resumed_at TIMESTAMP NULL COMMENT '恢复时间',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_session_id (session_id),
    INDEX idx_user_id (user_id),
    INDEX idx_transfer_type (transfer_type),
    INDEX idx_created_at (created_at)
) COMMENT '意图转移记录表';

-- 11. 系统配置表
DROP TABLE IF EXISTS system_configs;
CREATE TABLE IF NOT EXISTS system_configs (
    id INT AUTO_INCREMENT PRIMARY KEY,
    config_category VARCHAR(50) NOT NULL COMMENT '配置分类',
    config_key VARCHAR(100) NOT NULL COMMENT '配置键',
    config_value TEXT NOT NULL COMMENT '配置值',
    value_type ENUM('string', 'number', 'boolean', 'json') DEFAULT 'string' COMMENT '值类型',
    description TEXT COMMENT '配置描述',
    is_encrypted BOOLEAN DEFAULT FALSE COMMENT '是否加密存储',
    is_active BOOLEAN DEFAULT TRUE COMMENT '是否激活',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY unique_category_key (config_category, config_key),
    INDEX idx_category (config_category),
    INDEX idx_active (is_active)
) COMMENT '系统配置表';

-- 12. API调用日志表
DROP TABLE IF EXISTS api_call_logs;
CREATE TABLE IF NOT EXISTS api_call_logs (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    conversation_id BIGINT NOT NULL COMMENT '对话ID',
    function_name VARCHAR(100) NOT NULL COMMENT '函数名称',
    api_endpoint VARCHAR(500) NOT NULL COMMENT 'API端点',
    request_params JSON COMMENT '请求参数',
    response_data JSON COMMENT '响应数据',
    status_code INT COMMENT 'HTTP状态码',
    response_time_ms INT COMMENT '响应时间毫秒',
    error_message TEXT COMMENT '错误信息',
    retry_count INT DEFAULT 0 COMMENT '重试次数',
    success BOOLEAN COMMENT '是否成功',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (conversation_id) REFERENCES conversations(id) ON DELETE CASCADE,
    INDEX idx_conversation_id (conversation_id),
    INDEX idx_function_name (function_name),
    INDEX idx_success (success),
    INDEX idx_created_at (created_at)
) COMMENT 'API调用日志表';

-- 13. RAGFLOW集成配置表
DROP TABLE IF EXISTS ragflow_configs;
CREATE TABLE IF NOT EXISTS ragflow_configs (
    id INT AUTO_INCREMENT PRIMARY KEY,
    config_name VARCHAR(100) NOT NULL UNIQUE COMMENT '配置名称',
    api_endpoint VARCHAR(500) NOT NULL COMMENT 'RAGFLOW API端点',
    api_key VARCHAR(200) COMMENT 'API密钥',
    headers JSON COMMENT '请求头配置',
    timeout_seconds INT DEFAULT 30 COMMENT '超时时间',
    rate_limit JSON COMMENT '频率限制配置',
    fallback_config JSON COMMENT '回退配置',
    health_check_url VARCHAR(500) COMMENT '健康检查URL',
    is_active BOOLEAN DEFAULT TRUE COMMENT '是否激活',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_config_name (config_name),
    INDEX idx_active (is_active)
) COMMENT 'RAGFLOW集成配置表';

-- 14. 安全审计日志表
DROP TABLE IF EXISTS security_audit_logs;
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
DROP TABLE IF EXISTS async_tasks;
CREATE TABLE IF NOT EXISTS async_tasks (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    task_id VARCHAR(100) NOT NULL UNIQUE COMMENT '任务ID',
    task_type ENUM('api_call', 'batch_process', 'data_export', 'ragflow_call') NOT NULL COMMENT '任务类型',
    status ENUM('pending', 'processing', 'completed', 'failed', 'cancelled') DEFAULT 'pending' COMMENT '任务状态',
    conversation_id BIGINT COMMENT '关联对话ID',
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
) COMMENT '异步任务管理表';

-- 16. 缓存一致性管理表
DROP TABLE IF EXISTS cache_invalidation_logs;
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
) COMMENT '缓存失效日志表';

-- 17. 异步日志队列表
DROP TABLE IF EXISTS async_log_queue;
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

-- 18. 响应类型定义表（优化ENUM可维护性）
DROP TABLE IF EXISTS response_types;
CREATE TABLE IF NOT EXISTS response_types (
    id INT AUTO_INCREMENT PRIMARY KEY,
    type_code VARCHAR(50) NOT NULL UNIQUE COMMENT '响应类型码',
    type_name VARCHAR(100) NOT NULL COMMENT '响应类型名称',
    description TEXT COMMENT '类型描述',
    category VARCHAR(50) COMMENT '类型分类',
    is_active BOOLEAN DEFAULT TRUE COMMENT '是否激活',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_type_code (type_code),
    INDEX idx_category (category),
    INDEX idx_active (is_active)
) COMMENT '响应类型定义表';

-- 19. 对话状态定义表（优化ENUM可维护性）
DROP TABLE IF EXISTS conversation_statuses;
CREATE TABLE IF NOT EXISTS conversation_statuses (
    id INT AUTO_INCREMENT PRIMARY KEY,
    status_code VARCHAR(50) NOT NULL UNIQUE COMMENT '状态码',
    status_name VARCHAR(100) NOT NULL COMMENT '状态名称',
    description TEXT COMMENT '状态描述',
    category VARCHAR(50) COMMENT '状态分类',
    is_final BOOLEAN DEFAULT FALSE COMMENT '是否为终态',
    is_active BOOLEAN DEFAULT TRUE COMMENT '是否激活',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_status_code (status_code),
    INDEX idx_category (category),
    INDEX idx_active (is_active)
) COMMENT '对话状态定义表';

-- 初始化数据 v2.1

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
INSERT INTO slots (intent_id, slot_name, slot_type, is_required, validation_rules, prompt_template, examples) VALUES
((SELECT id FROM intents WHERE intent_name = 'book_flight'), 'departure_city', 'TEXT', TRUE, 
'{"min_length": 2, "max_length": 20}', '请告诉我出发城市是哪里？', '["北京", "上海", "广州", "深圳"]'),

((SELECT id FROM intents WHERE intent_name = 'book_flight'), 'arrival_city', 'TEXT', TRUE, 
'{"min_length": 2, "max_length": 20}', '请告诉我到达城市是哪里？', '["北京", "上海", "广州", "深圳"]'),

((SELECT id FROM intents WHERE intent_name = 'book_flight'), 'departure_date', 'DATE', TRUE, 
'{"format": "YYYY-MM-DD", "min_date": "today"}', '请告诉我出发日期是哪天？', '["2024-12-01", "明天", "下周一"]'),

((SELECT id FROM intents WHERE intent_name = 'book_flight'), 'return_date', 'DATE', FALSE, 
'{"format": "YYYY-MM-DD", "min_date": "departure_date"}', '请问是否需要返程票？如果需要，请告诉我返程日期。', '["2024-12-05", "下周五", "不需要"]'),

((SELECT id FROM intents WHERE intent_name = 'book_flight'), 'passenger_count', 'NUMBER', FALSE, 
'{"min": 1, "max": 9, "default": 1}', '请告诉我乘客人数，默认为1人。', '["1", "2", "3人"]'),

((SELECT id FROM intents WHERE intent_name = 'book_flight'), 'seat_class', 'ENUM', FALSE, 
'{"options": ["经济舱", "商务舱", "头等舱"], "default": "经济舱"}', '请选择座位等级：经济舱、商务舱或头等舱？', '["经济舱", "商务舱", "头等舱"]');

-- 插入查银行卡余额相关槽位
INSERT INTO slots (intent_id, slot_name, slot_type, is_required, validation_rules, prompt_template, examples) VALUES
((SELECT id FROM intents WHERE intent_name = 'check_balance'), 'card_number', 'TEXT', TRUE, 
'{"pattern": "^\\\\d{16}$|^\\\\d{4}\\\\s\\\\d{4}\\\\s\\\\d{4}\\\\s\\\\d{4}$", "mask": true}', '请提供您的银行卡号（16位数字）', '["6222080012345678", "6222 0800 1234 5678"]'),

((SELECT id FROM intents WHERE intent_name = 'check_balance'), 'verification_code', 'TEXT', FALSE, 
'{"pattern": "^\\\\d{6}$", "expires": 300}', '请输入手机验证码（6位数字）', '["123456", "验证码"]');

-- 插入槽位依赖关系
INSERT INTO slot_dependencies (dependent_slot_id, required_slot_id, dependency_type, dependency_condition, priority) VALUES
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
INSERT INTO prompt_templates (template_name, template_type, intent_id, template_content, variables, version, is_active, is_default, description) VALUES
-- 意图识别模板
('book_flight_intent_recognition', 'intent_recognition', 
(SELECT id FROM intents WHERE intent_name = 'book_flight'), 
'根据用户输入识别是否为机票预订意图：\n用户输入: {user_input}\n上下文: {context}\n请判断意图并返回JSON格式结果: {"intent": "intent_name", "confidence": 0.95}', 
'["user_input", "context"]', '1.0', TRUE, TRUE, '机票预订意图识别专用模板'),

-- 槽位提取模板
('flight_slot_extraction', 'slot_extraction', 
(SELECT id FROM intents WHERE intent_name = 'book_flight'), 
'从用户输入中提取机票预订相关槽位：\n用户输入: {user_input}\n需要提取的槽位: {slot_definitions}\n请返回JSON格式结果: {"slots": {"departure_city": "北京", "arrival_city": "上海"}}', 
'["user_input", "slot_definitions"]', '1.1', TRUE, TRUE, '机票槽位提取模板'),

-- 歧义澄清模板
('global_disambiguation', 'disambiguation', NULL, 
'用户输入存在歧义，请选择您的意图：\n{ambiguous_options}\n请回复数字选择或直接描述您的需求', 
'["ambiguous_options"]', '1.0', TRUE, TRUE, '通用歧义澄清模板'),

-- 响应生成模板
('slot_filling_response', 'response_generation', NULL, 
'基于缺失槽位生成友好的提示：\n缺失槽位: {missing_slots}\n用户历史: {user_history}\n生成个性化提示语', 
'["missing_slots", "user_history"]', '1.0', TRUE, TRUE, '槽位填充响应生成模板');

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
INSERT INTO ragflow_configs (config_name, api_endpoint, api_key, headers, timeout_seconds, rate_limit, fallback_config, health_check_url) VALUES
('default_ragflow', 'https://api.ragflow.com/v1/chat', 'ragflow_api_key_here', 
'{"Content-Type": "application/json", "Authorization": "Bearer ${API_KEY}"}', 30,
'{"requests_per_minute": 100, "requests_per_hour": 1000}',
'{"enable_fallback": true, "fallback_response": "抱歉，服务暂时不可用，请稍后重试。"}',
'https://api.ragflow.com/health');

-- 创建索引优化查询性能
CREATE INDEX idx_conversations_session_created ON conversations(session_id, created_at);
CREATE INDEX idx_conversations_status_type ON conversations(status, response_type);
CREATE INDEX idx_slots_intent_required ON slots(intent_id, is_required);
CREATE INDEX idx_function_calls_intent_active ON function_calls(intent_id, is_active);
CREATE INDEX idx_prompt_templates_type_active ON prompt_templates(template_type, is_active);
CREATE INDEX idx_user_contexts_user_type ON user_contexts(user_id, context_type);
CREATE INDEX idx_intent_transfers_session_created ON intent_transfers(session_id, created_at);
CREATE INDEX idx_api_call_logs_function_success ON api_call_logs(function_name, success);
CREATE INDEX idx_security_audit_logs_risk_created ON security_audit_logs(risk_level, created_at);
CREATE INDEX idx_async_tasks_status_type ON async_tasks(status, task_type);
CREATE INDEX idx_async_tasks_user_created ON async_tasks(user_id, created_at);

-- 创建视图优化查询
DROP VIEW IF EXISTS v_active_intents;
CREATE VIEW v_active_intents AS
SELECT i.*, 
       COUNT(s.id) as slot_count,
       COUNT(fc.id) as function_count
FROM intents i
LEFT JOIN slots s ON i.id = s.intent_id AND s.is_required = TRUE
LEFT JOIN function_calls fc ON i.id = fc.intent_id AND fc.is_active = TRUE
WHERE i.is_active = TRUE
GROUP BY i.id;

DROP VIEW IF EXISTS v_conversation_summary;
CREATE VIEW v_conversation_summary AS
SELECT session_id,
       user_id,
       COUNT(*) as total_turns,
       COUNT(DISTINCT intent_recognized) as unique_intents,
       AVG(confidence_score) as avg_confidence,
       AVG(processing_time_ms) as avg_processing_time,
       MIN(created_at) as session_start,
       MAX(created_at) as session_end
FROM conversations
WHERE created_at >= DATE_SUB(NOW(), INTERVAL 30 DAY)
GROUP BY session_id, user_id;

-- 创建存储过程优化常用操作
DROP PROCEDURE IF EXISTS GetIntentWithSlots;
DROP PROCEDURE IF EXISTS CleanupExpiredSessions;

DELIMITER //

CREATE PROCEDURE GetIntentWithSlots(IN p_intent_name VARCHAR(100))
BEGIN
    SELECT i.*, 
           JSON_ARRAYAGG(
               JSON_OBJECT(
                   'slot_name', s.slot_name,
                   'slot_type', s.slot_type,
                   'is_required', s.is_required,
                   'validation_rules', s.validation_rules,
                   'prompt_template', s.prompt_template
               )
           ) as slots
    FROM intents i
    LEFT JOIN slots s ON i.id = s.intent_id
    WHERE i.intent_name = p_intent_name AND i.is_active = TRUE
    GROUP BY i.id;
END //

CREATE PROCEDURE CleanupExpiredSessions()
BEGIN
    DECLARE cleaned_sessions INT DEFAULT 0;
    
    -- 清理过期会话
    UPDATE sessions 
    SET session_state = 'expired' 
    WHERE session_state = 'active' 
    AND (expires_at < NOW() OR created_at < DATE_SUB(NOW(), INTERVAL 7 DAY));
    
    SET cleaned_sessions = ROW_COUNT();
    
    -- 清理过期用户上下文
    DELETE FROM user_contexts 
    WHERE expires_at IS NOT NULL AND expires_at < NOW();
    
    SELECT cleaned_sessions as cleaned_sessions_count, ROW_COUNT() as cleaned_contexts_count;
END //

-- 改进的审计日志存储过程
CREATE PROCEDURE LogConfigChange(
    IN p_table_name VARCHAR(50),
    IN p_record_id INT,
    IN p_action ENUM('INSERT', 'UPDATE', 'DELETE'),
    IN p_old_values JSON,
    IN p_new_values JSON,
    IN p_operator_id VARCHAR(100),
    IN p_operator_name VARCHAR(100)
)
BEGIN
    -- 插入审计日志
    INSERT INTO config_audit_logs (
        table_name, record_id, action, old_values, new_values, 
        operator_id, operator_name
    ) VALUES (
        p_table_name, p_record_id, p_action, p_old_values, p_new_values,
        p_operator_id, p_operator_name
    );
    
    -- 生成缓存失效日志
    CALL InvalidateRelatedCache(p_table_name, p_record_id, p_action);
END //

-- 缓存失效管理存储过程
CREATE PROCEDURE InvalidateRelatedCache(
    IN p_table_name VARCHAR(50),
    IN p_record_id VARCHAR(100),
    IN p_operation ENUM('INSERT', 'UPDATE', 'DELETE')
)
BEGIN
    DECLARE cache_keys_json JSON;
    
    -- 根据表名生成相关的缓存键
    CASE p_table_name
        WHEN 'intents' THEN
            SET cache_keys_json = JSON_ARRAY(
                CONCAT('intent_config:all'),
                CONCAT('intent_config:', (SELECT intent_name FROM intents WHERE id = p_record_id))
            );
        WHEN 'slots' THEN
            SET cache_keys_json = JSON_ARRAY(
                CONCAT('intent_config:', (SELECT i.intent_name FROM intents i JOIN slots s ON i.id = s.intent_id WHERE s.id = p_record_id))
            );
        WHEN 'prompt_templates' THEN
            SET cache_keys_json = JSON_ARRAY(
                CONCAT('template_config:', p_record_id),
                'template_config:all'
            );
        WHEN 'system_configs' THEN
            SET cache_keys_json = JSON_ARRAY(
                'system_config:all',
                CONCAT('system_config:', (SELECT config_category FROM system_configs WHERE id = p_record_id))
            );
        ELSE
            SET cache_keys_json = JSON_ARRAY(CONCAT(p_table_name, ':', p_record_id));
    END CASE;
    
    -- 插入缓存失效日志
    INSERT INTO cache_invalidation_logs (
        table_name, record_id, operation_type, cache_keys
    ) VALUES (
        p_table_name, p_record_id, p_operation, cache_keys_json
    );
END //

-- 异步日志写入存储过程
CREATE PROCEDURE WriteAsyncLog(
    IN p_log_type ENUM('api_call', 'security_audit', 'performance', 'error'),
    IN p_log_data JSON,
    IN p_priority INT
)
BEGIN
    INSERT INTO async_log_queue (log_type, log_data, priority) 
    VALUES (p_log_type, p_log_data, p_priority);
END //

DELIMITER ;

-- 改进的触发器实现审计日志（使用存储过程）
DROP TRIGGER IF EXISTS tr_intents_audit_insert;
DROP TRIGGER IF EXISTS tr_intents_audit_update;
DROP TRIGGER IF EXISTS tr_intents_audit_delete;

CREATE TRIGGER tr_intents_audit_insert
AFTER INSERT ON intents
FOR EACH ROW
BEGIN
    -- 使用存储过程确保操作者信息不为空
    CALL LogConfigChange(
        'intents', 
        NEW.id, 
        'INSERT',
        NULL,
        JSON_OBJECT('intent_name', NEW.intent_name, 'display_name', NEW.display_name, 
                   'confidence_threshold', NEW.confidence_threshold, 'priority', NEW.priority),
        COALESCE(@current_user_id, 'system'),
        COALESCE(@current_user_name, 'System User')
    );
END //

CREATE TRIGGER tr_intents_audit_update
AFTER UPDATE ON intents
FOR EACH ROW
BEGIN
    CALL LogConfigChange(
        'intents',
        NEW.id,
        'UPDATE',
        JSON_OBJECT('intent_name', OLD.intent_name, 'display_name', OLD.display_name, 
                   'confidence_threshold', OLD.confidence_threshold, 'priority', OLD.priority),
        JSON_OBJECT('intent_name', NEW.intent_name, 'display_name', NEW.display_name, 
                   'confidence_threshold', NEW.confidence_threshold, 'priority', NEW.priority),
        COALESCE(@current_user_id, 'system'),
        COALESCE(@current_user_name, 'System User')
    );
END //

CREATE TRIGGER tr_intents_audit_delete
AFTER DELETE ON intents
FOR EACH ROW
BEGIN
    CALL LogConfigChange(
        'intents',
        OLD.id,
        'DELETE',
        JSON_OBJECT('intent_name', OLD.intent_name, 'display_name', OLD.display_name),
        NULL,
        COALESCE(@current_user_id, 'system'),
        COALESCE(@current_user_name, 'System User')
    );
END //

DELIMITER ;