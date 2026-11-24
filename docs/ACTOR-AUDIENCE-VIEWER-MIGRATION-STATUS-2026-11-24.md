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
| `cat-turn.py` | System actor and intended audience are recorded separately. Speaker identity is explicitly unverified; no member habit learning occurs from these rows. Member-specific `today-report` CLI reads are blocked unless the explicit migration switch is set. | Connect only a trusted Core-verified speaker identity and Viewer issuer when a real verification chain exists. |
| `cat-proactive-gate.py` | Cooldown writes require a system Actor capability and store Audience separately. | Move the system capability issuance behind a narrower Core-owned service boundary rather than constructing it in the CLI. |
| `cat-living.py` / runtime | Target is not sent through IdentityResolver, not used as `who/viewer`, and not used to load member-private context. Only registered member IDs are stored as audience; speaker environment labels are ignored. Listener remains unverified. | Add trusted listener detection only if supported by reliable evidence; otherwise retain unknown. |
| `cat-remind.sh` | Proactive target is named and passed as Audience; the same target is used by the gate, scene call, and cooldown record. A speaker environment label is not reused as an audience. | Keep actual listener unknown unless a trusted sensor/authentication path can prove otherwise. |
| `cat-task-dispatch.py` | Scheduler runs as system Actor only; even a verified member carrying a `tasks:dispatch` capability cannot dispatch. Core returns FAMILY tasks only; PRIVATE tasks are silently deferred internally without titles or shared-device notifications. Delivery callback receives Audience separately. | Implement a private delivery channel with a verified owner Viewer before PRIVATE reminders can be spoken. |
| `ContextBuilder` / `ChatAdapter` | Non-public memory reads and recent conversation history require a ViewerContext; speaker/member ID and legacy `viewer_id` strings do not authorize reads. Structured recall honors `family:read` for FAMILY records while PRIVATE records remain owner-only. | Wire a trusted ViewerContext issuer into the actual voice/device authentication path; define narrower, resource-scoped grants before enabling broad family access. |
| `cat-memory.py` | `today/recent/stable/state/emotion`, family `next`, and member-targeted `trends/next` fail closed without a Viewer-aware Core API. Separate legacy switches are migration-only and do not authenticate a caller. | Replace CLI compatibility switches with a trusted Viewer handoff, then remove both switches. |

## Preserved privacy invariants

1. PRIVATE task/reminder content is never sent to the shared-room speech adapter or surfaced through a generic shared-device notification; due PRIVATE reminders are silently deferred inside Core.
2. FAMILY reminders remain subject to existing family visibility and quiet-hours policy.
3. A system-generated prompt is not stored as evidence of a child's personal behavior.
4. A scheduled audience is not treated as a verified speaker.
5. A successful local TTS command is recorded as command success only; listener identity and actual hearing remain unverified.
6. Missing Viewer context denies non-public memory reads.

## Validation and rollout

- PR #99: Core Actor/Audience/Viewer contract; member actors now also require an explicit action capability. Its follow-up test update is in progress.
- PR #98: member and family memory CLI read restrictions; latest CI passed.
- PR #100 / #101: proactive and short-turn migrations, stacked on the Core contract.
- PR #102: aggregate integration candidate for the Core, proactive, short-turn, task-dispatch, ContextBuilder/ChatAdapter recall enforcement, family/member memory CLI restrictions, and short-turn report CLI restriction. Latest full Python 3.10/3.11 V4 workflow passes on commit `4cbc031a67e253c8393467f772c46d22e8875afe` (run #485).

No PR has been merged or deployed as part of this work. No Mac mini runtime or microphone validation has been performed.
