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

    # ── r4：跨分頁不互蓋、清空不動下單頁的規格、結帳列不斷字 ──
    def _fn(self, name):
        m = re.search(r"function %s\([^)]*\)\s*\{(.*?)\n  \}" % name, self.store, re.S) or \
            re.search(r"function %s\([^)]*\)\s*\{([^\n]*)\}" % name, self.store)
        self.assertIsNotNone(m, "store.js 找不到 %s()" % name)
        return m.group(1)

    def test_store_js_rereads_storage_before_every_write(self):
        # 首頁分頁手上的舊資料不能蓋掉下單頁剛改的數量：add/setQty/clearCart 改之前都要先重讀
        self.assertRegex(self.store, r"function sync\(\)\s*\{\s*cart\s*=\s*load\(\);\s*\}")
        for name in ("add", "setQty", "clearCart", "removeOrdered"):
            self.assertIn("sync();", self._fn(name), "%s() 沒有先重讀 localStorage" % name)

    def test_store_js_clear_keeps_order_page_variants(self):
        # 清空只清 items；v（下單頁另選的規格）沒進這張單，不能一起清掉
        body = self._fn("clearCart")
        self.assertIn("cart.items = {}", body)
        self.assertNotRegex(body, r"cart\s*=\s*\{\s*items")

    def test_store_js_listens_to_other_tabs_and_bfcache(self):
        self.assertRegex(self.store, r"addEventListener\('storage'")
        self.assertRegex(self.store, r"addEventListener\('pageshow'")

    def test_store_js_shows_order_page_variants(self):
        # 從 order.html?add= 進來的新訪客，首頁購物車數字不能是 0、抽屜要告訴他東西在下單頁
        self.assertIn("count() + extraCount()", self.store)
        self.assertIn("order.html", self._fn("extrasHtml"))

    def test_order_page_rereads_before_changing_quantity(self):
        for fn in ("pick", "add"):
            m = re.search(r"\n\s*%s:function\([^)]*\)\{([^\n]*)\}," % fn, self.order)
            self.assertIsNotNone(m, "order.html 找不到 PM.%s" % fn)
            self.assertIn("cart=fromShared(readShared())", m.group(1))

    def test_order_bar_buttons_never_wrap_their_label(self):
        m = re.search(r"\.bar \.btn\{([^}]*)\}", self.order)
        self.assertIsNotNone(m)
        self.assertIn("white-space:nowrap", m.group(1))
        self.assertIn("min-width:max-content", m.group(1))

    # ── r5：下單頁規格要寫出是哪個規格、只有下單頁規格時結帳頁不說「購物車是空的」 ──
    def test_order_page_saves_spec_names_with_variants(self):
        m = re.search(r"function save\(\)\{(.*?)\n  \}", self.order, re.S)
        self.assertIsNotNone(m, "order.html 找不到 save()")
        self.assertIn("c.vn={}", m.group(1))
        self.assertIn("delete c.vn", m.group(1))

    def test_store_js_lists_spec_name_of_order_page_variants(self):
        body = self._fn("extras")
        self.assertIn("cart.vn", body)
        self.assertIn("規格在下單頁", self._fn("extrasHtml"))  # 舊資料沒有規格名稱時的寫法

    def test_cart_page_with_only_order_page_variants_is_not_called_empty(self):
        body = self._fn("renderCartPage")
        self.assertIn("extrasHtml(true)", body)
        self.assertLess(body.index("extras().length"), body.index("<p>購物車是空的</p>"),
                        "只有下單頁規格時要先判斷，不能直接顯示「購物車是空的」")


if __name__ == "__main__":
    unittest.main()
