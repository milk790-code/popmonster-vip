"""Ask the platform what a connected account can actually do.

``SocialAccount.scopes`` is not evidence. It is written from the adapter's
hardcoded ``DEFAULT_SCOPES`` at OAuth time, so it records what this codebase
*intended* to request, not what Meta granted. When the app uses Facebook
Login for Business (``META_LOGIN_CONFIG_ID``), the real scope list lives in
the login configuration on Meta's side and can differ in both directions.

That gap is expensive: "the auto first comment needs App Review for
pages_manage_engagement" is either a week of work or already solved, and the
stored value cannot tell you which. This endpoint asks Graph directly.

Read-only towards Meta. The access token is decrypted in-process, sent to
Meta's own debug endpoint, and never returned, logged, or persisted.
"""
from __future__ import annotations

from flask import Blueprint, jsonify

from ..config import config
from ..extensions import db
from ..models import Platform, SocialAccount
from ..platforms._http import request_json
from ..platforms.base import PlatformError
from ..platforms.facebook import GRAPH_BASE
from ..utils.auth import current_user_id

bp = Blueprint("graph_permissions", __name__, url_prefix="/api/graph")

# What each capability the console offers actually needs, so the answer is
# "your first comment will/won't work" rather than a list of scope strings.
CAPABILITY_SCOPES = {
    "發文": ["pages_manage_posts"],
    "首則留言／按讚": ["pages_manage_engagement"],
    "改粉專簡介": ["pages_manage_metadata"],
    "換封面": ["business_management"],
}


@bp.get("/permissions/<int:account_id>")
def account_permissions(account_id: int):
    """Return the scopes Meta actually granted for this account's token."""
    account = db.session.get(SocialAccount, account_id)
    if account is None:
        return jsonify({"error": "not found"}), 404
    if account.user_id != current_user_id():
        return jsonify({"error": "forbidden"}), 403
    if account.platform not in (Platform.FACEBOOK, Platform.INSTAGRAM):
        return jsonify({"error": "only meta accounts expose this"}), 400

    creds = config.platform("meta")
    if not creds.configured:
        return jsonify({"error": "meta app credentials not configured"}), 503

    from ..scheduler.tasks import _decrypt_token

    bundle = _decrypt_token(account)
    token = bundle.extra.get("page_access_token", bundle.access_token)

    try:
        payload = request_json(
            "GET",
            f"{GRAPH_BASE}/debug_token",
            params={
                "input_token": token,
                # App-token form: the app itself is the caller asking about
                # one of its own tokens. Never send the page token here.
                "access_token": f"{creds.client_id}|{creds.client_secret}",
            },
        )
    except PlatformError as exc:
        # A revoked or expired token is the most common cause and is itself
        # the answer, so surface it instead of a generic 500.
        return jsonify({"error": "graph rejected the token", "detail": str(exc)}), 502

    data = payload.get("data") or {}
    granted = sorted(data.get("scopes") or [])
    granular = {
        entry.get("scope"): entry.get("target_ids")
        for entry in (data.get("granular_scopes") or [])
    }

    capabilities = {
        name: {
            "ok": all(scope in granted for scope in needed),
            "needs": needed,
            "missing": [s for s in needed if s not in granted],
        }
        for name, needed in CAPABILITY_SCOPES.items()
    }

    return jsonify(
        {
            "account_id": account.id,
            "handle": account.handle,
            "platform": account.platform.value,
            "valid": bool(data.get("is_valid")),
            "expires_at": data.get("expires_at"),
            "granted_scopes": granted,
            # Which Pages each scope actually covers. A scope can be granted
            # app-wide while covering only some Pages, which is invisible in
            # the flat scope list.
            "granular_scopes": granular,
            "capabilities": capabilities,
            "stored_scopes": (account.scopes or "").split(",") if account.scopes else [],
            "note": "stored_scopes 是綁定當下寫死的，不是 Meta 給的；以 granted_scopes 為準。",
        }
    )
