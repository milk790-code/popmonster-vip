"""Application configuration loaded from environment."""
from __future__ import annotations

import os
from dataclasses import dataclass, field


def _env(key: str, default: str | None = None) -> str | None:
    value = os.environ.get(key, default)
    if value == "":
        return None
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
    secret_key: str = field(default_factory=lambda: _env("SECRET_KEY", "dev-secret"))
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

    def platform(self, name: str) -> PlatformCredentials:
        mapping = {
            "meta": ("META_APP_ID", "META_APP_SECRET", "META_REDIRECT_URI"),
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


config = Config()
