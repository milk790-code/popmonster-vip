"""Daily token-expiry scan + Meta liveness probe — 96號 指令2.

目標檔案位置:social_distributor/backend/app/scheduler/token_monitor.py(新檔)

每天掃 social_accounts.token_expires_at:
- 7 天內到期 → 寫入 alerts 表(kind=token_expiring)+ 列入 JSON 報告
- FACEBOOK / INSTAGRAM 帳號用 GET graph/me?fields=id 驗活;
  4xx(400/401/403)→ account.extra["needs_reauth"]=True
  + alerts(kind=needs_reauth)
- 任務回傳完整 JSON 報告(Celery result backend 可查),同時 log 一份;
  讀取走 GET /api/alerts?unresolved=1。

防 56號 token 老化重演。與既有 refresh_oauth_tokens(到期前 24h 自動續)
互補:那個救「能自動續的」,這個對「自動救不了、要人工重授權的」提前
7 天示警。
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone

from ..extensions import db
from ..models import Alert, Platform, SocialAccount
from ..platforms._http import request_json
from ..platforms.base import PlatformError
from ..utils.audit import record as audit
from ..utils.crypto import cipher
from .celery_app import celery_app

log = logging.getLogger(__name__)

GRAPH_BASE = "https://graph.facebook.com/v20.0"
EXPIRY_HORIZON_DAYS = 7
_META_PLATFORMS = (Platform.FACEBOOK, Platform.INSTAGRAM)


def _upsert_alert(account: SocialAccount, kind: str, detail: dict) -> None:
    """One open alert per (account, kind); refresh detail if it already exists."""
    existing = (
        db.session.query(Alert)
        .filter(
            Alert.account_id == account.id,
            Alert.kind == kind,
            Alert.resolved_at.is_(None),
        )
        .one_or_none()
    )
    if existing is not None:
        existing.detail = detail
        return
    db.session.add(
        Alert(user_id=account.user_id, account_id=account.id, kind=kind, detail=detail)
    )
    audit(
        f"token_monitor.{kind}", "social_account", account.id,
        actor_user_id=account.user_id, detail=detail,
    )


@celery_app.task
def token_expiry_scan() -> dict:
    """Scan all non-revoked accounts; returns the JSON report."""
    now = datetime.now(timezone.utc)
    horizon = now + timedelta(days=EXPIRY_HORIZON_DAYS)
    c = cipher()
    report: dict = {
        "scanned_at": now.isoformat(),
        "horizon_days": EXPIRY_HORIZON_DAYS,
        "expiring": [],
        "needs_reauth": [],
        "ok": 0,
        "total": 0,
    }

    accounts = (
        db.session.query(SocialAccount)
        .filter(SocialAccount.revoked_at.is_(None))
        .all()
    )
    report["total"] = len(accounts)

    for account in accounts:
        entry = {
            "account_id": account.id,
            "platform": account.platform.value,
            "handle": account.handle,
            "token_expires_at": (
                account.token_expires_at.isoformat()
                if account.token_expires_at else None
            ),
        }
        flagged = False

        if (
            account.token_expires_at is not None
            and account.token_expires_at <= horizon
        ):
            report["expiring"].append(entry)
            _upsert_alert(account, "token_expiring", entry)
            flagged = True

        if account.platform in _META_PLATFORMS:
            try:
                token = c.decrypt(account.access_token_enc)
                request_json(
                    "GET", f"{GRAPH_BASE}/me",
                    params={"fields": "id", "access_token": token},
                )
            except PlatformError as exc:
                if exc.status_code in (400, 401, 403):
                    extra = dict(account.extra or {})
                    extra["needs_reauth"] = True
                    account.extra = extra
                    detail = {**entry, "error": str(exc)[:200]}
                    report["needs_reauth"].append(detail)
                    _upsert_alert(account, "needs_reauth", detail)
                    flagged = True
                else:
                    # 5xx / 429 / network — transient, retry on next daily tick
                    log.warning(
                        "liveness probe transient failure account %s: %s",
                        account.id, exc,
                    )
            except Exception as exc:  # noqa: BLE001 — decrypt/edge cases
                log.warning("liveness probe failed account %s: %s", account.id, exc)

        if not flagged:
            report["ok"] += 1

    db.session.commit()
    log.info("token_expiry_scan report: %s", json.dumps(report, ensure_ascii=False))
    return report
