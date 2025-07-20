# 意图识别系统流程图

## 流程图优化说明

本流程图基于专业评审建议进行了系统性优化，提升了准确性、可读性和专业性。主要优化包括：

### 优化要点
- **决策逻辑优化**: 将分散的判断条件合并为统一的决策节点，提升逻辑清晰度
- **上下文恢复机制**: 明确展示B2B无状态设计下的完整上下文恢复流程
- **视觉规范标准化**: 建立统一的色彩规范体系，提升文档专业性
- **规则精确表达**: 意图转移和打岔处理规则从分散变为集中精确表达

### 技术价值体现
- **理解门槛降低**: 更直观的流程表达减少学习成本
- **实现指导性强**: 精确的规则描述指导代码实现  
- **沟通效率提升**: 标准化的视觉语言促进团队沟通
- **设计理念体现**: 更好地展现了B2B无状态架构特点

## 流程图色彩规范

为保证流程图的一致性和可读性，采用以下标准化色彩方案：

- **蓝色 (#e1f5fe)**: 外部输入和起始节点
- **黄色 (#fff3e0)**: 警告或需要特殊处理的中间状态（如意图转移、歧义处理）
- **橙色 (#ffeb3b)**: 重要状态变更或关键决策点
- **紫色 (#f3e5f5)**: 外部系统调用（RAGFLOW、业务API）
- **绿色 (#e8f5e8)**: 成功或最终输出状态
- **红色 (#ffebee)**: 错误或失败路径

## 1. 无状态意图识别系统流程

```mermaid
graph TB
    A[用户输入] --> B[请求预处理模块]
    B --> C[加载配置和用户上下文]
    C --> D[意图识别模块]
    D --> E[置信度评估]
    E --> F{是否歧义}
    F -->|有歧义| G[歧义处理模块]
    F -->|无歧义| H[槽位提取模块]
    G --> I[生成澄清问题]
    I --> J[返回澄清响应]
    H --> K{槽位完整性检查}
    K -->|不完整| L[生成补全提示]
    L --> M[返回补全响应]
    K -->|完整| N[业务规则验证]
    N --> O{验证通过}
    O -->|不通过| P[错误处理]
    P --> Q[返回错误响应]
    O -->|通过| R[API调用模块]
    R --> S{API调用成功}
    S -->|失败| T[重试机制]
    T --> U{重试次数检查}
    U -->|未超限| R
    U -->|超限| V[返回错误响应]
    S -->|成功| W[格式化响应]
    W --> X[返回结果]
    
    %% 处理非意图输入
    D --> Y{意图识别成功}
    Y -->|失败| Z[RAGFLOW处理]
    Z --> AA[返回闲聊响应]
    
    style A fill:#e1f5fe
    style X fill:#e8f5e8
    style Z fill:#f3e5f5
    style AA fill:#e8f5e8
    style H fill:#fff3e0
    style G fill:#fff3e0
    style P fill:#ffebee
    style V fill:#ffebee
```

## 2. 意图识别详细流程

```mermaid
graph TB
    A[用户输入] --> B[文本预处理]
    B --> C[实体预提取]
    C --> D[意图识别引擎]
    D --> E[LLM推理]
    E --> F[置信度计算]
    F --> G{置信度 >= 阈值}
    G -->|否| H[调用RAGFLOW]
    G -->|是| I[候选意图排序]
    I --> J{多个候选意图}
    J -->|否| K[单意图确认]
    J -->|是| L[歧义检测]
    L --> M{置信度差值 < 0.1}
    M -->|是| N[生成歧义澄清]
    M -->|否| O[选择最高置信度]
    K --> P[意图确认完成]
    O --> P
    N --> Q[用户澄清选择]
    Q --> R[解析用户选择]
    R --> S{选择有效}
    S -->|是| P
    S -->|否| T[重新询问]
    T --> Q
    H --> U[RAGFLOW响应]
    U --> V[返回对话结果]
    P --> W[进入槽位处理]
    
    style A fill:#e1f5fe
    style H fill:#f3e5f5
    style N fill:#fff3e0
    style U fill:#f3e5f5
    style V fill:#e8f5e8
    style W fill:#e8f5e8
```

## 3. 槽位填充流程

```mermaid
graph TB
    A[意图确认] --> B[加载槽位配置]
    B --> C[从输入提取槽位]
    C --> D[Duckling实体标准化]
    D --> E[槽位验证]
    E --> F[必填槽位检查]
    F --> G{有缺失必填槽位}
    G -->|是| H[生成槽位询问]
    G -->|否| I[可选槽位检查]
    I --> J[槽位依赖关系验证]
    J --> K{验证通过}
    K -->|否| L[生成错误提示]
    K -->|是| M[槽位完整性确认]
    H --> N[等待用户输入]
    N --> O[解析用户回复]
    O --> P{输入有效}
    P -->|否| Q[重新询问]
    P -->|是| R[更新槽位值]
    R --> S[增量槽位验证]
    S --> F
    Q --> N
    L --> T[返回错误响应]
    M --> U[准备API调用]
    
    style A fill:#e1f5fe
    style H fill:#fff3e0
    style L fill:#ffebee
    style T fill:#ffebee
    style U fill:#e8f5e8
```

## 4. 意图转移和打岔处理流程

```mermaid
graph TB
    A[用户新输入] --> B[当前意图上下文]
    B --> C[新意图识别]
    C --> D[评估意图转移规则]
    D --> E{意图转移决策}
    E -->|意图转移| F[保存当前意图状态]
    E -->|打岔处理| G[打岔类型分析]
    E -->|保持当前| H[继续当前意图处理]
    
    F --> I[切换到新意图]
    I --> J[新意图处理]
    
    G --> K{打岔类型}
    K -->|闲聊| L[调用RAGFLOW]
    K -->|信息查询| M[调用RAGFLOW + 保持上下文]
    K -->|系统指令| N[执行系统指令]
    
    L --> O[返回闲聊回复]
    M --> P[返回信息回复 + 引导回原意图]
    N --> Q[返回指令执行结果]
    H --> R[当前意图继续]
    J --> S[新意图处理完成]
    
    O --> T[可选：引导回原意图]
    P --> U[等待用户继续]
    Q --> V[等待用户继续]
    R --> W[更新会话状态]
    S --> W
    
    T --> X[用户选择]
    U --> X
    V --> X
    W --> Y[处理完成]
    
    X --> Z{用户选择}
    Z -->|回到原意图| AA[恢复原意图状态]
    Z -->|新的输入| A
    AA --> BB[继续原意图处理]
    BB --> W
    
    style A fill:#e1f5fe
    style D fill:#fff3e0
    style G fill:#fff3e0
    style F fill:#ffeb3b
    style I fill:#ffeb3b
    style L fill:#f3e5f5
    style M fill:#f3e5f5
    style O fill:#e8f5e8
    style P fill:#e8f5e8
    style Q fill:#e8f5e8
    style Y fill:#e8f5e8
```

### 意图转移决策规则说明

**[评估意图转移规则]** 节点实现的复合判断逻辑：

1. **意图转移条件**: 
   - 新意图置信度 > 0.7 
   - 且 新意图置信度 > 当前意图置信度 + 0.1
   - 且 新意图与当前意图不同

2. **打岔处理条件**:
   - 新意图置信度 < 0.7
   - 或 新意图置信度 <= 当前意图置信度 + 0.1

3. **保持当前条件**:
   - 新意图与当前意图相同
   - 或 无明确的新意图识别结果

这种设计确保了意图转移的准确性，同时提供了灵活的打岔处理机制。

## 5. 上下文管理流程

```mermaid
graph TB
    A[会话开始] --> B[创建会话上下文]
    B --> C[加载用户历史偏好]
    C --> D[初始化意图栈]
    D --> E[接收用户输入]
    E --> F[加载/恢复会话上下文]
    F --> G[恢复意图栈状态]
    G --> H[恢复槽位填充进度]
    H --> I[处理用户输入]
    I --> J[更新对话轮次]
    J --> K[意图识别处理]
    K --> L{意图类型}
    L -->|新意图| M[推入意图栈]
    L -->|继续当前意图| N[更新当前意图状态]
    L -->|意图转移| O[意图栈操作]
    M --> P[保存意图上下文]
    N --> Q[更新槽位上下文]
    O --> R{转移类型}
    R -->|完全转移| S[清空栈并推入新意图]
    R -->|嵌套处理| T[推入新意图保持栈]
    R -->|返回上级| U[弹出当前意图]
    P --> V[上下文持久化]
    Q --> V
    S --> V
    T --> V
    U --> V
    V --> W[Redis缓存更新]
    W --> X[数据库同步]
    X --> Y[继续处理]
    Y --> Z{会话状态}
    Z -->|活跃| E
    Z -->|完成| AA[清理临时上下文]
    Z -->|超时| BB[标记会话过期]
    AA --> CC[保存会话历史]
    BB --> DD[清理过期数据]
    CC --> EE[会话结束]
    DD --> EE
    
    style A fill:#e1f5fe
    style E fill:#e1f5fe
    style F fill:#fff3e0
    style G fill:#fff3e0
    style H fill:#fff3e0
    style M fill:#ffeb3b
    style O fill:#ffeb3b
    style V fill:#e8f5e8
    style W fill:#e8f5e8
    style EE fill:#e8f5e8
```

## 6. API调用处理流程

```mermaid
graph TB
    A[槽位验证完成] --> B[加载Function Call配置]
    B --> C[参数映射]
    C --> D[前置条件检查]
    D --> E{检查通过}
    E -->|否| F[返回错误信息]
    E -->|是| G[构建API请求]
    G --> H[发送API请求]
    H --> I[设置超时控制]
    I --> J{请求状态}
    J -->|超时| K[超时处理]
    J -->|成功| L[解析响应]
    J -->|失败| M[错误处理]
    K --> N{重试次数 < 上限}
    M --> N
    N -->|是| O[等待重试间隔]
    N -->|否| P[标记最终失败]
    O --> G
    L --> Q{响应格式正确}
    Q -->|否| R[响应格式错误]
    Q -->|是| S[业务逻辑验证]
    S --> T{业务验证通过}
    T -->|否| U[业务错误处理]
    T -->|是| V[格式化成功响应]
    F --> W[生成错误响应]
    P --> X[生成失败响应]
    R --> Y[生成格式错误响应]
    U --> Z[生成业务错误响应]
    V --> AA[更新会话状态]
    W --> BB[记录错误日志]
    X --> BB
    Y --> BB
    Z --> BB
    AA --> CC[返回用户]
    BB --> CC
    
    style A fill:#e1f5fe
    style G fill:#e8f5e8
    style H fill:#e8f5e8
    style V fill:#e8f5e8
    style F fill:#ffebee
    style P fill:#ffebee
    style R fill:#ffebee
    style U fill:#ffebee
```

## 7. 错误处理和恢复流程

```mermaid
graph TB
    A[错误发生] --> B[错误类型识别]
    B --> C{错误类型}
    C -->|意图识别失败| D[低置信度处理]
    C -->|槽位验证失败| E[槽位错误处理]
    C -->|API调用失败| F[API错误处理]
    C -->|系统错误| G[系统错误处理]
    D --> H[调用RAGFLOW]
    E --> I[生成重新询问]
    F --> J[重试机制]
    G --> K[错误日志记录]
    H --> L[RAGFLOW响应]
    I --> M[用户重新输入]
    J --> N{重试成功}
    K --> O[系统错误响应]
    L --> P[返回RAGFLOW回复]
    M --> Q[重新槽位验证]
    N -->|是| R[继续正常流程]
    N -->|否| S[标记API不可用]
    O --> T[通知系统管理员]
    P --> U[更新会话状态]
    Q --> V{验证通过}
    R --> W[更新会话状态]
    S --> X[返回服务不可用]
    T --> Y[降级处理]
    U --> Z[等待用户输入]
    V -->|是| AA[继续处理]
    V -->|否| BB[再次询问]
    W --> CC[返回用户]
    X --> CC
    Y --> CC
    Z --> DD[用户响应]
    AA --> CC
    BB --> EE[生成新的询问]
    DD --> FF[新输入处理]
    EE --> GG[等待用户输入]
    FF --> HH[重新进入主流程]
    GG --> II[用户重新输入]
    II --> JJ[重新处理]
    
    style A fill:#ffebee
    style B fill:#ffebee
    style D fill:#fff3e0
    style E fill:#fff3e0
    style F fill:#fff3e0
    style G fill:#ffebee
    style K fill:#ffebee
    style T fill:#ffebee
```

## 8. 性能优化流程

```mermaid
graph TB
    A[请求到达] --> B[负载均衡]
    B --> C[缓存检查]
    C --> D{缓存命中}
    D -->|命中| E[返回缓存结果]
    D -->|未命中| F[异步处理队列]
    F --> G[并发限制检查]
    G --> H{并发限制}
    H -->|超限| I[请求排队]
    H -->|未超限| J[分配处理资源]
    I --> K[队列等待]
    J --> L[NLU处理]
    L --> M[结果缓存]
    M --> N[响应生成]
    K --> O{队列超时}
    O -->|是| P[返回超时错误]
    O -->|否| Q[重新检查并发]
    E --> R[性能监控]
    N --> S[更新缓存]
    P --> T[错误统计]
    Q --> H
    R --> U[响应用户]
    S --> V[性能统计]
    T --> W[系统告警]
    U --> X[记录访问日志]
    V --> Y[自动扩缩容]
    W --> Z[管理员通知]
    X --> AA[请求完成]
    Y --> BB[资源调整]
    Z --> CC[系统维护]
    
    style A fill:#e1f5fe
    style E fill:#e8f5e8
    style I fill:#fff3e0
    style P fill:#ffebee
    style T fill:#ffebee
    style W fill:#ffebee
    style Y fill:#f3e5f5
    style BB fill:#f3e5f5
```

## 9. 系统监控流程

```mermaid
graph TB
    A[系统运行] --> B[实时监控]
    B --> C[指标采集]
    C --> D[数据分析]
    D --> E{异常检测}
    E -->|正常| F[继续监控]
    E -->|异常| G[告警触发]
    G --> H[告警分级]
    H --> I{告警级别}
    I -->|低级| J[日志记录]
    I -->|中级| K[通知管理员]
    I -->|高级| L[自动处理]
    J --> M[趋势分析]
    K --> N[人工干预]
    L --> O[自动恢复]
    M --> P[报告生成]
    N --> Q[问题解决]
    O --> R{恢复成功}
    R -->|是| S[恢复确认]
    R -->|否| T[升级告警]
    P --> U[优化建议]
    Q --> V[系统更新]
    S --> W[监控继续]
    T --> X[紧急处理]
    U --> Y[性能优化]
    V --> Z[配置更新]
    W --> F
    X --> AA[系统维护]
    Y --> BB[系统升级]
    Z --> CC[热更新]
    
    style A fill:#e1f5fe
    style E fill:#fff3e0
    style G fill:#ffeb3b
    style L fill:#ffeb3b
    style O fill:#e8f5e8
    style T fill:#ffebee
    style X fill:#ffebee
    style AA fill:#ffebee
```

## 10. 数据流向图

```mermaid
graph LR
    A[用户输入] --> B[Web/API Gateway]
    B --> C[负载均衡器]
    C --> D[应用服务器]
    D --> E[Redis缓存]
    D --> F[MySQL数据库]
    D --> G[NLU引擎]
    D --> H[RAGFLOW API]
    D --> I[外部业务API]
    E --> J[缓存数据]
    F --> K[持久化数据]
    G --> L[意图识别结果]
    H --> M[对话响应]
    I --> N[业务处理结果]
    J --> O[快速响应]
    K --> P[配置加载]
    L --> Q[意图处理]
    M --> R[兜底回复]
    N --> S[API调用结果]
    O --> T[响应生成]
    P --> U[系统配置]
    Q --> V[槽位处理]
    R --> W[最终响应]
    S --> X[业务完成]
    T --> Y[用户界面]
    U --> Z[系统运行]
    V --> AA[完整性检查]
    W --> BB[用户反馈]
    X --> CC[结果展示]
    Y --> DD[用户体验]
    Z --> EE[系统稳定]
    AA --> FF[API调用]
    BB --> GG[系统改进]
    CC --> HH[业务价值]
    
    style A fill:#e1f5fe
    style Y fill:#e8f5e8
    style DD fill:#e8f5e8
    style HH fill:#e8f5e8
    style GG fill:#f3e5f5
    style EE fill:#f3e5f5
```

## 11. 混合Prompt Template配置流程

```mermaid
graph TB
    A[请求Prompt Template] --> B[检查缓存]
    B --> C{缓存存在}
    C -->|是| D[返回缓存模板]
    C -->|否| E[加载配置优先级]
    E --> F[查询数据库模板]
    F --> G{数据库模板存在}
    G -->|是| H[使用数据库模板]
    G -->|否| I[加载配置文件模板]
    I --> J{配置文件模板存在}
    J -->|是| K[使用配置文件模板]
    J -->|否| L[使用系统默认模板]
    H --> M[模板变量替换]
    K --> M
    L --> M
    M --> N[模板验证]
    N --> O{验证通过}
    O -->|否| P[记录错误日志]
    O -->|是| Q[缓存模板结果]
    P --> R[使用备用模板]
    Q --> S[返回最终模板]
    R --> T[记录降级日志]
    S --> U[模板使用统计]
    T --> V[通知管理员]
    U --> W[性能监控]
    V --> X[系统维护]
    W --> Y[A/B测试分析]
    X --> Z[配置优化]
    Y --> AA[模板优化]
    
    style A fill:#e1f5fe
    style H fill:#e8f5e8
    style K fill:#fff3e0
    style L fill:#ffeb3b
    style P fill:#ffebee
    style R fill:#ffebee
    style S fill:#e8f5e8
```

## 12. 安全防护流程

```mermaid
graph TB
    A[用户请求] --> B[输入校验]
    B --> C{输入安全检查}
    C -->|失败| D[记录安全日志]
    C -->|通过| E[JWT Token验证]
    E --> F{Token有效}
    F -->|无效| G[返回认证错误]
    F -->|有效| H[权限检查]
    H --> I{权限验证}
    I -->|失败| J[记录权限日志]
    I -->|通过| K[频率限制检查]
    K --> L{频率限制}
    L -->|超限| M[返回限流错误]
    L -->|正常| N[IP白名单检查]
    N --> O{IP验证}
    O -->|失败| P[记录IP日志]
    O -->|通过| Q[数据加密处理]
    Q --> R[业务处理]
    R --> S[审计日志记录]
    S --> T[响应加密]
    T --> U[返回响应]
    D --> V[安全告警]
    G --> W[认证失败统计]
    J --> X[权限失败统计]
    M --> Y[限流统计]
    P --> Z[IP安全统计]
    V --> AA[安全分析]
    W --> BB[认证监控]
    X --> CC[权限监控]
    Y --> DD[流量监控]
    Z --> EE[IP监控]
    AA --> FF[安全报告]
    BB --> GG[系统加固]
    CC --> HH[权限优化]
    DD --> II[容量规划]
    EE --> JJ[IP策略调整]
    
    style A fill:#e1f5fe
    style D fill:#ffebee
    style G fill:#ffebee
    style J fill:#ffebee
    style M fill:#ffebee
    style P fill:#ffebee
    style V fill:#ffebee
    style Q fill:#e8f5e8
    style R fill:#e8f5e8
    style U fill:#e8f5e8
```