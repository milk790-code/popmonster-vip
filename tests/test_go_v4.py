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
        "popcard-demo",
        "site-launch",
        "grant-check",
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
    expected_surfaces = {"hero", "directory", "router_result", "pop_card"}

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
            "privacy.html",
            "docs/analytics/go-funnel-baseline.md",
        ):
            with self.subTest(relative=relative):
                self.assertTrue((ROOT / relative).is_file(), relative)

    def test_hero_copy_and_semantic_sections_are_fixed(self):
        html = self.read_required("go.html")
        for text in (
            "10 個免費第一步＋1 個 POP 汽美入口",
            "你先說卡在哪，我幫你把第一步分清楚。",
            "品牌內容、CreatorKit、店家系統、免費官網、補助快篩、租屋、合約、精品、機票、住宿、汽美選品",
            "直接看 11 個入口",
            "不知道選哪個？幫我分流",
            "POP 汽美：看商品／LINE 選品",
            "我先幫你把問題縮小，不急著推你買東西。",
            "免費範圍先說",
            "資料先遮蔽",
            "需專業資格時停止並協助轉介",
        ):
            with self.subTest(text=text):
                self.assertIn(text, html)
        for element_id in (
            "main-content",
            "route-map",
            "all-services",
            "problem-router",
            "route-result",
            "trust",
            "go-analytics-consent",
            "analytics-preferences",
        ):
            with self.subTest(element_id=element_id):
                self.assertRegex(html, rf'id=["\']{re.escape(element_id)}["\']')

        self.assertLess(html.index('id="all-services"'), html.index('id="problem-router"'))
        self.assertNotIn('class="signal-track"', html)
        self.assertNotIn('id="proof"', html)

    def test_directory_is_complete_visible_and_registry_rendered(self):
        html = self.read_required("go.html")
        self.assertNotRegex(html, r'<section\s+id="all-services"[^>]+hidden')
        self.assertEqual(len(re.findall(r'data-service-grid', html)), 5)
        self.assertNotRegex(html, r'<article\b[^>]*class="[^"]*service-card')
        self.assertIn("免費拿到", html)
        for category in ("business", "risk", "travel", "auto", "shop"):
            with self.subTest(category=category):
                self.assertRegex(html, rf'data-route-lane=["\']{category}["\']')
                self.assertRegex(html, rf'data-service-grid=["\']{category}["\']')

    def test_source_diagnostics_are_preview_only_and_consent_is_inline(self):
        html = self.read_required("go.html")
        css = self.read_required("css/go.css").lower()
        self.assertRegex(html, r'class="[^"]*source-indicator[^"]*preview-only[^"]*"')
        self.assertGreater(html.index('id="go-analytics-consent"'), html.index('id="trust"'))
        self.assertLess(html.index('id="go-analytics-consent"'), html.index("</main>"))
        self.assertNotRegex(
            css,
            r"\.analytics-consent\s*\{[^}]*position\s*:\s*fixed",
        )

    def test_line_destinations_are_searchable_in_registry(self):
        js = self.read_required("js/go.js")
        for line_id in (
            "@121lkspe",
            "@207cpaps",
            "@772iosnh",
            "@129vsziy",
            "@186vktox",
            "@805udwla",
            "@150tiznd",
        ):
            with self.subTest(line_id=line_id):
                self.assertIn(f'value: "{line_id}"', js)

    def test_html_loads_external_assets_and_complete_metadata(self):
        html = self.read_required("go.html")
        self.assertIn('lang="zh-Hant-TW"', html)
        self.assertIn('href="css/go.css"', html)
        analytics_tag = '<script src="js/go-analytics.js" defer></script>'
        app_tag = '<script src="js/go.js?v=20260729" defer></script>'
        self.assertIn(analytics_tag, html)
        self.assertLess(html.index(analytics_tag), html.index(app_tag))
        self.assertIn(app_tag, html)
        self.assertIn('rel="canonical" href="https://popmonster.vip/go"', html)
        self.assertRegex(html, r'rel=["\'](?:shortcut )?icon["\'][^>]+favicon\.svg')
        self.assertIn('property="og:image"', html)
        self.assertIn('name="twitter:card"', html)
        self.assertNotRegex(html, r'<script[^>]+src="https://www\.googletagmanager\.com')

    def test_v4_og_asset_is_social_safe_scoped_and_not_the_legacy_3q_card(self):
        html = self.read_required("go.html")
        relative = "assets/go-v4/go-link-preview-1200x630-20260729.png"
        self.assertIn(f"https://popmonster.vip/{relative}", html)
        self.assertIn(
            'property="og:title" content="你卡住的那件事，第一步先別急著花錢。"',
            html,
        )
        self.assertIn(
            'property="og:description" content="生意、網站、風險、出國、汽美，10 個免費入口幫你把下一步分清楚。"',
            html,
        )
        self.assertIn('property="og:image:width" content="1200"', html)
        self.assertIn('property="og:image:height" content="630"', html)
        self.assertNotIn("1.1億", html)
        self.assertNotIn("1.8億", html)
        self.assertNotIn("110,000,000", html)

        asset = ROOT / relative
        legacy = ROOT / "og-image-1200x630.png"
        self.assertTrue(asset.is_file(), relative)
        payload = asset.read_bytes()
        self.assertEqual(payload[:8], b"\x89PNG\r\n\x1a\n")
        width, height = struct.unpack(">II", payload[16:24])
        self.assertEqual((width, height), (1200, 630))
        self.assertNotEqual(
            hashlib.sha256(payload).digest(),
            hashlib.sha256(legacy.read_bytes()).digest(),
        )

    def test_one_registry_powers_directory_and_router_destinations(self):
        js = self.read_required("js/go.js")
        self.assertEqual(
            set(re.findall(r'slug:\s*"([a-z-]+)"', js)),
            self.expected_slugs,
        )
        self.assertIn("function renderDirectory()", js)
        self.assertIn("function createServiceTicket(service)", js)
        self.assertGreaterEqual(js.count("createServiceTicket(service)"), 3)
        self.assertIn("renderDirectory();", js)
        self.assertIn('label: "看 32 款商品"', js)
        self.assertIn('label: "傳車況，先避開買錯"', js)

    def test_all_eleven_services_have_strong_truth_bounded_hooks(self):
        js = self.read_required("js/go.js")
        hooks = (
            "先看改完，再決定要不要做。",
            "別再盯著空白頁，21 個 AI 工具直接免費用。",
            "簽約前先查一次，比入住後才後悔便宜。",
            "事情再亂，我先幫你排成一條看得懂的時間線。",
            "先別急著匯款，照片裡可能已經有紅旗。",
            "同一趟旅程，不要只看一個價格。",
            "不用再看 100 間，先把本次查詢縮成較符合條件的 3 間。",
            "先別亂買藥劑，傳車況再決定買什麼。",
            "讓客人自己想回來，先看公開展示再決定。",
            "建置費 0 元，先用滿意再談月費。",
            "3 分鐘看你的店符合哪些政府補助。",
        )
        for hook in hooks:
            with self.subTest(hook=hook):
                self.assertEqual(js.count(hook), 1)
        self.assertEqual(js.count("freeDeliverable:"), 11)
        self.assertEqual(js.count("freeScope:"), 11)

    def test_noscript_fallback_keeps_all_eleven_entries_usable(self):
        html = self.read_required("go.html")
        match = re.search(r"<noscript>(.*?)</noscript>", html, re.S)
        self.assertIsNotNone(match)
        fallback = match.group(1)
        for title in (
            "品牌內容",
            "CreatorKit",
            "租屋風險",
            "合約事件",
            "精品初篩",
            "機票比較",
            "旅遊住宿",
            "POP CARD 店家系統",
            "掘計畫 · 免費建官網",
            "政府補助快篩",
            "POP 汽美",
        ):
            with self.subTest(title=title):
                self.assertIn(title, fallback)
        self.assertGreaterEqual(len(re.findall(r"<a\b", fallback)), 12)
        self.assertIn("https://creatorkit.milk790.workers.dev/", fallback)
        self.assertIn("https://popmonster.vip/", fallback)

    def test_legacy_overclaims_are_removed(self):
        html = self.read_required("go.html")
        for phrase in (
            "房東是否本人",
            "討債指導",
            "省好幾千",
            "超低價",
            "價差差一半",
            "最省錢、最省時間、最少轉機",
            "最適合的 3 間",
            "工具不限次使用",
        ):
            with self.subTest(phrase=phrase):
                self.assertNotIn(phrase, html)

    def test_five_router_categories_exist(self):
        html = self.read_required("go.html")
        categories = set(re.findall(r'data-category=["\']([^"\']+)', html))
        self.assertEqual(categories, {"business", "risk", "travel", "auto", "shop"})

    def test_css_encodes_tokens_focus_touch_and_reduced_motion(self):
        css = self.read_required("css/go.css").lower()
        for token in ("#0d0c0a", "#171512", "#f4ebdd", "#b9ad9b", "#c6a15b", "#342f29"):
            with self.subTest(token=token):
                self.assertIn(token, css)
        self.assertIn(":focus-visible", css)
        self.assertRegex(css, r'min-(?:block-)?size\s*:\s*44px')
        self.assertIn("prefers-reduced-motion", css)
        self.assertIn("grid-template-columns", css)
        self.assertNotIn("min-inline-size: 20rem", css)
        self.assertIn('"iowan old style"', css)
        self.assertIn('"songti tc"', css)
        self.assertIn('"pingfang tc"', css)
        for selector in (".service-hook", ".service-ticket", ".ticket-label", ".ticket-stamp"):
            with self.subTest(selector=selector):
                self.assertIn(selector, css)
        self.assertRegex(css, r"\.service-ticket\s*\{[^}]*border[^;]*dashed")

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
        self.assertIn('localStorage.getItem("ck_consent") === "granted"', js)
        self.assertNotIn("document.cookie", js)
        self.assertRegex(js, r'window\.Switchboard\s*=')
        self.assertIn("const allowVariants = isPreviewMode();", js)
        self.assertIn('category: category', js)
        self.assertIn('target: cta.dataset.target', js)
        self.assertIn("event.stopImmediatePropagation()", js)
        for field in (
            "hook",
            "freeDeliverable",
            "freeScope",
            "outcome",
            "requiredInput",
            "boundary",
            "destinations",
            "icon",
        ):
            with self.subTest(field=field):
                self.assertIn(field, js)
        for surface in self.expected_surfaces:
            with self.subTest(surface=surface):
                self.assertIn(surface, js)
        self.assertIn('flow: "hybrid"', js)
        self.assertIn('new Set(["hybrid", "guided", "all"])', js)
        self.assertIn("resetRouter", js)
        self.assertIn("syncFlowControls", js)
        self.assertIn("開始兩步分流", js)
        self.assertIn('primary.href = "#problem-router"', js)
        self.assertIn('primary.href = "#all-services"', js)

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
calls.length = 0;
assert.equal(
  window.PopMonsterGoAnalytics.track("line_start", {
    slug: "legal-guidance",
    surface: "directory",
    raw_url: "https://line.me/private-prefill",
  }),
  true,
);
assert.deepEqual(calls[0], [
  "event",
  "line_start",
  { slug: "legal-guidance", surface: "directory", source: "social" },
]);
calls.length = 0;
assert.equal(
  window.PopMonsterGoAnalytics.track("site_start", {
    slug: "creator-kit",
    surface: "untrusted-query-value",
  }),
  true,
);
assert.deepEqual(calls[0], [
  "event",
  "site_start",
  { slug: "creator-kit", source: "social" },
]);

navigator.globalPrivacyControl = true;
assert.equal(window.PopMonsterGoAnalytics.track("line_start", { slug: "legal-guidance" }), false);
assert.equal(calls.length, 1);
navigator.globalPrivacyControl = false;
assert.equal(window.PopMonsterGoAnalytics.track("unknown_event", {}), false);
assert.equal(calls.length, 1);
globalThis.location.search = "?preview=1&src=social";
assert.equal(window.PopMonsterGoAnalytics.track("line_start", {
  slug: "legal-guidance",
  surface: "directory",
}), false);
assert.equal(window.PopMonsterGoAnalytics.setConsent("granted"), false);
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
  Object.defineProperty(globalThis, "localStorage", {
    configurable: true,
    value: {
      getItem(key) {
        assert.equal(key, "ck_consent");
        return "granted";
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
    window.Switchboard.sendEvent("line_start", {
      slug: "legal-guidance",
      surface: "router_result",
      raw_text: "不得傳送",
    }),
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
  assert.equal(payloads[1].payload.surface, "router_result");
  assert.equal(payloads[1].payload.raw_text, undefined);

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
        for value in ("signal", "manual", "tickets", "offer", "founder", "hybrid", "guided", "all", "full", "reduced"):
            with self.subTest(value=value):
                self.assertIn(f'value="{value}"', preview)
        self.assertIn("preview=1", preview)
        self.assertIn('src="js/go.js"', preview)
        self.assertRegex(preview, r'name="flow"\s+value="hybrid"\s+checked')
        self.assertIn("flow=hybrid", preview)

    def test_preview_founder_hook_has_distinct_copy(self):
        js = self.read_required("js/go.js")
        self.assertIn("HOOK_COPY", js)
        self.assertIn("我不先推銷，先陪你找出最該做哪一步。", js)

    def test_sitemap_includes_canonical_go_route(self):
        sitemap = self.read_required("sitemap.xml")
        self.assertIn("<loc>https://popmonster.vip/go</loc>", sitemap)


if __name__ == "__main__":
    unittest.main()
