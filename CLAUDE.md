# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**popmonster-vip** is a static e-commerce site for POP MONSTER, a Taiwanese auto-care product brand (hook fishing tackles, polishing compounds, etc.). The repo contains two main components:

1. **Main site** (root): Pure static HTML/CSS/JS deployed to Cloudflare Pages at `popmonster.vip`
2. **social_distributor** (subproject): Full-stack social media publishing platform (Flask API + Vanilla JS dashboard + Tauri desktop app + Celery workers)

## Architecture Overview

### Main Site Structure (Static)

- **27 product pages** (`a001.html`–`a041.html` with gaps in numbering; see README for deleted SKU list)
- **Navigation pages**: `index.html` (home with grid + carousel), `about.html` (brand story), `members.html`, `free-guide.html`, `ai-encyclopedia.html`, `error-report.html`, `privacy.html`, `terms.html`
- **Styling**: Single `css/main.css` with CSS variables for black-gold theme (`#0a0a0a`, `#c8a96b`). Responsive breakpoint at 768px. Mobile-first design with 44px touch targets.
- **JavaScript**: `js/main.js` handles carousel, FAQ collapsing, category filtering, Cookie Consent (GA4 v2 Consent Mode), scroll animations
- **Image structure**: `img/aXXX/` directories per product (multiple angles), keyed to product HTML by SKU
- **SEO**: Per-page canonical, hreflang, OG tags; `sitemap.xml` (27 products + 8 content pages); `robots.txt`; Schema.org (Product, BreadcrumbList, FAQPage as JSON-LD)
- **PWA**: `manifest.json`, `favicon.svg`; no service worker
- **Analytics**: GA4 (`G-WTKLHW33D7`) with IP anonymization and Consent Mode v2

**Key conventions:**
- Chinese (Traditional Taiwan): `zh-Hant-TW` lang attribute
- Affiliate links: `rel="nofollow sponsored noopener"` to Shopee
- LINE contact: `rel="noopener"`
- All links use inline `style` attributes for mobile menu (avoid stylesheet complexity in limited CSS)

### Social Distributor Architecture

Cross-platform publishing system for FB, IG, TikTok, YouTube. **Design principle**: compliance-first, official APIs only, no detection evasion.

```
social_distributor/
├── backend/
│   ├── run.py                 # Flask app entry
│   ├── celery_worker.py       # Celery + beat entry
│   ├── app/
│   │   ├── __init__.py        # create_app() factory
│   │   ├── config.py          # env-driven config (defaults supplied)
│   │   ├── models.py          # SQLAlchemy ORM (User, Post, DispatchTarget, etc.)
│   │   ├── extensions.py      # db, migrate, redis, sentry, otel
│   │   ├── auth/              # OAuth2 flows + magic-link login (SendGrid)
│   │   ├── api/               # REST endpoints (Flask blueprints)
│   │   ├── platforms/         # Platform adapters (Facebook, TikTok, YouTube)
│   │   ├── compliance/        # Text/video moderation, per-platform validators
│   │   ├── scheduler/         # Celery beat tasks (dispatch, insights, health sweeps)
│   │   ├── transfers/         # Ownership transfer state machine
│   │   ├── permissions/       # Grant management + drift alerts
│   │   └── utils/
│   │       ├── variants.py    # Caption rewriting (Claude or template fallback)
│   │       ├── rate_limit.py  # Per-platform rate guard
│   │       ├── retry.py       # Exponential backoff
│   │       ├── experiments.py # A/B variant analytics
│   │       ├── digest.py      # Weekly insights email (Claude powered)
│   │       └── [more]
│   ├── tests/                 # pytest (161 tests, no external API calls)
│   └── requirements.txt
├── frontend/
│   ├── index.html             # PWA shell
│   ├── login.html             # Magic-link login page
│   ├── js/app.js              # Dashboard logic (Compose, Status, Insights tabs)
│   ├── sw.js                  # Service worker (cache shell + SSE fallback)
│   └── css/
├── desktop/                   # Tauri 2 wrapper (loads frontend in native window)
│   ├── src-tauri/             # Rust harness
│   └── src/                   # Frontend assets (shared with web)
├── Dockerfile.backend
├── Dockerfile.frontend
├── docker-compose.yml
└── [SETUP.md, README.md, RAILWAY.md docs]
```

**Key data flow:**
1. Browser uploads media → presigned S3 PUT URL → S3 direct upload → `/api/uploads/complete` registers it
2. User composes caption + selects platform personas → `POST /api/posts/distribute` fans out
3. Per-persona/per-platform: variant engine rewrites caption (Claude or template), compliance check runs, target queued to Celery
4. Worker: `dispatch_target` task calls platform API, logs attempt, emits `target.status_changed` to Redis pub/sub
5. Dashboard: SSE stream `/api/events/stream` auto-refreshes status board without polling

**Key architectural choices:**
- **Compliance-first**: every dispatch hits `ComplianceEngine` before send; failures land in `rejected_compliance` status
- **Token security**: OAuth tokens encrypted with Fernet (AES-128-CBC + HMAC), never logged
- **Rate limiting**: per-platform quotas (TikTok 30/day, IG 50/24h, etc.) backed by Redis or fallback counter
- **Retry logic**: transient errors retry with exponential backoff; permanent errors surface for manual retry
- **Variants**: Claude API with prompt caching (style_profile as cached system block) or deterministic template fallback
- **Insights**: hourly ingestion from platform APIs, bucketed by hour-of-week to suggest best post times
- **Scheduling**: one-shot (ISO 8601) or cron (5-field + timezone); beat sweeps due targets every minute

## Common Development Tasks

### Main Site (Static)

**Build / Deploy:**
```bash
# Push to main branch; Cloudflare Pages auto-deploys
git push origin main
```

**Add a new product page:**
1. Create `aXXX.html` from template (copy `a001.html`, update SKU, title, description, image paths)
2. Add image directory: `mkdir img/aXXX/` and place JPGs
3. Update `sitemap.xml` to add `<loc>https://popmonster.vip/aXXX.html</loc>`
4. Update `index.html` carousel + grid to reference new product

**Update Shopee links:**
```bash
grep -r "https://shopee.tw/milk790" .  # Find all occurrences
# Then update each product HTML with its individual Shopee listing
```

**Update analytics tracking ID:**
```bash
grep -r "G-WTKLHW33D7" .  # All GA4 scripts
```

### Social Distributor

**Install dependencies (local Python):**
```bash
cd social_distributor/backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

**Run backend (local dev):**
```bash
cd social_distributor/backend
cp .env.example .env  # edit for local OAuth + encryption key
flask --app run.py run
# In another terminal:
celery -A celery_worker.celery worker -B -l info
```

**Run backend (Docker):**
```bash
cd social_distributor
docker compose up --build -d
docker compose logs -f api
```

**Run tests:**
```bash
cd social_distributor/backend
pytest                          # All tests
pytest tests/test_compliance.py # Single test file
pytest -k test_variant_engine   # Single test by name
```

**Run linters / type checks:**
```bash
cd social_distributor/backend
pytest --cov=app               # Coverage
flake8 app/ tests/             # (if configured)
```

**Debug a failing dispatch:**
- Check `docker compose logs worker` for task error
- Query `DispatchTarget` row in DB: `status`, `platform`, `external_post_id`, `error_message`
- Check `audit_logs` for actor + action sequence
- Review `compliance_checks` rows for that post if status is `rejected_compliance`

**Run Celery beat tasks manually (testing):**
```bash
cd social_distributor/backend
python -c "
from app import create_app
from app.scheduler.tasks import refresh_oauth_tokens
app = create_app()
with app.app_context():
    refresh_oauth_tokens()
"
```

**Generate encryption key for token storage:**
```bash
python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

## .claude/ Hook Configuration

The repository has a `SessionStart` hook in `.claude/settings.json` that runs `session-start.sh` in remote Claude Code sessions. This installs Python dependencies for the social_distributor backend so tests and linters work immediately. Local development is unaffected.

## File Patterns & Naming

- **Product pages**: `aXXX.html` where XXX is the product SKU (01–41, with gaps). Numbering starts at 01, not 00.
- **Product images**: `img/aXXX/` directory per product, containing multiple JPG angles
- **Main CSS**: Single `css/main.css` with CSS custom properties (variables) for theme colors, spacing, transitions
- **Platform adapters**: `social_distributor/backend/app/platforms/<platform>.py` (facebook.py, tiktok.py, youtube.py)
- **REST API**: `social_distributor/backend/app/api/<resource>.py` (posts.py, accounts.py, etc.)
- **Celery tasks**: `social_distributor/backend/app/scheduler/tasks.py` (beat tasks like `sweep_due_targets`, `ingest_insights`)

## Database Schema Highlights (Social Distributor)

Key tables in `models.py`:
- `User`: authenticated user (email, session)
- `Post`: draft or published content (caption, media_ids, scheduling)
- `DispatchTarget`: one post → one persona group → one platform (tracks status, retries, metrics)
- `SocialAccount`: connected OAuth account (platform, access_token [encrypted], expires_at)
- `AccountGroup`: persona group (name, style_profile JSON, members list)
- `PostMetric`: hourly engagement snapshot (reach, impressions, engagement_rate, etc.)
- `AuditLog`: every state change (user, action, resource, details blob)
- `PermissionGrant`: per-persona permission on an account (role, granted_at)
- `PermissionDriftAlert`: mismatch between DB and platform truth (resolved_at for closing)

## Environment Variables (Social Distributor)

Core:
- `SECRET_KEY`: Flask session secret
- `TOKEN_ENCRYPTION_KEY`: Fernet key for OAuth tokens
- `DATABASE_URL`: SQLAlchemy URI (SQLite by default, set for Postgres)
- `REDIS_URL`: for rate limiting, pub/sub, Celery broker (fallback to in-process if unset)

Platforms:
- `META_APP_ID`, `META_APP_SECRET`, `META_REDIRECT_URI`
- `TIKTOK_CLIENT_KEY`, `TIKTOK_CLIENT_SECRET`, `TIKTOK_REDIRECT_URI`
- `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `GOOGLE_REDIRECT_URI`

Media:
- `MEDIA_BUCKET`: S3 bucket name
- `S3_ENDPOINT_URL`: for R2/MinIO (leave empty for AWS S3)
- `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_REGION`
- `ENABLE_TRANSCODE`: set to 0 to skip ffmpeg (test mode)

Optional:
- `ANTHROPIC_API_KEY`: enables Claude variants + digest digest
- `SENDGRID_API_KEY`: for magic-link emails + failure notifications
- `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`: for SMS alerts
- `SENTRY_DSN`: error tracking
- `OTEL_EXPORTER_OTLP_ENDPOINT`: OpenTelemetry traces

Rate limits (override defaults):
- `RATE_LIMIT_TIKTOK=30:86400` (30 posts per 86400 seconds)
- `RATE_LIMIT_INSTAGRAM=50:86400`
- `RATE_LIMIT_FACEBOOK=200:3600`
- `RATE_LIMIT_YOUTUBE=6:86400`

## Testing Strategy (Social Distributor)

- 161 pytest tests in `backend/tests/` — zero external API mocking, uses SQLite in-memory DB
- Tests cover: compliance engine, cron scheduling, rate limiting, variant engine, A/B analytics, API smoke tests
- Run: `cd backend && pytest` (includes coverage)
- **No external API calls** — platform adapters return mock responses

## Deployment (Main Site)

**Cloudflare Pages:**
- `CNAME` file points to `popmonster.vip`
- GitHub integration: push to `main` → auto-build (no build command, pure static)
- Preview URLs: each PR gets a `*.popmonster-vip.pages.dev` URL (auto-generated by Cloudflare bot)
- HTTPS: automatic via Cloudflare
- DNS: already configured by Cloudflare

**Deployment (Social Distributor):**
- Dockerized: `Dockerfile.backend`, `Dockerfile.frontend`, `docker-compose.yml`
- Backend runs on Flask (dev) or gunicorn (prod with `--worker-class gevent` for SSE)
- Worker + beat: single Celery container with `-B` flag
- Database: SQLite (dev), Postgres (prod)
- Media: S3 or R2
- See `SETUP.md` and `RAILWAY.md` for full production hardening checklist

---

## Key Insights for Future Contributors

1. **Main site is intentionally static** — no build step, no Node.js, no runtime. Speeds up deploys and reduces attack surface.
2. **Social distributor is modular by platform** — add a new platform by extending `PlatformAdapter`, adding OAuth flow, compliance rules, and tests.
3. **Compliance is non-blocking for warnings** — set `ORIGINALITY_BLOCK=1` to escalate. Same for other checks.
4. **Claude integration is opt-in** — variants and digest email fall back gracefully if `ANTHROPIC_API_KEY` is missing.
5. **All tokens are encrypted at rest** — Fernet in the DB, never plaintext. Audit logs redact them.
6. **Rate limits are soft** — a breach reschedules the dispatch instead of consuming a retry. Platform-documented limits are used as defaults.
7. **Tests run fast** — no waiting for external APIs; in-memory DB + mocked platform responses.
