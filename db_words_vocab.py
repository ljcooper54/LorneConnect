# File: App/db_words_vocab.py | Created/Modified: 2026-02-27
# Copyright 2025 H2so4 Consulting LLC
"""Vocabulary insert/list + usable-word query.

Fix:
- Ensures category_vocab has required columns (category_display, created_at, flags)
  even if the table was created earlier by DBCore with fewer columns.

Implements get_usable_words() filtering:
- wrong_category (category)
- too_ambiguous (category, if present)
- inappropriate (user)
- too_hard (user)
- recent picks (PER USER + PER CATEGORY)
- exclude_words set
"""

from __future__ import annotations

import time

from .utils import normalize_token, normalize_category_key


# This DBVocab mixin stores vocab and returns usable candidates. (Start)
class DBVocab:
    """Vocab insert/list + usable selection."""

    # This returns table columns. (Start)
    def _table_columns(self, table: str) -> set[str]:
        try:
            with self.lock:
                cur = self.conn.cursor()
                cur.execute(f"PRAGMA table_info({table})")
                cols = {str(r[1]) for r in cur.fetchall() if r and len(r) > 1}
            # end with
            return cols
        except Exception:
            return set()
        # end try/except
    # end def _table_columns  # _table_columns

    # This ensures category_vocab exists and contains all required columns. (Start)
    def _ensure_category_vocab_schema(self) -> None:
        with self.lock:
            cur = self.conn.cursor()

            # Create table with full schema if it doesn't exist. (Start)
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS category_vocab(
                    category_key TEXT NOT NULL,
                    category_display TEXT NOT NULL,
                    word TEXT NOT NULL,
                    obscurity INTEGER NOT NULL DEFAULT 2,
                    created_at REAL NOT NULL DEFAULT (strftime('%s','now')),
                    wrong_category INTEGER NOT NULL DEFAULT 0,
                    too_ambiguous INTEGER NOT NULL DEFAULT 0,
                    PRIMARY KEY(category_key, word)
                )
                """
            )
            # end create

            # Add missing columns if table existed with fewer fields. (Start)
            cols = self._table_columns("category_vocab")

            if "category_display" not in cols:
                cur.execute("ALTER TABLE category_vocab ADD COLUMN category_display TEXT NOT NULL DEFAULT ''")
            # end if

            if "created_at" not in cols:
                cur.execute("ALTER TABLE category_vocab ADD COLUMN created_at REAL NOT NULL DEFAULT (strftime('%s','now'))")
            # end if

            if "wrong_category" not in cols:
                cur.execute("ALTER TABLE category_vocab ADD COLUMN wrong_category INTEGER NOT NULL DEFAULT 0")
            # end if

            if "too_ambiguous" not in cols:
                cur.execute("ALTER TABLE category_vocab ADD COLUMN too_ambiguous INTEGER NOT NULL DEFAULT 0")
            # end if

            # Helpful indexes. (Start)
            try:
                cur.execute(
                    "CREATE INDEX IF NOT EXISTS ix_category_vocab_key_display ON category_vocab(category_key, category_display)"
                )
                cur.execute(
                    "CREATE INDEX IF NOT EXISTS ix_category_vocab_key_obs ON category_vocab(category_key, obscurity)"
                )
            except Exception:
                pass
            # end try/except
            # end indexes

            self.conn.commit()
        # end with
    # end def _ensure_category_vocab_schema  # _ensure_category_vocab_schema

    # This inserts seeded vocab rows. (Start)
    def insert_vocab_batch(self, category: str, items: list[tuple[str, int]]) -> None:
        self._ensure_category_vocab_schema()

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
                try:
                    o = max(1, min(4, int(obscurity)))
                except Exception:
                    o = 2
                # end try/except

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

    # This lists category words (raw). (Start)
    def list_category_words(self, category: str) -> list[str]:
        self._ensure_category_vocab_schema()

        ck = normalize_category_key(category)
        if not ck:
            return []
        # end if
        with self.lock:
            cur = self.conn.cursor()
            cur.execute("SELECT word FROM category_vocab WHERE category_key=?", (ck,))
            return [normalize_token(r[0]) for r in cur.fetchall() if r and r[0]]
        # end with
    # end def list_category_words  # list_category_words

    # This lists categories with at least min_words usable rows. (Start)
    def list_categories(self, min_words: int = 4) -> list[str]:
        self._ensure_category_vocab_schema()

        cv_cols = self._table_columns("category_vocab")
        where = "WHERE wrong_category=0"
        if "too_ambiguous" in cv_cols:
            where += " AND too_ambiguous=0"
        # end if

        with self.lock:
            cur = self.conn.cursor()
            cur.execute(
                f"""
                SELECT category_display
                FROM category_vocab
                {where}
                GROUP BY category_key, category_display
                HAVING COUNT(*) >= ?
                ORDER BY category_display COLLATE NOCASE ASC
                """,
                (int(min_words),),
            )
            return [normalize_token(r[0]) for r in cur.fetchall() if r and r[0]]
        # end with
    # end def list_categories  # list_categories

    # This returns usable words with obscurity, applying all filters. (Start)
    def get_usable_words(self, category: str, user: str, recent_n: int, exclude_words: set[str]) -> list[tuple[str, int]]:
        self._ensure_category_vocab_schema()

        ck = normalize_category_key(category)
        if not ck:
            return []
        # end if

        # Per-user bans. (Start)
        user_bad = set(self.get_user_inappropriate_words(user))
        user_hard = set(self.get_user_too_hard_words(user))
        # end per-user bans

        # Recent picks for this user + category. (Start)
        recent = set()
        if recent_n and recent_n > 0:
            try:
                recent = set(self.get_last_n_picks(user=user, category=category, n=int(recent_n)))
            except Exception:
                recent = set()
            # end try/except
        # end if
        # end recent

        cv_cols = self._table_columns("category_vocab")
        where = ["category_key=?"]
        params = [ck]

        where.append("wrong_category=0")
        if "too_ambiguous" in cv_cols:
            where.append("too_ambiguous=0")
        # end if

        with self.lock:
            cur = self.conn.cursor()
            cur.execute(
                f"""
                SELECT word, obscurity
                FROM category_vocab
                WHERE {' AND '.join(where)}
                """,
                tuple(params),
            )
            rows = cur.fetchall()
        # end with

        out: list[tuple[str, int]] = []
        ex = {normalize_token(w) for w in (exclude_words or set())}
        rec = {normalize_token(w) for w in recent}
        bad = {normalize_token(w) for w in user_bad}
        hard = {normalize_token(w) for w in user_hard}

        for w, o in rows:
            ww = normalize_token(w)
            if not ww:
                continue
            # end if
            if ww in ex or ww in rec or ww in bad or ww in hard:
                continue
            # end if
            try:
                oo = int(o)
            except Exception:
                oo = 2
            # end try/except
            out.append((ww, oo))
        # end for

        return out
    # end def get_usable_words  # get_usable_words

# end class DBVocab  # DBVocab
