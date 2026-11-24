# Actor / Audience / Viewer authorization contract

Status: initial Core contract, 2026-11-24. This is a staged migration, not a claim
that every legacy entry point is already protected.

## Non-negotiable distinctions

- **Actor**: initiator of an operation (verified family member, system service, or anonymous).
- **Audience**: person the assistant is serving. Naming a child as audience does not
  authenticate that child and does not grant access to the child's records.
- **Viewer**: principal requesting information. Read access must be checked against
  the data owner's identity and visibility.

No adapter may infer Actor or Viewer from Audience, a target-member CLI argument,
a display label, Wi-Fi presence, or an unverified voice candidate.

## Core API

`core.security.contexts` defines immutable `ActorContext`, `AudienceContext`,
and `ViewerContext`, plus fail-closed `authorize_actor_action` and
`authorize_viewer` helpers.

- Member actors must be verified.
- System actors require the named capability for each operation.
- Anonymous actors cannot initiate privileged operations.
- PRIVATE reads are owner-only unless a narrowly scoped
  `private:read:<owner_member_id>` grant is present.
- FAMILY reads require an explicit `family:read` grant.
- Missing Viewer context denies non-public reads.
- Audience carries purpose and target only; it has no authentication or grants.

The initial Core contract deliberately does not invent family roles or grant parents
automatic access to every child's private memory. Grant issuance remains a separate
trusted setup/consent workflow.

## Entry-point migration and acceptance criteria

| Entry point | Required separation | Acceptance |
|---|---|---|
| `cat-turn.py` | System writes a turn for an Audience; child is not the Actor | CLI cannot attribute system-generated turn as child speech; ledger records actor kind and audience separately |
| `cat-remind.sh` | Scheduler Actor, reminder Audience, actual listener | Target member is never treated as verified speaker/viewer; public output follows visibility policy |
| `cat-proactive-gate.py` | System Actor plus Audience | Arbitrary member argument cannot forge member-originated activity or member-owned authorization state |
| `cat-memory.py` | Explicit Viewer for all reads | Non-public family/member reads fail closed without verified Viewer and grants |
| Core runtime | Contexts flow end-to-end | Actor, Audience and Viewer are distinct typed fields; no fallback from one to another |

## Existing safeguards to preserve

- PRIVATE tasks/reminders must not be broadcast to a public room.
- FAMILY reminders may use the family channel only after existing policy checks.
- Unknown or unverified voice identity remains unknown.
- Legacy bypasses stay disabled unless an explicit, time-bounded migration is approved.

## Rollout order

1. Land and test the Core context contract.
2. Migrate short-turn ledger and proactive gate to system-actor / audience semantics.
3. Migrate reminder scheduling and delivery to distinguish scheduler from listener.
4. Require Viewer authorization for family and member memory CLI reads.
5. Thread contexts through runtime and adapters; remove compatibility paths only after
   all callers and tests have migrated.

Do not treat this document or the Core dataclasses alone as proof that legacy shell
entry points are secured. Each migration needs its own tests and review.
