# 學誼接線台 v4 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use test-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 將 `https://popmonster.vip/go` 升級成可用、可追來源、可回滾的「學誼接線台」，並由 GitHub Pages 正式發布。

**Architecture:** 保留純 HTML/CSS/JS 與既有 GitHub Pages 架構。`go.html` 提供語意結構與無 JavaScript 直達入口，`css/go.css` 負責黑金 5/7 split 與訊號軌，`js/go.js` 以固定 Service schema 驅動兩段分流、LINE 預填與 best-effort 事件；`go-preview.html` 只做不送事件、不跳轉的預覽控制台。

**Tech Stack:** HTML5、CSS、Vanilla JavaScript、Python `unittest`、GitHub Pages Actions。

## Global Constraints

- 正式網址固定 `https://popmonster.vip/go`，不改網域、不搬 hosting。
- 只接受來源 `direct`、`business-card`、`package-insert`、`social`、`legacy-worker`；其他值回退 `direct`。
- 固定 slug：`brand-content`、`rental-check`、`legal-guidance`、`flight-plan`、`luxury-check`、`travel-stay`、`creator-kit`、`auto-care`。
- LINE ID 與預填訊息都用 UTF-8 percent-encode；訊息含 `【GO:<slug>:<source>】`。
- 固定事件：`page_ready`、`hero_cta`、`route_stage_1`、`route_result`、`line_start`、`site_start`、`share_success`。
- DNT 或 GPC 開啟時不送事件；事件失敗不得阻斷 LINE、CreatorKit 或 POP 導流。
- 預覽模式不得送事件、不得離開預覽頁。
- 所有觸控目標至少 44px；鍵盤 focus 可見；reduced motion 停止訊號動畫。
- 無 JavaScript 時仍顯示七項免費與 POP 本業八個目的地。
- production rollback 基準為 `main@23ae4a3`。

---

### Task 1: Contract tests

**Files:**
- Create: `tests/test_go_v4.py`

**Interfaces:**
- Consumes: attachment v4 copy, slugs, sources, events, accessibility constraints.
- Produces: `python3 -m unittest tests/test_go_v4.py -v` contract suite.

- [ ] **Step 1: Write tests that require the four release files**

```python
for relative in ("go.html", "css/go.css", "js/go.js", "go-preview.html"):
    self.assertTrue((ROOT / relative).is_file(), relative)
```

- [ ] **Step 2: Verify RED**

Run: `python3 -m unittest tests/test_go_v4.py -v`

Expected: FAIL because `css/go.css`, `js/go.js`, `go-preview.html` and v4 copy do not exist.

### Task 2: Semantic shell and no-JS destinations

**Files:**
- Modify: `go.html`

**Interfaces:**
- Consumes: fixed hero copy and eight service records.
- Produces: `#problem-router`, `#route-result`, `#all-services`, `#founder`; eight static `[data-service-slug]` links.

- [ ] **Step 1: Replace the inline legacy page with semantic regions**

```html
<main id="main-content">
  <section class="hero" aria-labelledby="hero-title">...</section>
  <section id="problem-router" aria-labelledby="router-title">...</section>
  <section id="route-result" aria-live="polite">...</section>
  <section id="founder">...</section>
  <section id="all-services">...</section>
</main>
```

- [ ] **Step 2: Keep eight real destinations in HTML**

Each static link carries one exact `data-service-slug`; seven free services remain separate from `auto-care`.

### Task 3: Visual system and responsive behavior

**Files:**
- Create: `css/go.css`

**Interfaces:**
- Consumes: semantic class names from Task 2.
- Produces: fixed palette, desktop 5/7 split, mobile hero under about 65dvh, visible focus, 44px controls, reduced motion.

- [ ] **Step 1: Define the fixed token system**

```css
:root {
  --ink: #0a0a0a;
  --panel: #161616;
  --paper: #f5f5f5;
  --muted: #a8a8a8;
  --gold: #d4af37;
  --line: #2a2a2a;
}
```

- [ ] **Step 2: Encode the signature signal track and accessibility states**

```css
.signal-track { animation: signal-pulse 2.8s ease-in-out infinite; }
:focus-visible { outline: 3px solid var(--gold); outline-offset: 3px; }
button, .button, .service-link { min-block-size: 44px; }
@media (prefers-reduced-motion: reduce) { .signal-track { animation: none; } }
```

### Task 4: Router, source codes, LINE links and telemetry

**Files:**
- Create: `js/go.js`

**Interfaces:**
- Produces: `window.Switchboard = { SERVICES, parseSource, buildLineUrl, sendEvent, renderService }`.

- [ ] **Step 1: Define the immutable service contract**

```javascript
const ALLOWED_SOURCES = new Set(["direct", "business-card", "package-insert", "social", "legacy-worker"]);
const EVENT_NAMES = new Set(["page_ready", "hero_cta", "route_stage_1", "route_result", "line_start", "site_start", "share_success"]);
```

- [ ] **Step 2: Build official LINE URLs**

```javascript
function buildLineUrl(lineId, prefill, slug, source) {
  const message = `${prefill}\n【GO:${slug}:${source}】`;
  return `https://line.me/R/oaMessage/${encodeURIComponent(lineId)}/?${encodeURIComponent(message)}`;
}
```

- [ ] **Step 3: Make events privacy-aware and fail-open**

`sendEvent()` returns without network when preview, DNT, GPC, unknown event, or missing endpoint applies; otherwise it uses `navigator.sendBeacon()` and never cancels destination navigation.

### Task 5: Preview control console

**Files:**
- Create: `go-preview.html`

**Interfaces:**
- Consumes: query contract `preview=1&concept=&hook=&flow=&motion=`.
- Produces: controls for `signal/manual/tickets`, `offer/founder`, `guided/all`, `full/reduced`; iframe always carries `preview=1`.

- [ ] **Step 1: Build one local preview surface**

Controls update the iframe URL only; production remains `signal + offer + guided + full` and preview navigation is intercepted.

### Task 6: Metadata and release documentation

**Files:**
- Modify: `sitemap.xml`
- Create: `reports/go-v4-qa.md`

- [ ] **Step 1: Add the canonical `/go` sitemap entry**

```xml
<url><loc>https://popmonster.vip/go</loc></url>
```

- [ ] **Step 2: Record test, commit, deploy-run, live hash and rollback evidence**

The QA report must distinguish static page release from any future Worker/DO or print/Canva release.

### Task 7: Verify, publish and read back production

- [ ] **Step 1: Run unit/static checks**

Run: `python3 -m unittest tests/test_go_v4.py -v`

Expected: all tests PASS.

- [ ] **Step 2: Run browser acceptance at 320, 375, 390, 768 and 1440 widths**

Verify no horizontal overflow, hero CTA visibility, keyboard flow, one-result behavior, source fallback, preview no-navigation, no serious console errors.

- [ ] **Step 3: Commit the isolated branch, push, fast-forward main and push main**

Expected: GitHub Pages workflow succeeds for the exact main SHA.

- [ ] **Step 4: Production readback with cache buster**

Verify fixed hero text, external CSS/JS 200, eight destinations, encoded LINE prefill, canonical/OG/favicon, and compare production content to the deployed commit.
