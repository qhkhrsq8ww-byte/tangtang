#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""糖糖 · 江苏译林英语小伴读（适当，不督学）

航航：小学二年级；洽洽：小学六年级。
中英夹一句，给选择，不测验、不比较。
"""
import json
import os
import sys
from datetime import datetime

CAT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_DATA = os.path.abspath(os.path.join(CAT_DIR, "..", "..", "data"))


def library_path():
    env = (os.environ.get("TANGTANG_ENGLISH_FILE") or "").strip()
    for p in (
        env,
        os.path.join(CAT_DIR, "english_jiangsu.json"),
        os.path.join(REPO_DATA, "english_jiangsu.json"),
    ):
        if p and os.path.isfile(p):
            return p
    return None


def load_library():
    path = library_path()
    if not path:
        return {}
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def resolve_who(who=""):
    w = (who or os.environ.get("TANGTANG_MEMBER_ID") or "").strip().lower()
    if w in ("qiaqia", "洽洽", "6", "grade6", "g6"):
        return "qiaqia"
    if w in ("hanghang", "航航", "2", "grade2", "g2"):
        return "hanghang"
    profile = (os.environ.get("TANGTANG_PROFILE") or "").strip().lower()
    if profile == "friend":
        return "qiaqia"
    return "hanghang"


def current_when():
    fake = (os.environ.get("TANGTANG_FAKE_TODAY") or "").strip()
    if fake:
        try:
            return datetime.strptime(fake, "%Y-%m-%d")
        except ValueError:
            pass
    return datetime.now()


def term_key(when=None):
    """9月-次年1月用上册 book_a；2-7月用下册 book_b。"""
    when = when or datetime.now()
    m = when.month
    if 2 <= m <= 7:
        return "book_b"
    return "book_a"


def pick_line(who="", when=None):
    lib = load_library()
    who = resolve_who(who)
    when = when or current_when()
    if who == "qiaqia":
        grade = lib.get("grade6") or {}
    else:
        grade = lib.get("grade2") or {}
    items = grade.get(term_key(when)) or []
    if not items:
        if who == "qiaqia":
            return "糖糖想跟你玩一个英语词。愿意再说，不愿意也没关系。"
        return "糖糖想学一个英语词。你要不要当小老师？不学也行。"
    idx = when.timetuple().tm_yday % len(items)
    item = items[idx]
    return (item.get("say") or "").strip()


def _selftest():
    lib = load_library()
    assert lib.get("grade2") and lib.get("grade6"), "missing grades"
    a = pick_line("hanghang", datetime(2026, 9, 1))
    b = pick_line("qiaqia", datetime(2026, 9, 1))
    assert a and b and a != b, (a, b)
    assert "aunt" in a.lower() or "dog" in a.lower() or "rabbit" in a.lower() or "tail" in a.lower() or "autumn" in a.lower() or "juice" in a.lower() or "school" in a.lower() or "clean" in a.lower() or "doctor" in a.lower()
    feb = pick_line("hanghang", datetime(2027, 3, 1))
    assert feb
    print("cat-english selftest ok")
    print("hanghang Sep1:", a)
    print("qiaqia Sep1:", b)


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] in ("--selftest", "selftest"):
        _selftest()
    else:
        who = sys.argv[1] if len(sys.argv) > 1 else ""
        print(pick_line(who))
