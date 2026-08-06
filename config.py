"""Shadowfax-specific values. This is the single place these live — see BUILD-INSTRUCTIONS.md section 7."""

import os

SUBREDDITS = ["dataanalyst", "FPandA"]

PAIN_POINTS = [
    "data prep",
    "data cleaning",
    "forecasting",
    "automation tools",
    "agentic tools with auditability",
    "reducing manual operations with agentic tools",
]

POSTS_PER_SUBREDDIT = 25        # how many recent posts to pull per subreddit per run
SCHEDULE_CRON = "0 6 * * *"     # 6 AM daily, adjust timezone in Railway's cron config directly

# Source: Apify actor, since Reddit's own API no longer grants self-service access.
# Billed per result stored, so TIME_FILTER doubles as a cost control — "day" matches the
# daily cadence and avoids paying for posts we already processed yesterday.
APIFY_ACTOR = "trudax/reddit-scraper-lite"   # actor id oAuCIx3ItNrs2okjQ
TIME_FILTER = "day"

# Pinned so the per-run start fee stays predictable: Apify charges $0.02 per 1 GB of
# memory per actor start, so letting the actor pick a larger default silently multiplies it.
APIFY_MEMORY_MBYTES = 1024

# Free-tier rates, from Apify's API (higher subscription tiers pay less).
COST_PER_RESULT_USD = 0.004
COST_PER_START_USD = 0.02

GEMINI_MODEL = "gemini-2.5-flash"

# Free tier allows 5 requests/minute for this model. One call per post with no pacing
# exhausts that after 5 posts and silently drops the rest, so requests are throttled to
# this rate. Raise it if the key moves to a paid tier.
GEMINI_RPM = 5
GEMINI_MAX_RETRIES = 4

# Overridden on Railway to point at the mounted volume.
SEEN_DB_PATH = os.environ.get("SEEN_DB_PATH", "seen.db")
