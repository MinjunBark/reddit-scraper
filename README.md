# Shadowfax Reddit Intent-Signal Pipeline

Daily job that pulls the newest posts from `r/dataanalyst` and `r/FPandA`, uses Gemini to summarize
each one and score it against Shadowfax's pain points, and posts the survivors as a digest to Discord
for a human to read and reply to manually.

**This system never replies to Reddit.** Delivery ends at the Discord digest — replying is a
deliberate human step. See `BUILD-INSTRUCTIONS.md` for the full spec.

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

```bash
python main.py --dry-run --limit 3   # check auth + Gemini output, posts nothing, writes nothing
python main.py                        # real run: posts the digest, records what it sent
```

`--dry-run` is the right first move on any change to the prompt or filters.

## How it fits together

| File | Role |
|---|---|
| `config.py` | The only place Shadowfax-specific values live — subreddits, pain points, model |
| `reddit_client.py` | Runs the Apify actor, normalizes results. **The only source-aware module** |
| `seen_store.py` | SQLite record of already-sent post IDs |
| `summarize_and_filter.py` | One Gemini call per post → summary, matched pain points, recommendation |
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

Railway, as a **scheduled job** (not a persistent worker), running `python main.py` daily.
Set the same env vars in Railway, plus `SEEN_DB_PATH` pointed at a mounted volume — without a
volume the dedup database resets every run and the digest repeats itself.

Railway cron is UTC; offset `0 6 * * *` to whatever 6 AM should mean.
