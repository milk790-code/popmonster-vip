"""Hashtag suggester (template fallback + Claude path mocked)."""
from unittest.mock import MagicMock, patch

from app.extensions import db
from app.models import AccountGroup, User
from app.utils.hashtags import (
    HashtagRequest,
    _filter_disallowed,
    _normalise,
    suggest_hashtags,
)

from .conftest import login_as


def test_normalise_adds_hash_and_strips_whitespace():
    assert _normalise("foo bar") == "#foobar"
    assert _normalise(" #台北美食 ") == "#台北美食"
    assert _normalise("") == ""


def test_filter_disallowed_strips_banned_tiktok_tags():
    tags = ["#fyp", "#foryou", "#美食", "#FYP"]
    out = _filter_disallowed(tags, "tiktok")
    assert "#fyp" not in [t.lower() for t in out]
    assert "#foryou" not in [t.lower() for t in out]
    assert "#美食" in out


def test_pool_fallback_returns_pool_subset(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    req = HashtagRequest(
        caption="test", platform="instagram",
        style_profile={"hashtag_pool": ["#a", "#b", "#c", "#d", "#e", "#f"]},
        count=3,
    )
    result = suggest_hashtags(req)
    assert result.used_engine == "pool"
    assert len(result.hashtags) == 3
    # Result must be deterministic for the same inputs.
    again = suggest_hashtags(req)
    assert again.hashtags == result.hashtags


def test_pool_fallback_drops_banned_tags(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    req = HashtagRequest(
        caption="t", platform="tiktok",
        style_profile={"hashtag_pool": ["#fyp", "#美食", "#foryou", "#推薦"]},
        count=10,
    )
    result = suggest_hashtags(req)
    tags_lower = [t.lower() for t in result.hashtags]
    assert "#fyp" not in tags_lower
    assert "#foryou" not in tags_lower


def test_claude_path_invoked_when_key_present(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
    fake_block = MagicMock()
    fake_block.type = "text"
    fake_block.text = '["#拉麵","#台北美食","#夜市","#fyp","#拉麵"]'  # has dup + banned
    fake_response = MagicMock()
    fake_response.content = [fake_block]

    with patch("anthropic.Anthropic") as anthropic_cls:
        anthropic_cls.return_value.messages.create.return_value = fake_response
        result = suggest_hashtags(HashtagRequest(
            caption="今天吃了拉麵", platform="tiktok",
            style_profile={"tone": "casual"}, count=10,
        ))
    assert result.used_engine == "claude"
    # Claude returned 5 strings; we drop dup + banned → 3 left
    assert "#fyp" not in [t.lower() for t in result.hashtags]
    assert len(result.hashtags) == 3


def test_endpoint_uses_group_style(client, app):
    with app.app_context():
        user = User(email="h@example.com", display_name="h")
        db.session.add(user); db.session.flush()
        group = AccountGroup(
            user_id=user.id, name="g",
            style_profile={"hashtag_pool": ["#台北", "#美食", "#日常"]},
        )
        db.session.add(group); db.session.commit()
        gid = group.id
        uid = user.id

    login_as(client, uid)
    res = client.post("/api/hashtags/suggest", json={
        "caption": "test", "platform": "instagram",
        "group_id": gid, "count": 3,
    })
    assert res.status_code == 200
    data = res.get_json()
    assert data["used_engine"] == "pool"
    assert len(data["hashtags"]) == 3
    for tag in data["hashtags"]:
        assert tag in ["#台北", "#美食", "#日常"]


def test_endpoint_404s_unknown_group(client, app):
    with app.app_context():
        user = User(email="hg@example.com", display_name="hg")
        db.session.add(user); db.session.commit()
        uid = user.id
    login_as(client, uid)
    res = client.post("/api/hashtags/suggest", json={
        "caption": "x", "platform": "instagram", "group_id": 99999,
    })
    assert res.status_code == 404
