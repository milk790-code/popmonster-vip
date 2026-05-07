"""Ownership transfer state machine + manual expiry sweep."""
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from app.extensions import db
from app.models import OwnershipTransfer, Platform, SocialAccount, User
from app.transfers.manual_transfer import advance, transition_expired_if_overdue
from app.utils.crypto import cipher


def _seed_user(app):
    with app.app_context():
        user = User(email="t@example.com", display_name="t")
        db.session.add(user)
        db.session.commit()
        return user.id


def test_manual_transfer_creation(client, app):
    user_id = _seed_user(app)
    res = client.post("/api/transfers", json={
        "user_id": user_id, "platform": "youtube", "channel": "manual",
        "asset_kind": "channel", "asset_external_id": "UC123",
        "source_label": "personal", "target_label": "Brand A",
    })
    assert res.status_code == 201
    body = res.get_json()
    assert body["channel"] == "manual"
    assert body["status"] == "requested"


def test_api_channel_rejects_non_facebook(client, app):
    user_id = _seed_user(app)
    res = client.post("/api/transfers", json={
        "user_id": user_id, "platform": "tiktok", "channel": "api",
        "asset_kind": "creator_account", "asset_external_id": "x",
    })
    assert res.status_code == 422


def test_api_channel_calls_meta_initiation(client, app):
    user_id = _seed_user(app)
    with app.app_context():
        c = cipher()
        db.session.add(SocialAccount(
            user_id=user_id, platform=Platform.FACEBOOK,
            external_account_id="page-9", handle="p",
            access_token_enc=c.encrypt("token"),
        ))
        db.session.commit()

    with patch("app.api.transfers.meta_transfer.initiate_page_transfer",
               return_value={"ok": True}) as init:
        res = client.post("/api/transfers", json={
            "user_id": user_id, "platform": "facebook", "channel": "api",
            "asset_kind": "page", "asset_external_id": "page-9",
            "from_business_id": "bm-source", "to_business_id": "bm-target",
        })
    assert res.status_code == 201
    init.assert_called_once()
    assert res.get_json()["status"] == "awaiting_target"


def test_state_transitions(app):
    with app.app_context():
        user = User(email="s@example.com", display_name="s")
        db.session.add(user)
        db.session.flush()
        t = OwnershipTransfer(
            user_id=user.id, platform=Platform.YOUTUBE,
            asset_kind="channel", asset_external_id="UC1",
            channel="manual", status="awaiting_target",
        )
        db.session.add(t)
        db.session.commit()
        advance(t, "completed", notes="done in YouTube UI")
        db.session.commit()
        assert t.status == "completed"
        assert t.completed_at is not None
        assert "done in YouTube UI" in t.notes


def test_sweep_expires_overdue_manual_transfers(app):
    with app.app_context():
        user = User(email="e@example.com", display_name="e")
        db.session.add(user)
        db.session.flush()
        past = datetime.now(timezone.utc) - timedelta(days=1)
        future = datetime.now(timezone.utc) + timedelta(days=1)
        db.session.add(OwnershipTransfer(
            user_id=user.id, platform=Platform.YOUTUBE,
            asset_kind="channel", asset_external_id="x1",
            channel="manual", status="awaiting_target", expires_at=past,
        ))
        db.session.add(OwnershipTransfer(
            user_id=user.id, platform=Platform.YOUTUBE,
            asset_kind="channel", asset_external_id="x2",
            channel="manual", status="awaiting_target", expires_at=future,
        ))
        db.session.commit()
        expired = transition_expired_if_overdue()
        assert expired == 1
        rows = db.session.query(OwnershipTransfer).order_by(OwnershipTransfer.id).all()
        assert rows[0].status == "expired"
        assert rows[1].status == "awaiting_target"
