# 多租戶架構評估 · Social Distributor

> 目的：支撐「內部引擎 vs 服務商產品」的定位拍板。  
> 讓學誼用工程量數字做決策，而不是空談架構。

---

## 當前狀態（單租戶）

| 項目 | 現況 |
|---|---|
| 用戶識別 | `user_id=1` 寫死在多處；`AUTO_SEED_USER` 自動建第一個 User |
| Token 隔離 | `SocialAccount.user_id` FK 存在，但 API 層有些路由未嚴格過濾 |
| 計費 | 無 |
| 帳號數 | 1 個 User，59 個 SocialAccount（估計） |
| 部署 | Railway 單容器（api + worker） |

---

## 改動點清單

### 1. 資料模型（Models）

| 表 | 需要加的欄位 | 工時估計 |
|---|---|---|
| `users` | 無（已有 User model） | — |
| `social_accounts` | 已有 `user_id` FK，**但要驗全部 query 都帶 WHERE user_id=** | 0.5 天審計 |
| `account_groups` | 已有 `user_id` FK | 驗 query 一致性 |
| `posts` | 已有 `user_id` FK | 同上 |
| `post_targets` | 透過 `posts.user_id` 間接隔離，需補直接 FK 或 JOIN 檢查 | 半天 |
| 新增 `tenants` 表 | `id, name, plan, created_at, stripe_customer_id` | 0.5 天 |
| `users` | 加 `tenant_id FK` | migration 1 行 |
| 所有資源表 | 長期目標：把 `user_id` 升格成 `tenant_id`，支援同租戶多用戶 | 3 天（大重構） |

### 2. Token 隔離

現況：`SocialAccount.access_token_enc` 用 Fernet 加密，key 全局共用（`TOKEN_ENCRYPTION_KEY`）。

多租戶後：
- **最小改動**：維持全局加密 key，依靠 DB `user_id` 行級隔離。工時：0。
- **強隔離**：每租戶獨立 Fernet key，存在 `tenants.token_key_enc`（再用主 key 包一層）。工時：2 天 + 遷移腳本。

推薦：先走最小改動，強隔離等 SOC 2 壓力來了再做。

### 3. API 層（鑑權 + 隔離）

已有：
- Flask session cookie 鑑權（C3 magic-link login）
- `attach_user_id_middleware` 注入 `g.current_user_id`

需改：
- 所有 `query(X).filter_by(user_id=g.current_user_id)` 改成同時過濾 `tenant_id`（如果引入租戶概念）。
- API Key 鑑權（指令1 已加）要加「key 屬於哪個租戶」的映射表。
- 工時估計：**3 天**（全面 grep + 修 + 測試）

### 4. 計費掛在哪

最小路徑：
1. `tenants.plan` = `free | starter | pro`
2. `api/__init__.py` 的 `before_request` 讀 plan，超出配額回 402
3. 計費事件 webhook → Stripe → 更新 `tenants.plan`

工時：**2 天**（Stripe webhook handler + plan 欄位 + 配額中間件）

### 5. 現有 59 帳號遷移

```sql
-- 假設現有所有 social_accounts 都歸屬 user_id=1 的學誼
-- 遷移步驟：
-- 1. 建 tenants 表，INSERT 一筆（學誼的租戶）
-- 2. ALTER TABLE users ADD COLUMN tenant_id INT NOT NULL DEFAULT 1
-- 3. 所有 59 個 social_accounts 的 user_id=1 本就是學誼，不需動
-- 零停機：Column default + backfill 在 Postgres 可在線完成
```

總遷移工時：**半天**（因為只有 1 個 user，風險極低）。

---

## 工程量彙整

| 範疇 | 最小改動（2租戶可用） | 完整多租戶 |
|---|---|---|
| 資料模型 | 2 天 | 5 天 |
| API 層隔離 | 3 天 | 3 天 |
| 計費 | 2 天 | 4 天（含 Stripe 整合） |
| Token 強隔離 | 0（走 DB 行級） | 2 天 |
| 遷移 59 帳號 | 0.5 天 | 0.5 天 |
| **合計** | **7.5 工作天** | **14.5 工作天** |

---

## 決策建議

| 定位 | 建議 |
|---|---|
| **內部引擎**（只服務自己三品牌） | 不改，現有 user_id 隔離已夠；投資報酬率極低 |
| **服務商雛型**（招募 2–5 個付費測試客） | 走「最小改動」7.5 天，先收費再做強隔離 |
| **正式 SaaS**（10+ 付費客） | 完整多租戶 14.5 天 + Stripe + SOC 2 審計 |

**現實建議**：先以 `user_id` 做邏輯隔離（實質上已有），加上指令1的 API Key，
手動為每個測試客建一個 User row + 發一個獨立 API Key。
等客戶數到 5 個再做真正的 `tenants` 表重構。
這樣可以在 0 天額外工程的前提下先開始收費驗證市場。

---

## 風險注意

- `PostTarget` 沒有直接 `user_id`，靠 JOIN `posts`，如果未來有 bulk query 要過濾要特別注意。
- Celery tasks 目前不過濾 user_id（全局掃 schedules），多租戶後需要加租戶範圍或做 task 隔離。
- Rate limit（Redis key 格式 `rl:{platform}:{account_id}`）本就帳號級隔離，不需改。
