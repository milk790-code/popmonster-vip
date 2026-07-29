# `/go` 三平台分享預覽實驗

## 架構

正式入口固定為 `https://popmonster.vip/go`。由於靜態託管無法依 query string 為社群爬蟲回傳不同 HTML，分享時使用 9 個薄 wrapper：

- wrapper 提供平台與文案版本專屬的 `og:title`、`og:description`、`og:image`。
- `rel=canonical` 一律指向正式 `/go`，wrapper 設為 `noindex,follow`。
- 真人開啟 wrapper 後，用 `location.replace` 前往 `/go?src=<platform>-<variant>`。
- `/go` 仍是唯一正式內容入口；wrapper 不保存輸入、不執行服務邏輯。

完整機器可讀對照在 `assets/go-v4/experiments/manifest.json`，可用
`python3 scripts/generate_go_share_campaign.py` 重建所有卡片與 wrapper。

## 三版訊息

| variant | 核心訊息 | 使用情境 |
|---|---|---|
| `free-first` | 免費第一步 | 低摩擦、明確說明先拿到什麼 |
| `dont-pay` | 別急著花錢 | 打斷衝動決策、提高避坑感 |
| `connect` | 我幫你接線 | 不要求使用者先理解服務分類 |

## 平台最佳化

| platform | 預覽策略 | `src` 範例 |
|---|---|---|
| Facebook | 資訊較完整，直接呈現 5 條服務線與 11 個入口 | `facebook-free-first` |
| LINE | 大字、對話泡泡、明確「回一句」動作 | `line-dont-pay` |
| Threads | 對話串節奏，降低廣告感與硬 CTA | `threads-connect` |

每個平台各有 `free-first`、`dont-pay`、`connect` 三個來源，共 9 組。

## 真正服務線歸因

`source` 只代表使用者從哪張分享卡進站；真正選擇則以
`service_select` 記錄：

- `slug`：11 個既有服務之一。
- `surface`：`hero`、`directory`、`router_result`、`pop_card`。
- `source`：由合法 `src` 白名單帶入。

只有使用者同意匿名分析且未啟用 GPC／DNT 時才送出。事件不包含輸入文字、
完整 URL、LINE 預填內容、姓名、電話或其他個資。`line_start`／`site_start`
仍保留，用來區分「選了服務」和「實際啟動外部目的地」。

## 判讀規則

1. 每個來源至少累積 30 個合意工作階段，再比較服務線選擇率。
2. 未達門檻只看原始數量，不宣布勝版。
3. 主要指標：`service_select / page_ready`。
4. 次要指標：`line_start + site_start / service_select`。
5. 同一平台內比較三版；跨平台不直接歸因為文案效果。
