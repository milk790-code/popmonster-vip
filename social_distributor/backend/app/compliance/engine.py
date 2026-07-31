"""Aggregates compliance checks into a single decision.

The engine is the only place that should write :class:`ComplianceCheck` rows;
keeping all writes here gives auditors a stable shape to query against.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from ..extensions import db
from ..models import ComplianceCheck, MediaAsset, Platform, Post, PostTarget
from ..platforms import get_publisher
from .rules import PLATFORM_RULES
from .text import analyze_text
from .video import analyze_video_s3


@dataclass
class Finding:
    checker: str
    passed: bool
    severity: str  # "info" | "warn" | "block"
    detail: dict


class ComplianceEngine:
    def evaluate(
        self,
        post: Post,
        targets: Iterable[PostTarget],
        *,
        persist: bool = True,
    ) -> list[Finding]:
        """Run all checks and return findings.

        ``persist`` controls whether ComplianceCheck rows are written. The
        preview-compliance endpoint and distribute dry-run pass ``False``
        so they don't pollute the audit table with throwaway evaluations
        (A3 — previously every dry-run inserted N rows + relied on a
        ``rollback()`` that only saved the transient targets, not the
        already-flushed ComplianceCheck inserts).
        """
        findings: list[Finding] = []
        findings.extend(self._text_checks(post))
        findings.extend(self._media_checks(post.media))
        findings.extend(self._platform_checks(post, targets))
        findings.extend(self._originality_checks(post))
        if persist:
            self._persist(post, findings)
        return findings

    def has_blockers(self, findings: Iterable[Finding]) -> bool:
        return any(f.severity == "block" and not f.passed for f in findings)

    def _text_checks(self, post: Post) -> list[Finding]:
        out: list[Finding] = []
        text = "\n".join(filter(None, [post.title, post.caption]))
        for f in analyze_text(text):
            severity = "block" if f.score >= 0.9 and not f.passed else "warn"
            out.append(
                Finding(
                    checker=f"text:{f.attribute}",
                    passed=f.passed,
                    severity=severity if not f.passed else "info",
                    detail={"score": f.score, **f.detail},
                )
            )
        return out

    def _media_checks(self, media: MediaAsset | None) -> list[Finding]:
        if media is None or media.kind != "video":
            return []
        bucket = media.compliance_report.get("s3_bucket") if media.compliance_report else None
        key = media.compliance_report.get("s3_key") if media.compliance_report else None
        if not (bucket and key):
            return [
                Finding(
                    checker="video:rekognition",
                    passed=True,
                    severity="info",
                    detail={"skipped": "no s3 location recorded for media"},
                )
            ]
        result = analyze_video_s3(bucket, key)
        return [
            Finding(
                checker="video:rekognition",
                passed=result.passed,
                severity=result.severity,
                detail=result.detail,
            )
        ]

    def _platform_checks(self, post: Post, targets: Iterable[PostTarget]) -> list[Finding]:
        out: list[Finding] = []
        for target in targets:
            platform: Platform = target.account.platform
            rules = PLATFORM_RULES.get(platform)
            if rules is None:
                continue
            issues: list[str] = []
            caption = target.overrides.get("caption", post.caption)
            title = target.overrides.get("title", post.title)
            if len(caption) > rules.caption_max:
                issues.append(
                    f"caption {len(caption)}/{rules.caption_max} chars"
                )
            if rules.title_max and len(title) > rules.title_max:
                issues.append(f"title {len(title)}/{rules.title_max} chars")
            media = target_media_asset(post, target)
            media_kind = media.kind if media else None
            if rules.requires_media and not media:
                issues.append("media is required")
            if media_kind and media_kind not in rules.allowed_media:
                issues.append(
                    f"media kind {media_kind} not allowed (need {rules.allowed_media})"
                )
            for tag in rules.banned_hashtags:
                if tag.lower() in caption.lower():
                    issues.append(f"discouraged hashtag: {tag}")

            publisher = get_publisher(platform)
            issues.extend(
                publisher.validate(
                    publisher_request_from(post, target)
                )
            )

            out.append(
                Finding(
                    checker=f"platform_rules:{platform.value}",
                    passed=not issues,
                    severity="block" if issues else "info",
                    detail={"issues": issues, "notes": rules.notes},
                )
            )
        return out

    def _originality_checks(self, post: Post) -> list[Finding]:
        from .originality import check_link_originality, check_media_originality

        out: list[Finding] = []
        if (media_finding := check_media_originality(post)):
            out.append(media_finding)
        if (link_finding := check_link_originality(post)):
            out.append(link_finding)
        return out

    def _persist(self, post: Post, findings: list[Finding]) -> None:
        from ..utils.redact import redact

        for f in findings:
            # B5: drop noisy raw platform payload before persisting and run
            # the rest through the redactor in case any platform error
            # message contained an echoed token.
            cleaned = {k: v for k, v in f.detail.items() if k != "raw"}
            db.session.add(
                ComplianceCheck(
                    post_id=post.id,
                    platform=None,
                    checker=f.checker,
                    passed=f.passed,
                    severity=f.severity,
                    findings=redact(cleaned),
                )
            )


def target_media_asset(post: Post, target: PostTarget):
    """Return the media asset for this target, honoring internal media overrides."""
    raw_media_id = (target.overrides or {}).get("_media_id")
    if raw_media_id is None:
        return post.media
    try:
        media_id = int(raw_media_id)
    except (TypeError, ValueError):
        raise ValueError("invalid target media override") from None
    media = db.session.get(MediaAsset, media_id)
    if media is None or media.user_id != post.user_id:
        raise ValueError("target media override not found")
    return media


def resolve_first_comment(target: PostTarget) -> str:
    """Pick the first-comment text for one delivery, most specific wins.

    1. this post on this account   (``target.overrides``)
    2. this account, always        (``account.extra.profile.first_comment``)
    3. this brand line, always     (``group.style_profile.first_comment``)
    4. deployment-wide fallback    (``FB_FIRST_COMMENT``)

    Levels 1-3 come from the database, so they work in the Celery worker.
    Level 4 only ever applied in whichever process happened to have the
    variable set, which is why it is now the last resort rather than the
    only source.
    """
    import os

    from ..utils.account_profile import read_profile

    override = (target.overrides or {}).get("first_comment")
    if isinstance(override, str) and override.strip():
        return override.strip()

    if target.account is not None:
        text = read_profile(target.account).get("first_comment") or ""
        if text.strip():
            return text.strip()

    # PostTarget holds group_id but has no ``group`` relationship, so this
    # level needs an explicit load. Skipping it would fail silently.
    if target.group_id:
        from ..models import AccountGroup

        group = db.session.get(AccountGroup, target.group_id)
        if group is not None:
            text = (group.style_profile or {}).get("first_comment") or ""
            if isinstance(text, str) and text.strip():
                return text.strip()

    return os.environ.get("FB_FIRST_COMMENT", "").strip()


def publisher_request_from(post: Post, target: PostTarget):
    """Build a PublishRequest from ORM rows. Defined here to avoid a cycle."""
    from ..platforms.base import PublishRequest

    overrides = dict(target.overrides or {})
    caption = overrides.pop("caption", post.caption)
    title = overrides.pop("title", post.title)
    overrides.pop("_media_id", None)
    overrides.pop("first_comment", None)
    from ..utils.storage import fresh_media_url

    media = target_media_asset(post, target)
    # Sign at send time, not at upload time. storage_url is a presigned URL
    # capped at 7 days, so anything scheduled further out than that fetches a
    # dead link and fails with a 403 that reads like a permissions problem.
    media_url = fresh_media_url(media) if media else None
    media_kind = media.kind if media else None
    return PublishRequest(
        caption=caption,
        title=title,
        link_url=post.link_url,
        media_url=media_url,
        media_kind=media_kind,
        first_comment=resolve_first_comment(target),
        overrides=overrides,
    )
