"""Facebook Page publisher (Graph API v20).

Reference:
- https://developers.facebook.com/docs/pages-api/posts
- https://developers.facebook.com/docs/video-api/guides/publishing
"""
from __future__ import annotations

import logging
import os
import re
import time
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode

from ..config import config
from ._http import request_json
from .base import (
    InsightsSnapshot,
    OAuthProvider,
    PlatformError,
    PublishRequest,
    PublishResult,
    Publisher,
    TokenBundle,
)

log = logging.getLogger(__name__)

# Graph versions expire, and expiry is silent: Meta does not fail the call,
# it quietly reroutes it to the next version still alive. So an unattended
# fleet does not break on the expiry date -- it starts running against a
# version nobody chose, with no error to notice. v20.0 expires 2026-09-24.
#
# Pinned in one place, and overridable, so the next bump is one variable
# rather than a hunt through the file.
GRAPH_VERSION = os.environ.get("META_GRAPH_VERSION", "v23.0")
GRAPH_BASE = f"https://graph.facebook.com/{GRAPH_VERSION}"
GRAPH_VIDEO_BASE = f"https://graph-video.facebook.com/{GRAPH_VERSION}"
DIALOG_BASE = f"https://www.facebook.com/{GRAPH_VERSION}/dialog/oauth"


def reels_enabled() -> bool:
    """Whether video should be published as a Reel rather than a video post.

    A ``/videos`` post is only delivered to people who already follow the
    Page. Every Page in this fleet has close to zero followers, so that path
    is a broadcast to nobody -- which is precisely the "zero plays" symptom.
    Reels are the one surface Facebook still hands to non-followers for free.

    On by default, and safe to be: a Reel that Facebook refuses falls back to
    the old path, so the worst case is the behaviour we already had.
    ``FB_REELS=0`` forces the old path for everything.
    """
    return (os.environ.get("FB_REELS") or "1").strip().lower() not in {
        "0", "false", "no", "off",
    }


# A Reel that breaks the format rules is not refused by the ``finish`` call --
# encoding and validation happen afterwards, so ``finish`` answers 200 and the
# failure only surfaces in the status phases minutes later. Without waiting for
# that answer we would record SUCCEEDED for a Reel that never appears on the
# Page, and the fallback would never fire. So we wait.
REEL_READY_TIMEOUT = float(os.environ.get("FB_REEL_READY_TIMEOUT", "240"))
REEL_POLL_INTERVAL = float(os.environ.get("FB_REEL_POLL_INTERVAL", "6"))

# A Reel that has just finished encoding may not have its post id attached
# yet, so the lookup is worth repeating a couple of times before giving up.
POST_ID_LOOKUP_ATTEMPTS = int(os.environ.get("FB_POST_ID_ATTEMPTS", "3"))
POST_ID_LOOKUP_INTERVAL = float(os.environ.get("FB_POST_ID_INTERVAL", "4"))

# ``video_status`` values that mean we can stop waiting.
_REEL_DONE = {"ready"}
_REEL_DEAD = {"error", "upload_failed", "expired"}


class ReelPending(PlatformError):
    """We stopped waiting, but Facebook has not refused the Reel.

    This is deliberately not the same as a refusal, because the two call for
    opposite actions. A refusal means nothing was published and we should post
    the plain video instead. A pending Reel means the upload succeeded and
    Meta is still encoding -- posting the plain video as well would put the
    same clip on the Page twice, and a duplicate has to be deleted by hand.

    Observed 2026-08-15 on target 15470: ``upload_complete`` for the whole
    240s window. Nothing was wrong with it; it was simply slow.

    Carries the ``video_id`` so the caller can still record a handle without
    reaching for publisher instance state -- a publisher is shared, so
    stashing per-call values on ``self`` would leak across concurrent posts.
    """

    def __init__(self, message: str, *, video_id: str = "", **kwargs) -> None:
        super().__init__(message, **kwargs)
        self.video_id = video_id


def _reject_if_unsuccessful(payload: dict, what: str) -> None:
    """Graph answers 200 with ``{"success": false}`` on a refusal.

    Treating that as success is worse than an error would be: we would report
    a post id for something that was never published, and never fall back.
    """
    if isinstance(payload, dict) and payload.get("success") is False:
        raise PlatformError(
            f"{what} rejected: {payload.get('message') or payload}",
            retryable=False,
        )


DEFAULT_SCOPES = [
    "pages_show_list",
    "pages_read_engagement",
    "pages_manage_posts",
    # Required to comment as a Page (the auto first comment) and to like
    # another Page's post. Without it every comment attempt returns a
    # permission error. Adding it here only affects the classic-login
    # fallback -- when META_LOGIN_CONFIG_ID is set, Facebook Login for
    # Business takes the scope list from the login config on Meta's side,
    # so the config must be updated there too and every Page re-authorised.
    "pages_manage_engagement",
    "instagram_basic",
    "instagram_content_publish",
]

# Deliberately NOT requested by default -- each needs its own App Review and
# would force all connected Pages through OAuth again, so they are opt-in:
#   pages_manage_metadata  -> edit a Page's about/description
#   business_management    -> replace a Page's cover photo (also needs
#                             business verification)
# There is no scope that enables posting into a Facebook Group: Meta removed
# the Groups API and publish_to_groups from all versions on 2024-04-22, and
# the Graph API cannot publish shares of an existing post either. Sharing a
# post into a community is a manual action; see api/communities.py.
OPTIONAL_SCOPES = ["pages_manage_metadata", "business_management"]


class MetaOAuth(OAuthProvider):
    """Shared between Facebook and Instagram (Meta consolidated app)."""

    name = "meta"

    def refresh(self, refresh_token: str) -> TokenBundle:
        """B4: Meta long-lived Page tokens don't expire, but the user
        token used to mint them does (60 days). We re-exchange the stored
        page/user token via ``fb_exchange_token`` which both extends the
        expiry window and detects revocation (returns 4xx from Graph)."""
        creds = config.platform("meta")
        if not creds.configured:
            raise PlatformError("meta app credentials not configured",
                                retryable=False)
        long_lived = request_json(
            "GET",
            f"{GRAPH_BASE}/oauth/access_token",
            params={
                "grant_type": "fb_exchange_token",
                "client_id": creds.client_id,
                "client_secret": creds.client_secret,
                "fb_exchange_token": refresh_token,
            },
        )
        from datetime import datetime, timedelta, timezone as _tz
        expires_at = None
        if (ttl := long_lived.get("expires_in")):
            expires_at = datetime.now(_tz.utc) + timedelta(seconds=int(ttl))
        return TokenBundle(
            access_token=long_lived["access_token"],
            expires_at=expires_at,
            scopes=DEFAULT_SCOPES,
        )

    def authorization_url(self, state: str) -> str:
        creds = config.platform("meta")
        if not creds.configured:
            raise PlatformError("meta app credentials not configured", retryable=False)
        params = {
            "client_id": creds.client_id,
            "redirect_uri": creds.redirect_uri,
            "response_type": "code",
            "state": state,
            # auth_type=reauthorize forces FB to show the consent dialog even
            # for already-connected users. Without it, FB Login for Business
            # short-circuits to a dead-end "already connected" info page that
            # never redirects back to our callback, so we can't re-pull the
            # Page list (e.g. when the user has added new Pages since the
            # original OAuth, or when paging cursor was missed in older code).
            "auth_type": "reauthorize",
        }
        # Facebook Login for Business: scopes are baked into the login config
        # so we send config_id instead of scope. Falls back to classic
        # Facebook Login flow with explicit scopes when META_LOGIN_CONFIG_ID
        # isn't set.
        config_id = os.environ.get("META_LOGIN_CONFIG_ID", "").strip()
        if config_id:
            params["config_id"] = config_id
        else:
            params["scope"] = ",".join(DEFAULT_SCOPES)
        return f"{DIALOG_BASE}?{urlencode(params)}"

    def exchange_code(self, code: str) -> TokenBundle:
        creds = config.platform("meta")
        payload = request_json(
            "GET",
            f"{GRAPH_BASE}/oauth/access_token",
            params={
                "client_id": creds.client_id,
                "client_secret": creds.client_secret,
                "redirect_uri": creds.redirect_uri,
                "code": code,
            },
        )
        # Exchange short-lived for long-lived (60 day) token.
        long_lived = request_json(
            "GET",
            f"{GRAPH_BASE}/oauth/access_token",
            params={
                "grant_type": "fb_exchange_token",
                "client_id": creds.client_id,
                "client_secret": creds.client_secret,
                "fb_exchange_token": payload["access_token"],
            },
        )
        expires_at = None
        if (ttl := long_lived.get("expires_in")):
            expires_at = datetime.now(timezone.utc) + timedelta(seconds=int(ttl))
        return TokenBundle(
            access_token=long_lived["access_token"],
            expires_at=expires_at,
            scopes=DEFAULT_SCOPES,
        )


class FacebookPublisher(Publisher):
    name = "facebook"

    def validate(self, request: PublishRequest) -> list[str]:
        issues: list[str] = []
        if len(request.caption) > 63206:
            issues.append("Facebook post text exceeds 63,206 characters.")
        return issues

    def publish(
        self,
        token: TokenBundle,
        external_account_id: str,
        request: PublishRequest,
    ) -> PublishResult:
        # external_account_id is the Page ID. The token must be a Page Access Token,
        # which the OAuth callback converts via /me/accounts.
        page_token = token.extra.get("page_access_token", token.access_token)

        if request.media_url and request.media_kind == "video":
            result = self._publish_video(page_token, external_account_id, request)
        elif request.media_url and request.media_kind == "image":
            result = self._publish_photo(page_token, external_account_id, request)
        else:
            result = self._publish_text(page_token, external_account_id, request)

        # Phase D: auto first comment. Seeds engagement on new accounts
        # (no comment -> 0 reach) and carries the brand site for traffic.
        self._post_first_comment(page_token, result, request)
        return result

    def _post_first_comment(self, token, result: PublishResult,
                            req: PublishRequest) -> None:
        """Post a first comment on the page's own post right after publishing.

        ``req.first_comment`` is resolved upstream by
        ``compliance.engine.resolve_first_comment`` (per-post override, then
        per-account profile, then brand-line default, then the
        ``FB_FIRST_COMMENT`` environment variable). The env var is checked
        here too so a directly-constructed request still honours it.

        The text supports an optional ``{link}`` placeholder, filled with
        request.link_url. This never raises -- a failed comment must not
        fail an already-succeeded post -- but the outcome is written back
        onto ``result`` so the caller can record it.
        """
        post_id = result.external_post_id
        template = (getattr(req, "first_comment", "")
                    or os.environ.get("FB_FIRST_COMMENT", "")).strip()
        if not template or not post_id:
            return
        try:
            message = template.replace("{link}", req.link_url or "")
            if self._already_carries_funnel_link(token, post_id, message):
                result.first_comment_skipped = "funnel_link_already_present"
                log.info("first comment skipped for %s -- the post already "
                         "carries a funnel link", post_id)
                return
            data = request_json(
                "POST",
                f"{GRAPH_BASE}/{post_id}/comments",
                data={"message": message, "access_token": token},
                timeout=30,
            )
            result.first_comment_id = str(data.get("id", ""))
        except Exception as exc:
            result.first_comment_error = str(exc)[:500]
            # Still swallowed -- the post itself succeeded and must not be
            # reported as failed. But swallowing *silently* meant a comment
            # that never once worked looked identical to one working fine.
            # Commenting as a Page needs pages_manage_engagement, which is
            # not in DEFAULT_SCOPES, so the likely steady state here is
            # "permission denied on every post, forever, with no signal".
            log.warning(
                "first comment failed post_id=%s err=%s "
                "(commenting as a Page requires the pages_manage_engagement "
                "permission; check the account's granted scopes)",
                post_id, exc,
            )

    @staticmethod
    def _funnel_host(message: str) -> str:
        """The bare host of the first link in ``message``, lowercased."""
        match = re.search(r"https?://([^/\s]+)", message or "")
        return match.group(1).lower() if match else ""

    def _already_carries_funnel_link(self, token, post_id, message) -> bool:
        """Is there already a comment pointing at the same funnel host?

        This Page is not the only thing commenting on its own posts: a
        separate scheduled engine (``fb-auto-engage``) leaves a permanent-entry
        link of its own, minutes after publishing. Both are configured, both
        work, and neither knows about the other -- so the steady state is two
        funnel links per post under two different ``?src=`` codes. That splits
        the attribution the whole persona matrix exists to measure, and a Page
        repeatedly dropping links under its own posts is the shape Meta's spam
        rules actually act on.

        Read before writing, then. On 2026-08-14 a backfill was run off this
        adapter's own audit trail -- which honestly said the comment had failed
        -- without looking at the post, and put a second link on fifteen of
        them. "Our record says we did not do it" is not "it was not done" when
        something else is also doing it.

        Unreadable comments mean posting anyway: a missing funnel link costs
        more than a duplicated one, and this check must never be the reason a
        comment goes missing.
        """
        host = self._funnel_host(message)
        if not host:
            return False
        try:
            data = request_json(
                "GET",
                f"{GRAPH_BASE}/{post_id}/comments",
                params={"fields": "message,from", "limit": 25,
                        "access_token": token},
                timeout=30,
            )
        except Exception as exc:                              # noqa: BLE001
            log.warning("could not read existing comments on %s (%s); "
                        "posting anyway", post_id, exc)
            return False
        return any(host in (c.get("message") or "").lower()
                   for c in data.get("data", []))

    # ---- Engagement as a Page (used by the cross-account boost) ----------
    #
    # Both calls need pages_manage_engagement on the *acting* Page's token.
    # Unlike the first comment above these DO raise: a boost that silently
    # never happens is indistinguishable from one that works, which is how
    # the auto first comment went unnoticed for months.

    def like_as_page(self, token: TokenBundle, object_id: str) -> None:
        """Like a post as the Page that owns ``token``.

        Write-only by design on Meta's side: the read side (who liked this)
        was retired on 2020-11-02, so we record our own action rather than
        trying to verify it by reading the like list back.
        """
        page_token = token.extra.get("page_access_token", token.access_token)
        request_json(
            "POST",
            f"{GRAPH_BASE}/{object_id}/likes",
            data={"access_token": page_token},
            timeout=30,
        )

    def comment_as_page(self, token: TokenBundle, object_id: str, message: str) -> str:
        """Comment on ``object_id`` as the Page that owns ``token``.

        Returns the new comment id so the action is auditable after the
        fact (there is no way to pin it -- the Graph API has no pin field
        on the comment node at all).
        """
        page_token = token.extra.get("page_access_token", token.access_token)
        data = request_json(
            "POST",
            f"{GRAPH_BASE}/{object_id}/comments",
            data={"message": message, "access_token": page_token},
            timeout=30,
        )
        return str(data.get("id", ""))

    def _publish_text(self, token, page_id, req: PublishRequest) -> PublishResult:
        body = {"message": req.caption, "access_token": token}
        if req.link_url:
            body["link"] = req.link_url
        data = request_json("POST", f"{GRAPH_BASE}/{page_id}/feed", data=body)
        return PublishResult(external_post_id=data["id"], raw=data)

    def _publish_photo(self, token, page_id, req: PublishRequest) -> PublishResult:
        data = request_json(
            "POST",
            f"{GRAPH_BASE}/{page_id}/photos",
            data={
                "url": req.media_url,
                "caption": req.caption,
                "access_token": token,
            },
        )
        # Deliberately *not* run through _qualify. Photo posts answer with ids
        # that are already commentable as-is -- 110 of today's non-Reels posts
        # carry bare ids and every one of them has a live comment on it. Only
        # the Reels path returns the half-id that cannot be addressed, so only
        # the Reels path is normalised. Reshaping the 90% that works, on the
        # strength of a read-only check that never exercised writing, would be
        # trading a proven success for an unproven one.
        return PublishResult(external_post_id=data.get("post_id", data["id"]),
                             raw=data)

    def fetch_insights(self, token, external_account_id, external_post_id):
        page_token = token.extra.get("page_access_token", token.access_token)
        try:
            data = request_json(
                "GET",
                f"{GRAPH_BASE}/{external_post_id}/insights",
                params={
                    "access_token": page_token,
                    "metric": "post_impressions,post_impressions_unique,"
                              "post_reactions_by_type_total,post_clicks",
                },
            )
        except PlatformError:
            return None
        metrics = {item["name"]: item["values"][0]["value"]
                   for item in data.get("data", []) if item.get("values")}
        reactions = metrics.get("post_reactions_by_type_total") or {}
        likes = sum(reactions.values()) if isinstance(reactions, dict) else None
        return InsightsSnapshot(
            reach=metrics.get("post_impressions_unique"),
            impressions=metrics.get("post_impressions"),
            likes=likes,
            raw=metrics,
        )

    def _publish_video(self, token, page_id, req: PublishRequest) -> PublishResult:
        """Publish as a Reel when we can, as a plain video post otherwise.

        Reels carry format rules (portrait, duration) that cannot be checked
        from a URL, so the only honest test is to ask Facebook and accept the
        answer. A refusal must not cost us the post -- it only costs us the
        recommendation surface, which is exactly what the fallback records.
        """
        fallback_error = ""
        if reels_enabled():
            try:
                return self._publish_reel(token, page_id, req)
            except ReelPending as exc:
                # Not a refusal -- Meta simply had not finished encoding when
                # we stopped waiting. Posting the plain video too would put
                # the same clip on the Page twice, and only a human can undo
                # that. A row that turns out to point at a Reel Facebook never
                # published is the cheaper mistake: it is wrong data, not
                # wrong content on a live Page.
                log.warning("reel %s still pending; reporting it as published "
                            "rather than posting a second copy: %s",
                            req.media_url, exc)
                return PublishResult(
                    external_post_id=self._resolve_post_id(
                        token, page_id, exc.video_id, {},
                    ) if exc.video_id else "",
                    raw={"pending": str(exc)},
                    surface="reel",
                    surface_fallback_error=str(exc)[:500],
                )
            except PlatformError as exc:
                fallback_error = str(exc)[:500]
                log.warning(
                    "reel refused for page_id=%s, falling back to a plain "
                    "video post (no recommendation surface): %s",
                    page_id, exc,
                )

        # B6: video uploads can take 60-120s; use long timeout instead of
        # the 60s default so a slow Meta CDN doesn't fail us spuriously.
        data = request_json(
            "POST",
            f"{GRAPH_VIDEO_BASE}/{page_id}/videos",
            data={
                "file_url": req.media_url,
                "description": req.caption,
                "title": req.title or None,
                "access_token": token,
            },
            timeout=180,
        )
        # A freshly accepted video has no post behind it yet -- Facebook still
        # has to encode it. The Reels path waits for that (up to four minutes)
        # before asking for the post id; this path used to wait only as long as
        # the id lookup's own retries, about twelve seconds. On 2026-08-15 a
        # Reel upload hit a network fault, fell through to here, and its funnel
        # comment came back "Object with ID ... does not exist" -- the id was
        # correctly page-qualified, the post simply did not exist yet. That was
        # the single failure among thirty; every success went down the Reels
        # path, which waits.
        #
        # Unlike the Reels path, a timeout here must not raise: the post is
        # already published, so failing now would report a live post as failed
        # and invite a duplicate on retry. We wait, then proceed regardless.
        video_id = str(data.get("id"))
        try:
            self._await_reel_ready(token, video_id)
        except PlatformError as exc:
            log.warning(
                "video %s not confirmed ready; resolving its post id anyway "
                "(the post exists, only the comment is at risk): %s",
                video_id, exc,
            )

        # ``/videos`` hands back a video id, and a video id is not a post id --
        # the funnel comment would fail here for exactly the reason it failed
        # on Reels. Resolve it the same way rather than keeping a second copy
        # of the bug on the fallback path.
        return PublishResult(
            external_post_id=self._resolve_post_id(
                token, page_id, video_id, data,
            ),
            raw=data,
            surface="video",
            surface_fallback_error=fallback_error,
        )

    def _publish_reel(self, token, page_id, req: PublishRequest) -> PublishResult:
        """Three-phase hosted upload: start, transfer, finish.

        https://developers.facebook.com/docs/video-api/guides/reels-publishing

        Unlike ``/videos`` there is no single call that accepts a file URL:
        phase 1 reserves a video id and hands back a one-shot upload host,
        phase 2 tells that host to fetch our URL, phase 3 publishes it.
        """
        start = request_json(
            "POST",
            f"{GRAPH_BASE}/{page_id}/video_reels",
            data={"upload_phase": "start", "access_token": token},
            timeout=60,
        )
        video_id = start.get("video_id")
        upload_url = start.get("upload_url")
        # Observed in production (target 18141, 2026-08-16): Graph answered
        # start with video_id="0" and a real-looking upload_url. "0" is a
        # non-empty string, so ``not video_id`` is False and this sailed past
        # the check below -- transfer and finish both "succeeded" against a
        # video that was never real, polling sat at upload_complete forever,
        # and the eventual fallback composed page_id_0: a post id that has
        # never existed. The comment then failed with "Invalid post_id
        # parameter", but worse, ``post.published`` recorded a fabricated
        # handle as a live post. Treating "0" as absent turns that into an
        # ordinary refusal, which correctly falls back to a plain video post
        # that is actually real.
        if not video_id or video_id == "0" or not upload_url:
            raise PlatformError(
                f"reel start returned no upload target: {start}",
                retryable=False,
            )

        # Phase 2 is the odd one out in the whole Graph API: the credentials
        # and the source URL travel as headers, and the body stays empty.
        transfer = request_json(
            "POST",
            upload_url,
            headers={
                "Authorization": f"OAuth {token}",
                "file_url": req.media_url,
                "Content-Type": "application/octet-stream",
            },
            timeout=180,
        )
        _reject_if_unsuccessful(transfer, "reel transfer")

        try:
            finish = request_json(
                "POST",
                f"{GRAPH_BASE}/{page_id}/video_reels",
                data={
                    "video_id": video_id,
                    "upload_phase": "finish",
                    "video_state": "PUBLISHED",
                    "description": req.caption,
                    "access_token": token,
                },
                timeout=120,
            )
        except PlatformError as exc:
            # A timeout here cannot tell "never arrived" from "arrived and
            # published". Falling straight back to /videos on the second case
            # posts the same clip twice, and a duplicate has to be deleted by
            # hand -- the only irreversible outcome in this whole path. So ask
            # Facebook what actually happened before deciding.
            log.warning("reel finish did not answer cleanly, waiting for the "
                        "real outcome before deciding: %s", exc)
            # Wait it out rather than peeking once: a Reel that is still
            # encoding would read as "not ready", we would fall back, and then
            # it would publish anyway -- the duplicate we are trying to avoid.
            self._await_reel_ready(token, video_id)
            return PublishResult(
                external_post_id=self._resolve_post_id(token, page_id, video_id, {}),
                raw={"start": start, "finish": "timeout_but_published"},
                surface="reel",
            )

        _reject_if_unsuccessful(finish, "reel finish")
        self._await_reel_ready(token, video_id)

        return PublishResult(
            external_post_id=self._resolve_post_id(token, page_id, video_id, finish),
            raw={"start": start, "finish": finish},
            surface="reel",
        )

    def _resolve_post_id(self, token, page_id, video_id, finish: dict) -> str:
        """The id of the *post*, not the video.

        These are different objects and only the post accepts comments, which
        is where the funnel link lives. Settling for the video id does not
        merely mislabel the row -- it drops the link off every Reel.

        Observed in production on the first Reel published this way: the
        ``post_id`` field came back empty, we fell back to the bare video id,
        and commenting on it returned ``(#12) singular statuses API is
        deprecated``. So the bare video id is not a usable fallback at all --
        it is a guaranteed failure wearing the costume of a safe default.

        Two changes follow from that. The lookup is retried, because a Reel
        that just finished encoding may not have its post id attached yet;
        and when the lookup still yields nothing we compose ``page_id_video_id``,
        the shape Facebook post ids actually take, rather than handing back
        something already known not to work.

        That was still not enough, and the reason is worth recording. Graph
        *does* answer with a ``post_id`` -- but it answers with only the second
        half of one, e.g. ``122123395610788815``. Every id handed back was
        therefore truthful, un-composed, and unusable, so the fallback above
        never ran and all fifteen Reels published on 2026-08-14 lost their
        funnel comment. Reproduced read-only against a live page: the same post
        answers to ``1101945063003688_122125272129308556`` and returns the very
        same ``(#12) singular statuses API is deprecated`` for the bare half.

        Hence ``_qualify``: a post id is only usable once the page id is on the
        front of it, whichever route produced it.
        """
        if post_id := finish.get("post_id"):
            return self._qualify(page_id, post_id)

        for attempt in range(POST_ID_LOOKUP_ATTEMPTS):
            try:
                data = request_json(
                    "GET",
                    f"{GRAPH_BASE}/{video_id}",
                    params={"fields": "post_id", "access_token": token},
                    timeout=30,
                )
            except PlatformError as exc:
                log.warning("reel post id lookup failed (video_id=%s): %s",
                            video_id, exc)
                break
            if post_id := data.get("post_id"):
                return self._qualify(page_id, post_id)
            if attempt + 1 < POST_ID_LOOKUP_ATTEMPTS:
                time.sleep(POST_ID_LOOKUP_INTERVAL)

        composed = f"{page_id}_{video_id}"
        log.warning(
            "reel %s published but Graph never returned a post_id; falling "
            "back to the composed id %s so the funnel comment has something "
            "valid to target", video_id, composed,
        )
        return composed

    @staticmethod
    def _qualify(page_id, post_id) -> str:
        """A page post id is ``{page_id}_{post_id}``; anything less is a 404.

        Graph is inconsistent about which half it returns, so normalise rather
        than trust. An id that already carries an underscore is left exactly as
        it is -- re-prefixing a qualified id would break the working case to
        fix the broken one.
        """
        post_id = str(post_id)
        if "_" in post_id:
            return post_id
        qualified = f"{page_id}_{post_id}"
        log.info(
            "graph returned an unqualified post id %s; commenting needs the "
            "page-qualified form %s", post_id, qualified,
        )
        return qualified

    def _reel_status(self, token, video_id) -> str:
        """Current ``video_status``, or "" when it cannot be read."""
        try:
            data = request_json(
                "GET",
                f"{GRAPH_BASE}/{video_id}",
                params={"fields": "status", "access_token": token},
                timeout=30,
            )
        except PlatformError:
            return ""
        return ((data.get("status") or {}).get("video_status") or "").lower()

    def _await_reel_ready(self, token, video_id) -> None:
        """Block until Facebook says the Reel is live, or say it failed.

        ``finish`` only starts the encode. Aspect ratio, resolution, duration
        and frame rate are all judged after that, so a 200 from ``finish``
        proves nothing about whether anyone will ever see this. Raising here
        is what lets the caller fall back to a plain video post -- the whole
        point of the fallback is defeated if we never learn of the refusal.
        """
        deadline = time.monotonic() + REEL_READY_TIMEOUT
        last = ""
        while time.monotonic() < deadline:
            last = self._reel_status(token, video_id)
            if last in _REEL_DONE:
                return
            if last in _REEL_DEAD:
                raise PlatformError(
                    f"reel rejected after upload (video_status={last}); "
                    "usually aspect ratio, resolution, duration or frame rate",
                    retryable=False,
                )
            time.sleep(REEL_POLL_INTERVAL)
        raise ReelPending(
            f"reel still not ready after {REEL_READY_TIMEOUT:.0f}s "
            f"(last video_status={last or 'unknown'}); assuming it will "
            "publish rather than risking a duplicate",
            video_id=str(video_id),
            retryable=False,
        )
