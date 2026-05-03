"""Telemetry safety: must be silent without env config."""
import importlib

from app.utils import telemetry


def test_init_telemetry_noop_without_env(monkeypatch):
    monkeypatch.delenv("SENTRY_DSN", raising=False)
    monkeypatch.delenv("OTEL_EXPORTER_OTLP_ENDPOINT", raising=False)
    importlib.reload(telemetry)
    telemetry.init_telemetry(component="test")  # must not raise
    with telemetry.trace_dispatch(
        target_id=1, post_id=2, user_id=3, platform="tiktok", attempt=1
    ) as span:
        assert span is None
    telemetry.add_breadcrumb("test", "hello", foo="bar")  # must not raise


def test_trace_dispatch_records_exception_when_otel_off():
    """When OTel is off, exceptions still propagate normally."""
    import pytest as _pytest
    with _pytest.raises(ValueError):
        with telemetry.trace_dispatch(
            target_id=1, post_id=2, user_id=3, platform="tiktok", attempt=1
        ):
            raise ValueError("boom")
