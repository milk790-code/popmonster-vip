# 學誼接線台 v4 素材與印刷規格

## 固定 QR

| 用途 | URL | 公開資產 |
| --- | --- | --- |
| 名片 | `https://popmonster.vip/go?src=business-card` | `qr/go-business-card.svg`、`qr/go-business-card-1640.png` |
| 出貨插卡 | `https://popmonster.vip/go?src=package-insert` | `qr/go-package-insert.svg`、`qr/go-package-insert-1640.png` |
| 社群 | `https://popmonster.vip/go?src=social` | `qr/go-social.svg`、`qr/go-social-1640.png` |

QR 固定為 Model 2、Version 4、Error Correction Q。資料矩陣 33 x 33 modules，四邊各保留 4 modules quiet zone，完整矩陣為 41 x 41。PNG 為 1640 x 1640 px、每 module 40 px、純黑白、不放 logo、不做圓角；SVG 使用 `viewBox="0 0 41 41"` 與 `crispEdges`。

名片成品 QR 外框固定 22 x 22 mm；出貨插卡成品 QR 外框固定 42 x 42 mm。不得由 Canva 動態 QR、QR Server 或第三方 CDN 重新產生。

## 社群尺寸

- OG：1200 x 630 px。
- QR Story：1080 x 1920 px，使用 `src=social`。
- 分享卡：1080 x 1350 px，使用 `src=social`。

## 印刷尺寸

- 名片 TrimBox：90 x 54 mm；四邊 3 mm 出血，BleedBox／MediaBox：96 x 60 mm；300 DPI proof：1134 x 709 px。
- 通用插卡 TrimBox：100 x 148 mm；四邊 3 mm 出血，BleedBox／MediaBox：106 x 154 mm；300 DPI proof：1252 x 1819 px。
- 關鍵文字與 QR 保持在裁切線內至少 5 mm；PDF 已設定 TrimBox、BleedBox 與 300 DPI 全版 proof。

## 放行 Gate

1. PNG 先以 OpenCV 與 ZXing-C++ 兩個獨立 decoder 驗證內容。
2. PDF 需 render 成 PNG，確認無裁切、重疊、缺字、黑塊或模糊 QR。
3. 名片與插卡以 100% 實際尺寸輸出後，分別用 iOS 與 Android 各掃一次。
4. Canva 只建立私人草稿；公開分享、印刷下單與付款不得由自動化執行。
