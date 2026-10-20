"""Regression checks for the production shell voice-chat entrypoint."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]
ENTRY = ROOT / "code" / "cat" / "cat-voice-chat.sh"
IMPL = ROOT / "code" / "cat" / "cat-voice.sh"


class TestVoiceChatEntrypoint(unittest.TestCase):
    def test_entrypoint_delegates_to_voice_conversation_implementation(self):
        source = ENTRY.read_text(encoding="utf-8")
        self.assertIn('VOICE_IMPL="$SCRIPT_DIR/cat-voice.sh"', source)
        self.assertIn('exec "$VOICE_IMPL" "$DUR"', source)
        self.assertNotIn('cat-brain.py', source)
        self.assertNotIn('cat-tts-edge.py', source)

    def test_voice_conversation_implementation_exists(self):
        self.assertTrue(IMPL.is_file())
        self.assertTrue(IMPL.stat().st_mode & 0o111)


if __name__ == "__main__":
    unittest.main()
