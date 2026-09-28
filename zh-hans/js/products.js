/* ═══════════════════════════════════════════════════════
   POP MONSTER 商品数据 · js/products.js
   ★★ 价格填写处 ★★
   在下方 PM_PRICES 把 null 改成数字即可，例： A001: 390,
   全站（首页卡片、商品页、购物车、LINE 订单）自动同步。
   ═══════════════════════════════════════════════════════ */
window.PM_CONFIG = {
  lineId: '@150tiznd',          // LINE 官方帐号 ID
  shipLabel: '宅配到府',
  shipFee: 120,                 // ★ 宅配运费（请确认金额）
  freeShipAt: 2000,             // 满额免运门槛
  payment: '银行转账（LINE 对账后出货）'
};

window.PM_PRICES = {
  A001: 1199,      // 天使涂层 Guard
  A002: 4099,      // 米速研磨剂三件组
  A003: 1699,      // 米速三号 80 番
  A004: 1599,      // 米速伍号 600 番
  A005: 1299,      // 米速拾号 1000 番
  A006: 799,      // 抛光盘系列
  A007: 699,      // 铁粉清洁剂
  A008: 699,      // 泡沫洗车液
  A009: 699,      // 液体橡皮擦
  A010: 499,      // 玻璃镀膜剂
  A012: 469,      // 内饰清洁剂
  A013: 2399,      // 皮革护理（真皮清洁剂）
  A017: 499,      // 雨刷精
  A020: 699,      // 轮圈清洁剂
  A024: 1199,      // 轮胎塑件精油
  A030: 499,      // 痕厉害
  A031: 699,      // 全能清洁剂（万用神喷）
  A032: 699,      // 丹若免刷预洗洗车液
  A033: 899,      // RO 订制镜面抛光盘 黑色
  A034: 599,      // 无毒脱脂神喷
  A035: 999,      // 无铈玻璃油膜去除膏
  A036: 469,      // 磨泥润滑液
  A037: 1099,      // 火山去污泥（洗车黏土）
  A038: 499,      // 包膜店专用除胶剂
  A039: 999,      // RO 订制羊毛盘 素黑软漆专用
  A040: 1399,      // 米速 RO 商用重切抛光剂
  A041: 2399,      // 米速镀铬抛光剂
  A042: 1099,      // 柔和真皮清洁剂（慕斯款）
  A043: 499,      // 柏油清洁剂
  A044: null,      // 超级泡沫洗车精 Super Foam
  A045: null,      // 木瓜怪兽洗车打底剂
  A046: null,      // 黑曼罗酸性洗车泡沫
};

window.PM_PRODUCTS = [
  { sku:"A001", name:"天使涂层 Guard", cat:"镀膜系列", img:"../img/a001-main.jpg", url:"a001.html", tagline:"千倍稀释的镜面魔法", get price(){ return window.PM_PRICES[this.sku] || null; } },
  { sku:"A002", name:"米速研磨剂三件组", cat:"研磨系列", img:"../img/a002-main.jpg", url:"a002.html", tagline:"一套搞定全流程", get price(){ return window.PM_PRICES[this.sku] || null; } },
  { sku:"A003", name:"米速三号 80 番", cat:"研磨系列", img:"../img/a003-main.jpg", url:"a003.html", tagline:"重切削极限 · 深刮痕的克星", get price(){ return window.PM_PRICES[this.sku] || null; } },
  { sku:"A004", name:"米速伍号 600 番", cat:"研磨系列", img:"../img/a004-main.jpg", url:"a004.html", tagline:"一剂抛・最有效率的中切削", get price(){ return window.PM_PRICES[this.sku] || null; } },
  { sku:"A005", name:"米速拾号 1000 番", cat:"研磨系列", img:"../img/real/a005-shi10-studio.jpg", url:"a005.html", tagline:"镜面还原的最后一步", get price(){ return window.PM_PRICES[this.sku] || null; } },
  { sku:"A006", name:"抛光盘系列", cat:"耗材系列", img:"../img/a006-main.jpg", url:"a006.html", tagline:"RO 订制职人级多规格", get price(){ return window.PM_PRICES[this.sku] || null; } },
  { sku:"A007", name:"铁粉清洁剂", cat:"清洁系列", img:"../img/a007-main.jpg", url:"a007.html", tagline:"紫色变色・看得见的溶解效果", get price(){ return window.PM_PRICES[this.sku] || null; } },
  { sku:"A008", name:"泡沫洗车液", cat:"清洁系列", img:"../img/real/a008-superfoam-480.jpg", url:"a008.html", tagline:"1 瓶抵 50 公升 · 高浓缩泡沫", get price(){ return window.PM_PRICES[this.sku] || null; } },
  { sku:"A009", name:"液体橡皮擦", cat:"清洁系列", img:"", url:"a009.html", tagline:"化学溶解 · 0 磨损深层去污", get price(){ return window.PM_PRICES[this.sku] || null; } },
  { sku:"A010", name:"玻璃镀膜剂", cat:"镀膜系列", img:"../img/a010-main.jpg", url:"a010.html", tagline:"雨天视线救星 · 去油膜提升拨水", get price(){ return window.PM_PRICES[this.sku] || null; } },
  { sku:"A012", name:"内饰清洁剂", cat:"清洁系列", img:"../img/a012-main.jpg", url:"a012.html", tagline:"橙油 APC · 1 瓶抵 20 罐", get price(){ return window.PM_PRICES[this.sku] || null; } },
  { sku:"A013", name:"皮革护理（真皮清洁剂）", cat:"护理系列", img:"", url:"a013.html", tagline:"高端真皮専用 · 深层滋润防干裂", get price(){ return window.PM_PRICES[this.sku] || null; } },
  { sku:"A017", name:"雨刷精", cat:"护理系列", img:"", url:"a017.html", tagline:"1200 高浓缩 · 防冻防雾", get price(){ return window.PM_PRICES[this.sku] || null; } },
  { sku:"A020", name:"轮圈清洁剂", cat:"清洁系列", img:"../img/a020-main.jpg", url:"a020.html", tagline:"木瓜重油双清 · 煞车粉尘克星", get price(){ return window.PM_PRICES[this.sku] || null; } },
  { sku:"A024", name:"轮胎塑件精油", cat:"护理系列", img:"../img/a024-main.jpg", url:"a024.html", tagline:"一擦亮如新 · 防龟裂防 UV", get price(){ return window.PM_PRICES[this.sku] || null; } },
  { sku:"A030", name:"痕厉害", cat:"护理系列", img:"../img/a030-main.jpg", url:"a030.html", tagline:"水痕水渍克星 · 车漆细节修复", get price(){ return window.PM_PRICES[this.sku] || null; } },
  { sku:"A031", name:"全能清洁剂（万用神喷）", cat:"清洁系列", img:"../img/a031-main.jpg", url:"a031.html", tagline:"1 瓶搞定全家 · 车内车外皆适用", get price(){ return window.PM_PRICES[this.sku] || null; } },
  { sku:"A032", name:"丹若免刷预洗洗车液", cat:"清洁系列", img:"../img/a032-main.jpg", url:"a032.html", tagline:"改装车 0 风险的洗车第一步", get price(){ return window.PM_PRICES[this.sku] || null; } },
  { sku:"A033", name:"RO 订制镜面抛光盘 黑色", cat:"耗材系列", img:"", url:"a033.html", tagline:"镜面收尾专用 · 密度最高", get price(){ return window.PM_PRICES[this.sku] || null; } },
  { sku:"A034", name:"无毒脱脂神喷", cat:"清洁系列", img:"../img/a034-main.jpg", url:"a034.html", tagline:"镀膜服贴必备 · 施工前置首选", get price(){ return window.PM_PRICES[this.sku] || null; } },
  { sku:"A035", name:"无铈玻璃油膜去除膏", cat:"清洁系列", img:"../img/a035-main.jpg", url:"a035.html", tagline:"台湾暴雨救星 · 透光 +90%", get price(){ return window.PM_PRICES[this.sku] || null; } },
  { sku:"A036", name:"磨泥润滑液", cat:"耗材系列", img:"", url:"a036.html", tagline:"黏土必备伴侣 · 防刮伤滑剂", get price(){ return window.PM_PRICES[this.sku] || null; } },
  { sku:"A037", name:"火山去污泥（洗车黏土）", cat:"清洁系列", img:"", url:"a037.html", tagline:"铁粉柏油一刀斩 · 物理深层去污", get price(){ return window.PM_PRICES[this.sku] || null; } },
  { sku:"A038", name:"包膜店专用除胶剂", cat:"清洁系列", img:"", url:"a038.html", tagline:"包膜师傅指定 · 残胶溶解去除", get price(){ return window.PM_PRICES[this.sku] || null; } },
  { sku:"A039", name:"RO 订制羊毛盘 素黑软漆专用", cat:"耗材系列", img:"../img/a039-main.jpg", url:"a039.html", tagline:"重切削首选 · 合成羊毛不喷毛", get price(){ return window.PM_PRICES[this.sku] || null; } },
  { sku:"A040", name:"米速 RO 商用重切抛光剂", cat:"研磨系列", img:"", url:"a040.html", tagline:"店家产能翻倍 · P800-P1200 职人级", get price(){ return window.PM_PRICES[this.sku] || null; } },
  { sku:"A041", name:"米速镀铬抛光剂", cat:"研磨系列", img:"../img/a041-main.jpg", url:"a041.html", tagline:"镀铬件去氧化 · 光泽完全恢复", get price(){ return window.PM_PRICES[this.sku] || null; } },
  { sku:"A042", name:"柔和真皮清洁剂（慕斯款）", cat:"护理系列", img:"", url:"a042.html", tagline:"慕斯泡沫护皮革 · 弱酸性深层护理", get price(){ return window.PM_PRICES[this.sku] || null; } },
  { sku:"A043", name:"柏油清洁剂", cat:"清洁系列", img:"../img/a043-main.jpg", url:"a043.html", tagline:"柏油一抹即去 · 车漆安全无腐蚀", get price(){ return window.PM_PRICES[this.sku] || null; } },
  { sku:"A044", name:"超级泡沫洗车精 Super Foam", cat:"清洁系列", img:"../img/a044-main.jpg", url:"a044.html", tagline:"洗车前置厚泡沫 · 高浓缩", get price(){ return window.PM_PRICES[this.sku] || null; } },
  { sku:"A045", name:"木瓜怪兽洗车打底剂", cat:"清洁系列", img:"../img/a045-main.jpg", url:"a045.html", tagline:"Papaya Monster · 稀释 1:10 免刷预洗", get price(){ return window.PM_PRICES[this.sku] || null; } },
  { sku:"A046", name:"黑曼罗酸性洗车泡沫", cat:"清洁系列", img:"../img/a046-main.jpg", url:"a046.html", tagline:"NEGROAMARO · 酸性洗车工作液", get price(){ return window.PM_PRICES[this.sku] || null; } },
];

/* 海外版（build.py 產生）：購物車改到下單頁用 WhatsApp，運費依國家報價 */
window.PM_CONFIG.intl = true;
window.PM_CONFIG.orderUrl = 'order.html';
