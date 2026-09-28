/* 泡泡怪兽 POP MONSTER · 商品目录 v2(2026-06-07 规格×价格全展开)
   来源:虾皮卖家中心 mass_update 官方导出档。每 SKU 含全部规格(spec)与对应价格。
   下单页依 variants 显示规格选择;勿手改数字,改价请重跑生成脚本或同步虾皮后台。 */
const PM_PRODUCTS = [
  { sku:"a001", name:"天使涂层 Guard", nameEn:"Angel Coating Guard", cat:"镀膜", variants:[{spec:"30ml入门体验款", price:699},{spec:"100ml热销首选款", price:1199},{spec:"200ml团购优惠款", price:2199},{spec:"300ml超值优惠款", price:2999}] },
  { sku:"a002", name:"米速研磨剂三件组", nameEn:"MISO Polish 3-Piece Set", cat:"研磨", variants:[{spec:"单一规格", price:4099}] },
  { sku:"a003", name:"米速三号 80 番", nameEn:"MISO No.3 Heavy-Cut (80)", cat:"研磨", variants:[{spec:"30g样品不划算", price:359},{spec:"100g", price:699},{spec:"200g", price:1199},{spec:"300g", price:1699}] },
  { sku:"a004", name:"米速伍号 600 番", nameEn:"MISO No.5 One-Step (600)", cat:"研磨", variants:[{spec:"30g试用品（不划算）", price:359},{spec:"100g", price:699},{spec:"200g", price:1199},{spec:"300g", price:1599}] },
  { sku:"a005", name:"米速拾号 1000 番", nameEn:"MISO No.10 Mirror Finish (1000)", cat:"研磨", variants:[{spec:"30g样品（不划算）", price:299},{spec:"100g", price:599},{spec:"200g", price:999},{spec:"300g", price:1299}] },
  { sku:"a006", name:"RO 订制粗棉抛光盘", nameEn:"RO Custom Foam Pad (Coarse)", cat:"耗材", variants:[{spec:"1入 体验装（不划算）", price:899},{spec:"2入 入门囤货", price:1299},{spec:"3入 常规补货", price:1899},{spec:"6入 最划算", price:3599}] },
  { sku:"a007", name:"铁粉清洁剂", nameEn:"Iron Remover", cat:"清洁", variants:[{spec:"1入 体验装（不划算）", price:699},{spec:"2入 入门囤货", price:1199},{spec:"3入 常规补货", price:1599},{spec:"6入 最划算", price:2999}] },
  { sku:"a008", name:"泡沫洗车液", nameEn:"Foam Car Wash", cat:"清洁", variants:[{spec:"100ml体验装", price:239},{spec:"200ml", price:359},{spec:"500ml", price:699}] },
  { sku:"a009", name:"液体橡皮擦", nameEn:"Liquid Eraser", cat:"清洁", variants:[{spec:"1入 体验装（不划算）", price:699},{spec:"2入 入门囤货", price:1199},{spec:"3入 常规补货", price:1599},{spec:"6入 最划算", price:2999}] },
  { sku:"a010", name:"玻璃镀膜剂(净护喷雾)", nameEn:"Glass Care Spray", cat:"镀膜", variants:[{spec:"1入 ,⚠️无喷头", price:499},{spec:"2入 双入补货,⚠️无喷头", price:799},{spec:"3入 入门囤货,⚠️无喷头", price:1099},{spec:"6入 划算,⚠️无喷头", price:1999}] },
  { sku:"a012", name:"内饰清洁剂 APC 橙油款", nameEn:"Interior Cleaner APC", cat:"清洁", variants:[{spec:"100ml", price:99},{spec:"200ml", price:189},{spec:"500ml", price:469}] },
  { sku:"a013", name:"高端真皮清洁剂", nameEn:"Premium Leather Cleaner", cat:"护理", variants:[{spec:"单一规格", price:2399}] },
  { sku:"a017", name:"雨刷精 1200 高浓缩", nameEn:"Windshield Washer 1200x", cat:"护理", variants:[{spec:"单一规格", price:499}] },
  { sku:"a020", name:"轮圈清洁剂(木瓜重油双清)", nameEn:"Wheel Cleaner 2-in-1", cat:"清洁", variants:[{spec:"1入 体验装（不划算）,20倍稀释最高可稀释65倍", price:699},{spec:"2入 入门囤货,20倍稀释最高可稀释65倍", price:1199},{spec:"3入 常规补货,20倍稀释最高可稀释65倍", price:1599},{spec:"6入 最划算,20倍稀释最高可稀释65倍", price:2999}] },
  { sku:"a024", name:"轮胎塑件精油", nameEn:"Tire & Trim Oil", cat:"护理", variants:[{spec:"100ml尝鲜装", price:359},{spec:"200ml", price:599},{spec:"500ml", price:1199}] },
  { sku:"a030", name:"痕厉害水渍去除剂", nameEn:"Water Spot Remover", cat:"护理", variants:[{spec:"1入 体验装（不划算）,不附喷头", price:499},{spec:"2入 入门囤货,不附喷头", price:799},{spec:"3入 常规补货,不附喷头", price:1099},{spec:"6入 最划算,不附喷头", price:1999}] },
  { sku:"a031", name:"全能清洁剂(万用神喷)", nameEn:"All-Purpose Cleaner", cat:"清洁", variants:[{spec:"1入 体验装（不划算）,不附喷头", price:699},{spec:"2入 入门囤货,不附喷头", price:1199},{spec:"3入 常规补货,不附喷头", price:1599},{spec:"6入 最划算,不附喷头", price:2999}] },
  { sku:"a032", name:"丹若免刷预洗洗车液", nameEn:"Danro Touchless Pre-Wash", cat:"清洁", variants:[{spec:"1入 体验装（不划算）,最高300倍稀释", price:699},{spec:"2入 入门囤货,最高300倍稀释", price:1199},{spec:"3入 常规补货,最高300倍稀释", price:1599},{spec:"6入 最划算,最高300倍稀释", price:2999}] },
  { sku:"a033", name:"RO 订制镜面抛光盘", nameEn:"RO Custom Foam Pad (Mirror)", cat:"耗材", variants:[{spec:"1入 体验装（不划算）", price:899},{spec:"2入 入门囤货", price:1299},{spec:"3入 常规补货", price:1899},{spec:"6入 最划算", price:3599}] },
  { sku:"a034", name:"无毒脱脂神喷", nameEn:"Prep Degreaser Spray", cat:"清洁", variants:[{spec:"100ml", price:239},{spec:"200ml", price:359},{spec:"500ml", price:599}] },
  { sku:"a035", name:"无铈玻璃油膜去除膏", nameEn:"Cerium-Free Glass Polish", cat:"清洁", variants:[{spec:"100克", price:299},{spec:"200克", price:589},{spec:"420赠油膜擦", price:999}] },
  { sku:"a036", name:"磨泥润滑液", nameEn:"Clay Lubricant", cat:"耗材", variants:[{spec:"100ml", price:99},{spec:"200ml", price:189},{spec:"500ml", price:469}] },
  { sku:"a037", name:"火山去污泥(洗车黏土)", nameEn:"Volcanic Clay Bar", cat:"清洁", variants:[{spec:"红色（重切）", price:1099},{spec:"灰色（细切）", price:1199}] },
  { sku:"a038", name:"包膜店专用除胶剂", nameEn:"Adhesive Remover", cat:"清洁", variants:[{spec:"1入 体验装（不划算）", price:499},{spec:"2入 入门囤货", price:799},{spec:"3入 常规补货", price:1099},{spec:"6入 最划算", price:1999}] },
  { sku:"a039", name:"RO/GA/DA 重切羊毛盘", nameEn:"Heavy-Cut Wool Pad", cat:"耗材", variants:[{spec:"1入 体验装（不划算）", price:899},{spec:"2入 入门囤货", price:1299},{spec:"3入 常规补货", price:1899},{spec:"6入 最划算", price:3599}] },
  { sku:"a040", name:"米速 RO 商用重切抛光剂", nameEn:"MISO RO Commercial Heavy-Cut", cat:"研磨", variants:[{spec:"100g样品不划算", price:359},{spec:"200g", price:529},{spec:"300g", price:779},{spec:"600g店家必囤", price:1399}] },
  { sku:"a041", name:"米速镀铬抛光剂", nameEn:"MISO Chrome Polish", cat:"研磨", variants:[{spec:"单一规格", price:2399}] },
  { sku:"a042", name:"柔和真皮清洁剂(慕斯款)", nameEn:"Gentle Leather Mousse", cat:"护理", variants:[{spec:"50ml", price:239},{spec:"100ml", price:359},{spec:"200ml", price:599},{spec:"500ml（赠慕斯瓶）", price:1099}] },
  { sku:"a043", name:"柏油清洁剂", nameEn:"Tar Remover", cat:"清洁", variants:[{spec:"1入 体验装（不划算）,⚠️无喷头", price:499},{spec:"2入 入门囤货,⚠️无喷头", price:799},{spec:"3入 常规补货,⚠️无喷头", price:1099},{spec:"6入 最划算,⚠️无喷头", price:1999}] },
];
const PM_CAT_EN = {"镀膜": "Coating", "研磨": "Polishing", "耗材": "Pads", "清洁": "Cleaning", "护理": "Care"};
const PM_SHIPPING = { leadDaysText: "付款后 3 个工作天内出货", note: "预购品于商品页标明预计出货日", leadDaysTextEn: "Ships within 3 business days after payment", noteEn: "Pre-order items show estimated ship date" };
if (typeof module!=="undefined") module.exports = { PM_PRODUCTS, PM_SHIPPING };
