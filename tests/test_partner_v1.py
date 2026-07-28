from pathlib import Path
import hashlib
import re
import subprocess
import unittest


ROOT = Path(__file__).resolve().parents[1]


class PartnerV11ContractTests(unittest.TestCase):
    required_files = (
        "partner.html",
        "partner-demo.html",
        "css/partner.css",
        "js/partner.js",
        "docs/partner-v1.1/README.md",
        "docs/partner-v1.1/copy-pack.md",
        "docs/partner-v1.1/evidence-ledger.md",
        "docs/partner-v1.1/legal-review-draft.md",
        "docs/partner-v1.1/pilot-operations.md",
        "docs/partner-v1.1/release-checklist.md",
        "docs/partner-v1.1/review-report.md",
    )
    allowed_sources = {
        "direct",
        "facebook",
        "instagram",
        "group",
        "referral",
        "distributor",
        "demo",
    }
    allowed_events = {
        "page_ready",
        "eligibility_check",
        "evidence_open",
        "apply_line_start",
        "audit_line_start",
        "share_success",
    }

    def read_required(self, relative: str) -> str:
        path = ROOT / relative
        self.assertTrue(path.is_file(), f"missing required file: {relative}")
        return path.read_text(encoding="utf-8")

    def test_required_review_package_exists(self):
        for relative in self.required_files:
            with self.subTest(relative=relative):
                self.assertTrue((ROOT / relative).is_file(), relative)

    def test_partner_metadata_routes_and_section_order(self):
        html = self.read_required("partner.html")
        self.assertIn('lang="zh-Hant-TW"', html)
        self.assertIn('rel="canonical" href="https://popmonster.vip/partner"', html)
        self.assertIn('property="og:title"', html)
        self.assertIn('property="og:image"', html)
        self.assertIn('href="css/partner.css"', html)
        self.assertIn('src="js/partner.js"', html)
        self.assertIn('href="privacy.html"', html)
        self.assertIn('href="terms.html"', html)
        self.assertIn("把漏掉的詢問，變成預約、加購與回訪", html)

        ordered_ids = (
            "partner-hero",
            "fit-check",
            "work-bay",
            "costs",
            "evidence",
            "partner-faq",
            "partner-apply",
        )
        positions = []
        for section_id in ordered_ids:
            match = re.search(rf'id=["\']{re.escape(section_id)}["\']', html)
            self.assertIsNotNone(match, section_id)
            positions.append(match.start())
        self.assertEqual(positions, sorted(positions))

        self.assertEqual(html.count('data-line-action="apply"'), 2)
        self.assertEqual(html.count('data-line-action="audit"'), 2)
        self.assertIn("開啟 LINE 不代表訊息已送出", html)
        self.assertIn("本輪導入容量", html)
        self.assertIn("不構成區域排他權", html)
        self.assertEqual(html.count('data-capability-status="immediate"'), 3)
        self.assertEqual(html.count('data-capability-status="conditional"'), 1)
        self.assertEqual(html.count('data-capability-status="locked"'), 1)

    def test_public_copy_has_no_blocked_claims(self):
        public = "\n".join(
            self.read_required(relative)
            for relative in ("partner.html", "js/partner.js")
        )
        blocked = (
            "單店每月近 3,000",
            "19,502",
            "15 倍",
            "97%",
            "30%",
            "永久獨家",
            "保證導客",
            "保證營收",
            "90 天破億",
            "每日有人詢問",
            "單品近百單",
            "AI 比多數店員準",
            "加盟",
            "總部",
            "代理",
        )
        for phrase in blocked:
            with self.subTest(phrase=phrase):
                self.assertNotIn(phrase, public)

    def test_evidence_wall_is_scoped_and_cited(self):
        html = self.read_required("partner.html")
        ledger = self.read_required("docs/partner-v1.1/evidence-ledger.md")
        for url in (
            "https://keepergiken.co.jp/ir/irdata/yuho",
            "https://news.nextapple.com/entertainment/20250818/CFC336A34EFE264F777E9CA530B277AA",
            "https://www.ctee.com.tw/news/20250421701442-430503",
        ):
            with self.subTest(url=url):
                self.assertIn(url, html)
                self.assertIn(url, ledger)
        for phrase in (
            "6,661",
            "2025 年 6 月",
            "台灣整體門市，非單店",
            "受訪估計，非官方統計",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, html)
        self.assertIn("公開可用", ledger)
        self.assertIn("條件式", ledger)
        self.assertIn("撤除", ledger)

    def test_demo_is_noindex_fake_and_locked(self):
        html = self.read_required("partner-demo.html")
        self.assertRegex(html, r'<meta\s+name="robots"\s+content="noindex,nofollow"')
        self.assertGreaterEqual(html.count("展示樣品／非正式報價"), 2)
        self.assertIn('data-preview="true"', html)
        self.assertIn('name="partner-events" content=""', html)
        self.assertIn("PARTNER_DEMO_CONFIG", html)
        for key in ("storeName", "city", "logo", "services", "prices"):
            with self.subTest(key=key):
                self.assertIn(key, html)
        for forbidden in ("secret", "token", "customer", "phone", "lineId"):
            with self.subTest(forbidden=forbidden):
                self.assertNotRegex(html, rf'(?i)["\']{forbidden}["\']\s*:')
        self.assertIn("預覽模式：外部跳轉、事件與送出均已停用", html)

    def test_source_event_line_and_privacy_contracts(self):
        js = self.read_required("js/partner.js")
        html = self.read_required("partner.html")
        sources = set(re.findall(r'ALLOWED_SOURCES\s*=\s*new Set\(\[([^]]+)', js, re.S)[0].replace('"', "").replace("'", "").replace("\n", "").replace(" ", "").split(","))
        sources.discard("")
        events = set(re.findall(r'EVENT_NAMES\s*=\s*new Set\(\[([^]]+)', js, re.S)[0].replace('"', "").replace("'", "").replace("\n", "").replace(" ", "").split(","))
        events.discard("")
        self.assertEqual(sources, self.allowed_sources)
        self.assertEqual(events, self.allowed_events)
        self.assertIn("【PARTNER:${safeAction}:${safeSource}】", js)
        self.assertIn("encodeURIComponent(lineId)", js)
        self.assertIn("encodeURIComponent(message)", js)
        self.assertIn("navigator.globalPrivacyControl", js)
        self.assertIn("doNotTrack", js)
        self.assertIn("navigator.sendBeacon", js)
        self.assertIn("localStorage", js)
        self.assertNotIn("sessionStorage", js)
        self.assertNotIn("document.cookie", js)
        self.assertIn('id="partner-analytics-consent"', html)
        self.assertIn('data-consent="denied"', html)
        self.assertIn('data-consent="granted"', html)

    def test_runtime_rejects_tracking_and_strips_pii(self):
        script = r'''
const assert = require("node:assert/strict");
const fs = require("node:fs");

let consent = null;
const beacons = [];
globalThis.window = globalThis;
globalThis.location = { href: "https://popmonster.vip/partner?src=facebook", search: "?src=facebook" };
Object.defineProperty(globalThis, "navigator", {
  configurable: true,
  value: {
    doNotTrack: "0",
    globalPrivacyControl: false,
    sendBeacon(url, body) {
      beacons.push({ url, body });
      return true;
    },
  },
});
globalThis.localStorage = {
  getItem(key) {
    assert.equal(key, "partner_analytics_consent");
    return consent;
  },
  setItem(key, value) {
    assert.equal(key, "partner_analytics_consent");
    consent = value;
  },
};
const body = { dataset: {} };
const endpoint = { content: "https://events.example.test/partner" };
globalThis.document = {
  addEventListener() {},
  body,
  documentElement: { dataset: {} },
  getElementById() { return null; },
  querySelector(selector) {
    return selector.includes("partner-events") ? endpoint : null;
  },
  querySelectorAll() { return []; },
  readyState: "loading",
};

eval(fs.readFileSync("js/partner.js", "utf8"));
assert.equal(window.PopPartner.source, "facebook");
assert.equal(window.PopPartner.lineMessage("apply"), "【PARTNER:apply:facebook】");
assert.match(window.PopPartner.buildLineUrl("apply"), /line\.me\/R\/oaMessage/);
assert.equal(window.PopPartner.track("apply_line_start", { raw_text: "店主姓名與電話" }), false);
assert.equal(beacons.length, 0);
assert.equal(window.PopPartner.setConsent("denied"), false);
assert.equal(beacons.length, 0);
assert.equal(window.PopPartner.setConsent("granted"), true);
assert.equal(beacons.length, 1);
assert.equal(window.PopPartner.track("apply_line_start", {
  surface: "hero",
  store_name: "不可送出",
  city: "不可送出",
  raw_text: "不可送出",
}), true);
assert.equal(beacons.length, 2);

Promise.all(beacons.map(async ({ body: beaconBody }) => JSON.parse(await beaconBody.text())))
  .then((payloads) => {
    assert.deepEqual(payloads[0], { event: "page_ready", source: "facebook" });
    assert.deepEqual(payloads[1], {
      event: "apply_line_start",
      source: "facebook",
      surface: "hero",
    });
    navigator.globalPrivacyControl = true;
    assert.equal(window.PopPartner.track("share_success", { surface: "hero" }), false);
    assert.equal(beacons.length, 2);
    document.body.dataset.preview = "true";
    navigator.globalPrivacyControl = false;
    assert.equal(window.PopPartner.canNavigate(), false);
  })
  .catch((error) => {
    console.error(error);
    process.exitCode = 1;
  });
'''
        result = subprocess.run(
            ["node", "-e", script],
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=15,
        )
        self.assertEqual(result.returncode, 0, result.stderr or result.stdout)

    def test_css_accessibility_and_responsive_contract(self):
        css = self.read_required("css/partner.css").lower()
        for token in ("#11110f", "#f4efe5", "#b68b50", "#7d8386", "#c6453d"):
            with self.subTest(token=token):
                self.assertIn(token, css)
        self.assertIn(":focus-visible", css)
        self.assertRegex(css, r'min-(?:block-)?size\s*:\s*(?:4[4-9]|[5-9][0-9])px')
        self.assertIn("prefers-reduced-motion", css)
        self.assertIn("@media", css)
        self.assertIn("overflow-x: hidden", css)
        self.assertNotIn("linear-gradient", css)

    def test_documents_cover_copy_legal_pilot_and_release_gates(self):
        copy_pack = self.read_required("docs/partner-v1.1/copy-pack.md")
        legal = self.read_required("docs/partner-v1.1/legal-review-draft.md")
        pilot = self.read_required("docs/partner-v1.1/pilot-operations.md")
        release = self.read_required("docs/partner-v1.1/release-checklist.md")
        for phrase in (
            "社團短版",
            "30 秒話術",
            "LINE 關鍵字回覆",
            "異議處理",
            "一週詢問量",
            "平均首次回覆時間",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, copy_pack)
        for phrase in (
            "90 天",
            "首批耗材",
            "第三方費用",
            "資料保存期限",
            "真人接手",
            "不構成區域排他權",
            "七日審閱期",
            "預付儲值",
            "律師審查",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, legal)
        for phrase in (
            "20 家",
            "4 個有效回覆",
            "3 場 Demo",
            "1 份試行意向",
            "每店獨立 Worker",
            "fail closed",
            "回退原 webhook",
            "單店損益",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, pilot)
        for phrase in (
            "自家流量／訂單證據",
            "律師",
            "首批貨品 BOM",
            "單店損益表",
            "測試店 canary",
            "不得 push",
            "不得正式部署",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, release)

    def test_sitemap_indexes_partner_but_not_demo(self):
        sitemap = self.read_required("sitemap.xml")
        self.assertIn("<loc>https://popmonster.vip/partner</loc>", sitemap)
        self.assertNotIn("partner-demo", sitemap)

    def test_go_route_is_unchanged(self):
        expected = {
            "go.html": "12ecaed6b438917fd6d14727c2ca51e93db64bdb2e30197a9dcc16a84f34dbc1",
            "css/go.css": "70b7530a0a6dd5a92598fbacb26d8b4b3b73be4f9c28b65b3cb4abb1f1d012d0",
            "js/go.js": "b90fd958686f132e6e3010dd133fa05147686b51c7430308af26f7f8f032433d",
        }
        for relative, digest in expected.items():
            with self.subTest(relative=relative):
                payload = (ROOT / relative).read_bytes()
                self.assertEqual(hashlib.sha256(payload).hexdigest(), digest)


if __name__ == "__main__":
    unittest.main()
