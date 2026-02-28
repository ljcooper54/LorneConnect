# File: App/db_words_user_flags.py | Created/Modified: 2026-02-26
# Copyright 2025 H2so4 Consulting LLC
"""Per-user word flags.

Flags:
- inappropriate (excluded for this user)
- too_hard (excluded for this user)

Schema:
- Adds user_word_flags.too_hard if missing.
"""

from __future__ import annotations

import time

from .utils import normalize_token


# This DBUserWordFlags mixin manages user-scoped word flags. (Start)
class DBUserWordFlags:
    """User-scoped word flags."""

    # This returns the set of columns present on a table. (Start)
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

    # This ensures user_word_flags has too_hard column. (Start)
    def _ensure_user_word_flags_cols(self) -> None:
        cols = self._table_columns("user_word_flags")
        if "too_hard" in cols:
            return
        # end if
        try:
            with self.lock:
                cur = self.conn.cursor()
                cur.execute("ALTER TABLE user_word_flags ADD COLUMN too_hard INTEGER NOT NULL DEFAULT 0")
                self.conn.commit()
            # end with
        except Exception:
            pass
        # end try/except
    # end def _ensure_user_word_flags_cols  # _ensure_user_word_flags_cols

    # This reads user-flagged words for a specific column. (Start)
    def _get_user_flagged_words(self, user: str, col: str) -> list[str]:
        u = normalize_token(user)
        if not u:
            return []
        # end if

        self._ensure_user_word_flags_cols()
        cols = self._table_columns("user_word_flags")
        if col not in cols:
            return []
        # end if

        with self.lock:
            cur = self.conn.cursor()
            cur.execute(f"SELECT word FROM user_word_flags WHERE user=? AND {col}=1", (u,))
            return [normalize_token(r[0]) for r in cur.fetchall() if r and r[0]]
        # end with
    # end def _get_user_flagged_words  # _get_user_flagged_words

    # This upserts a per-user flag on a word. (Start)
    def _set_user_word_flag(self, user: str, word: str, col: str, value: int) -> None:
        u = normalize_token(user)
        w = normalize_token(word)
        if not u or not w:
            return
        # end if

        self._ensure_user_word_flags_cols()
        cols = self._table_columns("user_word_flags")
        if col not in cols:
            return
        # end if

        now = time.time()
        with self.lock:
            cur = self.conn.cursor()
            cur.execute("INSERT OR IGNORE INTO user_word_flags(user, word, created_at) VALUES(?,?,?)", (u, w, now))
            cur.execute(f"UPDATE user_word_flags SET {col}=? WHERE user=? AND word=?", (int(value), u, w))
            self.conn.commit()
        # end with
    # end def _set_user_word_flag  # _set_user_word_flag

    # This flags a word as inappropriate for a user. (Start)
    def flag_inappropriate_for_user(self, user: str, word: str) -> None:
        self._set_user_word_flag(user, word, "inappropriate", 1)
    # end def flag_inappropriate_for_user  # flag_inappropriate_for_user

    # This flags a word as too hard for a user. (Start)
    def flag_too_hard_for_user(self, user: str, word: str) -> None:
        self._set_user_word_flag(user, word, "too_hard", 1)
    # end def flag_too_hard_for_user  # flag_too_hard_for_user

    # This returns user-inappropriate words. (Start)
    def get_user_inappropriate_words(self, user: str) -> list[str]:
        return self._get_user_flagged_words(user, "inappropriate")
    # end def get_user_inappropriate_words  # get_user_inappropriate_words

    # This returns user-too-hard words. (Start)
    def get_user_too_hard_words(self, user: str) -> list[str]:
        return self._get_user_flagged_words(user, "too_hard")
    # end def get_user_too_hard_words  # get_user_too_hard_words

# end class DBUserWordFlags  # DBUserWordFlags
