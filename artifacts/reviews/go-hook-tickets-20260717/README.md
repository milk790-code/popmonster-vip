# POP 免費接線台｜強鉤子成果票券審核包

日期：2026-07-17（Asia/Taipei）

## 本輪變更

- 八個入口各自加入真實、可交付的強鉤子。
- `hook`、`freeDeliverable`、`freeScope` 與 destinations 全部集中在同一份 service registry。
- 完整目錄與兩步分流結果共用 registry，不再各自維護文案。
- 卡片改為「鉤子 → 免費拿到 → 你準備 → 免費範圍 → 服務邊界 → CTA」。
- 新增紙本成果票券視覺，維持碳黑、黃銅與紙張顧問感。

## 營運範圍

- 人工服務預設每人一次、一次一個地址／事件／商品／路線／地點／車況或一項素材。
- CreatorKit 可直接使用，但工具產出仍需自行檢查。
- 租屋、合約、精品只做公開資訊或資料初篩，不提供權利、法律或真偽結論。
- 票價、房況、庫存與規格以查詢或官網當下資訊為準，不保留、不代訂。
- 不承諾回覆時間、成交、獲利、票價、鑑定或法律結果。

## 驗收證據

- `python3 -m unittest discover -s tests`：36 tests passed。
- `node --check js/go.js`、`node --check js/go-analytics.js`、`git diff --check`：通過。
- 390×844、768×1024、1280×720、1440×900：8 cards、8 tickets、0 overflow、互動目標至少 44px。
- 兩步分流、重新選擇、POP 雙 CTA、鍵盤 focus、reduced motion：通過。
- GA4：未同意前 0 個 Google Analytics 請求；同意後才載入。
- Browser 與 Computer Use：實際 Chrome 輔助樹可讀到八入口、八鉤子、八票券與所有 CTA。

## 截圖

1. `01-mobile-390x844-hero.png`
2. `02-desktop-1440x900-hero.png`
3. `03-directory-1440x900.png`
4. `04-router-result-1440x900.png`
