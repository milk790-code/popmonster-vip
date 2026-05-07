"""Ownership transfer tracking endpoints (Meta API + manual TikTok / YouTube)."""
from __future__ import annotations

from datetime import datetime, timezone

from flask import Blueprint, jsonify, request

from ..extensions import db
from ..models import OwnershipTransfer, Platform, SocialAccount
from ..transfers import meta_transfer
from ..transfers.manual_transfer import advance, transition_expired_if_overdue
from ..utils.audit import record as audit
from ..utils.crypto import cipher

bp = Blueprint("transfers", __name__, url_prefix="/api/transfers")


def _serialize(t: OwnershipTransfer) -> dict:
    return {
        "id": t.id,
        "platform": t.platform.value,
        "channel": t.channel,
        "asset_kind": t.asset_kind,
        "asset_external_id": t.asset_external_id,
        "asset_label": t.asset_label,
        "source_label": t.source_label,
        "target_label": t.target_label,
        "status": t.status,
        "requested_at": t.requested_at.isoformat() if t.requested_at else None,
        "completed_at": t.completed_at.isoformat() if t.completed_at else None,
        "expires_at": t.expires_at.isoformat() if t.expires_at else None,
        "notes": t.notes,
    }


@bp.get("")
def list_transfers():
    user_id = request.args.get("user_id", type=int)
    query = db.session.query(OwnershipTransfer)
    if user_id:
        query = query.filter_by(user_id=user_id)
    rows = query.order_by(OwnershipTransfer.requested_at.desc()).limit(200).all()
    return jsonify([_serialize(t) for t in rows])


@bp.post("")
def create_transfer():
    """Body::

        Meta API path:
        {
          "user_id": 1, "platform": "facebook",
          "channel": "api",
          "asset_kind": "page", "asset_external_id": "123",
          "from_business_id": "...", "to_business_id": "..."
        }

        TikTok / YouTube manual path:
        {
          "user_id": 1, "platform": "youtube" | "tiktok",
          "channel": "manual",
          "asset_kind": "channel" | "creator_account",
          "asset_external_id": "UC123",
          "source_label": "old @handle",
          "target_label": "new brand account",
          "expires_at": "2026-06-01T00:00:00Z"
        }
    """
    body = request.get_json(force=True)
    user_id = int(body["user_id"])
    platform = Platform(body["platform"])
    channel = body.get("channel", "manual")
    if channel not in ("api", "manual"):
        return jsonify({"error": "channel must be api or manual"}), 400

    transfer = OwnershipTransfer(
        user_id=user_id,
        platform=platform,
        asset_kind=body["asset_kind"],
        asset_external_id=body["asset_external_id"],
        asset_label=body.get("asset_label", ""),
        source_label=body.get("source_label", ""),
        target_label=body.get("target_label", ""),
        channel=channel,
        status="requested",
        notes=body.get("notes", ""),
    )
    if (raw_expiry := body.get("expires_at")):
        try:
            dt = datetime.fromisoformat(raw_expiry.replace("Z", "+00:00"))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            transfer.expires_at = dt
        except ValueError:
            return jsonify({"error": "invalid expires_at ISO8601"}), 400

    if channel == "api":
        if platform != Platform.FACEBOOK:
            return jsonify({
                "error": "API channel only supported for Meta Page transfers",
                "hint": "Use channel: manual for TikTok / YouTube",
            }), 422
        source_account = (
            db.session.query(SocialAccount)
            .filter_by(user_id=user_id, platform=Platform.FACEBOOK,
                       external_account_id=transfer.asset_external_id)
            .one_or_none()
        )
        if not source_account:
            return jsonify({"error": "no connected Page for this asset"}), 400
        token = cipher().decrypt(source_account.access_token_enc)
        try:
            raw = meta_transfer.initiate_page_transfer(
                from_business_id=body["from_business_id"],
                to_business_id=body["to_business_id"],
                page_id=transfer.asset_external_id,
                access_token=token,
            )
        except Exception as exc:
            return jsonify({"error": "meta transfer initiation failed",
                            "detail": str(exc)[:300]}), 502
        transfer.raw = raw if isinstance(raw, dict) else {}
        transfer.status = "awaiting_target"

    db.session.add(transfer)
    db.session.flush()
    audit("transfer.created", "ownership_transfer", transfer.id,
          actor_user_id=user_id,
          detail={"platform": platform.value, "channel": channel,
                  "asset": transfer.asset_external_id})
    db.session.commit()
    return jsonify(_serialize(transfer)), 201


@bp.post("/<int:transfer_id>/complete")
def mark_complete(transfer_id: int):
    transfer = db.session.get(OwnershipTransfer, transfer_id)
    if not transfer:
        return jsonify({"error": "not found"}), 404
    body = request.get_json(silent=True) or {}
    advance(transfer, "completed", notes=body.get("notes"))
    db.session.commit()
    return jsonify(_serialize(transfer))


@bp.post("/<int:transfer_id>/reject")
def mark_rejected(transfer_id: int):
    transfer = db.session.get(OwnershipTransfer, transfer_id)
    if not transfer:
        return jsonify({"error": "not found"}), 404
    body = request.get_json(silent=True) or {}
    advance(transfer, "rejected", notes=body.get("notes"))
    db.session.commit()
    return jsonify(_serialize(transfer))


@bp.post("/sweep-expired")
def sweep_expired():
    """Sync run of the auto-expire sweep; same logic as the Celery beat."""
    expired = transition_expired_if_overdue()
    return jsonify({"expired": expired})
