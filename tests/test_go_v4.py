from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[1]


class GoV4ContractTests(unittest.TestCase):
    expected_slugs = {
        "brand-content",
        "rental-check",
        "legal-guidance",
        "flight-plan",
        "luxury-check",
        "travel-stay",
        "creator-kit",
        "auto-care",
    }
    expected_sources = {
        "direct",
        "business-card",
        "package-insert",
        "social",
        "legacy-worker",
    }
    expected_events = {
        "page_ready",
        "hero_cta",
        "route_stage_1",
        "route_result",
        "line_start",
        "site_start",
        "share_success",
    }

    def read_required(self, relative: str) -> str:
        path = ROOT / relative
        self.assertTrue(path.is_file(), f"missing required file: {relative}")
        return path.read_text(encoding="utf-8")

    def test_required_release_files_exist(self):
        for relative in ("go.html", "css/go.css", "js/go.js", "go-preview.html"):
            with self.subTest(relative=relative):
                self.assertTrue((ROOT / relative).is_file(), relative)

    def test_hero_copy_and_semantic_sections_are_fixed(self):
        html = self.read_required("go.html")
        for text in (
            "7 個第一次，免費",
            "你卡住的那件事，我先免費幫你解第一步。",
            "選一個情境，30 秒帶你到正確入口；每項免費範圍先說清楚。",
            "選我的問題",
            "直接看 7 個免費入口",
            "看 POP 汽美本業",
            "敏感資料先遮蔽｜需要專業資格時協助轉介",
        ):
            with self.subTest(text=text):
                self.assertIn(text, html)
        for element_id in ("main-content", "problem-router", "route-result", "founder", "all-services"):
            with self.subTest(element_id=element_id):
                self.assertRegex(html, rf'id=["\']{re.escape(element_id)}["\']')

    def test_html_loads_external_assets_and_complete_metadata(self):
        html = self.read_required("go.html")
        self.assertIn('lang="zh-Hant-TW"', html)
        self.assertIn('href="css/go.css"', html)
        self.assertIn('src="js/go.js"', html)
        self.assertIn('rel="canonical" href="https://popmonster.vip/go"', html)
        self.assertRegex(html, r'rel=["\'](?:shortcut )?icon["\'][^>]+favicon\.svg')
        self.assertIn('property="og:image"', html)
        self.assertIn('name="twitter:card"', html)

    def test_static_html_has_exactly_eight_service_destinations(self):
        html = self.read_required("go.html")
        slugs = set(re.findall(r'data-service-slug=["\']([^"\']+)', html))
        self.assertEqual(slugs, self.expected_slugs)
        self.assertGreaterEqual(len(re.findall(r'<a\b[^>]+data-service-slug=', html)), 8)

    def test_legacy_overclaims_are_removed(self):
        html = self.read_required("go.html")
        for phrase in ("房東是否本人", "討債指導", "省好幾千", "超低價", "價差差一半"):
            with self.subTest(phrase=phrase):
                self.assertNotIn(phrase, html)

    def test_four_router_categories_exist(self):
        html = self.read_required("go.html")
        categories = set(re.findall(r'data-category=["\']([^"\']+)', html))
        self.assertEqual(categories, {"business", "risk", "travel", "auto"})

    def test_css_encodes_tokens_focus_touch_and_reduced_motion(self):
        css = self.read_required("css/go.css").lower()
        for token in ("#0a0a0a", "#161616", "#f5f5f5", "#a8a8a8", "#d4af37", "#2a2a2a"):
            with self.subTest(token=token):
                self.assertIn(token, css)
        self.assertIn(":focus-visible", css)
        self.assertRegex(css, r'min-(?:block-)?size\s*:\s*44px')
        self.assertIn("prefers-reduced-motion", css)
        self.assertIn("grid-template-columns", css)
        self.assertNotIn("min-inline-size: 20rem", css)

    def test_js_has_service_source_event_and_privacy_contracts(self):
        js = self.read_required("js/go.js")
        for value in self.expected_slugs | self.expected_sources | self.expected_events:
            with self.subTest(value=value):
                self.assertIn(value, js)
        self.assertIn("encodeURIComponent(lineId)", js)
        self.assertIn("encodeURIComponent(message)", js)
        self.assertIn("navigator.globalPrivacyControl", js)
        self.assertIn("doNotTrack", js)
        self.assertIn("navigator.sendBeacon", js)
        self.assertRegex(js, r'window\.Switchboard\s*=')
        self.assertIn("const allowVariants = isPreviewMode();", js)

    def test_preview_exposes_every_control_and_forces_preview_mode(self):
        preview = self.read_required("go-preview.html")
        for value in ("signal", "manual", "tickets", "offer", "founder", "guided", "all", "full", "reduced"):
            with self.subTest(value=value):
                self.assertIn(f'value="{value}"', preview)
        self.assertIn("preview=1", preview)
        self.assertIn('src="js/go.js"', preview)

    def test_preview_founder_hook_has_distinct_copy(self):
        js = self.read_required("js/go.js")
        self.assertIn("HOOK_COPY", js)
        self.assertIn("我不先推銷，先陪你找出最該做哪一步。", js)

    def test_sitemap_includes_canonical_go_route(self):
        sitemap = self.read_required("sitemap.xml")
        self.assertIn("<loc>https://popmonster.vip/go</loc>", sitemap)


if __name__ == "__main__":
    unittest.main()
