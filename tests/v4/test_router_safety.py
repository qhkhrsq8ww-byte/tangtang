"""Safety tests for direct router control commands."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
ROUTER_PATH = ROOT / "code" / "cat" / "cat-router.py"
spec = importlib.util.spec_from_file_location("tangtang_router", ROUTER_PATH)
router = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(router)


class RouterSafetyTests(unittest.TestCase):
    def test_mac_normalization_and_rejects_invalid_or_multicast(self):
        self.assertEqual(router.normalize_mac("AA-BB-CC-DD-EE-01"), "aa:bb:cc:dd:ee:01")
        for mac in ("unknown", "00:00:00:00:00:00", "ff:ff:ff:ff:ff:ff", "01:00:5e:00:00:01"):
            with self.subTest(mac=mac), self.assertRaises(ValueError):
                router.normalize_mac(mac)

    def test_block_requires_explicit_target_and_refuses_protected_device(self):
        with tempfile.TemporaryDirectory() as tmp:
            router.CAT_DIR = tmp
            config = {
                "targets": [{"name": "child phone", "member": "child", "mac": "aa:bb:cc:dd:ee:01"}],
                "protected": [{"name": "host Mac", "mac": "aa:bb:cc:dd:ee:02"}],
            }
            Path(tmp, "cat-schedule.json").write_text(json.dumps(config), encoding="utf-8")
            self.assertEqual(router.guard_block_target("AA-BB-CC-DD-EE-01"), "aa:bb:cc:dd:ee:01")
            with self.assertRaisesRegex(RuntimeError, "受保护"):
                router.guard_block_target("aa:bb:cc:dd:ee:02")
            with self.assertRaisesRegex(RuntimeError, "未列入"):
                router.guard_block_target("aa:bb:cc:dd:ee:03")

    def test_block_fails_closed_when_protected_list_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            router.CAT_DIR = tmp
            config = {"targets": [{"name": "child", "member": "child", "mac": "aa:bb:cc:dd:ee:01"}]}
            Path(tmp, "cat-schedule.json").write_text(json.dumps(config), encoding="utf-8")
            with self.assertRaisesRegex(RuntimeError, "protected 保护名单缺失"):
                router.guard_block_target("aa:bb:cc:dd:ee:01")

    def test_block_fails_closed_when_local_schedule_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            router.CAT_DIR = tmp
            with self.assertRaisesRegex(RuntimeError, "缺少本机"):
                router.guard_block_target("aa:bb:cc:dd:ee:01")


if __name__ == "__main__":
    unittest.main()
