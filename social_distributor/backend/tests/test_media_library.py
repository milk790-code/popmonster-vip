"""C4: media library list endpoint."""
from datetime import datetime, timedelta, timezone

from app.extensions import db
from app.models import MediaAsset, User

from .conftest import login_as


def _seed_media(app, user_id, count, kind="video", transcode_status="done"):
    with app.app_context():
        for i in range(count):
            db.session.add(MediaAsset(
                user_id=user_id, kind=kind,
                storage_url=f"https://cdn/{kind}-{i}.mp4",
                mime_type="video/mp4" if kind == "video" else "image/jpeg",
                transcode_status=transcode_status,
                created_at=datetime.now(timezone.utc) - timedelta(minutes=i),
                derivatives={"1:1": f"https://cdn/{kind}-{i}_1x1.mp4"} if kind == "video" else {},
            ))
        db.session.commit()


def test_list_uploads_requires_login(client):
    res = client.get("/api/uploads")
    assert res.status_code == 401


def test_list_uploads_returns_user_media(client, app):
    with app.app_context():
        u = User(email="m@e.com", display_name="m")
        db.session.add(u); db.session.commit(); uid = u.id
    login_as(client, uid)
    _seed_media(app, uid, 3)
    res = client.get("/api/uploads")
    assert res.status_code == 200
    body = res.get_json()
    assert body["total"] == 3
    assert len(body["items"]) == 3
    # Sorted newest first
    times = [item["created_at"] for item in body["items"]]
    assert times == sorted(times, reverse=True)


def test_list_uploads_filters_by_kind(client, app):
    with app.app_context():
        u = User(email="m2@e.com", display_name="m2")
        db.session.add(u); db.session.commit(); uid = u.id
    login_as(client, uid)
    _seed_media(app, uid, 2, kind="video")
    _seed_media(app, uid, 3, kind="image")
    res = client.get("/api/uploads?kind=image")
    assert res.status_code == 200
    body = res.get_json()
    assert body["total"] == 3
    assert all(i["kind"] == "image" for i in body["items"])


def test_list_uploads_filters_by_transcode_status(client, app):
    with app.app_context():
        u = User(email="m3@e.com", display_name="m3")
        db.session.add(u); db.session.commit(); uid = u.id
    login_as(client, uid)
    _seed_media(app, uid, 2, transcode_status="done")
    _seed_media(app, uid, 1, transcode_status="pending")
    res = client.get("/api/uploads?transcode_status=pending")
    assert res.status_code == 200
    body = res.get_json()
    assert body["total"] == 1
    assert body["items"][0]["transcode_status"] == "pending"


def test_list_uploads_paginates(client, app):
    with app.app_context():
        u = User(email="m4@e.com", display_name="m4")
        db.session.add(u); db.session.commit(); uid = u.id
    login_as(client, uid)
    _seed_media(app, uid, 25)
    res = client.get("/api/uploads?limit=10")
    body = res.get_json()
    assert body["total"] == 25
    assert len(body["items"]) == 10
    res = client.get("/api/uploads?limit=10&offset=20")
    body = res.get_json()
    assert len(body["items"]) == 5


def test_list_uploads_rejects_bad_kind(client, app):
    with app.app_context():
        u = User(email="m5@e.com", display_name="m5")
        db.session.add(u); db.session.commit(); uid = u.id
    login_as(client, uid)
    res = client.get("/api/uploads?kind=audio")
    assert res.status_code == 400


def test_list_uploads_isolates_users(client, app):
    """User A should never see User B's media (basic IDOR check).

    Identity comes from the session now, so even if A tries ?user_id=B the
    server ignores it and only ever returns A's own media.
    """
    with app.app_context():
        a = User(email="a@e.com", display_name="a")
        b = User(email="b@e.com", display_name="b")
        db.session.add_all([a, b]); db.session.commit()
        a_id, b_id = a.id, b.id
    _seed_media(app, a_id, 2)
    _seed_media(app, b_id, 3)
    login_as(client, a_id)
    # Attempt to impersonate B via query param must be ignored.
    res = client.get(f"/api/uploads?user_id={b_id}")
    assert res.get_json()["total"] == 2
    login_as(client, b_id)
    res = client.get("/api/uploads")
    assert res.get_json()["total"] == 3


def test_list_uploads_serializes_derivatives(client, app):
    with app.app_context():
        u = User(email="m6@e.com", display_name="m6")
        db.session.add(u); db.session.commit(); uid = u.id
    login_as(client, uid)
    _seed_media(app, uid, 1)
    body = client.get("/api/uploads").get_json()
    item = body["items"][0]
    assert "1:1" in item["derivatives"]
    assert item["sha256"] is None or isinstance(item["sha256"], str)
