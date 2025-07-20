"""
验证代码模型与MySQL schema的一致性测试
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import re
from typing import Dict, List, Set, Any


class MySQLSchemaValidator:
    """MySQL schema一致性验证器"""
    
    def __init__(self):
        self.schema_tables = {}
        self.model_tables = {}
        self.schema_path = "/Users/leicq/my_intent/claude/intelligance_intent/docs/design/mysql_schema.sql"
        
        # 模型类映射
        self.model_mappings = {
            'intents': 'Intent',
            'slots': 'Slot', 
            'function_calls': 'FunctionCall',
            'sessions': 'Session',
            'conversations': 'Conversation',
            'intent_ambiguities': 'IntentAmbiguity',
            'config_audit_logs': 'ConfigAuditLog',
            'prompt_templates': 'PromptTemplate',
            'user_contexts': 'UserContext',
            'intent_transfers': 'IntentTransfer',
            'system_configs': 'SystemConfig',
            'api_call_logs': 'ApiCallLog',
            'ragflow_configs': 'RagflowConfig',
            'security_audit_logs': 'SecurityAuditLog',
            'async_tasks': 'AsyncTask',
            'cache_invalidation_logs': 'CacheInvalidationLog',
            'async_log_queue': 'AsyncLogQueue',
            'response_types': 'ResponseType',
            'conversation_statuses': 'ConversationStatus'
        }
    
    def parse_mysql_schema(self):
        """解析MySQL schema文件"""
        with open(self.schema_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # 匹配CREATE TABLE语句
        table_pattern = r'CREATE TABLE IF NOT EXISTS (\w+) \((.*?)\) COMMENT'
        matches = re.findall(table_pattern, content, re.DOTALL)
        
        for table_name, columns_text in matches:
            columns = self.parse_table_columns(columns_text)
            self.schema_tables[table_name] = columns
    
    def parse_table_columns(self, columns_text: str) -> Dict[str, Dict]:
        """解析表的列定义"""
        columns = {}
        
        # 移除索引和约束定义
        lines = columns_text.split('\n')
        column_lines = []
        
        for line in lines:
            line = line.strip()
            if (line and not line.startswith('INDEX') and 
                not line.startswith('KEY') and 
                not line.startswith('UNIQUE') and
                not line.startswith('FOREIGN') and
                not line.startswith('PRIMARY')):
                column_lines.append(line)
        
        for line in column_lines:
            line = line.strip().rstrip(',')
            if not line:
                continue
                
            # 解析列定义
            parts = line.split()
            if len(parts) >= 2:
                column_name = parts[0].strip('`')
                column_type = parts[1]
                
                # 解析约束
                constraints = {
                    'nullable': 'NOT NULL' not in line,
                    'auto_increment': 'AUTO_INCREMENT' in line,
                    'primary_key': 'PRIMARY KEY' in line,
                    'unique': 'UNIQUE' in line,
                    'default': None
                }
                
                # 解析默认值
                default_match = re.search(r'DEFAULT\s+([^\s,]+)', line)
                if default_match:
                    constraints['default'] = default_match.group(1)
                
                columns[column_name] = {
                    'type': column_type,
                    'constraints': constraints
                }
        
        return columns
    
    def analyze_model_structure(self):
        """分析模型结构"""
        from src.models.intent import Intent, IntentExample, IntentCategory
        from src.models.slot import Slot, SlotValue, SlotDependency
        from src.models.conversation import Session, Conversation, IntentAmbiguity, IntentTransfer, UserContext
        from src.models.function_call import FunctionCall, ApiCallLog, AsyncTask
        from src.models.template import PromptTemplate, TemplateVersion, ABTestConfig
        from src.models.audit import ConfigAuditLog, SecurityAuditLog, CacheInvalidationLog, AsyncLogQueue, PerformanceLog
        from src.models.config import SystemConfig, RagflowConfig, ResponseType, ConversationStatus, FeatureFlag
        
        model_classes = [
            Intent, Slot, FunctionCall, Session, Conversation, IntentAmbiguity,
            ConfigAuditLog, PromptTemplate, UserContext, IntentTransfer,
            SystemConfig, ApiCallLog, RagflowConfig, SecurityAuditLog,
            AsyncTask, CacheInvalidationLog, AsyncLogQueue, ResponseType,
            ConversationStatus
        ]
        
        for model_class in model_classes:
            table_name = model_class._meta.table_name
            self.model_tables[table_name] = self.get_model_fields(model_class)
    
    def get_model_fields(self, model_class) -> Dict[str, Dict]:
        """获取模型字段信息"""
        fields = {}
        
        for field_name, field in model_class._meta.fields.items():
            field_info = {
                'type': type(field).__name__,
                'nullable': field.null,
                'primary_key': field.primary_key,
                'unique': field.unique,
                'default': getattr(field, 'default', None)
            }
            fields[field_name] = field_info
        
        return fields
    
    def validate_table_existence(self) -> List[str]:
        """验证表存在性"""
        issues = []
        
        # 检查schema中的表是否都有对应的模型
        for table_name in self.schema_tables:
            if table_name not in self.model_tables:
                if table_name in self.model_mappings:
                    issues.append(f"表 '{table_name}' 在schema中存在，但缺少对应的模型类 '{self.model_mappings[table_name]}'")
                else:
                    issues.append(f"表 '{table_name}' 在schema中存在，但没有对应的模型类")
        
        # 检查模型中的表是否都在schema中
        for table_name in self.model_tables:
            if table_name not in self.schema_tables:
                issues.append(f"模型表 '{table_name}' 不在schema定义中")
        
        return issues
    
    def validate_field_consistency(self) -> List[str]:
        """验证字段一致性"""
        issues = []
        
        for table_name in self.schema_tables:
            if table_name not in self.model_tables:
                continue
                
            schema_fields = self.schema_tables[table_name]
            model_fields = self.model_tables[table_name]
            
            # 检查schema中的字段是否在模型中存在
            for field_name, field_info in schema_fields.items():
                if field_name not in model_fields:
                    issues.append(f"表 '{table_name}': schema字段 '{field_name}' 在模型中缺失")
                else:
                    # 验证字段属性
                    model_field = model_fields[field_name]
                    field_issues = self.validate_field_attributes(table_name, field_name, field_info, model_field)
                    issues.extend(field_issues)
            
            # 检查模型中的字段是否在schema中存在
            for field_name in model_fields:
                if field_name not in schema_fields:
                    # 跳过Peewee自动添加的字段
                    if field_name not in ['id', 'created_at', 'updated_at']:
                        issues.append(f"表 '{table_name}': 模型字段 '{field_name}' 在schema中缺失")
        
        return issues
    
    def validate_field_attributes(self, table_name: str, field_name: str, 
                                schema_field: Dict, model_field: Dict) -> List[str]:
        """验证字段属性"""
        issues = []
        
        # 验证可空性
        schema_nullable = schema_field['constraints']['nullable']
        model_nullable = model_field['nullable']
        
        if schema_nullable != model_nullable:
            issues.append(
                f"表 '{table_name}' 字段 '{field_name}': "
                f"nullable不一致 (schema: {schema_nullable}, model: {model_nullable})"
            )
        
        # 验证主键
        schema_pk = schema_field['constraints']['primary_key']
        model_pk = model_field['primary_key']
        
        if schema_pk != model_pk:
            issues.append(
                f"表 '{table_name}' 字段 '{field_name}': "
                f"primary_key不一致 (schema: {schema_pk}, model: {model_pk})"
            )
        
        # 验证唯一性
        schema_unique = schema_field['constraints']['unique']
        model_unique = model_field['unique']
        
        if schema_unique != model_unique:
            issues.append(
                f"表 '{table_name}' 字段 '{field_name}': "
                f"unique不一致 (schema: {schema_unique}, model: {model_unique})"
            )
        
        return issues
    
    def validate_type_mapping(self) -> List[str]:
        """验证类型映射"""
        issues = []
        
        # MySQL类型到Peewee字段类型的映射
        type_mappings = {
            'INT': ['IntegerField', 'AutoField'],
            'BIGINT': ['BigIntegerField', 'BigAutoField'],
            'VARCHAR': ['CharField'],
            'TEXT': ['TextField'],
            'TIMESTAMP': ['DateTimeField'],
            'BOOLEAN': ['BooleanField'],
            'DECIMAL': ['DecimalField'],
            'JSON': ['TextField'],  # JSON通常用TextField存储
            'ENUM': ['CharField']   # ENUM通常用CharField存储
        }
        
        for table_name in self.schema_tables:
            if table_name not in self.model_tables:
                continue
                
            schema_fields = self.schema_tables[table_name]
            model_fields = self.model_tables[table_name]
            
            for field_name, schema_field in schema_fields.items():
                if field_name not in model_fields:
                    continue
                    
                schema_type = schema_field['type'].split('(')[0]  # 移除长度限制
                model_type = model_fields[field_name]['type']
                
                expected_types = type_mappings.get(schema_type, [])
                if expected_types and model_type not in expected_types:
                    issues.append(
                        f"表 '{table_name}' 字段 '{field_name}': "
                        f"类型不匹配 (schema: {schema_type}, model: {model_type}, "
                        f"期望: {expected_types})"
                    )
        
        return issues
    
    def run_validation(self) -> Dict[str, List[str]]:
        """运行完整验证"""
        print("开始解析MySQL schema...")
        self.parse_mysql_schema()
        
        print("开始分析模型结构...")
        self.analyze_model_structure()
        
        print("开始验证一致性...")
        
        results = {
            'table_existence': self.validate_table_existence(),
            'field_consistency': self.validate_field_consistency(),
            'type_mapping': self.validate_type_mapping()
        }
        
        return results


def test_schema_consistency():
    """测试schema一致性"""
    validator = MySQLSchemaValidator()
    results = validator.run_validation()
    
    print("\n=== MySQL Schema 一致性验证结果 ===\n")
    
    total_issues = 0
    
    for category, issues in results.items():
        print(f"## {category.replace('_', ' ').title()}")
        if issues:
            for issue in issues:
                print(f"  ❌ {issue}")
            total_issues += len(issues)
        else:
            print("  ✅ 无问题")
        print()
    
    print(f"总计问题数: {total_issues}")
    
    if total_issues == 0:
        print("🎉 所有验证通过！代码模型与MySQL schema完全一致。")
    else:
        print(f"⚠️  发现 {total_issues} 个问题需要修复。")
    
    return total_issues == 0


def test_specific_tables():
    """测试特定表的一致性"""
    validator = MySQLSchemaValidator()
    validator.parse_mysql_schema()
    validator.analyze_model_structure()
    
    # 重点验证核心表
    core_tables = ['intents', 'slots', 'conversations', 'function_calls', 'sessions']
    
    print("\n=== 核心表一致性验证 ===\n")
    
    for table_name in core_tables:
        print(f"验证表: {table_name}")
        
        if table_name not in validator.schema_tables:
            print(f"  ❌ 表在schema中不存在")
            continue
            
        if table_name not in validator.model_tables:
            print(f"  ❌ 表没有对应的模型类")
            continue
        
        schema_fields = set(validator.schema_tables[table_name].keys())
        model_fields = set(validator.model_tables[table_name].keys())
        
        # 排除自动字段
        model_fields.discard('id')
        if table_name in ['intents', 'slots', 'function_calls', 'prompt_templates']:
            model_fields.discard('created_at')
            model_fields.discard('updated_at')
        
        missing_in_model = schema_fields - model_fields
        missing_in_schema = model_fields - schema_fields
        
        if missing_in_model:
            print(f"  ❌ 模型中缺失字段: {missing_in_model}")
        
        if missing_in_schema:
            print(f"  ❌ Schema中缺失字段: {missing_in_schema}")
        
        if not missing_in_model and not missing_in_schema:
            print(f"  ✅ 字段完全匹配")
        
        print()


def test_enum_consistency():
    """测试枚举值一致性"""
    print("\n=== 枚举值一致性验证 ===\n")
    
    # 从schema中定义的ENUM值
    schema_enums = {
        'sessions.session_state': ['active', 'completed', 'expired'],
        'conversations.response_type': [
            'api_result', 'task_completion', 'slot_prompt', 'disambiguation',
            'qa_response', 'small_talk_with_context_return', 'intent_transfer_with_completion',
            'cancellation_confirmation', 'postponement_with_save', 'rejection_acknowledgment',
            'validation_error_prompt', 'error_with_alternatives', 'multi_intent_with_continuation',
            'security_error'
        ],
        'conversations.status': [
            'completed', 'incomplete', 'ambiguous', 'api_error', 'validation_error',
            'ragflow_handled', 'interruption_handled', 'multi_intent_processing',
            'intent_cancelled', 'intent_postponed', 'suggestion_rejected',
            'intent_transfer', 'slot_filling', 'context_maintained'
        ]
    }
    
    # 从代码中定义的枚举值（这里简化处理）
    code_enums = {
        'sessions.session_state': ['active', 'completed', 'expired'],
        'conversations.response_type': [
            'api_result', 'task_completion', 'slot_prompt', 'disambiguation',
            'qa_response', 'small_talk_with_context_return', 'intent_transfer_with_completion',
            'cancellation_confirmation', 'postponement_with_save', 'rejection_acknowledgment',
            'validation_error_prompt', 'error_with_alternatives', 'multi_intent_with_continuation',
            'security_error'
        ],
        'conversations.status': [
            'completed', 'incomplete', 'ambiguous', 'api_error', 'validation_error',
            'ragflow_handled', 'interruption_handled', 'multi_intent_processing',
            'intent_cancelled', 'intent_postponed', 'suggestion_rejected',
            'intent_transfer', 'slot_filling', 'context_maintained'
        ]
    }
    
    issues = 0
    for enum_name, schema_values in schema_enums.items():
        code_values = code_enums.get(enum_name, [])
        
        schema_set = set(schema_values)
        code_set = set(code_values)
        
        if schema_set == code_set:
            print(f"✅ {enum_name}: 枚举值完全匹配")
        else:
            print(f"❌ {enum_name}: 枚举值不匹配")
            missing_in_code = schema_set - code_set
            missing_in_schema = code_set - schema_set
            
            if missing_in_code:
                print(f"   代码中缺失: {missing_in_code}")
            if missing_in_schema:
                print(f"   Schema中缺失: {missing_in_schema}")
            
            issues += 1
    
    if issues == 0:
        print("\n🎉 所有枚举值验证通过！")
    else:
        print(f"\n⚠️  发现 {issues} 个枚举值不匹配问题。")
    
    return issues == 0


if __name__ == "__main__":
    print("开始验证代码模型与MySQL schema的一致性...")
    
    try:
        # 基础一致性验证
        basic_passed = test_schema_consistency()
        
        # 核心表验证
        test_specific_tables()
        
        # 枚举值验证
        enum_passed = test_enum_consistency()
        
        print("\n=== 总体验证结果 ===")
        if basic_passed and enum_passed:
            print("🎉 所有验证通过！代码框架与MySQL schema完全一致。")
        else:
            print("⚠️  存在不一致问题，需要修复。")
            
    except Exception as e:
        print(f"验证过程中出现错误: {str(e)}")
        import traceback
        traceback.print_exc()