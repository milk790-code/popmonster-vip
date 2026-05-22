# OPERATIONS_RUNBOOK — PopMonster 四線並進清單

> 涵蓋本週 / 本兩週要完成的四件事，依執行先後排序。
> 🔴 = 你本人必做、🟢 = 純複製貼上、⏱ = 預估時間。
> 完成一項打勾，把產出貼回對話。

---

## 任務 1 — Cloudflare DNS 5 分鐘體檢（先做這個）

> 目標：確認主站 / mail / 之後要加的 `api` 子網域 DNS 全部健康，
> 並列出尚未設定的紀錄。

### 1.1 🟢 開 DNS 列表頁
- URL：https://dash.cloudflare.com/?to=/:account/popmonster.vip/dns/records

### 1.2 🟢 截圖整張 DNS 紀錄表貼回對話
看到列表後**整張截圖**（或複製 type / name / content 三欄全部）貼回來，我幫你逐筆診斷。重點要看的：
- **A `@`** → 應該有 4 筆指向 `185.199.108.153 / .109.153 / .110.153 / .111.153`（GitHub Pages）
- **CNAME `www`** → 應該指向 `milk790-code.github.io` 或 `popmonster.vip`
- **MX 紀錄** → 若有用 Email 收件（@popmonster.vip），確認 MX 指向你信箱供應商
- **TXT `@` (SPF)** → 應該有 `v=spf1 ...` 一筆
- **TXT _dmarc** → 應該有 DMARC 政策
- **DKIM CNAME 或 TXT** → 看你 email 供應商要求

### 1.3 🟢 開 Email Routing 頁面確認郵件流
- URL：https://dash.cloudflare.com/?to=/:account/popmonster.vip/email
- 截圖貼回（如果有用 Cloudflare Email Routing）

### 1.4 🟢 開 SSL/TLS 設定
- URL：https://dash.cloudflare.com/?to=/:account/popmonster.vip/ssl-tls
- 確認 SSL 模式 = **Full** 或 **Full (Strict)**（GitHub Pages 兩個都可，Full (Strict) 較安全）
- 截圖貼回

### 1.5 ⏭ 待 1.2 / 1.3 / 1.4 截圖回來後，我會給：
- 缺少的紀錄清單（含 type / name / content 完整可貼值）
- 多餘 / 風險紀錄的清理建議
- `api.popmonster.vip` CNAME 該怎麼預留（未來 Render 上線時直接填）

---

## 任務 2 — Notion Skills Dashboard 結構（今天 1 天）

> 目標：建立「10 平台主控台 + 4 個支援資料庫」，所有後續工作的單一資訊源。
> 你 Notion 帳號登入後我給你一份**可複製貼上的模板結構**，你照建。

### 2.1 🔴 開 Notion workspace
- URL：https://www.notion.so/
- 確認登入 → 回我「Notion 好了」+ 你 workspace 名稱

### 2.2 📋 Page 結構（建在 workspace 根層）

```
🏠 PopMonster 營運中樞
├── 📊 10 平台主控台 (Database)
├── 📦 商品資料庫 (Database) ← 27 個 SKU
├── 🗓 內容行事曆 (Database)
├── 📚 SOP 庫 (Database)
├── 💬 客服 FAQ 庫 (Database)
└── 🔐 機密保險箱 (Page，存密碼/Token 提示，**不**存明文)
```

### 2.3 📋 Database 1：「10 平台主控台」

欄位（Properties）：
| 欄位名 | 類型 | 選項 / 說明 |
|---|---|---|
| 平台名稱 | Title | — |
| 類別 | Select | 銷售 / 社群 / 基建 / 內部工具 |
| 狀態 | Status | 未啟動 / 設定中 / 運作中 / 卡關 / 已棄用 |
| 優先序 | Select | P0 立刻 / P1 本週 / P2 本月 / P3 之後 |
| 下一步動作 | Text | 一句話 |
| 卡關點 | Text | 一句話 |
| 上次動 | Date | — |
| 負責人 | Person | 預設你 |
| Playbook | Relation → SOP 庫 | — |
| 密鑰提示 | Text | 例：「1Password vault: PopMonster / 項目名:Shopee API」**不寫明文** |
| 月度貢獻 (NT$) | Number | 估營收，每月更新 |

**預填 10 筆**：
- 🛒 蝦皮賣家中心 | 銷售 | 運作中 | P0 | 商品標題 SEO 優化 | — | — | — | — | — | —
- 💬 LINE OA | 社群 | 設定中 | P1 | 建圖文選單 | 沒設過 | — | — | — | — | —
- 🎨 Canva | 內部工具 | 運作中 | P3 | — | — | — | — | — | — | —
- ☁️ Cloudflare | 基建 | 運作中 | P1 | DNS 體檢 | — | — | — | — | — | —
- 🐙 GitHub Pages | 基建 | 運作中 | P3 | — | — | — | — | — | — | —
- 📘 Meta Business Suite | 社群 | 卡關 | P2 | App Review | OAuth | — | — | — | — | —
- 🎵 TikTok Creator | 社群 | 卡關 | P2 | Content Posting API audit | OAuth | — | — | — | — | —
- 🛍 Shopify | 銷售 | 未啟動 | P2 | 評估是否要開 | — | — | — | — | — | —
- 💰 PayPal | 銷售 | 未啟動 | P3 | 評估金流需求 | — | — | — | — | — | —
- 📝 Notion | 內部工具 | 設定中 | P0 | 這份 Dashboard 本身 | — | — | — | — | — | —

### 2.4 📋 Database 2：「商品資料庫」（27 SKU）

欄位：
| 欄位 | 類型 |
|---|---|
| SKU | Title（如 `a001`）|
| 中文品名 | Text |
| 主圖 | Files |
| 蝦皮連結 | URL |
| 蝦皮標題現況 | Text |
| 蝦皮標題建議 | Text |
| 庫存 | Number |
| 售價 | Number |
| 上次盤點 | Date |
| 主打族群 | Multi-select（新手 / 進階 / 商用 / DIY / ...）|
| FB/IG 素材狀態 | Status（無 / 草稿 / 已發 / 重發）|
| 短影音狀態 | Status |
| 備註 | Text |

**Import 來源**：你 repo 內 `index.html` 商品 grid + 各 `aXXX.html` 標題能撈出 27 筆，我可以幫你跑腳本產 CSV → Notion Import。需要時跟我說。

### 2.5 📋 Database 3：「內容行事曆」

欄位：
| 欄位 | 類型 |
|---|---|
| 內容標題 | Title |
| 排程日期 | Date |
| 平台 | Multi-select（FB / IG / TikTok / YouTube / LINE / Shopee 直播）|
| 狀態 | Status（草稿 / 待審 / 已排程 / 已發 / 失敗）|
| 主推商品 | Relation → 商品資料庫 |
| 文案 | Text |
| 素材 | Files |
| 數據（reach/like/comment）| Text（事後填）|

### 2.6 📋 Database 4：「SOP 庫」

欄位：
| 欄位 | 類型 |
|---|---|
| SOP 名稱 | Title |
| 適用平台 | Multi-select |
| 步驟 | Text（多行）|
| 上次更新 | Date |
| 替代方案 | Text |

**預填 5 個必要 SOP**（標題即可，內容後補）：
1. 蝦皮新品上架流程
2. LINE OA 推播流程
3. 短影音發布流程（拍 → 剪 → 上字 → 多平台分發）
4. 客戶退換貨流程
5. 月底庫存盤點流程

### 2.7 📋 Database 5：「客服 FAQ 庫」（給未來 LINE bot 或 social_distributor 用）

欄位：
| 欄位 | 類型 |
|---|---|
| 問題分類 | Select（出貨 / 退貨 / 商品用法 / 規格 / 折扣 / 其他）|
| 顧客常問句 | Title |
| 觸發關鍵字 | Multi-select |
| 標準回覆 | Text |
| 是否需轉真人 | Checkbox |
| 上次更新 | Date |

**預填 10 條最常見問題**（你補答案）：
1. 多久出貨？
2. 寄到哪些國家 / 地區？
3. 怎麼挑適合我車漆的研磨膏？
4. 鉤型釣餌怎麼用？
5. 可以開發票嗎？
6. 怎麼退換貨？
7. 有大量訂購折扣嗎？
8. 是不是台灣製？
9. 開封後怎麼保存？
10. 怎麼聯絡真人客服？

### 2.8 🔴 建好後回我「Notion 結構好了」
我會給你下一步：把蝦皮 27 個 SKU 用 CSV 匯入「商品資料庫」的腳本。

---

## 任務 3 — LINE OA 基底（本週 4-6 hr）

> 前提：你已經有 LINE Official Account（沒有的話先 https://www.linebiz.com/tw/entry/ 開）

### 3.1 🔴 開 LINE Official Account Manager
- URL：https://manager.line.biz/
- 登入 → 選 PopMonster 帳號

### 3.2 🎨 圖文選單（6 格設計）

建議格局（2 × 3，主螢幕版）：
```
┌─────────────┬─────────────┬─────────────┐
│  🛒 看商品  │  🎁 優惠券  │  📦 查訂單  │
├─────────────┼─────────────┼─────────────┤
│  🎬 教學影片│  💬 真人客服│  🌐 官網    │
└─────────────┴─────────────┴─────────────┘
```

連結對應：
- 🛒 看商品 → `https://shopee.tw/milk790`（或你 Shopee shop 連結）
- 🎁 優惠券 → LINE OA 內優惠券功能（在 Manager 內建）
- 📦 查訂單 → 蝦皮 App deep link：`shopee://orders` 或 fallback `https://shopee.tw/buyer/order`
- 🎬 教學影片 → `https://popmonster.vip/free-guide.html`
- 💬 真人客服 → 觸發關鍵字 `真人`（見 3.4）
- 🌐 官網 → `https://popmonster.vip/`

**版位設計**：用 Canva 1040 × 1040 px，留白多、icon 大、字 ≥ 24pt。
我可以給你 Canva 模板的色票（黑 `#0a0a0a` / 金 `#c8a96b` / 淺金 `#d8c08a`）— 直接套品牌配色。

### 3.3 💌 歡迎訊息（加好友自動回覆）

模板（直接複製到 LINE Manager → 加入好友的歡迎訊息）：

```
歡迎加入 POP MONSTER 泡泡怪獸！🌟

我們專門生產台灣製汽車美容耗材：
🐟 27 倒鉤釣餌系統｜🪞 RO 鏡面研磨膏｜🧽 拋光海綿

新朋友福利：
✅ 回覆「優惠券」領首單 9 折券
✅ 回覆「新手包」拿免費 RO 拋光入門指南
✅ 回覆「真人」聯絡店長

點下方選單立即逛商品 ↓
```

### 3.4 🔑 關鍵字自動回覆（必設 6 條）

到 Manager → **自動回應訊息** → **設定** → 開啟「關鍵字回應」。逐筆建：

| 關鍵字 | 回覆內容 |
|---|---|
| `優惠券` `折扣` `優惠` | 「🎁 首單 9 折券來囉！代碼 `WELCOME9`，蝦皮結帳輸入。https://shopee.tw/milk790」|
| `新手包` `入門` `教學` | 「📘 RO 拋光新手指南 → https://popmonster.vip/guide/ro-polish-beginner.html\n還有 4 篇進階指南：https://popmonster.vip/free-guide.html」|
| `真人` `客服` `店長` | 「👋 已通知店長，營業時間（週一至五 10:00-18:00）內 30 分鐘內回覆您～」+ **轉接給後台** |
| `出貨` `寄送` `多久` | 「📦 蝦皮下單 → 賣家出貨 1-2 個工作天 → 物流 1-3 天到貨。週末訂單下週一處理。」|
| `退換` `退貨` `退款` | 「↩️ 7 天鑑賞期內未拆封可退。直接從蝦皮 App 申請退貨即可，或回覆「真人」聯絡店長。」|
| `批發` `團購` `大量` | 「📋 10 件以上批發 / 商用詢價，請回覆「真人」，店長提供報價單。」|

### 3.5 📣 第一則推播訊息（建好選單後 24 小時內發）

```
親愛的車友 👋

POP MONSTER 全新 LINE 官方帳號上線！
打開下方選單 ↓ 即可：
🛒 直達蝦皮逛 27 款台灣製耗材
🎁 領首單 9 折券（限新朋友）
🎬 看免費新手教學

回覆「新手包」拿 RO 拋光入門 PDF 📘
```

### 3.6 🔴 完成後回我「LINE OA 基底好了」
下一步：分眾標籤（新客 / 舊客 / 高消費）+ 月度推播節奏。

---

## 任務 4 — 蝦皮賣家中心健檢（本週半天）

> 目標：6 項體檢，每項都有可量化指標。

### 4.1 🟢 開蝦皮賣家中心
- URL：https://seller.shopee.tw/

### 4.2 ✅ 體檢清單（逐項打勾）

#### A. 商品標題 SEO 體檢（最影響流量）
- URL：https://seller.shopee.tw/portal/product/list
- 對 27 個商品標題逐個檢查，標準格式：
  ```
  【品牌】商品名 規格 主關鍵字 副關鍵字 [贈品/組合]
  ```
- 範例對照：
  - ❌ 弱：「研磨膏」
  - ✅ 強：「【POP MONSTER】RO 鏡面研磨膏 200g 汽車拋光 細目深層去刮痕 台灣製」
- 字數**抓滿 60 字**（蝦皮上限 100，但 60 後通常被截斷顯示）
- 把現況 + 建議標題填回 Notion「商品資料庫」的 `蝦皮標題現況` / `蝦皮標題建議` 欄位

#### B. 庫存準確性
- URL：https://seller.shopee.tw/portal/product/list?status=normal
- 篩選「庫存 < 5」→ 補貨或下架
- 篩選「庫存 = 0」但仍在售 → 立即下架避免顧客下單後無貨

#### C. 商品圖品質
- 主圖必須 **1000 × 1000 px 以上**
- 第一張必須是純白底商品圖（蝦皮搜尋演算法偏好）
- 第二張開始可加情境圖、規格圖、對比圖
- 缺主圖的 → 開 Canva 補（用品牌色票黑 `#0a0a0a` / 金 `#c8a96b`）

#### D. 優惠券設置
- URL：https://seller.shopee.tw/portal/marketing/voucher
- 必備 3 種：
  1. **新客首單券**（如 9 折，無門檻）— 配合 LINE OA 推
  2. **滿額折扣券**（如滿 NT$1,000 折 NT$100）— 提升客單價
  3. **回購券**（如老客專屬 95 折）— 配合 LINE 老客標籤推

#### E. 聊聊回覆速度
- URL：https://seller.shopee.tw/portal/cs/chat
- 目標：**回覆時間 < 12 hr**（顯示在賣場頁，影響轉換）
- 開啟「自動回覆」設「您好，店長將於 1 小時內回覆～」
- 高頻問題（出貨、退換、規格）→ 建「常用回覆」範本

#### F. 蝦皮店家評分 / 違規紀錄
- URL：https://seller.shopee.tw/portal/myshop/penalty
- 確認沒有違規分（影響搜尋排名）
- 確認「準時出貨率」≥ 95%、「成功訂單率」≥ 95%

### 4.3 🔴 完成後回報以下數字
1. 27 個商品中，標題已是「強」格式的有幾個？
2. 庫存準確（與實際相符）的有幾個？
3. 主圖 1000×1000 + 純白底的有幾個？
4. 啟用中的優惠券幾張？
5. 過去 30 天平均聊聊回覆時間？
6. 是否有違規分 / 出貨延遲紀錄？

我會根據這 6 個數字給你下一步優先動作。

---

## 推薦執行順序

```
今天（半天）：
  ✅ 任務 1 — Cloudflare DNS 體檢（5 min）→ 我診斷 → 你補紀錄（30 min）
  ✅ 任務 2 — Notion 結構搭建（3-4 hr，邊看邊建）

明天 / 後天：
  ✅ 任務 4 — 蝦皮健檢（半天，數據先回報，再決定優化順序）

本週末 / 下週初：
  ✅ 任務 3 — LINE OA 基底（4-6 hr）

之後再回頭評估：
  - Render 部署要不要回去做（決於你想不想自動化社群）
  - Shopify / PayPal / Meta App Review
```

---

## 如何使用這份文件

- 每完成一項，把該節下方的 🔴 步驟回報給我
- 我根據你回報的內容給下一步具體指令（含可貼值、URL）
- 這份文件會隨任務進展持續更新（新增章節、修正步驟）
