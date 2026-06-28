"""X-API-Key guard for /api/* — 96號 指令1(地基:堵 API 裸奔).

目標檔案位置:social_distributor/backend/app/utils/api_key.py(新檔)

行為:
- 讀環境變數 ``API_KEY``。已設定時,所有 ``/api/*`` 請求必須帶
  ``X-API-Key`` header(或 ``?api_key=`` query 參數 — 給 EventSource/SSE 用,
  因為瀏覽器的 EventSource 無法自訂 header),用 ``hmac.compare_digest``
  比對,不符回 401。
- 放行:``/auth/*``、``/healthz*``(本 repo 健康端點叫 /healthz,不是
  /health)、以及 OPTIONS(CORS preflight 不帶自訂 header)。
- ``API_KEY`` 未設定時:log.critical 警告但放行(warn-only),避免
  「程式碼先上、變數還沒設」的部署順序把 dashboard 鎖死。
  部署後第一件事就是去 Railway Variables 設 API_KEY。

金鑰生成(學誼本機跑,值不入對話、不入 commit):
    openssl rand -hex 24
存進 Railway 的 api 服務 Variables(worker 服務不收外部 HTTP,可不設)。
"""
from __future__ import annotations

import hmac
import logging
import os

from flask import jsonify, request

log = logging.getLogger(__name__)

# /auth/*(OAuth 回調、magic link)與 /healthz*(Railway healthcheck)放行。
# 這兩類本來就不在 /api/ 前綴下,列在這裡是雙保險。
_EXEMPT_PREFIXES = ("/auth/", "/healthz")


def register_api_key_guard(app) -> None:
    api_key = os.environ.get("API_KEY", "")
    if not api_key:
        log.critical(
            "API_KEY not set — /api/* is UNPROTECTED (warn-only mode). "
            "Generate with `openssl rand -hex 24` and set it in Railway "
            "Variables on the `api` service, then redeploy."
        )

    @app.before_request
    def _check_api_key():
        if not api_key:
            return None  # warn-only mode until the variable is set
        if request.method == "OPTIONS":
            return None  # CORS preflight cannot carry custom headers
        path = request.path or ""
        if path.startswith(_EXEMPT_PREFIXES):
            return None
        if not path.startswith("/api/"):
            return None
        # A logged-in operator (session or signed bearer token) bypasses the
        # X-API-Key wall — the browser dashboard authenticates via password
        # login, not the server-side API key. X-API-Key remains for external
        # programmatic callers.
        from .auth import request_has_operator
        if request_has_operator():
            return None
        supplied = (
            request.headers.get("X-API-Key")
            or request.args.get("api_key")
            or ""
        )
        if hmac.compare_digest(supplied.encode("utf-8"), api_key.encode("utf-8")):
            return None
        return jsonify({"error": "invalid or missing API key"}), 401
