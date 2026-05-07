"""Meta System User token management.

System Users are non-human BM members issued long-lived tokens. They're the
correct way to give a backend service durable access without repeatedly
prompting a real human to re-OAuth.

Endpoints (v20):
- POST /{business-id}/system_users                     create a system user
- POST /{system-user-id}/access_tokens                 issue a fresh token
- GET  /me?access_token=<token>                        verify token still valid

We rotate tokens before they expire (Meta system user tokens by default are
"never expire" but apps in development mode get short-lived; we treat every
token as expiring after ``rotation_days`` days for safety regardless).
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from ..platforms._http import request_json
from ..platforms.facebook import GRAPH_BASE


def create_system_user(business_id: str, name: str, role: str,
                       access_token: str) -> dict:
    """``role`` is ``ADMIN`` or ``EMPLOYEE``."""
    if role not in {"ADMIN", "EMPLOYEE"}:
        raise ValueError(f"unsupported system user role: {role}")
    return request_json(
        "POST",
        f"{GRAPH_BASE}/{business_id}/system_users",
        data={"name": name, "role": role, "access_token": access_token},
    )


def issue_token(system_user_id: str, app_id: str, scope: list[str],
                admin_access_token: str) -> dict:
    return request_json(
        "POST",
        f"{GRAPH_BASE}/{system_user_id}/access_tokens",
        data={
            "appsecret_proof": "",  # caller adds if needed for app secret proof
            "business_app": app_id,
            "scope": ",".join(scope),
            "access_token": admin_access_token,
        },
    )


def verify_token(token: str) -> bool:
    """Returns True if ``/me`` succeeds with this token."""
    try:
        request_json("GET", f"{GRAPH_BASE}/me", params={"access_token": token})
        return True
    except Exception:
        return False


def needs_rotation(token_issued_at: datetime, rotation_days: int = 90) -> bool:
    if token_issued_at.tzinfo is None:
        token_issued_at = token_issued_at.replace(tzinfo=timezone.utc)
    return datetime.now(timezone.utc) - token_issued_at >= timedelta(days=rotation_days)
