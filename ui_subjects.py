# File: App/ui_subjects.py | Created/Modified: 2026-02-26
# Copyright 2025 H2so4 Consulting LLC
"""Choose Categories window.

Requirements:
- Eight rows
- Blank means "no category chosen"
- No "Category 1:" label
- No Clear button
- Surprise Me! stays literal in UI (resolved later)
- Categories button opens modal dialog listing existing categories and inserts selection
  into first empty row (or last row if all filled)
- Dialogs grab focus so they don’t get lost under other windows
"""

from __future__ import annotations

import tkinter as tk
from tkinter import messagebox

from .db import DB
from .utils import normalize_token

# Support either filename: ui_subjects_dialogs.py or ui_subjects_dialog.py. (Start)
try:
    from .ui_subjects_dialogs import show_categories_dialog
except Exception:  # pragma: no cover
    from .ui_subjects_dialog import show_categories_dialog  # type: ignore
# end try/except


# This SubjectWindow presents category entry boxes and helper buttons. (Start)
class SubjectWindow:
    """Category chooser UI."""

    ROWS = 8
    SURPRISE_LABEL = "Surprise Me!"

    # This initializes the chooser UI and loads recent subjects. (Start)
    def __init__(self, root: tk.Tk, user: str | None, db: DB, callback):
        self.root = root
        self.user = (user or "").strip()
        self.db = db
        self.callback = callback

        self.frame = tk.Frame(root)
        self.frame.pack(fill="both", expand=True, padx=16, pady=16)

        # Header (stats are best-effort). (Start)
        solved = 0
        try:
            stats = self.db.get_user_stats(self.user)
            solved = int(stats.get("won", 0))
        except Exception:
            pass
        # end try/except

        tk.Label(self.frame, text="Choose Categories", font=("Helvetica", 16, "bold")).grid(
            row=0, column=0, columnspan=3, sticky="w", pady=(0, 6)
        )
        tk.Label(self.frame, text=f"{self.user}, you've solved {solved} puzzles!", font=("Helvetica", 11)).grid(
            row=1, column=0, columnspan=3, sticky="w", pady=(0, 12)
        )
        # end header

        # Defaults (best-effort). (Start)
        try:
            defaults = self.db.get_subjects(self.user, limit=self.ROWS) or []
        except Exception:
            defaults = []
        # end try/except

        self.entries: list[tk.Entry] = []
        for r in range(self.ROWS):
            e = tk.Entry(self.frame, width=40)
            e.grid(row=2 + r, column=0, columnspan=3, sticky="w", pady=4)

            if r < len(defaults):
                d = (defaults[r] or "").strip()
                if d.casefold().replace(" ", "") in {"surpriseme!", "surpriseme"}:
                    d = self.SURPRISE_LABEL
                # end if
                e.insert(0, d)
            # end if

            self.entries.append(e)
        # end for

        # Buttons row. (Start)
        actions = tk.Frame(self.frame)
        actions.grid(row=2 + self.ROWS, column=0, columnspan=3, sticky="w", pady=(14, 0))

        self.play_btn = tk.Button(actions, text="Play", width=10, command=self.submit)
        self.play_btn.pack(side="left")

        self.surprise_btn = tk.Button(actions, text=self.SURPRISE_LABEL, width=14, command=self._surprise_me)
        self.surprise_btn.pack(side="left", padx=(8, 0))

        self.categories_btn = tk.Button(actions, text="Categories", width=12, command=self._open_categories)
        self.categories_btn.pack(side="left", padx=(8, 0))

        self.cancel_btn = tk.Button(actions, text="Cancel", width=10, command=self._cancel)
        self.cancel_btn.pack(side="left", padx=(18, 0))
        # end buttons row

        # Focus first entry so typing works immediately. (Start)
        self.root.after(80, lambda: self._focus_entry(0))
        # end focus
    # end def __init__  # __init__

    # This focuses an entry and selects its contents. (Start)
    def _focus_entry(self, idx: int) -> None:
        if 0 <= idx < len(self.entries):
            try:
                self.entries[idx].focus_force()
                self.entries[idx].selection_range(0, tk.END)
            except tk.TclError:
                pass
            # end try/except
        # end if
    # end def _focus_entry  # _focus_entry

    # This returns the first empty row index, else the last row index. (Start)
    def _first_empty_or_last(self) -> int:
        for i, e in enumerate(self.entries):
            if not normalize_token(e.get()):
                return i
            # end if
        # end for
        return len(self.entries) - 1
    # end def _first_empty_or_last  # _first_empty_or_last

    # This inserts text into the first empty slot (or last) and focuses it. (Start)
    def fill_and_focus(self, category: str) -> None:
        cat = (category or "").strip()
        if not cat:
            return
        # end if
        idx = self._first_empty_or_last()
        self.entries[idx].delete(0, tk.END)
        self.entries[idx].insert(0, cat)
        self._focus_entry(idx)
    # end def fill_and_focus  # fill_and_focus

    # This opens the Categories dialog (modal) and lets it call fill_and_focus. (Start)
    def _open_categories(self) -> None:
        show_categories_dialog(self)
    # end def _open_categories  # _open_categories

    # This inserts the literal Surprise Me! placeholder into first empty slot (or last). (Start)
    def _surprise_me(self) -> None:
        idx = self._first_empty_or_last()
        self.entries[idx].delete(0, tk.END)
        self.entries[idx].insert(0, self.SURPRISE_LABEL)
        self._focus_entry(idx)
    # end def _surprise_me  # _surprise_me

    # This gathers subjects preserving literal Surprise Me! and removing blanks/dupes. (Start)
    def _gather_subjects(self) -> list[str]:
        out: list[str] = []
        seen: set[str] = set()

        for e in self.entries:
            raw = (e.get() or "").strip()
            if not raw:
                continue
            # end if

            if raw.casefold().replace(" ", "") == "surpriseme!":
                key = self.SURPRISE_LABEL.casefold()
                if key not in seen:
                    seen.add(key)
                    out.append(self.SURPRISE_LABEL)
                # end if
                continue
            # end if

            norm = normalize_token(raw)
            if not norm:
                continue
            # end if

            k = norm.casefold()
            if k in seen:
                continue
            # end if
            seen.add(k)
            out.append(norm)
        # end for

        return out
    # end def _gather_subjects  # _gather_subjects

    # This disables the chooser during generation. (Start)
    def disable(self) -> None:
        for e in self.entries:
            e.config(state="disabled")
        # end for
        self.play_btn.config(state="disabled")
        self.surprise_btn.config(state="disabled")
        self.categories_btn.config(state="disabled")
        self.cancel_btn.config(state="disabled")
    # end def disable  # disable

    # This re-enables the chooser. (Start)
    def enable(self) -> None:
        for e in self.entries:
            e.config(state="normal")
        # end for
        self.play_btn.config(state="normal")
        self.surprise_btn.config(state="normal")
        self.categories_btn.config(state="normal")
        self.cancel_btn.config(state="normal")
    # end def enable  # enable

    # This submits the chosen categories and persists them as history. (Start)
    def submit(self) -> None:
        subjects = self._gather_subjects()
        if not subjects:
            messagebox.showerror("No Categories", "Please enter at least one category.", parent=self.root)
            self._focus_entry(0)
            return
        # end if

        try:
            self.db.add_subjects(self.user, subjects)
        except Exception:
            pass
        # end try/except

        self.disable()
        self.callback(subjects, self)
    # end def submit  # submit

    # This cancels category selection and returns to caller. (Start)
    def _cancel(self) -> None:
        self.callback([], self)
    # end def _cancel  # _cancel

    # This destroys the chooser frame. (Start)
    def destroy(self) -> None:
        try:
            self.frame.destroy()
        except tk.TclError:
            pass
        # end try/except
    # end def destroy  # destroy

# end class SubjectWindow  # SubjectWindow
