from __future__ import annotations

import json
import os
import subprocess
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
CAT = ROOT / "code" / "cat"


def test_family_observe_cli_cannot_bypass_core_privacy_gate():
    with tempfile.TemporaryDirectory() as tmp:
        env = os.environ.copy()
        env["TANGTANG_DATA_DIR"] = tmp
        result = subprocess.run(
            ["/usr/bin/python3", str(CAT / "cat-family.py"), "observe", "dad", "我今天开会"],
            capture_output=True,
            text=True,
            env=env,
            timeout=10,
        )
        assert result.returncode == 2
        assert "通过 TangTang Core" in result.stderr
        assert not (Path(tmp) / "cat-habits.json").exists()


def test_family_log_cli_cannot_bypass_core_privacy_gate():
    with tempfile.TemporaryDirectory() as tmp:
        env = os.environ.copy()
        env["TANGTANG_DATA_DIR"] = tmp
        result = subprocess.run(
            ["/usr/bin/python3", str(CAT / "cat-family.py"), "log", "dad", "meal"],
            capture_output=True,
            text=True,
            env=env,
            timeout=10,
        )
        assert result.returncode == 2
        assert not (Path(tmp) / "cat-habits.json").exists()
