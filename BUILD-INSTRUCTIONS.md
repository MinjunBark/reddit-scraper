# Shadowfax Reddit Intent-Signal Pipeline — Build Instructions

Portable spec, written to be copy-pasted as the README/build doc into a new repo. This rebuilds
the Reddit intent-signal system originally run manually/semi-automated at Shadowfax AI, as a real,
version-controlled, scheduled system: identify Reddit posts from the exact ICP showing buying-
intent signals, summarize and filter them, and deliver a daily digest to Discord.

This is a **faithful rebuild of the Shadowfax-specific system** — subreddits and pain-point
criteria are hardcoded to match what was actually run, not built as a generic multi-tenant tool.

---

## 1. What this system does, end to end

1. Every day at 6 AM, pull the most recent posts from two target subreddits: `r/dataanalyst` and
   `r/FPandA`
2. Summarize each post
3. Filter for posts that resonate with Shadowfax's specific pain points: data prep, data cleaning,
   forecasting, automation tooling, agentic tools with auditability, reducing manual ops through
   agentic tools
4. Post a daily digest to a designated Discord channel via webhook — summary, recommendation,
   direct source link per post, with the most relevant posts bolded
5. Human review happens after delivery, not automated: the digest is for a person to read and
   manually reply to the posts that genuinely resonate — this system does not auto-post replies

## 2. Stack

- **Language**: Python 3.11+
- **Reddit data access**: PRAW (Python Reddit API Wrapper) — official Reddit API client, free
  tier, no scraping-detection risk since it uses Reddit's own API rather than HTML scraping
- **Summarization + filtering**: Gemini API (matches the existing pattern used in Project F and
  Project S)
- **Delivery**: Discord webhook (matches Project S's existing autonomous-newsletter pattern)
- **Scheduling + hosting**: Railway, using Railway's cron schedule feature to trigger the script
  daily rather than running a long-lived process
- **Version control**: GitHub, private repo

## 3. Repo structure

```
shadowfax-reddit-pipeline/
├── README.md                  (this file, or a shortened pointer to it)
├── .env.example                (documents required env vars, no real secrets committed)
├── .gitignore                  (.env, __pycache__/, *.pyc)
├── requirements.txt
├── config.py                   (subreddits list, pain-point criteria, schedule constant)
├── main.py                     (entry point, orchestrates the full run)
├── reddit_client.py             (PRAW setup + fetch-recent-posts logic)
├── summarize_and_filter.py     (Gemini API calls: summarize each post, score against pain points)
├── discord_delivery.py         (formats and posts the daily digest via webhook)
└── railway.json                 (or railway's dashboard-configured cron, whichever Railway's
                                   current setup uses — confirm at build time, Railway's cron
                                   config method may be dashboard-only rather than a repo file)
```

## 4. Environment variables (`.env`, never committed — `.env.example` documents the shape only)

```
REDDIT_CLIENT_ID=
REDDIT_CLIENT_SECRET=
REDDIT_USER_AGENT=shadowfax-reddit-pipeline/1.0
GEMINI_API_KEY=
DISCORD_WEBHOOK_URL=
```

- Reddit `client_id`/`client_secret`: create a "script" type app at
  https://www.reddit.com/prefs/apps — free, immediate
- `GEMINI_API_KEY`: from Google AI Studio, same source as existing Project F/S keys
- `DISCORD_WEBHOOK_URL`: from the target Discord server → channel settings → Integrations →
  Webhooks → New Webhook → Copy URL

## 5. Config (`config.py`) — the values that make this Shadowfax-specific

```python
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
```

## 6. Build steps, in order

1. **Scaffold the repo** — create the file structure above, `git init`, first commit
2. **Reddit access** — register the Reddit app, implement `reddit_client.py`:
   `praw.Reddit(client_id=..., client_secret=..., user_agent=...)`, then
   `reddit.subreddit(name).new(limit=POSTS_PER_SUBREDDIT)` per subreddit in `config.SUBREDDITS`
3. **Summarize + filter** — for each fetched post, send title + body text to Gemini with a prompt
   that does two things in one call: (a) produce a 1-2 sentence summary, (b) score/classify
   whether the post resonates with any entry in `config.PAIN_POINTS`, returning which pain point(s)
   matched or none. Discard posts with no match before they reach the digest step
4. **Format the digest** — build a Discord message (or embed, Discord embeds render more cleanly
   than a raw pasted block): each surviving post gets its summary, the matched pain point(s), a
   direct link back to the Reddit thread, and a recommendation line (why this post is worth a
   reply). Bold the post title for the ones judged most relevant (e.g., matched more than one pain
   point, or has unusually high signal in the summary)
5. **Deliver** — POST the formatted digest to `DISCORD_WEBHOOK_URL`
6. **Wire up scheduling on Railway** — deploy the repo to Railway, configure it as a scheduled job
   (Railway's cron/scheduled-service feature) rather than a persistent worker, set it to run
   `python main.py` once daily. Confirm Railway's current cron configuration method when setting
   this up, since dashboard-vs-config-file setup can change between Railway platform versions
7. **Test end to end before trusting the schedule** — run `python main.py` manually first, confirm
   a real digest lands in the target Discord channel with correctly filtered, correctly formatted
   posts, before relying on the scheduled run

## 7. What this build intentionally does NOT do

- Does not auto-reply to any Reddit post — delivery ends at the Discord digest, replying stays a
  manual, human step, matching how it was actually run at Shadowfax
- Does not scrape Reddit's HTML directly — uses the official Reddit API via PRAW, staying within
  Reddit's terms of service and avoiding scraping-detection/blocking risk
- Does not generalize subreddits or pain points via a config UI or multi-tenant setup — this is a
  faithful rebuild of one specific system, not a reusable product; keep `config.py` as the single
  place those values live if they ever need to change

## 8. Verification checklist once built

- [ ] `python main.py` run manually produces a Discord message with real posts from both
      subreddits, not an empty digest
- [ ] Every post in the digest has a working, direct link back to the original Reddit thread
- [ ] Posts that don't match any pain point are confirmed filtered out (spot-check a known
      off-topic post is excluded)
- [ ] Railway's scheduled run actually fires at 6 AM without manual triggering, confirmed over at
      least 2 consecutive days
- [ ] `.env` is in `.gitignore` and no real secret ever appears in a commit
