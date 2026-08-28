"""Resolve an observation to a family member_id.

Event does not embed this resolver. Voiceprint is never the primary path:
school hours + presence + optional coarse features win. family.json is
injected by the caller — this module does not open files.
"""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

# Product living-room names. Do not rewrite data/family.json this round.
# 12岁姐姐 → qiaqia, 9岁弟弟 → hanghang, 妈妈 → mom.
PRODUCT_GROUPS: dict[str, frozenset[str]] = {
    "qiaqia": frozenset({
        "qiaqia", "洽洽", "child_12", "姐姐", "12岁姐姐", "12岁女孩", "girl",
    }),
    "hanghang": frozenset({
        "hanghang", "航航", "child_9", "弟弟", "9岁弟弟", "9岁男孩", "boy",
    }),
    "mom": frozenset({"mom", "妈妈", "妈", "mother"}),
    "dad": frozenset({"dad", "爸爸", "爸", "父亲", "father"}),
    "grandpa": frozenset({"grandpa", "爷爷", "外公", "grandfather"}),
    "grandma": frozenset({"grandma", "奶奶", "外婆", "grandmother"}),
}

CHILD_PRODUCTS = frozenset({"qiaqia", "hanghang", "child_12", "child_9"})


def _norm(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


class IdentityResolver:
    def __init__(self, members: Mapping[str, object] | None = None) -> None:
        self.members = dict(members or {})
        self._label_index: dict[str, str] = {}
        self._build_index()

    def _build_index(self) -> None:
        index: dict[str, str] = {}
        for member_id, rec in self.members.items():
            labels = {member_id}
            if isinstance(rec, Mapping):
                display = rec.get("display_name")
                if display:
                    labels.add(str(display))
                for alias in rec.get("aliases") or []:
                    labels.add(str(alias))
            product = None
            for prod, group in PRODUCT_GROUPS.items():
                if labels & group or member_id in group:
                    labels |= set(group)
                    labels.add(prod)
                    product = prod
                    break
            for label in labels:
                index[label] = member_id
                index[label.lower()] = member_id
            if product:
                index[product] = member_id
        # If registry is empty, still resolve product aliases.
        if not self.members:
            for product, group in PRODUCT_GROUPS.items():
                for label in set(group) | {product}:
                    index[label] = product
                    index[label.lower()] = product
        self._label_index = index

    def _lookup(self, raw: str | None) -> str | None:
        key = _norm(raw)
        if not key:
            return None
        if key in self._label_index:
            return self._label_index[key]
        return self._label_index.get(key.lower())

    def _is_child(self, member_id: str | None) -> bool:
        if not member_id:
            return False
        if member_id in CHILD_PRODUCTS:
            return True
        rec = self.members.get(member_id)
        if isinstance(rec, Mapping):
            if rec.get("relation") == "child":
                return True
            if rec.get("age") in (9, 12):
                return True
        return False

    def is_child(self, member_id: str | None) -> bool:
        """Public: hanghang / 弟弟 / child_9 (and sister aliases) are children."""
        if not member_id:
            return False
        canonical = self._lookup(member_id) or member_id
        if self._is_child(canonical) or self._is_child(member_id):
            return True
        for prod, group in PRODUCT_GROUPS.items():
            if prod in CHILD_PRODUCTS and (member_id in group or canonical in group):
                return True
        return False

    def resolve(self, observation: Mapping[str, Any] | str | None) -> str | None:
        """Read observation → member_id. Strings are treated as a label only."""
        if observation is None:
            return None
        if isinstance(observation, str):
            observation = {"label": observation}
        if not isinstance(observation, Mapping) or not observation:
            return None

        voiceprint = _norm(
            observation.get("voiceprint_id") or observation.get("voiceprint")
        )
        presence = _norm(
            observation.get("presence_member_id")
            or (observation.get("presence") if isinstance(observation.get("presence"), str) else None)
        )
        label = _norm(
            observation.get("label")
            or observation.get("member_id")
            or observation.get("speaker")
        )
        coarse = observation.get("coarse_features")
        if not isinstance(coarse, Mapping):
            coarse = {}

        # Voiceprint alone is never enough.
        has_non_voice = bool(presence or label or coarse)
        if voiceprint and not has_non_voice:
            return None

        candidate = self._lookup(presence) or self._lookup(label)

        if candidate is None and coarse:
            guess = _norm(coarse.get("role_guess") or coarse.get("age_band"))
            candidate = self._lookup(guess)

        at_school = bool(observation.get("school_hours") or observation.get("at_school"))
        presence_home = observation.get("presence_home")
        if at_school and self._is_child(candidate) and presence_home is False:
            return None

        return candidate
