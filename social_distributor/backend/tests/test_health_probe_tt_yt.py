"""C1: TikTok + YouTube token health probes."""
from unittest.mock import MagicMock, patch

from app.extensions import db
from app.models import (
    PermissionDriftAlert,
    Platform,
    SocialAccount,
    User,
)
from app.permissions.health import (
    _tiktok_token_alive,
    _youtube_token_alive,
    run_health_sweep,
)
from app.platforms.base import PlatformError
from app.utils.crypto import cipher


# -- _tiktok_token_alive --------------------------------------------

def test_tiktok_token_alive_true_on_200():
    with patch("app.permissions.health.request_json", return_value={"data": {"user": {"open_id": "x"}}}):
        assert _tiktok_token_alive("good-token") is True


def test_tiktok_token_alive_false_on_401():
    with patch("app.permissions.health.request_json",
               side_effect=PlatformError("invalid_token", retryable=False, status_code=401)):
        assert _tiktok_token_alive("bad-token") is False


# -- _youtube_token_alive -------------------------------------------

def test_youtube_token_alive_true_when_channel_returned():
    fake_yt = MagicMock()
    fake_yt.channels().list().execute.return_value = {"items": [{"id": "UC1"}]}
    with patch("app.permissions.health.build", return_value=fake_yt, create=True):
        from app.permissions import health
        # patch import inline since build is imported lazily
        with patch.object(health, "_youtube_token_alive",
                          wraps=health._youtube_token_alive):
            with patch("googleapiclient.discovery.build", return_value=fake_yt):
                assert _youtube_token_alive("ya29.x", "1//refresh") is True


def test_youtube_token_alive_false_on_exception():
    with patch("googleapiclient.discovery.build",
               side_effect=Exception("invalid_grant")):
        assert _youtube_token_alive("dead-token", None) is False


# -- run_health_sweep covers TT/YT ---------------------------------

def test_health_sweep_marks_tiktok_token_invalid(app):
    with app.app_context():
        user = User(email="c1tt@example.com", display_name="c1")
        db.session.add(user); db.session.flush()
        c = cipher()
        account = SocialAccount(
            user_id=user.id, platform=Platform.TIKTOK,
            external_account_id="tt-1", handle="tt-1",
            access_token_enc=c.encrypt("dead"),
        )
        db.session.add(account); db.session.commit()

    with patch("app.permissions.health._tiktok_token_alive", return_value=False):
        with app.app_context():
            counts = run_health_sweep()
    assert counts["token_invalid"] >= 1
    with app.app_context():
        alerts = db.session.query(PermissionDriftAlert).filter_by(
            platform=Platform.TIKTOK, kind="token_invalid").all()
        assert len(alerts) == 1


def test_health_sweep_marks_youtube_token_invalid(app):
    with app.app_context():
        user = User(email="c1yt@example.com", display_name="c1")
        db.session.add(user); db.session.flush()
        c = cipher()
        account = SocialAccount(
            user_id=user.id, platform=Platform.YOUTUBE,
            external_account_id="UC-1", handle="UC-1",
            access_token_enc=c.encrypt("dead-yt"),
            refresh_token_enc=c.encrypt("refresh"),
        )
        db.session.add(account); db.session.commit()

    with patch("app.permissions.health._youtube_token_alive", return_value=False):
        with app.app_context():
            counts = run_health_sweep()
    assert counts["token_invalid"] >= 1
    with app.app_context():
        alerts = db.session.query(PermissionDriftAlert).filter_by(
            platform=Platform.YOUTUBE, kind="token_invalid").all()
        assert len(alerts) == 1


def test_health_sweep_alive_tt_yt_no_alerts(app):
    with app.app_context():
        user = User(email="c1ok@example.com", display_name="c1ok")
        db.session.add(user); db.session.flush()
        c = cipher()
        for plat, ext in [(Platform.TIKTOK, "tt"), (Platform.YOUTUBE, "yt")]:
            db.session.add(SocialAccount(
                user_id=user.id, platform=plat,
                external_account_id=ext, handle=ext,
                access_token_enc=c.encrypt("good"),
                refresh_token_enc=c.encrypt("r"),
            ))
        db.session.commit()

    with patch("app.permissions.health._tiktok_token_alive", return_value=True), \
         patch("app.permissions.health._youtube_token_alive", return_value=True):
        with app.app_context():
            counts = run_health_sweep()
    assert counts["token_invalid"] == 0
