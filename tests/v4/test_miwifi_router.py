import json
import os
import unittest
from unittest.mock import patch

from core.integrations.miwifi_router import MiWiFiClient, RouterError


class FakeResponse:
    def __init__(self, payload):
        self.payload = json.dumps(payload).encode("utf-8")
    def __enter__(self):
        return self
    def __exit__(self, *args):
        return False
    def read(self, size=-1):
        return self.payload[:size]


class MiWiFiClientTests(unittest.TestCase):
    def client(self, payload, captured=None):
        def opener(request, timeout=3):
            if captured is not None:
                captured.append((request.full_url, timeout))
            return FakeResponse(payload)
        return MiWiFiClient(token="1234567890abcdef", opener=opener)

    def test_private_lan_only(self):
        with self.assertRaises(ValueError):
            MiWiFiClient(base_url="http://example.com", token="1234567890abcdef")
        with self.assertRaises(ValueError):
            MiWiFiClient(base_url="http://8.8.8.8", token="1234567890abcdef")

    def test_list_devices_normalizes_data(self):
        client = self.client({"code": 0, "list": [{
            "mac": "AA-BB-CC-DD-EE-FF", "name": "Living Room Projector",
            "online": 1, "type": 2, "authority": {"wan": 1},
            "ip": [{"ip": "192.168.31.22", "active": 1}],
        }]})
        self.assertEqual(client.list_devices(), [{
            "mac": "aa:bb:cc:dd:ee:ff", "name": "Living Room Projector",
            "online": True, "ips": ["192.168.31.22"], "connection_type": 2,
            "internet_allowed": 1,
        }])

    def test_list_rejects_router_error(self):
        client = self.client({"code": 401})
        with self.assertRaises(RouterError):
            client.list_devices()

    def test_control_requires_parent_approval_and_opt_in(self):
        client = self.client({"code": 0})
        mac = "aa:bb:cc:dd:ee:ff"
        with self.assertRaises(PermissionError):
            client.set_internet_access(mac, False, confirmed_mac=mac)
        with patch.dict(os.environ, {"TANGTANG_ROUTER_CONTROL_ENABLED": "0"}):
            with self.assertRaises(PermissionError):
                client.set_internet_access(mac, False, parent_approved=True, confirmed_mac=mac)

    def test_control_requires_exact_confirmation_and_protects_devices(self):
        client = self.client({"code": 0})
        mac = "aa:bb:cc:dd:ee:ff"
        with patch.dict(os.environ, {"TANGTANG_ROUTER_CONTROL_ENABLED": "1"}):
            with self.assertRaises(PermissionError):
                client.set_internet_access(mac, False, parent_approved=True,
                                           confirmed_mac="00:11:22:33:44:55")
            with self.assertRaises(PermissionError):
                client.set_internet_access(mac, False, parent_approved=True,
                                           confirmed_mac=mac, protected_macs=[mac])
            result = client.set_internet_access(mac, True, parent_approved=True,
                                                 confirmed_mac=mac)
        self.assertEqual(result, {"mac": mac, "internet_allowed": True, "code": 0})

    def test_missing_token_fails_closed(self):
        client = MiWiFiClient(token="")
        with self.assertRaises(RouterError):
            client.list_devices()


if __name__ == "__main__":
    unittest.main()
