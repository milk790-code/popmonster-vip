"""下單頁（order.html）跟全站購物車（js/store.js）要讀寫同一個購物車；購物車相關的字不小於 12px。"""
from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[1]


class OrderCartContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.order = (ROOT / "order.html").read_text(encoding="utf-8")
        cls.store = (ROOT / "js" / "store.js").read_text(encoding="utf-8")
        cls.store_css = (ROOT / "css" / "store.css").read_text(encoding="utf-8")
        cls.accents = (ROOT / "css" / "canwu-accents.css").read_text(encoding="utf-8")

    def test_order_page_uses_the_same_cart_key_as_store_js(self):
        m = re.search(r"var LS_CART = '([^']+)'", self.store)
        self.assertIsNotNone(m, "store.js 找不到 LS_CART")
        self.assertIn("LS_CART='%s'" % m.group(1), self.order)

    def test_old_v2_cart_is_only_merged_never_written(self):
        # 舊版下單頁的 pm_cart_v2 只讀進來合併，不再寫回
        self.assertIn("LS_OLD='pm_cart_v2'", self.order)
        self.assertNotRegex(self.order, r"setItem\(\s*'pm_cart_v2'")
        self.assertNotRegex(self.order, r"setItem\(\s*LS_OLD\s*,")

    def test_site_prices_load_before_the_order_catalog(self):
        # 對應規格要用官網售價（js/products.js）；products_catalog.js 的 const PM_PRODUCTS 會遮住同名變數，所以先存一份
        i_site = self.order.index('<script src="js/products.js"></script>')
        i_keep = self.order.index("window.PM_SITE_PRODUCTS=window.PM_PRODUCTS")
        i_cat = self.order.index('<script src="products_catalog.js"></script>')
        self.assertLess(i_site, i_keep)
        self.assertLess(i_keep, i_cat)

    def test_placeholder_seal_is_at_least_12px(self):
        m = re.search(r"\.ink-ph--sm \.ink-ph-seal\{([^}]*)\}", self.accents)
        self.assertIsNotNone(m)
        size = re.search(r"font-size:(\d+)px", m.group(1))
        self.assertGreaterEqual(int(size.group(1)), 12)

    def test_cart_css_has_no_text_below_12px(self):
        for css, name in ((self.store_css, "store.css"),):
            for px in re.findall(r"font-size:\s*(\d+(?:\.\d+)?)px", css):
                self.assertGreaterEqual(float(px), 12, "%s 有 %spx 的字" % (name, px))


if __name__ == "__main__":
    unittest.main()
