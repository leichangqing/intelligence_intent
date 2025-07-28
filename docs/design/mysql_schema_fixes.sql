-- 修复SQL脚本中的问题
-- 1. 添加缺失的last_health_check字段到system_configs表
-- 2. 创建缺失的config_audit_logs表
-- 3. 修复重复索引名称问题

USE intent_db;
SET FOREIGN_KEY_CHECKS = 0;

-- 修复system_configs表（添加last_health_check字段）
ALTER TABLE system_configs 
ADD COLUMN last_health_check TIMESTAMP NULL COMMENT '最后健康检查时间' AFTER is_active,
ADD INDEX systemconfig_last_health_check (last_health_check);

-- 创建config_audit_logs表（如果不存在）
CREATE TABLE IF NOT EXISTS config_audit_logs (
    id INT PRIMARY KEY AUTO_INCREMENT,
    operation_type VARCHAR(20) NOT NULL COMMENT '操作类型',
    table_name VARCHAR(100) NOT NULL COMMENT '表名',
    record_id VARCHAR(100) NOT NULL COMMENT '记录ID',
    old_values JSON COMMENT '旧值',
    new_values JSON COMMENT '新值',
    operation_by VARCHAR(100) COMMENT '操作人',
    operation_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '操作时间',
    INDEX idx_audit_operation (operation_type),
    INDEX idx_audit_table (table_name),
    INDEX idx_audit_time (operation_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='配置变更审计日志表';

-- 重新创建有问题的表（删除重复索引）
DROP TABLE IF EXISTS ragflow_configs;
CREATE TABLE IF NOT EXISTS ragflow_configs (
    id INT PRIMARY KEY AUTO_INCREMENT,
    config_name VARCHAR(100) UNIQUE NOT NULL COMMENT '配置名称',
    display_name VARCHAR(200) NOT NULL COMMENT '显示名称',
    api_url VARCHAR(500) NOT NULL COMMENT 'API地址',
    api_key VARCHAR(200) NOT NULL COMMENT 'API密钥',
    chat_id VARCHAR(100) COMMENT '对话ID',
    timeout_seconds INT DEFAULT 30 COMMENT '超时时间',
    is_active BOOLEAN DEFAULT TRUE COMMENT '是否启用',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    INDEX idx_ragflow_active (is_active)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='RAGFLOW配置表';

DROP TABLE IF EXISTS prompt_templates;  
CREATE TABLE IF NOT EXISTS prompt_templates (
    id INT PRIMARY KEY AUTO_INCREMENT,
    template_name VARCHAR(100) UNIQUE NOT NULL COMMENT '模板名称',
    intent_id INT COMMENT '关联意图ID',
    template_type VARCHAR(50) NOT NULL COMMENT '模板类型',
    template_content TEXT NOT NULL COMMENT '模板内容',
    variables JSON COMMENT '模板变量',
    is_active BOOLEAN DEFAULT TRUE COMMENT '是否激活',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    FOREIGN KEY (intent_id) REFERENCES intents(id) ON DELETE CASCADE,
    INDEX idx_template_intent (intent_id),
    INDEX idx_template_type (template_type)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='提示模板表';

DROP TABLE IF EXISTS intent_ambiguities;
CREATE TABLE IF NOT EXISTS intent_ambiguities (
    id INT PRIMARY KEY AUTO_INCREMENT,
    conversation_id BIGINT NOT NULL COMMENT '对话ID',
    user_input TEXT NOT NULL COMMENT '用户输入',
    candidate_intents JSON NOT NULL COMMENT '候选意图',
    resolved_intent VARCHAR(100) COMMENT '解决的意图',
    resolution_method VARCHAR(50) COMMENT '解决方法',
    resolved_at TIMESTAMP NULL COMMENT '解决时间',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    FOREIGN KEY (conversation_id) REFERENCES conversations(id) ON DELETE CASCADE,
    INDEX idx_ambiguity_conversation (conversation_id),
    INDEX idx_ambiguity_resolved (resolved_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='意图歧义记录表';

DROP TABLE IF EXISTS async_tasks;
CREATE TABLE IF NOT EXISTS async_tasks (
    id INT PRIMARY KEY AUTO_INCREMENT,
    task_id VARCHAR(100) UNIQUE NOT NULL COMMENT '任务ID',
    task_type VARCHAR(50) NOT NULL COMMENT '任务类型',
    task_data JSON COMMENT '任务数据',
    status VARCHAR(20) DEFAULT 'pending' COMMENT '任务状态',
    result JSON COMMENT '执行结果',
    error_message TEXT COMMENT '错误信息',
    retry_count INT DEFAULT 0 COMMENT '重试次数',
    max_retries INT DEFAULT 3 COMMENT '最大重试次数',
    scheduled_at TIMESTAMP NULL COMMENT '计划执行时间',
    started_at TIMESTAMP NULL COMMENT '开始执行时间',
    completed_at TIMESTAMP NULL COMMENT '完成时间',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    INDEX idx_async_status (status),
    INDEX idx_async_type (task_type),
    INDEX idx_async_scheduled (scheduled_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='异步任务表';

DROP TABLE IF EXISTS stop_words;
CREATE TABLE IF NOT EXISTS stop_words (
    id INT PRIMARY KEY AUTO_INCREMENT,
    word VARCHAR(50) UNIQUE NOT NULL COMMENT '停用词',
    language VARCHAR(10) DEFAULT 'zh' COMMENT '语言',
    category VARCHAR(50) COMMENT '分类',
    is_active BOOLEAN DEFAULT TRUE COMMENT '是否启用',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    INDEX idx_stopword_lang (language),
    INDEX idx_stopword_active (is_active)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='停用词表';

DROP TABLE IF EXISTS entity_patterns;
CREATE TABLE IF NOT EXISTS entity_patterns (
    id INT PRIMARY KEY AUTO_INCREMENT,
    pattern_name VARCHAR(100) UNIQUE NOT NULL COMMENT '模式名称',
    entity_type VARCHAR(50) NOT NULL COMMENT '实体类型',
    pattern_regex VARCHAR(500) NOT NULL COMMENT '正则表达式',
    extraction_template VARCHAR(200) COMMENT '提取模板',
    priority INT DEFAULT 1 COMMENT '优先级',
    is_active BOOLEAN DEFAULT TRUE COMMENT '是否启用',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    INDEX idx_pattern_entity (entity_type),
    INDEX idx_pattern_active (is_active),
    INDEX idx_pattern_priority (priority)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='实体识别模式表';

SET FOREIGN_KEY_CHECKS = 1;

SELECT 'SQL修复完成！' as status;