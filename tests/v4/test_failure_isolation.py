"""Failure isolation: network/TTS/STT/projection/LLM/handler/memory/context."""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.events.event import Event
from core.events.event_bus import EventBus
from core.ingest import PrivacyPipeline
from core.response.orchestrator import PresentationAction, ResponseOrchestrator
from core.runtime.checkpoint import FileSeenStore
from core.runtime.isolate import isolate
from core.runtime.presentation import PresentationRuntime
from core.context.builder import ContextBuilder
from core.policy.interrupt_policy import InterruptPolicy


def _boom(*_a, **_k):
    raise RuntimeError("sink down")


class TestIsolateHelper(unittest.TestCase):
    def test_isolate_returns_fallback(self):
        result = isolate(lambda: (_ for _ in ()).throw(RuntimeError("x")), fallback="汪汪～")
        self.assertFalse(result.ok)
        self.assertEqual(result.value, "汪汪～")
        self.assertEqual(result.error_type, "RuntimeError")


class TestTtsFailKeepsEvent(unittest.TestCase):
    def test_tts_exception_does_not_drop_event(self):
        ev = Event.create(id="evt_tts", type="utterance", privacy="PRIVATE", member_id="child_9")
        action = PresentationAction(
            decision="SPEAK", text="汪汪～", action="greet", member_id="child_9", sink="voice"
        )
        runtime = PresentationRuntime(tts=_boom)
        delivered = runtime.deliver(ev, action)
        self.assertTrue(delivered.event_kept)
        self.assertEqual(delivered.event_id, "evt_tts")
        self.assertFalse(delivered.tts_ok)
        self.assertIn("tts:", delivered.errors[0])

    def test_stt_projection_network_isolated(self):
        ev = Event.create(id="evt_sinks", type="tick")
        runtime = PresentationRuntime(stt=_boom, projection=_boom, network=_boom)
        action = PresentationAction(
            decision="SPEAK", text="hi", action="show", member_id="dad", sink="projection"
        )
        delivered = runtime.deliver(ev, action, audio=b"x")
        self.assertTrue(delivered.event_kept)
        self.assertFalse(delivered.stt_ok)
        self.assertFalse(delivered.projection_ok)
        self.assertFalse(delivered.network_ok)

    def test_llm_fail_falls_back_to_wangwang(self):
        orch = ResponseOrchestrator(responder=lambda ctx: (_ for _ in ()).throw(ConnectionError("llm")))
        action = orch.run(decision="SPEAK", context={"who": {"member_id": "mom"}})
        self.assertEqual(action.text, "汪汪～")
        self.assertEqual(action.decision, "SPEAK")


class TestMemoryContextHandlerFail(unittest.TestCase):
    def test_memory_put_fail_keeps_event(self):
        class BoomPrivate:
            def put(self, **kwargs):
                raise OSError("disk full")

        pipe = PrivacyPipeline()
        pipe.stores.private = BoomPrivate()  # type: ignore[assignment]
        result = pipe.ingest("我今天被同学欺负了。", {"label": "弟弟"})
        self.assertEqual(result.event.privacy, "PRIVATE")
        self.assertTrue(result.event.id)
        self.assertFalse(result.stored_private)

    def test_context_memory_query_fail_empty(self):
        class BoomMem:
            def query(self, **kwargs):
                raise RuntimeError("sqlite locked")

        builder = ContextBuilder(BoomMem(), InterruptPolicy())
        ev = Event.create(type="tick")
        ctx = builder.build(who={"member_id": "dad"}, event=ev)
        self.assertEqual(ctx["memory"], [])
        self.assertIn("policy_decision", ctx)

    def test_handler_and_restart_dedupe(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = FileSeenStore(home=tmp)
            bus = EventBus(seen_store=store, error_sink=lambda *_: None)
            bus.subscribe("tick", lambda e: (_ for _ in ()).throw(ValueError("handler")))
            ev = Event.create(id="evt_restart", type="tick")
            first = bus.publish(ev)
            self.assertFalse(first.ok)
            bus2 = EventBus(seen_store=FileSeenStore(home=tmp))
            second = bus2.publish(ev)
            self.assertTrue(second.duplicate)


class TestIsolateEmptyUnknown(unittest.TestCase):
    def test_empty_fn_ok(self):
        self.assertTrue(isolate(lambda: None).ok)

    def test_unknown_exception_type_recorded(self):
        class Weird(Exception):
            pass
        self.assertEqual(isolate(lambda: (_ for _ in ()).throw(Weird("z"))).error_type, "Weird")


if __name__ == "__main__":
    unittest.main()
