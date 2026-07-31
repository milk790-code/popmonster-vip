"""Media URLs must be signed at send time, not replayed from upload time.

Presigned URLs are capped at 7 days (SigV4). Storing one and reusing it later
means every post scheduled further out than a week fetches a dead link — which
Facebook reports as a 403, so it reads like a permissions problem rather than
an expiry. Observed in production: the same five posts failed every night for
over ten days on `Unable to fetch video file from URL` and `403 Forbidden`.
"""
from unittest.mock import patch

import pytest

from app.extensions import db
from app.models import MediaAsset, Platform, Post, PostTarget, SocialAccount, User
from app.utils.storage import derivative_key, fresh_media_url

from .conftest import login_as

EXPIRED = "https://r2.example/videos/a.mov?X-Amz-Date=20260101&X-Amz-Signature=old"
FRESH = "https://r2.example/videos/a.mov?X-Amz-Date=20260801&X-Amz-Signature=new"


class _Media:
    """Stand-in for MediaAsset — fresh_media_url only reads attributes."""

    def __init__(self, *, bucket="b", key="users/1/video/a.mov",
                 storage_url=EXPIRED, derivatives=None, kind="video"):
        self.kind = kind
        self.storage_url = storage_url
        self.derivatives = derivatives or {}
        self.compliance_report = ({"s3_bucket": bucket, "s3_key": key}
                                  if bucket and key else {})


def test_resigns_the_original_instead_of_replaying_the_stored_url():
    with patch("app.utils.storage.presign_get", return_value=FRESH) as signer:
        assert fresh_media_url(_Media()) == FRESH
    signer.assert_called_once_with("b", "users/1/video/a.mov")


def test_resigns_a_derivative_using_the_shared_key_rule():
    media = _Media(derivatives={"9:16": EXPIRED})
    with patch("app.utils.storage.presign_get", return_value=FRESH) as signer:
        assert fresh_media_url(media, "9:16") == FRESH
    signer.assert_called_once_with("b", "users/1/video/a__9x16.mp4")


def test_derivative_key_matches_what_the_transcoder_writes():
    """If these two ever drift, the dispatcher signs a key that doesn't exist
    and silently falls back to the expired URL."""
    assert derivative_key("users/1/video/a.mov", "9:16") == "users/1/video/a__9x16.mp4"
    assert derivative_key("users/1/video/a.mp4", "1:1") == "users/1/video/a__1x1.mp4"


def test_missing_derivative_is_not_invented():
    """Only re-sign a variant the transcoder actually produced — signing a
    key that was never uploaded would swap a working original for a 404."""
    with patch("app.utils.storage.presign_get", return_value=FRESH):
        assert fresh_media_url(_Media(derivatives={}), "9:16") is None


def test_external_media_without_bucket_keeps_its_url():
    """Rebroadcast candidates carry someone else's URL; it isn't ours to sign."""
    external = _Media(bucket=None, key=None, storage_url="https://cdn.example/x.mp4")
    assert fresh_media_url(external) == "https://cdn.example/x.mp4"


def test_signing_failure_falls_back_instead_of_breaking_the_dispatch():
    with patch("app.utils.storage.presign_get", side_effect=RuntimeError("no creds")):
        assert fresh_media_url(_Media()) == EXPIRED


def test_none_media_is_none():
    assert fresh_media_url(None) is None


# ------------------------------------------------------- end-to-end wiring


@pytest.fixture()
def target(app):
    with app.app_context():
        user = User(email="m@example.com", display_name="m")
        db.session.add(user)
        db.session.flush()
        media = MediaAsset(
            user_id=user.id,
            kind="video",
            storage_url=EXPIRED,
            mime_type="video/mp4",
            compliance_report={"s3_bucket": "b", "s3_key": "users/1/video/a.mov"},
        )
        account = SocialAccount(
            user_id=user.id,
            platform=Platform.FACEBOOK,
            external_account_id="page-1",
            handle="@p",
            access_token_enc=b"a",
        )
        db.session.add_all([media, account])
        db.session.flush()
        post = Post(user_id=user.id, caption="hi", media_id=media.id)
        db.session.add(post)
        db.session.flush()
        t = PostTarget(post_id=post.id, account_id=account.id)
        db.session.add(t)
        db.session.commit()
        return t.id


def test_publish_request_carries_a_freshly_signed_url(app, target):
    from app.compliance.engine import publisher_request_from

    with app.app_context():
        row = db.session.get(PostTarget, target)
        with patch("app.utils.storage.presign_get", return_value=FRESH):
            req = publisher_request_from(row.post, row)
    assert req.media_url == FRESH, "發文時必須重新簽名，不能沿用上傳當下那條"


def test_media_library_returns_a_freshly_signed_url(client, app):
    """The library's own thumbnails break after 7 days for the same reason
    dispatch did — the stored URL is presigned. Sign on read."""
    from app.utils.crypto import cipher  # noqa: F401 - keeps import parity

    with app.app_context():
        user = User(email="lib@example.com", display_name="l")
        db.session.add(user)
        db.session.flush()
        db.session.add(MediaAsset(
            user_id=user.id, kind="image", storage_url=EXPIRED,
            mime_type="image/jpeg",
            compliance_report={"s3_bucket": "b", "s3_key": "users/1/image/a.jpg"},
        ))
        db.session.add(MediaAsset(
            user_id=user.id, kind="image", storage_url="https://cdn.example/ext.jpg",
            mime_type="image/jpeg", compliance_report={},
        ))
        db.session.commit()
        user_id = user.id

    login_as(client, user_id)
    with patch("app.utils.storage.presign_get", return_value=FRESH):
        body = client.get("/api/uploads").get_json()

    by_url = {i["storage_url"]: i for i in body["items"]}
    assert FRESH in by_url, "自家素材必須回傳重新簽名的連結"
    assert by_url[FRESH]["resignable"] is True
    external = by_url["https://cdn.example/ext.jpg"]
    assert external["resignable"] is False, "外部素材簽不了，要誠實標示"
