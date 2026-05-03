"""Centralised audit logging."""
from __future__ import annotations

from typing import Any

from flask import has_request_context, request

from ..extensions import db
from ..models import AuditLog


def record(
    action: str,
    resource_type: str,
    resource_id: str | int | None = None,
    actor_user_id: int | None = None,
    detail: dict[str, Any] | None = None,
) -> None:
    entry = AuditLog(
        actor_user_id=actor_user_id,
        action=action,
        resource_type=resource_type,
        resource_id=str(resource_id) if resource_id is not None else None,
        detail=detail or {},
        request_ip=request.remote_addr if has_request_context() else None,
    )
    db.session.add(entry)
