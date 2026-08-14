"""The account list must not hand back the credentials it stores.

Tokens are Fernet-encrypted at rest precisely so they cannot leak. Serialising
``extra`` wholesale gave the decrypted Page tokens back over the API, so one
operator session was enough to walk off with posting rights to every Page in
the fleet -- tokens that do not expire, and that belong to Pages Meta treats as
a single entity. This is the regression test for that.
"""
from app.api.accounts import _safe_extra
from app.extensions import db
from app.models import Platform, SocialAccount, User
from app.utils.crypto import cipher

from .conftest import login_as

SECRET = "EAASFbPd2Ii4B-not-a-real-token"


def _seed(app):
    with app.app_context():
        user = User(email="leak@example.test", display_name="l")
        db.session.add(user)
        db.session.flush()
        db.session.add(SocialAccount(
            user_id=user.id,
            platform=Platform.FACEBOOK,
            external_account_id="page-1",
            handle="測試粉專",
            access_token_enc=cipher().encrypt("stored-secret"),
            extra={
                "page_access_token": SECRET,
                "proxy_url": "http://proxy.example.test:8080",
                "profile": {"link_src": "fb-abc123", "persona": "溫和的講古口吻"},
            },
        ))
        db.session.commit()
        return user.id


def test_the_account_list_never_returns_a_page_token(client, app):
    user_id = _seed(app)
    login_as(client, user_id)

    resp = client.get("/api/accounts")
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)

    # The strongest form of the assertion: the secret must not appear anywhere
    # in the response, no matter how the payload gets restructured later.
    assert SECRET not in body

    row = resp.get_json()[0]
    assert row["extra"]["page_access_token"] == "***"
    # The persona profile is what the console actually renders -- masking the
    # credentials must not blank out the rest of the record.
    assert row["extra"]["profile"]["link_src"] == "fb-abc123"
    # proxy_url stays dropped entirely, and its presence is reported separately.
    assert "proxy_url" not in row["extra"]
    assert row["proxy_configured"] is True


def test_every_known_credential_key_is_masked():
    masked = _safe_extra({
        "page_access_token": "a",
        "access_token": "b",
        "refresh_token": "c",
        "client_secret": "d",
        "app_secret": "e",
        "profile": {"keep": "me"},
    })
    assert set(k for k, v in masked.items() if v == "***") == {
        "page_access_token", "access_token", "refresh_token",
        "client_secret", "app_secret",
    }
    assert masked["profile"] == {"keep": "me"}
