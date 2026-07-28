# v1.1 規格追溯表

| 規格 | 實作／證據 | 狀態 |
|---|---|---|
| 獨立 `/partner`，保留 `/go` | `partner.html`；`tests/test_partner_v1.py::test_go_route_is_unchanged` | 完成 |
| 五席與非排他定義 | Hero 工位票、FAQ、合作草案 | 完成 |
| 首批耗材直接交貨開票 | 費用責任表、`goods-bom-template.md` | 模板完成；第一店 BOM 待填 |
| 儲值預設關閉 | 90 天軌道、FAQ、合作草案 feature gate | 完成 |
| 兩個 LINE CTA 與來源碼 | `js/partner.js` allowlist＋runtime test | 完成 |
| 匿名事件且拒絕後零傳送 | 事件／欄位 allowlist＋Node runtime test | 完成 |
| 網站不設申請後端 | 全頁無表單；CTA 只開啟 LINE | 完成 |
| 證據牆 | 三筆公開來源＋`evidence-ledger.md` | 完成；發布日須重查 |
| 公開禁語與未證實數字 | `test_public_copy_has_no_blocked_claims` | 完成 |
| 假資料 Demo | `partner-demo.html`、noindex、preview lock、設定物件 | 完成 |
| 每店隔離架構 | `pilot-operations.md`、`canary-runbook.md` | 設計完成；尚未建立正式資源 |
| 合作文件 | `legal-review-draft.md` | 草案完成；律師未審 |
| 單店損益 | `unit-economics-template.md` | 模板完成；真實數據待填 |
| Canary 測試與回退 | `canary-runbook.md` | Runbook 完成；店家授權與實測待辦 |
| sitemap／canonical／OG／政策 | 靜態契約測試 | 完成 |
| 390／768／1440、焦點、Console、截圖 | `review-report.md`、`artifacts/reviews/partner-v1-20260718/README.md` | Browser 實例不可用，明確阻擋 |
| push／merge／部署／發訊息／webhook | `release-checklist.md` | 未執行，維持負責人閘門 |

「完成」只指本地檔案與已執行測試；不代表線上、法律、商業或 canary 已通過。
