# File: App/db.py | Created/Modified: 2026-02-27
# Copyright 2025 H2so4 Consulting LLC
"""DB facade for Connections app.

Composes all DB mixins into a single concrete DB class.
All schema upgrades are handled in db_core via PRAGMA user_version.
"""

from __future__ import annotations

from .db_core import DBCore
from .db_stats_subjects import DBStatsSubjects
from .db_obscurity import DBObscurity
from .db_words_vocab import DBVocab
from .db_words_category_flags import DBCategoryWordFlags
from .db_words_user_flags import DBUserWordFlags
from .db_words_picks import DBPicks


__all__ = ["DB"]


# This DB class composes all mixins used by the application. (Start)
class DB(
    DBCore,
    DBStatsSubjects,
    DBObscurity,
    DBVocab,
    DBCategoryWordFlags,
    DBUserWordFlags,
    DBPicks,  # <-- REQUIRED for get_last_n_picks / record_picks
):
    """Concrete database class used by the app."""

    # This initializes the DB. Schema versioning handled by DBCore. (Start)
    def __init__(self):
        super().__init__()
    # end def __init__  # __init__

# end class DB  # DB

    # This decrements effective obscurity for a user-word pair. (Start)
    def decrement_obscurity_for_user(self, user: str, word: str) -> None:
        self.conn.execute(
            """
            INSERT INTO user_word_flags(user, word, obscurity_adjust)
            VALUES (?, ?, -1)
            ON CONFLICT(user, word)
            DO UPDATE SET obscurity_adjust =
                user_word_flags.obscurity_adjust - 1
            """,
            (user, word),
        )
        self.conn.commit()
    # end def decrement_obscurity_for_user

    # This returns obscurity adjustment for a user-word pair. (Start)
    def get_user_obscurity_adjust(self, user: str, word: str) -> int:
        row = self.conn.execute(
            "SELECT obscurity_adjust FROM user_word_flags WHERE user=? AND word=?",
            (user, word),
        ).fetchone()
        return int(row[0]) if row else 0
    # end def get_user_obscurity_adjust

