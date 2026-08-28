"""Runtime paths use TANGTANG_HOME. launchd/crontab are user-level, not root."""
from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

FORBIDDEN = "/Users/lv/.qclaw/workspace/cat/"
RUNTIME_DIRS = (ROOT / "core", ROOT / "code" / "cat", ROOT / "config")
RUNTIME_SUFFIXES = {".py", ".sh", ".js", ".mjs", ".plist", ".json", ".example"}


def _iter_runtime_files():
    for base in RUNTIME_DIRS:
        if not base.exists():
            continue
        for path in base.rglob("*"):
            if not path.is_file():
                continue
            if "backups" in path.parts:
                continue
            if path.suffix not in RUNTIME_SUFFIXES and path.name != "crontab.example":
                continue
            yield path


class TestNoHardcodedCatHome(unittest.TestCase):
    def test_runtime_files_use_tangtang_home(self):
        hits = []
        for path in _iter_runtime_files():
            text = path.read_text(encoding="utf-8", errors="replace")
            if FORBIDDEN in text:
                hits.append(str(path.relative_to(ROOT)))
        self.assertEqual(hits, [], f"hardcoded old cat home in {hits}")

    def test_tangtang_home_required_for_persist(self):
        from core.errors import PathError
        from core.memory.paths import tangtang_home

        env = os.environ.pop("TANGTANG_HOME", None)
        data = os.environ.pop("TANGTANG_DATA_DIR", None)
        try:
            with self.assertRaises(PathError):
                tangtang_home()
        finally:
            if env is not None:
                os.environ["TANGTANG_HOME"] = env
            if data is not None:
                os.environ["TANGTANG_DATA_DIR"] = data


class TestLaunchdCrontabNotRoot(unittest.TestCase):
    def test_plist_is_user_agent_template(self):
        plist = (ROOT / "config" / "com.tangtang.daemon.plist.example").read_text(encoding="utf-8")
        self.assertIn("__TANGTANG_HOME__", plist)
        self.assertNotIn("sudo launchctl", plist)
        self.assertIn("com.tangtang.daemon", plist)
        self.assertIn("LaunchAgent", plist)

    def test_crontab_example_uses_env_home(self):
        cron = (ROOT / "config" / "crontab.example").read_text(encoding="utf-8")
        self.assertIn("$TANGTANG_HOME", cron)
        self.assertNotIn(FORBIDDEN, cron)
        self.assertIn("不要 root", cron)

    def test_migrate_requires_tangtang_home(self):
        script = (ROOT / "config" / "migrate-paths.sh").read_text(encoding="utf-8")
        self.assertIn("TANGTANG_HOME", script)
        self.assertIn("LaunchAgents", script)
        self.assertIn("禁止 sudo", script)
        self.assertNotIn(FORBIDDEN, script)


if __name__ == "__main__":
    unittest.main()
