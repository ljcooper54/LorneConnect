# File: App/db_words_category_flags.py | Created/Modified: 2026-02-26
# Copyright 2025 H2so4 Consulting LLC
"""Category-scoped word flags.

Flags:
- wrong_category (excluded for all users of that category)
- too_ambiguous (excluded for all users of that category)

Schema:
- Adds category_vocab.too_ambiguous if missing.
"""

from __future__ import annotations

from .utils import normalize_token, normalize_category_key


# This DBCategoryWordFlags mixin manages category-scoped word flags. (Start)
class DBCategoryWordFlags:
    """Category-scoped word flags."""

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

    # This ensures category_vocab has too_ambiguous column. (Start)
    def _ensure_category_vocab_cols(self) -> None:
        cols = self._table_columns("category_vocab")
        if "too_ambiguous" in cols:
            return
        # end if
        try:
            with self.lock:
                cur = self.conn.cursor()
                cur.execute("ALTER TABLE category_vocab ADD COLUMN too_ambiguous INTEGER NOT NULL DEFAULT 0")
                self.conn.commit()
            # end with
        except Exception:
            pass
        # end try/except
    # end def _ensure_category_vocab_cols  # _ensure_category_vocab_cols

    # This marks a word as wrong category for a category. (Start)
    def flag_wrong_category(self, category: str, word: str) -> None:
        ck = normalize_category_key(category)
        w = normalize_token(word)
        if not ck or not w:
            return
        # end if
        with self.lock:
            cur = self.conn.cursor()
            cur.execute(
                """
                UPDATE category_vocab
                SET wrong_category=1
                WHERE category_key=? AND word=?
                """,
                (ck, w),
            )
            self.conn.commit()
        # end with
    # end def flag_wrong_category  # flag_wrong_category

    # This marks a word as too ambiguous for a category. (Start)
    def flag_too_ambiguous(self, category: str, word: str) -> None:
        ck = normalize_category_key(category)
        w = normalize_token(word)
        if not ck or not w:
            return
        # end if

        self._ensure_category_vocab_cols()
        cols = self._table_columns("category_vocab")
        if "too_ambiguous" not in cols:
            return
        # end if

        with self.lock:
            cur = self.conn.cursor()
            cur.execute(
                """
                UPDATE category_vocab
                SET too_ambiguous=1
                WHERE category_key=? AND word=?
                """,
                (ck, w),
            )
            self.conn.commit()
        # end with
    # end def flag_too_ambiguous  # flag_too_ambiguous

# end class DBCategoryWordFlags  # DBCategoryWordFlags
