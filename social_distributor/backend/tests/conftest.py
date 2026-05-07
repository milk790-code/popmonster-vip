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
