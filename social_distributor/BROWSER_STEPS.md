# BROWSER_STEPS — 瀏覽器一路執行到「非你本人不可」的指令清單

> 用法：每一步給你**直達 URL**（點開就到該頁）+ **要貼進去的值**。
> 標示 🔴 = 你本人必須親手做（輸入密碼、勾選同意、按 Submit）。
> 標示 🟢 = 純複製貼上、無決策。
>
> 規則：完成每一步、把該頁產出的值貼回對話，我幫你貼下一步。
> 你不用記菜單路徑、不用找選單在哪。

---

## Phase 1 — Render 免費層部署（**現行路徑**）

> Railway 需要先充值 $5，本路徑改用 Render 完全免費起步。
> 限制：(a) Render Worker 要付費 → Phase 1–4 不開 worker，等 OAuth 過完
> 真正要 seed 時再升級。(b) Web Service idle 15 min 會 sleep → 對 OAuth
> 影響不大（reviewer 等 50s 沒差）。

### R1.1 🔴 開 Render 帳號
- URL：https://dashboard.render.com/register
- **用 GitHub 登入**（同 `milk790-code` 那個 GitHub 帳號）
- 完成後回來貼一句「Render 登入好了」

### R1.2 🟢 建 Postgres（Free 90 天）
- URL：https://dashboard.render.com/new/database
- Name = `popmonster-distributor-db`
- Database = 留空（用 default）
- User = 留空
- Region = **Singapore**（離台灣最近）
- PostgreSQL Version = 16
- Plan = **Free**
- 按 **Create Database**
- 等 ~1 min 變 Available
- **不用** 抄 URL；下面 Web Service 會自動 link 拿

### R1.3 🟢 建 Key Value（Redis-compat，25MB Free）
- URL：https://dashboard.render.com/new/keyvalue
- Name = `popmonster-distributor-redis`
- Region = **Singapore**（一定要和 Postgres 同區）
- Maxmemory Policy = `allkeys-lru`
- Plan = **Free**
- 按 **Create Key Value**

### R1.4 🟢 建 Web Service `api`
- URL：https://dashboard.render.com/select-repo?type=web
- 第一次會跳 GitHub 授權 → 允許 Render 讀 `milk790-code/popmonster-vip`
- 找到 `popmonster-vip` → **Connect**
- 然後在表單填：
  - Name = `popmonster-api`
  - Region = **Singapore**
  - Branch = `claude/remote-control-skill-CiYUW`
  - Root Directory = `social_distributor`
  - Runtime = **Docker**（會自動偵測 Dockerfile.backend）
  - Dockerfile Path = `./Dockerfile.backend`（相對於 Root Directory）
  - Docker Build Context Directory = `.`
  - Instance Type = **Free**
  - Health Check Path = `/healthz`
- **Start Command** 留空（Dockerfile 已寫好，但 Render 會傳 `$PORT`，
  Dockerfile.backend 的 CMD 已支援）
- **先別 Create**，往下走 R1.5 把 env 設完再 Deploy

### R1.5 🔴 設 `api` Environment Variables
在同一個表單下半部 → **Advanced** → **Add Environment Variable**，整批貼：

```
SECRET_KEY=e0686761307e8b3e9f51c92c1264e833e86e4eb3db40d11d33933e0a8a85d792
TOKEN_ENCRYPTION_KEY=EdrVxNsgkbiiqVJKtFu6BM2MwAzBEQ7vFNXUW6Ty9DA=
AUTO_SEED_USER=0
PUBLISH_DEFAULT_TIMEZONE=Asia/Taipei
MEDIA_BUCKET=popmonster-media
META_REDIRECT_URI=https://api.popmonster.vip/auth/meta/callback
TIKTOK_REDIRECT_URI=https://api.popmonster.vip/auth/tiktok/callback
```

然後**另外 4 個用 Render 內部 link**（不是貼字串、是用 "Add from Database"）：

- `DATABASE_URL` → 點 **Add from Database** → 選 `popmonster-distributor-db` →
  Property = `Internal Database URL`
- `REDIS_URL` → 點 **Add from Key Value** → 選 `popmonster-distributor-redis` →
  Property = `Internal Connection String`
- `CELERY_BROKER_URL` → 同上（同一個 Redis）
- `CELERY_RESULT_BACKEND` → 同上

按 **Create Web Service** → Render 開始 build（~5–8 min）

### R1.6 🟢 等 build 完，驗證 health
- Render 給你一個臨時 URL `https://popmonster-api-<hash>.onrender.com`
- 開 `https://popmonster-api-<hash>.onrender.com/healthz` → 期望 `{"status":"ok"}`
- 開 `https://popmonster-api-<hash>.onrender.com/healthz/ready` →
  **把整段 JSON 貼回給我**

期望 `database / redis / celery / encryption` 都是 `configured: true`。

### R1.7 🔴 Bootstrap initial User
- Render → `popmonster-api` service → **Shell** tab（free 也有 shell）
- 貼：
  ```
  python -m scripts.bootstrap_user --email <你的 email> --display-name "陳學誼" --timezone Asia/Taipei
  ```
- **把印出的 `user_id=N` 貼回給我**

### R1.8 🟢 Custom domain `api.popmonster.vip`
- Render → `popmonster-api` → **Settings** → 滑到 **Custom Domains** →
  **Add Custom Domain** → 填 `api.popmonster.vip`
- Render 給你一個 CNAME target（形如 `popmonster-api-<hash>.onrender.com`）
- **記住這個 target**，往下 R1.9 用

### R1.9 🔴 Cloudflare DNS：加 `api` CNAME
- URL：https://dash.cloudflare.com/?to=/:account/popmonster.vip/dns/records
- **Add record**：
  - Type = `CNAME`
  - Name = `api`
  - Target = （R1.8 拿到的那個 `<hash>.onrender.com`）
  - Proxy = **DNS only**（灰雲）
  - TTL = Auto
- **Save**
- 回 Render 等 2–5 min 看綠勾（Let's Encrypt 簽完）
- 開 `https://api.popmonster.vip/healthz` → `{"status":"ok"}` = 成功

### R1.10 ⏭ worker 暫不開
Phase 1–4 不需要。Phase 7 要 seed 時再決定升級。

---

## Phase 1.5 — Cloudflare R2（不變，同下方原 S2 段）

### R2.1 🔴 開 Cloudflare R2
- URL：https://dash.cloudflare.com/?to=/:account/r2/overview
- 第一次用 R2 要按 **Purchase R2 Plan**（前 10 GB 免費，超過按用量）
- 綁信用卡（🔴 你本人輸入）
- 完成後**貼一句「R2 開通好了」**

### R2.2 🟢 建 R2 bucket
- URL：https://dash.cloudflare.com/?to=/:account/r2/new
- Bucket Name = `popmonster-media`
- Location = **Automatic**
- Default Storage Class = **Standard**
- 按 **Create bucket**

### R2.3 🔴 建 R2 API Token
- URL：https://dash.cloudflare.com/?to=/:account/r2/api-tokens
- 按 **Create API Token**
- Token name = `popmonster-distributor-prod`
- Permissions = **Object Read & Write**
- Specify bucket = `popmonster-media`
- 按 **Create API Token**
- 🔴 **這頁只會出現一次**：拷貝 `Access Key ID` / `Secret Access Key` /
  `S3 API Endpoint URL` 三個值貼回對話

### R2.4 🟢 回 Render 補 R2 env
- Render → `popmonster-api` → Environment → Add 4 個：
  ```
  AWS_ACCESS_KEY_ID=<R2.3 拿到>
  AWS_SECRET_ACCESS_KEY=<R2.3 拿到>
  AWS_REGION=auto
  S3_ENDPOINT_URL=https://<account>.r2.cloudflarestorage.com
  ```
- 自動 redeploy
- 回 `/healthz/ready` 確認 `media_bucket.configured=true`

### R2.5 🟢 R2 CORS
- URL：https://dash.cloudflare.com/?to=/:account/r2/popmonster-media/settings
- **CORS Policy** → **Edit** → 貼：
  ```json
  [{
    "AllowedOrigins":["https://api.popmonster.vip"],
    "AllowedMethods":["GET","PUT"],
    "AllowedHeaders":["*"],
    "ExposeHeaders":["ETag"],
    "MaxAgeSeconds":3600
  }]
  ```
- **Save**

---

## Phase 4 — OAuth onboarding（這段最久，越早開始越好）— 見下方原 S3 / S4 段

---

# 以下為原 Railway 路徑（不再使用，保留作參考）

## Phase 1 — Railway 部署（先做這段）

### S1.1 🔴 開 Railway 帳號（如果還沒有）
- URL：https://railway.app/login
- 用 GitHub 登入（綁 `milk790-code` 的那個 GitHub 帳號）
- 完成後**回來貼一句「Railway 登入好了」**

### S1.2 🔴 從 GitHub repo 建專案
- URL：https://railway.com/new
- 點 **Deploy from GitHub repo**
- 第一次用要授權 Railway 讀 `milk790-code/popmonster-vip`（GitHub 會跳轉確認）
- 選 repo：**popmonster-vip**
- **不要** 讓它自動 detect → 跳出時選 **"Empty Service"** 或直接關掉 Auto Deploy
- 完成後**貼專案 URL 給我**（形如 `https://railway.com/project/<uuid>`）

### S1.3 🟢 加 Postgres plugin
- 在剛建的專案頁 → 右上 **+ New** → **Database** → **PostgreSQL**
- 不用設定，等右下角 plugin 變 Active

### S1.4 🟢 加 Redis plugin
- 同位置 **+ New** → **Database** → **Redis**
- 等 Active

### S1.5 🟢 加 `api` service
- **+ New** → **GitHub Repo** → 選 `milk790-code/popmonster-vip`
- Service 取名 `api`
- 進 service → **Settings**：
  - Source → Repo Branch = `claude/remote-control-skill-CiYUW`
  - Root Directory = `social_distributor`
  - Dockerfile Path = `Dockerfile.backend`
- **Start Command**（複製貼上）：
  ```
  gunicorn -k gevent -w 2 --worker-connections 100 --timeout 120 -b 0.0.0.0:$PORT run:app
  ```
- **先別 Deploy**，往下走 S1.6 把 env 設完再 deploy

### S1.6 🔴 設 `api` service Variables
進 service → **Variables** → **Raw Editor**，整批貼下面（**🔴 兩個密鑰你必須先在本機生成**）：

```
SECRET_KEY=<🔴 本機跑：python3 -c "import secrets; print(secrets.token_hex(32))" 把輸出貼這>
TOKEN_ENCRYPTION_KEY=<🔴 本機跑：python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())" 把輸出貼這>
DATABASE_URL=${{Postgres.DATABASE_URL}}
REDIS_URL=${{Redis.REDIS_URL}}
CELERY_BROKER_URL=${{Redis.REDIS_URL}}
CELERY_RESULT_BACKEND=${{Redis.REDIS_URL}}
AUTO_SEED_USER=0
PUBLISH_DEFAULT_TIMEZONE=Asia/Taipei
MEDIA_BUCKET=popmonster-media
META_REDIRECT_URI=https://api.popmonster.vip/auth/meta/callback
TIKTOK_REDIRECT_URI=https://api.popmonster.vip/auth/tiktok/callback
```

> 兩個 OAuth ID/SECRET、R2 keys、AWS_REGION、S3_ENDPOINT_URL 留空 — Phase 4 / S2 才填

### S1.7 🟢 加 `worker` service
- **+ New** → **GitHub Repo** → 同 repo
- Service 取名 `worker`
- Settings 同 S1.5（branch、root、Dockerfile）
- **Start Command**：
  ```
  celery -A celery_worker.celery worker -B -l info
  ```
- Variables 用 **Reference all from api**（Railway 右上有按鈕）
- Settings → Networking → **關掉 Public Networking**（worker 不開 HTTP）

### S1.8 🟢 加 `frontend` service
- **+ New** → **GitHub Repo** → 同 repo
- Service 取名 `frontend`
- Settings：
  - Branch / Root 同 api
  - **Dockerfile Path = `Dockerfile.frontend`**
- Variables（Raw Editor 貼）：
  ```
  API_BASE_URL=https://api.popmonster.vip
  CACHE_VERSION=v1
  ```

### S1.9 🔴 Deploy 三個 service
- 回專案總覽 → 每個 service 右上 **Deploy**
- 等 5–8 min build
- 三個都 Active 後**貼一句「三個 service 都 Active」**，附 `api` 的臨時 URL

### S1.10 🟢 健康檢查（自動，把 URL 點開貼回結果）
- `https://<api 臨時 url>/healthz` → 期望 `{"status":"ok"}`
- `https://<api 臨時 url>/healthz/ready` → **整段 JSON 貼回給我**

期望看到 `database / redis / celery / encryption` 都是 `configured: true`。

---

## Phase 1.5 — Cloudflare R2 + Custom Domain

### S2.1 🔴 開 Cloudflare R2（如果還沒開）
- URL：https://dash.cloudflare.com/?to=/:account/r2/overview
- 第一次用 R2 要按 **Purchase R2 Plan**（前 10 GB 免費，超過按用量）
- 綁信用卡（🔴 你本人輸入）
- 完成後**貼一句「R2 開通好了」**

### S2.2 🟢 建 R2 bucket
- URL：https://dash.cloudflare.com/?to=/:account/r2/new
- Bucket Name = `popmonster-media`
- Location = **Automatic**
- Default Storage Class = **Standard**
- 按 **Create bucket**

### S2.3 🔴 建 R2 API Token
- URL：https://dash.cloudflare.com/?to=/:account/r2/api-tokens
- 按 **Create API Token**
- Token name = `popmonster-distributor-prod`
- Permissions = **Object Read & Write**
- Specify bucket = `popmonster-media`
- 按 **Create API Token**
- 🔴 **這頁只會出現一次**：拷貝 `Access Key ID` / `Secret Access Key` /
  `S3 API Endpoint URL` 三個值貼回對話。我幫你貼回 Railway env。

### S2.4 🟢 R2 CORS 設定
- URL：https://dash.cloudflare.com/?to=/:account/r2/popmonster-media/settings
- 滑到 **CORS Policy** → **Edit CORS Policy** → 貼下面 JSON：
  ```json
  [{
    "AllowedOrigins":["https://api.popmonster.vip","https://app.popmonster.vip"],
    "AllowedMethods":["GET","PUT"],
    "AllowedHeaders":["*"],
    "ExposeHeaders":["ETag"],
    "MaxAgeSeconds":3600
  }]
  ```
- **Save**

### S2.5 🔴 Cloudflare DNS：加 `api` CNAME
- URL：https://dash.cloudflare.com/?to=/:account/popmonster.vip/dns/records
- 按 **Add record**：
  - Type = `CNAME`
  - Name = `api`
  - Target = （Railway 的 api service Custom Domain 設定頁會給你的 `<hash>.up.railway.app`）
  - Proxy status = **DNS only**（灰雲，不要橘雲）
  - TTL = Auto
- 按 **Save**

### S2.6 🔴 Cloudflare DNS：加 `app` CNAME
- 同頁 **Add record**：
  - Type = `CNAME`
  - Name = `app`
  - Target = （Railway 的 frontend service Custom Domain 給的 `<hash>.up.railway.app`）
  - Proxy status = **DNS only**
- **Save**

### S2.7 🟢 Railway 綁 custom domain
- `api` service → Settings → Networking → Custom Domain → `api.popmonster.vip` → Add
- `frontend` service → 同上 → `app.popmonster.vip`
- Railway 會給你 CNAME target，回去 S2.5 / S2.6 把 Target 換對
- 等 2–5 min 看到綠勾 = TLS 簽好

### S2.8 🟢 驗收
- `https://api.popmonster.vip/healthz` → `{"status":"ok"}`
- `https://api.popmonster.vip/healthz/ready` → JSON 貼回給我
- `https://app.popmonster.vip/login` → 看到 magic-link 登入頁

---

## Phase 4 — OAuth onboarding（這段最久，越早開始越好）

### S3.1 🔴 Meta Developer 建 App
- URL：https://developers.facebook.com/apps/creation/
- 用個人 Facebook 登入
- App Type = **Business**
- App Name = `PopMonster Distributor`
- App Contact Email = 你的 email
- 按 **Create App**（會要求重新輸入 FB 密碼 🔴）
- 完成後**貼 App ID 給我**

### S3.2 🟢 Meta：加 Products
建好 App 後在 Dashboard：
- **Facebook Login for Business** → Set Up
- **Instagram Graph API** → Set Up
- **Pages API** → 自動帶入

### S3.3 🟢 Meta：設 Redirect URI
- 左側 → Facebook Login → Settings
- Valid OAuth Redirect URIs = `https://api.popmonster.vip/auth/meta/callback`
- Save Changes

### S3.4 🔴 Meta：補商業驗證 + 送 App Review
- Settings → Basic → 填 Privacy Policy URL = `https://popmonster.vip/privacy.html`
- 填 Terms of Service URL = `https://popmonster.vip/terms.html`
- 填 App Icon、Category = Business and Pages
- 按左側 **App Review** → **Permissions and Features**
- 申請以下 scope（每個都要錄一段示範影片 🔴）：
  - `pages_show_list`
  - `pages_manage_posts`
  - `pages_read_engagement`
  - `instagram_basic`
  - `instagram_content_publish`
- **Submit for Review**
- ⏰ 1–2 週

### S3.5 🔴 Meta：拿 App ID / App Secret
- Settings → Basic
- 把 `App ID` 貼給我 → 進 Railway api / worker env `META_APP_ID`
- 按 App Secret 旁邊 **Show**（🔴 要重輸 FB 密碼）→ 貼給我 → 進 `META_APP_SECRET`

### S4.1 🔴 TikTok Developer 建 App
- URL：https://developers.tiktok.com/apps
- 用 TikTok 帳號登入
- **Connect an App**
- App Name = `PopMonster Distributor`
- Category = Business / Marketing
- 描述 = （我幫你寫好放下面）

### S4.2 🟢 TikTok：加 Products
- Login Kit → Add
- Content Posting API → Add

### S4.3 🟢 TikTok：設 Redirect URI
- App Settings → Login Kit → Redirect URI = `https://api.popmonster.vip/auth/tiktok/callback`
- Scopes：勾 `user.info.basic`、`video.upload`、`video.publish`

### S4.4 🔴 TikTok：送 Audit
- App → **Submit for Review**
- ⏰ 2–4 週（瓶頸）
- 通過後**貼 Client Key / Client Secret 給我**

---

## Phase T — Threads OAuth（3Q LINE OA 用）

> **背景**：Threads API 只能掛在「消費者 (Consumer)」類型的 Meta App 上，不能掛在商業 (Business) 類型的 App 上。  
> 現有的 `956987317313843`（popmonster-distributor-v2）和 `1845315733092457`（3q-hatchery-）都是 Business 類型，無法使用 Threads API。  
> 需要新建一個 Consumer App，專門給 3Q LINE OA 的 Threads 自動換 token 用。

### T1 🔴 建立 Consumer 類型 Meta App

直連 URL：`https://developers.facebook.com/apps/create/`

操作步驟：
1. 進入頁面後 **App Type** 選 **「消費者 (Consumer)」** ← 這一步是關鍵，不能選「企業商家 (Business)」
2. App 名稱：

```
3q-threads-consumer
```

3. Contact email 填你的信箱（自動帶入）
4. 點 **建立應用程式** → 系統可能要求輸入 Meta 密碼 🔴
5. 建立成功後，**把 App ID 貼回給我**

### T2 🟢 加 Threads API 產品（T1 完成後我來提示你）

- 在新 App 的 Dashboard 左側：**Add Product** → 找到 **Threads API** → 點 **Set Up**
- （如果 Add Product 清單裡看不到 Threads API，代表 App Type 選錯了，請刪除重建）

### T3 🟢 設 OAuth Redirect URI

位置：Threads API → Settings（設定頁）

**Valid OAuth Redirect URI** 填入：

```
https://milk790-code.github.io/3q-hatchery-line-oa/assets/threads-auth.html
```

點 **Save**。

### T4 🔴 取得 App Secret

- App Dashboard → **Settings → Basic**
- 在 **App Secret** 欄位按 **Show** → 系統要求輸入 Meta 密碼 🔴
- 複製後**把 App ID + App Secret 一起貼回給我**

### T5 🟢（我來做）更新 3Q LINE OA 相關設定

拿到 T1 的 App ID + T4 的 App Secret 之後，我自動完成：

1. `3q-hatchery-line-oa/assets/threads-auth.html` 的 `APP_ID` 更新
2. `.github/workflows/threads-token-setup.yml` 的 `THREADS_APP_ID` 更新
3. 呼叫 GitHub API 把 `THREADS_APP_SECRET` 寫入 GitHub Secret（取代舊的）
4. 推送到 main 分支並 dispatch workflow 完成首次 token 換取

---

## 走到這裡你會擁有

✅ 一個生產 backend `https://api.popmonster.vip`
✅ 前端 magic-link 登入頁 `https://app.popmonster.vip`
✅ 三個平台 OAuth ID/Secret 可以連社群帳號
✅ R2 bucket 可以收 5 支影片
✅ （Phase T 完成後）Threads 自動換 token → 3Q LINE OA Threads 帳號接入

→ 接著走 `RUNBOOK_SEED_SPRINT.md` Phase 5–8（建 AccountGroup、上傳影片、seed、worker）
