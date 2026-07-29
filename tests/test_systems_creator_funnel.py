from pathlib import Path
import subprocess
import unittest


ROOT = Path(__file__).resolve().parents[1]
CREATORKIT = "https://creatorkit.milk790.workers.dev/"


class SystemsCreatorFunnelContract(unittest.TestCase):
    def test_first_viewport_exposes_three_real_creator_tools_and_two_cta_surfaces(self):
        html = (ROOT / "systems.html").read_text(encoding="utf-8")
        hero_end = html.index("</section>", html.index('class="systems-hero"'))
        hero = html[:hero_end]

        for tool in ("viral-breakdown", "ai-script", "rewrite"):
            with self.subTest(tool=tool):
                self.assertIn(f"{CREATORKIT}?src=th3&amp;tool={tool}", hero)
                self.assertIn(f'data-tool-slug="{tool}"', hero)

        self.assertIn('data-creator-entry data-surface="systems_hero"', hero)
        self.assertIn('data-creator-entry data-surface="systems_section"', html)
        self.assertIn('data-cta-a="先逛 22 個免費工具"', hero)
        self.assertIn('data-cta-b="今天先做一支內容"', hero)

    def test_systems_page_loads_the_allowlisted_first_party_funnel_and_consent_controls(self):
        html = (ROOT / "systems.html").read_text(encoding="utf-8")
        self.assertIn(
            '<meta name="systems-events" content="https://go-events.milk790.workers.dev/e">',
            html,
        )
        self.assertIn('<script src="js/systems-funnel.js" defer></script>', html)
        self.assertIn('id="systems-analytics-consent"', html)
        self.assertIn('data-systems-consent="granted"', html)
        self.assertIn('data-systems-consent="denied"', html)

    def test_runtime_is_consent_gated_session_scoped_and_sends_only_allowlisted_fields(self):
        script = r'''
const assert = require("node:assert/strict");
const fs = require("node:fs");

let consent = "denied";
const beacons = [];
const listeners = {};
const nodes = [
  {
    href: "https://creatorkit.milk790.workers.dev/?src=th3",
    dataset: {
      creatorEntry: "",
      surface: "systems_hero",
      ctaA: "先逛 22 個免費工具",
      ctaB: "今天先做一支內容",
    },
    textContent: "",
    addEventListener(name, fn) { this[name] = fn; },
    setAttribute() {},
  },
  {
    href: "https://creatorkit.milk790.workers.dev/?src=th3&tool=viral-breakdown",
    dataset: {
      creatorTool: "",
      toolSlug: "viral-breakdown",
      surface: "systems_hero",
    },
    addEventListener(name, fn) { this[name] = fn; },
    setAttribute() {},
  },
];
const consentPanel = {
  hidden: false,
  querySelectorAll() { return []; },
};
globalThis.window = globalThis;
globalThis.location = { search: "" };
Object.defineProperty(globalThis, "navigator", { configurable: true, value: {
  doNotTrack: "0",
  globalPrivacyControl: false,
  sendBeacon(url, body) {
    beacons.push({ url, body: JSON.parse(String(body)) });
    return true;
  },
}});
const session = new Map([
  ["systems_creator_cta_variant", "a"],
  ["switchboard_v5_session_hash", "a".repeat(64)],
]);
globalThis.sessionStorage = {
  getItem(key) { return session.get(key) || null; },
  setItem(key, value) { session.set(key, value); },
};
globalThis.localStorage = {
  getItem(key) { assert.equal(key, "ck_consent"); return consent; },
  setItem(key, value) { assert.equal(key, "ck_consent"); consent = value; },
};
globalThis.crypto = {
  randomUUID() { return "5f8a8fa6-e0d5-4f3b-8f79-8d7d9b2a5e7c"; },
  getRandomValues(bytes) { bytes.fill(7); return bytes; },
};
globalThis.document = {
  readyState: "loading",
  addEventListener(name, fn) { listeners[name] = fn; },
  querySelector(selector) {
    if (selector === 'meta[name="systems-events"]') {
      return { content: "https://go-events.milk790.workers.dev/e" };
    }
    return null;
  },
  querySelectorAll(selector) {
    if (selector === "[data-creator-entry], [data-creator-tool]") return nodes;
    if (selector === "[data-creator-cta]") return [nodes[0]];
    if (selector === "[data-systems-consent]") return [];
    return [];
  },
  getElementById(id) {
    return id === "systems-analytics-consent" ? consentPanel : null;
  },
};

eval(fs.readFileSync("js/systems-funnel.js", "utf8"));
listeners.DOMContentLoaded();
assert.equal(nodes[0].textContent, "先逛 22 個免費工具");
assert.equal(beacons.length, 0);

consent = "granted";
assert.equal(window.PopMonsterSystemsFunnel.track("creator_impression", {
  target: "cta_a",
}), true);
assert.equal(beacons.length, 1);
assert.match(beacons[0].body.event_id, /^[0-9a-f-]{36}$/);
const { event_id, ...firstPayload } = beacons[0].body;
assert.deepEqual(firstPayload, {
  event: "creator_impression",
  session_hash: "a".repeat(64),
  source: "th3",
  timestamp: beacons[0].body.timestamp,
  target: "cta_a",
});

nodes[0].click();
nodes[1].click();
assert.equal(beacons[1].body.event, "creator_entry_click");
assert.equal(beacons[1].body.surface, "systems_hero");
assert.equal(beacons[1].body.target, "cta_a");
assert.equal(beacons[2].body.event, "creator_tool_start");
assert.equal(beacons[2].body.slug, "viral-breakdown");
assert.equal(beacons[2].body.surface, "systems_hero");
assert.equal(beacons[2].body.target, "cta_a");
assert.equal(new URL(nodes[0].href).searchParams.get("cta"), "cta_a");
assert.equal(new URL(nodes[1].href).searchParams.get("cta"), "cta_a");

assert.equal(window.PopMonsterSystemsFunnel.track("unknown", {}), false);
navigator.globalPrivacyControl = true;
assert.equal(window.PopMonsterSystemsFunnel.track("creator_impression", {
  target: "cta_a",
}), false);
'''
        result = subprocess.run(
            ["node", "-e", script],
            cwd=ROOT,
            text=True,
            capture_output=True,
            timeout=15,
        )
        self.assertEqual(result.returncode, 0, result.stderr or result.stdout)


if __name__ == "__main__":
    unittest.main()
