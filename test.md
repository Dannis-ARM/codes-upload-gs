```mermaid
sequenceDiagram
    participant A as 用户
    participant B as 系统
    participant C as 数据库
    
    A->>B: aaa
    B->>C: 验证用户信息
    C-->>B: 返回验证结果
    C->>C: self
    B-->>A: 登录成功/失败
    系统-->>用户: 登录成功
```

- [ ] test
- [ ] test
- [ ] test

sdfasd

| a    | b    | c     |       |
|:-----|:-----|:------|:------|
| asdf | 2    | 3     |       |
|      | 3242 | 23423 | 23432 |

```mermaid
sequenceDiagram
    autonumber
    participant User as 用户 (User)
    participant Host as MCP Client (如 Claude Desktop/IDE)
    participant LLM as 语言模型 (LLM)
    participant Server as MCP Server (如 Google Maps/GitHub/Local DB)
    participant Resource as 外部资源/工具 (Tools/Resources)

    User->>Host: 输入查询 (例如: "分析这个本地数据库的数据")
    Host->>LLM: 发送 Prompt + 可用工具列表 (Tool Definitions)
    
    Note over LLM: LLM 判断需要调用特定工具
    LLM-->>Host: 返回控制指令 (Call Tool: "query_db")
    
    rect rgb(12, 12, 120)
        Note right of Host: MCP 标准协议交互开始
        Host->>Server: 发送 JSON-RPC 请求 (tools/call)
        Server->>Resource: 执行具体操作 (查询数据库/读取文件/API调用)
        Resource-->>Server: 返回原始数据
        Server-->>Host: 返回标准化结果 (Text/Image/Content)
    end

    Host->>LLM: 将工具返回的内容作为上下文发送
    Note over LLM: 结合上下文生成最终回答
    LLM-->>Host: 返回文本响应
    Host->>User: 显示最终结果
```

asdf adasdf asds2asd
as



df dfasdf asds2 v d
asdf dfasdf asds2