"""Cron successor materialisation."""
from datetime import datetime, timedelta, timezone

from app.extensions import db
from app.models import (
    JobStatus,
    Platform,
    Post,
    PostTarget,
    SocialAccount,
    User,
)
from app.scheduler.tasks import advance_cron_targets


def test_cron_creates_successor(app):
    with app.app_context():
        user = User(email="t@example.com", display_name="t")
        db.session.add(user)
        db.session.flush()

        post = Post(user_id=user.id, title="t", caption="c")
        db.session.add(post)
        db.session.flush()

        account = SocialAccount(
            user_id=user.id,
            platform=Platform.FACEBOOK,
            external_account_id="page",
            handle="page",
            access_token_enc=b"",
        )
        db.session.add(account)
        db.session.flush()

        parent = PostTarget(
            post_id=post.id,
            account_id=account.id,
            cron_expr="0 9 * * *",
            timezone="UTC",
            scheduled_for=datetime.now(timezone.utc) - timedelta(days=1),
            status=JobStatus.SUCCEEDED,
            published_at=datetime.now(timezone.utc) - timedelta(days=1),
        )
        db.session.add(parent)
        db.session.commit()

        advance_cron_targets()

        successors = (
            db.session.query(PostTarget)
            .filter(PostTarget.id != parent.id)
            .all()
        )
        assert len(successors) == 1
        successor = successors[0]
        assert successor.cron_expr == "0 9 * * *"
        assert successor.status == JobStatus.PENDING
        assert successor.scheduled_for is not None
