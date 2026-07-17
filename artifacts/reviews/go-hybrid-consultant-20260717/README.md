# POP 免費接線台 v5：LOCAL_READY 審核包

## 基準

- branch：`codex/go-hybrid-consultant-20260717`
- base：`origin/main@861d92087f4efb34d0bfa1d643ad12a1b42c0375`
- production：未部署、未合併、未改 `main`
- Canva：只完成 v5 handoff 規格，未儲存提交

## 變更摘要

- 首屏改為 7 個免費第一步＋1 個 POP 汽美入口，採第一人稱顧問語氣。
- 四線路徑牆直接列出四類與八個端點；八張工作單預設可見。
- 每張卡固定呈現「我先幫你／你準備／服務邊界／前往方式」。
- POP 同時提供 32 款商品官網與 `@150tiznd` LINE 選品。
- 完整目錄後保留兩步路由器；卡片與結果共用 service registry，支援重新選擇。
- consent 改為文件流內的 static 區塊；preview、GPC、DNT 均 fail-closed。
- `line_start`／`site_start` 僅接受 `hero`、`directory`、`router_result`、`pop_card` surface。
- 視覺改為暖碳黑、黃銅、紙本工作單與自製 inline SVG，不新增外部依賴。

## Browser 驗證

- 390×844、768×1024、1280×720、1440×900：八卡可見、四線可辨識、零水平溢位、無小於 12px 的可見文字、無小於 44px 的互動目標。
- heading hierarchy：單一 H1；路徑牆／目錄／路由器／信任區為 H2；lane 為 H3；服務為 H4。
- 目錄位於路由器之前；POP 雙 CTA、兩步分流、ARIA live 結果、重新選擇、preview 外連阻擋皆通過。
- preview `guided` 會改接路由器並隱藏重複 CTA；`all` 會只保留目錄 CTA，兩個比較模式都不指向隱藏區塊。
- focus ring 為 3px，順序由 skip link → brand → 首屏主 CTA；reduced motion 時 trace animation 為 `none`、scroll behavior 為 `auto`。
- production 模式會忽略公開 `flow=guided` 與未知 `src`，固定回到 `hybrid`／`direct`；技術來源 badge 不顯示。
- 未同意時無 Google 請求；同意後只觀察到 GA4 loader 請求，Browser QA 以 CDP 主動阻擋外送；參數 allowlist 由 Node contract test 驗證。
- preview 模式隱藏 consent、沒有 GA script；console error／warning 為 0。

## 審核圖

- `01-mobile-390x844-hero.png`
- `02-desktop-1265x712-hero.jpg`
- `03-directory-1265x712.jpg`
- `04-router-result-1265x712.jpg`

## 人工紅線

分支 push、Draft PR、Cloudflare preview、Canva v5 儲存提交、合併 `main` 與 production 驗證均未執行。下一步需由使用者決定是否先推 Draft PR／Cloudflare 審核預覽；合併 `main` 會直接觸發 GitHub Pages 正式上線。
