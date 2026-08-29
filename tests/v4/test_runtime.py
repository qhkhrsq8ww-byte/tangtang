"""End-to-end runtime: observe → identify → event → brain → response → presentation."""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.adapters.event_store import JsonlEventStore
from core.adapters.family_loader import load_family_document, load_members
from core.adapters.tts_adapter import TTSAdapter
from tangtang_runtime import TangTangRuntime

MEMBERS = load_members()
BULLY = "我今天被同学欺负了。"
FAMILY = load_family_document()


class TestFamilyJsonNotOverwritten(unittest.TestCase):
    def test_sister_brother_display_names(self):
        names = {m["member_id"]: m.get("display_name") for m in FAMILY["members"]}
        self.assertEqual(names["qiaqia"], "洽洽")
        self.assertEqual(names["hanghang"], "航航")
        self.assertIn("grandpa", names)
        self.assertIn("dad", names)


class TestRuntimeOffline(unittest.TestCase):
    def test_offline_policy_animation_event_log(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = JsonlEventStore(home=tmp, persist=True)
            rt = TangTangRuntime(members=MEMBERS, events=store, offline=True)
            result = rt.handle_utterance("糖糖，我加班回来了。", {"label": "dad"})
            self.assertTrue(result.event_kept)
            self.assertEqual(result.decision, "SPEAK")
            self.assertTrue(result.action.text.startswith("汪汪～"))
            self.assertTrue(result.animation)
            self.assertTrue(store.contains(result.event_id))
            path = Path(tmp) / "events" / "events.jsonl"
            self.assertTrue(path.is_file())
            self.assertNotIn("/Users/lv/.qclaw/workspace/cat/", path.read_text(encoding="utf-8"))


class TestDuplicateEventNoDuplicateBehavior(unittest.TestCase):
    def test_same_event_id_does_not_speak_twice(self):
        spoken: list[str] = []
        from datetime import datetime, timezone
        from core.ingest import PrivacyPipeline
        from core.policy.interrupt_policy import InterruptPolicy

        day = datetime(2026, 8, 28, 16, 0, tzinfo=timezone.utc)
        rt = TangTangRuntime(
            members=MEMBERS,
            pipeline=PrivacyPipeline(members=MEMBERS, interrupt=InterruptPolicy(clock=lambda: day)),
            tts=TTSAdapter(speaker=spoken.append),
        )
        first = rt.handle_living_room(
            "手机",
            member_id="dad",
            event_id="evt_dup_phone_1",
        )
        second = rt.handle_living_room(
            "手机",
            member_id="dad",
            event_id="evt_dup_phone_1",
        )
        self.assertEqual(first.event_id, "evt_dup_phone_1")
        self.assertTrue(second.duplicate)
        self.assertEqual(second.decision, "LOG_ONLY")
        self.assertEqual(len(spoken), 1 if first.decision == "SPEAK" else 0)


class TestRuntimeFailuresLocal(unittest.TestCase):
    def test_stt_llm_tts_projection_do_not_raise(self):
        def stt_boom(_a):
            raise RuntimeError("stt")

        def llm_boom(_c):
            raise RuntimeError("llm")

        def tts_boom(_t):
            raise RuntimeError("tts")

        rt = TangTangRuntime(
            members=MEMBERS,
            stt=stt_boom,
            llm=llm_boom,
            tts=TTSAdapter(speaker=tts_boom),
        )
        result = rt.handle_voice(
            candidate_member="dad",
            utterance="糖糖，我加班回来了。",
            audio=b"x",
        )
        self.assertTrue(result.event_kept)
        self.assertEqual(result.member_id, "dad")
        self.assertEqual(result.action.text, "汪汪～")

    def test_unknown_stays_unknown(self):
        rt = TangTangRuntime(members=MEMBERS)
        result = rt.handle_voice(candidate_member="unknown", utterance="嗨")
        self.assertIsNone(result.member_id)
        self.assertNotIn(result.member_id, {"child_9", "hanghang", "child_12"})


class TestRuntimeEvidenceChains(unittest.TestCase):
    def test_child9_and_phone_evidence(self):
        spoken: list[str] = []
        from datetime import datetime, timezone
        from core.ingest import PrivacyPipeline
        from core.policy.interrupt_policy import InterruptPolicy

        day = datetime(2026, 8, 28, 16, 0, tzinfo=timezone.utc)
        rt = TangTangRuntime(
            members=MEMBERS,
            pipeline=PrivacyPipeline(members=MEMBERS, interrupt=InterruptPolicy(clock=lambda: day)),
            tts=TTSAdapter(speaker=spoken.append),
        )
        voice = rt.handle_voice(
            candidate_member="child_9",
            utterance=BULLY,
        )
        self.assertEqual(voice.member_id, "child_9")
        self.assertEqual(voice.privacy, "PRIVATE")
        self.assertTrue(voice.event_id.startswith("evt_"))
        self.assertTrue(voice.ingest.stored_private)
        self.assertFalse(rt.pipeline.stores.summary.contains_text(BULLY))
        dad_view = rt.pipeline.builder.build(
            who={"member_id": "dad"},
            event=voice.event,
            privacy_scope="FAMILY",
        )
        self.assertNotIn(BULLY, json.dumps(dad_view, ensure_ascii=False))
        self.assertFalse(rt.logger.contains_raw(BULLY))

        phone = rt.handle_living_room("手机", member_id="child_9")
        self.assertEqual(phone.event.type, "phone.usage")
        self.assertIn(phone.decision, {"SPEAK", "LOG_ONLY", "DELAY", "SILENT"})
        print(
            f"EVIDENCE_RUNTIME voice_id={voice.event_id} voice_privacy={voice.privacy} "
            f"phone_id={phone.event_id} phone_decision={phone.decision}"
        )


class TestV3NotDeleted(unittest.TestCase):
    def test_v3_modules_remain(self):
        self.assertTrue((ROOT / "code" / "cat" / "cat-vp.py").is_file())
        self.assertTrue((ROOT / "code" / "cat" / "cat-chat.py").is_file())


if __name__ == "__main__":
    unittest.main()
