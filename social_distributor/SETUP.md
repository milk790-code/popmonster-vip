# Setup — From zero to first published post

This walks through every step needed to get the Social Distributor running
on your own infrastructure and post your first piece of content. Plan on
60–90 minutes for the first time (most of it waiting for OAuth app reviews
to be ready).

## 0. Prerequisites

- **Docker + Docker Compose** (`docker --version` should print 20+).
- **An S3-compatible bucket** for media storage. Any of these work:
  - AWS S3 (default)
  - Cloudflare R2 (set `S3_ENDPOINT_URL=https://<account>.r2.cloudflarestorage.com`)
  - MinIO (self-hosted; set `S3_ENDPOINT_URL` accordingly)
- **A domain with HTTPS** for the OAuth callback URLs. Localhost works for
  Google/Meta dev mode but **not** TikTok — TikTok rejects `localhost` and
  HTTP. Use ngrok / Cloudflare Tunnel for local dev: `ngrok http 5000`.
- **Optional but recommended**: an Anthropic API key for the Claude variant
  engine, a Sentry DSN for error tracking.

## 1. Clone + first-time config

```bash
git clone https://github.com/milk790-code/popmonster-vip.git
cd popmonster-vip/social_distributor

cp backend/.env.example backend/.env

# Generate the encryption key for stored OAuth tokens. Paste the output
# into backend/.env as TOKEN_ENCRYPTION_KEY=
python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Edit `backend/.env`:

| Variable | What to put |
|---|---|
| `SECRET_KEY` | `python3 -c "import secrets; print(secrets.token_urlsafe(48))"` |
| `TOKEN_ENCRYPTION_KEY` | output of the Fernet command above |
| `MEDIA_BUCKET` | the bucket name you'll create in step 2 |
| `S3_ENDPOINT_URL` | leave empty for AWS, set for R2/MinIO |
| `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` | IAM user credentials |
| `AWS_REGION` | `us-east-1` for AWS, `auto` for R2 |
| `ANTHROPIC_API_KEY` | optional — enables Claude variants |
| `SENTRY_DSN` | optional |

Leave the OAuth `*_APP_ID/CLIENT_ID/CLIENT_SECRET` blank for now — we fill
them in step 3.

## 2. Object storage

### AWS S3

```bash
aws s3 mb s3://my-distributor-media --region us-east-1
aws s3api put-bucket-cors --bucket my-distributor-media --cors-configuration '{
  "CORSRules": [{
    "AllowedOrigins": ["https://your-dashboard.example.com"],
    "AllowedMethods": ["PUT", "GET"],
    "AllowedHeaders": ["*"],
    "MaxAgeSeconds": 3000
  }]
}'
```

Create an IAM user with this policy attached:

```json
{
  "Version": "2012-10-17",
  "Statement": [{
    "Effect": "Allow",
    "Action": ["s3:PutObject", "s3:GetObject", "s3:DeleteObject"],
    "Resource": "arn:aws:s3:::my-distributor-media/*"
  }]
}
```

Use that user's access key in `.env`.

### Cloudflare R2

1. R2 → Create bucket (e.g. `distributor-media`)
2. Manage R2 API Tokens → Create token with **Object Read & Write** for the
   bucket
3. In `.env`:
   ```
   AWS_ACCESS_KEY_ID=<R2 access key>
   AWS_SECRET_ACCESS_KEY=<R2 secret>
   AWS_REGION=auto
   S3_ENDPOINT_URL=https://<account-id>.r2.cloudflarestorage.com
   MEDIA_BUCKET=distributor-media
   ```
4. Settings → Public Access → enable if you want platform fetchers to grab
   media without signed URLs (faster IG/FB publishing).

## 3. Create OAuth apps

> Each platform's "redirect URI" must exactly match the corresponding
> `*_REDIRECT_URI` in your `.env`. For local dev with ngrok, that's the
> https URL ngrok gave you, e.g. `https://abc123.ngrok-free.app/auth/meta/callback`.

### Meta (Facebook + Instagram)

1. https://developers.facebook.com/apps → **Create App** → "Business" type.
2. Add products:
   - **Facebook Login for Business**
   - **Instagram Graph API**
3. Settings → Basic: copy **App ID** to `META_APP_ID`, **App Secret** to `META_APP_SECRET`.
4. Facebook Login → Settings → Valid OAuth Redirect URIs: add
   `https://<your-domain>/auth/meta/callback`.
5. App Review → Permissions → request these (start in development mode for
   testing first):
   - `pages_show_list`
   - `pages_read_engagement`
   - `pages_manage_posts`
   - `instagram_basic`
   - `instagram_content_publish`
   - `business_management` (only if you'll use the Permissions / Transfers
     features in Phase 5; needed to call BM endpoints)
6. **Crucial**: The Instagram account you publish to **must be a Business
   or Creator account** *and* linked to a Facebook Page. The OAuth flow
   discovers IG accounts via the linked Page.

### TikTok

1. https://developers.tiktok.com → Manage Apps → Create app.
2. Add product: **Login Kit**, **Content Posting API**.
3. App settings → URL configurations:
   - Redirect URI: `https://<your-domain>/auth/tiktok/callback`
   - Web URL: your domain
4. Copy **Client Key** to `TIKTOK_CLIENT_KEY`, **Client Secret** to
   `TIKTOK_CLIENT_SECRET`.
5. App Review → request scopes:
   - `user.info.basic`
   - `video.upload`
   - `video.publish` (this needs **production review** — until approved,
     posts publish as `SELF_ONLY` drafts only)
   - `business.creator.read` (only if you'll use the Permissions Phase 5
     features against TikTok Business Center assets)
6. **Heads up**: TikTok rate-limits and reviews are strict. The default
   `RATE_LIMIT_TIKTOK=30:86400` (30/day) reflects what an unaudited app
   typically gets; bump it after audit.

### Google (YouTube)

1. https://console.cloud.google.com → Create project.
2. APIs & Services → Library → enable **YouTube Data API v3** *and*
   **YouTube Analytics API**.
3. APIs & Services → OAuth consent screen → "External" type, fill out app
   info, add test users (your own Google account).
4. Credentials → Create OAuth client ID → Web application:
   - Authorized redirect URIs: `https://<your-domain>/auth/youtube/callback`
5. Copy **Client ID** to `GOOGLE_CLIENT_ID`, **Client Secret** to
   `GOOGLE_CLIENT_SECRET`.
6. While in development mode, only test users you've added can authorise
   the app. Submit for verification when you go live.

## 4. Start the stack

```bash
docker compose up --build -d
docker compose logs -f api  # in another tab, for sanity checking
```

Services come up:

- API: `http://localhost:5000` (proxy to your domain in production)
- Dashboard: `http://localhost:8080`
- Worker + beat: runs in `worker` container

Verify:

```bash
curl http://localhost:5000/healthz       # → {"status":"ok"}
```

## 5. Sign in (magic link, no password)

Open `https://your-dashboard.example.com/login.html` (or `http://localhost:8080/login.html`
for local dev). Enter your email → check your inbox → click the magic link
→ you're in. The dashboard auto-detects the session and hides the manual
User ID field.

> **First-boot shortcut**: if you launched fresh and the `users` table is
> empty, the API auto-seeds `me@local` (`user_id=1`) so the dashboard works
> immediately without going through magic-link. Disable with
> `AUTO_SEED_USER=0`.

> **Backcompat**: any endpoint still accepts `?user_id=N` for 7 days from
> deploy (sunset 2026-05-12). Old scripts keep working but emit a
> `Deprecation` response header.

> **Need SendGrid?** Magic links go out via SendGrid. Without
> `SENDGRID_API_KEY` set, the `/auth/login/request` call still returns 200
> but no email goes out. For local dev without SendGrid, you can mint and
> consume a magic link directly:
>
> ```bash
> docker compose exec api python -c "
> from app import create_app; from app.utils.auth import issue_magic_token
> app = create_app()
> with app.app_context():
>     print('http://localhost:5000/auth/login/verify?token=' + issue_magic_token('you@example.com'))
> "
> ```

## 6. Connect first account

1. Dashboard → **Accounts** tab → click **Connect Facebook + Instagram**.
2. New tab opens with Meta's authorisation screen. Approve.
3. After redirect, the dashboard's account list refreshes; you should see
   one row per Facebook Page you manage and one per linked IG Business
   account.
4. Repeat for TikTok and YouTube buttons.

If a connect button does nothing or returns 400, check `docker compose logs
api` — usually the redirect URI didn't match.

## 7. Create your first persona group

Dashboard → **人設群組** tab:

```
群組名稱:    美食日常 A
描述:        親切口吻分享每天吃的東西
預設時區:    Asia/Taipei
Style profile (JSON):
{
  "tone": "casual",
  "voice": "親切的鄰家姊姊，喜歡用比喻",
  "emoji_density": "medium",
  "hashtag_pool": ["#日常", "#美食", "#推薦", "#療癒", "#台北", "#週末"],
  "audience": "20-30 歲都會女性",
  "do_not_say": ["保證", "100% 有效", "limited time only"]
}
```

Click **建立群組**, then on the new card click **加入帳號** to attach your
FB / IG / TikTok / YouTube accounts to this persona.

## 8. First post

1. **Compose** tab → drag a video into the dropzone. The status text shows
   `Uploading … → Uploaded ✓ media_id=N (transcode: pending)`. Within
   ~30s the worker finishes transcoding and `derivatives` populate.
2. Fill in title (used for YouTube) and caption.
3. Watch the WYSIWYG cards underneath — fix any red character counts.
4. Click **Save draft** — note the `id` in the JSON output.
5. **Distribute** tab:
   - Post ID = the saved draft's id
   - 選擇群組 = your persona
   - Scheduled for = leave blank for "send now" or pick a future time
   - Jitter window = 20 minutes (recommended for matrix)
   - ✅ 為每個帳號產生變體文案
   - ⬜ Dry run (uncheck to actually send)
6. Click **Distribute**. The plan shows up in the output box.
7. **Status board** tab shows live progress (auto-updates via SSE).

## 9. After a few posts: check insights

Once you have ~3 successful posts on the same account:

- **Insights** tab → 載入 → see reach/likes/comments per platform
- **最佳發布時段建議** → 填 Account ID 或 Group ID → 查詢 →
  table shows top engagement-rate hours of week

The `ingest_insights` Celery beat runs every hour, so metrics catch up
within an hour of publishing.

## 10. Production hardening checklist

- [ ] HTTPS in front of port 5000 (Caddy / nginx / Cloudflare Tunnel)
- [ ] Postgres replaces SQLite (uncomment `db` service is already done; just
      set `DATABASE_URL=postgresql+psycopg2://...`)
- [ ] `gunicorn --worker-class gevent` for the api service so SSE doesn't
      starve worker pool
- [ ] Backup the `dbdata` volume (it holds all your tokens, posts,
      schedules, audit log)
- [ ] Set `SENTRY_DSN` and `OTEL_EXPORTER_OTLP_ENDPOINT` for visibility
- [ ] Configure `notify_email_from` + Sendgrid/Twilio for failure pages
- [ ] Restrict the `MEDIA_BUCKET` IAM user to `s3:PutObject,GetObject` only
- [ ] Rotate `TOKEN_ENCRYPTION_KEY` on a schedule (re-encrypt during a
      scheduled maintenance window)

## Troubleshooting

| Symptom | Likely cause |
|---|---|
| Upload shows "Presign failed: 500" | `MEDIA_BUCKET` empty or IAM user lacks permission |
| FB/IG connect succeeds but no rows appear | the OAuth user has no FB Pages, or IG Business account isn't linked to a Page |
| TikTok publish status stuck pending | `video.publish` scope unaudited → posts go to drafts inside TikTok app |
| YouTube upload fails with 403 | `YouTube Data API v3` not enabled, or app still in "Testing" without user as test user |
| Dashboard shows nothing on Status board | likely SSE blocked; ensure `worker-class gevent` (or just refresh manually — falls back to polling) |
| `ffmpeg: not found` in worker | rebuild image (`docker compose build worker`) — Dockerfile installs ffmpeg |
