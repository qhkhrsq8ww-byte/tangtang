# V3 接入状态（2026-09-03）

## 结论

线上 `main` 已完成 V3/V4 核心接入（`core/`）。本轮将文档约定的顶层包补成**门面**，并完成线上线下同步与剩余分支合入。

## 顶层门面 → 实现

| 文档模块 | 门面包 | 实现 |
|---|---|---|
| family | `family/` | `core.identity` + `core.adapters.family_loader` |
| memory | `memory/` | `core.memory`（含 Family Memory 2.0） |
| context | `context/` | `core.context.builder` |
| behavior | `behavior/` | `behavior.character_state` + `core.policy.*` |
| interaction | `interaction/` | `core.response.orchestrator` |
| presentation | `presentation/` + `core.presentation` | 媒体注册表 / 动画 |

## 运行时入口（旧脚本保留）

- `cat-talk.sh` → quiet-hours + `tangtang-speak-gate.py` + `cat-brain.py`
- `cat-brain.py` → `behavior.legacy_adapter` → CharacterStateEngine
- `cat-remind.sh` → `cat-talk.sh`（主动提醒统一过 speak gate）
- `cat-chat.py` → `core.policy.speak_gate`

## 分支同步

- 本地 `main` fast-forward 到 `origin/main`
- 合入仅剩领先分支：`family-memory-2-449b`、`openclaw-field-20260828-449b`
- 其余远程分支相对 `main` ahead=0（已在历史中合入）

## 未做（刻意）

- 不删除 `cat-*`（V3 第四阶段清理）
- 不 merge 本地旧分支 `feature/character-state-engine-20260829`（与线上 CSE 重复；线上以 `behavior/character_state.py` 为准）
