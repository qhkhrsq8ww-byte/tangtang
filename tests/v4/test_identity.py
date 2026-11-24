"""IdentityResolver: observation → member_id. Not embedded in Event."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.identity.resolver import IdentityResolver
from core.interfaces import IdentityPort

V4_MEMBERS = {
    "grandpa": {"display_name": "爷爷", "relation": "elder", "aliases": ["爷爷"]},
    "grandma": {"display_name": "奶奶", "relation": "elder", "aliases": ["奶奶"]},
    "dad": {"display_name": "爸爸", "profile": "adult", "aliases": ["爸爸"]},
    "mom": {"display_name": "妈妈", "profile": "adult", "aliases": ["妈妈", "妈"]},
    "child_12": {
        "display_name": "姐姐",
        "relation": "child",
        "age": 12,
        "aliases": ["姐姐", "12岁女孩"],
    },
    "child_9": {
        "display_name": "弟弟",
        "relation": "child",
        "age": 9,
        "aliases": ["弟弟", "9岁男孩"],
    },
}


class TestIdentityHappy(unittest.TestCase):
    def setUp(self):
        self.r = IdentityResolver(V4_MEMBERS)
        self.assertIsInstance(self.r, IdentityPort)

    def test_registry_id(self):
        self.assertEqual(self.r.resolve({"member_id": "dad"}), "dad")

    def test_sister_alias_maps_to_registry_not_overwrite(self):
        self.assertEqual(self.r.resolve({"label": "12岁姐姐"}), "child_12")
        self.assertEqual(self.r.resolve({"label": "qiaqia"}), "child_12")
        self.assertEqual(self.r.resolve({"label": "洽洽"}), "child_12")

    def test_brother_alias(self):
        self.assertEqual(self.r.resolve({"label": "9岁弟弟"}), "child_9")
        self.assertEqual(self.r.resolve({"label": "hanghang"}), "child_9")
        self.assertEqual(self.r.resolve({"label": "航航"}), "child_9")

    def test_mom_present(self):
        self.assertEqual(self.r.resolve({"label": "妈妈"}), "mom")

    def test_presence_beats_label(self):
        self.assertEqual(
            self.r.resolve({"presence_member_id": "dad", "label": "姐姐"}),
            "dad",
        )


class TestIdentityEmptyUnknown(unittest.TestCase):
    def setUp(self):
        self.r = IdentityResolver(V4_MEMBERS)

    def test_empty_none(self):
        self.assertIsNone(self.r.resolve(None))
        self.assertIsNone(self.r.resolve({}))
        self.assertIsNone(self.r.resolve(""))

    def test_unknown(self):
        self.assertIsNone(self.r.resolve({"label": "邻居小孩"}))
        self.assertIsNone(self.r.resolve({"member_id": "stranger"}))


class TestIdentityVoiceprintNotPrimary(unittest.TestCase):
    def test_voiceprint_only_unknown(self):
        r = IdentityResolver(V4_MEMBERS)
        self.assertIsNone(r.resolve({"voiceprint_id": "vp_child_9"}))

    def test_school_hours_child_not_home(self):
        r = IdentityResolver(V4_MEMBERS)
        self.assertIsNone(r.resolve({
            "label": "hanghang",
            "school_hours": True,
            "presence_home": False,
        }))

    def test_school_hours_child_home_ok(self):
        r = IdentityResolver(V4_MEMBERS)
        self.assertEqual(
            r.resolve({
                "label": "hanghang",
                "school_hours": True,
                "presence_home": True,
            }),
            "child_9",
        )


class TestIdentityProductWithoutRegistry(unittest.TestCase):
    def test_empty_members_uses_product_ids(self):
        r = IdentityResolver({})
        self.assertEqual(r.resolve({"label": "12岁姐姐"}), "qiaqia")
        self.assertEqual(r.resolve({"label": "9岁弟弟"}), "hanghang")
        self.assertEqual(r.resolve({"label": "妈妈"}), "mom")


class TestIdentityDecoupledFromEvent(unittest.TestCase):
    def test_resolver_source_has_no_event_import(self):
        from core.identity import resolver as mod
        src = Path(mod.__file__).read_text(encoding="utf-8")
        self.assertNotIn("from core.events", src)
        self.assertNotIn("import Event", src)
        self.assertNotIn("EventBus", src)


class TestPerceptionEvidence(unittest.TestCase):
    def test_identity_evidence_requires_verified_fresh_confident_signal(self):
        from datetime import datetime, timedelta, timezone
        from core.perception.evidence import evidence_is_usable

        now = datetime(2026, 11, 24, 12, 0, tzinfo=timezone.utc)
        valid = {
            "evidence": {
                "identity": {
                    "source": "voiceprint_presence_fusion",
                    "observed_at": (now - timedelta(seconds=5)).isoformat(),
                    "expires_at": (now + timedelta(seconds=20)).isoformat(),
                    "confidence": 0.93,
                    "verification_status": "verified",
                }
            }
        }
        self.assertTrue(evidence_is_usable(valid, "identity", now=now))
        stale = {"evidence": {"identity": {**valid["evidence"]["identity"], "observed_at": (now - timedelta(minutes=5)).isoformat()}}}
        self.assertFalse(evidence_is_usable(stale, "identity", now=now))
        weak = {"evidence": {"identity": {**valid["evidence"]["identity"], "confidence": 0.5}}}
        self.assertFalse(evidence_is_usable(weak, "identity", now=now))
        unverified = {"evidence": {"identity": {**valid["evidence"]["identity"], "verification_status": "candidate"}}}
        self.assertFalse(evidence_is_usable(unverified, "identity", now=now))

    def test_required_identity_evidence_fails_closed_in_resolver(self):
        r = IdentityResolver(V4_MEMBERS)
        self.assertIsNone(r.resolve({
            "label": "dad",
            "identity_evidence_required": True,
            "evidence": {},
        }))
        from datetime import datetime, timedelta, timezone
        now = datetime.now(timezone.utc)
        self.assertEqual(r.resolve({
            "label": "dad",
            "identity_evidence_required": True,
            "evidence": {
                "identity": {
                    "source": "manual_confirmation",
                    "observed_at": (now - timedelta(seconds=1)).isoformat(),
                    "expires_at": (now + timedelta(seconds=30)).isoformat(),
                    "confidence": 1.0,
                    "verification_status": "verified",
                }
            },
        }), "dad")


if __name__ == "__main__":
    unittest.main()
