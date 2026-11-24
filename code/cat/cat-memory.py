#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""糖糖 · Family Memory 2.0（客厅 Mac 本机）

今天 / 近期变化 / 稳定记忆 / 家庭状态 / 下一步陪伴。
只读已有 cat-habits.json、cat-habit-growth.json、cat-turn-ledger.json，
写出派生 family-state.json（标签，不含小朋友原话）。不调用 LLM。

用法:
  ./cat-memory.py today
  ./cat-memory.py recent
  ./cat-memory.py state
  ./cat-memory.py next
  ./cat-memory.py trends [成员]
  ./cat-memory.py emotion
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

from tangtang_paths import data_dir, now_dt  # noqa: E402


def _home():
    path = data_dir()
    os.environ.setdefault("TANGTANG_DATA_DIR", path)
    return path


def _engine():
    from core.memory.family_memory_v2 import FamilyMemoryV2

    return FamilyMemoryV2(home=_home(), persist=True, clock=now_dt)


def _dump(obj):
    print(json.dumps(obj, ensure_ascii=False, indent=2))


def main(argv=None):
    args = list(sys.argv[1:] if argv is None else argv)
    cmd = args[0] if args else "state"
    if cmd in ("-h", "--help", "help"):
        print(__doc__.strip())
        return 0
    # A CLI target or a local process is not an authenticated Viewer.
    # Keep legacy access only behind explicit migration switches until this
    # command is routed through a trusted Core Viewer issuer.
    if cmd == "trends" and os.environ.get("TANGTANG_ALLOW_LEGACY_MEMBER_MEMORY_CLI") != "1":
        print("成员专属记忆查询已关闭：当前 CLI 没有经过 Core 验证的 viewer 身份。", file=sys.stderr)
        return 2
    if cmd == "next" and len(args) > 1 and os.environ.get("TANGTANG_ALLOW_LEGACY_MEMBER_MEMORY_CLI") != "1":
        print("指定成员的主动陪伴查询已关闭：目标成员不能代替已验证的 viewer 身份。", file=sys.stderr)
        return 2
    family_read_commands = {"today", "recent", "stable", "state", "emotion"}
    if cmd in family_read_commands and os.environ.get("TANGTANG_ALLOW_LEGACY_FAMILY_MEMORY_READ_CLI") != "1":
        print("家庭记忆查询已关闭：当前 CLI 尚未接入经过 Core 授权的 viewer。", file=sys.stderr)
        return 2
    if cmd == "next" and len(args) == 1 and os.environ.get("TANGTANG_ALLOW_LEGACY_FAMILY_MEMORY_READ_CLI") != "1":
        print("家庭级主动陪伴查询已关闭：当前 CLI 尚未接入经过 Core 授权的 viewer。", file=sys.stderr)
        return 2
    eng = _engine()
    now = now_dt()
    if cmd == "today":
        _dump(eng.today_ledger(now))
        return 0
    if cmd == "recent":
        _dump(eng.recent_change(now))
        return 0
    if cmd == "stable":
        _dump(eng.stable_memory())
        return 0
    if cmd == "state":
        _dump(eng.family_state(now, persist=True))
        return 0
    if cmd == "next":
        who = args[1] if len(args) > 1 else ""
        obs = {}
        if who:
            obs["label"] = who
            obs["member_id"] = who
        dec = eng.next_accompany(now, observation=obs or None, channel="remind")
        _dump(dec.as_dict())
        return 0
    if cmd == "trends":
        from core.memory.habit_trends import HabitTrendStore

        who = args[1] if len(args) > 1 else "hanghang"
        store = HabitTrendStore(home=_home(), persist=True)
        _dump({
            "member_id": who,
            "today": store.today(who, now=now),
            "recent_7d": store.recent(who, now=now),
            "stable": store.stable(who),
        })
        return 0
    if cmd == "emotion":
        from core.memory.emotion_drift import EmotionDriftStore

        store = EmotionDriftStore(home=_home(), persist=True)
        _dump(store.current(now=now))
        return 0
    print("用法: today | recent | state | next [成员] | trends [成员] | emotion", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
