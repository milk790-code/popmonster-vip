# POP MONSTER LINE Redirect Contract

## Purpose

`/r/index.html` is the noindex transition page served by GitHub Pages at `/r`. It normalizes a fixed service target, attaches a sanitized source code, records a minimized anonymous handoff event when browser privacy signals allow it, and then opens the matching LINE OA or website.

This page is a review-ready local artifact until the owner approves merge and deployment.

## URL format

```text
https://popmonster.vip/r?to=brand-content&src=social
```

- `to`: one of the canonical targets below. Unknown values fall back to `brand-content`.
- `src`: ASCII letters, digits, `_`, and `-` only; all other characters are removed, the result is limited to 32 characters, and an empty result becomes `direct`.
- Other query parameters are ignored. In particular, raw `fbclid` is never copied to the beacon or LINE message.

## Canonical targets

| `to` | Destination | Handoff |
|---|---|---|
| `brand-content` | `@121lkspe` | LINE OA |
| `rental-check` | `@207cpaps` | LINE OA |
| `legal-guidance` | `@772iosnh` | LINE OA |
| `flight-plan` | `@129vsziy` | LINE OA |
| `luxury-check` | `@186vktox` | LINE OA |
| `travel-stay` | `@805udwla` | LINE OA |
| `creator-kit` | CreatorKit | Website |
| `auto-care` | POP MONSTER | Website |

Legacy compatibility aliases are normalized before attribution:

- `creatorkit` → `creator-kit`
- `pop` → `auto-care`

## LINE marker

LINE routes append an eight-character anonymous correlation ID:

```text
【GO:brand-content:social:12ab34cd】
```

The ID joins the transition beacon to the voluntary LINE handoff. It is not stored in a cookie or browser storage and is not an authentication token.

## Telemetry and privacy

When Global Privacy Control or Do Not Track is active, `/r` skips the beacon and continues to the destination. When telemetry is allowed, the page sends only this payload as `text/plain;charset=UTF-8`:

```json
{
  "cid": "12ab34cd",
  "to": "brand-content",
  "src": "social"
}
```

The redirect is fail-open: a missing or failed `sendBeacon` call does not block navigation. The page does not send raw campaign click IDs, diagnostic text, contact data, cookies, or persistent browser identifiers.

## Verification

```bash
python3 -m unittest tests/test_line_redirect.py -v
python3 -m unittest discover -s tests -v
git diff --check
```

Real-browser QA must intercept or block both `https://line.me/**` and `https://pop-r-redirect.milk790.workers.dev/**` so smoke tests do not create external writes or launch a real LINE handoff. Production GitHub Pages deployment is defined in `.github/workflows/static.yml`; the workflow runs only on `main` pushes or manual dispatch, so this PR cannot publish `/r` before merge.

## Deployment gate

Do not treat the file, tests, or local browser result as proof that `https://popmonster.vip/r` is live. Merge to the protected release branch and GitHub Pages deployment remain owner-reviewed external actions. After an approved deployment, verify the live HTTP response and one owner-approved mobile LINE handoff separately.
