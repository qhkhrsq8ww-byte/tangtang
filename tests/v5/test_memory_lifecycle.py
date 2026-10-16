"""V5 memory lifecycle tests."""
from __future__ import annotations
import unittest
from datetime import datetime, timezone, timedelta
from core.memory.lifecycle import lifecycle_state, suggested_expiry

class TestMemoryLifecycle(unittest.TestCase):
    def setUp(self):
        self.now=datetime(2026,10,16,10,0,tzinfo=timezone.utc)

    def test_completed_task_is_not_active(self):
        row={"type":"task","data":{"status":"completed"}}
        self.assertEqual(lifecycle_state(row,now=self.now),"completed")

    def test_due_task_expires(self):
        row={"type":"task","data":{"status":"open","due_at":"2026-10-15T10:00:00+00:00"}}
        self.assertEqual(lifecycle_state(row,now=self.now),"expired")

    def test_preference_is_persistent(self):
        self.assertEqual(lifecycle_state({"type":"preference","data":{"value":"蛋炒饭"}},now=self.now),"persistent")

    def test_default_task_expiry_is_bounded(self):
        expiry=suggested_expiry("task",now=self.now)
        self.assertEqual(expiry,self.now+timedelta(days=14))

if __name__=="__main__": unittest.main()
