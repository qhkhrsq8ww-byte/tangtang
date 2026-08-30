"""Live wrappers: desktop MP4 pet entry + V4 pipeline flags (no network)."""
from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CAT = ROOT / "code" / "cat"


class TestPetEntryScripts(unittest.TestCase):
    def test_cat_sh_pet_points_at_desktop_pet(self):
        src = (CAT / "cat.sh").read_text(encoding="utf-8")
        self.assertIn("tangtang_ensure_pet", src)
        self.assertIn("cat-desktop-pet.html", src)
        self.assertIn("./cat.sh -p", src)
        self.assertNotIn("cat-pet.html", src)

    def test_lib_and_start_open_desktop_pet(self):
        lib = (CAT / "cat-lib.sh").read_text(encoding="utf-8")
        start = (CAT / "start-cat.sh").read_text(encoding="utf-8")
        self.assertIn("tangtang_ensure_pet()", lib)
        self.assertIn("http://127.0.0.1:8080/cat-desktop-pet.html", lib)
        self.assertIn("python3 -m http.server 8080", lib)
        self.assertIn("tangtang_ensure_pet", start)
        self.assertIn("file://", lib)


class TestLiveWrappersSetV4(unittest.TestCase):
    def test_voice_exports_v4(self):
        src = (CAT / "cat-voice.sh").read_text(encoding="utf-8")
        self.assertIn("TANGTANG_V4_PIPELINE=1", src)
        self.assertIn("cat-chat.py", src)
        self.assertIn("cat-presence.py", src)
        self.assertIn("suggest", src)
        self.assertIn("EXPLICIT_MEMBER", src)
        self.assertIn("cat-family.py", src)

    def test_cat_sh_chat_exports_v4(self):
        src = (CAT / "cat.sh").read_text(encoding="utf-8")
        self.assertIn("TANGTANG_V4_PIPELINE=1", src)
        self.assertIn('CHAT_REQ=1', src.replace(" ", ""))

    def test_example_config_exports_v4(self):
        src = (CAT / "tangtang-config.example.sh").read_text(encoding="utf-8")
        self.assertIn("export TANGTANG_V4_PIPELINE=1", src)

    def test_cat_chat_cli_stays_opt_in(self):
        src = (CAT / "cat-chat.py").read_text(encoding="utf-8")
        self.assertIn('os.environ.get("TANGTANG_V4_PIPELINE") == "1"', src)
        self.assertIn("def chat(", src)
        self.assertIn("def build_persona(", src)


if __name__ == "__main__":
    unittest.main()
