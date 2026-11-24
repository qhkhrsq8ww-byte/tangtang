# Actor / Audience / Viewer migration status

Updated: 2026-11-24

This is an implementation status record, not a claim that identity verification or listener detection is complete.

## Identity contract

- **Actor**: initiator of an operation. Member actors require verified identity and an explicit action capability; system actors require an explicit system capability.
- **Audience**: person for whom a service is intended. An audience ID never authenticates a speaker or grants read access.
- **Viewer**: principal requesting information. Non-public reads require a verified viewer and explicit grants.

The current context objects are an in-process Core contract. A trusted issuer / authentication handoff for Viewer grants is still required; callers must not construct verified identities from arbitrary CLI arguments or environment variables.

## Entry-point status

| Entry point | Current implementation | Remaining work |
|---|---|---|
| `cat-turn.py` | System actor and intended audience are recorded separately. Speaker identity is explicitly unverified; no member habit learning occurs from these rows. | Connect only a trusted Core-verified speaker identity when a real verification chain exists. |
| `cat-proactive-gate.py` | Cooldown writes require a system Actor capability and store Audience separately. | Move the system capability issuance behind a narrower Core-owned service boundary rather than constructing it in the CLI. |
| `cat-living.py` / runtime | Target is not sent through IdentityResolver, not used as `who/viewer`, and not used to load member-private context. Event payload stores audience; listener remains unverified. | Add trusted listener detection only if supported by reliable evidence; otherwise retain unknown. |
| `cat-remind.sh` | Proactive target is named and passed as Audience. Successful speech command is not proof of who heard it. | Keep actual listener unknown unless a trusted sensor/authentication path can prove otherwise. |
| `cat-task-dispatch.py` | Scheduler runs as system Actor, never loops through family member IDs as viewers. Core returns FAMILY tasks only; PRIVATE tasks are deferred internally without exposing titles to the adapter. Delivery callback receives Audience separately. | Implement a private delivery channel with a verified owner Viewer before PRIVATE reminders can be spoken. |
| `cat-memory.py` | Separate PR #98 blocks unscoped member and family reads by default; legacy bypass is explicitly named and documented as migration-only. | Wire a trusted Viewer issuer into Core memory APIs, then remove the migration bypass. |

## Preserved privacy invariants

1. PRIVATE task/reminder content is never sent to the shared-room speech adapter.
2. FAMILY reminders remain subject to existing family visibility and quiet-hours policy.
3. A system-generated prompt is not stored as evidence of a child's personal behavior.
4. A scheduled audience is not treated as a verified speaker.
5. A successful local TTS command is recorded as command success only; listener identity and actual hearing remain unverified.
6. Missing Viewer context denies non-public memory reads.

## Validation and rollout

- PR #99: Core Actor/Audience/Viewer contract; CI previously passed before the member-capability tightening, which is included in the integration PR.
- PR #98: member and family memory CLI read restrictions; latest CI passed.
- PR #100 / #101: proactive and short-turn migrations, stacked on the Core contract.
- PR #102: aggregate integration candidate for the complete Core, proactive, short-turn, and task-dispatch changes; full Python 3.10/3.11 V4 workflow is the merge gate.

No PR has been merged or deployed as part of this work. No Mac mini runtime or microphone validation has been performed.
