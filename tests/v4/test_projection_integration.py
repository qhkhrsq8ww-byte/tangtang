"""Projection + animation stay outside Family Brain. Failures do not crash."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.adapters.animation import ANIMATION_NAMES, AnimationAction, AnimationController
from core.adapters.family_loader import load_members
from core.adapters.projection_adapter import ProjectionAdapter
from core.events.event import Event
from core.response.orchestrator import PresentationAction
from tangtang_runtime import TangTangRuntime

MEMBERS = load_members()
PROJ_SRC = (ROOT / "core" / "adapters" / "projection_adapter.py").read_text(encoding="utf-8")


class TestProjectionFailureIsolated(unittest.TestCase):
    def test_projection_fail_keeps_event(self):
        ev = Event.create(id="evt_proj", type="show", privacy="PUBLIC", member_id="dad")
        action = PresentationAction(
            decision="SPEAK", text="汪汪～", action="show", member_id="dad", sink="projection"
        )

        def boom(_action):
            raise RuntimeError("hdmi")

        delivered = ProjectionAdapter(projector=boom).deliver(ev, action)
        self.assertTrue(delivered.event_kept)
        self.assertFalse(delivered.projection_ok)
        self.assertEqual(delivered.event_id, "evt_proj")

    def test_runtime_projection_fail_does_not_drop_brain_event(self):
        def boom(_action):
            raise RuntimeError("screen")

        rt = TangTangRuntime(members=MEMBERS, projection=ProjectionAdapter(projector=boom))
        result = rt.handle_utterance("糖糖，帮我看看明天天气。", {"label": "grandpa"})
        self.assertTrue(result.event_kept)
        self.assertTrue(result.event_id)
        # Voice sink SPEAK does not invoke projection; present() with projection sink does.
        action = PresentationAction(
            decision="SPEAK",
            text=result.action.text,
            action="show",
            member_id="grandpa",
            sink="projection",
        )
        delivery, _frames = rt.present(result.event, action)
        self.assertTrue(delivery.event_kept)
        self.assertFalse(delivery.projection_ok)

    def test_core_does_not_name_screen_binary(self):
        self.assertNotIn("hdmi", PROJ_SRC.lower())


class TestAnimationOutsideBrain(unittest.TestCase):
    def test_known_clips(self):
        self.assertEqual(ANIMATION_NAMES, ("站立", "眨眼", "走路", "跑步"))
        ctrl = AnimationController()
        for name in ANIMATION_NAMES:
            frames = ctrl.play(AnimationAction(name))
            self.assertTrue(frames)
        self.assertIn("walk_0", ctrl.play("走路"))
        self.assertIn("run_0", ctrl.play("跑步"))

    def test_unknown_clip_falls_back_to_stand(self):
        frames = AnimationController().play("飞天")
        self.assertTrue(frames)
        self.assertIn("stand_0", frames)

    def test_controller_failure_isolated(self):
        frames = AnimationController().play_safe(None)
        self.assertTrue(frames)

    def test_phone_scene_uses_walk(self):
        from core.ingest import PrivacyPipeline
        from core.policy.interrupt_policy import InterruptPolicy
        from datetime import datetime, timezone

        day = datetime(2026, 8, 28, 16, 0, tzinfo=timezone.utc)
        rt = TangTangRuntime(
            members=MEMBERS,
            pipeline=PrivacyPipeline(members=MEMBERS, interrupt=InterruptPolicy(clock=lambda: day)),
        )
        result = rt.handle_living_room("手机", member_id="dad")
        if result.decision == "SPEAK":
            self.assertTrue(any(f.startswith("walk_") for f in result.animation))


if __name__ == "__main__":
    unittest.main()
