/* ═══════════════════════════════════════════════════════
   POP MONSTER 商品資料 · js/products.js
   ★★ 價格填寫處 ★★
   在下方 PM_PRICES 把 null 改成數字即可，例： A001: 390,
   全站（首頁卡片、商品頁、購物車、LINE 訂單）自動同步。
   ═══════════════════════════════════════════════════════ */
window.PM_CONFIG = {
  lineId: '@150tiznd',          // LINE 官方帳號 ID
  shipLabel: '宅配到府',
  shipFee: 120,                 // ★ 宅配運費（請確認金額）
  freeShipAt: 2000,             // 滿額免運門檻
  payment: '銀行轉帳（LINE 對帳後出貨）'
};

window.PM_PRICES = {
  A001: 999,      // 天使塗層 Guard
  A002: 2999,      // 米速研磨劑三件組
  A003: 1199,      // 米速三號 80 番
  A004: 1099,      // 米速伍號 600 番
  A005: 1099,      // 米速拾號 1000 番
  A006: 599,      // 拋光盤系列
  A007: 499,      // 鐵粉清潔劑
  A008: 599,      // 泡沫洗車液
  A009: 599,      // 液體橡皮擦
  A010: 399,      // 玻璃鍍膜劑
  A012: 599,      // 內飾清潔劑
  A013: 999,      // 皮革護理（真皮清潔劑）
  A017: 399,      // 雨刷精
  A020: 599,      // 輪圈清潔劑
  A024: 799,      // 輪胎塑件精油
  A030: 399,      // 痕厲害
  A031: 599,      // 全能清潔劑（萬用神噴）
  A032: 599,      // 丹若免刷預洗洗車液
  A033: 699,      // RO 訂製鏡面拋光盤 黑色
  A034: 499,      // 無毒脫脂神噴
  A035: 799,      // 無鈰玻璃油膜去除膏
  A036: 399,      // 磨泥潤滑液
  A037: 499,      // 火山去污泥（洗車黏土）
  A038: 399,      // 包膜店專用除膠劑
  A039: 799,      // RO 訂製羊毛盤 素黑軟漆專用
  A040: 1099,      // 米速 RO 商用重切拋光劑
  A041: 999,      // 米速鍍鉻拋光劑
  A042: 999,      // 柔和真皮清潔劑（慕斯款）
  A043: 499,      // 柏油清潔劑
  A044: null,      // 超級泡沫洗車精 Super Foam
  A045: null,      // 木瓜怪獸洗車打底劑
  A046: null,      // 黑曼羅酸性洗車泡沫
};

window.PM_PRODUCTS = [
  { sku:"A001", name:"天使塗層 Guard", cat:"鍍膜系列", img:"img/a001-main.jpg", url:"a001.html", tagline:"千倍稀釋的鏡面魔法", get price(){ return window.PM_PRICES[this.sku] || null; } },
  { sku:"A002", name:"米速研磨劑三件組", cat:"研磨系列", img:"img/a002-main.jpg", url:"a002.html", tagline:"一套搞定全流程", get price(){ return window.PM_PRICES[this.sku] || null; } },
  { sku:"A003", name:"米速三號 80 番", cat:"研磨系列", img:"img/a003-main.jpg", url:"a003.html", tagline:"重切削極限 · 深刮痕的克星", get price(){ return window.PM_PRICES[this.sku] || null; } },
  { sku:"A004", name:"米速伍號 600 番", cat:"研磨系列", img:"img/a004-main.jpg", url:"a004.html", tagline:"一劑拋・最有效率的中切削", get price(){ return window.PM_PRICES[this.sku] || null; } },
  { sku:"A005", name:"米速拾號 1000 番", cat:"研磨系列", img:"img/a005-main.jpg", url:"a005.html", tagline:"鏡面還原的最後一步", get price(){ return window.PM_PRICES[this.sku] || null; } },
  { sku:"A006", name:"拋光盤系列", cat:"耗材系列", img:"img/a006-main.jpg", url:"a006.html", tagline:"RO 訂製職人級多規格", get price(){ return window.PM_PRICES[this.sku] || null; } },
  { sku:"A007", name:"鐵粉清潔劑", cat:"清潔系列", img:"img/a007-main.jpg", url:"a007.html", tagline:"紫色變色・看得見的溶解效果", get price(){ return window.PM_PRICES[this.sku] || null; } },
  { sku:"A008", name:"泡沫洗車液", cat:"清潔系列", img:"", url:"a008.html", tagline:"1 瓶抵 50 公升 · 高濃縮泡沫", get price(){ return window.PM_PRICES[this.sku] || null; } },
  { sku:"A009", name:"液體橡皮擦", cat:"清潔系列", img:"", url:"a009.html", tagline:"化學溶解 · 0 磨損深層去污", get price(){ return window.PM_PRICES[this.sku] || null; } },
  { sku:"A010", name:"玻璃鍍膜劑", cat:"鍍膜系列", img:"img/a010-main.jpg", url:"a010.html", tagline:"雨天視線救星 · 去油膜提升撥水", get price(){ return window.PM_PRICES[this.sku] || null; } },
  { sku:"A012", name:"內飾清潔劑", cat:"清潔系列", img:"img/a012-main.jpg", url:"a012.html", tagline:"橙油 APC · 1 瓶抵 20 罐", get price(){ return window.PM_PRICES[this.sku] || null; } },
  { sku:"A013", name:"皮革護理（真皮清潔劑）", cat:"護理系列", img:"", url:"a013.html", tagline:"高端真皮専用 · 深層滋潤防乾裂", get price(){ return window.PM_PRICES[this.sku] || null; } },
  { sku:"A017", name:"雨刷精", cat:"護理系列", img:"", url:"a017.html", tagline:"1200 高濃縮 · 防凍防霧", get price(){ return window.PM_PRICES[this.sku] || null; } },
  { sku:"A020", name:"輪圈清潔劑", cat:"清潔系列", img:"img/a020-main.jpg", url:"a020.html", tagline:"木瓜重油雙清 · 煞車粉塵剋星", get price(){ return window.PM_PRICES[this.sku] || null; } },
  { sku:"A024", name:"輪胎塑件精油", cat:"護理系列", img:"img/a024-main.jpg", url:"a024.html", tagline:"一擦亮如新 · 防龜裂防 UV", get price(){ return window.PM_PRICES[this.sku] || null; } },
  { sku:"A030", name:"痕厲害", cat:"護理系列", img:"img/a030-main.jpg", url:"a030.html", tagline:"水痕水漬剋星 · 車漆細節修復", get price(){ return window.PM_PRICES[this.sku] || null; } },
  { sku:"A031", name:"全能清潔劑（萬用神噴）", cat:"清潔系列", img:"img/a031-main.jpg", url:"a031.html", tagline:"1 瓶搞定全家 · 車內車外皆適用", get price(){ return window.PM_PRICES[this.sku] || null; } },
  { sku:"A032", name:"丹若免刷預洗洗車液", cat:"清潔系列", img:"img/a032-main.jpg", url:"a032.html", tagline:"改裝車 0 風險的洗車第一步", get price(){ return window.PM_PRICES[this.sku] || null; } },
  { sku:"A033", name:"RO 訂製鏡面拋光盤 黑色", cat:"耗材系列", img:"", url:"a033.html", tagline:"鏡面收尾專用 · 密度最高", get price(){ return window.PM_PRICES[this.sku] || null; } },
  { sku:"A034", name:"無毒脫脂神噴", cat:"清潔系列", img:"img/a034-main.jpg", url:"a034.html", tagline:"鍍膜服貼必備 · 施工前置首選", get price(){ return window.PM_PRICES[this.sku] || null; } },
  { sku:"A035", name:"無鈰玻璃油膜去除膏", cat:"清潔系列", img:"img/a035-main.jpg", url:"a035.html", tagline:"台灣暴雨救星 · 透光 +90%", get price(){ return window.PM_PRICES[this.sku] || null; } },
  { sku:"A036", name:"磨泥潤滑液", cat:"耗材系列", img:"", url:"a036.html", tagline:"黏土必備伴侶 · 防刮傷滑劑", get price(){ return window.PM_PRICES[this.sku] || null; } },
  { sku:"A037", name:"火山去污泥（洗車黏土）", cat:"清潔系列", img:"", url:"a037.html", tagline:"鐵粉柏油一刀斬 · 物理深層去污", get price(){ return window.PM_PRICES[this.sku] || null; } },
  { sku:"A038", name:"包膜店專用除膠劑", cat:"清潔系列", img:"", url:"a038.html", tagline:"包膜師傅指定 · 殘膠溶解去除", get price(){ return window.PM_PRICES[this.sku] || null; } },
  { sku:"A039", name:"RO 訂製羊毛盤 素黑軟漆專用", cat:"耗材系列", img:"img/a039-main.jpg", url:"a039.html", tagline:"重切削首選 · 合成羊毛不噴毛", get price(){ return window.PM_PRICES[this.sku] || null; } },
  { sku:"A040", name:"米速 RO 商用重切拋光劑", cat:"研磨系列", img:"", url:"a040.html", tagline:"店家產能翻倍 · P800-P1200 職人級", get price(){ return window.PM_PRICES[this.sku] || null; } },
  { sku:"A041", name:"米速鍍鉻拋光劑", cat:"研磨系列", img:"", url:"a041.html", tagline:"鍍鉻件去氧化 · 光澤完全恢復", get price(){ return window.PM_PRICES[this.sku] || null; } },
  { sku:"A042", name:"柔和真皮清潔劑（慕斯款）", cat:"護理系列", img:"", url:"a042.html", tagline:"慕斯泡沫護皮革 · 弱酸性深層護理", get price(){ return window.PM_PRICES[this.sku] || null; } },
  { sku:"A043", name:"柏油清潔劑", cat:"清潔系列", img:"img/a043-main.jpg", url:"a043.html", tagline:"柏油一抹即去 · 車漆安全無腐蝕", get price(){ return window.PM_PRICES[this.sku] || null; } },
  { sku:"A044", name:"超級泡沫洗車精 Super Foam", cat:"清潔系列", img:"img/a044-main.jpg", url:"a044.html", tagline:"洗車前置厚泡沫 · 高濃縮", get price(){ return window.PM_PRICES[this.sku] || null; } },
  { sku:"A045", name:"木瓜怪獸洗車打底劑", cat:"清潔系列", img:"img/a045-main.jpg", url:"a045.html", tagline:"Papaya Monster · 稀釋 1:10 免刷預洗", get price(){ return window.PM_PRICES[this.sku] || null; } },
  { sku:"A046", name:"黑曼羅酸性洗車泡沫", cat:"清潔系列", img:"img/a046-main.jpg", url:"a046.html", tagline:"NEGROAMARO · 酸性洗車工作液", get price(){ return window.PM_PRICES[this.sku] || null; } },
];
