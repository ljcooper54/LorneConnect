# File: App/db_user_word_flags.py | Created/Modified: 2026-03-03
# Copyright 2025 H2so4 Consulting LLC
"""Per-user word flags and per-user obscurity transitions.

Implements:
- get_user_inappropriate_words()
- flag_inappropriate_for_user()
- get_user_obscurity_adjust()
- transition_word_obscurity()

Design:
- "Inappropriate" is a per-user ban.
- Obscurity adjustment is a signed per-user transition (obscurity_delta).
  - Too Hard  => +1 transition (harder => treated as more obscure)
  - Too Easy  => -1 transition (easier => treated as less obscure, not below 1)
- We keep legacy column too_hard for backwards compatibility, but generation should
  rely on obscurity_delta, not on too_hard as a ban.

Schema (auto-migrated if older DB):
user_word_flags(
  user TEXT,
  word TEXT,
  inappropriate INTEGER,
  too_hard INTEGER,         -- legacy
  obscurity_delta INTEGER,  -- signed adjustment [-3..+3]
  PRIMARY KEY(user, word)
)
"""

from __future__ import annotations

from .utils import normalize_token


# This DBUserWordFlags mixin manages per-user word bans + obscurity deltas. (Start)
class DBUserWordFlags:
    """Per-user word bans and per-user obscurity delta."""

    # This ensures the user_word_flags table and expected columns exist. (Start)
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
                    obscurity_delta INTEGER NOT NULL DEFAULT 0,
                    PRIMARY KEY(user, word)
                )
                """
            )

            # Add missing columns if table predates them. (Start)
            try:
                cur.execute("PRAGMA table_info(user_word_flags)")
                cols = {str(r[1]) for r in (cur.fetchall() or []) if r and len(r) > 1}
            except Exception:
                cols = set()
            # end try/except

            if "too_hard" not in cols:
                try:
                    cur.execute("ALTER TABLE user_word_flags ADD COLUMN too_hard INTEGER NOT NULL DEFAULT 0")
                except Exception:
                    pass
                # end try/except
            # end if

            if "obscurity_delta" not in cols:
                try:
                    cur.execute("ALTER TABLE user_word_flags ADD COLUMN obscurity_delta INTEGER NOT NULL DEFAULT 0")
                except Exception:
                    pass
                # end try/except
            # end if

            self.conn.commit()
        # end with
    # end def _ensure_user_word_flags_schema  # _ensure_user_word_flags_schema

    # This returns per-user inappropriate words (normalized). (Start)
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

    # This flags a word as inappropriate for the given user. (Start)
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
                INSERT INTO user_word_flags(user, word, inappropriate, too_hard, obscurity_delta)
                VALUES(?,?,1,0,0)
                ON CONFLICT(user, word) DO UPDATE SET inappropriate=1
                """,
                (u, w),
            )
            self.conn.commit()
        # end with
    # end def flag_inappropriate_for_user  # flag_inappropriate_for_user

    # This returns the signed obscurity adjustment for (user, word). (Start)
    def get_user_obscurity_adjust(self, user: str, word: str) -> int:
        """Return signed obscurity delta in [-3..+3]."""
        self._ensure_user_word_flags_schema()
        u = normalize_token(user)
        w = normalize_token(word)
        if not u or not w:
            return 0
        # end if

        with self.lock:
            cur = self.conn.cursor()
            cur.execute(
                "SELECT obscurity_delta FROM user_word_flags WHERE user=? AND word=?",
                (u, w),
            )
            row = cur.fetchone()
        # end with

        try:
            v = int(row[0]) if row and row[0] is not None else 0
        except Exception:
            v = 0
        # end try/except

        if v < -3:
            return -3
        if v > 3:
            return 3
        return v
    # end def get_user_obscurity_adjust  # get_user_obscurity_adjust

    # This applies an obscurity transition step for (user, word). (Start)
    def transition_word_obscurity(self, user: str, word: str, step: int) -> int:
        """Increment obscurity_delta by step, clamp to [-3..+3], return new delta."""
        self._ensure_user_word_flags_schema()
        u = normalize_token(user)
        w = normalize_token(word)
        if not u or not w:
            return 0
        # end if

        try:
            s = int(step)
        except Exception:
            s = 0
        # end try/except

        if s == 0:
            return self.get_user_obscurity_adjust(u, w)
        # end if

        with self.lock:
            cur = self.conn.cursor()
            cur.execute(
                "SELECT obscurity_delta FROM user_word_flags WHERE user=? AND word=?",
                (u, w),
            )
            row = cur.fetchone()

            try:
                cur_delta = int(row[0]) if row and row[0] is not None else 0
            except Exception:
                cur_delta = 0
            # end try/except

            new_delta = cur_delta + s
            if new_delta < -3:
                new_delta = -3
            if new_delta > 3:
                new_delta = 3
            # end clamp

            # Preserve legacy too_hard column for compatibility; do not treat as ban. (Start)
            legacy_too_hard = 1 if new_delta > 0 else 0
            # end legacy calc

            cur.execute(
                """
                INSERT INTO user_word_flags(user, word, inappropriate, too_hard, obscurity_delta)
                VALUES(?,?,0,?,?)
                ON CONFLICT(user, word) DO UPDATE SET obscurity_delta=?, too_hard=?
                """,
                (u, w, legacy_too_hard, new_delta, new_delta, legacy_too_hard),
            )

            self.conn.commit()
        # end with

        return new_delta
    # end def transition_word_obscurity  # transition_word_obscurity

# end class DBUserWordFlags  # DBUserWordFlags
