"""Voice adapter: voiceprint wrap → Observation → Identity. unknown stays unknown."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.adapters.family_loader import load_members
from core.adapters.observation import VOICE_OBSERVED, is_unknown_candidate
from core.adapters.voice_adapter import VoiceAdapter
from core.identity.resolver import IdentityResolver
from tangtang_runtime import TangTangRuntime

MEMBERS = load_members()
BULLY = "我今天被同学欺负了。"


class TestVoiceObservation(unittest.TestCase):
    def test_candidate_maps_through_identity(self):
        adapter = VoiceAdapter(identify_fn=lambda _p: "hanghang")
        obs = adapter.observe("fake.pcm")
        self.assertEqual(obs.type, VOICE_OBSERVED)
        self.assertEqual(obs.candidate_member, "hanghang")
        member = IdentityResolver(MEMBERS).resolve(obs.to_mapping())
        self.assertEqual(member, "hanghang")

    def test_qiaqia_dad_grandpa(self):
        ident = IdentityResolver(MEMBERS)
        for cand, expect in (
            ("qiaqia", "qiaqia"),
            ("dad", "dad"),
            ("grandpa", "grandpa"),
        ):
            obs = VoiceAdapter().observe(candidate_member=cand, confidence=0.9)
            self.assertEqual(ident.resolve(obs.to_mapping()), expect, cand)

    def test_unknown_never_defaults_to_child(self):
        adapter = VoiceAdapter(identify_fn=lambda _p: "unknown")
        obs = adapter.observe("x.pcm")
        self.assertIsNone(obs.candidate_member)
        self.assertEqual(obs.confidence, 0.0)
        ident = IdentityResolver(MEMBERS)
        self.assertIsNone(ident.resolve(obs.to_mapping()))
        self.assertIsNone(ident.resolve({"candidate_member": "unknown"}))
        self.assertTrue(is_unknown_candidate("访客"))

    def test_identify_failure_is_unknown(self):
        def boom(_p):
            raise RuntimeError("mic")

        obs = VoiceAdapter(identify_fn=boom).observe("x.pcm")
        self.assertIsNone(obs.candidate_member)
        self.assertNotEqual(obs.candidate_member, "child_9")
        self.assertNotEqual(obs.candidate_member, "hanghang")


class TestVoiceFullChainChild9(unittest.TestCase):
    def test_child9_voice_to_private_memory_context_response_tts(self):
        spoken: list[str] = []
        rt = TangTangRuntime(
            members=MEMBERS,
            tts=__import__("core.adapters.tts_adapter", fromlist=["TTSAdapter"]).TTSAdapter(
                speaker=spoken.append
            ),
        )
        result = rt.handle_voice(
            candidate_member="hanghang",
            confidence=0.99,
            utterance=BULLY,
        )
        self.assertEqual(result.member_id, "hanghang")
        self.assertEqual(result.privacy, "PRIVATE")
        self.assertTrue(result.event_id)
        self.assertTrue(str(result.event_id).startswith("evt_"))
        self.assertTrue(result.event_kept)
        self.assertTrue(result.ingest and result.ingest.stored_private)
        self.assertFalse(result.ingest.stored_family)
        self.assertFalse(result.ingest.stored_summary)
        self.assertIsNotNone(result.private_memory_id)
        blob = str(result.context)
        # Owner context may hold the utterance; family snapshot must not.
        family = result.context.get("family") or {}
        self.assertNotIn(BULLY, str(family))
        self.assertFalse(rt.pipeline.stores.summary.contains_text(BULLY))
        self.assertFalse(rt.pipeline.stores.family.contains_text(BULLY))
        self.assertFalse(rt.logger.contains_raw(BULLY))
        self.assertEqual(result.decision, "SPEAK")
        self.assertTrue(spoken)
        self.assertNotIn(BULLY, "\n".join(rt.logger.lines))
        # Evidence for the integration report:
        print(
            f"EVIDENCE1 event_id={result.event_id} member={result.member_id} "
            f"privacy={result.privacy} memory={result.private_memory_id} "
            f"decision={result.decision} tts={spoken[-1]!r}"
        )


class TestVoiceSttFailure(unittest.TestCase):
    def test_stt_fail_does_not_kill_process(self):
        def boom(_audio):
            raise ConnectionError("stt down")

        rt = TangTangRuntime(members=MEMBERS, stt=boom)
        result = rt.handle_voice(
            candidate_member="dad",
            audio=b"x",
        )
        self.assertTrue(result.event_kept)
        self.assertTrue(result.event_id)
        self.assertTrue(any("stt:" in e for e in result.errors) or result.event is not None)


class TestVoiceEmptyUnknown(unittest.TestCase):
    def test_empty_pcm_unknown(self):
        obs = VoiceAdapter().observe(candidate_member="")
        self.assertIsNone(obs.candidate_member)

    def test_unknown_runtime_member_none(self):
        rt = TangTangRuntime(members=MEMBERS)
        result = rt.handle_voice(candidate_member="unknown", utterance="你好糖糖")
        self.assertIsNone(result.member_id)
        self.assertNotEqual(result.member_id, "child_9")
        self.assertNotEqual(result.member_id, "hanghang")


if __name__ == "__main__":
    unittest.main()
