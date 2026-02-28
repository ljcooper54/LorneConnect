# File: App/debug.py | Created/Modified: 2026-02-27
# Copyright 2025 H2so4 Consulting LLC
"""Centralized debug logging and optional debug exports.

Exports:
- debug_log(module, message)
- debug_log_category_obscurity_csv_excel(db)

DEBUG is enabled when env var DEBUG is one of: 1, true, yes, on (case-insensitive).
"""

from __future__ import annotations

import csv
import datetime
import os
from pathlib import Path
from typing import Any


# This determines whether DEBUG logging is enabled. (Start)
def _is_debug_enabled() -> bool:
    val = os.environ.get("DEBUG", "")
    return str(val).strip().lower() in {"1", "true", "yes", "on"}
# end def _is_debug_enabled  # _is_debug_enabled


# This prints a timestamped debug message if DEBUG is enabled. (Start)
def debug_log(module: str, message: str) -> None:
    if not _is_debug_enabled():
        return
    # end if

    ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{ts}][{module}][DEBUG] {message}")
# end def debug_log  # debug_log


# This returns True if a table exists in the current sqlite DB. (Start)
def _table_exists(db: Any, table: str) -> bool:
    try:
        cur = db.conn.cursor()
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table,))
        return cur.fetchone() is not None
    except Exception:
        return False
    # end try/except
# end def _table_exists  # _table_exists


# This exports category_vocab obscurity counts to a CSV Excel can open. (Start)
def debug_log_category_obscurity_csv_excel(db: Any, outfile: str = "category_obscurity_counts.csv") -> None:
    """
    Writes a CSV (Excel-friendly) with per-category counts by obscurity, based on category_vocab.

    This is primarily for validating:
    - obscurity distribution per category
    - whether you have enough words in each obscurity bucket to assign colors

    Safe behavior:
    - If DEBUG is off: returns immediately.
    - If db/conn missing or category_vocab missing: logs and returns.
    """
    if not _is_debug_enabled():
        return
    # end if

    if db is None or not hasattr(db, "conn"):
        debug_log("debug", "debug_log_category_obscurity_csv_excel: db has no .conn; skipping")
        return
    # end if

    if not _table_exists(db, "category_vocab"):
        debug_log("debug", "debug_log_category_obscurity_csv_excel: table category_vocab not found; skipping")
        return
    # end if

    # Collect counts by category_key and obscurity, excluding category-level rejected words. (Start)
    try:
        cur = db.conn.cursor()
        cur.execute(
            """
            SELECT
                category_key,
                MAX(category_display) as category_display,
                obscurity,
                COUNT(*) as n
            FROM category_vocab
            WHERE COALESCE(wrong_category,0)=0 AND COALESCE(too_ambiguous,0)=0
            GROUP BY category_key, obscurity
            ORDER BY category_display COLLATE NOCASE ASC, obscurity ASC
            """
        )
        rows = cur.fetchall()
    except Exception as e:
        debug_log("debug", f"debug_log_category_obscurity_csv_excel: query failed: {e}")
        return
    # end try/except
    # end collect

    # Build a wide table for Excel. (Start)
    data: dict[str, dict[int, int]] = {}
    display: dict[str, str] = {}

    for ck, cd, obs, n in rows:
        ck_s = str(ck or "").strip()
        cd_s = str(cd or "").strip()
        try:
            o = int(obs)
        except Exception:
            o = 0
        # end try/except
        try:
            nn = int(n)
        except Exception:
            nn = 0
        # end try/except

        if not ck_s:
            continue
        # end if
        display[ck_s] = cd_s or ck_s
        data.setdefault(ck_s, {1: 0, 2: 0, 3: 0, 4: 0})
        if o in (1, 2, 3, 4):
            data[ck_s][o] = nn
        # end if
    # end for

    out_path = Path(outfile)
    try:
        with out_path.open("w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["category_key", "category_display", "obs1", "obs2", "obs3", "obs4", "total"])
            for ck in sorted(data.keys(), key=lambda x: (display.get(x, x)).casefold()):
                o1 = data[ck].get(1, 0)
                o2 = data[ck].get(2, 0)
                o3 = data[ck].get(3, 0)
                o4 = data[ck].get(4, 0)
                total = o1 + o2 + o3 + o4
                w.writerow([ck, display.get(ck, ck), o1, o2, o3, o4, total])
            # end for
        # end with
        debug_log("debug", f"Wrote obscurity counts CSV: {out_path.resolve()}")
    except Exception as e:
        debug_log("debug", f"debug_log_category_obscurity_csv_excel: write failed: {e}")
    # end try/except
# end def debug_log_category_obscurity_csv_excel  # debug_log_category_obscurity_csv_excel
