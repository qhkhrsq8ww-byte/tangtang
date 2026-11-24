from __future__ import annotations

import importlib.util
from datetime import datetime
from pathlib import Path


def _load_alarm_module():
    root = Path(__file__).resolve().parents[2]
    path = root / "code" / "cat" / "cat-alarm.py"
    spec = importlib.util.spec_from_file_location("tangtang_cat_alarm", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_alarm_intent_requires_owner_and_does_not_mutate_store(tmp_path, monkeypatch):
    alarm = _load_alarm_module()
    store = tmp_path / "cat-alarms.json"
    monkeypatch.setattr(alarm, "store_path", lambda: str(store))
    now = datetime(2026, 11, 24, 12, 0)

    before = alarm.handle_utterance("每天早上7点叫我", now=now)
    assert "还没确认" in before
    assert alarm.load_alarms() == []


def test_alarm_natural_language_cannot_choose_another_member(tmp_path, monkeypatch):
    alarm = _load_alarm_module()
    store = tmp_path / "cat-alarms.json"
    monkeypatch.setattr(alarm, "store_path", lambda: str(store))
    now = datetime(2026, 11, 24, 12, 0)

    # The utterance mentions 爸爸, but the authenticated caller is alice.
    alarm.handle_utterance(
        "明天早上7点叫我爸爸", now=now, owner_member_id="alice"
    )
    rows = alarm.load_alarms()
    assert len(rows) == 1
    assert rows[0]["member"] == "alice"


def test_alarm_list_and_cancel_all_are_owner_scoped(tmp_path, monkeypatch):
    alarm = _load_alarm_module()
    store = tmp_path / "cat-alarms.json"
    monkeypatch.setattr(alarm, "store_path", lambda: str(store))
    now = datetime(2026, 11, 24, 12, 0)

    alarm.set_alarm("07:00", member="alice", now=now)
    alarm.set_alarm("08:00", member="bob", now=now)

    visible = alarm.list_alarms(member="alice")
    assert len(visible) == 1
    assert visible[0]["member"] == "alice"

    alarm.handle_utterance("别再叫我了", now=now, owner_member_id="alice")
    remaining = alarm.load_alarms()
    assert len(remaining) == 1
    assert remaining[0]["member"] == "bob"
