"""Bulk-upload videos via /api/uploads/presign + S3 PUT + /api/uploads/complete.

Wraps the three-step upload flow so you don't have to curl by hand for each
file. Prints the resulting media_id per file at the end, in the same order as
the input arguments — ready to paste into ``seed_sprint_v1.MEDIA_MANIFEST``.

Auth: uses ``--user-id`` as a query param (the backend's documented backcompat
path; see ``app/utils/auth.py:94``). For a real session, pass ``--cookie`` and
omit ``--user-id``.

Usage:
    cd social_distributor/backend
    python -m scripts.upload_videos \
        --backend-url https://your-app.up.railway.app \
        --user-id 1 \
        card1.mp4 card2.mp4 card3.mp4 card4.mp4 card5.mp4

    # or with a real session cookie copied from your browser
    python -m scripts.upload_videos \
        --backend-url https://your-app.up.railway.app \
        --cookie "session=abc123..." \
        card1.mp4 ...
"""
from __future__ import annotations

import argparse
import hashlib
import sys
from pathlib import Path
from urllib.parse import urlencode

import requests


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def upload_one(
    session: requests.Session,
    backend_url: str,
    user_id: int | None,
    path: Path,
    content_type: str,
) -> int:
    qs = f"?{urlencode({'user_id': user_id})}" if user_id else ""

    presign = session.post(
        f"{backend_url}/api/uploads/presign{qs}",
        json={"kind": "video", "content_type": content_type, "user_id": user_id},
        timeout=30,
    )
    presign.raise_for_status()
    info = presign.json()

    with path.open("rb") as f:
        put = requests.put(
            info["put_url"],
            data=f,
            headers={"Content-Type": content_type},
            timeout=600,
        )
    put.raise_for_status()

    complete = session.post(
        f"{backend_url}/api/uploads/complete{qs}",
        json={
            "kind": "video",
            "bucket": info["bucket"],
            "key": info["key"],
            "public_get_url": info["public_get_url"],
            "content_type": content_type,
            "sha256": _sha256(path),
            "user_id": user_id,
        },
        timeout=30,
    )
    complete.raise_for_status()
    body = complete.json()
    return int(body["id"])


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--backend-url", required=True, help="e.g. https://app.railway.app")
    parser.add_argument("--user-id", type=int, help="backcompat auth; omit if using --cookie")
    parser.add_argument("--cookie", help="raw Cookie header value, e.g. 'session=abc'")
    parser.add_argument("--content-type", default="video/mp4")
    parser.add_argument("files", nargs="+", help="paths to video files in card order")
    args = parser.parse_args()

    if not args.user_id and not args.cookie:
        print("ERROR: pass --user-id OR --cookie", file=sys.stderr)
        return 2

    paths = [Path(p) for p in args.files]
    for p in paths:
        if not p.is_file():
            print(f"ERROR: not a file: {p}", file=sys.stderr)
            return 2

    session = requests.Session()
    if args.cookie:
        session.headers["Cookie"] = args.cookie

    media_ids: list[tuple[Path, int]] = []
    for idx, path in enumerate(paths, start=1):
        print(f"[{idx}/{len(paths)}] uploading {path.name} ...", flush=True)
        try:
            mid = upload_one(
                session,
                args.backend_url.rstrip("/"),
                args.user_id,
                path,
                args.content_type,
            )
        except requests.HTTPError as e:
            print(f"  FAIL: {e.response.status_code} {e.response.text[:200]}", file=sys.stderr)
            return 3
        media_ids.append((path, mid))
        print(f"  → media_id={mid}")

    print("\n=== MEDIA_MANIFEST paste ===")
    for card_id, (path, mid) in enumerate(media_ids, start=1):
        print(f"    {card_id}: {mid},  # {path.name}")
    print("============================")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
