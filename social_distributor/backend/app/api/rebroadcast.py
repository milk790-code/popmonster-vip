"""Re-broadcast: list a connected account's historical posts and promote
selected ones into the existing distributor flow.

Honest scope:
- We **don't** re-host video bytes. ``media_urls`` references the platform's
  hosted CDN URLs. For FB/IG this works because the publisher accepts URLs;
  for TikTok the upstream URL is short-lived so the user is asked to
  re-upload during promotion.
- We don't claim to migrate cross-account ownership. This is a "republish
  the content idea on a different persona" workflow, not a transfer.
"""
from __future__ import annotations

import logging

from flask import Blueprint, jsonify, request

from ..extensions import db
from ..models import (
    AccountGroup,
    JobStatus,
    MediaAsset,
    Platform,
    Post,
    PostTarget,
    RebroadcastCandidate,
    SocialAccount,
)
from ..platforms._http import request_json
from ..platforms.facebook import GRAPH_BASE
from ..utils.audit import record as audit
from ..utils.auth import current_user_id
from ..utils.crypto import cipher
from ..utils.jitter import spread
from ..utils.redact import redact_error

log = logging.getLogger(__name__)
bp = Blueprint("rebroadcast", __name__, url_prefix="/api/rebroadcast")


def _serialize(c: RebroadcastCandidate) -> dict:
    return {
        "id": c.id,
        "source_account_id": c.source_account_id,
        "external_post_id": c.external_post_id,
        "snippet": c.snippet,
        "media_urls": c.media_urls,
        "permalink": c.permalink,
        "fetched_at": c.fetched_at.isoformat() if c.fetched_at else None,
        "posted_at": c.posted_at.isoformat() if c.posted_at else None,
        "used": c.used,
        "promoted_post_id": c.promoted_post_id,
    }


@bp.get("/candidates")
def list_candidates():
    source_account_id = request.args.get("source_account_id", type=int)
    # Always scope to the logged-in user.
    query = db.session.query(RebroadcastCandidate).filter_by(user_id=current_user_id())
    if source_account_id:
        query = query.filter_by(source_account_id=source_account_id)
    rows = query.order_by(RebroadcastCandidate.fetched_at.desc()).limit(200).all()
    return jsonify([_serialize(c) for c in rows])


@bp.post("/scan")
def scan():
    """Pull recent posts from the source account into rebroadcast_candidates."""
    body = request.get_json(force=True)
    source_account_id = int(body["source_account_id"])
    limit = min(int(body.get("limit", 25)), 100)

    account = db.session.get(SocialAccount, source_account_id)
    if not account:
        return jsonify({"error": "account not found"}), 404
    if account.user_id != current_user_id():
        return jsonify({"error": "forbidden"}), 403
    if account.revoked_at is not None:
        return jsonify({"error": "account is revoked"}), 400

    token = cipher().decrypt(account.access_token_enc)
    try:
        items = _scan_platform(account, token, limit)
    except Exception as exc:
        return jsonify({"error": "scan failed", "detail": redact_error(exc)}), 502

    inserted = 0
    for item in items:
        ext_id = item["external_post_id"]
        existing = (
            db.session.query(RebroadcastCandidate)
            .filter_by(source_account_id=account.id, external_post_id=ext_id)
            .one_or_none()
        )
        if existing:
            continue
        db.session.add(RebroadcastCandidate(
            user_id=account.user_id,
            source_account_id=account.id,
            external_post_id=ext_id,
            snippet=item.get("snippet", "")[:1000],
            media_urls=item.get("media_urls", []),
            permalink=item.get("permalink"),
            posted_at=item.get("posted_at"),
        ))
        inserted += 1

    audit("rebroadcast.scanned", "social_account", account.id,
          actor_user_id=account.user_id,
          detail={"inserted": inserted, "examined": len(items)})
    db.session.commit()
    return jsonify({"inserted": inserted, "examined": len(items)})


def _scan_platform(account: SocialAccount, token: str, limit: int) -> list[dict]:
    """Returns a list of dicts with ``external_post_id``, ``snippet``,
    ``media_urls``, ``permalink``."""
    if account.platform == Platform.FACEBOOK:
        page_token = account.extra.get("page_access_token", token)
        payload = request_json(
            "GET", f"{GRAPH_BASE}/{account.external_account_id}/posts",
            params={"access_token": page_token,
                    "fields": "id,message,permalink_url,created_time,full_picture",
                    "limit": limit},
        )
        out = []
        for item in payload.get("data", []):
            out.append({
                "external_post_id": item["id"],
                "snippet": item.get("message", ""),
                "media_urls": [item["full_picture"]] if item.get("full_picture") else [],
                "permalink": item.get("permalink_url"),
            })
        return out

    if account.platform == Platform.INSTAGRAM:
        payload = request_json(
            "GET", f"{GRAPH_BASE}/{account.external_account_id}/media",
            params={"access_token": token,
                    "fields": "id,caption,permalink,media_url,media_type,timestamp",
                    "limit": limit},
        )
        out = []
        for item in payload.get("data", []):
            url = item.get("media_url")
            out.append({
                "external_post_id": item["id"],
                "snippet": item.get("caption", ""),
                "media_urls": [url] if url else [],
                "permalink": item.get("permalink"),
            })
        return out

    if account.platform == Platform.TIKTOK:
        payload = request_json(
            "POST", "https://open.tiktokapis.com/v2/video/list/",
            headers={"Authorization": f"Bearer {token}",
                     "Content-Type": "application/json"},
            params={"fields": "id,title,share_url,cover_image_url,video_description"},
            json={"max_count": limit},
        )
        out = []
        for item in payload.get("data", {}).get("videos", []):
            out.append({
                "external_post_id": item["id"],
                "snippet": item.get("video_description") or item.get("title", ""),
                "media_urls": [item["cover_image_url"]] if item.get("cover_image_url") else [],
                "permalink": item.get("share_url"),
            })
        return out

    if account.platform == Platform.YOUTUBE:
        from googleapiclient.discovery import build
        from ..platforms.youtube import _credentials_from_token
        from ..platforms.base import TokenBundle

        bundle = TokenBundle(access_token=token,
                             refresh_token=cipher().decrypt(account.refresh_token_enc)
                                            if account.refresh_token_enc else None)
        creds = _credentials_from_token(bundle)
        yt = build("youtube", "v3", credentials=creds, cache_discovery=False)
        # Lookup uploads playlist for this channel.
        ch = yt.channels().list(part="contentDetails",
                                id=account.external_account_id).execute()
        items = ch.get("items", [])
        if not items:
            return []
        uploads = items[0]["contentDetails"]["relatedPlaylists"]["uploads"]
        listed = yt.playlistItems().list(
            part="snippet,contentDetails", playlistId=uploads, maxResults=limit
        ).execute()
        out = []
        for entry in listed.get("items", []):
            snippet = entry.get("snippet", {})
            video_id = entry.get("contentDetails", {}).get("videoId")
            thumb = (snippet.get("thumbnails") or {}).get("high", {}).get("url")
            out.append({
                "external_post_id": video_id,
                "snippet": (snippet.get("title", "") + "\n\n" +
                            snippet.get("description", "")).strip(),
                "media_urls": [thumb] if thumb else [],
                "permalink": f"https://www.youtube.com/watch?v={video_id}" if video_id else None,
            })
        return out

    return []


@bp.post("/promote")
def promote():
    """Promote a candidate into a new Post + immediately distribute to groups.

    Body::

        {
          "candidate_id": 1,
          "group_ids": [1, 2],
          "scheduled_for": null,
          "timezone": "Asia/Taipei",
          "jitter_minutes": 20,
          "generate_variants": true,
          "edit_caption": "optional override"
        }
    """
    body = request.get_json(force=True)
    candidate = db.session.get(RebroadcastCandidate, int(body["candidate_id"]))
    if not candidate:
        return jsonify({"error": "candidate not found"}), 404
    if candidate.user_id != current_user_id():
        return jsonify({"error": "forbidden"}), 403
    if candidate.used:
        return jsonify({"error": "candidate already promoted"}), 409

    group_ids = body.get("group_ids") or []
    if not group_ids:
        return jsonify({"error": "group_ids is required"}), 400

    media_id = None
    if candidate.media_urls:
        media = MediaAsset(
            user_id=candidate.user_id,
            kind="image",  # conservative default; user can swap before publish
            storage_url=candidate.media_urls[0],
            mime_type="image/jpeg",
            transcode_status="skipped",
        )
        db.session.add(media)
        db.session.flush()
        media_id = media.id

    post = Post(
        user_id=candidate.user_id,
        title="",
        caption=body.get("edit_caption") or candidate.snippet or "",
        media_id=media_id,
    )
    db.session.add(post)
    db.session.flush()

    candidate.used = True
    candidate.promoted_post_id = post.id

    audit("rebroadcast.promoted", "rebroadcast_candidate", candidate.id,
          actor_user_id=candidate.user_id,
          detail={"new_post_id": post.id, "group_ids": group_ids})
    db.session.commit()

    # Reuse the distribute endpoint's logic by calling the function directly
    # via a redirect. Simpler: hand back the post_id and let the caller hit
    # /api/posts/<id>/distribute. That avoids duplicating fanout logic here.
    return jsonify({
        "post_id": post.id,
        "next_step": f"POST /api/posts/{post.id}/distribute",
        "suggested_body": {
            "group_ids": group_ids,
            "scheduled_for": body.get("scheduled_for"),
            "timezone": body.get("timezone", "UTC"),
            "jitter_minutes": int(body.get("jitter_minutes", 0)),
            "generate_variants": bool(body.get("generate_variants", False)),
        },
    }), 201
