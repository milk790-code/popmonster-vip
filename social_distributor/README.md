# Social Distributor

Cross-platform content distribution system for Facebook, Instagram, TikTok, and
YouTube. Designed for compliance-first publishing using the **official
platform APIs** — no scraping, no headless-browser automation, no
detection-evasion techniques. Failures bubble up as platform errors and we
back off according to each provider's documented rate limits.

## Layout

```
social_distributor/
├── backend/                # Flask + Celery + SQLAlchemy
│   ├── app/
│   │   ├── auth/           # OAuth2 connect flows
│   │   ├── platforms/      # Adapters per platform (Graph, TikTok, YouTube)
│   │   ├── compliance/     # Text/video moderation + per-platform rules
│   │   ├── scheduler/      # Celery tasks (dispatch, cron, sweep)
│   │   ├── api/            # REST endpoints
│   │   └── utils/          # Crypto, audit logging, retry/backoff
│   ├── tests/
│   ├── requirements.txt
│   └── .env.example
├── frontend/               # Vanilla HTML/JS dashboard
├── Dockerfile.backend
└── docker-compose.yml
```

## Quick start (Docker)

```bash
cp backend/.env.example backend/.env
# fill in OAuth client IDs/secrets and a Fernet TOKEN_ENCRYPTION_KEY:
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

docker compose up --build
# API:        http://localhost:5000
# Dashboard:  http://localhost:8080
```

## Quick start (local Python)

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env  # edit
flask --app run.py db upgrade  # if migrations are present
flask --app run.py run
# in another shell:
celery -A celery_worker.celery worker -B -l info
```

## Configuring platforms

Each platform requires its own developer-portal app. The OAuth callback URLs
must match what's stored in the corresponding `*_REDIRECT_URI` env var.

| Platform | Console | Required scopes |
|---|---|---|
| Facebook + Instagram | [developers.facebook.com](https://developers.facebook.com) | `pages_manage_posts`, `instagram_content_publish` (see `platforms/facebook.py`) |
| TikTok | [developers.tiktok.com](https://developers.tiktok.com) | `video.publish`, `video.upload` |
| YouTube | [console.cloud.google.com](https://console.cloud.google.com) | `youtube.upload`, `youtube.readonly` |

After configuration, click **Connect …** in the dashboard. The callback writes
encrypted tokens (Fernet, AES-128-CBC + HMAC-SHA256) to the database — they
are never logged.

## Insights, best-time learning, SSE, WYSIWYG (Phase 3)

* `ingest_insights` Celery beat task (every hour, minute 15) pulls engagement
  metrics for every successful target published in the last 30 days. Per
  platform:
  - **Facebook**: `/<post_id>/insights` — impressions, unique reach, reactions
  - **Instagram**: `/<media_id>/insights` — reach, impressions, likes, comments,
    shares, saves, plays
  - **TikTok**: `/v2/video/query/` — view/like/comment/share counts (full
    retention requires Research API approval)
  - **YouTube**: `videos.list` for counts + `youtubeAnalytics.reports.query`
    for `averageViewPercentage` and `estimatedMinutesWatched`
* Snapshots persist as `PostMetric` rows so trends are queryable. The latest
  snapshot per target is exposed via `GET /api/insights?post_id=` or
  `?group_id=`.
* `GET /api/insights/best-times?account_id=` (or `?group_id=`) buckets
  successful posts by hour-of-week, computes engagement rate
  `(likes+comments+shares)/reach`, and returns the top slots once a bucket
  has at least 3 samples. Used to suggest the next best send time.
* `GET /api/events/stream?user_id=` is a Server-Sent Events stream; the
  dispatcher publishes `target.status_changed` events to Redis pub/sub on
  every success/failure, and the dashboard refreshes the status board
  in-place (no manual refresh). Without Redis the endpoint emits a single
  `noop` frame so the client can fall back to polling.
* The Compose tab now renders a **WYSIWYG per-platform preview card** for FB,
  IG, TikTok, YouTube — character counts go red when over the platform limit
  so you see truncation before publish.
* Production note for SSE: gunicorn's default sync worker pins one request per
  worker for the lifetime of the stream. Use `--worker-class gevent` or
  `uvicorn` so the SSE endpoint doesn't starve your pool.

## Account groups / personas (Phase 2)

The "matrix" workflow you actually want isn't `1 post → 4 platforms`; it's
`1 post → N personas, each with FB+IG+TikTok+YouTube, each in its own voice`.

* **Group** = one persona. Owns a name, description, `style_profile` (free
  JSON), and a list of `SocialAccount` members. Same account may belong to
  multiple groups.
* `POST /api/groups` to create, `PUT` to edit (including `style_profile`
  iteratively), `DELETE` to remove. `POST /api/groups/<id>/members` /
  `DELETE /api/groups/<id>/members/<account_id>` for membership.
* `style_profile` example::

      {
        "tone": "casual",
        "voice": "親切的鄰家姊姊，喜歡用比喻",
        "emoji_density": "medium",
        "hashtag_pool": ["#日常", "#推薦", "#療癒"],
        "audience": "20-30 歲都會女性",
        "do_not_say": ["保證", "100% 有效"]
      }

* `POST /api/posts/<id>/distribute` fans a post out to one or more groups,
  with three switches:
  - `jitter_minutes` — spread the start times deterministically across a
    window so N accounts don't all post at the same second (looks like a bot
    swarm to platform integrity systems).
  - `generate_variants` — call the variant engine to rewrite the caption per
    persona / per platform, so the matrix isn't N copies of identical text.
  - `dry_run` — return the plan without persisting.

### Variant engine

`utils.variants.generate_variant` rewrites a source caption in the persona's
voice for a target platform. Two backends:

1. **Claude** when `ANTHROPIC_API_KEY` is set (default model
   `claude-haiku-4-5-20251001`). The persona's `style_profile` is sent as a
   cached system block so multi-account fanouts pay the input tokens once
   and reuse the cache across the rest of the calls.
2. **Template** fallback when no key — deterministic, swaps emoji density
   and hashtag pool. Ships a different but coherent caption per account
   without an external dependency.

### Rate limit guard

`utils.rate_limit.check_and_consume` runs before every dispatch. Defaults
follow each platform's documented limits (TikTok 30/day, YouTube 6/day, IG
50/24h, FB 200/h). Override via `RATE_LIMIT_<PLATFORM>=calls:seconds`.
Backed by Redis when available; falls back to a process-local counter.
A breach reschedules the dispatch for the documented retry-after window
instead of consuming a retry attempt.

## Uploads + transcoding (Phase 1)

* Browser asks `POST /api/uploads/presign` for a one-shot S3/R2 PUT URL,
  uploads the file directly, then registers it via `POST /api/uploads/complete`.
  No file goes through the API server.
* Set `MEDIA_BUCKET` (and optionally `S3_ENDPOINT_URL` for R2/MinIO) plus the
  AWS access key vars. Set `ENABLE_TRANSCODE=0` to skip ffmpeg locally.
* On video upload completion, Celery `transcode_media` produces three
  derivatives (`16:9`, `9:16`, `1:1`) using the bundled `ffmpeg` binary
  (installed in `Dockerfile.backend`). Derivatives land in S3 and the URLs
  are stored in `media_assets.derivatives`.
* At publish time, `dispatch_target` swaps the request's `media_url` for the
  platform-preferred derivative (TikTok/IG → 9:16, YouTube/Facebook → 16:9).

## Token freshness + failure notifications

* Beat task `refresh_oauth_tokens` runs every 6 hours: any non-revoked
  account whose `token_expires_at` is within 24 h gets refreshed via the
  provider's `OAuthProvider.refresh()`. Failures are audit-logged but never
  stop the beat.
* On a permanent `dispatch_target` failure, `notify_publish_failed` sends
  email (SendGrid) and SMS (Twilio) when those credentials are configured.
  Missing credentials silently skip the channel — never raises.

## Compliance

Every publish goes through `ComplianceEngine.evaluate(...)` which runs:

1. **Text moderation** — Google Perspective API if `PERSPECTIVE_API_KEY` is
   set, otherwise a small local blocklist.
2. **Video moderation** — AWS Rekognition `StartContentModeration` when the
   media has S3 coordinates recorded; no-op otherwise.
3. **Platform rule checks** — caption/title length, required media kinds,
   discouraged hashtags (e.g. `#fyp` for TikTok), platform-specific
   `Publisher.validate(...)` hooks.

Findings persist in `compliance_checks` and the dispatcher refuses to publish
when any blocker is present (status flips to `rejected_compliance`).

## Scheduling

* **One-shot**: post `scheduled_for` in `POST /api/schedules` (any timezone,
  ISO 8601). The `sweep_due_targets` Celery beat queues anything past due
  every minute.
* **Recurring (cron)**: provide a 5-field cron expression and a timezone. The
  beat task `advance_cron_targets` materialises the next dispatch as soon as
  the previous one finishes, so missed slots don't pile up unbounded.
* **Retry**: transient platform errors (`5xx`, `429`, network) are retried
  with exponential backoff + jitter (`utils.retry.backoff_seconds`) up to
  `RETRY_MAX_ATTEMPTS`. Permanent errors land in `failed` and surface in the
  dashboard for manual retry.

## Audit + GDPR

Every state-changing API call writes an `audit_logs` row with the actor,
action, resource, and a structured detail blob. Tokens are stored encrypted;
`POST /api/accounts/users/<id>/erase` records an erasure request which a
downstream worker (not included) processes for right-to-be-forgotten.

## REST API summary

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/api/posts/media` | Register a media asset |
| `POST` | `/api/posts` | Create a draft |
| `PUT` | `/api/posts/<id>` | Save a new version |
| `POST` | `/api/posts/<id>/rollback` | Revert to parent version |
| `POST` | `/api/posts/<id>/preview-compliance` | Run checks without scheduling |
| `GET` | `/api/posts/<id>/diff/<other_id>` | Diff two versions |
| `POST` | `/api/schedules` | Attach platforms to a post |
| `GET` | `/api/schedules` | Status board feed |
| `POST` | `/api/schedules/<id>/cancel` | Cancel a pending target |
| `POST` | `/api/schedules/<id>/retry` | Re-queue a failed target |
| `GET` | `/api/accounts` | Connected accounts |
| `POST` | `/api/accounts/<id>/test` | Token freshness check |
| `GET`/`POST` | `/auth/{meta,tiktok,youtube}/...` | OAuth start/callback |
| `GET` | `/api/audit` | Audit log feed |

## Platform notes / TOS

* **Facebook + Instagram** require a Page (and a linked IG Business account
  for Instagram). Use the long-lived Page Access Token returned by
  `/me/accounts` — we store that, not the user token.
* **TikTok** Content Posting API enforces strict rate limits and may require
  app review for `video.publish`. The adapter only uses `PULL_FROM_URL`
  upload mode.
* **YouTube** uploads use the resumable protocol via the official client to
  ride out network blips. The default `privacyStatus` is `private`; flip via
  the per-target `overrides.privacy_status`.

The system never simulates user input or attempts to bypass rate limits.
Configure your dispatch cadence to stay within each platform's quota.

## Testing

```bash
cd backend
pytest
```

Tests cover the compliance engine, the cron successor logic, and the public
HTTP surface. They do not call any external APIs.
