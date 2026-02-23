# Copyright 2025 H2so4 Consulting LLC
from __future__ import annotations
"""Utility functions."""

import re

def normalize_token(token: str) -> str:
    """Normalizes a token for stable DB keys/comparisons."""
    if token is None:
        return ""
    return re.sub(r"\s+", " ", token.strip())
# end def normalize_token

def is_single_token(word: str) -> bool:
    """True if there are no spaces in the tile token."""
    w = (word or "").strip()
    return (" " not in w) and ("\t" not in w) and ("\n" not in w)
# end def is_single_token

def split_camel_case_display(token: str) -> str:
    """Splits CamelCase tokens for display only."""
    if not token:
        return token
    spaced = re.sub(r"(?<=[a-z])(?=[A-Z])", " ", token)
    spaced = re.sub(r"(?<=[A-Z])(?=[A-Z][a-z])", " ", spaced)
    return spaced
# end def split_camel_case_display
