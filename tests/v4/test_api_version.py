"""V4 ports are versioned. V5 cannot silently replace them."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.context.builder import ContextBuilder
from core.errors import CompatibilityError
from core.events.event_bus import EventBus
from core.identity.resolver import IdentityResolver
from core.interfaces import CORE_API_MAJOR, CORE_API_VERSION, require_v4
from core.memory.store import MemoryStore
from core.policy.injection import InjectionGuard
from core.policy.interrupt_policy import InterruptPolicy
from core.policy.privacy_policy import PrivacyPolicy
from core.response.orchestrator import ResponseOrchestrator


class _V4:
    core_api_version = "4.0.0"


class _V5:
    core_api_version = "5.0.0"


class TestApiVersion(unittest.TestCase):
    def test_core_api_is_v4(self):
        self.assertEqual(CORE_API_VERSION, "4.0.0")
        self.assertEqual(CORE_API_MAJOR, 4)
        self.assertTrue(CORE_API_VERSION.startswith("4."))

    def test_implementations_declare_v4(self):
        for cls in (
            PrivacyPolicy,
            IdentityResolver,
            InterruptPolicy,
            MemoryStore,
            EventBus,
            ContextBuilder,
            ResponseOrchestrator,
            InjectionGuard,
        ):
            self.assertEqual(cls.core_api_version, "4.0.0", cls.__name__)
            require_v4(cls, cls.__name__)

    def test_v5_rejected(self):
        with self.assertRaises(CompatibilityError) as ctx:
            require_v4(_V5(), "FakeV5")
        self.assertIn("not V4", str(ctx.exception))
        self.assertIn("smash", str(ctx.exception))

    def test_missing_version_rejected(self):
        with self.assertRaises(CompatibilityError):
            require_v4(object(), "no-version")

    def test_v4_accepted(self):
        require_v4(_V4(), "ok")


class TestApiVersionEmptyUnknown(unittest.TestCase):
    def test_empty_version_rejected(self):
        class Empty:
            core_api_version = ""

        with self.assertRaises(CompatibilityError):
            require_v4(Empty(), "empty")

    def test_unknown_major_rejected(self):
        class Other:
            core_api_version = "3.9.0"

        with self.assertRaises(CompatibilityError):
            require_v4(Other(), "v3")


if __name__ == "__main__":
    unittest.main()
