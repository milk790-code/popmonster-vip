# popmonster.vip 部署操作 SOP
## 泡泡怪獸 POP MONSTER 官網（黑金主題 v2.0）

---

## 檔案清單（v2.1 — 補完版）

### 繁體中文
- `index.html` — 首頁（31 商品卡片 + 分類篩選 + 商品搜尋）
- `a001.html` ~ `a031.html` — 31 個商品頁（黑金主題 + Schema + FAQ）
- `about.html` — 品牌故事
- `contact.html` — 聯絡我們（含 mailto 表單）
- `privacy.html` — 隱私權政策（noindex）
- `terms.html` — 服務條款（noindex）
- `404.html` — 自訂 404 頁面

### English
- `en/index.html` — homepage with 31 products + search + filter
- `en/about.html`、`en/contact.html`、`en/privacy.html`、`en/terms.html`、`en/404.html`

### 共用資源
- `css/main.css` — 共用黑金主題樣式（含 static / contact / search 樣式）
- `js/main.js` — Cookie Consent + 滾動動畫 + FAQ 開合 + 分類篩選 + 即時搜尋
- `og-image.svg` — Open Graph / Twitter card 預設圖（1200×630）
- `sitemap.xml` — 含 hreflang 的多語 sitemap
- `robots.txt` — 搜尋引擎爬蟲規則
- `CNAME` — GitHub Pages 自訂網域（popmonster.vip）

---

## 部署步驟（逐步操作）

### 步驟一：登入 GitHub
1. 打開 https://github.com
2. 用您的帳號 `milk790-code` 登入

### 步驟二：建立新 Repository
1. 點右上角 `+` → `New repository`
2. Repository name 填：`popmonster-vip`
3. 選擇 `Public`
4. **不要**勾選 Initialize with README
5. 點 `Create repository`

### 步驟三：上傳檔案
1. 解壓 `popmonster-vip-ready.zip`
2. 在新建的 repo 頁面，點 `uploading an existing file`
3. 把解壓後的**所有檔案和資料夾**拖進上傳區域
   （包含 css/、js/、.github/ 資料夾，以及所有 .html 檔案）
4. 注意：`.github` 資料夾在 Mac/Windows 上可能是隱藏的
   - Mac：在 Finder 按 `Cmd + Shift + .` 顯示隱藏檔案
   - Windows：在檔案總管 → 檢視 → 勾選「隱藏的項目」
5. Commit message 填：`feat: 黑金主題全站上線 v2.0`
6. 點 `Commit changes`

### 步驟四：啟用 GitHub Pages
1. 進入 repo → `Settings` → 左側選 `Pages`
2. Source 選 `GitHub Actions`
3. Custom domain 填：`popmonster.vip`，點 Save
4. 等約 1-2 分鐘，勾選 `Enforce HTTPS`

### 步驟五：DNS 設定
在您的網域 DNS 管理介面（Cloudflare / GoDaddy / Namecheap 等），設定以下記錄：

**A 記錄（4 條，指向 GitHub Pages）：**
| 類型 | 名稱 | 值 |
|------|------|---|
| A | @ | 185.199.108.153 |
| A | @ | 185.199.109.153 |
| A | @ | 185.199.110.153 |
| A | @ | 185.199.111.153 |

**CNAME 記錄（1 條，www 子網域）：**
| 類型 | 名稱 | 值 |
|------|------|---|
| CNAME | www | milk790-code.github.io |

### 步驟六：驗證上線
等待 5-30 分鐘（DNS 生效時間），在瀏覽器輸入：
- https://popmonster.vip
- https://www.popmonster.vip

兩個網址都應該能看到黑金主題的泡泡怪獸官網。

---

## 後續維護指南

### 替換商品圖片
1. 準備好每個商品的圖片（建議 1000x1000 以上，JPG 或 WebP）
2. 命名為 `a001.jpg`、`a002.jpg` ... `a031.jpg`
3. 上傳到 repo 的 `img/` 資料夾
4. 修改對應 HTML 裡的 `<img src="...">` 路徑為 `img/a001.jpg`

### 更新蝦皮個別商品連結
在每個 HTML 檔案裡，搜尋 `https://shopee.tw/milk790`
替換成該商品的蝦皮個別連結即可。

### 新增 Google Analytics 4
取得 GA4 追蹤 ID（G-XXXXXXXXXX）後：
1. 在每個 HTML 的 `</head>` 前加入：
```html
<script async src="https://www.googletagmanager.com/gtag/js?id=G-XXXXXXXXXX"></script>
<script>
  window.dataLayer=window.dataLayer||[];
  function gtag(){dataLayer.push(arguments)}
  gtag('js',new Date());
  gtag('config','G-XXXXXXXXXX');
</script>
```

### 提交 Google Search Console
1. 進入 https://search.google.com/search-console
2. 新增資源 → URL 前置 → 輸入 https://popmonster.vip
3. 用 DNS TXT 記錄或 HTML 標記驗證
4. 驗證後提交 sitemap：https://popmonster.vip/sitemap.xml

---

## 技術規格

- 語言標記：`zh-Hant-TW`（繁體中文 台灣）
- hreflang：`zh-Hant-TW` + `x-default`
- Schema.org：Product + BreadcrumbList + FAQPage（JSON-LD）
- 字體：Montserrat（英文）+ Noto Sans TC（繁中）
- 主色：#0a0a0a（黑底）、#c8a96b（香檳金）、#d8c08a（淺金）
- 對比度：香檳金/黑底 = 8.06:1（超過 WCAG AAA 標準）
- 觸控目標：所有按鈕 ≥ 44px（WCAG 2.2 AA）
- 行動端：優先設計，768px 斷點自適應
- Cookie Consent：內建同意橫幅
- SEO：每頁獨立 title/description/canonical/OG tags
- 蝦皮連結：統一 rel="nofollow sponsored noopener"
