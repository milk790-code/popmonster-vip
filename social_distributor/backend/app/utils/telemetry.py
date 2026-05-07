"""Optional observability: Sentry for errors, OpenTelemetry for traces.

Both are off-by-default. Enabling either is a single env var:

* ``SENTRY_DSN`` — full Sentry project DSN. We attach Flask + Celery
  integrations and enable performance tracing at ``SENTRY_TRACES_SAMPLE_RATE``
  (defaults to 0.1, i.e. 10% of transactions).
* ``OTEL_EXPORTER_OTLP_ENDPOINT`` — any OTLP receiver (Tempo, Jaeger,
  Honeycomb, Datadog OTLP proxy). Auto-instruments Flask, Celery,
  SQLAlchemy, and the ``requests`` library used by every platform adapter.

``trace_dispatch`` wraps each publish attempt in a named span tagged with
``target_id``, ``post_id``, ``user_id``, and ``platform`` so a failure jumps
straight to the offending row in the traces UI.
"""
from __future__ import annotations

import contextlib
import logging
import os
from typing import Any, Iterator

log = logging.getLogger(__name__)

SERVICE_NAME = os.environ.get("OTEL_SERVICE_NAME", "social-distributor")

_sentry_initialized = False
_otel_initialized = False
_tracer = None


def init_telemetry(component: str = "api") -> None:
    """Idempotent. Safe to call from both Flask app factory and Celery worker."""
    _init_sentry(component)
    _init_otel(component)


def _init_sentry(component: str) -> None:
    global _sentry_initialized
    dsn = os.environ.get("SENTRY_DSN")
    if not dsn or _sentry_initialized:
        return
    try:
        import sentry_sdk
        from sentry_sdk.integrations.flask import FlaskIntegration
        from sentry_sdk.integrations.celery import CeleryIntegration
        from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration
    except ImportError:
        log.warning("sentry_sdk not installed; SENTRY_DSN ignored")
        return
    sentry_sdk.init(
        dsn=dsn,
        integrations=[
            FlaskIntegration(),
            CeleryIntegration(),
            SqlalchemyIntegration(),
        ],
        traces_sample_rate=float(os.environ.get("SENTRY_TRACES_SAMPLE_RATE", "0.1")),
        send_default_pii=False,
        environment=os.environ.get("SENTRY_ENVIRONMENT") or os.environ.get("FLASK_ENV", "production"),
        release=os.environ.get("RELEASE_VERSION"),
    )
    sentry_sdk.set_tag("component", component)
    _sentry_initialized = True
    log.info("sentry initialized for component=%s", component)


def _init_otel(component: str) -> None:
    global _otel_initialized, _tracer
    endpoint = os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT")
    if not endpoint or _otel_initialized:
        return
    try:
        from opentelemetry import trace
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
    except ImportError:
        log.warning("opentelemetry not installed; OTEL_EXPORTER_OTLP_ENDPOINT ignored")
        return

    provider = TracerProvider(
        resource=Resource.create(
            {"service.name": SERVICE_NAME, "service.component": component}
        )
    )
    provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter()))
    trace.set_tracer_provider(provider)
    _tracer = trace.get_tracer(SERVICE_NAME)

    # Auto-instrument the libraries we use most often. Each of these is a
    # no-op until init_telemetry has been called, so it's safe to import
    # them lazily.
    _try_instrument("opentelemetry.instrumentation.flask", "FlaskInstrumentor")
    _try_instrument("opentelemetry.instrumentation.celery", "CeleryInstrumentor")
    _try_instrument("opentelemetry.instrumentation.sqlalchemy", "SQLAlchemyInstrumentor")
    _try_instrument("opentelemetry.instrumentation.requests", "RequestsInstrumentor")

    _otel_initialized = True
    log.info("otel initialized for component=%s endpoint=%s", component, endpoint)


def _try_instrument(module_path: str, class_name: str) -> None:
    try:
        module = __import__(module_path, fromlist=[class_name])
        cls = getattr(module, class_name)
        cls().instrument()
    except Exception as exc:  # noqa: BLE001
        log.debug("otel: skipping %s (%s)", class_name, exc)


@contextlib.contextmanager
def trace_dispatch(
    *,
    target_id: int,
    post_id: int,
    user_id: int,
    platform: str,
    attempt: int,
) -> Iterator[Any]:
    """Span around a single dispatch attempt; no-op if OTel not configured."""
    if _tracer is None:
        yield None
        return
    with _tracer.start_as_current_span("dispatch_target") as span:
        span.set_attribute("target.id", target_id)
        span.set_attribute("post.id", post_id)
        span.set_attribute("user.id", user_id)
        span.set_attribute("platform", platform)
        span.set_attribute("attempt", attempt)
        try:
            yield span
        except Exception as exc:
            span.record_exception(exc)
            raise


def add_breadcrumb(category: str, message: str, **data: Any) -> None:
    """Attach context to the current scope so a later error report shows the trail."""
    if not _sentry_initialized:
        return
    try:
        import sentry_sdk
        sentry_sdk.add_breadcrumb(category=category, message=message, data=data)
    except Exception:  # noqa: BLE001
        pass
