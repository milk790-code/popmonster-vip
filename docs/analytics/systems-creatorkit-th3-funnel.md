# systems → CreatorKit `src=th3` 漏斗

## Funnel contract

| Stage | Origin | Event / metric | Fields |
|---|---|---|---|
| Creator CTA shown | `popmonster.vip` | `creator_impression` | `target=cta_a\|cta_b` |
| Generic CreatorKit entry clicked | `popmonster.vip` | `creator_entry_click` | `surface`, `target` |
| Featured deep-link clicked | `popmonster.vip` | `creator_tool_start` | `slug`, `surface` |
| CreatorKit landed | CreatorKit KV | `by_src.th3` | aggregate count |
| Deep-linked tool rendered | CreatorKit KV | `by_tool_open.th3.<tool>` | aggregate count |
| AI action executed | CreatorKit KV | `by_tool.<tool>` | aggregate count |

`creator_impression`, `creator_entry_click`, and `creator_tool_start` require
`ck_consent=granted`, honor DNT/GPC, use a random tab-scoped session hash, and
never include input text, account data, IP, cookies, or referrer URLs.

CreatorKit tool-open counters are aggregate-only and carry only the allowlisted
campaign source and tool ID. They honor DNT/GPC and deduplicate the same
source/tool once per tab.

## CTA experiment

- Variant A: browse-oriented copy (`先逛 22 個免費工具`).
- Variant B: outcome-oriented copy (`今天先做一支內容`).
- Assignment is random, stored in `sessionStorage`, and stable only for the tab.
- Compare both the variant and the surface; do not pool hero and lower-section
  clicks before checking whether one placement dominates.

## Featured tools

- `viral-breakdown`: identify why a successful post worked.
- `ai-script`: turn a topic into a short-video script.
- `rewrite`: reshape one caption for multiple platforms.

Each link preserves `src=th3` and adds an allowlisted `tool` deep link.

## Deployment order

1. Deploy CreatorKit Worker and verify `/api/events` plus `/api/stats`.
2. Deploy `go-events` and verify its expanded event contract plus `/stats`.
3. Merge/deploy the website last, then perform a consented browser smoke.

This order prevents the live page from sending events that an older collector
would reject.

## Rollback

Rollback the website first to stop new traffic, then rollback `go-events`, then
CreatorKit. No D1 migration is required; `go-events` reuses existing nullable
columns and CreatorKit adds only KV metric keys.
