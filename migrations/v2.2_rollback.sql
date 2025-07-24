-- V2.2回滚脚本
-- 将数据库从V2.2回滚到V2.1结构
-- 警告：此脚本会删除V2.2新增的数据和功能

SET FOREIGN_KEY_CHECKS = 0;
SET AUTOCOMMIT = 0;

-- 开始事务
START TRANSACTION;

-- =============================================================================
-- 1. 预回滚检查和备份
-- =============================================================================

-- 记录回滚开始
INSERT INTO config_audit_logs (table_name, record_id, action, old_values, new_values, operator_id, operator_name)
VALUES ('system_rollback', 0, 'UPDATE', 
        JSON_OBJECT('version', 'v2.2', 'rollback_started_at', NOW()),
        JSON_OBJECT('version', 'v2.1', 'target_version', 'v2.1'),
        'rollback_script', 'V2.2 Rollback Script');

-- 创建槽位值数据备份（以防回滚后需要恢复）
CREATE TABLE IF NOT EXISTS _backup_slot_values_v22 AS
SELECT * FROM slot_values WHERE extracted_from IN ('migration_v21', 'session_migration');

-- 验证备份表是否存在（确保可以恢复原始数据）
SELECT COUNT(*) as original_backup_count FROM _backup_conversations_v21;

-- =============================================================================
-- 2. 恢复conversations表的槽位数据
-- =============================================================================

-- 2.1 从slot_values表重新构建slots_filled JSON字段
UPDATE conversations c
SET slots_filled = (
    SELECT JSON_OBJECTAGG(sv.slot_name, 
           CASE 
               WHEN sv.slot_value IS NULL THEN NULL
               WHEN JSON_VALID(sv.slot_value) THEN JSON_EXTRACT(sv.slot_value, '$')
               ELSE sv.slot_value
           END
    )
    FROM slot_values sv
    WHERE sv.conversation_id = c.id 
      AND sv.validation_status = 'valid'
      AND sv.slot_value IS NOT NULL
    GROUP BY sv.conversation_id
)
WHERE c.id IN (
    SELECT DISTINCT conversation_id 
    FROM slot_values 
    WHERE conversation_id IS NOT NULL 
      AND validation_status = 'valid'
      AND slot_value IS NOT NULL
);

-- 2.2 从slot_values表重新构建slots_missing JSON数组字段
UPDATE conversations c
SET slots_missing = (
    SELECT JSON_ARRAYAGG(sv.slot_name)
    FROM slot_values sv
    WHERE sv.conversation_id = c.id 
      AND sv.validation_status = 'missing'
    GROUP BY sv.conversation_id
)
WHERE c.id IN (
    SELECT DISTINCT conversation_id 
    FROM slot_values 
    WHERE conversation_id IS NOT NULL 
      AND validation_status = 'missing'
);

-- =============================================================================
-- 3. 重新创建V2.1的数据库对象
-- =============================================================================

-- 3.1 重新创建存储过程
DELIMITER $$

CREATE PROCEDURE GetIntentWithSlots(
    IN p_intent_name VARCHAR(100)
)
BEGIN
    SELECT 
        i.id, i.intent_name, i.display_name, i.description,
        i.is_active, i.confidence_threshold,
        GROUP_CONCAT(
            CONCAT(s.slot_name, ':', s.slot_type, ':', IFNULL(s.is_required, 0))
            ORDER BY s.slot_order SEPARATOR ';'
        ) as slots_info
    FROM intents i
    LEFT JOIN slots s ON i.id = s.intent_id AND s.is_active = 1
    WHERE i.intent_name = p_intent_name AND i.is_active = 1
    GROUP BY i.id;
END$$

CREATE PROCEDURE CleanupExpiredSessions(
    IN p_expiry_hours INT DEFAULT 24
)
BEGIN
    DECLARE v_cutoff_time DATETIME DEFAULT DATE_SUB(NOW(), INTERVAL p_expiry_hours HOUR);
    
    -- 标记过期会话
    UPDATE sessions 
    SET session_state = 'expired' 
    WHERE session_state = 'active' 
      AND (expires_at < NOW() OR updated_at < v_cutoff_time);
    
    -- 返回清理统计
    SELECT 
        ROW_COUNT() as expired_sessions,
        (SELECT COUNT(*) FROM sessions WHERE session_state = 'active') as active_sessions,
        NOW() as cleanup_time;
END$$

CREATE PROCEDURE LogConfigChange(
    IN p_table_name VARCHAR(100),
    IN p_record_id BIGINT,
    IN p_action VARCHAR(20),
    IN p_old_values JSON,
    IN p_new_values JSON,
    IN p_operator_id VARCHAR(100)
)
BEGIN
    INSERT INTO config_audit_logs (
        table_name, record_id, action, old_values, new_values, 
        operator_id, operator_name
    ) VALUES (
        p_table_name, p_record_id, p_action, p_old_values, p_new_values,
        p_operator_id, COALESCE(p_operator_id, 'system')
    );
END$$

CREATE PROCEDURE InvalidateRelatedCache(
    IN p_cache_keys JSON,
    IN p_reason VARCHAR(200)
)
BEGIN
    INSERT INTO cache_invalidation_logs (
        cache_keys, invalidation_reason, invalidation_status, priority
    ) VALUES (
        p_cache_keys, p_reason, 'pending', 1
    );
END$$

CREATE PROCEDURE WriteAsyncLog(
    IN p_log_type VARCHAR(50),
    IN p_log_data JSON,
    IN p_priority INT DEFAULT 1
)
BEGIN
    INSERT INTO async_log_queue (
        log_type, log_data, priority, status
    ) VALUES (
        p_log_type, p_log_data, p_priority, 'pending'
    );
END$$

DELIMITER ;

-- 3.2 重新创建触发器
DELIMITER $$

-- 意图表审计触发器
CREATE TRIGGER tr_intents_audit_insert
    AFTER INSERT ON intents
    FOR EACH ROW
BEGIN
    CALL LogConfigChange('intents', NEW.id, 'INSERT', 
                        NULL, 
                        JSON_OBJECT('intent_name', NEW.intent_name, 'display_name', NEW.display_name),
                        'trigger_system');
END$$

CREATE TRIGGER tr_intents_audit_update  
    AFTER UPDATE ON intents
    FOR EACH ROW
BEGIN
    IF OLD.intent_name != NEW.intent_name OR OLD.display_name != NEW.display_name OR OLD.is_active != NEW.is_active THEN
        CALL LogConfigChange('intents', NEW.id, 'UPDATE',
                            JSON_OBJECT('intent_name', OLD.intent_name, 'display_name', OLD.display_name, 'is_active', OLD.is_active),
                            JSON_OBJECT('intent_name', NEW.intent_name, 'display_name', NEW.display_name, 'is_active', NEW.is_active),
                            'trigger_system');
    END IF;
END$$

CREATE TRIGGER tr_intents_audit_delete
    AFTER DELETE ON intents  
    FOR EACH ROW
BEGIN
    CALL LogConfigChange('intents', OLD.id, 'DELETE',
                        JSON_OBJECT('intent_name', OLD.intent_name, 'display_name', OLD.display_name),
                        NULL,
                        'trigger_system');
END$$

-- 槽位表审计触发器
CREATE TRIGGER tr_slots_audit_insert
    AFTER INSERT ON slots
    FOR EACH ROW
BEGIN
    CALL LogConfigChange('slots', NEW.id, 'INSERT',
                        NULL,
                        JSON_OBJECT('slot_name', NEW.slot_name, 'intent_id', NEW.intent_id, 'slot_type', NEW.slot_type),
                        'trigger_system');
END$$

CREATE TRIGGER tr_slots_audit_update
    AFTER UPDATE ON slots
    FOR EACH ROW  
BEGIN
    IF OLD.slot_name != NEW.slot_name OR OLD.slot_type != NEW.slot_type OR OLD.is_required != NEW.is_required THEN
        CALL LogConfigChange('slots', NEW.id, 'UPDATE',
                            JSON_OBJECT('slot_name', OLD.slot_name, 'slot_type', OLD.slot_type, 'is_required', OLD.is_required),
                            JSON_OBJECT('slot_name', NEW.slot_name, 'slot_type', NEW.slot_type, 'is_required', NEW.is_required),
                            'trigger_system');
    END IF;
END$$

CREATE TRIGGER tr_slots_audit_delete
    AFTER DELETE ON slots
    FOR EACH ROW
BEGIN
    CALL LogConfigChange('slots', OLD.id, 'DELETE', 
                        JSON_OBJECT('slot_name', OLD.slot_name, 'intent_id', OLD.intent_id, 'slot_type', OLD.slot_type),
                        NULL,
                        'trigger_system');
END$$

-- 系统配置表审计触发器
CREATE TRIGGER tr_system_configs_audit_insert
    AFTER INSERT ON system_configs
    FOR EACH ROW
BEGIN
    CALL LogConfigChange('system_configs', NEW.id, 'INSERT',
                        NULL,
                        JSON_OBJECT('config_key', NEW.config_key, 'config_value', NEW.config_value),
                        'trigger_system');
END$$

CREATE TRIGGER tr_system_configs_audit_update
    AFTER UPDATE ON system_configs  
    FOR EACH ROW
BEGIN
    IF OLD.config_value != NEW.config_value THEN
        CALL LogConfigChange('system_configs', NEW.id, 'UPDATE',
                            JSON_OBJECT('config_key', OLD.config_key, 'config_value', OLD.config_value),
                            JSON_OBJECT('config_key', NEW.config_key, 'config_value', NEW.config_value),
                            'trigger_system');
                            
        -- 触发相关缓存失效
        CALL InvalidateRelatedCache(
            JSON_ARRAY(CONCAT('config:', OLD.config_key)),
            CONCAT('Config updated: ', OLD.config_key)
        );
    END IF;
END$$

CREATE TRIGGER tr_system_configs_audit_delete
    AFTER DELETE ON system_configs
    FOR EACH ROW
BEGIN
    CALL LogConfigChange('system_configs', OLD.id, 'DELETE',
                        JSON_OBJECT('config_key', OLD.config_key, 'config_value', OLD.config_value),
                        NULL,
                        'trigger_system');
END$$

DELIMITER ;

-- =============================================================================
-- 4. 恢复原始表结构
-- =============================================================================

-- 4.1 将config_audit_logs.record_id字段改回INT类型
ALTER TABLE config_audit_logs MODIFY COLUMN record_id INT NOT NULL COMMENT '记录ID';

-- 4.2 恢复conversations表状态字段为ENUM
ALTER TABLE conversations MODIFY COLUMN status ENUM(
    'processing', 'completed', 'failed', 'pending_user', 'ambiguous', 
    'api_error', 'timeout', 'cancelled'
) DEFAULT 'processing' COMMENT '对话状态';

-- 4.3 删除V2.2新增的索引
DROP INDEX IF EXISTS idx_status_intent ON conversations;
DROP INDEX IF EXISTS idx_user_status_time ON conversations;
DROP INDEX IF EXISTS idx_slot_values_session_intent ON slot_values;
DROP INDEX IF EXISTS idx_slot_values_active_slots ON slot_values;
DROP INDEX IF EXISTS idx_conversations_session_status_time ON conversations;
DROP INDEX IF EXISTS idx_sessions_user_state_updated ON sessions;

-- =============================================================================
-- 5. 删除V2.2特有的数据和表
-- =============================================================================

-- 5.1 删除V2.2的槽位值数据（保留在备份表中）
DELETE FROM slot_values WHERE extracted_from IN ('migration_v21', 'session_migration');

-- 5.2 可选：删除整个slot_values表（如果要完全回到V2.1）
-- DROP TABLE IF EXISTS slot_values;

-- =============================================================================
-- 6. 恢复表注释
-- =============================================================================

ALTER TABLE conversations COMMENT = '对话历史表 (V2.1: 使用JSON字段存储槽位数据)';
ALTER TABLE config_audit_logs COMMENT = '配置审计日志表 (V2.1: 由触发器自动写入)';
ALTER TABLE cache_invalidation_logs COMMENT = '缓存失效日志表 (V2.1: 由触发器写入，供后台服务消费)';

-- =============================================================================
-- 7. 数据一致性验证
-- =============================================================================

-- 验证槽位数据恢复情况
SELECT 
    'Rollback Verification' as check_type,
    COUNT(*) as conversations_with_restored_slots,
    (SELECT COUNT(*) FROM _backup_conversations_v21) as original_backup_count,
    (SELECT COUNT(*) FROM slot_values) as remaining_slot_values,
    NOW() as verified_at
FROM conversations 
WHERE slots_filled IS NOT NULL OR slots_missing IS NOT NULL;

-- 检查触发器和存储过程是否正确创建
SELECT 
    'Database Objects Check' as check_type,
    (SELECT COUNT(*) FROM information_schema.ROUTINES 
     WHERE ROUTINE_SCHEMA = DATABASE() AND ROUTINE_TYPE = 'PROCEDURE') as procedures_count,
    (SELECT COUNT(*) FROM information_schema.TRIGGERS 
     WHERE TRIGGER_SCHEMA = DATABASE()) as triggers_count;

-- =============================================================================
-- 8. 记录回滚完成
-- =============================================================================

INSERT INTO config_audit_logs (table_name, record_id, action, old_values, new_values, operator_id, operator_name)
VALUES ('system_rollback', 0, 'UPDATE',
        JSON_OBJECT('version', 'v2.2'),
        JSON_OBJECT(
            'version', 'v2.1',
            'rollback_completed_at', NOW(),
            'restored_conversations', (SELECT COUNT(*) FROM conversations WHERE slots_filled IS NOT NULL OR slots_missing IS NOT NULL),
            'backup_tables', JSON_ARRAY('_backup_conversations_v21', '_backup_slot_values_v22')
        ),
        'rollback_script', 'V2.2 Rollback Script');

-- =============================================================================
-- 9. 完成回滚
-- =============================================================================

-- 最终验证查询
SELECT 
    'Rollback Completed' as status,
    (SELECT COUNT(*) FROM conversations WHERE slots_filled IS NOT NULL OR slots_missing IS NOT NULL) as conversations_with_slots,
    (SELECT COUNT(*) FROM information_schema.ROUTINES WHERE ROUTINE_SCHEMA = DATABASE() AND ROUTINE_TYPE = 'PROCEDURE') as procedures,
    (SELECT COUNT(*) FROM information_schema.TRIGGERS WHERE TRIGGER_SCHEMA = DATABASE()) as triggers,
    NOW() as rollback_completed_at;

-- 提交事务
COMMIT;

SET AUTOCOMMIT = 1;
SET FOREIGN_KEY_CHECKS = 1;

-- =============================================================================
-- 回滚完成提示
-- =============================================================================

SELECT 'V2.2 Rollback Completed Successfully!' as status,
       'Database has been rolled back to V2.1 structure.' as result,
       'Backup tables contain V2.2 data for recovery if needed.' as backup_info;

-- 注意事项说明
SELECT 'IMPORTANT NOTES:' as notice,
       '1. V2.2 slot_values data is backed up in _backup_slot_values_v22' as note1,
       '2. Original V2.1 data is in _backup_conversations_v21' as note2,
       '3. All V2.1 triggers and procedures have been restored' as note3,
       '4. Please restart your application and verify functionality' as note4;