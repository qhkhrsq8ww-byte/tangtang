from __future__ import annotations

import pytest

from core.security.contexts import (
    ActorContext,
    AudienceContext,
    ViewerContext,
    authorize_actor_action,
    authorize_viewer,
)


def test_audience_is_not_actor_or_viewer():
    audience = AudienceContext(member_id="hanghang", purpose="reminder")
    system = ActorContext(None, "system", "system")
    assert audience.member_id == "hanghang"
    assert not authorize_actor_action(system, "reminder:deliver", audience)
    assert not authorize_viewer(
        ViewerContext(None, "anonymous"),
        owner_member_id="hanghang",
        visibility="PRIVATE",
    )


def test_system_actor_requires_capability():
    actor = ActorContext(
        None, "system", "system", frozenset({"reminder:deliver"})
    )
    assert authorize_actor_action(
        actor, "reminder:deliver",
        AudienceContext("hanghang", "reminder"),
    )
    assert not authorize_actor_action(actor, "memory:read")


def test_member_actor_must_be_verified():
    with pytest.raises(ValueError):
        ActorContext("hanghang", "member", "unverified")
    actor = ActorContext("parent", "member", "verified")
    assert authorize_actor_action(actor, "reminder:create")


def test_private_view_is_owner_only_or_explicit_grant():
    assert authorize_viewer(
        ViewerContext("hanghang", "verified"),
        owner_member_id="hanghang",
        visibility="PRIVATE",
    )
    assert not authorize_viewer(
        ViewerContext("parent", "verified"),
        owner_member_id="hanghang",
        visibility="PRIVATE",
    )
    assert authorize_viewer(
        ViewerContext("parent", "verified", frozenset({"private:read:hanghang"})),
        owner_member_id="hanghang",
        visibility="PRIVATE",
    )


def test_family_view_requires_explicit_grant():
    assert not authorize_viewer(
        ViewerContext("parent", "verified"),
        owner_member_id="hanghang",
        visibility="FAMILY",
    )
    assert authorize_viewer(
        ViewerContext("parent", "verified", frozenset({"family:read"})),
        owner_member_id="hanghang",
        visibility="FAMILY",
    )


def test_missing_viewer_fails_closed_for_non_public_data():
    assert not authorize_viewer(
        None, owner_member_id="parent", visibility="PRIVATE"
    )
    assert not authorize_viewer(
        None, owner_member_id=None, visibility="FAMILY"
    )
    assert authorize_viewer(
        None, owner_member_id=None, visibility="PUBLIC"
    )
