# V3 / V4 调用路径与退役计划

> 基线：main `d3d3e7009e12d9306db36dec8de00e6b575dbc10`
> 日期：2026-11-24
> 原则：先收敛生产入口，不按文件名批量删除 V3 资产。

## 1. 对话主入口

```text
cat-voice-chat.sh
  └─ exec cat-voice.sh
       └─ cat-chat.py
            ├─ 默认 / TANGTANG_V4_PIPELINE=1
            │    └─ _private_cli_reply()
            │         └─ ChatAdapter.turn()
            │              └─ PrivacyPipeline.ingest()
            │                   └─ Identity → PrivacyPolicy → Event → gated memory
            │              └─ SpeakGate → ContextBuilder → optional LLM
            │              └─ ResponseOrchestrator
            │
            └─ legacy V3（仅双重显式开关）
                 └─ direct chat() + cat-chat-history.json
```

本轮收敛：
- V4 保持默认。
- 仅设置 `TANGTANG_V4_PIPELINE=0` 不再足以进入 V3。
- 必须同时设置 `TANGTANG_ALLOW_LEGACY_V3=1` 才能启用旧直连路径。
- V3 回退是人工应急开关，不是自动故障降级；Hermes/V4 失败不得静默切换到旧云模型。

## 2. 其他运行入口分类

| 入口/模块 | 当前职责 | 处理策略 |
|---|---|---|
| `cat-voice-chat.sh` / `cat-voice.sh` | 录音、STT、调用对话入口、TTS | 保留为设备适配层；逐步将业务判断下沉 Core |
| `cat-chat.py` | CLI 对话总入口、V4/V3 选择、模型后端选择 | V4 主入口；V3 仅人工显式回退 |
| `cat-living.py` | 主动场景 CLI，调用 TangTangRuntime | 保留薄适配器；身份参数必须视为候选输入 |
| `cat-turn.py` / `cat-turn.sh` | 客厅短回合、能量/关键词判断、只写标签账本 | 独立低延迟体验路径；未来统一事件与可信度契约，不强行改成 LLM 对话 |
| `cat-brain.py` | 旧版角色状态、情绪漂移、话术生成与旧状态文件 | 迁移角色状态数据后再退役；不得与 V4 记忆自动合并 |
| `cat-memory.py` | Family Memory 2.0 查询/派生家庭状态 | CLI 外壳可保留，核心由 `core.memory.family_memory_v2` 承担 |
| `cat-alarm.py` / `cat-remind.sh` | 闹钟与提醒 | 保留设备/调度入口；业务权限由 Core TaskService/dispatcher 收敛 |
| `cat-presence.py` / `cat-vp.py` | 在场与声纹识别 | 作为感知适配器保留；输出带 source/time/confidence/expiry/status 的证据，不直接授予权限 |
| `family/`, `memory/`, `context/`, `behavior/`, `interaction/` 顶层兼容包 | V3 导入兼容门面 | 暂不删除；先统计外部调用，迁移 import 后再退役 |

## 3. 不应混为一谈的三类 V3 资产

1. **旧业务实现**：重复的身份、记忆、隐私、对话决策逻辑。目标是迁入 Core 并减少双重实现。
2. **硬件/系统适配脚本**：录音、音频、投影、TTS、启动脚本。即使文件来自 V3，也可能长期作为薄适配层保留。
3. **数据兼容与导入工具**：旧 JSON 状态、账本、对话历史。需单独做 schema 映射、隐私重分类和用户可控迁移，不自动合并。

## 4. 收敛路线

### P0：入口唯一化（当前）
- 默认对话只走 V4。
- legacy V3 必须双重显式 opt-in。
- Hermes 配置失败只返回本地安全 fallback，不切换到其他云模型。
- CI 覆盖 V4 默认和 legacy 双开关条件。

### P1：业务决策下沉
- 将 CLI 中身份解析、隐私判定、提醒/任务权限、主动打扰决策统一委托 Core。
- shell/python 脚本只负责设备 I/O、参数采集和结果播放。
- 对每个入口记录调用的 Core API 版本和输入来源。

### P2：数据迁移
- 盘点 `cat-chat-history.json`、`cat-memory.json`、`cat-state.json`、`cat-habits.json`、`cat-turn-ledger.json` 等本地文件。
- 按成员、隐私等级、是否原话、TTL、是否可删除建立迁移矩阵。
- 迁移前备份；默认不导入旧对话原文；迁移后做数量核对和抽样验证。
- 不将旧数据直接写入 FamilyMemory；必须经过 Core PrivacyPolicy。

### P3：退役门槛
- 全部生产入口已在 CI 和实际语音链路中证明调用 V4/Core。
- V3 业务逻辑无活跃调用，只有经过批准的兼容适配仍在使用。
- Mac mini、投影、音频、唤醒、主动场景和故障恢复验收通过。
- 至少一个完整观察周期无 V3 回退使用，且旧数据迁移/备份策略确认。
- 达到以上条件后再移除 legacy V3 chat/history branch；不要提前删除硬件脚本和兼容门面。

## 5. 当前不宣称完成的事项

- 未完成所有 shell/CLI/主动场景入口的静态调用图。
- 未完成 Mac mini 实机、麦克风、声纹、投影和 TTS 端到端验收。
- 未完成旧 JSON 数据迁移或清理。
- 未退役 `cat-brain.py`、V3 voiceprint 实现、顶层兼容包。
