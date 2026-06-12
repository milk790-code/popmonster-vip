# agentmemory 後端上線 + 記憶同步 runbook

把本機的 agentmemory（`@agentmemory/agentmemory` v0.9.22，REST 在 `:3111`）包成
一個 Railway 上的長駐服務，讓四個 repo 的 `.mcp.json` 透過 `AGENTMEMORY_URL`
指向它，並把你**本機累積的記憶資料**同步上去。

> 格式同 `social_distributor/BROWSER_STEPS.md`：🟢 = 純複製貼上、無決策；
> 🔴 = 你本人必須親手做（登入、付款、貼密鑰、做判斷）。完成每步把產出貼回。

---

## ⚠️ 先讀：兩個必須處理的限制

1. **預設無驗證（安全）。** agentmemory REST 原設計假設 localhost，對外暴露等於
   任何人都能讀寫你的記憶。**Dockerfile 已把監聽改成 `0.0.0.0`，但沒有加驗證。**
   上線前必須二擇一（見 §4）：
   - (A) 只用 Railway **私有網路**（不開 public domain），讓需要的服務走內網；或
   - (B) 在前面加一層帶 token 的反向代理 / 只允許特定來源。
   雲端 Claude session 與你本機要連得到 → 若需公開，務必用 (B)。
2. **Railway 需先儲值 $5。**（你的 `social_distributor/BROWSER_STEPS.md` 也記過這點。）
   不想付費的話，agentmemory 也可改用 Render，但 Render 免費層**無持久磁碟**，
   記憶會在每次重啟後消失 → 不建議。

---

## 1. 🔴 建 Railway 專案並儲值

- URL：https://railway.com/new
- 用 GitHub 登入（同 `milk790-code` 帳號）
- Billing 儲值 $5：https://railway.com/account/billing
- 完成後貼回「Railway 好了」

## 2. 🟢 從 repo 部署服務

- 在專案內 **+ New → Deploy from GitHub repo → `popmonster-vip`**
- **Settings → Source**：
  - Root Directory = `agentmemory-server`
  - Builder 會自動讀 `railway.json` → Dockerfile
- **Settings → Variables**（先設，再 deploy）：
  ```
  PORT=3111
  ```
  （Railway 通常自動注入 PORT；保險起見手動設。）

## 3. 🟢 掛持久化 Volume（記憶 DB 一定要保存）

- 服務 **Settings → Volumes → + New Volume**
- Mount Path = `/app/data`
- 大小 = 1 GB（之後可調大）
- 這對應容器內記憶資料的 `./data/`（`state_store.db` + `stream_store`）

## 4. 🔴 安全：選一條路（見上方 §先讀-1）

- **(A) 私網**：agentmemory service Settings → Networking → **不要** Generate Domain。
  其他需要的 Railway 服務用內部 hostname 連 `http://agentmemory.railway.internal:3111`。
  ⚠️ 你本機 / 雲端 session 連不到 → 只適合「服務對服務」。
- **(B) 公開 + token proxy**（已預先鋪好設定）：agentmemory service 維持私網，
  另開一個 Caddy proxy service 對外。設定檔在 `proxy/`：
  - 在同 Railway 專案 **+ New → Deploy from GitHub repo** → 一樣選 `popmonster-vip`
  - Settings → Source → Root Directory = `agentmemory-server/proxy`
    （它會自動讀 `proxy/railway.json` → `proxy/Dockerfile`）
  - Settings → Variables：
    ```
    AGENTMEMORY_INTERNAL_URL=http://agentmemory.railway.internal:3111
    AGENTMEMORY_SECRET=<自己產一串長字串，例：python3 -c "import secrets;print(secrets.token_urlsafe(40))">
    ```
  - Networking → **Generate Domain**（這個才對外）
  - 之後對外用 `https://<proxy-domain>` 當 `AGENTMEMORY_URL`，請求帶
    `Authorization: Bearer <AGENTMEMORY_SECRET>`。
    四個 repo 的 `.mcp.json` 已預留 `AGENTMEMORY_SECRET` 環境變數，會自動帶上。

> 建議路徑：先 (A) 確認 agentmemory 自己起得來；確認 OK 後再加 (B) proxy 對外。

## 5. 同步本機記憶資料 → 線上 volume

**重要**：要同步的記憶在**你本機**那台跑 agentmemory 的機器上，不在雲端容器裡。
雲端 session 是全新空白實例，無法代你匯出。請在**你本機**執行：

```bash
# 本機：確認 agentmemory 在跑、看記憶數量
agentmemory status

# 找出本機記憶資料目錄（state_store.db + stream_store 所在的 ./data/）
# 通常在你最常啟動 agentmemory 的工作目錄下，或用 export 工具：
```

兩種同步法：

- **法一（推薦）：直接搬 data 目錄。**
  把本機的 `data/state_store.db` 與 `data/stream_store/` 整包，
  在 Railway volume（`/app/data`）還原。Railway 可用
  `railway run` / `railway volume` CLI 或臨時 shell 上傳。
- **法二：用 MCP `memory_export` 匯出 JSON 備份。**
  注意：agentmemory **沒有對應的 import 指令**（CLI 只有 `import-jsonl`，
  那是匯入 Claude Code 轉錄，不是還原匯出 JSON）。所以 JSON 僅作**備份/保險**，
  正式同步仍走法一（搬 data 目錄）。

> 🔴 **退路**：若搬 data 目錄遇到版本/格式問題，退而求其次＝線上實例重新開始累積，
> 本機 JSON 僅留存。是否接受此退路請告知。

## 6. 🟢 把四個 repo 指向線上實例

部署成功、拿到可連 URL 後（例如 `https://agentmemory-xxx.up.railway.app`），
把四個 repo 的 `.mcp.json` 裡：

```
"AGENTMEMORY_URL": "${AGENTMEMORY_URL:-http://localhost:3111}"
```

的預設值改成線上 URL（保留可被環境變數覆寫的形式）。我會在分支上一起改。

---

## 驗證清單

- [ ] Railway service 部署成功（build log 無錯、容器有起來）
- [ ] iii-engine 在容器內正常啟動（看 deploy log；native 引擎在 slim 容器是否需額外
      依賴**尚待驗證** — 若起不來，改用 `AGENTMEMORY_USE_DOCKER=1` 路徑或加缺漏套件）
- [ ] `curl https://<url>/` 或正確健康路徑有回應（**確切 health path 待驗證**）
- [ ] 用 MCP `memory_recall` 對線上 URL 查得到剛同步進去的舊記憶
- [ ] 四個 repo 連線正常（`agentmemory status` 指向線上 URL 顯示 memory count > 0）

## 尚待驗證的未知數（別當成已完成）

1. **native iii-engine 在 `node:22-slim` 容器能否啟動** —— 可能缺系統依賴或需 Docker-in-Docker。
   若失敗，試 `AGENTMEMORY_USE_DOCKER=1`（但 Railway 容器內跑 Docker 較麻煩）。
2. **確切健康檢查路徑** —— 文件未明示；部署後實測。
3. **data 目錄跨機/跨版本還原相容性** —— 同步前先在本機備份。
4. **對外驗證機制** —— agentmemory 無內建 auth，§4 的保護方案需落實。
