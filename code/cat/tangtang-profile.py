#!/usr/bin/env python3
"""Resolve a family member to a stable TangTang persona.

Usage:
  python3 tangtang-profile.py --speaker child_9
  python3 tangtang-profile.py --speaker "爷爷"

Output is shell-friendly KEY=VALUE lines when --shell is used.
"""
import argparse, json, os

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
FAMILY_FILE = os.path.join(ROOT, "data", "family.json")

DEFAULT = {"member_id": "unknown", "display_name": "小朋友", "profile": "play", "relation": "unknown"}


def load_family():
    try:
        with open(FAMILY_FILE, encoding="utf-8") as f:
            data = json.load(f)
        return data.get("members", [])
    except Exception:
        return []


def resolve(speaker):
    speaker = (speaker or "unknown").strip()
    if speaker in ("", "unknown", "访客"):
        return dict(DEFAULT)
    for m in load_family():
        values = {str(m.get("member_id", "")), str(m.get("display_name", "")), str(m.get("relation", ""))}
        values.update(str(x) for x in m.get("aliases", []))
        if speaker in values:
            return {
                "member_id": m.get("member_id", "unknown"),
                "display_name": m.get("display_name", "小朋友"),
                "profile": m.get("profile", "play"),
                "relation": m.get("relation", "unknown"),
            }
    return dict(DEFAULT)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--speaker", default=os.environ.get("TANGTANG_SPEAKER", "unknown"))
    ap.add_argument("--shell", action="store_true")
    args = ap.parse_args()
    r = resolve(args.speaker)
    if args.shell:
        for k, v in r.items():
            print(f"TANGTANG_{k.upper()}={json.dumps(str(v), ensure_ascii=False)}")
    else:
        print(json.dumps(r, ensure_ascii=False))

if __name__ == "__main__":
    main()
