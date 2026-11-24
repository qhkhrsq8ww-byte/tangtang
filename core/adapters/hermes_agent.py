"""Fail-closed client for a local Hermes API Server.

Intended to be injected as ChatAdapter's LLM callable. It sends only the
already-filtered prompt, uses an ephemeral Hermes session, verifies the
server's enabled toolsets before every turn, and deletes the session afterward.

Family identity, memory, privacy, and device authorization remain in TangTang Core.
"""
from __future__ import annotations

import ipaddress
import json
import os
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Mapping
from typing import Any
from uuid import uuid4

from core.persona.agent_prompt import build_agent_system_prompt


class _NoRedirectHandler(urllib.request.HTTPRedirectHandler):
    """Never forward a bearer-authenticated request to a redirect target."""

    def redirect_request(self, req: Any, fp: Any, code: int, msg: str, headers: Any, newurl: str) -> None:
        return None


class HermesAgentError(RuntimeError):
    """Base error for a Hermes request that must fail closed."""


class HermesConfigurationError(HermesAgentError):
    """The Hermes endpoint or its enabled tools do not match the safe policy."""


class HermesPrivacyError(HermesAgentError):
    """A per-turn Hermes session could not be confirmed deleted."""


class HermesAgentClient:
    """OpenAI-compatible local Hermes client with an exact toolset allowlist.

    `allowed_toolsets` maps toolset names to the exact tool names expected from
    GET /v1/toolsets. The default is no tools. A mismatch blocks inference.
    """

    def __init__(
        self,
        *,
        base_url: str | None = None,
        api_key: str | None = None,
        model: str | None = None,
        timeout: float | None = None,
        allowed_toolsets: Mapping[str, set[str] | frozenset[str]] | None = None,
        opener: Any = None,
    ) -> None:
        self.base_url = (base_url or os.environ.get("TANGTANG_HERMES_BASE_URL", "http://127.0.0.1:8642")).rstrip("/")
        self.api_key = (api_key if api_key is not None else os.environ.get("TANGTANG_HERMES_API_KEY", "")).strip()
        self.model = (model or os.environ.get("TANGTANG_HERMES_MODEL", "hermes-agent")).strip() or "hermes-agent"
        try:
            raw_timeout = float(timeout if timeout is not None else os.environ.get("TANGTANG_HERMES_TIMEOUT", "15"))
        except (TypeError, ValueError):
            raw_timeout = 15.0
        self.timeout = max(1.0, min(raw_timeout, 30.0))
        self.allowed_toolsets = {str(k): frozenset(v) for k, v in (allowed_toolsets or {}).items()}
        self._open = opener or urllib.request.build_opener(_NoRedirectHandler()).open
        self._validate_endpoint()
        if not self.api_key:
            raise HermesConfigurationError("TANGTANG_HERMES_API_KEY is required")

    def _validate_endpoint(self) -> None:
        parsed = urllib.parse.urlsplit(self.base_url)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment:
            raise HermesConfigurationError("Hermes URL must be a plain HTTP(S) origin without credentials or query")
        try:
            address = ipaddress.ip_address(parsed.hostname)
            loopback = address.is_loopback
        except ValueError:
            loopback = parsed.hostname.lower() == "localhost"
        if not loopback:
            raise HermesConfigurationError("Hermes API must bind to loopback; remote endpoints are not accepted by this adapter")

    def _request(self, path: str, *, method: str = "GET", payload: Mapping[str, Any] | None = None, session_id: str | None = None) -> tuple[int, bytes]:
        headers = {
            "Authorization": "Bearer " + self.api_key,
            "Accept": "application/json",
            "User-Agent": "TangTang-Hermes-Adapter/0.1",
        }
        data = None
        if payload is not None:
            headers["Content-Type"] = "application/json"
            data = json.dumps(dict(payload), ensure_ascii=False).encode("utf-8")
        if session_id:
            headers["X-Hermes-Session-Id"] = session_id
        request = urllib.request.Request(self.base_url + path, data=data, headers=headers, method=method)
        try:
            with self._open(request, timeout=self.timeout) as response:
                status = int(getattr(response, "status", 200))
                body = response.read(2 * 1024 * 1024 + 1)
        except urllib.error.HTTPError as exc:
            if method == "DELETE" and exc.code == 404:
                return 404, b""
            raise HermesAgentError(f"Hermes HTTP {exc.code}") from None
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            raise HermesAgentError(f"Hermes request failed ({type(exc).__name__})") from None
        if len(body) > 2 * 1024 * 1024:
            raise HermesAgentError("Hermes response exceeded 2 MiB")
        if status < 200 or status >= 300:
            raise HermesAgentError(f"Hermes HTTP {status}")
        return status, body

    def _verify_toolsets(self) -> None:
        _status, body = self._request("/v1/toolsets")
        try:
            rows = json.loads(body.decode("utf-8"))
        except (UnicodeDecodeError, ValueError) as exc:
            raise HermesConfigurationError("Hermes /v1/toolsets returned invalid JSON") from exc
        if not isinstance(rows, list):
            raise HermesConfigurationError("Hermes /v1/toolsets must return a list")
        actual: dict[str, frozenset[str]] = {}
        for row in rows:
            if not isinstance(row, Mapping) or not row.get("enabled"):
                continue
            name = str(row.get("name") or "").strip()
            tools = row.get("tools")
            if not name or not isinstance(tools, list) or not all(isinstance(tool, str) for tool in tools):
                raise HermesConfigurationError("Hermes returned a malformed enabled toolset")
            actual[name] = frozenset(tools)
        if actual != self.allowed_toolsets:
            raise HermesConfigurationError("Hermes enabled toolsets do not match the configured allowlist")

    def __call__(self, context: Mapping[str, Any]) -> str:
        prompt = context.get("_filtered_prompt") if isinstance(context, Mapping) else None
        if not isinstance(prompt, str) or not prompt.strip():
            raise HermesAgentError("TangTang filtered prompt is required")
        scope = str(context.get("privacy_scope") or "").upper()
        if scope not in {"PRIVATE", "FAMILY", "PUBLIC"}:
            raise HermesAgentError("A valid TangTang privacy scope is required")
        who = context.get("who") if isinstance(context.get("who"), Mapping) else {}
        member_id = who.get("member_id")
        system_prompt = build_agent_system_prompt(str(member_id) if member_id else None)
        self._verify_toolsets()
        session_id = "tangtang-" + uuid4().hex
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.7,
            "max_tokens": 600,
            "stream": False,
        }
        response_text = ""
        request_error: Exception | None = None
        try:
            _status, body = self._request("/v1/chat/completions", method="POST", payload=payload, session_id=session_id)
            try:
                parsed = json.loads(body.decode("utf-8"))
                content = parsed["choices"][0]["message"]["content"]
            except (UnicodeDecodeError, ValueError, KeyError, IndexError, TypeError) as exc:
                raise HermesAgentError("Hermes returned an invalid chat completion") from exc
            if not isinstance(content, str) or not content.strip():
                raise HermesAgentError("Hermes returned an empty response")
            response_text = content.strip()
        except Exception as exc:
            request_error = exc
        cleanup_error: Exception | None = None
        try:
            self._request("/api/sessions/" + urllib.parse.quote(session_id, safe=""), method="DELETE")
        except Exception as exc:
            cleanup_error = exc
        if cleanup_error is not None:
            raise HermesPrivacyError("Hermes ephemeral session cleanup failed; response withheld") from cleanup_error
        if request_error is not None:
            raise request_error
        return response_text

