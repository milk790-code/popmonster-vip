# 學誼接線台 v4 — QR／印刷素材 QA

日期：2026-07-11（Asia/Taipei）

## 固定 URL

| 用途 | 內容 |
| --- | --- |
| 名片 | `https://popmonster.vip/go?src=business-card` |
| 出貨插卡 | `https://popmonster.vip/go?src=package-insert` |
| 社群 | `https://popmonster.vip/go?src=social` |

## QR 契約

- Model 2、Version 4、Error Correction Q。
- 33 x 33 data modules，四邊各 4 modules quiet zone，完整 41 x 41。
- SVG 固定 `viewBox="0 0 41 41"`，PNG 固定 1640 x 1640 px、每 module 40 px。
- 黑碼白底，不放 logo、不圓角、不依賴第三方 QR 服務。

## 驗證證據

| 檢查 | 結果 |
| --- | --- |
| Delivery asset unit tests | 3/3 通過 |
| 原始 QR PNG - OpenCV | 3/3 通過 |
| 原始 QR PNG - ZXing-C++ | 3/3 通過 |
| 300 DPI 印刷 proof - OpenCV | 2/2 通過 |
| 300 DPI 印刷 proof - ZXing-C++ | 2/2 通過 |
| PDF 150 DPI render - OpenCV | 2/2 通過 |
| PDF 150 DPI render - ZXing-C++ | 2/2 通過 |
| PDF render 視覺檢查 | 無裁切、重疊、缺字或黑塊 |

## PDF boxes

- 名片：MediaBox／BleedBox 96 x 60 mm；TrimBox 90 x 54 mm；3 mm 出血。
- 通用插卡：MediaBox／BleedBox 106 x 154 mm；TrimBox 100 x 148 mm；3 mm 出血。
- Proof 皆為 300 DPI；QR 成品外框分別為 22 x 22 mm、42 x 42 mm。

## 未自動放行

- Canva 連接器目前回 HTTP 451，尚未建立私人 Canva 草稿。
- 公開分享、印刷下單與付款未執行。
- 印刷前仍須 100% 實際尺寸輸出，使用 iOS 與 Android 各掃一次。
