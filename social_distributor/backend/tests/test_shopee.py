"""Shopee platform adapter unit tests (no external API calls)."""
import hashlib
import hmac

import pytest

from app.models import Platform
from app.platforms.shopee import (
    DESCRIPTION_LIMIT,
    ShopeePublisher,
    _sign,
)


def test_sign_no_auth():
    """Public endpoint signature (no access_token / shop_id)."""
    sig = _sign("secret_key", "12345", "/api/v2/test", 1700000000)
    expected = hmac.new(
        b"secret_key",
        b"12345/api/v2/test1700000000",
        hashlib.sha256,
    ).hexdigest()
    assert sig == expected


def test_sign_with_auth():
    """Authenticated endpoint signature includes access_token + shop_id."""
    sig = _sign("secret_key", "12345", "/api/v2/test", 1700000000,
                access_token="tok", shop_id="99")
    expected = hmac.new(
        b"secret_key",
        b"12345/api/v2/test1700000000tok99",
        hashlib.sha256,
    ).hexdigest()
    assert sig == expected


def test_shopee_platform_in_enum():
    assert Platform.SHOPEE.value == "shopee"


def test_publisher_validate_missing_video():
    from app.platforms.base import PublishRequest
    pub = ShopeePublisher()
    req = PublishRequest(caption="hello", media_url=None, media_kind=None)
    issues = pub.validate(req)
    assert any("video" in i.lower() for i in issues)


def test_publisher_validate_caption_too_long():
    from app.platforms.base import PublishRequest
    pub = ShopeePublisher()
    req = PublishRequest(
        caption="x" * (DESCRIPTION_LIMIT + 1),
        media_url="https://example.com/v.mp4",
        media_kind="video",
    )
    issues = pub.validate(req)
    assert any("description" in i.lower() for i in issues)


def test_publisher_validate_ok():
    from app.platforms.base import PublishRequest
    pub = ShopeePublisher()
    req = PublishRequest(
        caption="好產品推薦",
        media_url="https://example.com/v.mp4",
        media_kind="video",
    )
    assert pub.validate(req) == []


def test_compliance_rules_shopee(app):
    """Shopee rules are present and require video media."""
    from app.compliance.rules import PLATFORM_RULES
    rules = PLATFORM_RULES[Platform.SHOPEE]
    assert rules.requires_media is True
    assert "video" in rules.allowed_media
    assert rules.caption_max == DESCRIPTION_LIMIT
