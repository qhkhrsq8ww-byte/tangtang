"""Presentation mapping stays out of V4 Brain. Failures do not crash Brain."""
from __future__ import annotations

import ast
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.events.event import Event
from core.response.orchestrator import PresentationAction, ResponseOrchestrator
from core.runtime.presentation import PresentationRuntime
from presentation.animation_controller import AnimationController


CORE = ROOT / "core"
FORBIDDEN_SNIPPETS = (
    "assets/character/tangtang",
    "from presentation",
    "import presentation",
    ".png",
)


def _boom(*_a, **_k):
    raise RuntimeError("sink down")


class TestBrainDoesNotOwnImages(unittest.TestCase):
    def test_core_python_has_no_character_png_paths(self) -> None:
        hits: list[str] = []
        for path in CORE.rglob("*.py"):
            text = path.read_text(encoding="utf-8")
            rel = path.relative_to(ROOT).as_posix()
            for needle in FORBIDDEN_SNIPPETS:
                if needle == ".png" and "tangtang" not in text.lower():
                    # allow unrelated comments; still ban explicit character png use
                    continue
                if needle in text:
                    hits.append(f"{rel}: {needle}")
        self.assertEqual(hits, [])

    def test_core_does_not_import_presentation_package(self) -> None:
        for path in CORE.rglob("*.py"):
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        self.assertFalse(alias.name == "presentation" or alias.name.startswith("presentation."))
                if isinstance(node, ast.ImportFrom) and node.module:
                    self.assertFalse(node.module == "presentation" or node.module.startswith("presentation."))

    def test_orchestrator_emits_action_id_not_path(self) -> None:
        orch = ResponseOrchestrator(responder=lambda ctx: "汪汪～")
        action = orch.run(decision="SPEAK", context={"who": {"member_id": "dad"}}, action="idle")
        self.assertEqual(action.action, "idle")
        self.assertNotIn(".png", action.action)
        self.assertNotIn("assets/", action.text)


class TestPresentationRuntimeIsolation(unittest.TestCase):
    def test_projection_failure_keeps_event(self) -> None:
        ev = Event.create(id="evt_proj", type="tick", source="test")
        action = PresentationAction(
            decision="SPEAK", text="hi", action="show", member_id="dad", sink="projection"
        )
        delivered = PresentationRuntime(projection=_boom).deliver(ev, action)
        self.assertTrue(delivered.event_kept)
        self.assertFalse(delivered.projection_ok)

    def test_controller_used_as_projection_sink(self) -> None:
        ctrl = AnimationController()
        ev = Event.create(type="utterance", source="mic", privacy="FAMILY")
        action = PresentationAction(
            decision="SPEAK", text="汪汪～", action="greet", member_id="child_9", sink="projection"
        )

        def project(payload):
            clips = ctrl.apply(ev, payload)
            if not clips:
                raise RuntimeError("no clip")
            return clips[0].name

        delivered = PresentationRuntime(projection=project).deliver(ev, action)
        self.assertTrue(delivered.event_kept)
        self.assertTrue(delivered.projection_ok)

    def test_family_json_untouched_by_presentation(self) -> None:
        family = (ROOT / "data" / "family.json").read_text(encoding="utf-8")
        src = (ROOT / "presentation" / "animation_controller.py").read_text(encoding="utf-8")
        self.assertNotIn("family.json", src)
        self.assertIn("member", family.lower() + family)


if __name__ == "__main__":
    unittest.main()
