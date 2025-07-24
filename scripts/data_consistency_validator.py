#!/usr/bin/env python3
"""
数据一致性检查工具
验证数据库结构与Peewee模型的一致性
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import asyncio
import json
from typing import Dict, List, Any, Optional
from datetime import datetime
import mysql.connector
from mysql.connector import Error
from peewee import *
import inspect

# 导入所有模型
from src.models.conversation import *
from src.models.intent import *
from src.models.slot import *
from src.models.function import *
from src.models.audit import *
from src.models.cache import *
from src.models.async_log import *
from src.models.conversation_status import *
from src.models.entity import *
from src.models.extraction import *
from src.models.prompt_template import *
from src.models.response_type import *
from src.models.slot_value import *
from src.models.system_config import *
from src.config.settings import settings


class DataConsistencyValidator:
    """数据一致性验证器"""
    
    def __init__(self):
        self.db_connection = None
        self.validation_results = []
        self.models_to_check = self._get_all_models()
    
    def _get_all_models(self) -> Dict[str, Any]:
        """获取所有需要检查的模型"""
        models = {}
        
        # 从各个模块导入的模型
        model_modules = [
            'src.models.conversation',
            'src.models.intent',
            'src.models.slot', 
            'src.models.function',
            'src.models.audit',
            'src.models.cache',
            'src.models.async_log',
            'src.models.conversation_status',
            'src.models.entity',
            'src.models.extraction',
            'src.models.prompt_template',
            'src.models.response_type',
            'src.models.slot_value',
            'src.models.system_config'
        ]
        
        # 收集继承自Model的类
        import importlib
        for module_name in model_modules:
            try:
                module = importlib.import_module(module_name)
                for name, obj in inspect.getmembers(module):
                    if (inspect.isclass(obj) and 
                        issubclass(obj, Model) and 
                        obj != Model and
                        hasattr(obj, '_meta') and
                        hasattr(obj._meta, 'table_name') and
                        not getattr(obj._meta, 'abstract', False)):
                        models[obj._meta.table_name] = obj
            except ImportError as e:
                print(f"警告: 无法导入模块 {module_name}: {e}")
        
        return models
    
    async def connect_to_database(self):
        """连接到数据库"""
        try:
            self.db_connection = mysql.connector.connect(
                host=settings.DATABASE_HOST,
                port=settings.DATABASE_PORT,
                user=settings.DATABASE_USER,
                password=settings.DATABASE_PASSWORD,
                database=settings.DATABASE_NAME,
                charset='utf8mb4'
            )
            print(f"✅ 成功连接到数据库: {settings.DATABASE_NAME}")
        except Error as e:
            print(f"❌ 数据库连接失败: {e}")
            raise
    
    async def get_database_schema(self, table_name: str) -> Dict[str, Any]:
        """获取数据库表结构"""
        try:
            cursor = self.db_connection.cursor(dictionary=True)
            cursor.execute(f"DESCRIBE {table_name}")
            columns = cursor.fetchall()
            cursor.close()
            
            schema = {}
            for col in columns:
                schema[col['Field']] = {
                    'type': col['Type'],
                    'null': col['Null'] == 'YES',
                    'key': col['Key'],
                    'default': col['Default'],
                    'extra': col['Extra']
                }
            return schema
        except Error as e:
            return {'error': str(e)}
    
    def get_model_schema(self, model_class) -> Dict[str, Any]:
        """获取Peewee模型结构"""
        schema = {}
        
        for field_name, field_obj in model_class._meta.fields.items():
            field_info = {
                'type': type(field_obj).__name__,
                'null': field_obj.null,
                'primary_key': field_obj.primary_key,
                'unique': field_obj.unique,
                'default': getattr(field_obj, 'default', None)
            }
            
            # 特殊字段类型处理
            if hasattr(field_obj, 'max_length'):
                field_info['max_length'] = field_obj.max_length
            if hasattr(field_obj, 'choices'):
                field_info['choices'] = field_obj.choices
                
            schema[field_name] = field_info
        
        return schema
    
    def compare_field_types(self, db_type: str, model_type: str, field_info: Dict) -> List[str]:
        """比较数据库字段类型与模型字段类型"""
        issues = []
        
        # 类型映射关系
        type_mapping = {
            'CharField': ['varchar', 'char'],
            'TextField': ['text', 'longtext', 'mediumtext'],
            'IntegerField': ['int', 'integer'],
            'BigIntegerField': ['bigint'],
            'FloatField': ['float', 'double'],
            'BooleanField': ['tinyint(1)', 'boolean'],
            'DateTimeField': ['datetime', 'timestamp'],
            'DateField': ['date'],
            'TimeField': ['time'],
            'JSONField': ['json', 'longtext'],
            'ForeignKeyField': ['int', 'bigint', 'varchar']
        }
        
        db_type_lower = db_type.lower()
        expected_types = type_mapping.get(model_type, [])
        
        if expected_types:
            type_match = any(expected_type in db_type_lower for expected_type in expected_types)
            if not type_match:
                issues.append(f"类型不匹配: DB({db_type}) vs Model({model_type})")
        
        # 检查长度限制
        if model_type == 'CharField' and 'max_length' in field_info:
            expected_length = field_info['max_length']
            if f'varchar({expected_length})' not in db_type_lower:
                issues.append(f"长度不匹配: 期望varchar({expected_length}), 实际{db_type}")
        
        return issues
    
    async def validate_table(self, table_name: str, model_class) -> Dict[str, Any]:
        """验证单个表"""
        print(f"🔍 检查表: {table_name}")
        
        # 获取数据库和模型结构
        db_schema = await self.get_database_schema(table_name)
        if 'error' in db_schema:
            return {
                'table': table_name,
                'status': 'error',
                'error': f"无法获取表结构: {db_schema['error']}"
            }
        
        model_schema = self.get_model_schema(model_class)
        
        issues = []
        
        # 检查字段一致性
        model_fields = set(model_schema.keys())
        db_fields = set(db_schema.keys())
        
        # 缺失字段
        missing_in_db = model_fields - db_fields
        if missing_in_db:
            issues.append(f"数据库缺失字段: {', '.join(missing_in_db)}")
        
        # 额外字段
        extra_in_db = db_fields - model_fields
        if extra_in_db:
            issues.append(f"数据库额外字段: {', '.join(extra_in_db)}")
        
        # 字段类型检查
        common_fields = model_fields & db_fields
        for field_name in common_fields:
            db_field = db_schema[field_name]
            model_field = model_schema[field_name]
            
            # 类型比较
            type_issues = self.compare_field_types(
                db_field['type'], 
                model_field['type'], 
                model_field
            )
            if type_issues:
                issues.extend([f"{field_name}: {issue}" for issue in type_issues])
            
            # NULL约束检查
            if db_field['null'] != model_field['null']:
                issues.append(
                    f"{field_name}: NULL约束不匹配 - DB({db_field['null']}) vs Model({model_field['null']})"
                )
        
        return {
            'table': table_name,
            'model': model_class.__name__,
            'status': 'success' if not issues else 'warning',
            'issues': issues,
            'db_fields_count': len(db_fields),
            'model_fields_count': len(model_fields),
            'common_fields_count': len(common_fields)
        }
    
    async def validate_all(self) -> List[Dict[str, Any]]:
        """验证所有表"""
        print(f"🚀 开始数据一致性检查，共{len(self.models_to_check)}个表")
        print("=" * 60)
        
        results = []
        
        for table_name, model_class in self.models_to_check.items():
            try:
                result = await self.validate_table(table_name, model_class)
                results.append(result)
                
                # 实时显示结果
                if result['status'] == 'success':
                    print(f"✅ {table_name}: 无问题")
                elif result['status'] == 'warning':
                    print(f"⚠️  {table_name}: 发现{len(result['issues'])}个问题")
                    for issue in result['issues']:
                        print(f"   - {issue}")
                else:
                    print(f"❌ {table_name}: {result.get('error', '未知错误')}")
                
            except Exception as e:
                error_result = {
                    'table': table_name,
                    'model': model_class.__name__,
                    'status': 'error',
                    'error': str(e)
                }
                results.append(error_result)
                print(f"❌ {table_name}: 检查失败 - {e}")
        
        return results
    
    def generate_report(self, results: List[Dict[str, Any]]) -> str:
        """生成检查报告"""
        total_tables = len(results)
        success_count = len([r for r in results if r['status'] == 'success'])
        warning_count = len([r for r in results if r['status'] == 'warning'])
        error_count = len([r for r in results if r['status'] == 'error'])
        
        report = f"""
# 数据一致性检查报告
生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

## 📊 总体统计
- 总表数: {total_tables}
- ✅ 无问题: {success_count}
- ⚠️ 有警告: {warning_count}  
- ❌ 有错误: {error_count}

## 📋 详细结果

"""
        
        for result in results:
            report += f"### {result['table']} ({result.get('model', 'Unknown')})\n"
            report += f"状态: {result['status']}\n"
            
            if result['status'] == 'success':
                report += f"字段数: {result.get('common_fields_count', 0)}\n"
            elif result['status'] == 'warning':
                report += f"问题数: {len(result.get('issues', []))}\n"
                for issue in result.get('issues', []):
                    report += f"- {issue}\n"
            elif result['status'] == 'error':
                report += f"错误: {result.get('error', '未知错误')}\n"
            
            report += "\n"
        
        return report
    
    async def close_connection(self):
        """关闭数据库连接"""
        if self.db_connection:
            self.db_connection.close()
            print("🔒 数据库连接已关闭")


async def main():
    """主函数"""
    validator = DataConsistencyValidator()
    
    try:
        # 连接数据库
        await validator.connect_to_database()
        
        # 执行验证
        results = await validator.validate_all()
        
        # 生成报告
        report = validator.generate_report(results)
        
        # 保存报告
        report_file = f"reports/data_consistency_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
        os.makedirs('reports', exist_ok=True)
        
        with open(report_file, 'w', encoding='utf-8') as f:
            f.write(report)
        
        print("=" * 60)
        print(f"📄 报告已保存到: {report_file}")
        
        # 显示摘要
        print("\n📊 检查摘要:")
        total = len(results)
        success = len([r for r in results if r['status'] == 'success'])
        warning = len([r for r in results if r['status'] == 'warning'])
        error = len([r for r in results if r['status'] == 'error'])
        
        print(f"总计: {total} | 成功: {success} | 警告: {warning} | 错误: {error}")
        
        if warning > 0 or error > 0:
            print("⚠️ 发现数据一致性问题，请查看报告详情")
            return 1
        else:
            print("✅ 所有表结构一致性检查通过")
            return 0
            
    except Exception as e:
        print(f"❌ 检查过程中发生错误: {e}")
        return 1
    finally:
        await validator.close_connection()


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)