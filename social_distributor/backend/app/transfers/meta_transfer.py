"""Meta BM-to-BM Page transfer requests.

Honest scope: Meta provides API endpoints for **requesting and tracking**
page transfer between two Business Managers. It does not provide a one-shot
"transfer this page" endpoint — both BMs' admins must approve in their own
BM web UIs, the same as if the request had been made manually. The value
this module adds is keeping a structured record of the request and polling
its status without anyone refreshing the BM web tab.

Endpoints (v20):
- POST /{from_business_id}/owned_pages?asset=<page_id>&type=PAGE
       → initiates the transfer request
- GET  /{to_business_id}/pending_owned_pages
       → list incoming requests (target BM admin sees these)
- GET  /{from_business_id}/owned_pages?fields=id,access_status
       → confirm post-transfer state
"""
from __future__ import annotations

from ..platforms._http import request_json
from ..platforms.facebook import GRAPH_BASE


def initiate_page_transfer(from_business_id: str, to_business_id: str,
                           page_id: str, access_token: str) -> dict:
    """``access_token`` must be a BM admin token for the source BM."""
    return request_json(
        "POST",
        f"{GRAPH_BASE}/{from_business_id}/owned_pages",
        data={
            "asset": page_id,
            "type": "PAGE",
            "child_business": to_business_id,
            "access_token": access_token,
        },
    )


def list_incoming_pending(business_id: str, access_token: str) -> list[dict]:
    payload = request_json(
        "GET",
        f"{GRAPH_BASE}/{business_id}/pending_owned_pages",
        params={"access_token": access_token, "fields": "id,name,access_status"},
    )
    return payload.get("data", [])


def is_page_owned_by(business_id: str, page_id: str, access_token: str) -> bool:
    """True if ``page_id`` currently shows up under ``business_id``'s owned pages."""
    payload = request_json(
        "GET",
        f"{GRAPH_BASE}/{business_id}/owned_pages",
        params={"access_token": access_token, "fields": "id"},
    )
    return any(p.get("id") == page_id for p in payload.get("data", []))
