# File: App/db_stats_subjects.py | Created/Modified: 2026-02-27
# Copyright 2025 H2so4 Consulting LLC
"""User stats and subject history.

Provides:
- ensure_user_stats(user)
- inc_played(user), inc_won(user), inc_solved(user), inc_lost(user)  (compat)
- get_user_stats(user)
- add_subjects(user, subjects)
- get_subjects(user, limit)
- list_all_subjects(limit)
"""

from __future__ import annotations

from typing import Iterable

from .utils import normalize_token


# This DBStatsSubjects mixin manages per-user stats and subject history. (Start)
class DBStatsSubjects:
    """User stats + subject history."""

    # This ensures required tables exist. (Start)
    def _ensure_stats_subjects_schema(self) -> None:
        with self.lock:
            cur = self.conn.cursor()

            # user_stats (user, played, won, lost). (Start)
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS user_stats(
                    user TEXT PRIMARY KEY,
                    played INTEGER NOT NULL DEFAULT 0,
                    won INTEGER NOT NULL DEFAULT 0,
                    lost INTEGER NOT NULL DEFAULT 0
                )
                """
            )
            # end user_stats

            # subjects history. (Start)
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS subjects(
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user TEXT NOT NULL,
                    subject TEXT NOT NULL,
                    created_at REAL NOT NULL DEFAULT (strftime('%s','now'))
                )
                """
            )
            cur.execute("CREATE INDEX IF NOT EXISTS ix_subjects_user_time ON subjects(user, created_at)")
            # end subjects

            self.conn.commit()
        # end with
    # end def _ensure_stats_subjects_schema  # _ensure_stats_subjects_schema

    # This ensures a user has a stats row. (Start)
    def ensure_user_stats(self, user: str) -> None:
        self._ensure_stats_subjects_schema()

        u = normalize_token(user)
        if not u:
            return
        # end if

        with self.lock:
            cur = self.conn.cursor()
            cur.execute("INSERT OR IGNORE INTO user_stats(user, played, won, lost) VALUES(?,?,?,?)", (u, 0, 0, 0))
            self.conn.commit()
        # end with
    # end def ensure_user_stats  # ensure_user_stats

    # This increments played. (Start)
    def inc_played(self, user: str) -> None:
        self.ensure_user_stats(user)
        u = normalize_token(user)
        if not u:
            return
        # end if
        with self.lock:
            cur = self.conn.cursor()
            cur.execute("UPDATE user_stats SET played = played + 1 WHERE user=?", (u,))
            self.conn.commit()
        # end with
    # end def inc_played  # inc_played

    # This increments won (NYT calls it solved). (Start)
    def inc_won(self, user: str) -> None:
        self.ensure_user_stats(user)
        u = normalize_token(user)
        if not u:
            return
        # end if
        with self.lock:
            cur = self.conn.cursor()
            cur.execute("UPDATE user_stats SET won = won + 1 WHERE user=?", (u,))
            self.conn.commit()
        # end with
    # end def inc_won  # inc_won

    # This is a compatibility alias: inc_solved == inc_won. (Start)
    def inc_solved(self, user: str) -> None:
        self.inc_won(user)
    # end def inc_solved  # inc_solved

    # This increments lost. (Start)
    def inc_lost(self, user: str) -> None:
        self.ensure_user_stats(user)
        u = normalize_token(user)
        if not u:
            return
        # end if
        with self.lock:
            cur = self.conn.cursor()
            cur.execute("UPDATE user_stats SET lost = lost + 1 WHERE user=?", (u,))
            self.conn.commit()
        # end with
    # end def inc_lost  # inc_lost

    # This returns stats. (Start)
    def get_user_stats(self, user: str) -> dict:
        self._ensure_stats_subjects_schema()
        u = normalize_token(user)
        if not u:
            return {"played": 0, "won": 0, "lost": 0}
        # end if

        with self.lock:
            cur = self.conn.cursor()
            cur.execute("SELECT played, won, lost FROM user_stats WHERE user=?", (u,))
            row = cur.fetchone()
        # end with

        if not row:
            return {"played": 0, "won": 0, "lost": 0}
        # end if

        return {"played": int(row[0]), "won": int(row[1]), "lost": int(row[2])}
    # end def get_user_stats  # get_user_stats

    # This adds subject choices for the user. (Start)
    def add_subjects(self, user: str, subjects: Iterable[str]) -> None:
        self._ensure_stats_subjects_schema()

        u = normalize_token(user)
        if not u:
            return
        # end if

        cleaned = [normalize_token(s) for s in (subjects or []) if normalize_token(s)]
        if not cleaned:
            return
        # end if

        with self.lock:
            cur = self.conn.cursor()
            for s in cleaned:
                cur.execute("INSERT INTO subjects(user, subject) VALUES(?,?)", (u, s))
            # end for
            self.conn.commit()
        # end with
    # end def add_subjects  # add_subjects

    # This returns recent subjects (deduped, most recent first). (Start)
    def get_subjects(self, user: str, limit: int = 8) -> list[str]:
        self._ensure_stats_subjects_schema()

        u = normalize_token(user)
        if not u:
            return []
        # end if

        try:
            lim = int(limit)
        except Exception:
            lim = 8
        # end try/except
        lim = max(1, min(100, lim))

        with self.lock:
            cur = self.conn.cursor()
            cur.execute(
                """
                SELECT subject
                FROM subjects
                WHERE user=?
                ORDER BY created_at DESC, id DESC
                LIMIT ?
                """,
                (u, lim * 5),
            )
            rows = [normalize_token(r[0]) for r in cur.fetchall() if r and r[0]]
        # end with

        out: list[str] = []
        seen = set()
        for s in rows:
            k = s.casefold()
            if k in seen:
                continue
            # end if
            seen.add(k)
            out.append(s)
            if len(out) >= lim:
                break
            # end if
        # end for

        return out
    # end def get_subjects  # get_subjects

    # This lists all subjects for the Categories dialog. (Start)
    def list_all_subjects(self, limit: int = 5000) -> list[str]:
        self._ensure_stats_subjects_schema()

        try:
            lim = int(limit)
        except Exception:
            lim = 5000
        # end try/except
        lim = max(1, min(50000, lim))

        with self.lock:
            cur = self.conn.cursor()
            cur.execute(
                """
                SELECT DISTINCT subject
                FROM subjects
                WHERE subject IS NOT NULL AND TRIM(subject) <> ''
                ORDER BY subject COLLATE NOCASE ASC
                LIMIT ?
                """,
                (lim,),
            )
            return [normalize_token(r[0]) for r in cur.fetchall() if r and r[0]]
        # end with
    # end def list_all_subjects  # list_all_subjects

# end class DBStatsSubjects  # DBStatsSubjects
