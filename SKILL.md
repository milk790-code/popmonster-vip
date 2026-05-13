---
name: 3qgongwan-bot
description: >
  3Q貢丸 LINE 客服機器人（台灣在地品牌孵化所）的完整部署、維護、除錯與更新技能。
  每當用戶提到「3Q貢丸」「品牌孵化」「LINE Bot」「修 bot」「bot 沒回」
  「更新路由」「改歡迎訊息」「Rich Menu」「Render 部署」「webhook 不通」
  或任何與 3Q貢丸客服機器人有關的任務時，必須使用此技能。
---

# 3Q貢丸 LINE Bot 技能

## 技術棧
- Python 3.10+ / FastAPI / uvicorn / line-bot-sdk v3
- 雲端: Render Free Plan (Singapore)
- Webhook: /line/webhook
- 版本: v2.1

## 架構
```
LINE 使用者
  ↓ 訊息
LINE Platform → POST /line/webhook
  ↓
_normalize()      全形→半形 + strip + .lower()
  ↓
route(text)       優先級 0-A → 9 依序比對
  ↓
_reply()          統一回覆
```

## 頂層常數（改一處全生效）

| 常數 | 用途 |
|------|------|
| KW_START_IMAGE | 開始生圖觸發詞 |
| KW_CUSTOMER_SERVICE | 客服觸發詞 |
| KW_BOOKING | 預約觸發詞 |
| KW_PRODUCT_2 | 客製行銷觸發詞 |
| KW_INQUIRY | 服務諮詢觸發詞 |
| KW_PROGRESS | 進度查詢觸發詞 |
| KW_THANKS | 感謝回覆觸發詞 |
| REPLY_RECEIVED_FORM | 十題表收件確認文字 |
| REPLY_TEN_QUESTIONS | 十題探尋表文字 |

要加關鍵字或改回覆文案，只改頂層常數，不進 route()。

## 路由對照表 (main.py v2.1)

| 優先序 | 常數/條件 | 回覆 |
|--------|----------|------|
| 0-A | 多行+含≥3編號行 | REPLY_RECEIVED_FORM |
| 0-B | KW_START_IMAGE | REPLY_TEN_QUESTIONS |
| 1 | text == "送出" | REPLY_RECEIVED_FORM |
| 2 | KW_CUSTOMER_SERVICE | 人工小編窗口 |
| 3 | KW_BOOKING 或 "3" | 30分鐘諮詢預約 |
| 4 | "500" / "生圖" / "1" | 500元生圖方案 |
| 5 | KW_PRODUCT_2 或 "2" | 客製行銷方案 |
| 6 | KW_INQUIRY | 兩條服務分流 |
| 7 | KW_PROGRESS | 進度查詢 |
| 8 | KW_THANKS | 暖回覆 |
| 9 | (其他) | _menu() |

## 部署 SOP
1. GitHub Private repo → 上傳所有檔案(不含.env)
2. Render → New Web Service → Connect repo → 自動讀 render.yaml
3. Render Environment 填 LINE_CHANNEL_SECRET + LINE_CHANNEL_ACCESS_TOKEN
4. LINE Developers Console → Webhook URL: https://xxx.onrender.com/line/webhook
5. python setup_richmenu.py 建立六格選單

## Rich Menu 六格
```
┌──────────┬──────────┬──────────┐
│ 諮詢服務  │ 500 生圖  │ 行銷方案  │
│  → 諮詢   │  → 500   │  → 行銷   │
├──────────┼──────────┼──────────┤
│  查進度   │ 客服小編  │  約諮詢   │
│  → 進度   │  → 客服   │ → 約諮詢  │
└──────────┴──────────┴──────────┘
```

## 檔案清單

```
main.py               主程式 v2.1
setup_richmenu.py     Rich Menu 一鍵設定
render.yaml           Render 自動部署設定
requirements.txt      套件清單
.env.template         環境變數範本
.gitignore            防憑證洩漏
DEPLOY.md             雲端部署 SOP
README.md             專案總覽
SKILL.md              本技能檔
test-checklist.md     測試清單
agent-instructions-A.txt  LINE OA 後台清理
install.ps1 / start.ps1  本機備用腳本
assets/               品牌素材
  ├ rich-menu-2500x1686.png
  ├ rich-menu-config.json
  ├ logo-3qgongwan-800.png
  ├ welcome-banner-1200x628.png
  └ og-image-1200x630.png
```

## 故障排除
- Bot 沒回 → Render Logs → 環境變數 → Webhook URL 含 /line/webhook
- LINE 預設回覆出現 → LINE OA Manager → Bot mode + 全關自動回應
- 路由錯誤 → 檢查 route() 優先序,上方先攔截
- 關鍵字沒生效 → 確認 _normalize() 有 .lower()，中文不受影響
- Render 睡眠 → cron-job.org 每10分鐘 ping 根路徑 /

## 常見維護

| 任務 | 操作 |
|------|------|
| 加觸發詞 | 改頂層 KW_* 常數 |
| 改回覆文案 | 改頂層 REPLY_* 或 route() 內 return |
| 加新路由 | route() 內加 if 區塊,注意優先序 |
| 改歡迎訊息 | handle_follow() 內改文字 |
| 換 Rich Menu | 改圖 → 重跑 setup_richmenu.py |

## 安全紅線
- .env 不上 Git
- Channel Secret / Access Token 不貼對話、不截圖
- 洩漏 → LINE Console Reissue → 更新 Render 環境變數
