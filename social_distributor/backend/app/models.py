"""SQLAlchemy ORM models.

Token columns store encrypted blobs (see utils.crypto). All timestamps are UTC.
GDPR note: ``User`` rows hold the legal basis for storing connected
``SocialAccount`` records and own ``erasure_requested_at`` for right-to-be-forgotten
processing.
"""
from __future__ import annotations

import enum
from datetime import datetime, timezone

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    LargeBinary,
    String,
    Table,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .extensions import db


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Platform(str, enum.Enum):
    FACEBOOK = "facebook"
    INSTAGRAM = "instagram"
    TIKTOK = "tiktok"
    YOUTUBE = "youtube"
    META_THREADS = "threads"
    SHOPEE = "shopee"
    LINKEDIN = "linkedin"


class JobStatus(str, enum.Enum):
    PENDING = "pending"
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"
    REJECTED_COMPLIANCE = "rejected_compliance"


class User(db.Model):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    display_name: Mapped[str] = mapped_column(String(120), nullable=False)
    timezone: Mapped[str] = mapped_column(String(64), default="UTC", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    erasure_requested_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    accounts: Mapped[list["SocialAccount"]] = relationship(back_populates="user")
    posts: Mapped[list["Post"]] = relationship(back_populates="user")


class SocialAccount(db.Model):
    """A connected platform account (per-user, per-platform)."""

    __tablename__ = "social_accounts"
    __table_args__ = (
        Index("ix_social_accounts_user_platform", "user_id", "platform"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    platform: Mapped[Platform] = mapped_column(Enum(Platform), nullable=False)
    external_account_id: Mapped[str] = mapped_column(String(128), nullable=False)
    handle: Mapped[str] = mapped_column(String(255), nullable=False)
    scopes: Mapped[str] = mapped_column(Text, default="")

    access_token_enc: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    refresh_token_enc: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    token_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    extra: Mapped[dict] = mapped_column(JSON, default=dict)
    revoked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    user: Mapped[User] = relationship(back_populates="accounts")
    targets: Mapped[list["PostTarget"]] = relationship(back_populates="account")
    groups: Mapped[list["AccountGroup"]] = relationship(
        secondary="account_group_members", back_populates="accounts"
    )


account_group_members = Table(
    "account_group_members",
    db.metadata,
    Column("group_id", ForeignKey("account_groups.id", ondelete="CASCADE"), primary_key=True),
    Column("account_id", ForeignKey("social_accounts.id", ondelete="CASCADE"), primary_key=True),
    UniqueConstraint("group_id", "account_id", name="uq_group_account"),
)


class AccountGroup(db.Model):
    """A persona / brand bundle of platform accounts.

    A user typically has many groups, each representing a distinct creator
    voice (e.g. "美食日常 A", "技術評測 B"). Each group bundles up to one
    SocialAccount per platform (but the schema doesn't enforce that — you
    can put two FB pages in one group if you want them in lockstep).

    ``style_profile`` is the seed for the variant engine: it captures tone,
    emoji density, hashtag pool, target audience, and brand voice notes that
    get fed into the caption rewriter on each distribute.
    """

    __tablename__ = "account_groups"
    __table_args__ = (UniqueConstraint("user_id", "name", name="uq_user_group_name"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="")
    style_profile: Mapped[dict] = mapped_column(JSON, default=dict)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    default_timezone: Mapped[str] = mapped_column(String(64), default="UTC")
    # C2: which variant engine the A/B backtest learned wins for this group.
    # nullable until enough data accumulates; written by ab-variant-backtest beat.
    preferred_variant_engine: Mapped[str | None] = mapped_column(
        String(32), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )

    accounts: Mapped[list[SocialAccount]] = relationship(
        secondary=account_group_members, back_populates="groups"
    )


class MediaAsset(db.Model):
    __tablename__ = "media_assets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    kind: Mapped[str] = mapped_column(String(16), nullable=False)  # video|image
    storage_url: Mapped[str] = mapped_column(String(1024), nullable=False)
    mime_type: Mapped[str] = mapped_column(String(64), nullable=False)
    width: Mapped[int | None] = mapped_column(Integer, nullable=True)
    height: Mapped[int | None] = mapped_column(Integer, nullable=True)
    duration_seconds: Mapped[float | None] = mapped_column(nullable=True)
    sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    compliance_status: Mapped[str] = mapped_column(String(32), default="unchecked")
    compliance_report: Mapped[dict] = mapped_column(JSON, default=dict)
    derivatives: Mapped[dict] = mapped_column(JSON, default=dict)
    transcode_status: Mapped[str] = mapped_column(String(16), default="pending")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Post(db.Model):
    """A piece of content the user wants distributed.

    A single ``Post`` can be retargeted to many platforms via :class:`PostTarget`.
    Per-platform variants (caption length, hashtags, thumbnails) live in
    ``PostTarget.overrides``.
    """

    __tablename__ = "posts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    title: Mapped[str] = mapped_column(String(255), default="")
    caption: Mapped[str] = mapped_column(Text, default="")
    link_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    media_id: Mapped[int | None] = mapped_column(ForeignKey("media_assets.id"), nullable=True)

    version: Mapped[int] = mapped_column(Integer, default=1)
    parent_post_id: Mapped[int | None] = mapped_column(ForeignKey("posts.id"), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )

    user: Mapped[User] = relationship(back_populates="posts")
    media: Mapped[MediaAsset | None] = relationship()
    targets: Mapped[list["PostTarget"]] = relationship(
        back_populates="post", cascade="all, delete-orphan"
    )


class PostTarget(db.Model):
    """A scheduled delivery of a post to a single account on a single platform."""

    __tablename__ = "post_targets"
    __table_args__ = (
        Index("ix_post_targets_status_run", "status", "scheduled_for"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    post_id: Mapped[int] = mapped_column(ForeignKey("posts.id"), nullable=False)
    account_id: Mapped[int] = mapped_column(
        ForeignKey("social_accounts.id"), nullable=False
    )
    group_id: Mapped[int | None] = mapped_column(
        ForeignKey("account_groups.id"), nullable=True
    )

    overrides: Mapped[dict] = mapped_column(JSON, default=dict)
    cron_expr: Mapped[str | None] = mapped_column(String(120), nullable=True)
    timezone: Mapped[str] = mapped_column(String(64), default="UTC")
    scheduled_for: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    status: Mapped[JobStatus] = mapped_column(
        Enum(JobStatus), default=JobStatus.PENDING, nullable=False
    )
    attempt_count: Mapped[int] = mapped_column(Integer, default=0)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    external_post_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    post: Mapped[Post] = relationship(back_populates="targets")
    account: Mapped[SocialAccount] = relationship(back_populates="targets")


class PostMetric(db.Model):
    """Time-series engagement metrics per published target.

    We snapshot whatever the platform exposes; columns are the union of common
    metrics so cross-platform queries stay simple. Per-platform extras (e.g.
    YouTube's ``averageViewPercentage``) live in ``raw``. Each row is one
    ingestion sample — ``fetched_at`` is when we asked the platform, not when
    the post was made.
    """

    __tablename__ = "post_metrics"
    __table_args__ = (
        Index("ix_post_metrics_target_fetched", "target_id", "fetched_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    target_id: Mapped[int] = mapped_column(
        ForeignKey("post_targets.id"), nullable=False
    )
    fetched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow
    )
    reach: Mapped[int | None] = mapped_column(Integer, nullable=True)
    impressions: Mapped[int | None] = mapped_column(Integer, nullable=True)
    likes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    comments: Mapped[int | None] = mapped_column(Integer, nullable=True)
    shares: Mapped[int | None] = mapped_column(Integer, nullable=True)
    saves: Mapped[int | None] = mapped_column(Integer, nullable=True)
    plays: Mapped[int | None] = mapped_column(Integer, nullable=True)
    watch_time_seconds: Mapped[float | None] = mapped_column(nullable=True)
    avg_view_pct: Mapped[float | None] = mapped_column(nullable=True)
    raw: Mapped[dict] = mapped_column(JSON, default=dict)


class ComplianceCheck(db.Model):
    __tablename__ = "compliance_checks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    post_id: Mapped[int] = mapped_column(ForeignKey("posts.id"), nullable=False)
    platform: Mapped[Platform | None] = mapped_column(Enum(Platform), nullable=True)
    checker: Mapped[str] = mapped_column(String(64), nullable=False)
    passed: Mapped[bool] = mapped_column(Boolean, nullable=False)
    severity: Mapped[str] = mapped_column(String(16), default="info")
    findings: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class AuditLog(db.Model):
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    actor_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id"), nullable=True
    )
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    resource_type: Mapped[str] = mapped_column(String(64), nullable=False)
    resource_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    detail: Mapped[dict] = mapped_column(JSON, default=dict)
    request_ip: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class PermissionGrant(db.Model):
    """A permission you've granted to someone on one of your assets.

    Notes:
    - ``asset_kind`` is one of: ``page`` (FB), ``ig_account``, ``ad_account``
      (TikTok BC), ``system_user`` (Meta SU token holder).
    - ``role`` mirrors the platform's wire role ("ADMIN"/"EDITOR"/etc) so we
      don't lose information across translations.
    - ``status`` is our local lifecycle: ``active``, ``revoked``, ``drift``
      (we expected it but the platform says it's gone), ``error``.
    - ``raw`` keeps the platform's last response so audit can reconstruct
      exactly what we asked for and what we got back.
    """

    __tablename__ = "permission_grants"
    __table_args__ = (
        Index("ix_perm_grants_asset", "asset_kind", "asset_external_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    platform: Mapped[Platform] = mapped_column(Enum(Platform), nullable=False)
    asset_kind: Mapped[str] = mapped_column(String(32), nullable=False)
    asset_external_id: Mapped[str] = mapped_column(String(128), nullable=False)
    asset_label: Mapped[str] = mapped_column(String(255), default="")
    grantee_external_id: Mapped[str] = mapped_column(String(128), nullable=False)
    grantee_label: Mapped[str] = mapped_column(String(255), default="")
    role: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(16), default="active")
    granted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow
    )
    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    revoked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    granted_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id"), nullable=True
    )
    raw: Mapped[dict] = mapped_column(JSON, default=dict)


class PermissionDriftAlert(db.Model):
    """Detected mismatch between our PermissionGrant rows and platform reality.

    ``kind``:
    - ``token_invalid``  — the asset's access token no longer authenticates
    - ``scope_missing``  — token is valid but lacks a scope we rely on
    - ``grant_disappeared`` — we recorded a grant the platform no longer reports
    - ``grant_unexpected``  — platform reports a grant we don't have on file
    """

    __tablename__ = "permission_drift_alerts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    grant_id: Mapped[int | None] = mapped_column(
        ForeignKey("permission_grants.id"), nullable=True
    )
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    platform: Mapped[Platform] = mapped_column(Enum(Platform), nullable=False)
    kind: Mapped[str] = mapped_column(String(32), nullable=False)
    detail: Mapped[dict] = mapped_column(JSON, default=dict)
    detected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow
    )
    resolved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    notified_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class OwnershipTransfer(db.Model):
    """Tracks an asset ownership transfer.

    ``channel`` distinguishes:
    - ``api`` — Meta BM-to-BM page transfer; we POST a request and poll status
    - ``manual`` — TikTok / YouTube / cross-org cases where the platform has
      no API for transfer; we only track what the user reports doing in the
      web UI, with reminders.

    State machine: ``requested → awaiting_target → completed | rejected | expired``.
    ``expired`` is set after ``expires_at`` if still ``awaiting_target``.
    """

    __tablename__ = "ownership_transfers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    platform: Mapped[Platform] = mapped_column(Enum(Platform), nullable=False)
    asset_kind: Mapped[str] = mapped_column(String(32), nullable=False)
    asset_external_id: Mapped[str] = mapped_column(String(128), nullable=False)
    asset_label: Mapped[str] = mapped_column(String(255), default="")
    source_label: Mapped[str] = mapped_column(String(255), default="")
    target_label: Mapped[str] = mapped_column(String(255), default="")
    channel: Mapped[str] = mapped_column(String(8), nullable=False)  # api | manual
    status: Mapped[str] = mapped_column(String(24), default="requested")
    requested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_polled_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    notes: Mapped[str] = mapped_column(Text, default="")
    raw: Mapped[dict] = mapped_column(JSON, default=dict)


class TokenExpiryAlert(db.Model):
    """Upcoming token expiration or FB liveness failure for a SocialAccount.

    kind:
    - ``expiring_soon``  — token_expires_at is within 7 days
    - ``needs_reauth``   — FB page token failed the /me liveness probe
    """

    __tablename__ = "token_expiry_alerts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    account_id: Mapped[int] = mapped_column(
        ForeignKey("social_accounts.id"), nullable=False
    )
    kind: Mapped[str] = mapped_column(String(32), nullable=False)
    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    detail: Mapped[dict] = mapped_column(JSON, default=dict)
    detected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow
    )
    resolved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    notified_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    account: Mapped["SocialAccount"] = relationship()


class RebroadcastCandidate(db.Model):
    """A historical post discovered on a connected account, available to
    promote into a new ``Post`` for re-distribution to a persona group.

    We do not download media bytes here; ``media_urls`` references the
    platform's hosted URLs (which the distributor's existing publish flow
    can pull from for FB/IG, or which the user can replace with a fresh
    upload before promoting).
    """

    __tablename__ = "rebroadcast_candidates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    source_account_id: Mapped[int] = mapped_column(
        ForeignKey("social_accounts.id"), nullable=False
    )
    external_post_id: Mapped[str] = mapped_column(String(255), nullable=False)
    fetched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow
    )
    posted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    snippet: Mapped[str] = mapped_column(Text, default="")
    media_urls: Mapped[list] = mapped_column(JSON, default=list)
    permalink: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    promoted_post_id: Mapped[int | None] = mapped_column(
        ForeignKey("posts.id"), nullable=True
    )
    used: Mapped[bool] = mapped_column(Boolean, default=False)
# ─── 96號 指令2 ───────────────────────────────────────────────────────
# 貼到 social_distributor/backend/app/models.py 檔案最末尾(RebroadcastCandidate
# class 之後)。所需 import(Integer/String/JSON/DateTime/ForeignKey/Mapped/
# mapped_column/utcnow)原檔全部已有,不用加。
#
# 建表:Railway 上 AUTO_SEED_USER=1(現役設定)會在 api 服務啟動時跑
# db.create_all(),自動補建缺少的 alerts 表,不用手動 migration。
# 保險起見的手動 SQL(Postgres):
#   CREATE TABLE IF NOT EXISTS alerts (
#     id SERIAL PRIMARY KEY,
#     user_id INTEGER REFERENCES users(id),
#     account_id INTEGER REFERENCES social_accounts(id),
#     kind VARCHAR(32) NOT NULL,
#     detail JSON,
#     created_at TIMESTAMPTZ,
#     resolved_at TIMESTAMPTZ
#   );


class Alert(db.Model):
    """96號 指令2 — token 到期/活性告警(scheduler.token_monitor 寫入).

    ``kind``:
    - ``token_expiring`` — token_expires_at 在 7 天內
    - ``needs_reauth``   — Meta GET /me?fields=id 驗活失敗(4xx),要人工重授權
    """

    __tablename__ = "alerts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    account_id: Mapped[int | None] = mapped_column(
        ForeignKey("social_accounts.id"), nullable=True
    )
    kind: Mapped[str] = mapped_column(String(32), nullable=False)
    detail: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow
    )
    resolved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    def as_dict(self) -> dict:
        return {
            "id": self.id,
            "user_id": self.user_id,
            "account_id": self.account_id,
            "kind": self.kind,
            "detail": self.detail,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "resolved_at": (
                self.resolved_at.isoformat() if self.resolved_at else None
            ),
        }
