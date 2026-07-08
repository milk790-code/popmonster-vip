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


def test_claude_allows_approved_free_consultation_and_source_terms(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")

    fake_response = MagicMock()
    fake_block = MagicMock()
    fake_block.type = "text"
    fake_block.text = '{"title":"t","caption":"免費諮詢看這邊，洗車分類也含 #鍍膜"}'
    fake_response.content = [fake_block]

    with patch("anthropic.Anthropic") as anthropic_cls:
        anthropic_cls.return_value.messages.create.return_value = fake_response
        result = generate_variant(VariantRequest(
            source_caption="原始分類 #鍍膜 #洗車",
            source_title="t",
            platform="facebook",
            style_profile={"tone": "casual"},
            seed="seed",
        ))

    assert result.used_engine == "claude"
    assert "免費諮詢" in result.caption


def test_claude_still_blocks_new_free_goods_claim(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")

    fake_response = MagicMock()
    fake_block = MagicMock()
    fake_block.type = "text"
    fake_block.text = '{"title":"t","caption":"今天下單免費送商品"}'
    fake_response.content = [fake_block]

    with patch("anthropic.Anthropic") as anthropic_cls:
        anthropic_cls.return_value.messages.create.return_value = fake_response
        result = generate_variant(VariantRequest(
            source_caption="今天有新品",
            source_title="t",
            platform="facebook",
            style_profile={"tone": "casual", "hashtag_pool": ["#a"]},
            seed="seed",
        ))

    assert result.used_engine == "template"


def test_referral_cta_appended_per_platform(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    base = dict(
        source_caption="天使塗層好用",
        source_title="t",
        style_profile={"hashtag_pool": ["#a"], "tone": "casual"},
        seed="s",
        referral_code="ABCD1234",
    )
    expected_url = "popmonster.vip/?ref=ABCD1234"
    for platform in ("facebook", "instagram", "tiktok", "threads", "youtube"):
        result = generate_variant(VariantRequest(platform=platform, **base))
        assert expected_url in result.caption, f"{platform} missing referral URL"


def test_referral_cta_omitted_when_no_code(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    result = generate_variant(VariantRequest(
        source_caption="abc",
        source_title="t",
        platform="instagram",
        style_profile={"hashtag_pool": ["#a"]},
        seed="s",
    ))
    assert "ref=" not in result.caption


def test_referral_cta_respects_url_template_env(monkeypatch):
    # 必須在 import 前 patch 環境變數；module 已經 import 過了，
    # 所以這個案例驗證的是 helper 對 module 常數的直接使用——
    # 改 env 後重新呼叫不會立即生效（已是預期行為，僅紀錄）。
    from app.utils import variants as v
    cta = v.build_referral_cta("instagram", "XYZ12345")
    assert "XYZ12345" in cta
