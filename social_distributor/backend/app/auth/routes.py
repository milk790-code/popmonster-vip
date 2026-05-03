"""OAuth2 connect flows.

Each provider exposes ``/auth/<provider>/start`` (returns the authorization
URL) and ``/auth/<provider>/callback`` (exchanges the code for tokens).

State protection: we sign a JWT-like blob with itsdangerous and pin it to the
user id so a stolen URL can't be replayed against another account.
"""
from __future__ import annotations

from datetime import datetime, timezone

from flask import Blueprint, jsonify, request
from itsdangerous import BadSignature, URLSafeTimedSerializer

from ..config import config
from ..extensions import db
from ..models import Platform, SocialAccount, User
from ..platforms import get_oauth_provider
from ..platforms._http import request_json
from ..platforms.facebook import GRAPH_BASE
from ..utils.audit import record as audit
from ..utils.crypto import cipher

bp = Blueprint("auth", __name__, url_prefix="/auth")

PROVIDERS = {
    "meta": {"platforms": [Platform.FACEBOOK, Platform.INSTAGRAM]},
    "tiktok": {"platforms": [Platform.TIKTOK]},
    "youtube": {"platforms": [Platform.YOUTUBE]},
}


def _serializer() -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(config.secret_key, salt="oauth-state")


@bp.get("/<provider>/start")
def start(provider: str):
    if provider not in PROVIDERS:
        return jsonify({"error": "unknown provider"}), 404

    user_id = request.args.get("user_id", type=int)
    if not user_id or not db.session.get(User, user_id):
        return jsonify({"error": "user_id required"}), 400

    state = _serializer().dumps({"user_id": user_id, "provider": provider})
    url = get_oauth_provider(provider).authorization_url(state)
    return jsonify({"authorization_url": url, "state": state})


@bp.get("/<provider>/callback")
def callback(provider: str):
    if provider not in PROVIDERS:
        return jsonify({"error": "unknown provider"}), 404

    code = request.args.get("code")
    state = request.args.get("state")
    if not code or not state:
        return jsonify({"error": "missing code/state"}), 400
    try:
        payload = _serializer().loads(state, max_age=600)
    except BadSignature:
        return jsonify({"error": "invalid state"}), 400
    if payload["provider"] != provider:
        return jsonify({"error": "state/provider mismatch"}), 400

    bundle = get_oauth_provider(provider).exchange_code(code)
    user_id = payload["user_id"]
    accounts = _persist_accounts(provider, user_id, bundle)
    return jsonify({"connected": [a for a in accounts]})


def _persist_accounts(provider: str, user_id: int, bundle):
    """Different providers expose different "account" units behind one OAuth.

    For Meta we discover Pages and linked IG Business accounts from /me/accounts.
    For TikTok/YouTube, the OAuth itself returns one identity, so we store one
    row per platform.
    """
    c = cipher()
    created: list[dict] = []

    def upsert(platform: Platform, ext_id: str, handle: str,
               access_token: str, refresh_token: str | None, expires_at, extra: dict):
        existing = (
            db.session.query(SocialAccount)
            .filter_by(user_id=user_id, platform=platform, external_account_id=ext_id)
            .one_or_none()
        )
        if existing is None:
            existing = SocialAccount(
                user_id=user_id,
                platform=platform,
                external_account_id=ext_id,
            )
            db.session.add(existing)
        existing.handle = handle
        existing.access_token_enc = c.encrypt(access_token)
        existing.refresh_token_enc = c.encrypt(refresh_token) if refresh_token else None
        existing.token_expires_at = expires_at
        existing.scopes = ",".join(bundle.scopes or [])
        existing.extra = extra
        existing.revoked_at = None
        db.session.flush()
        audit("account.connected", "social_account", existing.id,
              actor_user_id=user_id,
              detail={"platform": platform.value, "handle": handle})
        return {"id": existing.id, "platform": platform.value, "handle": handle}

    if provider == "meta":
        pages = request_json(
            "GET",
            f"{GRAPH_BASE}/me/accounts",
            params={"access_token": bundle.access_token,
                    "fields": "id,name,access_token,instagram_business_account"},
        )
        for page in pages.get("data", []):
            page_token = page["access_token"]
            created.append(
                upsert(
                    Platform.FACEBOOK,
                    page["id"],
                    page["name"],
                    page_token,
                    None,
                    bundle.expires_at,
                    {"page_access_token": page_token},
                )
            )
            if (ig := page.get("instagram_business_account")):
                ig_id = ig["id"]
                ig_meta = request_json(
                    "GET",
                    f"{GRAPH_BASE}/{ig_id}",
                    params={"access_token": page_token, "fields": "username"},
                )
                created.append(
                    upsert(
                        Platform.INSTAGRAM,
                        ig_id,
                        ig_meta.get("username", ig_id),
                        page_token,
                        None,
                        bundle.expires_at,
                        {"linked_page_id": page["id"]},
                    )
                )
    elif provider == "tiktok":
        open_id = bundle.extra.get("open_id") or "self"
        created.append(
            upsert(
                Platform.TIKTOK,
                open_id,
                open_id,
                bundle.access_token,
                bundle.refresh_token,
                bundle.expires_at,
                bundle.extra,
            )
        )
    elif provider == "youtube":
        creds_payload = request_json(
            "GET",
            "https://www.googleapis.com/youtube/v3/channels",
            params={"part": "snippet", "mine": "true"},
            headers={"Authorization": f"Bearer {bundle.access_token}"},
        )
        for ch in creds_payload.get("items", []):
            handle = ch.get("snippet", {}).get("title") or ch["id"]
            created.append(
                upsert(
                    Platform.YOUTUBE,
                    ch["id"],
                    handle,
                    bundle.access_token,
                    bundle.refresh_token,
                    bundle.expires_at,
                    {},
                )
            )
    db.session.commit()
    return created


@bp.post("/<int:account_id>/revoke")
def revoke(account_id: int):
    account = db.session.get(SocialAccount, account_id)
    if not account:
        return jsonify({"error": "not found"}), 404
    account.revoked_at = datetime.now(timezone.utc)
    account.access_token_enc = b""
    account.refresh_token_enc = None
    audit("account.revoked", "social_account", account.id,
          actor_user_id=account.user_id,
          detail={"platform": account.platform.value})
    db.session.commit()
    return jsonify({"revoked": account_id})
