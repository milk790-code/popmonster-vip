# popmonster.vip 部署與維運手冊
## 泡泡怪獸 POP MONSTER 官網（黑金主題 v12.0）

> 線上網址：<https://popmonster.vip>

---

## 專案概觀

泡泡怪獸是以「鉤子釣具 / 拋光保養」為主題的 31 商品 + 多元內容導購站。整站採黑金主題、零後端純靜態頁，搭配 Cloudflare Pages 部署。本 repo 同時包含一個獨立子專案 `social_distributor/`，用於跨平台社群分發（Flask + Tauri）。

---

## 檔案結構

### 主站（root）

**頁面**
- `index.html` — 首頁（27 商品卡片 + 分類篩選）
- `404.html` — 自訂 404 頁面
- `about.html` — 品牌故事 / 27 款鉤子標題系統
- `members.html` — 會員專區
- `free-guide.html` — 免費電子書下載
- `ai-encyclopedia.html` — AI 鉤子百科
- `error-report.html` — 錯誤回報
- `privacy.html` — 隱私政策（v4.0+）
- `terms.html` — 服務條款（v4.0+）

**商品頁（27 個）**
- `a001.html ~ a010.html`
- `a012.html`、`a013.html`、`a017.html`、`a020.html`、`a024.html`
- `a030.html`、`a031.html`
- `a032.html ~ a041.html`

> 註：a011 / a014-a016 / a018 / a019 / a021-a023 / a025-a029 共 14 個編號為已刪除佔位（v11.0），sitemap.xml 與 index.html 均已同步移除引用，不會產生 404。

**靜態資源**
- `css/main.css` — 共用黑金主題樣式
- `js/main.js` — Cookie Consent + 滾動動畫 + FAQ 開合 + 分類篩選 + GA4
- `img/` — 商品圖（a001.jpg ~ a041.jpg，與商品頁編號對齊）

**SEO / PWA**
- `sitemap.xml` — Google 搜尋爬蟲用（27 商品 + 全部子頁）
- `robots.txt` — 搜尋引擎爬蟲規則
- `manifest.json` — PWA App Manifest
- `favicon.svg`

**部署**
- `CNAME` — 自訂網域（`popmonster.vip`）

### 子目錄

- `guide/` — 5 篇導購長文（angel-coating-guide、ro-polish-beginner、polishing-pad-selection、miso-grit-system、wash-flow-complete）
- `tools/` — 內部工具集（v11.0 起隱藏未公開）
- `social_distributor/` — 跨平台社群分發子專案（詳見 `social_distributor/README.md`）

---

## 部署方式

> 目前正式環境採 **Cloudflare Pages** 自動部署。每次推到 `main` 會自動建置正式環境，每個 PR 會自動產生 `*.popmonster-vip.pages.dev` 預覽網址。

### 初次設定（一次性）

1. **連線 Cloudflare Pages 與 GitHub**
   - 登入 Cloudflare Dashboard → `Workers & Pages` → `Create application` → `Pages` → `Connect to Git`
   - 選擇 `milk790-code/popmonster-vip` repo
2. **建置設定**
   - Production branch：`main`
   - Build command：（留空，純靜態）
   - Build output directory：`/`
3. **自訂網域**
   - Pages 專案 → `Custom domains` → `Set up a domain` → 輸入 `popmonster.vip`
   - Cloudflare 會自動在 DNS 加上對應記錄
4. **HTTPS**：Cloudflare 自動簽發，預設啟用

### DNS 設定（網域在 Cloudflare 上）

由 Cloudflare Pages 自動管理，無需手動加 A 記錄。若網域在其他註冊商，需設定：

| 類型 | 名稱 | 值 |
|------|------|---|
| CNAME | @ | `popmonster-vip.pages.dev` |
| CNAME | www | `popmonster-vip.pages.dev` |

### 日常更新

```bash
git checkout main
# ...修改檔案...
git add .
git commit -m "feat: 描述"
git push
```

推送後 Cloudflare Pages 會自動建置並上線，通常 1-2 分鐘完成。

### 驗證部署

- 正式站：<https://popmonster.vip>
- Cloudflare 預覽：每個 PR 在留言區會看到 `cloudflare-workers-and-pages` bot 自動貼出的預覽網址

---

## 後續維護指南

### 替換商品圖片
1. 準備好每個商品的圖片（建議 1000x1000 以上，JPG 或 WebP）
2. 命名為對應編號 `a001.jpg`、`a002.jpg`、…、`a041.jpg`（注意：跳過已刪除編號）
3. 上傳到 `img/` 資料夾
4. 確認對應 HTML 的 `<img src="...">` 路徑為 `img/aXXX.jpg`

### 更新蝦皮個別商品連結
在每個商品 HTML 裡，搜尋 `https://shopee.tw/milk790` 替換成該商品的蝦皮個別連結。

### Google Analytics 4
GA4 已於 v10.0 全站安裝（含 Consent Mode v2 + IP 匿名化）。若需更換追蹤 ID，全站搜尋 `G-` 開頭的字串即可。

### 提交 Google Search Console
1. 進入 <https://search.google.com/search-console>
2. 新增資源 → URL 前置 → 輸入 `https://popmonster.vip`
3. 用 DNS TXT 記錄或 HTML 標記驗證
4. 驗證後提交 sitemap：`https://popmonster.vip/sitemap.xml`

---

## 技術規格

- 語言標記：`zh-Hant-TW`（繁體中文 台灣）
- hreflang：`zh-Hant-TW` + `x-default`
- Schema.org：Product + BreadcrumbList + FAQPage（JSON-LD）
- 字體：Montserrat（英文）+ Noto Sans TC（繁中）
- 主色：`#0a0a0a`（黑底）、`#c8a96b`（香檳金）、`#d8c08a`（淺金）
- 對比度：香檳金 / 黑底 = 8.06:1（超過 WCAG AAA 標準）
- 觸控目標：所有按鈕 ≥ 44px（WCAG 2.2 AA）
- 行動端：優先設計，768px 斷點自適應
- Cookie Consent：內建同意橫幅 + GA4 Consent Mode v2
- SEO：每頁獨立 title / description / canonical / OG tags
- 蝦皮連結：統一 `rel="nofollow sponsored noopener"`
- PWA：`manifest.json` + `favicon.svg`

---

## 版本演進摘要

| 版本 | 重點 |
|------|------|
| v2.0 | 黑金主題全站上線（31 商品 + SEO + Schema + FAQ） |
| v4.0 | 隱私政策 / 服務條款 / PWA / 進度條 / Footer 法律連結 |
| v6.0 | 全站一致性整合（favicon / OG / manifest / NAV / Footer） |
| v7.0 | 商品擴充至 41 款 + 真實圖片 388 張入庫 |
| v10.0 | GA4 全站安裝（52 頁面 + Consent Mode v2 + IP 匿名化） |
| v11.0 | 整合舊版內容（刪除 14 款佔位 / 隱藏 tools / FAQ 補充 / LINE 系統指南） |
| v12.0 | 補齊網站資訊 + 鉤子標題系統（about.html / 27 款 og:title / 實拍 gallery） |

---

## 相關專案

- `social_distributor/` — 跨平台社群分發子專案，獨立 README 與 SETUP 文件，使用 Flask（後端）+ Tauri（桌面）+ Vanilla JS（前端）+ Docker
