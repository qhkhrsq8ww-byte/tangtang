# 待办与推进状态（2026-09-03）

## 已完成

| 项 | 状态 |
|---|---|
| m1 风险升级 fail-closed | ✅ |
| m2 情绪漂移 + 习惯趋势 | ✅ |
| V3/`core` 接入 + 顶层门面 | ✅ |
| 分支合入 + 推远程 | ✅ |
| **m3 聊天 → LearningMemory** | ✅ 本轮 |
| **HabitTrends → FM2 today/recent** | ✅ 本轮 |

## 仍未完成（按价值）

### P1 产品/架构
1. **`TANGTANG_V4_PIPELINE` 默认仍关闭** — cat-chat 默认 V3 prompt 拼接；应评估默认开 V4 或双跑。
2. **客厅 living-room 旧栈未 dump-merge** — 仅有 `LivingRoomAdapter`；rest-day / English buddy 等产品场景在历史分支。
3. **V3 第四阶段清理** — 不删 `cat-*`，重复路径仍在。

### P2 体验/运维（多需 Mac 实机）
4. VAD / ASR 体验（静音停录、提示音）
5. 百度 Key 轮换与环境变量化
6. launchd / 合盖 / 24h 运转（硬件）
7. `test_alarm.py` 在 Windows 上因 `/bin/bash` 假设失败（环境差，非功能回归）

### P2 表现
8. 旧页 `cat-stage` / `tangtang-states` 静态图路径对齐视频主线
9. Asset Registry 真正驱动所有 HTML（部分仍手写 STATES）

## 本轮改动
- `cat-chat.py`：成功回复 / 风险回复后 `_learn_turn`
- `family_memory_v2.py`：读取 `habits/habit-trends.json`
- `cat-memory.py`：`trends` / `emotion` 子命令
