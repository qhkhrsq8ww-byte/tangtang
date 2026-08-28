# TangTang V4 Round 4 — Reliability

**Round:** 4 of 5 (failure isolation / payload robustness / home paths / launchd)  
**Parent:** Round 3 on `cursor/v4-five-rounds-449b` (P0=0, 139 tests)  
**Branch:** `cursor/v4-five-rounds-449b`  
**Not merged:** `cursor/living-room-ready-449b`

糖糖是比熊，口头禅「汪汪～」。不是监督机器人。  
`data/family.json` 未改写。无 Kafka。LLM 不能打 DB / 文件 / shell / TTS / 投影。

---

## Counts (end of Round 4)

| | Count | Notes |
| --- | --- | --- |
| **P0** | **0** | TTS-drop-event, crash-on-junk, hardcoded cat home closed |
| **P1** | **2** | living-room stack not merged; V3 cat-chat still separate |
| **P2** | **3** | real Mac launchd install untested here; device TTS; cooldown product |
| **tests/v4** | **161 PASS / 0 FAIL / 0 SKIP** | `python3 -m unittest discover -s tests/v4 -t . -v` |
| **launchd / real TTS / mic** | **SKIP** | Linux agent; templates + unit tests only — tests not weakened |

**Round 4 P0 == 0.** Enter Round 5 on the same linear branch.

---

## Failure isolation

| Fault | Behaviour |
| --- | --- |
| network | `PresentationRuntime` isolates; Event kept |
| TTS | `tts_ok=False`, **event_kept=True** |
| STT | `stt_ok=False`, Event kept |
| projection | `projection_ok=False`, Event kept |
| LLM / responder | fallback `汪汪～` (ActionError still raised for non-str) |
| handler | EventBus continues other handlers |
| memory put | ingest still returns Event; stored_* false |
| context query | empty memory list, SILENT if policy blows |
| process restart | `FileSeenStore` under `$TANGTANG_HOME/runtime/` dedupes event ids |

`core.runtime.isolate.isolate()` never raises and never logs arguments (speech).

---

## Payload robustness (`EventBus.accept`)

| Input | Crash? | Result |
| --- | --- | --- |
| duplicate id | no | `duplicate=True` |
| out-of-order ts | no | processed, `out_of_order=True` |
| future ts (>5 min) | no | processed, `future_ts=True` |
| bad ts | no | processed / flagged |
| huge payload | no | `accepted=False` |
| empty payload | no | ok |
| empty / non-event | no | `accepted=False` |

`publish()` still type-checks (Round 1). Intake path is `accept()`.

---

## TANGTANG_HOME / launchd / crontab

Runtime code (`core/`, `code/cat/*.{py,sh,js}`, `config/*.sh`, plist example, crontab example) **must not** contain `/Users/lv/.qclaw/workspace/cat/`.

| File | Rule |
| --- | --- |
| persist | `TANGTANG_HOME` / `TANGTANG_DATA_DIR` required |
| `config/com.tangtang.daemon.plist.example` | `__TANGTANG_HOME__` placeholders; user LaunchAgent |
| `config/crontab.example` | `$TANGTANG_HOME/...` ; current-user crontab |
| `config/migrate-paths.sh` | `TANGTANG_HOME` + `OLD_TANGTANG_HOME` env; no sudo root install |

**Not root-installed:** copy plist to `~/Library/LaunchAgents/` and `launchctl load` as the login user. Never `/Library/LaunchDaemons`, never `sudo launchctl`. Crontab is `crontab` as the user, not root.

Historical `config/backups/crontab-20260828.bak` keeps the old path as a backup snapshot only.

---

## 1. 系统架构师

| ID | Sev | Finding | Fix | Tests |
| --- | --- | --- | --- | --- |
| A-P0-1 | P0→0 | Presentation / TTS exception could unwind past Event | DeliveryResult.event_kept | `test_failure_isolation.py` |
| A-P0-2 | P0→0 | `publish` raised on junk dict | `accept()` never raises | `test_payload_robustness.py` |
| A-P1-1 | P1 (open) | living-room cat process model not on this branch | no merge | recorded |

---

## 2. 隐私与儿童安全审查员

| ID | Sev | Finding | Fix | Tests |
| --- | --- | --- | --- | --- |
| P-P2-1 | P2 | isolate() must not log utterance | isolate logs nothing | source of isolate.py |
| P-P0-1 | P0→0 | memory fail must not skip Event (and must not dump speech to logs) | ingest keeps Event | isolation tests |

Round 2 privacy suites remain green.

---

## 3. AI / 对话架构师

| ID | Sev | Finding | Fix | Tests |
| --- | --- | --- | --- | --- |
| I-P0-1 | P0→0 | LLM ConnectionError crashed SPEAK | fallback 汪汪～ | `test_llm_fail_falls_back_to_wangwang` |
| I-P1-1 | P1 (open) | V3 cat-chat urllib still unbounded | later | recorded |

---

## 4. 家庭产品经理

| ID | Sev | Finding | Fix | Tests |
| --- | --- | --- | --- | --- |
| F-P2-1 | P2 | TTS fail is silent (no extra nag) | event kept, tts_ok false | isolation |
| F-P1-1 | P1 (open) | living-room product scenes | no merge | SKIP |

糖糖 still 比熊 汪汪～.

---

## 5. macOS / IoT 工程师

| ID | Sev | Finding | Fix | Tests |
| --- | --- | --- | --- | --- |
| M-P0-1 | P0→0 | Hardcoded old cat home in migrate script | env `TANGTANG_HOME` | `test_tangtang_home.py` |
| M-P0-2 | P0→0 | launchd/crontab could be read as root install | documented user-only | plist + crontab + migrate tests |
| M-P2-1 | P2 | This Linux agent cannot `launchctl` / `plutil` | SKIP real device | **SKIP** not FAIL→SKIP of existing tests |

---

## 6. 测试 / QA

| ID | Sev | Finding | Fix | Tests |
| --- | --- | --- | --- | --- |
| Q-P0-1 | P0→0 | No isolation / junk-payload / home tests | three new files | 161 PASS |
| Q-P1-1 | P1→0 | Did not weaken Round 1 bus source scan | persist in `checkpoint.py` | `test_event_bus.py` still forbids `open(` / `Path(` in bus module |

---

## 7. 安全工程师

| ID | Sev | Finding | Fix | Tests |
| --- | --- | --- | --- | --- |
| S-P0-1 | P0→0 | Path jail still TANGTANG_HOME | unchanged + scan | home tests |
| S-P2-1 | P2 | backups/ still has old crontab snapshot | not runtime | excluded from scan |

---

## Remaining after Round 4 (not P0)

**P1 (2)** living-room cat stack; V3 cat-chat path.

**P2 (3)** real Mac launchd; real TTS/projection; extra copy variants.

---

## Tests

```bash
python3 -m unittest discover -s tests/v4 -t . -v
```

```
Ran 161 tests in 0.013s
OK
```

161 PASS / 0 FAIL / 0 SKIP.

---

## Conclusion

Round 4: a dead TTS/STT/projection/network/LLM/handler/memory/context cannot drop the Event or crash the process. Junk timestamps and payloads are absorbed by `accept()`. Runtime paths go through `TANGTANG_HOME`. launchd/crontab are user-level templates.

**Round 4 P0 == 0.**
