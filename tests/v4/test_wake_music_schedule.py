"""Regression checks for the daily wake-music and gentle voice routine."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]
CAT = ROOT / "code" / "cat"


class WakeMusicScheduleTests(unittest.TestCase):
    def test_daily_music_is_scheduled_at_0640(self):
        lines = (CAT / "tangtang-schedule.conf").read_text(encoding="utf-8").splitlines()
        self.assertIn("40 6 wake_music", [line.strip() for line in lines if line.strip() and not line.lstrip().startswith("#")])

    def test_crontab_runs_direct_music_script_not_tts_reminder(self):
        script = (CAT / "cat-schedule.sh").read_text(encoding="utf-8")
        self.assertIn('if [ "$TANGTANG_SCHED_EVENT" = "wake_music" ]; then', script)
        self.assertIn('echo "$TANGTANG_SCHED_MIN $TANGTANG_SCHED_HOUR * * $dow $CAT_DIR/wake-music.sh"', script)

    def test_wakeup_uses_existing_music_and_gentle_voice(self):
        script = (CAT / "wake-music.sh").read_text(encoding="utf-8")
        self.assertIn('MUSIC="$CAT_DIR/assets/wake_music_3min.mp3"', script)
        self.assertIn('VOICE_SCRIPT="$CAT_DIR/cat-say.sh"', script)
        self.assertIn('"$VOICE_SCRIPT" "$GREETING" soft', script)
        self.assertIn("早上好呀，我是糖糖。新的一天开始啦", script)
        self.assertIn('tangtang_play_audio "$MUSIC" 210', script)
        self.assertIn("语音失败不阻断音乐", script)
        self.assertIn("macOS 当前音频输出设置决定", script)


if __name__ == "__main__":
    unittest.main()
