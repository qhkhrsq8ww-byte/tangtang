"""In-memory EventBus: clock, isolation, duplicates, unknown types."""
from __future__ import annotations

import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.errors import EventError
from core.events.event import Event
from core.events.event_bus import EventBus, PublishResult
from core.interfaces import EventBusPort


class FrozenClock:
    def __init__(self, when: datetime) -> None:
        self.when = when
        self.calls = 0

    def __call__(self) -> datetime:
        self.calls += 1
        return self.when


class TestEventBusHappy(unittest.TestCase):
    def test_subscribe_and_publish(self):
        seen = []
        bus = EventBus()
        self.assertIsInstance(bus, EventBusPort)
        bus.subscribe("greet", seen.append)
        ev = Event.create(id="evt_ok", type="greet")
        result = bus.publish(ev)
        self.assertIsInstance(result, PublishResult)
        self.assertTrue(result.ok)
        self.assertFalse(result.duplicate)
        self.assertEqual(seen, [ev])

    def test_wildcard_and_typed(self):
        order = []
        bus = EventBus()
        bus.subscribe("greet", lambda e: order.append("typed"))
        bus.subscribe("*", lambda e: order.append("star"))
        bus.publish(Event.create(id="evt_w", type="greet"))
        self.assertEqual(order, ["typed", "star"])


class TestEventBusEmpty(unittest.TestCase):
    def test_unknown_type_no_handlers(self):
        bus = EventBus()
        result = bus.publish(Event.create(id="evt_u", type="unknown_scene"))
        self.assertTrue(result.ok)
        self.assertEqual(result.results, [])
        self.assertEqual(result.errors, [])

    def test_empty_subscribe_type_illegal(self):
        bus = EventBus()
        with self.assertRaises(EventError):
            bus.subscribe("", lambda e: None)


class TestEventBusIllegalAndDuplicate(unittest.TestCase):
    def test_non_event_rejected(self):
        bus = EventBus()
        with self.assertRaises(EventError):
            bus.publish({"id": "evt_1", "type": "greet"})  # type: ignore[arg-type]

    def test_duplicate_event_id_not_redelivered(self):
        calls = []
        bus = EventBus()
        bus.subscribe("greet", lambda e: calls.append(e.id))
        ev = Event.create(id="evt_dup", type="greet")
        first = bus.publish(ev)
        second = bus.publish(ev)
        self.assertTrue(first.ok)
        self.assertFalse(second.ok)
        self.assertTrue(second.duplicate)
        self.assertEqual(calls, ["evt_dup"])
        self.assertIn("duplicate", second.errors[0])


class TestEventBusHandlerException(unittest.TestCase):
    def test_handler_exception_does_not_crash_and_continues(self):
        sink = []

        def boom(_event):
            raise RuntimeError("handler exploded")

        later = []
        bus = EventBus(error_sink=lambda msg, exc: sink.append((msg, type(exc).__name__)))
        bus.subscribe("wake", boom)
        bus.subscribe("wake", later.append)
        ev = Event.create(id="evt_boom", type="wake", privacy="PRIVATE", member_id="child_9",
                          payload={"speech": "secret-child-words"})
        result = bus.publish(ev)
        self.assertFalse(result.ok)
        self.assertEqual(later, [ev])
        self.assertTrue(any("RuntimeError" in e for e in result.errors))
        self.assertEqual(len(sink), 1)
        self.assertIn("evt_boom", sink[0][0])
        self.assertNotIn("secret-child-words", sink[0][0])

    def test_process_survives(self):
        bus = EventBus(error_sink=lambda *_: None)
        bus.subscribe("*", lambda _e: (_ for _ in ()).throw(ValueError("x")))
        bus.publish(Event.create(id="evt_alive", type="tick"))
        bus.publish(Event.create(id="evt_alive2", type="tick"))


class TestEventBusClockNoIO(unittest.TestCase):
    def test_injected_clock(self):
        when = datetime(2026, 8, 28, 12, 0, tzinfo=timezone.utc)
        clock = FrozenClock(when)
        bus = EventBus(clock=clock)
        result = bus.publish(Event.create(id="evt_clk", type="tick"))
        self.assertEqual(result.received_at, when.isoformat())
        self.assertGreaterEqual(clock.calls, 1)

    def test_bus_source_has_no_file_io(self):
        from core.events import event_bus as mod
        src = Path(mod.__file__).read_text(encoding="utf-8")
        self.assertNotIn("open(", src)
        self.assertNotIn("Path(", src)


if __name__ == "__main__":
    unittest.main()
