from pathlib import Path
import json
import subprocess
import textwrap
import unittest
from urllib.parse import unquote


ROOT = Path(__file__).resolve().parents[1]
REDIRECT_PAGE = ROOT / "r" / "index.html"


class LineRedirectContractTests(unittest.TestCase):
    def read_page(self) -> str:
        self.assertTrue(REDIRECT_PAGE.is_file(), "missing required file: r/index.html")
        return REDIRECT_PAGE.read_text(encoding="utf-8")

    def run_redirect(
        self,
        search: str,
        *,
        gpc: bool = False,
        dnt: str = "0",
        beacon_throws: bool = False,
    ) -> dict:
        self.assertTrue(REDIRECT_PAGE.is_file(), "missing required file: r/index.html")
        harness = textwrap.dedent(
            f"""
            const fs = require("node:fs");

            const html = fs.readFileSync("r/index.html", "utf8");
            const match = html.match(/<script>([\\s\\S]*?)<\\/script>/i);
            if (!match) throw new Error("missing inline redirect script");

            const beacons = [];
            let navigation = "";
            globalThis.window = globalThis;
            globalThis.location = {{
              search: {json.dumps(search)},
              replace(value) {{ navigation = String(value); }},
            }};
            Object.defineProperty(globalThis, "navigator", {{
              configurable: true,
              value: {{
                doNotTrack: {json.dumps(dnt)},
                globalPrivacyControl: {str(gpc).lower()},
                sendBeacon(url, body) {{
                  if ({str(beacon_throws).lower()}) throw new Error("beacon unavailable");
                  beacons.push({{
                    payload: JSON.parse(body.body),
                    type: body.type,
                    url: String(url),
                  }});
                  return true;
                }},
              }},
            }});
            globalThis.Blob = class Blob {{
              constructor(parts, options) {{
                this.body = parts.join("");
                this.type = options.type;
              }}
            }};
            globalThis.setTimeout = (callback) => {{ callback(); return 1; }};

            eval(match[1]);
            process.stdout.write(JSON.stringify({{ beacons, navigation }}));
            """
        )
        result = subprocess.run(
            ["node", "-e", harness],
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=15,
        )
        self.assertEqual(result.returncode, 0, result.stderr or result.stdout)
        return json.loads(result.stdout)

    def test_line_route_uses_canonical_slug_source_and_correlation_id(self):
        result = self.run_redirect(
            "?to=brand-content&src=fb_ad%21&fbclid=raw-tracking-token"
        )
        self.assertEqual(len(result["beacons"]), 1)
        beacon = result["beacons"][0]
        self.assertRegex(beacon["payload"]["cid"], r"^[0-9a-f]{8}$")
        self.assertEqual(
            beacon["payload"],
            {
                "cid": beacon["payload"]["cid"],
                "src": "fb_ad",
                "to": "brand-content",
            },
        )
        self.assertEqual(beacon["type"], "text/plain;charset=UTF-8")
        self.assertEqual(
            beacon["url"],
            "https://pop-r-redirect.milk790.workers.dev/collect",
        )
        self.assertIn("%40121lkspe", result["navigation"])
        self.assertIn(
            f"GO%3Abrand-content%3Afb_ad%3A{beacon['payload']['cid']}",
            result["navigation"],
        )

    def test_page_is_noindex_referrer_safe_and_has_a_javascript_fallback(self):
        html = self.read_page()
        self.assertIn('lang="zh-Hant-TW"', html)
        self.assertRegex(
            html,
            r'<meta\s+name="robots"\s+content="noindex,nofollow">',
        )
        self.assertIn('<meta name="referrer" content="no-referrer">', html)
        self.assertIn("正在開啟服務…", html)
        self.assertNotIn("正在開啟 LINE…", html)
        self.assertIn("<noscript>", html)
        self.assertIn('href="/go"', html)
        sitemap = (ROOT / "sitemap.xml").read_text(encoding="utf-8")
        self.assertNotRegex(
            sitemap,
            r"<loc>https://popmonster\.vip/r(?:\.html)?</loc>",
        )

    def test_all_canonical_line_routes_use_the_expected_oa_and_label(self):
        routes = {
            "brand-content": ("@121lkspe", "品牌內容"),
            "rental-check": ("@207cpaps", "租屋風險"),
            "legal-guidance": ("@772iosnh", "合約事件"),
            "flight-plan": ("@129vsziy", "機票比較"),
            "luxury-check": ("@186vktox", "精品初篩"),
            "travel-stay": ("@805udwla", "旅遊住宿"),
        }
        for slug, (line_id, label) in routes.items():
            with self.subTest(slug=slug):
                result = self.run_redirect(f"?to={slug}&src=social")
                decoded = unquote(result["navigation"])
                self.assertIn(f"line.me/R/oaMessage/{line_id}/?", decoded)
                self.assertIn(f"你好，我想先做{label}免費第一步。", decoded)
                payload = result["beacons"][0]["payload"]
                self.assertRegex(payload["cid"], r"^[0-9a-f]{8}$")
                self.assertIn(f"【GO:{slug}:social:{payload['cid']}】", decoded)
                self.assertEqual(payload["to"], slug)

    def test_site_routes_append_source_without_changing_the_destination(self):
        routes = {
            "creator-kit": "https://creatorkit.milk790.workers.dev/?src=paidsocial",
            "auto-care": "https://popmonster.vip/?src=paidsocial",
        }
        for slug, expected in routes.items():
            with self.subTest(slug=slug):
                result = self.run_redirect(f"?to={slug}&src=paid%20social")
                self.assertEqual(result["navigation"], expected)
                payload = result["beacons"][0]["payload"]
                self.assertRegex(payload["cid"], r"^[0-9a-f]{8}$")
                self.assertEqual(payload["src"], "paidsocial")
                self.assertEqual(payload["to"], slug)

    def test_legacy_site_aliases_normalize_to_canonical_slugs(self):
        aliases = {
            "creatorkit": (
                "creator-kit",
                "https://creatorkit.milk790.workers.dev/?src=direct",
            ),
            "pop": ("auto-care", "https://popmonster.vip/?src=direct"),
        }
        for alias, (canonical, destination) in aliases.items():
            with self.subTest(alias=alias):
                result = self.run_redirect(f"?to={alias}&src=direct")
                self.assertEqual(result["navigation"], destination)
                self.assertEqual(result["beacons"][0]["payload"]["to"], canonical)

    def test_unknown_target_falls_back_to_brand_content(self):
        result = self.run_redirect("?to=not-a-service&src=direct")
        decoded = unquote(result["navigation"])
        self.assertIn("line.me/R/oaMessage/@121lkspe/?", decoded)
        payload = result["beacons"][0]["payload"]
        self.assertIn(f"【GO:brand-content:direct:{payload['cid']}】", decoded)
        self.assertEqual(payload["to"], "brand-content")

    def test_source_is_ascii_sanitized_truncated_and_never_empty(self):
        result = self.run_redirect(
            "?to=brand-content&src=campaign_%E5%8F%B0%E7%81%A3-123456789012345678901234567890"
        )
        source = result["beacons"][0]["payload"]["src"]
        self.assertEqual(source, "campaign_-1234567890123456789012")
        self.assertEqual(len(source), 32)

        empty = self.run_redirect("?to=brand-content&src=%21%40%23")
        self.assertEqual(empty["beacons"][0]["payload"]["src"], "direct")

    def test_privacy_signals_disable_beacon_without_blocking_navigation(self):
        cases = (
            {"gpc": True, "dnt": "0"},
            {"gpc": False, "dnt": "1"},
            {"gpc": False, "dnt": "yes"},
        )
        for case in cases:
            with self.subTest(case=case):
                result = self.run_redirect(
                    "?to=brand-content&src=social",
                    **case,
                )
                self.assertEqual(result["beacons"], [])
                self.assertIn("line.me/R/oaMessage", result["navigation"])

    def test_beacon_failure_does_not_block_navigation(self):
        result = self.run_redirect(
            "?to=brand-content&src=social",
            beacon_throws=True,
        )
        self.assertEqual(result["beacons"], [])
        self.assertIn("line.me/R/oaMessage", result["navigation"])


if __name__ == "__main__":
    unittest.main()
