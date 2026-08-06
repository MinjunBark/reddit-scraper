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

_VERDICT_SCHEMA = {
    "type": "object",
    "properties": {
        "post_index": {
            "type": "integer",
            "description": "The index number of the post this verdict is for, as given in the input.",
        },
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
    "required": [
        "post_index", "summary", "matched_pain_points", "recommendation", "signal_strength",
    ],
}

# Batched: the free tier limits requests per minute, not tokens, so scoring many posts in
# one call is dramatically faster than one call per post.
_RESPONSE_SCHEMA = {
    "type": "array",
    "items": _VERDICT_SCHEMA,
}

_PROMPT = """You are triaging Reddit posts to find people who have a problem that Shadowfax AI solves.

Shadowfax is an AI-native analytics platform for business analysts, FP&A managers, and consultants.
It turns messy data into repeatable, auditable analyses without requiring Python. Its founding
argument is that AI copilots bolted onto legacy tools did not remove analyst toil — analysts now
spend hours *auditing* AI output instead of producing it, and under 10% of business analysts have
adopted AI tooling, mostly because they do not trust it.

Pain points to match against:
{pain_points}

These are NOT signals. Posts about them should return an empty match list, even when the poster is
clearly an analyst or clearly frustrated:
{non_signals}

For EACH post, judge whether the poster is genuinely wrestling with one of the pain points. Match
only if they are actually describing that difficulty, not merely mentioning a related word — "I'm a
data analyst" is not about data prep.

Do match when someone describes doing this work manually, repetitively, or painfully, even if they
never ask for a tool. Rebuilding a forecast by hand every month is a match for "forecasting".

Do NOT match someone whose actual question is about their career, even if they mention painful
work along the way. A post that describes tedious dashboard work but asks "should I switch jobs?"
is a career post, not a lead — the person wants a different job, not better software.

signal_strength: "high" = actively looking for a better way right now; "medium" = clear operational
pain but not shopping; "low" = the pain is incidental to their actual question.

Return exactly one verdict object per post, carrying the post_index it corresponds to. Judge every
post independently — do not let one post's verdict influence another's.

{posts}
"""

_POST_TEMPLATE = """
--- POST {index} ---
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


def _evaluate_batch(client, batch):
    """Score a batch of posts in one call. Returns {post_index: verdict}."""
    rendered = "".join(
        _POST_TEMPLATE.format(
            index=i,
            subreddit=post["subreddit"],
            title=post["title"],
            body=(post["selftext"][:_MAX_BODY_CHARS] or "(no body text)"),
        )
        for i, post in enumerate(batch)
    )
    prompt = _PROMPT.format(
        pain_points="\n".join(f"- {p}" for p in config.PAIN_POINTS),
        non_signals="\n".join(f"- {n}" for n in config.NON_SIGNALS),
        posts=rendered,
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
            verdicts = json.loads(response.text)
            # Keyed by index rather than zipped by position: the model can return
            # verdicts out of order or omit one, and silent misalignment would attach
            # the wrong summary to the wrong post.
            return {
                v["post_index"]: v
                for v in verdicts
                if isinstance(v, dict) and isinstance(v.get("post_index"), int)
            }
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
    batches = [
        posts[i : i + config.GEMINI_BATCH_SIZE]
        for i in range(0, total, config.GEMINI_BATCH_SIZE)
    ]
    log.info("Scoring %d posts in %d request(s)", total, len(batches))

    for batch_number, batch in enumerate(batches, start=1):
        try:
            verdicts = _evaluate_batch(client, batch)
        except Exception as error:
            # Skipped, not marked seen — these get another chance on the next run.
            # Truncated: the full trace is noise in a cron log.
            log.error("batch %d/%d failed: %s", batch_number, len(batches), str(error)[:200])
            continue

        for index, post in enumerate(batch):
            verdict = verdicts.get(index)
            if verdict is None:
                # Not marked evaluated, so it is retried tomorrow rather than lost.
                log.warning("No verdict returned for post %s; will retry next run", post["id"])
                continue
            evaluated.append(post)
            if verdict.get("matched_pain_points"):
                matched.append({**post, **verdict})

    log.info("Evaluated %d posts, %d matched a pain point", len(evaluated), len(matched))
    return matched, evaluated
