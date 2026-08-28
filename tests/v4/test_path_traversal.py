"""Path traversal and shell: stay under TANGTANG_HOME; no event → os.system."""
from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.errors import PathError, ShellError
from core.events.event import Event
from core.memory.paths import habit_file, private_file, resolve_under, tangtang_home
from core.memory.private import PrivateMemory
from core.security.shell import guarded_system, reject_event_shell


class TestPathTraversalRejected(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="tangtang-home-"))

    def test_dotdot_rejected(self):
        with self.assertRaises(PathError):
            resolve_under(self.tmp, "../etc/passwd")
        with self.assertRaises(PathError):
            resolve_under(self.tmp, "private", "../../etc/passwd")
        with self.assertRaises(PathError):
            resolve_under(self.tmp, "..")

    def test_absolute_rejected(self):
        with self.assertRaises(PathError):
            resolve_under(self.tmp, "/etc/passwd")

    def test_member_id_traversal_rejected(self):
        mem = PrivateMemory(home=self.tmp, persist=True)
        with self.assertRaises(PathError):
            mem.put(member_id="../etc", utterance="secret")
        with self.assertRaises(PathError):
            mem.put(member_id="child/9", utterance="secret")

    def test_legal_private_file_stays_under_home(self):
        path = private_file(self.tmp, "child_9")
        self.assertTrue(str(path).startswith(str(self.tmp.resolve())))
        self.assertIn("/private/child_9/", str(path).replace("\\", "/"))
        habits = habit_file(self.tmp)
        self.assertTrue(str(habits).startswith(str(self.tmp.resolve())))

    def test_tangtang_home_required(self):
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


class TestShellForbidden(unittest.TestCase):
    def test_reject_event_shell(self):
        ev = Event.create(
            type="utterance",
            privacy="PRIVATE",
            member_id="child_9",
            payload={"redacted": True},
        )
        with self.assertRaises(ShellError):
            reject_event_shell(event=ev, text="rm -rf /")
        with self.assertRaises(ShellError):
            guarded_system("echo hi")

    def test_core_has_no_os_system(self):
        core_root = ROOT / "core"
        hits = []
        for path in core_root.rglob("*.py"):
            src = path.read_text(encoding="utf-8")
            if "os.system(" in src:
                hits.append(str(path))
            if "subprocess.Popen" in src and "shell=True" in src:
                hits.append(str(path))
        self.assertEqual(hits, [])


class TestPathEmptyUnknown(unittest.TestCase):
    def test_empty_part(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(PathError):
                resolve_under(tmp, "")
            with self.assertRaises(PathError):
                resolve_under(tmp)


if __name__ == "__main__":
    unittest.main()
