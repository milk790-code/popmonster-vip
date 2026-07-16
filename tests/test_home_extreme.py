from pathlib import Path
import json
import re
import subprocess
import unittest


ROOT = Path(__file__).resolve().parents[1]


class HomepageExtremeContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html = (ROOT / "index.html").read_text(encoding="utf-8")
        css_path = ROOT / "css" / "home-extreme.css"
        accents_path = ROOT / "css" / "canwu-accents.css"
        js_path = ROOT / "js" / "home.js"
        store_path = ROOT / "js" / "store.js"
        cls.css = css_path.read_text(encoding="utf-8") if css_path.exists() else ""
        cls.accents = accents_path.read_text(encoding="utf-8") if accents_path.exists() else ""
        cls.js = js_path.read_text(encoding="utf-8") if js_path.exists() else ""
        cls.store = store_path.read_text(encoding="utf-8") if store_path.exists() else ""
        cls.manifest = json.loads((ROOT / "manifest.json").read_text(encoding="utf-8"))

    def test_semantic_entry_and_social_metadata(self):
        self.assertIn('<link rel="canonical" href="https://popmonster.vip/">', self.html)
        self.assertIn('og-image-1200x630.png', self.html)
        self.assertRegex(self.html, r'<a[^>]+class="skip-link"[^>]+href="#main-content"')
        self.assertRegex(self.html, r'<main[^>]+id="main-content"')
        self.assertIn('aria-current="page"', self.html)

    def test_real_brand_and_product_assets_drive_the_hero(self):
        self.assertRegex(self.html, r'class="nav-mark"[^>]+src="favicon\.svg"')
        self.assertRegex(self.html, r'class="home-hero-product"[^>]+src="img/a001-main\.jpg"')
        self.assertRegex(self.html, r'class="home-hero-product"[^>]+fetchpriority="high"')
        self.assertNotIn('圖片整備中', self.html)
        featured = re.search(r'<section class="featured.*?</section>', self.html, re.S)
        self.assertIsNotNone(featured)
        self.assertIn('img/a001-main.jpg', featured.group(0))

    def test_hero_fetch_priority_does_not_duplicate_an_unused_preload(self):
        self.assertNotRegex(self.html, r'<link[^>]+rel="preload"[^>]+as="image"')

    def test_accents_reuse_the_primary_font_payload(self):
        self.assertNotIn('fonts.googleapis.com', self.accents)
        self.assertNotIn("'Ma Shan Zheng'", self.accents)

    def test_homepage_is_font_network_independent_and_manifest_icons_resolve(self):
        self.assertNotIn('fonts.googleapis.com', self.html)
        self.assertNotIn('fonts.gstatic.com', self.html)
        for icon in self.manifest["icons"]:
            self.assertTrue((ROOT / icon["src"].lstrip("/")).is_file(), icon["src"])

    def test_accessible_names_include_the_visible_control_text(self):
        self.assertIn('aria-label="POP MONSTER 泡泡怪獸首頁"', self.html)
        self.assertIn('aria-label="MENU 開啟選單"', self.html)
        self.assertIn("aria-label', 'CART 購物車'", self.store)
        self.assertIn('aria-hidden="true"', self.store)

    def test_lighthouse_contrast_and_touch_target_contracts(self):
        self.assertRegex(self.css, r'carousel-slide-info \.sku[^}]*color: var\(--home-gold-soft\)')
        self.assertRegex(self.css, r'card-price\.tbd[^}]*color: var\(--home-muted\)')
        self.assertRegex(self.css, r'footer-copy[^}]*opacity: 1')
        self.assertRegex(self.css, r'carousel-dot[^}]*min-width: 32px[^}]*min-height: 32px')

    def test_noncritical_assets_and_analytics_do_not_block_first_paint(self):
        self.assertNotRegex(self.html, r'<script[^>]+src="https://www\.googletagmanager\.com')
        self.assertIn('window.loadAnalytics', self.html)
        self.assertIn("typeof window.loadAnalytics === 'function'", (ROOT / "js" / "main.js").read_text(encoding="utf-8"))
        for asset in ("css/patch-p1p2.css", "css/store.css", "css/canwu-accents.css"):
            self.assertRegex(
                self.html,
                rf'<link rel="stylesheet" href="{re.escape(asset)}" media="print" onload="this\.media=\'all\'">',
            )

    def test_cart_accessible_name_tracks_only_visible_content(self):
        self.assertNotIn("🛒 <span", self.store)
        self.assertIn("b.textContent = c > 0 ? c : ''", self.store)
        self.assertIn("CART 購物車，' + c + ' 件商品", self.store)

    def test_intent_rail_and_catalog_search_are_wired(self):
        intents = set(re.findall(r'data-home-intent="([a-z]+)"', self.html))
        self.assertEqual(intents, {"cleaning", "compound", "coating", "pads", "care"})
        self.assertRegex(self.html, r'<input[^>]+id="product-search"[^>]+aria-controls="product-grid"')
        self.assertRegex(self.html, r'id="product-results"[^>]+role="status"')
        self.assertRegex(self.html, r'<div[^>]+class="grid"[^>]+id="product-grid"')
        self.assertEqual(len(re.findall(r'class="card fade-up"', self.html)), 32)
        self.assertIn('css/home-extreme.css', self.html)
        self.assertRegex(self.html, r'<script src="js/home\.js" defer></script>')

    def test_homepage_copy_avoids_absolute_safety_and_stale_consent_claims(self):
        for risky in ("零風險", "零不可逆傷害", "0 殘留風險", "繼續瀏覽即表示同意"):
            self.assertNotIn(risky, self.html)
        self.assertIn('aria-label="Cookie 偏好"', self.html)
        self.assertIn('你可以選擇是否允許分析用 Cookie', self.html)

    def test_home_css_has_accessible_responsive_motion_contract(self):
        self.assertIn(':focus-visible', self.css)
        self.assertIn('@media (prefers-reduced-motion: reduce)', self.css)
        self.assertIn('@media (max-width: 720px)', self.css)
        self.assertIn('content-visibility: auto', self.css)
        self.assertNotIn('linear-gradient(135deg, #8b5cf6', self.css.lower())

    def test_home_javascript_is_valid_and_manages_combined_filters(self):
        self.assertIn('aria-expanded', self.js)
        self.assertIn('aria-pressed', self.js)
        self.assertIn('activeCategory', self.js)
        self.assertIn('normalizedQuery', self.js)
        result = subprocess.run(
            ["node", "--check", str(ROOT / "js" / "home.js")],
            cwd=ROOT,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_home_analytics_is_consent_gated_and_parameter_allowlisted(self):
        analytics_path = ROOT / "js" / "home-analytics.js"
        self.assertTrue(analytics_path.is_file(), "missing js/home-analytics.js")
        analytics_tag = '<script src="js/home-analytics.js" defer></script>'
        home_tag = '<script src="js/home.js" defer></script>'
        self.assertIn(analytics_tag, self.html)
        self.assertLess(self.html.index(analytics_tag), self.html.index(home_tag))

        script = r'''
const assert = require("node:assert/strict");
const fs = require("node:fs");

let consent = "denied";
const calls = [];
globalThis.window = globalThis;
globalThis.localStorage = {
  getItem(key) {
    assert.equal(key, "ck_consent");
    return consent;
  },
};
globalThis.gtag = (...args) => calls.push(args);

const source = fs.readFileSync("js/home-analytics.js", "utf8");
eval(source);

assert.equal(
  window.PopMonsterAnalytics.track("hero_cta", { target: "intent" }),
  false,
);
assert.equal(calls.length, 0);

consent = "granted";
assert.equal(
  window.PopMonsterAnalytics.track("catalog_search", {
    category: "cleaning",
    query_length: 3,
    result_count: 4,
    query: "不得送出原文",
  }),
  true,
);
assert.deepEqual(calls[0], [
  "event",
  "catalog_search",
  { category: "cleaning", query_length: 3, result_count: 4 },
]);
assert.equal(window.PopMonsterAnalytics.track("unknown_event", {}), false);
assert.equal(calls.length, 1);

localStorage.getItem = () => { throw new Error("storage blocked"); };
assert.equal(
  window.PopMonsterAnalytics.track("support_click", {
    channel: "line",
    placement: "footer",
  }),
  false,
);
assert.equal(calls.length, 1);
'''
        result = subprocess.run(
            ["node", "-e", script],
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=15,
        )
        self.assertEqual(result.returncode, 0, result.stderr or result.stdout)

    def test_home_conversion_funnel_is_wired_without_raw_search_text(self):
        self.assertIn('data-home-cta="intent"', self.html)
        self.assertIn('data-home-cta="catalog"', self.html)
        for event_name in (
            "hero_cta",
            "home_intent_select",
            "catalog_filter",
            "catalog_search",
            "product_select",
            "support_click",
        ):
            with self.subTest(event_name=event_name):
                self.assertIn("'" + event_name + "'", self.js)
        self.assertIn('query_length: normalizedQuery.length', self.js)
        self.assertNotRegex(self.js, r"\bquery\s*:\s*(?:normalizedQuery|searchInput\.value)")
        self.assertIn("target.closest('[data-pm-add]')", self.js)


if __name__ == "__main__":
    unittest.main()
