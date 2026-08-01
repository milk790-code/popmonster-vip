"""Cross-account boost: our other Pages like AND comment on our own post.

Each test here pins one guardrail that exists because of a specific Meta
policy sentence, not because it seemed tidy. If a test looks over-strict,
read the docstring before relaxing it.
"""
import os
from types import SimpleNamespace

import pytest

from app.extensions import db
from app.models import (
    AuditLog, JobStatus, Platform, Post, PostTarget, SocialAccount, User,
)
from app.utils import boost as boost_rules
from app.utils.account_profile import validate_profile, write_profile
from app.utils.crypto import cipher

from .conftest import login_as


def _account(account_id, *, role="supporter", pool=None, max_per_day=1,
             link_src="fb-a1b2c3", handle=None, revoked=None):
    """A stand-in SocialAccount for the pure planner (no DB needed)."""
    profile = validate_profile({
        "link_src": link_src,
        "interaction": {
            "role": role,
            "max_per_day": max_per_day,
            "comment_pool": pool if pool is not None else [
                "這款我們自己店裡也在用，實際差在哪寫在這",
                "常被問順序怎麼排，整理成一頁了",
                "新手最容易卡的地方，這頁講得比較清楚",
            ],
        },
    })
    account = SimpleNamespace(
        id=account_id,
        handle=handle or f"@page{account_id}",
        external_account_id=f"page-{account_id}",
        revoked_at=revoked,
        extra={},
    )
    write_profile(account, profile)
    return account


def _plan(supporters, *, leader=99, spent=None, **kwargs):
    return boost_rules.plan_boost(
        post_key="target:1",
        leader_account_id=leader,
        supporters=supporters,
        spent_today=spent or {},
        **kwargs,
    )


# --- the link ------------------------------------------------------------


def test_comment_carries_the_pages_own_tracked_funnel_link():
    plan = _plan([_account(1, link_src="fb-a1b2c3")])
    assert len(plan.actions) == 1
    message = plan.actions[0].message
    # Fully qualified or Facebook won't linkify it -- a bare domain reads as
    # spam with no preview card.
    assert "https://popmonster.vip/go?src=fb-a1b2c3" in message


def test_unknown_src_falls_back_to_an_allow_listed_one():
    """``src`` is a closed allow-list on the frontend and the events worker.

    An off-list value doesn't break the link, it silently deletes the
    attribution -- so we never emit one.
    """
    for junk in ["", "qr-card", "FB-A1B2C3", "fb-zzzzzz", "fb-a1b2c"]:
        link = boost_rules.funnel_link(junk)
        assert link == "https://popmonster.vip/go?src=social", junk


def test_link_placeholder_is_filled_in_place():
    plan = _plan([_account(1, pool=["先看這頁再決定 {link} 不用先問我"])])
    message = plan.actions[0].message
    assert "{link}" not in message
    assert message.startswith("先看這頁再決定 https://popmonster.vip/go?src=")


# --- who speaks ----------------------------------------------------------


def test_role_off_never_participates():
    plan = _plan([_account(1, role="off"), _account(2, role="leader")])
    assert plan.actions == []


def test_a_page_does_not_support_its_own_post():
    plan = _plan([_account(7)], leader=7)
    assert plan.actions == []


def test_revoked_account_is_skipped_with_a_reason():
    plan = _plan([_account(1, revoked="2026-01-01")])
    assert plan.actions == []
    assert "撤銷" in plan.skipped[0]["reason"]


def test_empty_pool_stays_silent_instead_of_inventing_a_sentence():
    """No pool means no comment. Sharing one house sentence across Pages is
    the "same content across many assets" pattern Meta flags."""
    plan = _plan([_account(1, pool=[])])
    assert plan.actions == []
    assert "素材池" in plan.skipped[0]["reason"]


def test_filler_length_comments_are_rejected_at_both_ends():
    """"推" / "+1" is the coordinated-inauthentic-comment shape.

    The profile validator refuses to store it, and the planner refuses to
    use it even if a row predates the validator.
    """
    with pytest.raises(Exception) as stored:
        validate_profile({"interaction": {"role": "supporter",
                                          "comment_pool": ["推", "+1"]}})
    assert "at least 8 characters" in str(stored.value)

    smuggled = _account(1, pool=[])
    smuggled.extra = {"profile": {
        **smuggled.extra["profile"],
        "interaction": {"role": "supporter", "max_per_day": 1,
                        "comment_pool": ["推", "+1", "讚"]},
    }}
    assert _plan([smuggled]).actions == []


def test_daily_ceiling_is_enforced_per_page():
    used_up = _account(1, max_per_day=2)
    fresh = _account(2, max_per_day=2)
    plan = _plan([used_up, fresh], spent={1: 2, 2: 1})
    assert [a.account_id for a in plan.actions] == [2]
    assert any("上限" in s["reason"] for s in plan.skipped)


def test_a_post_never_gets_a_wall_of_our_own_pages():
    plan = _plan([_account(i) for i in range(1, 9)], limit=3)
    assert len(plan.actions) == 3
    assert len(plan.skipped) == 5


def test_limit_zero_disables_boosting_without_erroring():
    plan = _plan([_account(1), _account(2)], limit=0)
    assert plan.actions == []
    assert len(plan.skipped) == 2


# --- what they say -------------------------------------------------------


def test_two_pages_never_post_the_same_sentence_on_one_post():
    """Identical replicated text across assets is the flagged pattern."""
    shared = ["完全一樣的一句話素材池內容", "第二句也一樣的素材池內容啊"]
    plan = _plan([_account(1, pool=shared), _account(2, pool=shared)], limit=2)
    bodies = [a.message.split("\n")[0] for a in plan.actions]
    assert len(bodies) == 2
    assert bodies[0] != bodies[1]


def test_a_page_runs_out_of_unused_lines_rather_than_repeating():
    only_one = ["這是唯一的一句素材，沒有第二句"]
    plan = _plan([_account(1, pool=only_one), _account(2, pool=only_one)], limit=2)
    assert len(plan.actions) == 1
    assert "別的粉專" in plan.skipped[0]["reason"]


def test_the_plan_is_deterministic():
    """A retried task must land on the same sentences and the same clock,
    otherwise a replay stacks a second comment under the first."""
    first = _plan([_account(i) for i in range(1, 6)], limit=3)
    second = _plan([_account(i) for i in range(1, 6)], limit=3)
    assert [(a.account_id, a.message, a.delay_seconds) for a in first.actions] == \
           [(a.account_id, a.message, a.delay_seconds) for a in second.actions]


# --- when they say it ----------------------------------------------------


def test_actions_are_spread_out_never_a_burst():
    plan = _plan([_account(i) for i in range(1, 6)], limit=5,
                 window=180, min_delay=25)
    delays = [a.delay_seconds for a in plan.actions]
    assert delays == sorted(delays)
    assert min(delays) >= 25 * 60
    assert max(delays) <= 180 * 60
    # No two in the same minute -- five comments inside 60 seconds is the
    # "very high frequency" shape regardless of who clicked them.
    minutes = [d // 60 for d in delays]
    assert len(set(minutes)) == len(minutes)


# --- the master switch ---------------------------------------------------


def test_boost_is_off_unless_explicitly_turned_on(monkeypatch):
    monkeypatch.delenv("BOOST_ENABLED", raising=False)
    assert boost_rules.enabled() is False
    for value in ["0", "", "false", "no", "maybe"]:
        monkeypatch.setenv("BOOST_ENABLED", value)
        assert boost_rules.enabled() is False
    for value in ["1", "true", "YES", "on"]:
        monkeypatch.setenv("BOOST_ENABLED", value)
        assert boost_rules.enabled() is True


def test_env_limits_are_clamped_not_trusted(monkeypatch):
    monkeypatch.setenv("BOOST_MAX_SUPPORTERS_PER_POST", "500")
    assert boost_rules.max_supporters_per_post() == 8
    monkeypatch.setenv("BOOST_MAX_SUPPORTERS_PER_POST", "nonsense")
    assert boost_rules.max_supporters_per_post() == 3


# --- execution -----------------------------------------------------------


def _seed_published_post(app, *, supporters=2):
    with app.app_context():
        user = User(email="b@example.com", display_name="b")
        db.session.add(user)
        db.session.flush()
        enc = cipher().encrypt("tok")
        leader = SocialAccount(
            user_id=user.id, platform=Platform.FACEBOOK,
            external_account_id="page-leader", handle="@leader",
            access_token_enc=enc,
        )
        db.session.add(leader)
        db.session.flush()
        ids = []
        for i in range(supporters):
            account = SocialAccount(
                user_id=user.id, platform=Platform.FACEBOOK,
                external_account_id=f"page-{i}", handle=f"@support{i}",
                access_token_enc=enc,
            )
            db.session.add(account)
            db.session.flush()
            write_profile(account, validate_profile({
                "link_src": f"fb-00000{i}",
                "interaction": {
                    "role": "supporter",
                    "max_per_day": 1,
                    "comment_pool": [
                        f"第{i}個粉專自己的說法，內容不一樣",
                        f"第{i}個粉專的第二句，也不一樣",
                    ],
                },
            }))
            ids.append(account.id)
        post = Post(user_id=user.id, caption="hello")
        db.session.add(post)
        db.session.flush()
        target = PostTarget(
            post_id=post.id, account_id=leader.id,
            status=JobStatus.SUCCEEDED, external_post_id="page-leader_123",
        )
        db.session.add(target)
        db.session.commit()
        return user.id, target.id, ids


class _FakePublisher:
    def __init__(self):
        self.liked = []
        self.commented = []

    def like_as_page(self, token, object_id):
        self.liked.append(object_id)

    def comment_as_page(self, token, object_id, message):
        self.commented.append((object_id, message))
        return "comment-1"


def test_perform_boost_likes_then_comments_and_records_it(app, monkeypatch):
    monkeypatch.setenv("BOOST_ENABLED", "1")
    user_id, target_id, account_ids = _seed_published_post(app)
    from app.scheduler import tasks

    fake = _FakePublisher()
    monkeypatch.setattr(tasks, "get_publisher", lambda platform: fake)

    with app.app_context():
        result = tasks.perform_boost.run(
            target_id, account_ids[0], "自己的一句話\nhttps://popmonster.vip/go?src=fb-000000"
        )
        assert result["ok"] is True
        assert fake.liked == ["page-leader_123"]
        assert fake.commented[0][0] == "page-leader_123"
        assert "popmonster.vip/go?src=fb-000000" in fake.commented[0][1]
        logged = (
            db.session.query(AuditLog)
            .filter_by(action="boost.performed", resource_id=str(account_ids[0]))
            .one()
        )
        assert logged.detail["comment_id"] == "comment-1"


def test_perform_boost_does_nothing_while_the_switch_is_off(app, monkeypatch):
    monkeypatch.setenv("BOOST_ENABLED", "1")
    user_id, target_id, account_ids = _seed_published_post(app)
    from app.scheduler import tasks

    fake = _FakePublisher()
    monkeypatch.setattr(tasks, "get_publisher", lambda platform: fake)
    # Flipped off between scheduling and firing: the later check wins.
    monkeypatch.setenv("BOOST_ENABLED", "0")
    with app.app_context():
        result = tasks.perform_boost.run(target_id, account_ids[0], "文字")
    assert result["ok"] is False
    assert fake.liked == [] and fake.commented == []


def test_daily_spend_counts_from_the_audit_log(app, monkeypatch):
    monkeypatch.setenv("BOOST_ENABLED", "1")
    user_id, target_id, account_ids = _seed_published_post(app)
    from app.scheduler import tasks

    with app.app_context():
        target = db.session.get(PostTarget, target_id)
        assert len(tasks.build_boost_plan(target).actions) == 2
        # One page has now used its single daily slot.
        db.session.add(AuditLog(
            actor_user_id=user_id, action="boost.performed",
            resource_type="social_account", resource_id=str(account_ids[0]),
            detail={},
        ))
        db.session.commit()
        plan = tasks.build_boost_plan(target)
        assert [a.account_id for a in plan.actions] == [account_ids[1]]


def test_supporters_stay_inside_the_brand_line(app, monkeypatch):
    """A Page from an unrelated line must not chime in by default.

    Unrelated assets moving together is the network shape; keeping support
    inside the line is also the only way the comment makes sense to a
    reader.
    """
    monkeypatch.setenv("BOOST_ENABLED", "1")
    user_id, target_id, account_ids = _seed_published_post(app)
    from app.models import AccountGroup
    from app.scheduler import tasks

    with app.app_context():
        target = db.session.get(PostTarget, target_id)
        line = AccountGroup(user_id=user_id, name="泡泡怪獸")
        db.session.add(line)
        db.session.flush()
        # Leader and only the first supporter belong to the line.
        line.accounts.append(target.account)
        line.accounts.append(db.session.get(SocialAccount, account_ids[0]))
        db.session.commit()

        assert [a.account_id for a in tasks.build_boost_plan(target).actions] == \
               [account_ids[0]]

        monkeypatch.setenv("BOOST_CROSS_LINE", "1")
        assert len(tasks.build_boost_plan(target).actions) == 2


# --- dashboard views -----------------------------------------------------


def test_settings_flags_a_supporter_that_can_never_speak(app, client, monkeypatch):
    monkeypatch.delenv("BOOST_ENABLED", raising=False)
    user_id, target_id, account_ids = _seed_published_post(app)
    with app.app_context():
        account = db.session.get(SocialAccount, account_ids[0])
        write_profile(account, validate_profile({
            "interaction": {"role": "supporter", "max_per_day": 1,
                            "comment_pool": []},
        }))
        db.session.commit()
    login_as(client, user_id)
    body = client.get("/api/boost/settings").get_json()
    assert body["enabled"] is False
    by_id = {a["account_id"]: a for a in body["accounts"]}
    assert by_id[account_ids[0]]["ready"] is False
    assert by_id[account_ids[1]]["ready"] is True
    assert body["supporters_ready"] == 1


def test_preview_is_a_dry_run(app, client, monkeypatch):
    monkeypatch.setenv("BOOST_ENABLED", "1")
    user_id, target_id, account_ids = _seed_published_post(app)
    login_as(client, user_id)
    body = client.get(f"/api/boost/preview?target_id={target_id}").get_json()
    assert body["leader"] == "@leader"
    assert len(body["actions"]) == 2
    assert all("popmonster.vip/go?src=" in a["message"] for a in body["actions"])
    with app.app_context():
        # A preview must not look like an action to the audit trail.
        assert db.session.query(AuditLog).filter_by(
            action="boost.performed").count() == 0


def test_preview_refuses_another_users_target(app, client):
    user_id, target_id, _ = _seed_published_post(app)
    with app.app_context():
        other = User(email="other@example.com", display_name="o")
        db.session.add(other)
        db.session.commit()
        other_id = other.id
    login_as(client, other_id)
    assert client.get(f"/api/boost/preview?target_id={target_id}").status_code == 404


# --- the first comment on our own post (where the funnel link lives) -----


def test_first_comment_outcome_is_reported_not_swallowed(monkeypatch):
    """A comment that has never once worked used to look exactly like one
    working fine. The post must still succeed, but the outcome has to come
    back so the caller can record it."""
    from app.platforms import facebook
    from app.platforms.base import PublishRequest, PublishResult

    pub = facebook.FacebookPublisher()
    req = PublishRequest(caption="x", first_comment="先看這頁 {link}",
                         link_url="https://popmonster.vip/go?src=fb-000001")

    calls = {}

    def fake_request(*args, **kwargs):
        calls["data"] = kwargs.get("data")
        return {"id": "c-9"}

    monkeypatch.setattr(facebook, "request_json", fake_request)
    ok = PublishResult(external_post_id="p1")
    pub._post_first_comment("tok", ok, req)
    assert ok.first_comment_id == "c-9"
    assert ok.first_comment_error == ""
    assert calls["data"]["message"] == "先看這頁 https://popmonster.vip/go?src=fb-000001"

    def boom(*a, **k):
        raise RuntimeError("(#200) pages_manage_engagement required")
    monkeypatch.setattr(facebook, "request_json", boom)
    bad = PublishResult(external_post_id="p2")
    pub._post_first_comment("tok", bad, req)  # must not raise
    assert bad.first_comment_id == ""
    assert "pages_manage_engagement" in bad.first_comment_error


def test_no_first_comment_configured_reports_nothing(monkeypatch):
    from app.platforms import facebook
    from app.platforms.base import PublishRequest, PublishResult

    monkeypatch.delenv("FB_FIRST_COMMENT", raising=False)
    pub = facebook.FacebookPublisher()
    result = PublishResult(external_post_id="p3")
    pub._post_first_comment("tok", result, PublishRequest(caption="x"))
    assert result.first_comment_id == "" and result.first_comment_error == ""
