"""Manual ownership transfer tracking for TikTok / YouTube / cross-org cases.

These platforms don't expose ownership transfer through any API, so the
*actual* operation happens in their web UIs. We track the user's reported
intent and progress so:
- The dashboard knows which assets are mid-transfer (greying them out for
  publishing during the window)
- We can ping the user with an email reminder if a manual transfer goes
  past its self-declared deadline
- Audit log captures the operation as a first-class event regardless of
  whether the actual platform call was API or human

State transitions::

    requested → awaiting_target → completed
                                ↘ rejected
                                ↘ expired

``expired`` is set by ``transition_expired_if_overdue`` once the user-set
``expires_at`` passes without ``completed`` or ``rejected``.
"""
from __future__ import annotations

from datetime import datetime, timezone

from ..extensions import db
from ..models import OwnershipTransfer, User
from ..utils.audit import record as audit
from ..utils.notify import notify_publish_failed

VALID_STATUSES = {"requested", "awaiting_target", "completed", "rejected", "expired"}


def advance(transfer: OwnershipTransfer, new_status: str, *,
            notes: str | None = None) -> OwnershipTransfer:
    if new_status not in VALID_STATUSES:
        raise ValueError(f"unknown status: {new_status}")
    transfer.status = new_status
    if notes:
        transfer.notes = (transfer.notes + "\n" + notes).strip() if transfer.notes else notes
    if new_status in ("completed", "rejected", "expired"):
        transfer.completed_at = datetime.now(timezone.utc)
    audit("transfer.status_changed", "ownership_transfer", transfer.id,
          actor_user_id=transfer.user_id,
          detail={"to": new_status, "platform": transfer.platform.value,
                  "channel": transfer.channel})
    return transfer


def transition_expired_if_overdue() -> int:
    """Sweep awaiting_target transfers past their ``expires_at``."""
    now = datetime.now(timezone.utc)
    candidates = (
        db.session.query(OwnershipTransfer)
        .filter(OwnershipTransfer.status == "awaiting_target")
        .filter(OwnershipTransfer.expires_at.isnot(None))
        .all()
    )
    expired = 0
    for transfer in candidates:
        deadline = transfer.expires_at
        if deadline is not None and deadline.tzinfo is None:
            deadline = deadline.replace(tzinfo=timezone.utc)
        if deadline is None or deadline > now:
            continue
        advance(transfer, "expired", notes=f"auto-expired at {now.isoformat()}")
        owner = db.session.get(User, transfer.user_id)
        notify_publish_failed(
            user_email=owner.email if owner else None,
            user_phone=None,
            platform=transfer.platform.value,
            handle=transfer.asset_label or transfer.asset_external_id,
            error="manual transfer deadline passed without confirmation",
            target_id=transfer.id,
        )
        expired += 1
    db.session.commit()
    return expired
