# File: App/db_maintenance.py | Created/Modified: 2026-02-27
# Copyright 2025 H2so4 Consulting LLC
"""DB maintenance / migrations beyond basic schema.

Responsibilities:
- Merge duplicate categories safely without violating UNIQUE constraints.
- Normalize category keys (case/whitespace-insensitive category equivalence).

Key safety behavior:
- When merging category_key 'loser' -> 'winner', DO NOT UPDATE in-place when
  there is a UNIQUE(word, category_key) constraint. Instead:
    (a) INSERT OR IGNORE rows into winner
    (b) DELETE rows from loser

This file is intentionally separate to keep db.py small.
"""

from __future__ import annotations

from datetime import datetime
from typing import Iterable, List, Sequence

from .utils import normalize_category_key, normalize_token


# This DBMaintenance mixin provides safe merge and cleanup routines. (Start)
class DBMaintenance:
    """Maintenance and dedupe operations for DB tables."""

    # This returns True if a table exists. (Start)
    def _table_exists(self, table: str) -> bool:
        with self.lock:
            cur = self.conn.cursor()
            cur.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name=? LIMIT 1",
                (table,),
            )
            return cur.fetchone() is not None
        # end with
    # end def _table_exists  # _table_exists

    # This returns column names for a table. (Start)
    def _table_columns(self, table: str) -> list[str]:
        with self.lock:
            cur = self.conn.cursor()
            cur.execute(f"PRAGMA table_info({table})")
            return [str(r[1]) for r in cur.fetchall() if r and len(r) > 1]
        # end with
    # end def _table_columns  # _table_columns

    # This prints a debug line if DEBUG env is enabled by the core DB. (Start)
    def _dbg(self, msg: str) -> None:
        # Delegate to core if available; otherwise no-op.
        f = getattr(self, "_dbg_print", None)
        if callable(f):
            f("db_maintenance", msg)
        # end if
    # end def _dbg  # _dbg

    # This safely merges rows from loser_key into winner_key for a given table. (Start)
    def _merge_category_key_table(self, table: str, winner_key: str, loser_key: str) -> None:
        """
        Generic merge for tables that contain a 'category_key' column.

        Strategy:
        - SELECT all rows from loser_key
        - INSERT OR IGNORE into winner_key (row-by-row)
        - DELETE loser_key rows
        """
        if not self._table_exists(table):
            return
        # end if

        cols = self._table_columns(table)
        if "category_key" not in cols:
            return
        # end if

        # Build a stable column order for fetch/insert. (Start)
        other_cols = [c for c in cols if c != "category_key"]
        if not other_cols:
            return
        # end if

        select_cols = ", ".join(other_cols)
        insert_cols = ", ".join(["category_key"] + other_cols)
        placeholders = ", ".join(["?"] * (1 + len(other_cols)))

        with self.lock:
            cur = self.conn.cursor()
            cur.execute(f"SELECT {select_cols} FROM {table} WHERE category_key=?", (loser_key,))
            rows = cur.fetchall()

            for r in rows:
                cur.execute(
                    f"INSERT OR IGNORE INTO {table}({insert_cols}) VALUES({placeholders})",
                    (winner_key, *list(r)),
                )
            # end for

            cur.execute(f"DELETE FROM {table} WHERE category_key=?", (loser_key,))
            self.conn.commit()
        # end with
    # end def _merge_category_key_table  # _merge_category_key_table

    # This safely merges rows from loser_key into winner_key for legacy 'words' table. (Start)
    def _merge_words_table_if_present(self, winner_key: str, loser_key: str) -> None:
        """
        Legacy support: some older schemas use table 'words' with UNIQUE(word, category_key).
        This performs the safe merge pattern for that table if it exists.
        """
        if not self._table_exists("words"):
            return
        # end if

        cols = self._table_columns("words")
        if "category_key" not in cols or "word" not in cols:
            return
        # end if

        other_cols = [c for c in cols if c != "category_key"]
        select_cols = ", ".join(other_cols)
        insert_cols = ", ".join(["category_key"] + other_cols)
        placeholders = ", ".join(["?"] * (1 + len(other_cols)))

        with self.lock:
            cur = self.conn.cursor()
            cur.execute(f"SELECT {select_cols} FROM words WHERE category_key=?", (loser_key,))
            rows = cur.fetchall()

            for r in rows:
                cur.execute(
                    f"INSERT OR IGNORE INTO words({insert_cols}) VALUES({placeholders})",
                    (winner_key, *list(r)),
                )
            # end for

            cur.execute("DELETE FROM words WHERE category_key=?", (loser_key,))
            self.conn.commit()
        # end with
    # end def _merge_words_table_if_present  # _merge_words_table_if_present

    # This merges duplicate categories that normalize to the same category_key. (Start)
    def merge_duplicate_categories(self) -> None:
        """
        Merge duplicate categories where category_display variants normalize to the same key.

        We look at category_vocab if present (preferred), else fall back to subjects.
        """
        # Determine candidate (display -> key) sources. (Start)
        pairs: list[tuple[str, str]] = []

        if self._table_exists("category_vocab") and "category_display" in self._table_columns("category_vocab"):
            with self.lock:
                cur = self.conn.cursor()
                cur.execute("SELECT DISTINCT category_key, category_display FROM category_vocab")
                pairs = [(normalize_token(r[0]), normalize_token(r[1])) for r in cur.fetchall()]
            # end with
        elif self._table_exists("subjects"):
            with self.lock:
                cur = self.conn.cursor()
                cur.execute("SELECT DISTINCT subject FROM subjects")
                pairs = [(normalize_category_key(r[0]), normalize_token(r[0])) for r in cur.fetchall() if r and r[0]]
            # end with
        # end if
        # end determine source

        if not pairs:
            return
        # end if

        # Group by normalized display key. (Start)
        buckets: dict[str, list[str]] = {}
        for stored_key, display in pairs:
            k = normalize_category_key(display) or normalize_category_key(stored_key)
            if not k:
                continue
            # end if
            buckets.setdefault(k, [])
            if stored_key and stored_key not in buckets[k]:
                buckets[k].append(stored_key)
            # end if
        # end for
        # end grouping

        # For each bucket, merge losers into winner. (Start)
        for winner_key, keys in buckets.items():
            losers = [k for k in keys if k and k != winner_key]
            if not losers:
                continue
            # end if

            for loser_key in losers:
                self._dbg(f"Merging category_key '{loser_key}' -> '{winner_key}'")

                # Merge modern tables. (Start)
                for table in ["category_vocab", "category_picks", "category_obscurity", "category_picks_by_user"]:
                    self._merge_category_key_table(table, winner_key, loser_key)
                # end for

                # Merge legacy words table if present. (Start)
                self._merge_words_table_if_present(winner_key, loser_key)
                # end legacy

            # end for loser
        # end for winner
        # end merging
    # end def merge_duplicate_categories  # merge_duplicate_categories

# end class DBMaintenance  # DBMaintenance
