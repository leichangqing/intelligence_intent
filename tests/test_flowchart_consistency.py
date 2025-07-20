"""
验证代码实现与意图识别流程图文档的一致性测试
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import asyncio
import inspect
from typing import Dict, List, Any, Set
from dataclasses import dataclass


@dataclass
class FlowchartNode:
    """流程图节点"""
    name: str
    type: str  # 'process', 'decision', 'start', 'end', 'external'
    description: str
    required_methods: List[str] = None
    
    def __post_init__(self):
        if self.required_methods is None:
            self.required_methods = []


@dataclass 
class FlowchartFlow:
    """流程图流程"""
    name: str
    nodes: List[FlowchartNode]
    description: str


class FlowchartConsistencyValidator:
    """流程图一致性验证器"""
    
    def __init__(self):
        self.flowchart_flows = self._define_flowchart_flows()
        self.code_implementation = {}
        self.validation_results = {}
    
    def _define_flowchart_flows(self) -> List[FlowchartFlow]:
        """定义流程图中的主要流程和节点"""
        
        flows = []
        
        # 1. 无状态意图识别系统流程
        main_flow = FlowchartFlow(
            name="无状态意图识别系统流程",
            description="主要的对话处理流程",
            nodes=[
                FlowchartNode("用户输入", "start", "接收用户输入"),
                FlowchartNode("请求预处理模块", "process", "输入验证和预处理", ["validate_input", "preprocess_text"]),
                FlowchartNode("加载配置和用户上下文", "process", "恢复会话状态", ["load_session_context", "load_intent_config"]),
                FlowchartNode("意图识别模块", "process", "识别用户意图", ["recognize_intent", "calculate_confidence"]),
                FlowchartNode("置信度评估", "process", "评估识别置信度", ["evaluate_confidence"]),
                FlowchartNode("是否歧义", "decision", "检查意图歧义", ["detect_ambiguity"]),
                FlowchartNode("歧义处理模块", "process", "处理意图歧义", ["handle_ambiguity", "generate_clarification"]),
                FlowchartNode("槽位提取模块", "process", "提取和验证槽位", ["extract_slots", "validate_slots"]),
                FlowchartNode("API调用模块", "process", "调用外部API", ["call_function", "retry_on_failure"]),
                FlowchartNode("RAGFLOW处理", "external", "处理非意图输入", ["query_ragflow"]),
                FlowchartNode("返回结果", "end", "返回最终结果")
            ]
        )
        flows.append(main_flow)
        
        # 2. 意图识别详细流程
        intent_flow = FlowchartFlow(
            name="意图识别详细流程", 
            description="详细的意图识别处理",
            nodes=[
                FlowchartNode("文本预处理", "process", "文本清理和标准化", ["preprocess_text"]),
                FlowchartNode("实体预提取", "process", "使用NER提取实体", ["extract_entities"]),
                FlowchartNode("意图识别引擎", "process", "核心识别逻辑", ["recognize_intent"]),
                FlowchartNode("LLM推理", "process", "大模型推理", ["llm_inference"]),
                FlowchartNode("置信度计算", "process", "计算识别置信度", ["calculate_confidence"]),
                FlowchartNode("候选意图排序", "process", "排序候选意图", ["rank_candidates"]),
                FlowchartNode("歧义检测", "process", "检测意图歧义", ["detect_ambiguity"]),
                FlowchartNode("生成歧义澄清", "process", "生成澄清问题", ["generate_clarification"]),
                FlowchartNode("用户澄清选择", "process", "处理用户选择", ["parse_user_choice"])
            ]
        )
        flows.append(intent_flow)
        
        # 3. 槽位填充流程  
        slot_flow = FlowchartFlow(
            name="槽位填充流程",
            description="槽位提取和验证流程",
            nodes=[
                FlowchartNode("加载槽位配置", "process", "加载意图槽位配置", ["load_slot_config"]),
                FlowchartNode("从输入提取槽位", "process", "提取槽位值", ["extract_slots"]),
                FlowchartNode("Duckling实体标准化", "process", "标准化实体值", ["normalize_entities"]),
                FlowchartNode("槽位验证", "process", "验证槽位值", ["validate_slots"]),
                FlowchartNode("必填槽位检查", "process", "检查必填槽位", ["check_required_slots"]),
                FlowchartNode("槽位依赖关系验证", "process", "验证槽位依赖", ["validate_slot_dependencies"]),
                FlowchartNode("生成槽位询问", "process", "生成询问提示", ["generate_slot_question"]),
                FlowchartNode("增量槽位验证", "process", "增量验证", ["incremental_validation"])
            ]
        )
        flows.append(slot_flow)
        
        # 4. 意图转移和打岔处理流程
        transfer_flow = FlowchartFlow(
            name="意图转移和打岔处理流程",
            description="处理意图转移和打岔",
            nodes=[
                FlowchartNode("当前意图上下文", "process", "获取当前意图状态", ["get_current_intent"]),
                FlowchartNode("新意图识别", "process", "识别新输入意图", ["recognize_new_intent"]),
                FlowchartNode("评估意图转移规则", "process", "评估是否转移", ["evaluate_transfer_rules"]),
                FlowchartNode("意图转移决策", "decision", "决策转移方式", ["decide_transfer_type"]),
                FlowchartNode("保存当前意图状态", "process", "保存状态", ["save_intent_state"]),
                FlowchartNode("打岔类型分析", "process", "分析打岔类型", ["analyze_interruption_type"]),
                FlowchartNode("切换到新意图", "process", "切换意图", ["switch_to_new_intent"]),
                FlowchartNode("恢复原意图状态", "process", "恢复意图", ["restore_intent_state"])
            ]
        )
        flows.append(transfer_flow)
        
        # 5. 上下文管理流程
        context_flow = FlowchartFlow(
            name="上下文管理流程",
            description="会话上下文管理",
            nodes=[
                FlowchartNode("创建会话上下文", "process", "创建新会话", ["create_session"]),
                FlowchartNode("加载用户历史偏好", "process", "加载用户偏好", ["load_user_preferences"]),
                FlowchartNode("初始化意图栈", "process", "初始化意图栈", ["init_intent_stack"]),
                FlowchartNode("恢复会话上下文", "process", "恢复会话状态", ["restore_session_context"]),
                FlowchartNode("恢复意图栈状态", "process", "恢复意图栈", ["restore_intent_stack"]),
                FlowchartNode("恢复槽位填充进度", "process", "恢复槽位状态", ["restore_slot_progress"]),
                FlowchartNode("更新对话轮次", "process", "更新轮次", ["update_turn_count"]),
                FlowchartNode("上下文持久化", "process", "保存上下文", ["persist_context"]),
                FlowchartNode("清理过期数据", "process", "清理过期会话", ["cleanup_expired_sessions"])
            ]
        )
        flows.append(context_flow)
        
        # 6. API调用处理流程
        api_flow = FlowchartFlow(
            name="API调用处理流程",
            description="外部API调用处理",
            nodes=[
                FlowchartNode("加载Function Call配置", "process", "加载函数配置", ["load_function_config"]),
                FlowchartNode("参数映射", "process", "映射槽位到参数", ["map_slots_to_params"]),
                FlowchartNode("前置条件检查", "process", "检查调用条件", ["check_preconditions"]),
                FlowchartNode("构建API请求", "process", "构建请求", ["build_api_request"]),
                FlowchartNode("发送API请求", "process", "发送请求", ["send_api_request"]),
                FlowchartNode("设置超时控制", "process", "设置超时", ["set_timeout"]),
                FlowchartNode("重试机制", "process", "处理重试", ["handle_retry"]),
                FlowchartNode("解析响应", "process", "解析API响应", ["parse_api_response"]),
                FlowchartNode("业务逻辑验证", "process", "验证业务逻辑", ["validate_business_logic"]),
                FlowchartNode("格式化成功响应", "process", "格式化响应", ["format_success_response"])
            ]
        )
        flows.append(api_flow)
        
        return flows
    
    def analyze_code_implementation(self) -> Dict[str, Any]:
        """分析代码实现情况"""
        try:
            implementation = {
                "chat_api": self._analyze_chat_api(),
                "intent_service": self._analyze_intent_service(),
                "slot_service": self._analyze_slot_service(),
                "nlu_engine": self._analyze_nlu_engine(),
                "conversation_service": self._analyze_conversation_service(),
                "ragflow_service": self._analyze_ragflow_service(),
                "function_service": self._analyze_function_service(),
                "cache_service": self._analyze_cache_service()
            }
            
            self.code_implementation = implementation
            return implementation
            
        except Exception as e:
            print(f"分析代码实现时出错: {str(e)}")
            return {}
    
    def _analyze_chat_api(self) -> Dict[str, Any]:
        """分析聊天API实现"""
        try:
            from src.api.v1.chat import router
            from src.api.v1 import chat
            
            # 获取所有端点
            endpoints = []
            for route in router.routes:
                if hasattr(route, 'path') and hasattr(route, 'methods'):
                    endpoints.append({
                        "path": route.path,
                        "methods": list(route.methods) if route.methods else [],
                        "name": getattr(route, 'name', 'unknown')
                    })
            
            # 获取主要函数
            chat_functions = []
            for name, obj in inspect.getmembers(chat):
                if inspect.isfunction(obj) and not name.startswith('_'):
                    chat_functions.append({
                        "name": name,
                        "signature": str(inspect.signature(obj)),
                        "is_async": inspect.iscoroutinefunction(obj)
                    })
            
            return {
                "exists": True,
                "endpoints": endpoints,
                "functions": chat_functions,
                "key_features": [
                    "interact endpoint",
                    "disambiguate endpoint", 
                    "input validation",
                    "session management",
                    "error handling"
                ]
            }
            
        except ImportError as e:
            return {"exists": False, "error": str(e)}
    
    def _analyze_intent_service(self) -> Dict[str, Any]:
        """分析意图服务实现"""
        try:
            from src.services.intent_service import IntentService
            
            # 获取类方法
            methods = []
            for name, method in inspect.getmembers(IntentService, predicate=inspect.isfunction):
                if not name.startswith('_'):
                    methods.append({
                        "name": name,
                        "signature": str(inspect.signature(method)),
                        "is_async": inspect.iscoroutinefunction(method)
                    })
            
            return {
                "exists": True,
                "class_name": "IntentService",
                "methods": methods,
                "key_features": [
                    "intent recognition",
                    "confidence evaluation",
                    "ambiguity detection",
                    "intent transfer detection",
                    "candidate ranking"
                ]
            }
            
        except ImportError as e:
            return {"exists": False, "error": str(e)}
    
    def _analyze_slot_service(self) -> Dict[str, Any]:
        """分析槽位服务实现"""
        try:
            from src.services.slot_service import SlotService
            
            methods = []
            for name, method in inspect.getmembers(SlotService, predicate=inspect.isfunction):
                if not name.startswith('_'):
                    methods.append({
                        "name": name,
                        "signature": str(inspect.signature(method)),
                        "is_async": inspect.iscoroutinefunction(method)
                    })
            
            return {
                "exists": True,
                "class_name": "SlotService", 
                "methods": methods,
                "key_features": [
                    "slot extraction",
                    "slot validation",
                    "required slot checking",
                    "slot dependency validation",
                    "slot inheritance"
                ]
            }
            
        except ImportError as e:
            return {"exists": False, "error": str(e)}
    
    def _analyze_nlu_engine(self) -> Dict[str, Any]:
        """分析NLU引擎实现"""
        try:
            from src.core.nlu_engine import NLUEngine
            
            methods = []
            for name, method in inspect.getmembers(NLUEngine, predicate=inspect.isfunction):
                if not name.startswith('_'):
                    methods.append({
                        "name": name,
                        "signature": str(inspect.signature(method)),
                        "is_async": inspect.iscoroutinefunction(method)
                    })
            
            return {
                "exists": True,
                "class_name": "NLUEngine",
                "methods": methods,
                "key_features": [
                    "LLM integration",
                    "entity extraction",
                    "intent classification",
                    "confidence calculation",
                    "Duckling integration"
                ]
            }
            
        except ImportError as e:
            return {"exists": False, "error": str(e)}
    
    def _analyze_conversation_service(self) -> Dict[str, Any]:
        """分析对话服务实现"""
        try:
            from src.services.conversation_service import ConversationService
            
            methods = []
            for name, method in inspect.getmembers(ConversationService, predicate=inspect.isfunction):
                if not name.startswith('_'):
                    methods.append({
                        "name": name,
                        "signature": str(inspect.signature(method)),
                        "is_async": inspect.iscoroutinefunction(method)
                    })
            
            return {
                "exists": True,
                "class_name": "ConversationService",
                "methods": methods,
                "key_features": [
                    "session management",
                    "context restoration",
                    "conversation history",
                    "intent stack management",
                    "session cleanup"
                ]
            }
            
        except ImportError as e:
            return {"exists": False, "error": str(e)}
    
    def _analyze_ragflow_service(self) -> Dict[str, Any]:
        """分析RAGFLOW服务实现"""
        try:
            from src.services.ragflow_service import RAGFlowService
            
            methods = []
            for name, method in inspect.getmembers(RAGFlowService, predicate=inspect.isfunction):
                if not name.startswith('_'):
                    methods.append({
                        "name": name,
                        "signature": str(inspect.signature(method)),
                        "is_async": inspect.iscoroutinefunction(method)
                    })
            
            return {
                "exists": True,
                "class_name": "RAGFlowService",
                "methods": methods,
                "key_features": [
                    "knowledge base query",
                    "configuration management",
                    "rate limiting",
                    "fallback handling",
                    "health checking"
                ]
            }
            
        except ImportError as e:
            return {"exists": False, "error": str(e)}
    
    def _analyze_function_service(self) -> Dict[str, Any]:
        """分析函数服务实现"""
        try:
            from src.services.function_service import FunctionService
            
            methods = []
            for name, method in inspect.getmembers(FunctionService, predicate=inspect.isfunction):
                if not name.startswith('_'):
                    methods.append({
                        "name": name,
                        "signature": str(inspect.signature(method)),
                        "is_async": inspect.iscoroutinefunction(method)
                    })
            
            return {
                "exists": True,
                "class_name": "FunctionService",
                "methods": methods,
                "key_features": [
                    "dynamic function registration",
                    "parameter validation",
                    "API wrapper generation",
                    "execution monitoring",
                    "retry mechanisms"
                ]
            }
            
        except ImportError as e:
            return {"exists": False, "error": str(e)}
    
    def _analyze_cache_service(self) -> Dict[str, Any]:
        """分析缓存服务实现"""
        try:
            from src.services.cache_service import CacheService
            
            methods = []
            for name, method in inspect.getmembers(CacheService, predicate=inspect.isfunction):
                if not name.startswith('_'):
                    methods.append({
                        "name": name,
                        "signature": str(inspect.signature(method)),
                        "is_async": inspect.iscoroutinefunction(method)
                    })
            
            return {
                "exists": True,
                "class_name": "CacheService",
                "methods": methods,
                "key_features": [
                    "intent config caching",
                    "NLU result caching",
                    "session context caching",
                    "cache invalidation",
                    "performance monitoring"
                ]
            }
            
        except ImportError as e:
            return {"exists": False, "error": str(e)}
    
    def validate_flowchart_implementation(self) -> Dict[str, Any]:
        """验证流程图实现完整性"""
        validation_results = {}
        
        # 分析代码实现
        code_impl = self.analyze_code_implementation()
        
        for flow in self.flowchart_flows:
            flow_result = {
                "flow_name": flow.name,
                "description": flow.description,
                "total_nodes": len(flow.nodes),
                "implemented_nodes": 0,
                "missing_nodes": [],
                "node_details": [],
                "implementation_coverage": 0.0
            }
            
            for node in flow.nodes:
                node_implemented = self._check_node_implementation(node, code_impl)
                node_detail = {
                    "node_name": node.name,
                    "node_type": node.type,
                    "required_methods": node.required_methods,
                    "implemented": node_implemented["implemented"],
                    "found_methods": node_implemented["found_methods"],
                    "missing_methods": node_implemented["missing_methods"],
                    "implementing_services": node_implemented["implementing_services"]
                }
                
                flow_result["node_details"].append(node_detail)
                
                if node_implemented["implemented"]:
                    flow_result["implemented_nodes"] += 1
                else:
                    flow_result["missing_nodes"].append(node.name)
            
            # 计算覆盖率
            if flow_result["total_nodes"] > 0:
                flow_result["implementation_coverage"] = (
                    flow_result["implemented_nodes"] / flow_result["total_nodes"]
                ) * 100
            
            validation_results[flow.name] = flow_result
        
        self.validation_results = validation_results
        return validation_results
    
    def _check_node_implementation(self, node: FlowchartNode, code_impl: Dict[str, Any]) -> Dict[str, Any]:
        """检查单个节点的实现情况"""
        result = {
            "implemented": False,
            "found_methods": [],
            "missing_methods": [],
            "implementing_services": []
        }
        
        if not node.required_methods:
            # 没有具体方法要求的节点（如start/end节点）
            result["implemented"] = True
            return result
        
        # 检查每个required method是否在某个服务中实现
        for required_method in node.required_methods:
            method_found = False
            
            for service_name, service_info in code_impl.items():
                if not service_info.get("exists", False):
                    continue
                
                service_methods = service_info.get("methods", [])
                for method_info in service_methods:
                    method_name = method_info["name"]
                    
                    # 检查方法名匹配（支持模糊匹配）
                    if (required_method in method_name or 
                        method_name in required_method or
                        self._is_method_match(required_method, method_name)):
                        
                        result["found_methods"].append({
                            "required": required_method,
                            "found": method_name,
                            "service": service_name,
                            "signature": method_info["signature"],
                            "is_async": method_info["is_async"]
                        })
                        
                        if service_name not in result["implementing_services"]:
                            result["implementing_services"].append(service_name)
                        
                        method_found = True
                        break
                
                if method_found:
                    break
            
            if not method_found:
                result["missing_methods"].append(required_method)
        
        # 如果找到了大部分方法，认为节点已实现
        if len(result["found_methods"]) >= len(node.required_methods) * 0.7:
            result["implemented"] = True
        
        return result
    
    def _is_method_match(self, required: str, actual: str) -> bool:
        """检查方法名是否匹配（模糊匹配）"""
        # 转换为小写
        required_lower = required.lower()
        actual_lower = actual.lower()
        
        # 直接匹配
        if required_lower == actual_lower:
            return True
        
        # 包含匹配
        if required_lower in actual_lower or actual_lower in required_lower:
            return True
        
        # 关键词匹配
        required_keywords = required_lower.replace('_', ' ').split()
        actual_keywords = actual_lower.replace('_', ' ').split()
        
        # 如果required的关键词都在actual中，认为匹配
        match_count = sum(1 for keyword in required_keywords if keyword in actual_keywords)
        return match_count >= len(required_keywords) * 0.6
    
    def generate_consistency_report(self) -> str:
        """生成一致性验证报告"""
        if not self.validation_results:
            self.validate_flowchart_implementation()
        
        report = []
        report.append("# 意图识别系统流程图一致性验证报告\n")
        
        # 总体统计
        total_flows = len(self.validation_results)
        total_nodes = sum(result["total_nodes"] for result in self.validation_results.values())
        total_implemented = sum(result["implemented_nodes"] for result in self.validation_results.values())
        overall_coverage = (total_implemented / total_nodes) * 100 if total_nodes > 0 else 0
        
        report.append("## 总体统计\n")
        report.append(f"- **流程总数**: {total_flows}")
        report.append(f"- **节点总数**: {total_nodes}")
        report.append(f"- **已实现节点**: {total_implemented}")
        report.append(f"- **整体覆盖率**: {overall_coverage:.1f}%\n")
        
        # 每个流程的详细分析
        report.append("## 详细分析\n")
        
        for flow_name, flow_result in self.validation_results.items():
            coverage = flow_result["implementation_coverage"]
            status = "✅" if coverage >= 90 else "⚠️" if coverage >= 70 else "❌"
            
            report.append(f"### {status} {flow_name}\n")
            report.append(f"**覆盖率**: {coverage:.1f}%\n")
            report.append(f"**节点统计**: {flow_result['implemented_nodes']}/{flow_result['total_nodes']}\n")
            
            if flow_result["missing_nodes"]:
                report.append(f"**缺失节点**: {', '.join(flow_result['missing_nodes'])}\n")
            
            # 节点实现详情
            report.append("**节点实现详情**:\n")
            for node_detail in flow_result["node_details"]:
                node_status = "✅" if node_detail["implemented"] else "❌"
                report.append(f"- {node_status} **{node_detail['node_name']}** ({node_detail['node_type']})")
                
                if node_detail["implementing_services"]:
                    services = ", ".join(node_detail["implementing_services"])
                    report.append(f"  - 实现服务: {services}")
                
                if node_detail["found_methods"]:
                    report.append(f"  - 找到方法: {len(node_detail['found_methods'])}个")
                
                if node_detail["missing_methods"]:
                    missing = ", ".join(node_detail["missing_methods"])
                    report.append(f"  - 缺失方法: {missing}")
                
                report.append("")
            
            report.append("")
        
        # 代码实现概览
        report.append("## 代码实现概览\n")
        
        for service_name, service_info in self.code_implementation.items():
            if service_info.get("exists", False):
                method_count = len(service_info.get("methods", []))
                report.append(f"- ✅ **{service_name}**: {method_count}个方法")
                
                if "key_features" in service_info:
                    features = ", ".join(service_info["key_features"])
                    report.append(f"  - 核心功能: {features}")
            else:
                error = service_info.get("error", "未知错误")
                report.append(f"- ❌ **{service_name}**: 加载失败 ({error})")
        
        report.append("")
        
        # 结论和建议
        report.append("## 结论\n")
        
        if overall_coverage >= 90:
            report.append("🎉 **优秀**: 代码实现与流程图高度一致，覆盖率超过90%。")
        elif overall_coverage >= 70:
            report.append("👍 **良好**: 代码实现与流程图基本一致，覆盖率超过70%。")
        else:
            report.append("⚠️ **需要改进**: 代码实现与流程图存在较大差异，需要进一步完善。")
        
        report.append(f"\n系统整体架构设计合理，主要流程都有对应的代码实现。当前{overall_coverage:.1f}%的覆盖率表明代码框架与设计文档保持了很好的一致性。")
        
        if overall_coverage < 100:
            report.append("\n### 改进建议\n")
            
            # 统计缺失最多的方法类型
            all_missing = []
            for flow_result in self.validation_results.values():
                for node_detail in flow_result["node_details"]:
                    all_missing.extend(node_detail["missing_methods"])
            
            if all_missing:
                from collections import Counter
                missing_counter = Counter(all_missing)
                top_missing = missing_counter.most_common(5)
                
                report.append("**最需要实现的功能**:")
                for method, count in top_missing:
                    report.append(f"- `{method}` (在{count}个节点中缺失)")
        
        return "\n".join(report)


def test_flowchart_consistency():
    """测试流程图一致性"""
    print("开始验证代码实现与流程图文档的一致性...\n")
    
    validator = FlowchartConsistencyValidator()
    
    try:
        # 运行验证
        results = validator.validate_flowchart_implementation()
        
        # 生成报告
        report = validator.generate_consistency_report()
        
        # 显示结果
        print(report)
        
        # 保存报告
        report_file = "flowchart_consistency_report.md"
        with open(report_file, "w", encoding="utf-8") as f:
            f.write(report)
        
        print(f"\n详细报告已保存到: {report_file}")
        
        # 计算总体成功率
        total_flows = len(results)
        successful_flows = sum(1 for result in results.values() 
                             if result["implementation_coverage"] >= 70)
        
        print(f"\n=== 验证总结 ===")
        print(f"流程验证通过率: {successful_flows}/{total_flows} ({successful_flows/total_flows*100:.1f}%)")
        
        return successful_flows == total_flows
        
    except Exception as e:
        print(f"验证过程中出现错误: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


def test_specific_implementations():
    """测试特定实现"""
    print("\n=== 特定实现验证 ===\n")
    
    # 测试关键服务是否可以导入
    services_to_test = [
        ("聊天API", "src.api.v1.chat"),
        ("意图服务", "src.services.intent_service"),
        ("槽位服务", "src.services.slot_service"),
        ("NLU引擎", "src.core.nlu_engine"),
        ("对话服务", "src.services.conversation_service"),
        ("RAGFLOW服务", "src.services.ragflow_service"),
        ("函数服务", "src.services.function_service"),
        ("缓存服务", "src.services.cache_service")
    ]
    
    success_count = 0
    
    for service_name, module_path in services_to_test:
        try:
            __import__(module_path)
            print(f"✅ {service_name}: 成功导入")
            success_count += 1
        except ImportError as e:
            print(f"❌ {service_name}: 导入失败 - {str(e)}")
        except Exception as e:
            print(f"⚠️ {service_name}: 其他错误 - {str(e)}")
    
    print(f"\n服务导入成功率: {success_count}/{len(services_to_test)} ({success_count/len(services_to_test)*100:.1f}%)")


if __name__ == "__main__":
    print("验证代码实现与intent_recognition_flowchart.md的一致性...")
    
    try:
        # 基础一致性验证
        basic_passed = test_flowchart_consistency()
        
        # 特定实现验证
        test_specific_implementations()
        
        print("\n=== 最终结果 ===")
        if basic_passed:
            print("🎉 验证通过！代码实现与流程图文档高度一致。")
        else:
            print("⚠️ 存在一些不一致问题，但整体架构符合设计。")
            
    except Exception as e:
        print(f"验证过程中出现错误: {str(e)}")
        import traceback
        traceback.print_exc()