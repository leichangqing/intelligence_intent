-- V2.2数据库升级脚本
-- 从V2.1升级到V2.2结构
-- 主要变更：业务逻辑上移到应用层，数据规范化，性能优化

SET FOREIGN_KEY_CHECKS = 0;
SET AUTOCOMMIT = 0;

-- 开始事务
START TRANSACTION;

-- =============================================================================
-- 1. 备份关键数据（可选，建议在脚本执行前手动备份数据库）
-- =============================================================================

-- 创建备份表存储原有数据
CREATE TABLE IF NOT EXISTS _backup_conversations_v21 AS
SELECT id, session_id, user_id, conversation_turn, user_input, user_input_type,
       intent_id, intent_name, confidence_score, slots_filled, slots_missing,
       system_response, response_type, response_metadata, status, 
       processing_time_ms, error_message, created_at, updated_at
FROM conversations
WHERE slots_filled IS NOT NULL OR slots_missing IS NOT NULL;

-- 记录升级开始时间和统计信息
INSERT INTO config_audit_logs (table_name, record_id, action, old_values, new_values, operator_id, operator_name)
VALUES ('system_upgrade', 0, 'UPDATE', 
        JSON_OBJECT('version', 'v2.1', 'backup_records', (SELECT COUNT(*) FROM _backup_conversations_v21)),
        JSON_OBJECT('version', 'v2.2', 'started_at', NOW()),
        'migration_script', 'V2.2 Migration Script');

-- =============================================================================
-- 2. 表结构变更
-- =============================================================================

-- 2.1 修改config_audit_logs表的record_id字段类型
ALTER TABLE config_audit_logs MODIFY COLUMN record_id BIGINT NOT NULL COMMENT '记录ID';

-- 2.2 修改conversations表状态字段类型（从ENUM改为VARCHAR以支持扩展）
ALTER TABLE conversations MODIFY COLUMN status VARCHAR(50) COMMENT '对话状态码, 关联conversation_statuses.status_code';

-- 2.3 为conversations表添加新的索引（V2.2优化）
ALTER TABLE conversations ADD INDEX idx_status_intent (status, intent_name);
ALTER TABLE conversations ADD INDEX idx_user_status_time (user_id, status, created_at);

-- 2.4 确保slot_values表存在且结构正确
CREATE TABLE IF NOT EXISTS slot_values (
    id INT PRIMARY KEY AUTO_INCREMENT,
    session_id VARCHAR(100) NOT NULL COMMENT '会话ID',
    conversation_id INT COMMENT '对话ID',
    intent_name VARCHAR(100) COMMENT '意图名称',
    slot_name VARCHAR(100) NOT NULL COMMENT '槽位名称',
    slot_value TEXT COMMENT '槽位值',
    validation_status ENUM('valid', 'invalid', 'pending', 'corrected', 'missing') DEFAULT 'pending' COMMENT '验证状态',
    confidence_score DECIMAL(5,4) DEFAULT 0.0000 COMMENT '置信度分数',
    extracted_from VARCHAR(50) COMMENT '提取来源',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    
    INDEX idx_session_slot (session_id, slot_name),
    INDEX idx_conversation_slot (conversation_id, slot_name),
    INDEX idx_intent_slot (intent_name, slot_name),
    INDEX idx_validation_status (validation_status),
    INDEX idx_confidence (confidence_score),
    INDEX idx_created_at (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='槽位值存储表(V2.2)';

-- =============================================================================
-- 3. 数据迁移
-- =============================================================================

-- 3.1 迁移conversations表中的slots_filled数据到slot_values表
INSERT INTO slot_values (session_id, conversation_id, intent_name, slot_name, slot_value, validation_status, confidence_score, extracted_from)
SELECT 
    c.session_id,
    c.id,
    c.intent_name,
    slot_key,
    slot_value,
    'valid' as validation_status,
    GREATEST(c.confidence_score, 0.8) as confidence_score,
    'migration_v21' as extracted_from
FROM conversations c
CROSS JOIN JSON_TABLE(
    COALESCE(c.slots_filled, '{}'),
    '$.*' COLUMNS(
        slot_key VARCHAR(100) PATH '$.key',
        slot_value TEXT PATH '$.value'
    )
) AS slots_data
WHERE c.slots_filled IS NOT NULL 
  AND JSON_VALID(c.slots_filled)
  AND JSON_LENGTH(c.slots_filled) > 0
ON DUPLICATE KEY UPDATE
    slot_value = VALUES(slot_value),
    validation_status = 'valid',
    confidence_score = VALUES(confidence_score),
    updated_at = NOW();

-- 3.2 迁移conversations表中的slots_missing数据到slot_values表
INSERT INTO slot_values (session_id, conversation_id, intent_name, slot_name, slot_value, validation_status, confidence_score, extracted_from)
SELECT 
    c.session_id,
    c.id,
    c.intent_name,
    missing_slot,
    NULL as slot_value,
    'missing' as validation_status,
    0.0 as confidence_score,
    'migration_v21' as extracted_from
FROM conversations c
CROSS JOIN JSON_TABLE(
    COALESCE(c.slots_missing, '[]'),
    '$[*]' COLUMNS(
        missing_slot VARCHAR(100) PATH '$'
    )
) AS missing_slots
WHERE c.slots_missing IS NOT NULL 
  AND JSON_VALID(c.slots_missing)
  AND JSON_LENGTH(c.slots_missing) > 0
ON DUPLICATE KEY UPDATE
    validation_status = 'missing',
    updated_at = NOW();

-- 3.3 为已迁移的数据添加会话级别的槽位值（用于会话上下文）
INSERT INTO slot_values (session_id, conversation_id, intent_name, slot_name, slot_value, validation_status, confidence_score, extracted_from)
SELECT DISTINCT 
    sv.session_id,
    NULL as conversation_id,
    sv.intent_name,
    sv.slot_name,
    sv.slot_value,
    sv.validation_status,
    MAX(sv.confidence_score) as confidence_score,
    'session_migration' as extracted_from
FROM slot_values sv
WHERE sv.conversation_id IS NOT NULL
  AND sv.validation_status = 'valid'
GROUP BY sv.session_id, sv.intent_name, sv.slot_name, sv.slot_value, sv.validation_status
ON DUPLICATE KEY UPDATE
    confidence_score = GREATEST(confidence_score, VALUES(confidence_score)),
    updated_at = NOW();

-- =============================================================================
-- 4. 删除已弃用的数据库对象
-- =============================================================================

-- 4.1 删除V2.1的存储过程（业务逻辑已移至应用层）
DROP PROCEDURE IF EXISTS GetIntentWithSlots;
DROP PROCEDURE IF EXISTS CleanupExpiredSessions;
DROP PROCEDURE IF EXISTS LogConfigChange;
DROP PROCEDURE IF EXISTS InvalidateRelatedCache;
DROP PROCEDURE IF EXISTS WriteAsyncLog;

-- 4.2 删除V2.1的触发器（审计逻辑已移至应用层）
DROP TRIGGER IF EXISTS tr_intents_audit_insert;
DROP TRIGGER IF EXISTS tr_intents_audit_update;
DROP TRIGGER IF EXISTS tr_intents_audit_delete;
DROP TRIGGER IF EXISTS tr_slots_audit_insert;
DROP TRIGGER IF EXISTS tr_slots_audit_update;
DROP TRIGGER IF EXISTS tr_slots_audit_delete;
DROP TRIGGER IF EXISTS tr_system_configs_audit_insert;
DROP TRIGGER IF EXISTS tr_system_configs_audit_update;
DROP TRIGGER IF EXISTS tr_system_configs_audit_delete;

-- =============================================================================
-- 5. 数据一致性验证
-- =============================================================================

-- 5.1 验证槽位数据迁移完整性
SELECT 
    'Migration Verification' as check_type,
    COUNT(*) as total_conversations_with_slots,
    (SELECT COUNT(DISTINCT conversation_id) FROM slot_values WHERE conversation_id IS NOT NULL) as migrated_conversations,
    (SELECT COUNT(*) FROM slot_values) as total_slot_values,
    NOW() as verified_at
FROM conversations 
WHERE slots_filled IS NOT NULL OR slots_missing IS NOT NULL;

-- 5.2 检查是否存在未迁移的数据
SELECT 
    'Unmigrated Data Check' as check_type,
    COUNT(*) as conversations_with_unmigrated_slots
FROM conversations c
LEFT JOIN slot_values sv ON c.id = sv.conversation_id
WHERE (c.slots_filled IS NOT NULL OR c.slots_missing IS NOT NULL)
  AND sv.conversation_id IS NULL;

-- =============================================================================
-- 6. 更新表注释和元数据
-- =============================================================================

-- 6.1 更新表注释标明V2.2版本
ALTER TABLE conversations COMMENT = '对话历史表 (V2.2: 槽位数据已迁移至slot_values表)';
ALTER TABLE config_audit_logs COMMENT = '配置审计日志表 (V2.2: 由应用层写入，触发器已移除)';
ALTER TABLE cache_invalidation_logs COMMENT = '缓存失效日志表 (V2.2: 由应用层写入，供后台服务消费)';

-- 6.2 记录升级完成信息
INSERT INTO config_audit_logs (table_name, record_id, action, old_values, new_values, operator_id, operator_name)
VALUES ('system_upgrade', 0, 'UPDATE',
        JSON_OBJECT('version', 'v2.1'),
        JSON_OBJECT(
            'version', 'v2.2', 
            'completed_at', NOW(),
            'migrated_slot_values', (SELECT COUNT(*) FROM slot_values),
            'backup_table', '_backup_conversations_v21'
        ),
        'migration_script', 'V2.2 Migration Script');

-- =============================================================================
-- 7. 性能优化索引
-- =============================================================================

-- 7.1 为新的查询模式添加优化索引
CREATE INDEX IF NOT EXISTS idx_slot_values_session_intent ON slot_values(session_id, intent_name, validation_status);
CREATE INDEX IF NOT EXISTS idx_slot_values_active_slots ON slot_values(session_id, slot_name, validation_status) 
WHERE validation_status IN ('valid', 'pending');

-- 7.2 为频繁查询的组合添加复合索引
CREATE INDEX IF NOT EXISTS idx_conversations_session_status_time ON conversations(session_id, status, created_at);
CREATE INDEX IF NOT EXISTS idx_sessions_user_state_updated ON sessions(user_id, session_state, updated_at);

-- =============================================================================
-- 8. 清理和优化
-- =============================================================================

-- 8.1 更新表统计信息
ANALYZE TABLE conversations;
ANALYZE TABLE slot_values;
ANALYZE TABLE sessions;
ANALYZE TABLE config_audit_logs;

-- 8.2 优化表碎片
OPTIMIZE TABLE conversations;
OPTIMIZE TABLE slot_values;

-- =============================================================================
-- 9. 验证升级结果
-- =============================================================================

-- 最终验证查询
SELECT 
    'Final Verification' as status,
    (SELECT COUNT(*) FROM _backup_conversations_v21) as backed_up_records,
    (SELECT COUNT(*) FROM slot_values) as total_slot_values,
    (SELECT COUNT(DISTINCT session_id) FROM slot_values) as sessions_with_slot_values,
    (SELECT COUNT(*) FROM conversations WHERE slots_filled IS NOT NULL OR slots_missing IS NOT NULL) as conversations_with_legacy_slots,
    NOW() as migration_completed_at;

-- 提交事务
COMMIT;

SET AUTOCOMMIT = 1;
SET FOREIGN_KEY_CHECKS = 1;

-- =============================================================================
-- 升级完成提示
-- =============================================================================

SELECT 'V2.2 Migration Completed Successfully!' as status,
       'Please verify the migration results and test your application.' as next_steps,
       'Backup table _backup_conversations_v21 contains original slot data.' as backup_info;