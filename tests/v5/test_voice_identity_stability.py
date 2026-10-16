"""V5.1 voice identity stability tests."""
import unittest
from core.adapters.voice_adapter import VoiceAdapter

class TestVoiceIdentityStability(unittest.TestCase):
    def test_low_confidence_single_frame_stays_unknown(self):
        a=VoiceAdapter(identify_fn=lambda _: ("child_9",0.60))
        x=a.observe("a.wav")
        self.assertIsNone(x.candidate_member)
    def test_repeated_low_confidence_frames_can_stabilize(self):
        a=VoiceAdapter(identify_fn=lambda _: ("child_9",0.60))
        a.observe("a.wav")
        x=a.observe("b.wav")
        self.assertEqual(x.candidate_member,"child_9")
    def test_high_confidence_is_immediate(self):
        a=VoiceAdapter(identify_fn=lambda _: ("child_9",0.90))
        x=a.observe("a.wav")
        self.assertEqual(x.candidate_member,"child_9")

if __name__=="__main__":
    unittest.main()
