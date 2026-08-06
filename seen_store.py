"""Tracks which Reddit posts have already been sent, so a post appears in exactly one digest.

Not in the original spec: without this, pulling the 25 newest daily from two low-volume
subreddits makes consecutive digests near-duplicates.

Callers must only mark_seen() AFTER a digest is successfully delivered — otherwise a crash
mid-run silently burns that day's posts.
"""

import logging
import sqlite3
import time
from contextlib import contextmanager

import config

log = logging.getLogger(__name__)


@contextmanager
def _conn():
    conn = sqlite3.connect(config.SEEN_DB_PATH)
    try:
        conn.execute(
            "CREATE TABLE IF NOT EXISTS seen_posts ("
            "  post_id TEXT PRIMARY KEY,"
            "  first_seen_utc REAL NOT NULL"
            ")"
        )
        yield conn
        conn.commit()
    finally:
        conn.close()


def filter_unseen(posts):
    """Return only the posts whose IDs aren't already recorded."""
    if not posts:
        return []
    with _conn() as conn:
        known = {
            row[0]
            for row in conn.execute("SELECT post_id FROM seen_posts").fetchall()
        }
    return [p for p in posts if p["id"] not in known]


def mark_seen(posts):
    """Record these post IDs so they never appear in a future digest."""
    if not posts:
        return
    now = time.time()
    with _conn() as conn:
        conn.executemany(
            "INSERT OR IGNORE INTO seen_posts (post_id, first_seen_utc) VALUES (?, ?)",
            [(p["id"], now) for p in posts],
        )
    log.info("Marked %d posts as seen", len(posts))
