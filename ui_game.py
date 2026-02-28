# File: App/ui_game.py | Created/Modified: 2026-02-28
# Copyright 2025 H2so4 Consulting LLC
"""Game UI entry point.

This file now only contains the PuzzleGame class wiring.
Heavy logic is split into:
- ui_game_render.py (rendering + visuals + formatting)
- ui_game_actions.py (toggle/check/right-click flag menu)
- ui_game_hints.py (progressive hint logic)
"""

from __future__ import annotations

import tkinter as tk

from .db import DB
from .generator import PuzzleGenerator

from .ui_game_render import render_board
from .ui_game_actions import (
    toggle_selection,
    check_selection,
    on_right_click,
    on_right_click_word,
    new_categories,
    quit_game,
)
from .ui_game_hints import hint_progressive


# This PuzzleGame class renders and runs the puzzle UI. (Start)
class PuzzleGame:
    """Puzzle UI with selection, right-click flags, progressive hints, and solved rows."""

    COLORS = {
        "yellow": "#f7e45c",
        "green": "#7bd389",
        "blue": "#6aa9ff",
        "purple": "#c07bff",
    }

    GREY_BG = "#d0d0d0"
    TILE_BG = "white"

    SEL_BG = "#fff2cc"
    SEL_OUTLINE = "#ff9900"
    HINT_OUTLINE = "#444444"

    # This initializes the game and constructs all UI widgets. (Start)
    def __init__(
        self,
        root: tk.Tk,
        user: str,
        db: DB,
        generator: PuzzleGenerator,
        puzzle_data: dict,
        on_done,
    ):
        self.root = root
        self.user = user or ""
        self.db = db
        self.generator = generator
        self.on_done = on_done

        self.groups = puzzle_data["groups"]
        self.selected_subjects = list(puzzle_data.get("_selected_subjects") or [])

        # This preserves the original 4-subject selection for reliable restart. (Start)
        if self.selected_subjects:
            self.base_subjects = list(self.selected_subjects)
        else:
            self.base_subjects = [g.get("category", "") for g in self.groups]
        # end base_subjects  # base_subjects

        self.group_by_word: dict[str, dict] = {}
        for g in self.groups:
            for w in g["words"]:
                self.group_by_word[w] = g
            # end for
        # end for

        self.solved_groups: list[dict] = []
        all_words: list[str] = []
        for g in self.groups:
            all_words.extend(g["words"])
        # end for
        self.unsolved_words = list(all_words)

        # Selection + hint state. (Start)
        self.selected_idxs: set[int] = set()
        self.hint_category_key: str | None = None
        self.hint_progress_count: int = 0
        self.hint_selected_idxs: set[int] = set()
        # end selection + hint state

        # Root frame. (Start)
        self.frame = tk.Frame(root)
        self.frame.pack(padx=20, pady=20)
        try:
            self.frame.pack_propagate(True)
        except Exception:
            pass
        # end try/except

        self.status = tk.Label(self.frame, text="Select 4 words, then Submit.")
        self.status.pack(pady=(0, 10))

        self.solved_frame = tk.Frame(self.frame)
        self.solved_frame.pack()

        self.grid_frame = tk.Frame(self.frame)
        self.grid_frame.pack()

        controls = tk.Frame(self.frame)
        controls.pack(pady=10)

        self.submit_btn = tk.Button(controls, text="Submit", command=self.check)
        self.submit_btn.pack(side=tk.LEFT, padx=6)

        self.hint_btn = tk.Button(controls, text="Hint", command=self.hint)
        self.hint_btn.pack(side=tk.LEFT, padx=6)

        self.restart_btn = tk.Button(controls, text="Restart", command=self.restart_clicked)
        self.restart_btn.pack(side=tk.LEFT, padx=6)

        self.quit_btn = tk.Button(controls, text="Quit", command=self.quit_game)
        self.quit_btn.pack(side=tk.LEFT, padx=6)
        # end root frame

        # Tiles. (Start)
        self.tile_widgets: list[tk.Label] = []
        self.tile_base_bg: dict[int, str] = {}
        # end tiles

        render_board(self)
    # end def __init__  # __init__

    # This toggles tile selection. (Start)
    def toggle(self, idx: int) -> None:
        toggle_selection(self, idx)
    # end def toggle  # toggle

    # This checks selection against groups. (Start)
    def check(self) -> None:
        check_selection(self)
    # end def check  # check

    # This runs the progressive hint sequence. (Start)
    def hint(self) -> None:
        hint_progressive(self)
    # end def hint  # hint

    # This opens the right-click flag menu. (Start)
    def right_click(self, event, idx: int) -> None:
        on_right_click(self, event, idx)
    # end def right_click  # right_click

    # This quits the app. (Start)
    def quit_game(self) -> None:
        quit_game(self)
    # end def quit_game  # quit_game

    # This opens the right-click menu for a solved tile by word. (Start)
    def right_click_word(self, event, word: str) -> None:
        on_right_click_word(self, event, word)
    # end def right_click_word  # right_click_word

    # This handles the Restart button click. (Start)
    def restart_clicked(self) -> None:
        choice = self._ask_restart_choice()
        if choice == "continue":
            return
        # end if

        if choice == "new":
            new_categories(self)
            return
        # end if

        # choice == "restart"
        self._restart_same_categories()
    # end def restart_clicked  # restart_clicked

    # This asks the user what to do on Restart. (Start)
    def _ask_restart_choice(self) -> str:
        win = tk.Toplevel(self.root)
        win.title("Restart?")
        win.transient(self.root)
        win.grab_set()

        choice = {"v": "continue"}

        tk.Label(win, text="Are you sure?", font=("Helvetica", 12, "bold")).pack(padx=18, pady=(14, 6))
        tk.Label(win, text="Choose what you want to do:").pack(padx=18, pady=(0, 10))

        btns = tk.Frame(win)
        btns.pack(padx=18, pady=(0, 14))

        # This sets restart-choice and closes the dialog. (Start)
        def set_choice(v: str) -> None:
            choice["v"] = v
            win.destroy()
        # end def set_choice  # set_choice

        tk.Button(btns, text="Restart", width=14, command=lambda: set_choice("restart")).pack(side=tk.LEFT, padx=6)
        tk.Button(btns, text="New Categories", width=14, command=lambda: set_choice("new")).pack(side=tk.LEFT, padx=6)
        tk.Button(btns, text="Continue Game", width=14, command=lambda: set_choice("continue")).pack(side=tk.LEFT, padx=6)

        win.update_idletasks()
        win.lift()
        win.focus_force()

        self.root.wait_window(win)
        return choice["v"]
    # end def _ask_restart_choice  # _ask_restart_choice

    # This restarts with the same selected subjects but new words. (Start)
    def _restart_same_categories(self) -> None:
        subjects = list(getattr(self, "base_subjects", [])) or list(self.selected_subjects) or [g.get("category", "") for g in self.groups]

        # Ensure we always restart with 4 categories; pad with Surprise Me! if needed. (Start)
        while len(subjects) < 4:
            subjects.append("Surprise Me!")
        # end while

        # Hard reset all state that influences rendering before regeneration. (Start)
        self.groups = []
        self.group_by_word = {}
        self.unsolved_words = []
        self.tile_widgets = []
        self.tile_base_bg = {}
        # end hard reset

        # Reset state so we always get a full 4x4 board. (Start)
        self.selected_idxs = set()
        self.hint_category_key = None
        self.hint_progress_count = 0
        self.hint_selected_idxs = set()
        self.solved_groups = []
        # end reset

        try:
            puzzle = self.generator.generate(self.user, subjects, recent_n=0)
        except Exception as e:
            self.status.config(text=f"Restart failed: {type(e).__name__}: {e}")
            return
        # end try/except

        if puzzle is None:
            self.status.config(text="Restart failed: generator returned none")
            return
        # end if

        self.groups = puzzle["groups"]
        self.selected_subjects = list(puzzle.get("_selected_subjects") or subjects)

        # Keep the base subjects stable across any future gameplay mutations. (Start)
        if not getattr(self, "base_subjects", None):
            self.base_subjects = list(self.selected_subjects) if self.selected_subjects else [g.get("category", "") for g in self.groups]
        # end if

        self.group_by_word = {}
        for g in self.groups:
            for w in g["words"]:
                self.group_by_word[w] = g
            # end for
        # end for

        all_words: list[str] = []
        for g in self.groups:
            all_words.extend(g["words"])
        # end for
        self.unsolved_words = list(all_words)

        render_board(self)
        try:
            self.root.geometry("")
        except Exception:
            pass
        # end try/except
        self.status.config(text="Restarted. Select 4 words, then Submit.")
    # end def _restart_same_categories  # _restart_same_categories

# end class PuzzleGame  # PuzzleGame
