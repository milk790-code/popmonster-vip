"""Upload presign + complete endpoints with mocked S3."""
from unittest.mock import patch

from app.extensions import db
from app.models import MediaAsset, User
from app.utils.storage import PresignedUpload


def test_presign_returns_signed_urls(client, app):
    with app.app_context():
        user = User(email="t@example.com", display_name="t")
        db.session.add(user)
        db.session.commit()

    fake = PresignedUpload(
        bucket="my-bucket",
        key="users/1/video/abc.mp4",
        put_url="https://my-bucket.s3.example/put?sig=1",
        public_get_url="https://my-bucket.s3.example/get?sig=1",
    )
    with patch("app.api.uploads.presign_upload", return_value=fake):
        res = client.post(
            "/api/uploads/presign",
            json={"user_id": 1, "kind": "video", "content_type": "video/mp4"},
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

    with patch("app.api.uploads.transcode_media.delay") as transcode:
        res = client.post(
            "/api/uploads/complete",
            json={
                "user_id": 1,
                "kind": "video",
                "content_type": "video/mp4",
                "bucket": "my-bucket",
                "key": "users/1/video/abc.mp4",
                "public_get_url": "https://my-bucket.s3.example/get?sig=1",
            },
        )
    assert res.status_code == 201
    media_id = res.get_json()["id"]
    transcode.assert_called_once_with(media_id)
    with app.app_context():
        media = db.session.get(MediaAsset, media_id)
        assert media.compliance_report["s3_bucket"] == "my-bucket"
        assert media.transcode_status == "pending"


def test_presign_rejects_bad_kind(client):
    res = client.post(
        "/api/uploads/presign",
        json={"user_id": 1, "kind": "audio", "content_type": "audio/mp3"},
    )
    assert res.status_code == 400
