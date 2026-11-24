from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def _load_cat_chat():
    path = ROOT / "code" / "cat" / "cat-chat.py"
    spec = importlib.util.spec_from_file_location("tangtang_cat_chat", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_unknown_voice_candidate_is_not_promoted_by_chat_observation(monkeypatch):
    chat = _load_cat_chat()
    monkeypatch.setattr(chat, "_resolve_speaker_member", lambda: (None, "unknown"))
    monkeypatch.setenv("TANGTANG_SPEAKER", "unknown")
    monkeypatch.setenv("TANGTANG_MEMBER_ID", "dad")

    observation = chat._live_obs()

    assert "member_id" not in observation
    assert "label" not in observation


def test_voice_shell_does_not_write_legacy_family_memory_before_core():
    source = (ROOT / "code" / "cat" / "cat-voice.sh").read_text(encoding="utf-8")
    assert 'cat-family.py" observe' not in source
    assert 'cat-presence.py" suggest' not in source


def test_living_room_does_not_persist_raw_member_fallback():
    source = (ROOT / "code" / "cat" / "cat-living.py").read_text(encoding="utf-8")
    assert 'IdentityResolver(load_members()).resolve({"label": candidate})' in source
    assert 'result.member_id or member or "unknown"' not in source
    assert "if member and result.member_id == member:" in source
