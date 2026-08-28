# TangTang V4 Round 1 — Architecture Review

**Round:** 1 of 5 (architecture / boundary correctness only)  
**Status:** review recorded; P0 not yet closed in this commit  
**Do not enter Round 2.**  
**Parent branch:** `feat/v4-family-brain-core-20260828`  
**This branch:** `cursor/v4-round1-architecture-449b`  
**Not merged this round:** `cursor/living-room-ready-449b` (compatibility check only)

糖糖是比熊，口头禅「汪汪～」。不是监督机器人。

---

## Parent choice

Inspected after `git fetch`:

| Ref | `core/` | living-room cat (turn/habits/openclaw/school) | family.json names |
| --- | --- | --- | --- |
| `main` | missing | old cat only | schema example only |
| `cursor/living-room-ready-449b` (PR #16) | missing | **yes** | 洽洽 / 航航 |
| `codex/v3-family-brain-integration-20260828` (PR #15) | missing | no | 姐姐 / 弟弟 + 妈妈 |
| `fix/v3.1-privacy-paths-20260828` (PR #17) | missing | no | 姐姐 / 弟弟 + 妈妈 |
| `feat/v4-family-brain-core-20260828` | **stub modules present** | no (cat is V3 line) | 姐姐 / 弟弟 + 妈妈 |

**Parent = `feat/v4-family-brain-core-20260828`.** It is the only line with V4 `core/`. Living-room is another stack. Round 1 does **not** merge living-room-ready (would mix two products and risk overwriting cat-*). A later PR to `main` is still required; a later compatibility merge with living-room is out of scope for Round 1.

`data/family.json` on this parent is **not** overwritten this round (still 爷爷/奶奶/爸爸/妈妈/姐姐/弟弟, ids `child_12` / `child_9` / `mom`).

### Identity alias map (code only; family.json untouched)

| Observation labels | Product id (living-room) | Registry id on this parent |
| --- | --- | --- |
| 12岁姐姐, 姐姐, 12岁女孩, girl, 洽洽, qiaqia, child_12 | **qiaqia** | child_12 if present in members |
| 9岁弟弟, 弟弟, 9岁男孩, boy, 航航, hanghang, child_9 | **hanghang** | child_9 if present in members |
| 妈妈, 妈, mom, mother | **mom** | mom if present |

Voiceprint is **not** the primary identity path. Primary: school-hours flag + presence + optional coarse features. Projection is a **presentation sink**, never LLM-controlled.

---

## What existed vs what Round 1 must add

**Existed (stub `core/`):** `Event`, `EventBus`, `IdentityResolver`, `MemoryStore`, `ContextBuilder`, `InterruptPolicy`, `ResponseOrchestrator`. No Protocol/ABC ports. No `tests/v4/`. No payload bound. Bus does not isolate handler exceptions. ContextBuilder takes raw dicts (caller can dump PRIVATE). Identity is exact-string voice lookup. Orchestrator returns an unvalidated dict. No `should_interrupt` shim for cat-*.

**Must not throw away:** `code/cat/` (cat.sh, cat-brain, quiet hours, V3.1 privacy). Living-room cat-turn/habits/openclaw/school hours stay on their branch.

---

## Counts (this review commit, before boundary fixes)

| Severity | Count | Notes |
| --- | --- | --- |
| **P0** | **8** | must be 0 before Round 1 can conclude; still not Round 2 |
| **P1** | **5** | |
| **P2** | **3** | |
| Tests | not run in this commit | `tests/v4/` missing |

---

## 1. 系统架构师

### Findings

| ID | Sev | Finding |
| --- | --- | --- |
| A-P0-1 | P0 | Event canonical fields are `event_id` / `event_type` / `timestamp`, not required `id` / `type` / `ts`. No payload bound. Empty `event_id` is accepted (`default_factory` still allows `event_id=""`). |
| A-P0-2 | P0 | `EventBus.publish` calls handlers without try/except. One handler exception kills the process. No duplicate `event_id` guard. No injected clock. |
| A-P0-3 | P0 | No Protocol/ABC for EventBus, Identity, Memory, Context, Policy, Response. |
| A-P0-4 | P0 | `ContextBuilder` does not take MemoryStore/Policy ports. Caller passes `memories=` and `family=` blobs — PRIVATE can be stuffed in. It does **not** open files today (good), but the port boundary is missing. |
| A-P1-1 | P1 | Subpackages lack `__init__.py`. Identity docstring treats voice as the path. No `core.compat.should_interrupt` for cat-brain. |
| A-P2-1 | P2 | `core/__init__.py` does not export a public surface. |

**Forbidden cycles:** Memory does not import Context (good). Context does not import Memory module (good, but only because it has no ports). After fix, Context may depend on **MemoryPort / PolicyPort** in `interfaces.py`; Memory must still not import Context.

**LLM boundary:** InterruptPolicy is deterministic (good). ResponseOrchestrator holds an optional text `responder` (allowed) but does not emit a validated presentation action (must-solve #8).

**Fix (this round):** complete Event schema + constructors; in-memory EventBus with clock + catch; Protocol ports; ContextBuilder(memory, policy) only; MemoryStore no Context import; `core.compat.should_interrupt`; comment on `cat-brain.should_speak` (do not delete / rewrite cat-*).

**Tests:** `tests/v4/test_event.py`, `test_event_bus.py`, import-cycle assertions in memory/context tests.

---

## 2. 隐私与儿童安全审查员

### Findings

| ID | Sev | Finding |
| --- | --- | --- |
| P-P0-1 | P0 | `MemoryStore.query(member_id=..., scope="PRIVATE")` has no `viewer_id`. Any caller who knows another child’s id can read that child’s PRIVATE. Boundary fix: require viewer; PRIVATE only if viewer == member. |
| P-P0-2 | P0 | ContextBuilder privacy filter is a post-hoc list filter on caller-supplied memories. FAMILY scope currently drops PRIVATE (good) but PUBLIC scope of PRIVATE list is only as honest as the caller. |
| P-P1-1 | P1 | PRIVATE Event requires `member_id` (good). Payload is not bounded — a PRIVATE transcript could be huge. |
| P-P2-1 | P2 | Deep data-flow (disk, logs, cat-vp, habits) is **Round 2**. Do not expand this round except log-payload isolation on the new bus. |

**Fix:** viewer-scoped MemoryPort; ContextBuilder queries the port with `viewer_id=who.member_id`; Event payload max bytes; EventBus must **not** log payload / speech on handler errors.

**Tests:** PRIVATE/FAMILY/PUBLIC matrix; cross-member PRIVATE denied; huge payload rejected.

---

## 3. AI / 对话架构师

### Findings

| ID | Sev | Finding |
| --- | --- | --- |
| I-P0-1 | P0 | ResponseOrchestrator returns a loose dict. No validated action. Nothing stops a future responder from returning sink callables. TTS/projection are not called today (good) but the contract is unenforced. |
| I-P1-1 | P1 | IdentityResolver.resolve(str) is not observation-based. Event does not embed the resolver (good — keep it that way). |
| I-P1-2 | P1 | Policy has no school-hours / presence inputs (those must be observation flags, not LLM, and not file I/O inside Policy). |

**Fix:** `PresentationAction` with allowed decisions only; orchestrator never accepts tts/projection callables; IdentityResolver.resolve(observation) → member_id; InterruptPolicy reads observation flags only.

**Tests:** `test_response.py`, `test_identity.py`, `test_policy.py`; source scan that orchestrator/policy do not import TTS/projection/LLM.

---

## 4. 家庭产品经理

### Findings

| ID | Sev | Finding |
| --- | --- | --- |
| F-P1-1 | P1 | This parent’s family.json is 姐姐/弟弟, not 洽洽/航航. **Do not overwrite names.** Alias in IdentityResolver only. 糖糖是比熊汪汪～, not a supervisor — InterruptPolicy must default to less speech (quiet hours, school hours, active conversation → SILENT/DELAY/LOG_ONLY). |
| F-P2-1 | P2 | Product scenes (rest-day four steps, English buddy, habit growth) live on living-room-ready. Round 1 does not port them. |

**Fix:** document + alias map; policy `should_interrupt` for later cat-* ; no family.json edit.

**Tests:** alias 12岁姐姐 → registry child_12 or product qiaqia; unknown person → None; empty observation → None.

---

## 5. macOS / IoT 工程师

### Findings

| ID | Sev | Finding |
| --- | --- | --- |
| M-P1-1 | P1 | launchd plist exists on this parent (`config/com.tangtang.daemon.plist.example`). Round 1 does not change launchd/audio/TTS binaries. |
| M-P2-1 | P2 | Projection/TTS are presentation sinks. Orchestrator must emit actions, not call `cat-tts` / screen. |

**Tests:** **SKIP** launchd / real TTS / real projection / real microphone — not applicable this round. Unit tests must inject clock and use in-memory bus (no I/O).

---

## 6. 测试 / QA

### Findings

| ID | Sev | Finding |
| --- | --- | --- |
| Q-P0-1 | P0 | No `tests/v4/test_*.py`. Stub core is untested. Existing `tests/test-v3-family.sh` and `tests/test-v3.1-privacy.sh` must stay and still run. |
| Q-P1-1 | P1 | EventBus cannot inject clock; unit tests would be time-flaky if Event defaulted `now()`. |

**Fix:** add the seven files; tiny unittest runner (pytest not required). Cover happy / empty / illegal / unknown / privacy enum / handler exception / duplicate id.

**Tests:** see command section after fixes. This review commit: not run yet.

---

## 7. 安全工程师

### Findings

| ID | Sev | Finding |
| --- | --- | --- |
| S-P0-1 | P0 | Handler exceptions currently propagate (crash). After adding logs, logging `event.payload` would leak child speech — forbid in the bus error path. |
| S-P1-1 | P1 | Identity must not treat voiceprint as sufficient identity (spoof / school-hours bypass). |
| S-P2-1 | P2 | No Kafka/Redis/Postgres/K8s/vector DB — keep Python + JSON. Do not add those. |

**Fix:** isolate exceptions; error records carry `event_id` + `type` only; voiceprint-only observation → unknown.

---

## Compatibility check (living-room-ready, not merged)

Living-room `code/cat/cat-brain.py::should_speak` also consults habits + cat-turn gates. This parent’s `should_speak` is cooldown only. Round 1 adds `core.compat.should_interrupt` wrapping `InterruptPolicy` so cat-* **may later** call it without deleting cat-brain. A one-line comment is added on `should_speak`; behavior of cat-brain is unchanged.

---

## Fixes in this review commit

None (findings only). Following commits: `fix(v4): harden event boundary` and related boundary commits, then tests, then this document’s test transcript + P0==0 conclusion.

---

## Tests (pending)

```
PASS / FAIL / SKIP: not run in the review commit
Command: python3 -m unittest discover -s tests/v4 -t . -v
```

---

## Conclusion (review snapshot)

Round 1 **P0 == 8 (not 0)**. Stay on Round 1. **Do not enter Round 2.**

After boundary fixes, this document will be updated with actual test output and a P0==0 statement or a stay-and-fix statement.
