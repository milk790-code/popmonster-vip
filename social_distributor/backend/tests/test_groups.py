"""Account group CRUD + member management."""
from app.extensions import db
from app.models import Platform, SocialAccount, User


def _seed_user_and_account(app, platform: Platform = Platform.FACEBOOK):
    with app.app_context():
        user = User(email="t@example.com", display_name="t")
        db.session.add(user)
        db.session.flush()
        account = SocialAccount(
            user_id=user.id,
            platform=platform,
            external_account_id="ext-1",
            handle="@me",
            access_token_enc=b"a",
        )
        db.session.add(account)
        db.session.commit()
        return user.id, account.id


def test_group_create_with_members(client, app):
    user_id, account_id = _seed_user_and_account(app)
    res = client.post(
        "/api/groups",
        json={
            "user_id": user_id,
            "name": "美食日常 A",
            "description": "casual foodie persona",
            "style_profile": {"tone": "casual", "emoji_density": "medium"},
            "account_ids": [account_id],
        },
    )
    assert res.status_code == 201, res.data
    data = res.get_json()
    assert data["name"] == "美食日常 A"
    assert len(data["members"]) == 1
    assert data["members"][0]["account_id"] == account_id


def test_group_name_unique_per_user(client, app):
    user_id, _ = _seed_user_and_account(app)
    client.post("/api/groups", json={"user_id": user_id, "name": "dup"})
    res = client.post("/api/groups", json={"user_id": user_id, "name": "dup"})
    assert res.status_code == 409


def test_group_member_add_remove(client, app):
    user_id, account_id = _seed_user_and_account(app)
    res = client.post("/api/groups", json={"user_id": user_id, "name": "g1"})
    group_id = res.get_json()["id"]

    res = client.post(
        f"/api/groups/{group_id}/members", json={"account_id": account_id}
    )
    assert res.status_code == 200
    assert len(res.get_json()["members"]) == 1

    res = client.delete(f"/api/groups/{group_id}/members/{account_id}")
    assert res.status_code == 200
    assert res.get_json()["members"] == []


def test_group_update_style_profile(client, app):
    user_id, _ = _seed_user_and_account(app)
    res = client.post(
        "/api/groups",
        json={"user_id": user_id, "name": "g", "style_profile": {"tone": "casual"}},
    )
    group_id = res.get_json()["id"]
    res = client.put(
        f"/api/groups/{group_id}",
        json={"style_profile": {"tone": "formal", "voice": "academic"}},
    )
    assert res.status_code == 200
    assert res.get_json()["style_profile"]["voice"] == "academic"


def test_group_rejects_account_from_other_user(client, app):
    _, _ = _seed_user_and_account(app)
    with app.app_context():
        other = User(email="o@example.com", display_name="o")
        db.session.add(other)
        db.session.commit()
        other_id = other.id
    res = client.post("/api/groups", json={"user_id": other_id, "name": "g"})
    group_id = res.get_json()["id"]
    res = client.post(
        f"/api/groups/{group_id}/members", json={"account_id": 1}
    )
    assert res.status_code == 400
