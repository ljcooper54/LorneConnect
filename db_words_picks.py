# File: App/db_words_picks.py | Created/Modified: 2026-02-27
# Copyright 2025 H2so4 Consulting LLC
"""Per-user per-category pick history (anti-repeat)."""

from __future__ import annotations

import time
from typing import Iterable

from .utils import normalize_token, normalize_category_key


# This DBPicks mixin tracks last-N picks per user+category. (Start)
class DBPicks:
    """Per-user pick history."""

    # This ensures the word_picks table exists (versioned core creates it, but keep safe). (Start)
    def _ensure_word_picks_schema(self) -> None:
        with self.lock:
            cur = self.conn.cursor()
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS word_picks(
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user TEXT NOT NULL,
                    category_key TEXT NOT NULL,
                    word TEXT NOT NULL,
                    picked_at REAL NOT NULL DEFAULT (strftime('%s','now'))
                )
                """
            )
            cur.execute(
                "CREATE INDEX IF NOT EXISTS ix_word_picks_user_cat_time ON word_picks(user, category_key, picked_at DESC)"
            )
            self.conn.commit()
        # end with
    # end def _ensure_word_picks_schema  # _ensure_word_picks_schema

    # This returns last N picked words for a user+category. (Start)
    def get_last_n_picks(self, user: str, category: str, n: int = 16) -> list[str]:
        self._ensure_word_picks_schema()

        u = normalize_token(user)
        ck = normalize_category_key(category)
        if not u or not ck:
            return []
        # end if

        try:
            lim = int(n)
        except Exception:
            lim = 16
        # end try/except
        lim = max(0, min(500, lim))

        with self.lock:
            cur = self.conn.cursor()
            cur.execute(
                """
                SELECT word
                FROM word_picks
                WHERE user=? AND category_key=?
                ORDER BY picked_at DESC, id DESC
                LIMIT ?
                """,
                (u, ck, lim),
            )
            return [normalize_token(r[0]) for r in cur.fetchall() if r and r[0]]
        # end with
    # end def get_last_n_picks  # get_last_n_picks

    def get_recent_words(self, user: str, limit: int = 10):
        rows = self.conn.execute("""
            SELECT word
            FROM word_picks
            WHERE user = ?
            ORDER BY picked_at DESC
            LIMIT ?
        """, (user, limit)).fetchall()
        return [r["word"] for r in rows]

    # This records picked words for a user+category. (Start)
    def record_picks(self, user: str, category: str, words: Iterable[str]) -> None:
        self._ensure_word_picks_schema()

        u = normalize_token(user)
        ck = normalize_category_key(category)
        if not u or not ck:
            return
        # end if

        now = time.time()
        with self.lock:
            cur = self.conn.cursor()
            for w in words:
                ww = normalize_token(w)
                if not ww:
                    continue
                # end if
                cur.execute(
                    "INSERT INTO word_picks(user, category_key, word, picked_at) VALUES(?,?,?,?)",
                    (u, ck, ww, now),
                )
            # end for
            self.conn.commit()
        # end with
    # end def record_picks  # record_picks

# end class DBPicks  # DBPicks
