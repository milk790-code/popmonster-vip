# Phase 1 部署 social_distributor backend 到 Railway

## Context

Runbook（已存 `social_distributor/RUNBOOK_SEED_SPRINT.md`、commit a3b620f）
Phase 1 部署只給了表格 + 概略指令。實際操作會卡在：
- Railway 3 service 應該怎麼分？
- Redis plugin 只給 DB 0，docker-compose 用 db 0/1/2 拆 broker/result_backend，
  在 Railway 直接照搬會 task deadlock
- `db.create_all()` 自動執行（`app/__init__.py:138` `_auto_seed_user`），不用
  手動 `flask db upgrade`
- frontend 是 nginx template render，不是 reverse proxy；需 `API_BASE_URL` env
- Dockerfile.backend 已含 ffmpeg，**不用**設 `ENABLE_TRANSCODE=0`
- OAuth redirect URI 要 production 域名才不會被 Meta 反覆 reject

本 plan 把 Railway 部署拆成「12 個會檢查的步驟」，從建專案到 `/healthz/ready`
回 `database/redis/celery=configured`、custom domain 上 HTTPS，連 OAuth env
都先佔位（值留到 Phase 4 填）。預估 **30–60 min**，瓶頸是 Cloudflare DNS
propagation（通常 1–5 min）和 Railway image build（~5 min）。

## 推薦路徑：Railway + custom domain `api.popmonster.vip`

3 個 Railway service 共用同一個 image（Dockerfile.backend），加一個 nginx
frontend：

```
api      ─ public ─ api.popmonster.vip ─ Dockerfile.backend (gunicorn)
worker   ─ private ─ ───                ─ Dockerfile.backend (celery -B)
frontend ─ public ─ app.popmonster.vip  ─ Dockerfile.frontend (nginx)
```

`db` / `redis` 用 Railway 內建 plugin，URL 透過 `${{Postgres.DATABASE_URL}}`
注入。

**已拍板的設定（用戶確認）：**
- Railway Source branch = `claude/remote-control-skill-CiYUW`（PR #15 那條，
  不等 merge）。Phase 1 完成 + PR review 通過後改回 `main`
- Media storage = **Cloudflare R2**（同生態、無 egress fee、S3-compat）
- frontend service 一起上 `app.popmonster.vip`
- `ANTHROPIC_API_KEY` / `SENDGRID_API_KEY` Phase 1 不填，走 fallback

## 12 步部署 + 檢查清單

### Step 1 — Railway 建專案（5 min）
1. https://railway.app → New Project → Deploy from GitHub repo →
   選 `milk790-code/popmonster-vip`
2. 不要讓它自動 detect；先建空 project
3. 加 4 個 service：
   - Postgres plugin
   - Redis plugin
   - `api`（Empty Service，等 Step 3 設定）
   - `worker`（Empty Service）
   - （可選）`frontend`（Empty Service）

### Step 2 — Postgres / Redis plugin 就緒（自動）
- 等兩個 plugin 出現 `Active` 狀態
- 從 Plugin → Variables 抄出 `DATABASE_URL`、`REDIS_URL` 的 reference 語法
  `${{Postgres.DATABASE_URL}}` / `${{Redis.REDIS_URL}}`

### Step 3 — `api` service 設定（10 min）
**Source**：
- Repo = `milk790-code/popmonster-vip`
- Root Directory = `social_distributor`
- Branch = `claude/remote-control-skill-CiYUW`（PR #15）
- Dockerfile Path = `Dockerfile.backend`

**Start Command**（覆蓋 Dockerfile 的，因 Railway 注入 `$PORT`）：
```
gunicorn -k gevent -w 2 --worker-connections 100 --timeout 120 -b 0.0.0.0:$PORT run:app
```

**Variables**（複製貼上整批）：
```
PORT=                                # Railway auto-injects
SECRET_KEY=<生成：python -c "import secrets;print(secrets.token_hex(32))">
TOKEN_ENCRYPTION_KEY=<生成：python -c "from cryptography.fernet import Fernet;print(Fernet.generate_key().decode())">
DATABASE_URL=${{Postgres.DATABASE_URL}}
REDIS_URL=${{Redis.REDIS_URL}}
CELERY_BROKER_URL=${{Redis.REDIS_URL}}
CELERY_RESULT_BACKEND=${{Redis.REDIS_URL}}
AUTO_SEED_USER=0                     # 改用 scripts/bootstrap_user.py 顯式建
PUBLISH_DEFAULT_TIMEZONE=Asia/Taipei

# OAuth — 先佔位，Phase 4 通過後填
META_APP_ID=
META_APP_SECRET=
META_REDIRECT_URI=https://api.popmonster.vip/auth/meta/callback
TIKTOK_CLIENT_KEY=
TIKTOK_CLIENT_SECRET=
TIKTOK_REDIRECT_URI=https://api.popmonster.vip/auth/tiktok/callback

# S3 / R2 — Phase 6 之前要齊
MEDIA_BUCKET=popmonster-media
AWS_ACCESS_KEY_ID=
AWS_SECRET_ACCESS_KEY=
AWS_REGION=auto                       # R2 用 auto；AWS S3 用 us-east-1
S3_ENDPOINT_URL=                      # R2 才填；AWS 留空

# Soft skip（Phase 1 不填，走 fallback；Phase 4 後再補）
# ANTHROPIC_API_KEY=
# SENDGRID_API_KEY=
# NOTIFY_EMAIL_FROM=
```

**重要：** `CELERY_BROKER_URL` 和 `CELERY_RESULT_BACKEND` 都指同一個 Redis
URL（Railway managed Redis 只開 DB 0），不像 docker-compose 拆三個 DB index。
這會略增 key collision 風險但運作正常 — Celery 加自己的 key prefix。

### Step 4 — `worker` service 設定（5 min）
- 一模一樣 Source 設定
- **Start Command**：
  ```
  celery -A celery_worker.celery worker -B -l info
  ```
  （`-B` = beat 內嵌；不用另開 service）
- **Variables**：複製 `api` service 整份 env（Railway 有 "Reference all from api" 按鈕）
- **不要** 設 `PORT`（worker 不開 HTTP）
- Networking → 關掉 public domain

### Step 5 — First deploy（5–8 min build）
- 兩個 service 同時 Deploy
- 看 Logs：
  - `api`：應該看到 `gunicorn ... Listening at: http://0.0.0.0:<port>`
  - `worker`：應該看到 `celery@... ready.` 和 `beat: Scheduler: Sending due task ...`

### Step 6 — 健康檢查（2 min）
- Railway 給 `api` 一個臨時 URL `<service>-<hash>.up.railway.app`
- 開 `https://<railway-url>/healthz` → 期望 `{"status":"ok"}`
- 開 `https://<railway-url>/healthz/ready` → 看 JSON：
  ```json
  {
    "database": {"configured": true},
    "redis": {"configured": true},
    "celery": {"configured": true},
    "encryption": {"token_key_set": true},
    "media_bucket": {"configured": false},  // Step 9 之前都是 false
    "oauth": {"meta": false, "tiktok": false, ...} // Phase 4 之後才 true
  }
  ```
- 上面三個 `database/redis/celery=configured` 必須是 `true`，**Phase 1 才算過**

### Step 7 — Custom domain：`api.popmonster.vip`（10 min，含 DNS 等待）
1. Railway → `api` service → Settings → Networking → Custom Domain →
   填 `api.popmonster.vip` → Railway 給你一個 CNAME target，例如
   `<hash>.up.railway.app`
2. Cloudflare DNS（`popmonster.vip` zone）→ Add Record：
   - Type: CNAME
   - Name: api
   - Target: `<hash>.up.railway.app`
   - Proxy: **DNS only**（灰雲，不代理；Railway 自己處理 TLS）
3. 等 1–5 min Cloudflare 同步 + Railway 簽 Let's Encrypt 證書
4. 開 `https://api.popmonster.vip/healthz` → 應該回 `{"status":"ok"}`
5. **Step 6 的所有檢查在新 domain 重做一次**

### Step 8 — Bootstrap initial User（2 min）
Railway → `api` service → Shell（or `railway run` 從本機）：
```
python -m scripts.bootstrap_user --email <你的 email> --display-name "陳學誼" --timezone Asia/Taipei
```
- 印出 `user_id=N (created)`
- 記下 `user_id`，**Phase 5 / Phase 6 都會用**

### Step 9 — Cloudflare R2 bucket 開好（10 min，可平行做）
1. Cloudflare Dashboard → R2 → Create bucket: `popmonster-media`
   （Location = Automatic、Default Storage Class = Standard）
2. R2 → Manage API Tokens → Create Token：
   - Permissions = Object Read & Write
   - Resources = Apply to specific bucket → `popmonster-media`
3. 拿到 `Access Key ID` / `Secret Access Key` / Endpoint URL
   （形如 `https://<account>.r2.cloudflarestorage.com`）
4. 回 Railway `api` + `worker` 兩個 service 的 Variables 填：
   ```
   AWS_ACCESS_KEY_ID=<key>
   AWS_SECRET_ACCESS_KEY=<secret>
   AWS_REGION=auto
   S3_ENDPOINT_URL=https://<account>.r2.cloudflarestorage.com
   ```
5. **CORS** — bucket Settings → CORS Policy，加：
   ```json
   [{"AllowedOrigins":["https://api.popmonster.vip","https://app.popmonster.vip"],
     "AllowedMethods":["GET","PUT"],
     "AllowedHeaders":["*"],
     "ExposeHeaders":["ETag"],
     "MaxAgeSeconds":3600}]
   ```
6. Redeploy api + worker → `/healthz/ready` 的 `media_bucket.configured`
   應變 `true`

### Step 10 — `frontend` service + `app.popmonster.vip`（10 min）
- Railway 第三個 service：
  - Source 同 api（branch `claude/remote-control-skill-CiYUW`、root
    `social_distributor`）
  - **Dockerfile Path = `Dockerfile.frontend`**
- **Variables**：
  ```
  API_BASE_URL=https://api.popmonster.vip
  CACHE_VERSION=v1
  # PORT 由 Railway 自動注入，不要手填
  ```
- Custom domain：Railway → frontend → Networking → Custom Domain →
  `app.popmonster.vip`，Cloudflare DNS 加 CNAME（同 Step 7 流程，灰雲
  DNS only）
- 開 `https://app.popmonster.vip/login` → 看到 magic-link 登入頁
- Phase 4 OAuth 通過後，這頁是「連結 Facebook / TikTok」的入口

### Step 11 — Restart worker 確認 beat（2 min）
- Railway → `worker` → Restart
- Logs 看 `beat: Sending due task ...` 每分鐘出現一次
- 此時 `sweep_due_targets` 已經在巡了；只是 `post_targets` 表空，無事可做

### Step 12 — Smoke test 整條 pipeline（5 min）
不送真 OAuth，純測 backend：
```bash
# 本機
curl -X POST https://api.popmonster.vip/api/uploads/presign?user_id=1 \
  -H "Content-Type: application/json" \
  -d '{"kind":"video","content_type":"video/mp4"}'
# 期望：200 OK with bucket / key / put_url / public_get_url
```
回 200 = 整套 api → DB → S3 / R2 環境變數鏈通。

## 驗收條件（Definition of Done for Phase 1）

- [ ] `https://api.popmonster.vip/healthz` 回 `{"status":"ok"}`
- [ ] `https://api.popmonster.vip/healthz/ready` 的 `database` / `redis` /
      `celery` / `encryption` 都是 `configured: true`
- [ ] `worker` service Logs 每分鐘看到 `beat: Sending due task ...`
- [ ] `scripts/bootstrap_user.py` 跑過且記下 `user_id`
- [ ] R2 bucket 開好、CORS 配對、`media_bucket.configured=true`
- [ ] `/api/uploads/presign` 回 200 with put_url
- [ ] `https://app.popmonster.vip/login` 看到 magic-link 登入頁

完成這 6 項 → Phase 1 結束，**Phase 4 OAuth onboarding 可以開始送審**
（送 Meta + TikTok 各自的 App Review，預計 1–4 週）。

## 關鍵檔案路徑

| 路徑 | 為什麼 |
|---|---|
| `social_distributor/Dockerfile.backend` | gunicorn entrypoint（Step 3、4 覆蓋的 base） |
| `social_distributor/Dockerfile.frontend` | nginx + template render（Step 10） |
| `social_distributor/RAILWAY.md` | 原文件，當對照本 plan 的補充用 |
| `social_distributor/backend/app/__init__.py:88-99` | `/healthz` 和 `/healthz/ready` 路由（Step 6） |
| `social_distributor/backend/app/__init__.py:138` | `db.create_all()` 自動執行（不用 alembic） |
| `social_distributor/backend/app/config.py:106-146` | `readiness()` 內容 — 對照 Step 6 期望 |
| `social_distributor/backend/scripts/bootstrap_user.py` | Step 8（已存在 PR #15） |
| `social_distributor/backend/scripts/upload_videos.py` | Step 12 smoke test 後續會用 |

## Gotchas

1. **Redis DB 0 collision**：Railway managed Redis 只開 DB 0，broker /
   result_backend 共用一個 namespace。Celery 自己加 prefix 不會壞，但
   **不要** 寫 `${{Redis.REDIS_URL}}/1` 試圖拆 — Railway 不接受 multi-DB
   Redis。
2. **不用 alembic / flask db upgrade**：`db.create_all()` 在 app init 跑，
   schema 自動建。**但** 第一次啟動可能要 5–10 秒，期間 `/healthz` 回 503。
3. **`AUTO_SEED_USER=0`**：預設 1，會在 init 階段自動建 `user_id=1` 的
   `dev@example.com`。production 關掉，改用 `scripts/bootstrap_user.py`
   顯式建你自己的帳號（記下 id）。
4. **gunicorn worker class = gevent**：SSE `/api/events/stream` 需要；
   別改成 sync。Dockerfile 已預設，Railway Start Command 不能改成 `sync`。
5. **frontend nginx 用 `${PORT}`**：Dockerfile.frontend 的 `scripts/frontend-entrypoint.sh`
   讀 `$PORT` 渲染 nginx config。Railway 自動注入，不用設。
6. **Railway tracking PR #15 branch**：本次故意用 `claude/remote-control-skill-CiYUW`
   不等 merge。PR review 通過 + merge 後，記得三個 service 都改 Source
   Branch = `main`，否則之後 main 上的修補不會自動 deploy。
7. **Custom domain TLS 簽證可能等 2–5 min**：Railway 用 Let's Encrypt，DNS
   propagate + ACME challenge 完成才會綠燈。先用 Railway 子域試通再切。
8. **`scripts/upload_videos.py` 用 `--user-id` 不需 cookie**：backend 的
   `current_user_id()` 有 backcompat（`app/utils/auth.py:94`），生產環境
   是否要關掉這條 backcompat 之後 Phase 4 再評估。
