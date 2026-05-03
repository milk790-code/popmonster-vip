"""Daily health sweep over connected accounts and recorded grants.

We detect three kinds of drift:
1. ``token_invalid`` — a SocialAccount's token no longer authenticates against
   the platform's identity endpoint (likely revoked by user, or expired
   without successful refresh).
2. ``grant_disappeared`` — a PermissionGrant we have on file isn't in the
   platform's current assigned-users list.
3. ``grant_unexpected`` — the platform reports an assigned user we don't have
   a PermissionGrant for (someone added access outside our system).

All three create / update :class:`PermissionDriftAlert` rows. Notification
is fired only on the first detection (we don't re-page on the same row
every day).
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from ..extensions import db
from ..models import (
    PermissionDriftAlert,
    PermissionGrant,
    Platform,
    SocialAccount,
    User,
)
from ..platforms._http import request_json
from ..platforms.facebook import GRAPH_BASE
from ..utils.audit import record as audit
from ..utils.crypto import cipher
from ..utils.notify import notify_publish_failed
from .meta_bm import list_assigned_users

log = logging.getLogger(__name__)


def run_health_sweep() -> dict:
    """Returns counts: {scanned, token_invalid, grant_disappeared, grant_unexpected}."""
    counts = {
        "scanned": 0,
        "token_invalid": 0,
        "grant_disappeared": 0,
        "grant_unexpected": 0,
    }
    c = cipher()

    accounts = (
        db.session.query(SocialAccount)
        .filter(SocialAccount.revoked_at.is_(None))
        .all()
    )
    for account in accounts:
        counts["scanned"] += 1
        try:
            token = c.decrypt(account.access_token_enc)
        except Exception:
            _record_alert(account.user_id, account.platform, "token_invalid",
                          {"reason": "decrypt_failed", "account_id": account.id})
            counts["token_invalid"] += 1
            continue

        if account.platform in (Platform.FACEBOOK, Platform.INSTAGRAM):
            if not _meta_token_alive(token):
                _record_alert(account.user_id, account.platform, "token_invalid",
                              {"account_id": account.id,
                               "external_account_id": account.external_account_id})
                counts["token_invalid"] += 1
                continue
            counts.update(_reconcile_meta_grants(account, token, counts))

    db.session.commit()
    return counts


def _meta_token_alive(token: str) -> bool:
    try:
        request_json("GET", f"{GRAPH_BASE}/me", params={"access_token": token})
        return True
    except Exception:
        return False


def _reconcile_meta_grants(account: SocialAccount, token: str,
                            counts: dict) -> dict:
    """Compare our PermissionGrant rows for this asset with the platform's truth."""
    try:
        platform_grants = list_assigned_users(account.external_account_id, token)
    except Exception as exc:
        log.warning("could not list grants for %s: %s",
                    account.external_account_id, exc)
        return counts

    platform_users = {g.user_id for g in platform_grants}

    our_grants = (
        db.session.query(PermissionGrant)
        .filter(PermissionGrant.user_id == account.user_id)
        .filter(PermissionGrant.asset_external_id == account.external_account_id)
        .filter(PermissionGrant.status == "active")
        .all()
    )
    our_user_ids = {g.grantee_external_id for g in our_grants}

    for grant in our_grants:
        if grant.grantee_external_id not in platform_users:
            grant.status = "drift"
            _record_alert(account.user_id, account.platform, "grant_disappeared",
                          {"grant_id": grant.id,
                           "grantee_external_id": grant.grantee_external_id},
                          grant_id=grant.id)
            counts["grant_disappeared"] += 1

    for platform_grant in platform_grants:
        if platform_grant.user_id not in our_user_ids:
            _record_alert(account.user_id, account.platform, "grant_unexpected",
                          {"asset_id": account.external_account_id,
                           "grantee_external_id": platform_grant.user_id,
                           "role": platform_grant.role,
                           "name": platform_grant.name})
            counts["grant_unexpected"] += 1
    return counts


def _record_alert(user_id: int, platform: Platform, kind: str,
                   detail: dict, *, grant_id: int | None = None) -> None:
    existing = (
        db.session.query(PermissionDriftAlert)
        .filter_by(user_id=user_id, kind=kind, grant_id=grant_id, resolved_at=None)
        .first()
    )
    if existing:
        existing.detail = detail
        existing.detected_at = datetime.now(timezone.utc)
        return

    alert = PermissionDriftAlert(
        grant_id=grant_id,
        user_id=user_id,
        platform=platform,
        kind=kind,
        detail=detail,
    )
    db.session.add(alert)
    db.session.flush()
    audit("permission.drift_detected", "permission_drift_alert", alert.id,
          actor_user_id=user_id, detail={"kind": kind, **detail})

    owner = db.session.get(User, user_id)
    notify_publish_failed(
        user_email=owner.email if owner else None,
        user_phone=None,
        platform=platform.value,
        handle=detail.get("external_account_id") or detail.get("asset_id") or "",
        error=f"permission drift: {kind}",
        target_id=alert.id,
    )
    alert.notified_at = datetime.now(timezone.utc)
