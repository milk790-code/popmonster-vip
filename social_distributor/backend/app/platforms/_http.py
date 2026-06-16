"""HTTP helpers for platform adapters.

B6: ``timeout`` defaults to ``PLATFORM_HTTP_TIMEOUT`` env var (or 60s if
unset). Video upload / IG container poll callsites pass an explicit longer
timeout when needed (these can take 60–120s legitimately).

Proxy support: call ``set_proxy(proxy_url)`` before issuing requests in a
thread to route all ``request_json`` calls through that proxy.  Call
``clear_proxy()`` afterwards.  Tasks use this to give each SocialAccount its
own egress IP without touching individual platform modules.
"""
from __future__ import annotations

import os
import threading
from typing import Any

import requests

from .base import PlatformError

DEFAULT_TIMEOUT = float(os.environ.get("PLATFORM_HTTP_TIMEOUT", "60"))

_proxy_local = threading.local()


def set_proxy(proxy_url: str | None) -> None:
    """Set a per-thread proxy URL for all subsequent request_json calls."""
    _proxy_local.url = proxy_url


def clear_proxy() -> None:
    _proxy_local.url = None


def _current_proxies() -> dict | None:
    url = getattr(_proxy_local, "url", None)
    if not url:
        return None
    return {"http": url, "https": url}


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
    proxies = _current_proxies()
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
            proxies=proxies,
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
