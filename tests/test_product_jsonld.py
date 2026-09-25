"""商品頁 Product/Offer JSON-LD 要跟頁面看得到的價一致：價格＝js/products.js 的 PM_PRICES（全站售價單一來源），
TWD、InStock；PM_PRICES 是 null（A044–A046 還沒定價）就不放 Offer，不能自己編一個價。"""
from pathlib import Path
import json
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]


def pm_prices():
    src = (ROOT / "js" / "products.js").read_text(encoding="utf-8")
    blk = re.search(r"window\.PM_PRICES\s*=\s*\{(.*?)\};", src, re.S).group(1)
    return {s: (None if v == "null" else int(v)) for s, v in re.findall(r"(A\d{3}):\s*(null|\d+)", blk)}


class ProductJsonLd(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.prices = pm_prices()
        cls.pages = sorted(ROOT.glob("a0*.html"))

    def product(self, html, name):
        found = []
        for s in re.findall(r'<script type="application/ld\+json">(.*?)</script>', html, re.S):
            d = json.loads(s)  # 每一段都要是合法 JSON
            if d.get("@type") == "Product":
                found.append(d)
        self.assertEqual(len(found), 1, "%s 應該剛好一段 Product JSON-LD" % name)
        return found[0]

    def test_every_product_page_is_covered(self):
        self.assertGreaterEqual(len(self.pages), 32)
        for f in self.pages:
            self.assertIn(f.stem.upper(), self.prices, "%s 不在 PM_PRICES" % f.name)

    def test_offer_matches_site_price(self):
        for f in self.pages:
            sku = f.stem.upper()
            with self.subTest(page=f.name):
                html = f.read_text(encoding="utf-8")
                d = self.product(html, f.name)
                self.assertEqual(d.get("sku"), sku)
                price = self.prices[sku]
                if price is None:
                    self.assertNotIn("offers", d, "%s 沒有售價，不能放 Offer" % sku)
                    continue
                o = d.get("offers")
                self.assertIsNotNone(o, "%s 有售價 %s 但沒有 Offer" % (sku, price))
                self.assertEqual(o.get("@type"), "Offer")
                self.assertEqual(int(o.get("price")), price)
                self.assertEqual(o.get("priceCurrency"), "TWD")
                self.assertEqual(o.get("availability"), "https://schema.org/InStock")
                # 頁面上寫死的「NT$X 起」（a001、a006）也要一樣
                m = re.search(r'pd-price-block.*?NT\$([\d,]+)\s*<span[^>]*>起', html, re.S)
                if m:
                    self.assertEqual(int(m.group(1).replace(",", "")), price)
                else:
                    self.assertRegex(html, r'data-pm-price="%s"' % sku, "%s 頁面沒有顯示售價的地方" % sku)


if __name__ == "__main__":
    unittest.main()
