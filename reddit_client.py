"""Fetches recent subreddit posts via the Apify actor `trudax/reddit-scraper-lite`.

This is the only module that knows where posts come from. It returns the same normalized
dicts regardless of source, so dedup / scoring / delivery are unaffected by this swap.
"""

import logging
import os
from datetime import datetime, timezone

from apify_client import ApifyClient

import config

log = logging.getLogger(__name__)


def _client():
    token = os.environ.get("APIFY_TOKEN")
    if not token:
        raise RuntimeError("Missing required env var: APIFY_TOKEN")
    return ApifyClient(token)


def _to_epoch(value):
    """Apify returns ISO-8601 timestamps; downstream sorting needs a float."""
    if not value:
        return 0.0
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).timestamp()
    except ValueError:
        log.warning("Unparseable createdAt: %r", value)
        return 0.0


def _subreddit_of(item):
    """Prefer the actor's community field; fall back to parsing the URL."""
    name = item.get("parsedCommunityName") or item.get("communityName") or ""
    name = name.removeprefix("r/")
    if name:
        return name
    url = item.get("url", "")
    if "/r/" in url:
        return url.split("/r/", 1)[1].split("/", 1)[0]
    return "unknown"


def _normalize(item):
    return {
        "id": item.get("parsedId") or item.get("id"),
        "subreddit": _subreddit_of(item),
        "title": item.get("title") or "",
        "selftext": item.get("body") or "",
        "permalink": item.get("url") or "",
        "created_utc": _to_epoch(item.get("createdAt")),
        "author": item.get("username") or "[deleted]",
        "score": item.get("upVotes") or 0,
    }


def _is_wanted(item):
    """Keep real posts only — drop comments, ads, and NSFW."""
    data_type = item.get("dataType")
    if data_type and data_type != "post":
        return False
    if item.get("isAd"):
        return False
    if item.get("over18"):
        return False
    return bool(item.get("title"))


def estimate_cost(max_items):
    """Worst-case USD for one run: every capped result stored, plus the start fee."""
    return max_items * config.COST_PER_RESULT_USD + config.COST_PER_START_USD


def fetch_recent_posts(max_items=None):
    """Run the Apify actor over config.SUBREDDITS and return normalized post dicts.

    `max_items` is a hard cap on TOTAL results across all subreddits, because that is the
    unit Apify bills on. Left unset, it defaults to POSTS_PER_SUBREDDIT per subreddit.
    """
    if max_items is None:
        max_items = config.POSTS_PER_SUBREDDIT * len(config.SUBREDDITS)
        per_sub = config.POSTS_PER_SUBREDDIT
    else:
        per_sub = max_items

    client = _client()

    run_input = {
        "startUrls": [
            {"url": f"https://www.reddit.com/r/{name}/new/"} for name in config.SUBREDDITS
        ],
        "sort": "New",
        "time": config.TIME_FILTER,
        "maxItems": max_items,
        "maxPostCount": per_sub,
        "maxComments": 0,
        "skipComments": True,
        "skipUserPosts": True,
        "skipCommunity": True,
        "includeNSFW": False,
        "proxy": {"useApifyProxy": True, "apifyProxyGroups": ["RESIDENTIAL"]},
    }

    log.info(
        "Starting Apify actor %s — capped at %d results, max cost ~$%.3f (takes 1-2 min)",
        config.APIFY_ACTOR, max_items, estimate_cost(max_items),
    )
    run = client.actor(config.APIFY_ACTOR).call(
        run_input=run_input,
        memory_mbytes=config.APIFY_MEMORY_MBYTES,
    )

    status = run.get("status")
    if status != "SUCCEEDED":
        raise RuntimeError(
            f"Apify run finished with status {status!r} — see "
            f"https://console.apify.com/actors/runs/{run.get('id')}"
        )

    raw = list(client.dataset(run["defaultDatasetId"]).iterate_items())
    posts = [_normalize(item) for item in raw if _is_wanted(item)]
    posts = [p for p in posts if p["id"]]

    log.info("Apify returned %d items, %d usable posts", len(raw), len(posts))
    for name in config.SUBREDDITS:
        count = sum(1 for p in posts if p["subreddit"].lower() == name.lower())
        if count == 0:
            # Looks identical to "quiet subreddit" downstream, so say it loudly here.
            log.warning("Zero posts for r/%s — check the subreddit name and the actor run.", name)
        else:
            log.info("r/%s: %d posts", name, count)

    return posts
