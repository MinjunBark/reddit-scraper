"""Shadowfax-specific values. This is the single place these live — see BUILD-INSTRUCTIONS.md section 7."""

import os

SUBREDDITS = ["dataanalyst", "FPandA"]

# Derived from shadowfaxai_about.md. The first six are the original list from
# BUILD-INSTRUCTIONS.md; the rest close gaps found by reading Shadowfax's actual
# positioning — most importantly "verifying AI output", which is their founding thesis
# and was missing entirely.
PAIN_POINTS = [
    "data prep",
    "data cleaning",
    "forecasting",
    "automation tools",
    "agentic tools with auditability",
    "reducing manual operations with agentic tools",
    "distrust of AI output or the burden of verifying it",
    "reproducibility of analysis",
    "spreadsheet fragility at scale",
    "BI tool rigidity or waiting on engineering",
    "wanting analysis power without coding",
    "data profiling and exploration toil",
    "ad-hoc analysis request backlog",
    "repetitive manual reporting cycles",
]

# Volume in these subreddits is dominated by career talk, and it is the main source of
# false positives. Stated explicitly to the model rather than left to inference.
NON_SIGNALS = [
    "career advice, job hunting, resumes, salary, or interviews",
    "certifications, courses, degrees, or exam prep",
    "how to break into the field",
    "wanting to leave the profession — venting about the job is not buying intent",
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

GEMINI_MODEL = "gemini-3.6-flash"

# The free tier enforces TWO quotas, and the daily one is the binding constraint:
#   GenerateRequestsPerMinutePerProjectPerModel-FreeTier = 5   (per minute)
#   GenerateRequestsPerDayPerProjectPerModel-FreeTier    = 20  (per DAY)
# One request per post cannot work here — 50 posts/day would need 50 requests against a
# budget of 20. Batching is therefore load-bearing, not an optimization: at 15 posts per
# request a full day costs ~4 requests.
GEMINI_BATCH_SIZE = 15
GEMINI_RPM = 5
GEMINI_MAX_RETRIES = 4

# Overridden on Railway to point at the mounted volume.
SEEN_DB_PATH = os.environ.get("SEEN_DB_PATH", "seen.db")

# Every run writes its raw actor output and scored results here for inspection.
# Gitignored — this is scraped third-party content, not ours to commit.
DATA_DIR = os.environ.get("DATA_DIR", "data")
