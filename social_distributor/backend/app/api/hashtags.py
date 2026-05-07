"""Hashtag suggestion endpoint."""
from __future__ import annotations

from flask import Blueprint, jsonify, request

from ..extensions import db
from ..models import AccountGroup
from ..utils.hashtags import HashtagRequest, suggest_hashtags

bp = Blueprint("hashtags", __name__, url_prefix="/api/hashtags")


@bp.post("/suggest")
def suggest():
    """Body::

        {
          "caption": "...",
          "platform": "instagram",
          "group_id": 1,        // optional — pulls style_profile from this group
          "style_profile": {},  // optional — explicit override
          "count": 5
        }
    """
    body = request.get_json(force=True)
    style_profile: dict = body.get("style_profile") or {}
    if not style_profile and (gid := body.get("group_id")):
        group = db.session.get(AccountGroup, int(gid))
        if group is None:
            return jsonify({"error": "group_id not found"}), 404
        style_profile = group.style_profile or {}

    req = HashtagRequest(
        caption=body.get("caption", ""),
        platform=body.get("platform", "instagram"),
        style_profile=style_profile,
        count=min(int(body.get("count", 5)), 30),
    )
    result = suggest_hashtags(req)
    return jsonify({
        "hashtags": result.hashtags,
        "used_engine": result.used_engine,
    })
