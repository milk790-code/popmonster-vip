# TikTok: personal → business account, and inviting collaborators

TikTok does **not** expose account-type changes or cross-organisation
account migration through any public API. The Business Center API can
manage **ad accounts and pixels** between team members; it cannot move a
creator account between organisations or change a creator's account type.
This runbook covers the manual paths.

## Switch a personal account to a Business account

Required for IG-style content publishing scopes (`video.publish` audited
mode) and for TikTok Business Center asset assignment.

1. Open the TikTok mobile app (this is mobile-only).
2. Profile → ☰ menu → **Settings and privacy**.
3. **Account** → **Switch to Business Account**.
4. Pick the closest category (Education, Entertainment, etc.).
5. Optional: add contact info and website link.

Switching back to personal is allowed and resets the categorisation but
does not delete videos.

## Invite collaborators (Business Center membership)

A TikTok Business Center can host **ad accounts**, **pixels**, **catalogues**,
and **TikTok Shop** assets. Members get explicit permission per asset.

1. https://business.tiktok.com/ → **Business Center**.
2. Pick your BC → **Members** → **Invite members**.
3. Enter their TikTok-for-business email; pick role:
   - **Owner**
   - **Admin**
   - **Standard**
   - **Custom** (per-asset)
4. Send invite. They receive an email and accept inside their BC.

After they accept, this dashboard's **Permissions** tab can grant them
specific ad-account / pixel access via the BC API (we use
`/bc/asset/assign/`). For **content creator account access** there is no
API — they must be an Editor on TikTok's *creator* product, which is a
separate manual flow inside the TikTok Studio web UI.

## What to record in this dashboard

After completing the manual switch:

1. Re-run TikTok OAuth on the affected account so the new scopes apply.
2. Open **Transfers** tab → "Mark manual transfer complete" with notes
   describing what changed (so audit log captures the rationale).
