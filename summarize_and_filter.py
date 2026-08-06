"""Gemini pass: summarize each post and score it against config.PAIN_POINTS.

One call per post with a strict JSON response schema. Per-post isolation is deliberate — a
malformed response loses that post, not the whole digest.
"""

import json
import logging
import os

from google import genai
from google.genai import types

import config

log = logging.getLogger(__name__)

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
    response = client.models.generate_content(
        model=config.GEMINI_MODEL,
        contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=_RESPONSE_SCHEMA,
        ),
    )
    return json.loads(response.text)


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

    for post in posts:
        try:
            verdict = _evaluate_one(client, post)
        except Exception:
            # Skipped, not marked seen — it gets another chance on the next run.
            log.exception("Gemini evaluation failed for post %s; skipping", post["id"])
            continue

        evaluated.append(post)
        if verdict.get("matched_pain_points"):
            matched.append({**post, **verdict})

    log.info("Evaluated %d posts, %d matched a pain point", len(evaluated), len(matched))
    return matched, evaluated
