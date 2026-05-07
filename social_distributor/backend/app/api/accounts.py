"""Connected accounts: list, soft-delete, GDPR erasure trigger."""
from __future__ import annotations

from datetime import datetime, timezone

from flask import Blueprint, jsonify, request

from ..extensions import db
from ..models import Platform, SocialAccount, User
from ..platforms import all_platforms
from ..utils.audit import record as audit

bp = Blueprint("accounts", __name__, url_prefix="/api/accounts")


@bp.get("")
def list_accounts():
    user_id = request.args.get("user_id", type=int)
    query = db.session.query(SocialAccount)
    if user_id:
        query = query.filter_by(user_id=user_id)
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
    user = db.session.get(User, user_id)
    if not user:
        return jsonify({"error": "not found"}), 404
    user.erasure_requested_at = datetime.now(timezone.utc)
    audit("user.erasure_requested", "user", user.id, actor_user_id=user.id)
    db.session.commit()
    return jsonify({"queued": user.id})
