#!/usr/bin/env python3
"""
应用字段标准化脚本
对系统中的关键文件应用字段命名标准化
"""
import sys
import shutil
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any

# 添加src路径
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))
sys.path.append(str(project_root / "src"))

try:
    from src.utils.field_name_standardizer import get_field_standardizer, create_field_mapping_report
    from src.utils.logger import get_logger
except ImportError as e:
    print(f"❌ 导入失败: {e}")
    print("请确保在项目根目录运行此脚本")
    sys.exit(1)

logger = get_logger(__name__)

# 需要标准化的文件列表
TARGET_FILES = [
    "src/schemas/chat.py",
    "src/schemas/api_response.py",
    "src/api/v1/chat.py",
    "src/api/v1/enhanced_chat.py",
    "src/utils/response_transformer.py",
    "docs/api_documentation.md"
]

def backup_files(files: List[str], backup_dir: str = None) -> str:
    """备份文件"""
    if backup_dir is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_dir = f"backups/field_standardization_{timestamp}"
    
    backup_path = project_root / backup_dir
    backup_path.mkdir(parents=True, exist_ok=True)
    
    print(f"📂 创建备份目录: {backup_path}")
    
    for file_path in files:
        source_file = project_root / file_path
        if source_file.exists():
            # 保持目录结构
            relative_path = Path(file_path)
            backup_file = backup_path / relative_path
            backup_file.parent.mkdir(parents=True, exist_ok=True)
            
            shutil.copy2(source_file, backup_file)
            print(f"  ✅ 备份: {file_path}")
        else:
            print(f"  ⚠️ 文件不存在: {file_path}")
    
    return backup_dir

def analyze_files(files: List[str]) -> Dict[str, List[Any]]:
    """分析文件中的命名问题"""
    print("🔍 分析文件中的命名问题...")
    
    standardizer = get_field_standardizer()
    all_issues = {}
    
    for file_path in files:
        full_path = project_root / file_path
        if not full_path.exists():
            continue
            
        try:
            with open(full_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            issues = standardizer.analyze_naming_issues(content, file_path)
            if issues:
                all_issues[file_path] = issues
                print(f"  📝 {file_path}: {len(issues)} 个问题")
                
                # 显示问题详情
                for issue in issues[:3]:  # 只显示前3个问题
                    severity_icon = "🔴" if issue.severity == "error" else "🟡"
                    print(f"    {severity_icon} {issue.field_name} -> {issue.suggestion} ({issue.issue_type})")
                
                if len(issues) > 3:
                    print(f"    ... 还有 {len(issues) - 3} 个问题")
            else:
                print(f"  ✅ {file_path}: 无问题")
                
        except Exception as e:
            print(f"  ❌ 分析失败 {file_path}: {str(e)}")
    
    return all_issues

def apply_standardization_to_files(files: List[str], dry_run: bool = False) -> Dict[str, List[str]]:
    """对文件应用标准化"""
    action = "预览" if dry_run else "应用"
    print(f"🔧 {action}字段标准化...")
    
    standardizer = get_field_standardizer()
    all_changes = {}
    
    for file_path in files:
        full_path = project_root / file_path
        if not full_path.exists():
            continue
            
        try:
            with open(full_path, 'r', encoding='utf-8') as f:
                original_content = f.read()
            
            # 根据文件类型选择适当的范围
            if file_path.endswith('.md'):
                scope = "api"  # 文档主要涉及API
            elif 'api/' in file_path:
                scope = "api"  # API文件
            else:
                scope = "all"  # 其他文件应用所有范围
            
            standardized_content, changes = standardizer.apply_standardization(
                original_content, scope=scope
            )
            
            if changes:
                all_changes[file_path] = changes
                print(f"  📝 {file_path}: {len(changes)} 个更改")
                
                for change in changes[:3]:  # 显示前3个更改
                    print(f"    🔄 {change}")
                
                if len(changes) > 3:
                    print(f"    ... 还有 {len(changes) - 3} 个更改")
                
                # 如果不是预览模式，写入文件
                if not dry_run:
                    with open(full_path, 'w', encoding='utf-8') as f:
                        f.write(standardized_content)
                    print(f"    ✅ 已更新文件")
            else:
                print(f"  ✅ {file_path}: 无需更改")
                
        except Exception as e:
            print(f"  ❌ 处理失败 {file_path}: {str(e)}")
    
    return all_changes

def create_standardization_report(issues: Dict[str, List[Any]], 
                                changes: Dict[str, List[str]], 
                                backup_dir: str) -> str:
    """创建标准化报告"""
    report_content = f"""# 字段命名标准化执行报告

**执行时间**: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
**备份目录**: {backup_dir}

## 概述

本次字段命名标准化处理了 {len(TARGET_FILES)} 个目标文件，发现并修复了字段命名不一致问题。

"""

    # 添加发现的问题统计
    total_issues = sum(len(file_issues) for file_issues in issues.values())
    if total_issues > 0:
        report_content += f"""## 发现的问题 ({total_issues} 个)

"""
        for file_path, file_issues in issues.items():
            report_content += f"""### {file_path}

"""
            for issue in file_issues:
                severity_icon = "🔴" if issue.severity == "error" else "🟡"
                report_content += f"- {severity_icon} **{issue.field_name}** → `{issue.suggestion}` ({issue.issue_type})\n"
            
            report_content += "\n"

    # 添加应用的更改统计
    total_changes = sum(len(file_changes) for file_changes in changes.values())
    if total_changes > 0:
        report_content += f"""## 应用的更改 ({total_changes} 个)

"""
        for file_path, file_changes in changes.items():
            report_content += f"""### {file_path}

"""
            for change in file_changes:
                report_content += f"- ✅ {change}\n"
            
            report_content += "\n"

    # 添加字段映射详情
    report_content += """## 字段映射详情

"""
    report_content += create_field_mapping_report()

    # 添加验证建议
    report_content += """
## 验证建议

### 1. 运行测试套件
```bash
# 运行所有测试
python -m pytest tests/

# 运行特定的响应格式测试
python scripts/test_response_transformer.py
python scripts/test_slot_data_consistency.py
```

### 2. 检查API文档一致性
```bash
# 检查API文档是否与代码保持一致
curl -X POST "http://localhost:8000/api/v1/chat/interact" \\
  -H "Content-Type: application/json" \\
  -d '{"user_id": "test", "input": "test"}'
```

### 3. 验证数据库兼容性
如果应用了数据库字段更改，请运行数据库迁移脚本。

## 回滚方案

如果需要回滚更改：

1. 从备份恢复文件：
```bash
cp -r {backup_dir}/* ./
```

2. 重启服务并验证功能

## 注意事项

- 所有更改都已备份到 `{backup_dir}` 目录
- 建议在生产环境部署前进行充分测试
- 如发现问题，请及时使用备份进行回滚
"""

    return report_content

def main():
    """主函数"""
    print("=" * 60)
    print("🚀 字段命名标准化执行脚本")
    print("=" * 60)
    
    # 询问是否执行预览
    if len(sys.argv) > 1 and sys.argv[1] == "--dry-run":
        dry_run = True
        print("📋 预览模式 - 不会修改任何文件")
    else:
        dry_run = False
        print("⚡ 执行模式 - 将修改文件")
        
        # 确认执行
        confirm = input("确认执行字段标准化？这将修改代码文件 (y/N): ")
        if confirm.lower() != 'y':
            print("❌ 取消执行")
            return 1
    
    try:
        # 1. 备份文件
        if not dry_run:
            backup_dir = backup_files(TARGET_FILES)
            print(f"✅ 文件备份完成: {backup_dir}")
        else:
            backup_dir = "预览模式-无备份"
        
        # 2. 分析文件
        print("\n" + "=" * 40)
        issues = analyze_files(TARGET_FILES)
        
        # 3. 应用标准化
        print("\n" + "=" * 40)
        changes = apply_standardization_to_files(TARGET_FILES, dry_run=dry_run)
        
        # 4. 生成报告
        print("\n" + "=" * 40)
        report_content = create_standardization_report(issues, changes, backup_dir)
        
        # 保存报告
        report_file = project_root / f"field_standardization_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
        with open(report_file, 'w', encoding='utf-8') as f:
            f.write(report_content)
        
        print(f"📄 标准化报告已生成: {report_file}")
        
        # 5. 总结
        total_issues = sum(len(file_issues) for file_issues in issues.values())
        total_changes = sum(len(file_changes) for file_changes in changes.values())
        
        print("\n" + "=" * 60)
        print("📊 执行总结:")
        print("=" * 60)
        print(f"📁 处理文件: {len(TARGET_FILES)} 个")
        print(f"🔍 发现问题: {total_issues} 个")
        print(f"🔧 应用更改: {total_changes} 个")
        
        if dry_run:
            print("📋 这是预览结果，使用不带 --dry-run 参数重新运行以实际执行更改")
        else:
            print(f"💾 备份位置: {backup_dir}")
            print("✅ 字段标准化执行完成!")
            
            # 建议运行测试
            print("\n🧪 建议运行以下测试验证更改:")
            print("  python scripts/test_response_transformer.py")
            print("  python scripts/test_slot_data_consistency.py")
        
        return 0
        
    except Exception as e:
        print(f"❌ 执行失败: {str(e)}")
        logger.error(f"字段标准化执行失败: {str(e)}")
        return 1

if __name__ == "__main__":
    sys.exit(main())