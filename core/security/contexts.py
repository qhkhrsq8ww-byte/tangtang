"""Explicit actor, audience and viewer contexts for family operations.

Identity, service target and read authority are separate facts.  In particular,
an AudienceContext never authenticates a speaker or grants memory access.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import FrozenSet, Literal

IdentityStatus = Literal["verified", "unverified", "system", "anonymous"]
ActorKind = Literal["member", "system", "anonymous"]
Visibility = Literal["PRIVATE", "FAMILY", "PUBLIC"]


@dataclass(frozen=True)
class ActorContext:
    """Who initiated an operation; system actors are never family members."""

    actor_id: str | None
    kind: ActorKind
    identity_status: IdentityStatus
    capabilities: FrozenSet[str] = field(default_factory=frozenset)

    def __post_init__(self) -> None:
        if self.kind == "member":
            if not self.actor_id or self.identity_status != "verified":
                raise ValueError("member actor requires a verified actor_id")
        elif self.kind == "system":
            if self.identity_status != "system":
                raise ValueError("system actor must use identity_status=system")
        elif self.kind == "anonymous":
            if self.actor_id is not None:
                raise ValueError("anonymous actor cannot carry actor_id")


@dataclass(frozen=True)
class AudienceContext:
    """Who receives a service; this is not proof of who spoke or who may read."""

    member_id: str | None
    purpose: str

    def __post_init__(self) -> None:
        if not self.purpose.strip():
            raise ValueError("audience purpose is required")


@dataclass(frozen=True)
class ViewerContext:
    """Who is requesting data, plus explicit read grants from a trusted issuer."""

    viewer_id: str | None
    identity_status: IdentityStatus
    grants: FrozenSet[str] = field(default_factory=frozenset)

    @property
    def authenticated(self) -> bool:
        return bool(self.viewer_id) and self.identity_status == "verified"


def authorize_actor_action(
    actor: ActorContext,
    capability: str,
    audience: AudienceContext | None = None,
) -> bool:
    """Authorize an operation without promoting its audience to its actor."""
    if actor.kind == "member":
        return actor.identity_status == "verified" and capability in actor.capabilities
    if actor.kind == "system":
        return capability in actor.capabilities
    return False


def authorize_viewer(
    viewer: ViewerContext | None,
    *,
    owner_member_id: str | None,
    visibility: Visibility,
) -> bool:
    """Fail closed: missing viewer context never grants access.

    PRIVATE is owner-only unless an explicit private:read:<owner> grant exists.
    FAMILY requires an explicit family:read grant. PUBLIC may be read without
    authentication, but a supplied viewer must not be treated as an owner.
    """
    if visibility == "PUBLIC":
        return True
    if viewer is None or not viewer.authenticated:
        return False
    if owner_member_id and viewer.viewer_id == owner_member_id:
        return True
    if visibility == "FAMILY":
        return "family:read" in viewer.grants
    if visibility == "PRIVATE" and owner_member_id:
        return f"private:read:{owner_member_id}" in viewer.grants
    return False
