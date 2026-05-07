"""C5: weekly insights digest — fact-grounded summary + email path."""
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest

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
from app.utils.digest import (
    EMOJI_MIN_SAMPLES,
    _emoji_comparison,
    _has_emoji,
    _template_narrative,
    build_user_digest,
    send_weekly_digests,
)


def _seed_user_with_published_targets(app, *, count, with_emoji=False, reach=1000,
                                       engagement=50):
    with app.app_context():
        user = User(email=f"d-{datetime.now().timestamp()}@e.com", display_name="d")
        db.session.add(user); db.session.flush()
        account = SocialAccount(
            user_id=user.id, platform=Platform.INSTAGRAM,
            external_account_id="x", handle="x", access_token_enc=b"x",
        )
        db.session.add(account); db.session.flush()
        for i in range(count):
            cap = ("🔥 caption " if with_emoji else "plain caption ") + str(i)
            post = Post(user_id=user.id, title="t", caption=cap)
            db.session.add(post); db.session.flush()
            t = PostTarget(
                post_id=post.id, account_id=account.id,
                status=JobStatus.SUCCEEDED,
                published_at=datetime.now(timezone.utc) - timedelta(days=2),
                overrides={"caption": cap},
            )
            db.session.add(t); db.session.flush()
            db.session.add(PostMetric(
                target_id=t.id, fetched_at=datetime.now(timezone.utc),
                reach=reach, likes=engagement, comments=0, shares=0, saves=0,
            ))
        db.session.commit()
        return user.id, account.id


# -- _has_emoji ------------------------------------------------------

def test_has_emoji_detects_common_ranges():
    assert _has_emoji("hello 🔥") is True
    assert _has_emoji("plain text") is False
    assert _has_emoji("✨ sparkle") is True


# -- _emoji_comparison min samples ----------------------------------

def test_emoji_comparison_returns_none_when_below_min_samples():
    snaps = []
    # 2 with emoji, 1 without — below threshold
    from app.utils.digest import TargetSnapshot
    for i in range(2):
        snaps.append(TargetSnapshot(i, "ig", "x", "🔥 hi", 100, 10, 0.10))
    snaps.append(TargetSnapshot(99, "ig", "x", "hi", 100, 5, 0.05))
    assert _emoji_comparison(snaps) is None


def test_emoji_comparison_computes_delta_when_threshold_met():
    from app.utils.digest import TargetSnapshot
    snaps = []
    for i in range(EMOJI_MIN_SAMPLES):
        snaps.append(TargetSnapshot(i, "ig", "x", "🔥 hi", 100, 10, 0.10))
    for i in range(EMOJI_MIN_SAMPLES):
        snaps.append(TargetSnapshot(100 + i, "ig", "x", "hi", 100, 5, 0.05))
    cmp = _emoji_comparison(snaps)
    assert cmp is not None
    assert cmp["with_emoji_samples"] == EMOJI_MIN_SAMPLES
    assert cmp["delta_pct"] == 100.0  # 10% / 5% = +100%


# -- build_user_digest end-to-end -----------------------------------

def test_build_user_digest_aggregates_correctly(app):
    uid, _ = _seed_user_with_published_targets(
        app, count=5, with_emoji=False, reach=1000, engagement=50,
    )
    with app.app_context():
        digest = build_user_digest(uid)
    assert digest is not None
    assert digest.total_published == 5
    assert digest.total_reach == 5000
    assert digest.total_engagement == 250
    assert digest.avg_rate == 0.05
    assert digest.best is not None
    assert digest.narrative  # template fallback always populates


def test_build_user_digest_returns_none_for_unknown_user(app):
    with app.app_context():
        assert build_user_digest(999999) is None


def test_build_user_digest_handles_no_posts(app):
    with app.app_context():
        u = User(email="empty@e.com", display_name="empty")
        db.session.add(u); db.session.commit(); uid = u.id
    with app.app_context():
        digest = build_user_digest(uid)
    assert digest is not None
    assert digest.total_published == 0
    assert digest.has_data() is False
    assert "Keep going" in digest.narrative


# -- _template_narrative is purely deterministic --------------------

def test_template_narrative_uses_only_provided_numbers(app):
    """Critical anti-fabrication property — narrative numbers must match
    the digest fields, not invented stats."""
    uid, _ = _seed_user_with_published_targets(
        app, count=3, reach=2000, engagement=80,
    )
    with app.app_context():
        digest = build_user_digest(uid)
    n = digest.narrative
    assert "3 posts" in n
    assert "6,000" in n  # total reach
    assert "240" in n     # total engagement
    assert digest.total_engagement * 100 // digest.total_reach == 4  # ≈4%


# -- send_weekly_digests -------------------------------------------

def test_send_weekly_digests_emails_active_users(app):
    uid, _ = _seed_user_with_published_targets(app, count=3)
    with patch("app.utils.digest.send_failure_email") as send:
        with app.app_context():
            counts = send_weekly_digests()
    assert counts["sent"] == 1
    send.assert_called_once()
    kwargs = send.call_args.kwargs
    assert "Weekly insights" in kwargs["subject"]


def test_send_weekly_digests_skips_users_with_no_data(app):
    """User exists but no published targets → don't send."""
    with app.app_context():
        u = User(email="silent@e.com", display_name="silent")
        db.session.add(u); db.session.commit()
    with patch("app.utils.digest.send_failure_email") as send:
        with app.app_context():
            counts = send_weekly_digests()
    assert counts["sent"] == 0
    send.assert_not_called()


# -- HTTP endpoints -------------------------------------------------

def test_digest_preview_endpoint_returns_json(client, app):
    uid, _ = _seed_user_with_published_targets(app, count=4)
    res = client.get(f"/api/insights/digest/preview?user_id={uid}")
    assert res.status_code == 200
    body = res.get_json()
    assert body["total_published"] == 4
    assert body["narrative"]


def test_digest_preview_unknown_user_404(client):
    res = client.get("/api/insights/digest/preview?user_id=999999")
    assert res.status_code == 404


def test_digest_send_returns_sent_false_without_sendgrid(client, app):
    uid, _ = _seed_user_with_published_targets(app, count=2)
    # SENDGRID_API_KEY not set in test env → sent:false but no error
    with patch("app.utils.notify.send_failure_email"):
        res = client.post("/api/insights/digest/send",
                          json={"user_id": uid})
    assert res.status_code == 200
    body = res.get_json()
    assert body["sent"] is False  # no SendGrid creds in test env
    assert "narrative_preview" in body


def test_digest_send_no_data_returns_skip_reason(client, app):
    with app.app_context():
        u = User(email="qq@e.com", display_name="qq")
        db.session.add(u); db.session.commit(); uid = u.id
    res = client.post("/api/insights/digest/send", json={"user_id": uid})
    body = res.get_json()
    assert body["sent"] is False
    assert "no published" in body["reason"]


# -- _claude_narrative respects the no-fabrication contract --------

def test_claude_narrative_falls_back_to_template_on_error(app):
    uid, _ = _seed_user_with_published_targets(app, count=3)
    with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "fake"}):
        with patch("anthropic.Anthropic", side_effect=Exception("network")):
            with app.app_context():
                digest = build_user_digest(uid)
    # Template fallback path exercised; numbers still real.
    assert "3 posts" in digest.narrative
