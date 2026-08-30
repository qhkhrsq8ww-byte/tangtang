#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""糖糖 · 隐私与存储策略层（存储层拦截）

架构：
  Event
    ↓
  PrivacyPolicy (resolve_policy)
    ↓
  StoragePolicy (scrub_text / filter_*)
    ↓
  Habit / Memory / Summary / Context

核心原则：儿童 PRIVATE 原话**禁止**进入任何持久化存储。
身份→人格（tangtang-profile.py）与身份→隐私策略（本模块）解耦但共享 family.json。

存储级别：
  PRIVATE  self_private=true  → 禁止原话落盘（habit store / summary / parent context 全隔离）
  FAMILY   family_summary=true → 可进家庭摘要，但永远不含原话
  PUBLIC   默认               → 普通事件流

注意：结构化信息（谁、何时、时长、活跃时段）仍保留，仅原话文本被拦截。
"""
import json
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
FAMILY_FILE = os.path.join(ROOT, "data", "family.json")

PUBLIC = "PUBLIC"
FAMILY = "FAMILY"
PRIVATE = "PRIVATE"

DEFAULT = {
    "member_id": "unknown",
    "display_name": "访客",
    "profile": "play",
    "relation": "unknown",
    "permissions": {"self_private": False, "family_summary": False},
}


def load_family():
    try:
        with open(FAMILY_FILE, encoding="utf-8") as f:
            return json.load(f).get("members", [])
    except Exception:
        return []


def _canonical_speaker(speaker):
    """Map living-room aliases (hanghang/qiaqia) onto family.json ids without renaming."""
    if not speaker:
        return speaker
    try:
        if ROOT not in sys.path:
            sys.path.insert(0, ROOT)
        from core.identity.resolver import IdentityResolver

        members = {}
        for row in load_family():
            mid = row.get("member_id")
            if mid:
                members[str(mid)] = row
        resolved = IdentityResolver(members).resolve({"label": speaker})
        if resolved:
            return resolved
    except Exception:
        pass
    return speaker


def resolve_member(speaker):
    """返回含 permissions 的完整成员描述（基础字段，供 profile 层使用）。"""
    speaker = _canonical_speaker((speaker or "unknown").strip())
    if speaker in ("", "unknown", "访客"):
        return dict(DEFAULT)
    for m in load_family():
        values = {
            str(m.get("member_id", "")),
            str(m.get("display_name", "")),
            str(m.get("relation", "")),
        }
        values.update(str(x) for x in m.get("aliases", []))
        if speaker in values:
            return {
                "member_id": m.get("member_id", "unknown"),
                "display_name": m.get("display_name", "访客"),
                "profile": m.get("profile", "play"),
                "relation": m.get("relation", "unknown"),
                "permissions": m.get("permissions", {"self_private": False, "family_summary": False}),
            }
    return dict(DEFAULT)


def storage_policy(member):
    """由成员权限推导存储级别。

    优先级：family_summary > self_private > 默认
      - family_summary=true  → FAMILY（可进家庭摘要，但永远不含原话）
      - 仅 self_private=true → PRIVATE（完全私密，本人上下文以外均隔离）
      - 二者皆无            → PUBLIC（普通事件流）
    """
    perms = member.get("permissions", {})
    sp = bool(perms.get("self_private"))
    fs = bool(perms.get("family_summary"))
    if fs:
        return FAMILY
    if sp:
        return PRIVATE
    return PUBLIC


def policy_for(speaker):
    """对外统一接口：返回给定说话人的完整策略决策。

    包含基础字段（member_id/display_name/profile/relation/permissions）
    与 storage 决策字段（storage/allow_raw_text/allow_family_summary/allow_parent_context）。
    """
    member = resolve_member(speaker)
    policy = storage_policy(member)
    allow_raw = policy == PUBLIC
    return {
        "member_id": member["member_id"],
        "display_name": member["display_name"],
        "profile": member["profile"],
        "relation": member["relation"],
        "permissions": member["permissions"],
        "storage": policy,
        "allow_raw_text": allow_raw,
        "allow_family_summary": policy in (FAMILY, PUBLIC),
        "allow_parent_context": allow_raw,
    }


def scrub_text(text, storage):
    """存储层拦截：PRIVATE 成员的原话一律清空，其他级别保留。"""
    if storage == PRIVATE:
        return ""
    return (text or "").strip()


def filter_summary_texts(entries, display_name=None):
    """家庭摘要时，过滤掉 PRIVATE 成员的原话文本。

    返回可用于摘要的 entries（PRIVATE 成员只保留结构化信息，text 置空）。
    """
    out = []
    for e in entries:
        name = e.get("name", "unknown")
        pol = policy_for(name)
        item = dict(e)
        if not pol["allow_family_summary"] or not pol["allow_raw_text"]:
            item["text"] = ""
        out.append(item)
    return out


def build_parent_context(exclude_private=True):
    """为家长（爸爸/妈妈）构建上下文时，排除 PRIVATE 成员的原话。

    返回结构化、不含原话的家庭状态描述。
    """
    ctx = []
    for m in load_family():
        name = m.get("display_name", "未知")
        pol = policy_for(name)
        if exclude_private and not pol["allow_parent_context"]:
            ctx.append(f"{name}：互动数据受隐私保护，不展示原话")
        else:
            ctx.append(f"{name}：关系={m.get('relation')}，人格={m.get('profile')}")
    return "\n".join(ctx)


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--speaker", default="unknown")
    ap.add_argument("--shell", action="store_true")
    args = ap.parse_args()
    p = policy_for(args.speaker)
    if args.shell:
        # 兼容 tangtang-profile.py --shell 输出格式
        for k in ["member_id", "display_name", "profile", "relation", "permissions", "storage"]:
            print(f"TANGTANG_{k.upper()}={json.dumps(p[k], ensure_ascii=False)}")
    else:
        print(json.dumps(p, ensure_ascii=False))


if __name__ == "__main__":
    main()
