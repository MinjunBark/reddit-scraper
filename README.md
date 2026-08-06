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
| `REDDIT_CLIENT_ID` / `REDDIT_CLIENT_SECRET` | a **script**-type app at https://www.reddit.com/prefs/apps |
| `GEMINI_API_KEY` | https://aistudio.google.com/apikey |
| `DISCORD_WEBHOOK_URL` | target channel → Integrations → Webhooks → New Webhook |

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
| `reddit_client.py` | PRAW, read-only, official API (not scraping) |
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

## Deployment

Railway, as a **scheduled job** (not a persistent worker), running `python main.py` daily.
Set the same env vars in Railway, plus `SEEN_DB_PATH` pointed at a mounted volume — without a
volume the dedup database resets every run and the digest repeats itself.

Railway cron is UTC; offset `0 6 * * *` to whatever 6 AM should mean.
