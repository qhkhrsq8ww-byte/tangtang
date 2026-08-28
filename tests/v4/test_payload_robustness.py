"""Duplicate / out-of-order / future / bad ts / huge / empty: process does not crash."""
from __future__ import annotations

import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.events.event import MAX_PAYLOAD_BYTES, Event
from core.events.event_bus import EventBus


class FrozenClock:
    def __init__(self, when: datetime) -> None:
        self.when = when

    def __call__(self) -> datetime:
        return self.when


NOW = datetime(2026, 8, 28, 12, 0, tzinfo=timezone.utc)


class TestPayloadRobustness(unittest.TestCase):
    def setUp(self):
        self.bus = EventBus(clock=FrozenClock(NOW))

    def test_duplicate_no_crash(self):
        ev = Event.create(id="evt_dup2", type="tick", ts=NOW.isoformat())
        a = self.bus.accept(ev)
        b = self.bus.accept(ev)
        self.assertTrue(a.ok)
        self.assertTrue(b.duplicate)
        self.assertFalse(b.ok)

    def test_out_of_order_processed(self):
        later = Event.create(id="evt_later", type="tick", ts="2026-08-28T13:00:00+00:00")
        earlier = Event.create(id="evt_earlier", type="tick", ts="2026-08-28T11:00:00+00:00")
        self.bus.accept(later)
        result = self.bus.accept(earlier)
        self.assertTrue(result.ok)
        self.assertTrue(result.out_of_order)

    def test_future_ts_no_crash(self):
        ev = Event.create(id="evt_future", type="tick", ts="2026-08-28T18:00:00+00:00")
        result = self.bus.accept(ev)
        self.assertTrue(result.ok)
        self.assertTrue(result.future_ts)

    def test_bad_ts_no_crash(self):
        ev = Event.create(id="evt_badts", type="tick", ts="not-a-timestamp")
        result = self.bus.accept(ev)
        self.assertTrue(result.accepted)
        self.assertTrue(result.ok or result.out_of_order)

    def test_huge_payload_no_crash(self):
        raw = {
            "id": "evt_huge",
            "type": "tick",
            "ts": NOW.isoformat(),
            "source": "mic",
            "privacy": "PUBLIC",
            "payload": {"text": "x" * (MAX_PAYLOAD_BYTES + 50)},
        }
        result = self.bus.accept(raw)
        self.assertFalse(result.accepted)
        self.assertFalse(result.ok)

    def test_empty_payload_ok(self):
        result = self.bus.accept(Event.create(id="evt_empty", type="tick", payload={}))
        self.assertTrue(result.ok)

    def test_empty_raw_no_crash(self):
        result = self.bus.accept(None)
        self.assertFalse(result.accepted)
        result2 = self.bus.accept({})
        self.assertFalse(result2.accepted)

    def test_process_still_runs_after_junk(self):
        self.bus.accept("not-json")
        self.bus.accept({"id": "x"})
        ok = self.bus.accept(Event.create(id="evt_after_junk", type="tick"))
        self.assertTrue(ok.ok)


if __name__ == "__main__":
    unittest.main()
