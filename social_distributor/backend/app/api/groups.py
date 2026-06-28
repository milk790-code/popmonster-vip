"""Account groups (personas) — bundle one FB + IG + YT + TikTok per identity.

Schema:
- A user can own many groups (`name` is unique per user).
- A SocialAccount can belong to multiple groups (e.g. a portfolio account that
  also acts as the cross-promo channel for several niches).
- ``style_profile`` is free-form JSON consumed by the variant engine; we
  preserve it verbatim so users can iterate on the prompt without code change.
"""
from __future__ import annotations

from flask import Blueprint, jsonify, request

from ..extensions import db
from ..models import AccountGroup, PostTarget, SocialAccount, User
from ..utils.audit import record as audit
from ..utils.auth import current_user_id

bp = Blueprint("groups", __name__, url_prefix="/api/groups")


def _load_owned_group(group_id: int):
    """Return (group, None) if the group belongs to the logged-in user, else error."""
    group = db.session.get(AccountGroup, group_id)
    if not group:
        return None, (jsonify({"error": "not found"}), 404)
    if group.user_id != current_user_id():
        return None, (jsonify({"error": "forbidden"}), 403)
    return group, None


def _serialize(group: AccountGroup) -> dict:
    return {
        "id": group.id,
        "user_id": group.user_id,
        "name": group.name,
        "description": group.description,
        "style_profile": group.style_profile,
        "is_active": group.is_active,
        "default_timezone": group.default_timezone,
        "created_at": group.created_at.isoformat() if group.created_at else None,
        "updated_at": group.updated_at.isoformat() if group.updated_at else None,
        "members": [
            {
                "account_id": a.id,
                "platform": a.platform.value,
                "handle": a.handle,
                "revoked": a.revoked_at is not None,
            }
            for a in group.accounts
        ],
    }


@bp.get("")
def list_groups():
    # Always scope to the logged-in user.
    query = db.session.query(AccountGroup).filter_by(user_id=current_user_id())
    rows = query.order_by(AccountGroup.created_at.desc()).all()
    return jsonify([_serialize(g) for g in rows])


@bp.post("")
def create_group():
    body = request.get_json(force=True)
    user_id = current_user_id()
    if not db.session.get(User, user_id):
        return jsonify({"error": "unknown user"}), 400

    existing = (
        db.session.query(AccountGroup)
        .filter_by(user_id=user_id, name=body["name"])
        .one_or_none()
    )
    if existing:
        return jsonify({"error": "group name already exists for this user"}), 409

    group = AccountGroup(
        user_id=user_id,
        name=body["name"],
        description=body.get("description", ""),
        style_profile=body.get("style_profile", {}),
        default_timezone=body.get("default_timezone", "UTC"),
    )
    db.session.add(group)
    db.session.flush()

    # Optional: bind member account_ids on creation.
    for account_id in body.get("account_ids", []):
        _attach_account(group, int(account_id))

    audit("group.created", "account_group", group.id, actor_user_id=user_id,
          detail={"name": group.name, "members": len(group.accounts)})
    db.session.commit()
    return jsonify(_serialize(group)), 201


@bp.get("/<int:group_id>")
def get_group(group_id: int):
    group, err = _load_owned_group(group_id)
    if err:
        return err
    return jsonify(_serialize(group))


@bp.put("/<int:group_id>")
def update_group(group_id: int):
    group, err = _load_owned_group(group_id)
    if err:
        return err
    body = request.get_json(force=True)
    for field in ("name", "description", "default_timezone"):
        if field in body:
            setattr(group, field, body[field])
    if "style_profile" in body:
        group.style_profile = body["style_profile"]
    if "is_active" in body:
        group.is_active = bool(body["is_active"])
    audit("group.updated", "account_group", group.id, actor_user_id=group.user_id,
          detail={"fields": list(body.keys())})
    db.session.commit()
    return jsonify(_serialize(group))


@bp.delete("/<int:group_id>")
def delete_group(group_id: int):
    group, err = _load_owned_group(group_id)
    if err:
        return err
    user_id = group.user_id
    # Unlink historical post targets first. PostTarget.group_id is a nullable
    # FK with no ON DELETE rule, so deleting a group that was ever used for
    # dispatch would raise a foreign-key violation (500). Null the reference
    # to preserve post history (account/post stay intact) and allow deletion.
    db.session.query(PostTarget).filter_by(group_id=group_id).update(
        {"group_id": None}, synchronize_session=False
    )
    db.session.delete(group)
    audit("group.deleted", "account_group", group_id, actor_user_id=user_id)
    db.session.commit()
    return jsonify({"deleted": group_id})


@bp.post("/<int:group_id>/members")
def add_member(group_id: int):
    group, err = _load_owned_group(group_id)
    if err:
        return err
    body = request.get_json(force=True)
    account_id = int(body["account_id"])
    err = _attach_account(group, account_id)
    if err:
        return jsonify({"error": err}), 400
    audit("group.member_added", "account_group", group.id,
          actor_user_id=group.user_id, detail={"account_id": account_id})
    db.session.commit()
    return jsonify(_serialize(group))


@bp.delete("/<int:group_id>/members/<int:account_id>")
def remove_member(group_id: int, account_id: int):
    group, err = _load_owned_group(group_id)
    if err:
        return err
    account = db.session.get(SocialAccount, account_id)
    if account and account in group.accounts:
        group.accounts.remove(account)
    audit("group.member_removed", "account_group", group.id,
          actor_user_id=group.user_id, detail={"account_id": account_id})
    db.session.commit()
    return jsonify(_serialize(group))


def _attach_account(group: AccountGroup, account_id: int) -> str | None:
    account = db.session.get(SocialAccount, account_id)
    if not account:
        return f"account {account_id} not found"
    if account.user_id != group.user_id:
        return "account belongs to a different user"
    if account in group.accounts:
        return None
    group.accounts.append(account)
    return None
