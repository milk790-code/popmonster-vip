"""Distribute fanout: jitter, group expansion, dry-run, variant overrides."""
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from app.extensions import db
from app.models import (
    AccountGroup,
    JobStatus,
    MediaAsset,
    Platform,
    Post,
    PostTarget,
    SocialAccount,
    User,
)
from app.utils.jitter import spread

from .conftest import login_as


def _make_group(app, *, accounts: list[Platform], style: dict | None = None):
    with app.app_context():
        user = User(email="t@example.com", display_name="t")
        db.session.add(user)
        db.session.flush()

        group = AccountGroup(
            user_id=user.id,
            name="g1",
            style_profile=style or {"tone": "casual", "hashtag_pool": ["#a", "#b"]},
        )
        db.session.add(group)
        db.session.flush()

        for i, p in enumerate(accounts):
            acct = SocialAccount(
                user_id=user.id,
                platform=p,
                external_account_id=f"ext-{i}",
                handle=f"h{i}",
                access_token_enc=b"a",
            )
            db.session.add(acct)
            db.session.flush()
            group.accounts.append(acct)

        post = Post(user_id=user.id, title="t", caption="hello world")
        db.session.add(post)
        db.session.commit()
        return user.id, group.id, post.id


def test_jitter_spread_is_deterministic_and_inside_window(app):
    base = datetime(2026, 5, 4, 9, 0, 0, tzinfo=timezone.utc)
    a = spread(base, 30, "seed-1", 5)
    b = spread(base, 30, "seed-1", 5)
    assert a == b  # deterministic
    assert all(base <= t <= base + timedelta(minutes=30) for t in a)
    assert a == sorted(a)


def test_jitter_zero_window_returns_base_repeated():
    base = datetime(2026, 5, 4, 9, 0, 0, tzinfo=timezone.utc)
    out = spread(base, 0, "s", 3)
    assert out == [base, base, base]


def test_distribute_jitter_is_centered_and_scheduled_at_alias(client, app):
    user_id, group_id, post_id = _make_group(
        app, accounts=[Platform.FACEBOOK] * 20
    )
    login_as(client, user_id)
    res = client.post(
        f"/api/posts/{post_id}/distribute",
        json={
            "group_ids": [group_id],
            "scheduled_at": "2026-05-04T18:00:00+08:00",
            "timezone": "Asia/Taipei",
            "jitter_minutes": 90,
            "dry_run": True,
        },
    )
    assert res.status_code == 200, res.data
    scheduled = [datetime.fromisoformat(p["scheduled_for"]) for p in res.get_json()["plan"]]
    base = datetime(2026, 5, 4, 10, 0, 0, tzinfo=timezone.utc)
    assert all(base - timedelta(minutes=90) <= t <= base + timedelta(minutes=90) for t in scheduled)
    assert min(scheduled) < base
    assert max(scheduled) > base


def test_distribute_creates_targets_for_all_group_accounts(client, app):
    user_id, group_id, post_id = _make_group(
        app, accounts=[Platform.FACEBOOK, Platform.INSTAGRAM, Platform.YOUTUBE]
    )
    login_as(client, user_id)
    future = (datetime.now(timezone.utc) + timedelta(days=1)).strftime("%Y-%m-%dT%H:%M:%S")
    with patch("app.api.posts.dispatch_target.delay") as dispatch:
        res = client.post(
            f"/api/posts/{post_id}/distribute",
            json={
                "group_ids": [group_id],
                "scheduled_for": future,
                "timezone": "UTC",
                "jitter_minutes": 15,
                "generate_variants": False,
            },
        )
    assert res.status_code == 201, res.data
    data = res.get_json()
    assert len(data["created_target_ids"]) == 3
    assert len(data["plan"]) == 3
    assert {p["platform"] for p in data["plan"]} == {"facebook", "instagram", "youtube"}
    dispatch.assert_not_called()  # all in the future

    with app.app_context():
        targets = db.session.query(PostTarget).filter_by(post_id=post_id).all()
        scheduled = [t.scheduled_for for t in targets]
        assert all(t.status == JobStatus.PENDING for t in targets)
        assert all(t.group_id == group_id for t in targets)
        # Times must be unique because jitter offsets are derived per-account.
        assert len(set(scheduled)) == 3


def test_distribute_dry_run_persists_nothing(client, app):
    user_id, group_id, post_id = _make_group(app, accounts=[Platform.FACEBOOK])
    login_as(client, user_id)
    res = client.post(
        f"/api/posts/{post_id}/distribute",
        json={"group_ids": [group_id], "dry_run": True},
    )
    assert res.status_code == 200
    assert res.get_json()["created_target_ids"] == []
    with app.app_context():
        assert db.session.query(PostTarget).count() == 0


def test_distribute_media_map_sets_per_account_media(client, app):
    user_id, group_id, post_id = _make_group(
        app, accounts=[Platform.FACEBOOK, Platform.YOUTUBE]
    )
    login_as(client, user_id)
    with app.app_context():
        account_ids = [
            a.id for a in db.session.get(AccountGroup, group_id).accounts
        ]
        media = [
            MediaAsset(
                user_id=user_id,
                kind="video",
                storage_url=f"https://cdn.test/{i}.mp4",
                mime_type="video/mp4",
            )
            for i in range(2)
        ]
        db.session.add_all(media)
        db.session.commit()
        media_ids = [m.id for m in media]

    media_map = {str(account_ids[0]): media_ids[0], str(account_ids[1]): media_ids[1]}
    res = client.post(
        f"/api/posts/{post_id}/distribute",
        json={"group_ids": [group_id], "media_map": media_map, "dry_run": True},
    )
    assert res.status_code == 200, res.data
    plan = sorted(res.get_json()["plan"], key=lambda p: p["account_id"])
    assert {p["media_source"] for p in plan} == {"media_map"}
    assert {p["media_id"] for p in plan} == set(media_ids)

    res = client.post(
        f"/api/posts/{post_id}/distribute",
        json={
            "group_ids": [group_id],
            "media_map": media_map,
            "scheduled_for": (
                datetime.now(timezone.utc) + timedelta(days=1)
            ).strftime("%Y-%m-%dT%H:%M:%S"),
        },
    )
    assert res.status_code == 201, res.data
    with app.app_context():
        targets = db.session.query(PostTarget).filter_by(post_id=post_id).all()
        assert {
            t.account_id: t.overrides["_media_id"] for t in targets
        } == {account_ids[0]: media_ids[0], account_ids[1]: media_ids[1]}


def test_distribute_media_map_rejects_other_group_accounts(client, app):
    user_id, group_id, post_id = _make_group(app, accounts=[Platform.FACEBOOK])
    login_as(client, user_id)
    with app.app_context():
        other_account = SocialAccount(
            user_id=user_id,
            platform=Platform.FACEBOOK,
            external_account_id="outside-group",
            handle="outside",
            access_token_enc=b"a",
        )
        media = MediaAsset(
            user_id=user_id,
            kind="video",
            storage_url="https://cdn.test/v.mp4",
            mime_type="video/mp4",
        )
        db.session.add_all([other_account, media])
        db.session.commit()
        other_account_id = other_account.id
        media_id = media.id
    res = client.post(
        f"/api/posts/{post_id}/distribute",
        json={
            "group_ids": [group_id],
            "media_map": {str(other_account_id): media_id},
            "dry_run": True,
        },
    )
    assert res.status_code == 400
    assert res.get_json()["error"] == "media_map includes accounts outside selected groups"


def test_schedule_item_can_override_media_id(client, app):
    user_id, group_id, post_id = _make_group(app, accounts=[Platform.YOUTUBE])
    login_as(client, user_id)
    with app.app_context():
        account_id = db.session.get(AccountGroup, group_id).accounts[0].id
        media = MediaAsset(
            user_id=user_id,
            kind="video",
            storage_url="https://cdn.test/y.mp4",
            mime_type="video/mp4",
        )
        db.session.add(media)
        db.session.commit()
        media_id = media.id

    res = client.post(
        "/api/schedules",
        json={
            "post_id": post_id,
            "items": [
                {
                    "account_id": account_id,
                    "media_id": media_id,
                    "scheduled_at": "2026-05-04T18:00:00+08:00",
                    "timezone": "Asia/Taipei",
                }
            ],
        },
    )
    assert res.status_code == 201, res.data
    with app.app_context():
        target = db.session.query(PostTarget).filter_by(post_id=post_id).one()
        assert target.overrides["_media_id"] == media_id
        assert target.scheduled_for == datetime(2026, 5, 4, 10, 0, 0)


def test_distribute_with_variants_uses_template_fallback(client, app):
    """Without ANTHROPIC_API_KEY the variant engine falls back to templates."""
    user_id, group_id, post_id = _make_group(
        app, accounts=[Platform.INSTAGRAM, Platform.TIKTOK],
        style={"tone": "casual", "emoji_density": "high",
               "hashtag_pool": ["#美食", "#日常", "#推薦", "#療癒",
                                "#週末", "#輕食", "#台北", "#甜點"]},
    )
    login_as(client, user_id)
    future = (datetime.now(timezone.utc) + timedelta(days=1)).strftime("%Y-%m-%dT%H:%M:%S")
    res = client.post(
        f"/api/posts/{post_id}/distribute",
        json={
            "group_ids": [group_id],
            "scheduled_for": future,
            "generate_variants": True,
        },
    )
    assert res.status_code == 201
    plan = res.get_json()["plan"]
    assert all(item["variant_engine"] == "template" for item in plan)
    # Template engine must produce different captions for each account.
    captions = [item["preview_caption"] for item in plan]
    assert len(set(captions)) == len(captions)


def test_distribute_skips_revoked_accounts(client, app):
    user_id, group_id, post_id = _make_group(app, accounts=[Platform.FACEBOOK, Platform.TIKTOK])
    login_as(client, user_id)
    with app.app_context():
        from datetime import datetime
        group = db.session.get(AccountGroup, group_id)
        group.accounts[0].revoked_at = datetime.now(timezone.utc)
        db.session.commit()

    res = client.post(
        f"/api/posts/{post_id}/distribute",
        json={"group_ids": [group_id], "dry_run": True},
    )
    plan = res.get_json()["plan"]
    assert len(plan) == 1
    assert plan[0]["platform"] == "tiktok"


def test_distribute_unauthenticated_is_rejected(client, app):
    """No session → 401, never silent impersonation."""
    _, group_id, post_id = _make_group(app, accounts=[Platform.FACEBOOK])
    res = client.post(
        f"/api/posts/{post_id}/distribute",
        json={"group_ids": [group_id], "dry_run": True},
    )
    assert res.status_code == 401


def test_distribute_other_users_post_is_forbidden(client, app):
    """IDOR: logging in as a different user must not reach another's post."""
    _, group_id, post_id = _make_group(app, accounts=[Platform.FACEBOOK])
    with app.app_context():
        attacker = User(email="attacker@example.com", display_name="x")
        db.session.add(attacker)
        db.session.commit()
        attacker_id = attacker.id
    login_as(client, attacker_id)
    res = client.post(
        f"/api/posts/{post_id}/distribute",
        json={"group_ids": [group_id], "dry_run": True},
    )
    assert res.status_code == 403
