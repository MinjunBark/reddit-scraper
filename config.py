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
APIFY_ACTOR = "trudax/reddit-scraper-lite"
TIME_FILTER = "day"

GEMINI_MODEL = "gemini-2.5-flash"

# Overridden on Railway to point at the mounted volume.
SEEN_DB_PATH = os.environ.get("SEEN_DB_PATH", "seen.db")
