"""Insights ingestion + endpoints (no real API calls)."""
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

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
from app.platforms.base import InsightsSnapshot
from app.scheduler import tasks


def _seed(app, *, platform=Platform.INSTAGRAM):
    with app.app_context():
        user = User(email="i@example.com", display_name="i")
        db.session.add(user)
        db.session.flush()
        account = SocialAccount(
            user_id=user.id, platform=platform,
            external_account_id="ext-1", handle="@h",
            access_token_enc=b"a",
        )
        db.session.add(account)
        db.session.flush()
        post = Post(user_id=user.id, title="t", caption="c")
        db.session.add(post)
        db.session.flush()
        target = PostTarget(
            post_id=post.id, account_id=account.id,
            status=JobStatus.SUCCEEDED,
            external_post_id="external-123",
            published_at=datetime.now(timezone.utc) - timedelta(hours=2),
        )
        db.session.add(target)
        db.session.commit()
        return user.id, account.id, post.id, target.id


def test_ingest_inserts_metric_row(app):
    _, _, _, target_id = _seed(app)
    snapshot = InsightsSnapshot(
        reach=1200, impressions=1500, likes=80, comments=10, shares=4, saves=12,
        raw={"reach": 1200},
    )
    fake_publisher = MagicMock()
    fake_publisher.fetch_insights.return_value = snapshot
    with patch("app.scheduler.tasks.get_publisher", return_value=fake_publisher), \
         patch("app.scheduler.tasks._decrypt_token", return_value=MagicMock()):
        with app.app_context():
            tasks.ingest_insights()
            metrics = db.session.query(PostMetric).filter_by(target_id=target_id).all()
            assert len(metrics) == 1
            assert metrics[0].reach == 1200
            assert metrics[0].likes == 80


def test_ingest_skips_when_publisher_returns_none(app):
    _, _, _, target_id = _seed(app)
    fake_publisher = MagicMock()
    fake_publisher.fetch_insights.return_value = None
    with patch("app.scheduler.tasks.get_publisher", return_value=fake_publisher), \
         patch("app.scheduler.tasks._decrypt_token", return_value=MagicMock()):
        with app.app_context():
            tasks.ingest_insights()
            assert db.session.query(PostMetric).count() == 0


def test_insights_endpoint_returns_latest_per_target(client, app):
    _, _, post_id, target_id = _seed(app)
    with app.app_context():
        db.session.add(PostMetric(target_id=target_id, reach=100, likes=5,
                                  fetched_at=datetime.now(timezone.utc)
                                  - timedelta(hours=1)))
        db.session.add(PostMetric(target_id=target_id, reach=300, likes=20))
        db.session.commit()

    res = client.get(f"/api/insights?post_id={post_id}")
    assert res.status_code == 200
    data = res.get_json()
    assert len(data) == 1
    assert data[0]["metric"]["reach"] == 300  # latest, not first


def test_insights_endpoint_filter_by_group(client, app):
    user_id, account_id, _, target_id = _seed(app)
    with app.app_context():
        group = AccountGroup(user_id=user_id, name="g")
        db.session.add(group)
        db.session.flush()
        group.accounts.append(db.session.get(SocialAccount, account_id))
        db.session.add(PostMetric(target_id=target_id, reach=42))
        db.session.commit()
        group_id = group.id
    res = client.get(f"/api/insights?group_id={group_id}")
    assert res.status_code == 200
    assert len(res.get_json()) == 1
