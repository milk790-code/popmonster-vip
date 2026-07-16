from pathlib import Path
import hashlib
import re
import struct
import subprocess
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
        for relative in (
            "go.html",
            "css/go.css",
            "js/go-analytics.js",
            "js/go.js",
            "go-preview.html",
            "docs/analytics/go-funnel-baseline.md",
        ):
            with self.subTest(relative=relative):
                self.assertTrue((ROOT / relative).is_file(), relative)

    def test_hero_copy_and_semantic_sections_are_fixed(self):
        html = self.read_required("go.html")
        for text in (
            "花錢前，先避開最貴的錯",
            "有些坑，等踩到才看到就太晚。",
            "租屋、合約、機票、精品、內容、汽美——先用免費第一步把風險說清楚，再決定要不要花錢。",
            "先問的成本是 0，踩雷的成本不是。",
            "為什麼免費？",
            "我在累積真實服務案例，需要實際使用者。",
            "現在加，等於零成本先卡位。",
            "看你需要哪一種，直接點連結，或在 LINE 搜尋 ID 加我。",
            "選我的問題",
            "直接看 7 個免費入口",
            "看 POP 汽美本業",
            "敏感資料先遮蔽｜需要專業資格時協助轉介",
        ):
            with self.subTest(text=text):
                self.assertIn(text, html)
        for element_id in (
            "main-content",
            "proof",
            "problem-router",
            "route-result",
            "founder",
            "all-services",
            "go-analytics-consent",
        ):
            with self.subTest(element_id=element_id):
                self.assertRegex(html, rf'id=["\']{re.escape(element_id)}["\']')

    def test_line_destinations_are_searchable_without_clicking(self):
        html = self.read_required("go.html")
        for line_id in (
            "@121lkspe",
            "@207cpaps",
            "@772iosnh",
            "@129vsziy",
            "@186vktox",
            "@805udwla",
        ):
            with self.subTest(line_id=line_id):
                self.assertIn(f"LINE ID：<code>{line_id}</code>", html)

    def test_html_loads_external_assets_and_complete_metadata(self):
        html = self.read_required("go.html")
        self.assertIn('lang="zh-Hant-TW"', html)
        self.assertIn('href="css/go.css"', html)
        analytics_tag = '<script src="js/go-analytics.js" defer></script>'
        app_tag = '<script src="js/go.js" defer></script>'
        self.assertIn(analytics_tag, html)
        self.assertLess(html.index(analytics_tag), html.index(app_tag))
        self.assertIn('src="js/go.js"', html)
        self.assertIn('rel="canonical" href="https://popmonster.vip/go"', html)
        self.assertRegex(html, r'rel=["\'](?:shortcut )?icon["\'][^>]+favicon\.svg')
        self.assertIn('property="og:image"', html)
        self.assertIn('name="twitter:card"', html)
        self.assertNotRegex(html, r'<script[^>]+src="https://www\.googletagmanager\.com')

    def test_v4_og_asset_is_scoped_and_not_the_legacy_3q_card(self):
        html = self.read_required("go.html")
        relative = "assets/go-v4/go-link-preview-2560x1440.png"
        self.assertIn(f"https://popmonster.vip/{relative}", html)

        asset = ROOT / relative
        legacy = ROOT / "og-image-1200x630.png"
        self.assertTrue(asset.is_file(), relative)
        payload = asset.read_bytes()
        self.assertEqual(payload[:8], b"\x89PNG\r\n\x1a\n")
        width, height = struct.unpack(">II", payload[16:24])
        self.assertEqual((width, height), (2560, 1440))
        self.assertNotEqual(
            hashlib.sha256(payload).digest(),
            hashlib.sha256(legacy.read_bytes()).digest(),
        )

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
        self.assertIn("crypto.randomUUID", js)
        self.assertIn("crypto.getRandomValues", js)
        self.assertIn("sessionStorage", js)
        self.assertIn("event_id", js)
        self.assertIn("session_hash", js)
        self.assertIn('type: "text/plain;charset=UTF-8"', js)
        self.assertNotIn("localStorage", js)
        self.assertNotIn("document.cookie", js)
        self.assertRegex(js, r'window\.Switchboard\s*=')
        self.assertIn("const allowVariants = isPreviewMode();", js)
        self.assertIn('category: category', js)
        self.assertIn('target: cta.dataset.target', js)
        self.assertIn("event.stopImmediatePropagation()", js)

    def test_ga4_funnel_is_explicitly_consented_and_allowlisted(self):
        analytics = self.read_required("js/go-analytics.js")
        for event_name in self.expected_events:
            with self.subTest(event_name=event_name):
                self.assertIn(event_name, analytics)
        self.assertIn("ck_consent", analytics)
        self.assertIn("navigator.globalPrivacyControl", analytics)
        self.assertIn("doNotTrack", analytics)
        self.assertNotIn("session_hash", analytics)
        self.assertNotIn("event_id", analytics)

        script = r'''
const assert = require("node:assert/strict");
const fs = require("node:fs");

let consent = "denied";
const calls = [];
globalThis.window = globalThis;
globalThis.location = { search: "?src=social" };
globalThis.navigator = { doNotTrack: "0", globalPrivacyControl: false };
globalThis.localStorage = {
  getItem(key) {
    assert.equal(key, "ck_consent");
    return consent;
  },
  setItem(key, value) {
    assert.equal(key, "ck_consent");
    consent = value;
  },
};
globalThis.gtag = (...args) => calls.push(args);
globalThis.document = {
  addEventListener() {},
  getElementById() { return null; },
  querySelector(selector) {
    return selector === "script[data-pm-analytics]" ? {} : null;
  },
  readyState: "loading",
};

const source = fs.readFileSync("js/go-analytics.js", "utf8");
eval(source);
calls.length = 0;

assert.equal(
  window.PopMonsterGoAnalytics.track("route_result", {
    slug: "legal-guidance",
    raw_text: "不得送出的原始對話",
  }),
  false,
);
assert.equal(calls.length, 0);

assert.equal(window.PopMonsterGoAnalytics.setConsent("granted"), true);
assert.deepEqual(calls[calls.length - 1], [
  "event",
  "page_ready",
  { source: "social" },
]);
calls.length = 0;
assert.equal(
  window.PopMonsterGoAnalytics.track("route_result", {
    slug: "legal-guidance",
    raw_text: "不得送出的原始對話",
  }),
  true,
);
assert.deepEqual(calls[0], [
  "event",
  "route_result",
  { slug: "legal-guidance", source: "social" },
]);

navigator.globalPrivacyControl = true;
assert.equal(window.PopMonsterGoAnalytics.track("line_start", { slug: "legal-guidance" }), false);
assert.equal(calls.length, 1);
navigator.globalPrivacyControl = false;
assert.equal(window.PopMonsterGoAnalytics.track("unknown_event", {}), false);
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

    def test_js_runtime_telemetry_is_private_stable_and_fail_open(self):
        script = r'''
const assert = require("node:assert/strict");
const fs = require("node:fs");
const { webcrypto } = require("node:crypto");

(async () => {
  let endpoint = "";
  let randomCalls = 0;
  let storageReads = 0;
  let storageWrites = 0;
  let storageBlocked = false;
  const stored = new Map();
  const beacons = [];

  Object.defineProperty(globalThis, "crypto", {
    configurable: true,
    value: {
      getRandomValues(target) {
        randomCalls += 1;
        return webcrypto.getRandomValues(target);
      },
      randomUUID() {
        randomCalls += 1;
        return webcrypto.randomUUID();
      },
    },
  });
  Object.defineProperty(globalThis, "navigator", {
    configurable: true,
    value: {
      doNotTrack: "0",
      globalPrivacyControl: false,
      sendBeacon(url, body) {
        beacons.push({ body, url });
        return true;
      },
    },
  });
  Object.defineProperty(globalThis, "sessionStorage", {
    configurable: true,
    value: {
      getItem(key) {
        storageReads += 1;
        if (storageBlocked) throw new Error("storage blocked");
        return stored.get(key) || null;
      },
      setItem(key, value) {
        storageWrites += 1;
        if (storageBlocked) throw new Error("storage blocked");
        stored.set(key, value);
      },
    },
  });

  globalThis.window = globalThis;
  window.location = { href: "https://popmonster.vip/go", search: "" };
  const body = { dataset: {} };
  const meta = { content: "" };
  globalThis.document = {
    addEventListener() {},
    body,
    documentElement: { dataset: {} },
    getElementById() { return null; },
    querySelector(selector) {
      return selector.includes("switchboard-events") ? meta : null;
    },
    querySelectorAll() { return []; },
    readyState: "loading",
  };

  const source = fs.readFileSync("js/go.js", "utf8");
  eval(source);

  assert.equal(window.Switchboard.sendEvent("page_ready"), false);
  assert.deepEqual(
    { beacons: beacons.length, randomCalls, storageReads, storageWrites },
    { beacons: 0, randomCalls: 0, storageReads: 0, storageWrites: 0 },
  );

  endpoint = "https://events.example.test/events";
  meta.content = endpoint;
  storageBlocked = true;
  assert.equal(
    window.Switchboard.sendEvent("route_result", { slug: "legal-guidance" }),
    true,
  );
  assert.equal(
    window.Switchboard.sendEvent("line_start", { slug: "legal-guidance" }),
    true,
  );
  assert.equal(beacons.length, 2);
  const payloads = await Promise.all(
    beacons.map(async ({ body: beaconBody, url }) => ({
      payload: JSON.parse(await beaconBody.text()),
      type: beaconBody.type,
      url,
    })),
  );
  assert.equal(payloads[0].url, endpoint);
  assert.equal(payloads[0].type, "text/plain;charset=utf-8");
  assert.match(
    payloads[0].payload.event_id,
    /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/,
  );
  assert.notEqual(payloads[0].payload.event_id, payloads[1].payload.event_id);
  assert.match(payloads[0].payload.session_hash, /^[0-9a-f]{64}$/);
  assert.equal(
    payloads[0].payload.session_hash,
    payloads[1].payload.session_hash,
  );
  assert.equal(payloads[0].payload.slug, "legal-guidance");
  assert.equal(payloads[1].payload.event, "line_start");

  const countsBeforePrivacy = { beacons: beacons.length, randomCalls, storageReads, storageWrites };
  navigator.globalPrivacyControl = true;
  assert.equal(window.Switchboard.sendEvent("page_ready"), false);
  navigator.globalPrivacyControl = false;
  navigator.doNotTrack = "1";
  assert.equal(window.Switchboard.sendEvent("page_ready"), false);
  navigator.doNotTrack = "0";
  document.body.dataset.preview = "true";
  assert.equal(window.Switchboard.sendEvent("page_ready"), false);
  assert.deepEqual(
    { beacons: beacons.length, randomCalls, storageReads, storageWrites },
    countsBeforePrivacy,
  );
})().catch((error) => {
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
