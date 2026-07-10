# PR: Repair OAuth connect start flow

## Background

The dashboard connect buttons depend on authenticated OAuth start endpoints. The previous flow could still fall back to `authentication required` or the wrong start shape when the browser tried to open provider auth URLs.

This PR fixes the `/auth/{platform}/start` and `/auth/{platform}/start-url` contract so authenticated operators can start OAuth without passing `user_id` in the query string.

## Scope

- Require authenticated identity from session or signed operator bearer token.
- Ignore caller-supplied `?user_id=` and sign OAuth state with the authenticated user id.
- Return browser-safe OAuth URL payloads:
  - `/auth/{provider}/start` returns `authorization_url` and `state`.
  - `/auth/{provider}/start-url` returns `redirect_url` and `state`.
- Keep revoke and TikTok cookie flows scoped to the authenticated operator.
- Update frontend connect flow to request `start-url` and send users to the returned redirect URL.
- Add focused IDOR/session tests for OAuth start, start-url, revoke, and TikTok cookie flows.

## Files Changed

- `social_distributor/backend/app/auth/routes.py`
- `social_distributor/backend/tests/test_auth_routes_idor.py`
- `social_distributor/frontend/js/app.js`

## Test Results

Focused test command:

```bash
cd social_distributor/backend
python -m pytest tests/test_auth_routes_idor.py
```

Verified locally with Python 3.12.13 in a temporary venv:

- `tests/test_auth_routes_idor.py`: 11 passed

Note: the current local `social_distributor/backend/.venv` is Python 3.9.6 and cannot collect this repo because SQLAlchemy evaluates `datetime | None` annotations. Use Python 3.12, matching `Dockerfile.backend`.

Expected post-deploy smoke:

```bash
cd social_distributor/backend
API_BASE_URL="https://<api-domain>" \
SD_OPERATOR_TOKEN="$SD_OPERATOR_TOKEN" \
python scripts/smoke_test.py
```

## Risks

- OAuth provider credentials must be present in the deployed environment; otherwise `/auth/{platform}/start` can still fail with provider configuration errors.
- Existing frontend clients that still call `/auth/{provider}/start?user_id=...` should keep working only when they also send a valid session or bearer token.
- This branch is currently local only and has not been pushed or opened as a PR.

## Rollback

- Revert commit `740f2b1` or redeploy the previous Railway deployment for the `api` and `frontend` services.
- No DB migration is included in this OAuth-only change, so rollback does not require schema changes.

## Branch Note

Prepared local branch:

```bash
codex/oauth-start-flow-fix-20260708
```
