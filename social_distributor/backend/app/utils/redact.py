"""Redact secret-like substrings from audit / log payloads.

We never want OAuth tokens, refresh tokens, or Authorization headers ending
up in ``audit_logs.detail`` or ``compliance_checks.findings.raw``. Platform
APIs sometimes echo back tokens in error responses (TikTok in particular),
so a best-effort regex sweep is the only realistic defence.
"""
from __future__ import annotations

import re
from typing import Any

# Keys that should always be masked when they appear in dict structures.
_SENSITIVE_KEYS = {
    "access_token", "refresh_token", "page_access_token",
    "client_secret", "Authorization", "authorization",
    "appsecret_proof", "code", "id_token",
}

# Token-shaped substrings to mask in any string value.
_TOKEN_PATTERNS = [
    re.compile(r"EAA[0-9A-Za-z_-]{30,}"),                  # Meta tokens
    re.compile(r"act\.[0-9A-Za-z._-]{30,}"),               # TikTok tokens
    re.compile(r"ya29\.[0-9A-Za-z_-]{30,}"),               # Google tokens
    re.compile(r"ghp_[0-9A-Za-z]{30,}"),                   # GitHub PATs
    re.compile(r"github_pat_[0-9A-Za-z_]{40,}"),           # GitHub fine-grained
    re.compile(r"sk-ant-[0-9A-Za-z_-]{20,}"),              # Anthropic
]

MASK = "***"


def redact(value: Any) -> Any:
    """Recursively walk ``value`` masking secret-like content.

    Returns a new structure; never mutates input. Lists / tuples preserve
    order; dicts preserve key set. Non-collection values are stringified
    and pattern-swept.
    """
    if isinstance(value, dict):
        return {
            k: (MASK if k in _SENSITIVE_KEYS else redact(v))
            for k, v in value.items()
        }
    if isinstance(value, (list, tuple)):
        cls = type(value)
        return cls(redact(v) for v in value)
    if isinstance(value, str):
        return _redact_string(value)
    return value


def _redact_string(s: str) -> str:
    out = s
    for pat in _TOKEN_PATTERNS:
        out = pat.sub(MASK, out)
    return out
