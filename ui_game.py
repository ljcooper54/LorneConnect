# Copyright 2025 H2so4 Consulting LLC
from __future__ import annotations
"""Game UI."""

import tkinter as tk
from tkinter import messagebox
import random

from .constants import COLORS
from .utils import split_camel_case_display
from .db import DB
from .generator import PuzzleGenerator

class PuzzleGame:
    """Puzzle UI with hint + right-click flags + colored solved rows."""

    COLORS = {
        "yellow": "#f7e45c",
        "green": "#7bd389",
        "blue": "#6aa9ff",
        "purple": "#c07bff"
    }

    def __init__(self, root, user: str, db: DB, generator: PuzzleGenerator, puzzle_data: dict, on_done):
        self.root = root
        self.user = user
        self.db = db
        self.generator = generator
        self.on_done = on_done

        self.groups = puzzle_data["groups"]
        self.group_by_word = {w: g for g in self.groups for w in g["words"]}

        self.unsolved_words = [w for g in self.groups for w in g["words"]]
        random.shuffle(self.unsolved_words)

        self.selected_idxs: set[int] = set()
        self.solved_groups: list[dict] = []

        # Hint state
        self.hint_state = 0  # 0 => next click reveals category, 1 => next click reveals a tile
        self.hint_category = None
        self.hint_highlight_word = None

        self.frame = tk.Frame(root)
        self.frame.pack(padx=20, pady=20)

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

        self.play_again_btn = tk.Button(controls, text="Play Again", command=self.play_again)
        self.play_again_btn.pack(side=tk.LEFT, padx=6)

        self.quit_btn = tk.Button(controls, text="Quit", command=self.quit_game)
        self.quit_btn.pack(side=tk.LEFT, padx=6)

        self.tile_widgets: list[tk.Label] = []
        self.tile_base_bg: dict[int, str] = {}
        self._render()

    def _render(self):
        for w in self.solved_frame.winfo_children():
            w.destroy()
        for w in self.grid_frame.winfo_children():
            w.destroy()
        self.tile_widgets = []

        # solved rows at top
        for g in self.solved_groups:
            row = tk.Frame(self.solved_frame)
            row.pack(pady=(0, 6), fill=tk.X)

            header = tk.Label(row, text=g["category"], font=("Helvetica", 12, "bold"))
            header.pack(anchor="w")

            tiles_row = tk.Frame(row)
            tiles_row.pack()

            bg = self.COLORS.get(g["color"], "#d0d0d0")
            for wtxt in g["words"]:
                tk.Label(tiles_row, text=split_camel_case_display(wtxt), width=18, height=2, bg=bg, relief=tk.GROOVE)\
                  .pack(side=tk.LEFT, padx=3, pady=2)

        # remaining grid
        for i, wtxt in enumerate(self.unsolved_words):
            r = i // 4
            c = i % 4
            lbl = tk.Label(self.grid_frame, text=split_camel_case_display(wtxt), width=18, height=3,
                         relief=tk.RIDGE, bd=3, bg="white", font=("Helvetica", 13, "bold"), highlightthickness=0)
            lbl.grid(row=r, column=c, padx=5, pady=5, sticky="nsew")
            lbl.bind("<Button-1>", lambda e, idx=i: self.toggle(idx))
            lbl.bind("<Button-3>", lambda e, idx=i: self.on_right_click(e, idx))
            self.tile_widgets.append(lbl)
            self.tile_base_bg[i] = "white"
            # Right-click on macOS often maps to Control+Click or Button-2
            lbl.bind("<Control-Button-1>", lambda e, idx=i: self.on_right_click(e, idx))
            lbl.bind("<Button-2>", lambda e, idx=i: self.on_right_click(e, idx))

        self._refresh_selection_visual()
        self.root.update_idletasks()

    def _clear_hint(self):
        self.hint_state = 0
        self.hint_category = None
        # clear highlight
        if self.hint_highlight_word:
            try:
                idx = self.unsolved_words.index(self.hint_highlight_word)
                if 0 <= idx < len(self.tile_widgets) and idx not in self.selected_idxs:
                    self.tile_widgets[idx].config(bg="white")
            except ValueError:
                pass
        self.hint_highlight_word = None

    def toggle(self, idx: int):
        # any manual interaction clears hint highlight state
        self._clear_hint()

        if idx in self.selected_idxs:
            self.selected_idxs.remove(idx)
        else:
            if len(self.selected_idxs) < 4:
                self.selected_idxs.add(idx)
        self._refresh_selection_visual()

    def _refresh_selection_visual(self):
        for i, lbl in enumerate(self.tile_widgets):
            base_bg = self.tile_base_bg.get(i, "white")
            if i in self.selected_idxs:
                # Clear selection: thicker border + sunken relief. Avoid Tk focus highlight artifacts on macOS.
                lbl.config(relief=tk.SUNKEN, bg=base_bg, bd=6, highlightthickness=0)
            else:
                lbl.config(relief=tk.RIDGE, bg=base_bg, bd=3, highlightthickness=0)

    def _selected_words(self) -> list[str]:
        return [self.unsolved_words[i] for i in sorted(self.selected_idxs)]

    def check(self):
        if len(self.selected_idxs) != 4:
            messagebox.showinfo("Select", "Must select 4 words.")
            return

        selected = self._selected_words()
        for g in self.groups:
            if set(selected) == set(g["words"]) and g not in self.solved_groups:
                self._solve_group(g)
                return

        messagebox.showerror("Incorrect", "Not a correct group.")
        self.selected_idxs.clear()
        self._refresh_selection_visual()

    def _solve_group(self, group: dict):
        # Fix hint glitch: fully reset hint state on every successful solve
        self._clear_hint()
        self.status.config(text=f"Solved: {group['category']}")
        self.selected_idxs.clear()

        solved_set = set(group["words"])
        self.unsolved_words = [w for w in self.unsolved_words if w not in solved_set]

        self.solved_groups.append(group)
        self._render()
        self.root.update_idletasks()

        if len(self.solved_groups) == 4:
            self.db.inc_solved(self.user)
            self.status.config(text="You solved the puzzle! Click Play Again for a new one, or Quit.")

    def hint(self):
        unsolved_groups = [g for g in self.groups if g not in self.solved_groups]
        if not unsolved_groups:
            self.status.config(text="No hint available.")
            return

        selected_words = set(self._selected_words())

        # prefer categories with no selected members
        candidates = [g for g in unsolved_groups if not (selected_words & set(g["words"]))]
        if not candidates:
            candidates = unsolved_groups

        if self.hint_state == 0:
            g = random.choice(candidates)
            self.hint_category = g
            self.hint_state = 1
            self.status.config(text=f"Hint: {g['category']}")
            return

        # Second click: reveal a tile and ALSO select it for user
        g = self.hint_category or random.choice(candidates)
        available = [w for w in g["words"] if w in self.unsolved_words]
        if not available:
            self._clear_hint()
            self.status.config(text="No hint available.")
            return

        w = random.choice(available)
        self.hint_highlight_word = w
        self.hint_state = 0
        self.hint_category = None

        # color the tile
        try:
            idx = self.unsolved_words.index(w)
            if 0 <= idx < len(self.tile_widgets):
                self.tile_widgets[idx].config(bg=self.COLORS.get(g["color"], "#e6e6e6"))
                # Auto-select it (requirement)
                if len(self.selected_idxs) < 4:
                    self.selected_idxs.add(idx)
                self._refresh_selection_visual()
        except ValueError:
            pass

        self.root.update_idletasks()

    def on_right_click(self, event, idx: int):
        word = self.unsolved_words[idx]
        group = self.group_by_word.get(word, None)
        category = group["category"] if group else "Unknown Category"
        self.on_right_click_word(event, word, category)

    def on_right_click_word(self, event, word: str, category: str):
        menu = tk.Menu(self.root, tearoff=0)
        menu.add_command(label="Inappropriate", command=lambda: self._flag_inappropriate(word))
        menu.add_command(label="Wrong Category", command=lambda: self._flag_wrong_category(category, word))
        menu.add_command(label="Misspelled", command=lambda: self._flag_misspelled(category, word))
        menu.add_command(label="Very Hard", command=lambda: self._flag_very_hard(category, word))
        menu.tk_popup(event.x_root, event.y_root)

    def _flag_inappropriate(self, word: str):
        self.db.flag_inappropriate_for_user(self.user, word)
        messagebox.showinfo("Flagged", f"Banned for you (all categories):\n{split_camel_case_display(word)}")

    def _flag_wrong_category(self, category: str, word: str):
        self.db.flag_wrong_category(category, word)
        messagebox.showinfo("Flagged", f"Wrong Category (banned only for '{category}'):\n{split_camel_case_display(word)}")

    def _flag_misspelled(self, category: str, word: str):
        # Spinner while spellchecking
        spinner = tk.Toplevel(self.root)
        spinner.title("Checking…")
        spinner.geometry("240x80")
        spinner.transient(self.root)
        spinner.grab_set()

        lbl = tk.Label(spinner, text="Checking spelling...")
        lbl.pack(pady=18)

        q = queue.Queue()

        def worker():
            try:
                data = self.generator.check_spelling(word, category)
                q.put(("ok", data))
            except Exception as e:
                q.put(("err", str(e)))

        threading.Thread(target=worker, daemon=True).start()

        def poll():
            try:
                msg = q.get_nowait()
            except queue.Empty:
                self.root.after(120, poll)
                return

            spinner.destroy()

            if msg[0] == "err":
                messagebox.showerror("Spellcheck Error", msg[1])
                return

            data = msg[1]
            is_m = bool(data.get("is_misspelled", False))
            sug = data.get("suggestion", None)
            sug = normalize_token(sug) if sug else None

            self.db.flag_misspelled(category, word, 1 if is_m else 0, sug)

            if not is_m:
                messagebox.showinfo("Spellcheck", f"No misspelling detected:\n{split_camel_case_display(word)}")
            else:
                messagebox.showinfo("Spellcheck", f"Suggested spelling:\n{split_camel_case_display(word)} → {split_camel_case_display(sug) if sug else '(none)'}")

        poll()

    def _flag_very_hard(self, category: str, word: str):
        self.db.flag_very_hard(category, word)
        messagebox.showinfo("Flagged", f"Marked Very Hard (+1 obscurity):\n{split_camel_case_display(word)}")

# end class PuzzleGame
