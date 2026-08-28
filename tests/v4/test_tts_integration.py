"""TTS adapter: Core never calls a vendor. Failures keep the Event."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.adapters.family_loader import load_members
from core.adapters.tts_adapter import TTSAdapter
from core.events.event import Event
from core.persona.copy import CopyGuard, WALK_SUGGESTION
from core.response.orchestrator import PresentationAction
from tangtang_runtime import TangTangRuntime

MEMBERS = load_members()
TTS_SRC = (ROOT / "core" / "adapters" / "tts_adapter.py").read_text(encoding="utf-8")
LOOP_SRC = (ROOT / "core" / "runtime" / "loop.py").read_text(encoding="utf-8")


class TestTtsNoVendorInCore(unittest.TestCase):
    def test_adapter_has_no_vendor_call(self):
        self.assertNotIn("baidu", TTS_SRC.lower())
        self.assertNotIn("edge_tts", TTS_SRC)
        self.assertNotIn("say ", TTS_SRC)
        self.assertNotIn("os.system", TTS_SRC)
        self.assertNotIn("baidu", LOOP_SRC.lower())

    def test_fail_keeps_event(self):
        ev = Event.create(id="evt_tts_keep", type="utterance", privacy="PRIVATE", member_id="child_9")
        action = PresentationAction(
            decision="SPEAK", text="汪汪～", action="reply", member_id="child_9", sink="voice"
        )

        def boom(_text):
            raise RuntimeError("speaker down")

        delivered = TTSAdapter(speaker=boom).deliver(ev, action)
        self.assertTrue(delivered.event_kept)
        self.assertEqual(delivered.event_id, "evt_tts_keep")
        self.assertFalse(delivered.tts_ok)
        self.assertIn("tts:", delivered.errors[0])

    def test_runtime_tts_fail_keeps_event(self):
        def boom(_text):
            raise OSError("offline speaker")

        rt = TangTangRuntime(members=MEMBERS, tts=TTSAdapter(speaker=boom))
        result = rt.handle_utterance("糖糖，我加班回来了。", {"label": "dad"})
        self.assertTrue(result.event_kept)
        self.assertTrue(result.event_id)
        self.assertFalse(result.delivery.tts_ok)
        self.assertEqual(result.decision, "SPEAK")

    def test_offline_unwired_speaker_still_keeps_event(self):
        rt = TangTangRuntime(members=MEMBERS, offline=True)
        result = rt.handle_utterance("糖糖陪奶奶说说话。", {"label": "grandma"})
        self.assertTrue(result.event_kept)
        self.assertEqual(result.decision, "SPEAK")
        self.assertTrue(result.delivery.tts_ok)

    def test_surveillance_copy_rewritten(self):
        line = "我知道你已经玩手机43分钟了。"
        out = CopyGuard().sanitize(line, member_id="child_9", role="play")
        self.assertEqual(out, WALK_SUGGESTION)
        self.assertNotIn("43", out)


if __name__ == "__main__":
    unittest.main()
