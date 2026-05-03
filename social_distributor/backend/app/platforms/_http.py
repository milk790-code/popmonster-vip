"""HTTP helpers for platform adapters."""
from __future__ import annotations

from typing import Any

import requests

from .base import PlatformError


def request_json(
    method: str,
    url: str,
    *,
    params: dict[str, Any] | None = None,
    data: dict[str, Any] | None = None,
    json: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
    files: dict[str, Any] | None = None,
    timeout: float = 30.0,
) -> dict[str, Any]:
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
