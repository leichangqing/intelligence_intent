# 用户请求和系统回复的数据结构示例

## 1. 通用数据结构定义

### 1.1 标准请求结构
```json
{
  "user_id": "string",
  "input": "string",
  "context": {
    "location": {
      "ip": "string",
      "city": "string", 
      "country": "string"
    },
    "user_preferences": {
      "language": "string",
      "timezone": "string"
    }
  }
}
```

**请求说明**:
- `user_id`: 用户标识符，用于上下文分析和个性化推荐
- `input`: 用户输入内容，系统自动识别意图和提取槽位
- `context`: 请求上下文信息，用于辅助意图识别（可选）
  - `location`: 位置信息（可选）
  - `user_preferences`: 用户偏好设置（可选）

### 1.2 标准响应结构
```json
{
  "success": true,
  "code": 200,
  "message": "Success",
  "data": {
    "response": "string",
    "intent": "string",
    "confidence": 0.95,
    "status": "completed",
    "response_type": "api_result",
    "slots": {},
    "api_result": {},
    "missing_slots": [],
    "candidate_intents": []
  },
  "timestamp": "2024-12-01T10:00:00Z",
  "request_id": "req_20241201_001",
  "processing_time_ms": 250
}
```

**响应说明**:
- `success`: 请求是否成功处理
- `code`: HTTP状态码（200=成功，400=请求错误，500=服务器错误）
- `message`: 状态码对应的描述信息
- `data`: 业务数据
  - `response`: 系统生成的响应文本，返回给用户的消息
  - `intent`: 识别到的意图名称，null表示未识别到意图
  - `confidence`: 意图识别的置信度（0.0-1.0）
  - `status`: 处理状态（completed=完成，incomplete=不完整，ambiguous=有歧义，error=错误）
  - `response_type`: 响应类型（api_result=API调用结果，slot_prompt=槽位询问，disambiguation=歧义澄清，ragflow_response=对话回复）
  - `slots`: 提取到的所有槽位信息
  - `api_result`: 外部API调用的结果数据（仅在response_type=api_result时存在）
  - `missing_slots`: 缺失的必需槽位列表（仅在status=incomplete时存在）
  - `candidate_intents`: 候选意图列表（仅在status=ambiguous时存在）
- `timestamp`: 响应时间戳
- `request_id`: 请求唯一标识符
- `processing_time_ms`: 处理耗时（毫秒）

## 2. 意图识别成功场景

### 2.1 完整槽位 - 直接API调用

#### 用户请求
```json
{
  "user_id": "user123",
  "input": "我想订一张明天从北京到上海的经济舱机票",
  "context": {
    "location": {
      "ip": "192.168.1.100",
      "city": "Beijing",
      "country": "CN"
    },
    "user_preferences": {
      "language": "zh-CN",
      "timezone": "Asia/Shanghai"
    }
  }
}
```

#### 系统响应
```json
{
  "success": true,
  "code": 200,
  "message": "Success",
  "data": {
    "response": "机票预订成功！订单号：FL202412010001，航班号：CA1234，出发时间：2024-12-02T08:30:00，到达时间：2024-12-02T10:45:00，座位：12A，票价：580元，请及时支付。",
    "intent": "book_flight",
    "confidence": 0.95,
    "status": "completed",
    "response_type": "api_result",
    "slots": {
      "departure_city": {
        "value": "北京",
        "confidence": 0.98,
        "source": "user_input",
        "normalized_value": "Beijing",
        "extracted_from": "从北京"
      },
      "arrival_city": {
        "value": "上海",
        "confidence": 0.97,
        "source": "user_input",
        "normalized_value": "Shanghai",
        "extracted_from": "到上海"
      },
      "departure_date": {
        "value": "2024-12-02",
        "confidence": 0.90,
        "source": "user_input",
        "normalized_value": "2024-12-02",
        "extracted_from": "明天"
      },
      "seat_class": {
        "value": "经济舱",
        "confidence": 0.95,
        "source": "user_input",
        "normalized_value": "economy",
        "extracted_from": "经济舱"
      },
      "passenger_count": {
        "value": 1,
        "confidence": 0.80,
        "source": "default",
        "normalized_value": 1,
        "extracted_from": "一张"
      }
    },
    "api_result": {
      "order_id": "FL202412010001",
      "flight_number": "CA1234",
      "departure_time": "2024-12-02T08:30:00",
      "arrival_time": "2024-12-02T10:45:00",
      "seat": "12A",
      "price": 580.00,
      "payment_deadline": "2024-12-01T22:00:00Z"
    }
  },
  "timestamp": "2024-12-01T10:00:15Z",
  "request_id": "req_20241201_001",
  "processing_time_ms": 350
}
```

### 2.2 槽位不完整 - 需要补全

#### 用户请求
```json
{
  "user_id": "user456",
  "input": "我想订机票",
  "timestamp": "2024-12-01T10:05:00Z",
  "context": {
    "user_preferences": {
      "frequent_routes": ["北京-上海", "上海-深圳"],
      "preferred_class": "经济舱"
    }
  }
}
```

#### 系统响应
```json
{
  "success": true,
  "code": 200,
  "message": "Success",
  "data": {
    "response": "好的，我来帮您预订机票。根据您的历史记录，您经常飞北京-上海航线，请问这次也是从北京到上海吗？",
    "intent": "book_flight",
    "confidence": 0.92,
    "slots": {
      "departure_city": {
        "value": null,
        "confidence": 0,
        "source": null,
        "required": true,
        "prompt_template": "请告诉我出发城市是哪里？",
        "suggestions": ["北京", "上海", "广州", "深圳"]
      },
      "arrival_city": {
        "value": null,
        "confidence": 0,
        "source": null,
        "required": true,
        "prompt_template": "请告诉我到达城市是哪里？"
      },
      "departure_date": {
        "value": null,
        "confidence": 0,
        "source": null,
        "required": true,
        "prompt_template": "请告诉我出发日期是哪天？"
      }
    },
    "status": "slot_filling",
    "response_type": "slot_prompt",
    "missing_slots": ["departure_city", "arrival_city", "departure_date"],
    "context_suggestions": {
      "based_on_history": true,
      "suggested_route": "北京-上海",
      "confidence": 0.75
    }
  },
  "timestamp": "2024-12-01T10:05:12Z",
  "request_id": "req_20241201_002",
  "processing_time_ms": 180
}
```

## 3. 意图歧义场景

### 3.1 用户输入模糊导致多个候选意图

#### 用户请求
```json
{
  "user_id": "user789",
  "input": "我想订票",
  "context": {
    "user_preferences": {
      "language": "zh-CN"
    }
  }
}
```

#### 系统响应（歧义澄清）
```json
{
  "success": true,
  "code": 200,
  "message": "Success",
  "data": {
    "response": "请问您想要预订哪种票？\n1. 机票\n2. 火车票\n3. 电影票",
    "intent": null,
    "confidence": 0,
    "status": "ambiguous",
    "response_type": "disambiguation",
    "candidate_intents": [
      {
        "intent": "book_flight",
        "confidence": 0.72,
        "display_name": "机票",
        "description": "预订航班机票"
      },
      {
        "intent": "book_train",
        "confidence": 0.68,
        "display_name": "火车票",
        "description": "预订火车票"
      },
      {
        "intent": "book_movie",
        "confidence": 0.65,
        "display_name": "电影票",
        "description": "预订电影票"
      }
    ],
    "missing_slots": [],
    "api_result": {}
  },
  "timestamp": "2024-12-01T10:10:08Z",
  "request_id": "req_20241201_003",
  "processing_time_ms": 200
}
```

### 3.2 用户澄清回复

#### 用户请求
```json
{
  "user_id": "user789",
  "session_id": "sess_20241201_003",
  "input": "机票",
  "timestamp": "2024-12-01T10:12:00Z",
  "context": {
    "disambiguation_id": "amb_20241201_003",
    "awaiting_clarification": true
  }
}
```

#### 系统响应
```json
{
  "success": true,
  "code": 200,
  "message": "Success",
  "data": {
    "response": "好的，预订机票。请告诉我出发城市是哪里？",
    "intent": "book_flight",
    "confidence": 0.95,
    "slots": {
      "departure_city": {
        "value": null,
        "confidence": 0,
        "source": null,
        "required": true,
        "prompt_template": "请告诉我出发城市是哪里？"
      }
    },
    "status": "slot_filling",
    "response_type": "slot_prompt",
    "disambiguation_resolved": true,
    "resolved_intent": "book_flight",
    "resolution_method": "user_choice"
  },
  "timestamp": "2024-12-01T10:12:03Z",
  "request_id": "req_20241201_004",
  "processing_time_ms": 120
}
```

## 4. 意图转移场景

### 4.1 槽位填充过程中的意图转移

#### 用户请求
```json
{
  "user_id": "user123",
  "session_id": "sess_20241201_001",
  "input": "算了，我先查一下余额，卡号是6222080012345678",
  "timestamp": "2024-12-01T10:15:00Z",
  "context": {
    "current_intent": "book_flight",
    "filled_slots": {
      "departure_city": "北京",
      "arrival_city": "上海"
    },
    "awaiting_slot": "departure_date"
  }
}
```

#### 系统响应
```json
{
  "success": true,
  "code": 200,
  "message": "Success",
  "data": {
    "response": "好的，正在为您查询余额...\n您的银行卡余额为：5000元，可用余额：5000元。\n\n是否要继续预订之前的北京到上海的机票？",
    "intent": "check_balance",
    "confidence": 0.88,
    "slots": {
      "card_number": {
        "value": "6222080012345678",
        "confidence": 0.95,
        "source": "user_input",
        "masked_value": "6222****5678"
      }
    },
    "status": "completed",
    "response_type": "intent_transfer_with_completion",
    "intent_transfer": {
      "from": "book_flight",
      "to": "check_balance",
      "transfer_type": "interruption",
      "previous_intent_state": {
        "intent": "book_flight",
        "filled_slots": {
          "departure_city": "北京",
          "arrival_city": "上海"
        },
        "missing_slots": ["departure_date"],
        "saved_at": "2024-12-01T10:15:00Z"
      }
    },
    "api_result": {
      "balance": 5000.00,
      "available_balance": 5000.00,
      "card_type": "储蓄卡",
      "bank_name": "工商银行"
    }
  },
  "timestamp": "2024-12-01T10:15:25Z",
  "request_id": "req_20241201_005",
  "processing_time_ms": 800
}
```

## 5. 打岔场景

### 5.1 闲聊打岔

#### 用户请求
```json
{
  "user_id": "user123",
  "session_id": "sess_20241201_001",
  "input": "今天天气真好啊",
  "timestamp": "2024-12-01T10:20:00Z",
  "context": {
    "current_intent": "book_flight",
    "filled_slots": {
      "departure_city": "北京",
      "arrival_city": "上海"
    },
    "awaiting_slot": "departure_date"
  }
}
```

#### 系统响应
```json
{
  "success": true,
  "code": 200,
  "message": "Success",
  "data": {
    "response": "是的，今天天气确实很不错呢！阳光明媚，很适合出行。\n\n回到我们的机票预订，您想要预订从北京到上海的航班，请告诉我出发日期是哪天？",
    "intent": "small_talk",
    "confidence": 0.85,
    "slots": {},
    "status": "interruption_handled",
    "response_type": "small_talk_with_context_return",
    "interruption_handling": {
      "interruption_type": "small_talk",
      "ragflow_response": "是的，今天天气确实很不错呢！阳光明媚，很适合出行。",
      "context_maintained": true,
      "return_to_intent": "book_flight",
      "return_to_slot": "departure_date"
    }
  },
  "timestamp": "2024-12-01T10:20:08Z",
  "request_id": "req_20241201_006",
  "processing_time_ms": 450
}
```

## 6. 非意图输入 - RAGFLOW处理

### 6.1 完全非意图的输入

#### 用户请求
```json
{
  "user_id": "user999",
  "input": "什么是人工智能的发展历程？",
  "timestamp": "2024-12-01T10:25:00Z",
  "context": {}
}
```

#### 系统响应
```json
{
  "success": true,
  "code": 200,
  "message": "Success",
  "data": {
    "response": "人工智能的发展历程可以追溯到1950年代...\n\n[RAGFLOW详细回答]\n\n您还有什么其他问题吗？如果需要订票、查询余额等服务，我也可以帮助您。",
    "intent": "general_query",
    "confidence": 0.15,
    "slots": {},
    "status": "ragflow_handled",
    "response_type": "ragflow_response",
    "ragflow_processing": {
      "query_type": "knowledge_question",
      "response_confidence": 0.92,
      "response_length": 1200,
      "processing_time_ms": 680
    }
  },
  "timestamp": "2024-12-01T10:25:18Z",
  "request_id": "req_20241201_007",
  "processing_time_ms": 750
}
```

## 7. 错误处理场景

### 7.1 API调用失败

#### 用户请求
```json
{
  "user_id": "user111",
  "session_id": "sess_20241201_005",
  "input": "我要订明天北京到上海的机票",
  "timestamp": "2024-12-01T10:30:00Z",
  "context": {}
}
```

#### 系统响应
```json
{
  "success": true,
  "code": 200,
  "message": "Success",
  "data": {
    "response": "很抱歉，机票预订服务暂时不可用，我们正在努力修复中。请稍后重试或联系客服电话400-123-4567。\n\n您可以先查看其他服务，比如查询余额等。",
    "intent": "book_flight",
    "confidence": 0.93,
    "slots": {
      "departure_city": {
        "value": "北京",
        "confidence": 0.95,
        "source": "user_input"
      },
      "arrival_city": {
        "value": "上海",
        "confidence": 0.94,
        "source": "user_input"
      },
      "departure_date": {
        "value": "2024-12-02",
        "confidence": 0.88,
        "source": "user_input"
      }
    },
    "status": "api_error",
    "response_type": "error_with_alternatives",
    "error_details": {
      "error_type": "api_unavailable",
      "error_code": "SERVICE_TIMEOUT",
      "retry_after": 300,
      "alternative_actions": [
        "查询余额",
        "联系客服",
        "稍后重试"
      ]
    }
  },
  "timestamp": "2024-12-01T10:30:25Z",
  "request_id": "req_20241201_008",
  "processing_time_ms": 5000
}
```

### 7.2 槽位验证失败

#### 用户请求
```json
{
  "user_id": "user222",
  "session_id": "sess_20241201_006",
  "input": "我要从北京到北京的机票",
  "timestamp": "2024-12-01T10:35:00Z",
  "context": {}
}
```

#### 系统响应
```json
{
  "success": true,
  "code": 200,
  "message": "Success",
  "data": {
    "response": "出发城市和到达城市不能相同，请重新告诉我您要去哪个城市？\n\n常见目的地：上海、广州、深圳、成都、西安",
    "intent": "book_flight",
    "confidence": 0.91,
    "slots": {
      "departure_city": {
        "value": "北京",
        "confidence": 0.95,
        "source": "user_input",
        "validation_status": "valid"
      },
      "arrival_city": {
        "value": "北京",
        "confidence": 0.94,
        "source": "user_input",
        "validation_status": "invalid",
        "validation_error": "same_as_departure"
      }
    },
    "status": "validation_error",
    "response_type": "validation_error_prompt",
    "validation_errors": [
      {
        "slot_name": "arrival_city",
        "error_type": "same_as_departure",
        "error_message": "到达城市不能与出发城市相同",
        "suggested_values": ["上海", "广州", "深圳", "成都", "西安"]
      }
    ]
  },
  "timestamp": "2024-12-01T10:35:05Z",
  "request_id": "req_20241201_009",
  "processing_time_ms": 150
}
```

## 8. 复杂场景 - 多意图混合

### 8.1 多意图同时处理

#### 用户请求
```json
{
  "user_id": "user333",
  "session_id": "sess_20241201_007",
  "input": "我想查一下余额然后订机票，卡号是6222080012345678，要从北京到上海",
  "timestamp": "2024-12-01T10:40:00Z",
  "context": {}
}
```

#### 系统响应
```json
{
  "success": true,
  "code": 200,
  "message": "Success",
  "data": {
    "response": "我先为您查询余额，然后帮您预订北京到上海的机票。\n\n您的银行卡余额为：8000元，可用余额：8000元。余额充足，可以进行机票预订。\n\n现在为您预订北京到上海的机票，请告诉我出发日期是哪天？",
    "intent": "multi_intent",
    "confidence": 0.89,
    "processed_intents": [
      {
        "intent": "check_balance",
        "confidence": 0.92,
        "status": "completed",
        "slots": {
          "card_number": {
            "value": "6222080012345678",
            "confidence": 0.98,
            "source": "user_input",
            "masked_value": "6222****5678"
          }
        },
        "api_result": {
          "balance": 8000.00,
          "available_balance": 8000.00
        }
      },
      {
        "intent": "book_flight",
        "confidence": 0.86,
        "status": "slot_filling",
        "slots": {
          "departure_city": {
            "value": "北京",
            "confidence": 0.94,
            "source": "user_input"
          },
          "arrival_city": {
            "value": "上海",
            "confidence": 0.93,
            "source": "user_input"
          },
          "departure_date": {
            "value": null,
            "confidence": 0,
            "source": null,
            "required": true
          }
        }
      }
    ],
    "current_intent": "book_flight",
    "status": "multi_intent_processing",
    "response_type": "multi_intent_with_continuation",
    "missing_slots": ["departure_date"]
  },
  "timestamp": "2024-12-01T10:40:15Z",
  "request_id": "req_20241201_010",
  "processing_time_ms": 950
}
```

## 9. 会话状态查询响应

### 9.1 会话完整状态

#### 系统响应
```json
{
  "success": true,
  "code": 200,
  "message": "Success",
  "data": {
    "user_id": "user123",
    "session_state": "active",
    "current_intent": "book_flight",
    "created_at": "2024-12-01T10:00:00Z",
    "updated_at": "2024-12-01T10:40:00Z",
    "expires_at": "2024-12-02T10:00:00Z",
    "conversation_turns": 8,
    "context": {
      "intent_stack": ["book_flight"],
      "previous_intents": ["check_balance"],
      "user_preferences": {
        "preferred_class": "经济舱",
        "frequent_routes": ["北京-上海"]
      }
    },
    "current_slots": {
      "departure_city": {
        "value": "北京",
        "confidence": 0.95,
        "filled_at": "2024-12-01T10:02:00Z"
      },
      "arrival_city": {
        "value": "上海",
        "confidence": 0.93,
        "filled_at": "2024-12-01T10:03:00Z"
      },
      "departure_date": {
        "value": "2024-12-02",
        "confidence": 0.88,
        "filled_at": "2024-12-01T10:35:00Z"
      }
    },
    "conversation_history": [
      {
        "turn": 1,
        "timestamp": "2024-12-01T10:00:00Z",
        "user_input": "我想订机票",
        "intent": "book_flight",
        "system_response": "好的，请告诉我出发城市是哪里？",
        "response_type": "slot_prompt"
      },
      {
        "turn": 2,
        "timestamp": "2024-12-01T10:02:00Z",
        "user_input": "北京",
        "intent": "book_flight",
        "system_response": "好的，从北京出发。请告诉我到达城市是哪里？",
        "response_type": "slot_prompt"
      }
    ]
  },
  "timestamp": "2024-12-01T10:45:00Z",
  "request_id": "req_20241201_011",
  "processing_time_ms": 50
}
```

## 10. 用户拒答/否定意图处理场景

### 10.1 用户拒绝当前意图

#### 用户请求
```json
{
  "user_id": "user123",
  "session_id": "sess_20241201_001",
  "input": "我不订了",
  "timestamp": "2024-12-01T10:30:00Z",
  "context": {
    "current_intent": "book_flight",
    "filled_slots": {
      "departure_city": "北京",
      "arrival_city": "上海"
    },
    "awaiting_slot": "departure_date"
  }
}
```

#### 系统响应
```json
{
  "success": true,
  "code": 200,
  "message": "Success",
  "data": {
    "response": "好的，已取消机票预订。如果您有其他需要帮助的地方，请随时告诉我。",
    "intent": "cancel_intent",
    "confidence": 0.92,
    "status": "intent_cancelled",
    "response_type": "cancellation_confirmation",
    "cancelled_intent": {
      "intent": "book_flight",
      "filled_slots": {
        "departure_city": "北京",
        "arrival_city": "上海"
      },
      "cancelled_at": "2024-12-01T10:30:00Z"
    },
    "next_suggestions": [
      "查询余额",
      "预订酒店",
      "其他服务"
    ]
  },
  "timestamp": "2024-12-01T10:30:05Z",
  "request_id": "req_20241201_015",
  "processing_time_ms": 120
}
```

### 10.2 用户表达不确定/犹豫

#### 用户请求
```json
{
  "user_id": "user456",
  "session_id": "sess_20241201_002",
  "input": "算了，我再想想",
  "timestamp": "2024-12-01T10:35:00Z",
  "context": {
    "current_intent": "book_hotel",
    "filled_slots": {
      "hotel_city": "上海",
      "check_in_date": "2024-12-02"
    },
    "awaiting_slot": "check_out_date"
  }
}
```

#### 系统响应
```json
{
  "success": true,
  "code": 200,
  "message": "Success",
  "data": {
    "response": "没问题，您可以慢慢考虑。我已经为您保存了酒店预订信息：上海，入住时间2024-12-02。当您确定后随时可以继续完成预订。",
    "intent": "postpone_intent",
    "confidence": 0.88,
    "status": "intent_postponed",
    "response_type": "postponement_with_save",
    "saved_context": {
      "intent": "book_hotel",
      "filled_slots": {
        "hotel_city": "上海",
        "check_in_date": "2024-12-02"
      },
      "saved_at": "2024-12-01T10:35:00Z",
      "expires_at": "2024-12-02T10:35:00Z"
    },
    "resume_suggestions": [
      "继续预订酒店",
      "修改预订信息",
      "查看其他酒店"
    ]
  },
  "timestamp": "2024-12-01T10:35:08Z",
  "request_id": "req_20241201_016",
  "processing_time_ms": 150
}
```

### 10.3 用户明确拒绝系统建议

#### 用户请求
```json
{
  "user_id": "user789",
  "session_id": "sess_20241201_003",
  "input": "不用了，我不需要这个服务",
  "timestamp": "2024-12-01T10:40:00Z",
  "context": {
    "system_suggestion": "根据您的历史记录，推荐预订北京到上海的机票",
    "suggestion_type": "proactive_recommendation"
  }
}
```

#### 系统响应
```json
{
  "success": true,
  "code": 200,
  "message": "Success",
  "data": {
    "response": "好的，我理解您现在不需要这个服务。如果将来有需要，我随时为您提供帮助。还有什么其他我可以协助您的吗？",
    "intent": "reject_suggestion",
    "confidence": 0.90,
    "status": "suggestion_rejected",
    "response_type": "rejection_acknowledgment",
    "rejected_suggestion": {
      "suggestion_type": "proactive_recommendation",
      "suggested_intent": "book_flight",
      "rejected_at": "2024-12-01T10:40:00Z"
    },
    "user_preference_update": {
      "disable_proactive_suggestions": false,
      "suggestion_frequency": "reduced"
    }
  },
  "timestamp": "2024-12-01T10:40:03Z",
  "request_id": "req_20241201_017",
  "processing_time_ms": 80
}
```

## 11. 字段说明和状态对照表

### 11.1 status 和 response_type 字段区分

#### 字段区分说明
- **status**: 表示当前任务/意图的处理状态
- **response_type**: 表示系统的响应行为类型

#### 状态对照表

| status | response_type | 说明 | 示例场景 |
|--------|---------------|------|----------|
| completed | task_completion | 意图识别+执行成功 | 机票预订完成 |
| completed | api_result | API调用成功并返回结果 | 余额查询成功 |
| incomplete | slot_prompt | 槽位不全，继续追问 | 缺少出发日期 |
| ambiguous | disambiguation | 意图歧义澄清 | "我想订票"的歧义 |
| api_error | error_with_alternatives | API调用失败，附带替代方案 | 机票服务不可用 |
| validation_error | validation_error_prompt | 输入参数验证失败 | 出发城市=到达城市 |
| ragflow_handled | qa_response | 知识问答类自由问句处理 | "什么是人工智能" |
| interruption_handled | small_talk_with_context_return | 打岔处理后恢复上下文 | 闲聊后回到订票 |
| multi_intent_processing | multi_intent_with_continuation | 同时处理多个意图 | 查余额+订机票 |
| intent_cancelled | cancellation_confirmation | 用户取消当前意图 | "我不订了" |
| intent_postponed | postponement_with_save | 用户延迟决定，保存上下文 | "算了，我再想想" |
| suggestion_rejected | rejection_acknowledgment | 用户拒绝系统建议 | "不用了，我不需要" |
| intent_transfer | intent_transfer_with_completion | 意图转移并完成新意图 | 订票中途查余额 |
| slot_filling | slot_prompt | 正在填充槽位 | 询问出发城市 |
| context_maintained | context_continuation | 维持上下文继续对话 | 多轮对话中 |

### 11.2 响应类型详细说明

#### 11.2.1 任务完成类响应
```json
{
  "status": "completed",
  "response_type": "task_completion",
  "description": "意图识别成功，所有槽位完整，API调用成功"
}
```

#### 11.2.2 槽位填充类响应
```json
{
  "status": "incomplete", 
  "response_type": "slot_prompt",
  "description": "意图识别成功，但槽位不完整，需要用户补充信息"
}
```

#### 11.2.3 歧义处理类响应
```json
{
  "status": "ambiguous",
  "response_type": "disambiguation", 
  "description": "用户输入存在多个可能的意图，需要用户澄清"
}
```

#### 11.2.4 错误处理类响应
```json
{
  "status": "api_error",
  "response_type": "error_with_alternatives",
  "description": "API调用失败，提供备选方案"
}
```

#### 11.2.5 打岔处理类响应
```json
{
  "status": "interruption_handled",
  "response_type": "small_talk_with_context_return",
  "description": "处理用户打岔（如闲聊），然后返回原始上下文"
}
```

## 12. 字段说明表

### 12.1 请求字段说明

| 字段名 | 类型 | 必填 | 默认值 | 示例值 | 说明 |
|--------|------|------|--------|--------|------|
| user_id | string | 是 | - | "user123" | 用户唯一标识符 |
| input | string | 是 | - | "我想订机票" | 用户输入的文本内容 |
| session_id | string | 否 | null | "sess_20241201_001" | 会话标识符，用于多轮对话 |
| timestamp | string | 否 | 当前时间 | "2024-12-01T10:00:00Z" | 请求时间戳，ISO 8601格式 |
| context | object | 否 | {} | 见context字段说明 | 请求上下文信息 |
| context.device_info | object | 否 | {} | {"platform": "web"} | 设备信息 |
| context.location | object | 否 | {} | {"city": "北京"} | 位置信息 |
| context.user_preferences | object | 否 | {} | {"language": "zh-CN"} | 用户偏好设置 |
| context.current_intent | string | 否 | null | "book_flight" | 当前进行中的意图 |
| context.filled_slots | object | 否 | {} | {"departure_city": "北京"} | 已填充的槽位信息 |
| context.awaiting_slot | string | 否 | null | "departure_date" | 等待填充的槽位 |

### 12.2 响应字段说明

| 字段名 | 类型 | 必填 | 默认值 | 示例值 | 说明 |
|--------|------|------|--------|--------|------|
| success | boolean | 是 | - | true | 请求是否成功处理 |
| code | integer | 是 | - | 200 | HTTP状态码 |
| message | string | 是 | - | "Success" | 状态码描述信息 |
| data | object | 是 | - | 见data字段说明 | 业务数据 |
| timestamp | string | 是 | - | "2024-12-01T10:00:00Z" | 响应时间戳 |
| request_id | string | 是 | - | "req_20241201_001" | 请求唯一标识符 |

### 12.3 data字段说明

| 字段名 | 类型 | 必填 | 默认值 | 示例值 | 说明 |
|--------|------|------|--------|--------|------|
| response | string | 是 | - | "好的，请告诉我出发城市" | 系统响应文本 |
| intent | string | 否 | null | "book_flight" | 识别到的意图名称 |
| confidence | number | 否 | 0.0 | 0.95 | 意图识别置信度，0.0-1.0 |
| status | string | 是 | - | "completed" | 处理状态，见状态对照表 |
| response_type | string | 是 | - | "task_completion" | 响应类型，见状态对照表 |
| slots | object | 否 | {} | 见slots字段说明 | 槽位信息 |
| missing_slots | array | 否 | [] | ["departure_date"] | 缺失的必需槽位列表 |
| api_result | object | 否 | {} | 见api_result字段说明 | API调用结果 |
| candidate_intents | array | 否 | [] | 见candidate_intents说明 | 候选意图列表(歧义时) |
| processing_time_ms | integer | 否 | 0 | 250 | 处理耗时，毫秒 |

### 12.4 slots字段说明

| 字段名 | 类型 | 必填 | 默认值 | 示例值 | 说明 |
|--------|------|------|--------|--------|------|
| value | any | 是 | - | "北京" | 槽位值 |
| confidence | number | 是 | - | 0.95 | 提取置信度，0.0-1.0 |
| source | string | 是 | - | "user_input" | 槽位来源：user_input/context/default |
| normalized_value | any | 否 | null | "Beijing" | 标准化后的槽位值 |
| extracted_from | string | 否 | null | "从北京" | 从用户输入中提取的原始文本 |
| validation_status | string | 否 | "valid" | "valid" | 验证状态：valid/invalid/pending |
| validation_error | string | 否 | null | "same_as_departure" | 验证错误代码 |
| required | boolean | 否 | false | true | 是否为必需槽位 |
| prompt_template | string | 否 | null | "请告诉我出发城市" | 槽位提示模板 |

### 12.5 api_result字段说明

| 字段名 | 类型 | 必填 | 默认值 | 示例值 | 说明 |
|--------|------|------|--------|--------|------|
| success | boolean | 是 | - | true | API调用是否成功 |
| data | object | 否 | {} | 见具体API返回 | API返回的业务数据 |
| error_code | string | 否 | null | "SERVICE_TIMEOUT" | API错误代码 |
| error_message | string | 否 | null | "服务超时" | API错误消息 |
| retry_count | integer | 否 | 0 | 1 | 重试次数 |
| api_response_time | integer | 否 | 0 | 1500 | API响应时间，毫秒 |

### 12.6 candidate_intents字段说明

| 字段名 | 类型 | 必填 | 默认值 | 示例值 | 说明 |
|--------|------|------|--------|--------|------|
| intent | string | 是 | - | "book_flight" | 候选意图名称 |
| confidence | number | 是 | - | 0.85 | 候选意图置信度 |
| display_name | string | 否 | null | "机票预订" | 候选意图显示名称 |
| description | string | 否 | null | "预订航班机票" | 候选意图描述 |
| priority | integer | 否 | 0 | 10 | 候选意图优先级 |

## 13. 错误码表

### 13.1 HTTP状态码说明

| 状态码 | 名称 | 业务含义 | 解决方案 |
|--------|------|----------|----------|
| 200 | OK | 请求成功处理 | 正常响应 |
| 400 | Bad Request | 请求参数错误 | 检查请求参数格式和必填字段 |
| 401 | Unauthorized | 未授权访问 | 提供有效的JWT Token或API Key |
| 403 | Forbidden | 权限不足 | 检查用户权限或联系管理员 |
| 404 | Not Found | 资源不存在 | 检查请求路径或资源ID |
| 422 | Unprocessable Entity | 业务逻辑错误 | 检查业务参数和依赖关系 |
| 429 | Too Many Requests | 请求频率限制 | 降低请求频率或联系管理员提升配额 |
| 500 | Internal Server Error | 服务器内部错误 | 联系技术支持或稍后重试 |
| 503 | Service Unavailable | 服务不可用 | 稍后重试或联系技术支持 |

### 13.2 业务错误码说明

| 错误码 | 错误类型 | 说明 | 解决方案 |
|--------|----------|------|----------|
| INTENT_NOT_FOUND | 意图识别错误 | 无法识别用户意图 | 重新表述或联系人工客服 |
| SLOT_VALIDATION_FAILED | 槽位验证错误 | 槽位值验证失败 | 提供正确的槽位值 |
| API_CALL_FAILED | 外部API错误 | 外部API调用失败 | 稍后重试或选择其他服务 |
| SERVICE_TIMEOUT | 服务超时 | 外部服务响应超时 | 稍后重试 |
| INSUFFICIENT_SLOTS | 槽位不足 | 必需槽位未填充完整 | 提供缺失的必需信息 |
| AMBIGUOUS_INTENT | 意图歧义 | 多个候选意图置信度相近 | 明确指定具体意图 |
| RATE_LIMIT_EXCEEDED | 频率限制 | 超过请求频率限制 | 降低请求频率 |
| CONTEXT_EXPIRED | 上下文过期 | 会话上下文已过期 | 重新开始对话 |
| VALIDATION_ERROR | 输入验证错误 | 输入参数不符合要求 | 检查输入格式和内容 |
| PERMISSION_DENIED | 权限拒绝 | 用户权限不足 | 联系管理员或升级权限 |

## 14. 响应体大小和分页指南

### 14.1 响应体大小限制

| 响应类型 | 建议大小 | 最大大小 | 说明 |
|----------|----------|----------|------|
| 标准响应 | < 5KB | 50KB | 普通意图识别响应 |
| 槽位提示 | < 2KB | 10KB | 槽位填充提示响应 |
| 歧义澄清 | < 3KB | 15KB | 意图歧义澄清响应 |
| API结果 | < 10KB | 100KB | 外部API调用结果 |
| 对话历史 | < 20KB | 200KB | 会话历史记录 |
| 系统监控 | < 50KB | 500KB | 系统性能监控数据 |

### 14.2 分页字段说明

| 字段名 | 类型 | 必填 | 默认值 | 示例值 | 说明 |
|--------|------|------|--------|--------|------|
| page | integer | 否 | 1 | 1 | 页码，从1开始 |
| size | integer | 否 | 10 | 20 | 每页记录数 |
| total | integer | 是 | - | 150 | 总记录数 |
| pages | integer | 是 | - | 8 | 总页数 |
| has_next | boolean | 是 | - | true | 是否有下一页 |
| has_prev | boolean | 是 | - | false | 是否有上一页 |

### 14.3 分页响应示例

```json
{
  "success": true,
  "code": 200,
  "message": "Success",
  "data": {
    "items": [
      {
        "conversation_id": 12345,
        "user_input": "我想订机票",
        "intent": "book_flight",
        "timestamp": "2024-12-01T10:00:00Z"
      }
    ],
    "pagination": {
      "page": 1,
      "size": 10,
      "total": 150,
      "pages": 15,
      "has_next": true,
      "has_prev": false
    }
  },
  "timestamp": "2024-12-01T10:00:00Z",
  "request_id": "req_20241201_001"
}
```

### 14.4 大数据量处理建议

1. **流式传输**: 对于大量数据，建议使用流式传输
2. **数据压缩**: 启用gzip压缩减少传输大小
3. **字段过滤**: 支持字段选择，只返回必需字段
4. **缓存策略**: 对频繁访问的数据启用缓存
5. **异步处理**: 大型任务使用异步处理，返回任务ID
6. **任务监控**: 支持实时查询任务进度和状态
7. **错误恢复**: 自动重试机制和详细的错误日志
8. **批量处理**: 支持批量操作提高效率
9. **任务取消**: 支持用户主动取消正在执行的任务
10. **RAGFLOW集成**: 无缝集成RAGFLOW处理非意图输入

## 15. 系统监控数据结构

### 15.1 性能监控响应

#### 系统响应
```json
{
  "success": true,
  "code": 200,
  "message": "Success",
  "data": {
    "system_health": {
      "status": "healthy",
      "uptime": "99.9%",
      "last_check": "2024-12-01T10:45:00Z"
    },
    "performance_metrics": {
      "avg_response_time": 245,
      "p95_response_time": 800,
      "p99_response_time": 1200,
      "requests_per_second": 150,
      "error_rate": 0.02,
      "cache_hit_rate": 0.85
    },
    "intent_statistics": {
      "total_requests": 12450,
      "successful_recognitions": 11823,
      "ambiguous_cases": 327,
      "fallback_cases": 300,
      "intent_distribution": {
        "book_flight": 4500,
        "check_balance": 3200,
        "book_hotel": 1800,
        "other": 2950
      }
    },
    "resource_usage": {
      "cpu_usage": 0.65,
      "memory_usage": 0.72,
      "disk_usage": 0.45,
      "network_io": 0.38
    }
  },
  "timestamp": "2024-12-01T10:45:00Z",
  "request_id": "req_20241201_012",
  "processing_time_ms": 25
}
```

## 16. 异步任务处理场景

### 16.1 创建异步任务

#### 用户请求
```json
{
  "task_type": "api_call",
  "conversation_id": 12345,
  "user_id": "user123",
  "request_data": {
    "function_name": "book_flight_api",
    "params": {
      "departure_city": "北京",
      "arrival_city": "上海",
      "departure_date": "2024-12-02",
      "passenger_count": 1,
      "seat_class": "经济舱"
    }
  },
  "priority": "normal",
  "estimated_duration_seconds": 30
}
```

#### 系统响应
```json
{
  "success": true,
  "code": 201,
  "message": "Async task created successfully",
  "data": {
    "task_id": "task_20241201_001",
    "status": "pending",
    "estimated_completion": "2024-12-01T10:08:00Z",
    "created_at": "2024-12-01T10:05:00Z",
    "polling_url": "/api/v1/tasks/async/task_20241201_001",
    "webhook_url": null
  },
  "timestamp": "2024-12-01T10:05:00Z",
  "request_id": "req_20241201_013",
  "processing_time_ms": 50
}
```

### 16.2 查询异步任务状态

#### 任务进行中
```json
{
  "success": true,
  "code": 200,
  "message": "Task in progress",
  "data": {
    "task_id": "task_20241201_001",
    "task_type": "api_call",
    "status": "processing",
    "progress": 65.5,
    "estimated_completion": "2024-12-01T10:08:00Z",
    "created_at": "2024-12-01T10:05:00Z",
    "updated_at": "2024-12-01T10:06:30Z",
    "result_data": null,
    "error_message": null,
    "retry_count": 0,
    "max_retries": 3,
    "logs": [
      {
        "timestamp": "2024-12-01T10:05:00Z",
        "level": "INFO",
        "message": "Task started"
      },
      {
        "timestamp": "2024-12-01T10:06:00Z",
        "level": "INFO",
        "message": "API call initiated"
      },
      {
        "timestamp": "2024-12-01T10:06:30Z",
        "level": "INFO",
        "message": "Processing flight search results"
      }
    ]
  },
  "timestamp": "2024-12-01T10:06:45Z",
  "request_id": "req_20241201_014",
  "processing_time_ms": 15
}
```

#### 任务完成
```json
{
  "success": true,
  "code": 200,
  "message": "Task completed successfully",
  "data": {
    "task_id": "task_20241201_001",
    "task_type": "api_call",
    "status": "completed",
    "progress": 100.0,
    "created_at": "2024-12-01T10:05:00Z",
    "updated_at": "2024-12-01T10:07:24Z",
    "completed_at": "2024-12-01T10:07:24Z",
    "processing_time_ms": 144000,
    "result_data": {
      "success": true,
      "order_id": "FL202412010001",
      "flight_number": "CA1234",
      "departure_time": "2024-12-02T08:30:00",
      "arrival_time": "2024-12-02T10:45:00",
      "seat": "12A",
      "price": 580.00,
      "payment_deadline": "2024-12-01T22:00:00Z",
      "confirmation_code": "ABC123DEF"
    },
    "error_message": null,
    "retry_count": 0,
    "notification_sent": true
  },
  "timestamp": "2024-12-01T10:07:25Z",
  "request_id": "req_20241201_015",
  "processing_time_ms": 12
}
```

### 16.3 异步任务失败

#### 系统响应
```json
{
  "success": true,
  "code": 200,
  "message": "Task failed",
  "data": {
    "task_id": "task_20241201_002",
    "task_type": "api_call",
    "status": "failed",
    "progress": 30.0,
    "created_at": "2024-12-01T10:10:00Z",
    "updated_at": "2024-12-01T10:12:30Z",
    "failed_at": "2024-12-01T10:12:30Z",
    "processing_time_ms": 150000,
    "result_data": null,
    "error_message": "External API timeout after 3 retry attempts",
    "error_code": "API_TIMEOUT",
    "retry_count": 3,
    "max_retries": 3,
    "failure_reason": "外部API调用超时，已达到最大重试次数",
    "logs": [
      {
        "timestamp": "2024-12-01T10:10:00Z",
        "level": "INFO",
        "message": "Task started"
      },
      {
        "timestamp": "2024-12-01T10:10:30Z",
        "level": "ERROR",
        "message": "API call timeout, retrying (1/3)"
      },
      {
        "timestamp": "2024-12-01T10:11:30Z",
        "level": "ERROR",
        "message": "API call timeout, retrying (2/3)"
      },
      {
        "timestamp": "2024-12-01T10:12:30Z",
        "level": "ERROR",
        "message": "API call timeout, max retries reached"
      }
    ]
  },
  "timestamp": "2024-12-01T10:12:31Z",
  "request_id": "req_20241201_016",
  "processing_time_ms": 8
}
```

### 16.4 RAGFLOW异步调用

#### 创建RAGFLOW异步任务
```json
{
  "task_type": "ragflow_call",
  "conversation_id": 12346,
  "user_id": "user456",
  "request_data": {
    "input_text": "今天天气真好啊，不过我还是想了解一下你们的服务",
    "context": {
      "previous_intents": ["book_flight"],
      "conversation_history": [
        "我想订机票",
        "请告诉我出发城市",
        "今天天气真好啊"
      ]
    },
    "fallback_config": {
      "enable_context_return": true,
      "max_response_length": 200
    }
  },
  "priority": "low"
}
```

#### RAGFLOW任务完成响应
```json
{
  "success": true,
  "code": 200,
  "message": "RAGFLOW task completed",
  "data": {
    "task_id": "task_20241201_003",
    "task_type": "ragflow_call",
    "status": "completed",
    "progress": 100.0,
    "created_at": "2024-12-01T10:15:00Z",
    "completed_at": "2024-12-01T10:15:08Z",
    "processing_time_ms": 8000,
    "result_data": {
      "ragflow_response": "是的，今天确实是个好天气！😊 不过我们还是回到刚才的话题吧，您刚才想要预订机票，请告诉我出发城市是哪里？",
      "response_type": "small_talk_with_context_return",
      "confidence": 0.92,
      "context_maintained": true,
      "fallback_used": false,
      "suggested_next_action": "continue_slot_filling",
      "ragflow_metadata": {
        "model_used": "gpt-3.5-turbo",
        "tokens_used": 150,
        "processing_time_ms": 750
      }
    },
    "error_message": null
  },
  "timestamp": "2024-12-01T10:15:08Z",
  "request_id": "req_20241201_017",
  "processing_time_ms": 10
}
```

### 16.5 批量任务处理

#### 用户请求（批量查询航班）
```json
{
  "task_type": "batch_process",
  "user_id": "user789",
  "request_data": {
    "batch_type": "flight_search",
    "queries": [
      {
        "departure_city": "北京",
        "arrival_city": "上海",
        "departure_date": "2024-12-02"
      },
      {
        "departure_city": "北京",
        "arrival_city": "广州",
        "departure_date": "2024-12-02"
      },
      {
        "departure_city": "北京",
        "arrival_city": "深圳",
        "departure_date": "2024-12-02"
      }
    ]
  },
  "priority": "normal"
}
```

#### 批量任务完成响应
```json
{
  "success": true,
  "code": 200,
  "message": "Batch task completed",
  "data": {
    "task_id": "task_20241201_004",
    "task_type": "batch_process",
    "status": "completed",
    "progress": 100.0,
    "created_at": "2024-12-01T10:20:00Z",
    "completed_at": "2024-12-01T10:22:45Z",
    "processing_time_ms": 165000,
    "result_data": {
      "total_queries": 3,
      "successful_queries": 3,
      "failed_queries": 0,
      "results": [
        {
          "query_index": 0,
          "route": "北京-上海",
          "status": "success",
          "flights": [
            {
              "flight_number": "CA1234",
              "price": 580.00,
              "departure_time": "08:30"
            },
            {
              "flight_number": "MU5678",
              "price": 620.00,
              "departure_time": "10:15"
            }
          ]
        },
        {
          "query_index": 1,
          "route": "北京-广州",
          "status": "success",
          "flights": [
            {
              "flight_number": "CZ9999",
              "price": 890.00,
              "departure_time": "07:45"
            }
          ]
        },
        {
          "query_index": 2,
          "route": "北京-深圳",
          "status": "success",
          "flights": [
            {
              "flight_number": "ZH1111",
              "price": 950.00,
              "departure_time": "09:20"
            }
          ]
        }
      ],
      "summary": {
        "cheapest_route": "北京-上海",
        "cheapest_price": 580.00,
        "total_options": 5
      }
    },
    "error_message": null
  },
  "timestamp": "2024-12-01T10:22:46Z",
  "request_id": "req_20241201_018",
  "processing_time_ms": 15
}
```

### 16.6 异步任务取消

#### 取消请求
```json
{
  "task_id": "task_20241201_005",
  "cancel_reason": "User requested cancellation"
}
```

#### 取消响应
```json
{
  "success": true,
  "code": 200,
  "message": "Task cancelled successfully",
  "data": {
    "task_id": "task_20241201_005",
    "status": "cancelled",
    "cancelled_at": "2024-12-01T10:25:00Z",
    "cancel_reason": "User requested cancellation",
    "progress_at_cancellation": 45.0,
    "partial_results": {
      "completed_steps": [
        "validation",
        "api_preparation"
      ],
      "cancelled_step": "api_execution",
      "cleanup_performed": true
    }
  },
  "timestamp": "2024-12-01T10:25:01Z",
  "request_id": "req_20241201_019",
  "processing_time_ms": 25
}
```