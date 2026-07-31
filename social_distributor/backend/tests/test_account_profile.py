"""Per-account operating profile: validation, endpoints, and the
first-comment resolution chain that feeds the publish pipeline."""
import os

import pytest

from app.extensions import db
from app.models import AccountGroup, Platform, Post, PostTarget, SocialAccount, User
from app.utils.account_profile import (
    ProfileError,
    empty_profile,
    read_profile,
    validate_profile,
    write_profile,
)

from .conftest import login_as


def _seed(app, *, platform: Platform = Platform.FACEBOOK):
    with app.app_context():
        user = User(email="t@example.com", display_name="t")
        db.session.add(user)
        db.session.flush()
        account = SocialAccount(
            user_id=user.id,
            platform=platform,
            external_account_id="page-1",
            handle="@popmonster",
            access_token_enc=b"a",
        )
        db.session.add(account)
        db.session.commit()
        return user.id, account.id


# --------------------------------------------------------------- validation


def test_empty_payload_yields_all_defaults():
    profile = validate_profile({})
    assert profile == empty_profile()
    assert profile["interaction"]["role"] == "off"


def test_unknown_field_is_rejected_not_ignored():
    """A typo must fail loudly; silently dropping it means the operator
    thinks a setting is live for weeks when it never was."""
    with pytest.raises(ProfileError) as exc:
        validate_profile({"frist_comment": "oops"})
    assert any("unknown profile field" in e for e in exc.value.errors)


def test_community_requires_name_and_https_url():
    with pytest.raises(ProfileError) as exc:
        validate_profile({"communities": [{"name": "", "url": "facebook.com/g/1"}]})
    errors = " ".join(exc.value.errors)
    assert "name is required" in errors
    assert "must start with https://" in errors


def test_duplicate_community_url_is_dropped_with_an_error():
    with pytest.raises(ProfileError) as exc:
        validate_profile(
            {
                "communities": [
                    {"name": "A", "url": "https://facebook.com/groups/1"},
                    {"name": "B", "url": "https://facebook.com/groups/1"},
                ]
            }
        )
    assert any("duplicate" in e for e in exc.value.errors)


def test_community_defaults_are_conservative():
    profile = validate_profile(
        {"communities": [{"name": "改裝車同好", "url": "https://facebook.com/groups/9"}]}
    )
    entry = profile["communities"][0]
    assert entry["cadence_days"] == 14
    assert entry["active"] is True
    assert entry["allows_links"] is True
    assert entry["priority"] == 3


def test_short_comment_pool_entry_is_rejected():
    """A one-word "推" is the signature of engagement farming, which is the
    behaviour this whole feature must not enable."""
    with pytest.raises(ProfileError) as exc:
        validate_profile(
            {"interaction": {"role": "supporter", "comment_pool": ["推推"]}}
        )
    assert any("genuine comment" in e for e in exc.value.errors)


def test_substantive_comment_pool_entry_is_accepted():
    profile = validate_profile(
        {
            "interaction": {
                "role": "supporter",
                "max_per_day": 1,
                "comment_pool": ["這款我們自己車庫也在用，冬天低溫比較不會結塊。"],
            }
        }
    )
    assert len(profile["interaction"]["comment_pool"]) == 1


def test_interaction_role_must_be_known():
    with pytest.raises(ProfileError) as exc:
        validate_profile({"interaction": {"role": "botnet"}})
    assert any("interaction.role must be one of" in e for e in exc.value.errors)


def test_max_per_day_is_capped():
    with pytest.raises(ProfileError) as exc:
        validate_profile({"interaction": {"role": "supporter", "max_per_day": 500}})
    assert any("between 0 and 5" in e for e in exc.value.errors)


# ------------------------------------------------------------------ storage


def test_write_profile_preserves_reserved_keys(app):
    """proxy_url is owned by the egress-proxy feature. Writing a profile must
    not clobber it, or every profile save would silently disable the proxy."""
    user_id, account_id = _seed(app)
    with app.app_context():
        account = db.session.get(SocialAccount, account_id)
        account.extra = {"proxy_url": "socks5://host:1080"}
        db.session.commit()

        account = db.session.get(SocialAccount, account_id)
        write_profile(account, validate_profile({"note": "主力"}))
        db.session.commit()

        account = db.session.get(SocialAccount, account_id)
        assert account.extra["proxy_url"] == "socks5://host:1080"
        assert read_profile(account)["note"] == "主力"


def test_read_profile_on_untouched_account_is_empty(app):
    user_id, account_id = _seed(app)
    with app.app_context():
        account = db.session.get(SocialAccount, account_id)
        assert read_profile(account) == empty_profile()


# ---------------------------------------------------------------- endpoints


def test_put_and_get_profile_roundtrip(client, app):
    user_id, account_id = _seed(app)
    login_as(client, user_id)
    payload = {
        "profile": {
            "note": "泡泡怪獸主力粉專",
            "first_comment": "完整選型對照表在這 👉 {link}",
            "link_src": "fb-a1b2c3",
            "communities": [
                {
                    "name": "台灣汽車美容交流",
                    "url": "https://facebook.com/groups/123",
                    "why": "問拋光問題的人最多",
                    "cadence_days": 21,
                    "allows_links": False,
                }
            ],
        }
    }
    res = client.put(f"/api/accounts/{account_id}/profile", json=payload)
    assert res.status_code == 200, res.data

    res = client.get(f"/api/accounts/{account_id}/profile")
    assert res.status_code == 200
    profile = res.get_json()["profile"]
    assert profile["first_comment"] == "完整選型對照表在這 👉 {link}"
    assert profile["communities"][0]["cadence_days"] == 21
    assert profile["communities"][0]["allows_links"] is False


def test_put_profile_rejects_bad_payload_with_details(client, app):
    user_id, account_id = _seed(app)
    login_as(client, user_id)
    res = client.put(
        f"/api/accounts/{account_id}/profile",
        json={"profile": {"communities": [{"name": "x", "url": "http://insecure"}]}},
    )
    assert res.status_code == 400
    assert res.get_json()["details"]


def test_profile_endpoints_are_owner_scoped(client, app):
    user_id, account_id = _seed(app)
    with app.app_context():
        intruder = User(email="other@example.com", display_name="o")
        db.session.add(intruder)
        db.session.commit()
        intruder_id = intruder.id
    login_as(client, intruder_id)
    assert client.get(f"/api/accounts/{account_id}/profile").status_code == 403
    assert client.put(
        f"/api/accounts/{account_id}/profile", json={"profile": {}}
    ).status_code == 403


def test_list_profiles_returns_whole_fleet(client, app):
    user_id, account_id = _seed(app)
    with app.app_context():
        second = SocialAccount(
            user_id=user_id,
            platform=Platform.META_THREADS,
            external_account_id="th-1",
            handle="@threads",
            access_token_enc=b"a",
        )
        db.session.add(second)
        db.session.commit()
    login_as(client, user_id)
    res = client.get("/api/accounts/profiles")
    assert res.status_code == 200
    rows = res.get_json()
    assert len(rows) == 2
    assert all("profile" in r and "groups" in r for r in rows)


# ------------------------------------------- first-comment resolution chain


def _seed_target(app, *, overrides=None, account_profile=None, group_style=None):
    with app.app_context():
        user = User(email="fc@example.com", display_name="fc")
        db.session.add(user)
        db.session.flush()
        account = SocialAccount(
            user_id=user.id,
            platform=Platform.FACEBOOK,
            external_account_id="page-9",
            handle="@page9",
            access_token_enc=b"a",
        )
        db.session.add(account)
        db.session.flush()
        if account_profile is not None:
            write_profile(account, validate_profile(account_profile))

        group_id = None
        if group_style is not None:
            group = AccountGroup(
                user_id=user.id, name="line-a", style_profile=group_style
            )
            db.session.add(group)
            db.session.flush()
            group_id = group.id

        post = Post(
            user_id=user.id,
            caption="hello",
            link_url="https://popmonster.vip/go?src=fb-a1b2c3",
        )
        db.session.add(post)
        db.session.flush()
        target = PostTarget(
            post_id=post.id,
            account_id=account.id,
            group_id=group_id,
            overrides=overrides or {},
        )
        db.session.add(target)
        db.session.commit()
        return target.id


def _resolve(app, target_id):
    from app.compliance.engine import resolve_first_comment

    with app.app_context():
        target = db.session.get(PostTarget, target_id)
        return resolve_first_comment(target)


def test_first_comment_prefers_per_post_override(app, monkeypatch):
    monkeypatch.setenv("FB_FIRST_COMMENT", "env level")
    target_id = _seed_target(
        app,
        overrides={"first_comment": "post level"},
        account_profile={"first_comment": "account level"},
        group_style={"first_comment": "group level"},
    )
    assert _resolve(app, target_id) == "post level"


def test_first_comment_falls_back_to_account_profile(app, monkeypatch):
    monkeypatch.setenv("FB_FIRST_COMMENT", "env level")
    target_id = _seed_target(
        app,
        account_profile={"first_comment": "account level"},
        group_style={"first_comment": "group level"},
    )
    assert _resolve(app, target_id) == "account level"


def test_first_comment_falls_back_to_group_style(app, monkeypatch):
    """The group level needs an explicit load because PostTarget has no
    ``group`` relationship -- if that regresses this test goes to env."""
    monkeypatch.setenv("FB_FIRST_COMMENT", "env level")
    target_id = _seed_target(app, group_style={"first_comment": "group level"})
    assert _resolve(app, target_id) == "group level"


def test_first_comment_falls_back_to_env(app, monkeypatch):
    monkeypatch.setenv("FB_FIRST_COMMENT", "env level")
    target_id = _seed_target(app)
    assert _resolve(app, target_id) == "env level"


def test_first_comment_defaults_to_silence(app, monkeypatch):
    """No profile anywhere and no env var means no comment is posted. This is
    the state all 60+ live accounts start in, so it must stay silent."""
    monkeypatch.delenv("FB_FIRST_COMMENT", raising=False)
    target_id = _seed_target(app)
    assert _resolve(app, target_id) == ""


def test_publisher_request_carries_first_comment_and_hides_it_from_overrides(app):
    from app.compliance.engine import publisher_request_from

    target_id = _seed_target(app, account_profile={"first_comment": "看這裡 {link}"})
    with app.app_context():
        target = db.session.get(PostTarget, target_id)
        req = publisher_request_from(target.post, target)
    assert req.first_comment == "看這裡 {link}"
    # first_comment is consumed by the resolver; leaking it into overrides
    # would push an unknown key into platform adapters.
    assert "first_comment" not in req.overrides


def test_facebook_posts_the_resolved_first_comment(app, monkeypatch):
    """End of the chain: a resolved first comment reaches Graph with the
    {link} placeholder filled."""
    from app.platforms.base import PublishRequest, TokenBundle
    from app.platforms.facebook import FacebookPublisher

    monkeypatch.delenv("FB_FIRST_COMMENT", raising=False)
    calls = []

    def fake_request_json(method, url, **kwargs):
        calls.append((method, url, kwargs.get("data", {})))
        return {"id": "post-123"}

    monkeypatch.setattr("app.platforms.facebook.request_json", fake_request_json)

    publisher = FacebookPublisher()
    publisher.publish(
        TokenBundle(access_token="tok"),
        "page-9",
        PublishRequest(
            caption="hi",
            link_url="https://popmonster.vip/go?src=fb-a1b2c3",
            first_comment="對照表 👉 {link}",
        ),
    )

    comment_calls = [c for c in calls if c[1].endswith("/comments")]
    assert len(comment_calls) == 1
    assert comment_calls[0][2]["message"] == (
        "對照表 👉 https://popmonster.vip/go?src=fb-a1b2c3"
    )


def test_facebook_stays_silent_without_a_first_comment(app, monkeypatch):
    from app.platforms.base import PublishRequest, TokenBundle
    from app.platforms.facebook import FacebookPublisher

    monkeypatch.delenv("FB_FIRST_COMMENT", raising=False)
    calls = []

    def fake_request_json(method, url, **kwargs):
        calls.append(url)
        return {"id": "post-123"}

    monkeypatch.setattr("app.platforms.facebook.request_json", fake_request_json)
    FacebookPublisher().publish(
        TokenBundle(access_token="tok"), "page-9", PublishRequest(caption="hi")
    )
    assert not [u for u in calls if u.endswith("/comments")]


def test_overrides_whitelist_accepts_first_comment_for_facebook():
    from app.utils.overrides import validate_overrides

    assert validate_overrides("facebook", {"first_comment": "hi"}) == []
    assert validate_overrides("facebook", {"first_comment": 123})
    # Other platforms have no first-comment support yet; it must not slip in.
    assert validate_overrides("instagram", {"first_comment": "hi"})
