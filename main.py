"""Entry point: fetch -> dedup -> summarize/filter -> deliver -> record.

Run `python main.py --dry-run --limit 3` first to check Reddit auth and Gemini output without
spending a Discord post or writing state.
"""

import argparse
import logging
import os
import sys

from dotenv import load_dotenv

import discord_delivery
import reddit_client
import seen_store
import summarize_and_filter


def parse_args():
    parser = argparse.ArgumentParser(description="Shadowfax Reddit intent-signal pipeline")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the digest instead of posting it. Does not write seen-state.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Override posts-per-subreddit, for cheap iteration.",
    )
    return parser.parse_args()


def check_env(dry_run):
    """Fail before doing any work, rather than after the Gemini spend.

    Without this, a missing webhook URL only surfaces at the delivery step — by which point
    every post has already been fetched and scored.
    """
    required = ["REDDIT_CLIENT_ID", "REDDIT_CLIENT_SECRET", "REDDIT_USER_AGENT", "GEMINI_API_KEY"]
    if not dry_run:
        required.append("DISCORD_WEBHOOK_URL")
    missing = [name for name in required if not os.environ.get(name)]
    if missing:
        raise RuntimeError(
            f"Missing required env vars: {', '.join(missing)}. "
            "Copy .env.example to .env and fill it in — see the README for where each comes from."
        )


def print_digest(posts):
    if not posts:
        print("\n(no matching posts — digest would say 'no matching posts today')")
        return
    for post in discord_delivery.sort_for_digest(posts):
        marker = "🔥 " if discord_delivery.is_most_relevant(post) else "   "
        print(f"\n{marker}{post['title']}")
        print(f"   r/{post['subreddit']} · {post['permalink']}")
        print(f"   {post.get('summary', '')}")
        print(f"   Matched: {', '.join(post.get('matched_pain_points', []))}"
              f" (signal: {post.get('signal_strength')})")
        print(f"   Why reply: {post.get('recommendation', '')}")


def main():
    args = parse_args()
    load_dotenv()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    log = logging.getLogger("main")
    check_env(args.dry_run)

    posts = reddit_client.fetch_recent_posts(limit=args.limit)
    unseen = seen_store.filter_unseen(posts)
    matched, evaluated = summarize_and_filter.summarize_and_filter(unseen)

    log.info(
        "fetched=%d unseen=%d evaluated=%d matched=%d",
        len(posts), len(unseen), len(evaluated), len(matched),
    )

    if args.dry_run:
        print_digest(matched)
        log.info("Dry run — nothing posted, no state written.")
        return 0

    # Delivery first, state second: a crash here must not burn today's posts.
    discord_delivery.deliver(matched)
    # Record everything we got a verdict on, not just the matches — otherwise non-matching
    # posts get re-scored (and re-billed) on every future run.
    seen_store.mark_seen(evaluated)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        logging.exception("Pipeline run failed")
        sys.exit(1)  # non-zero so Railway marks the scheduled run as failed
