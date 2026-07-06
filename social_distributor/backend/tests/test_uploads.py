"""Upload presign + complete endpoints with mocked S3."""
from unittest.mock import patch

from app.extensions import db
from app.models import MediaAsset, User
from app.utils.storage import PresignedUpload

from .conftest import login_as


def test_presign_returns_signed_urls(client, app):
    with app.app_context():
        user = User(email="t@example.com", display_name="t")
        db.session.add(user)
        db.session.commit()
        uid = user.id
    login_as(client, uid)

    fake = PresignedUpload(
        bucket="my-bucket",
        key="users/1/video/abc.mp4",
        put_url="https://my-bucket.s3.example/put?sig=1",
        public_get_url="https://my-bucket.s3.example/get?sig=1",
    )
    with patch("app.api.uploads.presign_upload", return_value=fake):
        res = client.post(
            "/api/uploads/presign",
            json={"kind": "video", "content_type": "video/mp4"},
        )
    assert res.status_code == 200
    data = res.get_json()
    assert data["bucket"] == "my-bucket"
    assert data["put_url"].startswith("https://")
    assert data["headers"]["Content-Type"] == "video/mp4"


def test_complete_creates_media_and_queues_transcode(client, app):
    with app.app_context():
        user = User(email="t@example.com", display_name="t")
        db.session.add(user)
        db.session.commit()
        uid = user.id
    login_as(client, uid)

    # bucket/key must match this session's own presign prefix and the
    # configured media bucket; public_get_url is regenerated server-side
    # (see security-audit follow-up in app/api/uploads.py), not trusted from
    # the client, so presign_get is mocked here rather than passed in body.
    with patch("app.api.uploads.transcode_media.delay") as transcode, \
         patch("app.api.uploads.media_bucket", return_value="my-bucket"), \
         patch("app.api.uploads.presign_get",
               return_value="https://my-bucket.s3.example/get?sig=1") as presign_get:
        res = client.post(
            "/api/uploads/complete",
            json={
                "kind": "video",
                "content_type": "video/mp4",
                "bucket": "my-bucket",
                "key": f"users/{uid}/video/abc.mp4",
            },
        )
    presign_get.assert_called_once_with("my-bucket", f"users/{uid}/video/abc.mp4")
    assert res.status_code == 201
    media_id = res.get_json()["id"]
    transcode.assert_called_once_with(media_id)
    with app.app_context():
        media = db.session.get(MediaAsset, media_id)
        assert media.compliance_report["s3_bucket"] == "my-bucket"
        assert media.transcode_status == "pending"


def test_presign_rejects_bad_kind(client, app):
    with app.app_context():
        user = User(email="bk@example.com", display_name="bk")
        db.session.add(user)
        db.session.commit()
        uid = user.id
    login_as(client, uid)
    res = client.post(
        "/api/uploads/presign",
        json={"kind": "audio", "content_type": "audio/mp3"},
    )
    assert res.status_code == 400


def test_complete_rejects_key_outside_callers_own_prefix(client, app):
    """Security-audit regression (2026-07-07): a logged-in caller must not be
    able to register a MediaAsset pointing at another user's (or an arbitrary)
    S3 key — only objects under their own users/{their_id}/ presign prefix."""
    with app.app_context():
        user = User(email="victim@example.com", display_name="victim")
        db.session.add(user)
        db.session.commit()
        uid = user.id
    login_as(client, uid)
    with patch("app.api.uploads.media_bucket", return_value="my-bucket"), \
         patch("app.api.uploads.presign_get") as presign_get:
        res = client.post(
            "/api/uploads/complete",
            json={
                "kind": "video",
                "bucket": "my-bucket",
                "key": "users/9999/video/someone-elses.mp4",
            },
        )
    assert res.status_code == 403
    presign_get.assert_not_called()


def test_complete_rejects_unknown_bucket(client, app):
    """Security-audit regression (2026-07-07): the bucket must match the
    server's configured media bucket, not whatever the client sends."""
    with app.app_context():
        user = User(email="bucket-check@example.com", display_name="bc")
        db.session.add(user)
        db.session.commit()
        uid = user.id
    login_as(client, uid)
    with patch("app.api.uploads.media_bucket", return_value="my-bucket"), \
         patch("app.api.uploads.presign_get") as presign_get:
        res = client.post(
            "/api/uploads/complete",
            json={
                "kind": "video",
                "bucket": "attacker-controlled-bucket",
                "key": f"users/{uid}/video/abc.mp4",
            },
        )
    assert res.status_code == 403
    presign_get.assert_not_called()
