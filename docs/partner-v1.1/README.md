# 泡泡怪獸「城市共創試行夥伴」v1.1 審核包

狀態：`LOCAL_REVIEW_READY / RELEASE_BLOCKED`

這份審核包把公開頁、假資料 Demo、成交文案、證據台帳、合作說明、試行 SOP 與發布閘門分開。它可以在本機審核，不代表已公開、已報價、已簽署、已收款或已切換任何 LINE webhook。

## 公開介面候選

- `/partner`：B2B 合作說明頁；網站不收申請表，兩個 CTA 只開啟 POP LINE。
- `/partner-demo`：`noindex` 通用假資料 Demo；預覽模式永久停止外部跳轉、事件與送出。
- `/go`：既有 B2C 免費接線台；本次未修改。

## 文件導覽

- `copy-pack.md`：主文案、社團短版、30 秒話術、LINE 回覆、異議處理與去識別化健檢。
- `evidence-ledger.md`：公開數字、口徑、來源與啟用條件。
- `legal-review-draft.md`：不可直接簽署的 90 天合作說明草案。
- `goods-bom-template.md`：首批耗材逐項交貨、開票、退換貨附件。
- `unit-economics-template.md`：單店損益與停止條件。
- `pilot-operations.md`：20 店小樣本、五店導入、隔離架構與量測方式。
- `canary-runbook.md`：單店 LINE canary、fail closed 與回退步驟。
- `release-checklist.md`：發布前硬閘門與禁止動作。
- `review-report.md`：本機測試、瀏覽器 QA 與人工審核紀錄。
- `requirements-traceability.md`：規格、檔案證據與外部閘門逐項對照。

## 本機預覽

在此專案根目錄執行：

```zsh
python3 -m http.server 4173
```

然後開啟：

- `http://127.0.0.1:4173/partner.html?preview=1&src=direct`
- `http://127.0.0.1:4173/partner-demo.html`

`preview=1` 會停止 `/partner` 的外部跳轉與匿名事件。Demo 無論網址參數為何都保持預覽鎖定。

## 目前紅線

以下項目尚未由負責人與外部專業人員完成，因此不得把這份包視為可直接公開的最終版本：

1. 自家流量與訂單後台證據。
2. 律師審過的合作文件與資料角色。
3. 第一店實際 BOM、補助上限與單店損益。
4. 第一家測試店授權與 canary 結果。

不得 push、merge、正式部署、公開貼文、發陌生訊息、收款或切換合作店 LINE webhook。
