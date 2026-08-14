"""A "variant" that is identical to the source must not pass silently.

The template engine has nothing to work with when a group has no style
profile: no tone to shift, no emoji to add, no hashtag pool to draw from. It
therefore hands the caption straight back. Every account in that group then
publishes the same text, word for word -- the shape Meta's spam policy names,
on Pages it treats as a single entity.

Nothing about that is visible at publish time. These tests pin the signal
that makes it visible instead.
"""
from unittest.mock import patch

from app.utils.variants import VariantRequest, generate_variant

SOURCE = "洗完沒吹乾就打蠟，等於把水鎖在裡面"


def _req(style_profile=None, seed="s:1", label=""):
    return VariantRequest(
        source_caption=SOURCE,
        source_title="標題",
        platform="facebook",
        style_profile=style_profile if style_profile is not None else {},
        seed=seed,
        account_label=label,
    )


def test_an_empty_style_profile_is_reported_not_hidden(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    result = generate_variant(_req())

    assert result.used_engine == "template"
    assert result.caption.strip() == SOURCE          # nothing to vary with
    assert result.unchanged is True                  # ...and it says so


def test_a_real_style_profile_actually_varies(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    result = generate_variant(_req({
        "tone": "casual",
        "emoji_density": "medium",
        "hashtag_pool": ["#汽車美容", "#洗車"],
    }))

    assert result.caption.strip() != SOURCE
    assert result.unchanged is False


def test_two_accounts_sharing_a_persona_do_not_get_the_same_prompt(monkeypatch):
    """Every account in a group shares one style profile, so without the
    account identity the prompts were byte-identical and "each Page sounds
    different" was left to sampling luck."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    seen = []

    class _Block:
        type = "text"
        text = '{"title": "t", "caption": "改寫過的文案"}'

    class _Resp:
        content = [_Block()]

    class _Messages:
        def create(self, **kwargs):
            seen.append(kwargs["messages"][0]["content"])
            return _Resp()

    class _Client:
        messages = _Messages()

    with patch("anthropic.Anthropic", return_value=_Client()):
        generate_variant(_req({"tone": "casual"}, seed="s:9", label="泡泡小獸"))
        generate_variant(_req({"tone": "casual"}, seed="s:14", label="米速研磨系"))

    assert len(seen) == 2
    assert seen[0] != seen[1]
    assert "泡泡小獸" in seen[0]
    assert "米速研磨系" in seen[1]
    # The model is told the caption is going to several sibling accounts, so
    # "different from the others" is an instruction rather than an accident.
    assert "must not read like theirs" in seen[0]


def test_a_claude_variant_that_changed_the_text_is_not_flagged(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")

    class _Block:
        type = "text"
        text = '{"title": "t", "caption": "完全不同的寫法"}'

    class _Resp:
        content = [_Block()]

    class _Messages:
        def create(self, **kwargs):
            return _Resp()

    class _Client:
        messages = _Messages()

    with patch("anthropic.Anthropic", return_value=_Client()):
        result = generate_variant(_req({"tone": "casual"}))

    assert result.used_engine == "claude"
    assert result.unchanged is False
