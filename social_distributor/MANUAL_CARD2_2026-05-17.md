# 卡 2 手動發文手冊 — 2026-05-17 21:00 Asia/Taipei

> 路徑 A：backend / OAuth 還沒齊，今晚這張卡走手動。
> 觸發 remote-control skill：在主對話打 `夜班啟動` 把這份手冊丟給 Claude，
> 它會逐項陪你做完。

## 影片
- 1080×1920 直立短影音（卡 2 對應的那支，本機已剪好）

## 標題 / 主文
> 99% 的 愛車一族 正在親手 搞砸 自己的漆面

```
99% 愛車一族每週都在親手搞砸自己的漆面
五個錯誤你一定犯過至少三個
不預洗直接擦就是砂紙磨漆
留言想要送你五大錯誤對應解法卡

#米速 #泡泡怪獸 #汽車美容 #拋光 #鍍膜 #洗車錯誤 #兩桶水法 #漆面保養 #新手洗車
```

## 三平台同步動作（21:00 ± 5 min）

| 平台 | 動作 |
|---|---|
| FB Page（米速 / 泡泡怪獸） | 上傳影片 → 貼上 caption → 發布 |
| IG Reels | 上傳影片 → 貼上 caption → 封面取片頭 → 發布 |
| TikTok | 上傳影片 → 貼上 caption（hashtag 直接寫） → 發布 |

## 釘留言（發布完馬上做）

```
👇 留言「解法卡」我私訊送你五大錯誤對應解法 PDF
```

三平台都釘。

## 24h 三件套尾段（23:00 前）

1. **跨平台留言鏡像** — FB 留言區有人問什麼，IG / TikTok 同步貼類似回答
2. **私訊回覆** — 留言「解法卡」的人，私訊送 PDF（之前準備好的素材包）
3. **互動截圖** — FB / IG / TikTok 各截一張前 1 小時數據，明天歸檔

## 數據回填（明天）

實際發文 URL 記下來：

```
FB:     https://www.facebook.com/...
IG:     https://www.instagram.com/reel/...
TikTok: https://www.tiktok.com/@.../video/...
```

Phase 1 backend 上線後，可以把這三個 URL 補回 `posts.targets[*].external_post_id`
欄位，讓 insights 串得起來。

---

> 卡 5（05-18 20:30）、卡 3（05-19 21:00）、卡 1（05-20 20:30）、卡 4（05-21 21:00）
> 如果到時 pipeline 還沒齊，複製這份手冊改 caption 即可。
> 五張卡的 caption 模板都在 `backend/scripts/seed_sprint_v1.py` 的 `CARDS` list。
