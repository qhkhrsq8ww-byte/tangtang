"""Tests for selecting Hermes as the V4 LLM backend without silent fallback."""
from __future__ import annotations

import importlib.util
import os
import sys
import types
import unittest
from pathlib import Path
from unittest import mock

MODULE_PATH = Path(__file__).resolve().parents[2] / "code" / "cat" / "cat-chat.py"
SPEC = importlib.util.spec_from_file_location("tangtang_cat_chat_backend_test", MODULE_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("Unable to load cat-chat.py")
CAT_CHAT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(CAT_CHAT)


class FakeHermesClient:
    def __init__(self, **kwargs):
        self.kwargs = kwargs
        self.context = None

    def __call__(self, context):
        self.context = context
        return "Hermes response"


class TestHermesBackendSelection(unittest.TestCase):
    def context(self):
        return {"_filtered_prompt": "member=child_9\\nprivacy=PRIVATE\\nutterance=hello", "privacy_scope": "PRIVATE", "who": {"member_id": "child_9"}}

    def test_hermes_backend_uses_adapter_and_not_direct_provider(self):
        fake = FakeHermesClient()
        module = types.SimpleNamespace(HermesAgentClient=mock.Mock(return_value=fake))
        with mock.patch.dict(os.environ, {
            "TANGTANG_LLM_BACKEND": "hermes",
            "TANGTANG_ALLOW_PRIVATE_LLM": "1",
            "TANGTANG_HERMES_MODEL": "hermes-agent",
        }, clear=True):
            with mock.patch.dict(sys.modules, {"core.adapters.hermes_agent": module}):
                with mock.patch.object(CAT_CHAT, "chat") as direct_chat:
                    call = CAT_CHAT._runtime_llm()
                    result = call(self.context())
        self.assertEqual(result, "Hermes response")
        self.assertEqual(fake.kwargs["model"], "hermes-agent")
        self.assertEqual(fake.context["_filtered_prompt"], self.context()["_filtered_prompt"])
        direct_chat.assert_not_called()

    def test_hermes_failure_does_not_fall_back_to_direct_provider(self):
        module = types.SimpleNamespace(HermesAgentClient=mock.Mock(side_effect=RuntimeError("offline")))
        with mock.patch.dict(os.environ, {
            "TANGTANG_LLM_BACKEND": "hermes",
            "TANGTANG_ALLOW_PRIVATE_LLM": "1",
        }, clear=True):
            with mock.patch.dict(sys.modules, {"core.adapters.hermes_agent": module}):
                with mock.patch.object(CAT_CHAT, "chat") as direct_chat:
                    call = CAT_CHAT._runtime_llm()
                    result = call(self.context())
        self.assertEqual(result, CAT_CHAT.FALLBACK_REPLY)
        direct_chat.assert_not_called()

    def test_private_turn_still_requires_existing_explicit_opt_in(self):
        module = types.SimpleNamespace(HermesAgentClient=mock.Mock(return_value=FakeHermesClient()))
        with mock.patch.dict(os.environ, {"TANGTANG_LLM_BACKEND": "hermes"}, clear=True):
            with mock.patch.dict(sys.modules, {"core.adapters.hermes_agent": module}):
                call = CAT_CHAT._runtime_llm()
                result = call(self.context())
        self.assertEqual(result, CAT_CHAT.FALLBACK_REPLY)
        module.HermesAgentClient.assert_called_once()

    def test_default_backend_remains_legacy_direct(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            with mock.patch.object(CAT_CHAT, "chat", return_value="direct response") as direct_chat:
                call = CAT_CHAT._runtime_llm(model="test-model")
                result = call({"_filtered_prompt": "safe prompt", "privacy_scope": "FAMILY", "who": {"member_id": "dad"}})
        self.assertEqual(result, "direct response")
        direct_chat.assert_called_once_with("safe prompt", model="test-model", history=None)

    def test_unknown_backend_fails_closed(self):
        with mock.patch.dict(os.environ, {"TANGTANG_LLM_BACKEND": "unknown"}, clear=True):
            with mock.patch.object(CAT_CHAT, "chat") as direct_chat:
                call = CAT_CHAT._runtime_llm()
                result = call({"_filtered_prompt": "safe prompt", "privacy_scope": "FAMILY", "who": {"member_id": "dad"}})
        self.assertEqual(result, CAT_CHAT.FALLBACK_REPLY)
        direct_chat.assert_not_called()


if __name__ == "__main__":
    unittest.main()
