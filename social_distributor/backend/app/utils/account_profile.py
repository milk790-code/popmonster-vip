"""Per-account operating profile stored in ``SocialAccount.extra``.

One connected account is more than a token. It has a voice, a landing-page
source code, a first comment that seeds engagement, a hand-picked list of
communities its content belongs in, and a role in cross-account support.
Today all of that lives in the operator's head and gets re-decided on every
post. This module gives it a home so the publish pipeline can read it.

``SocialAccount.extra`` is already a JSON column, so this needs no migration.
Reserved keys owned by other subsystems (``proxy_url``) are never touched.

Everything defaults to empty/off. An account with no profile behaves exactly
as it did before this module existed -- that is deliberate: turning on a
first comment or cross-account support across 57 live Pages must be an
explicit, per-account decision, never a side effect of a deploy.
"""
from __future__ import annotations

import re
from copy import deepcopy
from typing import Any

# Keys in ``extra`` owned by other subsystems. Never read, written, or
# returned by the profile endpoints.
RESERVED_KEYS = {"proxy_url", "page_access_token"}

# Where the profile lives inside ``extra``.
PROFILE_KEY = "profile"

MAX_TEXT = 2000
MAX_COMMUNITIES = 60
MAX_COMMENT_POOL = 30

# Roles an account can play when several accounts support one launch.
# leader    -- the account that publishes the original post
# supporter -- may add a substantive comment on the leader's post
# off       -- never participates in cross-account interaction (default)
INTERACTION_ROLES = {"leader", "supporter", "off"}

_URL_RE = re.compile(r"^https://[^\s]+$")


class ProfileError(ValueError):
    """Raised with a human-readable, single-sentence message per problem."""

    def __init__(self, errors: list[str]) -> None:
        super().__init__("; ".join(errors))
        self.errors = errors


def _text(value: Any, field: str, errors: list[str], *, max_len: int = MAX_TEXT) -> str:
    if value is None:
        return ""
    if not isinstance(value, str):
        errors.append(f"{field} must be text")
        return ""
    value = value.strip()
    if len(value) > max_len:
        errors.append(f"{field} is longer than {max_len} characters")
        return value[:max_len]
    return value


def _bool(value: Any, field: str, errors: list[str], *, default: bool = False) -> bool:
    if value is None:
        return default
    if not isinstance(value, bool):
        errors.append(f"{field} must be true or false")
        return default
    return value


def _int(value: Any, field: str, errors: list[str], *, default: int,
         lo: int, hi: int) -> int:
    if value is None:
        return default
    if isinstance(value, bool) or not isinstance(value, int):
        errors.append(f"{field} must be a whole number")
        return default
    if not (lo <= value <= hi):
        errors.append(f"{field} must be between {lo} and {hi}")
        return default
    return value


def _community(raw: Any, index: int, errors: list[str]) -> dict[str, Any] | None:
    """Validate one hand-picked community entry.

    ``url`` is required and must be https -- a community we cannot open in
    one click is not usable in the share hand-off, and a bare domain would
    silently produce a dead link in the operator's checklist.
    """
    where = f"communities[{index}]"
    if not isinstance(raw, dict):
        errors.append(f"{where} must be an object")
        return None

    name = _text(raw.get("name"), f"{where}.name", errors, max_len=200)
    url = _text(raw.get("url"), f"{where}.url", errors, max_len=1000)
    if not name:
        errors.append(f"{where}.name is required")
    if not url:
        errors.append(f"{where}.url is required")
    elif not _URL_RE.match(url):
        errors.append(f"{where}.url must start with https://")

    return {
        "name": name,
        "url": url,
        # Why this community was picked, in the operator's own words. The
        # whole point of a hand-picked list is that the reason survives.
        "why": _text(raw.get("why"), f"{where}.why", errors, max_len=500),
        "topic": _text(raw.get("topic"), f"{where}.topic", errors, max_len=200),
        # Some communities ban outbound links outright. Recording it here is
        # what stops a link-bearing post being suggested for them at all.
        "allows_links": _bool(raw.get("allows_links"), f"{where}.allows_links",
                              errors, default=True),
        "members": _int(raw.get("members"), f"{where}.members", errors,
                        default=0, lo=0, hi=100_000_000),
        # Minimum days between two shares into the same community. This is
        # the single most important anti-spam knob in the whole profile.
        "cadence_days": _int(raw.get("cadence_days"), f"{where}.cadence_days",
                             errors, default=14, lo=1, hi=365),
        "priority": _int(raw.get("priority"), f"{where}.priority", errors,
                         default=3, lo=1, hi=5),
        "last_shared_at": _text(raw.get("last_shared_at"),
                                f"{where}.last_shared_at", errors, max_len=40),
        "active": _bool(raw.get("active"), f"{where}.active", errors, default=True),
    }


def _interaction(raw: Any, errors: list[str]) -> dict[str, Any]:
    if raw is None:
        raw = {}
    if not isinstance(raw, dict):
        errors.append("interaction must be an object")
        raw = {}

    role = _text(raw.get("role"), "interaction.role", errors, max_len=20) or "off"
    if role not in INTERACTION_ROLES:
        errors.append(
            f"interaction.role must be one of {sorted(INTERACTION_ROLES)}"
        )
        role = "off"

    pool_raw = raw.get("comment_pool") or []
    pool: list[str] = []
    if not isinstance(pool_raw, list):
        errors.append("interaction.comment_pool must be a list of texts")
    else:
        if len(pool_raw) > MAX_COMMENT_POOL:
            errors.append(
                f"interaction.comment_pool holds at most {MAX_COMMENT_POOL} entries"
            )
        for i, item in enumerate(pool_raw[:MAX_COMMENT_POOL]):
            text = _text(item, f"interaction.comment_pool[{i}]", errors, max_len=600)
            if not text:
                continue
            # A one-word "推" or an emoji is the exact signature of engagement
            # farming. Requiring substance is a policy safeguard, not styling.
            if len(text) < 8:
                errors.append(
                    f"interaction.comment_pool[{i}] is too short to read as a "
                    "genuine comment (needs at least 8 characters)"
                )
                continue
            pool.append(text)

    return {
        "role": role,
        "max_per_day": _int(raw.get("max_per_day"), "interaction.max_per_day",
                            errors, default=1, lo=0, hi=5),
        "comment_pool": pool,
    }


def validate_profile(raw: Any) -> dict[str, Any]:
    """Normalise a profile payload. Raises :class:`ProfileError` on problems.

    Unknown keys are rejected rather than ignored, so a typo surfaces at the
    API boundary instead of silently doing nothing for weeks.
    """
    if not isinstance(raw, dict):
        raise ProfileError(["profile must be a JSON object"])

    known = {
        "note", "persona", "first_comment", "link_src", "bio", "cta",
        "cover_asset", "avatar_asset", "communities", "interaction",
    }
    errors: list[str] = []
    for key in raw:
        if key not in known:
            errors.append(f"unknown profile field: {key}")

    communities_raw = raw.get("communities") or []
    communities: list[dict[str, Any]] = []
    if not isinstance(communities_raw, list):
        errors.append("communities must be a list")
    else:
        if len(communities_raw) > MAX_COMMUNITIES:
            errors.append(f"communities holds at most {MAX_COMMUNITIES} entries")
        seen_urls: set[str] = set()
        for i, item in enumerate(communities_raw[:MAX_COMMUNITIES]):
            entry = _community(item, i, errors)
            if entry is None:
                continue
            if entry["url"] and entry["url"] in seen_urls:
                errors.append(f"communities[{i}].url is a duplicate")
                continue
            seen_urls.add(entry["url"])
            communities.append(entry)

    profile = {
        "note": _text(raw.get("note"), "note", errors),
        "persona": _text(raw.get("persona"), "persona", errors),
        # Supports a {link} placeholder, filled with the post's link_url.
        "first_comment": _text(raw.get("first_comment"), "first_comment", errors),
        "link_src": _text(raw.get("link_src"), "link_src", errors, max_len=64),
        "bio": _text(raw.get("bio"), "bio", errors),
        "cta": _text(raw.get("cta"), "cta", errors, max_len=200),
        "cover_asset": _text(raw.get("cover_asset"), "cover_asset", errors, max_len=1000),
        "avatar_asset": _text(raw.get("avatar_asset"), "avatar_asset", errors, max_len=1000),
        "communities": communities,
        "interaction": _interaction(raw.get("interaction"), errors),
    }

    if errors:
        raise ProfileError(errors)
    return profile


def empty_profile() -> dict[str, Any]:
    return {
        "note": "", "persona": "", "first_comment": "", "link_src": "",
        "bio": "", "cta": "", "cover_asset": "", "avatar_asset": "",
        "communities": [],
        "interaction": {"role": "off", "max_per_day": 1, "comment_pool": []},
    }


def read_profile(account) -> dict[str, Any]:
    """Return a detached copy of the account's profile, defaults filled.

    The copy is deep on purpose. Returning live references into
    ``account.extra`` makes read-modify-write silently no-op: the caller
    mutates the stored dict in place, so by the time ``write_profile``
    reassigns ``extra`` the new value already equals the old one and
    SQLAlchemy emits no UPDATE.
    """
    stored = (account.extra or {}).get(PROFILE_KEY) or {}
    if not isinstance(stored, dict):
        return empty_profile()
    merged = empty_profile()
    for key, value in stored.items():
        if key in merged:
            merged[key] = deepcopy(value)
    return merged


def write_profile(account, profile: dict[str, Any]) -> None:
    """Persist a validated profile, preserving keys owned elsewhere.

    ``extra`` must be reassigned rather than mutated in place -- SQLAlchemy
    does not track in-place mutation of a plain JSON column, so mutating it
    would commit nothing.
    """
    extra = dict(account.extra or {})
    extra[PROFILE_KEY] = profile
    account.extra = extra
