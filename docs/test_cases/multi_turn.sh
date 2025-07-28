#\!/bin/bash

# 测试多轮间隔槽位补充功能
BASE_URL="http://localhost:8000/api/v1/chat/interact"
USER_ID="test_user_004"

echo "=== 轮次1: 初始订票请求 ==="
RESPONSE1=$(curl -s -X POST "$BASE_URL" \
  -H "Content-Type: application/json" \
  -d "{
    \"user_id\": \"$USER_ID\",
    \"input\": \"我想订机票去上海\"
  }")

echo "$RESPONSE1" | jq '.'
SESSION_ID=$(echo "$RESPONSE1" | jq -r '.data.session_id')
echo "Session ID: $SESSION_ID"

echo -e "\n=== 轮次2: 系统询问出发城市（自动生成） ==="
echo "系统应该询问：请问您从哪个城市出发？"

echo -e "\n=== 轮次3: 无关对话1 - 询问天气 ==="
RESPONSE3=$(curl -s -X POST "$BASE_URL" \
  -H "Content-Type: application/json" \
  -d "{
    \"session_id\": \"$SESSION_ID\",
    \"user_id\": \"$USER_ID\", 
    \"input\": \"今天天气怎么样？\"
  }")

echo "$RESPONSE3" | jq '.'

echo -e "\n=== 轮次4: 无关对话2 - 工作话题 ==="
RESPONSE4=$(curl -s -X POST "$BASE_URL" \
  -H "Content-Type: application/json" \
  -d "{
    \"session_id\": \"$SESSION_ID\",
    \"user_id\": \"$USER_ID\",
    \"input\": \"最近工作很忙\"
  }")

echo "$RESPONSE4" | jq '.'

echo -e "\n=== 轮次5: 槽位补充 - 出发城市 ==="
RESPONSE5=$(curl -s -X POST "$BASE_URL" \
  -H "Content-Type: application/json" \
  -d "{
    \"session_id\": \"$SESSION_ID\",
    \"user_id\": \"$USER_ID\",
    \"input\": \"武汉\"
  }")

echo "$RESPONSE5" | jq '.'

echo -e "\n=== 测试结果分析 ==="
echo "轮次1: $(echo "$RESPONSE1" | jq -r '.data.intent // "null"') - $(echo "$RESPONSE1" | jq -r '.data.status')"
echo "轮次3: $(echo "$RESPONSE3" | jq -r '.data.intent // "null"') - $(echo "$RESPONSE3" | jq -r '.data.status')" 
echo "轮次4: $(echo "$RESPONSE4" | jq -r '.data.intent // "null"') - $(echo "$RESPONSE4" | jq -r '.data.status')"
echo "轮次5: $(echo "$RESPONSE5" | jq -r '.data.intent // "null"') - $(echo "$RESPONSE5" | jq -r '.data.status')"
echo ""
echo "期望结果:"
echo "- 轮次1: book_flight - incomplete"
echo "- 轮次3: null - non_intent_input"  
echo "- 轮次4: null - non_intent_input"
echo "- 轮次5: book_flight - incomplete/completed (取决于是否还有其他缺失槽位)"