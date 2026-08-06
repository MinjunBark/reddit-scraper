"""Formats the daily digest and posts it to the Discord webhook."""

import logging
import os
import time

import requests

log = logging.getLogger(__name__)

MAX_EMBEDS_PER_MESSAGE = 10     # Discord's hard limit; exceeding it 400s
MAX_DESCRIPTION_CHARS = 4096
_TIMEOUT = 30


def is_most_relevant(post):
    """Spec section 6.4: bold the ones judged most relevant.

    Discord embed titles don't render markdown bold, so these get an emoji marker and are
    sorted to the top instead.
    """
    return post.get("signal_strength") == "high" or len(post.get("matched_pain_points", [])) >= 2


def sort_for_digest(posts):
    """Most relevant first, then strongest signal, then newest."""
    strength_rank = {"high": 0, "medium": 1, "low": 2}
    return sorted(
        posts,
        key=lambda p: (
            not is_most_relevant(p),
            strength_rank.get(p.get("signal_strength"), 3),
            -p["created_utc"],
        ),
    )


def _embed(post):
    pain_points = ", ".join(post.get("matched_pain_points", []))
    description = (
        f"{post.get('summary', '')}\n\n"
        f"**Matched:** {pain_points}\n"
        f"**Why reply:** {post.get('recommendation', '')}"
    )
    title = post["title"]
    if is_most_relevant(post):
        title = f"🔥 {title}"

    return {
        "title": title[:256],
        "url": post["permalink"],
        "description": description[:MAX_DESCRIPTION_CHARS],
        "footer": {"text": f"r/{post['subreddit']} · u/{post['author']} · {post['score']} points"},
    }


def build_digest(posts):
    """Return a list of webhook payloads (chunked to Discord's 10-embed limit)."""
    if not posts:
        return [{"content": "**Reddit intent digest** — no matching posts today."}]

    ordered = sort_for_digest(posts)
    embeds = [_embed(p) for p in ordered]
    payloads = []

    for i in range(0, len(embeds), MAX_EMBEDS_PER_MESSAGE):
        chunk = embeds[i : i + MAX_EMBEDS_PER_MESSAGE]
        payload = {"embeds": chunk}
        if i == 0:
            payload["content"] = (
                f"**Reddit intent digest** — {len(ordered)} post"
                f"{'s' if len(ordered) != 1 else ''} worth a look. 🔥 = highest signal."
            )
        payloads.append(payload)

    return payloads


def deliver(posts):
    """POST the digest. Raises on any non-2xx — a failed delivery must fail the run."""
    webhook_url = os.environ.get("DISCORD_WEBHOOK_URL")
    if not webhook_url:
        raise RuntimeError("Missing required env var: DISCORD_WEBHOOK_URL")

    payloads = build_digest(posts)
    for index, payload in enumerate(payloads):
        if index > 0:
            time.sleep(1)  # stay clear of the webhook rate limit
        response = requests.post(webhook_url, json=payload, timeout=_TIMEOUT)
        if not response.ok:
            raise RuntimeError(
                f"Discord webhook returned {response.status_code}: {response.text[:500]}"
            )

    log.info("Delivered digest in %d message(s)", len(payloads))
