from __future__ import annotations

import importlib.util
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
CAT = ROOT / "code" / "cat"


def _load_voiceprint():
    path = CAT / "cat-vp.py"
    spec = importlib.util.spec_from_file_location("tangtang_voiceprint_test", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_coarse_voice_similarity_never_returns_authenticated_identity():
    vp = _load_voiceprint()
    assert vp.identify("missing-audio.pcm") == "unknown"
    candidate = vp.identify_candidate("missing-audio.pcm")
    assert candidate["candidate_member_id"] is None


def test_voice_wrapper_does_not_promote_presence_or_write_memory_before_core():
    source = (CAT / "cat-voice.sh").read_text(encoding="utf-8")
    assert 'cat-presence.py" suggest' not in source
    assert 'cat-family.py" observe' not in source
    assert 'cat-vp.py" log' not in source
    assert "env -u TANGTANG_MEMBER_ID -u TANGTANG_SPEAKER" in source
    assert '--member "$WHO"' in source


def test_voiceprint_log_cli_is_closed():
    result = subprocess.run(
        ["/usr/bin/python3", str(CAT / "cat-vp.py"), "log", "dad"],
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert result.returncode == 2
    assert "通过 TangTang Core" in result.stderr
