"""V5.1 API contract smoke tests."""
from __future__ import annotations
import unittest
from core.runtime.loop import TangTangRuntime
from core.response.orchestrator import ResponseOrchestrator
from core.adapters.tts_adapter import TTSAdapter
from core.adapters.projection_adapter import ProjectionAdapter

class TestV51ApiContract(unittest.TestCase):
    def test_core_versions_are_aligned(self):
        self.assertEqual(TangTangRuntime.core_api_version, "5.1.0")
        self.assertEqual(ResponseOrchestrator.core_api_version, "5.1.0")
        self.assertEqual(TTSAdapter.core_api_version, "5.1.0")
        self.assertEqual(ProjectionAdapter.core_api_version, "5.1.0")

if __name__ == "__main__":
    unittest.main()
