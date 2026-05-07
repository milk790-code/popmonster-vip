"""A/B variant experiments — distribute and query results.

Two endpoints:

- ``POST /api/posts/<id>/distribute_ab`` — same as ``distribute`` but splits
  the group's accounts into two halves and assigns engine A to one half,
  engine B to the other. Useful when you want a controlled test inside one
  publish run instead of waiting for the weekly backtest.

- ``GET /api/experiments/results?group_id=N&since=ISO`` — the rolled-up
  comparison from ``utils.experiments.compare_variants``, suitable for the
  Insights tab.

- ``POST /api/experiments/backtest`` — run the same backtest the weekly
  beat runs, on demand. Returns the persisted winners so the user can see
  what changed without waiting until next Monday.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from flask import Blueprint, jsonify, request

from ..extensions import db
from ..models import (
    AccountGroup,
    JobStatus,
    Platform,
    Post,
    PostTarget,
    SocialAccount,
)
from ..utils.audit import record as audit
from ..utils.experiments import backtest_and_persist_winners, compare_variants
from ..utils.jitter import spread
from ..utils.variants import VariantRequest, generate_variant

bp = Blueprint("experiments", __name__, url_prefix="/api")


@bp.post("/posts/<int:post_id>/distribute_ab")
def distribute_ab(post_id: int):
    """A/B distribute one post across a group, splitting accounts between
    two variant engines.

    Body::

        {
          "group_id": 12,
          "engine_a": "claude",     // any of: claude, template, none
          "engine_b": "template",
          "scheduled_for": "...",   // optional, defaults to now
          "jitter_minutes": 15,
          "dry_run": false
        }
    """
    post = db.session.get(Post, post_id)
    if not post:
        return jsonify({"error": "post not found"}), 404
    body = request.get_json(force=True) or {}

    group = db.session.get(AccountGroup, body.get("group_id"))
    if not group:
        return jsonify({"error": "group not found"}), 404

    engine_a = body.get("engine_a", "claude")
    engine_b = body.get("engine_b", "none")
    if engine_a == engine_b:
        return jsonify({
            "error": "engine_a and engine_b must differ for a meaningful A/B"
        }), 400
    if engine_a not in {"claude", "template", "none"} or \
       engine_b not in {"claude", "template", "none"}:
        return jsonify({
            "error": "engines must be one of: claude, template, none"
        }), 400

    base = _parse_when(body.get("scheduled_for")) or datetime.now(timezone.utc)
    jitter = max(0, int(body.get("jitter_minutes", 0)))
    dry_run = bool(body.get("dry_run", False))

    active_accounts = [a for a in group.accounts if a.revoked_at is None]
    if len(active_accounts) < 2:
        return jsonify({
            "error": f"group needs ≥2 active accounts to A/B; has {len(active_accounts)}"
        }), 400

    # Deterministic split: alternate by sorted account id so re-running the
    # same A/B on the same group/post produces the same A vs B assignment.
    active_accounts.sort(key=lambda a: a.id)
    seed = f"distribute_ab:{post.id}:{group.id}:{base.isoformat()}"
    starts = spread(base, jitter, seed, len(active_accounts))

    plan = []
    created_ids: list[int] = []
    for idx, (account, when) in enumerate(zip(active_accounts, starts)):
        engine = engine_a if idx % 2 == 0 else engine_b
        variant_label = "A" if idx % 2 == 0 else "B"

        overrides: dict = {
            "variant_label": variant_label,
            "variant_engine": engine,
        }
        if engine != "none":
            req = VariantRequest(
                source_caption=post.caption,
                source_title=post.title,
                platform=account.platform.value,
                style_profile=group.style_profile or {},
                seed=f"{seed}:{variant_label}:{account.id}",
            )
            result = generate_variant(req)
            # Honest about what actually ran — generate_variant might fall
            # back to template even when claude was requested.
            overrides["caption"] = result.caption
            if result.title:
                overrides["title"] = result.title
            overrides["variant_engine"] = result.used_engine

        plan.append({
            "group_id": group.id,
            "account_id": account.id,
            "platform": account.platform.value,
            "handle": account.handle,
            "scheduled_for": when.isoformat(),
            "variant_label": variant_label,
            "variant_engine": overrides["variant_engine"],
            "preview_caption": overrides.get("caption", post.caption)[:200],
        })

        if not dry_run:
            target = PostTarget(
                post_id=post.id,
                account_id=account.id,
                overrides=overrides,
                scheduled_for=when,
                status=JobStatus.PENDING,
            )
            db.session.add(target)
            db.session.flush()
            created_ids.append(target.id)

    if not dry_run:
        audit(
            "post.distribute_ab", "post", post.id,
            actor_user_id=post.user_id,
            detail={
                "group_id": group.id,
                "engine_a": engine_a, "engine_b": engine_b,
                "target_ids": created_ids,
            },
        )
        db.session.commit()
        # Schedule via existing dispatcher pipeline.
        from ..scheduler.tasks import dispatch_target
        for tid in created_ids:
            dispatch_target.apply_async(args=[tid], eta=_target_when(tid))

    return jsonify({
        "post_id": post.id,
        "group_id": group.id,
        "engine_a": engine_a,
        "engine_b": engine_b,
        "dry_run": dry_run,
        "plan": plan,
        "created_target_ids": created_ids,
    })


@bp.get("/experiments/results")
def experiment_results():
    group_id = request.args.get("group_id", type=int)
    if not group_id:
        return jsonify({"error": "group_id required"}), 400
    since_arg = request.args.get("since")
    since = _parse_when(since_arg) if since_arg else None

    comparison = compare_variants(group_id, since=since)
    if comparison is None:
        return jsonify({"error": "group not found"}), 404

    return jsonify({
        "group_id": comparison.group_id,
        "group_name": comparison.group_name,
        "since": comparison.since.isoformat(),
        "winner": comparison.winner,
        "note": comparison.confidence_note,
        "by_engine": [
            {
                "engine": s.engine,
                "samples": s.samples,
                "total_reach": s.total_reach,
                "total_engagement": s.total_engagement,
                "rate": round(s.rate, 4),
            }
            for s in comparison.by_engine
        ],
    })


@bp.post("/experiments/backtest")
def run_backtest():
    """Run the same backtest the weekly beat runs, immediately."""
    results = backtest_and_persist_winners()
    audit("experiments.backtest", "system", None,
          actor_user_id=None,
          detail={"groups_evaluated": len(results),
                  "winners_set": sum(1 for r in results if r.get("updated"))})
    db.session.commit()
    return jsonify({"results": results})


def _parse_when(value):
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None


def _target_when(target_id: int) -> datetime | None:
    target = db.session.get(PostTarget, target_id)
    return target.scheduled_for if target else None
