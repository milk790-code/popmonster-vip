"""Phase 7B hardening fixes: race lock, 401 handling, IG EXPIRED retry,
Meta refresh, redaction, timeout config, overrides whitelist."""
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest

from app.extensions import db
from app.models import (
    JobStatus,
    Platform,
    Post,
    PostTarget,
    SocialAccount,
    User,
)
from app.platforms.base import PlatformError, TokenBundle
from app.utils.audit import record as audit_record
from app.utils.overrides import validate_overrides
from app.utils.redact import redact


# -- B2: refresh distinguishes 401 from 5xx ----------------------------

def test_refresh_oauth_marks_account_revoked_on_401(app):
    from app.scheduler import tasks
    from app.utils.crypto import cipher

    with app.app_context():
        user = User(email="b2@example.com", display_name="b2")
        db.session.add(user); db.session.flush()
        c = cipher()
        account = SocialAccount(
            user_id=user.id, platform=Platform.YOUTUBE,
            external_account_id="x", handle="x",
            access_token_enc=c.encrypt("a"),
            refresh_token_enc=c.encrypt("r"),
            token_expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
        )
        db.session.add(account); db.session.commit()
        account_id = account.id

    fake_provider = MagicMock()
    fake_provider.refresh.side_effect = PlatformError(
        "invalid_token", retryable=False, status_code=401,
    )
    with patch("app.scheduler.tasks.get_oauth_provider", return_value=fake_provider):
        tasks.refresh_oauth_tokens()

    with app.app_context():
        a = db.session.get(SocialAccount, account_id)
        assert a.revoked_at is not None
        # Token NOT updated (still the old encrypted "a")
        assert cipher().decrypt(a.access_token_enc) == "a"


def test_refresh_oauth_keeps_account_alive_on_5xx(app):
    """5xx errors are transient; account should stay live for next tick."""
    from app.scheduler import tasks
    from app.utils.crypto import cipher

    with app.app_context():
        user = User(email="b2b@example.com", display_name="b2b")
        db.session.add(user); db.session.flush()
        c = cipher()
        account = SocialAccount(
            user_id=user.id, platform=Platform.YOUTUBE,
            external_account_id="x", handle="x",
            access_token_enc=c.encrypt("a"),
            refresh_token_enc=c.encrypt("r"),
            token_expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
        )
        db.session.add(account); db.session.commit()
        account_id = account.id

    fake_provider = MagicMock()
    fake_provider.refresh.side_effect = PlatformError(
        "google upstream down", retryable=True, status_code=503,
    )
    with patch("app.scheduler.tasks.get_oauth_provider", return_value=fake_provider):
        tasks.refresh_oauth_tokens()

    with app.app_context():
        a = db.session.get(SocialAccount, account_id)
        assert a.revoked_at is None  # still alive


# -- B3: IG container EXPIRED is retryable ----------------------------

def test_ig_container_expired_is_retryable():
    from app.platforms.instagram import InstagramPublisher

    pub = InstagramPublisher()
    fake_status = {"status_code": "EXPIRED"}
    with patch("app.platforms.instagram.request_json", return_value=fake_status):
        with pytest.raises(PlatformError) as exc_info:
            pub._wait_for_container("c123", "tok")
    assert exc_info.value.retryable is True
    assert "expired" in str(exc_info.value).lower()


def test_ig_container_error_is_not_retryable():
    from app.platforms.instagram import InstagramPublisher

    pub = InstagramPublisher()
    fake_status = {"status_code": "ERROR"}
    with patch("app.platforms.instagram.request_json", return_value=fake_status):
        with pytest.raises(PlatformError) as exc_info:
            pub._wait_for_container("c123", "tok")
    assert exc_info.value.retryable is False


# -- B4: MetaOAuth.refresh extends long-lived tokens ------------------

def test_meta_oauth_refresh_extends_token():
    from app.platforms.facebook import MetaOAuth

    fake = {"access_token": "new-llt", "expires_in": 5184000}  # 60 days
    # Need to satisfy creds.configured check — patch config.platform.
    fake_creds = MagicMock(client_id="x", client_secret="y", redirect_uri="z",
                            configured=True)
    with patch("app.platforms.facebook.config.platform", return_value=fake_creds), \
         patch("app.platforms.facebook.request_json", return_value=fake):
        bundle = MetaOAuth().refresh("old-llt")
    assert bundle.access_token == "new-llt"
    assert bundle.expires_at is not None


# -- B5: redactor masks secret-like substrings ------------------------

def test_redact_masks_known_keys():
    out = redact({"access_token": "EAAxxx", "user_id": 1, "nested": {
        "refresh_token": "abc", "page_access_token": "def",
    }})
    assert out["access_token"] == "***"
    assert out["nested"]["refresh_token"] == "***"
    assert out["nested"]["page_access_token"] == "***"
    assert out["user_id"] == 1  # passthrough


def test_redact_masks_token_shaped_substrings():
    out = redact("Bearer EAA0123456789abcdefghijklmnopqrstuv leak")
    assert "EAA0123456789" not in out
    assert "***" in out


def test_audit_record_redacts_detail(app):
    from app.models import AuditLog

    with app.app_context():
        audit_record(
            "test", "x", 1, actor_user_id=1,
            detail={"access_token": "EAAxxx", "info": "ok"},
        )
        db.session.commit()
        row = db.session.query(AuditLog).order_by(AuditLog.id.desc()).first()
        assert row.detail["access_token"] == "***"
        assert row.detail["info"] == "ok"


# -- B6: HTTP timeout is configurable ----------------------------------

def test_http_timeout_default_uses_env(monkeypatch):
    """Importing fresh _http reads PLATFORM_HTTP_TIMEOUT."""
    import importlib
    monkeypatch.setenv("PLATFORM_HTTP_TIMEOUT", "120")
    import app.platforms._http as http_mod
    importlib.reload(http_mod)
    assert http_mod.DEFAULT_TIMEOUT == 120.0


# -- B7: overrides whitelist ------------------------------------------

def test_validate_overrides_accepts_known_keys():
    assert validate_overrides("instagram", {"caption": "hi"}) == []
    assert validate_overrides("tiktok", {
        "caption": "hi", "privacy_level": "SELF_ONLY",
        "disable_duet": True, "challenges": ["#a"],
    }) == []


def test_validate_overrides_rejects_unknown_keys():
    errors = validate_overrides("instagram", {"random_field": 1})
    assert errors
    assert "random_field" in errors[0]


def test_validate_overrides_rejects_wrong_type():
    errors = validate_overrides("tiktok", {"disable_duet": "yes"})
    assert any("expected bool" in e for e in errors)


def test_validate_overrides_checks_tiktok_privacy_enum():
    errors = validate_overrides("tiktok", {"privacy_level": "BOGUS"})
    assert any("privacy_level" in e for e in errors)


def test_validate_overrides_checks_youtube_privacy_enum():
    errors = validate_overrides("youtube", {"privacy_status": "secret"})
    assert any("privacy_status" in e for e in errors)


def test_distribute_rejects_invalid_overrides(client, app):
    """End-to-end: distribute returns 400 with details on bad overrides."""
    from app.models import AccountGroup

    with app.app_context():
        user = db.session.query(User).first() or User(
            email="b7@example.com", display_name="b7")
        if user.id is None:
            db.session.add(user); db.session.commit()
        account = SocialAccount(
            user_id=user.id, platform=Platform.INSTAGRAM,
            external_account_id="x", handle="x", access_token_enc=b"a",
        )
        db.session.add(account); db.session.flush()
        group = AccountGroup(user_id=user.id, name="b7-group")
        group.accounts.append(account)
        db.session.add(group); db.session.flush()
        post = Post(user_id=user.id, title="t", caption="c")
        db.session.add(post); db.session.commit()
        post_id, group_id = post.id, group.id

    res = client.post(f"/api/posts/{post_id}/distribute", json={
        "group_ids": [group_id],
        "dry_run": True,
        "overrides": {"random_field": 1},
    })
    assert res.status_code == 400
    body = res.get_json()
    assert body["error"] == "invalid overrides"
    assert "random_field" in body["details"][0]
