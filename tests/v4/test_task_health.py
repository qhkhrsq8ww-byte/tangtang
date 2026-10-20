"""Reminder health audit catches missing cron installation and stale/failed runs."""
from __future__ import annotations
import importlib.util
import sys
import tempfile
import unittest
from datetime import datetime, timezone, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
SCRIPT = ROOT / "code" / "cat" / "cat-task-health.py"
spec = importlib.util.spec_from_file_location("cat_task_health", SCRIPT)
health = importlib.util.module_from_spec(spec)
spec.loader.exec_module(health)


class TestTaskHealth(unittest.TestCase):
    def test_missing_cron_or_run_is_not_healthy(self):
        with tempfile.TemporaryDirectory() as td:
            report = health.inspect(Path(td), now=datetime(2026, 10, 21, 9, tzinfo=timezone.utc),
                                    cron_text="")
            self.assertEqual(report["status"], "attention_required")
            self.assertIn("dispatcher_not_installed", report["issues"])
            self.assertIn("no_delivery_run_record", report["issues"])

    def test_recent_run_and_installed_cron_are_healthy(self):
        with tempfile.TemporaryDirectory() as td:
            home = Path(td)
            log = home / "tasks" / "dispatch-health.jsonl"
            log.parent.mkdir(parents=True)
            now = datetime(2026, 10, 21, 9, tzinfo=timezone.utc)
            log.write_text('{"ts":"2026-10-21T08:59:00+00:00","mode":"deliver","outcome":"ok","stats":{"succeeded":1}}\n', encoding="utf-8")
            report = health.inspect(home, now=now, cron_text="* * * * * /usr/bin/python3 cat-task-dispatch.py --deliver")
            self.assertEqual(report["status"], "healthy")
            self.assertEqual(report["last_delivery_age_seconds"], 60)

    def test_failed_task_is_flagged_without_exposing_title(self):
        with tempfile.TemporaryDirectory() as td:
            home = Path(td)
            task_path = home / "tasks" / "tasks.json"
            task_path.parent.mkdir(parents=True)
            task_path.write_text('{"tasks":[{"title":"private child task","status":"failed"}]}', encoding="utf-8")
            report = health.inspect(home, now=datetime(2026, 10, 21, 9, tzinfo=timezone.utc),
                                    cron_text="* * * * * cat-task-dispatch.py --deliver")
            self.assertIn("failed_tasks_need_review", report["issues"])
            self.assertNotIn("private child task", str(report))


if __name__ == "__main__":
    unittest.main()
