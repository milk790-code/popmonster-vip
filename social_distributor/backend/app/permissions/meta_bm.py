"""Meta Business Manager — list assets, grant / revoke / list user permissions.

Real Graph API endpoints used (v20):
- ``GET  /{business-id}/owned_pages``                  list FB Pages owned by BM
- ``GET  /{business-id}/owned_instagram_accounts``     list IG Business accounts
- ``GET  /{page-id}/assigned_users``                   who has access + which role
- ``POST /{page-id}/assigned_users``                   grant role
- ``DELETE /{page-id}/assigned_users``                 revoke
- ``POST /{business-id}/agencies``                     authorize an agency BM
- ``DELETE /{business-id}/agencies``                   revoke agency

Roles map to Meta's wire values; we keep them verbatim so audit/log can be
diff'd against the BM web UI without translation surprises.
"""
from __future__ import annotations

from dataclasses import dataclass

from ..platforms._http import request_json
from ..platforms.facebook import GRAPH_BASE

# Wire-level role names; do not localise these — Meta accepts these exactly.
PAGE_ROLES = {"ADMIN", "EDITOR", "MODERATOR", "ADVERTISER", "ANALYST"}
IG_ROLES = {"ADMIN", "EDITOR", "MODERATOR", "ADVERTISER", "ANALYST"}


@dataclass
class AssignedUser:
    user_id: str
    role: str
    name: str | None = None


def list_owned_pages(business_id: str, access_token: str) -> list[dict]:
    payload = request_json(
        "GET",
        f"{GRAPH_BASE}/{business_id}/owned_pages",
        params={"access_token": access_token, "fields": "id,name,access_token"},
    )
    return payload.get("data", [])


def list_owned_instagram_accounts(business_id: str, access_token: str) -> list[dict]:
    payload = request_json(
        "GET",
        f"{GRAPH_BASE}/{business_id}/owned_instagram_accounts",
        params={"access_token": access_token, "fields": "id,username"},
    )
    return payload.get("data", [])


def list_assigned_users(asset_id: str, access_token: str) -> list[AssignedUser]:
    payload = request_json(
        "GET",
        f"{GRAPH_BASE}/{asset_id}/assigned_users",
        params={"access_token": access_token, "fields": "id,name,role,tasks"},
    )
    out: list[AssignedUser] = []
    for entry in payload.get("data", []):
        role = entry.get("role")
        if not role:
            tasks = entry.get("tasks") or []
            role = ",".join(tasks) if tasks else "UNKNOWN"
        out.append(AssignedUser(user_id=entry["id"], role=role, name=entry.get("name")))
    return out


def grant_role(asset_id: str, user_id: str, role: str, access_token: str) -> dict:
    """Grant ``user_id`` ``role`` on ``asset_id`` (page or IG account)."""
    if role not in PAGE_ROLES:
        raise ValueError(f"unsupported role: {role}")
    return request_json(
        "POST",
        f"{GRAPH_BASE}/{asset_id}/assigned_users",
        data={"user": user_id, "tasks": role, "access_token": access_token},
    )


def revoke_role(asset_id: str, user_id: str, access_token: str) -> dict:
    return request_json(
        "DELETE",
        f"{GRAPH_BASE}/{asset_id}/assigned_users",
        params={"user": user_id, "access_token": access_token},
    )


def authorize_agency(business_id: str, agency_id: str, permitted_tasks: list[str],
                     access_token: str) -> dict:
    """Allow another BM (``agency_id``) to act on ``business_id`` assets."""
    return request_json(
        "POST",
        f"{GRAPH_BASE}/{business_id}/agencies",
        data={
            "child_business_id": agency_id,
            "permitted_tasks": ",".join(permitted_tasks),
            "access_token": access_token,
        },
    )


def revoke_agency(business_id: str, agency_id: str, access_token: str) -> dict:
    return request_json(
        "DELETE",
        f"{GRAPH_BASE}/{business_id}/agencies",
        params={"child_business_id": agency_id, "access_token": access_token},
    )
