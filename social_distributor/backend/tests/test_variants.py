"""Variant engine: template fallback + Claude path (mocked)."""
from unittest.mock import MagicMock, patch

from app.utils.variants import VariantRequest, generate_variant


def test_template_variant_changes_caption_with_style(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    req = VariantRequest(
        source_caption="今天試了一家新拉麵，湯頭超讚",
        source_title="Ramen review",
        platform="instagram",
        style_profile={
            "tone": "casual",
            "emoji_density": "high",
            "hashtag_pool": ["#拉麵", "#美食日記", "#台北"],
        },
        seed="seed-1",
    )
    result = generate_variant(req)
    assert result.used_engine == "template"
    assert result.caption != req.source_caption
    assert any(tag in result.caption for tag in req.style_profile["hashtag_pool"])


def test_template_variant_is_deterministic(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    req = VariantRequest(
        source_caption="hello", source_title="t", platform="tiktok",
        style_profile={"tone": "casual", "hashtag_pool": ["#a", "#b", "#c"]},
        seed="seed-2",
    )
    a = generate_variant(req).caption
    b = generate_variant(req).caption
    assert a == b


def test_claude_variant_invoked_when_key_present(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")

    fake_response = MagicMock()
    fake_block = MagicMock()
    fake_block.type = "text"
    fake_block.text = '{"title": "新標題", "caption": "新內文 #推薦"}'
    fake_response.content = [fake_block]

    with patch("anthropic.Anthropic") as anthropic_cls:
        anthropic_cls.return_value.messages.create.return_value = fake_response
        req = VariantRequest(
            source_caption="原文", source_title="原標題", platform="instagram",
            style_profile={"tone": "casual"}, seed="seed",
        )
        result = generate_variant(req)
    assert result.used_engine == "claude"
    assert result.caption == "新內文 #推薦"
    assert result.title == "新標題"


def test_claude_variant_falls_back_on_error(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
    with patch("anthropic.Anthropic", side_effect=RuntimeError("boom")):
        result = generate_variant(VariantRequest(
            source_caption="orig", source_title="t", platform="instagram",
            style_profile={"tone": "casual", "hashtag_pool": ["#a"]},
            seed="seed",
        ))
    assert result.used_engine == "template"
