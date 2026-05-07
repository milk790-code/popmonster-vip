"""Phase 1 unit tests: derivative selection, token refresh, notify safety."""
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

from app.extensions import db
from app.models import (
    JobStatus,
    MediaAsset,
    Platform,
    Post,
    PostTarget,
    SocialAccount,
    User,
)
from app.platforms.base import TokenBundle
from app.scheduler import tasks


def _make_target(app, *, platform: Platform, derivatives: dict | None = None,
                 expires_at=None, refresh_token=b"r"):
    user = User(email="t@example.com", display_name="t")
    db.session.add(user)
    db.session.flush()

    media = MediaAsset(
        user_id=user.id,
        kind="video",
        storage_url="https://example.com/orig.mp4",
        mime_type="video/mp4",
        derivatives=derivatives or {},
    )
    db.session.add(media)
    db.session.flush()

    post = Post(user_id=user.id, title="t", caption="c", media_id=media.id)
    db.session.add(post)
    db.session.flush()

    account = SocialAccount(
        user_id=user.id,
        platform=platform,
        external_account_id="x",
        handle="h",
        access_token_enc=b"a",
        refresh_token_enc=refresh_token,
        token_expires_at=expires_at,
    )
    db.session.add(account)
    db.session.flush()

    target = PostTarget(
        post_id=post.id,
        account_id=account.id,
        status=JobStatus.PENDING,
        timezone="UTC",
    )
    db.session.add(target)
    db.session.flush()
    return media, account, target


def test_derivative_swap_picks_per_platform_aspect(app):
    with app.app_context():
        derivatives = {"16:9": "https://cdn/h16.mp4", "9:16": "https://cdn/v9.mp4"}
        media, _, _ = _make_target(app, platform=Platform.TIKTOK, derivatives=derivatives)
        from app.platforms.base import PublishRequest
        req = PublishRequest(caption="c", media_url="https://example.com/orig.mp4",
                             media_kind="video")
        tasks._swap_in_preferred_derivative(req, media, "tiktok")
        assert req.media_url == "https://cdn/v9.mp4"

        req2 = PublishRequest(caption="c", media_url="https://example.com/orig.mp4",
                              media_kind="video")
        tasks._swap_in_preferred_derivative(req2, media, "youtube")
        assert req2.media_url == "https://cdn/h16.mp4"


def test_derivative_swap_falls_back_when_missing(app):
    with app.app_context():
        media, _, _ = _make_target(app, platform=Platform.YOUTUBE, derivatives={})
        from app.platforms.base import PublishRequest
        req = PublishRequest(caption="c", media_url="https://example.com/orig.mp4",
                             media_kind="video")
        tasks._swap_in_preferred_derivative(req, media, "youtube")
        assert req.media_url == "https://example.com/orig.mp4"


def test_token_refresh_updates_account(app):
    with app.app_context():
        soon = datetime.now(timezone.utc) + timedelta(hours=1)
        _, account, _ = _make_target(app, platform=Platform.YOUTUBE, expires_at=soon)
        from app.utils.crypto import cipher
        c = cipher()
        account.access_token_enc = c.encrypt("old-access")
        account.refresh_token_enc = c.encrypt("old-refresh")
        db.session.commit()

        new_expiry = datetime.now(timezone.utc) + timedelta(hours=24)
        fake_provider = MagicMock()
        fake_provider.refresh.return_value = TokenBundle(
            access_token="new-access",
            refresh_token="new-refresh",
            expires_at=new_expiry,
            scopes=["youtube.upload"],
        )
        with patch("app.scheduler.tasks.get_oauth_provider", return_value=fake_provider):
            tasks.refresh_oauth_tokens()

        db.session.refresh(account)
        assert c.decrypt(account.access_token_enc) == "new-access"
        assert c.decrypt(account.refresh_token_enc) == "new-refresh"
        stored = account.token_expires_at
        if stored.tzinfo is None:
            stored = stored.replace(tzinfo=timezone.utc)
        assert abs((stored - new_expiry).total_seconds()) < 2
        fake_provider.refresh.assert_called_once_with("old-refresh")


def test_token_refresh_skips_when_far_from_expiry(app):
    with app.app_context():
        far = datetime.now(timezone.utc) + timedelta(days=30)
        _, account, _ = _make_target(app, platform=Platform.YOUTUBE, expires_at=far)
        fake_provider = MagicMock()
        with patch("app.scheduler.tasks.get_oauth_provider", return_value=fake_provider):
            tasks.refresh_oauth_tokens()
        fake_provider.refresh.assert_not_called()


def test_notify_is_silent_without_credentials(app):
    """Notification helpers must never raise when env is unset."""
    from app.utils import notify
    notify.notify_publish_failed(
        user_email=None, user_phone=None,
        platform="tiktok", handle="h", error="boom", target_id=1,
    )
