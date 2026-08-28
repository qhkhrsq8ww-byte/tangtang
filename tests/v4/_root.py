"""Path helper so tests import `core` from the repo root."""
from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

DAYTIME = datetime(2026, 8, 28, 16, 0, tzinfo=timezone.utc)
