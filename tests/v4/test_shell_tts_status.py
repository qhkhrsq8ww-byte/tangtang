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
        for path in (CAT / "cat-lib.sh", CAT / "cat-listen.sh", CAT / "cat-say.sh", CAT / "cat-task-dispatch.py"):
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


    def test_concurrent_recording_is_rejected_while_microphone_is_locked(self):
        with tempfile.TemporaryDirectory() as td:
            temp = Path(td)
            fake_ffmpeg = temp / "ffmpeg"
            fake_ffmpeg.write_text("#!/bin/sh\\nsleep 2\\nexit 0\\n", encoding="utf-8")
            fake_ffmpeg.chmod(0o755)
            env = dict(os.environ)
            env["PATH"] = td + os.pathsep + env.get("PATH", "")
            env["TMPDIR"] = td
            first_output = temp / "first.pcm"
            second_output = temp / "second.pcm"
            first = subprocess.Popen(
                ["bash", str(CAT / "cat-listen.sh"), "1", str(first_output)],
                env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
            )
            try:
                lock_dir = temp / "tangtang-mic-capture.lock"
                for _ in range(30):
                    if (lock_dir / "pid").is_file():
                        break
                    import time
                    time.sleep(0.05)
                self.assertTrue((lock_dir / "pid").is_file(), "first recorder did not acquire lock")
                second = subprocess.run(
                    ["bash", str(CAT / "cat-listen.sh"), "1", str(second_output)],
                    env=env, capture_output=True, text=True, check=False,
                )
                self.assertEqual(second.returncode, 75, second.stderr)
                self.assertIn("另一个录音任务", second.stderr)
            finally:
                first.communicate(timeout=5)
            self.assertFalse((temp / "tangtang-mic-capture.lock").exists())

    def test_recording_cli_propagates_ffmpeg_failure(self):
        with tempfile.TemporaryDirectory() as td:
            temp = Path(td)
            fake_ffmpeg = temp / "ffmpeg"
            fake_ffmpeg.write_text("#!/bin/sh\nexit 7\n", encoding="utf-8")
            fake_ffmpeg.chmod(0o755)
            output = temp / "capture.pcm"
            env = dict(os.environ)
            env["PATH"] = td + os.pathsep + env.get("PATH", "")
            result = subprocess.run(
                ["bash", str(CAT / "cat-listen.sh"), "1", str(output)],
                env=env,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(result.returncode, 7, result.stderr)
            self.assertIn("录音程序失败", result.stderr)
            self.assertFalse(output.exists())

    def test_recording_cli_rejects_success_without_audio_file(self):
        with tempfile.TemporaryDirectory() as td:
            temp = Path(td)
            fake_ffmpeg = temp / "ffmpeg"
            fake_ffmpeg.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
            fake_ffmpeg.chmod(0o755)
            output = temp / "capture.pcm"
            env = dict(os.environ)
            env["PATH"] = td + os.pathsep + env.get("PATH", "")
            result = subprocess.run(
                ["bash", str(CAT / "cat-listen.sh"), "1", str(output)],
                env=env,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(result.returncode, 1, result.stderr)
            self.assertIn("没有生成有效录音文件", result.stderr)

    def test_launch_agent_one_shot_launcher_does_not_keep_restarting(self):
        import plistlib

        plist_path = ROOT / "config" / "com.tangtang.daemon.plist.example"
        with plist_path.open("rb") as handle:
            config = plistlib.load(handle)
        self.assertTrue(config["RunAtLoad"])
        self.assertFalse(config["KeepAlive"])

    def test_short_turn_stt_pipeline_failure_is_not_reported_as_success(self):
        source = (CAT / "cat-turn.sh").read_text(encoding="utf-8")
        self.assertIn('set -o pipefail; "$CAT_DIR/cat-stt-baidu.sh"', source)
        self.assertIn('stt_status=$?', source)
        self.assertIn('STT_STATUS="fail"', source)
        self.assertIn('STT_STATUS="ok"', source)
        self.assertLess(
            source.index('stt_status=$?'),
            source.index('if [ "$stt_status" -ne 0 ]'),
        )

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
                'rc=$?; printf "status:%s\n" "$rc"; exit 0'
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



    def test_voice_cli_preserves_tts_failure_status_on_both_reply_paths(self):
        source = (CAT / "cat-voice.sh").read_text(encoding="utf-8")
        self.assertEqual(source.count('say_status=$?'), 2)
        self.assertIn('闹铃回复语音播放失败', source)
        self.assertIn('糖糖回复语音播放失败', source)
        self.assertIn('exit "$say_status"', source)
        self.assertLess(
            source.index('say_status=$?', source.index('ALARM_LINE=') ),
            source.index('rm -f "$PCM"', source.index('ALARM_LINE=') ),
        )



    def test_voice_cli_does_not_mask_stt_or_chat_pipeline_failures(self):
        source = (CAT / "cat-voice.sh").read_text(encoding="utf-8")
        self.assertIn("set -u -o pipefail", source)
        self.assertIn('stt_status=$?', source)
        self.assertIn('chat_status=$?', source)
        self.assertIn('语音识别进程失败', source)
        self.assertIn('糖糖对话进程失败', source)
        self.assertIn('exit "$stt_status"', source)
        self.assertIn('exit "$chat_status"', source)
        self.assertLess(
            source.index('stt_status=$?'),
            source.index('if [ -z "$TEXT" ]'),
        )
        self.assertLess(
            source.index('chat_status=$?'),
            source.index('if [ -z "$REPLY" ]'),
        )


if __name__ == "__main__":
    unittest.main()
