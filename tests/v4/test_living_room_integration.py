"""Living-room scenes → events → InterruptPolicy → Response. No dump-merge."""
from __future__ import annotations

import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.adapters.family_loader import load_members
from core.adapters.living_room_adapter import LivingRoomAdapter
from core.ingest import PrivacyPipeline
from core.policy.interrupt_policy import InterruptPolicy
from tangtang_runtime import TangTangRuntime

MEMBERS = load_members()


def _dt(hhmm: str) -> datetime:
    h, m = hhmm.split(":")
    return datetime(2026, 8, 28, int(h), int(m), tzinfo=timezone.utc)


class TestLivingRoomEventMap(unittest.TestCase):
    def test_chinese_kinds(self):
        a = LivingRoomAdapter()
        mapping = {
            "手机": "phone.usage",
            "久坐": "activity.sedentary",
            "吃饭": "meal.missed",
            "运动": "exercise.missing",
            "睡觉": "sleep.late",
            "回家": "family.arrived",
            "离家": "family.left",
        }
        for kind, expect in mapping.items():
            self.assertEqual(a.event_type_for(kind), expect, kind)
            ev = a.to_event(kind, member_id="dad")
            self.assertEqual(ev.type, expect)


class TestLivingRoomPolicy(unittest.TestCase):
    def test_phone_speak_then_log_only(self):
        spoken: list[str] = []
        from core.adapters.tts_adapter import TTSAdapter
        from core.ingest import PrivacyPipeline
        from core.policy.interrupt_policy import InterruptPolicy as IP

        policy = IP(clock=lambda: _dt("16:00"))
        rt = TangTangRuntime(
            members=MEMBERS,
            pipeline=PrivacyPipeline(members=MEMBERS, interrupt=policy),
            tts=TTSAdapter(speaker=spoken.append),
        )
        first = rt.handle_living_room("手机", member_id="child_9", observation={"phone_minutes": 43})
        second = rt.handle_living_room("phone", member_id="child_9", observation={"phone_minutes": 44})
        self.assertEqual(first.event.type, "phone.usage")
        self.assertEqual(first.decision, "SPEAK")
        self.assertTrue(first.event_id.startswith("evt_"))
        self.assertEqual(second.decision, "LOG_ONLY")
        self.assertTrue(spoken)
        self.assertNotIn("43", spoken[0])
        self.assertNotIn("我知道你已经玩手机", spoken[0])
        self.assertIn("走一走", spoken[0])
        print(
            f"EVIDENCE2 first_id={first.event_id} first_decision={first.decision} "
            f"second_id={second.event_id} second_decision={second.decision} tts={spoken[0]!r}"
        )

    def test_sleeping_silent(self):
        rt = TangTangRuntime(members=MEMBERS)
        result = rt.handle_living_room(
            "睡觉", member_id="child_9", observation={"sleeping": True}
        )
        self.assertEqual(result.event.type, "sleep.late")
        self.assertEqual(result.decision, "SILENT")
        self.assertEqual(result.action.text, "")

    def test_just_reminded_delay(self):
        rt = TangTangRuntime(members=MEMBERS)
        result = rt.handle_living_room(
            "吃饭", member_id="child_12", observation={"recently_interrupted": True}
        )
        self.assertEqual(result.event.type, "meal.missed")
        self.assertEqual(result.decision, "DELAY")

    def test_low_value_log_only(self):
        rt = TangTangRuntime(members=MEMBERS)
        result = rt.handle_living_room(
            "运动", member_id="dad", observation={"importance": "low"}
        )
        self.assertEqual(result.event.type, "exercise.missing")
        self.assertEqual(result.decision, "LOG_ONLY")

    def test_away_silent(self):
        rt = TangTangRuntime(members=MEMBERS)
        result = rt.handle_living_room("离家", member_id="grandpa")
        self.assertEqual(result.event.type, "family.left")
        self.assertEqual(result.decision, "SILENT")

    def test_does_not_speak_to_child_without_policy(self):
        src = (ROOT / "core" / "runtime" / "loop.py").read_text(encoding="utf-8")
        self.assertIn("interrupt.decide", src)
        self.assertIn("handle_living_room", src)


class TestLivingRoomEmptyUnknown(unittest.TestCase):
    def test_unknown_kind_still_event(self):
        ev = LivingRoomAdapter().to_event("unicorn", member_id="dad")
        self.assertTrue(ev.id)
        self.assertEqual(ev.member_id, "dad")

    def test_interrupt_sleeping_beats_phone(self):
        p = InterruptPolicy(clock=lambda: _dt("16:00"))
        self.assertEqual(
            p.decide({"scene": "phone", "sleeping": True, "member_id": "child_9"}),
            "SILENT",
        )


if __name__ == "__main__":
    unittest.main()
