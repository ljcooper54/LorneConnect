# File: App/generator_rules.py | Created/Modified: 2026-02-25
# Copyright 2025 H2so4 Consulting LLC
"""Generator rules: normalization and validation."""

from __future__ import annotations

from .utils import normalize_token, is_single_token


# This validates group structure and word rules. (Start)
def validate_group(category: str, words: list[str]) -> None:
    cat = normalize_token(category)
    if not cat:
        raise RuntimeError("Missing category.")
    # end if
    if len(words) != 4 or len(set(words)) != 4:
        raise RuntimeError(f"Category '{cat}' must have exactly 4 distinct words.")
    # end if
    for w in words:
        if not is_single_token(w):
            raise RuntimeError(f"Word '{w}' is not a single token.")
        # end if
    # end for
# end def validate_group  # validate_group
