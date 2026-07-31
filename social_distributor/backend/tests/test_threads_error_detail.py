"""Threads failures must carry enough detail to act on.

A scheduled Threads post failed every night for over ten days with the single
string `Threads create container: Invalid parameter`. Meta had told us which
parameter — in `error_subcode` and the `error_user_title`/`error_user_msg`
pair — but the adapter kept only the top-level `message` and threw the rest
away, so the failure was unactionable no matter how many times it repeated.
"""
import json

import pytest

from app.platforms.base import PlatformError
from app.platforms.threads import _raise


class _Resp:
    def __init__(self, payload, status=400, text=""):
        self._payload = payload
        self.status_code = status
        self.text = text or json.dumps(payload)
        self.ok = status < 400

    def json(self):
        if self._payload is None:
            raise ValueError("not json")
        return self._payload


def test_keeps_the_human_readable_pair_and_the_trace_id():
    resp = _Resp({
        "error": {
            "message": "Invalid parameter",
            "code": 100,
            "error_subcode": 2207026,
            "error_user_title": "影片長度不符",
            "error_user_msg": "影片必須介於 1 秒到 5 分鐘之間。",
            "fbtrace_id": "AbCdEf123",
        }
    })
    with pytest.raises(PlatformError) as exc:
        _raise(resp, "create container")
    text = str(exc.value)
    assert "Invalid parameter" in text
    assert "影片必須介於 1 秒到 5 分鐘之間。" in text, "Meta 講了人話就要留下來"
    assert "subcode=2207026" in text
    assert "fbtrace_id=AbCdEf123" in text
    assert exc.value.platform_code == "100"


def test_plain_error_still_reads_cleanly():
    """No extras should mean no empty brackets or dangling punctuation."""
    resp = _Resp({"error": {"message": "Invalid parameter", "code": 100}})
    with pytest.raises(PlatformError) as exc:
        _raise(resp, "create container")
    assert str(exc.value) == "Threads create container: Invalid parameter"


def test_only_a_title_is_enough_to_surface():
    resp = _Resp({"error": {"message": "boom", "code": 1,
                            "error_user_title": "暫時無法發布"}})
    with pytest.raises(PlatformError) as exc:
        _raise(resp, "publish")
    assert "（暫時無法發布）" in str(exc.value)


def test_non_json_body_does_not_crash_the_error_path():
    with pytest.raises(PlatformError) as exc:
        _raise(_Resp(None, status=502, text="<html>gateway</html>"), "publish")
    assert "gateway" in str(exc.value)
    assert exc.value.retryable is True, "5xx 應該可重試"


def test_4xx_is_not_retryable():
    with pytest.raises(PlatformError) as exc:
        _raise(_Resp({"error": {"message": "nope", "code": 100}}), "publish")
    assert exc.value.retryable is False
