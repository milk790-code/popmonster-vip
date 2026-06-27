"""Read-only alerts endpoint — 96號 指令2 配套.

目標檔案位置:social_distributor/backend/app/api/alerts.py(新檔)

GET  /api/alerts/?unresolved=1&limit=100   — 列警報(JSON 報告同款資料)
POST /api/alerts/<id>/resolve              — 學誼重授權後手動關閉

受 patch1 的 X-API-Key guard 保護(在 /api/ 前綴下)。
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import or_
from flask import Blueprint, jsonify, request

from ..extensions import db
from ..models import Alert
from ..utils.auth import current_user_id

bp = Blueprint("alerts", __name__, url_prefix="/api/alerts")


@bp.get("/")
def list_alerts():
    # Scope to the caller's own alerts plus system-level alerts (user_id NULL).
    uid = current_user_id()
    q = (
        db.session.query(Alert)
        .filter(or_(Alert.user_id == uid, Alert.user_id.is_(None)))
        .order_by(Alert.created_at.desc())
    )
    if request.args.get("unresolved") == "1":
        q = q.filter(Alert.resolved_at.is_(None))
    limit = min(request.args.get("limit", default=100, type=int), 500)
    return jsonify([a.as_dict() for a in q.limit(limit).all()])


@bp.post("/<int:alert_id>/resolve")
def resolve_alert(alert_id: int):
    alert = db.session.get(Alert, alert_id)
    if alert is None:
        return jsonify({"error": "not found"}), 404
    # Only the owning user (or a system-level alert) may be resolved.
    if alert.user_id is not None and alert.user_id != current_user_id():
        return jsonify({"error": "forbidden"}), 403
    alert.resolved_at = datetime.now(timezone.utc)
    db.session.commit()
    return jsonify(alert.as_dict())
