# POP MONSTER 官網英文翻譯守則（translate.py 與人工翻譯共用）

Source: Traditional Chinese (Taiwan) pages of popmonster.vip, a Taiwanese car-care brand selling
coatings, compounds, cleaners and pads. Audience of the English site: car owners and detailers
outside Taiwan (Hong Kong, Singapore, Malaysia, US) who reach us on WhatsApp.

## Hard rules

1. Meaning only. Change the words, never the claims. Do not add benefits, numbers,
   certifications, guarantees, comparisons or urgency that the Chinese does not state. Keep every
   hedge and every caution ("no test data yet", "test on a small hidden area first",
   "ask us first"). If the Chinese is cautious, the English stays cautious.
2. Keep every number, ratio, unit, SKU, price and time exactly (1:100, 30g, 40°C, A035,
   NT$1,199, 15 min). Keep "NT$" prices in TWD; never convert currency.
3. Placeholders `<g0>…</g0>` and `<x1/>` are markup. Every one in the source must appear exactly
   once in the English, `<gN>` before `</gN>`. You may move them to fit English word order.
   Never add new ones.
4. Output only the translation. No quotes around it, no notes.
5. A segment may be a fragment of a sentence that code joins with a number or a product name
   (e.g. "再買 " + NT$500 + " 即享免運"). Keep leading/trailing spaces and make the fragment
   read correctly once joined.
6. Short UI labels stay short (buttons, nav, table headers). Sentence case for headings.

## Voice

Plain, direct, practical: an experienced detailer explaining to a customer. American English.
Short sentences. No marketing filler: never "elevate", "unleash", "game-changer", "seamless",
"cutting-edge", "revolutionary", "take it to the next level", "look no further". Avoid em-dash
chains; one dash per sentence at most. Do not start with "Introducing". Don't use exclamation
marks unless the Chinese has one.

## Contact and ordering (English site only)

The English site sends people to WhatsApp, not LINE and not Shopee:
- 「LINE 諮詢」「LINE 問用法」「LINE 詢問」「加 LINE 問」「先加 LINE 向小編確認」 →
  "WhatsApp us", "Ask on WhatsApp", "message us on WhatsApp first".
- 「用 LINE 送出訂單」「透過 LINE 下單」 → "send your order on WhatsApp".
- Shopee (蝦皮) is Taiwan-only. 「蝦皮賣場」 as a nav/store link → "WhatsApp order".
  Where the text is about Shopee itself (ratings, "5.0 蝦皮評分", Shopee return policy) translate
  literally: "Shopee".
- Bank transfer / home delivery (銀行轉帳、宅配到府、對帳後出貨) are domestic-Taiwan terms.
  In checkout text say "we confirm the total and shipping to your country on WhatsApp before
  you pay".
- 「滿 NT$2,000 免運」 is a Taiwan-only offer: "Free shipping in Taiwan over NT$2,000".
- LINE features that only exist in LINE (LINE official account, LINE membership, rich menu,
  「加入 LINE 會員」) keep "LINE".
- 小編 → "we" / "our team" (never "the editor").

## Brand and product names

| Chinese | English |
|---|---|
| 泡泡怪獸 POP MONSTER / 泡泡怪獸 / 泡怪 | POP MONSTER |
| 米速 MISO / 米速 | MISO |
| 丹若 DANRUO / 丹若 | DANRUO |
| 叁無 / 參無 | Sanwu (brand motto mark; don't explain it) |
| 叁無 × 重新定義汽美 | Sanwu × Redefining car care |
| 汽美 | car care / detailing |
| 天使塗層 Guard | Angel Coating Guard |
| 米速研磨劑三件組 | MISO Compound 3-Piece Set |
| 米速三號 80 番 | MISO No.3 Heavy Cut (80 grit) |
| 米速伍號 600 番 | MISO No.5 One-Step (600 grit) |
| 米速拾號 1000 番 | MISO No.10 Mirror Finish (1000 grit) |
| 拋光盤系列 | Polishing Pad Series |
| 鐵粉清潔劑 | Iron Remover |
| 泡沫洗車液 | Foam Car Wash |
| 液體橡皮擦 | Liquid Eraser |
| 玻璃鍍膜劑 | Glass Coating Spray |
| 內飾清潔劑 | Interior Cleaner |
| 皮革護理（真皮清潔劑） / 高端真皮清潔劑 | Leather Care (Leather Cleaner) |
| 雨刷精 | Windshield Washer Concentrate |
| 輪圈清潔劑 | Wheel Cleaner |
| 輪胎塑件精油 | Tire & Trim Oil |
| 痕厲害 | Water Spot Remover |
| 全能清潔劑（萬用神噴） | All-Purpose Cleaner |
| 丹若免刷預洗洗車液 | DANRUO Touchless Pre-Wash |
| RO 訂製鏡面拋光盤 黑色 | RO Custom Mirror Foam Pad (Black) |
| 無毒脫脂神噴 | Prep Degreaser Spray |
| 無鈰玻璃油膜去除膏 | Cerium-Free Glass Oil-Film Remover |
| 磨泥潤滑液 | Clay Lubricant |
| 火山去污泥（洗車黏土） | Volcanic Clay Bar |
| 包膜店專用除膠劑 | Adhesive Remover (for wrap shops) |
| RO 訂製羊毛盤 素黑軟漆專用 | RO Custom Wool Pad (for soft black paint) |
| 米速 RO 商用重切拋光劑 | MISO RO Commercial Heavy-Cut Compound |
| 米速鍍鉻拋光劑 | MISO Chrome Polish |
| 柔和真皮清潔劑（慕斯款） | Gentle Leather Cleaner (Mousse) |
| 柏油清潔劑 | Tar Remover |
| 超級泡沫洗車精 Super Foam | Super Foam Car Wash |
| 木瓜怪獸洗車打底劑 | Papaya Monster Wash Base |
| 黑曼羅酸性洗車泡沫 | Black Mandala Acidic Wash Foam |

Categories: 鍍膜系列 Coatings · 研磨系列 Compounds · 清潔系列 Cleaners · 護理系列 Care ·
耗材系列 Pads & Tools · 預洗系列 Pre-wash.

Site sections: 全部商品 All Products · 會員生態 Membership · 教學攻略 Guides · 關於我們 About ·
免費接線台 Free Help Desk · 品牌館 Brand · 系統館 Systems · 隱私權政策 Privacy Policy ·
服務條款 Terms of Service · 購物車 Cart · 加入購物車 Add to cart · 前往結帳 Checkout.

## Car-care terms

| Chinese | English |
|---|---|
| RO（旋轉機） | rotary polisher (RO) |
| DA（偏心機、偏心拋光機） | dual-action polisher (DA) |
| GA（強制偏心、齒輪驅動） | gear-driven / forced-rotation polisher (GA) |
| 番 / 番數 | grit (80 番 = 80 grit) |
| 研磨劑 | compound |
| 拋光劑 | polish |
| 一劑拋 | one-step polish |
| 重切 / 中切 / 細切 | heavy cut / medium cut / fine cut |
| 鏡面 | mirror finish |
| 拋光盤 / 海綿盤 / 羊毛盤 | polishing pad / foam pad / wool pad |
| 太陽紋 / 旋紋 | swirl marks / holograms |
| 刮痕 / 細紋 | scratches / fine scratches |
| 鍍膜 / 鍍晶 / 封體 | coating / ceramic-type coating / sealant |
| 包膜 / 車衣 | wrap / paint protection film (PPF) |
| 撥水 / 疏水 | water beading / hydrophobic |
| 水痕 / 水漬 / 水垢 | water spots / mineral deposits |
| 鐵粉 | iron fallout |
| 柏油 | tar |
| 油膜 | oil film (on glass) |
| 酸雨痕 / 鳥糞痕 / 樹膠 | acid-rain marks / bird-dropping etching / tree sap |
| 預洗 / 正洗 | pre-wash / contact wash |
| 泡沫壺 / PA 壺 / 手壓泡沫壺 | foam cannon / PA foam lance / pump foam sprayer |
| 稀釋比例 1:100 | dilution 1:100 |
| 濕上濕下 | apply wet, wipe off wet |
| 施工 | application / applying |
| 收水 | drying off (water sheeting off) |
| 漆面 / 車漆 | paint / paintwork |
| 電鍍 / 陽極處理 | chrome-plated / anodized |
| 內裝 / 內飾 | interior |
| 塑件 | plastic trim |
| 輪圈 | wheels (rims) |
| 汽美店 / 美容店 | detailing shop |
| 職人 | pro detailers |
| 開蠟 | (Chinese slang for a strong degreasing wash) strip wash |
