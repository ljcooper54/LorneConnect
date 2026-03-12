# File: App/ui_game_render.py | Created/Modified: 2026-03-12
# Copyright 2025 H2so4 Consulting LLC
"""Rendering + visuals for PuzzleGame.

Fixes:
- Keep the active board in a 4-column grid with equal column weights.
- Use stable tile sizing that fits four columns without clipping the fourth column.
- Recompute the top-level minimum size from actual rendered content after each board refresh.
"""

from __future__ import annotations

import random
import tkinter as tk

from .tile_text import tile_display_words
from .utils import split_camel_case_display


# This formats tile text (token-cap + single spaces). (Start)
def fmt_tile(raw: str) -> str:
    s = split_camel_case_display(raw or "")
    parts = [p for p in s.split() if p]

    # This capitalizes a single token without altering the rest. (Start)
    def cap_token(t: str) -> str:
        if not t:
            return t
        return t[0].upper() + t[1:]
    # end def cap_token  # cap_token

    return " ".join(cap_token(p) for p in parts)
# end def fmt_tile  # fmt_tile


# This refreshes selection/hint visuals without changing widget geometry. (Start)
def refresh_tile_visuals(game) -> None:
    for i, tile in enumerate(game.tile_widgets):
        border = tile["border"]
        inner = tile["inner"]

        base_bg = game.tile_base_bg.get(i, game.TILE_BG)

        # Priority: hint-selected > selected > default. (Start)
        if i in game.hint_selected_idxs:
            border.config(bg=game.HINT_OUTLINE)
            inner.config(bg=base_bg)
            continue
        # end if

        if i in game.selected_idxs:
            border.config(bg=game.SEL_OUTLINE)
            inner.config(bg=game.SEL_BG)
        else:
            border.config(bg=base_bg)
            inner.config(bg=base_bg)
        # end if
        # end priority
    # end for
# end def refresh_tile_visuals  # refresh_tile_visuals


# This renders the solved rows and the unsolved grid. (Start)
def render_board(game) -> None:
    for w in game.solved_frame.winfo_children():
        w.destroy()
    # end for
    for w in game.grid_frame.winfo_children():
        w.destroy()
    # end for

    game.tile_widgets = []
    game.tile_base_bg = {}

    # Build per-word display labels (minimized) for this puzzle. (Start)
    display_by_word: dict[str, str] = {}
    for g in game.groups:
        words = list(g.get("words", []))
        if len(words) != 4:
            continue
        d1, d2, d3, d4 = tile_display_words(g.get("category", ""), words[0], words[1], words[2], words[3])
        display_by_word[words[0]] = d1
        display_by_word[words[1]] = d2
        display_by_word[words[2]] = d3
        display_by_word[words[3]] = d4
    # end for

    # Collision handling: revert colliding display strings to the original raw token. (Start)
    key_to_words: dict[str, list[str]] = {}
    for raw, disp in display_by_word.items():
        k = (disp or "").strip().casefold()
        key_to_words.setdefault(k, []).append(raw)
    # end for

    for k, raws in key_to_words.items():
        if not k:
            continue
        if len(raws) > 1:
            for raw in raws:
                display_by_word[raw] = raw
            # end for
        # end if
    # end for
    # end collision handling

    # Solved rows. (Start)
    for solved_idx, g in enumerate(game.solved_groups):
        row = tk.Frame(game.solved_frame)
        row.grid(row=solved_idx, column=0, sticky="ew", pady=(0, 8))
        row.grid_columnconfigure(0, weight=1)

        header = tk.Label(row, text=g["category"], font=("Helvetica", 12, "bold"))
        header.grid(row=0, column=0, sticky="w")

        tiles_row = tk.Frame(row)
        tiles_row.grid(row=1, column=0, sticky="ew")
        for col in range(4):
            tiles_row.grid_columnconfigure(col, weight=1, uniform="solvedtile")
        # end for

        bg = game.COLORS.get(g.get("color", "yellow"), game.GREY_BG)
        for col, wtxt in enumerate(g["words"]):
            lbl = tk.Label(
                tiles_row,
                text=fmt_tile(display_by_word.get(wtxt, wtxt)),
                width=18,
                height=2,
                bg=bg,
                relief=tk.GROOVE,
                padx=6,
                pady=4,
            )
            lbl.bind("<Button-3>", lambda e, w=wtxt: game.right_click_word(e, w))
            lbl.bind("<Button-2>", lambda e, w=wtxt: game.right_click_word(e, w))
            lbl.bind("<Control-Button-1>", lambda e, w=wtxt: game.right_click_word(e, w))
            lbl.grid(row=0, column=col, padx=4, pady=3, sticky="ew")
        # end for
    # end for
    # end solved rows

    # Shuffle unsolved words to scatter categories. (Start)
    random.shuffle(game.unsolved_words)
    # end shuffle

    # Unsolved grid. (Start)
    for row in range(4):
        game.grid_frame.grid_rowconfigure(row, weight=1)
    # end for

    for i, wtxt in enumerate(game.unsolved_words):
        r = i // 4
        c = i % 4

        border = tk.Frame(
            game.grid_frame,
            bg=game.TILE_BG,
            bd=0,
            highlightthickness=0,
        )
        border.grid(row=r, column=c, padx=6, pady=4, sticky="nsew")

        inner = tk.Label(
            border,
            text=fmt_tile(display_by_word.get(wtxt, wtxt)),
            width=18,
            height=2,
            bg=game.TILE_BG,
            fg="black",
            font=("Helvetica", 14, "bold"),
            wraplength=150,
            justify="center",
            anchor="center",
            relief=tk.FLAT,
            bd=0,
            padx=6,
            pady=4,
        )
        inner.pack(fill="both", expand=True, padx=4, pady=4)

        # Bind clicks on BOTH widgets so selection is robust. (Start)
        for widget in (border, inner):
            widget.bind("<Button-1>", lambda _e, idx=i: game.toggle(idx))
            widget.bind("<Button-3>", lambda e, idx=i: game.right_click(e, idx))
            widget.bind("<Control-Button-1>", lambda e, idx=i: game.right_click(e, idx))
            widget.bind("<Button-2>", lambda e, idx=i: game.right_click(e, idx))
        # end for

        game.tile_widgets.append({"border": border, "inner": inner})
        game.tile_base_bg[i] = game.TILE_BG
    # end for
    # end grid

    refresh_tile_visuals(game)
    game.root.update_idletasks()
    sync = getattr(game, "_sync_window_to_content", None)
    if callable(sync):
        sync(set_geometry=False)
    # end if
# end def render_board  # render_board
