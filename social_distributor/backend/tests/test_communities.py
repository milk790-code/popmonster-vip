"""Community share planning: cadence guard, link rules, ordering, stamping."""
from datetime import datetime, timedelta, timezone

from app.extensions import db
from app.models import Platform, Post, PostTarget, SocialAccount, User
from app.utils.account_profile import validate_profile, write_profile

from .conftest import login_as


def _iso(days_ago: float) -> str:
    return (datetime.now(timezone.utc) - timedelta(days=days_ago)).isoformat()


def _seed(app, communities, *, handle="@popmonster"):
    with app.app_context():
        user = User(email="c@example.com", display_name="c")
        db.session.add(user)
        db.session.flush()
        account = SocialAccount(
            user_id=user.id,
            platform=Platform.FACEBOOK,
            external_account_id="page-1",
            handle=handle,
            access_token_enc=b"a",
        )
        db.session.add(account)
        db.session.flush()
        write_profile(account, validate_profile({"communities": communities}))
        db.session.commit()
        return user.id, account.id


GROUP_A = {
    "name": "台灣汽車美容交流",
    "url": "https://facebook.com/groups/aaa",
    "why": "問拋光問題的人最多",
    "priority": 5,
    "members": 30000,
    "cadence_days": 14,
}
GROUP_B = {
    "name": "北部洗車同好",
    "url": "https://facebook.com/groups/bbb",
    "priority": 2,
    "members": 4000,
    "cadence_days": 7,
}
GROUP_NO_LINKS = {
    "name": "嚴禁廣告的技術群",
    "url": "https://facebook.com/groups/ccc",
    "priority": 4,
    "allows_links": False,
    "cadence_days": 30,
}


def test_never_shared_community_is_due(client, app):
    user_id, account_id = _seed(app, [GROUP_A])
    login_as(client, user_id)
    res = client.post(
        "/api/communities/plan",
        json={"account_ids": [account_id], "link_url": "https://popmonster.vip/go?src=fb-a1"},
    )
    assert res.status_code == 200, res.data
    body = res.get_json()
    assert body["due_count"] == 1
    entry = body["accounts"][0]["due"][0]
    assert entry["name"] == "台灣汽車美容交流"
    assert entry["include_link"] is True
    assert entry["why"] == "問拋光問題的人最多"


def test_cadence_holds_a_recently_shared_community(client, app):
    recent = {**GROUP_A, "last_shared_at": _iso(3)}  # cadence 14 days
    user_id, account_id = _seed(app, [recent])
    login_as(client, user_id)
    body = client.post(
        "/api/communities/plan", json={"account_ids": [account_id]}
    ).get_json()
    assert body["due_count"] == 0
    assert body["holding_count"] == 1
    held = body["accounts"][0]["holding"][0]
    assert held["days_remaining"] >= 10
    assert "14 天" in held["reason"]


def test_cadence_releases_after_the_window(client, app):
    old = {**GROUP_A, "last_shared_at": _iso(20)}  # cadence 14 days
    user_id, account_id = _seed(app, [old])
    login_as(client, user_id)
    body = client.post(
        "/api/communities/plan", json={"account_ids": [account_id]}
    ).get_json()
    assert body["due_count"] == 1


def test_link_banning_community_gets_a_linkless_plan(client, app):
    user_id, account_id = _seed(app, [GROUP_NO_LINKS])
    login_as(client, user_id)
    body = client.post(
        "/api/communities/plan",
        json={"account_ids": [account_id], "link_url": "https://popmonster.vip/go?src=fb-a1"},
    ).get_json()
    entry = body["accounts"][0]["due"][0]
    assert entry["include_link"] is False
    assert entry["link_url"] is None
    assert "禁止外連" in entry["link_note"]


def test_inactive_community_is_skipped_entirely(client, app):
    user_id, account_id = _seed(app, [{**GROUP_A, "active": False}])
    login_as(client, user_id)
    body = client.post(
        "/api/communities/plan", json={"account_ids": [account_id]}
    ).get_json()
    assert body["due_count"] == 0
    assert body["holding_count"] == 0


def test_due_list_is_ordered_by_priority_then_size(client, app):
    user_id, account_id = _seed(app, [GROUP_B, GROUP_A, GROUP_NO_LINKS])
    login_as(client, user_id)
    body = client.post(
        "/api/communities/plan", json={"account_ids": [account_id]}
    ).get_json()
    names = [c["name"] for c in body["accounts"][0]["due"]]
    assert names == ["台灣汽車美容交流", "嚴禁廣告的技術群", "北部洗車同好"]


def test_plan_from_post_id_uses_delivered_accounts_and_post_link(client, app):
    user_id, account_id = _seed(app, [GROUP_A])
    with app.app_context():
        post = Post(
            user_id=user_id,
            caption="新品上架",
            link_url="https://popmonster.vip/go?src=fb-post1",
        )
        db.session.add(post)
        db.session.flush()
        db.session.add(PostTarget(post_id=post.id, account_id=account_id))
        db.session.commit()
        post_id = post.id

    login_as(client, user_id)
    body = client.post("/api/communities/plan", json={"post_id": post_id}).get_json()
    assert body["post"]["id"] == post_id
    entry = body["accounts"][0]["due"][0]
    assert entry["link_url"] == "https://popmonster.vip/go?src=fb-post1"


def test_plan_rejects_another_users_post(client, app):
    user_id, account_id = _seed(app, [GROUP_A])
    with app.app_context():
        other = User(email="x@example.com", display_name="x")
        db.session.add(other)
        db.session.flush()
        post = Post(user_id=other.id, caption="not yours")
        db.session.add(post)
        db.session.commit()
        post_id = post.id
    login_as(client, user_id)
    assert client.post(
        "/api/communities/plan", json={"post_id": post_id}
    ).status_code == 404


def test_mark_shared_starts_the_cadence_clock(client, app):
    user_id, account_id = _seed(app, [GROUP_A])
    login_as(client, user_id)

    assert client.post(
        "/api/communities/plan", json={"account_ids": [account_id]}
    ).get_json()["due_count"] == 1

    res = client.post(
        "/api/communities/mark-shared",
        json={"account_id": account_id, "urls": [GROUP_A["url"]]},
    )
    assert res.status_code == 200, res.data

    after = client.post(
        "/api/communities/plan", json={"account_ids": [account_id]}
    ).get_json()
    assert after["due_count"] == 0
    assert after["holding_count"] == 1


def test_mark_shared_rejects_a_url_not_on_that_account(client, app):
    user_id, account_id = _seed(app, [GROUP_A])
    login_as(client, user_id)
    res = client.post(
        "/api/communities/mark-shared",
        json={"account_id": account_id, "urls": ["https://facebook.com/groups/zzz"]},
    )
    assert res.status_code == 404


def test_mark_shared_is_owner_scoped(client, app):
    user_id, account_id = _seed(app, [GROUP_A])
    with app.app_context():
        intruder = User(email="i@example.com", display_name="i")
        db.session.add(intruder)
        db.session.commit()
        intruder_id = intruder.id
    login_as(client, intruder_id)
    res = client.post(
        "/api/communities/mark-shared",
        json={"account_id": account_id, "urls": [GROUP_A["url"]]},
    )
    assert res.status_code == 403


def test_list_communities_skips_accounts_with_none(client, app):
    user_id, account_id = _seed(app, [GROUP_A])
    with app.app_context():
        bare = SocialAccount(
            user_id=user_id,
            platform=Platform.META_THREADS,
            external_account_id="th-1",
            handle="@bare",
            access_token_enc=b"a",
        )
        db.session.add(bare)
        db.session.commit()
    login_as(client, user_id)
    body = client.get("/api/communities").get_json()
    assert body["total_communities"] == 1
    assert [a["handle"] for a in body["accounts"]] == ["@popmonster"]


def _seed_two_accounts_same_community(app):
    """同一個社團掛在兩個粉專底下——這是實際會發生的常態。"""
    with app.app_context():
        user = User(email="two@example.com", display_name="t")
        db.session.add(user)
        db.session.flush()
        ids = []
        for i, handle in enumerate(("A粉專", "B粉專")):
            account = SocialAccount(
                user_id=user.id,
                platform=Platform.FACEBOOK,
                external_account_id=f"page-{i}",
                handle=handle,
                access_token_enc=b"a",
            )
            db.session.add(account)
            db.session.flush()
            write_profile(account, validate_profile({"communities": [GROUP_A]}))
            ids.append(account.id)
        db.session.commit()
        return user.id, ids


def test_one_page_sharing_holds_the_community_for_every_other_page(client, app):
    """煞車必須看整個社團。各算各的話，17 個粉專配 14 天間隔，
    那個社團最快可以每天被灌一次——社團裡的人只會覺得「又是這家」。"""
    user_id, (a_id, b_id) = _seed_two_accounts_same_community(app)
    login_as(client, user_id)

    both = client.post("/api/communities/plan", json={}).get_json()
    assert both["due_count"] == 2  # 兩個粉專都還沒分享過

    res = client.post("/api/communities/mark-shared",
                      json={"account_id": a_id, "urls": [GROUP_A["url"]]})
    assert res.status_code == 200

    after = client.post("/api/communities/plan", json={}).get_json()
    assert after["due_count"] == 0, "A 分享完，B 不該還被列為可分享"
    assert after["holding_count"] == 2

    held = [h for p in after["accounts"] for h in p["holding"]]
    borrowed = [h for h in held if h["last_shared_by"] == "A粉專"]
    assert len(borrowed) == 2
    assert any("A粉專" in h["reason"] for h in held if h["last_shared_by"] == "A粉專")


def test_selecting_one_account_still_sees_other_accounts_history(client, app):
    """只挑 B 粉專來算時，也要看得到 A 昨天分享過——否則單選就繞過了煞車。"""
    user_id, (a_id, b_id) = _seed_two_accounts_same_community(app)
    login_as(client, user_id)
    client.post("/api/communities/mark-shared",
                json={"account_id": a_id, "urls": [GROUP_A["url"]]})

    only_b = client.post("/api/communities/plan",
                         json={"account_ids": [b_id]}).get_json()
    assert only_b["due_count"] == 0
    assert only_b["accounts"][0]["holding"][0]["last_shared_by"] == "A粉專"
