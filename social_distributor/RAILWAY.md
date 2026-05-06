# Railway 部署指南 / Railway Deployment

This project deploys to Railway as **3 services** sharing the same GitHub repo
+ a managed Postgres + a managed Redis. All deploy from this branch automatically.

## Services to create in Railway UI

For each service, choose **"Deploy from GitHub repo"** → pick `popmonster-vip`
→ then in **Settings → Source**, set **Root Directory** = `social_distributor`.

### 1. `api` (web, public)

| Field | Value |
|---|---|
| Root Directory | `social_distributor` |
| Dockerfile Path | `Dockerfile.backend` |
| Custom Start Command | _leave blank_ (uses Dockerfile CMD) |
| Public Networking | **Generate Domain** (yes) |
| Healthcheck Path | `/healthz` |

### 2. `worker` (private, no public domain)

| Field | Value |
|---|---|
| Root Directory | `social_distributor` |
| Dockerfile Path | `Dockerfile.backend` |
| Custom Start Command | `celery -A celery_worker.celery worker -B -l info` |
| Public Networking | _disabled_ |

### 3. `frontend` (web, public)

| Field | Value |
|---|---|
| Root Directory | `social_distributor` |
| Dockerfile Path | `Dockerfile.frontend` |
| Custom Start Command | _leave blank_ |
| Public Networking | **Generate Domain** (yes) |

### 4. `Postgres` (managed)

Click **+ New → Database → PostgreSQL**. Railway auto-injects `DATABASE_URL`
into services that reference it.

### 5. `Redis` (managed)

Click **+ New → Database → Redis**. Railway auto-injects `REDIS_URL`.

---

## Environment variables

Set on **`api`** AND **`worker`** services (use Variable References for the DBs):

```
SECRET_KEY=<generate>
TOKEN_ENCRYPTION_KEY=<fernet key>
DATABASE_URL=${{Postgres.DATABASE_URL}}
REDIS_URL=${{Redis.REDIS_URL}}
CELERY_BROKER_URL=${{Redis.REDIS_URL}}
CELERY_RESULT_BACKEND=${{Redis.REDIS_URL}}
META_APP_ID=<from developers.facebook.com>
META_APP_SECRET=<from developers.facebook.com>
META_REDIRECT_URI=https://<api-railway-domain>/auth/meta/callback
MEDIA_BUCKET=<R2 bucket name>
S3_ENDPOINT_URL=https://<r2-account-id>.r2.cloudflarestorage.com
AWS_ACCESS_KEY_ID=<R2 access key>
AWS_SECRET_ACCESS_KEY=<R2 secret>
AWS_REGION=auto
FLASK_ENV=production
SESSION_COOKIE_SECURE=1
AUTO_SEED_USER=1
ENABLE_TRANSCODE=1
PUBLISH_DEFAULT_TIMEZONE=UTC
PLATFORM_HTTP_TIMEOUT=60
MAGIC_LINK_TTL=1800
ANTHROPIC_VARIANT_MODEL=claude-haiku-4-5-20251001
DASHBOARD_URL=https://<frontend-railway-domain>/
```

Generate secrets:

```bash
python3 -c "import secrets; print(secrets.token_urlsafe(48))"  # SECRET_KEY
python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"  # TOKEN_ENCRYPTION_KEY
```

Set on **`frontend`** service:

```
API_BASE_URL=https://<api-railway-domain>
CACHE_VERSION=prod-1
```

---

## After first deploy

1. Note the `api` and `frontend` Railway-generated domains.
2. Update `META_REDIRECT_URI` to use the `api` domain.
3. In Meta Developers app settings → Facebook Login → Settings, add:
   - `https://<api-railway-domain>/auth/meta/callback` to **Valid OAuth Redirect URIs**
4. Update `DASHBOARD_URL` to the `frontend` domain.
5. Redeploy `api` to pick up new env vars.
6. Open `https://<frontend-railway-domain>/` → Accounts tab → connect Meta.
