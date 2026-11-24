# 糖糖 V2 阶段 0：代码资产与迁移风险审计

> 审计日期：2026-11-24
> 基线：main @ d3d3e700（截至本轮代码审查开始时的主分支）
> 性质：基于 GitHub 当前代码和 PR 的静态审计；Mac mini、语音设备、投影和路由器实机状态尚未验证。

## 1. 核心结论

1. 糖糖已经有独立的 V4 家庭业务核心。不要重写身份、隐私、记忆、陪伴、任务和发声策略。
2. Hermes 接入点不是“替换一个现有 OpenClaw Gateway”。当前 V4 默认对话路径是 TangTang Core 注入 LLM callable，底层通过 `cat-chat.py` 直接请求 OpenAI 兼容模型接口（默认智谱 BigModel URL，模型 `glm-4-flash`）；环境变量仍沿用 `QCLAW_*` 命名。OpenClaw 的旧部署报告也说明糖糖云脑走智谱直连。此次实际改造是把 V4 的 LLM/Agent 适配层替换为 Hermes API/Agent，而不是拆掉一个当前必需的 OpenClaw 主网关。
3. Hermes API Server 默认工具权限较宽，官方文档明确包含 terminal、file operations、web、memory、skills 等。必须先通过 `agent.disabled_toolsets` 禁用不需要的内置工具，再检查 `/v1/toolsets`；`platform_toolsets.api_server` 只筛选动态 MCP Server，不会关闭内置工具。否则不能接入家庭数据。
4. Hermes 默认内置记忆会跨会话保存并自动整理。糖糖初期必须关闭 Hermes 内置 MEMORY/USER stores，家庭记忆继续只由 TangTang Core 掌管。
5. 当前语音入口曾存在一项实际隐私风险：`cat-voice.sh` 将识别出的原话传给 `cat-vp.py log`，后者原先会写入 `cat-habits.json` 并在 summary 中显示。PR #76 已合并，已阻止新原话写入；历史本机文件仍需迁移前单独清理。
6. 当前 main 的核心接口版本是 4.0.0，但 `core/brain/planner.py` 的文档口径出现 V5。必须在任何适配代码之前厘清，不擅自改变 CORE_API_VERSION。

## 2. 已确认可保留的代码资产

| 资产 | 代码位置 | 现状与处理建议 |
|---|---|---|
| V4 主运行时 | `core/runtime/loop.py` | `TangTangRuntime`，API 4.0.0；保留 |
| 身份识别 | `core/identity/` | Core 负责身份解析；保留，Agent 不得认定身份 |
| 隐私流水线 | `core/ingest.py`、`core/policy/privacy_policy.py` | `PrivacyPipeline` 先做身份、隐私分类和上下文构建；保留为唯一权限事实源 |
| 对话适配 | `core/adapters/chat_adapter.py` | `LLMFn` 注入 callable；这是首选 Hermes Adapter 接入点 |
| 上下文构建 | `core/context/` | 只将过滤后的上下文交给模型；保留 |
| 记忆 | `core/memory/` | 私人、家庭共享、摘要、偏好和检索分层；保留，Hermes 不取代 |
| 发声与打扰策略 | `core/policy/speak_gate.py`、`interrupt_policy.py` | 确定性决策，保留为最终发声门控 |
| 主动陪伴 | `core/companion/`、`core/brain/` | 计划器可被 Agent 辅助，但最终是否执行仍由 Core 决定 |
| 任务服务 | `core/tasks/` | 本地任务状态、可见性和幂等；保留，先不启用 Hermes Cron |
| 语音适配 | `core/adapters/voice_adapter.py`、`code/cat/cat-voice.sh` | 采集、STT、身份识别、对话和 TTS 已有链路；逐段迁移和实测 |
| TTS / 投影 | `core/adapters/tts_adapter.py`、`projection_adapter.py`、`presentation/` | 保留适配器和资源，验证 Mac mini 输出设备与投影链路 |
| 安全 | `core/security/`、`core/policy/injection.py` | 保留并增加 Agent 工具边界测试 |

## 3. 当前真实对话调用链

```text
code/cat/cat-voice.sh
  -> cat-listen.sh / cat-vp.py identify / cat-stt-baidu.sh
  -> cat-chat.py
  -> _private_cli_reply()
  -> core.adapters.chat_adapter.ChatAdapter
  -> PrivacyPipeline / ContextBuilder / ResponseOrchestrator
  -> injected _runtime_llm()
  -> cat-chat.py chat()
  -> OpenAI-compatible HTTP endpoint (default BigModel URL)
  -> Core response / cat-say.sh
```

重要核查点：
- `cat-chat.py` 默认 `TANGTANG_V4_PIPELINE=1`，V4 路径不使用旧 V3 对话历史。
- `_runtime_llm()` 只接受 `_filtered_prompt`，且 PRIVATE 和 unknown 默认受环境开关限制；实际生产配置是否启用了 `TANGTANG_ALLOW_PRIVATE_LLM` 尚需在 Mac mini 安全核对，不能从仓库推断。
- `cat-chat.py` 中仍保留 V3 直连模型和本地历史文件路径，属于兼容/回退路径；迁移时应加明确 feature flag，不直接删除。
- V4 的 `ChatAdapter` 接收 `Callable[[Mapping], str]`，可先用 Hermes HTTP Adapter 替换 LLM callable，而无需改动 PrivacyPipeline。

## 4. Mac mini 迁移依赖

| 项目 | 当前仓库证据 | 改造要求 |
|---|---|---|
| 旧主机口径 | README、`tangtang_paths.py` 注释仍提到 MacBook Air / Mac Air | 文档和路径抽象改为通用 macOS 主机，不硬编码旧机器 |
| 数据目录 | `tangtang_paths.py` 默认 macOS `~/Library/Application Support/Tangtang`，并拒绝网络卷 | M6 继续本地存储；迁移前先盘点、脱敏、备份、恢复演练 |
| 启动器 | `start-cat.sh` 只启动舞台/宠物页面后退出 | 它不是完整常驻守护进程；需单独设计 Core、Hermes、语音服务生命周期 |
| LaunchAgent | `config/com.tangtang.daemon.plist.example` 的 `KeepAlive=false` | 不应原样作为 Agent/Core 守护进程；为各服务设计独立服务管理 |
| 定时任务 | `config/crontab.example` 与 `cat-schedule.sh` 负责语音提醒/闹铃/任务派发 | 先确定唯一调度权威，防止旧 crontab 与 Hermes Cron 重复 |
| 模型密钥 | `.llm_key` / `QCLAW_LLM_API_KEY` / `QCLAW_LLM_BASE_URL` | 改为本机安全配置；不复制旧机器密钥到 GitHub |
| 投影/音频 | shell 脚本依赖 macOS `say`、音频输出、AirPlay 和本机设备 | M6 需实机检查音频设备、投影、休眠唤醒和无头运行策略 |

## 5. OpenClaw 依赖边界

- `cat-openclaw.sh` / `cat-openclaw-report.py` 是以 OpenClaw 命名的每日互动/标签报告流程，不是 V4 对话主入口。
- `docs/openclaw-deployment-20261029.md` 记录的是旧 MacBook Air / Big Sur / Node 22 环境；不能作为 M6 的兼容性结论。
- 当前对话路径的 LLM callable 直连 BigModel；`QCLAW_*` 是历史配置命名，需查清是否有其他生产脚本读取，不应直接全局替换变量。
- 因此 OpenClaw 相关脚本暂时保留。Hermes 先接管 V4 模型/Agent 适配，不需要同时部署 OpenClaw Gateway。

## 6. 隐私问题与当前修复

### 已发现
- `code/cat/cat-voice.sh` 调用 `cat-vp.py log "$WHO" "$TEXT"`。
- 旧版 `code/cat/cat-vp.py` 将原话写入 `cat-habits.json` 的 `text` 字段。
- `cat-vp.py summary` 会输出最近三条原话。
- `cat-family.py` 的儿童习惯写入路径有 PrivacyPolicy 过滤，但这不能抵消 `cat-vp.py` 旁路写入。

### 修复状态
- PR #76 已合并：停止写入新原话，保留互动计数/时间/时段；summary 不再打印历史原话；新增回归测试，Python 3.10/3.11 CI 通过。
- PR #76 不会自动清理历史本机 `cat-habits.json`。M6 数据迁移前需在本机备份后，对旧文件做本地清理/脱敏，不将历史原文导入 Hermes。

## 7. 开放 PR 审查结论

| PR | 当前内容 | 审查结论 | 下一步 |
|---|---|---|---|
| #67 VoiceStudio TTS | 可选 TTS 路由，默认关闭，增加请求构造测试 | 可保留为可选后端；分支基于旧 main，未做真实 VoiceStudio 端到端验证 | 等 Hermes 主链路稳定后重基线、补失败回退/语音测试，再考虑合并 |
| #69 MiWiFi Router | 设备列表与 WAN 控制适配、CLI 和测试 | 暂不合并；基于旧 main，未实机验证；`parent_approved` 是调用方布尔值，不是可验证的家长身份凭据 | 重基线并把写权限改为 Core 签发的一次性授权/家长会话凭据；先只读接入 |
| #70 Router plan | 家庭设备管控方案文档 | 不合并当前版本；内容含家庭设备标签和局域网 IP 片段，公开仓库应先进一步脱敏 | 保留安全原则，删去可识别的家庭设备清单后再整理入主文档 |

所有 PR 的 `base_sha` 均落后于当前 main，必须重新基线；不把分支测试通过等同于当前 main 可直接合并。

## 8. 版本口径问题

- `core/interfaces.py`、`core/runtime/loop.py`、`core/ingest.py`、`core/policy/privacy_policy.py`、`core/tasks/service.py` 和多个 adapters 均声明 `core_api_version = 4.0.0`。
- `core/brain/planner.py` 自身明确称为“Deterministic V5 companion planner”，描述的是陪伴规划器这一模块迭代；它并未声明 Core API V5。当前 Core API 仍为 4.0.0。
- 处理结论：将“Planner V5”视为模块版本/代际名称，不等同于 Core API major；Hermes Adapter 使用独立 schema version，不改 Core API 4.x。后续文档应避免把 Planner V5 写成系统 API V5。

## 9. 阶段 0 退出条件

- [x] 现有 V4 主调用链已定位。
- [x] Hermes 官方 API、MCP、Toolsets、Memory 和安全边界已查阅并记录在 `HERMES-V2-HERMES-REFERENCE.md`。
- [x] 当前 main CI 基线问题已在 PR #74 修复并合并；主分支 Python 3.10/3.11 CI 通过。
- [x] 规划基线已在 PR #75 合并。
- [x] PR #76 隐私修复 CI 通过并合并。
- [x] 已核对 planner V5 与 Core API 4.0.0：属于模块版本口径，不需要升级 Core API。
- [ ] 重新审查并更新 #67/#69/#70，明确是否保留/重写/关闭；当前仍未合并。
- [ ] 完成 Hermes API Server 最小工具集 PoC；PR #78 已合并本地客户端和 V4 feature flag，默认工具 allowlist 为空；需在 M6 验证 `/v1/toolsets` 实际只返回空工具集，再逐步考虑 `mcp-tangtang`。
- [ ] 在 Mac mini 上记录真实硬件/macOS/磁盘/模型配置。

## 10. 最新执行状态（2026-11-24）

- PR #78 已合并到 main（commit `da7c513`），新增 Hermes API Adapter、成员人格系统提示词、V4 `TANGTANG_LLM_BACKEND=hermes` 开关、配置示例和回归测试。
- 默认仍使用原模型直连；Hermes 模式未在真实 Hermes/Mac mini 上验证，不应启用。
- PR #78 的 Python 3.10/3.11 CI 通过；main 合并后 CI 正在运行。

## 11. 下一步

1. 合并并验证 PR #76 的语音原话隐私修复。
2. 完成版本口径和 OpenClaw 遗留配置盘点。
3. 在无真实家庭数据的环境下启动 Hermes API Server，验证本地认证、工具集白名单、超时、会话和资源占用。
4. 只有 PoC 的 `/v1/toolsets` 证明最小权限生效后，才开始实现 Core 侧 Hermes Adapter/MCP Server。


## 12. 后续静态代码审查记录（2026-11-24）

本轮由用户明确要求先暂停 Mac mini 实机工作，继续审查代码并通过独立 PR 优化。以下变更均尚未合并主分支：

| PR | 审查发现 | 修改 | CI |
|---|---|---|---|
| [#82](https://github.com/qhkhrsq8ww-byte/tangtang/pull/82) | Hermes system prompt 使用字面量 `\\n` 作为分隔符 | 改为真实换行，并增加提示词结构、年龄人格、未知身份测试 | Python 3.10/3.11 通过（run 391） |
| [#83](https://github.com/qhkhrsq8ww-byte/tangtang/pull/83) | 未注册的说话人标签可能被当作家庭成年人，进入共享记忆/摘要/日志 | 未能映射到名册的身份改为 PUBLIC/transient，禁止家庭存储和原话日志；增加未知访客测试 | 首轮因集成测试名册不完整失败；补充确定性测试名册后 Python 3.10/3.11 通过（run 394） |
| [#84](https://github.com/qhkhrsq8ww-byte/tangtang/pull/84) | ChatAdapter 每轮临时修改共享 ResponseOrchestrator.responder，存在并发串话风险 | 改为 run 级 responder 参数，不再修改共享对象；增加回归测试 | Python 3.10/3.11 通过（run 393） |

审查边界：
- 上述 CI 是 GitHub Linux runner 上的自动化测试，不代表 macOS、Hermes API Server、语音设备或投影实测。
- PR #82/#83/#84 通过 CI 不等于已合并或已上线。
- PR #83 对身份的判定以配置名册为准；名册缺失或不完整时，未解析身份保持访客权限，不得靠任意字符串推断家庭成员身份。
