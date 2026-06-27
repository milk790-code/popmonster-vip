"""Best-time recommendation logic."""
from datetime import datetime, timezone

from app.extensions import db
from app.models import (
    JobStatus,
    Platform,
    Post,
    PostMetric,
    PostTarget,
    SocialAccount,
    User,
)
from app.utils.best_times import best_times_for_account

from .conftest import login_as


def _publish_at(app, *, account_id, post_id, dt: datetime, reach: int, likes: int):
    target = PostTarget(
        post_id=post_id, account_id=account_id, status=JobStatus.SUCCEEDED,
        external_post_id=f"ext-{dt.timestamp()}", published_at=dt,
    )
    db.session.add(target)
    db.session.flush()
    db.session.add(PostMetric(target_id=target.id, reach=reach, likes=likes))


def test_best_times_returns_top_buckets(app):
    with app.app_context():
        user = User(email="b@example.com", display_name="b")
        db.session.add(user)
        db.session.flush()
        account = SocialAccount(
            user_id=user.id, platform=Platform.INSTAGRAM,
            external_account_id="x", handle="h", access_token_enc=b"a",
        )
        db.session.add(account)
        db.session.flush()
        post = Post(user_id=user.id, title="t", caption="c")
        db.session.add(post)
        db.session.flush()

        # Three posts at Mon 09:00 with strong engagement
        for week in range(3):
            _publish_at(
                app,
                account_id=account.id,
                post_id=post.id,
                dt=datetime(2026, 4, 6 + week * 7, 9, 0, tzinfo=timezone.utc),
                reach=100,
                likes=20,
            )
        # Three posts at Sat 03:00 with weak engagement
        for week in range(3):
            _publish_at(
                app,
                account_id=account.id,
                post_id=post.id,
                dt=datetime(2026, 4, 11 + week * 7, 3, 0, tzinfo=timezone.utc),
                reach=100,
                likes=2,
            )
        db.session.commit()

        slots = best_times_for_account(account.id, top_n=2, min_samples=2)
        assert len(slots) == 2
        # Mon 09:00 should rank first (engagement rate 0.20 vs 0.02)
        top = slots[0]
        assert top.day == "Mon"
        assert top.hour == 9
        assert top.avg_engagement_rate > slots[1].avg_engagement_rate


def test_best_times_respects_min_samples(app):
    with app.app_context():
        user = User(email="b2@example.com", display_name="b")
        db.session.add(user)
        db.session.flush()
        account = SocialAccount(
            user_id=user.id, platform=Platform.INSTAGRAM,
            external_account_id="x", handle="h", access_token_enc=b"a",
        )
        db.session.add(account)
        db.session.flush()
        post = Post(user_id=user.id, title="t", caption="c")
        db.session.add(post)
        db.session.flush()

        _publish_at(
            app, account_id=account.id, post_id=post.id,
            dt=datetime(2026, 4, 6, 9, 0, tzinfo=timezone.utc),
            reach=100, likes=20,
        )
        db.session.commit()

        # min_samples=3 → no slot survives
        assert best_times_for_account(account.id, min_samples=3) == []
        # min_samples=1 → one slot returned
        assert len(best_times_for_account(account.id, min_samples=1)) == 1


def test_best_times_endpoint_requires_filter(client, app):
    with app.app_context():
        user = User(email="bt@example.com", display_name="bt")
        db.session.add(user)
        db.session.commit()
        uid = user.id
    login_as(client, uid)
    res = client.get("/api/insights/best-times")
    assert res.status_code == 400
