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


QIAQIA_ALIASES = ("qiaqia", "洽洽", "6", "grade6", "g6", "姐姐")
HANGHANG_ALIASES = ("hanghang", "航航", "2", "grade2", "g2", "弟弟")
# 测验腔：命中则退回伴读句。不匹配「不听写」这类否定。
QUIZ_MARKERS = (
    "现在开始测试",
    "开始测验",
    "跟我读",
    "repeat after me",
    "你的分数",
    "打分",
    "答对了",
    "我来检查",
    "必须跟读",
    "再说一遍我检查",
)


def resolve_who(who=""):
    """时刻表参数 / TANGTANG_MEMBER_ID 优先。口吻 friend 不能把航航改成洽洽。"""
    w = (
        who
        or os.environ.get("TANGTANG_MEMBER_ID")
        or os.environ.get("TANGTANG_SPEAKER")
        or ""
    ).strip().lower()
    if w in QIAQIA_ALIASES:
        return "qiaqia"
    if w in HANGHANG_ALIASES:
        return "hanghang"
    return "hanghang"


def looks_like_quiz(text):
    t = (text or "").strip()
    if not t:
        return False
    low = t.lower()
    return any(m in t or m in low for m in QUIZ_MARKERS)


def companion_line(text, who=""):
    """弱伴读：去掉测验/督学腔，保留给选择的短句。"""
    t = (text or "").strip()
    if not t or looks_like_quiz(t):
        return fallback_line(who)
    return t


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


def iter_items(who="", when=None):
    lib = load_library()
    who = resolve_who(who)
    when = when or current_when()
    if who == "qiaqia":
        grade = lib.get("grade6") or {}
    else:
        grade = lib.get("grade2") or {}
    term = term_key(when)
    items = grade.get(term) or []
    for idx, item in enumerate(items):
        lid = (item.get("id") or "").strip() or "en_%s_%s_%d" % (who, term, idx)
        yield lid, item


def fallback_line(who):
    who = resolve_who(who)
    if who == "qiaqia":
        return "糖糖想跟你玩一个英语词。愿意再说，不愿意也没关系。"
    return "糖糖想学一个英语词。你要不要当小老师？不学也行。"


def pick_with_id(who="", when=None, preferred_id=None):
    who = resolve_who(who)
    when = when or current_when()
    rows = list(iter_items(who, when))
    if not rows:
        return fallback_line(who), ""
    pref = (preferred_id or "").strip()
    if pref:
        for lid, item in rows:
            text = companion_line((item.get("say") or "").strip(), who)
            if lid == pref and text:
                return text, lid
    idx = when.timetuple().tm_yday % len(rows)
    lid, item = rows[idx]
    return companion_line((item.get("say") or "").strip(), who), lid


def pick_line(who="", when=None, preferred_id=None):
    text, _lid = pick_with_id(who, when, preferred_id=preferred_id)
    return text


def _selftest():
    lib = load_library()
    assert lib.get("grade2") and lib.get("grade6"), "missing grades"
    assert resolve_who("洽洽") == "qiaqia"
    assert resolve_who("qiaqia") == "qiaqia"
    assert resolve_who("g6") == "qiaqia"
    assert resolve_who("hanghang") == "hanghang"
    os.environ["TANGTANG_MEMBER_ID"] = "qiaqia"
    os.environ["TANGTANG_PROFILE"] = "play"
    assert resolve_who("") == "qiaqia", "explicit member must win over play default"
    os.environ["TANGTANG_MEMBER_ID"] = "hanghang"
    os.environ["TANGTANG_PROFILE"] = "friend"
    assert resolve_who("") == "hanghang", "friend mouth must not remap hanghang"
    os.environ.pop("TANGTANG_MEMBER_ID", None)
    os.environ.pop("TANGTANG_PROFILE", None)
    a = pick_line("hanghang", datetime(2026, 9, 1))
    b = pick_line("qiaqia", datetime(2026, 9, 1))
    assert a and b and a != b, (a, b)
    assert "aunt" in a.lower() or "dog" in a.lower() or "rabbit" in a.lower() or "tail" in a.lower() or "autumn" in a.lower() or "juice" in a.lower() or "school" in a.lower() or "clean" in a.lower() or "doctor" in a.lower()
    feb = pick_line("hanghang", datetime(2027, 3, 1))
    assert feb
    for lid, item in list(iter_items("hanghang", datetime(2026, 9, 1))) + list(iter_items("qiaqia", datetime(2026, 9, 1))):
        say = (item.get("say") or "")
        assert not looks_like_quiz(say), (lid, say)
        assert "正确" not in say and "打分" not in say
    assert looks_like_quiz("跟我读 apple，我来检查")
    assert companion_line("跟我读 apple，我来检查", "hanghang") == fallback_line("hanghang")
    print("cat-english selftest ok")
    print("hanghang Sep1:", a)
    print("qiaqia Sep1:", b)


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] in ("--selftest", "selftest"):
        _selftest()
    else:
        who = sys.argv[1] if len(sys.argv) > 1 else ""
        print(pick_line(who))
