"""next_best_time_for_group + use_best_time flag in /distribute."""
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from app.extensions import db
from app.models import (
    AccountGroup,
    JobStatus,
    Platform,
    Post,
    PostMetric,
    PostTarget,
    SocialAccount,
    User,
)
from app.utils.best_times import (
    TimeSlot,
    _next_future_occurrence,
    next_best_time_for_group,
)

from .conftest import login_as


def test_next_future_occurrence_skips_to_next_week_when_today_already_passed():
    # Tuesday 14:00 UTC
    now = datetime(2026, 5, 5, 14, 0, tzinfo=timezone.utc)
    slot = TimeSlot(day="Tue", hour=9, sample_count=5, avg_engagement_rate=0.2)
    result = _next_future_occurrence(slot, after=now)
    # 9:00 already passed today, so next Tuesday
    assert result == datetime(2026, 5, 12, 9, 0, tzinfo=timezone.utc)


def test_next_future_occurrence_uses_today_when_still_ahead():
    now = datetime(2026, 5, 5, 6, 0, tzinfo=timezone.utc)  # Tue 06:00
    slot = TimeSlot(day="Tue", hour=9, sample_count=5, avg_engagement_rate=0.2)
    result = _next_future_occurrence(slot, after=now)
    assert result == datetime(2026, 5, 5, 9, 0, tzinfo=timezone.utc)


def test_next_best_time_for_group_returns_none_without_data(app):
    with app.app_context():
        user = User(email="b@example.com", display_name="b")
        db.session.add(user); db.session.flush()
        group = AccountGroup(user_id=user.id, name="g")
        db.session.add(group); db.session.commit()
        assert next_best_time_for_group(group.id) is None


def _post_with_metric(app, *, account_id, post_id, dt: datetime,
                      reach: int, likes: int):
    target = PostTarget(
        post_id=post_id, account_id=account_id, status=JobStatus.SUCCEEDED,
        external_post_id=f"ext-{dt.timestamp()}", published_at=dt,
    )
    db.session.add(target); db.session.flush()
    db.session.add(PostMetric(target_id=target.id, reach=reach, likes=likes))


def test_next_best_time_for_group_with_history(app):
    with app.app_context():
        user = User(email="b2@example.com", display_name="b2")
        db.session.add(user); db.session.flush()
        account = SocialAccount(
            user_id=user.id, platform=Platform.INSTAGRAM,
            external_account_id="x", handle="h", access_token_enc=b"a",
        )
        db.session.add(account); db.session.flush()
        group = AccountGroup(user_id=user.id, name="g2")
        group.accounts.append(account)
        db.session.add(group); db.session.flush()
        post = Post(user_id=user.id, title="t", caption="c")
        db.session.add(post); db.session.flush()

        # Three Mondays at 09:00 UTC with strong engagement
        for week in range(3):
            _post_with_metric(
                app,
                account_id=account.id, post_id=post.id,
                dt=datetime(2026, 4, 6 + week * 7, 9, 0, tzinfo=timezone.utc),
                reach=100, likes=20,
            )
        db.session.commit()
        result = next_best_time_for_group(group.id, min_samples=2,
                                            after=datetime(2026, 5, 5, 14, 0,
                                                           tzinfo=timezone.utc))
        assert result is not None
        assert result.weekday() == 0  # Monday
        assert result.hour == 9


def test_distribute_with_use_best_time_overrides_scheduled_for(client, app):
    """When use_best_time is set, /distribute should swap in the learned slot."""
    with app.app_context():
        user = User(email="d@example.com", display_name="d")
        db.session.add(user); db.session.flush()
        account = SocialAccount(
            user_id=user.id, platform=Platform.INSTAGRAM,
            external_account_id="x", handle="h", access_token_enc=b"a",
        )
        db.session.add(account); db.session.flush()
        group = AccountGroup(user_id=user.id, name="g")
        group.accounts.append(account)
        db.session.add(group); db.session.flush()
        post = Post(user_id=user.id, title="t", caption="c")
        db.session.add(post); db.session.commit()
        group_id, post_id, user_id = group.id, post.id, user.id

    login_as(client, user_id)
    forced_time = datetime(2026, 6, 1, 9, 0, tzinfo=timezone.utc)
    with patch("app.api.posts.next_best_time_for_group", return_value=forced_time):
        res = client.post(f"/api/posts/{post_id}/distribute", json={
            "group_ids": [group_id],
            "use_best_time": True,
            "dry_run": True,
            "jitter_minutes": 0,
        })
    assert res.status_code == 200
    data = res.get_json()
    assert data["best_time_used"][str(group_id)] == "learned"
    assert data["plan"][0]["scheduled_for"].startswith("2026-06-01T09:00")


def test_distribute_with_use_best_time_falls_back_when_no_data(client, app):
    """No history → distribute falls back to scheduled_for / now and reports it."""
    with app.app_context():
        user = User(email="d2@example.com", display_name="d")
        db.session.add(user); db.session.flush()
        account = SocialAccount(
            user_id=user.id, platform=Platform.INSTAGRAM,
            external_account_id="x", handle="h", access_token_enc=b"a",
        )
        db.session.add(account); db.session.flush()
        group = AccountGroup(user_id=user.id, name="g")
        group.accounts.append(account)
        db.session.add(group); db.session.flush()
        post = Post(user_id=user.id, title="t", caption="c")
        db.session.add(post); db.session.commit()
        group_id, post_id, user_id = group.id, post.id, user.id

    login_as(client, user_id)
    res = client.post(f"/api/posts/{post_id}/distribute", json={
        "group_ids": [group_id],
        "use_best_time": True,
        "dry_run": True,
    })
    assert res.status_code == 200
    data = res.get_json()
    assert data["best_time_used"][str(group_id)] == "fallback_no_data"
