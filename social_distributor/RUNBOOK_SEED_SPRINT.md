# Runbook：真正操作 seed_sprint_v1 一次（從零到第一波發文）

> 對應 script：[`backend/scripts/seed_sprint_v1.py`](backend/scripts/seed_sprint_v1.py)
> 預檢工具：[`backend/scripts/preflight_seed_sprint.py`](backend/scripts/preflight_seed_sprint.py)
> Phase 2 一鍵：[`backend/scripts/bootstrap_user.py`](backend/scripts/bootstrap_user.py)
> Phase 6 一鍵：[`backend/scripts/upload_videos.py`](backend/scripts/upload_videos.py)

## Context

把「汽美短影音爆款衝刺包 v1.0」5 張卡 × 3 平台（FB / IG / TT）= 15 條
PostTarget seed 進 `social_distributor`，讓 Celery beat 的 `sweep_due_targets`
在 2026-05-17 → 05-21 各個 21:00 / 20:30 Asia/Taipei 自動發文。

**首次跑的時間現實：**
- TikTok Content Posting API 需 audit，**通常 2–4 週**
- Meta App 需 Business Verification + IG Business 綁定 FB Page，**通常 1–2 週**

因此第一次跑分兩條路：
- **路徑 A（救火）**：前面幾張卡到時間時，手動發 + `remote-control` skill 收 24h 三件套尾
- **路徑 B（這週起跑、未來自動化）**：pipeline 建好後，最晚卡 4 / 卡 5 接上自動化

---

## 路徑 A — 該卡到時間時手動發

1. 到時間前 30 min 在主對話打 `夜班啟動` 觸發 `remote-control` skill，把該卡
   的影片 + 文案（見 `backend/scripts/seed_sprint_v1.py` `CARDS` list）丟給 skill
2. 三平台同步發（FB Page / IG Reels / TikTok）
3. 24h 三件套：跨平台留言鏡像、私訊回覆、互動截圖
4. （可選）把實際發文 URL 填回 `media_assets` 對應的 `external_post_id`，
   讓之後 insights 串得起來

---

## 路徑 B — 官方 pipeline 完整建立

### Phase 1：部署 backend

詳細 12 步部署清單（含 R2 + frontend + custom domain）見
**[`RUNBOOK_PHASE1_RAILWAY.md`](RUNBOOK_PHASE1_RAILWAY.md)**。

選一條最快的：

| 方案 | 時間 | 適用 |
|---|---|---|
| Railway（推薦） | 30–60 min | DB + Redis + worker 一次給齊；走 RUNBOOK_PHASE1_RAILWAY.md |
| Docker compose（本機常開） | 1 hr | 本機長開；OAuth 需 ngrok 暴露 |
| Docker compose + VPS | 2 hr | 已有 Hetzner / Linode |

**Railway 路線**（看 [`RAILWAY.md`](RAILWAY.md) + [`RUNBOOK_PHASE1_RAILWAY.md`](RUNBOOK_PHASE1_RAILWAY.md)）：
1. Railway 新建專案，連 GitHub repo，root path = `social_distributor`
2. 三個 service：
   - `api`：Dockerfile = `Dockerfile.backend`，start cmd = `gunicorn -k gevent -w 2 -b 0.0.0.0:$PORT run:app`
   - `worker`：同 image，start cmd = `celery -A celery_worker.celery worker -B -l info`
   - `db`：Railway Postgres plugin
   - `redis`：Railway Redis plugin
3. 設 env（見 Phase 3）
4. Deploy，等 `/healthz` 回 200

### Phase 2：建初始 User（一鍵）

```bash
# Railway shell 或本機 backend
cd social_distributor/backend
python -m scripts.bootstrap_user --email milk790@example.com --display-name "陳學誼" --timezone Asia/Taipei
# → 印出 user_id=N，記下來
```

腳本會 idempotent — 同 email 已存在就回該 user 的 id，不重複建。

### Phase 3：env 設好

**硬需求：**

```bash
SECRET_KEY=$(python -c 'import secrets; print(secrets.token_hex(32))')
TOKEN_ENCRYPTION_KEY=$(python -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())')
DATABASE_URL=postgresql+psycopg2://...   # Railway plugin 自動帶
REDIS_URL=redis://...                     # Railway plugin 自動帶
CELERY_BROKER_URL=$REDIS_URL/1
CELERY_RESULT_BACKEND=$REDIS_URL/2
MEDIA_BUCKET=popmonster-media
AWS_ACCESS_KEY_ID=<S3 / R2 key>
AWS_SECRET_ACCESS_KEY=<S3 / R2 secret>
AWS_REGION=us-east-1
S3_ENDPOINT_URL=        # R2 才需要；AWS S3 留空
```

**OAuth（Phase 4 之後填）：**

```bash
META_APP_ID=
META_APP_SECRET=
META_REDIRECT_URI=https://<railway-app>/auth/meta/callback
TIKTOK_CLIENT_KEY=
TIKTOK_CLIENT_SECRET=
TIKTOK_REDIRECT_URI=https://<railway-app>/auth/tiktok/callback
```

**soft skip（缺也能跑）：** `ANTHROPIC_API_KEY`、`PERSPECTIVE_API_KEY`、
`SENDGRID_API_KEY`、`ENABLE_TRANSCODE=0`（worker 沒 ffmpeg 時設 0 用原檔發）

### Phase 4：OAuth onboarding（最大不確定性）

兩條平行做：

**Meta（FB Page + IG Business）— 1~2 週**
1. https://developers.facebook.com/apps/ 建新 App，type = Business
2. 開啟產品：Facebook Login、Instagram Graph API、Pages API
3. 加 scope：`pages_show_list`、`pages_manage_posts`、`pages_read_engagement`、
   `instagram_basic`、`instagram_content_publish`
4. OAuth Redirect URI = `https://<railway-app>/auth/meta/callback`
5. **送 App Review**（瓶頸 — 要錄影示範每個 scope 的使用情境）
6. 通過後前端 `/login` Magic Link 登入 → 點「連結 Facebook」→ 授權 →
   `app/auth/routes.py` `_persist_accounts("meta", ...)` 把每個 FB Page 寫成
   一個 `SocialAccount`，IG 透過 `instagram_business_account` 探測加入
7. IG Business 必須事先綁定到某個 FB Page

**TikTok Content Posting API — 2~4 週**
1. https://developers.tiktok.com/ → 建 App
2. 產品：Login Kit、Content Posting API
3. scope：`user.info.basic`、`video.upload`、`video.publish`
4. Redirect URI = `https://<railway-app>/auth/tiktok/callback`
5. **送 Audit**（更久 — TikTok 要看商業用途說明）
6. 通過後前端授權

**驗收：**

```python
# flask --app run.py shell
from app.models import SocialAccount
for a in SocialAccount.query.filter_by(revoked_at=None):
    print(a.id, a.platform, a.handle)
# 期望至少 1 個 facebook、1 個 instagram、1 個 tiktok
```

### Phase 5：建「PopMonster 主推」AccountGroup

OAuth 完，三個 `SocialAccount` 都在 DB 之後，flask shell：

```python
from app.extensions import db
from app.models import AccountGroup, SocialAccount
fb = SocialAccount.query.filter_by(platform="facebook").first()
ig = SocialAccount.query.filter_by(platform="instagram").first()
tt = SocialAccount.query.filter_by(platform="tiktok").first()
g = AccountGroup(user_id=fb.user_id, name="PopMonster 主推", default_timezone="Asia/Taipei")
g.accounts = [fb, ig, tt]
db.session.add(g); db.session.commit()
print("group_id =", g.id)
```

或 `POST /api/groups`（看 `app/api/groups.py:54`）。

### Phase 6：上傳 5 支影片（一鍵）

```bash
cd social_distributor/backend
# 先在 frontend /login 走完 magic-link，從 browser DevTools 抓 session cookie
python -m scripts.upload_videos \
  --backend-url https://<railway-app> \
  --cookie "session=<value>" \
  card1.mp4 card2.mp4 card3.mp4 card4.mp4 card5.mp4
# → 依序印出 5 個 media_id
```

**關鍵：等 transcode 完**

```python
# flask shell
from app.models import MediaAsset
for m in MediaAsset.query.order_by(MediaAsset.id.desc()).limit(5):
    print(m.id, m.transcode_status, m.derivatives)
# 全部要 == "ready"
```

worker 環境沒 ffmpeg → env 設 `ENABLE_TRANSCODE=0`，接受原檔發；1080×1920
已是 9:16 應該還 OK。

### Phase 7：真正執行 seed

```bash
cd social_distributor/backend

# 1. 編輯 MEDIA_MANIFEST：把 5 個 None 換成 Phase 6 拿到的 media_id
$EDITOR scripts/seed_sprint_v1.py

# 2. dry-run 預覽
python -m scripts.seed_sprint_v1 --dry-run
# 確認 5 個 200 OK、各帶 3 條 plan、時間正確、平台對

# 3. 正式 seed
python -m scripts.seed_sprint_v1
# → 5 個 post_id + 15 個 created_target_ids
```

### Phase 8：起 worker

Phase 1 worker service 已跑著就跳過。否則：

```bash
celery -A celery_worker.celery worker -B -l info
```

---

## 驗收

**發文後 5 分鐘內：**

```python
# flask shell
from app.models import PostTarget
for t in PostTarget.query.order_by(PostTarget.id.desc()).limit(15):
    print(t.id, t.status, t.scheduled_for, t.external_post_id, t.error_message)
```

- `succeeded` + `external_post_id` → 真的發了
- `failed` + `error_message` → 看 worker log
- `rejected_compliance` → caption 觸發規則，`POST /api/posts/{id}/preview-compliance` 預檢
- `queued` 卡 > 5 min → worker 沒在跑 / rate limit

**眼見為憑：** 三個官方 App 各看 feed 最新一則 + 手動置頂第一則留言。

---

## Gotchas

1. **TikTok Audit 是最長路徑** — 別卡在這之前才開始申請。
2. **IG Business 必須綁到 FB Page** — 個人 IG 用不了 Graph API publish。
3. **transcode pending 就 seed**：TikTok / IG 拿到原檔；務必等 `transcode_status=ready`
   或 `ENABLE_TRANSCODE=0` 接受原檔。
4. **compliance 在 dispatch 才檢**：`distribute` POST 過了不代表會發；worker
   才會 reject。卡 1 caption 有「打 1 我私訊你」可能被視為 engagement bait，
   觀察 `compliance_checks` 表。
5. **時區陷阱**：seed 寫的是 local time + `timezone="Asia/Taipei"`，worker 比
   `scheduled_for` 是 UTC。preflight 已驗證 21:00 Taipei = 13:00 UTC。
   別在 .env 改 `PUBLISH_DEFAULT_TIMEZONE`。
6. **rate limit**：FB 200/hr、IG 50/24h、TikTok 30/day。15 條遠低於上限。
7. **/api/uploads/complete 需 session cookie**：純 curl 要先 magic-link 登入
   拿 cookie，或用 frontend `/login` 走完一次。
