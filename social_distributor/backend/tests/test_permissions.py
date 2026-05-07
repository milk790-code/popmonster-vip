"""Permission grant CRUD + drift detection (no real Graph API calls)."""
from datetime import datetime, timezone
from unittest.mock import patch

from app.extensions import db
from app.models import (
    PermissionDriftAlert,
    PermissionGrant,
    Platform,
    SocialAccount,
    User,
)
from app.permissions import meta_bm
from app.permissions.health import run_health_sweep
from app.utils.crypto import cipher


def _seed(app, *, platform=Platform.FACEBOOK, ext_id="page-1"):
    with app.app_context():
        user = User(email="p@example.com", display_name="p")
        db.session.add(user)
        db.session.flush()
        c = cipher()
        account = SocialAccount(
            user_id=user.id, platform=platform,
            external_account_id=ext_id, handle="my-page",
            access_token_enc=c.encrypt("token"),
            extra={"page_access_token": "token"},
        )
        db.session.add(account)
        db.session.commit()
        return user.id, account.id


def test_grant_calls_platform_then_persists(client, app):
    user_id, _ = _seed(app)
    raw = {"success": True}
    with patch("app.api.permissions.meta_bm.grant_role", return_value=raw) as grant:
        res = client.post("/api/permissions/grants", json={
            "user_id": user_id,
            "platform": "facebook",
            "asset_kind": "page",
            "asset_external_id": "page-1",
            "grantee_external_id": "user-99",
            "grantee_label": "Alice",
            "role": "EDITOR",
        })
    assert res.status_code == 201, res.data
    grant.assert_called_once()
    with app.app_context():
        rows = db.session.query(PermissionGrant).all()
        assert len(rows) == 1
        assert rows[0].role == "EDITOR"
        assert rows[0].status == "active"


def test_grant_rejects_youtube_with_runbook_pointer(client, app):
    user_id, _ = _seed(app)
    res = client.post("/api/permissions/grants", json={
        "user_id": user_id, "platform": "youtube", "asset_kind": "channel",
        "asset_external_id": "UC123", "grantee_external_id": "x", "role": "ADMIN",
    })
    assert res.status_code == 422
    assert "runbook" in res.get_json()


def test_revoke_calls_platform_and_marks_status(client, app):
    user_id, _ = _seed(app)
    with patch("app.api.permissions.meta_bm.grant_role", return_value={}):
        client.post("/api/permissions/grants", json={
            "user_id": user_id, "platform": "facebook", "asset_kind": "page",
            "asset_external_id": "page-1", "grantee_external_id": "u",
            "role": "ADMIN",
        })
    with app.app_context():
        gid = db.session.query(PermissionGrant).one().id

    with patch("app.api.permissions.meta_bm.revoke_role", return_value={}) as revoke:
        res = client.delete(f"/api/permissions/grants/{gid}")
    assert res.status_code == 200
    revoke.assert_called_once()
    assert res.get_json()["status"] == "revoked"


def test_runbook_endpoint_serves_youtube_doc(client):
    res = client.get("/api/permissions/runbooks/youtube_transfer.md")
    assert res.status_code == 200
    body = res.get_data(as_text=True)
    assert "Brand Account" in body  # sanity check on the runbook content


def test_health_sweep_records_grant_disappeared(app):
    """Health sweep must flag a recorded grant the platform no longer reports."""
    user_id, account_id = _seed(app)
    with app.app_context():
        db.session.add(PermissionGrant(
            user_id=user_id,
            platform=Platform.FACEBOOK,
            asset_kind="page",
            asset_external_id="page-1",
            grantee_external_id="user-missing",
            role="ADMIN",
            status="active",
            granted_by_user_id=user_id,
        ))
        db.session.commit()

    with patch("app.permissions.health._meta_token_alive", return_value=True), \
         patch("app.permissions.health.list_assigned_users", return_value=[]):
        with app.app_context():
            counts = run_health_sweep()

    assert counts["grant_disappeared"] >= 1
    with app.app_context():
        alerts = db.session.query(PermissionDriftAlert).all()
        assert any(a.kind == "grant_disappeared" for a in alerts)
        # Original grant marked as drift.
        grants = db.session.query(PermissionGrant).all()
        assert grants[0].status == "drift"


def test_health_sweep_records_grant_unexpected(app):
    """Platform reports a user we don't have a grant for → drift alert."""
    user_id, _ = _seed(app)
    fake_user = meta_bm.AssignedUser(user_id="surprise", role="EDITOR", name="?")
    with patch("app.permissions.health._meta_token_alive", return_value=True), \
         patch("app.permissions.health.list_assigned_users", return_value=[fake_user]):
        with app.app_context():
            counts = run_health_sweep()
    assert counts["grant_unexpected"] >= 1


def test_health_sweep_records_invalid_token(app):
    user_id, _ = _seed(app)
    with patch("app.permissions.health._meta_token_alive", return_value=False):
        with app.app_context():
            counts = run_health_sweep()
    assert counts["token_invalid"] >= 1
    with app.app_context():
        alerts = db.session.query(PermissionDriftAlert).all()
        assert any(a.kind == "token_invalid" for a in alerts)
