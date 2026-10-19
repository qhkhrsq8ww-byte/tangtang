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


    def test_microphone_lock_uses_current_pid_for_acquire_and_release(self):
        source = (CAT / "cat-listen.sh").read_text(encoding="utf-8")
        self.assertIn('if [ "$lock_pid" = "$$" ]; then', source)
        self.assertIn('stale_dir="$LOCK_DIR.stale.$$"', source)
        self.assertIn('printf \'%s\\n\' "$$" > "$LOCK_DIR/pid"', source)

    def test_concurrent_recording_is_rejected_while_microphone_is_locked(self):
        with tempfile.TemporaryDirectory() as td:
            temp = Path(td)
            lock_dir = temp / "tangtang-mic-capture.lock"
            lock_dir.mkdir()
            (lock_dir / "pid").write_text(str(os.getpid()), encoding="utf-8")
            fake_ffmpeg = temp / "ffmpeg"
            fake_ffmpeg.write_text("#!/bin/sh\\nexit 0\\n", encoding="utf-8")
            fake_ffmpeg.chmod(0o755)
            env = dict(os.environ)
            env["PATH"] = td + os.pathsep + env.get("PATH", "")
            env["TMPDIR"] = td
            result = subprocess.run(
                ["bash", str(CAT / "cat-listen.sh"), "1", str(temp / "blocked.pcm")],
                env=env, capture_output=True, text=True, check=False,
            )
            self.assertEqual(result.returncode, 75, result.stderr)
            self.assertIn("另一个录音任务", result.stderr)
            self.assertFalse((temp / "blocked.pcm").exists())
    def test_reminder_does_not_continue_after_speech_output_is_skipped(self):
        source = (CAT / "cat-remind.sh").read_text(encoding="utf-8")
        self.assertIn('talk_status=$?', source)
        self.assertIn('糖糖语音输出失败或正在播放其它语音，本次提醒跳过', source)
        self.assertIn('exit "$talk_status"', source)
        status = source.index('if [ "$talk_status" -ne 0 ]; then')
        self.assertLess(status, source.index('# 上学闹铃：Glass 短铃', status))
    def test_tts_output_lock_rejects_overlapping_speech(self):
        with tempfile.TemporaryDirectory() as td:
            temp = Path(td)
            lock_dir = temp / "tangtang-tts-output.lock"
            lock_dir.mkdir()
            (lock_dir / "pid").write_text(str(os.getpid()), encoding="utf-8")
            env = dict(os.environ)
            env["TMPDIR"] = td
            script = 'source "$1"; tangtang_tts_lock; rc=$?; printf "status:%s\\n" "$rc"; exit 0'
            result = subprocess.run(
                ["bash", "-c", script, "test", str(CAT / "cat-lib.sh")],
                env=env, capture_output=True, text=True, check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("status:75", result.stdout)
            self.assertIn("避免重叠播放", result.stderr)

    def test_tts_output_lock_releases_after_owner_exits(self):
        with tempfile.TemporaryDirectory() as td:
            env = dict(os.environ)
            env["TMPDIR"] = td
            script = 'source "$1"; tangtang_tts_lock || exit $?; echo acquired'
            result = subprocess.run(
                ["bash", "-c", script, "test", str(CAT / "cat-lib.sh")],
                env=env, capture_output=True, text=True, check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("acquired", result.stdout)
            self.assertFalse((Path(td) / "tangtang-tts-output.lock").exists())

    def test_cat_talk_clears_stale_tts_audio_and_propagates_playback_failure(self):
        source = (CAT / "cat-talk.sh").read_text(encoding="utf-8")
        self.assertIn('rm -f /tmp/cat_tts.mp3', source)
        self.assertIn('&& [ -s /tmp/cat_tts.mp3 ]', source)
        self.assertIn('tangtang_play_audio /tmp/cat_tts.mp3\n    return $?', source)
        self.assertIn('esac\nexit $?\n', source)
        english = source.index('if [ "${1:-}" = "english" ]')
        english_exit = source.index('exit $?', english)
        lock = source.index('tangtang_tts_lock || exit $?')
        self.assertGreater(lock, english_exit)

    def test_startup_script_stops_when_stage_or_pet_startup_fails(self):
        source = (CAT / "start-cat.sh").read_text(encoding="utf-8")
        self.assertIn('if ! tangtang_ensure_stage; then', source)
        self.assertIn('if ! tangtang_ensure_pet; then', source)
        self.assertIn('糖糖舞台启动失败', source)
        self.assertIn('糖糖宠物页面启动失败', source)
        self.assertLess(source.index('if ! tangtang_ensure_stage'), source.index('if ! tangtang_ensure_pet'))
        self.assertLess(source.index('if ! tangtang_ensure_pet'), source.index('echo "🐾 糖糖全屏舞台已启动。'))

    def test_stage_server_checks_http_success_and_waits_for_readiness(self):
        source = (CAT / "cat-lib.sh").read_text(encoding="utf-8")
        self.assertIn('curl -fsS -o /dev/null --max-time 3 "$url"', source)
        self.assertIn('for attempt in 1 2 3 4 5 6 7 8 9 10; do', source)
        self.assertIn('tangtang_ensure_server || return $?', source)
        self.assertIn('糖糖本地页面服务启动失败', source)
        self.assertIn('tangtang_ensure_pet() {\n  tangtang_ensure_server || return $?', source)
    def test_aborted_recording_cleans_partial_pcm_and_releases_lock(self):
        source = (CAT / "cat-listen.sh").read_text(encoding="utf-8")
        self.assertIn('RECORDING_COMPLETE=0', source)
        self.assertIn('if [ "$LOCK_ACQUIRED" = "1" ] && [ "$RECORDING_COMPLETE" != "1" ]; then', source)
        self.assertIn('trap release_capture_lock EXIT', source)
        self.assertIn('RECORDING_COMPLETE=1', source)

    def test_voice_cli_installs_temp_audio_cleanup_after_successful_capture(self):
        source = (CAT / "cat-voice.sh").read_text(encoding="utf-8")
        self.assertIn('trap \'rm -f "$PCM"\' EXIT', source)
        self.assertLess(source.index('trap \'rm -f "$PCM"\' EXIT'), source.index('MEMBER_ID="unknown"'))

    def test_short_turn_retains_pcm_path_until_exit_cleanup(self):
        source = (CAT / "cat-turn.sh").read_text(encoding="utf-8")
        stt = source.index('stt_status=$?')
        decide = source.index('case "$TEXT" in', stt)
        self.assertNotIn('PCM=""', source[stt:decide])

    def test_recording_cli_propagates_ffmpeg_failure(self):
        with tempfile.TemporaryDirectory() as td:
            temp = Path(td)
            fake_ffmpeg = temp / "ffmpeg"
            fake_ffmpeg.write_text("#!/bin/sh\nexit 7\n", encoding="utf-8")
            fake_ffmpeg.chmod(0o755)
            output = temp / "capture.pcm"
            env = dict(os.environ)
            env["PATH"] = td + os.pathsep + env.get("PATH", "")
            env["TMPDIR"] = td
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
            self.assertFalse((temp / "tangtang-mic-capture.lock").exists())

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
