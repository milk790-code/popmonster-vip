"""Compliance engine surface checks (no external services hit)."""
from app.compliance.engine import ComplianceEngine
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


def _seed(app):
    user = User(email="t@example.com", display_name="t")
    db.session.add(user)
    db.session.flush()

    media = MediaAsset(
        user_id=user.id,
        kind="video",
        storage_url="https://example.com/v.mp4",
        mime_type="video/mp4",
    )
    db.session.add(media)
    db.session.flush()

    post = Post(user_id=user.id, title="Test", caption="hello world", media_id=media.id)
    db.session.add(post)
    db.session.flush()

    account = SocialAccount(
        user_id=user.id,
        platform=Platform.TIKTOK,
        external_account_id="abc",
        handle="abc",
        access_token_enc=b"",
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
    return post, target


def test_engine_flags_oversize_caption(app):
    with app.app_context():
        post, target = _seed(app)
        post.caption = "x" * 3000  # exceeds TikTok's 2200 limit
        findings = ComplianceEngine().evaluate(post, [target])
        platform_findings = [f for f in findings if f.checker.startswith("platform_rules:")]
        assert any(not f.passed for f in platform_findings)


def test_engine_passes_clean_post(app):
    with app.app_context():
        post, target = _seed(app)
        findings = ComplianceEngine().evaluate(post, [target])
        platform_findings = [f for f in findings if f.checker.startswith("platform_rules:")]
        assert all(f.passed for f in platform_findings)
