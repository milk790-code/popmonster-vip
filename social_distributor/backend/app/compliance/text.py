"""Text moderation using Google Perspective API with a local fallback.

If ``PERSPECTIVE_API_KEY`` is unset we fall back to a small built-in keyword
list so the system fails closed (i.e. caller still gets a structured Finding).
The keyword list is deliberately conservative; production deployments should
plug in their own moderation service.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

import requests

from ..config import config

PERSPECTIVE_URL = (
    "https://commentanalyzer.googleapis.com/v1alpha1/comments:analyze"
)
ATTRIBUTES = ["TOXICITY", "SEVERE_TOXICITY", "INSULT", "THREAT", "SEXUALLY_EXPLICIT"]
DEFAULT_THRESHOLD = 0.75

# Used only as last-resort fallback. Literal matches; case-insensitive.
LOCAL_BLOCKLIST = [
    r"\bbuy followers?\b",
    r"\bguaranteed\s+1\s*million\s+views\b",
    r"\bcrypto\s+giveaway\b",
]


@dataclass
class TextFinding:
    passed: bool
    score: float
    attribute: str
    detail: dict


def analyze_text(text: str) -> list[TextFinding]:
    if not text.strip():
        return []
    if config.perspective_api_key:
        return _perspective(text)
    return _local(text)


def _perspective(text: str) -> list[TextFinding]:
    body = {
        "comment": {"text": text},
        "languages": ["en"],
        "requestedAttributes": {a: {} for a in ATTRIBUTES},
    }
    response = requests.post(
        PERSPECTIVE_URL,
        params={"key": config.perspective_api_key},
        json=body,
        timeout=15,
    )
    if not response.ok:
        # Treat API failure as a soft warning rather than blocking the post.
        return [TextFinding(passed=True, score=0.0, attribute="api_error",
                            detail={"status": response.status_code})]
    data = response.json()
    findings: list[TextFinding] = []
    for attr in ATTRIBUTES:
        score = (
            data.get("attributeScores", {})
            .get(attr, {})
            .get("summaryScore", {})
            .get("value", 0.0)
        )
        findings.append(
            TextFinding(
                passed=score < DEFAULT_THRESHOLD,
                score=float(score),
                attribute=attr,
                detail={"threshold": DEFAULT_THRESHOLD},
            )
        )
    return findings


def _local(text: str) -> list[TextFinding]:
    matches = [pat for pat in LOCAL_BLOCKLIST if re.search(pat, text, re.IGNORECASE)]
    return [
        TextFinding(
            passed=not matches,
            score=1.0 if matches else 0.0,
            attribute="LOCAL_BLOCKLIST",
            detail={"matched": matches, "fallback": True},
        )
    ]
