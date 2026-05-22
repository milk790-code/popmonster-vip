"""Ephemeral preflight for seed_sprint_v1.py.

Builds a throwaway SQLite DB with fixtures (User + AccountGroup「PopMonster 主推」
+ 3 active SocialAccounts FB/IG/TT + 5 MediaAsset rows), patches MEDIA_MANIFEST,
and runs ``seed_sprint_v1.main(dry_run=True)``. Verifies the 5 cards each fan
out to 3 platforms with the correct schedule. Does not touch any real DB.

Usage:
    cd social_distributor/backend
    python -m scripts.preflight_seed_sprint
"""
from __future__ import annotations

import os
import tempfile


def _bootstrap_env() -> str:
    fd, path = tempfile.mkstemp(suffix=".sqlite")
    os.close(fd)
    os.environ["DATABASE_URL"] = f"sqlite:///{path}"
    os.environ.setdefault("TOKEN_ENCRYPTION_KEY", "preflight-only-not-used")
    os.environ.setdefault("SECRET_KEY", "preflight")
    return path


def main() -> int:
    db_path = _bootstrap_env()

    from app import create_app
    from app.extensions import db
    from app.models import AccountGroup, MediaAsset, Platform, SocialAccount, User
    from scripts import seed_sprint_v1

    app = create_app()
    with app.app_context():
        db.create_all()

        user = User(
            email="preflight@example.com",
            display_name="Preflight",
            timezone="Asia/Taipei",
        )
        db.session.add(user)
        db.session.commit()

        accounts = []
        for platform, handle in [
            (Platform.FACEBOOK, "popmonster.fb"),
            (Platform.INSTAGRAM, "popmonster.ig"),
            (Platform.TIKTOK, "popmonster.tt"),
        ]:
            account = SocialAccount(
                user_id=user.id,
                platform=platform,
                external_account_id=f"ext-{platform.value}",
                handle=handle,
                access_token_enc=b"stub",
            )
            db.session.add(account)
            accounts.append(account)
        db.session.commit()

        group = AccountGroup(
            user_id=user.id,
            name=seed_sprint_v1.GROUP_NAME,
            description="preflight",
            default_timezone=seed_sprint_v1.TZ,
        )
        group.accounts = accounts
        db.session.add(group)
        db.session.commit()

        media_ids: dict[int, int | None] = {}
        for card_id in (1, 2, 3, 4, 5):
            asset = MediaAsset(
                user_id=user.id,
                kind="video",
                storage_url=f"s3://stub/card{card_id}.mp4",
                mime_type="video/mp4",
                width=1080,
                height=1920,
                duration_seconds=30.0,
                compliance_status="approved",
                transcode_status="ready",
            )
            db.session.add(asset)
            db.session.flush()
            media_ids[card_id] = asset.id
        db.session.commit()

        print(
            f"Fixtures: user={user.id} group={group.id} "
            f"accounts={[a.id for a in accounts]} media={media_ids}"
        )

    seed_sprint_v1.MEDIA_MANIFEST = media_ids
    try:
        rc = seed_sprint_v1.main(dry_run=True)
    finally:
        try:
            os.unlink(db_path)
        except OSError:
            pass
    print(f"\nexit_code={rc}")
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
