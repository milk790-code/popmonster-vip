# 3Q貢丸 LINE Bot — 本機啟動指南

## 整體流程

```
[LINE 加好友] → [LINE OA 3Q貢丸] → [Messaging API channel]
                                       ↓
                                   [Webhook URL]
                                       ↓
                                 [Python 伺服器(本機)]
                                       ↓
                                 [客服路由邏輯]
                                       ↓
                                   [自動回覆]
```

| 階段 | 執行者 | 工作 |
|---|---|---|
| A | 瀏覽器代理 | 步驟 1–4：LINE 後台設定 |
| B | 本機終端（陳學誼） | 步驟 5–6：啟動程式 + ngrok |
| C | 手機 LINE App | 步驟 7：測試 |

---

## 階段 A — LINE 後台設定（代理執行，步驟 1–4）

> **紅線**：不要點 Issue 按鈕，不要複製 Channel Secret / Access Token 任何字元，遇敏感操作停下描述畫面等陳學誼介入

### 步驟 1 — 建立 Messaging API channel

LINE Developers Console → Provider「波普怪獸」→ Create a Messaging API channel

| 欄位 | 填入值 |
|---|---|
| Region | Taiwan |
| Company name | 陳學誼 |
| Channel icon | 跳過 |
| Channel name | 3Q貢丸 |
| Channel description | 台灣在地品牌孵化所，小店家的夢，我們陪你 Q 到底 |
| Channel category | Local Business |
| Channel subcategory | 任選最近項 |
| Email address | 填常用 email |
| Privacy / Terms URL | 留空 |

點 Create → 建完進詳情頁 → 把 **Channel ID** 複製回報

### 步驟 2 — 連到 LINE 官方帳號

channel 詳情頁 → Messaging API 分頁 → LINE Official Account 區塊 → 點 **Enable Messaging API**
（若還沒 LINE OA → 點 Create LINE Official Account，名稱：3Q貢丸 / 類別：Local Business / Consulting）

連完回報 **LINE OA basic ID**（@開頭那串）

### 步驟 3 — 關閉舊回覆設定

從步驟 2 頁面點 LINE Official Account features 旁的 Edit → 跳到 LINE Official Account Manager

| 設定 | 值 |
|---|---|
| Auto-reply messages | **OFF** |
| Greeting messages | **OFF** |
| Webhooks | **ON** |

關完回 Developers Console 確認 channel 還在

### 步驟 4 — 停在 Access Token 區塊等陳學誼

回 channel 的 Messaging API 分頁 → 找到 Channel access token 區塊 → **停下，描述畫面，等陳學誼指示，不要按 Issue**

**回報清單：**
- Channel ID：（填）
- LINE OA basic ID：@（填）
- Auto-reply / Greeting OFF、Webhooks ON 已確認
- 停在 Channel access token 等指示

---

## 階段 B — 本機啟動（陳學誼執行，步驟 5–6）

### 步驟 5 — 建環境 + 填金鑰

```powershell
cd D:\projects\3qgongwan-bot
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

複製 `.env.example` → `.env`，填入兩個值：

```
LINE_CHANNEL_ACCESS_TOKEN=（從 LINE Console Issue 後複製）
LINE_CHANNEL_SECRET=（點眼睛圖示後複製）
```

> ⚠ 兩值貼完關掉 .env，不再開啟，不拍照

### 步驟 6 — 啟動伺服器 + ngrok + 設 webhook

**終端機 1（啟 FastAPI）：**

```powershell
cd D:\projects\3qgongwan-bot
.venv\Scripts\activate
uvicorn main:app --host 0.0.0.0 --port 8001
```

**終端機 2（ngrok）：**

```powershell
ngrok http 8001
```

看到 `Forwarding https://xxxx-xx.ngrok-free.app` → 複製 https 那串

**回 LINE Developers Console：**

1. 3Q貢丸 channel → Messaging API 分頁
2. Webhook URL 填：`https://xxxx-xx.ngrok-free.app/line/webhook`
3. 點 Update → 點 Verify → 綠勾通過 = 成功
4. 開啟 Use webhook 開關
5. 開啟 Webhook redelivery 開關

---

## 階段 C — 手機測試（步驟 7）

LINE App 加好友：搜尋 LINE OA basic ID（@開頭）或掃 QR code

依序測 6 句：

| 傳送內容 | 預期回覆 |
|---|---|
| 你好 | 主選單 4 選項 |
| 想了解你們的服務 | 兩條服務分流 |
| 500 | 500 元生圖方案 |
| 客製行銷怎麼算 | 客製方案 + 目標承諾書 |
| 我要約諮詢 | 諮詢資料採集 |
| 想查我上次案件進度 | 客服窗口回覆 |

---

## 卡點處置

| 卡點 | 處理方式 |
|---|---|
| Verify 不通過（紅字） | 看 ngrok 終端是否有 POST 進來；沒進來 → 檢查 URL 是否正確、路徑是否 `/line/webhook` |
| 有 POST 但 400 | signature 對不上，檢查 `.env` 的 SECRET |
| 有 POST 但 500 | 程式炸，看 uvicorn 終端錯誤訊息 |
| ngrok URL 每次重啟會變 | 暫時：每次回 LINE Console 重設 webhook URL；長期：付費 ngrok 固定子網域 或上 Render |
| 訊息沒走到對應路由 | 你打的關鍵字沒命中 `route()` 清單，加進對應的 `any(kw in text for kw in [...])` |
| Channel Secret 外洩 | 立刻到 LINE Console 點 Reissue 換新值，改 `.env` 並重啟 uvicorn |
| 關機後想繼續 | 兩個終端 Ctrl+C → 下次啟動：cd 目錄 → activate → uvicorn → 新終端 ngrok → LINE 重設 URL |

---

## 路由邏輯一覽

```
使用者輸入
│
├── 含「諮詢/了解/報價/方案/服務...」→ 兩條服務分流選單
├── 含「500/生圖」或輸入「1」       → 500 元生圖方案
├── 含「行銷/客製/承諾書/孵化」或「2」→ 客製行銷方案
├── 含「約/預約/見面/開始生圖」或「3」→ 諮詢資料採集
├── 含「進度/上次/做完/等多久」       → 客服窗口
└── 其他                            → 主選單
```

---

## 未來升級路線

- **P1**：上 Render / Railway，取代 ngrok，webhook URL 固定
- **P2**：接 Claude API 做語意理解，取代純關鍵字比對
- **P3**：加資料庫記錄客戶狀態，做多輪對話
