# Railway deployment

Railway's **cron schedule and volumes are dashboard-only** — they cannot be set from
`railway.json` or the CLI. `railway.json` in this repo covers only the build and start command.

## Constraints that shape this setup

- Cron runs on **UTC**. There is no timezone setting; offset the expression yourself.
- **One cron schedule per service.** Two different run times require two services.
- A cron service **must exit** when finished. `main.py` does, and `restartPolicyType: NEVER`
  stops Railway treating the exit as a crash and restarting it in a loop.
- Minimum interval between runs is 5 minutes.
- If a run is still going when the next is due, Railway **skips** the new one.

## Steps

1. **New project** → Deploy from GitHub repo → `MinjunBark/reddit-scraper`.

2. **Variables** — add all four:
   ```
   APIFY_TOKEN=...
   GEMINI_API_KEY=...
   DISCORD_WEBHOOK_URL=...
   SEEN_DB_PATH=/data/seen.db
   ```
   `SEEN_DB_PATH` must point inside the volume mount from step 3, or dedup resets every run
   and the same posts are delivered daily.

3. **Volume** — service → Settings → Volumes → New Volume, mount path `/data`.
   Without this the container filesystem is ephemeral and `seen.db` is lost between runs.

4. **Cron** — service → Settings → Cron Schedule → enter the UTC expression.

5. **Verify** — trigger one run manually from the dashboard before trusting the schedule.
   Check the logs for `fetched=… unseen=… evaluated=… matched=…` and confirm the digest
   arrives in Discord.

## Cron reference (America/Los_Angeles, PDT = UTC−7)

| Local time | UTC | Cron expression |
|---|---|---|
| 6:00 AM PDT | 13:00 UTC | `0 13 * * *` |
| 5:20 PM PDT | 00:20 UTC **next day** | `20 0 * * *` |
| 6:30 PM PDT | 01:30 UTC **next day** | `30 1 * * *` |

Evening Pacific times cross midnight UTC, so they fire on the following UTC date. This is the
usual cause of "the cron ran on the wrong day".

**PDT is UTC−7; PST is UTC−8.** These expressions do not self-adjust — when daylight saving
ends, a 6:00 AM PDT schedule becomes 5:00 AM PST until you change it.

## Cost per run

Apify bills $0.02 per run plus $0.004 per result stored. A typical day (~10 posts) is about
$0.06; a full 50-result run is $0.22. Gemini stays inside the free tier at 20 requests/day
because scoring is batched.
