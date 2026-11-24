from __future__ import annotations

import unittest

from core.security.contexts import (
    ActorContext,
    AudienceContext,
    ViewerContext,
    authorize_actor_action,
    authorize_viewer,
)


class TestActorAudienceViewerContexts(unittest.TestCase):
    def test_audience_is_not_actor_or_viewer(self):
        audience = AudienceContext(member_id="hanghang", purpose="reminder")
        system = ActorContext(None, "system", "system")
        self.assertEqual(audience.member_id, "hanghang")
        self.assertFalse(authorize_actor_action(system, "reminder:deliver", audience))
        self.assertFalse(authorize_viewer(
            ViewerContext(None, "anonymous"),
            owner_member_id="hanghang",
            visibility="PRIVATE",
        ))

    def test_system_actor_requires_capability(self):
        actor = ActorContext(
            None, "system", "system", frozenset({"reminder:deliver"})
        )
        self.assertTrue(authorize_actor_action(
            actor, "reminder:deliver", AudienceContext("hanghang", "reminder")
        ))
        self.assertFalse(authorize_actor_action(actor, "memory:read"))

    def test_member_actor_must_be_verified(self):
        with self.assertRaises(ValueError):
            ActorContext("hanghang", "member", "unverified")
        actor = ActorContext("parent", "member", "verified")
        self.assertTrue(authorize_actor_action(actor, "reminder:create"))

    def test_private_view_is_owner_only_or_explicit_grant(self):
        self.assertTrue(authorize_viewer(
            ViewerContext("hanghang", "verified"),
            owner_member_id="hanghang",
            visibility="PRIVATE",
        ))
        self.assertFalse(authorize_viewer(
            ViewerContext("parent", "verified"),
            owner_member_id="hanghang",
            visibility="PRIVATE",
        ))
        self.assertTrue(authorize_viewer(
            ViewerContext("parent", "verified", frozenset({"private:read:hanghang"})),
            owner_member_id="hanghang",
            visibility="PRIVATE",
        ))

    def test_family_view_requires_explicit_grant(self):
        self.assertFalse(authorize_viewer(
            ViewerContext("parent", "verified"),
            owner_member_id="hanghang",
            visibility="FAMILY",
        ))
        self.assertTrue(authorize_viewer(
            ViewerContext("parent", "verified", frozenset({"family:read"})),
            owner_member_id="hanghang",
            visibility="FAMILY",
        ))

    def test_missing_viewer_fails_closed_for_non_public_data(self):
        self.assertFalse(authorize_viewer(
            None, owner_member_id="parent", visibility="PRIVATE"
        ))
        self.assertFalse(authorize_viewer(
            None, owner_member_id=None, visibility="FAMILY"
        ))
        self.assertTrue(authorize_viewer(
            None, owner_member_id=None, visibility="PUBLIC"
        ))


if __name__ == "__main__":
    unittest.main()
