"""Regression checks for the daily wake-music schedule."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]
CAT = ROOT / "code" / "cat"


class WakeMusicScheduleTests(unittest.TestCase):
    def test_daily_music_is_scheduled_at_0640(self):
        lines = (CAT / "tangtang-schedule.conf").read_text(encoding="utf-8").splitlines()
        self.assertIn("40 6 wake_music", [line.strip() for line in lines if line.strip() and not line.lstrip().startswith("#")])

    def test_crontab_runs_direct_music_script_not_tts(self):
        script = (CAT / "cat-schedule.sh").read_text(encoding="utf-8")
        self.assertIn('if [ "$TANGTANG_SCHED_EVENT" = "wake_music" ]; then', script)
        self.assertIn('echo "$TANGTANG_SCHED_MIN $TANGTANG_SCHED_HOUR * * $dow $CAT_DIR/wake-music.sh"', script)

    def test_playback_logs_result_and_uses_mac_default_output(self):
        script = (CAT / "wake-music.sh").read_text(encoding="utf-8")
        self.assertIn('command -v afplay', script)
        self.assertIn('wake-music.log', script)
        self.assertIn('tangtang_play_audio "$MUSIC" 210', script)
        self.assertIn('macOS 当前音频输出设置决定', script)


if __name__ == "__main__":
    unittest.main()
