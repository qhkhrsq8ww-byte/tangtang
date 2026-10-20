"""Dispatch health log must remain valid line-delimited JSON without private task content."""
from __future__ import annotations
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CAT_DIR = ROOT / "code" / "cat"
for path in (ROOT, CAT_DIR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))
SCRIPT = CAT_DIR / "cat-task-dispatch.py"
spec = importlib.util.spec_from_file_location("cat_task_dispatch", SCRIPT)
dispatch = importlib.util.module_from_spec(spec)
spec.loader.exec_module(dispatch)


class TestDispatchHealthLog(unittest.TestCase):
    def test_each_run_is_valid_jsonl_and_contains_no_task_text(self):
        with tempfile.TemporaryDirectory() as td:
            home = Path(td)
            dispatch.write_health(home, mode="deliver", outcome="ok",
                                  stats={"succeeded": 1, "failed": 0})
            dispatch.write_health(home, mode="deliver", outcome="delivery_failed",
                                  stats={"succeeded": 0, "failed": 1})
            log = home / "tasks" / "dispatch-health.jsonl"
            lines = log.read_text(encoding="utf-8").splitlines()
            self.assertEqual(len(lines), 2)
            rows = [json.loads(line) for line in lines]
            self.assertEqual(rows[0]["stats"]["succeeded"], 1)
            self.assertEqual(rows[1]["outcome"], "delivery_failed")
            self.assertNotIn("title", log.read_text(encoding="utf-8"))
            self.assertEqual(log.stat().st_mode & 0o777, 0o600)


if __name__ == "__main__":
    unittest.main()
