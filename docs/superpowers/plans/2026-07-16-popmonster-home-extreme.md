# POP MONSTER Homepage Extreme Optimization Implementation Plan

> **For agentic workers:** Execute inline in the current session. Do not spawn subagents. Every behavior change follows red-green verification, and production publication remains human-gated.

**Goal:** Turn the existing POP MONSTER homepage into a decision-first, premium, accessible storefront while preserving the current vanilla HTML/CSS/JS stack and product/cart behavior.

**Architecture:** Keep `index.html` and the existing catalogue as the source of content truth. Add one homepage-only CSS layer and one homepage-only behavior module so shared product pages and cart code are not rewritten. Static contract tests protect semantics, claims, assets, and integration; Playwright validates browser behavior and responsive rendering.

**Tech Stack:** Static HTML, CSS custom properties, vanilla JavaScript, Python `unittest`, Node syntax check, Playwright CLI, Lighthouse CLI when available.

## Global constraints

- Work from `/Users/mac/Documents/Codex/popmonster-vip` at `main@da3f6b1`.
- Preserve all 32 catalogue cards, URLs, `data-pm-add`, prices, cart drawer, GA consent mode, privacy and terms links.
- Use only repository assets; no new dependency, framework, hotlinked image, fabricated testimonial, or fabricated metric.
- Homepage palette uses brass as its only accent; motion respects `prefers-reduced-motion`.
- Remove absolute safety claims from the homepage draft.
- Do not push, merge, deploy, publish, change secrets, or mutate customer data.

---

### Task 1: Lock the homepage contract

**Files:**
- Create: `tests/test_home_extreme.py`
- Test: `tests/test_home_extreme.py`

**Interfaces:**
- Consumes: `index.html`, `css/home-extreme.css`, `js/home.js`.
- Produces: repeatable checks for semantic structure, assets, search/filter hooks, risk-copy removal, responsive CSS and valid JavaScript.

- [x] Write the static contract assertions for canonical `/`, PNG social card, skip link, main landmark, real hero/featured imagery, five intent controls, product search/status, 32 cards and accessible cookie copy.
- [x] Run `python3 -m unittest tests.test_home_extreme -v` and confirm it fails because the homepage-only integration does not exist yet.

### Task 2: Build the decision-first homepage

**Files:**
- Modify: `index.html`
- Create: `css/home-extreme.css`
- Create: `js/home.js`
- Modify: `brand-spec.md`

**Interfaces:**
- Consumes: existing `.card[data-cat]`, `.filter-btn`, `js/store.js`, `favicon.svg`, `img/a001-main*.jpg`.
- Produces: `#main-content`, `.home-hero`, `[data-home-intent]`, `#product-search`, `#product-results`, `#product-grid`, and `window.PMHome`.

- [x] Replace the centered logo-only hero with a split thesis and real product image, keeping exactly two primary decision CTAs.
- [x] Replace emoji route cards with five text-led construction-task controls that select existing catalogue categories.
- [x] Replace the placeholder featured image with the real A001 asset and soften absolute safety copy.
- [x] Add accessible search, combined category/query filtering, result status, clear action, Escape handling, `aria-pressed`, and mobile-menu `aria-expanded` management in `js/home.js`.
- [x] Add the custom homepage design layer, keyboard focus, 390/768/1440 responsive behavior, reduced-motion fallback, and below-fold `content-visibility` in `css/home-extreme.css`.
- [x] Run `node --check js/home.js` and `python3 -m unittest tests.test_home_extreme -v`; confirm green.

### Task 3: Browser QA and deploy handoff

**Files:**
- Create locally generated screenshots under `.playwright-cli/` (ignored runtime artifacts only).
- Update: mission/audit artifacts under `/Users/mac/Documents/Codex/control-center/autopilot/`.

**Interfaces:**
- Consumes: local HTTP preview.
- Produces: console evidence, mobile/tablet/desktop screenshots, search/filter interaction proof, static link checks, performance report when available, and a production red-line item.

- [x] Start `python3 -m http.server 4173 --bind 127.0.0.1` and open `http://127.0.0.1:4173/` with Playwright CLI.
- [x] Verify 390×844, 768×1024 and 1440×1000 render without overflow; verify console errors/warnings are zero.
- [x] Search for「玻璃」and verify only matching cards remain; activate an intent and verify category/query state is predictable; clear and verify all 32 cards return.
- [x] Run the existing homepage contract, current `/go` tests, HTML/link/static checks, and Lighthouse if the local CLI can run without installing a new dependency.
- [x] Review `git diff`, preserve `da3f6b1` as rollback point, and queue production deployment for explicit owner approval.

## Verification note

- Homepage and delivery-asset scope: 16/16 tests pass.
- Full repository discovery: 28/29 tests pass. The sole failure is the pre-existing `/go` OG contract expecting `go-og-1200x630.png` while the untouched `go.html` currently points to `go-link-preview-2560x1440.png`; this homepage branch does not change `/go`.
- Lighthouse mobile: Performance 94, Accessibility 100, Best Practices 100, SEO 100; LCP 2.8s, TBT 120ms, CLS 0.
