"""Smoke tests for the HTTP surface; no external services."""
from app.extensions import db
from app.models import User


def test_healthz(client):
    res = client.get("/healthz")
    assert res.status_code == 200
    assert res.get_json() == {"status": "ok"}


def test_create_post_and_diff(client, app):
    with app.app_context():
        user = User(email="t@example.com", display_name="t")
        db.session.add(user)
        db.session.commit()
        user_id = user.id

    res = client.post(
        "/api/posts",
        json={"user_id": user_id, "title": "v1", "caption": "first"},
    )
    assert res.status_code == 201, res.data
    post_id = res.get_json()["id"]

    res = client.put(f"/api/posts/{post_id}", json={"caption": "second"})
    assert res.status_code == 200
    new_id = res.get_json()["id"]
    assert new_id != post_id

    diff = client.get(f"/api/posts/{post_id}/diff/{new_id}").get_json()
    assert "caption" in diff["diff"]
