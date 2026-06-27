"""Sha256 dedup on upload + originality findings in compliance."""
from unittest.mock import patch

from app.compliance import ComplianceEngine
from app.compliance.originality import (
    _normalise_link,
    check_link_originality,
    check_media_originality,
)
from app.extensions import db
from app.models import (
    JobStatus,
    MediaAsset,
    Platform,
    Post,
    PostTarget,
    SocialAccount,
    User,
)

from .conftest import login_as


def _seed_user(app):
    with app.app_context():
        user = User(email="d@example.com", display_name="d")
        db.session.add(user)
        db.session.commit()
        return user.id


def test_check_endpoint_finds_existing_media(client, app):
    user_id = _seed_user(app)
    with app.app_context():
        media = MediaAsset(
            user_id=user_id, kind="video",
            storage_url="https://x", mime_type="video/mp4",
            sha256="abc123",
        )
        db.session.add(media)
        db.session.commit()

    login_as(client, user_id)
    res = client.get("/api/uploads/check?sha256=abc123")
    assert res.status_code == 200
    data = res.get_json()
    assert data["found"] is True
    assert data["media_id"]


def test_check_endpoint_returns_not_found_for_unknown_hash(client, app):
    user_id = _seed_user(app)
    login_as(client, user_id)
    res = client.get("/api/uploads/check?sha256=nope")
    assert res.get_json() == {"found": False}


def test_complete_with_matching_sha256_dedupes(client, app):
    user_id = _seed_user(app)
    with app.app_context():
        existing = MediaAsset(
            user_id=user_id, kind="video", storage_url="https://x",
            mime_type="video/mp4", sha256="dup-hash",
        )
        db.session.add(existing)
        db.session.commit()
        existing_id = existing.id

    login_as(client, user_id)
    with patch("app.api.uploads.transcode_media.delay") as transcode:
        res = client.post("/api/uploads/complete", json={
            "kind": "video", "content_type": "video/mp4",
            "bucket": "b", "key": "k",
            "public_get_url": "https://b/k", "sha256": "dup-hash",
        })
    assert res.status_code == 200
    body = res.get_json()
    assert body["deduped"] is True
    assert body["id"] == existing_id
    transcode.assert_not_called()
    with app.app_context():
        # No new MediaAsset row should have been created.
        assert db.session.query(MediaAsset).count() == 1


def test_complete_without_dedup_creates_new(client, app):
    user_id = _seed_user(app)
    login_as(client, user_id)
    with patch("app.api.uploads.transcode_media.delay") as transcode:
        res = client.post("/api/uploads/complete", json={
            "kind": "video", "content_type": "video/mp4",
            "bucket": "b", "key": "k",
            "public_get_url": "https://b/k", "sha256": "new-hash",
        })
    assert res.status_code == 201
    assert res.get_json()["deduped"] is False
    transcode.assert_called_once()


def test_normalise_link_strips_query_and_trailing_slash():
    assert _normalise_link("https://Example.COM/foo/?utm=1") == \
        "https://example.com/foo"
    assert _normalise_link("HTTPS://example.com/foo/") == \
        "https://example.com/foo"


def test_originality_media_check_flags_repeat_upload(app):
    with app.app_context():
        user = User(email="o@example.com", display_name="o")
        db.session.add(user); db.session.flush()

        m1 = MediaAsset(user_id=user.id, kind="video",
                        storage_url="https://x", mime_type="video/mp4",
                        sha256="same")
        m2 = MediaAsset(user_id=user.id, kind="video",
                        storage_url="https://y", mime_type="video/mp4",
                        sha256="same")
        db.session.add_all([m1, m2]); db.session.flush()

        post = Post(user_id=user.id, title="t", caption="c", media_id=m2.id)
        db.session.add(post); db.session.flush()

        finding = check_media_originality(post)
        assert finding is not None
        assert finding.checker == "originality:media_sha256"
        assert finding.severity == "warn"
        assert m1.id in finding.detail["previous_media_ids"]


def test_originality_link_check_flags_reshare(app):
    with app.app_context():
        user = User(email="o2@example.com", display_name="o2")
        db.session.add(user); db.session.flush()

        old = Post(user_id=user.id, title="old", caption="x",
                   link_url="https://example.com/article")
        new = Post(user_id=user.id, title="new", caption="y",
                   link_url="https://Example.com/article/?ref=fb")
        db.session.add_all([old, new]); db.session.flush()

        finding = check_link_originality(new)
        assert finding is not None
        assert finding.checker == "originality:link_reshare"
        assert old.id in finding.detail["previous_post_ids"]


def test_originality_findings_persist_via_engine(app):
    with app.app_context():
        user = User(email="e@example.com", display_name="e")
        db.session.add(user); db.session.flush()
        m1 = MediaAsset(user_id=user.id, kind="image",
                        storage_url="https://x", mime_type="image/jpeg",
                        sha256="dup")
        m2 = MediaAsset(user_id=user.id, kind="image",
                        storage_url="https://y", mime_type="image/jpeg",
                        sha256="dup")
        db.session.add_all([m1, m2]); db.session.flush()
        post = Post(user_id=user.id, title="t", caption="c", media_id=m2.id)
        db.session.add(post); db.session.flush()
        account = SocialAccount(
            user_id=user.id, platform=Platform.FACEBOOK,
            external_account_id="x", handle="x", access_token_enc=b"a",
        )
        db.session.add(account); db.session.flush()
        target = PostTarget(post_id=post.id, account_id=account.id,
                            status=JobStatus.PENDING)
        db.session.add(target); db.session.commit()

        findings = ComplianceEngine().evaluate(post, [target])
        names = [f.checker for f in findings]
        assert "originality:media_sha256" in names
