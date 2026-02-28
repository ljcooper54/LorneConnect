# Copyright 2025 H2so4 Consulting LLC
# File: App/ui_game_actions.py
# This module implements user actions for the PuzzleGame UI.

from __future__ import annotations

import tkinter as tk
from tkinter import messagebox

from .utils import normalize_token
from .ui_game_render import refresh_tile_visuals, fmt_tile, render_board
from .ui_game_hints import clear_hint_selection


# This gets the category string for a given word, if known. (Start)
def _category_for_word(game, word: str) -> str:
    word_n = normalize_token(word or "")
    if not word_n:
        return ""
    # end if

    g = getattr(game, "group_by_word", {}).get(word)
    if isinstance(g, dict):
        return g.get("category", "") or ""
    # end if

    # Fallback: scan groups. (Start)
    for grp in getattr(game, "groups", []) or []:
        try:
            if word in grp.get("words", []):
                return grp.get("category", "") or ""
            # end if
        except Exception:
            continue
        # end try/except
    # end for

    return ""
# end def _category_for_word  # _category_for_word


# This opens the right-click flag menu for a specific word. (Start)
def _open_flag_menu(game, event, word: str) -> None:
    word = normalize_token(word or "")
    if not word:
        return
    # end if

    category = _category_for_word(game, word)

    menu = tk.Menu(game.root, tearoff=0)
    menu.add_command(label="Inappropriate", command=lambda: _flag_inappropriate(game, word))
    menu.add_command(label="Wrong Category", command=lambda: _flag_wrong_category(game, category, word))
    menu.add_command(label="Too Hard", command=lambda: _flag_too_hard(game, word))
    menu.add_command(label="Too Ambiguous", command=lambda: _flag_too_ambiguous(game, category, word))

    try:
        menu.tk_popup(event.x_root, event.y_root)
    finally:
        menu.grab_release()
    # end try/finally
# end def _open_flag_menu  # _open_flag_menu


# This opens the right-click flag menu for an unsolved tile by index. (Start)
def on_right_click(game, event, idx: int) -> None:
    if idx < 0 or idx >= len(game.unsolved_words):
        return
    # end if
    _open_flag_menu(game, event, game.unsolved_words[idx])
# end def on_right_click  # on_right_click


# This opens the right-click flag menu for a solved tile by word. (Start)
def on_right_click_word(game, event, word: str) -> None:
    _open_flag_menu(game, event, word)
# end def on_right_click_word  # on_right_click_word


# This toggles user selection unless tile is currently hinted-selected. (Start)
def toggle_selection(game, idx: int) -> None:
    if idx in game.hint_selected_idxs:
        return
    # end if

    if idx in game.selected_idxs:
        game.selected_idxs.remove(idx)
    else:
        game.selected_idxs.add(idx)
    # end if

    refresh_tile_visuals(game)
# end def toggle_selection  # toggle_selection


# This checks selected words against groups and advances solved state. (Start)
def check_selection(game) -> None:
    if len(game.selected_idxs) != 4:
        messagebox.showinfo("Select", "Must select 4 tiles.", parent=game.root)
        return
    # end if

    selected_words = [game.unsolved_words[i] for i in sorted(game.selected_idxs)]

    for g in game.groups:
        if g in game.solved_groups:
            continue
        # end if

        if set(selected_words) == set(g["words"]):
            game.solved_groups.append(g)

            for w in list(selected_words):
                if w in game.unsolved_words:
                    game.unsolved_words.remove(w)
                # end if
            # end for

            game.selected_idxs.clear()
            clear_hint_selection(game)

            game.status.config(text="Correct!")
            render_board(game)

            if len(game.solved_groups) == len(game.groups):
                game.status.config(text="You solved it!")
                try:
                    game.db.inc_won(game.user)
                except Exception:
                    pass
                # end try/except
            # end if

            return
        # end if
    # end for

    game.status.config(text="Not a group. Try again.")
    game.selected_idxs.clear()
    clear_hint_selection(game)
    refresh_tile_visuals(game)
# end def check_selection  # check_selection


# This flags a word as inappropriate for the current user. (Start)
def _flag_inappropriate(game, word: str) -> None:
    game.db.flag_inappropriate_for_user(game.user, word)
    messagebox.showinfo("Flagged", f"Inappropriate for you:\n{fmt_tile(word)}", parent=game.root)
# end def _flag_inappropriate  # _flag_inappropriate


# This flags a word as too hard for the current user. (Start)
def _flag_too_hard(game, word: str) -> None:
    game.db.flag_too_hard_for_user(game.user, word)
    messagebox.showinfo("Flagged", f"Too hard for you:\n{fmt_tile(word)}", parent=game.root)
# end def _flag_too_hard  # _flag_too_hard


# This flags a word as wrong category globally for that category. (Start)
def _flag_wrong_category(game, category: str, word: str) -> None:
    if not normalize_token(category):
        messagebox.showwarning("Flag", "Unknown category for this tile.", parent=game.root)
        return
    # end if

    game.db.flag_wrong_category(category, word)
    messagebox.showinfo("Flagged", f"Wrong category:\n{fmt_tile(word)}\nCategory: {category}", parent=game.root)
# end def _flag_wrong_category  # _flag_wrong_category


# This flags a word as too ambiguous globally for that category. (Start)
def _flag_too_ambiguous(game, category: str, word: str) -> None:
    if not normalize_token(category):
        messagebox.showwarning("Flag", "Unknown category for this tile.", parent=game.root)
        return
    # end if

    game.db.flag_too_ambiguous(category, word)
    messagebox.showinfo("Flagged", f"Too ambiguous:\n{fmt_tile(word)}\nCategory: {category}", parent=game.root)
# end def _flag_too_ambiguous  # _flag_too_ambiguous


# This calls controller on_done(False). (Start)
def quit_game(game) -> None:
    game.on_done(False)
# end def quit_game  # quit_game


# This returns to category selection (new categories). (Start)
def new_categories(game) -> None:
    game.on_done(True)
# end def new_categories  # new_categories
