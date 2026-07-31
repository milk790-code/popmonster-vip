"""Re-authorising a Meta account must not wipe operator-owned settings.

The OAuth login URL deliberately sends ``auth_type=reauthorize`` so the
operator can re-run the flow to pick up newly created Pages. That makes
re-auth a routine action -- and it used to rebuild ``SocialAccount.extra``
from the platform payload alone, silently discarding the egress proxy URL
and the account's whole operating profile (first comment, curated
communities, cross-account role).
"""
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

from app.auth import routes as auth_routes
from app.extensions import db
from app.models import Platform, SocialAccount, User
from app.platforms.base import TokenBundle
from app.utils.account_profile import read_profile, validate_profile, write_profile


def _run_meta_callback(client, user_id):
    state = auth_routes._serializer().dumps({"user_id": user_id, "provider": "meta"})
    bundle = TokenBundle(
        access_token="user-tok",
        refresh_token=None,
        expires_at=datetime.now(timezone.utc) + timedelta(days=60),
        scopes=["pages_show_list", "pages_manage_posts"],
        extra={},
    )
    provider = MagicMock()
    provider.exchange_code.return_value = bundle

    def fake_request_json(method, url, **kw):
        if "/me/accounts" in url:
            return {"data": [{"id": "page-1", "name": "My Page 改名了",
                              "access_token": "page-tok-v2"}]}
        if "/me/businesses" in url:
            return {"data": []}
        raise AssertionError(f"unexpected call: {url}")

    with patch("app.auth.routes.get_oauth_provider", return_value=provider), \
         patch("app.auth.routes.request_json", side_effect=fake_request_json):
        return client.get(f"/auth/meta/callback?code=x&state={state}")


def _seed_configured_account(app):
    with app.app_context():
        user = User(email="reauth@example.com", display_name="r")
        db.session.add(user)
        db.session.flush()
        account = SocialAccount(
            user_id=user.id,
            platform=Platform.FACEBOOK,
            external_account_id="page-1",
            handle="My Page",
            access_token_enc=b"old",
        )
        db.session.add(account)
        db.session.flush()
        write_profile(account, validate_profile({
            "note": "主力粉專",
            "first_comment": "對照表在這 {link}",
            "communities": [{"name": "台灣汽車美容交流",
                             "url": "https://facebook.com/groups/aaa",
                             "why": "問拋光的人最多", "cadence_days": 21}],
        }))
        extra = dict(account.extra)
        extra["proxy_url"] = "socks5://host:1080"
        account.extra = extra
        db.session.commit()
        return user.id, account.id


def test_reauth_keeps_the_account_profile(client, app):
    user_id, account_id = _seed_configured_account(app)
    assert _run_meta_callback(client, user_id).status_code == 200

    with app.app_context():
        account = db.session.get(SocialAccount, account_id)
        profile = read_profile(account)
        assert profile["note"] == "主力粉專"
        assert profile["first_comment"] == "對照表在這 {link}"
        assert len(profile["communities"]) == 1
        assert profile["communities"][0]["cadence_days"] == 21


def test_reauth_keeps_the_egress_proxy(client, app):
    user_id, account_id = _seed_configured_account(app)
    assert _run_meta_callback(client, user_id).status_code == 200
    with app.app_context():
        account = db.session.get(SocialAccount, account_id)
        assert account.extra.get("proxy_url") == "socks5://host:1080"


def test_reauth_still_refreshes_platform_owned_fields(client, app):
    """Preserving operator keys must not freeze the platform's own data --
    the page token and handle still have to move forward."""
    user_id, account_id = _seed_configured_account(app)
    assert _run_meta_callback(client, user_id).status_code == 200
    with app.app_context():
        account = db.session.get(SocialAccount, account_id)
        assert account.extra.get("page_access_token") == "page-tok-v2"
        assert account.handle == "My Page 改名了"


def test_reauth_clears_a_stale_unaudited_flag(client, app):
    """An account previously connected through the unaudited cookie path and
    later re-connected via real OAuth must lose the flag, otherwise it stays
    marked untrustworthy forever."""
    user_id, account_id = _seed_configured_account(app)
    with app.app_context():
        account = db.session.get(SocialAccount, account_id)
        extra = dict(account.extra)
        extra["unaudited"] = True
        account.extra = extra
        db.session.commit()

    assert _run_meta_callback(client, user_id).status_code == 200
    with app.app_context():
        account = db.session.get(SocialAccount, account_id)
        assert "unaudited" not in account.extra
        assert read_profile(account)["note"] == "主力粉專"
