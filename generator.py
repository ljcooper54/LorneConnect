# Copyright 2025 H2so4 Consulting LLC
# File: App/generator.py | Created/Modified: 2026-02-27
"""Puzzle generation.

Fix:
- Auto-pad categories to 4 with 'Surprise Me!'
- Resolve 'Surprise Me!' placeholders using DB categories with enough usable words.
"""

from __future__ import annotations

import random
from typing import Dict, List, Sequence, Set, Tuple

from .utils import normalize_token


class PuzzleGenerator:
    """Builds puzzles primarily from the local DB."""

    MIN_SURPRISE_USABLE = 16  # must have at least this many usable words to be a "surprise" candidate

    def __init__(self, db):
        """Initialize PuzzleGenerator with a DB handle."""
        self.db = db
    # end def __init__  # __init__

    # This picks a random "surprise" category with enough usable words. (Start)
    def _pick_surprise_category(self, user: str, exclude: Set[str], recent_n: int) -> str:
        """Pick a random category display name not in exclude, with enough usable words."""
        # DB API is list_categories(min_words=...). It returns list[str] display names.
        all_categories = self.db.list_categories(min_words=4)
    
        exclude_cf = {e.casefold() for e in exclude}
        candidates: List[str] = []

        for disp in all_categories:
            name = normalize_token(disp)
            if not name:
                continue
            # end if
            if name.casefold() in exclude_cf:
                continue
            # end if
            usable = self.db.get_usable_words(name, user, recent_n=recent_n, exclude_words=set())
            if len(usable) >= self.MIN_SURPRISE_USABLE:
                candidates.append(name)
            # end if
        # end for

        if not candidates:
            # Fallback: allow any non-excluded category even if small.
            for disp in all_categories:
                name = normalize_token(disp)
                if name and (name.casefold() not in exclude_cf):
                    candidates.append(name)
                # end if
            # end for
        # end if

        return random.choice(candidates) if candidates else "Surprise Me!"
    # end def _pick_surprise_category  # _pick_surprise_category

    def _finalize_categories(self, user: str, interests: Sequence[str], recent_n: int) -> List[str]:
        """Normalize, pad, and resolve categories to exactly 4."""
        raw = [normalize_token(s) for s in (interests or []) if s and normalize_token(s)]
        cats = [c for c in raw if c]

        while len(cats) < 4:
            cats.append("Surprise Me!")
        # end while
        cats = cats[:4]

        resolved: List[str] = []
        exclude: Set[str] = set()

        for c in cats:
            if c.casefold().replace(" ", "") in ("surpriseme!", "surpriseme"):
                pick = self._pick_surprise_category(user=user, exclude=exclude, recent_n=recent_n)
                resolved.append(pick)
                exclude.add(pick)
            else:
                resolved.append(c)
                exclude.add(c)
            # end if/else
        # end for

        return resolved
    # end def _finalize_categories  # _finalize_categories

    def generate(self, user: str, interests: Sequence[str], recent_n: int = 0) -> Dict:
        """Generate a puzzle dict using DB words for the user and categories."""
        u = normalize_token(user)
        if not u:
            raise RuntimeError("Missing user.")
        # end if

        categories = self._finalize_categories(user=u, interests=interests, recent_n=recent_n)

        # Build per-category usable buckets by obscurity (1..4). (Start)
        per_cat: Dict[str, List[Tuple[str, int]]] = {}
        for cat in categories:
            pairs = self.db.get_usable_words(cat, u, recent_n=recent_n, exclude_words=set())
            per_cat[cat] = pairs
        # end for
        # end buckets

        # Minimal validation: must be able to pick 4 words per category
        for cat, pairs in per_cat.items():
            if len(pairs) < 4:
                raise RuntimeError(f"Not enough usable words for category '{cat}' (have {len(pairs)}; need 4).")
            # end if
        # end for

        # Pick 4 words per category (simple: random sample; keep your existing obscurity logic if you have it elsewhere). (Start)
        puzzle_rows = []
        chosen_words: List[str] = []

        for cat, pairs in per_cat.items():
            words_only = [w for (w, _o) in pairs]
            picks = random.sample(words_only, 4)
            puzzle_rows.append({"category": cat, "words": picks})
            chosen_words.extend(picks)
            self.db.record_picks(u, cat, picks)
        # end for
        # end picks

        self.db.inc_played(u)

        colors = ["yellow", "green", "blue", "purple"]
        for i, row in enumerate(puzzle_rows):
            row["color"] = colors[i % len(colors)]
        # end for

        return {"user": u, "groups": puzzle_rows, "all_words": chosen_words}
    # end def generate  # generate
# end class PuzzleGenerator  # PuzzleGenerator
