# POP MONSTER Conversion Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use test-driven-development and verification-before-completion. This LOOP is executed inline because the owner requested autonomous continuation.

**Goal:** Restore a fully green regression suite and add privacy-safe homepage funnel events that can measure task selection, catalogue use, product interest, and support clicks after explicit analytics consent.

**Architecture:** Keep the existing static storefront and GA4 loader unchanged. Add one focused `home-analytics.js` allowlist adapter, then call it from the existing `home.js` interaction handlers; no event is recorded before `ck_consent=granted`, and free-form search text never leaves the page. Correct the stale `/go` test to the intentionally deployed scoped 2560×1440 preview asset without changing production metadata.

**Tech Stack:** Static HTML, browser JavaScript (ES5-compatible syntax), Python `unittest`, Node.js runtime assertions, Playwright CLI, Lighthouse.

## Global Constraints

- Do not change payment, LINE OA, customer data, secrets, or production configuration.
- Do not load GA4 before explicit analytics consent.
- Do not send raw catalogue search text or arbitrary event parameters.
- Preserve the existing 32-product catalogue, five task routes, cart behavior, accessibility, and non-blocking first paint.
- Stop before feature-branch push, PR creation, merge, or production deploy unless the owner explicitly authorizes the new release.

---

### Task 1: Repair the stale `/go` OG regression contract

**Files:**
- Modify: `tests/test_go_v4.py:76-92`
- Production reference only: `go.html:23-35`
- Asset reference only: `assets/go-v4/go-link-preview-2560x1440.png`

**Interfaces:**
- Consumes: the intentionally deployed `go-link-preview-2560x1440.png` metadata introduced by commit `5e932a3`.
- Produces: a regression assertion that still rejects the legacy root `og-image-1200x630.png` while accepting the current scoped asset and its exact dimensions.

- [x] **Step 1: Preserve the observed RED baseline**

Run:

```bash
python3 -m unittest tests.test_go_v4.GoV4ContractTests.test_v4_og_asset_is_scoped_and_not_the_legacy_3q_card -v
```

Expected: FAIL because `go.html` references `assets/go-v4/go-link-preview-2560x1440.png`, while the stale test expects `assets/go-v4/go-og-1200x630.png`.

- [x] **Step 2: Correct only the stale contract**

Replace the method body with:

```python
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
```

- [x] **Step 3: Verify GREEN**

Run the same targeted test. Expected: PASS with no production-file changes.

### Task 2: Add a consent-gated event allowlist

**Files:**
- Create: `js/home-analytics.js`
- Modify: `tests/test_home_extreme.py`
- Modify: `index.html:348-352`

**Interfaces:**
- Consumes: `window.gtag`, `localStorage.getItem('ck_consent')`.
- Produces: `window.PopMonsterAnalytics.track(eventName, parameters) -> boolean`.
- Allowed events and parameters:
  - `hero_cta`: `target`
  - `home_intent_select`: `intent`, `result_count`
  - `catalog_filter`: `category`, `result_count`
  - `catalog_search`: `category`, `query_length`, `result_count`
  - `product_select`: `sku`, `category`, `source`
  - `support_click`: `channel`, `placement`

- [x] **Step 1: Write the failing runtime contract**

Add a Python unittest that runs Node against `js/home-analytics.js` and asserts:

```javascript
assert.equal(window.PopMonsterAnalytics.track("hero_cta", { target: "intent" }), false);
assert.equal(calls.length, 0);
consent = "granted";
assert.equal(window.PopMonsterAnalytics.track("catalog_search", {
  category: "cleaning",
  query_length: 3,
  result_count: 4,
  query: "不得送出原文"
}), true);
assert.deepEqual(calls[0], ["event", "catalog_search", {
  category: "cleaning",
  query_length: 3,
  result_count: 4
}]);
assert.equal(window.PopMonsterAnalytics.track("unknown_event", {}), false);
```

Also assert that `index.html` loads `js/home-analytics.js` before `js/home.js`.

- [x] **Step 2: Run RED**

Run:

```bash
python3 -m unittest tests.test_home_extreme.HomepageExtremeContract.test_home_analytics_is_consent_gated_and_parameter_allowlisted -v
```

Expected: FAIL because `js/home-analytics.js` does not exist.

- [x] **Step 3: Implement the minimal adapter**

Create an IIFE that:

```javascript
var EVENT_PARAMETERS = {
  hero_cta: ['target'],
  home_intent_select: ['intent', 'result_count'],
  catalog_filter: ['category', 'result_count'],
  catalog_search: ['category', 'query_length', 'result_count'],
  product_select: ['sku', 'category', 'source'],
  support_click: ['channel', 'placement']
};
```

`track()` must return `false` for denied/missing consent, storage exceptions, unknown events, or missing/throwing `gtag`; otherwise it sends only allowlisted scalar parameters and returns `true`. Strings are trimmed and capped at 64 characters; non-finite numbers and non-scalar values are discarded.

Add this script before `home.js`:

```html
<script src="js/home-analytics.js" defer></script>
<script src="js/home.js" defer></script>
```

- [x] **Step 4: Run GREEN**

Run the targeted runtime contract and `node --check js/home-analytics.js`. Expected: PASS.

### Task 3: Wire the decision-first homepage funnel

**Files:**
- Modify: `index.html:95-98`
- Modify: `js/home.js:1-156`
- Modify: `tests/test_home_extreme.py`

**Interfaces:**
- Consumes: `window.PopMonsterAnalytics.track()` and existing filter/search DOM.
- Produces: the six allowlisted events without changing navigation, filtering, cart interception, or visible UI.

- [x] **Step 1: Write failing wiring assertions**

Require `data-home-cta="intent"` and `data-home-cta="catalog"` on the two hero actions. Require `home.js` to call each event name and to pass `query_length`, never a raw `query` parameter.

- [x] **Step 2: Run RED**

Run:

```bash
python3 -m unittest tests.test_home_extreme -v
```

Expected: FAIL on the new funnel wiring assertion.

- [x] **Step 3: Implement minimal event wiring**

- Make `setCategory(category)` return `applyFilters()`'s visible count.
- After filter and intent clicks, send the selected category/intent and visible count.
- On the search input `change` event, send only category, normalized query length, and visible count.
- Delegate catalogue-card clicks to `product_select`, excluding `[data-pm-add]` cart clicks already tracked by `store.js`.
- Delegate `[data-home-cta]`, LINE, and WhatsApp anchors to `hero_cta` or `support_click` with fixed target/channel/placement labels.
- Wrap the adapter call so analytics failures never interrupt storefront behavior.

- [x] **Step 4: Run GREEN**

Run homepage tests and Node syntax checks. Expected: all pass.

### Task 4: Full verification and local handoff

**Files:**
- Verify all modified files.
- Update: this plan's checkboxes and the local mission audit only after evidence exists.

**Interfaces:**
- Produces: a locally committed, push-ready branch; no external publication.

- [x] **Step 1: Run all automated tests**

```bash
python3 -m unittest discover -s tests -v
node --check js/main.js
node --check js/home-analytics.js
node --check js/home.js
node --check js/store.js
```

Expected: 29/29 or higher, all PASS.

- [x] **Step 2: Run local browser behavior checks**

At 390×844 and 1440×1000, verify no horizontal overflow, 32 products, filter/search behavior, 0 console errors/warnings, zero events before consent, and allowlisted events after consent.

- [x] **Step 3: Run Lighthouse against the local preview**

Expected gate: Accessibility, Best Practices, and SEO remain 100; Performance remains at least 90; GA network remains absent before consent.

- [x] **Step 4: Review and commit**

Review only task-scoped diffs, then commit with:

```bash
git commit -m "feat: add consented homepage conversion telemetry"
```

Do not push. Prepare a PR title/body and queue the feature-branch push/PR as the next human gate.
