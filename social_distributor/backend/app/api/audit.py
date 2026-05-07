"""Read-only audit log endpoint for compliance review."""
from __future__ import annotations

from flask import Blueprint, jsonify, request

from ..extensions import db
from ..models import AuditLog

bp = Blueprint("audit", __name__, url_prefix="/api/audit")


@bp.get("")
def list_audit():
    user_id = request.args.get("user_id", type=int)
    resource_type = request.args.get("resource_type")
    limit = min(request.args.get("limit", default=200, type=int), 1000)

    query = db.session.query(AuditLog)
    if user_id:
        query = query.filter_by(actor_user_id=user_id)
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
