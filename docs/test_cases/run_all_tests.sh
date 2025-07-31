#!/bin/bash

# 完整测试套件执行脚本
# 包含单轮意图测试和多轮对话测试

TEST_DIR="/Users/leicq/github/intelligence_intent/docs/test_cases"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
REPORT_FILE="test_report_$TIMESTAMP.md"

echo "# 智能意图识别系统测试报告" > $REPORT_FILE
echo "" >> $REPORT_FILE
echo "**执行时间**: $(date)" >> $REPORT_FILE
echo "**测试环境**: $(uname -a)" >> $REPORT_FILE
echo "" >> $REPORT_FILE

echo "======================================"
echo "    智能意图识别系统完整测试套件"
echo "======================================"
echo "开始时间: $(date)"
echo "测试报告: $REPORT_FILE"
echo "======================================"

# 检查服务器是否运行
echo "🔍 检查服务器状态..."
SERVER_URL="http://localhost:8000/api/v1/chat/interact"
if curl -s --connect-timeout 5 "$SERVER_URL" > /dev/null 2>&1; then
    echo "✅ 服务器运行正常"
    echo "## 服务器状态: ✅ 正常运行" >> $REPORT_FILE
else
    echo "❌ 服务器未运行或无法连接"
    echo "请确保服务器在 $SERVER_URL 上运行"
    echo "## 服务器状态: ❌ 无法连接" >> $REPORT_FILE
    echo "" >> $REPORT_FILE
    echo "**错误**: 服务器未运行，测试中止" >> $REPORT_FILE
    exit 1
fi

echo "" >> $REPORT_FILE

# =====================================
# 执行单轮意图测试
# =====================================
echo ""
echo "🚀 开始执行单轮意图测试..."
echo "## 单轮意图测试结果" >> $REPORT_FILE
echo "" >> $REPORT_FILE

cd "$TEST_DIR"
if [ -f "single_intent_test.sh" ]; then
    echo "执行单轮意图测试脚本..."
    ./single_intent_test.sh
    
    # 检查是否生成了结果文件
    if [ -f "single_intent_test_results.log" ]; then
        echo "✅ 单轮意图测试完成，结果已保存"
        
        # 统计测试结果
        total_tests=$(grep -c "执行测试:" single_intent_test_results.log)
        echo "- **测试用例总数**: $total_tests" >> $REPORT_FILE
        echo "- **详细日志**: single_intent_test_results.log" >> $REPORT_FILE
    else
        echo "❌ 单轮意图测试未生成结果文件"
        echo "- **状态**: 测试执行失败" >> $REPORT_FILE
    fi
else
    echo "❌ 单轮意图测试脚本不存在"
    echo "- **状态**: 脚本文件缺失" >> $REPORT_FILE
fi

echo "" >> $REPORT_FILE

# =====================================
# 执行多轮对话测试  
# =====================================
echo ""
echo "🚀 开始执行多轮对话测试..."
echo "## 多轮对话测试结果" >> $REPORT_FILE
echo "" >> $REPORT_FILE

# 检查jq是否安装
if command -v jq &> /dev/null; then
    echo "✅ jq已安装，可以自动处理session_id"
    echo "- **jq状态**: ✅ 已安装" >> $REPORT_FILE
    
    if [ -f "multi_turn_enhanced.sh" ]; then
        echo "执行多轮对话测试脚本..."
        ./multi_turn_enhanced.sh
        
        if [ -f "multi_turn_test_results.log" ]; then
            echo "✅ 多轮对话测试完成，结果已保存"
            
            # 统计测试结果
            total_tests=$(grep -c "开始多轮测试:" multi_turn_test_results.log)
            echo "- **测试场景总数**: $total_tests" >> $REPORT_FILE
            echo "- **详细日志**: multi_turn_test_results.log" >> $REPORT_FILE
        else
            echo "❌ 多轮对话测试未生成结果文件"
            echo "- **状态**: 测试执行失败" >> $REPORT_FILE
        fi
    else
        echo "❌ 多轮对话测试脚本不存在"
        echo "- **状态**: 脚本文件缺失" >> $REPORT_FILE
    fi
else
    echo "⚠️  jq未安装，多轮对话测试可能无法正确处理session_id"
    echo "- **jq状态**: ⚠️ 未安装（建议安装: brew install jq）" >> $REPORT_FILE
    echo "- **影响**: session_id无法自动提取，可能影响多轮对话测试准确性" >> $REPORT_FILE
fi

echo "" >> $REPORT_FILE

# =====================================
# 生成测试总结
# =====================================
echo "## 测试总结" >> $REPORT_FILE
echo "" >> $REPORT_FILE
echo "### 测试文件清单" >> $REPORT_FILE

ls -la *.txt *.sh | while read line; do
    echo "- $line" >> $REPORT_FILE
done

echo "" >> $REPORT_FILE
echo "### 使用说明" >> $REPORT_FILE
echo "" >> $REPORT_FILE
echo "1. **单轮意图测试**: 每个测试都是独立对话，不需要session_id" >> $REPORT_FILE
echo "   - 执行命令: \`./single_intent_test.sh\`" >> $REPORT_FILE
echo "   - 包含6类场景：基本意图、完整信息、部分信息、低置信度、fallback、参数验证" >> $REPORT_FILE
echo "" >> $REPORT_FILE
echo "2. **多轮对话测试**: 需要维护session_id，第一轮从响应中提取" >> $REPORT_FILE
echo "   - 执行命令: \`./multi_turn_enhanced.sh\`" >> $REPORT_FILE
echo "   - 包含5类场景：意图切换、槽位纠错、槽位依赖、多意图并行、歧义消解" >> $REPORT_FILE
echo "" >> $REPORT_FILE
echo "3. **完整测试**: 一键执行所有测试" >> $REPORT_FILE
echo "   - 执行命令: \`./run_all_tests.sh\`" >> $REPORT_FILE

echo ""
echo "======================================"
echo "✅ 测试套件执行完成！"
echo "完成时间: $(date)"
echo "测试报告: $REPORT_FILE"
echo "======================================"

echo "" >> $REPORT_FILE
echo "---" >> $REPORT_FILE
echo "**报告生成时间**: $(date)" >> $REPORT_FILE