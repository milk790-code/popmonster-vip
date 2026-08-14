"""REST endpoints for the permission grants table.

The actual platform calls happen via the modules in ``app.permissions.*``;
this layer enforces ownership, persists ``PermissionGrant`` rows, and writes
the audit log so every grant/revoke is traceable to a request.

Honest scope reflected in the endpoints:
- ``POST /grants`` only works for platforms with a real grant API (Meta
  Pages/IG, TikTok BC). YouTube is rejected with a runbook pointer.
"""
from __future__ import annotations

from datetime import datetime, timezone

from flask import Blueprint, jsonify, request, send_from_directory

from ..extensions import db
from ..models import (
    PermissionDriftAlert,
    PermissionGrant,
    Platform,
    SocialAccount,
)
from ..permissions import meta_bm, tiktok_bc
from ..permissions.health import run_health_sweep
from ..utils.audit import record as audit
from ..utils.auth import current_user_id
from ..utils.crypto import cipher
from ..utils.redact import redact_error

bp = Blueprint("permissions", __name__, url_prefix="/api/permissions")


def _serialize(grant: PermissionGrant) -> dict:
    return {
        "id": grant.id,
        "platform": grant.platform.value,
        "asset_kind": grant.asset_kind,
        "asset_external_id": grant.asset_external_id,
        "asset_label": grant.asset_label,
        "grantee_external_id": grant.grantee_external_id,
        "grantee_label": grant.grantee_label,
        "role": grant.role,
        "status": grant.status,
        "granted_at": grant.granted_at.isoformat() if grant.granted_at else None,
        "expires_at": grant.expires_at.isoformat() if grant.expires_at else None,
        "revoked_at": grant.revoked_at.isoformat() if grant.revoked_at else None,
    }


@bp.get("/grants")
def list_grants():
    # Always scope to the logged-in user — no cross-tenant listing.
    query = db.session.query(PermissionGrant).filter_by(user_id=current_user_id())
    rows = query.order_by(PermissionGrant.granted_at.desc()).all()
    return jsonify([_serialize(g) for g in rows])


@bp.post("/grants")
def create_grant():
    """Grant a role to a user on one of your platform assets.

    Body::

        {
          "user_id": 1,
          "platform": "facebook" | "instagram" | "tiktok",
          "asset_kind": "page" | "ig_account" | "ad_account",
          "asset_external_id": "123",
          "grantee_external_id": "fbuser_456",
          "grantee_label": "Alice",
          "role": "ADMIN" | "EDITOR" | ...
        }
    """
    body = request.get_json(force=True)
    platform_str = body["platform"]
    if platform_str == "youtube":
        return jsonify({
            "error": "no API for YouTube grants",
            "runbook": "/api/permissions/runbooks/youtube_transfer.md",
        }), 422

    try:
        platform = Platform(platform_str)
    except ValueError:
        return jsonify({"error": f"unknown platform: {platform_str}"}), 400

    asset_id = body["asset_external_id"]
    grantee = body["grantee_external_id"]
    role = body["role"]
    user_id = current_user_id()

    # Look up the source account whose token we'll use to perform the grant.
    source_account = (
        db.session.query(SocialAccount)
        .filter_by(user_id=user_id, platform=platform,
                   external_account_id=asset_id)
        .one_or_none()
    )
    if not source_account or source_account.revoked_at is not None:
        return jsonify({"error": "no connected account for this asset"}), 400
    token = cipher().decrypt(source_account.access_token_enc)

    try:
        if platform in (Platform.FACEBOOK, Platform.INSTAGRAM):
            raw = meta_bm.grant_role(asset_id, grantee, role,
                                     source_account.extra.get("page_access_token", token))
        elif platform == Platform.TIKTOK:
            asset_type = body.get("asset_type", "ADVERTISER")
            raw = tiktok_bc.assign_asset(
                bc_id=body["bc_id"],
                member_id=grantee,
                asset_id=asset_id,
                asset_type=asset_type,
                role=role,
                access_token=token,
            )
        else:
            return jsonify({"error": f"grants not supported for {platform_str}"}), 422
    except Exception as exc:
        return jsonify({"error": "platform grant failed", "detail": redact_error(exc)}), 502

    grant = PermissionGrant(
        user_id=user_id,
        platform=platform,
        asset_kind=body["asset_kind"],
        asset_external_id=asset_id,
        asset_label=body.get("asset_label", source_account.handle),
        grantee_external_id=grantee,
        grantee_label=body.get("grantee_label", ""),
        role=role,
        status="active",
        granted_by_user_id=user_id,
        raw=raw if isinstance(raw, dict) else {},
    )
    db.session.add(grant)
    db.session.flush()
    audit("permission.granted", "permission_grant", grant.id,
          actor_user_id=user_id,
          detail={"platform": platform_str, "asset": asset_id,
                  "grantee": grantee, "role": role})
    db.session.commit()
    return jsonify(_serialize(grant)), 201


@bp.delete("/grants/<int:grant_id>")
def revoke_grant(grant_id: int):
    grant = db.session.get(PermissionGrant, grant_id)
    if not grant:
        return jsonify({"error": "not found"}), 404
    if grant.user_id != current_user_id():
        return jsonify({"error": "forbidden"}), 403
    if grant.status != "active":
        return jsonify({"error": f"grant is {grant.status}, not active"}), 409

    source_account = (
        db.session.query(SocialAccount)
        .filter_by(user_id=grant.user_id, platform=grant.platform,
                   external_account_id=grant.asset_external_id)
        .one_or_none()
    )
    if source_account is None:
        return jsonify({"error": "source account no longer connected"}), 400
    token = cipher().decrypt(source_account.access_token_enc)

    try:
        if grant.platform in (Platform.FACEBOOK, Platform.INSTAGRAM):
            meta_bm.revoke_role(grant.asset_external_id, grant.grantee_external_id,
                                source_account.extra.get("page_access_token", token))
        elif grant.platform == Platform.TIKTOK:
            tiktok_bc.unassign_asset(
                bc_id=grant.raw.get("bc_id", ""),
                member_id=grant.grantee_external_id,
                asset_id=grant.asset_external_id,
                asset_type=grant.raw.get("asset_type", "ADVERTISER"),
                access_token=token,
            )
    except Exception as exc:
        return jsonify({"error": "platform revoke failed", "detail": redact_error(exc)}), 502

    grant.status = "revoked"
    grant.revoked_at = datetime.now(timezone.utc)
    audit("permission.revoked", "permission_grant", grant.id,
          actor_user_id=grant.user_id,
          detail={"platform": grant.platform.value,
                  "asset": grant.asset_external_id,
                  "grantee": grant.grantee_external_id})
    db.session.commit()
    return jsonify(_serialize(grant))


@bp.get("/drift")
def list_drift():
    # Always scope to the logged-in user — no cross-tenant listing.
    query = db.session.query(PermissionDriftAlert).filter_by(user_id=current_user_id())
    if request.args.get("unresolved", default="1") == "1":
        query = query.filter(PermissionDriftAlert.resolved_at.is_(None))
    rows = query.order_by(PermissionDriftAlert.detected_at.desc()).limit(200).all()
    return jsonify([
        {
            "id": a.id,
            "grant_id": a.grant_id,
            "platform": a.platform.value,
            "kind": a.kind,
            "detail": a.detail,
            "detected_at": a.detected_at.isoformat() if a.detected_at else None,
            "resolved_at": a.resolved_at.isoformat() if a.resolved_at else None,
        }
        for a in rows
    ])


@bp.post("/drift/<int:alert_id>/resolve")
def resolve_drift(alert_id: int):
    alert = db.session.get(PermissionDriftAlert, alert_id)
    if not alert:
        return jsonify({"error": "not found"}), 404
    if alert.user_id != current_user_id():
        return jsonify({"error": "forbidden"}), 403
    alert.resolved_at = datetime.now(timezone.utc)
    audit("permission.drift_resolved", "permission_drift_alert", alert.id,
          actor_user_id=alert.user_id)
    db.session.commit()
    return jsonify({"resolved": alert.id})


@bp.post("/health/run")
def trigger_health_sweep():
    """Synchronous run for ad-hoc audits; the daily Celery beat runs the same code."""
    counts = run_health_sweep()
    return jsonify(counts)


@bp.get("/runbooks/<path:filename>")
def runbook(filename: str):
    """Serve manual runbooks for platforms that don't have a grant API."""
    import os
    base = os.path.join(os.path.dirname(__file__), "..", "permissions", "manual_runbooks")
    return send_from_directory(os.path.abspath(base), filename, mimetype="text/markdown")
