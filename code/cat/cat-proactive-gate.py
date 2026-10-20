#!/usr/bin/env python3
"""Check or record a low-pressure proactive scene without storing dialogue."""
from __future__ import annotations

import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

CAT_DIR = Path(__file__).resolve().parent
ROOT = CAT_DIR.parent if (CAT_DIR.parent / "core").is_dir() else CAT_DIR.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from tangtang_paths import data_dir
from core.companion.proactive import ProactiveGate


def main() -> int:
    action = sys.argv[1] if len(sys.argv) > 1 else "check"
    event = (sys.argv[2] if len(sys.argv) > 2 else "scene").strip()[:80]
    member = (sys.argv[3] if len(sys.argv) > 3 else os.environ.get("TANGTANG_MEMBER_ID", "room")).strip()[:80]
    home = Path(data_dir())
    gate = ProactiveGate(home=home, cooldown_minutes=int(os.environ.get("TANGTANG_SCENE_COOLDOWN_MINUTES", "45")))
    now = datetime.now().astimezone()
    if action == "record":
        gate.record(event=event, member_id=member, now=now)
        print("recorded")
        return 0
    if action != "check":
        print("usage: cat-proactive-gate.py check|record EVENT [MEMBER]", file=sys.stderr)
        return 2

    start = os.environ.get("TANGTANG_QUIET_START", "22:30")
    end = os.environ.get("TANGTANG_QUIET_END", "07:00")
    habit_allows = True
    habits = CAT_DIR / "cat-habits.py"
    if habits.is_file():
        try:
            result = subprocess.run(
                ["/usr/bin/python3", str(habits), "should-speak", event, member],
                capture_output=True, text=True, timeout=5, check=False,
            )
            if result.returncode == 0 and result.stdout.strip().startswith("skip|"):
                habit_allows = False
        except (OSError, subprocess.TimeoutExpired):
            # If the habit subsystem is unavailable, retain quiet-hours/cooldown safeguards.
            pass
    allowed, reason = gate.check(event=event, member_id=member, now=now,
                                 habit_allows=habit_allows, quiet_start=start, quiet_end=end)
    print(("speak|" if allowed else "skip|") + reason)
    return 0 if allowed else 3


if __name__ == "__main__":
    raise SystemExit(main())
