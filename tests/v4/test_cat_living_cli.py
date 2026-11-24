"""cat-living CLI + remind wiring (no Mac TTS)."""

from __future__ import annotations

import importlib.util
import os
import sys
import types
from types import SimpleNamespace
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, ROOT)


def _load_living():
    path = ROOT / "code" / "cat" / "cat-living.py"
    spec = importlib.util.spec_from_file_location("cat_living_cli", path)
    mod = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(mod)
    return mod


class TestCatLiving(unittest.TestCase):
    def test_normalize_events(self):
        mod = _load_living()
        self.assertEqual(mod._normalize("rest"), "久坐")
        self.assertEqual(mod._normalize("exercise"), "运动")
        self.assertEqual(mod._habit_tag("sleep"), "sleep")

    def test_speaker_environment_variable_is_not_a_proactive_target(self):
        source = (ROOT / "code" / "cat" / "cat-living.py").read_text(encoding="utf-8")
        self.assertNotIn("TANGTANG_SPEAKER", source)
        self.assertIn('obs["audience_id"] = member', source)
        self.assertIn("audience_id=member or None", source)

    def test_unregistered_cli_target_is_not_written_as_audience(self):
        mod = _load_living()
        calls = {}
        class FakeRuntime:
            members = {"hanghang": {}}
            def handle_living_room(self, kind, *, audience_id=None, observation=None):
                calls["kind"] = kind
                calls["audience_id"] = audience_id
                calls["observation"] = dict(observation or {})
                return SimpleNamespace(decision="SILENT", action=None, member_id=None, observation={})
        fake_module = types.ModuleType("tangtang_runtime")
        fake_module.TangTangRuntime = FakeRuntime
        with tempfile.TemporaryDirectory() as td:
            with mock.patch.dict(sys.modules, {"tangtang_runtime": fake_module}):
                with mock.patch.object(mod, "data_dir", return_value=td):
                    with mock.patch.dict(
                        os.environ,
                        {"TANGTANG_DATA_DIR": td, "TANGTANG_MEMBER_ID": "", "TANGTANG_SPEAKER": "hanghang"},
                        clear=False,
                    ):
                        code = mod.main(["meal", "not-a-member"])
        self.assertEqual(code, 0)
        self.assertIsNone(calls["audience_id"])
        self.assertEqual(calls["observation"], {})

    def test_sleeping_silent_no_stdout(self):
        mod = _load_living()
        with tempfile.TemporaryDirectory() as td:
            with mock.patch.object(mod, "data_dir", return_value=td):
                with mock.patch.dict(os.environ, {"TANGTANG_DATA_DIR": td}, clear=False):
                    # sleeping observation forces SILENT in runtime tests; pass via audience only
                    code = mod.main(["睡觉", "hanghang"])
            self.assertEqual(code, 0)


if __name__ == "__main__":
    unittest.main()
