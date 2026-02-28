# File: App/db_core.py
# Copyright 2025 H2so4 Consulting LLC
"""Simple versioned DB core for Connections.

No migrations.
If schema version changes, a new DB file is created.
"""

from __future__ import annotations

import sqlite3
import threading
from pathlib import Path

from .debug import debug_log

# ----- SCHEMA VERSION -----
DB_SCHEMA_VERSION = 2

BASE_DB_NAME = "connections"
DB_FILE = f"{BASE_DB_NAME}_v{DB_SCHEMA_VERSION}.db"


# This DBCore owns the sqlite connection and creates schema fresh. (Start)
class DBCore:
    """SQLite connection + fresh schema creation."""

    # This initializes the DB and creates schema. (Start)
    def __init__(self):
        self.lock = threading.RLock()

        self.db_path = Path(DB_FILE)
        existed = self.db_path.exists()

        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self.conn.execute("PRAGMA journal_mode=WAL;")
        self.conn.execute("PRAGMA foreign_keys=ON;")

        debug_log("db_core", f"DB opened: {self.db_path}")
        debug_log("db_core", f"DB existed before open: {existed}")

        self._create_schema()
    # end def __init__  # __init__

    # This creates all tables for this schema version. (Start)
    def _create_schema(self) -> None:
        with self.lock:
            cur = self.conn.cursor()

            # Subjects
            cur.execute("""
                CREATE TABLE IF NOT EXISTS subjects(
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user TEXT NOT NULL,
                    subject TEXT NOT NULL,
                    created_at REAL NOT NULL DEFAULT (strftime('%s','now'))
                )
            """)

            # User stats
            cur.execute("""
                CREATE TABLE IF NOT EXISTS user_stats(
                    user TEXT PRIMARY KEY,
                    played INTEGER NOT NULL DEFAULT 0,
                    won INTEGER NOT NULL DEFAULT 0,
                    lost INTEGER NOT NULL DEFAULT 0
                )
            """)

            # User word flags
            cur.execute("""
                CREATE TABLE IF NOT EXISTS user_word_flags(
                    user TEXT NOT NULL,
                    word TEXT NOT NULL,
                    inappropriate INTEGER NOT NULL DEFAULT 0,
                    too_hard INTEGER NOT NULL DEFAULT 0,
                    PRIMARY KEY(user, word)
                )
            """)

            # Category vocab
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

            # Word picks (per user, per category)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS word_picks(
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user TEXT NOT NULL,
                    category_key TEXT NOT NULL,
                    word TEXT NOT NULL,
                    picked_at REAL NOT NULL DEFAULT (strftime('%s','now'))
                )
            """)

            # Obscurity snapshots
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

            self.conn.commit()
        # end with
    # end def _create_schema  # _create_schema

# end class DBCore  # DBCore
