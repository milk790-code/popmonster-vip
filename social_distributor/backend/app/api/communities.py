"""Hand-picked communities: the fleet-wide map, share planning, cadence.

Facebook's Graph API cannot publish into Groups -- the ``publish_to_groups``
permission and the Groups API were retired, so there is no supported way for
this backend to post a Page's content into a community on the operator's
behalf. What *is* automatable is every decision around that action: which
communities this account's content belongs in, which of them are due given
the cadence we promised ourselves, whether each one tolerates an outbound
link, and what exactly to say. This module produces that plan so the manual
step shrinks to open-and-paste.

Cadence is the load-bearing part. Dropping the same link into the same
community every time you post is what gets an account reported as spam. The
plan endpoint refuses to suggest a community until ``cadence_days`` have
passed since ``last_shared_at``, and ``mark_shared`` is what makes that
counter real.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from flask import Blueprint, jsonify, request

from ..extensions import db
from ..models import Post, PostTarget, SocialAccount
from ..utils.account_profile import read_profile, write_profile
from ..utils.audit import record as audit
from ..utils.auth import current_user_id

bp = Blueprint("communities", __name__, url_prefix="/api/communities")


def _parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def _owned_accounts():
    return (
        db.session.query(SocialAccount)
        .filter_by(user_id=current_user_id())
        .filter(SocialAccount.revoked_at.is_(None))
        .order_by(SocialAccount.handle)
        .all()
    )


@bp.get("")
def list_communities():
    """Every account's curated community list, in one response."""
    out = []
    for account in _owned_accounts():
        communities = read_profile(account)["communities"]
        if not communities:
            continue
        out.append(
            {
                "account_id": account.id,
                "handle": account.handle,
                "platform": account.platform.value,
                "communities": communities,
            }
        )
    return jsonify(
        {
            "accounts": out,
            "total_communities": sum(len(a["communities"]) for a in out),
        }
    )


def _plan_for_account(account, *, link_url: str, now: datetime) -> dict:
    profile = read_profile(account)
    due, holding = [], []

    for community in profile["communities"]:
        if not community.get("active", True):
            continue

        last = _parse_iso(community.get("last_shared_at"))
        cadence = int(community.get("cadence_days") or 14)
        if last is not None:
            next_ok = last + timedelta(days=cadence)
            if next_ok > now:
                holding.append(
                    {
                        "name": community["name"],
                        "url": community["url"],
                        "next_eligible_at": next_ok.isoformat(),
                        "days_remaining": max(
                            1, (next_ok - now).days + (1 if (next_ok - now).seconds else 0)
                        ),
                        "reason": f"上次分享後還沒滿 {cadence} 天",
                    }
                )
                continue

        # A community that bans outbound links gets the post without one.
        # Silently pasting a link there is how a Page loses posting rights.
        allows_links = community.get("allows_links", True)
        due.append(
            {
                "name": community["name"],
                "url": community["url"],
                "why": community.get("why", ""),
                "topic": community.get("topic", ""),
                "priority": community.get("priority", 3),
                "members": community.get("members", 0),
                "allows_links": allows_links,
                "include_link": bool(allows_links and link_url),
                "link_url": link_url if allows_links else None,
                "link_note": None
                if allows_links
                else "這個社團禁止外連，貼文時不要帶連結",
                "cadence_days": community.get("cadence_days", 14),
                "last_shared_at": community.get("last_shared_at") or None,
            }
        )

    due.sort(key=lambda c: (-c["priority"], -c["members"], c["name"]))
    return {
        "account_id": account.id,
        "handle": account.handle,
        "platform": account.platform.value,
        "due": due,
        "holding": holding,
    }


@bp.post("/plan")
def plan_shares():
    """Which communities should receive this post, and with what caveats.

    Body: ``{"post_id": 12}`` or ``{"account_ids": [1,2], "link_url": "..."}``.
    When ``post_id`` is given, the accounts default to the ones the post was
    actually delivered to, and the link comes from the post.

    This endpoint never contacts a platform. It reads state and returns a
    checklist -- publishing into a community stays a human action.
    """
    body = request.get_json(silent=True) or {}
    user_id = current_user_id()
    now = datetime.now(timezone.utc)

    link_url = body.get("link_url") or ""
    accounts: list[SocialAccount] = []
    post_summary = None

    if (post_id := body.get("post_id")) is not None:
        post = db.session.get(Post, post_id)
        if post is None or post.user_id != user_id:
            return jsonify({"error": "post not found"}), 404
        link_url = link_url or (post.link_url or "")
        targets = (
            db.session.query(PostTarget)
            .filter_by(post_id=post.id)
            .all()
        )
        seen: set[int] = set()
        for target in targets:
            if target.account_id in seen:
                continue
            seen.add(target.account_id)
            account = db.session.get(SocialAccount, target.account_id)
            if account is not None and account.user_id == user_id:
                accounts.append(account)
        post_summary = {
            "id": post.id,
            "title": post.title,
            "caption_preview": (post.caption or "")[:160],
            "link_url": post.link_url,
        }
    else:
        wanted = body.get("account_ids")
        for account in _owned_accounts():
            if wanted is None or account.id in set(wanted):
                accounts.append(account)

    plans = [
        _plan_for_account(a, link_url=link_url, now=now)
        for a in accounts
    ]
    plans = [p for p in plans if p["due"] or p["holding"]]

    return jsonify(
        {
            "post": post_summary,
            "generated_at": now.isoformat(),
            "accounts": plans,
            "due_count": sum(len(p["due"]) for p in plans),
            "holding_count": sum(len(p["holding"]) for p in plans),
            "note": (
                "Facebook 官方 API 不能代發到社團，這份清單是給你一次點完用的。"
                "分享完請呼叫 /api/communities/mark-shared 記一筆，節奏控管才算數。"
            ),
        }
    )


@bp.post("/mark-shared")
def mark_shared():
    """Stamp ``last_shared_at`` after a community share actually happened.

    Body: ``{"account_id": 1, "urls": ["https://facebook.com/groups/123"]}``.
    Without this the cadence guard has nothing to measure and every community
    looks permanently due.
    """
    body = request.get_json(silent=True) or {}
    account_id = body.get("account_id")
    urls = body.get("urls") or ([body["url"]] if body.get("url") else [])
    if not account_id or not urls:
        return jsonify({"error": "account_id and urls are required"}), 400

    account = db.session.get(SocialAccount, account_id)
    if account is None:
        return jsonify({"error": "not found"}), 404
    if account.user_id != current_user_id():
        return jsonify({"error": "forbidden"}), 403

    stamped_at = _parse_iso(body.get("shared_at")) or datetime.now(timezone.utc)
    profile = read_profile(account)
    wanted = set(urls)
    matched = []
    for community in profile["communities"]:
        if community.get("url") in wanted:
            community["last_shared_at"] = stamped_at.isoformat()
            matched.append(community["url"])

    if not matched:
        return jsonify({"error": "no matching community on this account",
                        "urls": sorted(wanted)}), 404

    write_profile(account, profile)
    audit(
        "community.shared",
        "social_account",
        account.id,
        actor_user_id=account.user_id,
        detail={"urls": matched, "shared_at": stamped_at.isoformat()},
    )
    db.session.commit()
    return jsonify({"account_id": account.id, "marked": matched,
                    "shared_at": stamped_at.isoformat()})
