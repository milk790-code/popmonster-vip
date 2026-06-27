"""Read-only audit log endpoint for compliance review."""
from __future__ import annotations

from flask import Blueprint, jsonify, request

from ..extensions import db
from ..models import AuditLog
from ..utils.auth import current_user_id

bp = Blueprint("audit", __name__, url_prefix="/api/audit")


@bp.get("")
def list_audit():
    resource_type = request.args.get("resource_type")
    limit = min(request.args.get("limit", default=200, type=int), 1000)

    # Always scope to the logged-in user — never expose other users' audit log.
    query = db.session.query(AuditLog).filter_by(actor_user_id=current_user_id())
    if resource_type:
        query = query.filter_by(resource_type=resource_type)
    rows = query.order_by(AuditLog.created_at.desc()).limit(limit).all()
    return jsonify(
        [
            {
                "id": e.id,
                "actor_user_id": e.actor_user_id,
                "action": e.action,
                "resource_type": e.resource_type,
                "resource_id": e.resource_id,
                "request_ip": e.request_ip,
                "detail": e.detail,
                "created_at": e.created_at.isoformat(),
            }
            for e in rows
        ]
    )
