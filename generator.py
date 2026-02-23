# Copyright 2025 H2so4 Consulting LLC
from __future__ import annotations
"""Puzzle generation logic."""

import os
import json
import re
import time
import random

from openai import OpenAI

from .constants import EXCLUDE_LAST_N
from .utils import normalize_token, is_single_token
from .db import DB
from .debug import debug_log_openai
from .constants import DEBUG_USERNAME

class PuzzleGenerator:
    """Generates puzzles via OpenAI (gpt-4o-mini)."""

    def __init__(self, db: DB):
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise RuntimeError("Missing OPENAI_API_KEY in environment (.env or export).")
        self.client = OpenAI(api_key=api_key)
        self.db = db

    def _call_json(self, messages, temperature=0.7):
        """Call Chat Completions and robustly parse JSON output (with debug logging)."""
        resp = self.client.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages,
            temperature=temperature,
            response_format={"type": "json_object"},
        )

        content = resp.choices[0].message.content or ""
        debug_log_openai(DEBUG_USERNAME or "unknown", "OK_RAW", messages, content)
        raw = content.strip()

        # First attempt: direct JSON parse
        try:
            parsed = json.loads(raw)
            debug_log_openai(DEBUG_USERNAME or "unknown", "OK_JSON", messages, content)
            return parsed
        except Exception:
            pass

        # Second attempt: extract first {...} block
        m = re.search(r"\{[\s\S]*\}", content)
        if m:
            candidate = m.group(0).strip()
            try:
                parsed = json.loads(candidate)
                debug_log_openai(DEBUG_USERNAME or "unknown", "OK_JSON_CAND", messages, content)
                return parsed
            except Exception:
                raw = candidate  # for logging

        # Log for inspection
        try:
            with open(DEBUG_LOG_FILE, "a", encoding="utf-8") as f:
                f.write("\n" + "=" * 80 + "\n")
                f.write(f"TIME: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write("MESSAGES:\n")
                f.write(json.dumps(messages, indent=2) + "\n")
                f.write("RAW_CONTENT:\n")
                f.write((content or "") + "\n")
        except Exception:
            pass

        snippet = (content or "").strip().replace("\n", " ")
        snippet = snippet[:220] + ("…" if len(snippet) > 220 else "")
        debug_log_openai(DEBUG_USERNAME or "unknown", "FAIL_PARSE", messages, content, error="JSON parse failed")
        raise RuntimeError(f"Model did not return valid JSON. First 220 chars: {snippet}")
    # end def _call_json

    def _gen_categories(self, interests: list[str], excluded_subjects: list[str]):
        has_surprise = any(normalize_token(x).lower() == "surprise me!" for x in interests)
        prompt = f"""
Return JSON only: {{ "groups":[{{"category":"...","color":"yellow|green|blue|purple"}}, ...] }}

Rules:
- Exactly 4 groups; colors in order: yellow easiest, then green, blue, purple hardest.
- Categories must be specific sub-categories (2–5 words), not broad topics.
- Categories must be distinct.

Interests:
{json.dumps(interests)}

If Surprise Me is included, at least one category must NOT overlap these subjects:
{json.dumps(excluded_subjects)}
"""
        return self._call_json([{"role": "user", "content": prompt}], temperature=0.6)
    # end def _gen_categories

    def _gen_words_for_category(self, category: str, color: str, seed_words: list[str], banned_words: list[str], forbid_words: set[str]):
        seed_words = [normalize_token(w) for w in seed_words if w]
        banned_words = [normalize_token(w) for w in banned_words if w]
        prompt = f"""
Return JSON only: {{ "words":["w1","w2","w3","w4"], "obscurity": 1 }}

Category: {category}
Color: {color}

Constraints:
- Exactly 4 tiles; each tile is a single token (no spaces).
- Must be clearly associated with the category.
- Include all seed words if provided, and add exactly the remaining number of new tiles.
- Do not use any avoided words.

Seed:
{json.dumps(seed_words)}

Avoid:
{json.dumps(banned_words[:60])}
"""
        return self._call_json([{"role": "user", "content": prompt}], temperature=0.65)
    # end def _gen_words_for_category

    def _verify_group(self, category: str, words: list[str]) -> tuple[bool, str]:
        if not VERIFY_STRICT:
            return True, "verification disabled"
        prompt = f"""
Verify whether these 4 words reasonably fit the category for a Connections-style puzzle. Be strict about outright wrong facts, but allow broad/adjacent membership (roles, positions, generic elements) if they are commonly associated with the category label.

Category: {category}
Words: {json.dumps(words)}

Return JSON ONLY:
{{
  "valid": true,
  "bad_words": [],
  "reason": "short"
}}
If any word does not belong, set valid=false and list bad_words.
"""
        data = self._call_json([{"role": "user", "content": prompt}], temperature=0.0)
        valid = bool(data.get("valid", False))
        reason = str(data.get("reason", ""))
        bad = data.get("bad_words", [])
        if bad:
            reason = f"{reason} (bad_words={bad})".strip()
        return valid, reason
    # end def _verify_group

    def _repair_group(self, category: str, color: str, words: list[str], bad_words: list[str], banned_words: list[str]) -> list[str]:
        """
        Replace the flagged bad_words while keeping the other words, returning a new 4-word list.
        Enforces single-token tiles and no duplicates.
        """
        keep = [w for w in words if w not in set(bad_words)]
        need = 4 - len(keep)
        prompt = f"""
You are repairing a NYT Connections category.

Category: {category}
Difficulty color: {color}

Keep these words exactly (do not change):
{json.dumps(keep)}

Replace these words (they were judged weak fits):
{json.dumps(bad_words)}

Rules:
- Return exactly {need} replacement words.
- Each replacement must be a single token (NO spaces). Hyphen or CamelCase is allowed.
- Avoid banned words and avoid duplicates with the kept words.
- Choose replacements that are clearly and commonly associated with the category.

Banned words (never use):
{json.dumps(banned_words)}

Return JSON ONLY:
{{ "replacements": ["w1","w2"] }}
"""
        data = self._call_json([{"role":"user","content":prompt}], temperature=0.6)
        repl = [normalize_token(w) for w in data.get("replacements", [])]
        repl = [w for w in repl if w and is_single_token(w)]
        if len(repl) != need:
            raise RuntimeError("Repair did not return required replacements")
        new_words = keep + repl
        if len(new_words) != 4 or len(set(new_words)) != 4:
            raise RuntimeError("Repair produced duplicates or wrong count")
        return new_words
    # end def _repair_group

    
    def generate(self, user: str, interests: list[str], excluded_subjects: list[str], max_retries: int = 6):
        """
        Generate a puzzle with minimal API calls.

        Strategy:
        - Fill as many groups as possible from the local database (no API).
        - Only call the API for "SurpriseMe!" slots (may be >1).
        - If repeated failures occur, fall back to a single-call Option A full-puzzle generation.
        """
        # Normalize interests and count surprise slots
        norm_interests = [normalize_token(s) for s in (interests or []) if s and normalize_token(s)]
        surprise_slots = [s for s in norm_interests if s.lower() == "surpriseme!"]
        surprise_n = min(4, len(surprise_slots))

        colors = ["yellow", "green", "blue", "purple"]

        user_banned = set(self.db.get_user_inappropriate_words(user))
        used_words: set[str] = set()
        used_categories: set[str] = set()
        groups: list[dict] = []

        # --- 1) Fill from DB (no API) ---
        need_from_db = 4 - surprise_n
        if need_from_db > 0:
            candidates = self.db.list_categories(min_words=4)
            random.shuffle(candidates)

            for cat in candidates:
                if len(groups) >= need_from_db:
                    break
                if cat in used_categories:
                    continue

                banned = set(self.db.get_banned_words_for_category(user, cat)) | user_banned | used_words
                words = [w for w in self.db.get_words_for_category(cat) if w not in banned]
                # Favor variety: shuffle and take first 4
                random.shuffle(words)
                if len(words) < 4:
                    continue
                picked = [normalize_token(w) for w in words[:4]]
                if len(set(picked)) != 4:
                    continue

                used_categories.add(cat)
                used_words |= set(picked)
                groups.append(
                    {
                        "category": cat,
                        "words": picked,
                        "description": "",
                        "obscurity": 2,
                    }
                )

        # --- 2) Surprise Me groups (API only for these) ---
        # If we couldn't fill enough from DB, we will use Option A fallback.
        if len(groups) + surprise_n < 4:
            return self._generate_option_a_full(user, excluded_subjects, max_retries=max_retries)

        for _ in range(surprise_n):
            last_err = None
            for _attempt in range(max_retries):
                try:
                    g = self._gen_surprise_group(user, excluded_subjects, used_categories, used_words)
                    cat = normalize_token(g["category"])
                    words = [normalize_token(w) for w in g["words"]]
                    if not cat or len(words) != 4:
                        raise RuntimeError("Surprise group missing category or 4 words")
                    if len(set(words)) != 4:
                        raise RuntimeError("Surprise group has duplicate words")
                    if any(w in used_words for w in words):
                        raise RuntimeError("Surprise group reused a word already on the board")
                    if cat in used_categories:
                        raise RuntimeError("Surprise group reused a category already on the board")

                    # If category already exists and is large, seed with 2 old words (from the least-recent 75)
                    count = self.db.get_category_word_count(cat)
                    if count > 100:
                        banned = set(self.db.get_banned_words_for_category(user, cat)) | user_banned | used_words
                        seed = self.db.get_random_old_words(cat, n=2, skip_recent=EXCLUDE_LAST_N, pool_size=75, exclude=banned)
                        if len(seed) == 2:
                            data = self._gen_words_for_category(cat, "purple", seed, list(banned), banned)
                            words2 = [normalize_token(w) for w in data.get("words", [])]
                            if len(words2) == 4 and set(seed).issubset(set(words2)) and len(set(words2)) == 4 and not any(w in used_words for w in words2):
                                words = words2

                    # Store words + obscurity
                    obscurity = int(g.get("obscurity", 2) or 2)
                    self.db.upsert_category_words(cat, words)
                    self.db.insert_obscurity_record(cat, words, obscurity)

                    used_categories.add(cat)
                    used_words |= set(words)
                    groups.append(
                        {
                            "category": cat,
                            "words": words,
                            "description": g.get("description", "") or "",
                            "obscurity": obscurity,
                        }
                    )
                    break
                except Exception as e:
                    last_err = e
                    continue
            else:
                # Surprise group failed repeatedly; fall back to Option A full puzzle
                return self._generate_option_a_full(user, excluded_subjects, max_retries=max_retries)

        # Assign colors easiest->hardest by obscurity ascending
        groups_sorted = sorted(groups, key=lambda gg: int(gg.get("obscurity", 2)))
        for i, g in enumerate(groups_sorted):
            g["color"] = colors[i]
        return {"groups": groups_sorted}
    # end def generate


    def _gen_surprise_group(self, user: str, excluded_subjects: list[str], used_categories: set[str], used_words: set[str]) -> dict:
        """Generate a single SurpriseMe group via the API."""
        prompt = f"""
Return JSON only: {{"category":"2-5 word specific subcategory","description":"short","words":["w1","w2","w3","w4"],"obscurity":2}}

Rules:
- Category must NOT overlap these subjects: {json.dumps(excluded_subjects[:8])}
- Category must be a specific subcategory (not broad like History/Sports).
- Words must be single tokens (no spaces).
- Avoid categories already used: {json.dumps(list(used_categories)[:8])}
- Avoid words already on board: {json.dumps(list(used_words)[:16])}
"""
        return self._call_json([{"role":"user","content":prompt}], temperature=0.7)
    # end def _gen_surprise_group


    def _generate_option_a_full(self, user: str, excluded_subjects: list[str], max_retries: int = 4) -> dict:
        """Option A: single API call to generate the entire puzzle."""
        colors = ["yellow", "green", "blue", "purple"]
        user_banned = set(self.db.get_user_inappropriate_words(user))

        last_err = None
        for _ in range(max_retries):
            try:
                prompt = f"""
Return JSON only: {{"groups":[{{"category":"...","description":"...","color":"yellow|green|blue|purple","words":["w1","w2","w3","w4"],"obscurity":2}}, ...]}}

Rules:
- Exactly 4 groups; use each color exactly once.
- Each category is a specific 2-5 word subcategory.
- Each word is a single token (no spaces) and unique across all 16.
- Avoid these subjects for at least 1 group if possible: {json.dumps(excluded_subjects[:10])}
- Avoid these banned words: {json.dumps(list(user_banned)[:40])}
"""
                data = self._call_json([{"role":"user","content":prompt}], temperature=0.7)
                groups = data.get("groups", [])
                if len(groups) != 4:
                    raise RuntimeError("Option A did not return 4 groups")

                seen_words: set[str] = set()
                seen_colors: set[str] = set()
                cleaned = []
                for g in groups:
                    cat = normalize_token(g.get("category", ""))
                    color = normalize_token(g.get("color", "")).lower()
                    words = [normalize_token(w) for w in g.get("words", [])]
                    obs = int(g.get("obscurity", 2) or 2)
                    desc = g.get("description", "") or ""
                    if not cat or color not in colors:
                        raise RuntimeError("Option A missing category or color")
                    if color in seen_colors:
                        raise RuntimeError("Option A repeated a color")
                    if len(words) != 4 or len(set(words)) != 4:
                        raise RuntimeError("Option A group did not have 4 unique words")
                    if any((w in seen_words) or (w in user_banned) or (not is_single_token(w)) for w in words):
                        raise RuntimeError("Option A had invalid/duplicate/banned/non-token words")
                    seen_words |= set(words)
                    seen_colors.add(color)

                    self.db.upsert_category_words(cat, words)
                    self.db.insert_obscurity_record(cat, words, obs)

                    cleaned.append({"category": cat, "color": color, "words": words, "description": desc, "obscurity": obs})

                # sort into color order
                order = {c:i for i,c in enumerate(colors)}
                cleaned.sort(key=lambda gg: order.get(gg["color"], 9))
                return {"groups": cleaned}

            except Exception as e:
                last_err = e
                continue

        raise RuntimeError(f"Unable to generate puzzle (Option A) after retries: {last_err}")
    # end def _generate_option_a_full


    def check_spelling(self, word: str, category: str) -> dict:
        prompt = f"""
Check whether the following tile word is misspelled.

Category context: {category}
Word: {word}

Return JSON ONLY:
{{
  "is_misspelled": true,
  "suggestion": "CorrectSpellingOrNull"
}}
If correction would add spaces, return a CamelCase suggestion with no spaces.
"""
        return self._call_json([{"role": "user", "content": prompt}], temperature=0.0)
    # end def check_spelling

# end class PuzzleGenerator
