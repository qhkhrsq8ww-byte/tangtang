"""Regression tests for shell TTS syntax and audio failure propagation."""
from __future__ import annotations

import os
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CAT = ROOT / "code" / "cat"


class TestShellTtsStatus(unittest.TestCase):
    def test_speech_scripts_have_valid_bash_syntax(self):
        for path in (CAT / "cat-lib.sh", CAT / "cat-say.sh", CAT / "cat-task-dispatch.py"):
            # cat-task-dispatch.py is Python, validated by Python/CI instead.
            if path.suffix == ".py":
                continue
            with self.subTest(path=path.name):
                result = subprocess.run(
                    ["bash", "-n", str(path)],
                    capture_output=True,
                    text=True,
                    check=False,
                )
                self.assertEqual(result.returncode, 0, result.stderr)

    def test_audio_player_nonzero_exit_is_propagated(self):
        with tempfile.TemporaryDirectory() as td:
            temp = Path(td)
            fake_player = temp / "afplay"
            fake_player.write_text("#!/bin/sh\nexit 7\n", encoding="utf-8")
            fake_player.chmod(0o755)
            audio = temp / "dummy.wav"
            audio.write_bytes(b"fake")
            env = dict(os.environ)
            env["PATH"] = td + os.pathsep + env.get("PATH", "")
            script = (
                'source "$1"; '
                'tangtang_play_audio "$2" 3; '
                'rc=$?; printf "status:%s\\n" "$rc"; exit 0'
            )
            result = subprocess.run(
                ["bash", "-c", script, "test", str(CAT / "cat-lib.sh"), str(audio)],
                env=env,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("status:7", result.stdout)


if __name__ == "__main__":
    unittest.main()
