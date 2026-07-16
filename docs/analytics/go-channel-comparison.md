# `/go` 社群／名片／包裹 QR 分流比較

## 目的

比較三個來源帶來的不是「誰掃得最多」，而是：

1. 誰能讓更多人完成問題路由。
2. 誰能帶來更多真實 LINE 詢問。
3. 誰能用更少的發放量帶來成交與營收。

## 固定來源

| 渠道 | source | 固定入口 | 曝光／發放單位 |
|---|---|---|---|
| 社群 | `social` | `https://popmonster.vip/go?src=social` | 含連結貼文的觸及或可驗證曝光 |
| 名片 | `business-card` | `https://popmonster.vip/go?src=business-card` | 實際交付的名片張數 |
| 包裹插卡 | `package-insert` | `https://popmonster.vip/go?src=package-insert` | 已送達且內含插卡的包裹數 |

三個渠道必須使用同一版 `/go`、同一組服務、同一段免費說明與相同量測期間。不要在測試中途只替某一渠道換 CTA。

## 三層真相

### 1. 發放真相

- 社群：平台可驗證的觸及、連結點擊。
- 名片：實際交付張數；無法知道未同意 GA4 的掃碼數。
- 包裹：已送達包裹數；無法知道未同意 GA4 的掃碼數。

### 2. 合意漏斗真相

只計入明確允許匿名分析的事件：

`page_ready → route_stage_1 → route_result → line_start / site_start`

這一層可公平比較「進站之後」的效率，但不能代表全部掃碼者，因為未同意者不會進 GA4。

### 3. 商業真相

LINE 預填訊息會保留 `【GO:<slug>:<source>】`。人工對帳只記匿名案例代號、source、slug、階段與收入，不記姓名、電話、LINE user ID 或對話內容。

## 核心指標

| 指標 | 公式 | 用途 |
|---|---|---|
| 合意啟動率 | consented sessions / placement units | 方向性比較渠道拉動；受 consent 影響，不等同真實掃碼率 |
| 路由完成率 | route result / consented sessions | 落地頁是否把需求說清楚 |
| LINE 啟動率 | line start / consented sessions | 點擊 LINE 的意願 |
| 已驗證詢問率 | verified inquiries / consented sessions | 最重要的進站後商業指標 |
| 付費率 | paid cases / verified inquiries | 詢問品質 |
| 每百次發放營收 | revenue / placement units × 100 | 比較渠道單位經濟 |

不要用 GA4 `line_start` 直接宣稱「加好友」或「已詢問」；只有 LINE 端出現帶來源碼的真實訊息才算 verified inquiry。

## 樣本與決策

- 少於每渠道 30 個 consented sessions：只報原始數量，不排名。
- 每渠道至少 30 個 consented sessions 且至少 5 個 verified inquiries：可做方向性判讀。
- 每渠道至少 100 個 consented sessions 且至少 10 個 verified inquiries：才進入正式渠道決策。
- 領先渠道需在「已驗證詢問率」高出第二名至少 20%，而且「每百次發放營收」沒有落後超過 10%，才可稱為 winner。
- 若名片或包裹 30 天仍未達樣本，延長測試，不用社群的大量曝光強行宣判。

## 7 日與 30 日讀法

### 7 日

只回答：資料鏈路是否正常、各渠道有哪些需求、是否有明顯零事件或 source 漏失。除非三個渠道都達方向性門檻，否則不選 winner。

### 30 日

依序判讀：

1. 發放量是否可信且口徑一致。
2. 合意漏斗是否完整。
3. LINE 已驗證詢問是否能對回 source／slug。
4. 樣本門檻是否達標。
5. 再比較 verified inquiry rate 與 revenue per 100 placements。

## 可直接填寫的渠道彙總

| 期間 | source | placement units | known clicks | consented sessions | route results | LINE starts | verified inquiries | paid cases | revenue | sample status |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| Day 1–7 | social |  |  |  |  |  |  |  |  |  |
| Day 1–7 | business-card |  | N/A |  |  |  |  |  |  |  |
| Day 1–7 | package-insert |  | N/A |  |  |  |  |  |  |  |
| Day 1–30 | social |  |  |  |  |  |  |  |  |  |
| Day 1–30 | business-card |  | N/A |  |  |  |  |  |  |  |
| Day 1–30 | package-insert |  | N/A |  |  |  |  |  |  |  |

衍生欄位：

- `consent activation = consented sessions / placement units`
- `route completion = route results / consented sessions`
- `LINE start rate = LINE starts / consented sessions`
- `verified inquiry rate = verified inquiries / consented sessions`
- `paid rate = paid cases / verified inquiries`
- `revenue per 100 placements = revenue / placement units × 100`

## LINE 匿名對帳模板

| date | source | slug | anonymous case alias | status | revenue TWD | notes without PII |
|---|---|---|---|---|---:|---|
|  |  |  | CASE-001 | opened / verified / qualified / paid / closed_no_sale |  |  |

`verified inquiry` 僅計 `verified`、`qualified`、`paid`；`paid case` 僅計 `paid`。

## QA 排除

- 排除 hostname 為 `127.0.0.1` 或 `localhost` 的事件。
- 排除測試 source、重複測試案例與沒有來源碼的人工測試訊息。
- `0` 只代表目前沒有符合條件的證據；不能推論沒有人掃、沒有需求或渠道無效。
