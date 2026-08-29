# TangTang V4 — System Integration Report

**Branch:** `cursor/v4-integration-449b`  
**Parent:** `cursor/v4-five-rounds-449b` (182 PASS, P0=0). Not a five-round redo. Not V5. **Not merged to `main`.**  
**Living-room cat stack:** `cursor/living-room-ready-449b` was **read**, not dump-merged.  
**`data/family.json`:** not overwritten. `姐姐` / `弟弟` remain `child_12` / `child_9`. Product aliases `qiaqia` / `hanghang` stay in `IdentityResolver`.

Command: `python3 -m unittest discover -s tests/v4 -t . -v`

---

## Totals

| | Count |
| --- | --- |
| **tests/v4** | **228 PASS / 0 FAIL / 0 SKIP** |
| prior five-round suite | 182 PASS (unchanged, not weakened) |
| new integration tests | 46 PASS |
| **P0** | **0** |
| **P1 leftover** | **4** (honest V3 bypasses; see below) |
| **P2 leftover** | **3** |

No FAIL→SKIP. V3 `cat-vp.py` / `cat-chat.py` were not deleted.

---

## Current vs old V3 architecture

### V3 (still on disk)

```
Mic → cat-stt / cat-voice.sh → cat-vp.py identify()
                            → cat-chat.py (concat data/*.json + LLM)
                            → cat-say.sh / vendor TTS   (direct TTS)
Living room → cat-brain / cat-remind.sh → cat-say.sh  (direct speak)
Habits → cat-habits.json (on living-room-ready: cat-family.observe writes text)
```

V3 `cat-chat.py` still builds a system prompt from `tangtang-profile.py` + local JSON and can send child speech to the LLM **without** `PrivacyPolicy`. That CLI is the old path.

### V4 wired path (this PR)

```
Mic → STT → VoiceAdapter → Observation {type: voice.observed, candidate_member, confidence}
    → IdentityResolver → Event → EventBus + JSONL Event Store
    → Family Brain (Memory, ContextBuilder, PrivacyPolicy, InterruptPolicy, Decision)
    → ResponseOrchestrator → PresentationAction
    → TTSAdapter / ProjectionAdapter / AnimationController
```

Proactive: `LivingRoomAdapter` (手机/久坐/吃饭/运动/睡觉/回家/离家) → Event → Brain → InterruptPolicy (`SPEAK|SILENT|DELAY|LOG_ONLY`) → Response → presentation.

**Forbidden on the new path (enforced in code + tests):**

- `cat-chat` → TTS directly
- living-room adapter → speak to a child without InterruptPolicy
- LLM → projection / TTS / shell / files / DB

LLM receives PrivacyPolicy-filtered context only. Failures of STT / Voice / Identity / Memory / LLM / TTS / Projection / Animation are `isolate()`-local; the process does not die. LLM down → `汪汪～`. TTS fail → presentation error recorded, **Event kept**.

---

## Adapters

| Adapter | File | What it wraps | What it does not do |
| --- | --- | --- | --- |
| Voice | `core/adapters/voice_adapter.py` | V3 `cat-vp.py::identify()` via importlib | Does not rewrite voiceprint. `unknown` never becomes `child_9` / `hanghang`. |
| Chat | `core/adapters/chat_adapter.py` | Reuses `looks_risky` / `sanitize_output` only | Does **not** call V3 `chat()` (unfiltered prompt concat). Always `pipeline.ingest` → PrivacyPolicy. |
| Living room | `core/adapters/living_room_adapter.py` | Scene names from the living-room product | Does not merge `cat-family.py` / `cat-turn.py`. Does not speak. |
| TTS | `core/adapters/tts_adapter.py` | Injected `speaker(text)` | Core never calls Baidu / macOS speak. |
| Projection | `core/adapters/projection_adapter.py` | Injected `projector(action)` | Brain emits `PresentationAction` only. |
| Animation | `core/adapters/animation.py` | `站立` / `眨眼` / `走路` / `跑步` | Outside Brain. `AnimationAction` → frames. |
| Event store | `core/adapters/event_store.py` | JSONL under `TANGTANG_HOME` | No SQLite / Kafka / Redis. Duplicate `event_id` is a no-op. |
| Family | `core/adapters/family_loader.py` | `data/family.json` | Does not hardcode members. Does not overwrite names. |

Runtime: `core/runtime/loop.py` (`TangTangRuntime`) and `tangtang_runtime.py`.  
`TANGTANG_HOME` only. No `/Users/lv/.qclaw/workspace/cat/`.

---

## Data flow (new path)

1. **Observe** — STT (injected; failure → empty transcript, Event still logged) and/or VoiceAdapter.
2. **Identify** — `candidate_member` → `IdentityResolver`. `unknown` / `访客` → `None`. Voiceprint-only (no candidate/label) still unknown.
3. **Event** — canonical `Event` (`id, type, ts, source, privacy, payload, member_id?`). PRIVATE requires `member_id`. Child utterance payload is redacted on the Event; raw lives in `PrivateMemory` only.
4. **Bus + store** — `EventBus.accept` + `JsonlEventStore.append`. Same `event_id` → `duplicate=True`, no second SPEAK / no second memory write.
5. **PrivacyPolicy** — single gate. Child (hanghang / `child_9` / 弟弟, qiaqia / `child_12` / 姐姐) → PRIVATE, fail-closed. Adult → FAMILY unless clearly private. Unknown → PUBLIC, not a default child.
6. **Memory** — PRIVATE / FAMILY / PUBLIC; `created_at`, `expires_at`, `confidence`, `source_events`. Family summary is structured `{mood, interaction_count}` and **still rejected for children / PRIVATE**.
7. **ContextBuilder** — MemoryPort + PolicyPort only. Other members do not receive PRIVATE payload.
8. **Decision** — InterruptPolicy. Sleeping → `SILENT`. Just reminded → `DELAY`. Low value → `LOG_ONLY`. Phone cooldown → first `SPEAK`, repeat `LOG_ONLY`.
9. **Response** — `PresentationAction`. CopyGuard rewrites surveillance lines to `汪汪～ 要不要起来走一走？` (including 「我知道你已经玩手机43分钟了。」).
10. **Presentation** — TTSAdapter / ProjectionAdapter / AnimationController. Brain does not call devices.

Offline (`TangTangRuntime(offline=True)`): policy, silent, persona `汪汪～`, animation frames, JSONL event log still work.

---

## Privacy boundary

Everything that can reach an LLM (Event, Memory, History, Family Summary) on the **new path** goes through `PrivacyPolicy`.

Child bully line `我今天被同学欺负了。`:

- classified PRIVATE, owner `child_9`
- stored in `PrivateMemory` with TTL
- **not** in FamilyMemory / FamilySummary / ParentContext / HabitStore
- **not** in `SafeLogger` ordinary lines
- **not** in dad’s FAMILY context
- structured summary `add_structured(member_id="child_9", mood=...)` raises `MemoryError` (does not bypass PRIVATE)

---

## Evidence from this test run

Not “架构已经接入”. These IDs came from `python3 -m unittest` on this agent:

### 1. child9 voice → Identity child_9 → Event → PRIVATE Memory → filtered Context → Response → TTS

```
EVIDENCE1 event_id=evt_0b1ba98a7cdf4ed68309dc7adc504f65
          member=child_9
          privacy=PRIVATE
          memory=priv_3dff5f71e5024cd5a596195f8a733590
          decision=SPEAK
          tts='汪汪～ 糖糖陪你！我们一会儿再动一动好不好。'
```

Source: `tests/v4/test_voice_integration.py::test_child9_voice_to_private_memory_context_response_tts`  
(`candidate_member=hanghang` → Identity `child_9`, utterance = bully line.)

Runtime chain (same invariants): `evt_94f810186e6146a9b72e838753fad943` privacy=PRIVATE.

### 2. phone.usage → Event → Policy SPEAK then LOG_ONLY → Response → TTS

```
EVIDENCE2 first_id=evt_f6b494637f0445e681f91be189aac4c1  first_decision=SPEAK
          second_id=evt_413dbe081b5c45efbaa3860b374c3bab second_decision=LOG_ONLY
          tts='汪汪～ 要不要起来走一走？'
```

Source: `tests/v4/test_living_room_integration.py::test_phone_speak_then_log_only`  
(kind `手机` → `phone.usage`. Repeat tick is LOG_ONLY, not a second nag. Copy has no “43分钟”.)

Sleeping → SILENT; `recently_interrupted` → DELAY; `importance=low` → LOG_ONLY (covered in the same module).

---

## What is truly wired vs still bypassing

### Wired (new runtime path)

- `TangTangRuntime.handle_voice` / `handle_utterance` / `handle_living_room` / `present`
- `ChatAdapter.turn` always calls `PrivacyPipeline.ingest` (tests fail if that call is removed)
- Voice unknown stays unknown
- Living-room kinds map to V4 event types then InterruptPolicy
- TTS / projection failure keeps Event
- Duplicate `event_id` does not duplicate SPEAK
- Offline loop (no LLM, unwired speaker)

### Still bypassing (honest leftover — parent 验收)

These V3 entry points still exist **on purpose** (do not delete). They are **not** on `PrivacyPipeline` unless someone sets the new flag / calls `TangTangRuntime`.

| Path | Bypass | Notes |
| --- | --- | --- |
| `code/cat/cat-chat.py` CLI **default** | **yes** | Concatenates prompts, can skip PrivacyPolicy. `TANGTANG_V4_PIPELINE=1` uses ChatAdapter. |
| `code/cat/cat.sh` / `cat-voice.sh` | **yes** | Still `cat-chat` then `cat-say.sh` (direct TTS). |
| `code/cat/cat-vp.py` CLI | **partial** | `identify()` is wrapped by VoiceAdapter. Direct `log` / `summary` is still V3 (habit file). `log` already fail-closes child raw via PrivacyPolicy from Round 2. |
| `code/cat/cat-remind.sh` / `cat-brain.py` | **yes** | V3 cooldown `should_speak`. Not the V4 InterruptPolicy. `core.compat.should_interrupt` is available; cat-brain was not rewritten. |
| `cursor/living-room-ready-449b` (`cat-family.py`, `cat-habits.py`, `cat-turn.py`) | **yes, other branch** | Not dump-merged. If that stack is run as-is it still writes living-room files. V4 `LivingRoomAdapter` is the integration stand-in. |

Closing those CLIs by default was out of scope for a faithful wrap (Mac living-room must keep downloading). The **new path cannot skip PrivacyPolicy**; the old CLIs can.

---

## PASS / FAIL / SKIP

| Area | Result |
| --- | --- |
| Prior 182 v4 tests | **PASS** |
| Voice integration | **PASS** |
| Chat integration + bully chain | **PASS** |
| Living-room events + policy | **PASS** |
| TTS fail keeps Event | **PASS** |
| Projection fail does not crash Brain | **PASS** |
| Animation 站立/眨眼/走路/跑步 | **PASS** |
| Duplicate event | **PASS** |
| Offline runtime | **PASS** |
| Unknown ≠ child_9 | **PASS** |
| family.json names | **PASS** (姐姐/弟弟 untouched) |
| Real Mac mic / speak / HDMI / launchctl | **SKIP** (Linux agent; tests not weakened to skip) |
| Dump-merge living-room-ready | **not done** (by brief) |

---

## P0 / P1 / P2

| Sev | Item | Status |
| --- | --- | --- |
| P0 | Privacy gate on new speech path | **closed** |
| P0 | unknown defaulting to hanghang | **closed** |
| P0 | TTS/LLM/projection crash / drop Event | **closed** |
| P0 | Surveillance copy | **closed** |
| P1 | V3 `cat-chat.py` default CLI | **open** (flag to opt into V4) |
| P1 | `cat.sh` / `cat-voice.sh` → `cat-say.sh` | **open** |
| P1 | living-room-ready cat stack not merged | **open** (adapter only) |
| P1 | `cat-remind.sh` / `cat-brain.should_speak` | **open** |
| P2 | Real device TTS / mic / projection | **open** (Linux) |
| P2 | Product cooldown 15 min | **open** (unchanged) |
| P2 | V3 CLI remaining as the Mac download path | **open** by design |

---

## Verdict

**Integration PASS for a draft stacked PR onto `cursor/v4-five-rounds-449b`.**  
Do not merge `main` from this agent. Do not start V5. P0 on the new path is 0. Remaining P1 is the honest V3 CLI / living-room-ready bypass list above — that is the parent’s later 验收, not hidden as “already wired”.
