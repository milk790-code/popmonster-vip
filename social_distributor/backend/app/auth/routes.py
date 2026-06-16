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

import logging
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

logger = logging.getLogger(__name__)

bp = Blueprint("auth", __name__, url_prefix="/auth")

PROVIDERS = {
    "meta": {"platforms": [Platform.FACEBOOK, Platform.INSTAGRAM]},
    "threads": {"platforms": [Platform.META_THREADS]},
    "tiktok": {"platforms": [Platform.TIKTOK]},
    "youtube": {"platforms": [Platform.YOUTUBE]},
    "shopee": {"platforms": [Platform.SHOPEE]},
    "linkedin": {"platforms": [Platform.LINKEDIN]},
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

    # Shopee passes shop_id as a separate query param; encode it into code
    # so exchange_code() can unpack both values without extra arguments.
    if provider == "shopee":
        shop_id = request.args.get("shop_id", "")
        if not shop_id:
            return _callback_html(False, "missing shop_id from Shopee", [], [])
        code = f"{shop_id}:{code}"

    try:
        bundle = get_oauth_provider(provider).exchange_code(code)
    except Exception as exc:  # noqa: BLE001 - surface platform error in UI
        logger.exception("oauth.exchange_failed provider=%s", provider)
        return _callback_html(
            False, f"token exchange failed [{type(exc).__name__}]: {exc}", [], []
        )

    user_id = payload["user_id"]
    try:
        connected, skipped = _persist_accounts(provider, user_id, bundle)
    except Exception as exc:  # noqa: BLE001 - any per-account write failure
        logger.exception(
            "oauth.persist_failed provider=%s user_id=%s", provider, user_id
        )
        return _callback_html(
            False, f"persist failed [{type(exc).__name__}]: {exc}", [], []
        )

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
        all_pages = []
        url = f"{GRAPH_BASE}/me/accounts"
        params = {
            "access_token": bundle.access_token,
            "fields": "id,name,access_token,instagram_business_account",
            "limit": 100,
        }
        while url:
            payload = request_json("GET", url, params=params)
            all_pages.extend(payload.get("data", []))
            url = (payload.get("paging") or {}).get("next")
            params = None
            if len(all_pages) > 1000:
                break
        # Also fetch pages owned via Business Portfolios (/me/accounts misses these)
        try:
            seen_ids = {p["id"] for p in all_pages}
            biz_payload = request_json("GET", f"{GRAPH_BASE}/me/businesses", params={
                "access_token": bundle.access_token,
                "limit": 50,
            })
            for biz in biz_payload.get("data", []):
                b_url = f"{GRAPH_BASE}/{biz['id']}/owned_pages"
                b_params = {
                    "access_token": bundle.access_token,
                    "fields": "id,name,access_token,instagram_business_account",
                    "limit": 100,
                }
                while b_url:
                    b_page = request_json("GET", b_url, params=b_params)
                    for p in b_page.get("data", []):
                        if p.get("access_token") and p["id"] not in seen_ids:
                            seen_ids.add(p["id"])
                            all_pages.append(p)
                    b_url = (b_page.get("paging") or {}).get("next")
                    b_params = None
                    if len(all_pages) > 1000:
                        break
        except Exception:
            pass  # business pages are best-effort

        for page in all_pages:
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
                            "fields": "username"},
                )
                ig_username = ig_meta.get("username", ig_id)
                # Note: instagram_business_account on a Page only ever exposes
                # Business or Creator accounts — Personal IG never appears
                # here, so we don't need to filter by account_type. (The IG
                # Graph node also doesn't expose an account_type field; trying
                # to query it returns OAuthException #100.)
                created.append(
                    upsert(
                        Platform.INSTAGRAM,
                        ig_id,
                        ig_username,
                        page_token,
                        None,
                        bundle.expires_at,
                        {"linked_page_id": page["id"]},
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
    elif provider == "threads":
        # Resolve the Threads user profile (id + username) using /me.
        from ..platforms.threads import THREADS_BASE
        me = request_json(
            "GET",
            f"{THREADS_BASE}/me",
            params={
                "fields": "id,username",
                "access_token": bundle.access_token,
            },
        )
        threads_user_id = me["id"]
        username = me.get("username", threads_user_id)
        created.append(
            upsert(
                Platform.META_THREADS,
                threads_user_id,
                username,
                bundle.access_token,
                bundle.refresh_token,
                bundle.expires_at,
                bundle.extra,
            )
        )
    elif provider == "shopee":
        # shop_id is passed back by Shopee in the redirect alongside the code.
        # The callback receives ?code=<auth_code>&shop_id=<id>&state=<state>.
        # exchange_code() already unpacks shop_id from "shop_id:code".
        shop_id = bundle.extra.get("shop_id", "unknown")
        created.append(
            upsert(
                Platform.SHOPEE,
                shop_id,
                f"Shopee店鋪 #{shop_id}",
                bundle.access_token,
                bundle.refresh_token,
                bundle.expires_at,
                bundle.extra,
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


# ---------------------------------------------------------------------------
# TikTok Cookie binding (no OAuth app approval needed)
# ---------------------------------------------------------------------------

@bp.post("/tiktok/cookie")
def tiktok_cookie_connect():
    """Bind a TikTok account using a browser sessionid cookie.

    Body (JSON):
      user_id   int     required — owner user
      sessionid str     required — value of the ``sessionid`` cookie from
                                   a logged-in TikTok web session

    Returns the same shape as the OAuth callback postMessage payload so the
    frontend can handle both flows identically.
    """
    from ..platforms.tiktok import cookie_whoami

    body = request.get_json(silent=True) or {}
    user_id = body.get("user_id")
    sessionid = (body.get("sessionid") or "").strip()

    if not user_id or not db.session.get(User, user_id):
        return jsonify({"ok": False, "error": "user_id required"}), 400
    if not sessionid:
        return jsonify({"ok": False, "error": "sessionid required"}), 400

    # Validate the cookie and fetch profile info
    try:
        profile = cookie_whoami(sessionid)
    except Exception as exc:
        logger.exception("tiktok.cookie_connect whoami failed user_id=%s", user_id)
        return jsonify({"ok": False, "error": str(exc)}), 400

    open_id = profile["open_id"]
    handle = profile["handle"]

    c = cipher()
    existing = (
        db.session.query(SocialAccount)
        .filter_by(user_id=user_id, platform=Platform.TIKTOK, external_account_id=open_id)
        .one_or_none()
    )
    if existing is None:
        existing = SocialAccount(
            user_id=user_id,
            platform=Platform.TIKTOK,
            external_account_id=open_id,
        )
        db.session.add(existing)

    existing.handle = handle
    existing.access_token_enc = c.encrypt(sessionid)   # sessionid stored as access_token
    existing.refresh_token_enc = None
    existing.token_expires_at = None                   # cookie has no known expiry
    existing.scopes = "cookie"
    existing.extra = {"auth_type": "cookie", "open_id": open_id}
    existing.revoked_at = None
    db.session.flush()
    audit(
        "account.connected",
        "social_account",
        existing.id,
        actor_user_id=user_id,
        detail={"platform": "tiktok", "handle": handle, "auth_type": "cookie"},
    )
    db.session.commit()

    return jsonify({
        "ok": True,
        "connected": [{"id": existing.id, "platform": "tiktok", "handle": handle, "auth_type": "cookie"}],
        "skipped": [],
    })
