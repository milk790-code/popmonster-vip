from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[1]
POPCARD_STORY = "https://popcard-saas-preview.milk790.workers.dev/s/jilin#story"
POPCARD_MEMBER = "https://popcard-saas-preview.milk790.workers.dev/s/jilin#member"


class PopMonsterUniverseContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.home = (ROOT / "index.html").read_text(encoding="utf-8")
        cls.go = (ROOT / "go.html").read_text(encoding="utf-8")

    def test_system_hub_exists_with_complete_metadata_and_no_embedded_backend(self):
        path = ROOT / "systems.html"
        self.assertTrue(path.is_file(), "missing systems.html")
        html = path.read_text(encoding="utf-8")
        self.assertIn('lang="zh-Hant-TW"', html)
        self.assertIn(
            '<link rel="canonical" href="https://popmonster.vip/systems.html">',
            html,
        )
        self.assertIn('class="systems-page"', html)
        self.assertIn('href="css/systems.css"', html)
        self.assertIn(POPCARD_STORY, html)
        self.assertIn(POPCARD_MEMBER, html)
        self.assertIn("不共用登入、Cookie、會員資料、購物車或付款狀態", html)
        self.assertNotIn("<iframe", html.lower())

    def test_all_public_popcard_links_use_only_the_canonical_preview_routes(self):
        allowed = {POPCARD_STORY, POPCARD_MEMBER}
        pages = {
            "index.html": self.home,
            "go.html": self.go,
            "systems.html": (ROOT / "systems.html").read_text(encoding="utf-8"),
        }
        for name, html in pages.items():
            with self.subTest(page=name):
                links = {
                    href
                    for href in re.findall(r'href="([^"]+)"', html)
                    if "popcard" in href.lower()
                }
                self.assertTrue(links, f"{name} has no POP CARD link")
                self.assertTrue(links <= allowed, f"{name} has unexpected links: {links}")
                self.assertNotIn("popcard-saaspreview.", html)

    def test_homepage_has_a_role_based_universe_entry(self):
        self.assertRegex(
            self.home,
            r'<section[^>]+id="universe"[^>]+aria-labelledby="universe-title"',
        )
        self.assertIn("我是車主", self.home)
        self.assertIn("我是汽美店家", self.home)
        self.assertIn('href="systems.html"', self.home)
        self.assertIn(POPCARD_STORY, self.home)
        self.assertIn('data-home-cta="system"', self.home)
        self.assertNotIn("popcard-saaspreview.", self.home)

    def test_go_keeps_the_shop_bridge_and_expands_the_registry_to_eleven_services(self):
        self.assertRegex(
            self.go,
            r'<section[^>]+id="shop-system-bridge"[^>]+aria-labelledby="shop-system-title"',
        )
        self.assertIn('href="systems.html"', self.go)
        self.assertIn(POPCARD_STORY, self.go)
        self.assertLess(
            self.go.index('id="shop-system-bridge"'),
            self.go.index('id="all-services"'),
        )
        go_javascript = (ROOT / "js" / "go.js").read_text(encoding="utf-8")
        services = re.search(
            r"const SERVICES = Object\.freeze\(\[(.*?)\]\);",
            go_javascript,
            re.DOTALL,
        )
        self.assertIsNotNone(services, "missing canonical SERVICES registry")
        slugs = set(
            re.findall(r'^\s+slug:\s+"([^"]+)"', services.group(1), re.MULTILINE)
        )
        self.assertEqual(len(slugs), 11)
        self.assertTrue({"popcard-demo", "site-launch", "grant-check"} <= slugs)

    def test_system_route_is_in_sitemap_and_production_healthcheck(self):
        sitemap = (ROOT / "sitemap.xml").read_text(encoding="utf-8")
        healthcheck = (
            ROOT / ".github" / "workflows" / "site-healthcheck.yml"
        ).read_text(encoding="utf-8")
        self.assertIn("https://popmonster.vip/systems.html", sitemap)
        self.assertIn('"systems.html"', healthcheck)
        self.assertIn("https://popmonster.vip/systems.html", healthcheck)
        self.assertIn(POPCARD_STORY, healthcheck)

    def test_private_loop_artifacts_are_not_published_with_github_pages(self):
        gitignore = (ROOT / ".gitignore").read_text(encoding="utf-8")
        self.assertRegex(gitignore, r"(?m)^/ui-loop/$")

    def test_system_entry_analytics_is_consent_gated_and_allowlisted(self):
        app = (ROOT / "js" / "home.js").read_text(encoding="utf-8")
        analytics = (ROOT / "js" / "home-analytics.js").read_text(encoding="utf-8")
        self.assertIn("'system_entry'", app)
        self.assertRegex(analytics, r"system_entry:\s*\[[^\]]*'target'[^\]]*\]")

    def test_home_footer_links_keep_a_comfortable_touch_target(self):
        css = (ROOT / "css" / "home-extreme.css").read_text(encoding="utf-8")
        self.assertRegex(
            css,
            r"\.home-page \.footer-links a\s*\{[^}]*min-height:\s*44px",
        )

    def test_readme_describes_the_actual_site(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        self.assertIn("# POP MONSTER 官方網站", readme)
        self.assertIn("systems.html", readme)
        self.assertNotIn("# 3Q貢丸 LINE Bot", readme)


if __name__ == "__main__":
    unittest.main()
