"""Flask app factory.

⚠ 整檔替換 social_distributor/backend/app/__init__.py
   基於 main 分支 2026-06-11 拉下的原檔,僅加入兩段(都有「96號」註解):
   1. register_api_key_guard(指令1 X-API-Key 鑑權)
   2. alerts_bp 註冊(指令2 token 監控的讀取端點)
"""
from __future__ import annotations

import hmac
import logging
import os

from flask import Flask, jsonify

from .config import config
from .extensions import cors, db, migrate

log = logging.getLogger(__name__)


def _worker_health_payload():
    from .api.system import read_worker_heartbeat

    return read_worker_heartbeat()


def create_app() -> Flask:
    from .utils.telemetry import init_telemetry
    init_telemetry(component="api")

    app = Flask(__name__)
    app.config.update(config.as_flask())

    # C3: session cookie config — secure flags for prod, but allow plain
    # http on localhost / dev so first-time setup isn't blocked by HTTPS.
    app.config["SESSION_COOKIE_HTTPONLY"] = True
    app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
    app.config["SESSION_COOKIE_SECURE"] = (
        os.environ.get("SESSION_COOKIE_SECURE", "0") == "1"
    )
    app.config["PERMANENT_SESSION_LIFETIME"] = 60 * 60 * 24 * 30  # 30 days

    db.init_app(app)
    migrate.init_app(app, db)

    # Instruction 1: API key guard for all /api/* routes.
    # Set API_KEY in Railway Variables (openssl rand -hex 24).
    # Routes under /auth/* and /healthz* are exempt.
    _api_key = os.environ.get("API_KEY", "").strip()
    if _api_key:
        @app.before_request
        def _api_key_guard():
            from flask import request as _req
            if _req.method == "OPTIONS":
                return
            if not _req.path.startswith("/api/"):
                return
            # A logged-in operator (session cookie or signed bearer token) is
            # a valid identity for the browser dashboard — it must not be
            # forced to also carry the server-side X-API-Key (which would have
            # to be embedded in client JS, defeating the point). X-API-Key
            # stays available for external/programmatic callers.
            from .utils.auth import request_has_operator
            if request_has_operator():
                return
            client = _req.headers.get("X-API-Key", "")
            if not hmac.compare_digest(
                client.encode("utf-8"), _api_key.encode("utf-8")
            ):
                return jsonify({"error": "unauthorized"}), 401

    # CRIT: never reflect `*` with credentials. CORS_ALLOWED_ORIGINS must be an
    # explicit comma-separated allow-list in any shared/prod deploy; when unset
    # we fall back to a safe localhost-only list for first-time dev, NOT `*`.
    # Localhost-only origins are always allowed (they are only reachable from
    # the operator's own machine, so this is not a cross-site risk). This lets
    # local cockpit tools (e.g. the 8777 每日內容工作台) call the API and push
    # to the publisher without needing a Railway CORS_ALLOWED_ORIGINS change.
    _DEFAULT_DEV_ORIGINS = [
        "http://localhost:5173",
        "http://localhost:8080",
        "http://localhost:8777",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:8080",
        "http://127.0.0.1:8777",
        "http://localhost:8803",
        "http://127.0.0.1:8803",
        # First-party production tools (operator-owned origins; auth is still
        # enforced per-request via bearer/session, CORS only unblocks the call).
        # CreatorKit 標題 AB 測試器 pushes drafts into distribute_ab from here.
        "https://creatorkit.milk790.workers.dev",
    ]
    raw_origins = os.environ.get("CORS_ALLOWED_ORIGINS", "").strip()
    if raw_origins == "*":
        # Explicit wildcard is incompatible with credentialed CORS and unsafe;
        # refuse it and fall back to the dev allow-list with a loud warning.
        log.warning(
            "CORS_ALLOWED_ORIGINS='*' is not allowed with credentials; "
            "set an explicit comma-separated origin allow-list. Falling back "
            "to localhost-only origins."
        )
        cors_origins = _DEFAULT_DEV_ORIGINS
    elif raw_origins:
        # Production origins from env PLUS the always-allowed localhost origins.
        cors_origins = [o.strip() for o in raw_origins.split(",") if o.strip()]
        cors_origins += [o for o in _DEFAULT_DEV_ORIGINS if o not in cors_origins]
    else:
        cors_origins = _DEFAULT_DEV_ORIGINS
    cors.init_app(
        app,
        resources={
            r"/api/*": {"origins": cors_origins, "supports_credentials": True},
            r"/auth/*": {"origins": cors_origins, "supports_credentials": True},
            r"/healthz*": {"origins": cors_origins},
        },
    )

    # C3: resolve current user once per request from the authenticated session.
    from .utils.auth import attach_user_id_middleware
    attach_user_id_middleware(app)

    # CRIT: session login guard for all /api/* routes. Identity must come from
    # an authenticated session (set via the magic-link flow). Requests with no
    # logged-in user get 401 — there is no ?user_id= impersonation path anymore.
    # Exemptions: OPTIONS preflight (CORS), and non-/api paths (/auth/*,
    # /healthz*) which handle their own auth.
    @app.before_request
    def _require_login_for_api():
        from flask import request as _req, g as _g
        if _req.method == "OPTIONS":
            return None
        if not (_req.path or "").startswith("/api/"):
            return None
        if getattr(_g, "user_id", None) is None:
            return jsonify({"error": "authentication required"}), 401
        return None

    # 96號 指令1: X-API-Key guard for /api/* (exempts /auth/*, /healthz*,
    # OPTIONS preflight). Reads API_KEY from env; warn-only until it is set.
    from .utils.api_key import register_api_key_guard
    register_api_key_guard(app)

    from .auth import auth_bp
    from .api import (
        accounts_bp,
        audit_bp,
        auto_schedule_bp,
        events_bp,
        experiments_bp,
        groups_bp,
        hashtags_bp,
        insights_bp,
        permissions_bp,
        posts_bp,
        rebroadcast_bp,
        schedules_bp,
        transfers_bp,
        uploads_bp,
    )
    from .api.system import bp as system_bp
    from .api.login import bp as login_bp
    from .api.communities import bp as communities_bp
    from .api.graph_permissions import bp as graph_permissions_bp
    from .api.boost import bp as boost_bp

    # 96號 指令2: read-only alerts endpoint for token monitor results.
    from .api.alerts import bp as alerts_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(login_bp)
    app.register_blueprint(accounts_bp)
    app.register_blueprint(audit_bp)
    app.register_blueprint(auto_schedule_bp)
    app.register_blueprint(events_bp)
    app.register_blueprint(experiments_bp)
    app.register_blueprint(groups_bp)
    app.register_blueprint(hashtags_bp)
    app.register_blueprint(insights_bp)
    app.register_blueprint(permissions_bp)
    app.register_blueprint(posts_bp)
    app.register_blueprint(rebroadcast_bp)
    app.register_blueprint(schedules_bp)
    app.register_blueprint(transfers_bp)
    app.register_blueprint(uploads_bp)
    app.register_blueprint(alerts_bp)
    app.register_blueprint(communities_bp)
    app.register_blueprint(graph_permissions_bp)
    app.register_blueprint(boost_bp)
    app.register_blueprint(system_bp)

    @app.get("/healthz")
    def healthz():
        return jsonify({"status": "ok"})

    @app.get("/healthz/ready")
    def healthz_ready():
        """A7: per-dependency configuration readiness.

        This is intentionally configuration-only — actual liveness probes
        for Redis/S3/Meta would slow down every k8s readiness poll.
        """
        return jsonify(config.readiness())

    @app.get("/healthz/worker")
    def healthz_worker():
        payload, status_code = _worker_health_payload()
        public_fields = {
            key: payload[key]
            for key in ("component", "status", "fresh", "age_seconds", "release")
            if key in payload
        }
        return jsonify(public_fields), status_code

    @app.errorhandler(404)
    def not_found(_):
        return jsonify({"error": "not found"}), 404

    # A7: warn at boot if MEDIA_BUCKET / OAuth credentials not set, instead
    # of letting the user discover it during their first upload click.
    _warn_about_missing_config(app)

    # A9: in dev, auto-seed user_id=1 so the user doesn't have to docker exec
    # to create a User row before the first dashboard load. Skipped if magic
    # link login is enabled (C3) or any users already exist.
    if os.environ.get("AUTO_SEED_USER", "1") == "1":
        _auto_seed_user(app)

    return app


def _warn_about_missing_config(app: Flask) -> None:
    readiness = config.readiness()
    if not readiness["encryption"]["token_key_set"]:
        log.warning("TOKEN_ENCRYPTION_KEY not set — OAuth flows WILL fail")
    if not readiness["media_bucket"]["configured"]:
        log.warning("MEDIA_BUCKET not set — uploads will fail with 500")
    elif not readiness["media_bucket"]["aws_credentials"]:
        log.warning("MEDIA_BUCKET set but AWS credentials missing")
    for name in ("meta", "tiktok", "google"):
        if not readiness["oauth"][name]:
            log.warning("OAuth credentials for %s not configured", name)


def _auto_seed_user(app: Flask) -> None:
    from .models import User
    with app.app_context():
        # Idempotent schema creation — for dev SQLite "just works", for
        # Postgres with existing migrations it's a no-op (CREATE IF NOT
        # EXISTS via SQLAlchemy DDL).
        try:
            db.create_all()
        except Exception as exc:  # noqa: BLE001
            log.debug("auto-seed: create_all skipped (%s)", exc)
            return
        try:
            existing = db.session.query(User).count()
        except Exception as exc:  # noqa: BLE001 - schema still not ready
            log.debug("auto-seed: query failed (%s)", exc)
            return
        if existing == 0:
            seed = User(email="me@local", display_name="Me", timezone="UTC")
            db.session.add(seed)
            db.session.commit()
            log.info("AUTO_SEED_USER: created user_id=%s (me@local)", seed.id)
