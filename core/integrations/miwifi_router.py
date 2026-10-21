"""Safe, local-only adapter for Xiaomi MiWiFi device management.

No credentials are stored here. Read-only inventory is the default; network
access changes require an explicit local parent confirmation and an opt-in flag.
"""
from __future__ import annotations

import ipaddress
import json
import os
import re
import urllib.parse
import urllib.request


class RouterError(RuntimeError):
    """Router unavailable, unauthenticated, or returned an unexpected response."""


_MAC_RE = re.compile(r"^[0-9a-f]{2}(?::[0-9a-f]{2}){5}$")
_TOKEN_RE = re.compile(r"^[A-Za-z0-9_-]{8,128}$")


def normalize_mac(value):
    mac = str(value or "").strip().lower().replace("-", ":")
    if not _MAC_RE.fullmatch(mac):
        raise ValueError("A valid MAC address is required")
    return mac


class MiWiFiClient:
    """Client for the documented MiWiFi LAN API (R3D device-list/filter endpoints)."""

    def __init__(self, base_url=None, token=None, timeout=3.0, opener=None):
        self.base_url = (base_url or os.environ.get(
            "MIWIFI_ROUTER_URL", "http://192.168.31.1"
        )).rstrip("/")
        self.token = token if token is not None else os.environ.get("MIWIFI_STOK", "")
        self.timeout = max(1.0, min(float(timeout), 8.0))
        self._opener = opener or urllib.request.urlopen
        self._validate_base_url()
        if self.token and not _TOKEN_RE.fullmatch(self.token):
            raise ValueError("MIWIFI_STOK format is invalid")

    def _validate_base_url(self):
        parsed = urllib.parse.urlsplit(self.base_url)
        if parsed.scheme != "http" or not parsed.hostname or parsed.port not in (None, 80):
            raise ValueError("Router URL must be an HTTP LAN address on port 80")
        if parsed.username or parsed.password or parsed.query or parsed.fragment:
            raise ValueError("Router URL must not contain credentials, query, or fragment")
        try:
            address = ipaddress.ip_address(parsed.hostname)
        except ValueError:
            raise ValueError("Router host must be a private LAN IP address")
        if not address.is_private or address.is_loopback or address.is_link_local:
            raise ValueError("Router host must be a private LAN IP address")

    def _request(self, endpoint, params=None):
        if not self.token:
            raise RouterError("MIWIFI_STOK is not configured; log in to the router locally first")
        if endpoint not in ("api/misystem/devicelist", "api/xqsystem/set_mac_filter"):
            raise ValueError("Unsupported router endpoint")
        path = "/cgi-bin/luci/;stok={}/{}".format(self.token, endpoint)
        query = urllib.parse.urlencode(params or {})
        url = self.base_url + path + (("?" + query) if query else "")
        request = urllib.request.Request(
            url,
            headers={"Accept": "application/json", "User-Agent": "TangTang-Router/1.0"},
            method="GET",
        )
        try:
            with self._opener(request, timeout=self.timeout) as response:
                raw = response.read(1024 * 1024 + 1)
        except Exception as exc:
            raise RouterError("Router request failed; check LAN connectivity and login token") from exc
        if len(raw) > 1024 * 1024:
            raise RouterError("Router response exceeded size limit")
        try:
            data = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, ValueError) as exc:
            raise RouterError("Router returned invalid JSON") from exc
        if not isinstance(data, dict) or data.get("code") != 0:
            raise RouterError("Router rejected the request or the login token expired")
        return data

    def list_devices(self):
        """Return a normalized inventory; no device control is performed."""
        data = self._request("api/misystem/devicelist", {"mlo": "1"})
        raw_devices = data.get("list")
        if not isinstance(raw_devices, list):
            raise RouterError("Router response did not contain a device list")
        devices = []
        for item in raw_devices:
            if not isinstance(item, dict):
                continue
            try:
                mac = normalize_mac(item.get("mac"))
            except ValueError:
                continue
            ips = item.get("ip") if isinstance(item.get("ip"), list) else []
            active_ips = [
                str(ip.get("ip")) for ip in ips
                if isinstance(ip, dict) and ip.get("ip")
            ]
            authority = item.get("authority") if isinstance(item.get("authority"), dict) else {}
            devices.append({
                "mac": mac,
                "name": str(item.get("name") or item.get("oname") or "未命名设备")[:80],
                "online": bool(int(item.get("online", 0) or 0)),
                "ips": active_ips[:8],
                "connection_type": item.get("type"),
                "internet_allowed": authority.get("wan"),
            })
        return devices

    def set_internet_access(self, mac, allowed, *, parent_approved=False,
                            confirmed_mac=None, protected_macs=None):
        """Change WAN access only after an explicit local parent confirmation.

        Voice/LLM callers must not set parent_approved based on the child's utterance.
        """
        normalized = normalize_mac(mac)
        if not parent_approved:
            raise PermissionError("Parent approval is required")
        if normalize_mac(confirmed_mac) != normalized:
            raise PermissionError("Typed confirmation must match the target MAC")
        if os.environ.get("TANGTANG_ROUTER_CONTROL_ENABLED") != "1":
            raise PermissionError("Router control is disabled; set the local opt-in after review")
        router_mac_value = os.environ.get("MIWIFI_ROUTER_MAC", "").strip()
        if not router_mac_value:
            raise PermissionError("Configure MIWIFI_ROUTER_MAC before enabling device control")
        router_mac = normalize_mac(router_mac_value)
        env_protected = os.environ.get("TANGTANG_ROUTER_PROTECTED_MACS", "").split(",")
        protected = {
            normalize_mac(value) for value in (env_protected + list(protected_macs or []))
            if str(value or "").strip()
        }
        protected.add(router_mac)
        if normalized in protected:
            raise PermissionError("This device is protected from network changes")
        if not isinstance(allowed, bool):
            raise ValueError("allowed must be a boolean")
        result = self._request(
            "api/xqsystem/set_mac_filter",
            {"mac": normalized, "wan": "1" if allowed else "0"},
        )
        return {"mac": normalized, "internet_allowed": allowed, "code": result["code"]}
