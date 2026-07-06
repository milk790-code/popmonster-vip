import os

# Tests run against an in-memory SQLite DB and an inert encryption key.
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault(
    "TOKEN_ENCRYPTION_KEY", "X4sbE7kSvVgI7iNk7AY8K6jL5hQjYpY8LHEqRSfqhjU="
)
os.environ.setdefault("SECRET_KEY", "test-secret-key")

import pytest

from app import create_app
from app.extensions import db


@pytest.fixture()
def app():
    app = create_app()
    with app.app_context():
        db.create_all()
        yield app
        db.session.rollback()
        db.drop_all()


@pytest.fixture()
def client(app):
    return app.test_client()


@pytest.fixture(autouse=True)
def _reset_login_rate_limit():
    """The login-password rate limiter (added 2026-07-07) is a process-local
    module-level dict, so without this it leaks state across tests that share
    the test client's IP and starts failing tests order-dependently."""
    from app.api import login as login_module
    login_module._login_attempts.clear()
    yield
    login_module._login_attempts.clear()


def login_as(client, user_id: int) -> None:
    """Authenticate the test client as ``user_id`` via the real session flow.

    Identity now comes only from the session (the ``?user_id=`` backcompat
    impersonation path was removed for security), so endpoint tests must log in
    instead of passing ``user_id`` in the request. This mirrors what the
    magic-link verify endpoint does: set ``session['user_id']``.
    """
    with client.session_transaction() as sess:
        sess["user_id"] = user_id
