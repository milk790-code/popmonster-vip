"""Rebroadcast scan + promote (no real platform calls)."""
from unittest.mock import patch

from app.extensions import db
from app.models import (
    AccountGroup,
    JobStatus,
    Platform,
    Post,
    PostTarget,
    RebroadcastCandidate,
    SocialAccount,
    User,
)
from app.utils.crypto import cipher

from .conftest import login_as


def _seed(app, *, platform=Platform.FACEBOOK):
    with app.app_context():
        user = User(email="r@example.com", display_name="r")
        db.session.add(user)
        db.session.flush()
        c = cipher()
        account = SocialAccount(
            user_id=user.id, platform=platform,
            external_account_id="ext-1", handle="h",
            access_token_enc=c.encrypt("token"),
            extra={"page_access_token": "ptoken"},
        )
        db.session.add(account)
        db.session.commit()
        return user.id, account.id


def test_scan_inserts_candidates(client, app):
    user_id, account_id = _seed(app)
    login_as(client, user_id)
    fake_items = [
        {"external_post_id": "p-1", "snippet": "hello world",
         "media_urls": ["https://cdn/img1.jpg"], "permalink": "https://fb/1"},
        {"external_post_id": "p-2", "snippet": "second",
         "media_urls": [], "permalink": None},
    ]
    with patch("app.api.rebroadcast._scan_platform", return_value=fake_items):
        res = client.post("/api/rebroadcast/scan", json={
            "source_account_id": account_id, "limit": 25,
        })
    assert res.status_code == 200
    assert res.get_json()["inserted"] == 2

    with app.app_context():
        rows = db.session.query(RebroadcastCandidate).all()
        assert len(rows) == 2
        assert rows[0].snippet == "hello world"


def test_scan_dedupes_existing_external_ids(client, app):
    user_id, account_id = _seed(app)
    login_as(client, user_id)
    fake_items = [
        {"external_post_id": "dup", "snippet": "x", "media_urls": [], "permalink": None},
    ]
    with patch("app.api.rebroadcast._scan_platform", return_value=fake_items):
        client.post("/api/rebroadcast/scan",
                    json={"source_account_id": account_id, "limit": 5})
        res = client.post("/api/rebroadcast/scan",
                          json={"source_account_id": account_id, "limit": 5})
    assert res.status_code == 200
    assert res.get_json()["inserted"] == 0
    with app.app_context():
        assert db.session.query(RebroadcastCandidate).count() == 1


def test_promote_creates_post_and_marks_used(client, app):
    user_id, account_id = _seed(app)
    with app.app_context():
        candidate = RebroadcastCandidate(
            user_id=user_id, source_account_id=account_id,
            external_post_id="p-1", snippet="echo",
            media_urls=["https://cdn/x.jpg"], permalink="https://fb/1",
        )
        db.session.add(candidate)
        group = AccountGroup(user_id=user_id, name="g")
        db.session.add(group)
        db.session.commit()
        candidate_id, group_id = candidate.id, group.id

    login_as(client, user_id)
    res = client.post("/api/rebroadcast/promote", json={
        "candidate_id": candidate_id, "group_ids": [group_id],
        "jitter_minutes": 10, "generate_variants": False,
    })
    assert res.status_code == 201
    body = res.get_json()
    assert body["post_id"]
    with app.app_context():
        post = db.session.get(Post, body["post_id"])
        assert post.caption == "echo"
        candidate = db.session.get(RebroadcastCandidate, candidate_id)
        assert candidate.used is True
        assert candidate.promoted_post_id == post.id


def test_promote_rejects_already_used_candidate(client, app):
    user_id, account_id = _seed(app)
    with app.app_context():
        candidate = RebroadcastCandidate(
            user_id=user_id, source_account_id=account_id,
            external_post_id="p-1", snippet="x", used=True,
        )
        db.session.add(candidate)
        db.session.commit()
        candidate_id = candidate.id
    login_as(client, user_id)
    res = client.post("/api/rebroadcast/promote", json={
        "candidate_id": candidate_id, "group_ids": [1],
    })
    assert res.status_code == 409
