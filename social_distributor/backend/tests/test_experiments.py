"""C2: A/B variant comparison + distribute_ab + backtest persistence."""
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

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
from app.utils.experiments import (
    MIN_SAMPLES_PER_ENGINE,
    backtest_and_persist_winners,
    compare_variants,
)

from .conftest import login_as


def _login_group_owner(client, app, group_id):
    """Authenticate the client as the user who owns ``group_id``."""
    with app.app_context():
        owner_id = db.session.get(AccountGroup, group_id).user_id
    login_as(client, owner_id)
    return owner_id


def _seed_group_with_targets(app, *, engine_a_count, engine_a_engagement,
                              engine_b_count, engine_b_engagement,
                              reach_per_target=1000):
    """Create a group with N targets per engine and one PostMetric each."""
    with app.app_context():
        user = User(email=f"ab-{datetime.now().timestamp()}@e.com",
                    display_name="ab")
        db.session.add(user); db.session.flush()
        accounts = []
        for i in range(engine_a_count + engine_b_count):
            a = SocialAccount(
                user_id=user.id, platform=Platform.INSTAGRAM,
                external_account_id=f"acc-{i}", handle=f"acc-{i}",
                access_token_enc=b"x",
            )
            db.session.add(a); db.session.flush()
            accounts.append(a)
        group = AccountGroup(user_id=user.id, name=f"g-{datetime.now().timestamp()}")
        for a in accounts:
            group.accounts.append(a)
        db.session.add(group); db.session.flush()
        post = Post(user_id=user.id, title="t", caption="c")
        db.session.add(post); db.session.flush()

        published_at = datetime.now(timezone.utc) - timedelta(days=2)
        for i, a in enumerate(accounts):
            engine = "claude" if i < engine_a_count else "template"
            engagement = (
                engine_a_engagement if engine == "claude" else engine_b_engagement
            )
            t = PostTarget(
                post_id=post.id, account_id=a.id,
                status=JobStatus.SUCCEEDED,
                published_at=published_at,
                overrides={"variant_engine": engine},
            )
            db.session.add(t); db.session.flush()
            db.session.add(PostMetric(
                target_id=t.id, fetched_at=datetime.now(timezone.utc),
                reach=reach_per_target, likes=engagement, comments=0,
                shares=0, saves=0,
            ))
        db.session.commit()
        return group.id, post.id


# -- compare_variants ----------------------------------------------

def test_compare_variants_picks_higher_rate_engine(app):
    # claude: 5 samples × 100 engagement = winner
    # template: 5 samples × 50 engagement
    gid, _ = _seed_group_with_targets(
        app,
        engine_a_count=MIN_SAMPLES_PER_ENGINE,
        engine_a_engagement=100,
        engine_b_count=MIN_SAMPLES_PER_ENGINE,
        engine_b_engagement=50,
    )
    with app.app_context():
        cmp = compare_variants(gid)
    assert cmp.winner == "claude"
    assert any(s.engine == "claude" and s.samples == 5 for s in cmp.by_engine)
    assert "wins" in cmp.confidence_note


def test_compare_variants_no_winner_when_below_min_samples(app):
    gid, _ = _seed_group_with_targets(
        app,
        engine_a_count=MIN_SAMPLES_PER_ENGINE - 1,
        engine_a_engagement=100,
        engine_b_count=MIN_SAMPLES_PER_ENGINE,
        engine_b_engagement=50,
    )
    with app.app_context():
        cmp = compare_variants(gid)
    assert cmp.winner is None
    assert "need at least 2 engines" in cmp.confidence_note


def test_compare_variants_returns_none_for_unknown_group(app):
    with app.app_context():
        assert compare_variants(99999) is None


def test_compare_variants_handles_targets_without_metrics(app):
    """Targets without ingested metrics should be skipped (not zero-counted)."""
    with app.app_context():
        user = User(email="nm@e.com", display_name="nm")
        db.session.add(user); db.session.flush()
        a = SocialAccount(user_id=user.id, platform=Platform.INSTAGRAM,
                          external_account_id="x", handle="x",
                          access_token_enc=b"x")
        db.session.add(a); db.session.flush()
        group = AccountGroup(user_id=user.id, name="nm-grp")
        group.accounts.append(a)
        db.session.add(group); db.session.flush()
        post = Post(user_id=user.id, title="t", caption="c")
        db.session.add(post); db.session.flush()
        t = PostTarget(post_id=post.id, account_id=a.id,
                       status=JobStatus.SUCCEEDED,
                       published_at=datetime.now(timezone.utc) - timedelta(days=1),
                       overrides={"variant_engine": "claude"})
        db.session.add(t)
        db.session.commit()
        cmp = compare_variants(group.id)
    # Only 1 target with no metric → 0 samples in claude bucket → no winner
    assert cmp.winner is None
    assert all(s.samples == 0 for s in cmp.by_engine) or cmp.by_engine == []


# -- backtest_and_persist_winners ----------------------------------

def test_backtest_persists_winner_to_group(app):
    gid, _ = _seed_group_with_targets(
        app,
        engine_a_count=MIN_SAMPLES_PER_ENGINE,
        engine_a_engagement=200,
        engine_b_count=MIN_SAMPLES_PER_ENGINE,
        engine_b_engagement=50,
    )
    with app.app_context():
        results = backtest_and_persist_winners()
        assert any(r["group_id"] == gid and r["updated"] for r in results)
        group = db.session.get(AccountGroup, gid)
        assert group.preferred_variant_engine == "claude"


def test_backtest_does_not_overwrite_when_no_winner(app):
    """If a quiet week produces no winner, don't unlearn the previous one."""
    gid, _ = _seed_group_with_targets(
        app,
        engine_a_count=2, engine_a_engagement=100,
        engine_b_count=2, engine_b_engagement=50,
    )
    with app.app_context():
        group = db.session.get(AccountGroup, gid)
        group.preferred_variant_engine = "template"  # learned previously
        db.session.commit()
        backtest_and_persist_winners()
        group = db.session.get(AccountGroup, gid)
        assert group.preferred_variant_engine == "template"  # preserved


# -- distribute_ab endpoint ----------------------------------------

def test_distribute_ab_dry_run_assigns_alternating_engines(client, app):
    gid, pid = _seed_group_with_targets(
        app,
        engine_a_count=2, engine_a_engagement=0,
        engine_b_count=2, engine_b_engagement=0,
    )
    _login_group_owner(client, app, gid)
    with patch("app.api.experiments.generate_variant") as gen:
        gen.side_effect = lambda req: type("V", (), {
            "caption": f"variant-{req.seed}",
            "title": "t",
            "used_engine": req.seed.split(":")[-2],  # "A" or "B" — but our impl uses requested engine_x; let's just echo claude
        })()
        # Override the side_effect to return predictable engine
        from unittest.mock import MagicMock
        gen.side_effect = None
        gen.return_value = MagicMock(caption="rewritten",
                                      title="t",
                                      used_engine="claude")

        res = client.post(f"/api/posts/{pid}/distribute_ab", json={
            "group_id": gid,
            "engine_a": "claude",
            "engine_b": "none",
            "dry_run": True,
        })
    assert res.status_code == 200, res.get_data(as_text=True)
    body = res.get_json()
    assert body["dry_run"] is True
    labels = [p["variant_label"] for p in body["plan"]]
    assert "A" in labels and "B" in labels
    # alternating
    assert labels == ["A", "B", "A", "B"] or labels == ["B", "A", "B", "A"]


def test_distribute_ab_rejects_same_engine(client, app):
    gid, pid = _seed_group_with_targets(
        app,
        engine_a_count=2, engine_a_engagement=0,
        engine_b_count=2, engine_b_engagement=0,
    )
    _login_group_owner(client, app, gid)
    res = client.post(f"/api/posts/{pid}/distribute_ab", json={
        "group_id": gid, "engine_a": "claude", "engine_b": "claude",
        "dry_run": True,
    })
    assert res.status_code == 400
    assert "differ" in res.get_json()["error"]


def test_distribute_ab_rejects_too_few_accounts(client, app):
    with app.app_context():
        user = User(email="solo@e.com", display_name="solo")
        db.session.add(user); db.session.flush()
        a = SocialAccount(user_id=user.id, platform=Platform.INSTAGRAM,
                          external_account_id="x", handle="x",
                          access_token_enc=b"x")
        db.session.add(a); db.session.flush()
        group = AccountGroup(user_id=user.id, name="solo-grp")
        group.accounts.append(a)
        db.session.add(group); db.session.flush()
        post = Post(user_id=user.id, title="t", caption="c")
        db.session.add(post); db.session.commit()
        gid, pid, uid = group.id, post.id, user.id

    login_as(client, uid)
    res = client.post(f"/api/posts/{pid}/distribute_ab", json={
        "group_id": gid, "engine_a": "claude", "engine_b": "none",
        "dry_run": True,
    })
    assert res.status_code == 400
    assert "≥2" in res.get_json()["error"]


def test_results_endpoint_returns_engine_breakdown(client, app):
    gid, _ = _seed_group_with_targets(
        app,
        engine_a_count=MIN_SAMPLES_PER_ENGINE,
        engine_a_engagement=100,
        engine_b_count=MIN_SAMPLES_PER_ENGINE,
        engine_b_engagement=50,
    )
    _login_group_owner(client, app, gid)
    res = client.get(f"/api/experiments/results?group_id={gid}")
    assert res.status_code == 200
    body = res.get_json()
    assert body["winner"] == "claude"
    engines = {e["engine"] for e in body["by_engine"]}
    assert {"claude", "template"} <= engines


def test_backtest_endpoint_runs_immediately(client, app):
    gid, _ = _seed_group_with_targets(
        app,
        engine_a_count=MIN_SAMPLES_PER_ENGINE,
        engine_a_engagement=200,
        engine_b_count=MIN_SAMPLES_PER_ENGINE,
        engine_b_engagement=50,
    )
    _login_group_owner(client, app, gid)
    res = client.post("/api/experiments/backtest")
    assert res.status_code == 200
    body = res.get_json()
    assert any(r["group_id"] == gid and r["winner"] == "claude" for r in body["results"])
