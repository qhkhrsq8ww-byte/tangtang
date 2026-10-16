"""V5 memory relevance tests."""
from __future__ import annotations
import unittest
from datetime import datetime, timezone
from core.memory.relevance import relevance_score

class TestMemoryRelevance(unittest.TestCase):
    def test_open_due_task_beats_old_preference(self):
        now=datetime(2026,10,16,10,0,tzinfo=timezone.utc)
        task={"type":"task","confidence":1,"created_at":"2026-10-15T10:00:00+00:00","data":{"status":"open","due_at":"2026-10-18T10:00:00+00:00"}}
        pref={"type":"preference","confidence":1,"created_at":"2026-01-01T10:00:00+00:00","data":{"tag":"food","value":"蛋炒饭"}}
        self.assertGreater(relevance_score(task,now=now), relevance_score(pref,now=now))

if __name__=="__main__": unittest.main()
