# 3Q貢丸 LINE Bot 測試清單（v2.0）

## 測試前準備

```
雲端版(Render):
1. 確認 Render 服務已部署完成（Dashboard 顯示 Live）
2. 確認 LINE Developers Console Webhook URL 指向 Render URL + /line/webhook
3. 確認 LINE OA Manager 後台已照 agent-instructions-A.txt 全部關閉

本機版(備用):
1. 刪除既有的 3Q貢丸好友（若已加過）
2. 確認 install.ps1 跑完 + .env 兩值已填
3. 確認 start.ps1 已執行 + ngrok http 8001 已開
4. 確認 LINE Console Webhook URL 已更新為當前 ngrok 網址
```

## 核心 7 條測試

| # | 動作 | 預期回覆 |
|---|------|---------|
| 1 | 用 LINE 重新加 3Q貢丸 為好友 | 收到歡迎訊息 + 主選單 |
| 2 | 傳「開始生圖」 | 十題探尋表（不是 500 方案介紹） |
| 3 | 傳「多少錢」 | 兩條服務分流 |
| 4 | 傳「客服」 | 人工小編窗口 |
| 5 | 傳「推廣」 | 客製行銷方案 + 目標承諾書 |
| 6 | 傳「項目有什麼」 | 兩條服務分流 |
| 7 | 連發 5 次「你好」 | 5 次都收主選單（不出現 LINE 預設回覆） |

## v2.0 新增 5 條測試

| # | 動作 | 預期回覆 |
|---|------|---------|
| 8 | 傳「送出」 | 十題表收件確認（不是主選單） |
| 9 | 傳「約諮詢」 | 預約流程（不是諮詢分流） |
| 10 | 傳「品牌」 | 諮詢分流（不是主選單） |
| 11 | 傳全形「５００」 | 500 方案（全形容錯） |
| 12 | 傳純空白 | 主選單（不 crash） |

## 通過標準

```
核心 7 條:  6/7 以上 = 上線可用
全部 12 條: 10/12 以上 = v2.0 完整通過
```

## 常見卡點

```
卡點 1  仍出現「感謝您的訊息！很抱歉...」
       → LINE OA Manager 後台沒清乾淨,再跑一次 agent-instructions-A.txt

卡點 2  完全沒回覆
       → 雲端版: Render Dashboard → Logs 看有沒有 POST 進來
       → 本機版: ngrok URL 變了沒同步 / uvicorn 已停止

卡點 3  回的內容錯誤
       → main.py route() 有 bug,把輸入和實際回覆貼回對話

卡點 4  加好友沒歡迎訊息
       → 確認 handle_follow 函式存在
       → 確認 OA Manager Greeting message = OFF
```
