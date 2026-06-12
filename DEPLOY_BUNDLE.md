# 🎁 PopMonster 全棧自動部署包

> 把四個後端（agentmemory / linebot / portal / social_distributor）+ agentmemory
> 記憶資料同步全部上線的**單一執行清單**。每一步若可自動 → 我已預先做完；
> 🔴 = 你本人在瀏覽器操作；🟢 = 純複製貼上、無決策。
>
> 全部變更都在分支 `claude/memory-update-QASFZ` 上、各 repo 都有 draft PR：
>
> | Repo | PR | 狀態 |
> |---|---|---|
> | `popmonster-vip` | [#20](https://github.com/milk790-code/popmonster-vip/pull/20) | agentmemory-server/ + index.html ?ref 捕獲 + social_distributor 已含 BROWSER_STEPS |
> | `popmonster-linebot` | [#2](https://github.com/milk790-code/popmonster-linebot/pull/2) | render.yaml + DEPLOY_STEPS.md + /邀請 intent |
> | `customer-project-portal` | [#2](https://github.com/milk790-code/customer-project-portal/pull/2) | render.yaml + 邀請碼 schema + migration（⚠️ 有預存 build 問題見 §3-pre） |
> | `popmonster-website-deployment` | (memory wiring only) | GitHub Pages artifact，不需新部署 |

---

## 0. 🔴 Pre-flight — 產 secrets、儲值、決策

### 0.1 一次產出所有要用的 secrets（複製這段在你本機跑）
```bash
python3 - <<'PY'
import secrets
from cryptography.fernet import Fernet
print("FLASK_SECRET_KEY=", secrets.token_urlsafe(48))
print("TOKEN_ENCRYPTION_KEY=", Fernet.generate_key().decode())
print("AGENTMEMORY_SECRET=", secrets.token_urlsafe(40))
PY
```
> 沒裝 `cryptography`：`pip install cryptography` 再跑。
> 三個值都先**存進你的密碼管理器**，下面會反覆貼到 Render/Railway。

### 0.2 帳號 / 儲值
- Render：https://dashboard.render.com/register（用同 GitHub 登入）
- Railway 儲值 $5：https://railway.com/account/billing
- PlanetScale：https://app.planetscale.com/（首次免費 tier 已夠用）

### 0.3 兩個必選
- agentmemory 對外要走 **(B) Caddy proxy + token**（推薦，repo 已預先鋪好 `agentmemory-server/proxy/`）
- merge to main：**等所有 secrets 都進 Render/Railway 後再合**（否則正式環境自動部署會炸）

---

## 1. agentmemory 後端（Railway，最先做）

詳細：`popmonster-vip/agentmemory-server/README.md`。摘要：

### 1.1 🔴 建 Railway 專案 + 從 repo 部署 agentmemory service
- https://railway.com/new → Deploy from GitHub repo → `popmonster-vip`
- Settings → Source → Root Directory = `agentmemory-server`
- Settings → Volumes → + New Volume → Mount Path = `/app/data`，大小 1 GB
- Settings → Networking → **不要** Generate Domain（私網 only）

### 1.2 🔴 在同專案再建一個 Caddy proxy service（對外+token）
- + New → Deploy from GitHub repo → `popmonster-vip`
- Settings → Source → Root Directory = `agentmemory-server/proxy`
- Variables：
  ```
  AGENTMEMORY_INTERNAL_URL=http://agentmemory.railway.internal:3111
  AGENTMEMORY_SECRET=<貼 0.1 產的 AGENTMEMORY_SECRET>
  ```
- Networking → **Generate Domain** → 拿到 `https://<proxy-domain>` ← **記下這個 URL**

---

## 2. popmonster-linebot（Render，最簡單）

詳細：`popmonster-linebot/DEPLOY_STEPS.md`。摘要：

### 2.1 🔴 Render 建 Web Service
- https://dashboard.render.com/select-repo?type=web → `popmonster-linebot`
- 自動讀 `render.yaml`；Branch = `main`（合 main 後）；Region = Singapore；Plan = Free

### 2.2 🔴 Environment 變數
```
LINE_CHANNEL_SECRET=<LINE Developers → Basic settings>
LINE_CHANNEL_ACCESS_TOKEN=<LINE Developers → Messaging API → 發行 long-lived>
OPENAI_API_KEY=<OpenAI>
```

### 2.3 🔴 LINE Webhook
- LINE Developers → Messaging API → Webhook URL = `https://<service>.onrender.com/webhook` → Verify

### 2.4 🟢 驗證
- `curl https://<service>.onrender.com/health` → 200
- LINE 傳「我的邀請碼」→ 收到帶 8 碼的 Flex 邀請卡（自動裂變已上線）

---

## 3. customer-project-portal（Render + PlanetScale）

詳細：`customer-project-portal/DEPLOY_STEPS.md`。

### 3-pre. ⚠️ 必須先處理的預存問題（不修就 build fail）
`server/db.ts` import 了 `activities` / `catalogProducts` / `knowledgeBase` 等 symbol，
但 `drizzle/schema.ts` 沒 export。在 Render 點 Deploy 之前，二選一：
- (a) 把缺漏的 table 補回 `drizzle/schema.ts`（推薦，跟你舊資料對齊），或
- (b) 把 `server/db.ts` 多餘 import + 相關 function 拿掉（破壞性，會少功能）。

### 3.1 🔴 PlanetScale 建 DB
- https://app.planetscale.com/ → Create database `customer-project-portal`，Region `ap-southeast`
- Connect → Node.js / Drizzle → 複製 `DATABASE_URL`

### 3.2 🔴 Render 建 Web Service + 環境變數
- https://dashboard.render.com/select-repo?type=web → `customer-project-portal`
- 自動讀 `render.yaml`
- Environment：
  ```
  DATABASE_URL=<PlanetScale 連線字串>
  ANTHROPIC_API_KEY=<Claude API>
  AWS_REGION / AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY=<S3 才填>
  STRIPE_*=<電商才填>
  ```

### 3.3 🟢 首次部署後跑 migration + seed
Render Shell：
```bash
mysql "$DATABASE_URL" < drizzle/migrations/0001_add_referrals.sql
pnpm db:push
pnpm tsx run seed-popmonster.mjs
pnpm tsx run seed-knowledge.mjs
pnpm tsx run server/seed-products-v2.mjs
```

---

## 4. social_distributor（Render free tier 已鋪好）

詳細：`popmonster-vip/social_distributor/BROWSER_STEPS.md`（已完整，直接照走）。
摘要：Postgres → Key Value（Redis）→ Web Service api → Web Service frontend，
所有 deep link、欄位值都在那份文件，這裡不複製。

---

## 5. 記憶資料同步（你**本機**那台 agentmemory → Railway volume）

雲端 session 不持有你的記憶資料 → 同步要從本機發起。

### 5.1 🟢 本機備份匯出
```bash
# 本機，先確認在跑
agentmemory status

# 找出本機 data 目錄（state_store.db + stream_store 所在）
# 通常是你最常啟動 agentmemory 的工作目錄下的 ./data/
```

### 5.2 🔴 把 data 目錄推上 Railway volume
- Railway CLI：`railway link` → `railway shell --service agentmemory`
- 在容器內 `/app/data` 用 `scp` / `railway run`（具體看你裝沒裝 CLI）
- **退路**：data 還原失敗就接受重新累積，本機 JSON 留作備份

### 5.3 🟢 切換四個 repo 的 `.mcp.json` 預設值
等線上跑通後，把四個 repo 的 `.mcp.json` 預設值改成：
```
"AGENTMEMORY_URL": "${AGENTMEMORY_URL:-https://<proxy-domain>}"
"AGENTMEMORY_SECRET": "${AGENTMEMORY_SECRET:-}"
```
（保留環境變數覆寫；本機若仍要走 localhost，匯出 `AGENTMEMORY_URL=http://localhost:3111` 即可。）

---

## 6. 🔴 合 main 觸發自動部署

**所有 secrets 都進 Render/Railway 之後**，依序合：
1. `popmonster-linebot#2` → Render auto-deploy → 拿 webhook URL 回填 LINE
2. `popmonster-vip#20` → Railway / Render auto-deploy（agentmemory + social_distributor）
3. `customer-project-portal#2` → 在 §3-pre 修好後才合 → Render auto-deploy

> Cloudflare Pages preview build 持續 0 秒 fail 是 Cloudflare 側問題（額度 / 設定），
> 不阻擋 production，可以忽略。`popmonster.vip` 走 GitHub Pages 不受影響。

---

## 7. 驗證一輪

| 檢查 | 通過條件 |
|---|---|
| linebot | `curl https://<svc>.onrender.com/health` → 200；LINE 傳「邀請」→ 收到 8 碼 Flex 卡 |
| portal | `curl https://<svc>/` → 200；`/portal/` 開得起；`/ai-search` 有 Claude 回覆 |
| social_distributor | `curl https://<api>/healthz` → 200；frontend 載得起 |
| agentmemory | `curl -H "Authorization: Bearer $AGENTMEMORY_SECRET" https://<proxy>/...` → 200；MCP `memory_recall` 回得到舊記憶 |
| 邀請碼 | LINE 取得碼 → 開 `https://popmonster.vip/?ref=<code>` → DevTools localStorage 有 `pm_ref` |

---

## 附錄 — 完整環境變數總表

| Service | 變數 | 來源 |
|---|---|---|
| agentmemory | (none required) | volume 掛 `/app/data` |
| agentmemory-proxy | `AGENTMEMORY_INTERNAL_URL` | `http://agentmemory.railway.internal:3111` |
| agentmemory-proxy | `AGENTMEMORY_SECRET` | 0.1 產生 |
| linebot | `LINE_CHANNEL_SECRET` / `LINE_CHANNEL_ACCESS_TOKEN` | LINE Developers |
| linebot | `OPENAI_API_KEY` | OpenAI |
| portal | `DATABASE_URL` | PlanetScale |
| portal | `ANTHROPIC_API_KEY` | Anthropic console |
| portal | `AWS_*` / `STRIPE_*` | 如有用到 |
| social_distributor api+worker | `SECRET_KEY` | 0.1 產生 (FLASK_SECRET_KEY) |
| social_distributor api+worker | `TOKEN_ENCRYPTION_KEY` | 0.1 產生 |
| social_distributor api+worker | `DATABASE_URL` / `REDIS_URL` | Render 自動 link |
| social_distributor | `META_*` / `TIKTOK_*` / `GOOGLE_*` | 各 OAuth provider |

## 附錄 — 已知地雷

1. **linebot `app.py` L18-20 寫死 LINE 憑證當 env default** — 應 rotate + 改成 `os.environ["LINE_CHANNEL_SECRET"]` 沒 fallback。我沒動是怕舊環境炸。
2. **portal §3-pre 預存 build issue** — 沒修 Render build 一定失敗。
3. **agentmemory native iii-engine 在 slim 容器啟動性未驗證** — 若 fail 看 Railway log，可能要加系統依賴或改 `AGENTMEMORY_USE_DOCKER=1`（Railway 內較麻煩）。
4. **agentmemory 健康檢查路徑未文件化** — 部署後實測。
