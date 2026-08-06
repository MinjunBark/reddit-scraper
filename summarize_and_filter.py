"""Gemini pass: summarize each post and score it against config.PAIN_POINTS.

One call per post with a strict JSON response schema. Per-post isolation is deliberate — a
malformed response loses that post, not the whole digest.
"""

import json
import logging
import os
import re
import time

from google import genai
from google.genai import types

import config

log = logging.getLogger(__name__)

_MIN_INTERVAL_S = 60.0 / config.GEMINI_RPM
_last_call_at = 0.0


def _throttle():
    """Space calls out to stay under the per-minute quota."""
    global _last_call_at
    wait = _MIN_INTERVAL_S - (time.monotonic() - _last_call_at)
    if wait > 0:
        time.sleep(wait)
    _last_call_at = time.monotonic()


def _retry_delay_from(error, attempt):
    """Honour the retryDelay Gemini returns on a 429; otherwise back off exponentially."""
    match = re.search(r"'retryDelay': '(\d+)s'", str(error))
    if match:
        return int(match.group(1)) + 1
    return min(60, 2 ** attempt)

_RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "summary": {
            "type": "string",
            "description": "1-2 sentence summary of what the poster is actually dealing with.",
        },
        "matched_pain_points": {
            "type": "array",
            "description": "Pain points this post genuinely resonates with. Empty if none.",
            "items": {"type": "string", "enum": config.PAIN_POINTS},
        },
        "recommendation": {
            "type": "string",
            "description": "One line: why this post is worth a reply. Empty if no pain points matched.",
        },
        "signal_strength": {
            "type": "string",
            "enum": ["high", "medium", "low"],
        },
    },
    "required": ["summary", "matched_pain_points", "recommendation", "signal_strength"],
}

_PROMPT = """You are triaging Reddit posts to find people who have a problem that Shadowfax AI solves.

Shadowfax's pain points:
{pain_points}

Judge whether this post shows someone genuinely wrestling with one of those problems. Be strict:
match a pain point only if the poster is actually describing that difficulty, not merely mentioning
a related word. A post that says "I'm a data analyst" is not about data prep. If nothing genuinely
matches, return an empty matched_pain_points list — that is a normal and common outcome.

signal_strength reflects how strong the buying intent is: "high" means they are actively looking for
a better way to do this right now, "low" means the pain is incidental to their actual question.

Subreddit: r/{subreddit}
Title: {title}
Body:
{body}
"""

_MAX_BODY_CHARS = 4000


def _client():
    if not os.environ.get("GEMINI_API_KEY"):
        raise RuntimeError("Missing required env var: GEMINI_API_KEY")
    return genai.Client(api_key=os.environ["GEMINI_API_KEY"])


def _evaluate_one(client, post):
    prompt = _PROMPT.format(
        pain_points="\n".join(f"- {p}" for p in config.PAIN_POINTS),
        subreddit=post["subreddit"],
        title=post["title"],
        body=(post["selftext"][:_MAX_BODY_CHARS] or "(no body text)"),
    )
    last_error = None
    for attempt in range(config.GEMINI_MAX_RETRIES):
        _throttle()
        try:
            response = client.models.generate_content(
                model=config.GEMINI_MODEL,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=_RESPONSE_SCHEMA,
                    # Without this the same post scores differently between runs, which
                    # moves posts in and out of the "most relevant" bold set at random.
                    temperature=0,
                ),
            )
            return json.loads(response.text)
        except Exception as error:
            last_error = error
            if "RESOURCE_EXHAUSTED" not in str(error) and "429" not in str(error):
                raise
            delay = _retry_delay_from(error, attempt)
            log.warning(
                "Gemini rate limit hit (attempt %d/%d), waiting %ds",
                attempt + 1, config.GEMINI_MAX_RETRIES, delay,
            )
            time.sleep(delay)

    raise RuntimeError(f"Gemini rate limit not cleared after {config.GEMINI_MAX_RETRIES} attempts") from last_error


def summarize_and_filter(posts):
    """Evaluate every post; return (matched, evaluated).

    `matched` are posts with at least one pain point, each enriched with the Gemini fields.
    `evaluated` is every post we got a usable verdict on, matched or not — callers record all of
    them as seen so non-matches aren't re-scored (and re-billed) tomorrow.
    """
    if not posts:
        return [], []

    client = _client()
    matched, evaluated = [], []

    total = len(posts)
    log.info(
        "Scoring %d posts at %d/min — expect roughly %.0f min",
        total, config.GEMINI_RPM, total / config.GEMINI_RPM,
    )

    for index, post in enumerate(posts, start=1):
        try:
            verdict = _evaluate_one(client, post)
        except Exception as error:
            # Skipped, not marked seen — it gets another chance on the next run.
            # Truncated: the full trace is noise in a cron log.
            log.error("[%d/%d] failed for post %s: %s", index, total, post["id"], str(error)[:200])
            continue

        evaluated.append(post)
        if verdict.get("matched_pain_points"):
            matched.append({**post, **verdict})

    log.info("Evaluated %d posts, %d matched a pain point", len(evaluated), len(matched))
    return matched, evaluated
