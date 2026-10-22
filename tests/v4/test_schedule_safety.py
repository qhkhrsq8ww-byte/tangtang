"""Regression tests for safe and retryable family-device scheduling."""
import importlib.util
from pathlib import Path
import datetime
import unittest

ROOT = Path(__file__).resolve().parents[2]
SCHEDULE_PATH = ROOT / "code" / "cat" / "cat-schedule.py"
spec = importlib.util.spec_from_file_location("tangtang_schedule", SCHEDULE_PATH)
schedule = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(schedule)


def sample():
    return {
        "window": {"start": "22:30", "restore": "07:00"},
        "weekend_exempt": False,
        "targets": [{"name": "child phone", "member": "child", "mac": "AA:BB:CC:DD:EE:01"}],
        "protected": [{"name": "host Mac", "mac": "AA:BB:CC:DD:EE:02"}],
    }


class ScheduleSafetyTests(unittest.TestCase):
    def test_valid_schedule_passes_and_normalizes_mac(self):
        self.assertTrue(schedule.validate_schedule(sample()))
        self.assertEqual(schedule.normalize_mac("aa-bb-cc-dd-ee-01"), "aa:bb:cc:dd:ee:01")

    def test_refuses_protected_device_in_targets(self):
        config = sample()
        config["targets"][0]["mac"] = "aa:bb:cc:dd:ee:02"
        with self.assertRaisesRegex(ValueError, "受保护设备"):
            schedule.validate_schedule(config)

    def test_refuses_duplicate_targets(self):
        config = sample()
        config["targets"].append(dict(config["targets"][0]))
        with self.assertRaisesRegex(ValueError, "重复 MAC"):
            schedule.validate_schedule(config)

    def test_refuses_invalid_time_and_invalid_mac(self):
        config = sample()
        config["window"]["start"] = "25:90"
        with self.assertRaises(ValueError):
            schedule.validate_schedule(config)
        config = sample()
        config["targets"][0]["mac"] = "unknown"
        with self.assertRaisesRegex(ValueError, "MAC 地址格式无效"):
            schedule.validate_schedule(config)

    def test_window_crosses_midnight_and_weekend_exemption(self):
        config = sample()
        self.assertEqual(schedule.desired_state(config, datetime.datetime(2026, 10, 22, 23, 0)), "block")
        self.assertEqual(schedule.desired_state(config, datetime.datetime(2026, 10, 23, 6, 59)), "block")
        self.assertEqual(schedule.desired_state(config, datetime.datetime(2026, 10, 23, 7, 0)), "unblock")
        config["weekend_exempt"] = True
        self.assertEqual(schedule.desired_state(config, datetime.datetime(2026, 10, 24, 23, 0)), "unblock")


if __name__ == "__main__":
    unittest.main()
