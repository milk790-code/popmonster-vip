/* 泡泡怪獸 POP MONSTER · 商品目錄 v2(2026-06-07 規格×價格全展開)
   來源:蝦皮賣家中心 mass_update 官方匯出檔。每 SKU 含全部規格(spec)與對應價格。
   下單頁依 variants 顯示規格選擇;勿手改數字,改價請重跑生成腳本或同步蝦皮後台。 */
const PM_PRODUCTS = [
  { sku:"a001", name:"天使塗層 Guard", nameEn:"Angel Coating Guard", cat:"鍍膜", variants:[{spec:"30ml入門體驗款", price:699},{spec:"100ml熱銷首選款", price:1199},{spec:"200ml團購優惠款", price:2199},{spec:"300ml超值優惠款", price:2999}] },
  { sku:"a002", name:"米速研磨劑三件組", nameEn:"MISO Polish 3-Piece Set", cat:"研磨", variants:[{spec:"單一規格", price:4099}] },
  { sku:"a003", name:"米速三號 80 番", nameEn:"MISO No.3 Heavy-Cut (80)", cat:"研磨", variants:[{spec:"30g樣品不划算", price:359},{spec:"100g", price:699},{spec:"200g", price:1199},{spec:"300g", price:1699}] },
  { sku:"a004", name:"米速伍號 600 番", nameEn:"MISO No.5 One-Step (600)", cat:"研磨", variants:[{spec:"30g試用品（不划算）", price:359},{spec:"100g", price:699},{spec:"200g", price:1199},{spec:"300g", price:1599}] },
  { sku:"a005", name:"米速拾號 1000 番", nameEn:"MISO No.10 Mirror Finish (1000)", cat:"研磨", variants:[{spec:"30g樣品（不划算）", price:299},{spec:"100g", price:599},{spec:"200g", price:999},{spec:"300g", price:1299}] },
  { sku:"a006", name:"RO 訂製粗棉拋光盤", nameEn:"RO Custom Foam Pad (Coarse)", cat:"耗材", variants:[{spec:"1入 體驗裝（不划算）", price:899},{spec:"2入 入門囤貨", price:1299},{spec:"3入 常規補貨", price:1899},{spec:"6入 最划算", price:3599}] },
  { sku:"a007", name:"鐵粉清潔劑", nameEn:"Iron Remover", cat:"清潔", variants:[{spec:"1入 體驗裝（不划算）", price:699},{spec:"2入 入門囤貨", price:1199},{spec:"3入 常規補貨", price:1599},{spec:"6入 最划算", price:2999}] },
  { sku:"a008", name:"泡沫洗車液", nameEn:"Foam Car Wash", cat:"清潔", variants:[{spec:"100ml體驗裝", price:239},{spec:"200ml", price:359},{spec:"500ml", price:699}] },
  { sku:"a009", name:"液體橡皮擦", nameEn:"Liquid Eraser", cat:"清潔", variants:[{spec:"1入 體驗裝（不划算）", price:699},{spec:"2入 入門囤貨", price:1199},{spec:"3入 常規補貨", price:1599},{spec:"6入 最划算", price:2999}] },
  { sku:"a010", name:"玻璃鍍膜劑(淨護噴霧)", nameEn:"Glass Care Spray", cat:"鍍膜", variants:[{spec:"1入 ,⚠️無噴頭", price:499},{spec:"2入 雙入補貨,⚠️無噴頭", price:799},{spec:"3入 入門囤貨,⚠️無噴頭", price:1099},{spec:"6入 划算,⚠️無噴頭", price:1999}] },
  { sku:"a012", name:"內飾清潔劑 APC 橙油款", nameEn:"Interior Cleaner APC", cat:"清潔", variants:[{spec:"100ml", price:99},{spec:"200ml", price:189},{spec:"500ml", price:469}] },
  { sku:"a013", name:"高端真皮清潔劑", nameEn:"Premium Leather Cleaner", cat:"護理", variants:[{spec:"單一規格", price:2399}] },
  { sku:"a017", name:"雨刷精 1200 高濃縮", nameEn:"Windshield Washer 1200x", cat:"護理", variants:[{spec:"單一規格", price:499}] },
  { sku:"a020", name:"輪圈清潔劑(木瓜重油雙清)", nameEn:"Wheel Cleaner 2-in-1", cat:"清潔", variants:[{spec:"1入 體驗裝（不划算）,20倍稀釋最高可稀釋65倍", price:699},{spec:"2入 入門囤貨,20倍稀釋最高可稀釋65倍", price:1199},{spec:"3入 常規補貨,20倍稀釋最高可稀釋65倍", price:1599},{spec:"6入 最划算,20倍稀釋最高可稀釋65倍", price:2999}] },
  { sku:"a024", name:"輪胎塑件精油", nameEn:"Tire & Trim Oil", cat:"護理", variants:[{spec:"100ml嚐鮮裝", price:359},{spec:"200ml", price:599},{spec:"500ml", price:1199}] },
  { sku:"a030", name:"痕厲害水漬去除劑", nameEn:"Water Spot Remover", cat:"護理", variants:[{spec:"1入 體驗裝（不划算）,不附噴頭", price:499},{spec:"2入 入門囤貨,不附噴頭", price:799},{spec:"3入 常規補貨,不附噴頭", price:1099},{spec:"6入 最划算,不附噴頭", price:1999}] },
  { sku:"a031", name:"全能清潔劑(萬用神噴)", nameEn:"All-Purpose Cleaner", cat:"清潔", variants:[{spec:"1入 體驗裝（不划算）,不附噴頭", price:699},{spec:"2入 入門囤貨,不附噴頭", price:1199},{spec:"3入 常規補貨,不附噴頭", price:1599},{spec:"6入 最划算,不附噴頭", price:2999}] },
  { sku:"a032", name:"丹若免刷預洗洗車液", nameEn:"Danro Touchless Pre-Wash", cat:"清潔", variants:[{spec:"1入 體驗裝（不划算）,最高300倍稀釋", price:699},{spec:"2入 入門囤貨,最高300倍稀釋", price:1199},{spec:"3入 常規補貨,最高300倍稀釋", price:1599},{spec:"6入 最划算,最高300倍稀釋", price:2999}] },
  { sku:"a033", name:"RO 訂製鏡面拋光盤", nameEn:"RO Custom Foam Pad (Mirror)", cat:"耗材", variants:[{spec:"1入 體驗裝（不划算）", price:899},{spec:"2入 入門囤貨", price:1299},{spec:"3入 常規補貨", price:1899},{spec:"6入 最划算", price:3599}] },
  { sku:"a034", name:"無毒脫脂神噴", nameEn:"Prep Degreaser Spray", cat:"清潔", variants:[{spec:"100ml", price:239},{spec:"200ml", price:359},{spec:"500ml", price:599}] },
  { sku:"a035", name:"無鈰玻璃油膜去除膏", nameEn:"Cerium-Free Glass Polish", cat:"清潔", variants:[{spec:"100克", price:299},{spec:"200克", price:589},{spec:"420贈油膜擦", price:999}] },
  { sku:"a036", name:"磨泥潤滑液", nameEn:"Clay Lubricant", cat:"耗材", variants:[{spec:"100ml", price:99},{spec:"200ml", price:189},{spec:"500ml", price:469}] },
  { sku:"a037", name:"火山去污泥(洗車黏土)", nameEn:"Volcanic Clay Bar", cat:"清潔", variants:[{spec:"紅色（重切）", price:1099},{spec:"灰色（細切）", price:1199}] },
  { sku:"a038", name:"包膜店專用除膠劑", nameEn:"Adhesive Remover", cat:"清潔", variants:[{spec:"1入 體驗裝（不划算）", price:499},{spec:"2入 入門囤貨", price:799},{spec:"3入 常規補貨", price:1099},{spec:"6入 最划算", price:1999}] },
  { sku:"a039", name:"RO/GA/DA 重切羊毛盤", nameEn:"Heavy-Cut Wool Pad", cat:"耗材", variants:[{spec:"1入 體驗裝（不划算）", price:899},{spec:"2入 入門囤貨", price:1299},{spec:"3入 常規補貨", price:1899},{spec:"6入 最划算", price:3599}] },
  { sku:"a040", name:"米速 RO 商用重切拋光劑", nameEn:"MISO RO Commercial Heavy-Cut", cat:"研磨", variants:[{spec:"100g樣品不划算", price:359},{spec:"200g", price:529},{spec:"300g", price:779},{spec:"600g店家必囤", price:1399}] },
  { sku:"a041", name:"米速鍍鉻拋光劑", nameEn:"MISO Chrome Polish", cat:"研磨", variants:[{spec:"單一規格", price:2399}] },
  { sku:"a042", name:"柔和真皮清潔劑(慕斯款)", nameEn:"Gentle Leather Mousse", cat:"護理", variants:[{spec:"50ml", price:239},{spec:"100ml", price:359},{spec:"200ml", price:599},{spec:"500ml（贈慕斯瓶）", price:1099}] },
  { sku:"a043", name:"柏油清潔劑", nameEn:"Tar Remover", cat:"清潔", variants:[{spec:"1入 體驗裝（不划算）,⚠️無噴頭", price:499},{spec:"2入 入門囤貨,⚠️無噴頭", price:799},{spec:"3入 常規補貨,⚠️無噴頭", price:1099},{spec:"6入 最划算,⚠️無噴頭", price:1999}] },
];
const PM_CAT_EN = {"鍍膜": "Coating", "研磨": "Polishing", "耗材": "Pads", "清潔": "Cleaning", "護理": "Care"};
const PM_SHIPPING = { leadDaysText: "付款後 3 個工作天內出貨", note: "預購品於商品頁標明預計出貨日", leadDaysTextEn: "Ships within 3 business days after payment", noteEn: "Pre-order items show estimated ship date" };
if (typeof module!=="undefined") module.exports = { PM_PRODUCTS, PM_SHIPPING };
