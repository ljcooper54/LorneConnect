# File: App/generator.py
# Copyright 2025 H2so4 Consulting LLC
"""Puzzle generator (v3+).

Requirements implemented:
1) Category normalization: normalize_token collapses whitespace; comparisons are case-insensitive.
   - "italian food", "Italian Food", "Italian   food" all map to the same category key.

2) Surprise Me! category fill (resolved here, not in UI):
   - If user selects < 4 categories, pad with Surprise Me! placeholders.
   - For each missing category:
       a) candidates = existing categories minus explicitly-selected categories
       b) if len(candidates) > 10: randomly pick one
       c) if len(candidates) <= 10: call OpenAI to create a new category name, informed by user's categories
   - Repeat until there are 4 categories total.

3) Word selection:
   - Avoid recently-used words per user+category via DB.get_usable_words(...recent_n...).
   - Apply user-specific obscurity adjustment (Too Easy) via DB.get_user_obscurity_adjust(user, word).
   - Validate groups.

4) Difficulty distribution:
   - Exactly one Yellow, one Green, one Blue, one Purple category per puzzle.
   - Color assignment occurs AFTER the 4 categories are selected.
   - Assignment algorithm is reverse-greedy elimination with deadlock broadening:
       - Start with strict bins: Y={1}, G={2}, B={3}, P={4}
       - Eliminate categories from their worst-fit bins round-by-round.
       - When a bin has 3 rejected, the remaining category is assigned to that bin.
       - If deadlock, broaden bins once:
           Y={1,2}, G={2,3}, B={3,4}, P={4,3}
"""

from __future__ import annotations

import random
from typing import Dict, List, Sequence, Set, Tuple

from .category_seed import CategorySeeder, CategoryTooNarrowError
from .debug import debug_log
from .generator_client import OpenAIJSONClient
from .generator_rules import validate_group
from .utils import normalize_category_key, normalize_token


# This PuzzleGenerator generates Connections-style puzzles. (Start)
class PuzzleGenerator:
    """Generates 4 categories x 4 words with Surprise Me! + strict colors."""

    # This maps obscurity levels to canonical colors. (Start)
    LEVEL_TO_COLOR = {1: "Yellow", 2: "Green", 3: "Blue", 4: "Purple"}
    # end LEVEL_TO_COLOR  # LEVEL_TO_COLOR

    # This defines strict and broadened bins per spec. (Start)
    BINS_STRICT = {
        "Yellow": {1},
        "Green": {2},
        "Blue": {3},
        "Purple": {4},
    }
    BINS_BROADENED = {
        "Yellow": {1, 2},  # 1+2
        "Green": {2, 3},   # 2+3
        "Blue": {3, 4},    # 3+4
        "Purple": {4, 3},  # 4+3
    }
    # end bins  # BINS_STRICT/BINS_BROADENED

    # This initializes generator state. (Start)
    def __init__(self, db):
        self.db = db
        self.seeder = CategorySeeder(db)
        self.ai = OpenAIJSONClient(model="gpt-4o-mini")
    # end def __init__  # __init__

    # ------------------------------------------------------------
    # Surprise Me! category resolution
    # ------------------------------------------------------------

    # This returns True if a UI value represents Surprise Me!. (Start)
    def _is_surprise(self, s: str) -> bool:
        t = (s or "").strip().casefold()
        t = "".join(t.split())
        return t in {"surpriseme", "surpriseme!"}
    # end def _is_surprise  # _is_surprise

    # This normalizes a category key for stable comparisons. (Start)
    def _norm_cat(self, s: str) -> str:
        # Canonicalize categories for comparisons (case/whitespace/punct insensitive). (Start)
        return normalize_category_key(s)
        # end canonicalize
    # end def _norm_cat  # _norm_cat


    # This fetches recent subjects for the user (best effort). (Start)
    def _user_subject_history(self, user: str, limit: int = 50) -> List[str]:
        try:
            subs = self.db.get_subjects(user, limit=int(limit))
            return [normalize_token(s) for s in (subs or []) if normalize_token(s)]
        except Exception:
            return []
        # end try/except
    # end def _user_subject_history  # _user_subject_history

    # This asks OpenAI for a single new category name. (Start)
    def _ai_create_new_category(self, user: str, existing: List[str], user_hist: List[str], exclude: Set[str]) -> str | None:
        existing_norm = sorted({normalize_token(x) for x in (existing or []) if normalize_token(x)})
        user_norm = sorted({normalize_token(x) for x in (user_hist or []) if normalize_token(x)})

        prompt = (
            "Create ONE new category for a Connections-style word grouping game.\n\n"
            "Return JSON only: {\"category\": \"...\"}.\n\n"
            "Constraints:\n"
            "- Category name should be 1–5 words.\n"
            "- Do NOT repeat any existing category.\n"
            "- Avoid categories too similar to existing ones.\n\n"
            f"Existing categories (do NOT repeat): {existing_norm[:200]}\n"
            f"User '{user}' existing categories (optional guidance): {user_norm[:80]}\n"
        )

        try:
            resp = self.ai.call_json(prompt, temperature=0.6)
        except Exception as e:
            debug_log("generator", f"AI category create failed: {type(e).__name__}: {e}")
            return None
        # end try/except

        cat = normalize_token(str(resp.get("category", "")))
        if not cat:
            return None
        # end if

        ex_cf = {self._norm_cat(x) for x in (exclude or set()) if normalize_token(x)}
        if self._norm_cat(cat) in ex_cf:
            return None
        # end if

        exist_cf = {self._norm_cat(x) for x in existing_norm}
        if self._norm_cat(cat) in exist_cf:
            return None
        # end if

        return cat
    # end def _ai_create_new_category  # _ai_create_new_category

    # This picks a Surprise category per the spec. (Start)
    def _pick_surprise_category(self, user: str, explicit: Set[str], exclude: Set[str], explicit_display_cf: Set[str]) -> str:
        # Get a list of existing categories minus the ones the user explicitly selected. (Start)
        existing = [normalize_token(c) for c in self.db.list_categories(min_words=4) if normalize_token(c)]

        explicit_cf = {self._norm_cat(e) for e in (explicit or set()) if normalize_token(e)}
        exclude_cf = {self._norm_cat(e) for e in (exclude or set()) if normalize_token(e)}

        # Ensure explicit selections are always excluded from Surprise picks. (Start)
        exclude_cf |= explicit_cf
        # end ensure explicit excluded

        candidates = [
            c for c in existing
            if (self._norm_cat(c) not in explicit_cf)
            and (self._norm_cat(c) not in exclude_cf)
            and (normalize_token(c).casefold() not in (explicit_display_cf or set()))
        ]
        # end compute candidates

        # If there are > 10 candidates, randomly pick one. (Start)
        if len(candidates) > 10:
            choice = random.choice(candidates)
            debug_log("generator", f"Surprise pick (existing): '{choice}' candidates={len(candidates)}")
            return choice
        # end if > 10

        # If there are <= 10 candidates, ask OpenAI to create a new category. (Start)
        user_hist = self._user_subject_history(user=user, limit=50)
        ai_cat = self._ai_create_new_category(user=user, existing=existing, user_hist=user_hist, exclude=exclude)
        if ai_cat:
            return ai_cat
        # end if ai_cat
        # end <= 10 branch

        # Fallback: if we have any candidates, pick one; else return literal Surprise Me!. (Start)
        if candidates:
            return random.choice(candidates)
        # end if candidates

        return "Surprise Me!"
        # end fallback
    # end def _pick_surprise_category  # _pick_surprise_category

    # This normalizes/pads/resolves categories to exactly 4. (Start)
    def _finalize_categories(self, user: str, selections: Sequence[str]) -> List[str]:
        # Normalize selections while preserving order and intent. (Start)
        raw: List[str] = []
        for s in (selections or []):
            ss = (s or "").strip()
            if ss:
                raw.append(ss)
            # end if
        # end for
        # end normalize selections

        # Track explicitly-selected (non-surprise) categories for exclusion. (Start)
        explicit_norm = {normalize_token(s) for s in raw if (s and not self._is_surprise(s))}

        # Track explicit category displays (case-insensitive) to prevent Surprise from repeating them. (Start)
        explicit_display_cf = {normalize_token(s).casefold() for s in raw if (s and not self._is_surprise(s))}
        # end explicit_display_cf
        # end explicit_norm

        # Pad to 4 with Surprise Me! placeholders. (Start)
        padded: List[str] = []
        for s in raw:
            if self._is_surprise(s):
                padded.append("Surprise Me!")
            else:
                padded.append(normalize_token(s))
            # end if/else
        # end for

        while len(padded) < 4:
            padded.append("Surprise Me!")
        # end while
        padded = padded[:4]
        # end pad

        # Resolve placeholders until we have 4 concrete categories. (Start)
        resolved: List[str] = []
        used: Set[str] = set()

        for s in padded:
            if self._is_surprise(s):
                pick = self._pick_surprise_category(user=user, explicit=explicit_norm, exclude=used, explicit_display_cf=explicit_display_cf)
                resolved.append(pick)
                used.add(pick)
            else:
                if s:
                    resolved.append(s)
                    used.add(s)
                # end if
            # end if/else
        # end for
        # end resolve

        # If we still have fewer than 4, keep filling. (Start)
        while len(resolved) < 4:
            pick = self._pick_surprise_category(user=user, explicit=explicit_norm, exclude=set(resolved), explicit_display_cf=explicit_display_cf)
            resolved.append(pick)
        # end while
        # end fill

        return resolved[:4]
    # end def _finalize_categories  # _finalize_categories

    # ------------------------------------------------------------
    # Color assignment (reverse-greedy)
    # ------------------------------------------------------------

    # This computes available count per category per bin. (Start)
    def _bin_counts(self, buckets: Dict[int, List[str]], bin_levels: Set[int]) -> int:
        c = 0
        for lvl in bin_levels:
            c += len(buckets.get(lvl, []))
        # end for
        return c
    # end def _bin_counts  # _bin_counts

    # This assigns each category to a unique color bin using reverse-greedy elimination. (Start)
    def _assign_colors_reverse_greedy(self, cat_buckets: List[Dict[int, List[str]]], bins: Dict[str, Set[int]]) -> Dict[str, str]:
        colors = list(bins.keys())
        n = len(cat_buckets)
        if n != 4:
            raise RuntimeError(f"Need 4 categories for color assignment, got {n}")
        # end if

        cat_ids = [f"C{i}" for i in range(n)]

        # Precompute per-category counts per color bin. (Start)
        counts: Dict[str, Dict[str, int]] = {}
        for ci, cid in enumerate(cat_ids):
            counts[cid] = {}
            for color in colors:
                counts[cid][color] = self._bin_counts(cat_buckets[ci], bins[color])
            # end for
        # end for
        # end precompute

        # Track rejections and assignments. (Start)
        rejected: Dict[str, Set[str]] = {color: set() for color in colors}  # color -> set(category_ids rejected)
        assigned_color: Dict[str, str] = {}  # category_id -> color
        assigned_cat: Dict[str, str] = {}    # color -> category_id
        # end tracking

        # Rank colors for each category from fewest-to-most available. (Start)
        def color_rank(cid: str) -> List[str]:
            # Sort by available count ascending; ties broken by color name for stability.
            return sorted(colors, key=lambda c: (counts[cid][c], c))
        # end def color_rank

        ranks: Dict[str, List[str]] = {cid: color_rank(cid) for cid in cat_ids}
        # end ranks

        # Apply reverse-greedy elimination. (Start)
        progress = True
        round_idx = 0

        while progress and (len(assigned_color) < n):
            progress = False

            # Reject each unassigned category from its next-worst color. (Start)
            for cid in cat_ids:
                if cid in assigned_color:
                    continue
                # end if

                # Find the next color in rank list where this category is not yet rejected. (Start)
                for color in ranks[cid]:
                    if color in assigned_cat:
                        continue
                    # end if
                    if cid in rejected[color]:
                        continue
                    # end if

                    rejected[color].add(cid)
                    progress = True
                    break
                # end for
                # end pick next worst
            # end for
            # end rejection round

            # Assign any color bin that now has 3 rejected. (Start)
            for color in colors:
                if color in assigned_cat:
                    continue
                # end if

                if len(rejected[color]) >= 3:
                    remaining = [cid for cid in cat_ids if cid not in rejected[color] and cid not in assigned_color]
                    if len(remaining) == 1:
                        chosen = remaining[0]
                        assigned_cat[color] = chosen
                        assigned_color[chosen] = color
                        progress = True

                        # Mark chosen as rejected in all other unassigned colors. (Start)
                        for other in colors:
                            if other == color:
                                continue
                            # end if
                            rejected[other].add(chosen)
                        # end for
                        # end mark rejected elsewhere
                    # end if
                # end if 3 rejected
            # end for
            # end assignments

            round_idx += 1
            if round_idx > 20:
                break
            # end safety guard
        # end while
        # end elimination loop

        if len(assigned_color) != n:
            # Deadlock fallback: assign remaining colors to remaining categories. (Start)
            remaining_cats = [cid for cid in cat_ids if cid not in assigned_color]
            remaining_colors = [c for c in colors if c not in assigned_cat]

            # Assign each remaining category to the remaining color where it has the most available words. (Start)
            for cid in list(remaining_cats):
                if not remaining_colors:
                    break
                # end if

                best_color = max(remaining_colors, key=lambda c: (counts[cid].get(c, 0), c))
                assigned_color[cid] = best_color
                assigned_cat[best_color] = cid
                remaining_colors.remove(best_color)
            # end for
            # end deadlock fallback
        # end if

        # Return mapping from category_id -> color. (Start)
        return assigned_color
        # end return
    # end def _assign_colors_reverse_greedy  # _assign_colors_reverse_greedy

    # ------------------------------------------------------------
    # Core generation
    # ------------------------------------------------------------

    # This seeds and fetches buckets for a category. (Start)
    def _build_buckets_for_category(self, user: str, category: str, recent_n: int) -> Dict[int, List[str]]:
        # Ensure category has enough vocab (seed if needed). (Start)
        self.seeder.ensure_category_playable(user=user, category=category)
        # end ensure playable

        # Fetch usable words with per-user-per-category anti-repeat. (Start)
        pairs: List[Tuple[str, int]] = self.db.get_usable_words(
            category=category,
            user=user,
            recent_n=int(recent_n),
            exclude_words=set(),
        )
        # end fetch usable

        # Apply user obscurity adjustment BEFORE bucketing. (Start)
        adjusted: List[Tuple[str, int]] = []
        for (word, base_obscurity) in pairs:
            w = (word or "").strip()
            if not w:
                continue
            # end if

            try:
                base = int(base_obscurity)
            except Exception:
                base = 2
            # end try/except
            base = max(1, min(4, base))

            try:
                adj = int(self.db.get_user_obscurity_adjust(user, normalize_token(w)))
            except Exception:
                adj = 0
            # end try/except

            eff = max(1, min(4, base + adj))
            adjusted.append((w, eff))
        # end for adjustment
        # end apply adjustment

        buckets: Dict[int, List[str]] = {1: [], 2: [], 3: [], 4: []}
        for (w, eff) in adjusted:
            buckets[eff].append(w)
        # end for
        # end buckets

        return buckets
    # end def _build_buckets_for_category  # _build_buckets_for_category

    # This generates a puzzle for the given user + selected subjects. (Start)
    def generate(self, user: str, subjects: Sequence[str], recent_n: int = 20) -> Dict:
        u = normalize_token(user)
        if not u:
            raise RuntimeError("Missing user.")
        # end if

        # Resolve categories first (Surprise Me! supported). (Start)
        categories = self._finalize_categories(user=u, selections=subjects)
        # end resolve categories

        debug_log("generator", f"Generate: user='{u}' subjects={categories} recent_n={recent_n}")

        # Try a few attempts in case Surprise categories are weak for strict color assignment. (Start)
        attempts = 6
        last_error: Exception | None = None

        for attempt in range(1, attempts + 1):
            try:
                # Build word buckets for each of the 4 categories. (Start)
                cat_buckets: List[Dict[int, List[str]]] = []
                for cat in categories:
                    if self._is_surprise(cat):
                        raise RuntimeError("Unresolved Surprise category.")
                    # end if

                    buckets = self._build_buckets_for_category(user=u, category=cat, recent_n=int(recent_n))
                    cat_buckets.append(buckets)
                # end for
                # end build buckets

                if len(cat_buckets) != 4:
                    raise RuntimeError(f"Need 4 categories, got {len(cat_buckets)}")
                # end if

                # Assign colors using reverse-greedy with strict bins (deadlock fallback assigns remaining). (Start)
                assignment = self._assign_colors_reverse_greedy(cat_buckets, self.BINS_STRICT)
                bins_used = self.BINS_STRICT
                # end color assignment

                # Build groups according to assignments and bin level sets. (Start)
                groups: List[Dict] = []
                for idx in range(4):
                    cid = f"C{idx}"
                    color = assignment[cid]
                    bin_levels = bins_used[color]

                    # Create a pool from the assigned bin levels. (Start)
                    pool: List[str] = []
                    for lvl in sorted(bin_levels):
                        pool.extend(cat_buckets[idx].get(lvl, []))
                    # end for
                    # end pool creation

                    # Ensure we have enough words. (Start)
                    if len(pool) < 4:
                        raise RuntimeError(f"Not enough words in bin for {categories[idx]} color={color} pool={len(pool)}")
                    # end if

                    random.shuffle(pool)
                    selected = pool[:4]

                    # Validate the group. (Start)
                    validate_group(categories[idx], selected)
                    # end validate group

                    groups.append(
                        {
                            "category": categories[idx].strip(),
                            "category_key": normalize_token(categories[idx]),
                            "color": str(color).strip().casefold(),
                            "words": selected,
                        }
                    )
                    # end append group
                # end for
                # end build groups

                # Record picks so future games can avoid repeats. (Start)
                for g in groups:
                    self.db.record_picks(user=u, category=g["category"], words=g["words"])
                # end for
                # end record picks

                return {"user": u, "groups": groups, "_selected_subjects": categories}
                # end return success

            except Exception as e:
                last_error = e
                debug_log("generator", f"Attempt {attempt}/{attempts} failed: {type(e).__name__}: {e}")

                # Re-roll Surprise categories and try again. (Start)
                categories = self._finalize_categories(user=u, selections=subjects)
                # end reroll
                continue
            # end try/except
        # end for attempts
        # end retry loop

        raise RuntimeError(f"Puzzle generation failed after {attempts} attempts: {last_error}")
    # end def generate  # generate

# end class PuzzleGenerator  # PuzzleGenerator
