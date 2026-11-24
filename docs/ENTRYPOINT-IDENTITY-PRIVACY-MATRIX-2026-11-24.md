# 语音、主动陪伴、任务与提醒入口统一身份/隐私审计（2026-11-24）

## 目的与判定口径

所有外部入口必须先经过 TangTang Core 的统一身份解析与隐私授权，再进行私人数据读取、记忆写入、模型调用、任务/提醒变更或设备输出。入口参数、环境变量、自然语言中的家庭成员称呼、presence 推测值均不是身份凭证。

统一链路：

`Ingress Adapter → Canonical Identity + Evidence → Privacy/Authorization Decision → Event → scoped Memory/Task/Reminder → Agent Draft → Core Output Decision`

默认拒绝：身份不明、证据缺失/过期/未验证、viewer 与 owner 不一致、策略异常时，不读取私人数据、不写入成员记忆、不创建/修改个人任务提醒、不调用云端模型；允许不泄露家庭信息的通用回应。系统定时器触发的 due/ring 属于受限系统执行身份，不等于用户身份。

## 入口逐项盘点

| 入口 | 当前调用链/身份来源 | 主要缺口 | 必须达到的边界 |
|---|---|---|---|
| 麦克风语音 | `code/cat/cat-voice.sh` → `cat-vp.py identify` → `cat-presence.py suggest` → `cat-family.py observe` → `cat-alarm.py handle` → `cat-chat.py` | shell 在进入 V4 前先写入 family observe；presence suggestion 可把未知声纹提升为成员候选；alarm 在 V4 之外执行 | 语音识别结果携带来源/时间/置信度/验证状态；Core 统一解析；在授权前不执行 family observe、任务提醒或私人输出 |
| 文本/语音聊天 CLI | `code/cat/cat-chat.py` → `_task_reply` / `_alarm_reply` → Speak Gate → `ChatAdapter.turn` | task/alarm 在 V4 ingest 前短路；`TANGTANG_SPEAKER` 环境变量被当作成员候选；旧 V3 分支仍需双开关保护（PR #91 尚未合并） | 所有意图先 ingest；speaker 只能取 Core canonical identity；所有本地意图与普通对话共用隐私判定 |
| 主动场景 | `code/cat/cat-living.py` → `TangTangRuntime.handle_living_room` → InterruptPolicy | CLI 参数、`TANGTANG_MEMBER_ID`、`TANGTANG_SPEAKER` 直接成为成员候选；未解析时 habit store 仍可能写入 `unknown` 或原始候选；InterruptPolicy 对无身份场景可默认 SPEAK | 场景证据必须新鲜且可验证；受众身份不明时不引用成员私事、不写成员习惯；InterruptPolicy 只消费 Core 已授权的受众上下文 |
| 主动陪伴策略 | `core/policy/interrupt_policy.py` → `decide()` | 无身份/证据硬门槛；主动场景冷却 key 可退化为 `*`；紧急标志可直接 SPEAK | Core 在策略前完成身份/场景证据校验；策略输出仅是建议，不授予数据访问或设备执行权限 |
| 任务入口（旧语音快捷路径） | `cat-chat.py::_task_reply` → `IdentityResolver` → `core/tasks/intent.py::handle_voice_task` → `TaskService` | 任务处理早于 V4 ingest；owner 来自环境变量 speaker 候选；缺少证据与统一 Event 关联 | 任务创建/列表/完成/取消全部要求 canonical owner + viewer 一致；失败不得降级为家庭共享或模型处理 |
| 任务入口（V4） | `ChatAdapter.turn` → `PrivacyPipeline.ingest` → `_handle_task_intent` → `TaskService` | 主干身份解析回退问题由 PR #86 修复；私人记忆 viewer 隔离由 PR #89 修复；两者当前仍为未合并 PR | 只允许使用 ingest 返回的 canonical member_id；未知身份不能创建、查询、完成或取消个人任务 |
| 提醒入口（V4 reminder） | `ChatAdapter.turn` → `parse_reminder_intent` → `_handle_reminder_intent` → TaskService | 与 V4 ingest 同链，但仍依赖 #86/#89 的身份和 viewer 修复 | reminder 与 task 使用同一 owner/viewer 授权；家庭共享必须显式意图且经策略允许 |
| 闹铃入口 | `code/cat/cat-alarm.py` 的 `handle_utterance` / CLI `handle,set,cancel,list,cancel_all` | 自然语言可通过“爸爸/弟弟”等别名指定 member；CLI set/cancel/list 无用户身份参数；list 可列出全家闹铃；cancel_all 可全量取消 | 用户操作必须限定到 canonical owner；禁止用户借自然语言操作他人闹铃；系统 due/ring 单独使用最小权限系统执行身份 |
| 定时提醒执行 | `cat-alarm.py due/ring` 与任务调度服务 | 执行主体与用户创建主体没有统一授权/审计关联 | 仅执行已授权、已启用、owner/visibility 完整的到期记录；记录来源事件与执行结果；不在触发时读取其他成员私人信息 |
| 家庭事件/习惯写入 | `cat-voice.sh` → `cat-family.py observe`；`cat-living.py` → `HabitTrendStore.record` | 写入可能发生在统一身份与隐私决策之前；living fallback 可用原始 member 参数写习惯 | 所有写入必须由 Core 决定 scope、canonical owner、允许写入字段；入口不得直接写 store |
| 投影/TTS 输出 | `cat-chat.py`、`cat-alarm.py ring`、living adapter → `cat-say.sh` | 部分本地命令在 V4 策略前输出；定时闹铃需与私人对话权限区分 | 输出必须携带决策结果、sink 与 owner/受众；用户私人内容仅向 owner 的授权 sink 输出 |

## 当前已有修复与依赖

- PR #83/#86：未知身份与身份解析失败关闭；当前均未合并。
- PR #88：感知证据契约；目前是可启用的分阶段校验，不代表所有旧入口已输出 evidence。
- PR #89：私人记忆 owner/viewer 授权；当前未合并。
- PR #91：V3 回退双重显式开关；当前未合并。
- PR #76 已合并：停止新增语音原话写入旧日志；历史本地原话仍需独立迁移/清理。
- PR #90：记忆链路审计，不代表语音/主动陪伴/任务/提醒入口已全部完成迁移。

## 实施顺序与验收门槛

### P0：阻断绕过路径
1. 语音入口在任何 family observe、alarm/task handler 之前完成 Core ingest 与身份/隐私决策。
2. 闹铃用户命令必须有 canonical owner；列表/取消仅限 owner；自然语言不得指定他人作为 owner。
3. 主动场景不得用 CLI/env 原始字符串作为最终身份；身份不明不写 habit trend，不读取私人上下文。
4. 任务旧快捷路径迁入统一 ChatAdapter/Core 入口；不得在 V4 前独立读写 TaskService。

### P1：感知证据与策略收敛
1. voiceprint/presence/scene 均提供 `source`、`observed_at`、`confidence`、`expires_at`、`verification_status`。
2. Core 对 evidence 统一验证；旧适配器无 evidence 时只允许匿名、瞬时、非私人交互。
3. InterruptPolicy 不以 `*` 作为可访问私人上下文的身份；策略异常或 evidence 过期时静默/通用回应。

### P2：任务、提醒与系统执行权限
1. 任务/提醒统一 owner、viewer、visibility、source_event_id、idempotency_key。
2. 用户写操作与系统定时执行使用不同 capability；系统触发不能扩大用户读取权限。
3. 全部 CLI 子命令逐项分级：用户命令必须鉴权；scheduler 只允许 due/ring 最小权限操作。

### 验收用例（必须自动化）
- 未知声纹 + presence 推测：不得自动认领儿童身份或读取私人数据。
- 伪造 `TANGTANG_SPEAKER` / `TANGTANG_MEMBER_ID`：不得获得该成员权限。
- 访客说“列出爸爸的闹铃/取消全家闹铃”：拒绝，不泄露记录、不改变数据。
- A 说“我的任务”：只能读 A；A 不能完成/取消 B 的任务。
- 无身份主动场景：不读取成员记忆、不写习惯、不向特定成员播报。
- evidence 缺失、低置信度、过期、未验证：用户级私有操作 fail closed。
- scheduler due/ring：只触发已授权记录，不把系统身份转换为用户身份。
- 并发双人对话：上下文、任务、提醒、TTS 受众不可串线。

## 分批实施状态（2026-11-24）

| 批次 | PR | 当前结果 | 未覆盖事项 |
|---|---|---|---|
| 入口审计基线 | #92 | 静态调用链与风险矩阵已提交 | 不代表运行时已经全部接入 |
| 语音/任务/闹铃/主动场景第一批 | #93 | 待合并；Python 3.10/3.11 CI 通过 | voiceprint 新鲜证据、全部 legacy CLI、短回合账本 |
| Core 身份失败关闭与旧提醒隔离 | #95 | 待合并；Python 3.10/3.11 CI 通过 | 需要与 #93 的入口修复共同进入 main |
| 关闭旧家庭记忆直接写入 CLI | #96 | 待合并；Python 3.10/3.11 CI 通过 | 仍需审计所有非 CLI 的直接 store writer |
| 声纹身份失败关闭 | #97 | 待合并；首次 CI 暴露旧测试依赖，已修正测试，最新提交待 CI | 当前 voiceprint 算法只能给出未校准候选，成员专属语音能力暂时关闭 |
| 成员记忆 CLI viewer 授权 | #98 | 待合并；Python 3.10/3.11 CI 通过 | 家庭级本地报表仍作为本机操作员命令，后续需接入 viewer-aware Core API |
| 感知证据契约 | #88 | 待合并 | voiceprint/presence 适配器尚未全面产出并强制使用 evidence |
| 私人记忆 owner/viewer 授权 | #89 | 待合并 | 需与全部旧记忆写入/读取入口逐项核对 |

PR #94 是依赖 #93 的临时堆叠 PR，已关闭并由面向 main 的 PR #95 替代，不作为独立交付项。

## 下一批明确待办

1. **声纹证据接入**：`cat-vp.py` 当前识别命令只输出成员名；需输出 source/observed_at/confidence/expires_at/verification_status，并由 Core 强制校验，不能仅靠 roster 命中。
2. **主动场景证据**：`cat-presence.py` 的 Wi-Fi/麦克风能量是场景提示，不是身份凭证；场景事件需有独立证据与有效期，身份不明时只允许通用内容，不得读取私人记忆。
3. **短回合系统目标权限**：`cat-turn.sh` 是系统定向互动，不是声纹确认的用户身份；其 target、账本写入和报告读取需与 user identity 分离并标记 system actor。
4. **旧家庭记忆 CLI**：`cat-family.py observe/log` 仍保留直接写入接口；语音主链已移除该写入，但需关闭/迁移剩余直接调用。
5. **记忆查询 CLI**：`cat-memory.py today/recent/state/next/trends/emotion` 需区分家庭管理员读取、成员自有读取与系统调度读取，不能以任意命令行成员参数代替 viewer 授权。
6. **旧主动提醒**：非 V4 的 `cat-remind.sh` 路径已在 #95 中默认关闭；只有显式设置 `TANGTANG_ALLOW_LEGACY_PROACTIVE=1` 才能临时启用。后续应逐个迁入 Core，再删除回退开关。

## 状态说明

本文件是对当前 main 源码的静态调用链审计与实施基线。#93 和 #95 尚未合并，main 当前仍保留这些旧入口风险；CI 通过不等于 Mac mini 实机验证。后续代码变更应按入口分批提交 PR，每个 PR 配套负向权限测试；不在未经审查的情况下批量删除 V3 兼容入口或旧数据。
