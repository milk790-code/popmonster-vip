"""HTTP helpers for platform adapters.

B6: ``timeout`` defaults to ``PLATFORM_HTTP_TIMEOUT`` env var (or 60s if
unset). Video upload / IG container poll callsites pass an explicit longer
timeout when needed (these can take 60–120s legitimately).
"""
from __future__ import annotations

import os
from typing import Any

import requests

from .base import PlatformError

DEFAULT_TIMEOUT = float(os.environ.get("PLATFORM_HTTP_TIMEOUT", "60"))


def request_json(
    method: str,
    url: str,
    *,
    params: dict[str, Any] | None = None,
    data: dict[str, Any] | None = None,
    json: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
    files: dict[str, Any] | None = None,
    timeout: float | None = None,
) -> dict[str, Any]:
    if timeout is None:
        timeout = DEFAULT_TIMEOUT
    try:
        response = requests.request(
            method,
            url,
            params=params,
            data=data,
            json=json,
            headers=headers,
            files=files,
            timeout=timeout,
        )
    except requests.RequestException as exc:
        raise PlatformError(f"network failure calling {url}", retryable=True) from exc

    retryable = response.status_code in (408, 425, 429, 500, 502, 503, 504)
    if not response.ok:
        body = response.text[:500]
        raise PlatformError(
            f"{method} {url} returned {response.status_code}: {body}",
            retryable=retryable,
            status_code=response.status_code,
        )
    if not response.content:
        return {}
    try:
        return response.json()
    except ValueError as exc:
        raise PlatformError(
            f"non-JSON response from {url}", retryable=False
        ) from exc
