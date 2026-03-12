# 2026-03-12: Improve tile display minimization by stripping shared category-like prefix/suffix tokens (e.g. River, State) so tiles do not reveal their category.
# Copyright 2025 H2so4 Consulting LLC

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


# Common leading/trailing category nouns that often make tiles too revealing. (Start)
_GENERIC_EDGE_WORDS = {
    "river", "rivers", "state", "states", "nickname", "nicknames",
    "city", "cities", "county", "counties", "mount", "mountain", "mountains",
    "lake", "lakes", "sea", "seas", "ocean", "oceans",
    "street", "streets", "road", "roads", "avenue", "avenues",
    "president", "presidents", "king", "kings", "queen", "queens",
    "saint", "st", "fort", "ft",
}
# end _GENERIC_EDGE_WORDS  # _GENERIC_EDGE_WORDS


_ANCHOR_STOP = {
    # Common title-case words that are not proper-noun anchors.
    "a", "an", "and", "or", "of", "the", "in", "on", "to", "for", "with",
    "famous", "favorite", "things", "words", "pure", "math", "theorems", "terms",
    "us", "u.s.", "states", "state", "nicknames", "men", "women",
}


_GENERIC_CATEGORY_SUFFIX = {
    "terms", "words", "things", "places", "people", "foods", "cities",
    "movies", "books", "songs", "bands", "teams",
    "presidents", "states", "nicknames", "rivers",
}


# Normalize a string for token comparisons. (Start)
def _norm(s: str) -> str:
    s = (s or "").strip().lower()
    s = s.replace("’", "'")
    punct = string.punctuation.replace("'", "")
    s = s.translate(str.maketrans({ch: " " for ch in punct}))
    s = re.sub(r"\s+", " ", s).strip()
    return s
# end _norm


# Convert a string to comparable tokens, handling possessives. (Start)
def _tokens(s: str) -> list[str]:
    tks = _norm(s).split()
    out: list[str] = []
    for t in tks:
        if t.endswith("'s"):
            t = t[:-2]
        # end if
        out.append(t)
    # end for
    return [t for t in out if t]
# end _tokens


# Build category anchors from a category name. (Start)
def _anchors_from_name(category_name: str) -> list[list[str]]:
    cat = (category_name or "").strip()
    if not cat:
        return []
    # end if

    # Only use proper-noun-ish anchors: significant tokens from the category name.
    words = re.findall(r"[A-Za-z']+", cat.replace("’", "'"))
    anchors: list[list[str]] = []
    for w in words:
        if not w:
            continue
        # end if
        w_norm = _norm(w)
        if not w_norm:
            continue
        # end if
        if w_norm in _ANCHOR_STOP:
            continue
        # end if
        if w_norm in _GENERIC_CATEGORY_SUFFIX:
            continue
        # end if
        # Prefer longer anchors; keep short acronyms like US.
        if len(w_norm) < 4 and w_norm != "us":
            continue
        # end if
        anchors.append([w_norm])
    # end for
    # Deduplicate and sort longest-first.
    dedup: list[list[str]] = []
    seen = set()
    for a in anchors:
        key = tuple(a)
        if key not in seen:
            seen.add(key)
            dedup.append(a)
        # end if
    # end for
    dedup.sort(key=len, reverse=True)
    return dedup
# end _anchors_from_name


# Decide if a remainder is specific enough to be useful. (Start)
def _remainder_ok(rest: str) -> bool:
    rest_norm = _norm(rest)
    if not rest_norm:
        return False
    # end if

    toks = rest_norm.split()
    if len(toks) >= 2:
        return True
    # end if

    single = toks[0]
    if single in _GENERIC_REMAINDERS:
        return False
    # end if
    if len(single) < 4:
        return False
    # end if
    return True
# end _remainder_ok


# Strip a leading category anchor from a raw tile when the remainder is useful. (Start)
def _strip_category_anchor(category_name: str, raw_word: str) -> str:
    raw = (raw_word or "").strip()
    if not raw:
        return raw
    # end if

    raw_tokens = raw.split()
    raw_norm_tokens = _tokens(raw)
    if len(raw_norm_tokens) < 2:
        return raw
    # end if

    # Always strip a leading 'The ' from multi-word tokens when the remainder is specific enough. (Start)
    if raw_norm_tokens and raw_norm_tokens[0] == "the":
        rest = " ".join(raw.split()[1:]).strip()
        if _remainder_ok(rest):
            return rest
        # end if
    # end strip leading The  # StripThe

    anchors = _anchors_from_name(category_name)

    for a in anchors:
        if not a:
            continue
        # end if

        if raw_norm_tokens[: len(a)] == a:
            strip_n = len(a)
        elif raw_norm_tokens[: len(a) + 1] == ["the"] + a:
            strip_n = len(a) + 1
        else:
            continue
        # end if

        kept: list[str] = []
        dropped_norm = 0
        for tok in raw_tokens:
            if dropped_norm < strip_n:
                dropped_norm += max(1, len(_tokens(tok)))
                continue
            # end if
            kept.append(tok)
        # end for

        rest = " ".join(kept).strip()
        rest = re.sub(r"^[\-–—:;,.]+\s*", "", rest).strip()

        if _remainder_ok(rest):
            return rest
        # end if
        return raw
    # end for

    return raw
# end _strip_category_anchor


# Find a shared leading token among all four tiles that should be stripped. (Start)
def _shared_prefix_token(category_name: str, words: list[str]) -> str | None:
    category_tokens = set(_tokens(category_name))
    token_lists = [_tokens(w) for w in words if (w or "").strip()]
    if len(token_lists) != 4:
        return None
    # end if
    if any(len(toks) < 2 for toks in token_lists):
        return None
    # end if

    first = token_lists[0][0]
    if not all(toks[0] == first for toks in token_lists):
        return None
    # end if
    if first in {"the", "a", "an"}:
        return first
    # end if
    if first in category_tokens:
        return first
    # end if
    if first in _GENERIC_EDGE_WORDS:
        return first
    # end if
    return None
# end _shared_prefix_token


# Find a shared trailing token among all four tiles that should be stripped. (Start)
def _shared_suffix_token(category_name: str, words: list[str]) -> str | None:
    category_tokens = set(_tokens(category_name))
    token_lists = [_tokens(w) for w in words if (w or "").strip()]
    if len(token_lists) != 4:
        return None
    # end if
    if any(len(toks) < 2 for toks in token_lists):
        return None
    # end if

    last = token_lists[0][-1]
    if not all(toks[-1] == last for toks in token_lists):
        return None
    # end if
    if last in category_tokens:
        return last
    # end if
    if last in _GENERIC_EDGE_WORDS:
        return last
    # end if
    return None
# end _shared_suffix_token


# Strip one shared leading token if that makes the tile less revealing. (Start)
def _strip_shared_prefix(raw_word: str, shared_prefix: str | None) -> str:
    raw = (raw_word or "").strip()
    if not raw or not shared_prefix:
        return raw
    # end if

    raw_tokens = raw.split()
    norm_tokens = _tokens(raw)
    if len(norm_tokens) < 2:
        return raw
    # end if
    if not norm_tokens or norm_tokens[0] != shared_prefix:
        return raw
    # end if

    rest = " ".join(raw_tokens[1:]).strip()
    if _remainder_ok(rest):
        return rest
    # end if
    return raw
# end _strip_shared_prefix


# Strip one shared trailing token if that makes the tile less revealing. (Start)
def _strip_shared_suffix(raw_word: str, shared_suffix: str | None) -> str:
    raw = (raw_word or "").strip()
    if not raw or not shared_suffix:
        return raw
    # end if

    raw_tokens = raw.split()
    norm_tokens = _tokens(raw)
    if len(norm_tokens) < 2:
        return raw
    # end if
    if not norm_tokens or norm_tokens[-1] != shared_suffix:
        return raw
    # end if

    rest = " ".join(raw_tokens[:-1]).strip()
    rest = re.sub(r"\s*[\-–—:;,.]+$", "", rest).strip()
    if _remainder_ok(rest):
        return rest
    # end if
    return raw
# end _strip_shared_suffix


# Return four display strings for the four category tokens. (Start)
def tile_display_words(category_name: str, w1: str, w2: str, w3: str, w4: str) -> list[str]:
    raws = [w1, w2, w3, w4]
    stage1 = [_strip_category_anchor(category_name, w) for w in raws]

    shared_prefix = _shared_prefix_token(category_name, stage1)
    shared_suffix = _shared_suffix_token(category_name, stage1)

    out: list[str] = []
    for raw in stage1:
        disp = _strip_shared_prefix(raw, shared_prefix)
        disp = _strip_shared_suffix(disp, shared_suffix)
        out.append(disp)
    # end for
    return out
# end tile_display_words
