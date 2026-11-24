from __future__ import annotations

import os
import subprocess
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
CAT = ROOT / "code" / "cat"


def _run_memory(*args):
    env = os.environ.copy()
    env.pop("TANGTANG_ALLOW_LEGACY_MEMBER_MEMORY_CLI", None)
    with tempfile.TemporaryDirectory() as tmp:
        env["TANGTANG_DATA_DIR"] = tmp
        return subprocess.run(
            ["/usr/bin/python3", str(CAT / "cat-memory.py"), *args],
            capture_output=True,
            text=True,
            env=env,
            timeout=10,
        )


def test_member_trends_cli_requires_core_verified_viewer():
    result = _run_memory("trends", "hanghang")
    assert result.returncode == 2
    assert "没有经过 Core 验证的 viewer 身份" in result.stderr


def test_member_targeted_next_cli_requires_core_verified_viewer():
    result = _run_memory("next", "hanghang")
    assert result.returncode == 2
    assert "不能代替已验证的 viewer 身份" in result.stderr


import unittest


class TestFamilyMemoryViewerAuthorization(unittest.TestCase):
    def test_family_memory_read_commands_fail_closed_before_engine_init(self):
        for command in ("today", "recent", "stable", "state", "emotion", "next"):
            with self.subTest(command=command):
                result = _run_memory(command)
                self.assertEqual(result.returncode, 2)
                self.assertIn("经过 Core 授权的 viewer", result.stderr)

    def test_explicit_legacy_read_switch_is_only_a_migration_escape_hatch(self):
        env = os.environ.copy()
        env["TANGTANG_ALLOW_LEGACY_FAMILY_MEMORY_READ_CLI"] = "1"
        with tempfile.TemporaryDirectory() as tmp:
            env["TANGTANG_DATA_DIR"] = tmp
            result = subprocess.run(
                ["/usr/bin/python3", str(CAT / "cat-memory.py"), "today"],
                capture_output=True, text=True, env=env, timeout=10,
            )
        # The flag preserves the legacy command for migration; it is not an
        # authenticated Viewer grant.
        self.assertNotEqual(result.returncode, 2)
