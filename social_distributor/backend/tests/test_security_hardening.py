"""CRIT auth-layer hardening regressions.

Covers the boot-time fail-closed SECRET_KEY check and the CORS allow-list —
the two fixes that aren't exercised by the per-endpoint IDOR/login tests.
"""
import pytest

from app.config import Config, _require_secret_key


def test_secret_key_unset_fails_closed(monkeypatch):
    monkeypatch.delenv("SECRET_KEY", raising=False)
    with pytest.raises(RuntimeError):
        _require_secret_key()
    # A full Config() construction must also refuse to build.
    with pytest.raises(RuntimeError):
        Config()


def test_secret_key_dev_default_fails_closed(monkeypatch):
    monkeypatch.setenv("SECRET_KEY", "dev-secret")
    with pytest.raises(RuntimeError):
        _require_secret_key()
    with pytest.raises(RuntimeError):
        Config()


def test_secret_key_empty_fails_closed(monkeypatch):
    monkeypatch.setenv("SECRET_KEY", "")
    with pytest.raises(RuntimeError):
        _require_secret_key()


def test_secret_key_real_value_boots(monkeypatch):
    monkeypatch.setenv("SECRET_KEY", "a-real-secret-value")
    assert _require_secret_key() == "a-real-secret-value"
    assert Config().secret_key == "a-real-secret-value"


def test_cors_does_not_reflect_wildcard_with_credentials(monkeypatch):
    """An explicit `*` must NOT be served back with credentials."""
    monkeypatch.setenv("CORS_ALLOWED_ORIGINS", "*")
    from app import create_app

    app = create_app()
    client = app.test_client()
    res = client.get(
        "/healthz",
        headers={"Origin": "https://evil.example.com"},
    )
    # CORS must not echo the attacker origin nor a bare wildcard with creds.
    allow_origin = res.headers.get("Access-Control-Allow-Origin")
    assert allow_origin != "https://evil.example.com"
    assert allow_origin != "*"


def test_cors_allows_configured_origin(monkeypatch):
    monkeypatch.setenv("CORS_ALLOWED_ORIGINS", "https://app.example.com")
    from app import create_app

    app = create_app()
    client = app.test_client()
    res = client.get(
        "/healthz",
        headers={"Origin": "https://app.example.com"},
    )
    assert res.headers.get("Access-Control-Allow-Origin") == "https://app.example.com"
