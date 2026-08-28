#!/usr/bin/env python3
"""Central quiet-hours gate for proactive speech.

Default quiet window: 22:30-07:00. Interactive requests can bypass it by
setting TANGTANG_INTERACTIVE=1. This gate never deletes/logs events; it only
answers whether TangTang may speak right now.
"""
import datetime, os

START = os.environ.get("TANGTANG_QUIET_START", "22:30")
END = os.environ.get("TANGTANG_QUIET_END", "07:00")


def minutes(value):
    h, m = value.split(":", 1)
    return int(h) * 60 + int(m)


def is_quiet(now=None):
    if os.environ.get("TANGTANG_INTERACTIVE") == "1":
        return False
    now = now or datetime.datetime.now()
    cur = now.hour * 60 + now.minute
    start = minutes(START)
    end = minutes(END)
    if start < end:
        return start <= cur < end
    return cur >= start or cur < end

if __name__ == "__main__":
    print("quiet" if is_quiet() else "speak")
