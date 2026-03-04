# Copyright 2025 H2so4 Consulting LLC
# File: App/db.py | Created/Modified: 2026-03-02
"""DB facade for Connections app.

Composes all DB mixins into a single concrete DB class.
"""

from __future__ import annotations

from .db_core import DBCore
from .db_stats_subjects import DBStatsSubjects
from .db_obscurity import DBObscurity
from .db_words_vocab import DBVocab
from .db_words_category_flags import DBCategoryWordFlags
from .db_words_user_flags import DBUserWordFlags
from .db_words_picks import DBPicks
from .db_words_flags import DBWordsFlags

__all__ = ["DB"]


# This DB class composes all mixins used by the application. (Start)
class DB(
    DBCore,
    DBStatsSubjects,
    DBObscurity,
    DBVocab,
    DBWordsFlags,
    DBCategoryWordFlags,
    DBUserWordFlags,
    DBPicks,
):
    """Concrete database class used by the app."""

    # This initializes the DB. (Start)
    def __init__(self):
        super().__init__()
    # end def __init__  # __init__

# end class DB  # DB
