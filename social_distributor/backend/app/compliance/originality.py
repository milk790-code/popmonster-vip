"""Originality detection for re-uploads and re-shared links.

Two checks:

1. **Media duplicate** — ``sha256`` matches an existing ``MediaAsset`` we've
   already processed. This is fine for genuine reuse (rebroadcast workflow)
   but worth surfacing if the user thought they were uploading something new.

2. **Link reshare** — the post's ``link_url`` (after a basic normalisation:
   strip query strings and trailing slash) matches a previous ``Post``'s
   link in the same user's history. Useful warning for "I think I already
   posted this last week" mistakes.

Severity is **warn**, not block — these are advisories, not policy
violations. Set ``ORIGINALITY_BLOCK=1`` to escalate to block (e.g. for
agencies that contract not to repost).
"""
from __future__ import annotations

import os
from urllib.parse import urlparse, urlunparse

from ..extensions import db
from ..models import MediaAsset, Post
from .engine import Finding


def _normalise_link(url: str) -> str:
    parsed = urlparse(url)
    path = parsed.path.rstrip("/") or "/"
    return urlunparse((parsed.scheme.lower(), parsed.netloc.lower(), path, "", "", ""))


def _block_severity() -> str:
    return "block" if os.environ.get("ORIGINALITY_BLOCK") == "1" else "warn"


def check_media_originality(post: Post) -> Finding | None:
    if not post.media or not post.media.sha256:
        return None
    same_hash = (
        db.session.query(MediaAsset)
        .filter(MediaAsset.user_id == post.user_id)
        .filter(MediaAsset.sha256 == post.media.sha256)
        .filter(MediaAsset.id != post.media.id)
        .all()
    )
    if not same_hash:
        return None
    earlier_ids = [m.id for m in same_hash]
    return Finding(
        checker="originality:media_sha256",
        passed=False,
        severity=_block_severity(),
        detail={
            "sha256": post.media.sha256,
            "previous_media_ids": earlier_ids,
            "note": "this exact file was uploaded before",
        },
    )


def check_link_originality(post: Post) -> Finding | None:
    if not post.link_url:
        return None
    normalised = _normalise_link(post.link_url)
    others = (
        db.session.query(Post)
        .filter(Post.user_id == post.user_id)
        .filter(Post.id != post.id)
        .filter(Post.link_url.isnot(None))
        .all()
    )
    duplicates = [
        p for p in others if _normalise_link(p.link_url) == normalised
    ]
    if not duplicates:
        return None
    return Finding(
        checker="originality:link_reshare",
        passed=False,
        severity=_block_severity(),
        detail={
            "normalised_url": normalised,
            "previous_post_ids": [p.id for p in duplicates[:10]],
            "previous_count": len(duplicates),
            "note": "this link has been shared before",
        },
    )
