# Copyright 2025 H2so4 Consulting LLC
# 2026-03-03: Deterministic trimming: always strip leading 'The'; strip only proper-noun anchors from category; contract category=dict with TypeError otherwise.

from __future__ import annotations

import re
import string


# Generic remainder blacklist. (Start)
_GENERIC_REMAINDERS = {
    "day", "days", "time", "place", "thing", "things", "stuff",
    "fun", "park", "ride", "adventure", "story", "world", "land",
    "show", "movie", "book", "song", "game", "club", "office",
}
# end _GENERIC_REMAINDERS  # _GENERIC_REMAINDERS


_ANCHOR_STOP = {
    # Common title-case words that are not proper-noun anchors.
    "a", "an", "and", "or", "of", "the", "in", "on", "to", "for", "with",
    "famous", "favorite", "things", "words", "pure", "math", "theorems", "terms",
    "us", "u.s.", "states", "state", "nicknames", "men", "women",
}


_GENERIC_CATEGORY_SUFFIX = {
    "terms", "words", "things", "places", "people", "foods", "cities",
    "movies", "books", "songs", "bands", "teams",
    "presidents", "states", "nicknames",
}


def _norm(s: str) -> str:
    s = (s or "").strip().lower()
    s = s.replace("’", "'")
    punct = string.punctuation.replace("'", "")
    s = s.translate(str.maketrans({ch: " " for ch in punct}))
    s = re.sub(r"\s+", " ", s).strip()
    return s


def _tokens(s: str) -> list[str]:
    tks = _norm(s).split()
    out: list[str] = []
    for t in tks:
        if t.endswith("'s"):
            t = t[:-2]
        out.append(t)
    return [t for t in out if t]


def _extract_category_name(category: dict) -> str:
    if not isinstance(category, dict):
        raise TypeError(f"category must be dict, got {type(category).__name__}")

    for k in ("category", "name", "title", "display_name"):
        v = category.get(k)
        if isinstance(v, str) and v.strip():
            return v

    raise ValueError("category dict does not contain a usable category name")


def _anchors(category: dict) -> list[list[str]]:
    cat = _extract_category_name(category)
    # Only use proper-noun-ish anchors: significant tokens from the category name.
    # We treat title-cased category words as candidates but filter common/generic words.
    words = re.findall(r"[A-Za-z']+", cat.replace("’", "'"))
    anchors: list[list[str]] = []
    for w in words:
        if not w:
            continue
        w_norm = _norm(w)
        if not w_norm:
            continue
        if w_norm in _ANCHOR_STOP:
            continue
        if w_norm in _GENERIC_CATEGORY_SUFFIX:
            continue
        # Prefer longer anchors; keep short acronyms like US.
        if len(w_norm) < 4 and w_norm != "us":
            continue
        anchors.append([w_norm])
    # Deduplicate and sort longest-first.
    dedup: list[list[str]] = []
    seen = set()
    for a in anchors:
        key = tuple(a)
        if key not in seen:
            seen.add(key)
            dedup.append(a)
    dedup.sort(key=len, reverse=True)
    return dedup


def _remainder_ok(rest: str) -> bool:
    rest_norm = _norm(rest)
    if not rest_norm:
        return False

    toks = rest_norm.split()
    if len(toks) >= 2:
        return True

    single = toks[0]
    if single in _GENERIC_REMAINDERS:
        return False
    if len(single) < 6:
        return False
    return True


def tile_display_text(category: dict, raw_word: str) -> str:
    if not isinstance(category, dict):
        raise TypeError(f"category must be dict, got {type(category).__name__}")

    raw = (raw_word or "").strip()
    if not raw:
        return raw

    raw_tokens = raw.split()
    if len(raw_tokens) < 2:
        return raw

    raw_norm_tokens = _tokens(raw)
    if len(raw_norm_tokens) < 2:
        return raw

    # Always strip a leading 'The ' from multi-word tokens when the remainder is specific enough. (Start)
    if raw_norm_tokens and raw_norm_tokens[0] == "the":
        rest = " ".join(raw.split()[1:]).strip()
        if _remainder_ok(rest):
            return rest
    # end strip leading 'The'  # StripThe

    anchors = _anchors(category)

    for a in anchors:
        if not a:
            continue

        if raw_norm_tokens[: len(a)] == a:
            strip_n = len(a)
        elif raw_norm_tokens[: len(a) + 1] == ["the"] + a:
            strip_n = len(a) + 1
        else:
            continue

        kept: list[str] = []
        dropped_norm = 0
        for tok in raw_tokens:
            if dropped_norm < strip_n:
                dropped_norm += max(1, len(_tokens(tok)))
                continue
            kept.append(tok)

        rest = " ".join(kept).strip()
        rest = re.sub(r"^[\-–—:;,.]+\s*", "", rest).strip()

        if _remainder_ok(rest):
            return rest
        return raw

    return raw
