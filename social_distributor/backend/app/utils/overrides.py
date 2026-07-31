"""Whitelist validator for ``PostTarget.overrides`` payloads.

Without this, the Distribute / Schedule endpoints accept any JSON object —
including unknown keys that silently get ignored, or worse, keys with the
wrong type that crash deep inside a publisher (B7). We restrict to the
keys each publisher actually consults; everything else returns 400.

Errors are returned as a single sentence each so the dashboard can render
them inline next to the offending field.
"""
from __future__ import annotations

from typing import Any

# Common keys accepted regardless of platform.
_COMMON_FIELDS = {"caption": str, "title": str}

_PLATFORM_FIELDS: dict[str, dict[str, type | tuple]] = {
    # first_comment: text posted as a comment on our own post right after it
    # publishes. Overrides the account's stored profile for this post only.
    "facebook": {**_COMMON_FIELDS, "first_comment": str},
    "instagram": {
        **_COMMON_FIELDS,
        "as_reel": bool,
    },
    "tiktok": {
        **_COMMON_FIELDS,
        "privacy_level": str,
        "disable_duet": bool,
        "disable_stitch": bool,
        "disable_comment": bool,
        "cover_ts_ms": int,
        "challenges": list,
    },
    "youtube": {
        **_COMMON_FIELDS,
        "tags": list,
        "category_id": (int, str),
        "privacy_status": str,
        "made_for_kids": bool,
        "thumbnail_url": str,
    },
}

_TIKTOK_PRIVACY = {
    "PUBLIC_TO_EVERYONE", "MUTUAL_FOLLOW_FRIENDS",
    "FOLLOWER_OF_CREATOR", "SELF_ONLY",
}
_YOUTUBE_PRIVACY = {"private", "unlisted", "public"}


def validate_overrides(platform: str, overrides: dict[str, Any]) -> list[str]:
    """Return a list of validation errors. Empty list = ok."""
    if not isinstance(overrides, dict):
        return ["overrides must be a JSON object"]
    schema = _PLATFORM_FIELDS.get(platform)
    if schema is None:
        # Unknown platform: be strict — caller passed something we don't know
        # how to validate, so reject any non-empty overrides.
        if overrides:
            return [f"unknown platform: {platform}"]
        return []

    errors: list[str] = []
    for key, value in overrides.items():
        if key not in schema:
            errors.append(f"unknown override key for {platform}: {key}")
            continue
        expected = schema[key]
        if isinstance(expected, tuple):
            if not isinstance(value, expected):
                errors.append(
                    f"{key}: expected {[t.__name__ for t in expected]}, "
                    f"got {type(value).__name__}"
                )
        elif not isinstance(value, expected):
            errors.append(
                f"{key}: expected {expected.__name__}, "
                f"got {type(value).__name__}"
            )

    # Cross-field semantic checks.
    if platform == "tiktok":
        priv = overrides.get("privacy_level")
        if priv is not None and priv not in _TIKTOK_PRIVACY:
            errors.append(
                f"tiktok privacy_level must be one of {sorted(_TIKTOK_PRIVACY)}"
            )
    if platform == "youtube":
        priv = overrides.get("privacy_status")
        if priv is not None and priv not in _YOUTUBE_PRIVACY:
            errors.append(
                f"youtube privacy_status must be one of {sorted(_YOUTUBE_PRIVACY)}"
            )

    return errors
