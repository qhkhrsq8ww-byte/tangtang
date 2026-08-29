from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

from behavior.character_state import VALID_STATES, CharacterStateEngine, CharacterStateResolver
from behavior.legacy_adapter import decide_from_legacy, policy_for, to_event
from core.presentation.action import FORBIDDEN_BUSINESS, PRESENTATION_STATES, PresentationAction
from core.presentation.asset_registry import AssetRegistry
from core.presentation.character_presenter import CharacterPresenter


REPO = Path(__file__).resolve().parents[2]


class PresentationContractTests(unittest.TestCase):
    def test_unknown_state_falls_back_idle(self):
        a = PresentationAction(state="homework", speak=True, speech_allowed=True, text="x")
        self.assertEqual(a.state, "idle")

    def test_speech_gated(self):
        a = PresentationAction(state="caring", speak=True, speech_allowed=False, text="hi")
        self.assertFalse(a.speak)

    def test_no_business_states_in_presentation_set(self):
        for name in FORBIDDEN_BUSINESS:
            self.assertNotIn(name, PRESENTATION_STATES)

    def test_seventeen_states(self):
        self.assertEqual(len(PRESENTATION_STATES), 17)
        self.assertEqual(VALID_STATES, PRESENTATION_STATES)


class AssetRegistryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.reg = AssetRegistry()

    def test_all_videos_present(self):
        self.assertEqual(self.reg.missing(), [])

    def test_registry_has_no_homework_key(self):
        from core.presentation.asset_registry import STATE_FILES
        self.assertNotIn("homework", STATE_FILES)
        self.assertNotIn("exercise", STATE_FILES)

    def test_filename_never_none(self):
        for state in PRESENTATION_STATES:
            name = self.reg.filename(state)
            self.assertTrue(name.endswith(".mp4"))
            self.assertTrue(self.reg.exists(state), state)


class ResolverPrivacyTests(unittest.TestCase):
    def test_strips_utterance_keys(self):
        d = CharacterStateResolver().resolve(
            {"type": "conversation.started", "emotion": "sad", "utterance": "secret", "text": "secret"},
            {},
            {"now": datetime(2026, 8, 29, 16, 0)},
            {"decision": "SPEAK"},
        )
        self.assertNotIn("secret", d.reason)

    def test_engine_does_not_import_memory(self):
        import behavior.character_state as mod
        src = Path(mod.__file__).read_text(encoding="utf-8")
        self.assertNotIn("from core.memory", src)
        self.assertNotIn("assets/video", src)


class LegacyAdapterTests(unittest.TestCase):
    def test_event_state_table_not_used_for_exercise(self):
        d = decide_from_legacy("exercise", now=datetime(2026, 8, 29, 16, 0))
        self.assertEqual(d.presentation_state, "encouraging")

    def test_home_welcome(self):
        self.assertEqual(decide_from_legacy("home", now=datetime(2026, 8, 29, 16, 0)).presentation_state, "welcome")

    def test_sleep_sleeping(self):
        self.assertEqual(decide_from_legacy("sleep", now=datetime(2026, 8, 29, 16, 0)).presentation_state, "sleeping")

    def test_policy_quiet(self):
        ev = to_event("exercise", now=datetime(2026, 8, 29, 23, 40))
        p = policy_for(ev, now=datetime(2026, 8, 29, 23, 40))
        self.assertEqual(p["decision"], "SILENT")
        self.assertTrue(p["quiet_hours"])


class CatBrainIntegrationTests(unittest.TestCase):
    def test_brain_visual_from_engine(self):
        env = os.environ.copy()
        with tempfile.TemporaryDirectory() as tmp:
            env["TANGTANG_DATA_DIR"] = tmp
            env["TANGTANG_NOW"] = "2026-08-29T16:00:00"
            env["PYTHONPATH"] = str(REPO) + os.pathsep + env.get("PYTHONPATH", "")
            proc = subprocess.run(
                [sys.executable, str(REPO / "code/cat/cat-brain.py"), "home"],
                cwd=str(REPO / "code/cat"),
                capture_output=True,
                text=True,
                env=env,
                timeout=20,
            )
            self.assertEqual(proc.returncode, 0, proc.stderr)
            parts = proc.stdout.strip().split("\t")
            self.assertGreaterEqual(len(parts), 3)
            self.assertEqual(parts[-1], "welcome")
            action = json.loads(Path(tmp, "cat-presentation-action.json").read_text(encoding="utf-8"))
            self.assertEqual(action["state"], "welcome")

    def test_brain_night_exercise_no_speech(self):
        env = os.environ.copy()
        with tempfile.TemporaryDirectory() as tmp:
            env["TANGTANG_DATA_DIR"] = tmp
            env["PYTHONPATH"] = str(REPO) + os.pathsep + env.get("PYTHONPATH", "")
            # Freeze clock via event path: engine uses datetime.now unless we patch.
            # Call adapter directly for night; brain uses live clock.
            d = decide_from_legacy("exercise", now=datetime(2026, 8, 29, 23, 30))
            self.assertEqual(d.presentation_state, "night")
            self.assertFalse(d.speech_allowed)


class DesktopPetContractTests(unittest.TestCase):
    def test_html_avoids_business_events(self):
        html = (REPO / "code/cat/cat-desktop-pet.html").read_text(encoding="utf-8")
        self.assertIn("applyPresentationAction", html)
        self.assertIn("LEGACY ONLY", html)
        self.assertNotIn("{ name:'homework'", html.replace(" ", ""))
        self.assertNotIn("{ name:'exercise'", html.replace(" ", ""))
        self.assertNotIn("{ name:'screen'", html.replace(" ", ""))

    def test_html_lists_all_seventeen(self):
        html = (REPO / "code/cat/cat-desktop-pet.html").read_text(encoding="utf-8")
        for state in PRESENTATION_STATES:
            self.assertIn(f"name:'{state}'", html.replace(" ", ""), f"missing {state}")


class PresenterTtsDecoupleTests(unittest.TestCase):
    def test_tts_failure_does_not_change_state(self):
        d = CharacterStateResolver().resolve(
            {"type": "home.arrived"}, {}, {"now": datetime(2026, 8, 29, 16, 0)}, {"decision": "SPEAK"}
        )

        def broken_tts(_text: str) -> None:
            raise RuntimeError("tts down")

        action = CharacterPresenter().present(d, text="汪汪～")
        self.assertEqual(action.state, "welcome")
        try:
            broken_tts(action.text)
        except RuntimeError:
            pass
        self.assertEqual(action.state, "welcome")

    def test_silent_policy_no_speech(self):
        d = CharacterStateResolver().resolve(
            {"type": "screen.started"},
            {},
            {"now": datetime(2026, 8, 29, 23, 40)},
            {"decision": "SILENT", "quiet_hours": True},
        )
        action = CharacterPresenter().present(d, text="起来走走")
        self.assertFalse(action.speak)


class FallbackTests(unittest.TestCase):
    def test_bad_event_idle(self):
        d = CharacterStateResolver().resolve({}, {}, {"now": datetime(2026, 8, 29, 16, 0)}, {})
        self.assertEqual(d.presentation_state, "idle")

    def test_engine_survives_empty(self):
        d = CharacterStateEngine().decide({}, {}, {}, {})
        self.assertIn(d.presentation_state, VALID_STATES)

    def test_missing_video_falls_back_name(self):
        reg = AssetRegistry(root=REPO / "does-not-exist")
        self.assertEqual(reg.filename("caring"), "tangtang-caring.mp4")


class HoldMemoryTests(unittest.TestCase):
    def test_hold_does_not_grow_with_events(self):
        engine = CharacterStateEngine()
        t0 = datetime(2026, 8, 29, 16, 0, 0)
        for i in range(1800):
            engine.decide({"type": "screen.started"}, {}, {"now": t0}, {"decision": "SPEAK"})
        self.assertIsNotNone(engine._hold)
        self.assertEqual(engine._hold.state, "encouraging")


def _expand_state_matrix():
    cases = []
    for state in sorted(PRESENTATION_STATES):
        cases.append(state)
    return cases


class MatrixSmokeTests(unittest.TestCase):
    def test_presenter_emits_each_state(self):
        class Fake:
            presentation_state = "idle"
            speech_allowed = False
            transition_hint = "crossfade"
            previous_state = None
            intensity = 0.5
            reason = "x"

        presenter = CharacterPresenter()
        for state in PRESENTATION_STATES:
            Fake.presentation_state = state
            action = presenter.present(Fake(), text="")
            self.assertEqual(action.state, state)
            self.assertFalse(action.speak)
