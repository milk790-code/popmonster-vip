/* 泡泡怪獸 POP MONSTER · 商品目錄 v2(2026-06-07 規格×價格全展開)
   來源:蝦皮賣家中心 mass_update 官方匯出檔。每 SKU 含全部規格(spec)與對應價格。
   下單頁依 variants 顯示規格選擇;勿手改數字,改價請重跑生成腳本或同步蝦皮後台。 */
const PM_PRODUCTS = [
  { sku:"a001", name:"天使塗層 Guard", cat:"鍍膜", variants:[{spec:"30ml入門體驗款 可兌30L成品", price:599},{spec:"100ml熱銷首選款 可兌100L成品", price:999},{spec:"200ml團購優惠款 可兌200L成品", price:1799},{spec:"300ml超值優惠款 可兌300L成品", price:2499}] },
  { sku:"a002", name:"米速研磨劑三件組", cat:"研磨", variants:[{spec:"GA/DA適用套裝", price:1999},{spec:"RO適用套裝", price:1999}] },
  { sku:"a003", name:"米速三號 80 番", cat:"研磨", variants:[{spec:"30g樣品", price:299},{spec:"100g", price:599},{spec:"200g", price:999},{spec:"300g", price:1399}] },
  { sku:"a004", name:"米速伍號 600 番", cat:"研磨", variants:[{spec:"30g試用品樣品", price:299},{spec:"100g", price:599},{spec:"200g", price:999},{spec:"300g", price:1299}] },
  { sku:"a005", name:"米速拾號 1000 番", cat:"研磨", variants:[{spec:"30g樣品", price:299},{spec:"100g", price:599},{spec:"200g", price:999},{spec:"300g", price:1299}] },
  { sku:"a006", name:"RO 訂製粗棉拋光盤", cat:"耗材", variants:[{spec:"1入", price:699},{spec:"2入 入門囤貨", price:1099},{spec:"3入 常規補貨", price:1599},{spec:"6入 划算", price:2999}] },
  { sku:"a007", name:"鐵粉清潔劑", cat:"清潔", variants:[{spec:"1入", price:599},{spec:"2入 雙入補貨", price:999},{spec:"3入 入門囤貨", price:1399},{spec:"6入 划算", price:2499}] },
  { sku:"a008", name:"泡沫洗車液", cat:"清潔", variants:[{spec:"100ml", price:199},{spec:"200ml", price:299},{spec:"500ml", price:599}] },
  { sku:"a009", name:"液體橡皮擦", cat:"清潔", variants:[{spec:"1入", price:599},{spec:"2入 雙入補貨", price:999},{spec:"3入 入門囤貨", price:1299},{spec:"6入 划算", price:2499}] },
  { sku:"a010", name:"玻璃鍍膜劑(淨護噴霧)", cat:"鍍膜", variants:[{spec:"1入 ,⚠️無噴頭", price:399},{spec:"2入 雙入補貨,⚠️無噴頭", price:659},{spec:"3入 入門囤貨,⚠️無噴頭", price:899},{spec:"6入 划算,⚠️無噴頭", price:1659}] },
  { sku:"a012", name:"內飾清潔劑 APC 橙油款", cat:"清潔", variants:[{spec:"100ml", price:99},{spec:"200ml", price:199},{spec:"500ml", price:489}] },
  { sku:"a013", name:"高端真皮清潔劑", cat:"護理", variants:[{spec:"單一規格", price:1999}] },
  { sku:"a017", name:"雨刷精 1200 高濃縮", cat:"護理", variants:[{spec:"單一規格", price:399}] },
  { sku:"a020", name:"輪圈清潔劑(木瓜重油雙清)", cat:"清潔", variants:[{spec:"1入 ,20倍稀釋最高可稀釋65倍", price:599},{spec:"2入 雙入補貨,20倍稀釋最高可稀釋65倍", price:999},{spec:"3入 入門囤貨,20倍稀釋最高可稀釋65倍", price:1399},{spec:"6入 划算,20倍稀釋最高可稀釋65倍", price:2499}] },
  { sku:"a024", name:"輪胎塑件精油", cat:"護理", variants:[{spec:"100ml嚐鮮裝", price:299},{spec:"200ml", price:499},{spec:"500ml", price:999}] },
  { sku:"a030", name:"痕厲害水漬去除劑", cat:"護理", variants:[{spec:"1入 ,不附噴頭", price:399},{spec:"2入 雙入補貨,不附噴頭", price:659},{spec:"3入 入門囤貨,不附噴頭", price:899},{spec:"6入 划算,不附噴頭", price:1659}] },
  { sku:"a031", name:"全能清潔劑(萬用神噴)", cat:"清潔", variants:[{spec:"1入 ,不附噴頭", price:599},{spec:"2入 雙入補貨,不附噴頭", price:999},{spec:"3入 入門囤貨,不附噴頭", price:1299},{spec:"6入 划算,不附噴頭", price:2499}] },
  { sku:"a032", name:"丹若免刷預洗洗車液", cat:"清潔", variants:[{spec:"1入 ,最高300倍稀釋", price:599},{spec:"2入 雙入補貨,最高300倍稀釋", price:999},{spec:"3入 入門囤貨,最高300倍稀釋", price:1299},{spec:"6入 划算,最高300倍稀釋", price:2499}] },
  { sku:"a033", name:"RO 訂製鏡面拋光盤", cat:"耗材", variants:[{spec:"1入", price:699},{spec:"2入 入門囤貨", price:1199},{spec:"3入 常規補貨", price:1599},{spec:"6入 划算", price:2999}] },
  { sku:"a034", name:"無毒脫脂神噴", cat:"清潔", variants:[{spec:"100ml", price:199},{spec:"200ml", price:299},{spec:"500ml", price:499}] },
  { sku:"a035", name:"無鈰玻璃油膜去除膏", cat:"清潔", variants:[{spec:"100克", price:249},{spec:"200克", price:489},{spec:"420贈油膜擦", price:799}] },
  { sku:"a036", name:"磨泥潤滑液", cat:"耗材", variants:[{spec:"100ml", price:99},{spec:"200ml", price:199},{spec:"500ml", price:399}] },
  { sku:"a037", name:"火山去污泥(洗車黏土)", cat:"清潔", variants:[{spec:"紅色（重切）", price:888},{spec:"灰色（細切）", price:999}] },
  { sku:"a038", name:"包膜店專用除膠劑", cat:"清潔", variants:[{spec:"1入", price:399},{spec:"2入 雙入補貨", price:659},{spec:"3入 入門囤貨", price:899},{spec:"6入 划算", price:1659}] },
  { sku:"a039", name:"RO/GA/DA 重切羊毛盤", cat:"耗材", variants:[{spec:"1入", price:699},{spec:"2入 入門囤貨", price:1100},{spec:"3入 常規補貨", price:1590},{spec:"6入 划算", price:2999}] },
  { sku:"a040", name:"米速 RO 商用重切拋光劑", cat:"研磨", variants:[{spec:"100g樣品", price:299},{spec:"200g", price:429},{spec:"300g", price:699},{spec:"600g店家必囤", price:1199}] },
  { sku:"a041", name:"米速鍍鉻拋光劑", cat:"研磨", variants:[{spec:"單一規格", price:1999}] },
  { sku:"a042", name:"柔和真皮清潔劑(慕斯款)", cat:"護理", variants:[{spec:"50ml", price:199},{spec:"100ml", price:299},{spec:"200ml", price:499},{spec:"500ml（贈慕斯瓶）", price:899}] },
  { sku:"a043", name:"柏油清潔劑", cat:"清潔", variants:[{spec:"1入 ,⚠️無噴頭", price:399},{spec:"2入 雙入補貨,⚠️無噴頭", price:659},{spec:"3入 入門囤貨,⚠️無噴頭", price:899},{spec:"6入 划算,⚠️無噴頭", price:1659}] },
];
const PM_SHIPPING = { leadDaysText: "付款後 3 個工作天內出貨", note: "預購品於商品頁標明預計出貨日" };
if (typeof module!=="undefined") module.exports = { PM_PRODUCTS, PM_SHIPPING };
