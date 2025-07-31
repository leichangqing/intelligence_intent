#!/bin/bash

# 多轮对话测试脚本 - 需要维护session_id
# 第一轮不带session_id，后续轮次使用返回的session_id

SERVER_URL="http://localhost:8000/api/v1/chat/interact"
LOG_FILE="multi_turn_test_results.log"

# 清空日志文件
> $LOG_FILE

# 测试函数：执行多轮对话测试
execute_multi_turn_test() {
    local test_name="$1"
    local user_id="$2"
    shift 2
    local inputs=("$@")
    
    echo "开始多轮测试: $test_name" | tee -a $LOG_FILE
    echo "用户ID: $user_id" | tee -a $LOG_FILE
    
    local session_id=""
    
    for i in "${!inputs[@]}"; do
        local round=$((i + 1))
        local input_text="${inputs[$i]}"
        
        echo "第 $round 轮对话:" | tee -a $LOG_FILE
        echo "输入: $input_text" | tee -a $LOG_FILE
        
        # 构建请求体
        if [ -z "$session_id" ]; then
            # 第一轮，不带session_id
            request_body="{\"user_id\": \"$user_id\", \"input\": \"$input_text\"}"
        else
            # 后续轮次，带session_id
            request_body="{\"session_id\": \"$session_id\", \"user_id\": \"$user_id\", \"input\": \"$input_text\"}"
        fi
        
        echo "请求体: $request_body" | tee -a $LOG_FILE
        
        # 发送请求
        response=$(curl -s -X POST "$SERVER_URL" \
            -H "Content-Type: application/json" \
            -d "$request_body")
        
        echo "响应: $response" | tee -a $LOG_FILE
        
        # 提取session_id（如果这是第一轮）
        if [ -z "$session_id" ]; then
            session_id=$(echo "$response" | jq -r '.session_id // empty')
            if [ -n "$session_id" ]; then
                echo "获取到session_id: $session_id" | tee -a $LOG_FILE
            fi
        fi
        
        echo "----------------------------------------" | tee -a $LOG_FILE
        
        # 轮次间隔
        sleep 1
    done
    
    echo "测试 $test_name 完成" | tee -a $LOG_FILE
    echo "========================================" | tee -a $LOG_FILE
    echo ""
}

echo "======================================"
echo "         多轮对话测试套件"
echo "======================================"
echo "日志文件: $LOG_FILE"
echo "服务器: $SERVER_URL"  
echo "注意: 需要安装jq来解析JSON响应"
echo "======================================"

# 检查jq是否安装
if ! command -v jq &> /dev/null; then
    echo "警告: 未安装jq，无法自动提取session_id"
    echo "请手动安装: brew install jq (macOS) 或 apt-get install jq (Ubuntu)"
fi

echo -e "\n🎯 开始执行多轮对话测试...\n"

# =====================================
# 6. 意图切换与恢复测试
# =====================================
echo "======================================"
echo "         6. 意图切换与恢复测试"
echo "======================================"

execute_multi_turn_test "intent_switch_resume" "intent_switch_user_001" \
    "我想订一张明天去上海的机票" \
    "今天天气怎么样" \
    "查一下我的银行卡余额" \
    "继续订票，从武汉出发"

# =====================================
# 7. 槽位纠错与重填测试
# =====================================
echo "======================================"
echo "         7. 槽位纠错与重填测试" 
echo "======================================"

execute_multi_turn_test "slot_correction" "slot_correction_user_001" \
    "我想订一张明天去上海的机票" \
    "北京" \
    "不对，是武汉出发"

# =====================================
# 8. 复杂槽位依赖测试
# =====================================
echo "======================================"
echo "         8. 复杂槽位依赖测试"
echo "======================================"

execute_multi_turn_test "slot_dependency" "slot_dependency_user_001" \
    "我要订往返机票" \
    "北京到上海" \
    "下周一" \
    "下周五回来"

# =====================================
# 9. 多意图并行处理测试  
# =====================================
echo "======================================"
echo "         9. 多意图并行处理测试"
echo "======================================"

execute_multi_turn_test "multi_intent_parallel" "multi_intent_user_001" \
    "帮我订明天去上海的机票，然后查一下银行卡余额"

# =====================================
# 10. 上下文歧义消解测试
# =====================================
echo "======================================"
echo "         10. 上下文歧义消解测试"
echo "======================================"

execute_multi_turn_test "disambiguation" "disambiguation_user_001" \
    "我想订票" \
    "去上海的"

echo -e "\n🎉 多轮对话测试套件执行完成！"
echo "======================================"
echo "详细结果已保存到: $LOG_FILE"
echo "======================================"

# 使用说明
echo -e "\n📝 使用说明："
echo "1. 单轮意图测试：每次都是新对话，不需要session_id"
echo "   执行：./single_intent_test.sh"
echo ""
echo "2. 多轮对话测试：需要维护session_id，从第一轮响应中提取"
echo "   执行：./multi_turn_enhanced.sh"
echo ""
echo "3. 如果需要手动测试，可以参考以下模式："
echo "   第1轮：{\"user_id\": \"test_user\", \"input\": \"订机票\"}"
echo "   第2轮：{\"session_id\": \"从第1轮响应中获取\", \"user_id\": \"test_user\", \"input\": \"北京到上海\"}"