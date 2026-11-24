# Hermes-Agent ↔ TangTang Core 集成契约（草案）

> 状态：接口设计草案，尚未绑定某个 Hermes SDK/API 版本。
> 原则：先定义糖糖自己的稳定边界，再适配 Hermes；不让 Hermes 内部接口成为 Core 的公共 API。

## 1. 版本约定
- 当前 Core API 基线：4.x（以 core/interfaces.py 为准）。
- 本集成先作为 V4 外围适配器，不修改 CORE_API_MAJOR。
- Agent Adapter 自身使用独立 schema version，例如 1.0。
- 如确需改变 V4 核心端口语义，必须单独提出版本升级 ADR、迁移和兼容测试，不得静默升到 V5。

## 2. 最小调用流程
1. 交互入口把原始输入交给 TangTang Core。
2. Core 执行身份解析、隐私分类、风险识别和上下文裁剪。
3. Core 生成一次性、短时有效的 Agent Request。
4. Agent 仅获得该请求允许的最小上下文。
5. Agent 返回结构化 Response Draft 或 Tool Request。
6. Core 重新校验身份、隐私、策略、动作白名单和授权。
7. Core 决定是否保存记忆、创建任务、发声或展示动作。
8. Core 写入最小化审计事件。

## 3. 初始数据结构

### AgentRequest
```json
{
  "schema_version": "1.0",
  "request_id": "req_uuid",
  "created_at": "ISO-8601",
  "expires_at": "ISO-8601",
  "core_api_version": "4.0.0",
  "member": {
    "member_id": "child_9",
    "identity_status": "verified",
    "identity_confidence": 0.96,
    "persona": "play"
  },
  "privacy_scope": "PRIVATE",
  "purpose": "interactive_reply",
  "context": {"time_local": "20:30", "scene": "home", "authorized_facts": []},
  "input": {"text": "今天我有点累"},
  "allowed_capabilities": ["draft_response"]
}
```
示例仅定义字段，不代表真实家庭数据。不要把原始声纹、原始音频或完整事件历史放入请求。unknown 身份时 member_id 必须为空。identity_confidence 是 Core 判断结果，不接受 Agent 回写覆盖。

### AgentResponse
```json
{
  "schema_version": "1.0",
  "request_id": "req_uuid",
  "kind": "response_draft",
  "message": "糖糖在呢，要不要先休息一下？",
  "action_id": "caring",
  "memory_proposals": [],
  "tool_requests": []
}
```

### ToolRequest
```json
{
  "schema_version": "1.0",
  "request_id": "req_uuid",
  "tool": "tangtang.create_reminder",
  "arguments": {"title": "喝水", "due_at": "ISO-8601"},
  "reason": "用户明确提出提醒请求"
}
```
Agent 只能提出请求。Core 负责重新解析意图、验证权限、幂等和安全性。涉及家长控制、设备写操作、删除数据或对外通信时，必须执行额外授权流程。

## 4. 初始工具权限矩阵
| 工具 | 普通交互 | 未知身份 | 儿童 | 家长确认 |
|---|---:|---:|---:|---:|
| 获取当前轮次裁剪上下文 | 允许 | 最小匿名上下文 | 允许 | 否 |
| 生成回复草稿 | 允许 | 受限 | 允许 | 否 |
| 读取私人记忆 | Core 按 owner/viewer 决定 | 禁止 | 仅本人范围 | 否 |
| 创建普通提醒 | 需 Core 复核 | 禁止 | 可提议 | 视规则 |
| 修改家庭安全策略 | 禁止 | 禁止 | 禁止 | 必须 |
| 路由器设备写操作 | 禁止 | 禁止 | 禁止 | 必须 |
| 任意 shell/任意文件读写 | 禁止 | 禁止 | 禁止 | 不开放给 Agent |

## 5. 超时、重试与幂等
- 每个请求有明确 deadline；超时后走 Core fallback。
- 只读请求可在安全条件下有限重试。
- 创建任务/提醒必须使用 idempotency_key，避免重试造成重复任务。
- 设备写操作不自动重试。
- 每次请求记录 request_id、结果类型、耗时和错误类别，不记录不必要的儿童原文。
- Agent 返回过期 request_id 时直接拒绝。

## 6. 注入与工具输出安全
- 外部网页、文档、聊天记录和工具结果全部视为不可信数据。
- Agent 工具输出不得修改系统策略或权限。
- 工具参数必须 schema 校验、长度限制和 allowlist 校验。
- 不允许把 Agent 文本拼接到 shell、SQL 或任意路径。
- 失败默认拒绝（fail closed）。

## 7. Hermes 适配器待验证项
当前优先方向：TangTang Core 作为 MCP Server，Hermes 作为 MCP Client。Hermes 官方文档明确支持连接本地 stdio 和远程 HTTP MCP Server，并支持工具发现和按服务器过滤。Hermes 自身作为 MCP Server 的能力已迁移到独立 mcp-serve 插件，不能把两个方向混为一谈。

Agent Adapter 的候选运行形态为 Hermes API Server 本地 HTTP 接口；官方 `hermes-api-server` 默认保留大部分内置工具，包括 terminal/file。必须通过 `agent.disabled_toolsets` 禁用不需要的内置工具；`platform_toolsets.api_server` 只筛选动态 MCP 服务器，不会关闭内置工具。只有在 `/v1/toolsets` 验证实际启用列表精确符合 allowlist 后，才允许接入家庭数据。`API_SERVER_KEY` 即使绑定 loopback 也必须设置。

正式编码前核实所选 Hermes 版本：
- 官方支持的 MCP/工具接入方式及配置 schema。
- CLI 单轮调用、Hermes backend/API 与消息 Gateway 的职责差异、生命周期和认证方式。
- 工具调用参数/返回格式。
- Skills 的加载路径、权限和更新机制；初期建议 skills.write_approval=true。
- Agent Memory 的自动写入行为、禁用/allowlist 能力。官方当前配置可同时设置 memory.memory_enabled=false 和 memory.user_profile_enabled=false，关闭 Hermes 内置记忆工具；若不关闭，则 memory.write_approval=true 也只能审批 memory 工具写入，不能替代文件/终端权限隔离。
- Cron/定时任务的时区、重启补偿和重复执行语义。
- 超时、取消、并发限制和日志脱敏。
- macOS Apple Silicon 支持和版本最低要求。

在这些事实未通过小型 spike 验证前，不在 Core 中引入 Hermes 专有依赖。
