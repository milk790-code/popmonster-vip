"""Cross-account boost: read-only views of what the fleet would do.

The engine lives in ``utils/boost.py`` (rules) and ``scheduler/tasks.py``
(execution). This module exists so the operator can see the plan *before*
anything is written to Facebook -- which Pages would speak up on a given
post, what each would actually say, which link it would carry, and who was
skipped and why.

Nothing here writes to a platform. ``/preview`` is a dry run even when the
master switch is on.
"""
from __future__ import annotations

from flask import Blueprint, jsonify, request

from ..extensions import db
from ..models import Platform, PostTarget, SocialAccount
from ..utils import boost as boost_rules
from ..utils.account_profile import read_profile
from ..utils.auth import current_user_id

bp = Blueprint("boost", __name__, url_prefix="/api/boost")


@bp.get("/settings")
def settings():
    """The switch positions, plus who is currently signed up to support.

    Returned as plain numbers rather than raw env strings so the dashboard
    shows the value that is actually in force after clamping.
    """
    accounts = (
        db.session.query(SocialAccount)
        .filter_by(user_id=current_user_id(), platform=Platform.FACEBOOK)
        .filter(SocialAccount.revoked_at.is_(None))
        .order_by(SocialAccount.handle)
        .all()
    )
    roster = []
    for account in accounts:
        profile = read_profile(account)
        interaction = profile.get("interaction") or {}
        pool = [t for t in (interaction.get("comment_pool") or [])
                if len(t.strip()) >= boost_rules.MIN_COMMENT_CHARS]
        roster.append({
            "account_id": account.id,
            "handle": account.handle,
            "role": interaction.get("role", "off"),
            "max_per_day": interaction.get("max_per_day", 0),
            "comment_pool_size": len(pool),
            "link": boost_rules.funnel_link(profile.get("link_src") or ""),
            # The single most useful field: a Page set to supporter with an
            # empty pool will never speak, and that is easy to miss.
            "ready": (
                interaction.get("role") == "supporter"
                and int(interaction.get("max_per_day") or 0) > 0
                and bool(pool)
            ),
        })
    return jsonify({
        "enabled": boost_rules.enabled(),
        "max_supporters_per_post": boost_rules.max_supporters_per_post(),
        "window_minutes": boost_rules.window_minutes(),
        "min_delay_minutes": boost_rules.min_delay_minutes(),
        "supporters_ready": sum(1 for r in roster if r["ready"]),
        "accounts": roster,
    })


@bp.get("/preview")
def preview():
    """Dry run: the exact plan for one already-published target."""
    target_id = request.args.get("target_id", type=int)
    if not target_id:
        return jsonify({"error": "target_id is required"}), 400
    target = db.session.get(PostTarget, target_id)
    if target is None or target.post.user_id != current_user_id():
        return jsonify({"error": "target not found"}), 404
    if target.account.platform != Platform.FACEBOOK:
        return jsonify({"error": "boost only applies to Facebook Pages"}), 400

    # Imported lazily: the task module pulls in Celery, which the API
    # process does not otherwise need at import time.
    from ..scheduler.tasks import build_boost_plan

    plan = build_boost_plan(target)
    payload = plan.as_dict()
    payload["target_id"] = target.id
    payload["leader"] = target.account.handle
    payload["published"] = bool(target.external_post_id)
    return jsonify(payload)
