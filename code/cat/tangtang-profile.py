#!/usr/bin/env python3
"""Resolve a family member to a stable TangTang persona + privacy permissions.

Usage:
  python3 tangtang-profile.py --speaker child_9
  python3 tangtang-profile.py --speaker "爷爷"

Output is shell-friendly KEY=VALUE lines when --shell is used.
Persona 与隐私权限（self_private / family_summary）统一由 family.json 驱动，
由 tangtang-privacy.py 提供解析与存储策略，避免重复实现。
"""
import argparse, json, os

# 复用隐私层解析（同一 family.json、同一成员匹配逻辑）
import importlib.util
_PRIV_SPEC = importlib.util.spec_from_file_location(
    "tangtang_privacy", os.path.join(os.path.dirname(os.path.abspath(__file__)), "tangtang-privacy.py"))
_PRIV = importlib.util.module_from_spec(_PRIV_SPEC)
_PRIV_SPEC.loader.exec_module(_PRIV)

DEFAULT = {"member_id": "unknown", "display_name": "小朋友", "profile": "play", "relation": "unknown"}


def resolve(speaker):
    """返回成员基础信息 + permissions + storage 策略。"""
    member = _PRIV.resolve_member(speaker)
    policy = _PRIV.policy_for(speaker)
    return {
        "member_id": member.get("member_id", "unknown"),
        "display_name": member.get("display_name", "小朋友"),
        "profile": member.get("profile", "play"),
        "relation": member.get("relation", "unknown"),
        "permissions": member.get("permissions", {}),
        "storage": policy["storage"],
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--speaker", default=os.environ.get("TANGTANG_SPEAKER", "unknown"))
    ap.add_argument("--shell", action="store_true")
    args = ap.parse_args()
    r = resolve(args.speaker)
    if args.shell:
        for k, v in r.items():
            print(f"TANGTANG_{k.upper()}={json.dumps(v, ensure_ascii=False)}")
    else:
        print(json.dumps(r, ensure_ascii=False))


if __name__ == "__main__":
    main()
