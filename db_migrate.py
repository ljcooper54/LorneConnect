# Copyright 2025 H2so4 Consulting LLC
# File: App/db_migrate_v3.py
# Safe migration to DB schema version 3 (adds obscurity_adjust column).

from __future__ import annotations

import sqlite3
from .debug import dlog


TARGET_VERSION = 3


# This performs in-place safe migration preserving all existing data. (Start)
def migrate_if_needed(conn: sqlite3.Connection) -> None:
    cur = conn.cursor()

    # Determine existing version (default 1 if not present). (Start)
    try:
        row = cur.execute("PRAGMA user_version").fetchone()
        current_version = int(row[0]) if row else 1
    except Exception:
        current_version = 1
    # end version detection

    dlog("db_migrate", f"Current DB version: {current_version}")

    if current_version >= TARGET_VERSION:
        return
    # end if

    # ---- Migration to v3 ----
    # Add obscurity_adjust column if missing. (Start)
    try:
        cur.execute("ALTER TABLE user_word_flags ADD COLUMN obscurity_adjust INTEGER NOT NULL DEFAULT 0")
        dlog("db_migrate", "Added obscurity_adjust column.")
    except sqlite3.OperationalError:
        # Column likely already exists — safe to ignore
        dlog("db_migrate", "obscurity_adjust column already exists.")
    # end alter

    # Preserve all data — no destructive changes.
    cur.execute(f"PRAGMA user_version = {TARGET_VERSION}")
    conn.commit()

    dlog("db_migrate", "Migration to v3 complete.")
# end def migrate_if_needed
