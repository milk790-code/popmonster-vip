# v1.1 本機審核報告

狀態：`LOCAL_REVIEW_READY / VISUAL_QA_BLOCKED / RELEASE_BLOCKED`

工作樹：`codex/popmonster-partner-v1-20260718`

## 基準

- 來源：更新後的 `origin/main`。
- 建立前既有測試：37 項通過。
- `/go`：以 SHA-256 契約鎖定 `go.html`、`css/go.css`、`js/go.js` 不變。

## TDD

- RED：新增 partner 契約測試後，因頁面、Demo、JS、CSS、文件與 sitemap 尚未存在而失敗；`/go` 不變測試已通過。
- GREEN：`python3 -m unittest discover -s tests -v` 於 2026-07-18 執行，48 項通過、0 failure、0 error。
- JavaScript：`node --check js/partner.js` 通過。
- Patch hygiene：`git diff --check` 通過。
- HTTP：本機 `/partner.html?preview=1&src=direct`、`/partner-demo.html`、`/go.html` 均回應 200。

## 瀏覽器 QA

| 頁面 | 尺寸 | 橫向溢位 | 鍵盤／焦點 | Console | 截圖 |
|---|---|---|---|---|---|
| `/partner` | 390 | BLOCKED | BLOCKED | BLOCKED | Browser 實例不可用 |
| `/partner` | 768 | BLOCKED | BLOCKED | BLOCKED | Browser 實例不可用 |
| `/partner` | 1440 | BLOCKED | BLOCKED | BLOCKED | Browser 實例不可用 |
| `/partner-demo` | 390／1440 | BLOCKED | BLOCKED | BLOCKED | Browser 實例不可用 |
| `/go` | 390／1440 | BLOCKED | BLOCKED | BLOCKED | Browser 實例不可用；SHA 契約通過 |

使用者指定的 in-app Browser 回報可用實例清單為空。依 Browser 技能不改用其他瀏覽器冒充驗收，故沒有產生假截圖。待恢復項目與命名見 `artifacts/reviews/partner-v1-20260718/README.md`。

## 人工內容檢查

- [x] 兩個 LINE CTA 都只代表「開啟 LINE」，不是已送出。
- [x] 90 天軌道明確區分立即交付、條件式與尚未開放。
- [x] 耗材貨款、服務補助與第三方費用分開。
- [x] 外部證據有日期、口徑與來源。
- [x] Demo 永久顯示「展示樣品／非正式報價」。
- [x] 文件清楚標示不得直接簽署與發布硬閘門。

## 發布結論

本地程式與靜態契約可交付審核；視覺／互動瀏覽器 QA 尚未完成。商業證據、法律、第一店 BOM、單店損益與 canary 亦維持發布阻擋，因此不得 push、merge、部署、公開、發訊息、收款或切 webhook。
