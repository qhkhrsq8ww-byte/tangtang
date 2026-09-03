"""family — V3 家庭成员门面（实现位于 core.identity / core.adapters）。"""

from core.adapters.family_loader import load_family_document, load_members, require_members
from core.identity.resolver import IdentityResolver
from family.identity_resolver import IdentityResolver as VoiceAwareIdentityResolver

__all__ = [
    "IdentityResolver",
    "VoiceAwareIdentityResolver",
    "load_members",
    "load_family_document",
    "require_members",
]
