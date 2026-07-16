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
| 開啟 LINE | `line_start` | `slug`, `source` | LINE 啟動率 |
| 前往網站 | `site_start` | `slug`, `source` | 網站啟動率 |
| 分享入口 | `share_success` | `source` | 分享完成率 |

主要漏斗：`page_ready → route_stage_1 → route_result → line_start / site_start`。

## 第一個可用基線

部署後先累積 7 個完整日，並同時保留：

1. 每個階段的事件數與工作階段數。
2. `source` 分流：`direct`、`business-card`、`package-insert`、`social`、`legacy-worker`。
3. `category` 與 `slug` 的完成率。
4. 同意率，避免把未同意的瀏覽誤判為流失。

樣本不足 30 個合意工作階段時只報原始數量，不做勝負結論。第 8 天再建立第一版基線，之後每週固定比較同星期區間。

### QA 排除條件

2026-07-16 21:06–21:12（Asia/Taipei）的本機瀏覽器驗證曾送出少量測試事件。建立任何基線或探索報表時，必須排除 `page_location` hostname 為 `127.0.0.1` 或 `localhost` 的資料；這些事件不代表真實訪客。測試只開啟 LINE 官方入口，沒有送出訊息。

## 發布後驗證

1. 無既有 consent：Network 不得出現 `googletagmanager.com` 或 `google-analytics.com`。
2. 點「允許匿名分析」後：GA4 DebugView 應依操作順序顯示漏斗事件。
3. payload 不得出現輸入文字、URL query 原文或 LINE 預填訊息。
4. `src=social` 等合法來源應保留；未知來源應降級為 `direct`。
5. 服務連結只送 allowlist custom event；必須阻斷 GA4 Enhanced Measurement 自動 outbound `click`，避免完整 LINE 預填網址進入 `link_url`。
