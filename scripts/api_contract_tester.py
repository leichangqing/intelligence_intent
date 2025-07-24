#!/usr/bin/env python3
"""
API契约测试工具
验证API响应格式的一致性，确保所有接口都遵循标准化格式
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import asyncio
import json
import httpx
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime
from pydantic import BaseModel, ValidationError
import inspect
from pathlib import Path

# 导入API相关模块
from src.schemas.chat import ChatRequest, ChatResponse
from src.schemas.common import StandardResponse, ErrorResponse, HealthCheckResponse
from src.api.v1 import chat, health, admin, tasks, analytics
from src.config.settings import settings


class APIEndpoint(BaseModel):
    """API端点信息"""
    path: str
    method: str
    name: str
    request_model: Optional[str] = None
    response_model: Optional[str] = None
    status_codes: List[int] = [200]
    description: Optional[str] = None


class ContractTestResult(BaseModel):
    """契约测试结果"""
    endpoint: str
    method: str
    status: str  # pass, fail, error
    issues: List[str] = []
    response_time_ms: Optional[float] = None
    status_code: Optional[int] = None
    response_data: Optional[Dict[str, Any]] = None
    expected_schema: Optional[str] = None
    actual_schema: Optional[Dict[str, Any]] = None


class APIContractTester:
    """API契约测试器"""
    
    def __init__(self, base_url: str = None):
        self.base_url = base_url or f"http://localhost:{getattr(settings, 'SERVER_PORT', 8000)}"
        self.test_results: List[ContractTestResult] = []
        self.endpoints = self._discover_endpoints()
        
    def _discover_endpoints(self) -> List[APIEndpoint]:
        """自动发现API端点"""
        endpoints = []
        
        # 预定义的API端点配置
        predefined_endpoints = [
            APIEndpoint(
                path="/api/v1/chat/interact",
                method="POST",
                name="chat_interact",
                request_model="ChatRequest",
                response_model="StandardResponse[ChatResponse]",
                status_codes=[200, 400, 422, 500],
                description="智能对话处理接口"
            ),
            APIEndpoint(
                path="/api/v1/health",
                method="GET", 
                name="health_check",
                response_model="HealthCheckResponse",
                status_codes=[200],
                description="健康检查接口"
            ),
            APIEndpoint(
                path="/api/v1/admin/intents",
                method="GET",
                name="list_intents",
                response_model="StandardResponse[List[Intent]]",
                status_codes=[200, 401, 403],
                description="获取意图列表"
            ),
            APIEndpoint(
                path="/api/v1/admin/intents",
                method="POST",
                name="create_intent",
                request_model="IntentCreateRequest",
                response_model="StandardResponse[Intent]", 
                status_codes=[201, 400, 401, 403, 422],
                description="创建新意图"
            ),
            APIEndpoint(
                path="/api/v1/tasks/function-calls",
                method="GET",
                name="list_function_calls",
                response_model="StandardResponse[List[FunctionCall]]",
                status_codes=[200, 401, 403],
                description="获取函数调用列表"
            ),
            APIEndpoint(
                path="/api/v1/analytics/conversations",
                method="GET",
                name="conversation_analytics",
                response_model="StandardResponse[ConversationAnalytics]",
                status_codes=[200, 401, 403],
                description="对话分析数据"
            ),
        ]
        
        endpoints.extend(predefined_endpoints)
        return endpoints
    
    async def test_endpoint(self, endpoint: APIEndpoint) -> ContractTestResult:
        """测试单个端点"""
        print(f"🔍 测试端点: {endpoint.method} {endpoint.path}")
        
        start_time = asyncio.get_event_loop().time()
        result = ContractTestResult(
            endpoint=endpoint.path,
            method=endpoint.method,
            status="error",
            expected_schema=endpoint.response_model
        )
        
        try:
            # 构建测试请求
            request_data = self._build_test_request(endpoint)
            
            async with httpx.AsyncClient(timeout=30.0) as client:
                url = f"{self.base_url}{endpoint.path}"
                
                if endpoint.method.upper() == "GET":
                    response = await client.get(url, params=request_data)
                elif endpoint.method.upper() == "POST":
                    response = await client.post(url, json=request_data)
                elif endpoint.method.upper() == "PUT":
                    response = await client.put(url, json=request_data)
                elif endpoint.method.upper() == "DELETE":
                    response = await client.delete(url)
                else:
                    result.issues.append(f"不支持的HTTP方法: {endpoint.method}")
                    return result
                
                end_time = asyncio.get_event_loop().time()
                result.response_time_ms = (end_time - start_time) * 1000
                result.status_code = response.status_code
                
                # 检查状态码
                if response.status_code not in endpoint.status_codes:
                    result.issues.append(
                        f"意外的状态码: {response.status_code}, 期望: {endpoint.status_codes}"
                    )
                
                # 解析响应体
                try:
                    response_data = response.json()
                    result.response_data = response_data
                    result.actual_schema = self._analyze_response_schema(response_data)
                except json.JSONDecodeError:
                    result.issues.append("响应体不是有效的JSON格式")
                    return result
                
                # 验证响应格式
                validation_issues = self._validate_response_format(
                    response_data, endpoint, response.status_code
                )
                result.issues.extend(validation_issues)
                
                # 设置最终状态
                result.status = "pass" if not result.issues else "fail"
                
        except httpx.TimeoutException:
            result.issues.append("请求超时")
        except httpx.ConnectError:
            result.issues.append(f"无法连接到服务器: {self.base_url}")
        except Exception as e:
            result.issues.append(f"测试执行失败: {str(e)}")
        
        return result
    
    def _build_test_request(self, endpoint: APIEndpoint) -> Dict[str, Any]:
        """构建测试请求数据"""
        if endpoint.name == "chat_interact":
            return {
                "user_id": "test_user_123",
                "input": "你好，我想查询航班信息",
                "session_id": "test_session_001",
                "context": {
                    "device_info": {
                        "platform": "web",
                        "language": "zh-CN"
                    },
                    "client_system_id": "test_client",
                    "request_trace_id": "trace_123456"
                }
            }
        elif endpoint.name == "create_intent":
            return {
                "intent_name": "test_intent",
                "display_name": "测试意图",
                "description": "API契约测试用意图",
                "confidence_threshold": 0.7,
                "is_active": True
            }
        elif endpoint.method.upper() == "GET":
            # GET请求的查询参数
            return {
                "page": 1,
                "page_size": 10,
                "limit": 10
            }
        else:
            return {}
    
    def _validate_response_format(
        self, 
        response_data: Dict[str, Any], 
        endpoint: APIEndpoint,
        status_code: int
    ) -> List[str]:
        """验证响应格式"""
        issues = []
        
        # 检查基本响应格式
        if status_code == 200:
            # 成功响应格式检查
            if endpoint.response_model and "StandardResponse" in endpoint.response_model:
                issues.extend(self._validate_standard_response(response_data))
            elif endpoint.response_model == "HealthCheckResponse":
                issues.extend(self._validate_health_response(response_data))
        elif status_code >= 400:
            # 错误响应格式检查
            issues.extend(self._validate_error_response(response_data))
        
        # 检查数据类型一致性
        issues.extend(self._validate_data_types(response_data))
        
        # 检查必需字段
        issues.extend(self._validate_required_fields(response_data, endpoint))
        
        return issues
    
    def _validate_standard_response(self, data: Dict[str, Any]) -> List[str]:
        """验证标准响应格式"""
        issues = []
        required_fields = ["success", "message", "timestamp"]
        
        for field in required_fields:
            if field not in data:
                issues.append(f"缺少必需字段: {field}")
        
        # 检查字段类型
        if "success" in data and not isinstance(data["success"], bool):
            issues.append("success字段应为布尔类型")
        
        if "message" in data and not isinstance(data["message"], str):
            issues.append("message字段应为字符串类型")
        
        if "timestamp" in data:
            try:
                datetime.fromisoformat(data["timestamp"].replace('Z', '+00:00'))
            except (ValueError, AttributeError):
                issues.append("timestamp字段格式不正确，应为ISO格式")
        
        # 检查请求ID格式
        if "request_id" in data and data["request_id"] is not None:
            if not isinstance(data["request_id"], str):
                issues.append("request_id字段应为字符串类型")
        
        return issues
    
    def _validate_health_response(self, data: Dict[str, Any]) -> List[str]:
        """验证健康检查响应格式"""
        issues = []
        required_fields = ["status", "version", "timestamp"]
        
        for field in required_fields:
            if field not in data:
                issues.append(f"健康检查响应缺少必需字段: {field}")
        
        if "status" in data and data["status"] not in ["healthy", "unhealthy", "degraded"]:
            issues.append("健康状态值不在预期范围内")
        
        return issues
    
    def _validate_error_response(self, data: Dict[str, Any]) -> List[str]:
        """验证错误响应格式"""
        issues = []
        
        # 错误响应应该包含错误信息
        if "success" in data and data["success"]:
            issues.append("错误响应的success字段应为false")
        
        if "error" not in data and "message" not in data:
            issues.append("错误响应应包含error或message字段")
        
        return issues
    
    def _validate_data_types(self, data: Dict[str, Any]) -> List[str]:
        """验证数据类型一致性"""
        issues = []
        
        # 递归检查嵌套对象的类型一致性
        def check_types(obj, path=""):
            if isinstance(obj, dict):
                for key, value in obj.items():
                    current_path = f"{path}.{key}" if path else key
                    check_types(value, current_path)
            elif isinstance(obj, list):
                for i, item in enumerate(obj):
                    current_path = f"{path}[{i}]"
                    check_types(item, current_path)
        
        try:
            check_types(data)
        except Exception as e:
            issues.append(f"数据类型检查失败: {str(e)}")
        
        return issues
    
    def _validate_required_fields(self, data: Dict[str, Any], endpoint: APIEndpoint) -> List[str]:
        """验证必需字段"""
        issues = []
        
        # 根据端点类型检查特定字段
        if endpoint.name == "chat_interact" and "data" in data:
            chat_data = data["data"]
            if isinstance(chat_data, dict):
                # 检查聊天响应必需字段
                if "response" not in chat_data:
                    issues.append("聊天响应缺少response字段")
                
                if "intent" not in chat_data:
                    issues.append("聊天响应缺少intent字段")
        
        return issues
    
    def _analyze_response_schema(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """分析响应数据结构"""
        def analyze_value(value):
            if isinstance(value, dict):
                return {key: analyze_value(val) for key, val in value.items()}
            elif isinstance(value, list):
                if value:
                    return [analyze_value(value[0])]
                else:
                    return []
            else:
                return type(value).__name__
        
        return analyze_value(data)
    
    async def run_all_tests(self) -> List[ContractTestResult]:
        """运行所有端点测试"""
        print(f"🚀 开始API契约测试，共{len(self.endpoints)}个端点")
        print("=" * 60)
        
        results = []
        for endpoint in self.endpoints:
            try:
                result = await self.test_endpoint(endpoint)
                results.append(result)
                
                # 实时显示结果
                if result.status == "pass":
                    print(f"✅ {endpoint.path}: 通过 ({result.response_time_ms:.1f}ms)")
                elif result.status == "fail":
                    print(f"⚠️  {endpoint.path}: 发现{len(result.issues)}个问题")
                    for issue in result.issues:
                        print(f"   - {issue}")
                else:
                    print(f"❌ {endpoint.path}: 测试失败 - {result.issues[0] if result.issues else '未知错误'}")
            
            except Exception as e:
                error_result = ContractTestResult(
                    endpoint=endpoint.path,
                    method=endpoint.method,
                    status="error",
                    issues=[f"测试执行异常: {str(e)}"]
                )
                results.append(error_result)
                print(f"❌ {endpoint.path}: 测试异常 - {e}")
        
        self.test_results = results
        return results
    
    def generate_report(self, results: List[ContractTestResult]) -> str:
        """生成测试报告"""
        total_tests = len(results)
        passed = len([r for r in results if r.status == "pass"])
        failed = len([r for r in results if r.status == "fail"])
        errors = len([r for r in results if r.status == "error"])
        
        # 计算平均响应时间
        response_times = [r.response_time_ms for r in results if r.response_time_ms is not None]
        avg_response_time = sum(response_times) / len(response_times) if response_times else 0
        
        report = f"""
# API契约测试报告
生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
测试服务器: {self.base_url}

## 📊 总体统计
- 总测试数: {total_tests}
- ✅ 通过: {passed}
- ⚠️ 失败: {failed}
- ❌ 错误: {errors}
- 平均响应时间: {avg_response_time:.1f}ms

## 📋 详细结果

"""
        
        for result in results:
            report += f"### {result.method} {result.endpoint}\n"
            report += f"状态: {result.status}\n"
            
            if result.status_code:
                report += f"HTTP状态码: {result.status_code}\n"
            
            if result.response_time_ms:
                report += f"响应时间: {result.response_time_ms:.1f}ms\n"
            
            if result.issues:
                report += f"问题数: {len(result.issues)}\n"
                for issue in result.issues:
                    report += f"- {issue}\n"
            
            if result.expected_schema:
                report += f"预期模式: {result.expected_schema}\n"
            
            report += "\n"
        
        # 添加问题汇总
        if failed > 0 or errors > 0:
            report += "## 🔍 问题汇总\n\n"
            
            # 收集所有问题
            all_issues = {}
            for result in results:
                if result.issues:
                    for issue in result.issues:
                        if issue not in all_issues:
                            all_issues[issue] = []
                        all_issues[issue].append(f"{result.method} {result.endpoint}")
            
            for issue, endpoints in all_issues.items():
                report += f"**{issue}**\n"
                for endpoint in endpoints:
                    report += f"- {endpoint}\n"
                report += "\n"
        
        return report
    
    async def save_report(self, results: List[ContractTestResult]) -> str:
        """保存测试报告"""
        report = self.generate_report(results)
        
        # 保存报告
        report_file = f"reports/api_contract_test_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
        os.makedirs('reports', exist_ok=True)
        
        with open(report_file, 'w', encoding='utf-8') as f:
            f.write(report)
        
        return report_file


async def main():
    """主函数"""
    tester = APIContractTester()
    
    try:
        # 运行所有测试
        results = await tester.run_all_tests()
        
        # 保存报告
        report_file = await tester.save_report(results)
        
        print("=" * 60)
        print(f"📄 报告已保存到: {report_file}")
        
        # 显示摘要
        print("\n📊 测试摘要:")
        total = len(results)
        passed = len([r for r in results if r.status == "pass"])
        failed = len([r for r in results if r.status == "fail"])
        errors = len([r for r in results if r.status == "error"])
        
        print(f"总计: {total} | 通过: {passed} | 失败: {failed} | 错误: {errors}")
        
        if failed > 0 or errors > 0:
            print("⚠️ 发现API契约一致性问题，请查看报告详情")
            return 1
        else:
            print("✅ 所有API契约测试通过")
            return 0
            
    except Exception as e:
        print(f"❌ 测试过程中发生错误: {e}")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)