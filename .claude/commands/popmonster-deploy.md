---
description: PopMonster 官網維護自動化（檢查、加商品、換連結、同步 sitemap）
allowed-tools: Bash, Read, Edit, Write, Grep, Glob
---

# /popmonster-deploy — 官網維護指揮中心

支援的子指令（從 $ARGUMENTS 解析第一個 token，其餘為參數）：

| 子指令 | 說明 |
|---|---|
| `verify` | 跑健康度檢查（sitemap 一致性、壞連結、缺圖、雜檔）|
| `add-product <sku>` | 從現有 `aXXX.html` 模板 fork 出新商品頁 + 圖目錄 + sitemap entry + index.html 加入 |
| `update-link <old> <new>` | 全站搜尋並替換連結，列出影響檔案 |
| `sync-sitemap` | 依當前 `aXXX.html` 自動重建 `sitemap.xml`，剔除已刪除 SKU |
| （無參數） | 印出此 help + 顯示 git status / 最近 5 commits |

## 執行邏輯

1. **永遠先 `cd /home/user/popmonster-vip`** —這個指令只在這個 repo 範圍內運作。如果 git 工作區有未 commit 的東西，先列出讓使用者確認再動。
2. **以使用者確認為前提才寫檔**。任何 add-product / update-link / sync-sitemap 動作都先 dry-run 給差異預覽，等使用者說 OK 才真的寫入。
3. **不自動 push**。所有變動只 commit 在 local，由使用者決定何時 push。
4. **遵守跨 repo gotchas**：`tools/` 永遠不進 sitemap，`guide/` 永遠在 sitemap，`aXXX.html` 編號跳號（見 `README.md` 已刪除 SKU 表）。

## 子指令詳細

### `verify`

跑下列檢查並用 🔴 / 🟡 / 🟢 / ✅ 分級回報：

- 所有 `<loc>` 指到的 HTML 檔是否存在
- 所有 `<a href="...">` 內部連結（非 http/mailto/tel/#）是否指到存在的檔
- 所有 `<img src="...">` 是否指到存在的圖
- 已刪除 SKU（a011, a014–a016, a018, a019, a021–a023, a025–a029）是否確實沒有 HTML / 沒進 sitemap
- `tools/` 是否確實不在 sitemap、`guide/` 是否在 sitemap
- 是否有意外提交檔（`.DS_Store`, `*.bak`, `*.swp`）

完成後輸出一段「punch list」並停手等指示。

### `add-product <sku>`

例：`/popmonster-deploy add-product a042`

1. 從 `a001.html` 複製成 `a042.html`，把所有 SKU 字串、商品名、圖路徑換掉（先用占位符 `__TODO_NAME__`、`__TODO_DESC__`，請使用者後續補）
2. `mkdir img/a042/`
3. 在 `sitemap.xml` 中插入新 `<url>` 區塊（位置依編號順序）
4. 在 `index.html` 的商品 grid 與 carousel 加入卡片
5. 顯示 diff，等使用者 OK 才存檔

### `update-link <old-pattern> <new-pattern>`

例：`/popmonster-deploy update-link "https://yjlvjgif.gensparkspace.com" "https://popmonster.vip"`

1. `grep -rln "<old-pattern>" .` 列出所有命中檔案（排除 `.git/`、`img/`）
2. 顯示每檔案的 diff 預覽
3. 等使用者 OK 後 `sed -i` 全站替換
4. 印出影響統計

### `sync-sitemap`

1. 掃 `*.html` 檔（root + `guide/`），排除 `tools/`、`README.md`、`CLAUDE.md`、`WORKSPACE.md`、`404.html`
2. 重建 `sitemap.xml`，保留現有的 lastmod / priority / changefreq 設定
3. 顯示「新增 / 刪除 / 變動」差異
4. 等使用者 OK 才覆蓋

## 使用者輸入：$ARGUMENTS

依照上面規則處理。沒給參數就印 help。
