"""Connected accounts: list, soft-delete, GDPR erasure trigger."""
from __future__ import annotations

from datetime import datetime, timezone

from flask import Blueprint, jsonify, request

from ..extensions import db
from ..models import Platform, SocialAccount, User
from ..platforms import all_platforms
from ..utils.account_profile import (
    ProfileError,
    read_profile,
    validate_profile,
    write_profile,
)
from ..utils.audit import record as audit
from ..utils.auth import current_user_id

bp = Blueprint("accounts", __name__, url_prefix="/api/accounts")


def _load_owned_account(account_id: int):
    """Return (account, error_response). Exactly one is None."""
    account = db.session.get(SocialAccount, account_id)
    if not account:
        return None, (jsonify({"error": "not found"}), 404)
    if account.user_id != current_user_id():
        return None, (jsonify({"error": "forbidden"}), 403)
    return account, None


@bp.get("")
def list_accounts():
    # Always scope to the logged-in user.
    query = db.session.query(SocialAccount).filter_by(user_id=current_user_id())
    rows = query.filter(SocialAccount.revoked_at.is_(None)).all()
    return jsonify(
        [
            {
                "id": a.id,
                "user_id": a.user_id,
                "platform": a.platform.value,
                "handle": a.handle,
                "external_account_id": a.external_account_id,
                "token_expires_at": a.token_expires_at.isoformat()
                if a.token_expires_at
                else None,
                "scopes": (a.scopes or "").split(",") if a.scopes else [],
                "extra": {k: v for k, v in (a.extra or {}).items() if k != "proxy_url"},
                "proxy_configured": bool((a.extra or {}).get("proxy_url")),
            }
            for a in rows
        ]
    )


@bp.get("/platforms")
def supported_platforms():
    return jsonify([p.value for p in all_platforms()])


@bp.post("/<int:account_id>/test")
def test_account(account_id: int):
    """Lightweight liveness check; doesn't decrypt the token."""
    account = db.session.get(SocialAccount, account_id)
    if not account:
        return jsonify({"error": "not found"}), 404
    if account.user_id != current_user_id():
        return jsonify({"error": "forbidden"}), 403
    fresh = (
        account.token_expires_at is None
        or account.token_expires_at > datetime.now(timezone.utc)
    )
    return jsonify({"fresh": fresh, "revoked": account.revoked_at is not None})


@bp.post("/users/<int:user_id>/erase")
def request_erasure(user_id: int):
    """Schedules the account for GDPR right-to-be-forgotten processing.

    The actual purge is done by an out-of-band worker so we can keep an
    auditable trail of the request itself.
    """
    if user_id != current_user_id():
        return jsonify({"error": "forbidden"}), 403
    user = db.session.get(User, user_id)
    if not user:
        return jsonify({"error": "not found"}), 404
    user.erasure_requested_at = datetime.now(timezone.utc)
    audit("user.erasure_requested", "user", user.id, actor_user_id=user.id)
    db.session.commit()
    return jsonify({"queued": user.id})


@bp.get("/profiles")
def list_profiles():
    """Every account's operating profile in one response.

    The fleet is 60+ accounts across six brand lines. Reading them one at a
    time is what forces the operator to "switch accounts" mentally, which is
    exactly the friction this endpoint removes.
    """
    rows = (
        db.session.query(SocialAccount)
        .filter_by(user_id=current_user_id())
        .filter(SocialAccount.revoked_at.is_(None))
        .order_by(SocialAccount.platform, SocialAccount.handle)
        .all()
    )
    return jsonify(
        [
            {
                "id": a.id,
                "platform": a.platform.value,
                "handle": a.handle,
                "external_account_id": a.external_account_id,
                "groups": [{"id": g.id, "name": g.name} for g in a.groups],
                "profile": read_profile(a),
            }
            for a in rows
        ]
    )


@bp.get("/<int:account_id>/profile")
def get_profile(account_id: int):
    account, err = _load_owned_account(account_id)
    if err:
        return err
    return jsonify({"id": account.id, "handle": account.handle,
                    "profile": read_profile(account)})


@bp.put("/<int:account_id>/profile")
def put_profile(account_id: int):
    """Replace an account's operating profile.

    Full replace rather than merge: a partial PATCH makes "clear the
    community list" impossible to express, and silently keeping a stale
    first_comment after an edit is worse than making the caller resend it.
    """
    account, err = _load_owned_account(account_id)
    if err:
        return err
    body = request.get_json(silent=True) or {}
    try:
        profile = validate_profile(body.get("profile", body))
    except ProfileError as exc:
        return jsonify({"error": "invalid profile", "details": exc.errors}), 400

    write_profile(account, profile)
    audit(
        "account.profile_updated",
        "social_account",
        account.id,
        actor_user_id=account.user_id,
        detail={
            "communities": len(profile["communities"]),
            "first_comment_set": bool(profile["first_comment"]),
            "interaction_role": profile["interaction"]["role"],
        },
    )
    db.session.commit()
    return jsonify({"id": account.id, "profile": profile})


@bp.patch("/<int:account_id>/proxy")
def set_proxy_url(account_id: int):
    """Set or clear the egress proxy URL for a connected account.

    Body (JSON): {"proxy_url": "socks5://user:pass@host:port"}
    Send {"proxy_url": null} or omit key to clear.
    The proxy_url is stored in SocialAccount.extra and is picked up by
    the publish task via platforms._http.set_proxy().
    """
    account = db.session.get(SocialAccount, account_id)
    if not account:
        return jsonify({"error": "not found"}), 404
    if account.user_id != current_user_id():
        return jsonify({"error": "forbidden"}), 403
    body = request.get_json(silent=True) or {}
    proxy_url = body.get("proxy_url")  # None = clear
    extra = dict(account.extra or {})
    if proxy_url:
        extra["proxy_url"] = proxy_url
    else:
        extra.pop("proxy_url", None)
    account.extra = extra
    audit(
        "account.proxy_updated",
        "social_account",
        account.id,
        actor_user_id=account.user_id,
        detail={"proxy_set": bool(proxy_url)},
    )
    db.session.commit()
    return jsonify({"id": account_id, "proxy_set": bool(proxy_url)})
