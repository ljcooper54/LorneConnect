# File: App/ui_game_hints.py | Created/Modified: 2026-02-26
# Copyright 2025 H2so4 Consulting LLC
"""Progressive hint logic for PuzzleGame.

Sequence per spec:
1) Show category name
2..5) Select + color next tile in that category (up to 4)
After 4 hinted tiles selected: next press clears hinted (incomplete) tiles, greys them, and starts next category.
"""

from __future__ import annotations

from tkinter import messagebox

from .utils import normalize_token
from .ui_game_render import refresh_tile_visuals


# This returns unsolved groups (not in solved_groups). (Start)
def unsolved_groups(game) -> list[dict]:
    return [g for g in game.groups if g not in game.solved_groups]
# end def unsolved_groups  # unsolved_groups


# This clears current hint selection (unselect + grey). (Start)
def clear_hint_selection(game) -> None:
    for idx in list(game.hint_selected_idxs):
        game.tile_base_bg[idx] = game.GREY_BG
        if idx in game.selected_idxs:
            game.selected_idxs.remove(idx)
        # end if
    # end for

    game.hint_selected_idxs.clear()
    game.hint_progress_count = 0
    game.hint_category_key = None
    refresh_tile_visuals(game)
# end def clear_hint_selection  # clear_hint_selection


# This chooses the next group to hint. (Start)
def choose_next_hint_group(game) -> dict | None:
    unsolved = unsolved_groups(game)
    if not unsolved:
        return None
    # end if

    board = set(game.unsolved_words)
    for g in unsolved:
        if all(w in board for w in g["words"]):
            return g
        # end if
    # end for

    return unsolved[0]
# end def choose_next_hint_group  # choose_next_hint_group


# This performs the progressive hint press behavior. (Start)
def hint_progressive(game) -> None:
    # Completed hint sequence -> clear and continue same press into next category-name step. (Start)
    if game.hint_category_key and game.hint_progress_count >= 4:
        clear_hint_selection(game)
    # end if
    # end clear

    # Step 1: choose category and show name. (Start)
    if not game.hint_category_key:
        g = choose_next_hint_group(game)
        if not g:
            messagebox.showinfo("Hint", "No remaining categories to hint.", parent=game.root)
            return
        # end if

        game.hint_category_key = normalize_token(g["category"])
        game.hint_progress_count = 0
        game.status.config(text=f"Hint: {g['category']}")
        messagebox.showinfo("Hint", f"Category: {g['category']}", parent=game.root)
        return
    # end if
    # end step 1

    # Identify active group by category (case/whitespace-insensitive via normalize_token+casefold). (Start)
    active_group = None
    for g in game.groups:
        if normalize_token(g["category"]).casefold() == normalize_token(game.hint_category_key).casefold():
            active_group = g
            break
        # end if
    # end for
    if not active_group:
        clear_hint_selection(game)
        game.status.config(text="Hint reset.")
        return
    # end if
    # end identify group

    # Find remaining tiles in that group still on board. (Start)
    word_to_idx = {w: i for i, w in enumerate(game.unsolved_words)}
    remaining = []
    for w in active_group["words"]:
        if w in word_to_idx:
            idx = word_to_idx[w]
            if idx not in game.hint_selected_idxs:
                remaining.append(idx)
            # end if
        # end if
    # end for
    if not remaining:
        clear_hint_selection(game)
        game.status.config(text="Hint: no remaining tiles in that category.")
        return
    # end if
    remaining.sort()
    next_idx = remaining[0]
    # end find remaining

    # Apply category color + select. (Start)
    color_name = active_group.get("color", "yellow")
    color_bg = game.COLORS.get(color_name, game.GREY_BG)

    game.tile_base_bg[next_idx] = color_bg
    game.hint_selected_idxs.add(next_idx)
    game.selected_idxs.add(next_idx)
    game.hint_progress_count += 1

    game.status.config(text=f"Hint: {active_group['category']} ({game.hint_progress_count}/4)")
    refresh_tile_visuals(game)
    # end apply
# end def hint_progressive  # hint_progressive
