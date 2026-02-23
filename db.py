# Copyright 2025 H2so4 Consulting LLC
from __future__ import annotations
"""SQLite DB layer."""

import sqlite3
import threading
import time
import random

from .constants import DB_FILE, EXCLUDE_LAST_N
from .utils import normalize_token

class DB:
    """Thread-safe SQLite wrapper with additive schema migrations."""

    def __init__(self, db_path: str = DB_FILE):
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.conn.execute("PRAGMA journal_mode=WAL;")
        self.lock = threading.Lock()
        self.migrate()

    def _table_exists(self, name: str) -> bool:
        with self.lock:
            cur = self.conn.cursor()
            cur.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,))
            return cur.fetchone() is not None
    # end def _table_exists

    def _columns(self, table: str) -> set[str]:
        with self.lock:
            cur = self.conn.cursor()
            cur.execute(f"PRAGMA table_info({table})")
            return {r[1] for r in cur.fetchall()}  # name is index 1
    # end def _columns

    def _add_column_if_missing(self, table: str, col: str, ddl_fragment: str):
        cols = self._columns(table)
        if col in cols:
            return
        with self.lock:
            cur = self.conn.cursor()
            cur.execute(f"ALTER TABLE {table} ADD COLUMN {col} {ddl_fragment}")
            self.conn.commit()
    # end def _add_column_if_missing

    def migrate(self):
        """Create tables and add missing columns/indexes. Never drops columns."""
        with self.lock:
            cur = self.conn.cursor()

            # subjects
            cur.execute("""
            CREATE TABLE IF NOT EXISTS subjects(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user TEXT NOT NULL,
                subject TEXT NOT NULL
            )
            """)

            # user_stats
            cur.execute("""
            CREATE TABLE IF NOT EXISTS user_stats(
                user TEXT PRIMARY KEY,
                played INTEGER NOT NULL DEFAULT 0,
                solved INTEGER NOT NULL DEFAULT 0
            )
            """)

            # category_words (global)
            cur.execute("""
            CREATE TABLE IF NOT EXISTS category_words(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                category TEXT NOT NULL,
                word TEXT NOT NULL,
                created_at REAL NOT NULL DEFAULT (strftime('%s','now'))
            )
            """)

            # Additive columns (from various prior versions)
            self.conn.commit()

        # Add columns if missing
        self._add_column_if_missing("category_words", "wrong_category", "INTEGER NOT NULL DEFAULT 0")
        self._add_column_if_missing("category_words", "misspelled", "INTEGER NOT NULL DEFAULT 0")
        self._add_column_if_missing("category_words", "very_hard", "INTEGER NOT NULL DEFAULT 0")
        self._add_column_if_missing("category_words", "corrected_spelling", "TEXT")
        # Some prior versions had these; keep if present, ignore otherwise
        if self._table_exists("category_words"):
            # no-op; columns may exist

            pass

        # Unique index for (category, word)
        with self.lock:
            cur = self.conn.cursor()
            cur.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS idx_category_word_unique
            ON category_words(category, word)
            """)
            self.conn.commit()

        # user_word_flags (per-user inappropriate bans)
        with self.lock:
            cur = self.conn.cursor()
            cur.execute("""
            CREATE TABLE IF NOT EXISTS user_word_flags(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user TEXT NOT NULL,
                word TEXT NOT NULL,
                inappropriate INTEGER NOT NULL DEFAULT 0,
                created_at REAL NOT NULL DEFAULT (strftime('%s','now'))
            )
            """)
            cur.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS idx_user_word_unique
            ON user_word_flags(user, word)
            """)
            self.conn.commit()

        # category_obscurity snapshots
        with self.lock:
            cur = self.conn.cursor()
            cur.execute("""
            CREATE TABLE IF NOT EXISTS category_obscurity(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                category TEXT NOT NULL,
                color TEXT NOT NULL,
                obscurity INTEGER NOT NULL,
                words_json TEXT NOT NULL,
                created_at REAL NOT NULL DEFAULT (strftime('%s','now'))
            )
            """)
            self.conn.commit()
    # end def migrate

    # ---- Subjects ----

    def add_subjects(self, user: str, subjects: list[str]):
        """Insert user subjects (distinct)."""
        with self.lock:
            cur = self.conn.cursor()
            for s in subjects:
                s = normalize_token(s)
                if not s:
                    continue
                cur.execute("""
                    INSERT INTO subjects(user, subject)
                    SELECT ?, ?
                    WHERE NOT EXISTS (
                        SELECT 1 FROM subjects WHERE user=? AND subject=?
                    )
                """, (user, s, user, s))
            self.conn.commit()
    # end def add_subjects

    def delete_subject(self, user: str, subject: str):
        """Delete a subject for a user."""
        with self.lock:
            cur = self.conn.cursor()
            cur.execute("DELETE FROM subjects WHERE user=? AND subject=?", (user, normalize_token(subject)))
            self.conn.commit()
    # end def delete_subject

    def get_subjects(self, user: str) -> list[str]:
        """All distinct subjects for user."""
        with self.lock:
            cur = self.conn.cursor()
            cur.execute("SELECT DISTINCT subject FROM subjects WHERE user=?", (user,))
            return [r[0] for r in cur.fetchall()]
    # end def get_subjects

    def get_recent_subjects(self, user: str, limit: int = 6) -> list[str]:
        """Most recently used distinct subjects."""
        with self.lock:
            cur = self.conn.cursor()
            cur.execute("""
                SELECT subject
                FROM subjects
                WHERE user=?
                GROUP BY subject
                ORDER BY MAX(id) DESC
                LIMIT ?
            """, (user, int(limit)))
            return [r[0] for r in cur.fetchall()]
    # end def get_recent_subjects

    # ---- Stats ----

    def ensure_user_stats(self, user: str):
        """Ensure stats row exists."""
        with self.lock:
            cur = self.conn.cursor()
            cur.execute("""
                INSERT INTO user_stats(user, played, solved)
                SELECT ?, 0, 0
                WHERE NOT EXISTS (SELECT 1 FROM user_stats WHERE user=?)
            """, (user, user))
            self.conn.commit()
    # end def ensure_user_stats

    def inc_played(self, user: str):
        """Increment played."""
        self.ensure_user_stats(user)
        with self.lock:
            cur = self.conn.cursor()
            cur.execute("UPDATE user_stats SET played = played + 1 WHERE user=?", (user,))
            self.conn.commit()
    # end def inc_played

    def inc_solved(self, user: str):
        """Increment solved."""
        self.ensure_user_stats(user)
        with self.lock:
            cur = self.conn.cursor()
            cur.execute("UPDATE user_stats SET solved = solved + 1 WHERE user=?", (user,))
            self.conn.commit()
    # end def inc_solved

    def get_stats(self, user: str) -> tuple[int, int]:
        """(played, solved)."""
        self.ensure_user_stats(user)
        with self.lock:
            cur = self.conn.cursor()
            cur.execute("SELECT played, solved FROM user_stats WHERE user=?", (user,))
            row = cur.fetchone()
            return (int(row[0]), int(row[1])) if row else (0, 0)
    # end def get_stats

    # ---- Category word history / bans ----

    def get_last_n_words(self, category: str, n: int = EXCLUDE_LAST_N) -> list[str]:
        """Last N words for category."""
        with self.lock:
            cur = self.conn.cursor()
            cur.execute("""
                SELECT word FROM category_words
                WHERE category=?
                ORDER BY id DESC
                LIMIT ?
            """, (normalize_token(category), int(n)))
            return [r[0] for r in cur.fetchall()]
    # end def get_last_n_words

    def get_category_word_count(self, category: str) -> int:
        """Count stored words for category."""
        with self.lock:
            cur = self.conn.cursor()
            cur.execute("SELECT COUNT(*) FROM category_words WHERE category=?", (normalize_token(category),))
            return int(cur.fetchone()[0] or 0)
    # end def get_category_word_count

    def get_random_words(self, category: str, n: int = 2, exclude: set[str] | None = None) -> list[str]:
        """Random words for category."""
        exclude = exclude or set()
        with self.lock:
            cur = self.conn.cursor()
            cur.execute("SELECT word FROM category_words WHERE category=?", (normalize_token(category),))
            words = [r[0] for r in cur.fetchall()]
        words = [w for w in words if w not in exclude]
        random.shuffle(words)
        return words[:n]
    # end def get_random_words

    def get_wrong_category_words(self, category: str) -> list[str]:
        """Words flagged wrong_category for this category."""
        cols = self._columns("category_words")
        if "wrong_category" not in cols:
            return []
        with self.lock:
            cur = self.conn.cursor()
            cur.execute("""
                SELECT word FROM category_words
                WHERE category=? AND wrong_category=1
            """, (normalize_token(category),))
            return [r[0] for r in cur.fetchall()]
    # end def get_wrong_category_words

    def get_user_inappropriate_words(self, user: str) -> list[str]:
        """User-specific inappropriate words (banned across all categories for that user)."""
        user = normalize_token(user)
        with self.lock:
            cur = self.conn.cursor()
            cur.execute("""
                SELECT word FROM user_word_flags
                WHERE user=? AND inappropriate=1
            """, (user,))
            return [r[0] for r in cur.fetchall()]
    # end def get_user_inappropriate_words

    def get_banned_words_for_category(self, user: str, category: str, last_n: int = EXCLUDE_LAST_N) -> list[str]:
        """
        Banned words:
          - last N used in this category
          - wrong_category for this category
          - user-inappropriate words (global for user)

        Misspelled words are NOT banned.
        """
        category = normalize_token(category)
        last = self.get_last_n_words(category, last_n)
        wrong = self.get_wrong_category_words(category)
        user_bad = self.get_user_inappropriate_words(user)
        return list(dict.fromkeys(last + wrong + user_bad))
    # end def get_banned_words_for_category

    def upsert_category_words(self, category: str, words: list[str]):
        """Store non-duplicate words; prune to 100."""
        category = normalize_token(category)
        now = time.time()
        with self.lock:
            cur = self.conn.cursor()
            for w in words:
                w = normalize_token(w)
                cur.execute("""
                    INSERT OR IGNORE INTO category_words(category, word, created_at)
                    VALUES(?,?,?)
                """, (category, w, now))
            # prune to max 100
            cur.execute("""
                DELETE FROM category_words
                WHERE id IN (
                    SELECT id FROM category_words
                    WHERE category=?
                    ORDER BY id ASC
                    LIMIT (
                        SELECT MAX(COUNT(*) - 100, 0) FROM category_words WHERE category=?
                    )
                )
            """, (category, category))
            self.conn.commit()
    # end def upsert_category_words

    def insert_obscurity_record(self, category: str, color: str, obscurity: int, words: list[str]):
        """Store obscurity snapshot."""
        with self.lock:
            cur = self.conn.cursor()
            cur.execute("""
                INSERT INTO category_obscurity(category, color, obscurity, words_json, created_at)
                VALUES(?,?,?,?,?)
            """, (normalize_token(category), normalize_token(color).lower(), int(obscurity), json.dumps(words), time.time()))
            self.conn.commit()
    # end def insert_obscurity_record

    def bump_latest_obscurity_for_word(self, category: str, word: str, bump: int = 1):
        """Increment obscurity for most recent record containing word."""
        category = normalize_token(category)
        word = normalize_token(word)
        with self.lock:
            cur = self.conn.cursor()
            cur.execute("""
                SELECT id, obscurity, words_json
                FROM category_obscurity
                WHERE category=?
                ORDER BY id DESC
                LIMIT 30
            """, (category,))
            rows = cur.fetchall()
            for rid, ob, wjson in rows:
                try:
                    ws = json.loads(wjson)
                except Exception:
                    continue
                if word in ws:
                    new_ob = max(1, min(5, int(ob) + bump))
                    cur.execute("UPDATE category_obscurity SET obscurity=? WHERE id=?", (new_ob, rid))
                    self.conn.commit()
                    return
    # end def bump_latest_obscurity_for_word

    # ---- Flagging ----

    def flag_inappropriate_for_user(self, user: str, word: str):
        """Ban word for user across all categories."""
        user = normalize_token(user)
        word = normalize_token(word)
        with self.lock:
            cur = self.conn.cursor()
            cur.execute("""
                INSERT OR IGNORE INTO user_word_flags(user, word, inappropriate, created_at)
                VALUES(?,?,1,?)
            """, (user, word, time.time()))
            cur.execute("""
                UPDATE user_word_flags
                SET inappropriate=1, created_at=?
                WHERE user=? AND word=?
            """, (time.time(), user, word))
            self.conn.commit()
    # end def flag_inappropriate_for_user

    def flag_wrong_category(self, category: str, word: str):
        """Ban word only for this category."""
        category = normalize_token(category)
        word = normalize_token(word)
        self._add_column_if_missing("category_words", "wrong_category", "INTEGER NOT NULL DEFAULT 0")
        with self.lock:
            cur = self.conn.cursor()
            cur.execute("""
                INSERT OR IGNORE INTO category_words(category, word, created_at)
                VALUES(?,?,?)
            """, (category, word, time.time()))
            cur.execute("""
                UPDATE category_words SET wrong_category=1
                WHERE category=? AND word=?
            """, (category, word))
            self.conn.commit()
    # end def flag_wrong_category

    def flag_misspelled(self, category: str, word: str, is_misspelled: int, corrected: str | None):
        """Store misspelling result; do NOT ban."""
        category = normalize_token(category)
        word = normalize_token(word)
        corrected = normalize_token(corrected) if corrected else None
        self._add_column_if_missing("category_words", "misspelled", "INTEGER NOT NULL DEFAULT 0")
        self._add_column_if_missing("category_words", "corrected_spelling", "TEXT")
        with self.lock:
            cur = self.conn.cursor()
            cur.execute("""
                INSERT OR IGNORE INTO category_words(category, word, created_at)
                VALUES(?,?,?)
            """, (category, word, time.time()))
            cur.execute("""
                UPDATE category_words
                SET misspelled=?, corrected_spelling=?
                WHERE category=? AND word=?
            """, (int(is_misspelled), corrected, category, word))
            self.conn.commit()
    # end def flag_misspelled

    def flag_very_hard(self, category: str, word: str):
        """Mark very_hard and bump latest obscurity for that word."""
        category = normalize_token(category)
        word = normalize_token(word)
        self._add_column_if_missing("category_words", "very_hard", "INTEGER NOT NULL DEFAULT 0")
        with self.lock:
            cur = self.conn.cursor()
            cur.execute("""
                INSERT OR IGNORE INTO category_words(category, word, created_at)
                VALUES(?,?,?)
            """, (category, word, time.time()))
            cur.execute("""
                UPDATE category_words SET very_hard=1
                WHERE category=? AND word=?
            """, (category, word))
            self.conn.commit()
        self.bump_latest_obscurity_for_word(category, word, bump=1)
    # end def flag_very_hard


def get_words_for_category(self, category: str) -> list[str]:
    """All words for a category, excluding those flagged wrong_category for that category."""
    cat = normalize_token(category)
    with self.lock:
        cur = self.conn.cursor()
        cur.execute(
            """
            SELECT word FROM category_words
            WHERE category=? AND (wrong_category IS NULL OR wrong_category=0)
            ORDER BY id ASC
            """,
            (cat,)
        )
        return [r[0] for r in cur.fetchall()]
# end def get_words_for_category
    def get_random_old_words(
        self,
        category: str,
        n: int = 2,
        skip_recent: int = EXCLUDE_LAST_N,
        pool_size: int = 75,
        exclude: set[str] | None = None,
    ) -> list[str]:
        """Pick n random words from the least-recent pool (excluding the most recent skip_recent)."""
        exclude = exclude or set()
        cat = normalize_token(category)
        with self.lock:
            cur = self.conn.cursor()
            cur.execute(
                """
                SELECT word
                FROM category_words
                WHERE category=? AND COALESCE(wrong_category,0)=0 AND COALESCE(inappropriate,0)=0
                ORDER BY created_at ASC
                """,
                (cat,),
            )
            words = [normalize_token(r[0]) for r in cur.fetchall() if r and r[0]]

        words = [w for w in words if w and w not in exclude]
        if len(words) <= skip_recent:
            pool = words
        else:
            pool = words[: min(len(words) - skip_recent, pool_size)]

        random.shuffle(pool)
        return pool[:n]
    # end def get_random_old_words


def list_categories(self, min_words: int = 4) -> list[str]:
    """List distinct categories that have at least min_words usable words."""
    with self.lock:
        cur = self.conn.cursor()
        cur.execute(
            """
            SELECT category
            FROM category_words
            WHERE COALESCE(wrong_category,0)=0 AND COALESCE(inappropriate,0)=0
            GROUP BY category
            HAVING COUNT(DISTINCT word) >= ?
            ORDER BY category
            """,
            (int(min_words),),
        )
        return [normalize_token(r[0]) for r in cur.fetchall() if r and r[0]]
# end def list_categories

# end class DB
