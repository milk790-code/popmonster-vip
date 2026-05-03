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
