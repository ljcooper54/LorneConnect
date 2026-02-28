# File: App/db_user_word_flags.py | Created/Modified: 2026-02-26
# Copyright 2025 H2so4 Consulting LLC
"""Per-user word flags.

Implements:
- get_user_inappropriate_words()
- flag_inappropriate_for_user()
- get_user_too_hard_words()
- flag_too_hard_for_user()

These support:
- user-specific exclusion ("Inappropriate" and "Too Hard")
- filtering in DBVocab.get_usable_words()
"""

from __future__ import annotations

from .utils import normalize_token


# This DBUserWordFlags mixin manages per-user flags for words. (Start)
class DBUserWordFlags:
    """Per-user word flags (inappropriate, too_hard)."""

    # This ensures the user_word_flags table exists with required columns. (Start)
    def _ensure_user_word_flags_schema(self) -> None:
        with self.lock:
            cur = self.conn.cursor()
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS user_word_flags(
                    user TEXT NOT NULL,
                    word TEXT NOT NULL,
                    inappropriate INTEGER NOT NULL DEFAULT 0,
                    too_hard INTEGER NOT NULL DEFAULT 0,
                    PRIMARY KEY(user, word)
                )
                """
            )
            self.conn.commit()
        # end with
    # end def _ensure_user_word_flags_schema  # _ensure_user_word_flags_schema

    # This returns per-user inappropriate words. (Start)
    def get_user_inappropriate_words(self, user: str) -> list[str]:
        self._ensure_user_word_flags_schema()
        u = normalize_token(user)
        if not u:
            return []
        # end if

        with self.lock:
            cur = self.conn.cursor()
            cur.execute(
                "SELECT word FROM user_word_flags WHERE user=? AND inappropriate=1",
                (u,),
            )
            return [normalize_token(r[0]) for r in cur.fetchall() if r and r[0]]
        # end with
    # end def get_user_inappropriate_words  # get_user_inappropriate_words

    # This flags a word as inappropriate for a user. (Start)
    def flag_inappropriate_for_user(self, user: str, word: str) -> None:
        self._ensure_user_word_flags_schema()
        u = normalize_token(user)
        w = normalize_token(word)
        if not u or not w:
            return
        # end if

        with self.lock:
            cur = self.conn.cursor()
            cur.execute(
                """
                INSERT INTO user_word_flags(user, word, inappropriate, too_hard)
                VALUES(?,?,1,0)
                ON CONFLICT(user, word) DO UPDATE SET inappropriate=1
                """,
                (u, w),
            )
            self.conn.commit()
        # end with
    # end def flag_inappropriate_for_user  # flag_inappropriate_for_user

    # This returns per-user "too hard" words. (Start)
    def get_user_too_hard_words(self, user: str) -> list[str]:
        self._ensure_user_word_flags_schema()
        u = normalize_token(user)
        if not u:
            return []
        # end if

        with self.lock:
            cur = self.conn.cursor()
            cur.execute(
                "SELECT word FROM user_word_flags WHERE user=? AND too_hard=1",
                (u,),
            )
            return [normalize_token(r[0]) for r in cur.fetchall() if r and r[0]]
        # end with
    # end def get_user_too_hard_words  # get_user_too_hard_words

    # This flags a word as too hard for a user. (Start)
    def flag_too_hard_for_user(self, user: str, word: str) -> None:
        self._ensure_user_word_flags_schema()
        u = normalize_token(user)
        w = normalize_token(word)
        if not u or not w:
            return
        # end if

        with self.lock:
            cur = self.conn.cursor()
            cur.execute(
                """
                INSERT INTO user_word_flags(user, word, inappropriate, too_hard)
                VALUES(?,?,0,1)
                ON CONFLICT(user, word) DO UPDATE SET too_hard=1
                """,
                (u, w),
            )
            self.conn.commit()
        # end with
    # end def flag_too_hard_for_user  # flag_too_hard_for_user

# end class DBUserWordFlags  # DBUserWordFlags
