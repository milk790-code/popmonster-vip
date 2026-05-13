# 3Q貢丸 LINE Bot v2.0 · 部署套件

台灣在地品牌孵化所 · 客服機器人完整部署包

---

## 主推路線 · 雲端部署

讀 **DEPLOY.md** 一份檔案就能完成。

```
段落 1  上傳 GitHub     3 分鐘
段落 2  連到 Render     4 分鐘
段落 3  接回 LINE       1 分鐘
段落 4  代理 + 測試     3 分鐘
```

---

## v2.0 更新內容

```
修 Bug:
✅ 記憶體洩漏（去重 set 改 TTL dict）
✅ Webhook 簽名驗證修正
✅ 加好友改用 reply 省 push 額度
✅ 全形/半形容錯

補路由:
✅ 「送出」十題表收件確認
✅ 「約諮詢」不再被攔截
✅ 新增「品牌」「合作」「案例」等入口詞
✅ 空訊息/超長訊息防護

詳見 CODE-REVIEW.md
```

---

## 檔案說明

```
雲端部署
├─ DEPLOY.md                雲端部署 SOP
├─ render.yaml              Render 設定檔
├─ requirements.txt         套件清單

LINE Bot 核心
├─ main.py                  客服機器人 v2.0（8 路由 + 歡迎）
├─ agent-instructions-A.txt LINE OA 後台清理指令
├─ test-checklist.md        測試 12 條清單

品牌素材
├─ assets/
│  ├─ hero-card.png         品牌主視覺（1200×628,OG image）
│  ├─ service-500.png       500 生圖方案卡（1080×1080,IG）
│  ├─ service-marketing.png 客製行銷方案卡（1080×1080,IG）
│  ├─ rich-menu-3x1.png     LINE Rich Menu（2500×843,3 格）
│  └─ welcome-card.png      加好友歡迎卡（1200×628）

本機備用
├─ install.ps1              一鍵安裝
├─ start.ps1                一鍵啟動
├─ .env.template            環境變數範本

工具
├─ .gitignore               防憑證上傳
├─ CODE-REVIEW.md           Bug 報告 + 修正清單
└─ README.md                本檔
```

---

## 素材用途

| 素材 | 尺寸 | 用在哪 |
|------|------|--------|
| hero-card.png | 1200×628 | LINE OA 背景圖 / 社群分享預覽 |
| service-500.png | 1080×1080 | IG 貼文 / LINE 圖片訊息 |
| service-marketing.png | 1080×1080 | IG 貼文 / LINE 圖片訊息 |
| rich-menu-3x1.png | 2500×843 | LINE Rich Menu 背景圖 |
| welcome-card.png | 1200×628 | LINE 歡迎圖文訊息 |

---

## 安全紅線

```
1. .env 絕對不上傳 Git
2. .env 內容不貼進任何對話
3. Channel Secret / Access Token 不截圖
4. 外洩 → LINE Console 點 Reissue 重發
```
