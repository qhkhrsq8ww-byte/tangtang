#!/usr/bin/env python3
"""Tiny unittest runner (no pytest required)."""
from __future__ import annotations

import os
import os
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FIXTURE_FAMILY = ROOT / "tests" / "fixtures" / "family.test.json"
os.environ.setdefault("TANGTANG_FAMILY_FILE", str(FIXTURE_FAMILY))
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

if __name__ == "__main__":
    # All CI tests use a synthetic roster; never depend on a real family.json.
    os.environ["TANGTANG_FAMILY_FILE"] = str(ROOT / "tests" / "fixtures" / "family.json")
    suite = unittest.defaultTestLoader.discover(
        start_dir=str(Path(__file__).parent),
        pattern="test_*.py",
        top_level_dir=str(ROOT),
    )
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)
