"""Living-room presence: WiFi/ARP first, clip RMS second, voiceprint stub last."""
from __future__ import annotations

import importlib.util
import json
import math
import os
import struct
import sys
import tempfile
import unittest
import wave
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

CAT = ROOT / "code" / "cat"
ARP_GRANDPA = """
? (192.168.31.21) at 00:11:22:33:44:01 on en0 ifscope [ethernet]
router.local (192.168.31.1) at aa:aa:aa:aa:aa:aa on en0 ifscope [ethernet]
"""
ARP_HANGHANG = """
hanghang-iphone.local (192.168.31.25) at 00:11:22:33:44:05 on en0 ifscope [ethernet]
"""
ARP_QIAQIA = """
? (192.168.31.24) at 00:11:22:33:44:04 on en0 ifscope [ethernet]
"""
ARP_TWO_ADULTS = """
? (192.168.31.21) at 00:11:22:33:44:01 on en0 ifscope [ethernet]
dad-phone.local (192.168.31.23) at 00:11:22:33:44:03 on en0 ifscope [ethernet]
"""
ARP_INCOMPLETE = """
? (192.168.31.99) at (incomplete) on en0 ifscope
"""

EXAMPLE_DEVICES = {
    "devices": {
        "grandpa": {"mac": "00:11:22:33:44:01", "hostname": "grandpa-phone.local", "ip": "192.168.31.21"},
        "dad": {"mac": "00:11:22:33:44:03", "hostname": "dad-phone.local", "ip": "192.168.31.23"},
        "qiaqia": {"mac": "00:11:22:33:44:04", "hostname": "qiaqia-iphone.local", "ip": "192.168.31.24"},
        "hanghang": {"mac": "00:11:22:33:44:05", "hostname": "hanghang-iphone.local", "ip": "192.168.31.25"},
    }
}


def _load_mod(tmp: str):
    os.environ["TANGTANG_DATA_DIR"] = tmp
    os.environ.pop("TANGTANG_PRESENCE_CONFIG", None)
    os.environ.pop("TANGTANG_PRESENCE_ARP", None)
    os.environ.pop("TANGTANG_MEMBER_ID", None)
    os.environ.pop("TANGTANG_SPEAKER", None)
    os.environ.pop("TANGTANG_INTERACTIVE", None)
    os.environ.pop("CAT_CHILD_HOME", None)
    os.environ.pop("TANGTANG_CHILD_HOME", None)
    os.environ.pop("TANGTANG_FAKE_TODAY", None)
    os.environ.pop("TANGTANG_FAKE_TIME", None)
    os.environ["TANGTANG_SCHOOL_START"] = "2026-09-01"
    os.environ["TANGTANG_ALARM_DOW"] = "1-5"
    os.environ["TANGTANG_SCHOOL_LEAVE"] = "07:30"
    os.environ["TANGTANG_HOME_HANGHANG"] = "16:00"
    os.environ["TANGTANG_HOME_QIAQIA"] = "18:00"
    spec = importlib.util.spec_from_file_location(
        "tangtang_presence_test", CAT / "cat-presence.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _write_wav(path: Path, amp: int, seconds: float = 0.15, rate: int = 16000):
    n = int(rate * seconds)
    frames = bytearray()
    for i in range(n):
        sample = int(amp * math.sin(2 * math.pi * 440 * i / rate)) if amp else 0
        frames.extend(struct.pack("<h", max(-32767, min(32767, sample))))
    with wave.open(str(path), "w") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(bytes(frames))
    return path


class PresenceTestCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = self.tmp.name
        self.mod = _load_mod(self.root)
        self.cfg = EXAMPLE_DEVICES

    def tearDown(self):
        self.tmp.cleanup()

    def detect(self, arp="", clip=None, persist=True, **kw):
        return self.mod.detect_presence(
            arp_text=arp,
            clip_path=str(clip) if clip else None,
            config=self.cfg,
            allow_probe=False,
            persist=persist,
            **kw,
        )


class TestWifiArpIdentity(PresenceTestCase):
    def test_grandpa_phone_listed_in_fake_arp(self):
        os.environ["TANGTANG_FAKE_TODAY"] = "2026-09-02"
        os.environ["TANGTANG_FAKE_TIME"] = "15:00"
        hint = self.detect(ARP_GRANDPA)
        self.assertEqual(hint["source"], "wifi")
        self.assertEqual(hint["member_ids"], ["grandpa"])
        self.assertIn("grandpa", hint["present_on_wifi"])
        self.assertTrue(hint["interactable"])
        self.assertEqual(hint["interactable_ids"], ["grandpa"])
        self.assertGreater(hint["confidence"], 0.5)
        self.assertIn("wifi", hint["reason"])

    def test_incomplete_arp_ignored(self):
        hint = self.detect(ARP_INCOMPLETE)
        self.assertEqual(hint["member_ids"], [])
        self.assertEqual(hint["source"], "unknown")

    def test_multiple_phones_no_single_guess(self):
        os.environ["TANGTANG_FAKE_TODAY"] = "2026-09-02"
        os.environ["TANGTANG_FAKE_TIME"] = "20:00"
        hint = self.detect(ARP_TWO_ADULTS)
        self.assertEqual(set(hint["member_ids"]), {"grandpa", "dad"})
        self.assertEqual(hint["reason"].split("+")[0], "wifi_multiple")
        self.assertEqual(self.mod.suggest_member_id(explicit="", hint=hint), "unknown")


class TestSchoolHoursKids(PresenceTestCase):
    def test_kid_phone_school_hours_present_not_interactable(self):
        os.environ["TANGTANG_FAKE_TODAY"] = "2026-09-02"
        os.environ["TANGTANG_FAKE_TIME"] = "12:00"
        self.assertTrue(self.mod.is_school_day())
        self.assertTrue(self.mod.child_at_school("hanghang"))
        hint = self.detect(ARP_HANGHANG)
        self.assertEqual(hint["member_ids"], ["hanghang"])
        self.assertEqual(hint["present_on_wifi"], ["hanghang"])
        self.assertFalse(hint["interactable"])
        self.assertEqual(hint["interactable_ids"], [])
        self.assertEqual(self.mod.suggest_member_id(hint=hint), "unknown")

    def test_kid_phone_after_home_time_interactable(self):
        os.environ["TANGTANG_FAKE_TODAY"] = "2026-09-02"
        os.environ["TANGTANG_FAKE_TIME"] = "16:00"
        self.assertTrue(self.mod.is_school_day())
        self.assertFalse(self.mod.child_at_school("hanghang"))
        self.assertTrue(self.mod.child_at_school("qiaqia"))
        hint = self.detect(ARP_HANGHANG)
        self.assertEqual(hint["member_ids"], ["hanghang"])
        self.assertTrue(hint["interactable"])
        self.assertEqual(hint["interactable_ids"], ["hanghang"])
        # Still do not auto-talk to kids.
        self.assertEqual(self.mod.suggest_member_id(hint=hint), "unknown")

    def test_qiaqia_home_after_18(self):
        os.environ["TANGTANG_FAKE_TODAY"] = "2026-09-02"
        os.environ["TANGTANG_FAKE_TIME"] = "18:00"
        self.assertFalse(self.mod.child_at_school("qiaqia"))
        hint = self.detect(ARP_QIAQIA)
        self.assertEqual(hint["member_ids"], ["qiaqia"])
        self.assertTrue(hint["interactable"])


class TestMicEnergy(PresenceTestCase):
    def test_silence_vs_speech_wav(self):
        silent = _write_wav(Path(self.root) / "silent.wav", amp=0)
        speech = _write_wav(Path(self.root) / "speech.wav", amp=8000)
        quiet = self.mod.clip_energy(str(silent), threshold=300)
        loud = self.mod.clip_energy(str(speech), threshold=300)
        self.assertFalse(quiet["in_room_speech"])
        self.assertEqual(quiet["rms"], 0.0)
        self.assertTrue(loud["in_room_speech"])
        self.assertGreater(loud["rms"], 300)
        self.assertGreater(loud["peak"], 1000)

        hint_s = self.detect("", clip=silent)
        self.assertFalse(hint_s["in_room_speech"])
        self.assertEqual(hint_s["member_ids"], [])
        self.assertEqual(hint_s["source"], "unknown")

        hint_l = self.detect("", clip=speech)
        self.assertTrue(hint_l["in_room_speech"])
        self.assertEqual(hint_l["member_ids"], [])
        self.assertEqual(hint_l["source"], "mic_energy")
        self.assertFalse(hint_l["interactable"])
        self.assertEqual(hint_l["reason"], "mic_speech_unknown_who")


class TestExplicitMemberNotOverridden(PresenceTestCase):
    def test_suggest_keeps_cli_member(self):
        os.environ["TANGTANG_FAKE_TODAY"] = "2026-09-02"
        os.environ["TANGTANG_FAKE_TIME"] = "15:00"
        hint = self.detect(ARP_GRANDPA)
        self.assertEqual(hint["member_ids"], ["grandpa"])
        self.assertEqual(
            self.mod.suggest_member_id(explicit="dad", hint=hint),
            "dad",
        )
        self.assertEqual(
            self.mod.suggest_member_id(explicit="hanghang", hint=hint),
            "hanghang",
        )
        os.environ["TANGTANG_MEMBER_ID"] = "grandma"
        self.assertEqual(self.mod.suggest_member_id(hint=hint), "grandma")

    def test_unset_picks_single_interactable_adult(self):
        os.environ["TANGTANG_FAKE_TODAY"] = "2026-09-02"
        os.environ["TANGTANG_FAKE_TIME"] = "15:00"
        hint = self.detect(ARP_GRANDPA)
        self.assertEqual(self.mod.suggest_member_id(explicit="", hint=hint), "grandpa")
        self.assertEqual(self.mod.suggest_member_id(explicit="unknown", hint=hint), "grandpa")


class TestVoiceprintStub(PresenceTestCase):
    def test_stub_returns_unknown_and_writes_no_embeddings(self):
        speech = _write_wav(Path(self.root) / "clip.wav", amp=6000)
        before = set(Path(self.root).rglob("*"))
        result = self.mod.maybe_voiceprint(str(speech))
        self.assertEqual(result["member_id"], "unknown")
        self.assertEqual(result["confidence"], 0.0)
        self.assertFalse(result.get("enrolled"))
        after = set(Path(self.root).rglob("*"))
        self.assertEqual(after, before)
        self.assertFalse((Path(self.root) / "cat-voiceprints.json").exists())
        hint = self.detect("", clip=speech, persist=False)
        self.assertEqual(hint["voiceprint"], "unknown")
        self.assertNotEqual(hint["source"], "voiceprint_optional")


class TestChildAudioNotPersisted(PresenceTestCase):
    def test_child_clip_not_copied_and_no_embedding(self):
        os.environ["TANGTANG_FAKE_TODAY"] = "2026-09-02"
        os.environ["TANGTANG_FAKE_TIME"] = "16:10"
        child_wav = _write_wav(Path(self.root) / "incoming-child.wav", amp=7000)
        hint = self.detect(ARP_HANGHANG, clip=child_wav, persist=True)
        self.assertEqual(hint["member_ids"], ["hanghang"])
        self.assertEqual(hint["voiceprint"], "unknown")

        data = Path(self.root)
        persisted_audio = [
            p for p in data.rglob("*")
            if p.suffix.lower() in {".wav", ".pcm", ".raw"} and p.resolve() != child_wav.resolve()
        ]
        self.assertEqual(persisted_audio, [])
        self.assertFalse((data / "cat-voiceprints.json").exists())
        log = json.loads((data / "cat-presence.json").read_text(encoding="utf-8"))
        blob = json.dumps(log, ensure_ascii=False)
        self.assertNotIn("incoming-child.wav", blob)
        self.assertNotIn("embedding", blob)
        self.assertNotIn("voiceprint_ref", blob)
        last = log.get("last") or {}
        self.assertNotIn("clip", last)
        self.assertNotIn("path", last)
        self.assertNotIn("wav", last)


class TestQuietHoursCompose(PresenceTestCase):
    def test_quiet_hours_make_adult_not_interactable(self):
        os.environ["TANGTANG_FAKE_TODAY"] = "2026-09-02"
        os.environ["TANGTANG_FAKE_TIME"] = "23:00"
        hint = self.detect(ARP_GRANDPA)
        self.assertEqual(hint["present_on_wifi"], ["grandpa"])
        self.assertFalse(hint["interactable"])
        self.assertEqual(self.mod.suggest_member_id(hint=hint), "unknown")


class TestNoNewMicDaemon(unittest.TestCase):
    def test_presence_module_does_not_open_mic(self):
        src = (CAT / "cat-presence.py").read_text(encoding="utf-8")
        self.assertNotIn("avfoundation", src)
        self.assertNotIn("cat-listen", src)
        self.assertNotIn("while True", src)
        self.assertIn("already-captured", src)


if __name__ == "__main__":
    unittest.main()
