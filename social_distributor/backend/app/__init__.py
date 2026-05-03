"""Flask app factory."""
from __future__ import annotations

from flask import Flask, jsonify

from .config import config
from .extensions import cors, db, migrate


def create_app() -> Flask:
    app = Flask(__name__)
    app.config.update(config.as_flask())

    db.init_app(app)
    migrate.init_app(app, db)
    cors.init_app(app, resources={r"/api/*": {"origins": "*"}})

    from .auth import auth_bp
    from .api import (
        accounts_bp,
        audit_bp,
        events_bp,
        groups_bp,
        insights_bp,
        posts_bp,
        schedules_bp,
        uploads_bp,
    )

    app.register_blueprint(auth_bp)
    app.register_blueprint(accounts_bp)
    app.register_blueprint(audit_bp)
    app.register_blueprint(events_bp)
    app.register_blueprint(groups_bp)
    app.register_blueprint(insights_bp)
    app.register_blueprint(posts_bp)
    app.register_blueprint(schedules_bp)
    app.register_blueprint(uploads_bp)

    @app.get("/healthz")
    def healthz():
        return jsonify({"status": "ok"})

    @app.errorhandler(404)
    def not_found(_):
        return jsonify({"error": "not found"}), 404

    return app
