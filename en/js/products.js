/* ═══════════════════════════════════════════════════════
   POP MONSTER 商品資料 · js/products.js
   ★★ 價格填寫處 ★★
   在下方 PM_PRICES 把 null 改成數字即可，例： A001: 390,
   全站（首頁卡片、商品頁、購物車、LINE 訂單）自動同步。
   ═══════════════════════════════════════════════════════ */
window.PM_CONFIG = {
  lineId: '@150tiznd',          // LINE 官方帳號 ID
  shipLabel: 'Home delivery',
  shipFee: 120,                 // ★ 宅配運費（請確認金額）
  freeShipAt: 2000,             // 滿額免運門檻
  payment: 'Bank transfer (we confirm the total and shipping on WhatsApp before you pay)'
};

window.PM_PRICES = {
  A001: 1199,      // 天使塗層 Guard
  A002: 4099,      // 米速研磨劑三件組
  A003: 1699,      // 米速三號 80 番
  A004: 1599,      // 米速伍號 600 番
  A005: 1299,      // 米速拾號 1000 番
  A006: 799,      // 拋光盤系列
  A007: 699,      // 鐵粉清潔劑
  A008: 699,      // 泡沫洗車液
  A009: 699,      // 液體橡皮擦
  A010: 499,      // 玻璃鍍膜劑
  A012: 469,      // 內飾清潔劑
  A013: 2399,      // 皮革護理（真皮清潔劑）
  A017: 499,      // 雨刷精
  A020: 699,      // 輪圈清潔劑
  A024: 1199,      // 輪胎塑件精油
  A030: 499,      // 痕厲害
  A031: 699,      // 全能清潔劑（萬用神噴）
  A032: 699,      // 丹若免刷預洗洗車液
  A033: 899,      // RO 訂製鏡面拋光盤 黑色
  A034: 599,      // 無毒脫脂神噴
  A035: 999,      // 無鈰玻璃油膜去除膏
  A036: 469,      // 磨泥潤滑液
  A037: 1099,      // 火山去污泥（洗車黏土）
  A038: 499,      // 包膜店專用除膠劑
  A039: 999,      // RO 訂製羊毛盤 素黑軟漆專用
  A040: 1399,      // 米速 RO 商用重切拋光劑
  A041: 2399,      // 米速鍍鉻拋光劑
  A042: 1099,      // 柔和真皮清潔劑（慕斯款）
  A043: 499,      // 柏油清潔劑
  A044: null,      // 超級泡沫洗車精 Super Foam
  A045: null,      // 木瓜怪獸洗車打底劑
  A046: null,      // 黑曼羅酸性洗車泡沫
};

window.PM_PRODUCTS = [
  { sku:"A001", name:"Angel Coating Guard", cat:"Coatings", img:"../img/a001-main.jpg", url:"a001.html", tagline:"1:1000 dilution, mirror-finish magic", get price(){ return window.PM_PRICES[this.sku] || null; } },
  { sku:"A002", name:"MISO Compound 3-Piece Set", cat:"Compounds", img:"../img/a002-main.jpg", url:"a002.html", tagline:"One set does the whole job", get price(){ return window.PM_PRICES[this.sku] || null; } },
  { sku:"A003", name:"MISO No.3 Heavy Cut (80 grit)", cat:"Compounds", img:"../img/a003-main.jpg", url:"a003.html", tagline:"Extreme heavy cut · removes deep scratches", get price(){ return window.PM_PRICES[this.sku] || null; } },
  { sku:"A004", name:"MISO No.5 One-Step (600 grit)", cat:"Compounds", img:"../img/a004-main.jpg", url:"a004.html", tagline:"One-step polish, the most efficient medium cut", get price(){ return window.PM_PRICES[this.sku] || null; } },
  { sku:"A005", name:"MISO No.10 Mirror Finish (1000 grit)", cat:"Compounds", img:"../img/real/a005-shi10-studio.jpg", url:"a005.html", tagline:"The last step to a mirror finish", get price(){ return window.PM_PRICES[this.sku] || null; } },
  { sku:"A006", name:"Polishing Pad Series", cat:"Pads & Tools", img:"../img/a006-main.jpg", url:"a006.html", tagline:"RO custom, pro-grade, multiple sizes", get price(){ return window.PM_PRICES[this.sku] || null; } },
  { sku:"A007", name:"Iron Remover", cat:"Cleaners", img:"../img/a007-main.jpg", url:"a007.html", tagline:"Turns purple, so you can see the dissolving action", get price(){ return window.PM_PRICES[this.sku] || null; } },
  { sku:"A008", name:"Foam Car Wash", cat:"Cleaners", img:"../img/real/a008-superfoam-480.jpg", url:"a008.html", tagline:"1 bottle makes 50 liters, highly concentrated foam", get price(){ return window.PM_PRICES[this.sku] || null; } },
  { sku:"A009", name:"Liquid Eraser", cat:"Cleaners", img:"", url:"a009.html", tagline:"Chemical action, 0 abrasion, deep clean", get price(){ return window.PM_PRICES[this.sku] || null; } },
  { sku:"A010", name:"Glass Coating Spray", cat:"Coatings", img:"../img/a010-main.jpg", url:"a010.html", tagline:"A lifesaver for rainy-day visibility · removes oil film, boosts water beading", get price(){ return window.PM_PRICES[this.sku] || null; } },
  { sku:"A012", name:"Interior Cleaner", cat:"Cleaners", img:"../img/a012-main.jpg", url:"a012.html", tagline:"Orange oil APC · 1 bottle replaces 20 cans", get price(){ return window.PM_PRICES[this.sku] || null; } },
  { sku:"A013", name:"Leather Care (Leather Cleaner)", cat:"Care", img:"", url:"a013.html", tagline:"For premium leather · deep moisture, prevents cracking", get price(){ return window.PM_PRICES[this.sku] || null; } },
  { sku:"A017", name:"Windshield Washer Concentrate", cat:"Care", img:"", url:"a017.html", tagline:"1200, highly concentrated · anti-freeze, anti-fog", get price(){ return window.PM_PRICES[this.sku] || null; } },
  { sku:"A020", name:"Wheel Cleaner", cat:"Cleaners", img:"../img/a020-main.jpg", url:"a020.html", tagline:"Papaya heavy-oil double clean · beats brake dust", get price(){ return window.PM_PRICES[this.sku] || null; } },
  { sku:"A024", name:"Tire & Trim Oil", cat:"Care", img:"../img/a024-main.jpg", url:"a024.html", tagline:"One wipe brings it back like new · protects against cracking and UV", get price(){ return window.PM_PRICES[this.sku] || null; } },
  { sku:"A030", name:"Water Spot Remover", cat:"Care", img:"../img/a030-main.jpg", url:"a030.html", tagline:"Removes water spots and stains · restores paint detail", get price(){ return window.PM_PRICES[this.sku] || null; } },
  { sku:"A031", name:"All-Purpose Cleaner", cat:"Cleaners", img:"../img/a031-main.jpg", url:"a031.html", tagline:"One bottle does it all · works inside and out", get price(){ return window.PM_PRICES[this.sku] || null; } },
  { sku:"A032", name:"DANRUO Touchless Pre-Wash", cat:"Cleaners", img:"../img/a032-main.jpg", url:"a032.html", tagline:"The 0-risk first wash step for modified cars", get price(){ return window.PM_PRICES[this.sku] || null; } },
  { sku:"A033", name:"RO Custom Mirror Foam Pad (Black)", cat:"Pads & Tools", img:"", url:"a033.html", tagline:"For the final mirror finish · highest density", get price(){ return window.PM_PRICES[this.sku] || null; } },
  { sku:"A034", name:"Prep Degreaser Spray", cat:"Cleaners", img:"../img/a034-main.jpg", url:"a034.html", tagline:"A must for coating adhesion · the top choice for prep work", get price(){ return window.PM_PRICES[this.sku] || null; } },
  { sku:"A035", name:"Cerium-Free Glass Oil-Film Remover", cat:"Cleaners", img:"../img/a035-main.jpg", url:"a035.html", tagline:"A lifesaver in Taiwan's heavy rain · +90% light transmission", get price(){ return window.PM_PRICES[this.sku] || null; } },
  { sku:"A036", name:"Clay Lubricant", cat:"Pads & Tools", img:"", url:"a036.html", tagline:"The clay bar's best friend · a scratch-safe lubricant", get price(){ return window.PM_PRICES[this.sku] || null; } },
  { sku:"A037", name:"Volcanic Clay Bar", cat:"Cleaners", img:"", url:"a037.html", tagline:"Cuts through iron fallout and tar · physically removes deep dirt", get price(){ return window.PM_PRICES[this.sku] || null; } },
  { sku:"A038", name:"Adhesive Remover (for wrap shops)", cat:"Cleaners", img:"", url:"a038.html", tagline:"The choice of wrap pros · dissolves and removes leftover adhesive", get price(){ return window.PM_PRICES[this.sku] || null; } },
  { sku:"A039", name:"RO Custom Wool Pad (for soft black paint)", cat:"Pads & Tools", img:"../img/a039-main.jpg", url:"a039.html", tagline:"The top pick for heavy cutting · synthetic wool that won't shed", get price(){ return window.PM_PRICES[this.sku] || null; } },
  { sku:"A040", name:"MISO RO Commercial Heavy-Cut Compound", cat:"Compounds", img:"", url:"a040.html", tagline:"Doubles your shop's output · pro-grade P800-P1200", get price(){ return window.PM_PRICES[this.sku] || null; } },
  { sku:"A041", name:"MISO Chrome Polish", cat:"Compounds", img:"../img/a041-main.jpg", url:"a041.html", tagline:"Removes oxidation from chrome · fully restores the shine", get price(){ return window.PM_PRICES[this.sku] || null; } },
  { sku:"A042", name:"Gentle Leather Cleaner (Mousse)", cat:"Care", img:"", url:"a042.html", tagline:"Foam mousse for leather · mildly acidic, deep care", get price(){ return window.PM_PRICES[this.sku] || null; } },
  { sku:"A043", name:"Tar Remover", cat:"Cleaners", img:"../img/a043-main.jpg", url:"a043.html", tagline:"One wipe removes tar · safe on paint, won't corrode", get price(){ return window.PM_PRICES[this.sku] || null; } },
  { sku:"A044", name:"Super Foam Car Wash", cat:"Cleaners", img:"../img/a044-main.jpg", url:"a044.html", tagline:"Thick pre-wash foam · highly concentrated", get price(){ return window.PM_PRICES[this.sku] || null; } },
  { sku:"A045", name:"Papaya Monster Wash Base", cat:"Cleaners", img:"../img/a045-main.jpg", url:"a045.html", tagline:"Papaya Monster · dilute 1:10 for a touchless pre-wash", get price(){ return window.PM_PRICES[this.sku] || null; } },
  { sku:"A046", name:"Black Mandala Acidic Wash Foam", cat:"Cleaners", img:"../img/a046-main.jpg", url:"a046.html", tagline:"NEGROAMARO · acidic car wash solution", get price(){ return window.PM_PRICES[this.sku] || null; } },
];

/* 海外版（build.py 產生）：購物車改到下單頁用 WhatsApp，運費依國家報價 */
window.PM_CONFIG.intl = true;
window.PM_CONFIG.orderUrl = '../order.html?lang=en';
