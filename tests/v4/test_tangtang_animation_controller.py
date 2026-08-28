"""V10 AnimationController: switching, timing, sleep lock, missing-frame isolation."""
from __future__ import annotations

import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.events.event import Event
from core.response.orchestrator import PresentationAction, ResponseOrchestrator
from presentation.animation_controller import AnimationController, _is_two_frame_pong
from presentation.mapping import AnimationAction, plan_actions
from presentation.state_machine import SLEEP_LOCK_PRIORITY, AnimationStateMachine


def _idx(path: str) -> int:
    stem = Path(path).stem
    return int(stem) if stem.isdigit() else -1


class TestPlayHappy(unittest.TestCase):
    def setUp(self) -> None:
        self.ctrl = AnimationController(now=lambda: datetime(2026, 8, 28, 16, 0))

    def test_idle_default(self) -> None:
        clip = self.ctrl.play(None)
        self.assertEqual(clip.name, "idle")
        self.assertEqual(clip.state, "IDLE")
        self.assertTrue(clip.loop)
        self.assertGreaterEqual(clip.resolved_frame_count, 1)
        self.assertEqual(clip.declared_frame_count, 8)
        self.assertEqual(clip.scale, 1.0)
        self.assertEqual(clip.anchor, {"x": 0.5, "y": 1.0})
        self.assertEqual(clip.projection["character"], [512, 512])
        self.assertEqual(clip.projection["canvas"], [1920, 1080])

    def test_each_declared_frame_count(self) -> None:
        expected = {
            "idle": 8,
            "blink": 6,
            "listen": 8,
            "happy": 8,
            "encourage": 8,
            "sad": 8,
            "walk": 12,
            "run": 12,
            "sit": 8,
            "lie": 8,
            "sleep": 8,
        }
        for name, count in expected.items():
            clip = AnimationController(now=lambda: datetime(2026, 8, 28, 16, 0)).play(name)
            self.assertEqual(clip.declared_frame_count, count, name)

    def test_idle_does_not_skip_frames(self) -> None:
        clip = self.ctrl.play("idle")
        seq = clip.timeline(16)
        idxs = [_idx(p) for p in seq]
        for a, b in zip(idxs, idxs[1:]):
            if clip.loop and len(clip.frames) > 1:
                delta = (b - a) % len(clip.frames)
                self.assertIn(delta, (0, 1))
            else:
                self.assertLessEqual(abs(b - a), 1)

    def test_walk_is_continuous_not_two_frame_pong(self) -> None:
        clip = self.ctrl.play("walk")
        self.assertEqual(clip.name, "walk")
        self.assertFalse(clip.fallback_used)
        self.assertGreaterEqual(clip.resolved_frame_count, 8)
        self.assertEqual(clip.fps, 12)
        self.assertTrue(clip.loop)
        self.assertTrue(clip.continuous)
        seq = clip.timeline(24)
        self.assertFalse(_is_two_frame_pong(seq))
        idxs = [_idx(p) for p in seq]
        for a, b in zip(idxs, idxs[1:]):
            self.assertEqual((a + 1) % clip.resolved_frame_count, b)

    def test_run_is_continuous_not_two_frame_pong(self) -> None:
        clip = self.ctrl.play("run")
        self.assertEqual(clip.name, "run")
        self.assertFalse(clip.fallback_used)
        self.assertGreaterEqual(clip.resolved_frame_count, 8)
        self.assertFalse(_is_two_frame_pong(clip.timeline(16)))
        idxs = [_idx(p) for p in clip.timeline(clip.resolved_frame_count * 2)]
        n = clip.resolved_frame_count
        for a, b in zip(idxs, idxs[1:]):
            self.assertEqual((a + 1) % n, b)

    def test_sleep_does_not_flicker(self) -> None:
        clip = self.ctrl.play("sleep")
        self.assertEqual(clip.name, "sleep")
        self.assertLessEqual(clip.fps, 4)
        self.assertTrue(clip.loop)
        seq = clip.timeline(8)
        idxs = [_idx(p) for p in seq]
        for a, b in zip(idxs, idxs[1:]):
            self.assertLessEqual(abs(b - a) % max(len(clip.frames), 1), 1)

    def test_state_switch_does_not_crash(self) -> None:
        for name in ("idle", "listen", "happy", "walk", "run", "sit", "sad", "encourage", "sleep"):
            clip = self.ctrl.play_safe(name)
            self.assertTrue(clip.frames or clip.fallback_used or clip.name == "idle")
            self.assertEqual(clip.scale, 1.0)

    def test_unknown_action_falls_back_idle(self) -> None:
        clip = self.ctrl.play("飞天")
        self.assertEqual(clip.name, "idle")

    def test_presentation_action_mapping(self) -> None:
        action = PresentationAction(
            decision="SPEAK", text="汪汪～", action="greet", member_id="child_9", sink="voice"
        )
        clip = self.ctrl.play(action)
        self.assertEqual(clip.name, "happy")


class TestSleepLockAndNight(unittest.TestCase):
    def test_sleep_ignores_high_frequency(self) -> None:
        ctrl = AnimationController(now=lambda: datetime(2026, 8, 28, 16, 0))
        ctrl.play("sleep")
        blocked = ctrl.play("listen")
        self.assertTrue(blocked.interrupt_blocked)
        self.assertEqual(ctrl.machine.state, "SLEEP")
        still = ctrl.play("blink")
        self.assertEqual(ctrl.machine.state, "SLEEP")
        self.assertTrue(still.interrupt_blocked)

    def test_sleep_wake_with_force(self) -> None:
        ctrl = AnimationController(now=lambda: datetime(2026, 8, 28, 16, 0))
        ctrl.play("sleep")
        woke = ctrl.play(AnimationAction("idle", priority=SLEEP_LOCK_PRIORITY + 1, force=True))
        self.assertEqual(woke.name, "idle")
        self.assertEqual(ctrl.machine.state, "IDLE")

    def test_night_softens_run(self) -> None:
        ctrl = AnimationController(now=lambda: datetime(2026, 8, 28, 23, 10))
        clip = ctrl.play("run")
        self.assertNotEqual(clip.name, "run")
        self.assertTrue(clip.night_softened)
        self.assertIn(clip.name, ("sit", "idle"))

    def test_state_machine_lock_priority(self) -> None:
        sm = AnimationStateMachine()
        sm.request("SLEEP", priority=10, interrupt=True)
        denied = sm.request("LISTEN", priority=3, interrupt=True)
        self.assertFalse(denied.accepted)
        self.assertEqual(denied.reason, "sleep_locked")


class TestMissingFramesIsolateBrain(unittest.TestCase):
    def test_missing_root_falls_back_without_raise(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ctrl = AnimationController(root=tmp, now=lambda: datetime(2026, 8, 28, 16, 0))
            clip = ctrl.play_safe("walk")
            self.assertEqual(clip.name, "idle")
            self.assertTrue(clip.fallback_used)

    def test_two_frame_pong_rejected_for_walk(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            walk = root / "walk"
            walk.mkdir()
            png = (
                b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
                b"\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\rIDATx\x9cc````"
                b"\x00\x00\x00\x05\x00\x01\xa5\xf6E@\x00\x00\x00\x00IEND\xaeB`\x82"
            )
            (walk / "00.png").write_bytes(png)
            (walk / "01.png").write_bytes(png)
            (root / "idle").mkdir()
            (root / "idle" / "00.png").write_bytes(png)
            (root / "metadata.json").write_text(
                Path(ROOT / "assets/character/tangtang/metadata.json").read_text(encoding="utf-8"),
                encoding="utf-8",
            )
            ctrl = AnimationController(root=root, now=lambda: datetime(2026, 8, 28, 16, 0))
            clip = ctrl.play("walk")
            self.assertEqual(clip.name, "idle")
            self.assertTrue(clip.fallback_used)

    def test_brain_still_works_when_frames_missing(self) -> None:
        orch = ResponseOrchestrator(responder=lambda ctx: "汪汪～")
        action = orch.run(decision="SPEAK", context={"who": {"member_id": "mom"}}, action="greet")
        self.assertEqual(action.text, "汪汪～")
        with tempfile.TemporaryDirectory() as tmp:
            ctrl = AnimationController(root=tmp)
            clips = ctrl.apply(
                Event.create(type="utterance", source="test", privacy="FAMILY"),
                action,
            )
            self.assertTrue(clips)
            self.assertEqual(clips[-1].name, "idle")

    def test_projector_failure_isolated(self) -> None:
        ctrl = AnimationController(now=lambda: datetime(2026, 8, 28, 16, 0))
        clip = ctrl.play("idle")

        def boom(_clip):
            raise RuntimeError("projection down")

        self.assertFalse(ctrl.project_safe(boom, clip))
        # Brain path still returns a PresentationAction
        orch = ResponseOrchestrator(responder=lambda ctx: "汪汪～")
        self.assertEqual(orch.run(decision="SPEAK", context={}).text, "汪汪～")


class TestObserveThenAct(unittest.TestCase):
    def test_voice_event_listens_before_happy(self) -> None:
        ev = Event.create(type="utterance", source="mic", privacy="FAMILY")
        action = PresentationAction(
            decision="SPEAK", text="汪汪～", action="greet", member_id="child_9", sink="voice"
        )
        names = [step.name for step in plan_actions(ev, action, night=False)]
        self.assertEqual(names[0], "listen")
        self.assertIn("happy", names)

    def test_apply_sequence(self) -> None:
        ctrl = AnimationController(now=lambda: datetime(2026, 8, 28, 16, 0))
        ev = Event.create(type="voice.observed", source="mic", privacy="PUBLIC")
        action = PresentationAction(
            decision="SPEAK", text="汪汪～", action="greet", member_id=None, sink="voice"
        )
        clips = ctrl.apply(ev, action)
        self.assertGreaterEqual(len(clips), 2)
        self.assertEqual(clips[0].name, "listen")


if __name__ == "__main__":
    unittest.main()
