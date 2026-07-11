# 學誼接線台 v4 — 最終 QA 與部署證據

日期：2026-07-11（Asia/Taipei）

正式入口：https://popmonster.vip/go
完整回滾點：`23ae4a3db074bfb952bdf12798816920a6463114`

## 已正式發布

- 正式頁固定為 `signal + offer + guided + full`；只有 `preview=1` 可切換預覽變體。
- 七項免費服務與 POP 本業分開呈現；四類兩階段分流每次只顯示一個結果。
- LINE 深連結以 UTF-8 percent-encoding 帶入 `【GO:<slug>:<source>】`。
- 同源 OG、三組固定 QR、兩張社群圖與兩份 PDF Print 均已發布。
- production 直接由 GitHub Pages 提供，HTTP 轉 HTTPS，正式 `/go` 回 200。

## GitHub / production 證據

| 項目 | 證據 |
| --- | --- |
| v4 主頁 | PR [#41](https://github.com/milk790-code/popmonster-vip/pull/41)，merge `c9ce7a7` |
| 專用 OG | PR [#42](https://github.com/milk790-code/popmonster-vip/pull/42)，merge `0fba7c2` |
| QR／社群／印刷資產 | PR [#43](https://github.com/milk790-code/popmonster-vip/pull/43)，merge `32ad094` |
| GitHub Pages | run [29140737782](https://github.com/milk790-code/popmonster-vip/actions/runs/29140737782) 成功 |
| Pages source | `main /`，HTTPS enforced，API status `built` |
| Production readback | 19 個核心檔案／資產均 HTTP 200，且與 `origin/main@32ad094` SHA-256 一致 |
| QR live decode | business-card、package-insert、social 均以 OpenCV 與 ZXing-C++ 雙解碼成功 |

目前 GitHub aggregate commit status 仍有一個與網站無關的 Railway context
`feisty-creativity - 3qgongwan-bot` 失敗；GitHub Pages、Cloudflare Pages 與
deployment bundle 均成功。不得把 aggregate status 誤報成「所有 checks 全綠」。

## 本機驗證

| 檢查 | 結果 |
| --- | --- |
| Python contract + delivery tests | 16/16 通過 |
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
| 初次獨立 code review | 0 Critical；0 產品程式碼 Important |

## Telemetry 契約與目前邊界

正式頁的 `switchboard-events` endpoint 維持空白，所以 production 現在不送事件，
且 LINE、CreatorKit、POP 導流維持 fail-open。前端已準備 UUID v4 `event_id`、
per-tab 64-hex 匿名 session hash、`text/plain` beacon，以及 DNT／GPC／preview
停送契約；只有新 staging Worker 完成部署與 smoke test 後才能填 endpoint。

獨立 Worker deploy pack 位於本機：
`/Users/mac/Documents/Codex/control-center/popmonster-switchboard-v4-worker`。
本機 `wrangler types`、TypeScript、floating Promise lint、11/11 workerd tests
與 Wrangler dry-run bundle 已通過；包含 HMAC 分片、rate limit、alarm 自癒、
嚴格 CORS／MIME、去重與 90 日清除。尚未建立任何外部 Worker／Durable Object。

## 已知非阻斷缺口

- GitHub Pages 正式站未送 CSP、HSTS、`X-Content-Type-Options`、
  `Referrer-Policy`、`X-Frame-Options`、`Permissions-Policy`。Repo `_headers`
  不會套用到 GitHub Pages；要補需另改 hosting／proxy 架構。
- 五份 Canva 私人草稿已建立並以 design ID 回讀；未公開分享。
- iOS／Android 的 100% 實際尺寸掃描、公開分享、送印與付款均未執行。

## 回滾

若 LINE、OG、routing、版面或 telemetry client 退版，先 revert 最後一個相關
merge commit；若需整批撤回 v4，回復到 `23ae4a3db074bfb952bdf12798816920a6463114`，
重跑 GitHub Pages，再做 production hash readback。禁止以 ZIP 覆蓋 production。
