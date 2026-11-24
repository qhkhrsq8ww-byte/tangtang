#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""糖糖 · 客厅主动场景（V4 LivingRoomAdapter，不 dump-merge 旧栈）

用法:
  python3 cat-living.py <场景> [成员]
  场景: 手机|久坐|rest|吃饭|meal|运动|exercise|play|睡觉|sleep|回家|home|离家|away

走 InterruptPolicy：SPEAK 才打印话术；SILENT/LOG_ONLY/DELAY 输出空行并 exit 0。
不调用 LLM；不写儿童原话。主动场景不会被记作目标成员的个人习惯。
"""
from __future__ import annotations

import json
import os
import sys

CAT_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(CAT_DIR, "..", ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
if CAT_DIR not in sys.path:
    sys.path.insert(0, CAT_DIR)

from tangtang_paths import data_dir  # noqa: E402

EVENT_TO_KIND = {
    "rest": "久坐",
    "sitting": "久坐",
    "phone": "手机",
    "screen": "手机",
    "meal": "吃饭",
    "exercise": "运动",
    "play": "运动",
    "sleep": "睡觉",
    "sleepy": "睡觉",
    "home": "回家",
    "welcome": "回家",
    "away": "离家",
    "water": "久坐",  # soft nudge via sitting policy bucket when used as remind
}


KIND_TO_TAG = {
    "手机": "screen", "phone": "screen", "久坐": "rest", "sitting": "rest",
    "吃饭": "meal", "meal": "meal", "运动": "exercise", "exercise": "exercise",
    "play": "exercise", "睡觉": "sleep", "sleep": "sleep", "回家": "home",
    "home": "home", "离家": "away", "away": "away",
}


def _habit_tag(kind: str) -> str:
    """Map a scene to its legacy habit label; mapping alone does not record behavior."""
    normalized = EVENT_TO_KIND.get((kind or "").strip().lower(), (kind or "").strip())
    return KIND_TO_TAG.get(normalized) or KIND_TO_TAG.get(normalized.lower()) or "conversation"


def _normalize(kind: str) -> str:
    raw = (kind or "").strip()
    return EVENT_TO_KIND.get(raw.lower(), raw) or "久坐"



def main(argv=None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if not args or args[0] in ("-h", "--help", "help"):
        print(__doc__.strip())
        return 0
    kind = _normalize(args[0])
    member = (args[1] if len(args) > 1 else "").strip()
    member = member or (
        os.environ.get("TANGTANG_MEMBER_ID")
        or ""
    ).strip()

    from tangtang_runtime import TangTangRuntime

    home = data_dir()
    os.environ.setdefault("TANGTANG_DATA_DIR", home)
    rt = TangTangRuntime()
    obs = {}
    if member:
        obs["audience_id"] = member
    result = rt.handle_living_room(kind, audience_id=member or None, observation=obs)

    # This is a system-initiated scene for an audience, not member-authored activity.

    dump = (os.environ.get("TANGTANG_LIVING_DUMP") or "").strip() == "1"
    if dump:
        print(
            json.dumps(
                {
                    "kind": kind,
                    "decision": result.decision,
                    "member_id": result.member_id,
                    "audience_id": result.observation.get("audience_id"),
                    "text": (result.action.text if result.action else ""),
                    "event_type": result.event.type if result.event else None,
                },
                ensure_ascii=False,
            ),
            file=sys.stderr,
        )

    if result.decision != "SPEAK":
        return 0
    text = (result.action.text if result.action else "") or ""
    if text:
        print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
