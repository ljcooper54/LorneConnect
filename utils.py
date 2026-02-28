# Copyright 2025 H2so4 Consulting LLC
# File: App/utils.py | Created/Modified: 2026-02-27
"""Utility functions."""

from __future__ import annotations

import re


def normalize_token(token: str) -> str:
    """Normalizes a token for stable comparisons (preserves spaces)."""
    if token is None:
        return ""
    return re.sub(r"\s+", " ", str(token).strip())
# end def normalize_token  # normalize_token


def normalize_category_key(category: str) -> str:
    """Normalizes a category into a canonical DB key (case/whitespace insensitive)."""
    s = normalize_token(category).casefold()
    # Keep alnum; turn others into spaces, then drop all spaces to get a compact key.
    s = re.sub(r"[^a-z0-9]+", " ", s)
    s = "".join(s.split())
    return s
# end def normalize_category_key  # normalize_category_key

# This splits CamelCase into display-friendly words. (Start)
def split_camel_case_display(text: str) -> str:
    """
    Convert:
        "JapaneseFood" -> "Japanese Food"
        "VerySpicyTunaRoll" -> "Very Spicy Tuna Roll"
        "Sushi" -> "Sushi"
        "Ice cream" -> "Ice cream"  (unchanged)
    """

    if not text:
        return ""

    # If already contains space, assume formatted. (Start)
    if " " in text:
        return " ".join(text.split())
    # end if

    import re

    # Insert space between lower->upper transitions (e.g., tunaRoll)
    s = re.sub(r"([a-z])([A-Z])", r"\1 \2", text)

    # Handle acronym transitions (e.g., XMLParser -> XML Parser)
    s = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1 \2", s)

    return s.strip()
# end def split_camel_case_display  # split_camel_case_display

def is_single_token(word: str) -> bool:
    """True if there are no spaces in the tile token."""
    w = (word or "").strip()
    return (" " not in w) and ("\t" not in w) and ("\n" not in w)
# end def is_single_token  # is_single_token
