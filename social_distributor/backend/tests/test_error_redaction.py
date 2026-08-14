"""Platform errors handed back over the API must not carry credentials.

Adapter errors quote the platform's own response body verbatim, and platforms
do echo tokens back inside error text -- that is precisely why ``redact``
exists for audit rows. An error returned to a caller travels further than an
audit row does, so it needs at least the same treatment.
"""
from app.platforms.base import PlatformError
from app.utils.redact import redact_error

FAKE_META_TOKEN = "EAA" + "b" * 60
FAKE_GOOGLE_TOKEN = "ya29." + "c" * 40


def test_a_token_echoed_inside_an_error_body_is_masked():
    exc = PlatformError(
        "GET https://graph.facebook.com/v23.0/debug_token returned 400: "
        f'{{"error":{{"message":"Invalid OAuth access token {FAKE_META_TOKEN}"}}}}'
    )
    out = redact_error(exc)

    assert FAKE_META_TOKEN not in out
    assert "***" in out
    # The part that makes the error useful must survive.
    assert "Invalid OAuth access token" in out


def test_other_providers_are_covered_too():
    out = redact_error(RuntimeError(f"refresh failed for {FAKE_GOOGLE_TOKEN}"))
    assert FAKE_GOOGLE_TOKEN not in out
    assert "refresh failed" in out


def test_a_clean_error_is_left_readable():
    out = redact_error(PlatformError("meta app credentials not configured"))
    assert out == "meta app credentials not configured"


def test_the_message_is_capped_so_a_huge_body_cannot_be_dumped():
    out = redact_error(PlatformError("x" * 5000))
    assert len(out) == 300
