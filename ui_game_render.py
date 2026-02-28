# File: App/ui_game_render.py | Created/Modified: 2026-02-26
# Copyright 2025 H2so4 Consulting LLC
"""Rendering + visuals for PuzzleGame.

Fix #1 (macOS Tk selection reliability):
- Do NOT use highlightbackground/highlightcolor as the primary selection cue.
  On macOS Tk, highlight borders often behave like focus rings and can render
  partially (L-shape) or only for the focused widget.
- Instead, each tile is a frame "border" whose background we control, with an
  inner label for text. Selection/hint/solved becomes stable and persistent.

Also:
- Shuffle unsolved tiles so categories are scattered.
- Larger board: bigger tiles + spacing, without geometry "jump" when selected.
"""

from __future__ import annotations

import random
import tkinter as tk

from .utils import split_camel_case_display


# This formats tile text (token-cap + single spaces). (Start)
def fmt_tile(raw: str) -> str:
    s = split_camel_case_display(raw or "")
    parts = [p for p in s.split() if p]

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

    # Solved rows. (Start)
    for g in game.solved_groups:
        row = tk.Frame(game.solved_frame)
        row.pack(pady=(0, 8), fill=tk.X)

        header = tk.Label(row, text=g["category"], font=("Helvetica", 12, "bold"))
        header.pack(anchor="w")

        tiles_row = tk.Frame(row)
        tiles_row.pack()

        bg = game.COLORS.get(g.get("color", "yellow"), game.GREY_BG)
        for wtxt in g["words"]:
            lbl = tk.Label(
                tiles_row,
                text=fmt_tile(wtxt),
                width=20,
                height=2,
                bg=bg,
                relief=tk.GROOVE,
                wraplength=160,
                justify="center",
                anchor="center",
            )
            lbl.bind("<Button-3>", lambda e, w=wtxt: game.right_click_word(e, w))
            lbl.bind("<Button-2>", lambda e, w=wtxt: game.right_click_word(e, w))
            lbl.bind("<Control-Button-1>", lambda e, w=wtxt: game.right_click_word(e, w))
            lbl.pack(side=tk.LEFT, padx=4, pady=3)
        # end for
    # end for
    # end solved rows

    # Shuffle unsolved words to scatter categories. (Start)
    random.shuffle(game.unsolved_words)
    # end shuffle

    # Unsolved grid. (Start)
    for i, wtxt in enumerate(game.unsolved_words):
        r = i // 4
        c = i % 4

        # Outer "border" frame controls outline color and never changes size. (Start)
        border = tk.Frame(
            game.grid_frame,
            bg=game.TILE_BG,
            bd=0,
            highlightthickness=0,
        )
        border.grid(row=r, column=c, padx=10, pady=10, sticky="nsew")
        # end border frame

        # Inner label for the text; padding creates a constant border thickness. (Start)
        inner = tk.Label(
            border,
            text=fmt_tile(wtxt),
            width=20,
            height=4,
            bg=game.TILE_BG,
            fg="black",
            font=("Helvetica", 14, "bold"),
            wraplength=180,
            justify="center",
            anchor="center",
            relief=tk.FLAT,
            bd=0,
            padx=10,
            pady=10,
        )
        inner.pack(fill="both", expand=True, padx=4, pady=4)
        # end inner label

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
    try:
        game.root.geometry("")
    except Exception:
        pass
    # end try/except
# end def render_board  # render_board
