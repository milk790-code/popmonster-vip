# POP MONSTER LINE Redirect Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a review-ready `/r` page that routes approved service slugs to their LINE OA or site destination while carrying privacy-safe source attribution.

**Architecture:** Keep the redirect as `r/index.html`, one static noindex page so GitHub Pages can serve `/r` without a backend dependency. The page owns a fixed destination allowlist, sanitizes `src`, generates a short anonymous correlation ID for LINE handoff, sends only an allowlisted beacon payload when privacy signals permit, and always fails open to the destination.

**Tech Stack:** Static HTML, browser JavaScript, Python `unittest`, Node.js runtime harness.

## Global Constraints

- Preserve the eight canonical service slugs already used by `js/go.js`, including `creator-kit` and `auto-care`.
- Preserve `creatorkit` and `pop` as compatibility aliases while recording only canonical slugs.
- Never send raw `fbclid`, contact data, diagnostic text, cookies, or persistent identifiers.
- Respect Global Privacy Control and Do Not Track before telemetry.
- Keep redirect behavior independent from telemetry success.
- Keep the page `noindex` and outside the sitemap.
- Do not modify or deploy the Cloudflare collection Worker in this task.
- Do not deploy, push, merge, or publish without owner approval.

---

### Task 1: Lock the redirect contract with a failing runtime test

**Files:**
- Create: `tests/test_line_redirect.py`
- Test: `tests/test_line_redirect.py`

**Interfaces:**
- Consumes: an inline script from `r/index.html` plus browser-like globals supplied by a Node.js harness.
- Produces: executable requirements for routing, source sanitization, privacy signals, beacon minimization, and fail-open navigation.

- [x] **Step 1: Write the failing test**

```python
def test_line_route_uses_canonical_slug_source_and_correlation_id(self):
    result = self.run_redirect("?to=brand-content&src=fb_ad%21")
    self.assertEqual(result["beacons"][0]["payload"]["to"], "brand-content")
    self.assertNotIn("fbclid", result["beacons"][0]["payload"])
    self.assertIn("GO%3Abrand-content%3Afb_ad%3A", result["navigation"])
```

- [x] **Step 2: Run test to verify it fails**

Run: `python3 -m unittest tests.test_line_redirect -v`

Expected: FAIL because `r/index.html` does not exist.

- [x] **Step 3: Add remaining behavioral cases**

```python
def test_unknown_target_falls_back_to_brand_content(self):
    result = self.run_redirect("?to=unknown&src=direct")
    self.assertIn("%40121lkspe", result["navigation"])

def test_site_route_appends_sanitized_source(self):
    result = self.run_redirect("?to=creator-kit&src=paid%20social")
    self.assertEqual(result["navigation"], "https://creatorkit.milk790.workers.dev/?src=paidsocial")

def test_privacy_signal_disables_beacon_but_not_navigation(self):
    result = self.run_redirect("?to=brand-content&src=social", gpc=True)
    self.assertEqual(result["beacons"], [])
    self.assertIn("line.me/R/oaMessage", result["navigation"])

def test_beacon_failure_does_not_block_navigation(self):
    result = self.run_redirect("?to=brand-content&src=social", beacon_throws=True)
    self.assertIn("line.me/R/oaMessage", result["navigation"])
```

- [x] **Step 4: Re-run to confirm the suite still fails for the missing feature**

Run: `python3 -m unittest tests.test_line_redirect -v`

Expected: FAIL because `r/index.html` does not exist.

### Task 2: Implement the minimal static redirect page

**Files:**
- Create: `r/index.html`
- Modify: `tests/test_line_redirect.py`

**Interfaces:**
- Consumes: `to`, `src`, and optional ignored campaign parameters from `location.search`.
- Produces: one `location.replace()` call and, when permitted, one `text/plain;charset=UTF-8` beacon to `https://pop-r-redirect.milk790.workers.dev/collect` with `{cid,to,src}`.

- [x] **Step 1: Add the noindex document shell and fixed route table**

```html
<meta name="robots" content="noindex,nofollow">
<meta name="referrer" content="no-referrer">
<script>
var ROUTES = Object.freeze({
  "brand-content": { channel: "line", destination: "@121lkspe", label: "品牌內容" },
  "rental-check": { channel: "line", destination: "@207cpaps", label: "租屋風險" },
  "legal-guidance": { channel: "line", destination: "@772iosnh", label: "合約事件" },
  "flight-plan": { channel: "line", destination: "@129vsziy", label: "機票比較" },
  "luxury-check": { channel: "line", destination: "@186vktox", label: "精品初篩" },
  "travel-stay": { channel: "line", destination: "@805udwla", label: "旅遊住宿" },
  "creator-kit": { channel: "site", destination: "https://creatorkit.milk790.workers.dev/" },
  "auto-care": { channel: "site", destination: "https://popmonster.vip/" }
});
</script>
```

- [x] **Step 2: Add source normalization, anonymous ID generation, and privacy checks**

```js
function cleanSource(value) {
  return (String(value || "direct").replace(/[^A-Za-z0-9_-]/g, "").slice(0, 32) || "direct");
}
function privacySignalEnabled() {
  const dnt = navigator.doNotTrack || window.doNotTrack || navigator.msDoNotTrack || "";
  return navigator.globalPrivacyControl === true || dnt === "1" || String(dnt).toLowerCase() === "yes";
}
```

- [x] **Step 3: Add minimized beacon and fail-open destination building**

```js
if (!privacySignalEnabled() && typeof navigator.sendBeacon === "function") {
  navigator.sendBeacon(COLLECT_URL, new Blob([JSON.stringify({ cid, to, src })], { type: "text/plain;charset=UTF-8" }));
}
window.setTimeout(() => location.replace(destination), 250);
```

- [x] **Step 4: Run the focused suite to verify GREEN**

Run: `python3 -m unittest tests.test_line_redirect -v`

Expected: all redirect tests PASS.

### Task 3: Document use and run release verification

**Files:**
- Create: `docs/analytics/line-redirect.md`
- Verify: `r/index.html`, `tests/test_line_redirect.py`, `.github/workflows/static.yml`

**Interfaces:**
- Consumes: the completed `/r` contract.
- Produces: campaign URL examples, privacy rules, deployment boundary, and repeatable verification commands.

- [x] **Step 1: Document the canonical URL contract**

```markdown
`https://popmonster.vip/r?to=brand-content&src=social`

Allowed `to` values are the eight canonical service slugs. Invalid values fall back to `brand-content`.
```

- [x] **Step 2: Run syntax and contract verification**

Run: `python3 -m unittest discover -s tests -v`

Expected: all repository tests PASS.

- [x] **Step 3: Run a real-browser smoke check without contacting LINE or the collection Worker**

Run: serve the worktree locally, intercept external requests, open `/r?to=brand-content&src=social`, and confirm the attempted destination contains the encoded GO marker.

Expected: one attempted LINE navigation, no console errors, and no real external write.

- [x] **Step 4: Review the diff and stop at the deployment gate**

Run: `git diff --check && git status --short`

Expected: only `r/index.html`, `tests/test_line_redirect.py`, the implementation plan, and `docs/analytics/line-redirect.md` are changed.
