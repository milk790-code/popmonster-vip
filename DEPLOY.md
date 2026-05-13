# 3Q貢丸 LINE Bot · Render 雲端部署

不用本機 PowerShell,不用 ngrok,不用每天開機。
全程點滑鼠,總共三段共 10 分鐘左右。

---

## 全程預覽

```
段落 1  上傳到 GitHub    3 分鐘   點 3 次滑鼠
段落 2  連到 Render      4 分鐘   點 5 次滑鼠 + 貼 2 個值
段落 3  接回 LINE Console 1 分鐘   貼 1 次 URL
段落 4  代理清理 + 測試  3 分鐘   貼 1 段指令 + 測 12 句
```

---

## 段落 1 · 上傳到 GitHub（3 分鐘）

### 1-1 開 GitHub 帳號

去 https://github.com/signup 註冊

### 1-2 新建 repo

去 https://github.com/new

```
Repository name      3qgongwan-bot
Description          3Q貢丸 LINE 客服機器人
Public / Private     選 Private
Add a README file    不勾
.gitignore           不勾
License              None
```

點 **Create repository**

### 1-3 上傳檔案

點 **uploading an existing file**

```
1. 把資料夾內所有檔案全選（含 assets 資料夾）
2. 拖曳到 GitHub 上傳區
3. ⚠ 確認 .env 沒被選到（只要 .env.template）
4. Commit message 填: Initial commit v2.0
5. 點 Commit changes
```

---

## 段落 2 · 連到 Render（4 分鐘）

### 2-1 註冊 Render

去 https://dashboard.render.com/register → **Sign up with GitHub**

### 2-2 新建 Web Service

Dashboard → **New +** → **Web Service** → 連到 **3qgongwan-bot**

### 2-3 Render 自動讀 render.yaml

自動填好所有欄位,點 **Apply**

### 2-4 填兩個環境變數

**Environment** → **Add Environment Variable**

```
Key:    LINE_CHANNEL_SECRET
Value:  [從 LINE Developers Console 取得]

Key:    LINE_CHANNEL_ACCESS_TOKEN
Value:  [從 LINE Developers Console 取得]
```

⚠ 這兩個值絕對不要貼進對話、不要截圖

### 2-5 拿到固定 URL

部署完成後複製 `https://3qgongwan-bot.onrender.com`

---

## 段落 3 · 接回 LINE Console（1 分鐘）

```
Webhook URL: https://3qgongwan-bot.onrender.com/line/webhook
```

點 **Update** → **Verify** → 看到綠勾
開啟 **Use webhook** + **Webhook redelivery**

---

## 段落 4 · 後台清理 + 測試（3 分鐘）

1. `agent-instructions-A.txt` 給瀏覽器代理跑
2. 照 `test-checklist.md` 跑 12 條測試

---

## Render 免費方案提醒

```
1. 閒置 15 分鐘睡眠，首次喚醒約 30 秒
   用 https://cron-job.org 每 10 分鐘 ping 可保持清醒
2. 每月 750 小時免費，夠一個服務 24/7
3. Build 失敗看 Render Logs
4. 永不睡眠: Starter USD 7/月
```
