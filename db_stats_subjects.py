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
# Copyright 2025 H2so4 Consulting LLC
# 2026-03-02: Added missing imports for auth hashing and reset token support.

import os
import hashlib
import base64
import hmac
import secrets
import sqlite3
import time

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

    # This ensures required user-auth tables exist. (Start)
    def _ensure_users_schema(self) -> None:
        with self.lock:
            cur = self.conn.cursor()
            cur.execute(
                '''
                CREATE TABLE IF NOT EXISTS users (
                    email TEXT PRIMARY KEY,
                    password_hash TEXT,
                    reset_token TEXT,
                    reset_created_at REAL
                )
                '''
            )
            self.conn.commit()
        # end with
    # end def _ensure_users_schema  # _ensure_users_schema

    # This normalizes an email for consistent lookups. (Start)
    def _norm_email(self, email: str) -> str:
        e = normalize_token(email).strip().lower()
        return e
    # end def _norm_email  # _norm_email

    # This returns True if the user exists in the whitelist. (Start)
    def user_exists(self, email: str) -> bool:
        self._ensure_users_schema()
        e = self._norm_email(email)
        if not e:
            return False
        # end if
        with self.lock:
            cur = self.conn.cursor()
            cur.execute("SELECT 1 FROM users WHERE email = ? LIMIT 1", (e,))
            return cur.fetchone() is not None
        # end with
    # end def user_exists  # user_exists

    # This returns the stored password hash (or None). (Start)
    def get_user_password_hash(self, email: str) -> str | None:
        self._ensure_users_schema()
        e = self._norm_email(email)
        if not e:
            return None
        # end if
        with self.lock:
            cur = self.conn.cursor()
            cur.execute("SELECT password_hash FROM users WHERE email = ? LIMIT 1", (e,))
            row = cur.fetchone()
            if not row:
                return None
            # end if
            ph = row[0]
            return ph if ph else None
        # end with
    # end def get_user_password_hash  # get_user_password_hash

    # This returns True if the user has a non-blank password set. (Start)
    def user_has_password(self, email: str) -> bool:
        ph = self.get_user_password_hash(email)
        return bool(ph and str(ph).strip())
    # end def user_has_password  # user_has_password

    # This creates a whitelisted user. Blank password leaves password_hash NULL. (Start)
    def create_user(self, email: str, password: str = "") -> None:
        self._ensure_users_schema()
        e = self._norm_email(email)
        if not e:
            raise ValueError("email is blank")
        # end if
        with self.lock:
            cur = self.conn.cursor()
            cur.execute("INSERT OR IGNORE INTO users(email, password_hash) VALUES(?, NULL)", (e,))
            self.conn.commit()
        # end with
        if password and password.strip():
            self.set_password(e, password)
        # end if
    # end def create_user  # create_user

    # This hashes a password with PBKDF2-SHA256. (Start)
    def _hash_password(self, password: str, iterations: int = 240_000) -> str:
        pw = password.encode("utf-8")
        salt = os.urandom(16)
        dk = hashlib.pbkdf2_hmac("sha256", pw, salt, iterations, dklen=32)
        return "pbkdf2_sha256$%d$%s$%s" % (
            iterations,
            base64.urlsafe_b64encode(salt).decode("ascii").rstrip("="),
            base64.urlsafe_b64encode(dk).decode("ascii").rstrip("="),
        )
    # end def _hash_password  # _hash_password

    # This verifies a password hash in pbkdf2_sha256$... format. (Start)
    def _verify_password_hash(self, password: str, stored: str) -> bool:
        try:
            parts = stored.split("$")
            if len(parts) != 4 or parts[0] != "pbkdf2_sha256":
                return False
            # end if
            iterations = int(parts[1])
            salt = base64.urlsafe_b64decode(parts[2] + "==")
            expected = base64.urlsafe_b64decode(parts[3] + "==")
            dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations, dklen=len(expected))
            return hmac.compare_digest(dk, expected)
        except Exception:
            return False
        # end try/except
    # end def _verify_password_hash  # _verify_password_hash

    # This sets the user's password. (Start)
    def set_password(self, email: str, password: str) -> None:
        self._ensure_users_schema()
        e = self._norm_email(email)
        if not e:
            raise ValueError("email is blank")
        # end if
        if not password or not password.strip():
            raise ValueError("password is blank")
        # end if
        ph = self._hash_password(password)
        with self.lock:
            cur = self.conn.cursor()
            cur.execute("UPDATE users SET password_hash = ?, reset_token = NULL, reset_created_at = NULL WHERE email = ?", (ph, e))
            if cur.rowcount == 0:
                # Not whitelisted; do not auto-create.
                raise ValueError("user not authorized")
            # end if
            self.conn.commit()
        # end with
    # end def set_password  # set_password

    # This is a compatibility alias for older UI code. (Start)
    def set_user_password(self, email: str, password: str) -> None:
        self.set_password(email, password)
    # end def set_user_password  # set_user_password

    # This verifies the user password. (Start)
    def verify_password(self, email: str, password: str) -> bool:
        stored = self.get_user_password_hash(email)
        if not stored:
            return False
        # end if
        return self._verify_password_hash(password, stored)
    # end def verify_password  # verify_password

    # This is a compatibility alias for older UI code. (Start)
    def verify_user_password(self, email: str, password: str) -> bool:
        return self.verify_password(email, password)
    # end def verify_user_password  # verify_user_password

    # This creates a reset token for a whitelisted email and returns it. (Start)
    def create_reset_token(self, email: str) -> str:
        self._ensure_users_schema()
        e = self._norm_email(email)
        if not e:
            raise ValueError("email is blank")
        # end if
        token = base64.urlsafe_b64encode(os.urandom(24)).decode("ascii").rstrip("=")
        now = float(time.time())
        with self.lock:
            cur = self.conn.cursor()
            cur.execute(
                "UPDATE users SET reset_token = ?, reset_created_at = ? WHERE email = ?",
                (token, now, e),
            )
            if cur.rowcount == 0:
                raise ValueError("user not authorized")
            # end if
            self.conn.commit()
        # end with
        return token
    # end def create_reset_token  # create_reset_token

    # This resets a password using a token and clears it after use. (Start)
    def reset_password_with_token(self, token: str, new_password: str, max_age_seconds: int = 3600) -> str | None:
        self._ensure_users_schema()
        t = normalize_token(token).strip()
        if not t:
            return None
        # end if
        with self.lock:
            cur = self.conn.cursor()
            cur.execute(
                "SELECT email, reset_created_at FROM users WHERE reset_token = ? LIMIT 1",
                (t,),
            )
            row = cur.fetchone()
        # end with
        if not row:
            return None
        # end if
        email, created_at = row[0], row[1]
        if created_at is None:
            return None
        # end if
        age = float(time.time()) - float(created_at)
        if age < 0 or age > float(max_age_seconds):
            return None
        # end if
        self.set_password(email, new_password)

        with self.lock:
            cur = self.conn.cursor()
            cur.execute("UPDATE users SET reset_token = NULL, reset_created_at = NULL WHERE email = ?", (email,))
            self.conn.commit()
        # end with
        return email
    # end def reset_password_with_token  # reset_password_with_token

# end class DBStatsSubjects  # DBStatsSubjects
