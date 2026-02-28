# File: App/db_obscurity.py | Created/Modified: 2026-02-27
# Copyright 2025 H2so4 Consulting LLC
"""DB: obscurity tracking.

Provides:
- _ensure_obscurity_schema()
- insert_obscurity_record()
- get_category_obscurity_counts() for debug export
- get_recent_category_obscurity() for diagnostics

Schema uses category_key (normalized).
"""

from __future__ import annotations

import json
from typing import Any, List, Tuple

from .utils import normalize_category_key, normalize_token


# This DBObscurity mixin provides obscurity snapshot inserts + queries. (Start)
class DBObscurity:
    """Obscurity snapshot API."""

    # This ensures the category_obscurity schema exists. (Start)
    def _ensure_obscurity_schema(self) -> None:
        with self.lock:
            cur = self.conn.cursor()
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS category_obscurity(
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    category_key TEXT NOT NULL,
                    color TEXT NOT NULL,
                    obscurity INTEGER NOT NULL,
                    words_json TEXT NOT NULL,
                    created_at REAL NOT NULL DEFAULT (strftime('%s','now'))
                )
                """
            )
            cur.execute(
                """
                CREATE INDEX IF NOT EXISTS ix_category_obscurity_key_time
                ON category_obscurity(category_key, created_at)
                """
            )
            self.conn.commit()
        # end with
    # end def _ensure_obscurity_schema  # _ensure_obscurity_schema

    # This coerces an obscurity value into a safe int in 1..5 range. (Start)
    def _coerce_obscurity(self, value: Any) -> int:
        if isinstance(value, (list, tuple)):
            value = value[0] if value else 2
        # end if
        try:
            o = int(value)
        except Exception:
            o = 2
        # end try/except
        return max(1, min(5, o))
    # end def _coerce_obscurity  # _coerce_obscurity

    # This inserts an obscurity record. (Start)
    def insert_obscurity_record(self, category: str, color: str, obscurity: Any, words: list[str]) -> None:
        self._ensure_obscurity_schema()

        ck = normalize_category_key(category)
        if not ck:
            return
        # end if

        c = normalize_token(color).lower() or "yellow"
        o = self._coerce_obscurity(obscurity)

        cleaned_words = []
        for w in (words or []):
            nw = normalize_token(w)
            if nw:
                cleaned_words.append(nw)
            # end if
        # end for

        payload = json.dumps(cleaned_words)

        with self.lock:
            cur = self.conn.cursor()
            cur.execute(
                """
                INSERT INTO category_obscurity(category_key, color, obscurity, words_json)
                VALUES(?,?,?,?)
                """,
                (ck, c, o, payload),
            )
            self.conn.commit()
        # end with
    # end def insert_obscurity_record  # insert_obscurity_record

    # This returns obscurity record counts grouped by category and obscurity. (Start)
    def get_category_obscurity_counts(self, max_obscurity: int = 4) -> List[Tuple[Any, ...]]:
        """
        Returns rows suitable for debug export.

        Row shape:
            (category_key, obscurity, count)
        """
        self._ensure_obscurity_schema()

        try:
            m = int(max_obscurity)
        except Exception:
            m = 4
        # end try/except
        m = max(1, min(10, m))

        with self.lock:
            cur = self.conn.cursor()
            cur.execute(
                """
                SELECT category_key, obscurity, COUNT(*) AS n
                FROM category_obscurity
                WHERE obscurity <= ?
                GROUP BY category_key, obscurity
                ORDER BY category_key ASC, obscurity ASC
                """,
                (m,),
            )
            return list(cur.fetchall())
        # end with
    # end def get_category_obscurity_counts  # get_category_obscurity_counts

    # This returns recent obscurity records for a single category (diagnostic). (Start)
    def get_recent_category_obscurity(self, category: str, limit: int = 25) -> List[Tuple[Any, ...]]:
        """
        Row shape:
            (created_at, category_key, color, obscurity, words_json)
        """
        self._ensure_obscurity_schema()

        ck = normalize_category_key(category)
        if not ck:
            return []
        # end if

        try:
            lim = int(limit)
        except Exception:
            lim = 25
        # end try/except
        lim = max(1, min(500, lim))

        with self.lock:
            cur = self.conn.cursor()
            cur.execute(
                """
                SELECT created_at, category_key, color, obscurity, words_json
                FROM category_obscurity
                WHERE category_key = ?
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (ck, lim),
            )
            return list(cur.fetchall())
        # end with
    # end def get_recent_category_obscurity  # get_recent_category_obscurity

# end class DBObscurity  # DBObscurity
