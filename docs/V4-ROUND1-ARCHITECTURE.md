# TangTang V4 Round 1 — Architecture Review

**Round:** 1 of 5 (architecture / boundary correctness only)  
**Do not enter Round 2.**  
**Parent:** `feat/v4-family-brain-core-20260828`  
**Branch:** `cursor/v4-round1-architecture-449b`  
**Not merged:** `cursor/living-room-ready-449b` (compatibility check only)

糖糖是比熊，口头禅「汪汪～」。不是监督机器人。

---

## Counts (end of Round 1)

| | Count | Notes |
| --- | --- | --- |
| **P0** | **0** | all Round 1 architecture P0 closed |
| **P1** | **3** | out of Round 1 fix scope; recorded below |
| **P2** | **3** | recorded |
| **tests/v4** | **77 PASS / 0 FAIL / 0 SKIP** | `python3 -m unittest discover -s tests/v4 -t . -v` |
| **test-v3-family.sh** | **20 PASS / 0 FAIL** | not deleted |
| **test-v3.1-privacy.sh** | 26 PASS; 2 env FAIL (TTS edge, launchd `plutil`) | **SKIP for this round** — Linux agent has no `edge_tts` / no `plutil`. Tests not weakened. |
| **launchd / real TTS / real projection / mic** | **SKIP** | not applicable in Round 1 |

**Round 1 P0 == 0.** Stay stopped. **Do not enter Round 2.**

---

## Parent choice

Inspected after `git fetch`:

| Ref | `core/` | living-room cat | family.json names |
| --- | --- | --- | --- |
| `main` | missing | old cat | schema example only |
| `cursor/living-room-ready-449b` (PR #16) | missing | **yes** (turn/habits/openclaw/school) | 洽洽 / 航航 |
| PR #15 V3 family brain | missing | no | 姐姐 / 弟弟 + 妈妈 |
| PR #17 V3.1 privacy | missing | no | 姐姐 / 弟弟 + 妈妈 |
| `feat/v4-family-brain-core-20260828` | **stub `core/` present** | V3 cat line | 姐姐 / 弟弟 + 妈妈 |

**Parent = `feat/v4-family-brain-core-20260828`** because it already has the most V4 `core/` without requiring a merge that would discard or overwrite living-room cat. Living-room is another stack; Round 1 does **not** merge it. A later PR from this parent (or a stacked PR) to `main` is still required.

`data/family.json` was **not** overwritten this round.

### Identity alias map (code only)

| Observation labels | Product id (living-room) | Registry id on this parent |
| --- | --- | --- |
| 12岁姐姐, 姐姐, 12岁女孩, girl, 洽洽, qiaqia, child_12 | **qiaqia** | `child_12` if present in injected members |
| 9岁弟弟, 弟弟, 9岁男孩, boy, 航航, hanghang, child_9 | **hanghang** | `child_9` if present |
| 妈妈, 妈, mom, mother | **mom** | `mom` if present |

Voiceprint is **not** the primary identity path. Primary: school-hours flag + presence + optional coarse features. Projection is a **presentation sink** label, never LLM-controlled.

---

## What existed vs what was added

**Existed (stub):** `core/events/event.py`, `event_bus.py`, `identity/resolver.py`, `memory/store.py`, `context/builder.py`, `policy/interrupt_policy.py`, `response/orchestrator.py`. Incomplete schema, no ports, no tests/v4, bus did not isolate exceptions, ContextBuilder took raw memory blobs.

**Added / hardened:** Protocol ports (`core/interfaces.py`), Event constructors + payload bound, in-memory EventBus with clock + duplicate id + handler isolation, observation IdentityResolver + aliases, viewer-scoped MemoryStore, ContextBuilder(MemoryPort, PolicyPort) with no file I/O, InterruptPolicy.should_interrupt (no LLM), PresentationAction, `core.compat.should_interrupt`, `tests/v4/test_*.py`.

**Not thrown away:** `code/cat/` (cat.sh, cat-brain cooldown `should_speak`, quiet hours, V3.1 privacy). cat-brain gained a comment + future import hint only.

---

## 1. 系统架构师

| ID | Sev | Finding | Fix | Tests |
| --- | --- | --- | --- | --- |
| A-P0-1 | P0→0 | Event used `event_id`/`timestamp`; empty id allowed; no payload bound | Canonical `id, type, ts, source, member_id?, privacy, payload`; reject blank id, bad enum, >8192B payload | `test_event.py` happy/empty/illegal/unknown |
| A-P0-2 | P0→0 | Handler exception crashed process; no clock; no duplicate id | In-memory bus, inject clock, catch+continue, skip duplicate `event_id`, never log payload | `test_event_bus.py` |
| A-P0-3 | P0→0 | No Protocol/ABC | `EventBusPort, IdentityPort, MemoryPort, ContextPort, PolicyPort, ResponsePort` | isinstance checks in each suite |
| A-P0-4 | P0→0 | ContextBuilder accepted raw `memories=` | Constructor requires MemoryPort + PolicyPort; no `open(` / sqlite | `test_context.py` |
| A-P1-1 | P1→0 | No `should_interrupt` for cat-* | `core.compat.should_interrupt`; comment on `cat-brain.should_speak` (not deleted) | `test_policy.py` compat |

**Cycles:** MemoryStore source has no `from core.context`. Context depends only on ports in `interfaces.py`. Event does not import Identity.

**Forbidden:** Memory → Context → Memory — absent. LLM → files/DB/shell/TTS/projection — absent in core.

---

## 2. 隐私与儿童安全审查员

| ID | Sev | Finding | Fix | Tests |
| --- | --- | --- | --- | --- |
| P-P0-1 | P0→0 | `query(member_id=child_9, scope=PRIVATE)` with no viewer leaked | `viewer_id` required for PRIVATE; mismatch → `[]` | `test_memory.py` cross-child denied |
| P-P0-2 | P0→0 | Caller could stuff PRIVATE into ContextBuilder | Builder queries MemoryPort with `viewer_id=who.member_id`; FAMILY/PUBLIC drop PRIVATE | `test_context.py` + privacy matrix |
| P-P1-1 | P1→0 | Unbounded PRIVATE payload | Event payload max 8192 bytes | `test_event.py` huge payload |
| P-P2-1 | P2 | Disk/log/cat-vp data-flow | **Round 2.** Bus error path logs `event_id`+`type` only | handler exception test |

PRIVATE / FAMILY / PUBLIC are the only privacy enums. PRIVATE events require `member_id`.

---

## 3. AI / 对话架构师

| ID | Sev | Finding | Fix | Tests |
| --- | --- | --- | --- | --- |
| I-P0-1 | P0→0 | Orchestrator returned a loose dict; sinks unenforced | `PresentationAction`; responder must return `str`; SPEAK sink is the label `voice` (not a call) | `test_response.py` |
| I-P1-1 | P1→0 | Identity was `resolve(str)` voice lookup | `resolve(observation)`; Event does not embed resolver | `test_identity.py` |
| I-P1-2 | P1→0 | Policy had no school-hours input | Observation flags only; no calendar file open | `test_policy.py` |

LLM must not decide privacy, permissions, quiet hours, shell, TTS, or projection. InterruptPolicy and EventBus are deterministic code.

---

## 4. 家庭产品经理

| ID | Sev | Finding | Fix | Tests |
| --- | --- | --- | --- | --- |
| F-P1-1 | P1 (open) | Parent family.json is 姐姐/弟弟, living-room is 洽洽/航航 | **Did not overwrite family.json.** Alias table in IdentityResolver. 糖糖 remains 比熊 汪汪～, not a supervisor (quiet/school → SILENT) | alias tests; policy quiet/school |
| F-P2-1 | P2 (open) | Rest-day / English / habits live on living-room-ready | Compatibility check only; no merge | SKIP product merge |

Remaining **P1:** living-room cat stack is not on this branch. Later merge to main / living-room is a separate PR.

---

## 5. macOS / IoT 工程师

| ID | Sev | Finding | Fix | Tests |
| --- | --- | --- | --- | --- |
| M-P1-1 | P1 (open) | launchd plist exists; this Linux agent has no `plutil` | Unchanged this round | **SKIP** launchd |
| M-P2-1 | P2 (open) | TTS/projection are device sinks | Orchestrator emits labels only | **SKIP** real TTS/projection/mic; unit source scan PASS |

Existing `tests/test-v3.1-privacy.sh` TTS edge FAIL = `No module named 'edge_tts'`. launchd FAIL = `plutil` missing. Pre-existing environment; Round 1 did not touch those files.

---

## 6. 测试 / QA

| ID | Sev | Finding | Fix | Tests |
| --- | --- | --- | --- | --- |
| Q-P0-1 | P0→0 | No `tests/v4/` | Seven files + `tests/v4/run.py` (unittest, no pytest) | 77 PASS |
| Q-P1-1 | P1→0 | Bus not clock-injectable | `EventBus(clock=...)` | `test_event_bus.py` |

Coverage required: happy, empty, illegal, unknown, PRIVATE/FAMILY/PUBLIC, handler exception, duplicate `event_id` — all present.

---

## 7. 安全工程师

| ID | Sev | Finding | Fix | Tests |
| --- | --- | --- | --- | --- |
| S-P0-1 | P0→0 | Handler exceptions propagated; logging payload would leak speech | Catch `Exception`, continue; error text is `event_id` + `type` only | `test_event_bus.py` secret-child-words not in sink |
| S-P1-1 | P1 (open) | `code/cat/cat-vp.py` still exists on V3 runtime | Core IdentityResolver treats voiceprint-only as unknown. Wiring cat-vp off the primary path is Round 2+ | `test_identity.py` voiceprint-only → None |
| S-P2-1 | P2 | No Kafka/Redis/Postgres/K8s/vector DB | Python + in-memory JSON-shaped records only | n/a |

---

## Remaining after Round 1 (not P0)

**P1 (3)**

1. Living-room cat (turn/habits/openclaw/school hours, names 洽洽/航航) not merged — later PR.
2. V3 `cat-vp` / `cat-chat` speaker path still exists beside core; core is correct, runtime wiring is later.
3. Deep privacy data-flow (disk, habits logs, path migration) is **Round 2** by plan.

**P2 (3)**

1. Product scenes (rest-day four steps, English buddy) stay on living-room-ready.
2. Presentation layer that actually plays TTS / projection is not this round.
3. launchd install on a real Mac is Round 4 reliability.

---

## Compat shim

```python
from core.compat import should_interrupt
if should_interrupt(observation):
    # skip proactive speech
    ...
```

`code/cat/cat-brain.py::should_speak` is unchanged cooldown logic. It is **not** deleted. A comment points at the shim for later.

---

## Tests — actual output

Command:

```bash
python3 -m unittest discover -s tests/v4 -t . -v
```

Equivalent: `python3 tests/v4/run.py`

```
test_empty_who_and_event (tests.v4.test_context.TestContextEmptyUnknown.test_empty_who_and_event) ... ok
test_unknown_member_no_rows (tests.v4.test_context.TestContextEmptyUnknown.test_unknown_member_no_rows) ... ok
test_family_scope_drops_private (tests.v4.test_context.TestContextHappy.test_family_scope_drops_private) ... ok
test_private_scope_loads_via_port (tests.v4.test_context.TestContextHappy.test_private_scope_loads_via_port) ... ok
test_public_scope (tests.v4.test_context.TestContextHappy.test_public_scope) ... ok
test_recent_bound (tests.v4.test_context.TestContextHappy.test_recent_bound) ... ok
test_constructor_requires_ports (tests.v4.test_context.TestContextNoDirectIO.test_constructor_requires_ports) ... ok
test_source_has_no_open_or_db (tests.v4.test_context.TestContextNoDirectIO.test_source_has_no_open_or_db) ... ok
test_empty_member_id_public_ok (tests.v4.test_event.TestEventEmpty.test_empty_member_id_public_ok) ... ok
test_empty_payload_ok (tests.v4.test_event.TestEventEmpty.test_empty_payload_ok) ... ok
test_create_public_minimal (tests.v4.test_event.TestEventHappy.test_create_public_minimal) ... ok
test_from_dict_canonical_fields (tests.v4.test_event.TestEventHappy.test_from_dict_canonical_fields) ... ok
test_privacy_enum_all_three (tests.v4.test_event.TestEventHappy.test_privacy_enum_all_three) ... ok
test_bad_privacy_enum (tests.v4.test_event.TestEventIllegal.test_bad_privacy_enum) ... ok
test_blank_id (tests.v4.test_event.TestEventIllegal.test_blank_id) ... ok
test_huge_payload (tests.v4.test_event.TestEventIllegal.test_huge_payload) ... ok
test_missing_id_from_dict (tests.v4.test_event.TestEventIllegal.test_missing_id_from_dict) ... ok
test_missing_type (tests.v4.test_event.TestEventIllegal.test_missing_type) ... ok
test_non_mapping_payload (tests.v4.test_event.TestEventIllegal.test_non_mapping_payload) ... ok
test_non_serializable_payload (tests.v4.test_event.TestEventIllegal.test_non_serializable_payload) ... ok
test_payload_not_mutated_after_create (tests.v4.test_event.TestEventIllegal.test_payload_not_mutated_after_create) ... ok
test_private_without_member (tests.v4.test_event.TestEventIllegal.test_private_without_member) ... ok
test_event_module_does_not_import_identity (tests.v4.test_event.TestEventNoResolverEmbed.test_event_module_does_not_import_identity) ... ok
test_unknown_type_is_allowed_as_data (tests.v4.test_event.TestEventUnknown.test_unknown_type_is_allowed_as_data) ... ok
test_bus_source_has_no_file_io (tests.v4.test_event_bus.TestEventBusClockNoIO.test_bus_source_has_no_file_io) ... ok
test_injected_clock (tests.v4.test_event_bus.TestEventBusClockNoIO.test_injected_clock) ... ok
test_empty_subscribe_type_illegal (tests.v4.test_event_bus.TestEventBusEmpty.test_empty_subscribe_type_illegal) ... ok
test_unknown_type_no_handlers (tests.v4.test_event_bus.TestEventBusEmpty.test_unknown_type_no_handlers) ... ok
test_handler_exception_does_not_crash_and_continues (tests.v4.test_event_bus.TestEventBusHandlerException.test_handler_exception_does_not_crash_and_continues) ... ok
test_process_survives (tests.v4.test_event_bus.TestEventBusHandlerException.test_process_survives) ... ok
test_subscribe_and_publish (tests.v4.test_event_bus.TestEventBusHappy.test_subscribe_and_publish) ... ok
test_wildcard_and_typed (tests.v4.test_event_bus.TestEventBusHappy.test_wildcard_and_typed) ... ok
test_duplicate_event_id_not_redelivered (tests.v4.test_event_bus.TestEventBusIllegalAndDuplicate.test_duplicate_event_id_not_redelivered) ... ok
test_non_event_rejected (tests.v4.test_event_bus.TestEventBusIllegalAndDuplicate.test_non_event_rejected) ... ok
test_resolver_source_has_no_event_import (tests.v4.test_identity.TestIdentityDecoupledFromEvent.test_resolver_source_has_no_event_import) ... ok
test_empty_none (tests.v4.test_identity.TestIdentityEmptyUnknown.test_empty_none) ... ok
test_unknown (tests.v4.test_identity.TestIdentityEmptyUnknown.test_unknown) ... ok
test_brother_alias (tests.v4.test_identity.TestIdentityHappy.test_brother_alias) ... ok
test_mom_present (tests.v4.test_identity.TestIdentityHappy.test_mom_present) ... ok
test_presence_beats_label (tests.v4.test_identity.TestIdentityHappy.test_presence_beats_label) ... ok
test_registry_id (tests.v4.test_identity.TestIdentityHappy.test_registry_id) ... ok
test_sister_alias_maps_to_registry_not_overwrite (tests.v4.test_identity.TestIdentityHappy.test_sister_alias_maps_to_registry_not_overwrite) ... ok
test_empty_members_uses_product_ids (tests.v4.test_identity.TestIdentityProductWithoutRegistry.test_empty_members_uses_product_ids) ... ok
test_school_hours_child_home_ok (tests.v4.test_identity.TestIdentityVoiceprintNotPrimary.test_school_hours_child_home_ok) ... ok
test_school_hours_child_not_home (tests.v4.test_identity.TestIdentityVoiceprintNotPrimary.test_school_hours_child_not_home) ... ok
test_voiceprint_only_unknown (tests.v4.test_identity.TestIdentityVoiceprintNotPrimary.test_voiceprint_only_unknown) ... ok
test_empty_member_id (tests.v4.test_memory.TestMemoryEmptyUnknown.test_empty_member_id) ... ok
test_empty_store (tests.v4.test_memory.TestMemoryEmptyUnknown.test_empty_store) ... ok
test_unknown_member (tests.v4.test_memory.TestMemoryEmptyUnknown.test_unknown_member) ... ok
test_family_excludes_private (tests.v4.test_memory.TestMemoryHappy.test_family_excludes_private) ... ok
test_private_self (tests.v4.test_memory.TestMemoryHappy.test_private_self) ... ok
test_public_only (tests.v4.test_memory.TestMemoryHappy.test_public_only) ... ok
test_bad_privacy_on_put (tests.v4.test_memory.TestMemoryIllegalAndLeak.test_bad_privacy_on_put) ... ok
test_bad_scope_on_query (tests.v4.test_memory.TestMemoryIllegalAndLeak.test_bad_scope_on_query) ... ok
test_cross_child_private_denied (tests.v4.test_memory.TestMemoryIllegalAndLeak.test_cross_child_private_denied) ... ok
test_missing_ids_illegal (tests.v4.test_memory.TestMemoryIllegalAndLeak.test_missing_ids_illegal) ... ok
test_source_independent (tests.v4.test_memory.TestMemoryNoContextImport.test_source_independent) ... ok
test_empty_observation_daytime (tests.v4.test_policy.TestPolicyEmptyUnknown.test_empty_observation_daytime) ... ok
test_unknown_flags_ignored (tests.v4.test_policy.TestPolicyEmptyUnknown.test_unknown_flags_ignored) ... ok
test_daytime_speak (tests.v4.test_policy.TestPolicyHappy.test_daytime_speak) ... ok
test_emergency_overrides_quiet (tests.v4.test_policy.TestPolicyHappy.test_emergency_overrides_quiet) ... ok
test_compat_should_interrupt (tests.v4.test_policy.TestPolicyNoLLMAndCompat.test_compat_should_interrupt) ... ok
test_source_has_no_llm (tests.v4.test_policy.TestPolicyNoLLMAndCompat.test_source_has_no_llm) ... ok
test_active_conversation_silent (tests.v4.test_policy.TestPolicyQuietAndSchool.test_active_conversation_silent) ... ok
test_interactive_bypasses_quiet (tests.v4.test_policy.TestPolicyQuietAndSchool.test_interactive_bypasses_quiet) ... ok
test_low_importance_log_only (tests.v4.test_policy.TestPolicyQuietAndSchool.test_low_importance_log_only) ... ok
test_quiet_hours_silent (tests.v4.test_policy.TestPolicyQuietAndSchool.test_quiet_hours_silent) ... ok
test_recently_interrupted_delay (tests.v4.test_policy.TestPolicyQuietAndSchool.test_recently_interrupted_delay) ... ok
test_school_hours_child_not_home (tests.v4.test_policy.TestPolicyQuietAndSchool.test_school_hours_child_not_home) ... ok
test_delay_and_log_only (tests.v4.test_response.TestResponseEmptyUnknownIllegal.test_delay_and_log_only) ... ok
test_empty_context (tests.v4.test_response.TestResponseEmptyUnknownIllegal.test_empty_context) ... ok
test_non_speak_cannot_carry_text_on_action (tests.v4.test_response.TestResponseEmptyUnknownIllegal.test_non_speak_cannot_carry_text_on_action) ... ok
test_responder_must_return_str (tests.v4.test_response.TestResponseEmptyUnknownIllegal.test_responder_must_return_str) ... ok
test_unknown_decision_illegal (tests.v4.test_response.TestResponseEmptyUnknownIllegal.test_unknown_decision_illegal) ... ok
test_silent_empty_text (tests.v4.test_response.TestResponseHappy.test_silent_empty_text) ... ok
test_speak_emits_voice_sink_label_not_call (tests.v4.test_response.TestResponseHappy.test_speak_emits_voice_sink_label_not_call) ... ok
test_source_does_not_call_tts_or_projection (tests.v4.test_response.TestResponseNoSinks.test_source_does_not_call_tts_or_projection) ... ok

----------------------------------------------------------------------
Ran 77 tests in 0.003s

OK
```

Regression (not deleted): `bash tests/test-v3-family.sh` → `RESULT PASS=20 FAIL=0`.

---

## Conclusion

Round 1 architecture boundaries are in place: Event cannot be illegally constructed, EventBus is testable and fault-isolated, Identity is decoupled, Memory does not import Context, ContextBuilder does not open files, InterruptPolicy has no LLM, ResponseOrchestrator does not call TTS/projection.

**Round 1 P0 == 0.**

**Do not enter Round 2.** Deep privacy data-flow, living-room merge, and Mac launchd/TTS remain later rounds.

A later PR to `main` is required because this branch is stacked on `feat/v4-family-brain-core-20260828`, not on `main`.
