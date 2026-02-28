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
