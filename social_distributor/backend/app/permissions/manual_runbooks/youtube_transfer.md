# YouTube channel ownership transfer (manual — no API)

YouTube does **not** expose channel ownership transfer through the YouTube
Data API. The transfer must happen through the Google account interface.
This runbook lists the only paths that actually work.

## Path 1: move a channel to a Brand Account (recommended for matrix work)

A Brand Account decouples the channel from a specific personal Google
account, so multiple managers can be added/removed without re-OAuth-ing.

1. Sign in at https://www.youtube.com using the channel's current owner
   Google account.
2. Click the avatar → **Switch account** → select the channel.
3. Click the avatar → **Settings**.
4. **Advanced settings** → "Move channel to a Brand Account".
5. Pick an existing Brand Account or create a new one. (Creating one needs
   no extra Google account — the Brand Account is owned by your current
   Google identity.)
6. Confirm. Subscribers and videos move with the channel. Comments may take
   up to 24 hours to fully migrate.

## Path 2: add a manager / owner to an existing Brand Account

For an already-Brand-Account-backed channel, you can grant manager access
to other Google accounts without moving anything.

1. https://myaccount.google.com/brandaccounts
2. Pick the brand account → **Manage permissions**.
3. **Invite new users** → email of the new manager.
4. Choose role: **Owner** / **Manager** / **Communications Manager**.
5. Save. The invitee accepts via email.

> Only the **primary owner** can transfer the primary-owner role, and only
> after the new owner has been a manager for 7 days (Google's anti-takeover
> waiting period).

## Path 3: wholesale account transfer

YouTube does not support transferring a channel to a different Google
account directly. The only fully-clean alternative is:

1. Create a new Brand Account on the destination Google account.
2. Use Path 1 to move the channel into that new Brand Account.
3. Optionally remove the original owner from the Brand Account permissions.

## What to record in this dashboard

After completing any of the above:

1. Open **Transfers** tab → click "Mark manual transfer complete".
2. Re-run the YouTube OAuth flow on the destination account so the
   distributor stores fresh tokens.
3. Move the SocialAccount into the relevant persona group.
