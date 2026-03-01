# File: App/db_core.py
# Copyright 2025 H2so4 Consulting LLC
"""
Versioned DB core for Connections.

Design:
- Each schema version uses its own DB file.
- If a new version is created and an older version exists,
  we attempt to import category data safely.
"""

from __future__ import annotations

import sqlite3
import threading
from pathlib import Path

from .debug import debug_log


# ----- SCHEMA VERSION -----
DB_SCHEMA_VERSION = 3

BASE_DB_NAME = "connections"
DB_FILE = f"{BASE_DB_NAME}_v{DB_SCHEMA_VERSION}.db"


# This DBCore owns the sqlite connection and creates schema fresh. (Start)
class DBCore:
    """SQLite connection + schema creation + safe category import."""

    # This initializes the DB connection and ensures schema exists. (Start)
    def __init__(self):
        self.lock = threading.RLock()

        self.db_path = Path(DB_FILE)
        existed = self.db_path.exists()

        # Open the SQLite database. (Start)
        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        # end open connection

        # Enable WAL + FK support for reliability. (Start)
        self.conn.execute("PRAGMA journal_mode=WAL;")
        self.conn.execute("PRAGMA foreign_keys=ON;")
        # end PRAGMA setup

        debug_log("db_core", f"DB opened: {self.db_path}")
        debug_log("db_core", f"DB existed before open: {existed}")

        # Create schema tables. (Start)
        self._create_schema()
        # end create schema

        # If this DB did not exist before, try importing categories. (Start)
        if not existed:
            self._maybe_import_previous_categories()
        # end if new db
    # end def __init__  # __init__

    # ---------------------------------------------------------
    # Schema Creation
    # ---------------------------------------------------------

    # This creates all tables required for this schema version. (Start)
    def _create_schema(self) -> None:
        with self.lock:
            cur = self.conn.cursor()

            # Create subjects table. (Start)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS subjects(
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user TEXT NOT NULL,
                    subject TEXT NOT NULL,
                    created_at REAL NOT NULL DEFAULT (strftime('%s','now'))
                )
            """)
            # end subjects table

            # Create user_stats table. (Start)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS user_stats(
                    user TEXT PRIMARY KEY,
                    played INTEGER NOT NULL DEFAULT 0,
                    won INTEGER NOT NULL DEFAULT 0,
                    lost INTEGER NOT NULL DEFAULT 0
                )
            """)
            # end user_stats table

            # Create user_word_flags table (v3 includes obscurity_adjust). (Start)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS user_word_flags(
                    user TEXT NOT NULL,
                    word TEXT NOT NULL,
                    inappropriate INTEGER NOT NULL DEFAULT 0,
                    too_hard INTEGER NOT NULL DEFAULT 0,
                    obscurity_adjust INTEGER NOT NULL DEFAULT 0,
                    PRIMARY KEY(user, word)
                )
            """)
            # end user_word_flags table

            # Create category_vocab table. (Start)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS category_vocab(
                    category_key TEXT NOT NULL,
                    category_display TEXT NOT NULL,
                    word TEXT NOT NULL,
                    obscurity INTEGER NOT NULL,
                    wrong_category INTEGER NOT NULL DEFAULT 0,
                    too_ambiguous INTEGER NOT NULL DEFAULT 0,
                    created_at REAL NOT NULL DEFAULT (strftime('%s','now')),
                    PRIMARY KEY(category_key, word)
                )
            """)
            # end category_vocab table

            # Create word_picks table. (Start)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS word_picks(
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user TEXT NOT NULL,
                    category_key TEXT NOT NULL,
                    word TEXT NOT NULL,
                    picked_at REAL NOT NULL DEFAULT (strftime('%s','now'))
                )
            """)
            # end word_picks table

            # Create category_obscurity table. (Start)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS category_obscurity(
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    category_key TEXT NOT NULL,
                    color TEXT NOT NULL,
                    obscurity INTEGER NOT NULL,
                    words_json TEXT NOT NULL,
                    created_at REAL NOT NULL DEFAULT (strftime('%s','now'))
                )
            """)
            # end category_obscurity table

            self.conn.commit()
        # end with lock
    # end def _create_schema  # _create_schema

    # ---------------------------------------------------------
    # Category Import Logic
    # ---------------------------------------------------------

    # This attempts to import category data from the previous DB version. (Start)
    def _maybe_import_previous_categories(self) -> None:
        prev_version = DB_SCHEMA_VERSION - 1
        if prev_version <= 0:
            return
        # end if no previous version

        prev_path = Path(f"{BASE_DB_NAME}_v{prev_version}.db")
        if not prev_path.exists():
            debug_log("db_core", "No previous DB file found.")
            return
        # end if no old file

        debug_log("db_core", f"Importing category data from {prev_path}")

        try:
            old_conn = sqlite3.connect(prev_path)
            old_conn.row_factory = sqlite3.Row

            # Check if category_vocab has rows. (Start)
            row = old_conn.execute(
                "SELECT COUNT(*) AS c FROM category_vocab"
            ).fetchone()

            if not row or row["c"] == 0:
                debug_log("db_core", "Previous DB has no category data.")
                old_conn.close()
                return
            # end if no category data

            # Copy category_vocab rows. (Start)
            for r in old_conn.execute("SELECT * FROM category_vocab"):
                self.conn.execute("""
                    INSERT OR IGNORE INTO category_vocab(
                        category_key,
                        category_display,
                        word,
                        obscurity,
                        wrong_category,
                        too_ambiguous,
                        created_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    r["category_key"],
                    r["category_display"],
                    r["word"],
                    r["obscurity"],
                    r["wrong_category"],
                    r["too_ambiguous"],
                    r["created_at"],
                ))
            # end copy category_vocab

            # Copy category_obscurity rows. (Start)
            for r in old_conn.execute("SELECT * FROM category_obscurity"):
                self.conn.execute("""
                    INSERT OR IGNORE INTO category_obscurity(
                        category_key,
                        color,
                        obscurity,
                        words_json,
                        created_at
                    )
                    VALUES (?, ?, ?, ?, ?)
                """, (
                    r["category_key"],
                    r["color"],
                    r["obscurity"],
                    r["words_json"],
                    r["created_at"],
                ))
            # end copy category_obscurity

            self.conn.commit()
            old_conn.close()

            debug_log("db_core", "Category import complete.")
        except Exception as e:
            debug_log("db_core", f"Category import failed: {e}")
        # end try/except
    # end def _maybe_import_previous_categories  # _maybe_import_previous_categories

# end class DBCore  # DBCore
