# Hermes-Agent 官方能力核验记录

> 核验日期：2026-11-24
> 来源：Nous Research Hermes Agent 官方文档。
> 本文只记录公开文档可确认的能力；最终版本仍需在 Mac mini 实测并锁定。

## 1. 已确认的官方能力

| 项目 | 官方文档当前说明 | 对糖糖的影响 |
|---|---|---|
| Apple Silicon | macOS Desktop 安装包面向 Apple Silicon；CLI 安装脚本支持 macOS | M6 平台方向兼容，但仍需核对实际 macOS 版本 |
| MCP Client | Hermes 可连接本地 stdio 和远程 HTTP MCP Server，自动发现工具并支持按 server 过滤工具 | 可让 Hermes 调用 TangTang Core 提供的最小工具集 |
| Built-in Memory | 默认启用 MEMORY.md / USER.md，并可在轮次后后台自动整理写入 | 不能直接使用默认设置承载儿童陪伴会话 |
| Memory control | memory_enabled=false 且 user_profile_enabled=false 可关闭内置两类记忆工具；write_approval=true 可将 memory-tool 写入转为待审批 | 初期建议关闭内置持久记忆，家庭记忆只由 TangTang Core 管理 |
| Skills | skills.write_approval=true 可要求通过 skill_manage 的技能写入先审批 | 初期允许只读技能，技能修改必须审批 |
| Command approval | 支持 smart/manual/off；cron_mode、single_query_mode、unattended_mode 可设为 deny | 无人值守家庭环境应保持严格审批，不能使用 YOLO/off |
| Cron | 有内置定时任务能力 | 与现有 macOS crontab/TaskService 可能重复，必须先决定唯一调度权威 |
| Gateway | 消息平台 Gateway 有独立安装/启动流程；Hermes Desktop backend / hermes serve 与消息 Gateway 不是同一个概念 | 不得把所有 Hermes 进程统称为一个 Gateway；先做最小本地运行验证 |
| MCP Server mode | Hermes 自身作为 MCP Server 的命令已迁移到 mcp-serve 插件 | 糖糖首选方向是 TangTang Core 作为 MCP Server、Hermes 作为 MCP Client；不要假设 Hermes Agent 原生就是 MCP Server |

## 2. 初期建议的 Hermes 配置策略

以下为设计建议，不是已在设备上执行的配置：

```yaml
memory:
  memory_enabled: false
  user_profile_enabled: false

skills:
  write_approval: true

approvals:
  mode: manual
  cron_mode: deny
  single_query_mode: deny
  unattended_mode: deny
```

说明：
- 关闭 Hermes 内置记忆后，糖糖仍可通过 TangTang Core 的授权记忆接口提供必要上下文；这不是关闭糖糖自己的家庭记忆。
- 若未来确需 Hermes 记忆，只允许经安全评审后开启，并优先采用审批写入；不得把儿童私人对话自动沉淀为 Hermes USER.md/MEMORY.md。
- memory/skill 写审批只覆盖对应工具，不是文件系统沙箱。通用文件工具和 Terminal 仍可能修改文件，因此工具集和工作目录也必须最小化。
- 不允许使用 approvals.mode=off 或 HERMES_YOLO_MODE。

## 3. API Server 与工具白名单（重要补充）

Hermes 官方 API Server 提供 OpenAI 兼容接口，默认绑定 127.0.0.1:8642，并要求 API_SERVER_KEY；但官方文档明确说明 API Server 默认平台工具集仍包含终端、文件、网页、记忆、技能等完整工具能力。因此不能只因为 API 监听 loopback 就认为权限足够安全。

第一阶段先不配置任何 MCP Server，并通过 `agent.disabled_toolsets` 禁用 API Server 默认平台工具集中所有不需要的工具集。第二阶段才配置 TangTang MCP Server，并用 `platform_toolsets.api_server` 限制 API Server 可见的 MCP 服务器。注意：`platform_toolsets.api_server` 只控制动态 MCP 服务器选择，不会自动关闭内置 file/terminal 等工具。

```yaml
# 第一阶段：不配置 mcp_servers，先关闭 API Server 的内置工具
agent:
  disabled_toolsets:
    - browser
    - code_execution
    - connections
    - cronjob
    - delegation
    - file
    - image_gen
    - memory
    - search
    - session_search
    - skills
    - terminal
    - todo
    - vision
    - web
    - x_search
    - video
    - video_gen

# 第二阶段通过安全评审后才增加：
# mcp_servers:
#   tangtang:
#     command: /absolute/path/to/tangtang-mcp-server
#     args: []
# platform_toolsets:
#   api_server:
#     - tangtang  # 只选择该 MCP server；不替代上面的内置工具禁用清单
```

说明：
- 上述禁用清单是基于官方 `hermes-api-server` 平台工具集的初始草案，必须按锁定版本 `hermes tools list` 和 `/v1/toolsets` 核对；任何额外启用工具都会被 TangTang Adapter 拒绝。
- `mcp-tangtang` 是动态工具集的展示名；配置 `platform_toolsets.api_server` 时使用服务器名 `tangtang`。启动后必须通过 `/v1/toolsets` 检查实际启用列表和具体工具名。
- 上述配置不可未经 `hermes config check`、`hermes tools` 和 API 实测直接当作可运行配置。
- `API_SERVER_ENABLED=true`、`API_SERVER_HOST=127.0.0.1`、强随机 `API_SERVER_KEY`；不配置 CORS，不暴露公网。
- Hermes API Server 默认 `hermes-api-server` 会保留大部分内置工具。必须通过 `agent.disabled_toolsets` 逐项关闭，并验证最终工具列表；若不能做到，禁止接入家庭数据。
- 初期不启用 Hermes Cron；调度仍由 TangTang Core/现有任务机制负责，防止双重调度。
- Skills 工具集初期禁用；即使打开 write_approval，审批也不覆盖通用文件工具或终端。

## 4. API Server 的运行进程

Hermes API Server 通过 `hermes gateway` 进程提供（由 `API_SERVER_ENABLED=true` 或 `gateway.api_server.enabled: true` 启用），不是独立的 `hermes serve` Desktop backend，也不是 Hermes 自身作为 MCP Server 的 `mcp-serve` 插件。第一阶段只启动本机 API Server 所需的 Gateway，不配置外部消息渠道；进程生命周期、端口和日志要作为一个服务单独验收。

## 4. 运行形态选择

优先验证 API Server 的本地 HTTP 接口与会话能力，作为 TangTang Core 的 LLM/Agent Adapter 候选；同时保留 `hermes -z` 单次 CLI 作为最小 PoC/故障诊断入口。不要直接使用默认完整工具集的 API Server。

官方资料：
- API Server：https://hermes-agent.nousresearch.com/docs/user-guide/features/api-server
- Toolsets Reference：https://hermes-agent.nousresearch.com/docs/reference/toolsets-reference
- MCP Integration：https://hermes-agent.nousresearch.com/docs/user-guide/features/mcp
- CLI Commands：https://hermes-agent.nousresearch.com/docs/reference/cli-commands

## 5. 需要实测的接入形态

1. Hermes CLI 单轮调用：确认是否能满足 Core Adapter 的延迟、取消和结构化输出要求。
2. Hermes Desktop/backend：确认 JSON-RPC/WebSocket 接口、认证和进程管理是否适合本地 Core 调用。
3. Hermes Messaging Gateway：只在需要 Telegram/其他消息平台时评估，不作为本地麦克风/投影的默认前提。
4. MCP：优先让 Hermes 作为 MCP Client 调用 TangTang Core 暴露的只读/有限写工具；工具过滤、认证、超时和错误语义必须验证。

## 4. 官方资料

- 首页与功能总览：https://hermes-agent.nousresearch.com/docs
- 安装指南：https://hermes-agent.nousresearch.com/docs/getting-started/installation
- 快速入门（中文）：https://hermes-agent.nousresearch.com/docs/zh-Hans/getting-started/quickstart
- 配置说明：https://hermes-agent.nousresearch.com/docs/user-guide/configuration
- 持久记忆：https://hermes-agent.nousresearch.com/docs/user-guide/features/memory
- 安全模型：https://hermes-agent.nousresearch.com/docs/user-guide/security
- MCP：https://hermes-agent.nousresearch.com/docs/user-guide/features/mcp
- CLI 命令参考：https://hermes-agent.nousresearch.com/docs/reference/cli-commands
- Messaging Gateway：https://hermes-agent.nousresearch.com/docs/user-guide/messaging

## 5. 重要结论

Hermes 的持续学习能力很有价值，但其默认记忆会自动写入，且 memory/skill approval 并不等同于文件系统隔离。因此糖糖必须先关闭内置持久记忆、严格限制工具和终端权限，再通过 TangTang Core 提供家庭上下文。只有完成这层隔离，才进入真实儿童语音数据测试。
