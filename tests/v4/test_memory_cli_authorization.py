from __future__ import annotations

import os
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CAT = ROOT / "code" / "cat"


def _run_memory(*args, extra_env=None):
    env = os.environ.copy()
    env.pop("TANGTANG_ALLOW_LEGACY_MEMBER_MEMORY_CLI", None)
    env.pop("TANGTANG_ALLOW_LEGACY_FAMILY_MEMORY_READ_CLI", None)
    if extra_env:
        env.update(extra_env)
    with tempfile.TemporaryDirectory() as tmp:
        env["TANGTANG_DATA_DIR"] = tmp
        return subprocess.run(
            ["/usr/bin/python3", str(CAT / "cat-memory.py"), *args],
            capture_output=True,
            text=True,
            env=env,
            timeout=10,
        )


class TestMemoryCliViewerAuthorization(unittest.TestCase):
    def test_member_scoped_reads_fail_closed(self):
        for args in (("trends", "hanghang"), ("next", "hanghang")):
            with self.subTest(args=args):
                result = _run_memory(*args)
                self.assertEqual(result.returncode, 2)
                self.assertIn("viewer", result.stderr)

    def test_family_scoped_reads_fail_closed_before_engine_init(self):
        for command in ("today", "recent", "stable", "state", "emotion", "next"):
            with self.subTest(command=command):
                result = _run_memory(command)
                self.assertEqual(result.returncode, 2)
                self.assertIn("经过 Core 授权的 viewer", result.stderr)

    def test_legacy_switches_are_explicit_and_separate(self):
        family = _run_memory(
            "today",
            extra_env={"TANGTANG_ALLOW_LEGACY_FAMILY_MEMORY_READ_CLI": "1"},
        )
        self.assertNotEqual(family.returncode, 2)
        member = _run_memory(
            "trends", "hanghang",
            extra_env={"TANGTANG_ALLOW_LEGACY_MEMBER_MEMORY_CLI": "1"},
        )
        self.assertNotEqual(member.returncode, 2)


if __name__ == "__main__":
    unittest.main()
