"""Flask app factory."""
from __future__ import annotations

import hmac
import logging
import os

from flask import Flask, jsonify

from .config import config
from .extensions import cors, db, migrate

log = logging.getLogger(__name__)


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
            if not _req.path.startswith("/api/"):
                return
            client = _req.headers.get("X-API-Key", "")
            if not hmac.compare_digest(
                client.encode("utf-8"), _api_key.encode("utf-8")
            ):
                return jsonify({"error": "unauthorized"}), 401

    raw_origins = os.environ.get("CORS_ALLOWED_ORIGINS", "*").strip()
    cors_origins = (
        "*" if raw_origins in ("", "*")
        else [o.strip() for o in raw_origins.split(",") if o.strip()]
    )
    cors.init_app(
        app,
        resources={
            r"/api/*": {"origins": cors_origins, "supports_credentials": True},
            r"/auth/*": {"origins": cors_origins, "supports_credentials": True},
            r"/healthz*": {"origins": cors_origins},
        },
    )

    # C3: resolve current user once per request, surface deprecation header
    # for any caller still using ?user_id= backcompat.
    from .utils.auth import attach_user_id_middleware
    attach_user_id_middleware(app)

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
    from .api.login import bp as login_bp

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
