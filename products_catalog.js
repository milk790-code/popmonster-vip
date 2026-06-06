/* 泡泡怪獸 POP MONSTER · 商品目錄(2026-06-07 由官網現況盤點生成)
   ⚠️ price=蝦皮「單個」價,priceMax=蝦皮「最大容量」價(2026-06-07 自蝦皮賣場前端 API 實抓,29/29 全填;a013=高端真皮專用款 1999、a042=三重去污慕斯款 199–899(2026-06-07 自動判定對應)(2026-06-07 補:蝦皮後台 mass_update 匯出檔=官方權威價,a004 最大規格修正 999→1299))。其餘 null 待補(蝦皮反爬冷卻後續抓或學誼提供)。
   price=null 時下單頁自動只走「LINE 下單」路;填了價格即解鎖線上結帳。
   sku 對應官網 aXXX.html 與 img/aXXX-main.jpg。 */
const PM_PRODUCTS = [
  { sku:"a001", name:"天使塗層 Guard",            cat:"鍍膜", price:599, priceMax:2499,  unit:"瓶" },
  { sku:"a002", name:"米速研磨劑三件組",          cat:"研磨", price:1999, priceMax:1999, unit:"組" },
  { sku:"a003", name:"米速三號 80 番",            cat:"研磨", price:299, priceMax:1399, unit:"瓶" },
  { sku:"a004", name:"米速伍號 600 番",           cat:"研磨", price:299, priceMax:1299, unit:"瓶" },
  { sku:"a005", name:"米速拾號 1000 番",          cat:"研磨", price:299, priceMax:1299, unit:"瓶" },
  { sku:"a006", name:"拋光盤系列(RO 訂製粗棉)",   cat:"耗材", price:699, priceMax:2999, unit:"片" },
  { sku:"a007", name:"鐵粉清潔劑",                cat:"清潔", price:599, priceMax:2499, unit:"瓶" },
  { sku:"a008", name:"泡沫洗車液",                cat:"清潔", price:199, priceMax:599, unit:"瓶" },
  { sku:"a009", name:"液體橡皮擦",                cat:"清潔", price:599, priceMax:2499, unit:"瓶" },
  { sku:"a010", name:"玻璃鍍膜劑",                cat:"鍍膜", price:399, priceMax:1659, unit:"瓶" },
  { sku:"a012", name:"內飾清潔劑 APC 橙油款",     cat:"清潔", price:99, priceMax:489, unit:"瓶" },
  { sku:"a013", name:"皮革護理(高端真皮清潔劑)",  cat:"護理", price:1999, priceMax:1999, unit:"瓶" },
  { sku:"a017", name:"雨刷精 1200 高濃縮",        cat:"護理", price:399, priceMax:399, unit:"瓶" },
  { sku:"a020", name:"輪圈清潔劑(木瓜重油雙清)",  cat:"清潔", price:599, priceMax:2499, unit:"瓶" },
  { sku:"a024", name:"輪胎塑件精油",              cat:"護理", price:299, priceMax:999, unit:"瓶" },
  { sku:"a030", name:"痕厲害多功能水漬去除劑",    cat:"護理", price:399, priceMax:1659, unit:"瓶" },
  { sku:"a031", name:"全能清潔劑(萬用神噴)",      cat:"清潔", price:499, priceMax:2499, unit:"瓶" },
  { sku:"a032", name:"丹若免刷預洗洗車液",        cat:"清潔", price:599, priceMax:2499, unit:"瓶" },
  { sku:"a033", name:"RO 訂製鏡面拋光盤 黑色",    cat:"耗材", price:699, priceMax:2999, unit:"片" },
  { sku:"a034", name:"無毒脫脂神噴",              cat:"清潔", price:199, priceMax:499, unit:"瓶" },
  { sku:"a035", name:"無鈰玻璃油膜去除膏",        cat:"清潔", price:249, priceMax:799, unit:"罐" },
  { sku:"a036", name:"磨泥潤滑液",                cat:"耗材", price:99, priceMax:399, unit:"瓶" },
  { sku:"a037", name:"火山去污泥(洗車黏土)",      cat:"清潔", price:888, priceMax:999, unit:"塊" },
  { sku:"a038", name:"包膜店專用除膠劑",          cat:"清潔", price:399, priceMax:1659, unit:"瓶" },
  { sku:"a039", name:"RO 訂製羊毛盤 素黑軟漆專用",cat:"耗材", price:699, priceMax:2999, unit:"片" },
  { sku:"a040", name:"米速 RO 商用重切拋光劑",    cat:"研磨", price:299, priceMax:1199, unit:"瓶" },
  { sku:"a041", name:"米速鍍鉻拋光劑",            cat:"研磨", price:1999, priceMax:1999, unit:"瓶" },
  { sku:"a042", name:"柔和真皮清潔劑(慕斯款)",    cat:"護理", price:199, priceMax:899, unit:"瓶" },
  { sku:"a043", name:"柏油清潔劑",                cat:"清潔", price:399, priceMax:1659, unit:"瓶" },
];
/* 出貨設定(學誼填實際值;寧可保守不要跳票) */
const PM_SHIPPING = { leadDaysText: "付款後 3 個工作天內出貨", note: "預購品於商品頁標明預計出貨日" };
if (typeof module!=="undefined") module.exports = { PM_PRODUCTS, PM_SHIPPING };
