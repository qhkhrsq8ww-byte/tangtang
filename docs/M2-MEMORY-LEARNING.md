# m2 — 记录/学习（Memory 层）

**日期：** 2026-09-03  
**节奏（已定）：**

| 项 | 规则 |
|---|---|
| 情绪漂移 | 按距上次互动小时连续衰减：`loneliness +5/h`，`happiness −1.5/h`；深夜压 `energy` |
| 情绪落盘 | 每日最多 1 条 snapshot（`memory/emotion-snapshots.jsonl`）+ 实时 `memory/emotion-state.json` |
| 习惯趋势 | 日账本 + **7 日**滚动；**≥14 个活跃日**且事件数 ≥5 才升为 stable |
| 隐私 | 儿童原话只进 PrivateMemory；habit trends / family 只记 tag 与计数 |

## 模块

- `core/memory/emotion_drift.py` — `apply_drift` / `EmotionDriftStore`
- `core/memory/habit_trends.py` — `HabitTrendStore`
- `core/memory/learning.py` — `LearningMemoryService` 组合层
- `code/cat/cat-brain.py` — `drift()` 走同一套衰减，并 best-effort 写日快照；说话后记 habit tag

## 未做

- 不替换 Family Memory 2.0 读路径（仍兼容）
- 不删 `cat-state.json` 兼容键
