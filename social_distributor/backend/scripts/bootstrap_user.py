"""Idempotently create the initial User row.

Run once after `flask db upgrade` (or `db.create_all()`) on a fresh backend
deploy. If a user with the given email already exists, prints that user's id
and exits 0 without modifying anything.

Usage:
    cd social_distributor/backend
    python -m scripts.bootstrap_user \
        --email milk790@example.com \
        --display-name "陳學誼" \
        --timezone Asia/Taipei
"""
from __future__ import annotations

import argparse
import sys

from app import create_app
from app.extensions import db
from app.models import User


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--email", required=True)
    parser.add_argument("--display-name", required=True)
    parser.add_argument("--timezone", default="UTC")
    args = parser.parse_args()

    app = create_app()
    with app.app_context():
        existing = User.query.filter_by(email=args.email).one_or_none()
        if existing:
            print(f"user_id={existing.id} (already exists)")
            return 0

        user = User(
            email=args.email,
            display_name=args.display_name,
            timezone=args.timezone,
        )
        db.session.add(user)
        db.session.commit()
        print(f"user_id={user.id} (created)")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
