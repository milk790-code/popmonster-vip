# 學誼接線台 v4 — QA 與部署證據

日期：2026-07-11（Asia/Taipei）
目標：https://popmonster.vip/go
基準：`origin/main@23ae4a3db074bfb952bdf12798816920a6463114`
回滾點：同上

## 發布範圍

- 正式頁固定為 `signal + offer + guided + full`。
- `preview=1` 才能切換 concept、hook、flow、motion；預覽不送事件、不外跳。
- 七項免費服務與 POP 本業分開呈現。
- 四類、兩階段導流；每次只顯示一個推薦結果。
- LINE 首訊用 UTF-8 percent-encoding，並帶 `【GO:<slug>:<source>】`。
- 未知 `src` 一律回退 `direct`；DNT／GPC 開啟或事件端點未設定時停止追蹤，但不阻斷轉換。

## 本機驗證

| 檢查 | 結果 |
| --- | --- |
| Python contract tests | 11/11 通過 |
| JavaScript syntax | 通過 |
| Git whitespace | 通過 |
| Preview matrix | 24/24 通過 |
| 正式版 query 鎖定 | 通過 |
| 320 / 375 / 390 / 768 / 1440 viewport | 無水平溢位，主要 CTA 可見 |
| 200% / 400% zoom | 無水平溢位，主要 CTA 可見 |
| JavaScript 關閉 | 8 個靜態服務入口仍可用 |
| Axe | 0 violations |
| Lighthouse mobile | Performance 99 / Accessibility 100 / Best Practices 100 / SEO 100 |
| Lighthouse Web Vitals | FCP 1.7s / LCP 1.8s / CLS 0 / TBT 30ms / Speed Index 1.7s |
| Sitemap XML | 通過 |
| 獨立 code review | 0 Critical；0 產品程式碼 Important |

## 數據層界線

本次公開頁可獨立運作，`switchboard-events` 端點刻意留空。現有 production Worker 的 source、bindings、version 與 Durable Object migration 無法從 repo 還原，因此本次不虛構 `/events`、`/admin/stats` 或 `/admin/digest` 已上線；事件功能維持 fail-open 關閉，LINE、CreatorKit、POP 入口不受影響。

## GitHub / production 證據

- Commit：待發布
- Pull request：待發布
- GitHub Pages workflow：待發布
- Production readback：待發布
- Production asset hashes：待發布

## 回滾

若 LINE、OG、版面或 routing 退版，將 `main` 回復至基準 commit `23ae4a3db074bfb952bdf12798816920a6463114`，重新跑 GitHub Pages workflow，並再次執行 production readback。
