#!/bin/bash

# 单轮意图测试脚本 - 每个测试都是独立的单轮对话
# 不需要session_id，因为每次都是新的对话开始

SERVER_URL="http://localhost:8000/api/v1/chat/interact"
LOG_FILE="single_intent_test_results.log"

# 清空日志文件
> $LOG_FILE

# 测试函数：执行单个测试用例
execute_test() {
    local test_name="$1"
    local user_id="$2" 
    local input_text="$3"
    local description="$4"
    
    echo "执行测试: $description" | tee -a $LOG_FILE
    echo "输入: $input_text" | tee -a $LOG_FILE
    
    response=$(curl -s -X POST "$SERVER_URL" \
        -H "Content-Type: application/json" \
        -d "{\"user_id\": \"$user_id\", \"input\": \"$input_text\"}")
    
    echo "响应: $response" | tee -a $LOG_FILE
    echo "----------------------------------------" | tee -a $LOG_FILE
    echo ""
}

echo "======================================"
echo "         单轮意图完整测试套件"
echo "======================================"
echo "日志文件: $LOG_FILE"
echo "服务器: $SERVER_URL"
echo "======================================"

echo -e "\n🎯 开始执行单轮意图基础测试...\n"

# =====================================
# 0. 基本意图识别测试
# =====================================
echo "======================================"
echo "         0. 基本意图识别测试"
echo "======================================"

execute_test "basic_intent_1" "basic_intent_user_001" "订机票" "简单订票意图"
execute_test "basic_intent_2" "basic_intent_user_002" "查余额" "简单查询意图"  
execute_test "basic_intent_3" "basic_intent_user_003" "改密码" "简单修改意图"
execute_test "basic_intent_4" "basic_intent_user_004" "买票" "订票变体"
execute_test "basic_intent_5" "basic_intent_user_005" "查看余额" "查询变体"
execute_test "basic_intent_6" "basic_intent_user_006" "修改密码" "修改变体"

# =====================================
# 1. 完整信息意图测试
# =====================================
echo "======================================"
echo "         1. 完整信息意图测试"
echo "======================================"

execute_test "complete_intent_1" "complete_intent_user_001" "我要订明天从北京到上海的机票" "完整机票信息"
execute_test "complete_intent_2" "complete_intent_user_002" "查一下招商银行储蓄卡的余额" "完整余额查询"
execute_test "complete_intent_3" "complete_intent_user_003" "帮我改一下登录密码" "完整密码修改"
execute_test "complete_intent_4" "complete_intent_user_004" "订后天下午从深圳到广州的经济舱机票，1个人" "详细机票信息"
execute_test "complete_intent_5" "complete_intent_user_005" "我要订2024年8月15日从武汉到成都的机票" "完整时间表达"
execute_test "complete_intent_6" "complete_intent_user_006" "查询中国银行信用卡账户余额" "完整银行信息"

# =====================================
# 2. 部分信息意图测试  
# =====================================
echo "======================================"
echo "         2. 部分信息意图测试"
echo "======================================"

execute_test "partial_intent_1" "partial_intent_user_001" "我想订机票" "纯意图表达"
execute_test "partial_intent_2" "partial_intent_user_002" "我要去上海的机票" "部分地点信息"
execute_test "partial_intent_3" "partial_intent_user_003" "订明天的机票" "部分时间信息"
execute_test "partial_intent_4" "partial_intent_user_004" "帮我查余额" "缺少银行信息"
execute_test "partial_intent_5" "partial_intent_user_005" "修改密码" "缺少密码类型"
execute_test "partial_intent_6" "partial_intent_user_006" "从北京出发的机票" "部分出发信息"
execute_test "partial_intent_7" "partial_intent_user_007" "查招商银行的余额" "部分银行信息"

# =====================================
# 3. 低置信度确认测试
# =====================================
echo "======================================"
echo "         3. 低置信度确认测试"
echo "======================================"

execute_test "low_confidence_1" "low_confidence_user_001" "我想出行" "模糊出行"
execute_test "low_confidence_2" "low_confidence_user_002" "我要用钱" "模糊金融"
execute_test "low_confidence_3" "low_confidence_user_003" "账户操作" "模糊账户操作"
execute_test "low_confidence_4" "low_confidence_user_004" "我想买票" "模糊票务"
execute_test "low_confidence_5" "low_confidence_user_005" "我想查一下" "模糊查询"
execute_test "low_confidence_6" "low_confidence_user_006" "帮我办理业务" "模糊服务"
execute_test "low_confidence_7" "low_confidence_user_007" "我需要去外地" "间接表达"
execute_test "low_confidence_8" "low_confidence_user_008" "我想更新一些信息" "模糊安全操作"

# =====================================
# 4. Fallback处理测试
# =====================================
echo "======================================"
echo "         4. Fallback处理测试"
echo "======================================"

execute_test "fallback_1" "fallback_user_001" "今天天气真好" "天气闲聊"
execute_test "fallback_2" "fallback_user_002" "你好吗" "问候语"
execute_test "fallback_3" "fallback_user_003" "随机文本abc123" "随机文本"
execute_test "fallback_4" "fallback_user_004" "12345678" "纯数字"
execute_test "fallback_5" "fallback_user_005" "!@#$%^&*()" "特殊字符"
execute_test "fallback_6" "fallback_user_006" "" "空输入"
execute_test "fallback_7" "fallback_user_007" "   " "只有空格"
execute_test "fallback_8" "fallback_user_008" "我喜欢看电影" "无关话题"
execute_test "fallback_9" "fallback_user_009" "HTTP协议和TCP协议" "技术术语"
execute_test "fallback_10" "fallback_user_010" "Hello 你好 こんにちは" "混合语言"

# =====================================
# 5. 参数验证测试
# =====================================
echo "======================================"
echo "         5. 参数验证测试"
echo "======================================"

execute_test "validation_1" "validation_user_001" "订明天32月45日的机票" "无效日期"
execute_test "validation_2" "validation_user_002" "查-100元余额" "负数金额"
execute_test "validation_3" "validation_user_003" "订从火星到月球的机票" "无效地名"
execute_test "validation_4" "validation_user_004" "订2020年1月1日的机票" "过去日期"
execute_test "validation_5" "validation_user_005" "查火星银行的余额" "不存在银行"
execute_test "validation_6" "validation_user_006" "订从北京到北京的机票" "相同起终点"
execute_test "validation_7" "validation_user_007" "订从北京市朝阳区三里屯街道工人体育场北路13号院1号楼到上海市浦东新区陆家嘴环路1000号上海环球金融中心的机票" "超长字符串"
execute_test "validation_8" "validation_user_008" "订明天从北京到上海的机票，99999个人" "极值数量"
execute_test "validation_9" "validation_user_009" "订昨天的明天的后天的机票" "无效时间"
execute_test "validation_10" "validation_user_010" "订从北京<script>alert(\"xss\")</script>到上海的机票" "特殊字符"
execute_test "validation_11" "validation_user_011" "查余额 OR 1=1; DROP TABLE users;" "SQL注入"
execute_test "validation_12" "validation_user_012" "订机票，0个人" "零值参数"

echo -e "\n🎉 单轮意图测试套件执行完成！"
echo "======================================"
echo "详细结果已保存到: $LOG_FILE"
echo "======================================"