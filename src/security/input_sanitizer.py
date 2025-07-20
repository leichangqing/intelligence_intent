"""
输入净化和验证系统 (TASK-037)
提供全面的输入验证、净化和安全检查功能
"""
import re
import html
import urllib.parse
from typing import Any, Dict, List, Optional, Union, Pattern
from enum import Enum
import json
import base64
from dataclasses import dataclass

from ..utils.logger import get_logger

logger = get_logger(__name__)


class ThreatLevel(str, Enum):
    """威胁级别"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class AttackType(str, Enum):
    """攻击类型"""
    XSS = "xss"                    # 跨站脚本攻击
    SQL_INJECTION = "sql_injection" # SQL注入
    COMMAND_INJECTION = "command_injection"  # 命令注入
    PATH_TRAVERSAL = "path_traversal"        # 路径遍历
    XXSS = "xxss"                  # XML外部实体攻击
    LDAP_INJECTION = "ldap_injection"        # LDAP注入
    HEADER_INJECTION = "header_injection"    # HTTP头注入
    SCRIPT_INJECTION = "script_injection"    # 脚本注入
    HTML_INJECTION = "html_injection"        # HTML注入
    NOSQL_INJECTION = "nosql_injection"      # NoSQL注入


@dataclass
class SanitizationResult:
    """净化结果"""
    original_value: str
    sanitized_value: str
    is_safe: bool
    threats_detected: List[Dict[str, Any]]
    recommendations: List[str]
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'original_value': self.original_value,
            'sanitized_value': self.sanitized_value,
            'is_safe': self.is_safe,
            'threats_detected': self.threats_detected,
            'recommendations': self.recommendations
        }


class InputSanitizer:
    """输入净化器"""
    
    def __init__(self):
        # XSS攻击模式
        self.xss_patterns = [
            re.compile(r'<script[^>]*>.*?</script>', re.IGNORECASE | re.DOTALL),
            re.compile(r'javascript\s*:', re.IGNORECASE),
            re.compile(r'on\w+\s*=', re.IGNORECASE),
            re.compile(r'<iframe[^>]*>', re.IGNORECASE),
            re.compile(r'<object[^>]*>', re.IGNORECASE),
            re.compile(r'<embed[^>]*>', re.IGNORECASE),
            re.compile(r'<link[^>]*>', re.IGNORECASE),
            re.compile(r'<meta[^>]*>', re.IGNORECASE),
            re.compile(r'<style[^>]*>.*?</style>', re.IGNORECASE | re.DOTALL),
            re.compile(r'expression\s*\(', re.IGNORECASE),
            re.compile(r'vbscript\s*:', re.IGNORECASE),
            re.compile(r'data\s*:\s*text/html', re.IGNORECASE),
        ]
        
        # SQL注入模式
        self.sql_injection_patterns = [
            re.compile(r'\bunion\s+(all\s+)?select\b', re.IGNORECASE),
            re.compile(r'\bdrop\s+table\b', re.IGNORECASE),
            re.compile(r'\bdelete\s+from\b', re.IGNORECASE),
            re.compile(r'\bupdate\s+\w+\s+set\b', re.IGNORECASE),
            re.compile(r'\binsert\s+into\b', re.IGNORECASE),
            re.compile(r'\bexec\s*\(', re.IGNORECASE),
            re.compile(r'\bexecute\s*\(', re.IGNORECASE),
            re.compile(r';\s*(drop|delete|update|insert|create|alter)', re.IGNORECASE),
            re.compile(r"'.*?(?:or|and).*?'.*?=", re.IGNORECASE),
            re.compile(r'\bor\s+1\s*=\s*1\b', re.IGNORECASE),
            re.compile(r'\band\s+1\s*=\s*1\b', re.IGNORECASE),
            re.compile(r"'.*?union.*?select.*?'", re.IGNORECASE),
            re.compile(r'--.*$', re.MULTILINE),
            re.compile(r'/\*.*?\*/', re.DOTALL),
        ]
        
        # 命令注入模式
        self.command_injection_patterns = [
            re.compile(r'[;&|`]', re.IGNORECASE),
            re.compile(r'\$\(.*?\)', re.IGNORECASE),
            re.compile(r'`.*?`', re.IGNORECASE),
            re.compile(r'\|\s*\w+', re.IGNORECASE),
            re.compile(r'&&\s*\w+', re.IGNORECASE),
            re.compile(r';\s*\w+', re.IGNORECASE),
            re.compile(r'\beval\s*\(', re.IGNORECASE),
            re.compile(r'\bexec\s*\(', re.IGNORECASE),
            re.compile(r'\bsystem\s*\(', re.IGNORECASE),
            re.compile(r'\bshell_exec\s*\(', re.IGNORECASE),
        ]
        
        # 路径遍历模式
        self.path_traversal_patterns = [
            re.compile(r'\.\./', re.IGNORECASE),
            re.compile(r'\.\.\\', re.IGNORECASE),
            re.compile(r'%2e%2e%2f', re.IGNORECASE),
            re.compile(r'%2e%2e%5c', re.IGNORECASE),
            re.compile(r'%252e%252e%252f', re.IGNORECASE),
            re.compile(r'%c0%ae%c0%ae%c0%af', re.IGNORECASE),
        ]
        
        # LDAP注入模式
        self.ldap_injection_patterns = [
            re.compile(r'\*\)', re.IGNORECASE),
            re.compile(r'\(\|', re.IGNORECASE),
            re.compile(r'\)&', re.IGNORECASE),
            re.compile(r'\(\&', re.IGNORECASE),
            re.compile(r'\(\!\(', re.IGNORECASE),
        ]
        
        # NoSQL注入模式
        self.nosql_injection_patterns = [
            re.compile(r'\$where\s*:', re.IGNORECASE),
            re.compile(r'\$ne\s*:', re.IGNORECASE),
            re.compile(r'\$gt\s*:', re.IGNORECASE),
            re.compile(r'\$lt\s*:', re.IGNORECASE),
            re.compile(r'\$regex\s*:', re.IGNORECASE),
            re.compile(r'\$or\s*:', re.IGNORECASE),
            re.compile(r'\$and\s*:', re.IGNORECASE),
        ]
        
        # HTTP头注入模式
        self.header_injection_patterns = [
            re.compile(r'\r\n', re.IGNORECASE),
            re.compile(r'\n', re.IGNORECASE),
            re.compile(r'\r', re.IGNORECASE),
            re.compile(r'%0d%0a', re.IGNORECASE),
            re.compile(r'%0a', re.IGNORECASE),
            re.compile(r'%0d', re.IGNORECASE),
        ]
        
        # 危险的HTML标签
        self.dangerous_html_tags = [
            'script', 'iframe', 'object', 'embed', 'link', 'meta', 'style',
            'form', 'input', 'button', 'textarea', 'select', 'option'
        ]
        
        # 允许的HTML标签（白名单）
        self.allowed_html_tags = [
            'p', 'br', 'strong', 'em', 'u', 'i', 'b', 'span', 'div',
            'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'ul', 'ol', 'li'
        ]
        
        # 最大输入长度限制
        self.max_input_lengths = {
            'text': 10000,
            'url': 2048,
            'email': 254,
            'filename': 255,
            'username': 50,
            'password': 128
        }
    
    def sanitize_input(
        self,
        value: Any,
        input_type: str = 'text',
        allow_html: bool = False,
        max_length: Optional[int] = None
    ) -> SanitizationResult:
        """
        综合输入净化
        
        Args:
            value: 输入值
            input_type: 输入类型 (text, url, email, filename, etc.)
            allow_html: 是否允许HTML标签
            max_length: 最大长度限制
            
        Returns:
            SanitizationResult: 净化结果
        """
        if value is None:
            return SanitizationResult(
                original_value="",
                sanitized_value="",
                is_safe=True,
                threats_detected=[],
                recommendations=[]
            )
        
        original_value = str(value)
        sanitized_value = original_value
        threats_detected = []
        recommendations = []
        
        try:
            # 1. 长度检查
            max_len = max_length or self.max_input_lengths.get(input_type, 10000)
            if len(original_value) > max_len:
                sanitized_value = sanitized_value[:max_len]
                recommendations.append(f"输入长度超过限制({max_len})，已截断")
            
            # 2. 检测和移除各种攻击模式
            threats_detected.extend(self._detect_xss(sanitized_value))
            threats_detected.extend(self._detect_sql_injection(sanitized_value))
            threats_detected.extend(self._detect_command_injection(sanitized_value))
            threats_detected.extend(self._detect_path_traversal(sanitized_value))
            threats_detected.extend(self._detect_ldap_injection(sanitized_value))
            threats_detected.extend(self._detect_nosql_injection(sanitized_value))
            threats_detected.extend(self._detect_header_injection(sanitized_value))
            
            # 3. 基础净化
            sanitized_value = self._basic_sanitization(sanitized_value)
            
            # 4. HTML处理
            if allow_html:
                sanitized_value = self._sanitize_html(sanitized_value)
            else:
                sanitized_value = self._escape_html(sanitized_value)
            
            # 5. 特定类型处理
            if input_type == 'url':
                sanitized_value = self._sanitize_url(sanitized_value)
            elif input_type == 'email':
                sanitized_value = self._sanitize_email(sanitized_value)
            elif input_type == 'filename':
                sanitized_value = self._sanitize_filename(sanitized_value)
            
            # 6. 最终安全检查
            is_safe = len(threats_detected) == 0
            
            # 7. 生成推荐
            if threats_detected:
                threat_types = set(threat['type'] for threat in threats_detected)
                if AttackType.XSS in threat_types:
                    recommendations.append("检测到XSS攻击模式，请使用安全的HTML编码")
                if AttackType.SQL_INJECTION in threat_types:
                    recommendations.append("检测到SQL注入模式，请使用参数化查询")
                if AttackType.COMMAND_INJECTION in threat_types:
                    recommendations.append("检测到命令注入模式，请验证输入参数")
            
            logger.debug(f"输入净化完成: safe={is_safe}, threats={len(threats_detected)}")
            
            return SanitizationResult(
                original_value=original_value,
                sanitized_value=sanitized_value,
                is_safe=is_safe,
                threats_detected=threats_detected,
                recommendations=recommendations
            )
            
        except Exception as e:
            logger.error(f"输入净化失败: {str(e)}")
            return SanitizationResult(
                original_value=original_value,
                sanitized_value="",
                is_safe=False,
                threats_detected=[{
                    'type': 'processing_error',
                    'level': ThreatLevel.HIGH,
                    'pattern': str(e),
                    'position': 0
                }],
                recommendations=["输入处理异常，请检查输入格式"]
            )
    
    def _detect_xss(self, value: str) -> List[Dict[str, Any]]:
        """检测XSS攻击"""
        threats = []
        
        for pattern in self.xss_patterns:
            matches = pattern.finditer(value)
            for match in matches:
                threats.append({
                    'type': AttackType.XSS,
                    'level': ThreatLevel.HIGH,
                    'pattern': match.group(),
                    'position': match.start(),
                    'description': 'Potential XSS attack detected'
                })
        
        return threats
    
    def _detect_sql_injection(self, value: str) -> List[Dict[str, Any]]:
        """检测SQL注入"""
        threats = []
        
        for pattern in self.sql_injection_patterns:
            matches = pattern.finditer(value)
            for match in matches:
                threats.append({
                    'type': AttackType.SQL_INJECTION,
                    'level': ThreatLevel.CRITICAL,
                    'pattern': match.group(),
                    'position': match.start(),
                    'description': 'Potential SQL injection detected'
                })
        
        return threats
    
    def _detect_command_injection(self, value: str) -> List[Dict[str, Any]]:
        """检测命令注入"""
        threats = []
        
        for pattern in self.command_injection_patterns:
            matches = pattern.finditer(value)
            for match in matches:
                threats.append({
                    'type': AttackType.COMMAND_INJECTION,
                    'level': ThreatLevel.CRITICAL,
                    'pattern': match.group(),
                    'position': match.start(),
                    'description': 'Potential command injection detected'
                })
        
        return threats
    
    def _detect_path_traversal(self, value: str) -> List[Dict[str, Any]]:
        """检测路径遍历攻击"""
        threats = []
        
        for pattern in self.path_traversal_patterns:
            matches = pattern.finditer(value)
            for match in matches:
                threats.append({
                    'type': AttackType.PATH_TRAVERSAL,
                    'level': ThreatLevel.HIGH,
                    'pattern': match.group(),
                    'position': match.start(),
                    'description': 'Potential path traversal attack detected'
                })
        
        return threats
    
    def _detect_ldap_injection(self, value: str) -> List[Dict[str, Any]]:
        """检测LDAP注入"""
        threats = []
        
        for pattern in self.ldap_injection_patterns:
            matches = pattern.finditer(value)
            for match in matches:
                threats.append({
                    'type': AttackType.LDAP_INJECTION,
                    'level': ThreatLevel.MEDIUM,
                    'pattern': match.group(),
                    'position': match.start(),
                    'description': 'Potential LDAP injection detected'
                })
        
        return threats
    
    def _detect_nosql_injection(self, value: str) -> List[Dict[str, Any]]:
        """检测NoSQL注入"""
        threats = []
        
        for pattern in self.nosql_injection_patterns:
            matches = pattern.finditer(value)
            for match in matches:
                threats.append({
                    'type': AttackType.NOSQL_INJECTION,
                    'level': ThreatLevel.HIGH,
                    'pattern': match.group(),
                    'position': match.start(),
                    'description': 'Potential NoSQL injection detected'
                })
        
        return threats
    
    def _detect_header_injection(self, value: str) -> List[Dict[str, Any]]:
        """检测HTTP头注入"""
        threats = []
        
        for pattern in self.header_injection_patterns:
            matches = pattern.finditer(value)
            for match in matches:
                threats.append({
                    'type': AttackType.HEADER_INJECTION,
                    'level': ThreatLevel.MEDIUM,
                    'pattern': repr(match.group()),
                    'position': match.start(),
                    'description': 'Potential HTTP header injection detected'
                })
        
        return threats
    
    def _basic_sanitization(self, value: str) -> str:
        """基础净化"""
        # 移除控制字符
        value = re.sub(r'[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]', '', value)
        
        # 移除多余的空白字符
        value = re.sub(r'\s+', ' ', value).strip()
        
        # URL解码（防止双重编码绕过）
        try:
            decoded = urllib.parse.unquote(value)
            if decoded != value:
                # 递归解码
                value = self._basic_sanitization(decoded)
        except:
            pass
        
        return value
    
    def _sanitize_html(self, value: str) -> str:
        """净化HTML（白名单方式）"""
        # 移除危险标签
        for tag in self.dangerous_html_tags:
            value = re.sub(f'<{tag}[^>]*>.*?</{tag}>', '', value, flags=re.IGNORECASE | re.DOTALL)
            value = re.sub(f'<{tag}[^>]*/?>', '', value, flags=re.IGNORECASE)
        
        # 移除危险属性
        value = re.sub(r'\son\w+\s*=\s*["\'][^"\']*["\']', '', value, flags=re.IGNORECASE)
        value = re.sub(r'\sjavascript\s*:', '', value, flags=re.IGNORECASE)
        
        return value
    
    def _escape_html(self, value: str) -> str:
        """HTML转义"""
        return html.escape(value, quote=True)
    
    def _sanitize_url(self, value: str) -> str:
        """净化URL"""
        # 检查协议
        if not re.match(r'^https?://', value, re.IGNORECASE):
            if not value.startswith('//'):
                value = '//' + value
        
        # 移除危险协议
        dangerous_protocols = ['javascript:', 'vbscript:', 'data:', 'file:']
        for protocol in dangerous_protocols:
            if value.lower().startswith(protocol):
                value = value[len(protocol):]
        
        return value
    
    def _sanitize_email(self, value: str) -> str:
        """净化邮箱地址"""
        # 简单的邮箱格式验证和净化
        email_pattern = re.compile(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$')
        if not email_pattern.match(value):
            return ""
        
        return value.lower().strip()
    
    def _sanitize_filename(self, value: str) -> str:
        """净化文件名"""
        # 移除路径分隔符和危险字符
        value = re.sub(r'[<>:"/\\|?*]', '', value)
        value = re.sub(r'^\.+', '', value)  # 移除开头的点
        
        # 限制文件名长度
        if len(value) > 255:
            name, ext = os.path.splitext(value)
            if ext:
                max_name_len = 255 - len(ext)
                value = name[:max_name_len] + ext
            else:
                value = value[:255]
        
        return value
    
    def validate_json(self, value: str, max_depth: int = 10) -> tuple[bool, Optional[dict]]:
        """验证和净化JSON"""
        try:
            # 检查JSON深度（防止深度嵌套攻击）
            def check_depth(obj, depth=0):
                if depth > max_depth:
                    raise ValueError("JSON depth exceeds limit")
                
                if isinstance(obj, dict):
                    for v in obj.values():
                        check_depth(v, depth + 1)
                elif isinstance(obj, list):
                    for item in obj:
                        check_depth(item, depth + 1)
            
            # 解析JSON
            parsed = json.loads(value)
            
            # 检查深度
            check_depth(parsed)
            
            return True, parsed
            
        except (json.JSONDecodeError, ValueError) as e:
            logger.warning(f"JSON验证失败: {str(e)}")
            return False, None


# 全局输入净化器实例
global_input_sanitizer = InputSanitizer()