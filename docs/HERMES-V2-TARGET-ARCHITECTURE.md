# 糖糖 V2 目标架构

> 状态：设计基线，接口细节以 Hermes 官方当前版本实测结果为准。

## 1. 总体结构

```text
家庭交互入口（麦克风 / 语音 / 投影 / 家长管理）
                     |
                     v
             TangTang Interaction
                     |
                     v
               TangTang Core
  +-----------------------------------------------+
  | 身份解析 | 成员 Profile | Context Builder     |
  | Privacy Pipeline | 儿童安全 | Quiet/Speak Gate|
  | Family/Private Memory | Companion Planner    |
  | Task Service | Device Authorization          |
  +-----------------------------------------------+
                     |
          Versioned Agent Port / MCP
                     |
                     v
                Hermes-Agent
  +-----------------------------------------------+
  | LLM reasoning | Skills | Task planning        |
  | Agent memory (non-sensitive operational)     |
  | Tool orchestration | Optional subagents       |
  +-----------------------------------------------+
                     |
              Cloud Model Provider
                     |
                     v
       Approved TangTang Tools / Adapters
       TTS / Projection / Reminder / Device API

Mac mini M6：以上服务的家庭常驻运行主机
```

## 2. 职责边界

### Hermes-Agent
允许承担：
- 自然语言理解、推理和回复草拟。
- 将复杂请求拆解为任务。
- 调用明确授权的 TangTang 工具。
- 使用经过审查的通用 Skills。
- 记录不含儿童私人内容的运行经验和技能元数据。
- 在 TangTang Core 允许的上下文范围内进行计划。

不得承担：
- 最终身份认定。
- 最终隐私分类和数据访问授权。
- 儿童安全策略的最终判断。
- 是否打扰、是否主动发声的最终决定。
- 家庭成员权限和家长授权管理。
- 路由器/家庭设备的直接管理员权限。
- 任意 shell、任意文件、任意网络访问。

### TangTang Core
继续拥有：
- member_id、成员关系、身份置信度及 unknown 状态。
- 各成员 persona/profile。
- 家庭共享记忆和成员私人记忆。
- 隐私过滤、上下文最小化和提示注入防护。
- Quiet Hours、Speak Gate、主动提醒冷却和优先级。
- 任务、提醒、陪伴事件和结构化家庭数据。
- 设备操作授权、保护设备名单、家长确认及审计记录。
- 输出动作白名单和表现层资源映射。

## 3. Agent 接入方式
优先评估 Hermes 原生支持的受控工具接口/MCP。只有在确认具体版本、认证方式、超时和生命周期后，才选定最终传输方式。

建议在 TangTang Core 新增独立的 Agent Adapter/Port，不让业务模块直接依赖 Hermes SDK 或内部实现。

第一版工具面尽量小：
- tangtang.get_interaction_context
- tangtang.submit_response_draft
- tangtang.create_reminder
- tangtang.list_tasks
- tangtang.request_companion_plan
- tangtang.request_presentation_action
- tangtang.request_device_action（第一阶段仅返回拒绝/待授权，不执行写操作）

每个请求携带 request_id、correlation_id、schema_version、core_api_version、member_id、identity_confidence、identity_status、privacy_scope、purpose、source、issued_at、expires_at、idempotency_key 和由 Core 生成的 authorization_context。

Agent 不得自行把 member_id 或 privacy_scope 升权。Core 必须重新校验请求者、对象、用途和当前策略。

## 4. 记忆分层

| 存储 | 归属 | 允许内容 | 禁止内容 |
|---|---|---|---|
| Hermes Agent Memory | Hermes | 工具使用说明、通用任务经验、非敏感技能元数据 | 儿童私人对话、声纹、原始语音、家庭秘密 |
| TangTang Family Memory | Core | 经授权的家庭共享事实和事件摘要 | 成员私人内容 |
| TangTang Private Memory | Core | 对应成员的私人记忆 | 其他成员/家庭共享读取 |
| Event Store | Core | 最小化、可审计事件 | 无必要的原始敏感内容 |

第一阶段对 Hermes 持久记忆采用 allowlist：默认关闭自动保存对话正文；仅允许保存明确标记为 non-sensitive、approved 的技能/操作元数据。需要记忆某条家庭事实时，必须通过 Core 的记忆写入流程。

## 5. 输出协议

Agent 返回结构化结果，不直接执行动作：

```json
{
  "schema_version": "1.0",
  "request_id": "req_example",
  "kind": "response_draft",
  "member_id": "child_9",
  "message": "糖糖在呢，我们先一起想想。",
  "action_id": "caring",
  "requested_tools": [],
  "requires_confirmation": false
}
```

Core 对返回内容进行 schema 校验、成员/隐私校验、安全检查、动作白名单校验，再决定是否交给 TTS/投影。字段无效、超时或身份不匹配时 fail closed，使用现有安全 fallback。

## 6. 运行与网络边界
- Hermes Gateway 默认仅监听 loopback 或受控私网地址。
- 管理界面不得直接暴露公网。
- 远程维护使用 VPN/零信任通道；不开放未经认证的管理端口。
- Hermes 和 TangTang Core 使用独立配置、日志和运行环境。
- Core 的数据目录不得整体挂载给 Agent；只通过最小化工具返回所需数据。
- Agent 不获得生产家庭数据目录的通用写权限。
- 密钥存储于本机安全配置/Keychain 或受保护环境变量，不入仓库。
- 不部署第二个 Agent Gateway，除非后续架构决策记录明确批准。

## 7. 失败隔离
- Hermes 不可用：保留 Core 确定性规则、静默/基础提醒和简短 fallback。
- 云端模型不可用：超时后停止重试风暴，走安全 fallback。
- Agent 输出格式错误：拒绝动作，不自动修复后执行。
- 语音/TTS/投影失败：分别隔离，不影响事件记录和隐私策略。
- 设备接口失败：保持原状态，不重试危险写操作。