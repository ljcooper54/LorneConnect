# File: App/db_words_flags.py | Created/Modified: 2026-02-26
# Copyright 2025 H2so4 Consulting LLC
"""DB: category vocab + flags + usable-word filtering.

Change:
- recent exclusion is per-user per-category (NOT global).
"""

from __future__ import annotations

import time
from typing import Iterable

from .utils import normalize_token, normalize_category_key


# This DBWordsFlags mixin provides vocabulary storage, filtering, and usage history. (Start)
class DBWordsFlags:
    """Category vocab + flags + filtering."""

    # This returns per-user inappropriate words. (Start)
    def get_user_inappropriate_words(self, user: str) -> list[str]:
        u = normalize_token(user)
        if not u:
            return []
        # end if
        with self.lock:
            cur = self.conn.cursor()
            cur.execute("SELECT word FROM user_word_flags WHERE user=? AND inappropriate=1", (u,))
            return [normalize_token(r[0]) for r in cur.fetchall() if r and r[0]]
        # end with
    # end def get_user_inappropriate_words  # get_user_inappropriate_words

    # This inserts a batch of seeded vocab rows (category_key+word unique). (Start)
    def insert_vocab_batch(self, category: str, items: list[tuple[str, int]]) -> None:
        ck = normalize_category_key(category)
        cd = normalize_token(category)
        if not ck or not cd or not items:
            return
        # end if

        now = time.time()
        with self.lock:
            cur = self.conn.cursor()
            for (word, obscurity) in items:
                w = normalize_token(word)
                if not w:
                    continue
                # end if
                o = int(obscurity)
                o = max(1, min(4, o))
                cur.execute(
                    """
                    INSERT OR IGNORE INTO category_vocab(
                        category_key, category_display, word, obscurity, created_at
                    ) VALUES(?,?,?,?,?)
                    """,
                    (ck, cd, w, o, now),
                )
            # end for
            self.conn.commit()
        # end with
    # end def insert_vocab_batch  # insert_vocab_batch

    # This returns usable words (with obscurity) for a category. (Start)
    def get_usable_words(
        self,
        category: str,
        user: str,
        recent_n: int,
        exclude_words: set[str],
    ) -> list[tuple[str, int]]:
        ck = normalize_category_key(category)
        if not ck:
            return []
        # end if

        user_bad = set(self.get_user_inappropriate_words(user))
        recent = set(self.get_last_n_picks(user, category, n=int(recent_n)))

        with self.lock:
            cur = self.conn.cursor()
            cur.execute(
                """
                SELECT word, obscurity
                FROM category_vocab
                WHERE category_key=?
                  AND wrong_category=0
                """,
                (ck,),
            )
            rows = cur.fetchall()
        # end with

        out: list[tuple[str, int]] = []
        for (w, o) in rows:
            ww = normalize_token(w)
            if not ww:
                continue
            # end if
            if ww in exclude_words:
                continue
            # end if
            if ww in user_bad:
                continue
            # end if
            if ww in recent:
                continue
            # end if
            out.append((ww, int(o)))
        # end for

        return out
    # end def get_usable_words  # get_usable_words

# end class DBWordsFlags  # DBWordsFlags
