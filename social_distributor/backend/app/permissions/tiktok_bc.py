"""TikTok Business Center — assign / revoke ad-account access to members.

Honest scope note: TikTok Business Center API exposes membership for **ad
accounts and pixels owned by a Business Center**. It does NOT expose:
- Personal TikTok creator account ownership transfer
- Cross-organisation account migration

So this module is genuinely useful for advertiser teams; for creator-side
content asset transfer, refer the user to the manual runbook.

Endpoints (v1.3):
- POST /open_api/v1.3/bc/member/get/                  list members of a BC
- POST /open_api/v1.3/bc/asset/assign/                assign an asset to a member
- POST /open_api/v1.3/bc/asset/unassign/              revoke
- POST /open_api/v1.3/bc/asset/get/                   list assets owned by BC
"""
from __future__ import annotations

from typing import Iterable

from ..platforms._http import request_json

BC_BASE = "https://business-api.tiktok.com/open_api/v1.3"

# Wire roles per TikTok docs — keep verbatim.
ASSET_ROLES = {"ADMIN", "OPERATOR", "ANALYST"}


def _headers(access_token: str) -> dict:
    return {
        "Access-Token": access_token,
        "Content-Type": "application/json",
    }


def list_assets(bc_id: str, asset_type: str, access_token: str) -> list[dict]:
    """``asset_type`` is one of ``ADVERTISER``, ``PIXEL``, ``CATALOG``, etc."""
    payload = request_json(
        "GET",
        f"{BC_BASE}/bc/asset/get/",
        headers=_headers(access_token),
        params={"bc_id": bc_id, "asset_type": asset_type},
    )
    return payload.get("data", {}).get("list", [])


def list_members(bc_id: str, access_token: str) -> list[dict]:
    payload = request_json(
        "GET",
        f"{BC_BASE}/bc/member/get/",
        headers=_headers(access_token),
        params={"bc_id": bc_id},
    )
    return payload.get("data", {}).get("list", [])


def assign_asset(bc_id: str, member_id: str, asset_id: str, asset_type: str,
                 role: str, access_token: str) -> dict:
    if role not in ASSET_ROLES:
        raise ValueError(f"unsupported tiktok bc role: {role}")
    return request_json(
        "POST",
        f"{BC_BASE}/bc/asset/assign/",
        headers=_headers(access_token),
        json={
            "bc_id": bc_id,
            "member_id": member_id,
            "assets": [{"asset_id": asset_id, "asset_type": asset_type}],
            "permission": role,
        },
    )


def unassign_asset(bc_id: str, member_id: str, asset_id: str, asset_type: str,
                   access_token: str) -> dict:
    return request_json(
        "POST",
        f"{BC_BASE}/bc/asset/unassign/",
        headers=_headers(access_token),
        json={
            "bc_id": bc_id,
            "member_id": member_id,
            "assets": [{"asset_id": asset_id, "asset_type": asset_type}],
        },
    )


def assign_assets_bulk(bc_id: str, member_id: str,
                       assets: Iterable[tuple[str, str]],
                       role: str, access_token: str) -> dict:
    """Bulk variant: ``assets`` is iterable of ``(asset_id, asset_type)``."""
    if role not in ASSET_ROLES:
        raise ValueError(f"unsupported tiktok bc role: {role}")
    return request_json(
        "POST",
        f"{BC_BASE}/bc/asset/assign/",
        headers=_headers(access_token),
        json={
            "bc_id": bc_id,
            "member_id": member_id,
            "assets": [{"asset_id": aid, "asset_type": atype} for aid, atype in assets],
            "permission": role,
        },
    )
