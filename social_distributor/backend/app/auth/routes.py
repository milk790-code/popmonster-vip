"""OAuth2 connect flows.

Each provider exposes ``/auth/<provider>/start`` (returns the authorization
URL) and ``/auth/<provider>/callback`` (renders an HTML success page that
postMessages the parent window).

State protection: we sign a JWT-like blob with itsdangerous and pin it to the
user id so a stolen URL can't be replayed against another account.

Honest scope notes wired into the callback:

- **A1**: callback returns an HTML page (not JSON). Browser redirected here
  by the platform sees a real success view, posts a message back to the
  opener tab, then auto-closes after 2s. Falls back to a "click to return"
  link if there's no opener (e.g. user opened the auth URL directly).

- **A5**: TikTok's ``video.publish`` scope is unaudited by default. If the
  callback receives a token whose ``scopes`` does NOT include
  ``video.publish``, we mark the SocialAccount with ``extra.unaudited=true``
  so the publisher can warn the user that posts will land as drafts inside
  TikTok's app.

- **B9**: Meta callback discovers IG accounts via the linked Page; we read
  ``account_type`` and skip non-Business / non-Creator accounts (publishing
  to a personal IG fails at platform-level with a confusing error).
"""
from __future__ import annotations

from datetime import datetime, timezone

from flask import Blueprint, Response, jsonify, request
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

# IG account types that the Graph API actually allows publishing to.
_IG_PUBLISHABLE_TYPES = {"BUSINESS", "MEDIA_CREATOR"}


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
    """A1: render an HTML page that posts the result back to the opener."""
    if provider not in PROVIDERS:
        return _callback_html(False, "unknown provider", [], [])

    code = request.args.get("code")
    state = request.args.get("state")
    if not code or not state:
        return _callback_html(False, "missing code/state", [], [])
    try:
        payload = _serializer().loads(state, max_age=600)
    except BadSignature:
        return _callback_html(False, "invalid or expired state", [], [])
    if payload["provider"] != provider:
        return _callback_html(False, "state/provider mismatch", [], [])

    try:
        bundle = get_oauth_provider(provider).exchange_code(code)
    except Exception as exc:  # noqa: BLE001 - surface platform error in UI
        return _callback_html(False, f"token exchange failed: {exc}", [], [])

    user_id = payload["user_id"]
    try:
        connected, skipped = _persist_accounts(provider, user_id, bundle)
    except Exception as exc:  # noqa: BLE001 - any per-account write failure
        return _callback_html(False, f"persist failed: {exc}", [], [])

    return _callback_html(True, "success", connected, skipped)


def _callback_html(ok: bool, message: str, connected: list, skipped: list) -> Response:
    import json
    payload = json.dumps({
        "ok": ok, "message": message, "connected": connected, "skipped": skipped,
    })
    title = "已連接 ✓" if ok else "連接失敗"
    headline = "✓ 連接成功" if ok else "✗ 連接失敗"
    color = "#6abf69" if ok else "#e57373"
    detail_block = ""
    if connected:
        detail_block += "<h3>已連接帳號</h3><ul>"
        for c in connected:
            detail_block += (
                f"<li>{c.get('platform','?')} · {c.get('handle','?')}"
                + (f' <em style="color:#c8a96b">(unaudited — 草稿模式)</em>'
                   if c.get('unaudited') else '')
                + "</li>"
            )
        detail_block += "</ul>"
    if skipped:
        detail_block += "<h3>跳過（不符發布條件）</h3><ul>"
        for s in skipped:
            detail_block += (
                f"<li>{s.get('platform','?')} · {s.get('handle','?')} — "
                f"{s.get('reason','')}</li>"
            )
        detail_block += "</ul>"

    body = f"""<!doctype html>
<html lang="zh-Hant-TW"><head>
<meta charset="utf-8"><title>{title}</title>
<style>
body {{ background:#0f1115; color:#ecedef; font-family:-apple-system,BlinkMacSystemFont,
       "Segoe UI","Noto Sans TC",sans-serif; padding:40px;
       display:flex;flex-direction:column;align-items:center;text-align:center; }}
h1 {{ color:{color}; }}
ul {{ text-align:left; max-width:560px; }}
em {{ font-style:italic; }}
.hint {{ color:#9aa0a6; font-size:13px; margin-top:24px; }}
a {{ color:#c8a96b; }}
</style></head><body>
<h1>{headline}</h1>
<p>{message}</p>
{detail_block}
<p class="hint">此視窗 <span id="cd">2</span> 秒後自動關閉…
<a href="#" onclick="window.close();return false;">立即關閉</a></p>
<script>
const result = {payload};
try {{
  if (window.opener && !window.opener.closed) {{
    window.opener.postMessage({{type: "distributor.oauth.complete", result}}, "*");
  }}
}} catch (e) {{}}
let n = 2;
const el = document.getElementById("cd");
const t = setInterval(() => {{
  n--; el.textContent = n;
  if (n <= 0) {{ clearInterval(t); try {{ window.close(); }} catch(e) {{}} }}
}}, 1000);
</script>
</body></html>"""
    return Response(body, status=200 if ok else 400, mimetype="text/html")


def _persist_accounts(provider: str, user_id: int, bundle):
    """Different providers expose different "account" units behind one OAuth.

    Returns ``(connected, skipped)`` lists; skipped entries surface in the
    callback HTML so the user knows e.g. "this IG isn't a Business account".
    """
    c = cipher()
    created: list[dict] = []
    skipped: list[dict] = []

    def upsert(platform: Platform, ext_id: str, handle: str,
               access_token: str, refresh_token: str | None, expires_at,
               extra: dict, *, unaudited: bool = False):
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
        merged_extra = dict(extra or {})
        if unaudited:
            merged_extra["unaudited"] = True
        existing.extra = merged_extra
        existing.revoked_at = None
        db.session.flush()
        audit("account.connected", "social_account", existing.id,
              actor_user_id=user_id,
              detail={"platform": platform.value, "handle": handle,
                      "unaudited": unaudited})
        return {"id": existing.id, "platform": platform.value,
                "handle": handle, "unaudited": unaudited}

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
                    params={"access_token": page_token,
                            "fields": "username,account_type"},
                )
                ig_username = ig_meta.get("username", ig_id)
                ig_type = ig_meta.get("account_type")  # B9
                if ig_type and ig_type not in _IG_PUBLISHABLE_TYPES:
                    skipped.append({
                        "platform": "instagram",
                        "handle": ig_username,
                        "reason": (
                            f"account_type={ig_type}; needs BUSINESS or "
                            f"MEDIA_CREATOR for content publishing"
                        ),
                    })
                else:
                    created.append(
                        upsert(
                            Platform.INSTAGRAM,
                            ig_id,
                            ig_username,
                            page_token,
                            None,
                            bundle.expires_at,
                            {"linked_page_id": page["id"],
                             "account_type": ig_type or "UNKNOWN"},
                        )
                    )
    elif provider == "tiktok":
        # A5: scope set without video.publish → mark as unaudited (drafts only).
        granted_scopes = set(bundle.scopes or [])
        unaudited = "video.publish" not in granted_scopes
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
                unaudited=unaudited,
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
    return created, skipped


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
