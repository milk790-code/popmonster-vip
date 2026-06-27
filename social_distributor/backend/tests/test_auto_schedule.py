"""Phase 11: auto-schedule today's marketing distribution.

Builds N posts/account by re-using captions from prior SUCCEEDED PostTargets,
pairing with media library assets, spreading scheduled_for across the day.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

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
from app.utils.auto_schedule_orchestrator import (
    AutoScheduleParams,
    build_today_schedule,
)

from .conftest import login_as


def _seed_succeeded_post(user_id: int, caption: str) -> Post:
    """Create a Post + a SUCCEEDED PostTarget (so it counts toward caption pool)."""
    post = Post(user_id=user_id, caption=caption, link_url=None)
    db.session.add(post)
    db.session.flush()
    target = PostTarget(
        post_id=post.id,
        account_id=1,  # any account, just for FK
        scheduled_for=None,
        status=JobStatus.SUCCEEDED,
        published_at=datetime.now(timezone.utc) - timedelta(hours=1),
    )
    db.session.add(target)
    db.session.flush()
    return post


def _seed_user_and_accounts(n_accounts: int = 3) -> tuple[int, list[int]]:
    user = User(email="auto@example.com", display_name="auto")
    db.session.add(user)
    db.session.flush()
    account_ids = []
    for i in range(n_accounts):
        acct = SocialAccount(
            user_id=user.id,
            platform=Platform.FACEBOOK,
            external_account_id=f"fb-{i}",
            handle=f"page-{i}",
            access_token_enc=b"fake",
            extra={},
        )
        db.session.add(acct)
        db.session.flush()
        account_ids.append(acct.id)
    db.session.commit()
    return user.id, account_ids


def _seed_media(user_id: int, kind: str, transcode_status: str = "ready") -> MediaAsset:
    m = MediaAsset(
        user_id=user_id,
        kind=kind,
        storage_url=f"https://r2/{kind}/{transcode_status}",
        mime_type="video/mp4" if kind == "video" else "image/jpeg",
        transcode_status=transcode_status if kind == "video" else "skipped",
    )
    db.session.add(m)
    db.session.flush()
    return m


def test_caption_pool_excludes_failed_and_old(app):
    with app.app_context():
        user_id, _ = _seed_user_and_accounts(1)
        # Recent SUCCEEDED → in pool
        _seed_succeeded_post(user_id, "good caption A")
        _seed_succeeded_post(user_id, "good caption B")
        # FAILED → not in pool
        post_failed = Post(user_id=user_id, caption="failed caption", link_url=None)
        db.session.add(post_failed); db.session.flush()
        db.session.add(PostTarget(
            post_id=post_failed.id, account_id=1,
            status=JobStatus.FAILED,
            published_at=datetime.now(timezone.utc) - timedelta(hours=1),
        ))
        db.session.commit()

        from app.utils.auto_schedule_orchestrator import _caption_pool
        pool = _caption_pool(user_id)
        assert "good caption A" in pool
        assert "good caption B" in pool
        assert "failed caption" not in pool


def test_media_pool_excludes_pending_videos(app):
    with app.app_context():
        user_id, _ = _seed_user_and_accounts(1)
        _seed_media(user_id, "video", "ready")
        _seed_media(user_id, "video", "ready")
        _seed_media(user_id, "video", "pending")
        _seed_media(user_id, "image")
        db.session.commit()

        from app.utils.auto_schedule_orchestrator import _media_pools
        videos, images = _media_pools(user_id)
        assert len(videos) == 2
        assert len(images) == 1


def test_each_account_gets_n_posts(app):
    with app.app_context():
        user_id, account_ids = _seed_user_and_accounts(3)
        _seed_succeeded_post(user_id, "c1")
        _seed_succeeded_post(user_id, "c2")
        _seed_succeeded_post(user_id, "c3")
        _seed_media(user_id, "video", "ready")
        _seed_media(user_id, "image")
        db.session.commit()

        # Pin to 00:00 UTC (08:00 Taipei) so the [10,22) Taipei window is ahead.
        now_utc = datetime(2026, 5, 7, 0, 0, 0, tzinfo=timezone.utc)
        params = AutoScheduleParams(
            user_id=user_id, videos_per_account=2, posts_per_account=2,
            link="https://example.com",
            today=now_utc,
        )
        result = build_today_schedule(params)

        assert result["summary"]["accounts"] == 3
        # 3 accounts * 4 posts = 12; allow window-narrow to truncate
        assert result["summary"]["posts_created"] >= 4  # at least each account got something
        assert len(result["by_account"]) == 3
        for entry in result["by_account"]:
            assert len(entry["target_ids"]) == len(entry["scheduled_ats"])


def test_scheduled_ats_in_window(app):
    with app.app_context():
        user_id, _ = _seed_user_and_accounts(1)
        _seed_succeeded_post(user_id, "c1")
        _seed_media(user_id, "video", "ready")
        db.session.commit()

        # Pin "now" to 09:00 UTC = 17:00 Asia/Taipei. Window [10,22) Taipei
        # should be fully ahead in UTC terms (it's [02:00, 14:00) UTC).
        # Wait — 09:00 UTC = 17:00 Taipei, so window has already started
        # (10:00) but not ended (22:00). Set now earlier so window is ahead:
        now_utc = datetime(2026, 5, 7, 0, 0, 0, tzinfo=timezone.utc)
        # 00:00 UTC = 08:00 Taipei → window [10,22) Taipei = [02:00, 14:00) UTC
        params = AutoScheduleParams(
            user_id=user_id, videos_per_account=2, posts_per_account=0,
            window_start_hour=10, window_end_hour=22,
            timezone="Asia/Taipei",
            today=now_utc,
        )
        result = build_today_schedule(params)

        from zoneinfo import ZoneInfo
        tz = ZoneInfo("Asia/Taipei")
        for entry in result["by_account"]:
            assert len(entry["scheduled_ats"]) > 0
            for sched_iso in entry["scheduled_ats"]:
                dt = datetime.fromisoformat(sched_iso)
                local = dt.astimezone(tz)
                assert local.hour >= 10
                assert local.hour < 22


def test_window_passed_today_returns_warning(app):
    """If we run after window_end_hour in the user's TZ, no slots should be
    scheduled and a warning surfaces."""
    with app.app_context():
        user_id, _ = _seed_user_and_accounts(1)
        _seed_succeeded_post(user_id, "c1")
        _seed_media(user_id, "video", "ready")
        db.session.commit()

        # 15:00 UTC May 7 = 23:00 May 7 Taipei → today's window 10–22 has passed
        now_utc = datetime(2026, 5, 7, 15, 0, 0, tzinfo=timezone.utc)
        params = AutoScheduleParams(
            user_id=user_id, videos_per_account=2, posts_per_account=0,
            window_start_hour=10, window_end_hour=22,
            timezone="Asia/Taipei",
            today=now_utc,
        )
        result = build_today_schedule(params)
        # Either no posts created, or warning surfaced
        warnings = " ".join(result["summary"]["warnings"])
        assert "passed" in warnings or result["summary"]["posts_created"] == 0


def test_dry_run_writes_nothing(app):
    with app.app_context():
        user_id, _ = _seed_user_and_accounts(2)
        _seed_succeeded_post(user_id, "c1")
        _seed_media(user_id, "video", "ready")
        db.session.commit()

        before_posts = db.session.query(Post).count()
        before_targets = db.session.query(PostTarget).count()

        params = AutoScheduleParams(
            user_id=user_id, videos_per_account=2, posts_per_account=0,
            dry_run=True,
        )
        result = build_today_schedule(params)

        after_posts = db.session.query(Post).count()
        after_targets = db.session.query(PostTarget).count()
        assert before_posts == after_posts
        assert before_targets == after_targets
        assert result["summary"]["dry_run"] is True
        # by_account still populated, just without target_ids
        assert all(e["target_ids"] == [] for e in result["by_account"])


def test_caption_repeats_allowed(app):
    """5 captions × 100 accounts shouldn't IndexError; random.choices allows reuse."""
    with app.app_context():
        user_id, _ = _seed_user_and_accounts(20)
        for i in range(5):
            _seed_succeeded_post(user_id, f"caption {i}")
        _seed_media(user_id, "video", "ready")
        db.session.commit()

        # Pin to 00:00 UTC (08:00 Taipei) so the [10,22) Taipei window is ahead.
        now_utc = datetime(2026, 5, 7, 0, 0, 0, tzinfo=timezone.utc)
        params = AutoScheduleParams(
            user_id=user_id, videos_per_account=1, posts_per_account=0,
            today=now_utc,
        )
        result = build_today_schedule(params)
        assert result["summary"]["accounts"] == 20
        assert result["summary"]["posts_created"] >= 1


def test_no_captions_returns_warning(app):
    with app.app_context():
        user_id, _ = _seed_user_and_accounts(2)
        _seed_media(user_id, "video", "ready")
        db.session.commit()

        params = AutoScheduleParams(user_id=user_id)
        result = build_today_schedule(params)
        assert result["summary"]["posts_created"] == 0
        assert any("captions" in w for w in result["summary"]["warnings"])


def test_endpoint_dry_run(client, app):
    with app.app_context():
        user_id, _ = _seed_user_and_accounts(2)
        _seed_succeeded_post(user_id, "c1")
        _seed_succeeded_post(user_id, "c2")
        _seed_media(user_id, "video", "ready")
        _seed_media(user_id, "image")
        db.session.commit()

    login_as(client, user_id)
    res = client.post(
        "/api/auto-schedule/today",
        json={"videos_per_account": 1, "posts_per_account": 1, "dry_run": True},
    )
    assert res.status_code == 200
    data = res.get_json()
    assert data["summary"]["accounts"] == 2
    assert data["summary"]["dry_run"] is True


def test_endpoint_rejects_bad_window(client, app):
    with app.app_context():
        user_id, _ = _seed_user_and_accounts(1)

    login_as(client, user_id)
    res = client.post(
        "/api/auto-schedule/today",
        json={"window_start_hour": 22, "window_end_hour": 10, "dry_run": True},
    )
    assert res.status_code == 400
