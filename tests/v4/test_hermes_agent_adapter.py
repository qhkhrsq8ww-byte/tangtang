"""Tests for the fail-closed Hermes API adapter; all responses are mocked."""
from __future__ import annotations

import json
import unittest
import urllib.error
from unittest.mock import Mock

from core.adapters.hermes_agent import (
    HermesAgentClient,
    HermesAgentError,
    HermesConfigurationError,
    HermesPrivacyError,
)


class FakeResponse:
    def __init__(self, body: bytes = b"", status: int = 200):
        self._body = body
        self.status = status

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self, _limit: int = -1):
        return self._body


class TestHermesAgentClient(unittest.TestCase):
    def make_client(self, responses, **kwargs):
        calls = []
        queue = list(responses)

        def opener(request, timeout=0):
            calls.append((request, timeout))
            item = queue.pop(0)
            if isinstance(item, Exception):
                raise item
            return item

        client = HermesAgentClient(
            base_url="http://127.0.0.1:8642",
            api_key="unit-test-secret",
            opener=opener,
            **kwargs,
        )
        return client, calls

    def test_sends_only_filtered_prompt_and_deletes_ephemeral_session(self):
        toolsets = FakeResponse(b"[]")
        completion = FakeResponse(json.dumps({
            "choices": [{"message": {"content": "糖糖在呢，我们先慢慢来。"}}]
        }).encode("utf-8"))
        deleted = FakeResponse(b"", status=204)
        client, calls = self.make_client([toolsets, completion, deleted])
        result = client({
            "_filtered_prompt": "member=child_9\\nprivacy=PRIVATE\\nutterance=今天有点累",
            "utterance": "RAW_FIELD_MUST_NOT_BE_SENT",
            "who": {"member_id": "child_9"},
            "privacy_scope": "PRIVATE",
        })
        self.assertEqual(result, "糖糖在呢，我们先慢慢来。")
        self.assertEqual(len(calls), 3)
        request = calls[1][0]
        payload = json.loads(request.data.decode("utf-8"))
        self.assertEqual(payload["messages"][1]["content"], "member=child_9\\nprivacy=PRIVATE\\nutterance=今天有点累")
        self.assertNotIn("RAW_FIELD_MUST_NOT_BE_SENT", request.data.decode("utf-8"))
        self.assertEqual(payload["messages"][0]["role"], "system")
        self.assertIn("儿童玩伴模式", payload["messages"][0]["content"])
        self.assertEqual(request.get_header("Authorization"), "Bearer unit-test-secret")
        self.assertTrue(request.get_header("X-hermes-session-id").startswith("tangtang-"))
        self.assertEqual(calls[2][0].get_method(), "DELETE")

    def test_toolset_mismatch_blocks_inference(self):
        enabled = [{"name": "core", "enabled": True, "tools": ["read_file", "write_file"]}]
        client, calls = self.make_client([FakeResponse(json.dumps(enabled).encode("utf-8"))])
        with self.assertRaises(HermesConfigurationError):
            client({"_filtered_prompt": "safe", "privacy_scope": "PUBLIC", "who": {}})
        self.assertEqual(len(calls), 1)

    def test_exact_toolset_allowlist_is_enforced(self):
        enabled = [{"name": "mcp-tangtang", "enabled": True, "tools": ["get_context", "create_reminder"]}]
        expected = {"mcp-tangtang": {"get_context"}}
        client, calls = self.make_client([FakeResponse(json.dumps(enabled).encode("utf-8"))], allowed_toolsets=expected)
        with self.assertRaises(HermesConfigurationError):
            client({"_filtered_prompt": "safe", "privacy_scope": "PUBLIC", "who": {}})
        self.assertEqual(len(calls), 1)

    def test_rejects_non_loopback_endpoint(self):
        with self.assertRaises(HermesConfigurationError):
            HermesAgentClient(base_url="https://hermes.example.com", api_key="secret")

    def test_requires_api_key(self):
        with self.assertRaises(HermesConfigurationError):
            HermesAgentClient(base_url="http://127.0.0.1:8642", api_key="")

    def test_requires_filtered_prompt_and_privacy_scope(self):
        client, calls = self.make_client([])
        with self.assertRaises(HermesAgentError):
            client({"utterance": "hello", "privacy_scope": "PRIVATE", "who": {}})
        with self.assertRaises(HermesAgentError):
            client({"_filtered_prompt": "hello", "privacy_scope": "UNKNOWN", "who": {}})
        self.assertEqual(calls, [])

    def test_session_cleanup_failure_withholds_reply(self):
        toolsets = FakeResponse(b"[]")
        completion = FakeResponse(json.dumps({
            "choices": [{"message": {"content": "this must not be returned"}}]
        }).encode("utf-8"))
        cleanup_error = urllib.error.HTTPError("http://127.0.0.1:8642/api/sessions/test", 500, "failed", {}, None)
        client, _calls = self.make_client([toolsets, completion, cleanup_error])
        with self.assertRaises(HermesPrivacyError):
            client({"_filtered_prompt": "safe", "privacy_scope": "PUBLIC", "who": {}})


if __name__ == "__main__":
    unittest.main()
