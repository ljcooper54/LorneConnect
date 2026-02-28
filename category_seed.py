# File: App/category_seed.py | Created/Modified: 2026-02-26
# Copyright 2025 H2so4 Consulting LLC
"""Category seeding.

Rules:
- DB-first: if category already has enough words, do nothing.
- If it does not, call OpenAI to fetch up to MAX_WORDS terms (multi-word allowed),
  store them, and STOP once we have >= MIN_USABLE unique terms from any single call.

DEBUG:
If env DEBUG is True/true/1:
- Print every OpenAI call and stats (including obscurity distributions),
  with timestamp + module name.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime
from typing import Callable, Dict, List, Tuple

from .generator_client import OpenAIJSONClient
from .utils import normalize_token


ProgressCB = Callable[[str], None]


# This exception indicates a category cannot be seeded to a playable level. (Start)
@dataclass(frozen=True)
class CategoryTooNarrowError(RuntimeError):
    """Raised when OpenAI cannot provide enough usable words for a category."""

    category: str
    usable_count: int
    note: str = ""
# end class CategoryTooNarrowError  # CategoryTooNarrowError


# This CategorySeeder seeds vocab for categories via OpenAI. (Start)
class CategorySeeder:
    """Seeds category vocab via OpenAI only when needed."""

    MAX_WORDS = 100
    MIN_USABLE = 25
    MAX_ATTEMPTS = 3

    # This initializes the seeder with DB and OpenAI JSON client. (Start)
    def __init__(self, db):
        self.db = db
        self.client = OpenAIJSONClient()
        self._module = __name__.split(".")[-1]
    # end def __init__  # __init__

    # This returns True if DEBUG env is enabled. (Start)
    def _debug_enabled(self) -> bool:
        v = os.environ.get("DEBUG", "")
        return v.strip().casefold() in {"1", "true", "yes", "y", "on"}
    # end def _debug_enabled  # _debug_enabled

    # This formats a debug prefix with timestamp + module name. (Start)
    def _dbg_prefix(self) -> str:
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        return f"[{ts}][{self._module}][DEBUG]"
    # end def _dbg_prefix  # _dbg_prefix

    # This prints a debug line if enabled. (Start)
    def _dbg(self, msg: str) -> None:
        if self._debug_enabled():
            print(f"{self._dbg_prefix()} {msg}")
        # end if
    # end def _dbg  # _dbg

    # This normalizes a term while preserving internal spaces (multi-word allowed). (Start)
    def _norm_term(self, s: str) -> str:
        w = normalize_token(s)
        w = " ".join(w.split())  # collapse whitespace only
        return w
    # end def _norm_term  # _norm_term

    # This counts currently usable words for the user/category (no recent exclusion). (Start)
    def _usable_count(self, user: str, category: str) -> int:
        try:
            pairs = self.db.get_usable_words(category, user, recent_n=0, exclude_words=set())
            return int(len(pairs))
        except Exception:
            return 0
        # end try/except
    # end def _usable_count  # _usable_count

    # This builds the OpenAI prompt (STRICT JSON only). (Start)
    def _seed_prompt(self, category: str) -> str:
        return f"""
Return STRICT JSON only. No markdown. No commentary.

Generate up to {self.MAX_WORDS} UNIQUE terms strongly associated with: "{category}"

Rules:
- Terms may be 1 to 3 words (multi-word allowed).
- Avoid duplicates ignoring case and whitespace.
- Each term gets obscurity 1-4 (1 most common, 4 most obscure).
- Avoid offensive/inappropriate terms.

Schema:
{{
  "items": [ {{ "word": "term", "obscurity": 1 }} , ... ],
  "note": "optional short note"
}}
""".strip()
    # end def _seed_prompt  # _seed_prompt

    # This prints OpenAI stats when DEBUG is enabled. (Start)
    def _debug_print_stats(
        self,
        category: str,
        attempt: int,
        raw_len: int,
        invalid: int,
        dupes: int,
        raw_counts: Dict[int, int],
        kept_counts: Dict[int, int],
        kept_len: int,
        note: str,
    ) -> None:
        if not self._debug_enabled():
            return
        # end if
        self._dbg(f"OpenAI seed call category='{category}' attempt={attempt}/{self.MAX_ATTEMPTS}")
        self._dbg(f" raw_items={raw_len} invalid={invalid} dupes_removed={dupes} kept_unique={kept_len}")
        self._dbg(f" raw_by_obscurity={raw_counts} kept_by_obscurity={kept_counts}")
        if note:
            self._dbg(f" note='{note}'")
        # end if
    # end def _debug_print_stats  # _debug_print_stats

    # This ensures a category has enough words to play (>= MIN_USABLE). (Start)
    def ensure_category_playable(self, user: str, category: str, progress_cb: ProgressCB | None = None) -> None:
        cat = normalize_token(category)
        if not cat:
            raise CategoryTooNarrowError(category=cat, usable_count=0, note="Empty category.")
        # end if

        # DB-first. (Start)
        usable_before = self._usable_count(user, cat)
        if usable_before >= self.MIN_USABLE:
            return
        # end if
        # end DB-first

        removed_dupes_total = 0
        removed_invalid_total = 0
        last_note = ""

        for attempt in range(1, self.MAX_ATTEMPTS + 1):
            if progress_cb:
                progress_cb(f"Retrieving words for: {cat} (attempt {attempt}/{self.MAX_ATTEMPTS})")
            # end if

            self._dbg(f"OpenAI call: seed words for category='{cat}' attempt={attempt}")

            payload = self.client.call_json(self._seed_prompt(cat), temperature=0.25)
            items = payload.get("items", [])
            note = payload.get("note", "")
            last_note = normalize_token(note) if isinstance(note, str) else ""

            if not isinstance(items, list):
                raise CategoryTooNarrowError(category=cat, usable_count=usable_before, note="Missing 'items' list.")
            # end if

            # Normalize + de-dupe (case/whitespace-insensitive). (Start)
            seen: set[str] = set()
            out: List[Tuple[str, int]] = []

            raw_counts: Dict[int, int] = {1: 0, 2: 0, 3: 0, 4: 0}
            kept_counts: Dict[int, int] = {1: 0, 2: 0, 3: 0, 4: 0}

            invalid = 0
            dupes = 0

            for it in items:
                if not isinstance(it, dict):
                    invalid += 1
                    continue
                # end if

                w = self._norm_term(it.get("word", ""))
                if not w:
                    invalid += 1
                    continue
                # end if

                if len(w) > 48:
                    invalid += 1
                    continue
                # end if

                try:
                    o = int(it.get("obscurity", 2))
                except Exception:
                    o = 2
                # end try/except
                o = max(1, min(4, o))
                raw_counts[o] = raw_counts.get(o, 0) + 1

                k = " ".join(w.casefold().split())
                if k in seen:
                    dupes += 1
                    continue
                # end if
                seen.add(k)

                out.append((w, o))
                kept_counts[o] = kept_counts.get(o, 0) + 1
            # end for

            removed_invalid_total += invalid
            removed_dupes_total += dupes

            self._debug_print_stats(
                category=cat,
                attempt=attempt,
                raw_len=len(items),
                invalid=invalid,
                dupes=dupes,
                raw_counts=raw_counts,
                kept_counts=kept_counts,
                kept_len=len(out),
                note=last_note,
            )
            # end normalize

            if out:
                self.db.insert_vocab_batch(cat, out[: self.MAX_WORDS])
            # end if

            # STOP if the DB is now playable, even if this single call returned fewer than MIN_USABLE. (Start)
            usable_now = self._usable_count(user, cat)
            if usable_now >= self.MIN_USABLE:
                return
            # end if
        # end for

        note_bits = []
        if last_note:
            note_bits.append(last_note)
        note_bits.append(f"removed duplicates={removed_dupes_total}, removed invalid={removed_invalid_total}")
        raise CategoryTooNarrowError(category=cat, usable_count=self._usable_count(user, cat), note="; ".join(note_bits))
    # end def ensure_category_playable  # ensure_category_playable

# end class CategorySeeder  # CategorySeeder
