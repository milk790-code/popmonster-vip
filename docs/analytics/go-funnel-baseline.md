# `/go` GA4 真實轉換基線

## 量測邊界

- 只計入使用者明確允許匿名分析後的新事件。
- 不回補部署前資料，不記錄對話、輸入文字、姓名、電話或 LINE 使用者資料。
- `0` 只表示沒有收到符合條件的事件，不等於沒有人瀏覽或服務沒有需求。
- GPC／DNT 啟用時不載入 GA4，也不送出事件。

## 漏斗

| 階段 | GA4 event | 允許參數 | 指標 |
|---|---|---|---|
| 看到入口 | `page_ready` | `source` | 合意工作階段起點 |
| 點主要 CTA | `hero_cta` | `target`, `source` | 首屏行動率 |
| 選問題分類 | `route_stage_1` | `category`, `source` | 問題選擇率 |
| 找到服務 | `route_result` | `slug`, `source` | 路由完成率 |
| 真正選擇服務線 | `service_select` | `slug`, `surface`, `source` | 分享卡帶入後的服務線選擇率 |
| 開啟 LINE | `line_start` | `slug`, `surface`, `source` | LINE 啟動率 |
| 前往網站 | `site_start` | `slug`, `surface`, `source` | 網站啟動率 |
| 分享入口 | `share_success` | `source` | 分享完成率 |

混合入口的主要漏斗分成兩條：

- 直接目錄：`page_ready → service_select → line_start / site_start`。
- 協助分流：`page_ready → route_stage_1 → route_result → service_select → line_start / site_start`。

`surface` 只接受 `hero`、`directory`、`router_result`、`pop_card`。不得傳送原始輸入、完整 LINE URL、任意 query 或個資；非白名單值直接丟棄。

## 第一個可用基線

部署後先累積 7 個完整日，並同時保留：

1. 每個階段的事件數與工作階段數。
2. `source` 分流：既有 `direct`、`business-card`、`package-insert`、`social`、`legacy-worker`，以及 Facebook／LINE／Threads 的三版分享來源。
3. `category` 與 `slug` 的完成率。
4. 同意率，避免把未同意的瀏覽誤判為流失。
5. `source → service_select.slug → line_start / site_start`，辨認分享卡帶來的人真正選了哪條服務線。

樣本不足 30 個合意工作階段時只報原始數量，不做勝負結論。第 8 天再建立第一版基線，之後每週固定比較同星期區間。

### 部署前後切分

- 部署前資料沿用舊版漏斗，不回填 `surface`，也不與新版分母混算。
- 發布時記錄 production `go.html`、`css/go.css`、`js/go.js`、`js/go-analytics.js` hash 與 UTC 時間，作為新版資料起點。
- 2026-07-17 強鉤子成果票券版仍沿用相同 event 與 allowlist；比較時以發布 hash／UTC 為切點，不能把文案改版前後混成同一母體。
- 新版需累積 7 個完整日且至少 30 個合意工作階段後，才比較各 `surface` 的啟動率；未達門檻只看原始量。

### QA 排除條件

2026-07-16 21:06–21:12（Asia/Taipei）的本機瀏覽器驗證曾送出少量測試事件。建立任何基線或探索報表時，必須排除 `page_location` hostname 為 `127.0.0.1` 或 `localhost` 的資料；這些事件不代表真實訪客。測試只開啟 LINE 官方入口，沒有送出訊息。

## 發布後驗證

1. 無既有 consent：Network 不得出現 `googletagmanager.com` 或 `google-analytics.com`。
2. 點「允許匿名分析」後：GA4 DebugView 應依操作順序顯示漏斗事件。
3. payload 只能出現事件對應的 allowlist 參數；不得出現輸入文字、URL query 原文、完整 LINE URL 或預填訊息。
4. `src=social` 等合法來源應保留；未知來源應降級為 `direct`。
5. 服務連結只送 allowlist custom event；必須阻斷 GA4 Enhanced Measurement 自動 outbound `click`，避免完整 LINE 預填網址進入 `link_url`。
6. 目錄、分流結果、首屏 POP 與 POP 卡片應分別送出 `directory`、`router_result`、`hero`、`pop_card`；偽造 surface 必須被丟棄。

三渠道實驗與決策規則見 [`go-channel-comparison.md`](go-channel-comparison.md)。
分享預覽卡與 `src` 對照見 [`go-share-preview-experiment.md`](go-share-preview-experiment.md)。
