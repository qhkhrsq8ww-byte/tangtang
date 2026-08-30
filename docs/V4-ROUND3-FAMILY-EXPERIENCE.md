# TangTang V4 Round 3 — Family Behaviour & Product

**Round:** 3 of 5 (family experience / interruption / copy)  
**Parent:** `cursor/v4-round2-privacy-449b` (Round 2 P0=0, 114 tests)  
**Branch:** `cursor/v4-five-rounds-449b`  
**Not merged:** `cursor/living-room-ready-449b`

糖糖是比熊，口头禅「汪汪～」。不是监督机器人。  
`data/family.json` 未改写；别名仍是 姐姐→qiaqia、弟弟→hanghang。

---

## Counts (end of Round 3)

| | Count | Notes |
| --- | --- | --- |
| **P0** | **0** | persona mismatch, nag-on-every-event, surveillance copy closed |
| **P1** | **3** | living-room cat stack, V3 cat-chat path, real TTS device |
| **P2** | **4** | rest-day / English still on living-room; cooldown 15min product; more copy variants |
| **tests/v4** | **139 PASS / 0 FAIL / 0 SKIP** | `python3 -m unittest discover -s tests/v4 -t . -v` |
| **Round 2 suites** | still green | no tests deleted or weakened |
| **launchd / real TTS / mic** | **SKIP** | Linux agent; Round 4 |

**Round 3 P0 == 0.** Enter Round 4 (reliability) on the same linear branch.

---

## Six utterances → persona

| Member | Utterance | Role | Must not |
| --- | --- | --- | --- |
| 爷爷 grandpa | 糖糖，帮我看看明天天气。 | elder | 宝宝 / 吃饭饭 / 觉觉 |
| 奶奶 grandma | 糖糖陪奶奶说说话。 | elder | same toddler tokens |
| 爸爸 dad | 糖糖，我加班回来了。 | adult | childish |
| 妈妈 mom | 孩子们作业写完了吗？ | adult | childish |
| 姐姐 child_12 / qiaqia | 好无聊，不想写作业。 | friend (12) | toddler talk |
| 弟弟 child_9 / hanghang | 我想打游戏！ | play (9) | adult lecture (作为家长 / 立刻停止) |

All six replies start with `汪汪～`. Implementation: `core/persona/profiles.py` + `CopyGuard` last-line filter so a leaky LLM cannot ship forbidden tone.

---

## Proactive scenes (not speak-on-every-event)

| Scene | First | Repeat (15 min cooldown) |
| --- | --- | --- |
| phone | SPEAK | LOG_ONLY |
| sitting | SPEAK | LOG_ONLY |
| no_meal | SPEAK | DELAY |
| late_sleep | SPEAK | SILENT |
| home | SPEAK | LOG_ONLY |
| away | SILENT | SILENT |

Empty room (`presence_home is False` and not interactive) infers `away` → SILENT. Interactive (user talking to 糖糖) still SPEAK. Emergency / quiet hours / school-hours rules from Round 1 kept.

---

## Forbidden surveillance copy

**Forbidden:** `我知道你刚才玩了 43 分钟手机。`  
**Required:** `汪汪～ 要不要起来走一走？`

`CopyGuard` rewrites any minutes-on-phone / 监控到你 pattern. Orchestrator always runs the guard on SPEAK text, even when the responder is an LLM.

---

## 1. 系统架构师

| ID | Sev | Finding | Fix | Tests |
| --- | --- | --- | --- | --- |
| A-P0-1 | P0→0 | InterruptPolicy treated every observation as SPEAK unless quiet/school | Scene + per-(member,scene) cooldown | `test_interrupt_scenes.py` |
| A-P1-1 | P1 (open) | living-room cat-brain cooldown is a separate stack | Not merged | recorded |
| A-P2-1 | P2 | PersonaRenderer is deterministic, not an LLM | Intended | persona tests |

LLM still does not implement InterruptPolicy or CopyGuard.

---

## 2. 隐私与儿童安全审查员

| ID | Sev | Finding | Fix | Tests |
| --- | --- | --- | --- | --- |
| P-P0-1 | P0→0 | Phone-minute copy is a surveillance leak of behaviour | Forbidden regex → walk suggestion | `test_forbidden_copy.py` |
| P-P2-1 | P2 | Child PRIVATE still Round 2 path | Unchanged; persona does not read PrivateMemory of others | Round 2 suites still green |

---

## 3. AI / 对话架构师

| ID | Sev | Finding | Fix | Tests |
| --- | --- | --- | --- | --- |
| I-P0-1 | P0→0 | Responder could emit toddler/lecture/surveillance | CopyGuard after responder; optional PersonaRenderer | forbidden + persona tests |
| I-P1-1 | P1 (open) | V3 `cat-chat.py` not on this path | Later wiring | recorded |

---

## 4. 家庭产品经理

| ID | Sev | Finding | Fix | Tests |
| --- | --- | --- | --- | --- |
| F-P0-1 | P0→0 | Adults / 姐姐 / 弟弟 used one child voice | Six-role PERSONAS | `test_persona.py` |
| F-P0-2 | P0→0 | Phone/sitting ticks would nag every minute | Cooldown + LOG_ONLY/SILENT/DELAY | `test_interrupt_scenes.py` |
| F-P1-1 | P1 (open) | Rest-day four steps / English buddy on living-room | No merge | SKIP product merge |
| F-P2-1 | P2 | 15 minute cooldown is a product constant | Documented | cooldown-expires test |

糖糖仍是玩伴。不说「我知道你刚才…分钟」。

---

## 5. macOS / IoT 工程师

| ID | Sev | Finding | Fix | Tests |
| --- | --- | --- | --- | --- |
| M-P2-1 | P2 (open) | Real TTS / projection / launchd | Round 4 | **SKIP** device |

Orchestrator still emits sink labels only.

---

## 6. 测试 / QA

| ID | Sev | Finding | Fix | Tests |
| --- | --- | --- | --- | --- |
| Q-P0-1 | P0→0 | No persona / scene / forbidden-copy tests | Three new files | 139 PASS |
| Q-P1-1 | P1→0 | Could have SKIP'd | Did not | 0 SKIP |

New: `test_persona.py`, `test_interrupt_scenes.py`, `test_forbidden_copy.py`. Round 1+2 files untouched.

---

## 7. 安全工程师

| ID | Sev | Finding | Fix | Tests |
| --- | --- | --- | --- | --- |
| S-P0-1 | P0→0 | Minutes-on-phone is PII-ish behaviour telemetry in speech | CopyGuard | forbidden tests |
| S-P2-1 | P2 | No new secrets | n/a | Round 2 scan still holds |

---

## Remaining after Round 3 (not P0)

**P1 (3)**

1. Living-room cat (turn/habits/openclaw) not merged.
2. V3 `cat-chat.py` not on PrivacyPipeline + persona.
3. Real Mac TTS / launchd — Round 4.

**P2 (4)**

1. Rest-day / English buddy stay on living-room-ready.
2. Cooldown 15 minutes may need per-scene product tuning.
3. More copy variants than the six canonical lines.
4. Presentation layer still labels only.

---

## Tests

```bash
python3 -m unittest discover -s tests/v4 -t . -v
```

```
Ran 139 tests in 0.009s
OK
```

139 PASS / 0 FAIL / 0 SKIP.

---

## Conclusion

Round 3: six members get the right 糖糖 (adults not childish, 姐姐 not toddler, 弟弟 not lectured). Proactive phone/sitting/meal/sleep/home/away use SPEAK|SILENT|DELAY|LOG_ONLY with cooldown. Surveillance copy is rewritten to 「要不要起来走一走？」.

**Round 3 P0 == 0.**
