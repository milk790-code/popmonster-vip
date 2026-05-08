---
description: 跨 repo 視覺一致性 — 黑金主題色票同步、商品頁模板再生、品牌資源包
allowed-tools: Bash, Read, Edit, Write, Grep, Glob
---

# /theme-factory — 黑金主題視覺工廠

PopMonster 黑金品牌（黑底 `#0a0a0a` × 香檳金 `#c8a96b` × 淺金 `#d8c08a`）跨三個 repo（popmonster-vip 主站、customer-project-portal 嵌入副本、popmonster-linebot Flex Message）必須保持一致。這個指令是品牌一致性巡檢與同步工具。

支援的子指令：

| 子指令 | 說明 |
|---|---|
| `audit` | 跨 repo 掃描色票、字體、按鈕、文案調性的不一致處 |
| `sync-tokens` | 把 `popmonster-vip/css/main.css` 的 CSS variables 同步到其他 repo |
| `regenerate-product <sku>` | 用統一模板重新產生指定商品頁（保留商品資料，重置版面） |
| `brand-pack` | 產生「給設計師/外包」的品牌資源包（色票 hex、字體、logo URL、語氣指南、Schema.org JSON） |
| （無參數） | 印 help |

## 執行邏輯

1. **以 popmonster-vip 為品牌「單一事實來源」**：所有色票、字體、按鈕樣式以 `popmonster-vip/css/main.css` 的 `:root` CSS variables 為主。其他 repo 是消費端。
2. 跨 repo 動作絕不擅自 commit；產出 diff、列出影響檔案、由使用者決定。
3. 品牌核心 token：
   - 主色 `--color-bg: #0a0a0a`、`--color-gold: #c8a96b`、`--color-gold-light: #d8c08a`
   - 字體：Montserrat（拉丁） + Noto Sans TC（中文）
   - 對比度：8.06:1（WCAG AAA）
   - 觸控目標 ≥ 44px（WCAG 2.2 AA）
   - 斷點：768px（mobile-first）

## 子指令詳細

### `audit`

掃描下列三個 repo 並比對：

- `/home/user/popmonster-vip/css/main.css`（基準）
- `/home/user/customer-project-portal/client/public/*.html`（嵌入副本）
- `/home/user/popmonster-linebot/products.py`（Flex Message JSON 內 hex 色碼）
- `/home/user/customer-project-portal/client/src/index.css`（如有）

找出：

- **色票不一致**：basic 比對 hex 字串。例如 portal 用了 `#c8a86b`（少寫一個 9），就標出來。
- **字體不一致**：portal 是不是還在用其他 font-family
- **按鈕樣式分歧**：圓角、padding、字重
- **品牌名稱寫錯**：「泡泡怪」「PopMonster」（中間漏空格）等手誤

輸出 punch list 報告，分 🔴 立即影響 / 🟡 建議統一 / ✅ 已對齊。

### `sync-tokens`

1. 從 `popmonster-vip/css/main.css` 抓 `:root { --... }` 整段
2. 顯示其他 repo 中對應段落的 diff
3. 等使用者 OK 後寫進其他 repo（也是 v1 先 dry-run，使用者 confirm 才動）

### `regenerate-product <sku>`

例：`/theme-factory regenerate-product a001`

1. 從現有 `a001.html` 抽出商品資料（名稱、敘述、規格、價格、圖片 src、Shopee 連結、SKU、Schema.org JSON-LD）
2. 用 `a001.html` 自身的版面為模板（或可選擇「從 a002 拿模板」 by 第二參數）
3. 重組成新版的 `a001.html`，保留商品資料、套上一致的版面結構
4. 顯示 diff，使用者 confirm 才覆蓋

主要用在「某個商品頁手動改過版面之後想拉回標準」。

### `brand-pack`

不修任何檔，只輸出一份 markdown 文件「PopMonster 品牌資源包」，內容包括：

- 主色票（hex + RGB + CMYK 推算 + 對比度數據）
- 字體（CDN URL + 備援 stack）
- Logo 檔案路徑（`popmonster-vip/img/og-default.svg`、`favicon.svg` 等）
- 文案調性說明（一句話品牌風格 + 5 個 do / 5 個 don't）
- 三個 sub-brand（POP MONSTER / MISO / SANWU）的差異
- Schema.org JSON-LD 模板

輸出 markdown 可貼到 Notion / 設計師信件 / 外包契約附件。

## 使用者輸入：$ARGUMENTS

依規則處理。沒給參數就印 help。
