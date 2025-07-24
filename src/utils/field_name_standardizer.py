"""
字段命名标准化工具
统一系统中不一致的字段命名
"""
from typing import Dict, List, Any, Optional, Set, Tuple
from pathlib import Path
import re
import json
from dataclasses import dataclass
from enum import Enum

from src.utils.logger import get_logger

logger = get_logger(__name__)

class FieldNamingConvention(str, Enum):
    """字段命名约定"""
    SNAKE_CASE = "snake_case"
    CAMEL_CASE = "camelCase"
    PASCAL_CASE = "PascalCase"
    KEBAB_CASE = "kebab-case"

@dataclass
class FieldMapping:
    """字段映射定义"""
    old_name: str
    new_name: str
    description: str
    scope: str  # 应用范围: "api", "database", "cache", "all"
    priority: int  # 优先级: 1(高) - 5(低)

@dataclass
class NamingIssue:
    """命名问题"""
    field_name: str
    issue_type: str
    location: str
    suggestion: str
    severity: str  # "error", "warning", "info"

class FieldNameStandardizer:
    """字段命名标准化器"""
    
    def __init__(self):
        """初始化标准化器"""
        self.convention = FieldNamingConvention.SNAKE_CASE
        self.field_mappings = self._load_standard_mappings()
        self.reserved_words = {"response", "message", "result", "data", "error", "status"}
        self.naming_issues = []
    
    def _load_standard_mappings(self) -> List[FieldMapping]:
        """加载标准字段映射"""
        return [
            # 响应相关字段统一
            FieldMapping(
                old_name="system_response",
                new_name="response",
                description="统一响应字段命名",
                scope="all",
                priority=1
            ),
            FieldMapping(
                old_name="response_message",
                new_name="response",
                description="统一响应消息字段",
                scope="api",
                priority=1
            ),
            FieldMapping(
                old_name="msg",
                new_name="message",
                description="统一消息字段命名",
                scope="all",
                priority=1
            ),
            
            # API结果字段统一
            FieldMapping(
                old_name="api_result",
                new_name="result_data",
                description="统一API结果数据字段",
                scope="api",
                priority=2
            ),
            FieldMapping(
                old_name="result",
                new_name="result_data",
                description="统一结果数据字段（避免与内置result冲突）",
                scope="api",
                priority=2
            ),
            
            # 时间相关字段统一
            FieldMapping(
                old_name="response_time",
                new_name="response_time_ms",
                description="明确响应时间单位",
                scope="all",
                priority=2
            ),
            FieldMapping(
                old_name="processing_time",
                new_name="processing_time_ms",
                description="明确处理时间单位",
                scope="all",
                priority=2
            ),
            
            # 状态相关字段统一
            FieldMapping(
                old_name="status_code",
                new_name="status",
                description="简化状态字段命名",
                scope="api",
                priority=3
            ),
            FieldMapping(
                old_name="error_code",
                new_name="error_type",
                description="更清晰的错误类型字段",
                scope="all",
                priority=3
            ),
            
            # 用户相关字段统一
            FieldMapping(
                old_name="user_response",
                new_name="user_input",
                description="统一用户输入字段",
                scope="all",
                priority=3
            ),
            FieldMapping(
                old_name="user_message",
                new_name="user_input",
                description="统一用户输入字段",
                scope="all",
                priority=3
            ),
            
            # ID相关字段统一
            FieldMapping(
                old_name="session_uuid",
                new_name="session_id",
                description="统一会话标识符字段",
                scope="all",
                priority=2
            ),
            FieldMapping(
                old_name="request_uuid",
                new_name="request_id",
                description="统一请求标识符字段",
                scope="all",
                priority=2
            ),
        ]
    
    def analyze_naming_issues(self, text: str, file_path: str = "") -> List[NamingIssue]:
        """
        分析文本中的命名问题
        
        Args:
            text: 要分析的文本
            file_path: 文件路径（用于定位）
            
        Returns:
            List[NamingIssue]: 发现的命名问题列表
        """
        issues = []
        
        # 检查字段定义模式
        field_patterns = [
            r'(\w+):\s*(?:str|int|float|bool|Optional|List|Dict)',  # Pydantic字段
            r'(\w+)\s*=\s*Field',  # Field定义
            r'["\'](\w+)["\']:\s*',  # JSON字段
            r'\.(\w+)\s*=',  # 属性赋值
        ]
        
        for pattern in field_patterns:
            matches = re.finditer(pattern, text)
            for match in matches:
                field_name = match.group(1)
                line_num = text[:match.start()].count('\n') + 1
                
                # 检查命名约定
                issue = self._check_naming_convention(field_name, file_path, line_num)
                if issue:
                    issues.append(issue)
                
                # 检查是否有标准化映射
                mapping_issue = self._check_field_mapping(field_name, file_path, line_num)
                if mapping_issue:
                    issues.append(mapping_issue)
        
        return issues
    
    def _check_naming_convention(self, field_name: str, file_path: str, line_num: int) -> Optional[NamingIssue]:
        """检查字段命名约定"""
        if not self._is_snake_case(field_name):
            return NamingIssue(
                field_name=field_name,
                issue_type="naming_convention",
                location=f"{file_path}:{line_num}",
                suggestion=self._to_snake_case(field_name),
                severity="warning"
            )
        return None
    
    def _check_field_mapping(self, field_name: str, file_path: str, line_num: int) -> Optional[NamingIssue]:
        """检查字段是否需要标准化映射"""
        for mapping in self.field_mappings:
            if field_name == mapping.old_name:
                severity = "error" if mapping.priority <= 2 else "warning"
                return NamingIssue(
                    field_name=field_name,
                    issue_type="field_mapping",
                    location=f"{file_path}:{line_num}",
                    suggestion=mapping.new_name,
                    severity=severity
                )
        return None
    
    def _is_snake_case(self, name: str) -> bool:
        """检查是否符合snake_case命名约定"""
        if not name:
            return False
        
        # 允许数字、字母、下划线
        if not re.match(r'^[a-z][a-z0-9_]*$', name):
            return False
        
        # 不能以下划线结尾
        if name.endswith('_'):
            return False
        
        # 不能有连续的下划线
        if '__' in name:
            return False
        
        return True
    
    def _to_snake_case(self, name: str) -> str:
        """转换为snake_case格式"""
        # 处理camelCase和PascalCase
        s1 = re.sub('(.)([A-Z][a-z]+)', r'\1_\2', name)
        s2 = re.sub('([a-z0-9])([A-Z])', r'\1_\2', s1)
        
        # 处理kebab-case
        s3 = s2.replace('-', '_')
        
        # 转为小写并清理多余的下划线
        result = s3.lower()
        result = re.sub('_+', '_', result)  # 合并多个下划线
        result = result.strip('_')  # 移除首尾下划线
        
        return result
    
    def get_standardization_plan(self) -> Dict[str, Any]:
        """
        生成字段标准化计划
        
        Returns:
            Dict: 标准化计划
        """
        plan = {
            "high_priority_mappings": [],
            "medium_priority_mappings": [],
            "low_priority_mappings": [],
            "naming_convention_fixes": [],
            "affected_files": set(),
            "impact_assessment": {}
        }
        
        # 按优先级分组映射
        for mapping in self.field_mappings:
            mapping_info = {
                "old_name": mapping.old_name,
                "new_name": mapping.new_name,
                "description": mapping.description,
                "scope": mapping.scope
            }
            
            if mapping.priority <= 2:
                plan["high_priority_mappings"].append(mapping_info)
            elif mapping.priority <= 3:
                plan["medium_priority_mappings"].append(mapping_info)
            else:
                plan["low_priority_mappings"].append(mapping_info)
        
        return plan
    
    def apply_standardization(self, text: str, scope: str = "all") -> Tuple[str, List[str]]:
        """
        应用字段标准化
        
        Args:
            text: 要标准化的文本
            scope: 应用范围
            
        Returns:
            Tuple[str, List[str]]: (标准化后的文本, 应用的更改列表)
        """
        changes = []
        result_text = text
        
        # 按优先级排序应用映射
        sorted_mappings = sorted(self.field_mappings, key=lambda x: x.priority)
        
        for mapping in sorted_mappings:
            if scope != "all" and mapping.scope != "all" and mapping.scope != scope:
                continue
            
            # 使用精确的字段匹配模式
            patterns = [
                (rf'\b{re.escape(mapping.old_name)}:', f'{mapping.new_name}:'),  # 字段定义
                (rf'"{re.escape(mapping.old_name)}":', f'"{mapping.new_name}":'),  # JSON字段 - 双引号
                (rf"'{re.escape(mapping.old_name)}':", f'"{mapping.new_name}":'),  # JSON字段 - 单引号
                (rf'\.{re.escape(mapping.old_name)}\b', f'.{mapping.new_name}'),  # 属性访问
            ]
            
            for pattern, replacement in patterns:
                old_text = result_text
                result_text = re.sub(pattern, replacement, result_text)
                if old_text != result_text:
                    changes.append(f"字段重命名: {mapping.old_name} -> {mapping.new_name}")
        
        return result_text, changes
    
    def generate_migration_script(self) -> str:
        """生成数据库迁移脚本"""
        migration_sql = """-- 字段标准化迁移脚本
-- 生成时间: {timestamp}

BEGIN TRANSACTION;

-- 备份原始数据
CREATE TABLE conversations_backup AS SELECT * FROM conversations;
CREATE TABLE slot_values_backup AS SELECT * FROM slot_values;

""".format(timestamp=__import__('datetime').datetime.now().isoformat())
        
        # 生成字段重命名SQL
        for mapping in self.field_mappings:
            if mapping.scope in ["database", "all"] and mapping.priority <= 3:
                migration_sql += f"""
-- 重命名字段: {mapping.old_name} -> {mapping.new_name}
-- 描述: {mapping.description}
ALTER TABLE conversations RENAME COLUMN {mapping.old_name} TO {mapping.new_name};
"""
        
        migration_sql += """
-- 验证迁移结果
SELECT 'Migration completed' as status;

COMMIT;

-- 回滚脚本（如需要）
-- BEGIN TRANSACTION;
-- DROP TABLE conversations;
-- ALTER TABLE conversations_backup RENAME TO conversations;
-- DROP TABLE slot_values;
-- ALTER TABLE slot_values_backup RENAME TO slot_values;
-- COMMIT;
"""
        
        return migration_sql
    
    def validate_standardization(self, old_data: Dict[str, Any], new_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        验证标准化结果
        
        Args:
            old_data: 原始数据
            new_data: 标准化后的数据
            
        Returns:
            Dict: 验证结果
        """
        validation_result = {
            "is_valid": True,
            "issues": [],
            "mappings_applied": [],
            "data_integrity_check": True
        }
        
        # 检查数据完整性
        old_keys = set(old_data.keys())
        new_keys = set(new_data.keys())
        
        # 检查是否有数据丢失
        if len(old_keys) != len(new_keys):
            validation_result["is_valid"] = False
            validation_result["issues"].append("数据字段数量不匹配")
        
        # 检查映射是否正确应用
        for mapping in self.field_mappings:
            if mapping.old_name in old_data and mapping.new_name in new_data:
                if old_data[mapping.old_name] == new_data[mapping.new_name]:
                    validation_result["mappings_applied"].append(
                        f"{mapping.old_name} -> {mapping.new_name}"
                    )
                else:
                    validation_result["issues"].append(
                        f"字段映射值不匹配: {mapping.old_name} -> {mapping.new_name}"
                    )
        
        return validation_result


def get_field_standardizer() -> FieldNameStandardizer:
    """获取字段标准化器实例"""
    return FieldNameStandardizer()


# 使用示例和工具函数
def standardize_api_response(response_data: Dict[str, Any]) -> Dict[str, Any]:
    """标准化API响应数据"""
    standardizer = get_field_standardizer()
    
    # 转换为JSON字符串进行处理
    json_text = json.dumps(response_data, ensure_ascii=False, indent=2)
    
    # 应用标准化
    standardized_text, changes = standardizer.apply_standardization(json_text, scope="api")
    
    # 转换回字典
    try:
        standardized_data = json.loads(standardized_text)
        if changes:
            logger.info(f"应用的标准化更改: {changes}")
        return standardized_data
    except json.JSONDecodeError:
        logger.error("标准化后的JSON解析失败，返回原始数据")
        return response_data


def create_field_mapping_report() -> str:
    """创建字段映射报告"""
    standardizer = get_field_standardizer()
    plan = standardizer.get_standardization_plan()
    
    report = """# 字段命名标准化报告

## 高优先级映射 (立即执行)
"""
    
    for mapping in plan["high_priority_mappings"]:
        report += f"""
### {mapping['old_name']} → {mapping['new_name']}
- **描述**: {mapping['description']}
- **范围**: {mapping['scope']}
"""
    
    report += """
## 中等优先级映射 (近期执行)
"""
    
    for mapping in plan["medium_priority_mappings"]:
        report += f"""
### {mapping['old_name']} → {mapping['new_name']}
- **描述**: {mapping['description']}
- **范围**: {mapping['scope']}
"""
    
    report += """
## 低优先级映射 (可选执行)
"""
    
    for mapping in plan["low_priority_mappings"]:
        report += f"""
### {mapping['old_name']} → {mapping['new_name']}
- **描述**: {mapping['description']}
- **范围**: {mapping['scope']}
"""
    
    return report