# POST-MERGE PR #27 回归

## 身份

| 项 | 值 |
| --- | --- |
| PR | [#27](https://github.com/qhkhrsq8ww-byte/tangtang/pull/27) 收敛：先判说不说，能开口再用最少 token |
| 状态 | **MERGED**（merge commit，未 squash） |
| PR HEAD | `6520e51307a7698f71a69e32de81f519566cdffd` |
| merge commit | `d91233bbc14a0d1e588e6c8c725b02f050ee9dc5` |
| main HEAD | `d91233bbc14a0d1e588e6c8c725b02f050ee9dc5` |
| 合入时间 | 2026-09-03T02:46:24Z |

## 合入前检查

- 工作区干净（相对 PR 分支）
- PR 文件无真实 API Key（`git diff origin/main...HEAD` 无 sk-/AKIA/ghp_/PEM）
- `mergeable = true`
- 无新增 P0/P1

## 测试

### PASS

| 套件 | 结果 |
| --- | --- |
| `python3 -m pytest -q` | **434 passed** |
| `python3 -m unittest discover -s tests/v4` | **435 OK** |
| `tests.v4.test_speak_gate` + privacy + alarm + character-state + chat + live_wrappers | **109 OK** |
| `test-v3-family.sh` | 22 PASS |
| `test-child-reactions.sh` / `test-habit-growth.sh` / `test-english-buddy.sh` / `test-today-plan.sh` / `test-openclaw-report.sh` | ok |
| `compileall` core / behavior / code/cat | ok |

### SKIP

| 项 | 原因 |
| --- | --- |
| `test_desktop_pet_browser` Chrome 播 MP4 | **ENVIRONMENT BLOCKED**（chrome timed out）。HTML 存在测通过。 |

### FAIL（非本 PR 引入，未改成 SKIP）

| 套件 | 结果 | 说明 |
| --- | --- | --- |
| `test-v3.1-privacy.sh` | 30 PASS / **2 FAIL** | TTS edge（云 Linux 无实声）、launchd plist（非 Darwin） |
| `test-openclaw-plan.sh` | FAIL | 下午等到整点入口与 rest-day 文案未对齐；PR #27 未改这些文件 |
| `test-hwcheck.sh` | FAIL | Linux skip 文案；PR #27 未改 |
| `test-today-selftest.sh` | FAIL | 夹具听窗 stub 未接到 main 听窗；PR #27 未改 |

首次 `pytest` 曾因环境无 Pillow 红 2 条 V10 单主体测；装上 Pillow 后与 unittest 一致为绿。

## 清单核对

| 项 | 结论 |
| --- | --- |
| speak-gate 在 STT / LLM 之前 | **PASS**。`cat-voice.sh` 在 `cat-listen` / STT 前调 `tangtang-speak-gate.py`。`cat-chat.py` / `handle_utterance` / `ChatAdapter.turn` 在注入 LLM 前 `may_call_llm`。 |
| 主动提醒 22:30–07:00 不主动开口 | **PASS**。`channel=remind` 或非 interactive 的 chat/voice 在 quiet hours → SILENT。 |
| 人主动讲话仍回应 | **PASS**。interactive chat/voice 夜间 SPEAK；`test_chat_quiet_hours_interactive_may_speak`。 |
| 上学未到家的孩子不自动开口 | **PASS**。`school_hours` + child + `presence_home=False` → SILENT，boom LLM 不被调用。 |
| `TANGTANG_V4_PIPELINE=1` 不双跑 | **PASS**。V4 块不调 V3 `chat()` / `build_persona()` / 历史文件。 |
| 提醒 / 英语 / 听窗优先已有话术 | **PASS**。`TANGTANG_TURN_LLM is ignored`；无 `cat-chat.py`。 |
| 听不清不连续追问 | **PASS**。`cat-voice.sh` 无「再说一次」「再聊聊」。 |
| 闹铃仍响 | **PASS**。`channel=alarm` 恒 SPEAK；`test_alarm` 绿。 |
| speak-gate 不绕过 PrivacyPolicy | **PASS**。SILENT 早退不进 LLM。SPEAK 后仍 `PrivacyPipeline.ingest`；儿童 PRIVATE 不进家庭库 / `allow_log_raw=False`。无 PRIVATE → 日志 → 说出去。 |
| V4 未绕回 V3 direct path | **PASS**。生产对话 `TANGTANG_V4_PIPELINE=1` → `TangTangRuntime.handle_utterance`。 |
| CharacterState 仍是视觉状态入口 | **PASS**。本 PR 未改 `behavior/character_state.py`；`test_character_state_*` 绿。 |
| desktop pet | **PARTIAL**。页面在；Chrome 实播 **BLOCKED**。 |
| TTS | **BLOCKED**（本环境）。`test-v3.1-privacy` TTS edge FAIL，非本 PR。 |

## 结论

PR #27 已安全进入 main。

下一阶段（本次不做）：Family Memory 2.0。
