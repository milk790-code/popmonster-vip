# OPS.md — PopMonster 日常工作速查表

> 給人類使用者（milk790-code）日後查閱用。AI 看的是 CLAUDE.md / WORKSPACE.md，不看這份。
>
> 最後更新：2026-05-08 · `session_01PtpAY5UoCrrWind8ooKXeQ`

---

## 啟動方式

```cmd
cd C:\Users\USER\path\to\popmonster-vip
claude
```

進入 Claude Code 後，下面三組 slash commands 都可用（已併到 `main`）。

---

## /popmonster-deploy — 官網維護

| 子指令 | 用途 |
|---|---|
| `verify` | 全站健檢（sitemap、壞連結、缺圖、雜檔）|
| `add-product <sku>` | 新 SKU 骨架（HTML + img 目錄 + sitemap + index 卡片） |
| `update-link <old> <new>` | 全站連結批次替換 |
| `sync-sitemap` | 依現存 `aXXX.html` 重建 sitemap |

預設行為：**永遠 dry-run、等使用者確認、不自動 push**。

## /browser — 蝦皮後台輔助

| 子指令 | 用途 |
|---|---|
| `list-products` | 27 商品 SKU + 蝦皮連結對照表 |
| `caption <sku>` | 跨平台貼文（FB / IG / LINE / 蝦皮）四份文案 |
| `new-product <sku>` | 蝦皮上架包（標題、規格、商品介紹、主圖清單） |
| `update-price <sku> <price>` | 改價步驟（蝦皮後台 + popmonster-vip 同步） |
| `order-batch` | 訂單批次處理（貼訂單列表後產出包裝清單） |

蝦皮沒有公開 API，這個指令的角色是「產可貼上的內容 + 步驟引導」，不自動化執行。

## /theme-factory — 黑金主題視覺工廠

| 子指令 | 用途 |
|---|---|
| `audit` | 跨 popmonster-vip / customer-project-portal / popmonster-linebot 視覺一致性掃描 |
| `sync-tokens` | 把 `main.css` 的 CSS variables 同步到其他 repo |
| `regenerate-product <sku>` | 用統一模板重生指定商品頁 |
| `brand-pack` | 產出「給設計師/外包」的品牌資源包 |

---

## 每週日 22:00 / 15 分鐘 — 鯨宅週報 MVP

開 Claude Code，整段貼這個 prompt：

```
你是我的競品週報員。請執行：

1. 用 bb-browser 對下面 5 個關鍵字各跑一次蝦皮 + Google 搜尋（共 10 次）：
   鯨宅 / 鍍膜源頭 / LINE 鍍膜原料 / 泡泡怪獸 比較 / 米速 副廠

2. 整理「過去 7 天有什麼新動靜」。只看本週新出現或變動的。

3. 輸出（嚴格 ≤ 100 字）：

【三句結論】1. ... 2. ... 3. ...
【證據】最多 5 條，每條一個 URL + 一句說明
【建議行動】單一一句，「做」或「不做」的明確動作

完成後手動把結果貼到 Notion「競品週報」資料庫。
```

完成後手動填入 Notion「競品週報」資料庫的「是否實際做了」欄。

**第 4 週決策時刻**：

| 4 週「做了」次數 | 動作 |
|---|---|
| ≥ 2 | 加自動化（只加 Phase 2 排程，其他不加）|
| = 1 | 維持，再觀察一個月 |
| = 0 | **整個動線停掉** — 不是有用但沒做，是這事本身沒價值 |

---

## 蝦皮 / 社群文案重指引（隨時要用）

任何文案出現以下舊網域 → 用 `/popmonster-deploy update-link` 全站替換成 `https://popmonster.vip`：

- `yjlvjgif.gensparkspace.com` → `popmonster.vip`
- `popmonster.manus.space` → `popmonster.vip`

⚠️ 路徑對應已驗證（`/angel-coating.html`、`/miso-combo-3set.html`、`/pads.html` 在 popmonster.vip 上**不存在** — 這些舊路徑對應的是 customer-project-portal 那份副本，**不能直接搬到 popmonster.vip 用**）。要用時先確認新路徑是哪個 `aXXX.html`。

---

## Google 商家檔案設置（一次性，未做）

完整 prompt 包在 session 對話內。執行前先補 5 個欄位：

1. 是否有實體店面 / 工作室（地址）
2. 服務地區
3. 營業時間
4. 預約用電話
5. Google 帳號

然後把整段（含填好的 5 欄）貼給你選用的瀏覽器 AI 執行。

---

## 跨 repo 速查（在哪做什麼）

| 任務 | 進哪個 repo |
|---|---|
| 改網站文字 / SEO / 商品頁 / guide / tools | `popmonster-vip` |
| 多平台社群發文（FB/IG/TikTok/YouTube）| `popmonster-vip/social_distributor/` |
| LINE bot 意圖 / 商品卡 / GPT prompt | `popmonster-linebot` |
| 客戶後台 / AI 搜尋 / 會員系統 | `customer-project-portal` |
| 部署成品 zip → GitHub Pages | `popmonster-website-deployment` |

正式站 `popmonster.vip` 由 **GitHub Pages** 服務（從 `popmonster-vip/main/` 根目錄），不是 Cloudflare Pages。Cloudflare Pages 只做 PR 預覽。

---

## 工具庫精確瘦身（待你出手）

要從「框架」進到「精確點名」，貼以下任一份清單給我：

```cmd
dir %USERPROFILE%\.claude\agents
dir %USERPROFILE%\.claude\skills
dir %USERPROFILE%\.claude\commands
```

紅旗（已基於數字診斷出）：

- **opus(7) / sonnet(9) / haiku(3) 比例倒掛** — 應該是 haiku 最多，opus 最少。建議至少 4 個 opus 降級
- **16 SKILL.md 含 5 個範例** — 範例移到 `_examples/` 子目錄，從 active 16 降到 11
- **38 skills + 27 commands** 超出人類記憶上限 — 砍到 ~15 skills / ~10 commands

---

## 本 session 已完成 vs 未完成

### ✅ 已完成

- 5 個 repo 的 `CLAUDE.md` 全部 merged 到各自 `main`
- `popmonster-vip/WORKSPACE.md` 跨 repo 路由表已建
- 三個 slash commands 已併入 `popmonster-vip/main`
- 部署平台描述修正（Cloudflare → GitHub Pages）
- 蝦皮文案連結改寫範本（yjlvjgif / manus → popmonster.vip）

### ⏳ 等你動手

- [ ] iPhone Safari 清快取重測 popmonster.vip（驗證跑版只是快取殘影）
- [ ] GitHub `Settings → Pages` 看 DNS check 是否變綠勾
- [ ] 鯨宅週報 MVP 跑滿 4 週
- [ ] Google 商家檔案建立（補完 5 欄資料後）
- [ ] 工具庫精確瘦身（貼 `dir ~/.claude/*` 結果給我）

---

## 緊急情境

| 狀況 | 動作 |
|---|---|
| popmonster.vip 完全打不開 | 看 GitHub Pages Settings → Pages 的 DNS check 狀態。不要按「Unpublish site」或「Remove」紅鈕 |
| 想 rollback 最近的 main commit | `git revert <sha>` 比 `git reset --hard` 安全（保留歷史） |
| Slash commands 不出現 | 確認 `cd /home/user/popmonster-vip` 啟動的 Claude Code，且 `.claude/commands/` 三個檔案都在 |
| 多個 repo 想同時操作 | 用 `popmonster-vip/WORKSPACE.md` 的決策表先決定先進哪個 |
