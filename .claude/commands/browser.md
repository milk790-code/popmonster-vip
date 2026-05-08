---
description: 蝦皮後台輔助 — 產生可貼上內容、操作步驟清單、跨平台文案
allowed-tools: Bash, Read, Grep, Glob
---

# /browser — 蝦皮後台輔助

蝦皮（Shopee）沒有公開 Admin API，所以這個指令的角色是**內容生成 + 操作引導**：使用者在蝦皮後台動手，Claude 把要貼的東西、要對的步驟準備好。

支援的子指令：

| 子指令 | 說明 |
|---|---|
| `list-products` | 列出 popmonster-vip 27 商品的 SKU + 蝦皮連結對照表 |
| `caption <sku>` | 產生跨平台貼文（FB / IG / LINE 廣播 / 蝦皮商品說明）四份文案 |
| `new-product <sku>` | 產生「給蝦皮後台貼上」的標題、規格、描述、主圖檔名清單 |
| `update-price <sku> <price>` | 產生改價步驟清單（蝦皮後台 + popmonster-vip 同步） |
| `order-batch` | 引導處理今日訂單（讀使用者貼上的訂單列表，產生包裝清單 + 出貨備註） |
| （無參數） | 印 help |

## 執行邏輯

1. 商品資料來源以 `popmonster-vip/aXXX.html` 為單一事實來源。從這份 HTML grep 出商品名、SKU、價格、敘述、蝦皮連結。
2. 不直接修改任何檔案 —這個指令是「產出可貼到蝦皮後台的內容」+「步驟清單」，**不是自動化**。
3. 跨平台文案語氣統一：繁體中文 zh-Hant-TW，黑金品牌調性（簡潔、信任、技術感），按各平台慣例調整篇幅與表情符號用量。
4. 蝦皮後台連結不要寫死在輸出（容易過時），改提示「進蝦皮後台 → 商品 → 編輯」這種步驟。

## 子指令詳細

### `list-products`

輸出表格（從 `popmonster-vip/aXXX.html` 抓）：

```
| SKU  | 商品名稱       | 蝦皮連結                 | 主圖檔名         |
|------|---------------|--------------------------|------------------|
| a001 | 天使塗層 Guard | https://shopee.tw/...    | img/a001-main.jpg|
...
```

順便標出：哪些 SKU 的蝦皮連結是預設的 `https://shopee.tw/milk790`（還沒改成個別商品連結，待修）。

### `caption <sku>`

例：`/browser caption a001`

讀 `popmonster-vip/a001.html` 的 title、description、特色，產四份文案：

1. **FB 貼文**（150–250 字，加 hashtag、結尾蝦皮連結 + popmonster.vip 連結）
2. **IG 貼文**（80–140 字，視覺感重，建議 carousel 結構，hashtag 5–8 個）
3. **LINE 廣播**（短，60–100 字，含 emoji、問句結尾引導點擊）
4. **蝦皮商品介紹**（長版，含規格、使用步驟、注意事項，這份直接複製到蝦皮後台「商品介紹」欄）

四份分別用 ```` ```text ```` 區塊包起來方便複製。

### `new-product <sku>`

例：`/browser new-product a042`（前提：a042.html 已用 `/popmonster-deploy add-product` 建好骨架）

讀 a042.html 後產出蝦皮後台填寫包：

- **商品名稱**（蝦皮上限 100 字，建議格式「品牌 + 商品名 + 重點 keyword」）
- **商品分類**（建議：汽機車百貨 → 汽車美容 → 拋光保養）
- **規格**：列出該商品的所有規格項（容量、淨重、產地、製造日期等），格式對齊蝦皮輸入欄
- **商品介紹**（長文版）
- **主圖檔名清單**：使用者要從 `popmonster-vip/img/a042/` 上傳哪幾張，順序排好

### `update-price <sku> <price>`

例：`/browser update-price a005 890`

兩段輸出：

1. **蝦皮後台手動步驟**（編號清單，含跨頁 navigation 提示）
2. **popmonster-vip HTML 改點預覽**（grep 出 a005.html 中含舊價格的行，建議改成新價格 — 如果 popmonster-vip 上沒寫死價格就跳過此步）

不自動寫檔；改 HTML 那部分直接呼叫 `/popmonster-deploy update-link` 處理。

### `order-batch`

請使用者貼上「今日訂單列表」（蝦皮後台複製出來的純文字）。Claude 解析後輸出：

- 每張訂單的「包裝清單」（SKU + 數量 + 注意事項）
- 出貨備註卡（一張單一張，可列印）
- 庫存扣減提醒（哪幾個 SKU 今日要補貨）

## 使用者輸入：$ARGUMENTS

依規則處理。沒給參數就印 help。
