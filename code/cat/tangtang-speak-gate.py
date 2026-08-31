#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""CLI + live observation for the one speak-or-not path.

Prints `speak` or `silent`. Used by cat-voice / cat.sh / cat-talk / cat-chat
before STT or LLM. Alarm channel is always speak.
"""
from __future__ import annotations

import argparse
import importlib.util
import os
import sys
from datetime import datetime

CAT_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(CAT_DIR, "..", ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
if CAT_DIR not in sys.path:
    sys.path.insert(0, CAT_DIR)

from tangtang_paths import now_dt  # noqa: E402


def _presence():
    path = os.path.join(CAT_DIR, "cat-presence.py")
    spec = importlib.util.spec_from_file_location("tangtang_presence_gate", path)
    if spec is None or spec.loader is None:
        return None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def live_observation(member=None, extra=None):
    """Wall / FAKE clock + school-hours flags. No LLM."""
    obs = dict(extra or {})
    mid = (
        member
        or obs.get("member_id")
        or obs.get("label")
        or os.environ.get("TANGTANG_MEMBER_ID")
        or os.environ.get("TANGTANG_SPEAKER")
        or ""
    )
    mid = str(mid).strip()
    if mid and mid.lower() not in ("unknown", "访客", "guest"):
        obs.setdefault("label", mid)
        obs.setdefault("member_id", mid)
    now = obs.get("now")
    if not isinstance(now, datetime):
        now = now_dt()
        obs["now"] = now
    obs["live"] = True
    try:
        pres = _presence()
        if pres is not None and mid:
            who = pres.canonical_member(mid)
            if who and pres.is_child(who) and pres.child_at_school(who):
                obs["school_hours"] = True
                obs["at_school"] = True
                obs["audience_child"] = True
                obs["presence_home"] = False
    except Exception:
        pass
    return obs


def check_speak(channel="chat", member=None, event=None, extra=None):
    """SPEAK or not. alarm / event=alarm never silent."""
    ev = (event or "").strip().lower()
    ch = (channel or "chat").strip().lower()
    if ev == "alarm" or ch == "alarm":
        return "SPEAK"
    from core.policy.speak_gate import decide

    extra = dict(extra or {})
    if ch in ("chat", "voice"):
        extra.setdefault("interactive", True)
    elif ch == "remind":
        extra.setdefault("interactive", False)
    obs = live_observation(member, extra)
    return decide(obs, now=obs.get("now"), channel=ch, live=True)


def main(argv=None):
    ap = argparse.ArgumentParser(description="Tangtang speak-or-not gate")
    ap.add_argument("--channel", default="chat", help="chat|voice|remind|alarm")
    ap.add_argument("--member", default="", help="family member id")
    ap.add_argument("--event", default="", help="brain event (alarm is never gated)")
    args = ap.parse_args(argv)
    decision = check_speak(
        channel=args.channel,
        member=args.member or None,
        event=args.event or None,
    )
    print("speak" if decision == "SPEAK" else "silent")
    return 0 if decision == "SPEAK" else 0


if __name__ == "__main__":
    sys.exit(main())
