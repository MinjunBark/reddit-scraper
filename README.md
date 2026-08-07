# Shadowfax Reddit Intent-Signal Pipeline

Daily job that pulls the newest posts from `r/dataanalyst` and `r/FPandA`, uses Gemini to summarize
each one and score it against Shadowfax's pain points, and posts the survivors as a digest to Discord
for a human to read and reply to manually.

**This system never replies to Reddit.** Delivery ends at the Discord digest — replying is a
deliberate human step.

## How it operates, in order

```
                    ┌─────────────────────────────┐
                    │  RAILWAY CRON  ·  0 6 * * *  │   (UTC — offset for your tz)
                    └──────────────┬──────────────┘
                                   │ runs: python main.py
                                   ▼
   ┌───────────────────────────────────────────────────────────────────┐
   │ ①  check_env()                                    main.py         │
   │    APIFY_TOKEN · GEMINI_API_KEY · DISCORD_WEBHOOK_URL             │
   │    Fails HERE, before spending anything, if a credential is missing│
   └──────────────┬────────────────────────────────────────────────────┘
                  ▼
   ┌───────────────────────────────────────────────────────────────────┐
   │ ②  fetch_recent_posts()                    reddit_client.py       │
   │                                                                   │
   │    ┌──────────────────────────────────────────┐                   │
   │    │ APIFY  trudax/reddit-scraper-lite        │  ← 💲 $0.02/run   │
   │    │   startUrls: r/dataanalyst, r/FPandA     │    + $0.004/post  │
   │    │   sort=new · time=day · maxItems=50      │                   │
   │    └────────────────┬─────────────────────────┘                   │
   │                     ▼                                             │
   │    drop: comments · ads · NSFW · untitled                         │
   │    normalize → {id, subreddit, title, selftext, permalink,        │
   │                 created_utc, author, score}                       │
   │                     │                                             │
   │                     ├──────────────► data/*_raw.json              │
   │                     └──────────────► data/latest_normalized.json  │
   └──────────────┬────────────────────────────────────────────────────┘
                  │  ~5–15 posts/day
                  ▼
   ┌───────────────────────────────────────────────────────────────────┐
   │ ③  filter_unseen()                            seen_store.py       │
   │       ◄──── reads ────  🗄  seen.db  (SQLite, needs Railway volume)│
   │    Drops anything sent in a previous digest                       │
   └──────────────┬────────────────────────────────────────────────────┘
                  │  only NEW posts
                  ▼
   ┌───────────────────────────────────────────────────────────────────┐
   │ ④  summarize_and_filter()            summarize_and_filter.py      │
   │                                                                   │
   │    chunk into batches of 15 ──┐  free tier = 20 requests/DAY,     │
   │                               │  so 1-call-per-post cannot work   │
   │    ┌──────────────────────────▼───────────────────────────┐       │
   │    │ GEMINI  gemini-3.6-flash  ·  temperature=0           │       │
   │    │   in:  14 PAIN_POINTS + 4 NON_SIGNALS + N posts      │       │
   │    │   out: [{post_index, summary, matched_pain_points,   │       │
   │    │          recommendation, signal_strength}]           │       │
   │    │   retry on 429 (quota) and 503 (overload)            │       │
   │    └──────────────────────────┬───────────────────────────┘       │
   │                               ▼                                   │
   │    map back by post_index (NOT position — order can shift)        │
   │    drop posts with matched_pain_points == []      ~6% survive     │
   │                               │                                   │
   │                    ┌──────────┴──────────┐                        │
   │                 matched              evaluated                    │
   │              (goes to Discord)   (everything scored)              │
   └──────────────┬────────────────────────────────────────────────────┘
                  ├──────────────────────► data/latest_scored.json
                  ▼
          ┌───────────────┐   --dry-run    ┌──────────────────────────┐
          │  dry run?     ├───────────────►│ print to stdout · STOP   │
          └───────┬───────┘      yes       │ nothing sent, no state   │
                  │ no                     └──────────────────────────┘
                  ▼
   ┌───────────────────────────────────────────────────────────────────┐
   │ ⑤  deliver()                              discord_delivery.py     │
   │                                                                   │
   │    sort: 🔥 most-relevant first, then signal, then newest         │
   │      🔥 = signal_strength "high"  OR  ≥2 pain points matched      │
   │    build embed per post: title(link) · summary · matched ·        │
   │      why-reply · footer · timestamp(viewer's local tz)            │
   │    chunk at 10 embeds/message  ── Discord's hard limit            │
   │    0 matches → still sends "no matching posts today"              │
   │                          │                                        │
   │                          ▼                                        │
   │              ┌────────────────────────┐                           │
   │              │  DISCORD  #channel     │                           │
   │              └────────────────────────┘                           │
   │    any non-2xx → raise → exit 1 → Railway marks run FAILED        │
   └──────────────┬────────────────────────────────────────────────────┘
                  ▼
   ┌───────────────────────────────────────────────────────────────────┐
   │ ⑥  mark_seen(evaluated)                       seen_store.py       │
   │       ──── writes ────►  🗄  seen.db                              │
   └───────────────────────────────────────────────────────────────────┘
                  ▼
        👤  HUMAN reads the digest and replies manually on Reddit
            ── the system NEVER posts to Reddit ──
```

## Setup

```bash
pip install -r requirements.txt
cp .env.example .env   # then fill in the values
```

Credentials needed (all free, see `.env.example` for where each comes from):

| Var | Source |
|---|---|
| `APIFY_TOKEN` | https://console.apify.com/settings/integrations → Personal API tokens |
| `GEMINI_API_KEY` | https://aistudio.google.com/apikey |
| `DISCORD_WEBHOOK_URL` | target channel → Integrations → Webhooks → New Webhook |

### Why Apify and not Reddit's API

`BUILD-INSTRUCTIONS.md` §2 specifies PRAW against Reddit's official API. That is no longer
available: under Reddit's Responsible Builder Policy, self-service app creation is closed and new
credentials require manual approval. Posts are therefore sourced through the Apify actor
`trudax/reddit-scraper-lite`.

Note that Reddit's Public Content Policy requires an agreement for commercial use of Reddit content
regardless of how it is fetched. That question is not resolved by using Apify — it is a business
decision recorded here so it isn't rediscovered later.

## Running

`main.py` is the only file you run — everything else is an imported module.

```bash
./run.sh                    # real run: posts the digest, records what it sent
./run.sh --dry-run          # prints the digest, posts nothing, writes no state
```

Or directly, if you prefer:

```bash
.venv/bin/python main.py --dry-run --limit 10
```

Use `.venv/bin/python`, not bare `python` — dependencies live in the venv.

| Flag | Effect |
|---|---|
| `--dry-run` | Print the digest instead of posting. No Discord message, no state written. |
| `--limit N` | Cap **total** results across both subreddits. The cost lever. |
| `--time WINDOW` | `hour`/`day`/`week`/`month`/`year`. Defaults to `day`. |

`--dry-run` is the right first move on any change to the prompt or filters.

**Dedup is real:** a second run straight after the first finds nothing new and sends
"no matching posts today". That is correct, not a bug. To re-deliver posts already sent,
delete `seen.db`.

## How it fits together

| File | Role |
|---|---|
| `config.py` | The only place Shadowfax-specific values live — subreddits, pain points, model |
| `reddit_client.py` | Runs the Apify actor, normalizes results. **The only source-aware module** |
| `seen_store.py` | SQLite record of already-sent post IDs |
| `summarize_and_filter.py` | Batched Gemini scoring → summary, matched pain points, recommendation |
| `discord_delivery.py` | Builds embeds, chunks to Discord's 10-embed limit, POSTs |
| `main.py` | Orchestrates, and owns the ordering guarantees below |

Two ordering rules matter:

- **Deliver before recording.** State is written only after Discord accepts the digest, so a crash
  mid-run doesn't silently burn a day's posts.
- **Record everything evaluated, not just matches.** Otherwise non-matching posts get re-scored and
  re-billed on every future run.

If zero posts match, the digest still sends a short "no matching posts today" message. An explicit
"ran, found nothing" is what distinguishes a working job from a broken one.

## Cost

Apify bills this actor per event (rates from Apify's API, free tier):

| Event | Free-tier rate |
|---|---|
| Result stored | **$0.004** each ($4.00 / 1,000) |
| Actor start | **$0.02** per 1 GB of memory, per run |

The actor-start fee is charged **per run regardless of how many results come back**, so a
10-result test run costs about `10 × $0.004 + $0.02 = $0.06`, not $0.04. `APIFY_MEMORY_MBYTES`
is pinned to 1024 in `config.py` so that fee stays at $0.02 rather than scaling with a larger
default.

Full daily production (50 results) is roughly **$0.22/day ≈ $6.60/month**. Paid Apify tiers drop
the per-result rate to $0.0034. `TIME_FILTER = "day"` holds the volume down by not re-fetching
posts already processed. Gemini stays inside the free tier at this volume.

Use `--limit N` to cap **total** results on test runs — it's the cost lever, and the run logs the
worst-case cost before it starts.

## Deployment

See **`RAILWAY-SETUP.md`** for full steps, constraints, and UTC cron conversions.

Short version: Railway as a **scheduled job** (not a persistent worker) running `python main.py`.
Cron and volumes are **dashboard-only** — they cannot be set from `railway.json` or the CLI. A
volume must be mounted with `SEEN_DB_PATH` pointing into it, or the dedup database resets every
run and the digest repeats itself daily. Railway cron is UTC with no timezone setting.
