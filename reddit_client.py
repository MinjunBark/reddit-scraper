"""PRAW setup and recent-post fetching.

Uses Reddit's official API (application-only read-only OAuth), not HTML scraping — see
BUILD-INSTRUCTIONS.md section 7.
"""

import logging
import os

import praw

import config

log = logging.getLogger(__name__)


def _client():
    missing = [
        name
        for name in ("REDDIT_CLIENT_ID", "REDDIT_CLIENT_SECRET", "REDDIT_USER_AGENT")
        if not os.environ.get(name)
    ]
    if missing:
        raise RuntimeError(f"Missing required env vars: {', '.join(missing)}")

    reddit = praw.Reddit(
        client_id=os.environ["REDDIT_CLIENT_ID"],
        client_secret=os.environ["REDDIT_CLIENT_SECRET"],
        user_agent=os.environ["REDDIT_USER_AGENT"],
    )
    if not reddit.read_only:
        log.warning("Reddit client is not in read-only mode; this pipeline never writes.")
    return reddit


def _normalize(submission, subreddit_name):
    return {
        "id": submission.id,
        "subreddit": subreddit_name,
        "title": submission.title,
        "selftext": submission.selftext or "",
        "permalink": f"https://www.reddit.com{submission.permalink}",
        "created_utc": submission.created_utc,
        "author": str(submission.author) if submission.author else "[deleted]",
        "score": submission.score,
    }


def fetch_recent_posts(limit=None):
    """Return the newest posts across config.SUBREDDITS as normalized dicts.

    A subreddit that fails is logged and skipped rather than killing the run — one dead
    subreddit shouldn't cost us the other's posts.
    """
    per_sub = limit or config.POSTS_PER_SUBREDDIT
    reddit = _client()
    posts = []

    for name in config.SUBREDDITS:
        try:
            fetched = [_normalize(s, name) for s in reddit.subreddit(name).new(limit=per_sub)]
        except Exception:
            log.exception("Failed to fetch r/%s", name)
            continue

        if not fetched:
            # Indistinguishable from "quiet subreddit" downstream, so say it loudly here.
            log.warning("r/%s returned zero posts — check the subreddit name and API access.", name)
        log.info("Fetched %d posts from r/%s", len(fetched), name)
        posts.extend(fetched)

    return posts
