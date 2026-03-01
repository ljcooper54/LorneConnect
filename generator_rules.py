# File: App/generator_rules.py | Created/Modified: 2026-02-28
# Copyright 2025 H2so4 Consulting LLC
"""Generator rules: normalization and validation.

Important:
- Words in this game may be multi-word phrases (e.g. "Thunder Bay", "Empire State").
- We validate for non-empty, distinct, and reasonably well-formed entries.
"""

from __future__ import annotations

from .utils import normalize_token


# This validates group structure and word rules. (Start)
def validate_group(category: str, words: list[str]) -> None:
    # Normalize and validate category. (Start)
    cat = normalize_token(category)
    if not cat:
        raise RuntimeError("Missing category.")
    # end if
    # end category validation

    # Validate word count + uniqueness. (Start)
    if len(words) != 4:
        raise RuntimeError(f"Category '{cat}' must have exactly 4 words.")
    # end if

    normalized = []
    for w in words:
        ww = (w or "").strip()
        if not ww:
            raise RuntimeError(f"Category '{cat}' contains an empty word.")
        # end if
        if "\n" in ww or "\r" in ww or "\t" in ww:
            raise RuntimeError(f"Word '{ww}' contains illegal whitespace.")
        # end if
        normalized.append(normalize_token(ww))
    # end for

    if len(set(normalized)) != 4:
        raise RuntimeError(f"Category '{cat}' must have exactly 4 distinct words.")
    # end if
    # end word validation
# end def validate_group  # validate_group
