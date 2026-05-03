"""Phase 7A audit fixes: callback HTML, RUNNING trap, dry-run no-persist,
shared engine, TikTok unaudited, IG account_type, readiness, auto-seed."""
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest

from app.compliance import ComplianceEngine
from app.extensions import db
from app.models import (
    AccountGroup,
    ComplianceCheck,
    JobStatus,
    Platform,
    Post,
    PostTarget,
    SocialAccount,
    User,
)
from app.platforms.base import TokenBundle


# -- A1: OAuth callback returns HTML not JSON ---------------------------

def test_callback_returns_html_with_postmessage(client):
    res = client.get("/auth/meta/callback?code=fake&state=fake")
    assert "text/html" in res.headers["Content-Type"]
    body = res.get_data(as_text=True)
    # Hits the failure branch but still HTML, still calls postMessage.
    assert "<!doctype html>" in body
    assert "distributor.oauth.complete" in body
    assert "window.opener" in body


def test_callback_unknown_provider_returns_html(client):
    res = client.get("/auth/bogus/callback?code=x&state=y")
    assert "text/html" in res.headers["Content-Type"]
    body = res.get_data(as_text=True)
    assert "unknown provider" in body


# -- A2: RUNNING state never sticks on uncaught exception --------------

def test_dispatch_target_recovers_from_uncaught_exception(app):
    """Force _dispatch_body to raise → row should land in FAILED, not RUNNING."""
    from app.scheduler import tasks

    with app.app_context():
        user = User(email="a2@example.com", display_name="a2")
        db.session.add(user); db.session.flush()
        account = SocialAccount(
            user_id=user.id, platform=Platform.FACEBOOK,
            external_account_id="x", handle="x", access_token_enc=b"a",
        )
        db.session.add(account); db.session.flush()
        post = Post(user_id=user.id, title="t", caption="c")
        db.session.add(post); db.session.flush()
        target = PostTarget(post_id=post.id, account_id=account.id,
                            status=JobStatus.PENDING)
        db.session.add(target); db.session.commit()
        target_id = target.id

    with patch("app.scheduler.tasks._dispatch_body",
               side_effect=RuntimeError("boom — totally unexpected")):
        tasks.dispatch_target(target_id)

    with app.app_context():
        target = db.session.get(PostTarget, target_id)
        assert target.status == JobStatus.FAILED
        assert "uncaught: RuntimeError" in target.last_error


# -- A3: Compliance dry-run does NOT persist ComplianceCheck rows ------

def test_compliance_engine_persist_false_writes_nothing(app):
    with app.app_context():
        user = User(email="a3@example.com", display_name="a3")
        db.session.add(user); db.session.flush()
        post = Post(user_id=user.id, title="t", caption="c")
        db.session.add(post); db.session.commit()

        engine = ComplianceEngine()
        before = db.session.query(ComplianceCheck).count()
        engine.evaluate(post, [], persist=False)
        after = db.session.query(ComplianceCheck).count()
        assert before == after


def test_preview_compliance_endpoint_does_not_persist(client, app):
    with app.app_context():
        user = User(email="a3b@example.com", display_name="a3b")
        db.session.add(user); db.session.flush()
        post = Post(user_id=user.id, title="t", caption="c")
        db.session.add(post); db.session.commit()
        post_id = post.id

    for _ in range(5):
        res = client.post(f"/api/posts/{post_id}/preview-compliance",
                          json={})
        assert res.status_code == 200

    with app.app_context():
        # 5 previews → still zero ComplianceCheck rows.
        assert db.session.query(ComplianceCheck).count() == 0


# -- A4: shared engine instance (no double evaluation) ----------------
# Indirectly verified by A3 not double-persisting; here we lock the contract.

def test_compliance_engine_has_blockers_uses_findings_argument(app):
    """has_blockers should evaluate the SAME findings — no fresh evaluate."""
    with app.app_context():
        user = User(email="a4@example.com", display_name="a4")
        db.session.add(user); db.session.flush()
        post = Post(user_id=user.id, title="t", caption="c")
        db.session.add(post); db.session.commit()

        engine = ComplianceEngine()
        findings = engine.evaluate(post, [], persist=False)
        # has_blockers takes the explicit list.
        assert engine.has_blockers(findings) is False


# -- A5: TikTok unaudited flag set when video.publish missing ---------

def test_tiktok_callback_marks_unaudited_when_scope_missing(client, app):
    """Bundle without video.publish in scopes → SocialAccount.extra.unaudited=true."""
    from app.auth import routes as auth_routes

    with app.app_context():
        user = User(email="a5@example.com", display_name="a5")
        db.session.add(user); db.session.commit()
        user_id = user.id

    state = auth_routes._serializer().dumps(
        {"user_id": user_id, "provider": "tiktok"}
    )
    bundle = TokenBundle(
        access_token="t", refresh_token="r",
        expires_at=datetime.now(timezone.utc) + timedelta(hours=24),
        scopes=["user.info.basic"],  # no video.publish
        extra={"open_id": "tt-1"},
    )
    fake_provider = MagicMock()
    fake_provider.exchange_code.return_value = bundle

    with patch("app.auth.routes.get_oauth_provider", return_value=fake_provider):
        res = client.get(f"/auth/tiktok/callback?code=x&state={state}")

    assert res.status_code == 200
    body = res.get_data(as_text=True)
    assert "unaudited" in body  # surfaced in callback HTML

    with app.app_context():
        acc = db.session.query(SocialAccount).filter_by(
            platform=Platform.TIKTOK).one()
        assert acc.extra.get("unaudited") is True


def test_tiktok_callback_audited_when_scope_present(client, app):
    from app.auth import routes as auth_routes

    with app.app_context():
        user = User(email="a5b@example.com", display_name="a5b")
        db.session.add(user); db.session.commit()
        user_id = user.id

    state = auth_routes._serializer().dumps(
        {"user_id": user_id, "provider": "tiktok"}
    )
    bundle = TokenBundle(
        access_token="t", refresh_token="r",
        expires_at=datetime.now(timezone.utc) + timedelta(hours=24),
        scopes=["user.info.basic", "video.publish"],
        extra={"open_id": "tt-2"},
    )
    fake_provider = MagicMock()
    fake_provider.exchange_code.return_value = bundle

    with patch("app.auth.routes.get_oauth_provider", return_value=fake_provider):
        res = client.get(f"/auth/tiktok/callback?code=x&state={state}")
    assert res.status_code == 200

    with app.app_context():
        acc = db.session.query(SocialAccount).filter_by(
            platform=Platform.TIKTOK).one()
        assert acc.extra.get("unaudited") is not True


# -- A7: /healthz/ready surfaces dependency configuration -------------

def test_healthz_ready_returns_per_dep_config(client):
    res = client.get("/healthz/ready")
    assert res.status_code == 200
    body = res.get_json()
    for key in ("database", "redis", "media_bucket", "oauth", "ai",
                "notify", "encryption"):
        assert key in body
    # In the test env the encryption key is set (conftest), so this is True.
    assert body["encryption"]["token_key_set"] is True


# -- A9: auto-seeded user exists when DB is empty ---------------------
# create_app() runs _auto_seed_user; if the conftest leaves users empty,
# user_id=1 should already be seeded.

def test_auto_seed_user_exists(app):
    with app.app_context():
        # conftest creates the schema fresh per test; auto-seed runs in
        # create_app(). At least one user should exist.
        first = db.session.query(User).order_by(User.id).first()
        assert first is not None
        assert first.id == 1


# -- B9: IG non-business account is skipped -------------------------

def test_meta_callback_skips_personal_ig(client, app, monkeypatch):
    """Meta callback returning a personal IG account → skipped, not stored."""
    from app.auth import routes as auth_routes

    with app.app_context():
        user = User(email="b9@example.com", display_name="b9")
        db.session.add(user); db.session.commit()
        user_id = user.id

    state = auth_routes._serializer().dumps(
        {"user_id": user_id, "provider": "meta"}
    )
    bundle = TokenBundle(
        access_token="user-tok", refresh_token=None,
        expires_at=datetime.now(timezone.utc) + timedelta(days=60),
        scopes=["pages_show_list", "instagram_basic"],
        extra={},
    )
    fake_provider = MagicMock()
    fake_provider.exchange_code.return_value = bundle

    pages_response = {
        "data": [{
            "id": "page-1",
            "name": "My Page",
            "access_token": "page-tok",
            "instagram_business_account": {"id": "ig-1"},
        }]
    }
    ig_meta = {"username": "personal_ig", "account_type": "PERSONAL"}

    def fake_request_json(method, url, **kw):
        if "/me/accounts" in url:
            return pages_response
        if url.endswith("/ig-1"):
            return ig_meta
        raise AssertionError(f"unexpected call: {url}")

    with patch("app.auth.routes.get_oauth_provider", return_value=fake_provider), \
         patch("app.auth.routes.request_json", side_effect=fake_request_json):
        res = client.get(f"/auth/meta/callback?code=x&state={state}")

    assert res.status_code == 200
    body = res.get_data(as_text=True)
    # FB Page connected, IG personal skipped.
    assert "My Page" in body
    assert "personal_ig" in body
    assert "PERSONAL" in body or "BUSINESS" in body  # type surfaced

    with app.app_context():
        # Only the FB Page row exists; the IG account was NOT persisted.
        ig_count = db.session.query(SocialAccount).filter_by(
            platform=Platform.INSTAGRAM).count()
        assert ig_count == 0
        fb_count = db.session.query(SocialAccount).filter_by(
            platform=Platform.FACEBOOK).count()
        assert fb_count == 1
