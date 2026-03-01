# Copyright 2025 H2so4 Consulting LLC
"""
File: category_admin_tool.py

CLI tool to manage Connections categories in a SQLite DB:
- list categories
- rename a category (display + key)
- delete a category
- merge two categories

Works with the core tables:
- category_vocab
- word_picks
- category_obscurity

Usage examples:
  python category_admin_tool.py list
  python category_admin_tool.py rename --old "Canadian Cities" --new "Canadian Cities (Major)" --yes
  python category_admin_tool.py delete --category "Indian Food" --yes
  python category_admin_tool.py merge --source "CANADIAN CITIES" --target "Canadian Cities" --yes

DB selection:
- If --db is provided, uses that path
- Else finds ./connections_v*.db and chooses the most recently modified
"""

from __future__ import annotations

import argparse
import csv
import os
import re
import sqlite3
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional, Tuple


# ----------------------------
# Normalization helpers
# ----------------------------

# This normalizes an input token for display/storage comparisons. (Start)
def normalize_token(s: str) -> str:
    """Trim and collapse whitespace."""
    if s is None:
        return ""
    # end if
    s = str(s).strip()
    s = re.sub(r"\s+", " ", s)
    return s
# end def normalize_token  # normalize_token


# This normalizes a category key the same way the app typically does. (Start)
def normalize_category_key(category_display: str) -> str:
    """Normalize a category display string into a stable key."""
    s = normalize_token(category_display).lower()
    if not s:
        return ""
    # end if
    # Replace non-alphanumeric with underscores, collapse repeats.
    s = re.sub(r"[^a-z0-9]+", "_", s)
    s = re.sub(r"_+", "_", s).strip("_")
    return s
# end def normalize_category_key  # normalize_category_key


# ----------------------------
# DB utilities
# ----------------------------

# This structured record represents a category inventory row. (Start)
@dataclass(frozen=True)
class CategoryInventoryRow:
    """Inventory summary for a category."""
    category_key: str
    category_display: str
    words: int
# end class CategoryInventoryRow  # CategoryInventoryRow


# This finds the DB path based on CLI args or newest connections_v*.db. (Start)
def resolve_db_path(db_arg: Optional[str]) -> Path:
    """Resolve DB file path from --db or newest connections_v*.db in cwd."""
    if db_arg:
        p = Path(db_arg).expanduser().resolve()
        return p
    # end if

    cwd = Path.cwd()
    candidates = sorted(cwd.glob("connections_v*.db"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not candidates:
        raise FileNotFoundError(
            "No --db provided and no connections_v*.db found in current directory."
        )
    # end if
    return candidates[0]
# end def resolve_db_path  # resolve_db_path


# This opens a sqlite connection with FK enforcement and WAL mode. (Start)
def open_db(db_path: Path) -> sqlite3.Connection:
    """Open SQLite connection with pragmatic settings."""
    conn = sqlite3.connect(str(db_path), check_same_thread=False)
    conn.execute("PRAGMA foreign_keys=ON;")
    conn.execute("PRAGMA journal_mode=WAL;")
    return conn
# end def open_db  # open_db


# This checks if a table exists in the DB. (Start)
def table_exists(conn: sqlite3.Connection, name: str) -> bool:
    """Return True if table exists."""
    cur = conn.cursor()
    cur.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=? LIMIT 1", (name,))
    return cur.fetchone() is not None
# end def table_exists  # table_exists


# This returns required tables found in the DB. (Start)
def ensure_required_tables(conn: sqlite3.Connection) -> None:
    """Validate the DB contains expected tables."""
    required = ["category_vocab"]
    missing = [t for t in required if not table_exists(conn, t)]
    if missing:
        raise RuntimeError(f"DB is missing required table(s): {missing}")
    # end if
# end def ensure_required_tables  # ensure_required_tables


# This chooses a canonical display name for a category_key from category_vocab. (Start)
def get_display_for_key(conn: sqlite3.Connection, category_key: str) -> str:
    """Return most common category_display for a given key."""
    cur = conn.cursor()
    cur.execute(
        """
        SELECT category_display, COUNT(*) AS n
        FROM category_vocab
        WHERE category_key=?
        GROUP BY category_display
        ORDER BY n DESC, category_display ASC
        LIMIT 1
        """,
        (category_key,),
    )
    row = cur.fetchone()
    return normalize_token(row[0]) if row and row[0] else category_key
# end def get_display_for_key  # get_display_for_key


# This resolves either a key or a display string to a category_key. (Start)
def resolve_category_key(conn: sqlite3.Connection, category: str) -> str:
    """
    Resolve a category identifier to category_key.
    Accepts either:
    - an exact category_key (if it exists), else
    - a display string, normalized to key, if it exists, else
    - tries to match category_display case-insensitively.
    """
    ident = normalize_token(category)
    if not ident:
        return ""
    # end if

    # 1) Treat as key if it exists
    cur = conn.cursor()
    cur.execute("SELECT 1 FROM category_vocab WHERE category_key=? LIMIT 1", (ident,))
    if cur.fetchone() is not None:
        return ident
    # end if

    # 2) Try normalized key from display
    ck = normalize_category_key(ident)
    cur.execute("SELECT 1 FROM category_vocab WHERE category_key=? LIMIT 1", (ck,))
    if cur.fetchone() is not None:
        return ck
    # end if

    # 3) Try matching display directly (case-insensitive)
    cur.execute(
        "SELECT category_key FROM category_vocab WHERE lower(category_display)=lower(?) LIMIT 1",
        (ident,),
    )
    row = cur.fetchone()
    if row and row[0]:
        return str(row[0])
    # end if

    return ""
# end def resolve_category_key  # resolve_category_key


# ----------------------------
# Inventory and reporting
# ----------------------------

# This lists categories in the DB. (Start)
def list_categories(conn: sqlite3.Connection) -> list[CategoryInventoryRow]:
    """Return categories with a word count."""
    cur = conn.cursor()
    cur.execute(
        """
        SELECT category_key,
               MAX(category_display) as any_display,
               COUNT(*) as words
        FROM category_vocab
        GROUP BY category_key
        ORDER BY words DESC, category_key ASC
        """
    )
    out: list[CategoryInventoryRow] = []
    for (ck, any_display, words) in cur.fetchall():
        out.append(
            CategoryInventoryRow(
                category_key=str(ck),
                category_display=normalize_token(any_display) if any_display else str(ck),
                words=int(words or 0),
            )
        )
    # end for
    return out
# end def list_categories  # list_categories


# ----------------------------
# Mutations: delete / rename / merge
# ----------------------------

# This deletes a category across related tables. (Start)
def delete_category(conn: sqlite3.Connection, category_key: str) -> dict:
    """Delete category rows in known tables. Returns counts per table."""
    counts: dict[str, int] = {}

    with conn:
        cur = conn.cursor()

        # category_vocab
        cur.execute("DELETE FROM category_vocab WHERE category_key=?", (category_key,))
        counts["category_vocab"] = cur.rowcount if cur.rowcount is not None else 0

        # word_picks (optional)
        if table_exists(conn, "word_picks"):
            cur.execute("DELETE FROM word_picks WHERE category_key=?", (category_key,))
            counts["word_picks"] = cur.rowcount if cur.rowcount is not None else 0
        # end if

        # category_obscurity (optional)
        if table_exists(conn, "category_obscurity"):
            cur.execute("DELETE FROM category_obscurity WHERE category_key=?", (category_key,))
            counts["category_obscurity"] = cur.rowcount if cur.rowcount is not None else 0
        # end if
    # end with

    return counts
# end def delete_category  # delete_category


# This renames a category display and optionally its key. (Start)
def rename_category(
    conn: sqlite3.Connection,
    old_key: str,
    new_display: str,
    new_key: Optional[str],
) -> dict:
    """
    Rename a category.
    - Always updates category_display for the category rows
    - If new_key is provided and differs, moves rows to the new key (merge-like)
    """
    new_display = normalize_token(new_display)
    if not new_display:
        raise ValueError("new_display must be non-empty")
    # end if

    if new_key is None:
        new_key = old_key
    # end if
    new_key = normalize_token(new_key)

    if not new_key:
        raise ValueError("new_key must be non-empty")
    # end if

    result: dict[str, int] = {"moved_words": 0, "updated_words": 0}

    with conn:
        cur = conn.cursor()

        if new_key == old_key:
            cur.execute(
                "UPDATE category_vocab SET category_display=? WHERE category_key=?",
                (new_display, old_key),
            )
            result["updated_words"] = cur.rowcount if cur.rowcount is not None else 0
        else:
            # Move/merge words to the new key, resolving PK collisions.
            cur.execute(
                """
                SELECT word, obscurity, wrong_category, too_ambiguous, created_at
                FROM category_vocab
                WHERE category_key=?
                """,
                (old_key,),
            )
            rows = cur.fetchall()

            for (word, obscurity, wrong_category, too_ambiguous, created_at) in rows:
                w = str(word)
                o = int(obscurity or 2)
                wc = int(wrong_category or 0)
                ta = int(too_ambiguous or 0)
                ca = float(created_at or time.time())

                # Insert if missing.
                cur.execute(
                    """
                    INSERT OR IGNORE INTO category_vocab(
                        category_key, category_display, word, obscurity, wrong_category, too_ambiguous, created_at
                    ) VALUES (?,?,?,?,?,?,?)
                    """,
                    (new_key, new_display, w, o, wc, ta, ca),
                )

                if cur.rowcount and cur.rowcount > 0:
                    result["moved_words"] += 1
                else:
                    # Already existed: merge fields (keep min obscurity, max flags, min created_at)
                    cur.execute(
                        """
                        UPDATE category_vocab
                        SET category_display=?,
                            obscurity = MIN(obscurity, ?),
                            wrong_category = MAX(wrong_category, ?),
                            too_ambiguous = MAX(too_ambiguous, ?),
                            created_at = MIN(created_at, ?)
                        WHERE category_key=? AND word=?
                        """,
                        (new_display, o, wc, ta, ca, new_key, w),
                    )
                    result["updated_words"] += cur.rowcount if cur.rowcount is not None else 0
                # end if
            # end for

            # Delete old rows
            cur.execute("DELETE FROM category_vocab WHERE category_key=?", (old_key,))

            # Update related tables
            if table_exists(conn, "word_picks"):
                cur.execute("UPDATE word_picks SET category_key=? WHERE category_key=?", (new_key, old_key))
            # end if
            if table_exists(conn, "category_obscurity"):
                cur.execute(
                    "UPDATE category_obscurity SET category_key=? WHERE category_key=?",
                    (new_key, old_key),
                )
            # end if
        # end if/else
    # end with

    return result
# end def rename_category  # rename_category


# This merges one category into another, preserving the target and removing the source. (Start)
def merge_categories(conn: sqlite3.Connection, source_key: str, target_key: str, target_display: Optional[str]) -> dict:
    """
    Merge source into target:
    - Vocab words are inserted into target; collisions are merged (min obscurity, max flags, min created_at).
    - word_picks and category_obscurity are reassigned to target.
    - source vocab is deleted afterwards.
    """
    if source_key == target_key:
        raise ValueError("source and target must be different categories")
    # end if

    if not target_display:
        target_display = get_display_for_key(conn, target_key)
    # end if
    target_display = normalize_token(target_display)

    result: dict[str, int] = {"inserted": 0, "merged": 0}

    with conn:
        cur = conn.cursor()

        cur.execute(
            """
            SELECT word, obscurity, wrong_category, too_ambiguous, created_at
            FROM category_vocab
            WHERE category_key=?
            """,
            (source_key,),
        )
        rows = cur.fetchall()

        for (word, obscurity, wrong_category, too_ambiguous, created_at) in rows:
            w = str(word)
            o = int(obscurity or 2)
            wc = int(wrong_category or 0)
            ta = int(too_ambiguous or 0)
            ca = float(created_at or time.time())

            cur.execute(
                """
                INSERT OR IGNORE INTO category_vocab(
                    category_key, category_display, word, obscurity, wrong_category, too_ambiguous, created_at
                ) VALUES (?,?,?,?,?,?,?)
                """,
                (target_key, target_display, w, o, wc, ta, ca),
            )

            if cur.rowcount and cur.rowcount > 0:
                result["inserted"] += 1
            else:
                cur.execute(
                    """
                    UPDATE category_vocab
                    SET category_display=?,
                        obscurity = MIN(obscurity, ?),
                        wrong_category = MAX(wrong_category, ?),
                        too_ambiguous = MAX(too_ambiguous, ?),
                        created_at = MIN(created_at, ?)
                    WHERE category_key=? AND word=?
                    """,
                    (target_display, o, wc, ta, ca, target_key, w),
                )
                result["merged"] += 1
            # end if
        # end for

        # Reassign related tables
        if table_exists(conn, "word_picks"):
            cur.execute("UPDATE word_picks SET category_key=? WHERE category_key=?", (target_key, source_key))
        # end if
        if table_exists(conn, "category_obscurity"):
            cur.execute("UPDATE category_obscurity SET category_key=? WHERE category_key=?", (target_key, source_key))
        # end if

        # Remove the source category from vocab
        cur.execute("DELETE FROM category_vocab WHERE category_key=?", (source_key,))
    # end with

    return result
# end def merge_categories  # merge_categories


# ----------------------------
# CLI
# ----------------------------

# This prints categories in a simple table to stdout. (Start)
def cmd_list(conn: sqlite3.Connection) -> int:
    """List categories."""
    rows = list_categories(conn)
    print(f"{'Words':>6}  {'Category Key':<30}  Category Display")
    print("-" * 80)
    for r in rows:
        print(f"{r.words:>6}  {r.category_key:<30}  {r.category_display}")
    # end for
    return 0
# end def cmd_list  # cmd_list


# This handles the delete subcommand. (Start)
def cmd_delete(conn: sqlite3.Connection, args: argparse.Namespace) -> int:
    """Delete a category."""
    ck = resolve_category_key(conn, args.category)
    if not ck:
        print(f"ERROR: Category not found: {args.category}", file=sys.stderr)
        return 2
    # end if

    display = get_display_for_key(conn, ck)
    if not args.yes:
        print(f"Refusing to delete '{display}' (key={ck}) without --yes", file=sys.stderr)
        return 2
    # end if

    counts = delete_category(conn, ck)
    print(f"Deleted category '{display}' (key={ck}). Counts: {counts}")
    return 0
# end def cmd_delete  # cmd_delete


# This handles the rename subcommand. (Start)
def cmd_rename(conn: sqlite3.Connection, args: argparse.Namespace) -> int:
    """Rename a category."""
    old_key = resolve_category_key(conn, args.old)
    if not old_key:
        print(f"ERROR: Category not found: {args.old}", file=sys.stderr)
        return 2
    # end if

    new_display = normalize_token(args.new_display)
    if not new_display:
        print("ERROR: --new-display cannot be empty", file=sys.stderr)
        return 2
    # end if

    # Compute new key if requested; otherwise leave key unchanged.
    new_key: Optional[str] = None
    if args.new_key is not None:
        new_key = normalize_token(args.new_key)
        if not new_key:
            print("ERROR: --new-key cannot be empty", file=sys.stderr)
            return 2
        # end if
    # end if

    if args.derive_key:
        new_key = normalize_category_key(new_display)
    # end if

    if not args.yes:
        print("Refusing to rename without --yes", file=sys.stderr)
        print(f"Would rename key={old_key} to display='{new_display}' and key='{new_key or old_key}'", file=sys.stderr)
        return 2
    # end if

    res = rename_category(conn, old_key=old_key, new_display=new_display, new_key=new_key)
    print(f"Renamed category key={old_key} -> key={new_key or old_key}, display='{new_display}'. Result: {res}")
    return 0
# end def cmd_rename  # cmd_rename


# This handles the merge subcommand. (Start)
def cmd_merge(conn: sqlite3.Connection, args: argparse.Namespace) -> int:
    """Merge source into target."""
    source_key = resolve_category_key(conn, args.source)
    target_key = resolve_category_key(conn, args.target)

    if not source_key:
        print(f"ERROR: Source category not found: {args.source}", file=sys.stderr)
        return 2
    # end if
    if not target_key:
        print(f"ERROR: Target category not found: {args.target}", file=sys.stderr)
        return 2
    # end if

    if source_key == target_key:
        print("ERROR: source and target resolve to the same category_key", file=sys.stderr)
        return 2
    # end if

    if not args.yes:
        print("Refusing to merge without --yes", file=sys.stderr)
        print(f"Would merge source={source_key} into target={target_key}", file=sys.stderr)
        return 2
    # end if

    res = merge_categories(conn, source_key=source_key, target_key=target_key, target_display=args.target_display)
    print(f"Merged source={source_key} into target={target_key}. Result: {res}")
    return 0
# end def cmd_merge  # cmd_merge


# This builds an argparse parser. (Start)
def build_parser() -> argparse.ArgumentParser:
    """Build CLI parser."""
    p = argparse.ArgumentParser(prog="category_admin_tool.py", add_help=True)
    p.add_argument("--db", default=None, help="Path to SQLite DB. If omitted, uses newest ./connections_v*.db")

    sub = p.add_subparsers(dest="cmd", required=True)

    sp = sub.add_parser("list", help="List categories")
    sp.set_defaults(func=cmd_list)

    sp = sub.add_parser("delete", help="Delete a category")
    sp.add_argument("--category", required=True, help="Category display or key")
    sp.add_argument("--yes", action="store_true", help="Confirm destructive action")
    sp.set_defaults(func=cmd_delete)

    sp = sub.add_parser("rename", help="Rename a category (display and optionally key)")
    sp.add_argument("--old", required=True, help="Existing category display or key")
    sp.add_argument("--new-display", required=True, dest="new_display", help="New display name for the category")
    sp.add_argument("--new-key", default=None, help="New category_key to assign (optional)")
    sp.add_argument("--derive-key", action="store_true", help="Derive new key from new display (overrides --new-key)")
    sp.add_argument("--yes", action="store_true", help="Confirm destructive action")
    sp.set_defaults(func=cmd_rename)

    sp = sub.add_parser("merge", help="Merge source category into target category")
    sp.add_argument("--source", required=True, help="Source category display or key (will be removed)")
    sp.add_argument("--target", required=True, help="Target category display or key (will remain)")
    sp.add_argument("--target-display", default=None, help="Optional: set target display for all rows")
    sp.add_argument("--yes", action="store_true", help="Confirm destructive action")
    sp.set_defaults(func=cmd_merge)

    return p
# end def build_parser  # build_parser


# This main entrypoint dispatches CLI subcommands. (Start)
def main(argv: Optional[list[str]] = None) -> int:
    """CLI entrypoint."""
    parser = build_parser()
    args = parser.parse_args(argv)

    db_path = resolve_db_path(args.db)
    if not db_path.exists():
        print(f"ERROR: DB does not exist: {db_path}", file=sys.stderr)
        return 2
    # end if

    conn = open_db(db_path)
    try:
        ensure_required_tables(conn)
        rc = int(args.func(conn, args) if args.cmd != "list" else args.func(conn))
        return rc
    finally:
        conn.close()
    # end try/finally
# end def main  # main


if __name__ == "__main__":
    raise SystemExit(main())
