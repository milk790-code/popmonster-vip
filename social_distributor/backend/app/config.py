"""Application configuration loaded from environment."""
from __future__ import annotations

import os
from dataclasses import dataclass, field


def _env(key: str, default: str | None = None) -> str | None:
    value = os.environ.get(key, default)
    if value == "":
        return None
    return value


_INSECURE_SECRET = "dev-secret"

# One-way SHA-256 of the default single-operator password, used only when no
# password is configured via env. This is a verifier, NOT a usable credential:
# the repo cannot be used to log in (you need the plaintext, which is not
# stored here). Rotate by setting OPERATOR_PASSWORD (plaintext) or
# OPERATOR_PASSWORD_SHA256 in the environment — env always wins.
_DEFAULT_OPERATOR_PASSWORD_SHA256 = (
    "4a8199c25bf7f3db287787fb7f47c16c597d427da4e1606c7d9fe2f5f483e90c"
)


def _require_secret_key() -> str:
    """Fail-closed at boot: refuse to start without a real SECRET_KEY.

    A missing key, an empty key, or the placeholder ``dev-secret`` would let
    anyone forge session cookies (and magic-link tokens). We raise instead of
    silently falling back, so a misconfigured deploy never serves traffic with
    a predictable signing key.
    """
    value = os.environ.get("SECRET_KEY", "")
    if not value or value == _INSECURE_SECRET:
        raise RuntimeError(
            "SECRET_KEY is unset or set to the insecure default "
            f"'{_INSECURE_SECRET}'. Generate one with "
            "`python -c \"import secrets; print(secrets.token_hex(32))\"` "
            "and set it in the environment before starting."
        )
    return value


@dataclass
class PlatformCredentials:
    client_id: str | None
    client_secret: str | None
    redirect_uri: str | None

    @property
    def configured(self) -> bool:
        return bool(self.client_id and self.client_secret and self.redirect_uri)


@dataclass
class Config:
    secret_key: str = field(default_factory=_require_secret_key)
    token_encryption_key: str | None = field(
        default_factory=lambda: _env("TOKEN_ENCRYPTION_KEY")
    )
    database_url: str = field(
        default_factory=lambda: _env(
            "DATABASE_URL", "sqlite:///distributor.db"
        )
    )
    redis_url: str = field(default_factory=lambda: _env("REDIS_URL", "redis://localhost:6379/0"))
    celery_broker_url: str = field(
        default_factory=lambda: _env("CELERY_BROKER_URL", "redis://localhost:6379/1")
    )
    celery_result_backend: str = field(
        default_factory=lambda: _env("CELERY_RESULT_BACKEND", "redis://localhost:6379/2")
    )

    default_timezone: str = field(
        default_factory=lambda: _env("PUBLISH_DEFAULT_TIMEZONE", "UTC")
    )
    retry_max_attempts: int = field(
        default_factory=lambda: int(_env("RETRY_MAX_ATTEMPTS", "5"))
    )
    retry_backoff_base_seconds: int = field(
        default_factory=lambda: int(_env("RETRY_BACKOFF_BASE_SECONDS", "30"))
    )

    perspective_api_key: str | None = field(
        default_factory=lambda: _env("PERSPECTIVE_API_KEY")
    )
    aws_region: str = field(default_factory=lambda: _env("AWS_REGION", "us-east-1"))

    # Operator password login (single-operator convenience). Precedence:
    # OPERATOR_PASSWORD (plaintext env) > OPERATOR_PASSWORD_SHA256 (env) >
    # baked default hash. The baked value is only a verifier hash, so the sole
    # operator is never locked out on a fresh deploy yet no usable credential
    # lives in the repo. POST /auth/login/password mints a session + token.
    operator_password: str | None = field(
        default_factory=lambda: _env("OPERATOR_PASSWORD")
    )
    operator_password_sha256: str | None = field(
        default_factory=lambda: (
            _env("OPERATOR_PASSWORD_SHA256") or _DEFAULT_OPERATOR_PASSWORD_SHA256
        )
    )
    operator_email: str = field(
        default_factory=lambda: _env("OPERATOR_EMAIL", "operator@local")
    )

    sendgrid_api_key: str | None = field(
        default_factory=lambda: _env("SENDGRID_API_KEY")
    )
    notify_email_from: str | None = field(
        default_factory=lambda: _env("NOTIFY_EMAIL_FROM")
    )
    twilio_account_sid: str | None = field(
        default_factory=lambda: _env("TWILIO_ACCOUNT_SID")
    )
    twilio_auth_token: str | None = field(
        default_factory=lambda: _env("TWILIO_AUTH_TOKEN")
    )
    twilio_from_number: str | None = field(
        default_factory=lambda: _env("TWILIO_FROM_NUMBER")
    )
    line_channel_access_token: str | None = field(
        default_factory=lambda: _env("LINE_CHANNEL_ACCESS_TOKEN")
    )
    line_admin_user_id: str | None = field(
        default_factory=lambda: _env("LINE_ADMIN_USER_ID")
    )

    def platform(self, name: str) -> PlatformCredentials:
        mapping = {
            "meta": ("META_APP_ID", "META_APP_SECRET", "META_REDIRECT_URI"),
            "threads": (
                "THREADS_APP_ID",
                "THREADS_APP_SECRET",
                "THREADS_REDIRECT_URI",
            ),
            "tiktok": (
                "TIKTOK_CLIENT_KEY",
                "TIKTOK_CLIENT_SECRET",
                "TIKTOK_REDIRECT_URI",
            ),
            "google": (
                "GOOGLE_CLIENT_ID",
                "GOOGLE_CLIENT_SECRET",
                "GOOGLE_REDIRECT_URI",
            ),
            "shopee": (
                "SHOPEE_PARTNER_ID",
                "SHOPEE_PARTNER_KEY",
                "SHOPEE_REDIRECT_URI",
            ),
            "linkedin": (
                "LINKEDIN_CLIENT_ID",
                "LINKEDIN_CLIENT_SECRET",
                "LINKEDIN_REDIRECT_URI",
            ),
        }
        cid_key, sec_key, redir_key = mapping[name]
        return PlatformCredentials(
            client_id=_env(cid_key),
            client_secret=_env(sec_key),
            redirect_uri=_env(redir_key),
        )

    def as_flask(self) -> dict:
        return {
            "SECRET_KEY": self.secret_key,
            "SQLALCHEMY_DATABASE_URI": self.database_url,
            "SQLALCHEMY_TRACK_MODIFICATIONS": False,
            "CELERY_BROKER_URL": self.celery_broker_url,
            "CELERY_RESULT_BACKEND": self.celery_result_backend,
        }

    def readiness(self) -> dict:
        """A7: machine-readable readiness for /healthz/ready.

        Reports each external dependency's configuration status (not actual
        liveness — checking liveness on every request would be wasteful).
        Use ``/healthz`` for liveness, ``/healthz/ready`` for readiness."""
        meta_creds = self.platform("meta")
        tiktok_creds = self.platform("tiktok")
        google_creds = self.platform("google")
        return {
            "database": {"configured": bool(self.database_url)},
            "redis": {"configured": bool(self.redis_url)},
            "celery": {
                "configured": bool(self.celery_broker_url and self.celery_result_backend),
            },
            "media_bucket": {
                "configured": bool(_env("MEDIA_BUCKET")),
                "endpoint_override": bool(_env("S3_ENDPOINT_URL")),
                "aws_credentials": bool(
                    _env("AWS_ACCESS_KEY_ID") and _env("AWS_SECRET_ACCESS_KEY")
                ),
            },
            "oauth": {
                "meta": meta_creds.configured,
                "tiktok": tiktok_creds.configured,
                "google": google_creds.configured,
                "shopee": self.platform("shopee").configured,
            },
            "ai": {
                "anthropic_api_key": bool(_env("ANTHROPIC_API_KEY")),
                "perspective_api_key": bool(self.perspective_api_key),
            },
            "notify": {
                "sendgrid": bool(self.sendgrid_api_key and self.notify_email_from),
                "twilio": bool(
                    self.twilio_account_sid
                    and self.twilio_auth_token
                    and self.twilio_from_number
                ),
                "line": bool(self.line_channel_access_token and self.line_admin_user_id),
            },
            "encryption": {"token_key_set": bool(self.token_encryption_key)},
        }


config = Config()
